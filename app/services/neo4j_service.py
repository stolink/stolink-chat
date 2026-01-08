from neo4j import GraphDatabase
from app.config import settings
from typing import List, Dict, Any

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

neo4j_service = Neo4jService()
