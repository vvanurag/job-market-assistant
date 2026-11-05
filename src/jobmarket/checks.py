"""Environment checks behind ``jobmarket doctor``.

Each check maps to a Phase 0 exit criterion in docs/roadmap.md. Checks never raise:
every failure is returned as a result, so one broken dependency doesn't hide the others.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

import httpx

from jobmarket.settings import REPO_ROOT, Settings

MEDALLION_SCHEMAS = ("bronze", "silver", "gold")
MIN_PYTHON = (3, 12)


class Status(StrEnum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    SKIP = "SKIP"


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: Status
    detail: str


def check_python() -> CheckResult:
    version = ".".join(map(str, sys.version_info[:3]))
    ok = sys.version_info[:2] >= MIN_PYTHON
    return CheckResult("Python", Status.PASS if ok else Status.FAIL, f"{version} (need >= 3.12)")


def check_docker() -> CheckResult:
    try:
        out = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}} on {{.OperatingSystem}}"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except FileNotFoundError:
        return CheckResult("Docker", Status.FAIL, "docker CLI not found")
    except subprocess.TimeoutExpired:
        return CheckResult("Docker", Status.FAIL, "docker info timed out; is the daemon running?")
    if out.returncode != 0:
        return CheckResult("Docker", Status.FAIL, "daemon not reachable; start OrbStack or Docker Desktop")
    return CheckResult("Docker", Status.PASS, out.stdout.strip())


def check_secrets_not_tracked() -> CheckResult:
    """NFR-11: the .env file must never be committed."""
    try:
        out = subprocess.run(
            ["git", "ls-files", "--error-unmatch", ".env"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return CheckResult("Secrets", Status.WARN, "could not run git to verify .env is untracked")
    if out.returncode == 0:
        return CheckResult("Secrets", Status.FAIL, ".env is tracked by git; remove it with git rm --cached .env")
    return CheckResult("Secrets", Status.PASS, ".env is not tracked by git")


def check_duckdb(settings: Settings) -> CheckResult:
    try:
        import duckdb

        settings.duckdb_path.parent.mkdir(parents=True, exist_ok=True)
        with duckdb.connect(str(settings.duckdb_path)) as con:
            for schema in MEDALLION_SCHEMAS:
                con.execute(f"create schema if not exists {schema}")
            (version,) = con.execute("select version()").fetchone()
    except Exception as exc:
        return CheckResult("DuckDB", Status.FAIL, f"{type(exc).__name__}: {exc}")
    return CheckResult("DuckDB", Status.PASS, f"{version}, schemas bronze/silver/gold at {settings.duckdb_path}")


def check_snowflake(settings: Settings) -> CheckResult:
    if not settings.snowflake_configured:
        return CheckResult("Snowflake", Status.SKIP, "not configured in .env")
    try:
        from jobmarket.warehouse import snowflake_connect

        with snowflake_connect(settings) as con, con.cursor() as cur:
            cur.execute("select current_role(), current_warehouse(), current_database()")
            role, warehouse, database = cur.fetchone()
            cur.execute(f"show schemas in database {settings.snowflake_database}")
            schemas = {row[1].lower() for row in cur.fetchall()}
    except Exception as exc:
        return CheckResult("Snowflake", Status.FAIL, f"{type(exc).__name__}: {exc}"[:300])

    missing = [s for s in MEDALLION_SCHEMAS if s not in schemas]
    if not warehouse or missing:
        problem = f"missing schemas: {', '.join(missing)}" if missing else "warehouse not usable"
        return CheckResult("Snowflake", Status.FAIL, f"connected as {role}, but {problem}")
    return CheckResult("Snowflake", Status.PASS, f"role {role}, warehouse {warehouse}, database {database}")


def _model_installed(name: str, installed: set[str]) -> bool:
    return name in installed or f"{name}:latest" in installed


def check_ollama(settings: Settings, deep: bool, client: httpx.Client) -> CheckResult:
    base = settings.ollama_base_url.rstrip("/")
    try:
        resp = client.get(f"{base}/api/tags", timeout=5)
        resp.raise_for_status()
        installed = {m["name"] for m in resp.json().get("models", [])}
    except Exception:
        return CheckResult("Ollama", Status.FAIL, f"not reachable at {base}; start it with `ollama serve`")

    wanted = [settings.ollama_chat_model, settings.ollama_embed_model]
    missing = [m for m in wanted if not _model_installed(m, installed)]
    if missing:
        pulls = "; ".join(f"ollama pull {m}" for m in missing)
        return CheckResult("Ollama", Status.WARN, f"running, but models missing. Run: {pulls}")
    if not deep:
        return CheckResult("Ollama", Status.PASS, f"running; models {', '.join(wanted)} installed")

    try:
        gen = client.post(
            f"{base}/api/generate",
            json={"model": settings.ollama_chat_model, "prompt": "Reply with the single word OK.", "stream": False},
            timeout=180,
        )
        gen.raise_for_status()
        reply = gen.json().get("response", "").strip()[:40]
        emb = client.post(
            f"{base}/api/embed", json={"model": settings.ollama_embed_model, "input": "data engineer"}, timeout=60
        )
        emb.raise_for_status()
        dims = len(emb.json()["embeddings"][0])
    except Exception as exc:
        return CheckResult("Ollama", Status.FAIL, f"model call failed: {type(exc).__name__}: {exc}"[:300])
    return CheckResult("Ollama", Status.PASS, f"chat replied {reply!r}; embeddings have {dims} dimensions")


def _check_api_key(name: str, key, deep: bool, probe: Callable[[str], httpx.Response], key_hint: str) -> CheckResult:
    if not key or not key.get_secret_value():
        return CheckResult(name, Status.WARN, f"no API key set; {key_hint}")
    if not deep:
        return CheckResult(name, Status.PASS, "API key set (not verified; use --deep)")
    try:
        resp = probe(key.get_secret_value())
    except Exception as exc:
        return CheckResult(name, Status.FAIL, f"request failed: {type(exc).__name__}")
    if resp.status_code == 200:
        count = len(resp.json().get("models") or resp.json().get("data") or [])
        return CheckResult(name, Status.PASS, f"API key valid; {count} models available")
    return CheckResult(name, Status.FAIL, f"API key rejected (HTTP {resp.status_code})")


def check_gemini(settings: Settings, deep: bool, client: httpx.Client) -> CheckResult:
    return _check_api_key(
        "Google AI Studio",
        settings.gemini_api_key,
        deep,
        lambda key: client.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            headers={"x-goog-api-key": key},
            timeout=15,
        ),
        "create one at https://aistudio.google.com/apikey",
    )


def check_groq(settings: Settings, deep: bool, client: httpx.Client) -> CheckResult:
    return _check_api_key(
        "Groq Cloud",
        settings.groq_api_key,
        deep,
        lambda key: client.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {key}"},
            timeout=15,
        ),
        "create one at https://console.groq.com/keys",
    )


def run_all(settings: Settings, deep: bool = False, client: httpx.Client | None = None) -> list[CheckResult]:
    with client or httpx.Client() as http:
        return [
            check_python(),
            check_docker(),
            check_secrets_not_tracked(),
            check_duckdb(settings),
            check_snowflake(settings),
            check_ollama(settings, deep, http),
            check_gemini(settings, deep, http),
            check_groq(settings, deep, http),
        ]
