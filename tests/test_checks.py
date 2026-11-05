import duckdb
import httpx

from jobmarket.checks import (
    Status,
    check_duckdb,
    check_gemini,
    check_groq,
    check_ollama,
    check_python,
    check_snowflake,
)
from jobmarket.settings import Settings


def make(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def client_returning(routes: dict[str, httpx.Response]) -> httpx.Client:
    """An httpx client whose responses are looked up by URL path; unknown paths return 404."""

    def handler(request: httpx.Request) -> httpx.Response:
        return routes.get(request.url.path, httpx.Response(404))

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_python_version_is_supported():
    assert check_python().status is Status.PASS


def test_duckdb_creates_medallion_schemas(tmp_path):
    db = tmp_path / "dev.duckdb"
    result = check_duckdb(make(duckdb_path=db))
    assert result.status is Status.PASS
    with duckdb.connect(str(db)) as con:
        schemas = {r[0] for r in con.execute("select schema_name from information_schema.schemata").fetchall()}
    assert {"bronze", "silver", "gold"} <= schemas


def test_snowflake_is_skipped_when_not_configured():
    assert check_snowflake(make()).status is Status.SKIP


def test_ollama_passes_when_models_are_installed():
    tags = {"models": [{"name": "llama3:latest"}, {"name": "nomic-embed-text:latest"}]}
    client = client_returning({"/api/tags": httpx.Response(200, json=tags)})
    assert check_ollama(make(), deep=False, client=client).status is Status.PASS


def test_ollama_warns_with_pull_command_when_model_missing():
    client = client_returning({"/api/tags": httpx.Response(200, json={"models": [{"name": "llama3:latest"}]})})
    result = check_ollama(make(), deep=False, client=client)
    assert result.status is Status.WARN
    assert "ollama pull nomic-embed-text" in result.detail


def test_ollama_fails_when_not_running():
    def refuse(request):
        raise httpx.ConnectError("connection refused")

    client = httpx.Client(transport=httpx.MockTransport(refuse))
    assert check_ollama(make(), deep=False, client=client).status is Status.FAIL


def test_ollama_deep_check_calls_chat_and_embedding_models():
    client = client_returning(
        {
            "/api/tags": httpx.Response(200, json={"models": [{"name": "llama3"}, {"name": "nomic-embed-text"}]}),
            "/api/generate": httpx.Response(200, json={"response": "OK"}),
            "/api/embed": httpx.Response(200, json={"embeddings": [[0.1] * 768]}),
        }
    )
    result = check_ollama(make(), deep=True, client=client)
    assert result.status is Status.PASS
    assert "768 dimensions" in result.detail


def test_api_key_checks_warn_without_keys():
    client = client_returning({})
    assert check_gemini(make(), deep=False, client=client).status is Status.WARN
    assert check_groq(make(), deep=False, client=client).status is Status.WARN


def test_api_key_deep_check_reports_rejected_key():
    client = client_returning({"/openai/v1/models": httpx.Response(401)})
    result = check_groq(make(groq_api_key="bad"), deep=True, client=client)
    assert result.status is Status.FAIL
    assert "401" in result.detail


def test_api_key_deep_check_accepts_valid_key():
    client = client_returning({"/v1beta/models": httpx.Response(200, json={"models": [{}, {}]})})
    result = check_gemini(make(gemini_api_key="good"), deep=True, client=client)
    assert result.status is Status.PASS
    assert "2 models" in result.detail
