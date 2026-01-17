from neo4j import GraphDatabase
from app.config import settings
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class Neo4jService:
    def __init__(self):
        try:
            self.driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
            )
            self.initialize_index()
        except Exception as e:
            print(f"Failed to initialize Neo4j driver: {e}")
            self.driver = None

    def initialize_index(self):
        """
        Initializes the vector index if it doesn't exist.
        Uses 3072 dimensions to match Gemini embedding-001 model.
        """
        # Gemini embedding-001 모델의 차원 (3072)
        EMBEDDING_DIMENSION = 3072

        index_query = f"""
        CALL db.index.vector.createNodeIndex(
            'chunk_embedding',
            'Chunk',
            'embedding',
            {EMBEDDING_DIMENSION},
            'cosine'
        )
        """
        try:
            with self.driver.session() as session:
                session.run(index_query)
                print(f"Vector index 'chunk_embedding' created successfully ({EMBEDDING_DIMENSION} dimensions).")
        except Exception as e:
            if "EquivalentIndexAlreadyExists" in str(e) or "Index already exists" in str(e):
                print("Vector index 'chunk_embedding' already exists.")
            elif "different dimension" in str(e).lower():
                # 차원이 다른 인덱스가 존재하면 삭제 후 재생성
                print("Existing index has different dimensions. Recreating...")
                self._recreate_vector_index(EMBEDDING_DIMENSION)
            else:
                print(f"Failed to create vector index: {e}")

    def _recreate_vector_index(self, dimension: int):
        """기존 벡터 인덱스를 삭제하고 새 차원으로 재생성."""
        try:
            with self.driver.session() as session:
                # 기존 인덱스 삭제
                session.run("DROP INDEX chunk_embedding IF EXISTS")
                print("Old vector index dropped.")

                # 새 인덱스 생성
                session.run(f"""
                    CALL db.index.vector.createNodeIndex(
                        'chunk_embedding',
                        'Chunk',
                        'embedding',
                        {dimension},
                        'cosine'
                    )
                """)
                print(f"New vector index created with {dimension} dimensions.")
        except Exception as e:
            print(f"Failed to recreate vector index: {e}")

    def _ensure_driver(self):
        if self.driver is None:
             try:
                self.driver = GraphDatabase.driver(
                    settings.NEO4J_URI,
                    auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
                )
             except Exception as e:
                 print(f"Still failing to connect to Neo4j: {e}")

    def close(self):
        if self.driver:
            self.driver.close()

    def create_or_update_chunk(self, chunk_uuid: str, content: str, project_id: str, embedding: List[float] = None, metadata: Dict[str, Any] = None):
        """
        Stores a text chunk in Neo4j.
        If embedding is provided, it is stored.
        """
        query = """
        MERGE (c:Chunk {uuid: $chunk_uuid})
        SET c.content = $content,
            c.project_id = $project_id,
            c.updated_at = datetime()
        WITH c
        CALL apoc.do.when(
            $embedding IS NOT NULL,
            'SET c.embedding = $embedding',
            '',
            {c:c, embedding:$embedding}
        ) YIELD value
        WITH c
        MERGE (p:Project {id: $project_id})
        MERGE (c)-[:BELONGS_TO]->(p)
        """
        self._ensure_driver()
        if not self.driver:
            return

        with self.driver.session() as session:
            session.run(query, chunk_uuid=chunk_uuid, content=content, project_id=project_id, embedding=embedding)
            print(f"Stored chunk {chunk_uuid} in Neo4j (Embedding: {'Yes' if embedding else 'No'})")

    def vector_search(self, project_id: str, query_embedding: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        query = """
        CALL db.index.vector.queryNodes('chunk_embedding', $limit, $embedding) YIELD node, score
        WHERE node.project_id = $project_id
        RETURN node.uuid AS uuid, node.content AS content, score
        """
        self._ensure_driver()
        if not self.driver:
             return []

        with self.driver.session() as session:
            try:
                result = session.run(query, project_id=project_id, embedding=query_embedding, limit=limit)
                chunks = [{"chunk_uuid": record["uuid"], "content": record["content"], "score": record["score"]} for record in result]
                print(f"Vector search found {len(chunks)} chunks for project {project_id}")
                return chunks
            except Exception as e:
                print(f"Vector search failed: {e}")
                return []

    def search_characters(
        self,
        project_id: str,
        query: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Neo4j에서 캐릭터 노드 텍스트 검색.
        
        쿼리를 단어별로 분리하여 각 단어가 이름에 포함된 캐릭터를 검색.
        
        Args:
            project_id: 프로젝트 ID
            query: 검색 쿼리 (캐릭터 이름, 역할, 백스토리 등)
            limit: 반환할 결과 수
        
        Returns:
            [{"id": str, "name": str, "role": str, "backstory": str, ...}, ...]
        """
        import re
        
        # 한글 조사 패턴 (일반적인 조사들)
        KOREAN_PARTICLES = r'(이|가|을|를|은|는|의|와|과|랑|이랑|에게|한테|께|로|으로|에서|부터|까지|도|만|조차|마저)$'
        
        # 쿼리에서 2자 이상 단어 추출 (한글, 영문)
        raw_words = re.findall(r'[가-힣a-zA-Z]{2,}', query)
        
        # 한글 조사 제거
        words = []
        for word in raw_words:
            cleaned = re.sub(KOREAN_PARTICLES, '', word)
            # 조사 제거 후에도 2자 이상인 경우만 추가
            if len(cleaned) >= 2:
                words.append(cleaned)
        
        if not words:
            words = raw_words if raw_words else [query]
        
        logger.info(f"Character search words (after removing particles): {words}")
        
        # 각 단어에 대해 OR 조건으로 검색
        # Cypher에서 동적 OR 조건을 만들기 위해 ANY() 사용
        cypher = """
        MATCH (c:Character)
        WHERE c.project_id = $project_id
          AND ANY(word IN $words WHERE 
            toLower(c.name) CONTAINS toLower(word)
            OR toLower(coalesce(c.backstory, '')) CONTAINS toLower(word)
          )
        RETURN c.id as id,
               c.name as name,
               c.role as role,
               c.backstory as backstory,
               c.description as description,
               c.faction as faction
        LIMIT $limit
        """
        
        self._ensure_driver()
        if not self.driver:
            return []
        
        with self.driver.session() as session:
            try:
                result = session.run(cypher, project_id=project_id, words=words, limit=limit)
                characters = []
                for record in result:
                    characters.append({
                        "id": record["id"],
                        "name": record["name"],
                        "role": record["role"],
                        "backstory": record["backstory"],
                        "description": record["description"],
                        "faction": record["faction"],
                        "source": "neo4j",
                        "source_type": "character"
                    })
                logger.info(f"Neo4j characters search: {len(characters)} results for words {words}")
                return characters
            except Exception as e:
                logger.error(f"Neo4j characters search failed: {e}")
                return []

    def get_relationship_between(
        self, 
        project_id: str, 
        character_id_1: str, 
        character_id_2: str
    ) -> Optional[Dict[str, Any]]:
        """두 캐릭터 간의 관계 정보를 Neo4j에서 조회.
        
        양방향 조회: (A→B) 또는 (B→A) 중 하나가 존재하면 반환.
        관계 엣지 타입: RELATED_TO (단일 타입)
        
        Args:
            project_id: 프로젝트 ID
            character_id_1: 첫 번째 캐릭터 ID
            character_id_2: 두 번째 캐릭터 ID
        
        Returns:
            {
                "id": int,
                "sourceId": str,
                "sourceName": str,
                "targetId": str,
                "targetName": str,
                "types": List[str],
                "strength": int,
                "description": str,
                "bidirectional": bool,
                "since": str | None,
                "revealedInChapter": int | None
            } 또는 None
        """
        # RELATED_TO 단일 엣지 타입 + 양방향 조회
        query = """
        MATCH (source:Character)-[rel:RELATED_TO]->(target:Character)
        WHERE source.project_id = $project_id
          AND (
            (source.id = $char_id_1 AND target.id = $char_id_2)
            OR (source.id = $char_id_2 AND target.id = $char_id_1)
          )
        RETURN id(rel) as id,
               source.id as sourceId,
               source.name as sourceName,
               target.id as targetId,
               target.name as targetName,
               rel.types as types,
               rel.strength as strength,
               rel.description as description,
               rel.bidirectional as bidirectional,
               rel.since as since,
               rel.revealedInChapter as revealedInChapter
        LIMIT 1
        """
        
        self._ensure_driver()
        if not self.driver:
            return None
        
        with self.driver.session() as session:
            try:
                result = session.run(
                    query, 
                    project_id=project_id,
                    char_id_1=character_id_1, 
                    char_id_2=character_id_2
                )
                record = result.single()
                if record:
                    relationship_data = {
                        "id": record["id"],
                        "sourceId": record["sourceId"],
                        "sourceName": record["sourceName"],
                        "targetId": record["targetId"],
                        "targetName": record["targetName"],
                        "types": record["types"] or [],
                        "strength": record["strength"] or 5,
                        "description": record["description"] or "",
                        "bidirectional": record["bidirectional"] or False,
                        "since": record["since"],
                        "revealedInChapter": record["revealedInChapter"]
                    }
                    logger.info(f"Found relationship: {record['sourceName']} -> {record['targetName']}")
                    return relationship_data
                return None
            except Exception as e:
                logger.error(f"Relationship query failed: {e}")
                return None

    def search_events(
        self,
        project_id: str,
        query: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Neo4j에서 이벤트 노드 텍스트 검색.

        Args:
            project_id: 프로젝트 ID
            query: 검색 쿼리
            limit: 반환할 결과 수

        Returns:
            [{"id": str, "description": str, "narrativeSummary": str, ...}, ...]
        """
        import re

        # 한글 조사 제거
        KOREAN_PARTICLES = r'(이|가|을|를|은|는|의|와|과|에서|부터|까지|도|만)$'

        # 쿼리에서 2자 이상 단어 추출
        raw_words = re.findall(r'[가-힣a-zA-Z]{2,}', query)

        words = []
        for word in raw_words:
            cleaned = re.sub(KOREAN_PARTICLES, '', word)
            if len(cleaned) >= 2:
                words.append(cleaned)

        if not words:
            words = raw_words if raw_words else [query]

        logger.info(f"Event search words: {words}")

        cypher = """
        MATCH (e:Event)
        WHERE e.project_id = $project_id
          AND ANY(word IN $words WHERE
            toLower(coalesce(e.description, '')) CONTAINS toLower(word)
            OR toLower(coalesce(e.narrativeSummary, '')) CONTAINS toLower(word)
            OR toLower(coalesce(e.eventType, '')) CONTAINS toLower(word)
          )
        RETURN e.eventId as id,
               e.description as description,
               e.narrativeSummary as narrativeSummary,
               e.eventType as eventType,
               e.chapter as chapter,
               e.importance as importance
        LIMIT $limit
        """

        self._ensure_driver()
        if not self.driver:
            return []

        with self.driver.session() as session:
            try:
                result = session.run(cypher, project_id=project_id, words=words, limit=limit)
                events = []
                for record in result:
                    events.append({
                        "id": record["id"],
                        "description": record["description"],
                        "narrative_summary": record["narrativeSummary"],
                        "event_type": record["eventType"],
                        "chapter": record["chapter"],
                        "importance": record["importance"],
                        "source": "neo4j",
                        "source_type": "event"
                    })
                logger.info(f"Neo4j events search: {len(events)} results for words {words}")
                return events
            except Exception as e:
                logger.error(f"Neo4j events search failed: {e}")
                return []


    def get_character_by_name(
        self,
        project_id: str,
        character_name: str
    ) -> Optional[Dict[str, Any]]:
        """캐릭터 이름으로 상세 정보 조회 (페르소나 모드용).

        Args:
            project_id: 프로젝트 ID
            character_name: 캐릭터 이름 (부분 일치 지원)

        Returns:
            캐릭터 상세 정보 또는 None
        """
        import json

        cypher = """
        MATCH (c:Character)
        WHERE c.project_id = $project_id
          AND (
            toLower(c.name) = toLower($name)
            OR toLower(c.name) CONTAINS toLower($name)
            OR ANY(alias IN c.aliasesJson WHERE toLower(alias) CONTAINS toLower($name))
          )
        RETURN c
        ORDER BY CASE WHEN toLower(c.name) = toLower($name) THEN 0 ELSE 1 END
        LIMIT 1
        """

        self._ensure_driver()
        if not self.driver:
            return None

        with self.driver.session() as session:
            try:
                result = session.run(cypher, project_id=project_id, name=character_name)
                record = result.single()

                if not record:
                    return None

                char_node = dict(record["c"])

                # JSON 필드 파싱
                def safe_json_parse(val):
                    if not val:
                        return None
                    if isinstance(val, (dict, list)):
                        return val
                    try:
                        return json.loads(val)
                    except:
                        return val

                character = {
                    "id": char_node.get("id"),
                    "character_id": char_node.get("characterId"),
                    "name": char_node.get("name"),
                    "role": char_node.get("role"),
                    "gender": char_node.get("gender"),
                    "race": char_node.get("race"),
                    "status": char_node.get("status"),
                    "backstory": char_node.get("backstory"),
                    "aliases": safe_json_parse(char_node.get("aliasesJson")) or [],
                    "profile": safe_json_parse(char_node.get("profileJson")) or {},
                    "appearance": safe_json_parse(char_node.get("appearanceJson")) or {},
                    "current_mood": safe_json_parse(char_node.get("currentMoodJson")) or {},
                    "relations": safe_json_parse(char_node.get("relationsJson")) or {},
                }

                logger.info(f"Found character: {character['name']} (role: {character['role']})")
                return character

            except Exception as e:
                logger.error(f"Character lookup failed: {e}")
                return None

    def get_character_relationships(
        self,
        project_id: str,
        character_id: str
    ) -> List[Dict[str, Any]]:
        """캐릭터의 모든 관계 조회.

        Args:
            project_id: 프로젝트 ID
            character_id: 캐릭터 ID

        Returns:
            관계 리스트
        """
        cypher = """
        MATCH (c:Character {id: $character_id, project_id: $project_id})-[r:RELATED_TO]-(other:Character)
        RETURN other.name as name,
               other.role as role,
               r.types as types,
               r.description as description,
               r.strength as strength,
               CASE WHEN startNode(r) = c THEN 'outgoing' ELSE 'incoming' END as direction
        """

        self._ensure_driver()
        if not self.driver:
            return []

        with self.driver.session() as session:
            try:
                result = session.run(cypher, project_id=project_id, character_id=character_id)
                relationships = []
                for record in result:
                    relationships.append({
                        "target_name": record["name"],
                        "target_role": record["role"],
                        "types": record["types"] or [],
                        "description": record["description"],
                        "strength": record["strength"] or 5,
                        "direction": record["direction"]
                    })
                return relationships
            except Exception as e:
                logger.error(f"Relationship query failed: {e}")
                return []

    def get_character_events(
        self,
        project_id: str,
        character_name: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """캐릭터가 참여한 이벤트 조회.

        Args:
            project_id: 프로젝트 ID
            character_name: 캐릭터 이름
            limit: 반환할 이벤트 수

        Returns:
            이벤트 리스트
        """
        cypher = """
        MATCH (e:Event)
        WHERE e.project_id = $project_id
          AND (
            toLower(e.description) CONTAINS toLower($name)
            OR toLower(e.narrativeSummary) CONTAINS toLower($name)
          )
        RETURN e.eventId as id,
               e.description as description,
               e.narrativeSummary as narrative_summary,
               e.eventType as event_type,
               e.chapter as chapter
        ORDER BY e.chapter DESC
        LIMIT $limit
        """

        self._ensure_driver()
        if not self.driver:
            return []

        with self.driver.session() as session:
            try:
                result = session.run(cypher, project_id=project_id, name=character_name, limit=limit)
                return [dict(record) for record in result]
            except Exception as e:
                logger.error(f"Character events query failed: {e}")
                return []


neo4j_service = Neo4jService()
