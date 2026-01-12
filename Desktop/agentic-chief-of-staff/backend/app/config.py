"""Application configuration module."""
import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Application
    APP_NAME: str = "Chief of Staff AI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = "your-secret-key-change-in-production"

    # Database
    DATABASE_URL: str = "postgresql://cos_user:cos_secure_pass_2024@localhost:5442/chief_of_staff"

    # Redis
    REDIS_URL: str = "redis://localhost:6380/0"

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # CORS
    CORS_ORIGINS: str = "http://localhost:3001"

    # Public API base URL (used for download links)
    PUBLIC_API_URL: str = "http://localhost:2000"

    # File Upload
    UPLOAD_FOLDER: str = "/app/uploads"
    MAX_CONTENT_LENGTH: int = 16 * 1024 * 1024  # 16MB

    # Agent Configuration
    MAX_AGENT_ITERATIONS: int = 10
    AGENT_TIMEOUT: int = 120  # seconds

    # SMTP (Email sending)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_FROM_NAME: str = ""
    SMTP_USE_TLS: bool = True
    SMTP_USE_SSL: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
