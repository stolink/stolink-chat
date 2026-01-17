"""캐릭터 페르소나 서비스.

캐릭터의 관점에서 대화할 수 있도록 페르소나를 구축합니다.
@캐릭터명 형식으로 호출하면 해당 캐릭터가 직접 대답하는 것처럼 응답합니다.
"""

import re
import logging
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass

from app.services.neo4j_service import neo4j_service

logger = logging.getLogger(__name__)


@dataclass
class PersonaContext:
    """캐릭터 페르소나 컨텍스트."""
    character: Dict[str, Any]
    relationships: list
    recent_events: list
    is_active: bool = True


class PersonaService:
    """캐릭터 페르소나 관리 서비스.

    캐릭터의 성격, 배경, 관계를 기반으로 일관된 페르소나를 유지합니다.
    """

    # 페르소나 호출 패턴: @캐릭터명 또는 @"캐릭터 이름"
    PERSONA_PATTERN = re.compile(r'@(["\']?)([^"\'@\s][^@]*?)\1(?:\s|$|,)')

    def detect_persona_request(self, message: str) -> Optional[str]:
        """메시지에서 페르소나 요청 감지.

        Args:
            message: 사용자 메시지

        Returns:
            캐릭터 이름 또는 None
        """
        # @캐릭터명 패턴 찾기
        match = self.PERSONA_PATTERN.search(message)
        if match:
            character_name = match.group(2).strip()
            logger.info(f"Persona request detected: {character_name}")
            return character_name

        # "~의 관점에서", "~라면", "~처럼" 패턴 체크
        perspective_patterns = [
            r'([가-힣a-zA-Z]+)(?:의\s*)?(?:관점|시점|입장)에서',
            r'([가-힣a-zA-Z]+)(?:이|가)?라면',
            r'([가-힣a-zA-Z]+)처럼\s*(?:말|대답|답변)',
        ]

        for pattern in perspective_patterns:
            match = re.search(pattern, message)
            if match:
                character_name = match.group(1).strip()
                logger.info(f"Perspective request detected: {character_name}")
                return character_name

        return None

    def strip_persona_mention(self, message: str, character_name: str) -> str:
        """메시지에서 페르소나 멘션 제거.

        Args:
            message: 원본 메시지
            character_name: 캐릭터 이름

        Returns:
            멘션이 제거된 메시지
        """
        # @캐릭터명 제거
        cleaned = self.PERSONA_PATTERN.sub('', message)
        # "~의 관점에서" 등 제거
        cleaned = re.sub(rf'{character_name}(?:의\s*)?(?:관점|시점|입장)에서\s*', '', cleaned)
        cleaned = re.sub(rf'{character_name}(?:이|가)?라면\s*', '', cleaned)
        return cleaned.strip()

    async def build_persona_context(
        self,
        project_id: str,
        character_name: str
    ) -> Optional[PersonaContext]:
        """캐릭터 페르소나 컨텍스트 구축.

        Args:
            project_id: 프로젝트 ID
            character_name: 캐릭터 이름

        Returns:
            PersonaContext 또는 None (캐릭터 미발견 시)
        """
        import asyncio

        loop = asyncio.get_event_loop()

        # 1. 캐릭터 기본 정보 조회
        character = await loop.run_in_executor(
            None,
            neo4j_service.get_character_by_name,
            project_id, character_name
        )

        if not character:
            logger.warning(f"Character not found: {character_name}")
            return None

        # 2. 관계 정보 조회
        relationships = await loop.run_in_executor(
            None,
            neo4j_service.get_character_relationships,
            project_id, character["id"]
        )

        # 3. 최근 이벤트 조회
        recent_events = await loop.run_in_executor(
            None,
            neo4j_service.get_character_events,
            project_id, character["name"], 5
        )

        return PersonaContext(
            character=character,
            relationships=relationships,
            recent_events=recent_events,
            is_active=True
        )

    def generate_persona_prompt(self, context: PersonaContext) -> str:
        """페르소나 기반 System Prompt 생성.

        캐릭터의 성격, 배경, 현재 감정 상태를 반영한 프롬프트를 생성합니다.

        Args:
            context: PersonaContext

        Returns:
            System Prompt 문자열
        """
        char = context.character
        profile = char.get("profile", {})
        mood = char.get("current_mood", {})
        appearance = char.get("appearance", {})
        relations = char.get("relations", {})

        # 성격 정보 추출 (Neo4j 구조에 맞게)
        personality = profile.get("personality", {})
        # core_traits 또는 traits 지원
        traits = personality.get("core_traits", personality.get("traits", []))
        flaws = personality.get("flaws", [])
        values = personality.get("values", [])
        speech_style = personality.get("speech_style", "")
        mbti = profile.get("mbti", "")

        # 소속/팩션 정보
        faction = profile.get("faction", {})
        faction_name = faction.get("name", "") if isinstance(faction, dict) else ""
        faction_rank = ""
        if isinstance(faction, dict) and faction.get("social"):
            faction_rank = faction["social"].get("rank", "")

        # 외모 정보
        appearance_parts = []
        if appearance:
            if appearance.get("physique"):
                appearance_parts.append(f"체격: {appearance['physique']}")
            if appearance.get("attire"):
                attire = appearance['attire']
                if isinstance(attire, list):
                    appearance_parts.append(f"복장: {', '.join(attire[:2])}")
                else:
                    appearance_parts.append(f"복장: {attire}")
            if appearance.get("distinctive_features"):
                appearance_parts.append(f"특징: {appearance['distinctive_features']}")
        appearance_text = "\n".join([f"- {p}" for p in appearance_parts]) if appearance_parts else ""

        # 관계 정보 포맷팅 (Neo4j 엣지 + profile 내 관계 정보 병합)
        relationships_text = ""
        rel_lines = []

        # Neo4j 관계 (context.relationships)
        if context.relationships:
            for rel in context.relationships[:5]:
                types_str = ", ".join(rel.get('types', [])) if rel.get('types') else ""
                rel_desc = f"- {rel['target_name']}"
                if types_str:
                    rel_desc += f" ({types_str})"
                if rel.get('description'):
                    rel_desc += f": {rel['description'][:80]}"
                rel_lines.append(rel_desc)

        # profile 내 관계 정보 (relations.graph)
        if relations and relations.get("graph"):
            for rel in relations["graph"][:3]:
                if rel.get("target"):
                    rel_type = rel.get("type", "")
                    rel_desc = f"- {rel['target']}"
                    if rel_type:
                        rel_desc += f" ({rel_type})"
                    if rel.get("description"):
                        rel_desc += f": {rel['description'][:80]}"
                    if rel_desc not in rel_lines:
                        rel_lines.append(rel_desc)

        relationships_text = "\n".join(rel_lines) if rel_lines else ""

        # 최근 이벤트 포맷팅
        events_text = ""
        if context.recent_events:
            event_lines = []
            for evt in context.recent_events[:3]:
                evt_desc = evt.get('narrative_summary') or evt.get('description', '')
                if evt_desc:
                    event_lines.append(f"- {evt_desc[:120]}")
            events_text = "\n".join(event_lines)

        # 현재 감정 상태
        mood_text = ""
        if mood:
            emotion = mood.get("emotion", "")
            intensity = mood.get("intensity", 5)
            trigger = mood.get("trigger", "")
            if emotion:
                mood_text = f"현재 감정: {emotion} (강도: {intensity}/10)"
                if trigger:
                    mood_text += f"\n감정 원인: {trigger}"

        # 동적 프롬프트 생성
        personality_lines = []
        if traits:
            personality_lines.append(f"- 핵심 성격: {', '.join(traits)}")
        if flaws:
            personality_lines.append(f"- 결점/약점: {', '.join(flaws)}")
        if values:
            personality_lines.append(f"- 가치관: {', '.join(values)}")
        if mbti:
            personality_lines.append(f"- MBTI: {mbti}")
        if speech_style:
            personality_lines.append(f"- 말투: {speech_style}")
        personality_text = "\n".join(personality_lines) if personality_lines else "- 성격 정보 없음"

        prompt = f"""당신은 소설 속 캐릭터 **'{char['name']}'**입니다.
이 캐릭터가 되어 직접 1인칭으로 대화해주세요.

## 기본 정보
- 이름: {char['name']}
- 역할: {char.get('role', 'unknown')}
- 성별: {char.get('gender', 'unknown')}
- 종족: {char.get('race', 'human')}
- 상태: {char.get('status', 'alive')}
{f"- 소속: {faction_name}" if faction_name else ""}
{f"- 계급: {faction_rank}" if faction_rank else ""}

## 배경 스토리
{char.get('backstory', '정보 없음')}

## 성격 프로필
{personality_text}

## 외모
{appearance_text if appearance_text else "- 외모 정보 없음"}

## 현재 감정 상태
{mood_text if mood_text else "- 평온한 상태"}

## 주요 관계
{relationships_text if relationships_text else "- 관계 정보 없음"}

## 최근 경험한 사건
{events_text if events_text else "- 최근 이벤트 없음"}

---

## 연기 지침
1. **지식 제한 (중요)**: 위 '배경 스토리', '주요 관계', '최근 경험한 사건'에 없는 내용(인물, 사건 등)은 **절대** 아는 척하지 마세요. 특히 원작 소설의 내용을 가져오지 마세요. 모르는 인물은 "처음 듣는 이름인데...", "누구시죠?"와 같이 낯설어해야 합니다.
2. **1인칭 시점**: "나는...", "내가..." 형식으로 {char['name']}로서 직접 대답하세요.
3. **성격 일관성**: 위의 성격 특성과 가치관을 반영하여 답변하세요.
4. **감정 표현**: 현재 감정 상태를 자연스럽게 대화에 녹여주세요.
5. **관계 반영**: '주요 관계'에 명시된 인물에 대해서만 해당 관계를 반영하여 대하고, 그 외의 인물은 초면인 것처럼 대하세요.
6. **말투 유지**: 위 '성격 프로필'에 명시된 '말투'를 철저히 따르세요(존댓말/반말/사투리 등). 너무 길지 않게, 실제 대화하듯 자연스럽게 답변하세요.
7. **결점 반영**: 캐릭터의 결점과 약점도 은연중에 드러나도록 하세요.
"""
        return prompt

    def generate_persona_card(self, context: PersonaContext) -> Dict[str, Any]:
        """클라이언트에 전송할 페르소나 카드 생성.

        Args:
            context: PersonaContext

        Returns:
            페르소나 카드 데이터
        """
        char = context.character
        mood = char.get("current_mood", {})

        return {
            "type": "cards",
            "cards": [{
                "cardType": "persona",
                "data": {
                    "characterId": char.get("id"),
                    "name": char.get("name"),
                    "role": char.get("role"),
                    "status": char.get("status"),
                    "currentMood": {
                        "emotion": mood.get("emotion"),
                        "intensity": mood.get("intensity")
                    } if mood else None,
                    "relationshipCount": len(context.relationships),
                    "isActive": True
                }
            }]
        }


# 싱글톤 인스턴스
persona_service = PersonaService()
