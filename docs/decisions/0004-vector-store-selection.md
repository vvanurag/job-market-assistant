# ADR-0004: Vector store selection

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-05 |
| **Deciders** | Anurag V V |

## Context

The retrieval index (FR-IDX) must store chunk embeddings with metadata, support filters combined with vector similarity (FR-IDX-03), ideally support hybrid keyword and vector search (FR-IDX-06), and allow incremental updates and deletions (FR-IDX-04, FR-IDX-05). It must meet the search latency target in NFR-04 at personal-project cost.

The API runs on the owner's machine (Q4), so a vector store that runs locally in Docker is preferred.

## Options considered

1. **Snowflake vector features** (vector data type and Cortex Search): no extra system; ties retrieval to Snowflake. **Excluded** by [ADR-0005](0005-portable-warehouse-layer.md), because the Snowflake continuation decision is deferred.
2. **PostgreSQL with pgvector:** widely used, runs locally in Docker, plain SQL filters, hybrid search possible with full-text search.
3. **Qdrant:** purpose-built vector database with rich filtering and hybrid search; runs locally in Docker; one more system to operate.
4. **A managed vector service** (for example Pinecone): minimal operations; adds a vendor and a cost line, and is unnecessary for local demos.

## Decision

Not yet decided. To be decided at the start of Phase 5 after a short spike that compares options 2 and 3 on filtered search latency, ease of incremental updates and deletes, hybrid search support and local resource use.

## Consequences

To be completed when the decision is accepted.
