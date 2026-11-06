"""Data-quality experiment (goal G4, Evaluation Plan section 5).

Retrieval-only: the same semantic questions are searched under progressively better
data and search settings, changing one thing per step, and scored with the same
retrieval metrics as the main evaluation. No language model is involved, so results
reflect only the data engineering.

  A  every posting indexed: reposts and cross-source copies included; vector search,
     no filters (index idx_exp_all_postings)
  B  deduplicated jobs: the production index; vector search, no filters
  C  B + closed postings excluded
  D  C + the metadata filters the router chose for each question
  E  D + hybrid (keyword + vector) search

All variants use the router's rewritten query from a baseline evaluation run, so the
query text is identical across variants.
"""

from __future__ import annotations

import json
import statistics
from datetime import date
from pathlib import Path

from jobmarket.api.assistant import SearchPlan, to_index_filters
from jobmarket.api.metrics import MetricFilters
from jobmarket.evaluation.runner import RESULTS_DIR, load_eval_set, relevant_jobs, retrieval_scores, top_jobs
from jobmarket.index import store
from jobmarket.index.build import build_index
from jobmarket.llm import Embedder
from jobmarket.settings import Settings
from jobmarket.warehouse import duckdb_connect

EXPERIMENT_SCHEMA = "idx_exp_all_postings"

ALL_POSTINGS_SQL = """
select p.posting_key, p.title, p.company_name, p.city, false as is_remote_india,
       'unknown' as work_mode, 'unknown' as seniority, cast(null as integer) as min_years_experience,
       'open' as status, p.posted_date, cast(null as timestamp) as last_seen_at, p.url, p.source_id as source_key,
       '' as skills, p.description_text,
       md5(p.title || '|' || p.company_name || '|' || p.city || '|' || p.description_text) as document_hash
from silver.slv_postings p
where p.is_target_role
"""


def _rows(settings: Settings, sql: str) -> list[dict]:
    con = duckdb_connect(settings, read_only=True)
    try:
        cur = con.execute(sql)
        names = [d[0] for d in cur.description]
        return [dict(zip(names, r, strict=True)) for r in cur.fetchall()]
    finally:
        con.close()


def build_all_postings_index(settings: Settings, embedder: Embedder, progress=print):
    """Index A: every target-role posting in Silver, without deduplication (DuckDB only)."""
    return build_index(
        settings, embedder, docs=_rows(settings, ALL_POSTINGS_SQL), schema=EXPERIMENT_SCHEMA, progress=progress
    )


def run_experiment(settings: Settings, embedder: Embedder, baseline_run: Path) -> dict:
    plans = {r["id"]: r.get("plan") or {} for r in json.loads(baseline_run.read_text())["rows"]}
    job_of = {
        r["posting_key"]: r["job_key"]
        for r in _rows(settings, "select posting_key, job_key from silver.slv_posting_jobs")
    }
    production = store.schema_for(embedder.name)
    variants = {
        "A": (EXPERIMENT_SCHEMA, "vector", "none"),
        "B": (production, "vector", "none"),
        "C": (production, "vector", "open"),
        "D": (production, "vector", "router"),
        "E": (production, "hybrid", "router"),
    }
    today = date.today()
    per_question: dict[str, dict] = {}
    with store.connect(settings.vectordb_dsn.get_secret_value()) as con:
        for q in load_eval_set():
            if not q.get("relevant"):
                continue
            plan = SearchPlan.model_validate((plans.get(q["id"]) or {}).get("search") or {"query": q["question"]})
            relevant = relevant_jobs(settings, q["relevant"], today)
            vector = embedder.embed_query(plan.query)
            scores = {}
            for name, (schema, mode, filtering) in variants.items():
                if filtering == "none":
                    filters = store.Filters(include_closed=True)
                elif filtering == "open":
                    filters = store.Filters()
                else:
                    filters = to_index_filters(MetricFilters.model_validate(plan.filters.model_dump()))
                hits = store.search(con, schema, plan.query, vector, filters, limit=20, mode=mode)
                scores[name] = retrieval_scores(top_jobs(hits, job_of), relevant)
            per_question[q["id"]] = {"category": q["category"], "query": plan.query, "scores": scores}

    summary = {}
    for name in variants:
        rows = [v["scores"][name] for v in per_question.values()]
        summary[name] = {
            metric: round(statistics.mean(r[metric] for r in rows if r[metric] is not None), 3)
            for metric in ("recall_at_5", "mrr", "duplicate_at_5", "stale_at_5")
        }
        filtered = [
            v["scores"][name]
            for v in per_question.values()
            if v["category"] in ("semantic_filtered", "company", "freshness")
        ]
        summary[name]["recall_at_5_filtered_questions"] = round(
            statistics.mean(r["recall_at_5"] for r in filtered if r["recall_at_5"] is not None), 3
        )
    result = {
        "baseline_run": baseline_run.name,
        "embedding": embedder.name,
        "summary": summary,
        "questions": per_question,
    }
    (RESULTS_DIR / "data_quality_experiment.json").write_text(json.dumps(result, indent=1, default=str))
    return result
