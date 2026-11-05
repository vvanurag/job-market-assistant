# ADR-0003: Snowflake as the primary warehouse

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-11-05 |
| **Deciders** | Anurag V V |

## Context

The Bronze, Silver and Gold layers need a warehouse that supports semi-structured JSON, SQL transformations with dbt, role-based access control and low idle cost.

## Options considered

1. **Snowflake:** native JSON (`VARIANT`) support, mature dbt adapter, separate compute and storage with auto-suspend, and the owner has already built an ELT pipeline on it. Trial accounts expire, and it is a paid service afterwards.
2. **Databricks:** strong for Spark, ML and lakehouse workloads; more setup for a SQL-first project.
3. **PostgreSQL:** free and local, but not representative of cloud warehouse work and weaker for large analytical scans.
4. **DuckDB:** free, fast and local; excellent for development, but not a shared cloud service.

## Decision

Use Snowflake as the primary warehouse. Databricks is evaluated separately as a Phase 9 extension.

## Consequences

- Existing Snowflake and dbt experience carries over directly.
- Auto-suspend and small warehouses are required to control cost (NFR-08, NFR-09).
- Account continuity after the trial is deferred (open question Q3). [ADR-0005](0005-portable-warehouse-layer.md) sets the rules that keep that decision cheap.
- Snowflake's built-in vector features are not used, so retrieval doesn't depend on the warehouse ([ADR-0004](0004-vector-store-selection.md)).
