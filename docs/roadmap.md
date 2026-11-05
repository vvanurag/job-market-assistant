# Roadmap

| | |
|---|---|
| **Version** | 0.1 (draft) |
| **Owner** | Anurag V V |
| **Last updated** | 2026-11-05 |

Delivery is split into phases. Each phase produces something that runs and has explicit exit criteria. A phase is complete only when all of its exit criteria are met.

The project is also a structured learning path, so each phase lists the skills it develops.

---

## Overview

| Phase | Name | Delivers | Status |
|---|---|---|---|
| 0 | Foundations | Repository, environment, conventions | In progress |
| 1 | Ingestion (Bronze) | Raw postings landing in the warehouse daily | In progress |
| 2 | Modeling (Silver and Gold) | Clean, deduplicated, historised, tested models | In progress |
| 3 | Orchestration | Scheduled, monitored, alerting pipeline | Not started |
| 4 | Streaming | Near-real-time path for new postings | Not started |
| 5 | Retrieval index | Chunked, embedded, filterable index kept in sync | Not started |
| 6 | Serving | FastAPI service with routing and cited answers | Not started |
| 7 | Evaluation | Evaluation set, baseline, data-quality experiment, model comparison | Not started |
| 8 | Delivery | CI/CD, containers, deployment, health view | Not started |
| 9 | Extensions | Optional comparisons and advanced topics | Not started |

## Phase 0: Foundations

**Delivers:** repository layout, Python environment, Docker setup, coding conventions, documentation site, Snowflake account with roles, a local DuckDB target, and a local model server (Ollama).

**Exit criteria**

- Local environment set up from the README in under 60 minutes (NFR-19).
- Lint and format checks run locally (NFR-21).
- Snowflake roles for ingestion, transformation and serving exist (NFR-12).
- A DuckDB connection works locally alongside Snowflake (ADR-0005).
- A local model responds through Ollama, and API keys for Google AI Studio and Groq Cloud are stored outside the repository (ADR-0006, NFR-11).

**Skills:** Python project structure, virtual environments, Git, Docker, Snowflake RBAC, running local models.

## Phase 1: Ingestion (Bronze)

**Delivers:** extractors for at least two approved sources, loading raw JSON into the Bronze layer.

**Exit criteria**

- Open question Q6 (remote roles) answered.
- Target company list for Hyderabad and Bengaluru created ([Data Sources section 3](requirements/data_sources.md#3-target-company-list)).
- Every Bronze batch also written as files (NFR-26).
- At least two sources approved in [Data Sources](requirements/data_sources.md).
- FR-ING-01 to FR-ING-07 met.
- Re-running a batch creates no duplicates (FR-ING-04, NFR-17).

**Skills:** REST APIs, pagination, retries, idempotency, ELT loading patterns.

## Phase 2: Modeling (Silver and Gold)

**Delivers:** dbt project with staging, deduplication, cross-source matching, skill extraction, posting history and the Gold star schema.

**Exit criteria**

- FR-TRN-01 to FR-TRN-12 met for all **Must** items.
- The dbt project builds and passes tests on both Snowflake and DuckDB (NFR-24).
- Cross-source matching precision measured and documented.
- All model tests pass.

**Skills:** SQL, window functions, dimensional modeling, slowly changing dimensions, Medallion architecture, dbt tests.

## Phase 3: Orchestration

**Delivers:** Airflow DAG running ingestion, transformation, tests and indexing daily, with alerts.

**Exit criteria**

- FR-ORC-01 to FR-ORC-04 and FR-OBS-01 met.
- NFR-01 (batch freshness) met for 7 consecutive days.

**Skills:** Airflow, Cosmos, scheduling, retries, monitoring, service level objectives.

## Phase 4: Streaming

**Delivers:** a Kafka-based path that makes new postings searchable within an hour.

**Exit criteria**

- FR-STR-01 to FR-STR-04 met.
- NFR-02 (streaming freshness) measured.
- Decision record comparing Lambda and Kappa approaches for this system.

**Skills:** Kafka producers and consumers, event design, Lambda and Kappa architectures, batch and stream reconciliation.

## Phase 5: Retrieval index

**Delivers:** chunking and embedding pipeline, vector index with metadata, incremental updates.

**Exit criteria**

- ADR-0004 (vector store) accepted.
- FR-IDX-01 to FR-IDX-07 met for all **Must** items.

**Skills:** chunking strategies, embedding models, vector search, hybrid search, change-driven re-indexing, ETL outside the warehouse.

## Phase 6: Serving

**Delivers:** FastAPI service with `/health`, `/search`, `/ask`, `/postings/{id}` and optionally `/match`.

**Exit criteria**

- FR-QA and FR-API **Must** items met.
- NFR-04, NFR-05, NFR-10 and NFR-13 met.
- Open question Q5 (resume privacy) answered.

**Skills:** FastAPI, Pydantic, API design, query routing, prompt design, text-to-SQL safety, service-oriented architecture.

## Phase 7: Evaluation

**Delivers:** evaluation set, baseline results, data-quality experiment and model comparison.

**Exit criteria**

- FR-EVL-01, FR-EVL-02 and FR-EVL-04 met.
- Thresholds in the [Evaluation Plan](requirements/evaluation_plan.md#4-acceptance-thresholds) met.
- Data-quality experiment results published.

**Skills:** retrieval metrics, LLM-as-judge, experiment design, LLM and embedding model selection.

## Phase 8: Delivery

**Delivers:** GitHub Actions pipelines for tests, dbt builds (Snowflake and DuckDB) and evaluation; all services containerised and started locally with `docker compose up`; health view.

**Exit criteria**

- FR-EVL-03 and FR-OBS-03 met.
- NFR-11, NFR-20, NFR-21, NFR-23 and NFR-24 met.
- A clean local start of the full system for a demo takes one command.
- Version 1 release criteria in the [Product Requirements](requirements/product_requirements.md#11-release-criteria-for-version-1) met.

**Skills:** CI/CD, GitHub Actions, Docker, secrets management, deployment.

## Phase 9: Extensions (optional)

Each is independent and can be taken in any order after version 1.

| Extension | Purpose |
|---|---|
| Rebuild one layer on Databricks | Compare Snowflake and Databricks on the same workload |
| Store Silver as Apache Iceberg tables | Learn open table formats and the lakehouse pattern |
| Fine-tune a small model for skill extraction | Compare against dictionary and prompted extraction using the evaluation set |
| Rebuild one extractor in Azure Data Factory | Compare a low-code integration tool with code-based ingestion |
