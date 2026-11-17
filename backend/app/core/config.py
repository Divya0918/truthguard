"""Application settings loaded from .env file."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: str = "development"
    secret_key: str = "change-me-to-a-random-32-char-string"
    access_token_expire_minutes: int = 480

    # Database
    database_url: str = "sqlite+aiosqlite:///./truthguard.db"

    # LLM
    llm_provider: Literal["mock", "openai", "ollama"] = "mock"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    # Embeddings
    embedding_provider: Literal["mock", "local", "openai"] = "local"
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 384

    # pgvector
    pgvector_enabled: bool = False

    # Seed admin
    admin_email: str = "admin@demo.com"
    admin_password: str = "Admin@123456"
    admin_name: str = "Demo Admin"

    # CORS
    allowed_origins: str = "http://localhost:5173,http://localhost:5174"

    @field_validator("database_url")
    @classmethod
    def validate_db_url(cls, v: str) -> str:
        return v

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
