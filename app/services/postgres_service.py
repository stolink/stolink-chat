"""PostgreSQL pgvector 기반 벡터 검색 서비스.

Agent가 저장한 sections, characters, events 테이블을 검색합니다.
"""

import asyncpg
import json
import logging
from typing import List, Dict, Any, Optional

from app.config import settings

logger = logging.getLogger(__name__)


class PostgresService:
    """PostgreSQL pgvector 기반 Multi-Source 검색 서비스.

    데이터 소스:
    - sections: 본문 청크 (벡터 검색, 3072차원)
    - characters: 캐릭터 정보 (텍스트 검색)
    - events: 이벤트 정보 (텍스트 검색)
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
            self.pool = None

    async def close(self) -> None:
        """커넥션 풀 종료"""
        if self.pool:
            await self.pool.close()
            logger.info("PostgreSQL connection pool closed")

    # =========================================================================
    # Section 검색 (벡터 검색, 3072차원)
    # =========================================================================

    async def search_sections(
        self,
        project_id: str,
        query_embedding: List[float],
        limit: int = None
    ) -> List[Dict[str, Any]]:
        """sections 테이블에서 벡터 유사도 검색.

        Agent가 분석한 섹션 데이터를 검색합니다.

        Args:
            project_id: 프로젝트 ID
            query_embedding: 쿼리 임베딩 벡터 (3072차원)
            limit: 반환할 결과 수

        Returns:
            [{"section_id": str, "content": str, "score": float,
              "nav_title": str, "related_characters": list, "related_events": list}, ...]
        """
        limit = limit or settings.SEARCH_SECTIONS_LIMIT

        if not self.pool:
            logger.warning("PostgreSQL pool not available")
            return []

        query = """
            SELECT
                s.id AS section_id,
                s.content,
                s.nav_title,
                s.related_characters_json,
                s.related_events_json,
                1 - (s.embedding <=> $1::vector) AS score
            FROM sections s
            JOIN documents d ON s.document_id = d.id
            WHERE d.project_id = $2::uuid
              AND s.embedding IS NOT NULL
            ORDER BY s.embedding <=> $1::vector
            LIMIT $3
        """

        try:
            async with self.pool.acquire() as conn:
                embedding_str = f"[{','.join(map(str, query_embedding))}]"
                rows = await conn.fetch(query, embedding_str, project_id, limit)

                results = []
                for row in rows:
                    # JSON 파싱
                    related_chars = []
                    related_evts = []
                    try:
                        if row["related_characters_json"]:
                            related_chars = json.loads(row["related_characters_json"])
                    except:
                        pass
                    try:
                        if row["related_events_json"]:
                            related_evts = json.loads(row["related_events_json"])
                    except:
                        pass

                    results.append({
                        "section_id": str(row["section_id"]),
                        "content": row["content"],
                        "nav_title": row["nav_title"] or "Untitled",
                        "score": float(row["score"]),
                        "related_characters": related_chars,
                        "related_events": related_evts,
                        "source": "sections",
                        "source_type": "section"
                    })

                logger.info(f"Sections search: {len(results)} results")
                return results

        except asyncpg.UndefinedTableError:
            logger.warning("sections table does not exist")
            return []
        except Exception as e:
            logger.error(f"Sections search failed: {e}")
            return []

    # =========================================================================
    # Character 검색 (텍스트 검색)
    # =========================================================================

    async def search_characters(
        self,
        project_id: str,
        query: str,
        limit: int = None
    ) -> List[Dict[str, Any]]:
        """characters 테이블에서 텍스트 검색.

        Args:
            project_id: 프로젝트 ID
            query: 검색 쿼리 (캐릭터 이름, 역할, 백스토리 등)
            limit: 반환할 결과 수

        Returns:
            [{"id": uuid, "name": str, "role": str, "backstory": str, ...}, ...]
        """
        limit = limit or settings.SEARCH_CHARACTERS_LIMIT

        if not self.pool:
            return []

        sql = """
            SELECT
                id,
                name,
                role,
                backstory,
                description,
                appearance_json,
                personality_json
            FROM characters
            WHERE project_id = $1::uuid
              AND (
                name ILIKE $2
                OR backstory ILIKE $2
                OR role ILIKE $2
                OR description ILIKE $2
              )
            LIMIT $3
        """

        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(sql, project_id, f"%{query}%", limit)

                results = []
                for row in rows:
                    char_data = {
                        "id": str(row["id"]),
                        "name": row["name"],
                        "role": row["role"],
                        "backstory": row["backstory"],
                        "description": row["description"],
                        "source": "characters",
                        "source_type": "character"
                    }

                    # JSON 필드 파싱
                    try:
                        if row["appearance_json"]:
                            char_data["appearance"] = json.loads(row["appearance_json"])
                    except:
                        pass
                    try:
                        if row["personality_json"]:
                            char_data["personality"] = json.loads(row["personality_json"])
                    except:
                        pass

                    results.append(char_data)

                logger.info(f"Characters search: {len(results)} results for '{query}'")
                return results

        except asyncpg.UndefinedTableError:
            logger.warning("characters table does not exist")
            return []
        except Exception as e:
            logger.error(f"Characters search failed: {e}")
            return []

    # =========================================================================
    # Event 검색 (텍스트 검색)
    # =========================================================================

    async def search_events(
        self,
        project_id: str,
        query: str,
        limit: int = None
    ) -> List[Dict[str, Any]]:
        """events 테이블에서 텍스트 검색.

        Args:
            project_id: 프로젝트 ID
            query: 검색 쿼리
            limit: 반환할 결과 수

        Returns:
            [{"id": str, "description": str, "event_type": str, ...}, ...]
        """
        limit = limit or settings.SEARCH_EVENTS_LIMIT

        if not self.pool:
            return []

        sql = """
            SELECT
                id,
                description,
                event_type,
                location,
                chapter,
                participants
            FROM events
            WHERE project_id = $1::uuid
              AND (
                description ILIKE $2
                OR location ILIKE $2
                OR event_type ILIKE $2
              )
            LIMIT $3
        """

        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(sql, project_id, f"%{query}%", limit)

                results = []
                for row in rows:
                    event_data = {
                        "id": str(row["id"]),
                        "description": row["description"],
                        "narrative_summary": row["description"],  # 호환성 유지
                        "event_type": row["event_type"],
                        "location": row["location"],
                        "chapter": row["chapter"],
                        "source": "events",
                        "source_type": "event"
                    }

                    # participants (jsonb)
                    if row["participants"]:
                        event_data["participants"] = row["participants"]

                    results.append(event_data)

                logger.info(f"Events search: {len(results)} results for '{query}'")
                return results

        except asyncpg.UndefinedTableError:
            logger.warning("events table does not exist")
            return []
        except Exception as e:
            logger.error(f"Events search failed: {e}")
            return []

    # =========================================================================
    # 헬스체크
    # =========================================================================

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

    # =========================================================================
    # Chat Log 저장
    # =========================================================================

    async def save_chat_log(
        self,
        project_id: str,
        session_id: str,
        user_id: Optional[str],
        role: str,
        content: str,
        sources: Optional[List[Dict[str, Any]]] = None,
        cards: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """대화 로그를 PostgreSQL에 비동기 저장.

        Fire-and-forget 패턴: 저장 실패 시에도 챗봇 응답에 영향 없음.

        Args:
            project_id: 프로젝트 UUID
            session_id: 세션 ID
            user_id: 사용자 ID (optional)
            role: 'user' 또는 'ai'
            content: 대화 내용
            sources: AI 응답 시 참조한 소스 정보 (optional)
            cards: AI 응답 시 생성된 카드 정보 (optional)
        """
        if not self.pool:
            logger.warning("PostgreSQL pool not available, skipping chat log save")
            return

        sql = """
            INSERT INTO chat_logs (project_id, session_id, user_id, role, content, sources_json)
            VALUES ($1::uuid, $2, $3, $4, $5, $6::jsonb)
        """

        try:
            # sources_json에 sources와 cards를 모두 포함하여 저장
            metadata = {}
            if sources:
                metadata["sources"] = sources
            if cards:
                metadata["cards"] = cards

            metadata_json = json.dumps(metadata) if metadata else None

            async with self.pool.acquire() as conn:
                await conn.execute(
                    sql,
                    project_id,
                    session_id,
                    user_id,
                    role,
                    content,
                    metadata_json
                )
            logger.debug(f"Chat log saved: session={session_id}, role={role}")
        except Exception as e:
            # Fire-and-forget: 로그 저장 실패해도 챗봇 응답은 정상 동작
            logger.warning(f"Failed to save chat log: {e}")



# 싱글톤 인스턴스
postgres_service = PostgresService()
