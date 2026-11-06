"""Health view (FR-OBS-03): freshness, volume per source, tests, index, usage and cost.

GET /status renders one plain HTML page from the warehouse and the operations
database. It needs the API key, as a header or as ?key=… for a browser.
"""

from __future__ import annotations

import html

import psycopg

from jobmarket.ops import freshness
from jobmarket.settings import Settings
from jobmarket.warehouse import read_gold


def _table(headers: list[str], rows: list[list]) -> str:
    head = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><tr>{head}</tr>{body or '<tr><td colspan=9>none yet</td></tr>'}</table>"


def collect(settings: Settings) -> dict:
    data: dict = {}
    data["jobs_by_source"] = [
        [r["source_name"], r["collection"], r["jobs"], r["open_jobs"]]
        for r in read_gold(
            settings,
            "select s.source_name, s.collection, count(*) as jobs, "
            "sum(case when f.status = 'open' then 1 else 0 end) as open_jobs "
            "from gold.fct_postings f join gold.dim_source s using (source_key) group by 1, 2 order by 3 desc",
        )
    ]
    try:
        data["freshness"] = [
            [f.source_id, f.last_loaded_at, f.age_hours, "fresh" if f.fresh else "STALE"] for f in freshness(settings)
        ]
    except Exception as exc:
        data["freshness"] = [["(unavailable)", exc.__class__.__name__, "", ""]]
    with psycopg.connect(settings.vectordb_dsn.get_secret_value(), autocommit=True) as con:

        def rows(sql: str) -> list[list]:
            try:
                return [list(r) for r in con.execute(sql).fetchall()]
            except psycopg.errors.UndefinedTable:
                return []

        data["pipeline_runs"] = [
            [
                r[0],
                f"{r[1]:%Y-%m-%d %H:%M}",
                ", ".join((r[2] or {}).get("failed_tasks", [])) or "none",
                (r[2] or {}).get("index", {}).get("embedded", ""),
            ]
            for r in rows(
                "select run_id, recorded_at, summary from public.pipeline_runs order by recorded_at desc limit 5"
            )
        ]
        data["index"] = rows(
            "select build_id, embedding_model, chunker_version, to_char(finished_at, 'YYYY-MM-DD HH24:MI'), "
            "postings_embedded, postings_updated, postings_removed from public.index_builds "
            "where status = 'succeeded' order by build_id desc limit 3"
        )
        data["usage"] = rows(
            "select endpoint, count(*), percentile_cont(0.5) within group (order by latency_ms)::int, "
            "percentile_cont(0.95) within group (order by latency_ms)::int, sum(input_tokens + output_tokens), "
            "round(sum(paid_equivalent_usd), 4) from public.api_requests "
            "where requested_at > now() - interval '7 days' group by 1 order by 1"
        )
        data["alerts"] = rows(
            "select to_char(raised_at, 'YYYY-MM-DD HH24:MI'), kind, message, delivered from public.alerts "
            "order by raised_at desc limit 10"
        )
        data["stream"] = rows(
            "select outcome, count(*), round(avg(extract(epoch from processed_at - detected_at)), 1) "
            "from public.stream_events where processed_at > now() - interval '7 days' group by 1"
        )
    return data


def render(data: dict) -> str:
    sections = [
        ("Freshness (NFR-01: under 26 hours)", ["source", "last load", "age (hours)", "state"], data["freshness"]),
        ("Jobs in Gold by source", ["source", "collection", "jobs", "open"], data["jobs_by_source"]),
        ("Recent pipeline runs", ["run", "recorded", "failed tasks", "jobs embedded"], data["pipeline_runs"]),
        (
            "Index builds",
            ["build", "embedding model", "chunker", "finished", "embedded", "refreshed", "removed"],
            data["index"],
        ),
        (
            "API usage, last 7 days",
            ["endpoint", "requests", "p50 ms", "p95 ms", "tokens", "paid-equivalent USD"],
            data["usage"],
        ),
        ("Streaming, last 7 days", ["outcome", "events", "avg seconds detection to index"], data["stream"]),
        ("Alerts", ["raised", "kind", "message", "delivered"], data["alerts"]),
    ]
    body = "".join(f"<h2>{html.escape(t)}</h2>{_table(h, r)}" for t, h, r in sections)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Job Market Assistant status</title><style>
body{{font:14px/1.45 system-ui,sans-serif;margin:24px;max-width:1100px;color:#1f2328;background:#fff}}
h1{{font-size:20px}}h2{{font-size:15px;margin-top:28px}}table{{border-collapse:collapse;width:100%;overflow-x:auto;display:block}}
th,td{{text-align:left;padding:6px 10px;border-bottom:1px solid #d0d7de;vertical-align:top}}th{{background:#f6f8fa}}
@media (prefers-color-scheme:dark){{body{{color:#e6edf3;background:#0d1117}}th{{background:#161b22}}
th,td{{border-color:#30363d}}}}
</style></head><body><h1>Job Market Assistant: status</h1>{body}</body></html>"""
