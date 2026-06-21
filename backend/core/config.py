"""
Core configuration — all settings from environment variables
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # App
    APP_NAME: str = "SQLMind"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database
    POSTGRES_URL: str
    ASYNC_POSTGRES_URL: str
    REDIS_URL: str = "redis://localhost:6379"

    # AI
    OPENAI_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    DEFAULT_LLM: str = "openai"  # "openai" | "gemini"
    LLM_MODEL: str = "gpt-4o"
    MAX_TOKENS: int = 2000
    TEMPERATURE: float = 0.1

    # Guardrails
    ENABLE_PII_DETECTION: bool = True
    ENABLE_INJECTION_DETECTION: bool = True
    MAX_QUERY_COMPLEXITY: int = 10  # joins + subqueries threshold
    MAX_ROW_LIMIT: int = 10000

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 30
    RATE_LIMIT_PER_HOUR: int = 500

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # pgvector / RAG
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    RAG_TOP_K: int = 5

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
