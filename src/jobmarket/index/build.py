"""Build or refresh the retrieval index from Gold (Phase 5).

Incremental by design (FR-IDX-04, FR-IDX-05):

  - a job whose ``document_hash`` (title, company, city, description) and chunker
    version are unchanged is **not** re-embedded; only its metadata is refreshed
  - new or changed jobs are re-chunked and re-embedded
  - a job that closed keeps its chunks but gets status 'closed', so searches (which
    default to open jobs) stop returning it in the same run
  - a job no longer in Gold at all is deleted with its chunks

Every build is recorded in ``public.index_builds`` with the embedding model and the
chunker version (FR-IDX-07).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from jobmarket.index import store
from jobmarket.index.chunking import CHUNKER_VERSION, chunk_posting
from jobmarket.llm import Embedder
from jobmarket.settings import Settings
from jobmarket.warehouse import read_gold

EMBED_BATCH = 32

GOLD_QUERY = """
select posting_key, title, company_name, city, is_remote_india, work_mode, seniority,
       min_years_experience, status, posted_date, last_seen_at, url, source_key, skills,
       description_text, document_hash
from gold.posting_documents
"""

METADATA_COLUMNS = [
    "title",
    "company_name",
    "city",
    "is_remote_india",
    "work_mode",
    "seniority",
    "min_years_experience",
    "status",
    "posted_date",
    "last_seen_at",
    "url",
    "source_key",
    "skills",
]


@dataclass
class BuildResult:
    build_id: int
    schema: str
    postings_in_gold: int
    embedded: int
    updated: int
    removed: int
    chunks_written: int
    seconds: float


def _metadata(doc: dict) -> list:
    values = [doc[c] for c in METADATA_COLUMNS]
    values[METADATA_COLUMNS.index("skills")] = [s for s in (doc["skills"] or "").split("|") if s]
    return values


def build_index(
    settings: Settings,
    embedder: Embedder,
    limit: int | None = None,
    progress: Callable[[str], None] = lambda _msg: None,
) -> BuildResult:
    started = time.perf_counter()
    docs = read_gold(settings, GOLD_QUERY)
    if limit:
        docs = sorted(docs, key=lambda d: d["posting_key"])[:limit]
    schema = store.schema_for(embedder.name)

    with store.connect(settings.vectordb_dsn.get_secret_value()) as con:
        store.ensure_schema(con, schema, embedder.dimensions)
        build_id = con.execute(
            "insert into public.index_builds (index_schema, embedding_model, dimensions, chunker_version, "
            "source_warehouse, postings_in_gold) values (%s, %s, %s, %s, %s, %s) returning build_id",
            [schema, embedder.name, embedder.dimensions, CHUNKER_VERSION, settings.serving_warehouse, len(docs)],
        ).fetchone()[0]
        con.commit()

        existing = dict(
            con.execute(f"select posting_key, document_hash || '|' || chunker_version from {schema}.postings")
        )
        wanted = {d["posting_key"]: d for d in docs}
        to_embed = [d for d in docs if existing.get(d["posting_key"]) != f"{d['document_hash']}|{CHUNKER_VERSION}"]
        embed_keys = {d["posting_key"] for d in to_embed}
        to_update = [d for d in docs if d["posting_key"] in existing and d["posting_key"] not in embed_keys]
        # a limited (test) build sees only part of Gold, so it must not delete the rest
        to_remove = [] if limit else [k for k in existing if k not in wanted]

        # metadata-only refresh: status, seniority, skills... without re-embedding
        set_list = ", ".join(f"{c} = %s" for c in METADATA_COLUMNS)
        with con.cursor() as cur:
            cur.executemany(
                f"update {schema}.postings set {set_list}, updated_at = now() where posting_key = %s",
                [[*_metadata(d), d["posting_key"]] for d in to_update],
            )
        if to_remove:
            con.execute(f"delete from {schema}.postings where posting_key = any(%s)", [to_remove])
        con.commit()
        progress(f"{len(to_update)} unchanged jobs refreshed, {len(to_remove)} removed, {len(to_embed)} to embed")

        chunks_written = 0
        columns = ", ".join(["posting_key", "document_hash", "chunker_version", *METADATA_COLUMNS])
        placeholders = ", ".join(["%s"] * (3 + len(METADATA_COLUMNS)))
        for start in range(0, len(to_embed), EMBED_BATCH):
            batch = to_embed[start : start + EMBED_BATCH]
            chunked = [
                (d, chunk_posting(d["title"], d["company_name"], d["city"], d["description_text"] or "")) for d in batch
            ]
            texts = [c.text for _, chunks in chunked for c in chunks]
            vectors = iter(embedder.embed_documents(texts))
            keys = [d["posting_key"] for d in batch]
            con.execute(f"delete from {schema}.postings where posting_key = any(%s)", [keys])
            with con.cursor() as cur:
                cur.executemany(
                    f"insert into {schema}.postings ({columns}) values ({placeholders})",
                    [[d["posting_key"], d["document_hash"], CHUNKER_VERSION, *_metadata(d)] for d, _ in chunked],
                )
                cur.executemany(
                    f"insert into {schema}.chunks (posting_key, chunk_number, section, text, embedding) "
                    "values (%s, %s, %s, %s, %s::vector)",
                    [
                        [d["posting_key"], c.chunk_number, c.section, c.text, store.vector_literal(next(vectors))]
                        for d, chunks in chunked
                        for c in chunks
                    ],
                )
            con.commit()  # each batch is durable: an interrupted build resumes where it stopped
            chunks_written += len(texts)
            progress(f"embedded {min(start + EMBED_BATCH, len(to_embed))}/{len(to_embed)} jobs")

        con.execute(
            "update public.index_builds set finished_at = now(), status = 'succeeded', postings_embedded = %s, "
            "postings_updated = %s, postings_removed = %s, chunks_written = %s where build_id = %s",
            [len(to_embed), len(to_update), len(to_remove), chunks_written, build_id],
        )
        con.commit()

    return BuildResult(
        build_id,
        schema,
        len(docs),
        len(to_embed),
        len(to_update),
        len(to_remove),
        chunks_written,
        time.perf_counter() - started,
    )
