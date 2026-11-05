"""Load raw posting files into the Bronze layer of the DuckDB warehouse.

Files are expected at ``<bronze_root>/<source_id>/<batch_id>/postings/*.json``, one
JSON object per file. Each file becomes one row in ``bronze.raw_postings``, holding the
original JSON unchanged plus load metadata (FR-ING-03).

Loading is idempotent (FR-ING-04): a row is identified by (source_id, batch_id,
source_posting_id), and re-loading a batch never creates duplicates. Bronze is
immutable: if a re-delivered file has different content for an existing key, the
original row is kept and the difference is reported as a conflict.

Every load is recorded in ``bronze.load_runs`` with its counts (FR-OBS-01).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import duckdb

# JSON fields tried, in order, for the source's own identifier of a posting
ID_FIELDS = ("source_posting_id", "job_id", "id")

DDL = """
create schema if not exists bronze;

create table if not exists bronze.raw_postings (
    source_id          varchar      not null,  -- which system the record came from
    batch_id           varchar      not null,  -- which collection run delivered it
    source_posting_id  varchar      not null,  -- the source's own identifier
    record_hash        varchar      not null,  -- sha256 of the raw file content
    payload            json         not null,  -- the record exactly as received
    file_name          varchar      not null,  -- path relative to the Bronze root
    loaded_at          timestamptz  not null,
    load_run_id        varchar      not null,
    primary key (source_id, batch_id, source_posting_id)
);

create table if not exists bronze.load_runs (
    load_run_id        varchar      primary key,
    source_id          varchar      not null,
    batch_id           varchar      not null,
    started_at         timestamptz  not null,
    finished_at        timestamptz,
    files_seen         integer,
    rows_inserted      integer,     -- new rows written
    rows_unchanged     integer,     -- already loaded with identical content
    rows_conflicting   integer,     -- already loaded, but the new file differs
    rows_invalid       integer,     -- not valid JSON, or no identifier
    status             varchar      not null,
    error              varchar
);
"""


@dataclass(frozen=True)
class Batch:
    source_id: str
    batch_id: str
    postings_dir: Path

    @property
    def files(self) -> list[Path]:
        return sorted(self.postings_dir.glob("*.json"))


@dataclass(frozen=True)
class LoadResult:
    load_run_id: str
    source_id: str
    batch_id: str
    files_seen: int
    rows_inserted: int
    rows_unchanged: int
    rows_conflicting: int
    rows_invalid: int
    status: str
    error: str | None = None


def discover_batches(bronze_root: Path, source_id: str | None = None, batch_id: str | None = None) -> list[Batch]:
    """Find every <source>/<batch>/postings directory under the Bronze root."""
    batches = []
    for postings_dir in sorted(bronze_root.glob("*/*/postings")):
        batch = Batch(postings_dir.parent.parent.name, postings_dir.parent.name, postings_dir)
        if source_id and batch.source_id != source_id:
            continue
        if batch_id and batch.batch_id != batch_id:
            continue
        batches.append(batch)
    return batches


def ensure_schema(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(DDL)


def _id_expression() -> str:
    parts = ", ".join(f"json_extract_string(content, '$.{field}')" for field in ID_FIELDS)
    return f"coalesce({parts})"


def load_batch(con: duckdb.DuckDBPyConnection, bronze_root: Path, batch: Batch) -> LoadResult:
    """Load one batch. Never raises for data problems; they are counted and recorded."""
    run_id = str(uuid.uuid4())
    started = datetime.now(UTC)
    files = batch.files
    con.execute(
        "insert into bronze.load_runs (load_run_id, source_id, batch_id, started_at, files_seen, status) "
        "values (?, ?, ?, ?, ?, 'running')",
        [run_id, batch.source_id, batch.batch_id, started, len(files)],
    )

    if not files:
        return _finish(con, run_id, batch, len(files), 0, 0, 0, 0, "empty")

    # SQL substr() is 1-based: skip "<root>/" so file_name is relative to the Bronze root.
    relative_start = len(str(bronze_root.resolve())) + 2
    try:
        con.execute("begin transaction")
        # 1. Read every file in one pass and classify it.
        con.execute(
            f"""
            create or replace temp table staged as
            with raw as (
                select filename, content, json_valid(content) as is_json
                from read_text(?)
            )
            select
                substr(filename, {relative_start})                         as file_name,
                content,
                sha256(content)                                           as record_hash,
                case when is_json then {_id_expression()} end             as source_posting_id
            from raw
            """,
            [str(batch.postings_dir.resolve() / "*.json")],
        )
        # 2. Compare with what Bronze already holds for this batch.
        (invalid, unchanged, conflicting) = con.execute(
            """
            select
                count(*) filter (where s.source_posting_id is null),
                count(*) filter (where r.record_hash = s.record_hash),
                count(*) filter (where r.record_hash <> s.record_hash)
            from staged s
            left join bronze.raw_postings r
              on  r.source_id = ? and r.batch_id = ?
              and r.source_posting_id = s.source_posting_id
            """,
            [batch.source_id, batch.batch_id],
        ).fetchone()
        # 3. Insert only rows that are new. Bronze rows are never overwritten.
        (inserted,) = con.execute(
            """
            insert into bronze.raw_postings
            select ?, ?, s.source_posting_id, s.record_hash, s.content::json, s.file_name, ?, ?
            from staged s
            where s.source_posting_id is not null
              and not exists (
                  select 1 from bronze.raw_postings r
                  where r.source_id = ? and r.batch_id = ? and r.source_posting_id = s.source_posting_id
              )
            qualify row_number() over (partition by s.source_posting_id order by s.file_name) = 1
            """,
            [batch.source_id, batch.batch_id, started, run_id, batch.source_id, batch.batch_id],
        ).fetchone()
        con.execute("drop table staged")
        con.execute("commit")
    except Exception as exc:
        con.execute("rollback")
        return _finish(con, run_id, batch, len(files), 0, 0, 0, 0, "failed", f"{type(exc).__name__}: {exc}")

    status = "succeeded" if not (invalid or conflicting) else "succeeded_with_warnings"
    return _finish(con, run_id, batch, len(files), inserted, unchanged, conflicting, invalid, status)


def _finish(con, run_id, batch, files_seen, inserted, unchanged, conflicting, invalid, status, error=None):
    con.execute(
        """
        update bronze.load_runs
        set finished_at = ?, rows_inserted = ?, rows_unchanged = ?, rows_conflicting = ?,
            rows_invalid = ?, status = ?, error = ?
        where load_run_id = ?
        """,
        [datetime.now(UTC), inserted, unchanged, conflicting, invalid, status, error, run_id],
    )
    return LoadResult(
        run_id, batch.source_id, batch.batch_id, files_seen, inserted, unchanged, conflicting, invalid, status, error
    )


def load_all(
    duckdb_path: Path, bronze_root: Path, source_id: str | None = None, batch_id: str | None = None
) -> list[LoadResult]:
    """Load every matching batch. Each batch is independent: one failure doesn't stop the rest (NFR-16)."""
    duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(duckdb_path)) as con:
        ensure_schema(con)
        return [load_batch(con, bronze_root, b) for b in discover_batches(bronze_root, source_id, batch_id)]


def bronze_summary(duckdb_path: Path) -> list[tuple]:
    """Rows per source and batch, with the latest load time."""
    with duckdb.connect(str(duckdb_path)) as con:
        ensure_schema(con)
        return con.execute(
            """
            select source_id, batch_id, count(*) as postings, max(loaded_at) as last_loaded
            from bronze.raw_postings
            group by all
            order by source_id, batch_id
            """
        ).fetchall()
