from pathlib import Path

from jobmarket.settings import Settings


def make(**overrides) -> Settings:
    # _env_file=None keeps tests independent of a developer's local .env
    return Settings(_env_file=None, **overrides)


def test_defaults_point_at_project_resources():
    s = make()
    assert s.snowflake_role == "JMA_TRANSFORM"
    assert s.snowflake_warehouse == "JMA_WH"
    assert s.duckdb_path.name == "jobmarket.duckdb"
    assert not s.snowflake_configured


def test_environment_variables_override_defaults(monkeypatch):
    monkeypatch.setenv("OLLAMA_CHAT_MODEL", "gemma2:9b")
    monkeypatch.setenv("SNOWFLAKE_ROLE", "JMA_SERVE")
    s = make()
    assert s.ollama_chat_model == "gemma2:9b"
    assert s.snowflake_role == "JMA_SERVE"


def test_snowflake_configured_requires_account_user_and_auth():
    assert not make(snowflake_account="acct", snowflake_user="me").snowflake_configured
    assert make(snowflake_account="acct", snowflake_user="me", snowflake_password="pw").snowflake_configured
    assert make(
        snowflake_account="acct", snowflake_user="me", snowflake_private_key_path=Path("key.p8")
    ).snowflake_configured


def test_secrets_are_masked_when_printed():
    s = make(gemini_api_key="super-secret-value")
    assert "super-secret-value" not in repr(s)
    assert "super-secret-value" not in str(s.gemini_api_key)
