"""Collector for the Greenhouse Job Board API.

The Job Board API is public: "authentication is not required for any GET endpoints"
(docs.greenhouse.io/job-board.html). Terms review: docs/requirements/data_sources.md.

For each board in config/greenhouse_boards.csv the collector makes **one** request,
``GET /v1/boards/{token}/jobs?content=true``, keeps jobs located in a target city, and
writes each one as a Bronze file (FR-ING-01..07):

    data/bronze/greenhouse/<batch_id>/postings/<job id>.json   one job, as received
    data/bronze/greenhouse/<batch_id>/_run.json                per-board run summary

A failing board is recorded and skipped; the others continue (FR-ING-02, NFR-16).
Re-running a batch rewrites the same files, so it never creates duplicates (FR-ING-04).
"""

from __future__ import annotations

import csv
import json
import re
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx

from jobmarket.settings import REPO_ROOT

SOURCE_ID = "greenhouse"
API_BASE = "https://boards-api.greenhouse.io/v1/boards"
USER_AGENT = "job-market-assistant/0.1 (+https://github.com/vvanurag/job-market-assistant)"
BOARDS_FILE = REPO_ROOT / "config" / "greenhouse_boards.csv"
CITY_ALIASES_FILE = REPO_ROOT / "transform" / "seeds" / "city_aliases.csv"

DELAY_BETWEEN_BOARDS_SECONDS = 1.0
RETRY_WAITS_SECONDS = (5, 30)  # after the first and second failed attempt
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class Board:
    token: str
    company_name: str


@dataclass
class BoardResult:
    token: str
    company_name: str
    status: str  # ok | failed
    jobs_total: int = 0
    jobs_kept: int = 0
    error: str | None = None


def load_boards(path: Path = BOARDS_FILE) -> list[Board]:
    with path.open(newline="") as f:
        return [Board(r["board_token"].strip(), r["company_name"].strip()) for r in csv.DictReader(f)]


def city_pattern(path: Path = CITY_ALIASES_FILE) -> re.Pattern[str]:
    """One regex built from the same alias list the Silver layer uses, so both agree."""
    with path.open(newline="") as f:
        aliases = sorted({r["alias"].strip().lower() for r in csv.DictReader(f)}, key=len, reverse=True)
    alternatives = "|".join(re.escape(a) for a in aliases)
    # Whole words only, like the Silver model: "remote - india" must not match "Remote - Indiana".
    return re.compile(f"(?<![a-z])(?:{alternatives})(?![a-z])", re.IGNORECASE)


def job_locations(job: dict) -> list[str]:
    """Every location string on a job: its own location plus its offices."""
    names = [(job.get("location") or {}).get("name") or ""]
    for office in job.get("offices") or []:
        names += [office.get("name") or "", office.get("location") or ""]
    return [n for n in names if n]


def in_target_city(job: dict, pattern: re.Pattern[str]) -> bool:
    return any(pattern.search(name) for name in job_locations(job))


def fetch_board(client: httpx.Client, token: str, sleep: Callable[[float], None] = time.sleep) -> list[dict]:
    """Fetch every published job on a board, with descriptions. Retries transient errors."""
    url = f"{API_BASE}/{token}/jobs"
    for attempt in range(len(RETRY_WAITS_SECONDS) + 1):
        try:
            resp = client.get(url, params={"content": "true"}, timeout=30)
        except httpx.TransportError:
            if attempt == len(RETRY_WAITS_SECONDS):
                raise
        else:
            if resp.status_code == 200:
                return resp.json().get("jobs", [])
            if resp.status_code not in RETRYABLE_STATUS or attempt == len(RETRY_WAITS_SECONDS):
                resp.raise_for_status()
        sleep(RETRY_WAITS_SECONDS[attempt])
    raise RuntimeError("unreachable")


def _write_json(path: Path, record: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2))
    tmp.replace(path)


def collect(
    bronze_root: Path,
    batch_id: str,
    boards: list[Board],
    client: httpx.Client | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> list[BoardResult]:
    """Collect all boards into one Bronze batch and return a result per board."""
    batch_dir = bronze_root / SOURCE_ID / batch_id
    postings_dir = batch_dir / "postings"
    postings_dir.mkdir(parents=True, exist_ok=True)
    pattern = city_pattern()
    started = datetime.now(UTC).isoformat()
    results: list[BoardResult] = []

    with client or httpx.Client(headers={"User-Agent": USER_AGENT}) as http:
        for i, board in enumerate(boards):
            if i:
                sleep(DELAY_BETWEEN_BOARDS_SECONDS)
            result = BoardResult(board.token, board.company_name, status="ok")
            try:
                jobs = fetch_board(http, board.token, sleep)
            except Exception as exc:
                result.status, result.error = "failed", f"{type(exc).__name__}: {exc}"[:300]
                results.append(result)
                continue

            collected_at = datetime.now(UTC).isoformat()
            result.jobs_total = len(jobs)
            for job in jobs:
                if not in_target_city(job, pattern):
                    continue
                record = {
                    "source_posting_id": str(job["id"]),
                    "board_token": board.token,
                    "company_name": board.company_name,
                    "collected_at": collected_at,
                    "job": job,  # the job object exactly as the API returned it
                }
                _write_json(postings_dir / f"{job['id']}.json", record)
                result.jobs_kept += 1
            results.append(result)

    _write_json(
        batch_dir / "_run.json",
        {
            "source_id": SOURCE_ID,
            "batch_id": batch_id,
            "started_at": started,
            "finished_at": datetime.now(UTC).isoformat(),
            "boards": [asdict(r) for r in results],
        },
    )
    return results
