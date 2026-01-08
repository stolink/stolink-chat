import os
import logging
from logging.handlers import RotatingFileHandler
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    OPENAI_API_KEY: str
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
    SEARCH_NEO4J_LIMIT: int = 5
    SEARCH_POSTGRES_LIMIT: int = 5
    SEARCH_POSTGRES_LIMIT: int = 5
    SEARCH_FINAL_LIMIT: int = 10
    SEARCH_THRESHOLD: float = 0.4 # Minimum similarity score to be considered relevant

    @property
    def postgres_dsn(self) -> str:
        """PostgreSQL 연결 문자열 반환"""
        if self.POSTGRES_DSN:
            return self.POSTGRES_DSN
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    class Config:
        env_file = ".env"

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
