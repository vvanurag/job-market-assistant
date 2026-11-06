# ADR-0004: Vector store selection

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-11-06 |
| **Deciders** | Anurag V V |

## Context

The retrieval index (FR-IDX) must store chunk embeddings with metadata, support filters combined with vector similarity (FR-IDX-03), ideally support hybrid keyword and vector search (FR-IDX-06), and allow incremental updates and deletions (FR-IDX-04, FR-IDX-05). It must meet the search latency target in NFR-04 at personal-project cost.

The API runs on the owner's machine (Q4), so a vector store that runs locally in Docker is preferred.

## Options considered

1. **Snowflake vector features** (vector data type and Cortex Search): no extra system; ties retrieval to Snowflake. **Excluded** by [ADR-0005](0005-portable-warehouse-layer.md), because the Snowflake continuation decision is deferred.
2. **PostgreSQL with pgvector:** widely used, runs locally in Docker, plain SQL filters, hybrid search possible with full-text search.
3. **Qdrant:** purpose-built vector database with rich filtering and hybrid search; runs locally in Docker; one more system to operate.
4. **A managed vector service** (for example Pinecone): minimal operations; adds a vendor and a cost line, and is unnecessary for local demos.

## Spike (2026-11-06)

The same 12,444 chunk embeddings (`nomic-embed-text`, 768 dimensions, 1,872 jobs) were loaded into both stores, each running locally in Docker. 50 queries were timed, top 10 results each:

| Measure | pgvector 0.8 (PostgreSQL 17) | Qdrant 1.12 |
|---|---|---|
| Unfiltered search, p50 / p95 | 9.5 / 11.5 ms | 46.1 / 48.0 ms |
| Filtered (open, Hyderabad, hybrid), p50 / p95 | 12.1 / 13.5 ms | 45.4 / 47.3 ms |
| Same postings in the top 10 | 96% unfiltered, 100% filtered | (reference) |
| Hybrid keyword + vector, filtered, p50 / p95 | 3.9 / 8.8 ms, in one SQL query | Needs sparse vectors, a second index and client-side fusion |
| Memory with the index loaded | 147 MiB | 110 MiB |
| Incremental update and delete | SQL in a transaction, with foreign-key cascade from posting to chunks | Point upserts and deletes by filter |

Qdrant's times include HTTP and JSON overhead, so they shouldn't be read as engine speed. Both are two orders of magnitude inside NFR-04 (p95 under 1.5 s), so latency doesn't decide.

## Decision

**PostgreSQL with pgvector.**

- **Hybrid search in one query (FR-IDX-06).** PostgreSQL full-text search and vector similarity are fused with Reciprocal Rank Fusion in a single SQL statement, with the same metadata filters applied to both rankings (FR-IDX-03).
- **Incremental updates are plain transactions (FR-IDX-04/05).** Changed jobs are replaced, closed jobs are re-flagged, and removed jobs are deleted with their chunks by a cascade, all atomically per batch.
- **SQL skills carry over.** The index can be inspected, joined and debugged with the same SQL used in the warehouse.
- **One fewer system to run**, for a project that already runs a warehouse, a model server and a broker.

## Consequences

- The vector store runs as the `vectordb` service in `docker-compose.yml` (`pgvector/pgvector:0.8.0-pg17`, port 5433).
- Each embedding model has its own schema (`idx_<model>`), so models can be compared side by side (FR-EVL-04).
- Filtered HNSW search uses `hnsw.iterative_scan`, so strict filters still return enough rows.
- If the index grew to many millions of chunks, Qdrant or a managed service would be worth revisiting. At this project's scale (tens of thousands of chunks) it isn't needed.
