from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):  # type: ignore[misc]
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "coderev"
    app_version: str = "0.1.1"
    debug: bool = False
    environment: Literal["development", "staging", "production", "test"] = "development"

    # API Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 1

    # Database
    database_url: str = "postgresql+asyncpg://coderev:coderev@localhost:5432/coderev"
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # GitHub
    github_token: SecretStr = Field(default=...)
    github_api_url: str = "https://api.github.com"
    github_webhook_secret: SecretStr | None = None

    # LLM Providers
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    ollama_host: str = "http://localhost:11434"

    # LLM Settings
    default_llm_provider: Literal["anthropic", "openai", "ollama"] = "anthropic"
    default_model_anthropic: str = "claude-sonnet-4-20250514"
    default_model_openai: str = "gpt-4o"
    default_model_ollama: str = "deepseek-coder:6.7b"

    # Review Settings
    max_files_per_review: int = 20
    max_diff_size_bytes: int = 100_000
    review_timeout_seconds: int = 300

    @property
    def database_url_sync(self) -> str:
        """Return sync database URL for Alembic."""
        return self.database_url.replace("+asyncpg", "")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
