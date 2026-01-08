"""Gemini Embedding Service for Chatbot.

FastAPI Agent와 동일한 모델을 사용하여 임베딩 공간 일치.
- 모델: gemini-embedding-001
- 차원: 3072
"""

from google import genai
from app.config import settings
from typing import List
import logging

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Google Gemini 임베딩 서비스.
    
    FastAPI Agent와 동일한 모델을 사용하여 벡터 공간 일치.
    """
    
    MODEL_ID = "gemini-embedding-001"
    EMBEDDING_DIMENSION = 3072
    MAX_INPUT_TOKENS = 2048
    
    def __init__(self):
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is required")
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        logger.info(f"Gemini EmbeddingService initialized (model={self.MODEL_ID})")
    
    def get_embedding(self, text: str) -> List[float]:
        """텍스트 임베딩 생성 (동기)."""
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return [0.0] * self.EMBEDDING_DIMENSION
        
        # 토큰 제한 (한글 1자 ≈ 2토큰)
        max_chars = self.MAX_INPUT_TOKENS * 2
        if len(text) > max_chars:
            text = text[:max_chars]
            logger.warning(f"Text truncated to {max_chars} chars")
        
        try:
            response = self.client.models.embed_content(
                model=self.MODEL_ID,
                contents=text,
            )
            return list(response.embeddings[0].values)
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise
    
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """배치 임베딩 생성."""
        return [self.get_embedding(text) for text in texts]


# 싱글톤 인스턴스
embedding_service = EmbeddingService()
