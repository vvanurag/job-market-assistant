"""The Job Market Assistant HTTP API (Phase 6, FR-API-01 to FR-API-05).

Run locally:  make api   then open http://localhost:8000/docs

Every endpoint except /health needs the X-API-Key header (FR-API-05). Request and
response bodies are validated Pydantic models, and the OpenAPI description at
/openapi.json is generated from them (FR-API-02).
"""

from __future__ import annotations

import secrets
import time
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, Security, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field, ValidationError

from jobmarket import __version__
from jobmarket.api import assistant, logs
from jobmarket.api.match import match_resume, resume_text
from jobmarket.api.metrics import MetricFilters, MetricResult
from jobmarket.index import store
from jobmarket.llm import get_embedder, get_llm
from jobmarket.settings import Settings, get_settings
from jobmarket.warehouse import read_gold

MAX_RESUME_BYTES = 2_000_000


# --- schemas ----------------------------------------------------------------------


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=500, examples=["dbt and Snowflake analytics engineering"])
    filters: MetricFilters = Field(default_factory=MetricFilters)
    limit: int = Field(8, ge=1, le=50)
    mode: Literal["hybrid", "vector", "keyword"] = "hybrid"
    include_closed: bool = False


class SearchHit(BaseModel):
    posting_key: str
    title: str
    company_name: str
    city: str
    work_mode: str
    seniority: str
    status: str
    posted_date: date | None
    url: str | None
    section: str
    text: str
    score: float


class SearchResponse(BaseModel):
    request_id: str
    hits: list[SearchHit]


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000, examples=["Which skills are most in demand?"])


class CitationOut(BaseModel):
    number: int
    posting_key: str
    title: str
    company_name: str
    city: str
    url: str | None
    status: str


class AskResponse(BaseModel):
    request_id: str
    answer: str
    route: Literal["analytical", "semantic", "combined", "unanswerable"]
    citations: list[CitationOut]
    analytics: MetricResult | None = None
    model: str | None = None
    latency_ms: int


class PostingVersion(BaseModel):
    version_number: int
    status: str
    title: str | None
    location_raw: str | None
    valid_from: datetime
    valid_to: datetime | None
    is_current: bool


class PostingDetail(BaseModel):
    posting_key: str
    title: str
    company_name: str
    city: str
    work_mode: str
    seniority: str
    min_years_experience: int | None
    status: str
    posted_date: date | None
    first_seen_at: datetime | None
    last_seen_at: datetime | None
    url: str | None
    skills: list[str]
    description_text: str
    history: list[PostingVersion]


class MatchOut(BaseModel):
    posting_key: str
    title: str
    company_name: str
    city: str
    url: str | None
    score: float
    matched_skills: list[str]
    missing_skills: list[str]
    reason: str


class GapOut(BaseModel):
    skill: str
    jobs: int
    share_of_jobs: float


class MatchResponse(BaseModel):
    request_id: str
    resume_skills: list[str]
    matches: list[MatchOut]
    gaps: list[GapOut]
    jobs_considered: int
    filters_applied: list[str]


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    checks: dict[str, str]


# --- app --------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.llm = get_llm(settings=settings)
    app.state.embedder = get_embedder(settings=settings)
    yield


app = FastAPI(
    title="Job Market Assistant API",
    version=__version__,
    description="Answers questions about data and AI jobs in Hyderabad, Bengaluru and remote roles in India.",
    lifespan=lifespan,
)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(request: Request, key: Annotated[str | None, Security(api_key_header)]) -> None:
    expected = request.app.state.settings.api_key
    if expected is None or not expected.get_secret_value():
        raise HTTPException(503, "API_KEY is not configured on the server")
    if not key or not secrets.compare_digest(key, expected.get_secret_value()):
        raise HTTPException(401, "missing or invalid X-API-Key header")


Authorised = Depends(require_api_key)


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _dsn(settings: Settings) -> str:
    return settings.vectordb_dsn.get_secret_value()


@app.get("/health", response_model=Health, tags=["operations"])
def health(request: Request) -> Health:
    """Liveness and dependency checks. No API key needed."""
    settings = _settings(request)
    checks: dict[str, str] = {}
    try:
        n = read_gold(settings, "select count(*) as n from gold.fct_postings")[0]["n"]
        checks["warehouse"] = f"ok: {n} jobs in Gold ({settings.serving_warehouse})"
    except Exception as exc:
        checks["warehouse"] = f"failed: {exc.__class__.__name__}"
    try:
        with store.connect(_dsn(settings)) as con:
            row = con.execute(
                "select embedding_model, finished_at from public.index_builds "
                "where status = 'succeeded' order by build_id desc limit 1"
            ).fetchone()
        checks["index"] = f"ok: last build {row[1]:%Y-%m-%d %H:%M} UTC ({row[0]})" if row else "failed: no build yet"
    except Exception as exc:
        checks["index"] = f"failed: {exc.__class__.__name__}"
    checks["model"] = f"configured: {request.app.state.llm.provider}:{request.app.state.llm.model}"
    status = "ok" if all(not v.startswith("failed") for v in checks.values()) else "degraded"
    return Health(status=status, version=__version__, checks=checks)


@app.post("/search", response_model=SearchResponse, dependencies=[Authorised], tags=["assistant"])
def search(body: SearchRequest, request: Request) -> SearchResponse:
    """Hybrid search over open postings with metadata filters (no language model)."""
    started, request_id = time.perf_counter(), uuid.uuid4().hex
    settings, embedder = _settings(request), request.app.state.embedder
    filters = assistant.to_index_filters(body.filters, open_only_default=not body.include_closed)
    query = body.query if not body.filters.role_keywords else f"{' or '.join(body.filters.role_keywords)}: {body.query}"
    with store.connect(_dsn(settings)) as con:
        hits = store.search(
            con, store.schema_for(embedder.name), query, embedder.embed_query(query), filters, body.limit, body.mode
        )
    out = [
        SearchHit(
            posting_key=h.posting_key,
            title=h.title,
            company_name=h.company_name,
            city=h.city,
            work_mode=h.work_mode,
            seniority=h.seniority,
            status=h.status,
            posted_date=h.posted_date,
            url=h.url,
            section=h.section,
            text=h.text.split("\n", 2)[-1],
            score=round(float(h.score), 6),
        )
        for h in hits
    ]
    latency = int((time.perf_counter() - started) * 1000)
    logs.record(
        _dsn(settings),
        request_id=request_id,
        endpoint="/search",
        status_code=200,
        latency_ms=latency,
        question=body.query,
    )
    return SearchResponse(request_id=request_id, hits=out)


@app.post("/ask", response_model=AskResponse, dependencies=[Authorised], tags=["assistant"])
def ask(body: AskRequest, request: Request) -> AskResponse:
    """Answer a question: routed to analytics, search, both, or a refusal (FR-QA-01)."""
    started, request_id = time.perf_counter(), uuid.uuid4().hex
    settings = _settings(request)
    try:
        result = assistant.answer(body.question, settings, request.app.state.llm, request.app.state.embedder)
    except Exception as exc:
        latency = int((time.perf_counter() - started) * 1000)
        logs.record(
            _dsn(settings),
            request_id=request_id,
            endpoint="/ask",
            status_code=502,
            latency_ms=latency,
            question=body.question,
            error=exc.__class__.__name__,
        )
        raise HTTPException(502, f"the assistant failed: {exc.__class__.__name__} (request {request_id})") from exc
    latency = int((time.perf_counter() - started) * 1000)
    logs.record(
        _dsn(settings),
        request_id=request_id,
        endpoint="/ask",
        status_code=200,
        latency_ms=latency,
        route=result.route,
        calls=result.model_calls,
        question=body.question,
    )
    last = result.model_calls[-1] if result.model_calls else None
    return AskResponse(
        request_id=request_id,
        answer=result.answer,
        route=result.route,
        citations=[CitationOut(number=i, **c.__dict__) for i, c in enumerate(result.citations, start=1)],
        analytics=result.metric,
        model=f"{last.provider}:{last.model}" if last else None,
        latency_ms=latency,
    )


@app.get("/postings/{posting_key}", response_model=PostingDetail, dependencies=[Authorised], tags=["postings"])
def posting(posting_key: str, request: Request) -> PostingDetail:
    """One job: details, skills, open/closed status and change history (US-10)."""
    if not posting_key.isalnum() or len(posting_key) > 64:
        raise HTTPException(422, "posting_key must be the hexadecimal key returned by /search or /ask")
    settings = _settings(request)
    rows = read_gold(settings, "select * from gold.posting_documents where posting_key = ?", [posting_key])
    if not rows:
        raise HTTPException(404, "no such posting")
    doc = rows[0]
    versions = read_gold(
        settings,
        "select version_number, status, title, location_raw, valid_from, valid_to, is_current "
        "from gold.posting_versions where posting_key = ? order by version_number",
        [posting_key],
    )
    return PostingDetail(
        **{k: doc[k] for k in PostingDetail.model_fields if k in doc and k not in ("skills", "history")},
        skills=[s for s in (doc["skills"] or "").split("|") if s],
        history=[PostingVersion(**v) for v in versions],
    )


@app.post("/match", response_model=MatchResponse, dependencies=[Authorised], tags=["assistant"])
async def match(
    request: Request,
    resume: Annotated[UploadFile, File(description="Resume as PDF or plain text. Not stored or logged.")],
    role_keywords: Annotated[str, Form(description="Comma-separated title words, e.g. 'data engineer'")] = "",
    cities: Annotated[str, Form(description="Comma-separated: Hyderabad, Bengaluru, Remote (India)")] = "",
    limit: Annotated[int, Form(ge=1, le=50)] = 10,
) -> MatchResponse:
    """Best-matching open roles for a resume, and the skills it is missing (FR-API-04)."""
    started, request_id = time.perf_counter(), uuid.uuid4().hex
    settings = _settings(request)
    content = await resume.read(MAX_RESUME_BYTES + 1)
    if len(content) > MAX_RESUME_BYTES:
        raise HTTPException(413, "resume larger than 2 MB")
    try:
        filters = MetricFilters(
            role_keywords=[k for k in role_keywords.split(",") if k.strip()],
            cities=[c.strip() for c in cities.split(",") if c.strip()],
        )
    except ValidationError as exc:
        raise HTTPException(422, "cities must be Hyderabad, Bengaluru or Remote (India)") from exc
    text = resume_text(content, resume.filename)
    result = match_resume(settings, text, filters, limit)
    del text, content  # the resume isn't kept beyond this request (NFR-10)
    latency = int((time.perf_counter() - started) * 1000)
    logs.record(_dsn(settings), request_id=request_id, endpoint="/match", status_code=200, latency_ms=latency)
    return MatchResponse(
        request_id=request_id,
        resume_skills=result.resume_skills,
        matches=[MatchOut(**m.__dict__) for m in result.matches],
        gaps=[GapOut(**g.__dict__) for g in result.gaps],
        jobs_considered=result.jobs_considered,
        filters_applied=result.filters_applied,
    )


@app.get("/status", response_class=HTMLResponse, tags=["operations"])
def status_page(
    request: Request,
    key: Annotated[str | None, Security(api_key_header)] = None,
    key_param: Annotated[str | None, Query(alias="key")] = None,
) -> HTMLResponse:
    """Health view: freshness, volume per source, pipeline runs, index, usage and cost (FR-OBS-03).

    Open http://localhost:8000/status?key=<API_KEY> in a browser."""
    from jobmarket.api import status

    require_api_key(request, key or key_param)
    return HTMLResponse(status.render(status.collect(_settings(request))))
