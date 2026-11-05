"""Connections to the two warehouse engines (ADR-0003, ADR-0005)."""

from __future__ import annotations

from pathlib import Path

import duckdb

from jobmarket.settings import Settings


def duckdb_connect(settings: Settings, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    path: Path = settings.duckdb_path
    if not read_only:
        path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path), read_only=read_only)


def snowflake_connect(settings: Settings, role: str | None = None):
    """Open a Snowflake connection with key-pair (or password) authentication.

    ``role`` overrides SNOWFLAKE_ROLE, so each job can use the least-privileged role it
    needs (NFR-12): loading uses JMA_INGEST, transformation JMA_TRANSFORM.
    """
    import snowflake.connector

    if not settings.snowflake_configured:
        raise RuntimeError("Snowflake is not configured in .env (see docs/development/setup.md)")
    params: dict = {
        "account": settings.snowflake_account,
        "user": settings.snowflake_user,
        "role": role or settings.snowflake_role,
        "warehouse": settings.snowflake_warehouse,
        "database": settings.snowflake_database,
        "login_timeout": 30,
        # Always log out when the connection closes; this code never leaves async queries running.
        "enable_server_session_keep_alive_auto_detection": False,
    }
    if settings.snowflake_private_key_path:
        params["private_key_file"] = str(settings.snowflake_private_key_path.expanduser())
    else:
        params["password"] = settings.snowflake_password.get_secret_value()
    return snowflake.connector.connect(**params)
