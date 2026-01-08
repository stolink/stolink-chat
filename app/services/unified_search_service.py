"""Multi-Source RAG 통합 검색 서비스.

Agent가 분석/저장한 데이터를 RAG에서 활용합니다.

데이터 소스:
- sections: 본문 청크 (벡터 검색, Gemini 3072차원)
- characters: 캐릭터 정보 (텍스트 검색)
- events: 이벤트 정보 (텍스트 검색)
"""

import asyncio
import logging
from typing import List, Dict, Any

from app.services.postgres_service import postgres_service
from app.config import settings

logger = logging.getLogger(__name__)


class UnifiedSearchService:
    """Multi-Source RAG 통합 검색 서비스.
    
    sections(벡터) + characters(텍스트) + events(텍스트) 병렬 검색 후 결과 병합.
    """

    async def search(
        self,
        project_id: str,
        query_embedding: List[float],
        query_text: str,
        sections_limit: int = None,
        characters_limit: int = None,
        events_limit: int = None
    ) -> Dict[str, Any]:
        """Multi-Source 검색 수행.
        
        Args:
            project_id: 프로젝트 ID
            query_embedding: 쿼리 임베딩 (3072차원)
            query_text: 원본 텍스트 쿼리 (텍스트 검색용)
            *_limit: 각 소스별 결과 수
        
        Returns:
            {
                "sections": [...],      # 본문 맥락
                "characters": [...],    # 관련 캐릭터
                "events": [...]         # 관련 이벤트
            }
        """
        sections_limit = sections_limit or settings.SEARCH_SECTIONS_LIMIT
        characters_limit = characters_limit or settings.SEARCH_CHARACTERS_LIMIT
        events_limit = events_limit or settings.SEARCH_EVENTS_LIMIT

        # 병렬 검색 실행
        section_task = postgres_service.search_sections(
            project_id, query_embedding, sections_limit
        )
        character_task = postgres_service.search_characters(
            project_id, query_text, characters_limit
        )
        event_task = postgres_service.search_events(
            project_id, query_text, events_limit
        )

        sections, characters, events = await asyncio.gather(
            section_task, character_task, event_task,
            return_exceptions=True
        )

        # 예외 처리
        if isinstance(sections, Exception):
            logger.error(f"Sections search error: {sections}")
            sections = []
        if isinstance(characters, Exception):
            logger.error(f"Characters search error: {characters}")
            characters = []
        if isinstance(events, Exception):
            logger.error(f"Events search error: {events}")
            events = []

        # Threshold 필터링 (sections만, 벡터 검색 결과이므로)
        sections = [s for s in sections if s.get("score", 0) >= settings.SEARCH_THRESHOLD]

        logger.info(
            f"Multi-source search: sections={len(sections)}, "
            f"characters={len(characters)}, events={len(events)}"
        )

        return {
            "sections": sections,
            "characters": characters,
            "events": events
        }

    async def search_sections_only(
        self,
        project_id: str,
        query_embedding: List[float],
        limit: int = None
    ) -> List[Dict[str, Any]]:
        """Sections만 검색 (심플 모드).
        
        캐릭터/이벤트 텍스트 검색 없이 벡터 검색만 수행.
        """
        limit = limit or settings.SEARCH_FINAL_LIMIT

        results = await postgres_service.search_sections(
            project_id=project_id,
            query_embedding=query_embedding,
            limit=limit
        )

        # Threshold 필터링
        filtered = [r for r in results if r.get("score", 0) >= settings.SEARCH_THRESHOLD]
        filtered.sort(key=lambda x: x["score"], reverse=True)

        return filtered[:limit]


# 싱글톤 인스턴스
unified_search_service = UnifiedSearchService()
