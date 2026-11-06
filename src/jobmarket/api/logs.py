"""Request log (FR-OBS-02): route, latency, tokens and estimated cost per API request.

Stored in ``public.api_requests`` in the vector database, next to the index builds, so
the health view (Phase 8) can read both. The question text is logged for /ask and
/search; resume content never is (NFR-10): /match logs only counts.
"""

from __future__ import annotations

import logging

import psycopg

from jobmarket.llm import ChatResult

log = logging.getLogger("jobmarket.api")

# USD per million tokens (input, output), list prices when this was written. Free-tier use
# costs nothing (NFR-08); these give the paid-tier equivalent, for the budget decision.
PRICE_PER_MILLION = {
    "groq:openai/gpt-oss-120b": (0.15, 0.60),
    "groq:openai/gpt-oss-20b": (0.075, 0.30),
    "gemini:gemini-2.5-flash": (0.30, 2.50),
    "gemini:gemini-2.5-flash-lite": (0.10, 0.40),
}

DDL = """
create table if not exists public.api_requests (
    request_id        text primary key,
    requested_at      timestamptz not null default now(),
    endpoint          text not null,
    status_code       int not null,
    route             text,
    latency_ms        int not null,
    provider          text,
    model             text,
    input_tokens      int not null default 0,
    output_tokens     int not null default 0,
    paid_equivalent_usd numeric(12, 6) not null default 0,
    question          text,
    error             text
)"""


def paid_equivalent_usd(calls: list[ChatResult]) -> float:
    total = 0.0
    for c in calls:
        price_in, price_out = PRICE_PER_MILLION.get(f"{c.provider}:{c.model}", (0.0, 0.0))
        total += (c.input_tokens * price_in + c.output_tokens * price_out) / 1_000_000
    return round(total, 6)


def record(
    dsn: str,
    *,
    request_id: str,
    endpoint: str,
    status_code: int,
    latency_ms: int,
    route: str | None = None,
    calls: list[ChatResult] | None = None,
    question: str | None = None,
    error: str | None = None,
) -> None:
    """Write one log row. Logging must never break a request, so failures only warn."""
    calls = calls or []
    try:
        with psycopg.connect(dsn, autocommit=True) as con:
            con.execute(DDL)
            con.execute(
                "insert into public.api_requests (request_id, endpoint, status_code, route, latency_ms, provider, "
                "model, input_tokens, output_tokens, paid_equivalent_usd, question, error) "
                "values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                [
                    request_id,
                    endpoint,
                    status_code,
                    route,
                    latency_ms,
                    calls[-1].provider if calls else None,
                    calls[-1].model if calls else None,
                    sum(c.input_tokens for c in calls),
                    sum(c.output_tokens for c in calls),
                    paid_equivalent_usd(calls),
                    question,
                    error,
                ],
            )
    except psycopg.Error as exc:
        log.warning("could not write request log: %s", exc.__class__.__name__)
