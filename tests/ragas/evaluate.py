"""
RAGAS Evaluation Script for RAG Chatbot.

이 스크립트는 RAG 챗봇의 성능을 RAGAS 프레임워크로 평가합니다.

사용법:
    python -m tests.ragas.evaluate

사전 준비:
    1. tests/ragas/datasets/novel_qa.json 파일 작성
    2. 환경 변수 설정 (.env 파일)
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)
from datasets import Dataset

from app.services.embedding_service import embedding_service
from app.services.unified_search_service import unified_search_service
from app.services.chat_service import chat_service
from app.config import settings


def load_test_dataset(file_path: str) -> List[Dict[str, Any]]:
    """테스트 데이터셋 로드."""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


async def collect_rag_data(
    question: str,
    project_id: str,
) -> Dict[str, Any]:
    """단일 질문에 대해 RAG 파이프라인 실행 및 데이터 수집."""
    
    # 1. 임베딩 생성
    loop = asyncio.get_event_loop()
    query_embedding = await loop.run_in_executor(
        None,
        embedding_service.get_embedding,
        question
    )
    
    # 2. 컨텍스트 검색
    search_results = await unified_search_service.search(
        project_id=project_id,
        query_embedding=query_embedding,
        query_text=question
    )
    
    # 3. 컨텍스트 텍스트 추출
    contexts = []
    for section in search_results.get("sections", []):
        contexts.append(section.get("content", ""))
    for char in search_results.get("characters", []):
        contexts.append(f"{char.get('name', '')}: {char.get('backstory', '')}")
    for event in search_results.get("events", []):
        contexts.append(event.get("narrative_summary", ""))
    
    # 4. LLM 응답 생성 (비스트리밍)
    from langchain.schema import HumanMessage, SystemMessage
    
    context_text = "\n".join(contexts[:5])
    system_prompt = f"""당신은 소설 작품 전용 AI 어시스턴트입니다.
아래 제공된 컨텍스트에 있는 정보만을 기반으로 답변해주세요.

Context:
{context_text}
"""
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=question)
    ]
    
    response = await chat_service.llm.ainvoke(messages)
    
    return {
        "question": question,
        "answer": response.content,
        "contexts": contexts[:5],  # 상위 5개 컨텍스트
    }


async def run_evaluation(
    dataset_path: str,
    project_id: str,
    output_path: str = None,
):
    """RAGAS 평가 실행."""
    
    print(f"📂 Loading dataset from: {dataset_path}")
    test_data = load_test_dataset(dataset_path)
    print(f"📝 Loaded {len(test_data)} test cases")
    
    # 평가 데이터 수집
    eval_data = {
        "question": [],
        "answer": [],
        "contexts": [],
        "ground_truth": [],
    }
    
    print("\n🔄 Collecting RAG responses...")
    for i, item in enumerate(test_data):
        print(f"  [{i+1}/{len(test_data)}] {item['question'][:50]}...")
        
        result = await collect_rag_data(
            question=item["question"],
            project_id=project_id
        )
        
        eval_data["question"].append(result["question"])
        eval_data["answer"].append(result["answer"])
        eval_data["contexts"].append(result["contexts"])
        eval_data["ground_truth"].append(item.get("ground_truth", ""))
    
    print("\n📊 Running RAGAS evaluation...")
    
    # RAGAS 평가 실행
    dataset = Dataset.from_dict(eval_data)
    
    result = evaluate(
        dataset,
        metrics=[
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall,
        ],
    )
    
    print("\n" + "=" * 50)
    print("📈 RAGAS Evaluation Results")
    print("=" * 50)
    print(result)
    
    # 결과 저장
    if output_path:
        result_dict = {
            "metrics": dict(result),
            "details": eval_data,
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result_dict, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Results saved to: {output_path}")
    
    return result


if __name__ == "__main__":
    # 기본 설정
    DATASET_PATH = Path(__file__).parent / "datasets" / "novel_qa.json"
    OUTPUT_PATH = Path(__file__).parent / "results" / "evaluation_result.json"
    PROJECT_ID = os.getenv("TEST_PROJECT_ID", "test-project")
    
    # 결과 폴더 생성
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    if not DATASET_PATH.exists():
        print("❌ Error: Dataset file not found!")
        print(f"   Please create: {DATASET_PATH}")
        print("\n   Expected format:")
        print('   [{"question": "질문", "ground_truth": "정답"}, ...]')
        sys.exit(1)
    
    # 평가 실행
    asyncio.run(run_evaluation(
        dataset_path=str(DATASET_PATH),
        project_id=PROJECT_ID,
        output_path=str(OUTPUT_PATH),
    ))
