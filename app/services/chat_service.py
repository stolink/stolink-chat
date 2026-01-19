"""Chat Service - 고급 RAG 기반 소설 어시스턴트.

주요 기능:
1. Multi-Source RAG 검색 (sections + characters + events)
2. 캐릭터 페르소나 대화 모드 (@캐릭터명)
3. 일관성 검증 및 알림
4. 관계 카드 생성
"""

from app.services.embedding_service import embedding_service
from app.services.unified_search_service import unified_search_service
from app.services.redis_service import redis_service
from app.services.postgres_service import postgres_service
from app.services.neo4j_service import neo4j_service
from app.services.persona_service import persona_service, PersonaContext
from app.services.consistency_service import consistency_service
from app.config import settings

from langchain_aws import ChatBedrock
from langchain.schema import HumanMessage, SystemMessage, AIMessage
from typing import AsyncGenerator, Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import json
import asyncio
import logging
import boto3

logger = logging.getLogger(__name__)


class ChatMode(Enum):
    """채팅 모드."""
    NORMAL = "normal"           # 일반 어시스턴트 모드
    PERSONA = "persona"         # 캐릭터 페르소나 모드
    CONSISTENCY = "consistency" # 일관성 검증 모드


@dataclass
class ChatContext:
    """채팅 컨텍스트."""
    mode: ChatMode
    persona_context: Optional[PersonaContext] = None
    search_results: Optional[Dict[str, Any]] = None
    conflicts: Optional[List] = None
    original_message: str = ""
    processed_message: str = ""
    injected_data: Optional[Dict[str, Any]] = None


# 관계 질문 감지용 키워드
RELATIONSHIP_KEYWORDS = [
    "관계", "사이", "어떻게 생각", "친구", "적", "연인", "가족",
    "과의", "와의", "랑", "하고", "둘", "두 사람", "그들",
    "친한지", "싫어", "좋아", "원수", "동료", "형제", "자매"
]


class ChatService:
    """고급 소설 어시스턴트 서비스."""

    def __init__(self):
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

    async def _analyze_intent(self, message: str) -> Tuple[ChatMode, Optional[str]]:
        """사용자 의도 분석.

        Returns:
            (ChatMode, 캐릭터이름 또는 None)
        """
        # 1. 페르소나 요청 감지
        character_name = persona_service.detect_persona_request(message)
        if character_name:
            return ChatMode.PERSONA, character_name

        # 2. 일관성 검증 요청 감지
        consistency_keywords = ["일관성", "설정 충돌", "모순", "오류 있", "체크해"]
        if any(kw in message for kw in consistency_keywords):
            return ChatMode.CONSISTENCY, None

        return ChatMode.NORMAL, None

    async def _build_context(
        self,
        message: str,
        project_id: str,
        mode: ChatMode,
        character_name: Optional[str] = None,
        context_data: Optional[Dict[str, Any]] = None
    ) -> ChatContext:
        """채팅 컨텍스트 구축."""
        context = ChatContext(
            mode=mode,
            original_message=message,
            processed_message=message,
            injected_data=context_data
        )

        # Inject explicit conflicts immediately
        if context_data and context_data.get("conflicts"):
             context.conflicts = context_data["conflicts"]

        # 페르소나 모드: 캐릭터 정보 로드
        if mode == ChatMode.PERSONA and character_name:
            persona_ctx = await persona_service.build_persona_context(
                project_id, character_name
            )
            if persona_ctx:
                context.persona_context = persona_ctx
                context.processed_message = persona_service.strip_persona_mention(
                    message, character_name
                )
            else:
                # 캐릭터를 찾지 못하면 일반 모드로 전환
                context.mode = ChatMode.NORMAL
                logger.warning(f"Character not found: {character_name}, falling back to normal mode")

        return context

    async def _search_and_enrich(
        self,
        context: ChatContext,
        project_id: str
    ) -> ChatContext:
        """검색 및 컨텍스트 강화."""
        loop = asyncio.get_event_loop()

        # 1. 쿼리 임베딩 생성
        query_embedding = await loop.run_in_executor(
            None,
            embedding_service.get_embedding,
            context.processed_message
        )

        # 2. Multi-Source 검색
        search_results = await unified_search_service.search(
            project_id=project_id,
            query_embedding=query_embedding,
            query_text=context.processed_message
        )
        context.search_results = search_results

        # 3. 관련 일관성 충돌 조회
        character_names = [c.get("name") for c in search_results.get("characters", [])]
        if context.persona_context:
            character_names.append(context.persona_context.character.get("name"))

        conflicts = await consistency_service.get_relevant_conflicts(
            project_id, context.processed_message, character_names
        )
        if conflicts:
            context.conflicts = conflicts

        return context

    def _build_system_prompt(self, context: ChatContext, project_id: str) -> str:
        """컨텍스트 기반 System Prompt 생성."""

        # 페르소나 모드
        if context.mode == ChatMode.PERSONA and context.persona_context:
            return persona_service.generate_persona_prompt(context.persona_context)

        # 일반/일관성 모드: RAG 기반 프롬프트
        search_results = context.search_results or {}
        context_text = self._format_rich_context(search_results)
        consistency_text = ""

        if context.conflicts:
            consistency_text = "\n\n" + consistency_service.format_conflicts_for_prompt(
                context.conflicts
            )

        if context.injected_data:
            injected_text = self._format_injected_context(context.injected_data)
            if injected_text:
                context_text = injected_text + "\n\n" + context_text

        return f"""당신은 소설 작품 전용 AI 어시스턴트입니다.
작가의 '세컨드 브레인'으로서 소설 세계관, 캐릭터, 스토리에 대해 정확하고 통찰력 있는 답변을 제공합니다.

## 핵심 원칙
1. **정확성**: 아래 Context의 정보를 최우선으로 사용합니다.
2. **일관성**: 캐릭터 설정, 시간대, 장소가 일관되게 유지되도록 합니다.
3. **통찰력**: 단순 정보 제공을 넘어 창작에 도움이 되는 인사이트를 제공합니다.
4. **간결함**: 핵심을 담은 2-4문장으로 답변합니다.

## Context
{context_text}
{consistency_text}

## 답변 스타일
- 캐릭터 언급 시: 이름과 함께 핵심 특성을 간단히 언급
- 이벤트 언급 시: 시간순서와 인과관계 명확히
- 불확실한 정보: "작품 내 명시되지 않았지만..." 형식으로 구분
- 설정 충돌 발견 시: 명확히 알림
"""

    def _get_attr(self, obj: Any, attr: str, default: Any = None) -> Any:
        """객체 속성 또는 딕셔너리 키 값 안전하게 조회."""
        if isinstance(obj, dict):
            return obj.get(attr, default)
        return getattr(obj, attr, default)

    def _format_injected_context(self, injected_data: Dict[str, Any]) -> str:
        """사용자가 직접 언급한(태그한) 정보 포맷팅."""
        parts = []

        # Characters
        if injected_data.get("characters"):
            parts.append("### 🏷️ 언급된 캐릭터 (User Mentioned)")
            for c in injected_data["characters"]:
                # Frontend Character object structure safety check
                profile = self._get_attr(c, "profile", {})
                
                # Check profile type safely
                if isinstance(profile, dict):
                    name = profile.get("name", "Unknown")
                else:
                    name = getattr(profile, "name", "Unknown")
                    
                # Fallback to direct name attribute if profile lookup failed/empty
                if name == "Unknown":
                    name = self._get_attr(c, "name", "Unknown")
                    
                role = self._get_attr(c, "role", "")
                parts.append(f"- **{name}** ({role})")
            parts.append("")

        # Events
        if injected_data.get("events"):
            parts.append("### 🏷️ 언급된 사건 (User Mentioned)")
            for e in injected_data["events"]:
                summary = (self._get_attr(e, "narrative_summary") or 
                          self._get_attr(e, "narrativeSummary") or 
                          self._get_attr(e, "description") or 
                          self._get_attr(e, "event_type", "Event"))
                parts.append(f"- {summary}")
            parts.append("")

        return "\n".join(parts)

    def _format_rich_context(self, search_results: Dict[str, Any]) -> str:
        """풍부한 컨텍스트 포맷팅."""
        parts = []

        # 1. 본문 맥락 (가장 중요)
        sections = search_results.get("sections", [])
        if sections:
            parts.append("### 📖 관련 본문")
            for s in sections[:3]:
                if not s or not isinstance(s, dict):
                    continue
                title = s.get("nav_title", "Section")
                score = s.get("score", 0)
                content = s.get("content", "")[:600] if s.get("content") else ""

                # 신뢰도 표시
                confidence = "높음" if score >= 0.7 else "중간" if score >= 0.5 else "낮음"

                meta_parts = [f"신뢰도: {confidence}"]
                if s.get("related_characters"):
                    meta_parts.append(f"등장인물: {', '.join(s['related_characters'][:3])}")

                parts.append(f"**[{title}]** ({', '.join(meta_parts)})")
                parts.append(f"> {content}")
                parts.append("")

        # 2. 캐릭터 정보
        characters = search_results.get("characters", [])
        if characters:
            parts.append("### 👤 관련 캐릭터")
            for c in characters[:4]:
                if not c or not isinstance(c, dict):
                    continue
                name = c.get("name", "Unknown")
                role = c.get("role", "")
                role_emoji = {"protagonist": "⭐", "antagonist": "💀", "supporting": "👥"}.get(role, "")

                char_line = f"- **{name}** {role_emoji}"
                if c.get("backstory"):
                    char_line += f": {c['backstory'][:150]}..."
                parts.append(char_line)
            parts.append("")

        # 3. 관련 이벤트
        events = search_results.get("events", [])
        if events:
            parts.append("### 📅 관련 사건")
            for e in events[:3]:
                if not e or not isinstance(e, dict):
                    continue
                event_type = e.get("event_type", "")
                desc = e.get("narrative_summary") or e.get("description", "")
                if desc:
                    chapter = e.get("chapter")
                    chapter_str = f"[{chapter}장] " if chapter else ""
                    parts.append(f"- {chapter_str}{desc[:200]}")
            parts.append("")

        if not parts:
            return "(관련 정보를 찾지 못했습니다)"

        return "\n".join(parts)

    def _build_sources_response(self, context: ChatContext) -> Dict[str, Any]:
        """소스 정보 응답 생성."""
        search_results = context.search_results or {}
        sources = []

        # Sections
        for s in search_results.get("sections", [])[:5]:
            if not s or not isinstance(s, dict):
                continue
            sources.append({
                "id": s.get("section_id", ""),
                "content": s.get("content", "")[:200] + "..." if s.get("content") else "",
                "score": round(s.get("score", 0), 4),
                "source": "sections",
                "source_type": "section"
            })

        # Characters
        for c in search_results.get("characters", []):
            if not c or not isinstance(c, dict):
                continue
            sources.append({
                "id": c.get("id", ""),
                "content": f"{c.get('name', 'Unknown')}: {c.get('backstory', '')[:150]}",
                "source": "characters",
                "source_type": "character"
            })

        # Events
        for e in search_results.get("events", []):
            if not e or not isinstance(e, dict):
                continue
            sources.append({
                "id": e.get("id", ""),
                "content": e.get("narrative_summary", e.get("description", ""))[:150],
                "source": "events",
                "source_type": "event"
            })

        return {"type": "sources", "sources": sources}

    async def chat_stream(
        self,
        message: str,
        project_id: str,
        session_id: str,
        user_id: str = None,
        context_data: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[str, None]:
        """스트리밍 채팅 응답 생성."""
        collected_cards = []

        # 0. 사용자 메시지 저장
        await redis_service.add_message_to_history(session_id, "user", message)
        asyncio.create_task(postgres_service.save_chat_log(
            project_id=project_id,
            session_id=session_id,
            user_id=user_id,
            role="user",
            content=message
        ))

        # 1. 의도 분석
        mode, character_name = await self._analyze_intent(message)
        logger.info(f"Chat mode: {mode.value}, character: {character_name}")

        # 2. 컨텍스트 구축
        context = await self._build_context(message, project_id, mode, character_name, context_data)

        # 3. 페르소나 모드: 카드 전송
        if context.mode == ChatMode.PERSONA and context.persona_context:
            persona_card = persona_service.generate_persona_card(context.persona_context)
            if persona_card.get("cards"):
                collected_cards.extend(persona_card["cards"])
            yield f"data: {json.dumps(persona_card)}\n\n"

        # 4. Intent Classification (Out-of-Domain 필터링) - 페르소나 모드 제외
        if context.mode != ChatMode.PERSONA:
            intent_prompt = [
                SystemMessage(content="""You are an intent classifier for a novel chatbot.
Classify if the user's query is related to the novel (plot, characters, setting, writing advice) or **consistency reports/conflicts**.
Reply with 'Y' if related/safe, 'N' if Out-of-Domain.
"Report" or "Conflict" questions are IN-DOMAIN."""),
                HumanMessage(content=context.processed_message)
            ]
            intent_check = await self.llm.ainvoke(intent_prompt)
            if intent_check.content.strip().upper().startswith('N'):
                refusal_msg = "소설 내용이나 창작 관련 질문에 답변드릴 수 있습니다. 다른 질문이 있으시면 말씀해주세요."
                yield f"data: {json.dumps({'type': 'token', 'content': refusal_msg})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                await redis_service.add_message_to_history(session_id, "ai", refusal_msg)
                return

        # 5. 검색 및 컨텍스트 강화
        context = await self._search_and_enrich(context, project_id)

        # 6. 소스 정보 전송
        sources_data = self._build_sources_response(context)
        yield f"data: {json.dumps(sources_data)}\n\n"

        # 7. 일관성 충돌 알림
        if context.conflicts:
            consistency_data = consistency_service.format_conflicts_for_response(context.conflicts)
            if consistency_data:
                if consistency_data.get("cards"):
                    collected_cards.extend(consistency_data["cards"])
                yield f"data: {json.dumps(consistency_data)}\n\n"

        # 8. 관계 카드 생성 (일반 모드에서만)
        if context.mode == ChatMode.NORMAL:
            relationship_card = await self._check_relationship_query(
                context.processed_message,
                context.search_results,
                project_id
            )
            if relationship_card:
                if relationship_card.get("cards"):
                    collected_cards.extend(relationship_card["cards"])
                yield f"data: {json.dumps(relationship_card)}\n\n"

        # 9. System Prompt 생성
        system_prompt = self._build_system_prompt(context, project_id)

        # 10. 메시지 히스토리 구성
        messages = [SystemMessage(content=system_prompt)]

        history = await redis_service.get_session_history(session_id)
        for msg in history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "ai":
                messages.append(AIMessage(content=msg["content"]))

        # 11. Stop 리스너 설정
        pubsub = await redis_service.create_stop_listener(session_id)

        full_response = ""

        # 12. 스트리밍 응답 생성
        try:
            async for chunk in self.llm.astream(messages):
                msg = await pubsub.get_message(ignore_subscribe_messages=True)
                if msg and msg['data'] == 'STOP':
                    yield f"data: {json.dumps({'type': 'error', 'error': 'Generation stopped by user'})}\n\n"
                    full_response = ""
                    break

                if chunk.content:
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk.content})}\n\n"
                    full_response += chunk.content

            if full_response:
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                # 히스토리 저장 (카드 정보 포함)
                metadata = {"sources": sources_data.get("sources"), "cards": collected_cards}
                await redis_service.add_message_to_history(session_id, "ai", full_response, metadata=metadata)

                asyncio.create_task(postgres_service.save_chat_log(
                    project_id=project_id,
                    session_id=session_id,
                    user_id=user_id,
                    role="ai",
                    content=full_response,
                    sources=metadata["sources"],
                    cards=metadata["cards"]
                ))

        except Exception as e:
            logger.error(f"Chat stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
        finally:
            await pubsub.close()

    async def _check_relationship_query(
        self,
        message: str,
        search_results: Dict[str, Any],
        project_id: str
    ) -> Optional[Dict[str, Any]]:
        """관계 질문 감지 및 카드 생성."""
        if not any(kw in message for kw in RELATIONSHIP_KEYWORDS):
            return None

        characters = search_results.get("characters", [])
        if len(characters) < 2:
            return None

        candidates = characters[:4]

        # 상위 4명 중 2명씩 짝지어서 관계 확인
        loop = asyncio.get_event_loop()

        for i in range(len(candidates)):
            for j in range(i + 1, len(candidates)):
                char1 = candidates[i]
                char2 = candidates[j]

                relationship_data = await loop.run_in_executor(
                    None,
                    neo4j_service.get_relationship_between,
                    project_id, char1["id"], char2["id"]
                )

                if relationship_data:
                    return {
                        "type": "cards",
                        "cards": [{
                            "cardType": "relationship",
                            "data": {
                                "sourceCharacter": {"id": char1["id"], "name": char1["name"]},
                                "targetCharacter": {"id": char2["id"], "name": char2["name"]},
                                "types": relationship_data["types"],
                                "strength": relationship_data["strength"],
                                "description": relationship_data["description"],
                                "bidirectional": relationship_data["bidirectional"],
                                "since": relationship_data["since"]
                            },
                            "actionUrl": f"/projects/{project_id}/world?tab=graph"
                        }]
                    }

        return None


chat_service = ChatService()
