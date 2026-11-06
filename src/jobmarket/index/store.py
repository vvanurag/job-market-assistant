"""The retrieval index in PostgreSQL with pgvector (ADR-0004).

Each embedding model gets its own schema (``idx_<model>``), so two models can be
indexed side by side and compared on the same evaluation set (FR-EVL-04):

    idx_<model>.postings   one row per job: metadata used for filters (FR-IDX-02)
    idx_<model>.chunks     one row per chunk: text, embedding, full-text vector
    public.index_builds    one row per build: model, chunker version, counts (FR-IDX-07)

Search combines vector similarity and keyword (full-text) ranking with Reciprocal Rank
Fusion, and applies metadata filters inside both (FR-IDX-03, FR-IDX-06).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

import psycopg

RRF_K = 60  # standard Reciprocal Rank Fusion constant
CANDIDATES = 60  # candidates taken from each ranking before fusion


def schema_for(embedding_name: str) -> str:
    return "idx_" + re.sub(r"[^a-z0-9]+", "_", embedding_name.split(":", 1)[-1].lower()).strip("_")


def connect(dsn: str) -> psycopg.Connection:
    return psycopg.connect(dsn, autocommit=False)


def ensure_schema(con: psycopg.Connection, schema: str, dimensions: int) -> None:
    con.execute("create extension if not exists vector")
    con.execute(
        """
        create table if not exists public.index_builds (
            build_id            bigserial primary key,
            index_schema        text not null,
            embedding_model     text not null,
            dimensions          int not null,
            chunker_version     text not null,
            source_warehouse    text not null,
            started_at          timestamptz not null default now(),
            finished_at         timestamptz,
            postings_in_gold    int,
            postings_embedded   int,
            postings_updated    int,
            postings_removed    int,
            chunks_written      int,
            status              text not null default 'running'
        )"""
    )
    con.execute(f"create schema if not exists {schema}")
    con.execute(
        f"""
        create table if not exists {schema}.postings (
            posting_key          text primary key,
            document_hash        text not null,
            chunker_version      text not null,
            title                text not null,
            company_name         text not null,
            city                 text not null,
            is_remote_india      boolean not null,
            work_mode            text not null,
            seniority            text not null,
            min_years_experience int,
            status               text not null,
            posted_date          date,
            last_seen_at         timestamptz,
            url                  text,
            source_key           text not null,
            skills               text[] not null,
            embedded_at          timestamptz not null default now(),
            updated_at           timestamptz not null default now()
        )"""
    )
    con.execute(
        f"""
        create table if not exists {schema}.chunks (
            posting_key   text not null references {schema}.postings (posting_key) on delete cascade,
            chunk_number  int not null,
            section       text not null,
            text          text not null,
            embedding     vector({dimensions}) not null,
            tsv           tsvector generated always as (to_tsvector('english', text)) stored,
            primary key (posting_key, chunk_number)
        )"""
    )
    con.execute(
        f"create index if not exists chunks_embedding_hnsw on {schema}.chunks using hnsw (embedding vector_cosine_ops)"
    )
    con.execute(f"create index if not exists chunks_tsv_gin on {schema}.chunks using gin (tsv)")
    for column in ("status", "city", "work_mode", "seniority", "posted_date"):
        con.execute(f"create index if not exists postings_{column} on {schema}.postings ({column})")
    con.execute(f"create index if not exists postings_skills on {schema}.postings using gin (skills)")
    con.commit()


def vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{v:.7g}" for v in values) + "]"


# --- search -----------------------------------------------------------------------


@dataclass
class Filters:
    """Metadata filters (FR-IDX-03). Empty means "don't filter on this"."""

    cities: list[str] = field(default_factory=list)  # "Hyderabad", "Bengaluru", "Remote (India)"
    work_modes: list[str] = field(default_factory=list)
    seniorities: list[str] = field(default_factory=list)
    skills_all: list[str] = field(default_factory=list)  # every one of these skills
    company: str | None = None  # case-insensitive substring
    posted_since: date | None = None
    include_closed: bool = False
    posting_keys: list[str] = field(default_factory=list)

    def where(self) -> tuple[str, list]:
        clauses, params = [], []
        if not self.include_closed:
            clauses.append("p.status = 'open'")
        if self.cities:
            clauses.append("p.city = any(%s)")
            params.append(self.cities)
        if self.work_modes:
            clauses.append("p.work_mode = any(%s)")
            params.append(self.work_modes)
        if self.seniorities:
            clauses.append("p.seniority = any(%s)")
            params.append(self.seniorities)
        if self.skills_all:
            clauses.append("p.skills @> %s")
            params.append(self.skills_all)
        if self.company:
            clauses.append("p.company_name ilike %s")
            params.append(f"%{self.company}%")
        if self.posted_since:
            clauses.append("p.posted_date >= %s")
            params.append(self.posted_since)
        if self.posting_keys:
            clauses.append("p.posting_key = any(%s)")
            params.append(self.posting_keys)
        return (" and ".join(clauses) or "true"), params


@dataclass
class Hit:
    posting_key: str
    chunk_number: int
    section: str
    text: str
    score: float
    vector_rank: int | None
    keyword_rank: int | None
    title: str
    company_name: str
    city: str
    work_mode: str
    seniority: str
    status: str
    posted_date: date | None
    url: str | None


def search(
    con: psycopg.Connection,
    schema: str,
    query_text: str,
    query_vector: list[float],
    filters: Filters | None = None,
    limit: int = 8,
    mode: str = "hybrid",
    max_chunks_per_posting: int = 2,
) -> list[Hit]:
    """Top chunks for a query. ``mode`` is "hybrid", "vector" or "keyword"."""
    where, params = (filters or Filters()).where()
    use_vector = mode in ("hybrid", "vector")
    use_keyword = mode in ("hybrid", "keyword")
    # Filtered HNSW search keeps scanning until enough rows pass the filter (pgvector 0.8)
    con.execute("set local hnsw.iterative_scan = relaxed_order")
    sql = f"""
        with vector_ranked as (
            select c.posting_key, c.chunk_number,
                   row_number() over (order by c.embedding <=> %s::vector) as rank
            from {schema}.chunks c join {schema}.postings p using (posting_key)
            where {where} and {"true" if use_vector else "false"}
            order by c.embedding <=> %s::vector
            limit {CANDIDATES}
        ),
        keyword_ranked as (
            select c.posting_key, c.chunk_number,
                   row_number() over (order by ts_rank_cd(c.tsv, q) desc) as rank
            from {schema}.chunks c join {schema}.postings p using (posting_key),
                 websearch_to_tsquery('english', %s) q
            where {where} and c.tsv @@ q and {"true" if use_keyword else "false"}
            order by ts_rank_cd(c.tsv, q) desc
            limit {CANDIDATES}
        ),
        fused as (
            select coalesce(v.posting_key, k.posting_key) as posting_key,
                   coalesce(v.chunk_number, k.chunk_number) as chunk_number,
                   coalesce(1.0 / ({RRF_K} + v.rank), 0) + coalesce(1.0 / ({RRF_K} + k.rank), 0) as score,
                   v.rank as vector_rank, k.rank as keyword_rank
            from vector_ranked v
            full outer join keyword_ranked k using (posting_key, chunk_number)
        ),
        per_posting as (
            select *, row_number() over (partition by posting_key order by score desc) as nth
            from fused
        )
        select f.posting_key, f.chunk_number, c.section, c.text, f.score, f.vector_rank, f.keyword_rank,
               p.title, p.company_name, p.city, p.work_mode, p.seniority, p.status, p.posted_date, p.url
        from per_posting f
        join {schema}.chunks c using (posting_key, chunk_number)
        join {schema}.postings p using (posting_key)
        where f.nth <= %s
        order by f.score desc
        limit %s
    """
    vec = vector_literal(query_vector)
    rows = con.execute(sql, [vec, *params, vec, query_text, *params, max_chunks_per_posting, limit]).fetchall()
    con.rollback()  # read-only; ends the transaction that "set local" opened
    return [Hit(*row) for row in rows]
