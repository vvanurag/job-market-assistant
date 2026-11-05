"""Application settings, read from environment variables and the repository's .env file.

Secrets are typed as ``SecretStr`` so they are never printed by accident (NFR-11).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Local development warehouse (ADR-0005)
    duckdb_path: Path = REPO_ROOT / "data" / "dev" / "jobmarket.duckdb"

    # Snowflake (ADR-0003)
    snowflake_account: str | None = None
    snowflake_user: str | None = None
    snowflake_password: SecretStr | None = None
    snowflake_private_key_path: Path | None = None
    snowflake_role: str = "JMA_TRANSFORM"
    snowflake_warehouse: str = "JMA_WH"
    snowflake_database: str = "JOB_MARKET"

    # Local models (ADR-0006)
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "llama3"
    ollama_embed_model: str = "nomic-embed-text"

    # Hosted model APIs (ADR-0006)
    gemini_api_key: SecretStr | None = None
    groq_api_key: SecretStr | None = None

    @property
    def snowflake_configured(self) -> bool:
        has_auth = bool(self.snowflake_private_key_path) or bool(
            self.snowflake_password and self.snowflake_password.get_secret_value()
        )
        return bool(self.snowflake_account and self.snowflake_user and has_auth)


@lru_cache
def get_settings() -> Settings:
    return Settings()
