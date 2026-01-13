"""Chat Service - Bedrock Claude 3 Haiku + Multi-Source RAG.

AWS Bedrock Claude를 사용하여 소설 관련 질문에 응답합니다.
검색 소스: sections(벡터) + characters(텍스트) + events(텍스트)
"""

from app.services.embedding_service import embedding_service
from app.services.unified_search_service import unified_search_service
from app.services.redis_service import redis_service
from app.services.postgres_service import postgres_service
from app.services.neo4j_service import neo4j_service
from app.config import settings

from langchain_aws import ChatBedrock
from langchain.schema import HumanMessage, SystemMessage, AIMessage
from typing import AsyncGenerator, Dict, Any, List, Tuple, Optional
import json
import asyncio
import logging
import boto3

logger = logging.getLogger(__name__)

# 관계 질문 감지용 키워드
RELATIONSHIP_KEYWORDS = [
    "관계", "사이", "어떻게 생각", "친구", "적", "연인", "가족",
    "과의", "와의", "랑", "하고", "둘", "두 사람", "그들",
    "친한지", "싫어", "좋아", "원수", "동료", "형제", "자매"
]


def detect_relationship_context(
    search_results: Dict[str, Any],
    query: str
) -> Optional[Tuple[Dict, Dict]]:
    """RAG 검색 결과에서 관계 질문 여부를 감지.
    
    Returns:
        (캐릭터1 정보, 캐릭터2 정보) 또는 None
    """
    # Step 1: 키워드 프리필터
    if not any(kw in query for kw in RELATIONSHIP_KEYWORDS):
        return None
    
    # Step 2: 2명 이상의 캐릭터가 검색되었는지 확인
    characters = search_results.get("characters", [])
    if len(characters) < 2:
        return None
    
    # Step 3: 쿼리에 두 캐릭터 이름이 모두 언급되었는지 확인
    char1, char2 = characters[0], characters[1]
    query_lower = query.lower()
    
    if char1["name"].lower() in query_lower and char2["name"].lower() in query_lower:
        return (char1, char2)
    
    return None


class ChatService:
    """Bedrock Claude 기반 챗봇 서비스."""
    
    def __init__(self):
        # Bedrock 클라이언트 설정
        # 1. 표준 AWS 환경변수 사용
        aws_access_key = settings.AWS_ACCESS_KEY_ID or settings.AWS_BEDROCK_API_KEY_ID
        aws_secret_key = settings.AWS_SECRET_ACCESS_KEY or settings.AWS_BEDROCK_API_KEY_SECRET
        
        bedrock_client = boto3.client(
            "bedrock-runtime",
            region_name=settings.AWS_DEFAULT_REGION,
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
        )
        
        self.llm = ChatBedrock(
            client=bedrock_client,
            model_id=settings.AWS_BEDROCK_MODEL_ID,
            streaming=True,
            model_kwargs={
                "max_tokens": 4096,
                "temperature": 0.7
            }
        )
        logger.info(f"ChatService initialized with {settings.AWS_BEDROCK_MODEL_ID}")

    def _format_multi_source_context(self, search_results: Dict[str, Any]) -> str:
        """Multi-Source 검색 결과를 프롬프트용 컨텍스트로 포맷."""
        parts = []

        # 1. 본문 맥락 (가장 중요)
        sections = search_results.get("sections", [])
        if sections:
            parts.append("=== 소설 본문 ===")
            for s in sections[:5]:
                title = s.get("nav_title", "Section")
                score = s.get("score", 0)
                content = s["content"][:800] if len(s["content"]) > 800 else s["content"]
                
                # 관련 캐릭터/이벤트 표시
                meta = []
                if s.get("related_characters"):
                    meta.append(f"인물: {', '.join(s['related_characters'][:3])}")
                meta_str = f" ({', '.join(meta)})" if meta else ""
                
                parts.append(f"[{title}]{meta_str}\n{content}")

        # 2. 캐릭터 정보
        characters = search_results.get("characters", [])
        if characters:
            parts.append("\n=== 관련 캐릭터 ===")
            for c in characters:
                name = c.get("name", "Unknown")
                role = c.get("role", "")
                backstory = c.get("backstory", "")[:300] if c.get("backstory") else ""
                description = c.get("description", "")[:200] if c.get("description") else ""
                
                char_info = f"- {name}"
                if role:
                    char_info += f" ({role})"
                if backstory:
                    char_info += f": {backstory}"
                elif description:
                    char_info += f": {description}"
                
                parts.append(char_info)

        # 3. 이벤트 정보
        events = search_results.get("events", [])
        if events:
            parts.append("\n=== 관련 사건 ===")
            for e in events:
                event_info = e.get("narrative_summary") or e.get("description") or e.get("name", "")
                if event_info:
                    parts.append(f"- {event_info[:300]}")

        return "\n".join(parts)

    def _build_sources_response(self, search_results: Dict[str, Any]) -> Dict[str, Any]:
        """소스 정보를 클라이언트용 JSON으로 변환."""
        sources = []
        
        for s in search_results.get("sections", [])[:5]:
            sources.append({
                "id": s.get("section_id", ""),
                "content": s["content"][:200] + "..." if len(s["content"]) > 200 else s["content"],
                "score": round(s.get("score", 0), 4),
                "source": "sections",
                "source_type": "section"
            })
        
        for c in search_results.get("characters", []):
            sources.append({
                "id": c.get("id", ""),
                "content": f"{c.get('name', 'Unknown')}: {c.get('backstory', '')[:150]}",
                "source": "characters",
                "source_type": "character"
            })
        
        for e in search_results.get("events", []):
            sources.append({
                "id": e.get("id", ""),
                "content": e.get("narrative_summary", e.get("name", ""))[:150],
                "source": "events",
                "source_type": "event"
            })
        
        return {"type": "sources", "sources": sources}

    async def chat_stream(
        self,
        message: str,
        project_id: str,
        session_id: str,
        user_id: str = None
    ) -> AsyncGenerator[str, None]:
        """스트리밍 채팅 응답 생성."""
        
        # 0. Save User Message to History (Redis + PostgreSQL)
        await redis_service.add_message_to_history(session_id, "user", message)
        # PostgreSQL 영구 저장 (fire-and-forget)
        asyncio.create_task(postgres_service.save_chat_log(
            project_id=project_id,
            session_id=session_id,
            user_id=user_id,
            role="user",
            content=message
        ))

        # 0.5 Intent Classification (Guardrail)
        intent_prompt = [
            SystemMessage(content="""You are an intent classifier for a novel chatbot.
Classify if the user's query is related to the novel (plot, characters, setting, or casual greeting) or if it is Out-of-Domain (general knowledge, coding, math, real-world news).
Reply with 'Y' if related/safe, 'N' if Out-of-Domain."""),
            HumanMessage(content=message)
        ]
        intent_check = await self.llm.ainvoke(intent_prompt)
        if intent_check.content.strip().upper().startswith('N'):
            refusal_msg = "소설 내용에 관련된 질문만 답변드릴 수 있습니다."
            yield f"data: {json.dumps({'type': 'token', 'content': refusal_msg})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            await redis_service.add_message_to_history(session_id, "ai", refusal_msg)
            return

        # 1. Embed Query (Gemini 3072차원)
        loop = asyncio.get_event_loop()
        query_embedding = await loop.run_in_executor(
            None,
            embedding_service.get_embedding,
            message
        )

        # 2. Multi-Source 검색 (sections + characters + events)
        search_results = await unified_search_service.search(
            project_id=project_id,
            query_embedding=query_embedding,
            query_text=message
        )
        
        # DEBUG: 검색 결과 로그
        logger.info(f"Search results - sections: {len(search_results.get('sections', []))}, "
                    f"characters: {len(search_results.get('characters', []))}, "
                    f"events: {len(search_results.get('events', []))}")
        if search_results.get('characters'):
            logger.info(f"Characters found: {[c['name'] for c in search_results['characters']]}")

        # 3. Format Context
        context_text = self._format_multi_source_context(search_results)
        
        # DEBUG: LLM에 전달되는 컨텍스트 확인
        logger.info(f"Context text length: {len(context_text)}")
        if context_text:
            logger.info(f"Context preview: {context_text[:500]}...")

        # 4. Send sources to client
        sources_data = self._build_sources_response(search_results)
        yield f"data: {json.dumps(sources_data)}\n\n"

        # 4.5 관계 카드 생성 (조건부)
        relationship_pair = detect_relationship_context(search_results, message)
        if relationship_pair:
            char1, char2 = relationship_pair
            relationship_data = neo4j_service.get_relationship_between(
                project_id, char1["id"], char2["id"]
            )
            
            if relationship_data:
                card_event = {
                    "type": "cards",
                    "cards": [{
                        "cardType": "relationship",
                        "data": {
                            "sourceCharacter": {
                                "id": char1["id"],
                                "name": char1["name"],
                            },
                            "targetCharacter": {
                                "id": char2["id"],
                                "name": char2["name"],
                            },
                            "types": relationship_data["types"],
                            "strength": relationship_data["strength"],
                            "description": relationship_data["description"],
                            "bidirectional": relationship_data["bidirectional"],
                            "since": relationship_data["since"]
                        },
                        "actionUrl": f"/projects/{project_id}/world/characters?relationship={relationship_data['id']}"
                    }]
                }
                yield f"data: {json.dumps(card_event)}\n\n"
                logger.info(f"Relationship card generated: {char1['name']} <-> {char2['name']}")

        # 5. Construct Prompt
        # Context가 비어있는 경우 처리
        if not context_text or context_text.strip() == "":
            context_text = "(검색된 정보 없음)"
            logger.warning(f"Empty context for message: {message}")
        
        system_prompt = f"""당신은 소설 작품 전용 AI 어시스턴트입니다.

**핵심 규칙:**
1. 아래 Context에 있는 정보를 **반드시 우선적으로** 사용하세요.
2. Context에 캐릭터 정보가 있다면 그 내용을 직접 인용하여 답변하세요.
3. 답변은 **2-3문장**으로 간결하게 작성하세요.
4. 정보가 없을 때만 "정보가 없습니다"라고 짧게 말하세요.
5. 불필요한 사과나 긴 설명은 피하세요.

Context:
{context_text}
"""

        messages = [SystemMessage(content=system_prompt)]

        # 6. Retrieve History from Redis
        history = await redis_service.get_session_history(session_id)
        for msg in history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "ai":
                messages.append(AIMessage(content=msg["content"]))

        # 7. Setup Stop Listener
        pubsub = await redis_service.create_stop_listener(session_id)

        full_response = ""

        # 8. Generate Streaming Response
        try:
            async for chunk in self.llm.astream(messages):
                # Check for stop signal
                msg = await pubsub.get_message(ignore_subscribe_messages=True)
                if msg and msg['data'] == 'STOP':
                    yield f"data: {json.dumps({'type': 'error', 'error': 'Generation stopped by user'})}\n\n"
                    full_response = ""
                    break

                if chunk.content:
                    token_data = {
                        "type": "token",
                        "content": chunk.content
                    }
                    yield f"data: {json.dumps(token_data)}\n\n"
                    full_response += chunk.content

            # Done signal
            if full_response:
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                await redis_service.add_message_to_history(session_id, "ai", full_response)
                # PostgreSQL 영구 저장 (fire-and-forget)
                asyncio.create_task(postgres_service.save_chat_log(
                    project_id=project_id,
                    session_id=session_id,
                    user_id=user_id,
                    role="ai",
                    content=full_response,
                    sources=sources_data.get("sources")
                ))

        except Exception as e:
            logger.error(f"Chat stream error: {e}")
            error_data = {
                "type": "error",
                "error": str(e)
            }
            yield f"data: {json.dumps(error_data)}\n\n"
        finally:
            await pubsub.close()


chat_service = ChatService()
