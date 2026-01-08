from langchain_openai import OpenAIEmbeddings
from app.config import settings
from typing import List
from app.services.neo4j_service import neo4j_service

class EmbeddingService:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings(
            openai_api_key=settings.OPENAI_API_KEY,
            model="text-embedding-3-small"
        )

    def get_embedding(self, text: str) -> List[float]:
        return self.embeddings.embed_query(text)

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        return self.embeddings.embed_documents(texts)


embedding_service = EmbeddingService()



