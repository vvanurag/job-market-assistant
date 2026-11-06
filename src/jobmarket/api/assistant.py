"""Question routing and grounded answering (FR-QA-01 to FR-QA-05).

1. route()    The model classifies the question as analytical, semantic, combined or
              unanswerable, and returns a typed plan: a metric request and/or a search
              with filters. The plan is validated; an invalid plan falls back to a
              plain semantic search, never to free-form SQL.
2. answer()   Runs the plan. Analytical results come from the metrics layer
              (metrics.py). Semantic answers are written only from retrieved chunks.
              The model refers to sources by number ([S1], [S2]...), and citations are
              built from the retrieved postings by code, so it can't invent a posting.
              If the evidence doesn't answer the question, it says so (FR-QA-05).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from jobmarket.api.metrics import METRIC_DESCRIPTIONS, MetricFilters, MetricRequest, MetricResult, run_metric
from jobmarket.index import store
from jobmarket.llm import LLM, ChatResult, Embedder
from jobmarket.settings import Settings
from jobmarket.skills import canonical_skill, dictionary

Route = Literal["analytical", "semantic", "combined", "unanswerable"]
PROMPT_VERSION = "v2"  # recorded with every evaluation run; change it whenever a prompt changes
NOT_ENOUGH = "I don't have enough information in the collected job postings to answer that."


class SearchPlan(BaseModel):
    query: str
    filters: MetricFilters = Field(default_factory=MetricFilters)


class RoutePlan(BaseModel):
    route: Route
    metric_request: MetricRequest | None = None
    search: SearchPlan | None = None
    reason: str = ""


ROUTER_SYSTEM = """You route questions for a job-market assistant. Its data: about 1,900 \
data engineering, analytics, ML and AI job postings in Hyderabad, Bengaluru and remote roles \
open to candidates in India, collected in late 2026. Fields per job: title, company, city, \
work mode (remote/hybrid/on-site), seniority (intern/junior/mid/senior/lead/manager), skills \
mentioned, posted date, open/closed status, full description. There is NO salary data.

Routes:
- analytical: counts, rankings, trends or comparisons -> fill "metric_request".
- semantic: what postings say or mean, finding specific open roles, what a company looks for \
-> fill "search" (open roles unless the user asks otherwise).
- combined: needs both a number and examples from postings -> fill both.
- unanswerable: outside this data (salaries, other countries or cities, non-job topics, \
predictions, personal advice not about these jobs) -> fill neither.

Metrics (metric_request.metric):
{metrics}

metric_request fields: metric, filters, skill (one skill name), group_by \
(none|city|work_mode|seniority|week|month), grain (week|month), limit (1-50).
filters fields: cities (Hyderabad|Bengaluru|"Remote (India)"), work_modes, seniorities, \
role_keywords (words the title must contain, e.g. ["analytics engineer"]), company, \
skills_all (skill names), posted_within_days (e.g. 7 for "this week", 90 for "last 90 days"), \
open_only.
search fields: query (a rewritten search query), filters (same fields).
Use skill names from this list when possible: {skills}

Examples:
- "Which skills are most in demand for data engineers?" -> analytical, top_skills, \
role_keywords ["data engineer"]
- "What do employers mean by strong Kafka experience?" -> semantic: the postings' own wording \
answers it. Questions about what postings say, mean, expect or require are semantic, never \
unanswerable.
- "What does Databricks look for in data engineers?" -> semantic, company "Databricks"
- "How many remote roles mention LangChain, and what are some examples?" -> combined
- "What will data engineers earn in 2030?" -> unanswerable
Every job in the data is already a data, analytics, ML or AI role: never add role_keywords for \
generic phrases such as "data and AI jobs" or "tech roles". Use role_keywords only for a specific \
role, e.g. "data engineer", "analytics engineer", "machine learning engineer".
Remote roles: use work_modes ["remote"] (that includes remote roles open to India). Use cities \
["Remote (India)"] only when the user asks for roles with no city at all.
"How many ... and examples/which ones" questions are combined: count with metric_request and \
show examples with search, using the same filters in both.

Reply with one JSON object: {{"route": ..., "metric_request": ... or null, "search": ... or null, \
"reason": "one short sentence"}}"""

ANSWER_SYSTEM = """You answer questions about job postings using ONLY the numbered sources \
provided. Rules:
- Every claim must come from the sources. Cite sources inline as [S1], [S2]. Cite at least \
three different sources when three or more are relevant.
- If the sources don't contain the answer, set "sufficient" to false and leave "answer" empty. \
Don't use outside knowledge to fill gaps.
- If analytics results are provided, use their numbers exactly and say what they cover.
- The search already applied the user's filters (city, work mode, dates, skills); each source's \
header shows its city, work mode, status and posted date. Don't refuse because a filter isn't \
restated in the text.
- Be concise: at most about 180 words. Plain prose or short bullet points.
Reply with one JSON object: {"sufficient": true|false, "answer": "...", "sources_used": ["S1", ...]}"""


@dataclass
class Citation:
    posting_key: str
    title: str
    company_name: str
    city: str
    url: str | None
    status: str


@dataclass
class AskResult:
    answer: str
    route: Route
    citations: list[Citation] = field(default_factory=list)
    metric: MetricResult | None = None
    plan: dict | None = None
    model_calls: list[ChatResult] = field(default_factory=list)
    retrieved: list[store.Hit] = field(default_factory=list)  # what the answer was based on, in rank order


def _parse_json(text: str) -> dict:
    text = text.strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    return json.loads(match.group(0) if match else text)


def _drop_nulls(value):
    """Models often send null for "not set"; treat it as "use the default"."""
    if isinstance(value, dict):
        return {k: _drop_nulls(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_drop_nulls(v) for v in value if v is not None]
    return value


def _canonical_skills(filters: MetricFilters) -> MetricFilters:
    filters.skills_all = [canonical_skill(s) or s for s in filters.skills_all]
    return filters


def route(question: str, llm: LLM) -> tuple[RoutePlan, ChatResult]:
    system = ROUTER_SYSTEM.format(
        metrics="\n".join(f"- {k}: {v}" for k, v in METRIC_DESCRIPTIONS.items()),
        skills=", ".join(s.name for s in dictionary()),
    )
    result = llm.chat(system, question, json_output=True, max_tokens=600)
    try:
        plan = RoutePlan.model_validate(_drop_nulls(_parse_json(result.text)))
    except (ValueError, ValidationError):
        plan = RoutePlan(route="semantic", search=SearchPlan(query=question), reason="router output invalid")
    if plan.route in ("semantic", "combined") and plan.search is None:
        plan.search = SearchPlan(query=question)
    if plan.route in ("analytical", "combined") and plan.metric_request is None:
        plan.route = "semantic"
        plan.search = plan.search or SearchPlan(query=question)
    if plan.metric_request:
        _canonical_skills(plan.metric_request.filters)
        if plan.metric_request.skill:
            plan.metric_request.skill = canonical_skill(plan.metric_request.skill) or plan.metric_request.skill
    if plan.search:
        _canonical_skills(plan.search.filters)
    return plan, result


def to_index_filters(f: MetricFilters, open_only_default: bool = True) -> store.Filters:
    return store.Filters(
        cities=list(f.cities),
        work_modes=list(f.work_modes),
        seniorities=list(f.seniorities),
        skills_all=list(f.skills_all),
        company=f.company,
        posted_since=(date.today() - timedelta(days=f.posted_within_days)) if f.posted_within_days else None,
        include_closed=not (f.open_only or open_only_default),
    )


def retrieve(
    settings: Settings, embedder: Embedder, plan: SearchPlan, limit: int = 8, mode: str = "hybrid"
) -> list[store.Hit]:
    filters = to_index_filters(plan.filters)
    query = plan.query
    if plan.filters.role_keywords:  # titles aren't a filter in the index; steer the query instead
        query = f"{' or '.join(plan.filters.role_keywords)}: {query}"
    with store.connect(settings.vectordb_dsn.get_secret_value()) as con:
        return store.search(
            con, store.schema_for(embedder.name), query, embedder.embed_query(query), filters, limit, mode
        )


def _sources_block(hits: list[store.Hit]) -> tuple[str, dict[str, store.Hit]]:
    """One numbered source per posting, with all of its retrieved excerpts."""
    numbered: dict[str, store.Hit] = {}
    excerpts: dict[str, list[str]] = {}
    for h in hits:
        sid = next((k for k, v in numbered.items() if v.posting_key == h.posting_key), None)
        if sid is None:
            sid = f"S{len(numbered) + 1}"
            numbered[sid] = h
            excerpts[sid] = []
        excerpts[sid].append(f"({h.section}) " + h.text.split("\n", 2)[-1])
    lines = [
        f"[{sid}] {h.title} — {h.company_name} ({h.city}; {h.work_mode}; {h.status}; "
        f"posted {h.posted_date or 'date unknown'})\n" + "\n...\n".join(excerpts[sid])
        for sid, h in numbered.items()
    ]
    return "\n\n".join(lines), numbered


def answer(
    question: str,
    settings: Settings,
    llm: LLM,
    embedder: Embedder,
    plan: RoutePlan | None = None,
    search_limit: int = 8,
) -> AskResult:
    calls: list[ChatResult] = []
    if plan is None:
        plan, routed = route(question, llm)
        calls.append(routed)
    plan_dump = plan.model_dump(mode="json")

    if plan.route == "unanswerable":
        return AskResult(f"{NOT_ENOUGH} {plan.reason}".strip(), "unanswerable", plan=plan_dump, model_calls=calls)

    metric = None
    if plan.route in ("analytical", "combined") and plan.metric_request:
        try:
            metric = run_metric(settings, plan.metric_request)
        except ValueError:
            metric = None
        if plan.route == "analytical":
            if metric is None:
                return AskResult(NOT_ENOUGH, "analytical", plan=plan_dump, model_calls=calls)
            return AskResult(metric.summary, "analytical", metric=metric, plan=plan_dump, model_calls=calls)

    hits = retrieve(settings, embedder, plan.search or SearchPlan(query=question), limit=search_limit)
    if not hits:
        return AskResult(NOT_ENOUGH, plan.route, metric=metric, plan=plan_dump, model_calls=calls)
    base = {"metric": metric, "plan": plan_dump, "model_calls": calls, "retrieved": hits}

    sources, numbered = _sources_block(hits)
    analytics = f"Analytics result: {metric.summary}\n\n" if metric else ""
    result = llm.chat(
        ANSWER_SYSTEM, f"Question: {question}\n\n{analytics}Sources:\n{sources}", json_output=True, max_tokens=700
    )
    calls.append(result)
    try:
        reply = _parse_json(result.text)
    except ValueError:
        reply = {"sufficient": False}
    used = [s for s in reply.get("sources_used", []) if s in numbered]
    used += [s for s in re.findall(r"\[(S\d+)\]", reply.get("answer", "")) if s in numbered and s not in used]
    if not reply.get("sufficient") or not used or not reply.get("answer"):
        return AskResult(NOT_ENOUGH, plan.route, **base)

    seen, citations = set(), []
    for sid in used:
        h = numbered[sid]
        if h.posting_key not in seen:
            seen.add(h.posting_key)
            citations.append(Citation(h.posting_key, h.title, h.company_name, h.city, h.url, h.status))
    # the answer's [S1] markers are rewritten to the citation numbers the client sees
    order = {
        sid: citations.index(next(c for c in citations if c.posting_key == numbered[sid].posting_key)) + 1
        for sid in used
    }
    text = re.sub(r"\[(S\d+)\]", lambda m: f"[{order[m.group(1)]}]" if m.group(1) in order else "", reply["answer"])
    text = re.sub(r"\b(S\d+)\b", lambda m: f"[{order[m.group(1)]}]" if m.group(1) in order else "a source", text)
    return AskResult(text.strip(), plan.route, citations, **base)
