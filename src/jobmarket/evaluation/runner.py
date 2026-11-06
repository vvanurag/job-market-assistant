"""Run the evaluation set and score it (FR-EVL-01, FR-EVL-02, Evaluation Plan).

    jobmarket eval run [--llm groq] [--embedding ollama:nomic-embed-text] [--judge gemini]

Each question goes through the same code as POST /ask (or /match for resume items).
Scores per question are written to eval/results/<run_id>.json together with the full
configuration: commit, models, chunker and prompt versions, and the data snapshot.
Runs are resumable: an interrupted run continues from the questions already scored,
so free-tier rate limits never lose work (NFR-27).

Retrieval metrics are computed on the first 5 distinct jobs retrieved:

  recall@5     relevant jobs in the top 5, divided by min(5, number of relevant jobs).
               Equal to plain recall when 5 or fewer jobs are relevant, and to
               precision@5 when more are, so it is always between 0 and 1.
  MRR          1 / rank of the first relevant job (0 if none in the top 5)
  duplicate@5  share of the top 5 that repeat a job already listed
  stale@5      share of the top 5 that are closed
"""

from __future__ import annotations

import json
import statistics
import subprocess
import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import yaml

from jobmarket.api import assistant
from jobmarket.api.match import match_resume
from jobmarket.api.metrics import MetricFilters
from jobmarket.index.chunking import CHUNKER_VERSION
from jobmarket.llm import LLM, Embedder
from jobmarket.settings import REPO_ROOT, Settings
from jobmarket.warehouse import read_gold

EVAL_SET = REPO_ROOT / "eval" / "eval_set_v1.yaml"
RESULTS_DIR = REPO_ROOT / "eval" / "results"
TOP_K = 5

JUDGE_SYSTEM = """You check answers about job postings against the sources they cite.
Split the answer into its factual statements. For each, decide whether the cited
sources support it. Then, for each citation number, decide whether that source
supports the statements it is cited for.
Reply with one JSON object:
{"statements": <int>, "supported_statements": <int>,
 "citations": [{"number": <int>, "supports": true|false}]}"""


def load_eval_set(path: Path = EVAL_SET) -> list[dict]:
    return yaml.safe_load(path.read_text())["questions"]


# --- relevance and reference answers ------------------------------------------------


def relevant_jobs(settings: Settings, spec: dict, today: date) -> set[str]:
    """posting_keys in gold.posting_documents matching a 'relevant' spec."""
    clauses, params = ["status = 'open'"], []
    for column, key in (("city", "cities"), ("work_mode", "work_modes"), ("seniority", "seniorities")):
        if spec.get(key):
            clauses.append(f"{column} in ({', '.join('?' * len(spec[key]))})")
            params += spec[key]
    for skill in spec.get("skills_all", []):
        clauses.append("('|' || skills || '|') like ?")
        params.append(f"%|{skill}|%")
    if spec.get("skills_any"):
        clauses.append("(" + " or ".join("('|' || skills || '|') like ?" for _ in spec["skills_any"]) + ")")
        params += [f"%|{s}|%" for s in spec["skills_any"]]
    if spec.get("company"):
        clauses.append("lower(company_name) like ?")
        params.append(f"%{spec['company'].lower()}%")
    if spec.get("title_like"):
        clauses.append("lower(title) like ?")
        params.append(f"%{spec['title_like'].lower()}%")
    if spec.get("posted_within_days"):
        clauses.append("posted_date >= ?")
        params.append(today - timedelta(days=spec["posted_within_days"]))
    rows = read_gold(settings, "select posting_key from gold.posting_documents where " + " and ".join(clauses), params)
    return {r["posting_key"] for r in rows}


def _norm(value) -> str:
    if hasattr(value, "date") and callable(value.date):
        value = value.date()
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip().lower()


def analytical_correct(settings: Settings, reference_sql: str, metric_rows: list[list] | None) -> bool:
    """Every reference row (label, value) or (value) must appear in the answer's rows."""
    if not metric_rows:
        return False
    expected = [list(r.values()) for r in read_gold(settings, reference_sql)]
    actual = {(_norm(r[0]), _norm(r[-1] if len(r) == 1 else _first_count(r))) for r in metric_rows}
    actual_values = {_norm(r[0]) for r in metric_rows if len(r) == 1}
    for row in expected:
        if len(row) == 1:
            if _norm(row[0]) not in actual_values:
                return False
        elif (_norm(row[0]), _norm(row[1])) not in actual:
            return False
    return True


def _first_count(row: list):
    """The first integer column after the label (metrics put a share after the count)."""
    return next((v for v in row[1:] if isinstance(v, int) and not isinstance(v, bool)), row[-1])


# --- retrieval metrics --------------------------------------------------------------


def top_jobs(hits, job_of: dict[str, str] | None = None) -> list[tuple[str, str]]:
    """(job_key, status) for the first TOP_K distinct postings, in rank order."""
    seen, out = set(), []
    for h in hits:
        if h.posting_key in seen:
            continue
        seen.add(h.posting_key)
        out.append(((job_of or {}).get(h.posting_key, h.posting_key), h.status))
        if len(out) == TOP_K:
            break
    return out


def retrieval_scores(ranked: list[tuple[str, str]], relevant: set[str]) -> dict:
    jobs = [j for j, _ in ranked]
    hits = [j in relevant for j in jobs]
    first = next((i for i, h in enumerate(hits, start=1) if h), None)
    duplicates = sum(1 for i, j in enumerate(jobs) if j in jobs[:i])
    denominator = min(TOP_K, len(relevant))
    return {
        "relevant_jobs": len(relevant),
        "recall_at_5": round(len({j for j in jobs if j in relevant}) / denominator, 3) if denominator else None,
        "mrr": round(1 / first, 3) if first else 0.0,
        "duplicate_at_5": round(duplicates / len(jobs), 3) if jobs else 0.0,
        "stale_at_5": round(sum(1 for _, s in ranked if s == "closed") / len(ranked), 3) if ranked else 0.0,
    }


# --- judging ------------------------------------------------------------------------


def judge(judge_llm: LLM, answer_text: str, sources: list[str]) -> dict:
    numbered = "\n\n".join(f"[{i}] {s}" for i, s in enumerate(sources, start=1))
    result = judge_llm.chat(
        JUDGE_SYSTEM, f"Answer:\n{answer_text}\n\nSources:\n{numbered}", json_output=True, max_tokens=800
    )
    try:
        data = assistant._parse_json(result.text)
        statements = max(int(data.get("statements", 0)), 1)
        cites = data.get("citations", [])
        return {
            "groundedness": round(min(int(data.get("supported_statements", 0)), statements) / statements, 3),
            "citation_accuracy": round(sum(1 for c in cites if c.get("supports")) / len(cites), 3) if cites else None,
        }
    except (ValueError, TypeError, AttributeError):
        return {"groundedness": None, "citation_accuracy": None, "judge_error": result.text[:200]}


# --- the run ------------------------------------------------------------------------


@dataclass
class RunConfig:
    llm: str
    embedding: str
    judge: str | None
    chunker_version: str = CHUNKER_VERSION
    prompt_version: str = assistant.PROMPT_VERSION
    commit: str = ""
    snapshot: dict = field(default_factory=dict)


def _commit() -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=REPO_ROOT)
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"], capture_output=True, text=True, cwd=REPO_ROOT
        )
        return sha.stdout.strip() + ("-dirty" if dirty.stdout.strip() else "")
    except OSError:
        return "unknown"


def snapshot(settings: Settings) -> dict:
    row = read_gold(settings, "select count(*) as jobs, max(last_seen_at) as last_seen from gold.posting_documents")[0]
    return {"jobs": int(row["jobs"]), "last_seen_at": str(row["last_seen"]), "warehouse": settings.serving_warehouse}


def evaluate_question(
    q: dict, settings: Settings, llm: LLM, embedder: Embedder, judge_llm: LLM | None, today: date
) -> dict:
    row: dict = {"id": q["id"], "category": q["category"]}
    if q["category"] == "resume":
        started = time.perf_counter()
        result = match_resume(settings, q["resume_text"], MetricFilters(**(q.get("filters") or {})), limit=10)
        expected, found = set(q["expected_skills"]), set(result.resume_skills)
        cities = set((q.get("filters") or {}).get("cities", []))
        row.update(
            latency_ms=int((time.perf_counter() - started) * 1000),
            skill_precision=round(len(found & expected) / len(found), 3) if found else 0.0,
            skill_recall=round(len(found & expected) / len(expected), 3),
            matches=len(result.matches),
            filters_respected=all(not cities or m.city in cities for m in result.matches),
            reasons_exact=all(set(m.matched_skills) <= found for m in result.matches),
        )
        return row

    started = time.perf_counter()
    result = assistant.answer(q["question"], settings, llm, embedder)
    row.update(
        question=q["question"],
        expected_route=q["expected_route"],
        route=result.route,
        route_correct=result.route == q["expected_route"],
        latency_ms=int((time.perf_counter() - started) * 1000),
        input_tokens=sum(c.input_tokens for c in result.model_calls),
        output_tokens=sum(c.output_tokens for c in result.model_calls),
        answer=result.answer,
        refused=result.answer.startswith(assistant.NOT_ENOUGH),
        citations=[c.posting_key for c in result.citations],
        plan=result.plan,
    )
    if q.get("reference_sql"):
        row["analytical_correct"] = analytical_correct(
            settings, q["reference_sql"], result.metric.rows if result.metric else None
        )
    if q.get("relevant"):
        relevant = relevant_jobs(settings, q["relevant"], today)
        row.update(retrieval_scores(top_jobs(result.retrieved), relevant))
        row["citations_relevant"] = (
            round(sum(1 for c in row["citations"] if c in relevant) / len(row["citations"]), 3)
            if row["citations"]
            else None
        )
    if judge_llm and result.citations and not row["refused"]:
        row.update(judge(judge_llm, result.answer, judge_sources(result.retrieved, row["citations"])))
    return row


def judge_sources(hits, cited_keys: list[str]) -> list[str]:
    """Each cited posting exactly as the answering model saw it: metadata header and excerpts."""
    block, numbered = assistant._sources_block(hits)
    by_key = {h.posting_key: sid for sid, h in numbered.items()}
    parts = {sid: text for sid, text in (chunk.split("] ", 1) for chunk in ("\n" + block).split("\n[")[1:])}
    return [parts.get(by_key.get(k, ""), "")[len("") :] for k in cited_keys]


def rejudge(settings: Settings, embedder: Embedder, judge_llm: LLM, run_id: str, progress=print) -> dict:
    """Re-score groundedness and citation accuracy of a stored run with the current judge
    inputs. Retrieval is repeated from each row's stored plan (deterministic for an
    unchanged index), so the answers themselves are not regenerated."""
    path = RESULTS_DIR / f"{run_id}.json"
    data = json.loads(path.read_text())
    for row in data["rows"]:
        if not row.get("citations") or row.get("refused") or not (row.get("plan") or {}).get("search"):
            continue
        plan = assistant.SearchPlan.model_validate(row["plan"]["search"])
        hits = assistant.retrieve(settings, embedder, plan)
        row.update(judge(judge_llm, row["answer"], judge_sources(hits, row["citations"])))
        progress(f"{row['id']} groundedness {row.get('groundedness')} citations {row.get('citation_accuracy')}")
    data["summary"] = summarise(data["rows"])
    data["config"]["judge_inputs"] = "metadata header + excerpts"
    path.write_text(json.dumps(data, indent=1, default=str))
    return data


def summarise(rows: list[dict]) -> dict:
    def mean(key, subset=None):
        values = [r[key] for r in (subset or rows) if r.get(key) is not None]
        return round(statistics.mean(values), 3) if values else None

    asked = [r for r in rows if "route" in r]
    unanswerable = [r for r in asked if r["expected_route"] == "unanswerable"]
    latencies = sorted(r["latency_ms"] for r in asked)
    return {
        "questions": len(rows),
        "routing_accuracy": mean("route_correct", asked),
        "analytical_accuracy": mean("analytical_correct"),
        "recall_at_5": mean("recall_at_5"),
        "mrr": mean("mrr"),
        "duplicate_at_5": mean("duplicate_at_5"),
        "stale_at_5": mean("stale_at_5"),
        "citations_relevant": mean("citations_relevant"),
        "citation_accuracy": mean("citation_accuracy"),
        "groundedness": mean("groundedness"),
        "correct_refusal_rate": mean("refused", unanswerable),
        "false_refusal_rate": mean("refused", [r for r in asked if r["expected_route"] != "unanswerable"]),
        "resume_skill_precision": mean("skill_precision"),
        "resume_skill_recall": mean("skill_recall"),
        "latency_p50_ms": int(statistics.median(latencies)) if latencies else None,
        "latency_p95_ms": latencies[max(0, int(len(latencies) * 0.95) - 1)] if latencies else None,
        "tokens_per_question": int(statistics.mean(r["input_tokens"] + r["output_tokens"] for r in asked))
        if asked
        else None,
    }


def run(
    settings: Settings,
    llm: LLM,
    embedder: Embedder,
    judge_llm: LLM | None = None,
    run_id: str | None = None,
    only: list[str] | None = None,
    progress=print,
    pace_seconds: float = 0,
) -> dict:
    """``pace_seconds`` waits between questions (not counted in latency), so free-tier
    per-minute token quotas don't turn throttling into measured latency."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    run_id = run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + f"_{llm.provider}_{embedder.name.split(':')[-1]}"
    path = RESULTS_DIR / f"{run_id}.json"
    state = json.loads(path.read_text()) if path.exists() else None
    config = RunConfig(
        llm=f"{llm.provider}:{llm.model}",
        embedding=embedder.name,
        judge=f"{judge_llm.provider}:{judge_llm.model}" if judge_llm else None,
        commit=_commit(),
        snapshot=snapshot(settings),
    )
    rows: list[dict] = state["rows"] if state else []
    done = {r["id"] for r in rows}
    today = date.today()
    for q in load_eval_set():
        if q["id"] in done or (only and q["id"] not in only):
            continue
        if pace_seconds and rows and q["category"] != "resume":
            time.sleep(pace_seconds)
        try:
            row = evaluate_question(q, settings, llm, embedder, judge_llm, today)
        except Exception as exc:
            row = {
                "id": q["id"],
                "category": q["category"],
                "error": f"{exc.__class__.__name__}: {str(exc)[:300]}",
                "expected_route": q.get("expected_route"),
                "route": "error",
                "route_correct": False,
                "latency_ms": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "refused": False,
            }
            if q.get("reference_sql"):
                row["analytical_correct"] = False
        rows.append(row)
        path.write_text(json.dumps({"run_id": run_id, "config": config.__dict__, "rows": rows}, indent=1, default=str))
        mark = "ok " if row.get("route_correct", True) and row.get("analytical_correct", True) is not False else "ERR"
        progress(f"{mark} {q['id']} {row.get('route', 'resume'):12} {row['latency_ms']:>6} ms")
    result = {"run_id": run_id, "config": config.__dict__, "summary": summarise(rows), "rows": rows}
    path.write_text(json.dumps(result, indent=1, default=str))
    return result
