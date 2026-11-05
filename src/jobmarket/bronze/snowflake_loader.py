"""Load raw posting files into the Bronze layer in Snowflake.

Same contract as the DuckDB loader (``loader.py``), so both warehouses hold identical
Bronze data:

* table ``BRONZE.RAW_POSTINGS``, keyed on (source_id, batch_id, source_posting_id)
* the payload stored unchanged (as VARIANT), with a SHA-256 fingerprint of the exact
  file text, identical to the DuckDB fingerprint
* idempotent: re-runs insert nothing; changed content is reported, never overwritten
* every load recorded in ``BRONZE.LOAD_RUNS``

Steps per batch: PUT the files into the stage ``BRONZE.RAW_FILES`` (which also keeps a
file copy, NFR-26), COPY each file's text into a temporary table, then insert new rows.
Runs as JMA_INGEST, the role that may only write Bronze (NFR-12).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from jobmarket.bronze.loader import ID_FIELDS, Batch, LoadResult, discover_batches
from jobmarket.settings import Settings
from jobmarket.warehouse import snowflake_connect

STAGE = "bronze.raw_files"

DDL = [
    """
    create table if not exists bronze.raw_postings (
        source_id          varchar        not null,
        batch_id           varchar        not null,
        source_posting_id  varchar        not null,
        record_hash        varchar        not null,
        payload            variant        not null,
        file_name          varchar        not null,
        loaded_at          timestamp_tz   not null,
        load_run_id        varchar        not null,
        primary key (source_id, batch_id, source_posting_id)
    )
    """,
    """
    create table if not exists bronze.load_runs (
        load_run_id        varchar        primary key,
        source_id          varchar        not null,
        batch_id           varchar        not null,
        started_at         timestamp_tz   not null,
        finished_at        timestamp_tz,
        files_seen         integer,
        rows_inserted      integer,
        rows_unchanged     integer,
        rows_conflicting   integer,
        rows_invalid       integer,
        status             varchar        not null,
        error              varchar
    )
    """,
]

# Read each file as a single text value: no field or record splitting, no escape processing,
# so the text (and therefore its fingerprint) is byte-for-byte what is on disk.
WHOLE_FILE_AS_TEXT = (
    "type = csv field_delimiter = none record_delimiter = none "
    "escape_unenclosed_field = none field_optionally_enclosed_by = none "
    "encoding = 'UTF8' null_if = ()"
)


def _id_expression() -> str:
    parts = ", ".join(f"payload:{field}::varchar" for field in ID_FIELDS)
    return f"coalesce({parts})"


def load_batch(cur, batch: Batch) -> LoadResult:
    run_id = str(uuid.uuid4())
    started = datetime.now(UTC)
    files = batch.files
    cur.execute(
        "insert into bronze.load_runs (load_run_id, source_id, batch_id, started_at, files_seen, status) "
        "values (%s, %s, %s, %s, %s, 'running')",
        (run_id, batch.source_id, batch.batch_id, started, len(files)),
    )
    if not files:
        return _finish(cur, run_id, batch, 0, 0, 0, 0, 0, "empty")

    stage_path = f"{batch.source_id}/{batch.batch_id}/postings/"
    try:
        local = Path(batch.postings_dir).resolve().as_posix()
        cur.execute(
            f"put 'file://{local}/*.json' @{STAGE}/{stage_path} auto_compress = true overwrite = true parallel = 8"
        )

        cur.execute("begin")
        cur.execute("create or replace temporary table staged_files (file_name varchar, content varchar)")
        cur.execute(
            f"""
            copy into staged_files
            from (select metadata$filename, $1 from @{STAGE}/{stage_path})
            file_format = ({WHOLE_FILE_AS_TEXT})
            force = true
            """
        )
        cur.execute(
            f"""
            create or replace temporary table staged as
            with parsed as (
                select
                    regexp_replace(file_name, '[.]gz$', '') as file_name,
                    content,
                    sha2(content, 256)                      as record_hash,
                    try_parse_json(content)                 as payload
                from staged_files
            )
            select file_name, content, record_hash, payload,
                   case when payload is not null then {_id_expression()} end as source_posting_id
            from parsed
            """
        )
        cur.execute(
            """
            select
                count_if(s.source_posting_id is null),
                count_if(r.record_hash = s.record_hash),
                count_if(r.record_hash <> s.record_hash)
            from staged s
            left join bronze.raw_postings r
              on  r.source_id = %s and r.batch_id = %s
              and r.source_posting_id = s.source_posting_id
            """,
            (batch.source_id, batch.batch_id),
        )
        invalid, unchanged, conflicting = cur.fetchone()
        cur.execute(
            """
            insert into bronze.raw_postings
            select %s, %s, s.source_posting_id, s.record_hash, s.payload, s.file_name, %s, %s
            from staged s
            where s.source_posting_id is not null
              and not exists (
                  select 1 from bronze.raw_postings r
                  where r.source_id = %s and r.batch_id = %s and r.source_posting_id = s.source_posting_id
              )
            qualify row_number() over (partition by s.source_posting_id order by s.file_name) = 1
            """,
            (batch.source_id, batch.batch_id, started, run_id, batch.source_id, batch.batch_id),
        )
        inserted = cur.rowcount
        cur.execute("commit")
    except Exception as exc:
        cur.execute("rollback")
        return _finish(cur, run_id, batch, len(files), 0, 0, 0, 0, "failed", f"{type(exc).__name__}: {exc}"[:500])

    status = "succeeded" if not (invalid or conflicting) else "succeeded_with_warnings"
    return _finish(cur, run_id, batch, len(files), inserted, unchanged, conflicting, invalid, status)


def _finish(cur, run_id, batch, files_seen, inserted, unchanged, conflicting, invalid, status, error=None):
    cur.execute(
        """
        update bronze.load_runs
        set finished_at = %s, rows_inserted = %s, rows_unchanged = %s, rows_conflicting = %s,
            rows_invalid = %s, status = %s, error = %s
        where load_run_id = %s
        """,
        (datetime.now(UTC), inserted, unchanged, conflicting, invalid, status, error, run_id),
    )
    return LoadResult(
        run_id, batch.source_id, batch.batch_id, files_seen, inserted, unchanged, conflicting, invalid, status, error
    )


def load_all(
    settings: Settings, bronze_root: Path, source_id: str | None = None, batch_id: str | None = None
) -> list[LoadResult]:
    with snowflake_connect(settings, role=settings.snowflake_ingest_role) as con, con.cursor() as cur:
        cur.execute("use schema bronze")
        for statement in DDL:
            cur.execute(statement)
        return [load_batch(cur, b) for b in discover_batches(bronze_root, source_id, batch_id)]
