"""Pipeline operations: freshness checks, alerts and run records (Phase 3).

    jobmarket ops freshness            exit 1 if a daily source is older than 26 hours (NFR-01)
    jobmarket ops alert "<message>"    record an alert and send it to ALERT_WEBHOOK_URL (FR-ORC-04)
    jobmarket ops record-run <run id>  store per-source counts, durations and errors (FR-OBS-01)

Alerts and run records live in the operations database (the vector database's
PostgreSQL), where the health view reads them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx
import psycopg

from jobmarket.settings import REPO_ROOT, Settings
from jobmarket.warehouse import duckdb_connect

FRESHNESS_LIMIT = timedelta(hours=26)  # NFR-01
DAILY_SOURCES = ("greenhouse",)

OPS_DDL = """
create table if not exists public.alerts (
    alert_id     bigserial primary key,
    raised_at    timestamptz not null default now(),
    kind         text not null,
    message      text not null,
    delivered    boolean not null default false
);
create table if not exists public.pipeline_runs (
    run_id        text primary key,
    recorded_at   timestamptz not null default now(),
    summary       jsonb not null
);
"""


def _ops(settings: Settings) -> psycopg.Connection:
    con = psycopg.connect(settings.vectordb_dsn.get_secret_value(), autocommit=True)
    con.execute(OPS_DDL)
    return con


@dataclass
class Freshness:
    source_id: str
    last_loaded_at: datetime | None
    age_hours: float | None
    fresh: bool


def freshness(settings: Settings, now: datetime | None = None) -> list[Freshness]:
    """Age of the newest successfully loaded batch of each daily source."""
    now = now or datetime.now(UTC)
    con = duckdb_connect(settings, read_only=True)
    try:
        rows = dict(
            con.execute(
                "select source_id, max(finished_at) from bronze.load_runs "
                "where status = 'succeeded' and rows_inserted + rows_unchanged > 0 group by 1"
            ).fetchall()
        )
    finally:
        con.close()
    out = []
    for source in DAILY_SOURCES:
        last = rows.get(source)
        age = (now - last).total_seconds() / 3600 if last else None
        out.append(
            Freshness(
                source,
                last,
                round(age, 1) if age is not None else None,
                age is not None and age * 3600 <= FRESHNESS_LIMIT.total_seconds(),
            )
        )
    return out


def alert(settings: Settings, kind: str, message: str) -> bool:
    """Record an alert; deliver it to the webhook if one is configured. True if delivered."""
    delivered = False
    if settings.alert_webhook_url:
        try:
            # ntfy.sh-style endpoints take the message as the body; others accept JSON
            resp = httpx.post(
                settings.alert_webhook_url,
                content=f"[jobmarket] {kind}: {message}".encode(),
                headers={"Title": f"Job Market Assistant: {kind}"},
                timeout=10,
            )
            delivered = resp.status_code < 300
        except httpx.HTTPError:
            delivered = False
    try:
        with _ops(settings) as con:
            con.execute(
                "insert into public.alerts (kind, message, delivered) values (%s, %s, %s)", [kind, message, delivered]
            )
    except psycopg.Error:
        print(f"ALERT ({kind}): {message}")  # last resort: the task log
    return delivered


def record_run(settings: Settings, run_id: str) -> dict:
    """Collect what the run did from the artefacts each step leaves behind. Failed tasks
    come from the alerts their failure callbacks raised for this run."""
    summary: dict = {"run_id": run_id, "sources": {}}
    for source in DAILY_SOURCES:
        runs = sorted((settings.bronze_root / source).glob("*/_run.json"))
        if runs:
            data = json.loads(runs[-1].read_text())
            boards = data.get("boards", [])
            summary["sources"][source] = {
                "batch_id": data.get("batch_id"),
                "jobs_kept": sum(b.get("jobs_kept") or 0 for b in boards),
                "boards_ok": sum(1 for b in boards if b.get("status") == "ok"),
                "boards_failed": [b.get("token") for b in boards if b.get("status") != "ok"],
                "collect_started_at": data.get("started_at"),
                "collect_finished_at": data.get("finished_at"),
            }
    con = duckdb_connect(settings, read_only=True)
    try:
        loads = con.execute(
            "select source_id, batch_id, rows_inserted, rows_unchanged, rows_conflicting, rows_invalid, status, error, "
            "datediff('second', started_at, finished_at) from bronze.load_runs "
            "qualify row_number() over (partition by source_id order by started_at desc) = 1"
        ).fetchall()
    finally:
        con.close()
    for source, batch, new, same, changed, invalid, status, error, seconds in loads:
        summary["sources"].setdefault(source, {}).update(
            load_batch=batch,
            rows_new=new,
            rows_unchanged=same,
            rows_conflicting=changed,
            rows_invalid=invalid,
            load_status=status,
            load_error=error,
            load_seconds=seconds,
        )
    results = REPO_ROOT / "transform" / "target" / "run_results.json"
    if results.exists():
        data = json.loads(results.read_text())
        statuses: dict[str, int] = {}
        for r in data.get("results", []):
            statuses[r["status"]] = statuses.get(r["status"], 0) + 1
        # each per-model Airflow task overwrites run_results.json, so this is the last dbt
        # invocation only; the DAG passes the whole run's task states separately
        summary["last_dbt_invocation"] = {"statuses": statuses, "seconds": round(data.get("elapsed_time", 0), 1)}
    try:
        with _ops(settings) as con:
            row = con.execute(
                "select build_id, postings_embedded, postings_updated, postings_removed, "
                "extract(epoch from finished_at - started_at) from public.index_builds "
                "where status = 'succeeded' order by build_id desc limit 1"
            ).fetchone()
            if row:
                summary["index"] = dict(
                    zip(
                        ["build_id", "embedded", "refreshed", "removed", "seconds"],
                        [row[0], row[1], row[2], row[3], float(row[4] or 0)],
                        strict=True,
                    )
                )
            summary["freshness"] = [f.__dict__ for f in freshness(settings)]
            failed = con.execute(
                "select message from public.alerts where kind = 'task_failed' and message like %s", [f"%{run_id}%"]
            ).fetchall()
            summary["failed_tasks"] = sorted({m[0].split(" failed")[0] for m in failed})
            con.execute(
                "insert into public.pipeline_runs (run_id, summary) values (%s, %s) "
                "on conflict (run_id) do update set summary = excluded.summary, recorded_at = now()",
                [run_id, json.dumps(summary, default=str)],
            )
    except psycopg.Error as exc:
        summary["record_error"] = exc.__class__.__name__
    return summary
