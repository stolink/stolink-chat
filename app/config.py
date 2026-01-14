import os
import logging
from logging.handlers import RotatingFileHandler
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Gemini 임베딩 설정
    GEMINI_API_KEY: str

    # 환경 설정 (local, dev, production)
    APP_ENV: str = "local"
    
    # AWS Bedrock 설정 (Claude 3 Haiku)
    # 표준 AWS 변수명 지원
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    # 기존 변수명 하위 호환
    AWS_BEDROCK_API_KEY_ID: str = ""
    AWS_BEDROCK_API_KEY_SECRET: str = ""
    AWS_DEFAULT_REGION: str = "us-east-1"
    AWS_BEDROCK_MODEL_ID: str = "anthropic.claude-3-haiku-20240307-v1:0"
    
    # 임베딩 차원 (Gemini gemini-embedding-001)
    EMBEDDING_DIMENSION: int = 3072
    
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    REDIS_URL: str = "redis://localhost:6379/0"

    # PostgreSQL 설정
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "stolink"
    POSTGRES_PASSWORD: str = "stolink123"
    POSTGRES_DB: str = "stolink"
    POSTGRES_DSN: Optional[str] = None

    # 검색 설정
    SEARCH_SECTIONS_LIMIT: int = 5
    SEARCH_CHARACTERS_LIMIT: int = 5
    SEARCH_EVENTS_LIMIT: int = 5
    SEARCH_FINAL_LIMIT: int = 10
    SEARCH_THRESHOLD: float = 0.4

    # JWT 설정 (Spring 백엔드와 동일한 값 사용)
    JWT_SECRET: str = ""  # 환경변수로 설정 필수
    JWT_ALGORITHM: str = "HS512"

    @property
    def postgres_dsn(self) -> str:
        """PostgreSQL 연결 문자열 반환"""
        if self.POSTGRES_DSN:
            return self.POSTGRES_DSN
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def redis_url_with_scheme(self) -> str:
        """Ensure Redis URL has proper scheme (redis://, rediss://, or unix://).
        
        Auto-fixes bare host:port URLs (e.g., AWS ElastiCache Serverless format)
        by prepending 'redis://' scheme.
        """
        url = self.REDIS_URL
        
        # If already has scheme, return as-is
        if url.startswith(("redis://", "rediss://", "unix://")):
            return url
        
        # Auto-fix: prepend redis:// for bare host:port or host
        return f"rediss://{url}"

    class Config:
        env_file = ".env"
        extra = "ignore"  # .env에 정의되지 않은 변수 무시

settings = Settings()


def setup_logging():
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    handler = RotatingFileHandler(
        'logs/app.log',
        maxBytes=10485760,  # 10MB
        backupCount=10
    )
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    logging.getLogger().addHandler(handler)

    # Configure root logger
    logging.basicConfig(level=logging.INFO)
