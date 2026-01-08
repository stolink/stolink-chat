"""Neo4j와 PostgreSQL 벡터 검색 결과를 통합하는 서비스"""

import asyncio
import logging
from typing import List, Dict, Any

from app.services.neo4j_service import neo4j_service
from app.services.postgres_service import postgres_service
from app.config import settings

logger = logging.getLogger(__name__)


class UnifiedSearchService:
    """Neo4j(청크 단위)와 PostgreSQL(문장 단위) 벡터 검색 결과를 병합

    두 데이터소스에서 병렬로 검색한 후,
    유사도 점수 기준으로 통합 정렬하여 반환합니다.
    """

    async def hybrid_search(
        self,
        project_id: str,
        query_embedding: List[float],
        neo4j_limit: int = None,
        postgres_limit: int = None,
        final_limit: int = None
    ) -> List[Dict[str, Any]]:
        """두 데이터소스에서 병렬 검색 후 유사도 순으로 병합

        Args:
            project_id: 프로젝트 ID
            query_embedding: 쿼리 임베딩 벡터 (1536차원)
            neo4j_limit: Neo4j에서 가져올 청크 수 (기본: settings.SEARCH_NEO4J_LIMIT)
            postgres_limit: PostgreSQL에서 가져올 문장 수 (기본: settings.SEARCH_POSTGRES_LIMIT)
            final_limit: 최종 반환할 결과 수 (기본: settings.SEARCH_FINAL_LIMIT)

        Returns:
            병합된 검색 결과 (유사도 내림차순):
            [{"id": str, "content": str, "score": float, "source": str, "source_type": str}, ...]
        """
        neo4j_limit = neo4j_limit or settings.SEARCH_NEO4J_LIMIT
        postgres_limit = postgres_limit or settings.SEARCH_POSTGRES_LIMIT
        final_limit = final_limit or settings.SEARCH_FINAL_LIMIT

        # 병렬 검색 실행
        # Neo4j search is now optional/secondary as embeddings are primarily in Postgres
        neo4j_task = asyncio.create_task(
             self._search_neo4j(project_id, query_embedding, neo4j_limit)
        )
        postgres_task = asyncio.create_task(
            postgres_service.vector_search(project_id, query_embedding, postgres_limit)
        )

        neo4j_results, postgres_results = await asyncio.gather(
            neo4j_task,
            postgres_task,
            return_exceptions=True
        )

        # 예외 처리
        if isinstance(neo4j_results, Exception):
            logger.error(f"Neo4j search error: {neo4j_results}")
            neo4j_results = []
        if isinstance(postgres_results, Exception):
            logger.error(f"PostgreSQL search error: {postgres_results}")
            postgres_results = []

        # 결과 통합 및 정규화
        unified = self._normalize_and_merge(neo4j_results, postgres_results)

        # Threshold Filtering
        unified = [item for item in unified if item["score"] >= settings.SEARCH_THRESHOLD]

        # 유사도 순 정렬 후 상위 N개 반환
        unified.sort(key=lambda x: x["score"], reverse=True)

        logger.info(
            f"Hybrid search: Neo4j={len(neo4j_results)}, "
            f"PostgreSQL={len(postgres_results)}, "
            f"Merged={len(unified[:final_limit])}"
        )

        return unified[:final_limit]

    async def _search_neo4j(
        self,
        project_id: str,
        query_embedding: List[float],
        limit: int
    ) -> List[Dict[str, Any]]:
        """Neo4j 검색을 비동기로 래핑 (동기 드라이버를 스레드풀에서 실행)"""
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None,
            neo4j_service.vector_search,
            project_id,
            query_embedding,
            limit
        )

        # 소스 타입 추가
        for r in results:
            r["source"] = "neo4j"
            r["id"] = r.pop("chunk_uuid", r.get("uuid", ""))

        return results

    def _normalize_and_merge(
        self,
        neo4j_results: List[Dict],
        postgres_results: List[Dict]
    ) -> List[Dict[str, Any]]:
        """두 소스의 결과를 통합된 형식으로 정규화

        Note:
            두 시스템 모두 cosine similarity 사용하므로
            점수 스케일이 동일 (0~1, 높을수록 유사)
        """
        unified = []

        # Neo4j 결과 정규화
        for item in neo4j_results:
            unified.append({
                "id": item.get("id", item.get("chunk_uuid", "")),
                "content": item.get("content", ""),
                "score": float(item.get("score", 0.0)),
                "source": "neo4j",
                "source_type": "chunk",
                "metadata": item.get("metadata", {})
            })

        # PostgreSQL 결과 정규화
        for item in postgres_results:
            unified.append({
                "id": item.get("sentence_id", ""),
                "content": item.get("content", ""),
                "score": float(item.get("score", 0.0)),
                "source": "postgresql",
                "source_type": "sentence",
                "metadata": item.get("metadata", {})
            })

        return unified


# 싱글톤 인스턴스
unified_search_service = UnifiedSearchService()
