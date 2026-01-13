#!/usr/bin/env python3
"""
RAGAS 스타일 챗봇 테스트 스크립트

사용법:
    python tests/ragas/run_test.py --project-id 00000000-0000-0000-0000-000000000001
"""

import json
import asyncio
import httpx
import argparse
from pathlib import Path
from typing import Optional


# 설정
API_BASE_URL = "http://localhost:8000"
CHAT_ENDPOINT = "/ai-api/chat/stream"


async def send_chat_message(
    client: httpx.AsyncClient,
    message: str,
    project_id: str,
    user_id: str,
    session_id: str,
    token: Optional[str] = None,
) -> str:
    """챗봇에 메시지를 보내고 응답을 받습니다."""
    
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    payload = {
        "message": message,
        "project_id": project_id,
        "user_id": user_id,
        "session_id": session_id,
    }
    
    try:
        response_text = ""
        async with client.stream("POST", f"{API_BASE_URL}{CHAT_ENDPOINT}", 
                                  json=payload, headers=headers, timeout=60.0) as response:
            if response.status_code != 200:
                return f"[ERROR] HTTP {response.status_code}"
            
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    if data.get("type") == "token":
                        response_text += data.get("content", "")
                    elif data.get("type") == "done":
                        break
        
        return response_text.strip()
    except Exception as e:
        return f"[ERROR] {str(e)}"


async def run_test(
    dataset_path: str,
    project_id: str,
    user_id: str,
    token: Optional[str] = None,
    limit: int = 5,
):
    """데이터셋 기반 테스트 실행"""
    
    # 데이터셋 로드
    with open(dataset_path, "r", encoding="utf-8") as f:
        qa_data = json.load(f)
    
    print(f"\n{'='*60}")
    print(f"🧪 RAGAS 테스트 시작")
    print(f"📂 데이터셋: {dataset_path}")
    print(f"🔑 프로젝트: {project_id}")
    print(f"📊 테스트 개수: {min(limit, len(qa_data))}")
    print(f"{'='*60}\n")
    
    results = []
    session_id = f"ragas-test-{project_id[:8]}"
    
    async with httpx.AsyncClient() as client:
        for i, qa in enumerate(qa_data[:limit]):
            question = qa["question"]
            expected = qa["ground_truth"]
            
            print(f"\n[{i+1}/{min(limit, len(qa_data))}] 질문: {question}")
            print("-" * 40)
            
            # 챗봇 응답 받기
            answer = await send_chat_message(
                client=client,
                message=question,
                project_id=project_id,
                user_id=user_id,
                session_id=session_id,
                token=token,
            )
            
            print(f"🤖 챗봇 응답: {answer[:200]}{'...' if len(answer) > 200 else ''}")
            print(f"✅ 정답: {expected}")
            
            # 간단한 매칭 (실제 RAGAS는 더 정교한 평가 수행)
            # 정답의 핵심 키워드가 응답에 포함되어 있는지 확인
            keywords = expected.split()[:3]  # 첫 3개 단어
            match_count = sum(1 for kw in keywords if kw in answer)
            similarity = match_count / len(keywords) if keywords else 0
            
            results.append({
                "question": question,
                "expected": expected,
                "answer": answer,
                "keyword_match": similarity,
            })
            
            if similarity > 0.5:
                print(f"📊 평가: ✅ 관련성 있음 (키워드 매칭: {similarity:.0%})")
            else:
                print(f"📊 평가: ⚠️ 검토 필요 (키워드 매칭: {similarity:.0%})")
    
    # 요약
    print(f"\n{'='*60}")
    print("📈 테스트 요약")
    print(f"{'='*60}")
    
    total = len(results)
    good = sum(1 for r in results if r["keyword_match"] > 0.5)
    errors = sum(1 for r in results if r["answer"].startswith("[ERROR]"))
    
    print(f"✅ 관련성 있는 응답: {good}/{total} ({good/total*100:.1f}%)")
    print(f"⚠️ 검토 필요: {total - good - errors}/{total}")
    print(f"❌ 에러: {errors}/{total}")
    
    # 결과 저장
    result_path = Path(dataset_path).parent / "test_results.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n💾 결과 저장: {result_path}")


def main():
    parser = argparse.ArgumentParser(description="RAGAS 스타일 챗봇 테스트")
    parser.add_argument("--project-id", required=True, help="프로젝트 ID")
    parser.add_argument("--user-id", default="test-user-001", help="사용자 ID")
    parser.add_argument("--token", default=None, help="인증 토큰 (선택)")
    parser.add_argument("--dataset", default="tests/ragas/datasets/cyberpunk_qa.json", 
                        help="데이터셋 경로")
    parser.add_argument("--limit", type=int, default=5, help="테스트할 질문 개수")
    
    args = parser.parse_args()
    
    asyncio.run(run_test(
        dataset_path=args.dataset,
        project_id=args.project_id,
        user_id=args.user_id,
        token=args.token,
        limit=args.limit,
    ))


if __name__ == "__main__":
    main()
