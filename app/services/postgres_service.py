"""PostgreSQL pgvector 기반 문장 임베딩 검색 서비스"""

import asyncpg
import logging
from typing import List, Dict, Any, Optional

from app.config import settings

logger = logging.getLogger(__name__)


class PostgresService:
    """PostgreSQL pgvector를 사용한 문장 단위 벡터 검색 서비스

    외부 시스템이 저장한 sentence_embeddings 테이블에서
    유사도 기반 검색을 수행합니다.
    """

    def __init__(self) -> None:
        self.pool: Optional[asyncpg.Pool] = None

    async def initialize(self) -> None:
        """커넥션 풀 초기화 (앱 시작 시 호출)"""
        try:
            self.pool = await asyncpg.create_pool(
                dsn=settings.postgres_dsn,
                min_size=2,
                max_size=10,
                command_timeout=30
            )
            logger.info("PostgreSQL connection pool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL pool: {e}")
            # PostgreSQL 연결 실패해도 앱은 계속 동작 (Neo4j만 사용)
            self.pool = None

    async def close(self) -> None:
        """커넥션 풀 종료"""
        if self.pool:
            await self.pool.close()
            logger.info("PostgreSQL connection pool closed")

    async def vector_search(
        self,
        project_id: str,
        query_embedding: List[float],
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """pgvector를 사용한 유사도 검색

        Args:
            project_id: 프로젝트 ID (필터링용)
            query_embedding: 쿼리 임베딩 벡터 (1536차원)
            limit: 반환할 결과 수

        Returns:
            검색 결과 리스트:
            [{"sentence_id": str, "content": str, "score": float, "metadata": dict}, ...]
        """
        if not self.pool:
            logger.warning("PostgreSQL pool not available, skipping search")
            return []

        # pgvector cosine distance: 1 - cosine_similarity
        # 따라서 score = 1 - distance로 변환하여 유사도로 표현
        query = """
            SELECT
                sentence_id,
                content,
                1 - (embedding <=> $1::vector) AS score,
                metadata
            FROM sentence_embeddings
            WHERE project_id = $2
            ORDER BY embedding <=> $1::vector
            LIMIT $3
        """

        try:
            async with self.pool.acquire() as conn:
                # 벡터를 pgvector 형식 문자열로 변환
                embedding_str = f"[{','.join(map(str, query_embedding))}]"
                rows = await conn.fetch(query, embedding_str, project_id, limit)

                return [
                    {
                        "sentence_id": row["sentence_id"],
                        "content": row["content"],
                        "score": float(row["score"]),
                        "metadata": row["metadata"] if row["metadata"] else {},
                        "source": "postgresql"
                    }
                    for row in rows
                ]
        except asyncpg.UndefinedTableError:
            logger.warning("sentence_embeddings table does not exist yet")
            return []
        except Exception as e:
            logger.error(f"PostgreSQL vector search failed: {e}")
            return []

    async def health_check(self) -> bool:
        """PostgreSQL 연결 상태 확인"""
        if not self.pool:
            return False
        try:
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception:
            return False


# 싱글톤 인스턴스
postgres_service = PostgresService()
