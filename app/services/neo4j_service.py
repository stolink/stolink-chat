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
        """
        index_query = """
        CALL db.index.vector.createNodeIndex(
            'chunk_embedding',
            'Chunk',
            'embedding',
            1536,
            'cosine'
        )
        """
        try:
            with self.driver.session() as session:
                session.run(index_query)
                print("Vector index 'chunk_embedding' created successfully.")
        except Exception as e:
            if "EquivalentIndexAlreadyExists" in str(e) or "Index already exists" in str(e):
                print("Vector index 'chunk_embedding' already exists.")
            else:
                print(f"Failed to create vector index: {e}")

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

neo4j_service = Neo4jService()
