"""Streaming path: new postings searchable within minutes (Phase 4, ADR-0009, Lambda).

    jobmarket stream produce [--interval 900]   poll sources, publish new postings
    jobmarket stream consume                     land them in Bronze and the index

Producer: polls every Greenhouse board; any job in a target location that isn't in
Bronze and hasn't been published before becomes a ``posting.detected`` event on the
Kafka topic ``postings.detected``, keyed by posting_key (FR-STR-01).

Consumer: for each event, (1) writes the job to Bronze in exactly the collector's
format, in batch ``stream-<date>``, so the raw record is kept (NFR-26) and the daily
batch loads it; (2) builds a *provisional* document and indexes it straight away
(FR-STR-02); (3) records detection-to-index latency (NFR-02).

The provisional document is built in Python from the same seed files the dbt models
use (city aliases, skill dictionary, seniority and work-mode rules, target-role
pattern). The posting_key is the same md5(source | id) the warehouse computes, so the
next daily batch reconciles it to one posting (FR-STR-03) and replaces the provisional
text with the warehouse version: the batch layer is the source of truth.
"""

from __future__ import annotations

import csv
import hashlib
import html
import json
import re
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from functools import lru_cache
from pathlib import Path

import httpx
import psycopg

from jobmarket.index import store
from jobmarket.index.build import build_index
from jobmarket.ingestion import greenhouse
from jobmarket.llm import Embedder
from jobmarket.settings import REPO_ROOT, Settings
from jobmarket.skills import extract_skills

TOPIC = "postings.detected"
EVENT_TYPE = "posting.detected.v1"
SEEDS = REPO_ROOT / "transform" / "seeds"

STREAM_DDL = """
create table if not exists public.stream_events (
    event_id      text primary key,
    posting_key   text not null,
    detected_at   timestamptz not null,
    processed_at  timestamptz not null default now(),
    outcome       text not null,
    index_seconds numeric
)"""


def posting_key(source_id: str, source_posting_id: str) -> str:
    """Identical to the warehouse's md5(source_id || '|' || source_posting_id)."""
    return hashlib.md5(f"{source_id}|{source_posting_id}".encode()).hexdigest()


# --- provisional document: the warehouse rules, applied in Python -------------------


def _posix_to_python(pattern: str) -> str:
    return pattern.replace("[[:space:]]", r"\s")


def _whole_word(pattern: str) -> re.Pattern[str]:
    return re.compile(rf"(^|[^a-z0-9])({_posix_to_python(pattern)})([^a-z0-9]|$)")


@lru_cache
def _rules(name: str, value_column: str) -> tuple[tuple[int, str, str, re.Pattern[str]], ...]:
    with (SEEDS / f"{name}.csv").open(newline="") as f:
        rows = [
            (int(r["rule_order"]), r[value_column], r["field"], _whole_word(r["pattern"])) for r in csv.DictReader(f)
        ]
    return tuple(sorted(rows))


@lru_cache
def _target_role_pattern() -> re.Pattern[str]:
    macros = (REPO_ROOT / "transform" / "macros" / "portability.sql").read_text()
    body = re.search(r"macro target_role_pattern\(\) -%}\s*(.*?)\s*{%- endmacro", macros, re.DOTALL).group(1)
    return re.compile(body.strip())


@lru_cache
def _city_aliases() -> tuple[tuple[int, str, re.Pattern[str]], ...]:
    rank = {"city": 1, "area": 2, "state": 3, "remote": 4}
    with (SEEDS / "city_aliases.csv").open(newline="") as f:
        rows = [
            (rank[r["match_level"]], r["city"], re.compile(rf"(^|[^a-z]){re.escape(r['alias'])}([^a-z]|$)"))
            for r in csv.DictReader(f)
        ]
    return tuple(sorted(rows, key=lambda r: r[0]))


EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+[.][A-Za-z]{2,}")
PHONE = re.compile(r"([+]91[ -]?)?[6-9][0-9]{4}[ -]?[0-9]{5}")


def html_to_text(raw: str) -> str:
    text = html.unescape(html.unescape(raw or ""))
    text = re.sub(r"(?i)<\s*(br|/p|/li|/h[1-6]|/div)\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"[ \t]+", " ", html.unescape(text)).strip()


def redact(text: str) -> str:
    return PHONE.sub("[phone removed]", EMAIL.sub("[email removed]", text))


def resolve_city(location: str) -> str | None:
    lowered = location.lower()
    return next((city for _, city, pattern in _city_aliases() if pattern.search(lowered)), None)


def provisional_document(record: dict) -> dict | None:
    """The index document for a streamed Greenhouse record; None if out of scope."""
    job = record["job"]
    title = (job.get("title") or "").strip()
    # like slv_postings: the city comes from the job's own location, not its offices
    location = (job.get("location") or {}).get("name") or ""
    city = resolve_city(location)
    if not city or not _target_role_pattern().search(title.lower()):
        return None
    description = redact(html_to_text(job.get("content") or ""))
    fields = {
        "title": title.lower(),
        "source": "",
        "title_location": f"{title} | {location}".lower(),
        "description": description.lower(),
    }
    seniority = next(
        (
            v
            for _, v, field, p in _rules("seniority_rules", "seniority")
            if field == "title" and p.search(fields["title"])
        ),
        "unknown",
    )
    work_mode = next(
        (v for _, v, field, p in _rules("work_mode_rules", "work_mode") if p.search(fields[field])), "unknown"
    )
    company = record.get("company_name") or ""
    return {
        "posting_key": posting_key("greenhouse", str(job["id"])),
        "title": title,
        "company_name": company,
        "city": city,
        "is_remote_india": city == "Remote (India)",
        "work_mode": work_mode,
        "seniority": seniority,
        "min_years_experience": None,
        "status": "open",
        "posted_date": date.fromisoformat(
            (job.get("first_published") or job.get("updated_at") or "")[:10] or date.today().isoformat()
        ),
        "last_seen_at": datetime.now(UTC),
        "url": job.get("absolute_url"),
        "source_key": "greenhouse",
        "skills": "|".join(sorted({s.name for s in extract_skills(f"{title} {description}")})),
        "description_text": description,
        "document_hash": "provisional:" + hashlib.md5(f"{title}|{company}|{city}|{description}".encode()).hexdigest(),
    }


# --- producer ---------------------------------------------------------------------


def known_posting_ids(settings: Settings) -> set[str]:
    """Greenhouse job ids already in Bronze, from any batch (daily or streamed)."""
    return {p.stem for p in (settings.bronze_root / "greenhouse").glob("*/postings/*.json")}


@dataclass
class ProduceResult:
    boards: int
    seen: int
    published: int


def produce_once(settings: Settings, producer, state_file: Path) -> ProduceResult:
    emitted = set(json.loads(state_file.read_text())) if state_file.exists() else set()
    known = known_posting_ids(settings) | emitted
    pattern = greenhouse.city_pattern()
    boards = greenhouse.load_boards()
    seen = published = 0
    with httpx.Client(headers={"User-Agent": greenhouse.USER_AGENT}) as client:
        for board in boards:
            try:
                jobs = greenhouse.fetch_board(client, board.token)
            except Exception:
                continue
            for job in jobs:
                if not greenhouse.in_target_city(job, pattern):
                    continue
                seen += 1
                job_id = str(job["id"])
                if job_id in known:
                    continue
                event = {
                    "event_id": uuid.uuid4().hex,
                    "event_type": EVENT_TYPE,
                    "detected_at": datetime.now(UTC).isoformat(),
                    "source_id": "greenhouse",
                    "posting_key": posting_key("greenhouse", job_id),
                    "record": {
                        "source_posting_id": job_id,
                        "board_token": board.token,
                        "company_name": board.company_name,
                        "collected_at": datetime.now(UTC).isoformat(),
                        "job": job,
                    },
                }
                producer.produce(TOPIC, key=event["posting_key"], value=json.dumps(event).encode())
                known.add(job_id)
                emitted.add(job_id)
                published += 1
            time.sleep(greenhouse.DELAY_BETWEEN_BOARDS_SECONDS)
    producer.flush(30)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(sorted(emitted)))
    return ProduceResult(len(boards), seen, published)


# --- consumer ---------------------------------------------------------------------


def land_in_bronze(settings: Settings, event: dict) -> Path:
    """Write the record exactly as the collector would, in batch stream-<date> (NFR-26)."""
    batch = "stream-" + event["detected_at"][:10]
    record = event["record"]
    path = settings.bronze_root / "greenhouse" / batch / "postings" / f"{record['source_posting_id']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(record, ensure_ascii=False, indent=1))
    tmp.replace(path)
    return path


def handle_event(settings: Settings, embedder: Embedder, event: dict) -> str:
    """Process one event; returns the outcome. Safe to repeat (at-least-once delivery)."""
    started = time.perf_counter()
    land_in_bronze(settings, event)
    schema = store.schema_for(embedder.name)
    dsn = settings.vectordb_dsn.get_secret_value()
    with psycopg.connect(dsn) as con:
        store.ensure_schema(con, schema, embedder.dimensions)  # the stream may run before any batch build
    with psycopg.connect(dsn, autocommit=True) as con:
        con.execute(STREAM_DDL)
        already = con.execute(
            f"select 1 from {schema}.postings where posting_key = %s", [event["posting_key"]]
        ).fetchone()
    doc = None if already else provisional_document(event["record"])
    if already:
        outcome = "already_indexed"  # the batch layer has it; it wins
    elif doc is None:
        outcome = "out_of_scope"
    else:
        build_index(settings, embedder, docs=[doc], schema=schema, remove_missing=False, source_label="stream")
        outcome = "indexed"
    with psycopg.connect(dsn, autocommit=True) as con:
        con.execute(
            "insert into public.stream_events (event_id, posting_key, detected_at, outcome, index_seconds) "
            "values (%s, %s, %s, %s, %s) on conflict (event_id) do nothing",
            [
                event["event_id"],
                event["posting_key"],
                event["detected_at"],
                outcome,
                round(time.perf_counter() - started, 3),
            ],
        )
    return outcome
