"""Application settings, read from environment variables and the repository's .env file.

Secrets are typed as ``SecretStr`` so they are never printed by accident (NFR-11).
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# The repository (seeds, config, data). Derived from this file in a source checkout; set
# JOBMARKET_HOME where the package is installed elsewhere, as in the API container.
REPO_ROOT = Path(os.environ.get("JOBMARKET_HOME") or Path(__file__).resolve().parents[2])


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Local development warehouse (ADR-0005)
    duckdb_path: Path = REPO_ROOT / "data" / "dev" / "jobmarket.duckdb"

    # Raw files waiting to be loaded: <bronze_root>/<source_id>/<batch_id>/postings/*.json
    bronze_root: Path = REPO_ROOT / "data" / "bronze"

    # Snowflake (ADR-0003)
    snowflake_account: str | None = None
    snowflake_user: str | None = None
    snowflake_password: SecretStr | None = None
    snowflake_private_key_path: Path | None = None
    snowflake_role: str = "JMA_TRANSFORM"
    snowflake_ingest_role: str = "JMA_INGEST"  # loading Bronze uses the write-Bronze-only role (NFR-12)
    snowflake_warehouse: str = "JMA_WH"
    snowflake_database: str = "JOB_MARKET"

    # Local models (ADR-0006)
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "llama3"
    ollama_embed_model: str = "nomic-embed-text"

    # Hosted model APIs (ADR-0006)
    gemini_api_key: SecretStr | None = None
    groq_api_key: SecretStr | None = None

    # Which model answers questions and which embeds text (FR-QA-08); see jobmarket/llm.py
    llm_provider: str = "groq"
    llm_model: str | None = None  # None means the provider's default in llm.DEFAULT_CHAT_MODELS
    embedding_model: str = "ollama:nomic-embed-text"

    # Where the API and the index read Gold from: "duckdb" (local) or "snowflake" (role JMA_SERVE)
    serving_warehouse: str = "duckdb"
    snowflake_serve_role: str = "JMA_SERVE"

    # Vector store (ADR-0004), started by docker compose
    vectordb_dsn: SecretStr = SecretStr("postgresql://jobmarket:jobmarket-local@localhost:5433/jobmarket")

    # Kafka for the streaming path (Phase 4); started by docker compose up -d
    kafka_bootstrap: str = "localhost:9094"

    # Where pipeline alerts are sent (FR-ORC-04), e.g. https://ntfy.sh/<your-private-topic>.
    # Empty: alerts are only recorded in the operations database and the task log.
    alert_webhook_url: str | None = None

    # API key clients send in the X-API-Key header (FR-API-05)
    api_key: SecretStr | None = None

    @property
    def snowflake_configured(self) -> bool:
        has_auth = bool(self.snowflake_private_key_path) or bool(
            self.snowflake_password and self.snowflake_password.get_secret_value()
        )
        return bool(self.snowflake_account and self.snowflake_user and has_auth)


@lru_cache
def get_settings() -> Settings:
    return Settings()
