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
    con = snowflake.connector.connect(**params)
    # Accounts created since 2024 activate ALL of a user's roles as secondary roles by
    # default, which would let a session use privileges beyond its own role. Turning
    # them off makes each connection exactly as privileged as its role (NFR-12).
    con.cursor().execute("use secondary roles none")
    return con


def read_gold(settings: Settings, query: str, params: list | None = None) -> list[dict]:
    """Run a read-only query against Gold on the serving warehouse; rows as dicts.

    DuckDB opens the file read-only; Snowflake connects as the read-Gold-only role
    (NFR-12). Column names are lowercase on both engines.
    """
    if settings.serving_warehouse == "snowflake":
        con = snowflake_connect(settings, role=settings.snowflake_serve_role)
        try:
            cur = con.cursor()
            # queries use DuckDB's "?" placeholders; the Snowflake connector's default is "%s"
            cur.execute(query.replace("?", "%s") if params else query, params or None)
            names = [d[0].lower() for d in cur.description]
            return [dict(zip(names, row, strict=True)) for row in cur.fetchall()]
        finally:
            con.close()
    con = duckdb_connect(settings, read_only=True)
    try:
        cur = con.execute(query, params or [])
        names = [d[0].lower() for d in cur.description]
        return [dict(zip(names, row, strict=True)) for row in cur.fetchall()]
    finally:
        con.close()
