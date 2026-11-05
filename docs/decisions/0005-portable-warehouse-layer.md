# ADR-0005: Keep the warehouse layer portable

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-11-05 |
| **Deciders** | Anurag V V |

## Context

Snowflake is the primary warehouse ([ADR-0003](0003-snowflake-as-primary-warehouse.md)), but development starts on a trial account. How the project continues afterwards (a paid account, a new trial, or another engine) is deliberately deferred (open question Q3). Whatever is decided later must not force a rewrite of ingestion, transformation or retrieval.

## Options considered

1. **Use Snowflake fully, decide later:** fastest to start, but Snowflake-only features spread through the code and make any later change expensive.
2. **Avoid Snowflake, use only a local engine:** no lock-in, but loses the cloud-warehouse experience that is a project goal.
3. **Use Snowflake as the main target, with portability guarantees:** a small, steady cost in discipline, in exchange for keeping every later option open.

## Decision

Use option 3. Specifically:

1. **Raw data is kept as files.** Every Bronze batch is also written as compressed JSON files outside the warehouse (NFR-26), so Bronze can be rebuilt in any engine.
2. **dbt models use portable SQL.** Engine-specific syntax is wrapped in dbt macros with per-engine implementations, and kept to a short, documented list.
3. **DuckDB is the second target.** The dbt project builds and tests against DuckDB as well as Snowflake, locally and in CI (NFR-24). This proves portability continuously rather than assuming it.
4. **Retrieval does not live in the warehouse.** The vector index is a separate component, so ADR-0004 excludes Snowflake's built-in vector features.
5. **Access goes through interfaces.** The API reads Gold data through one data-access module, never through engine-specific calls spread across the code.

## Consequences

- When Q3 is decided, the options are: continue on Snowflake with no changes, move to DuckDB (or MotherDuck) with a profile change, or move to another dbt-supported warehouse with macro work only.
- Some convenient Snowflake features (for example `QUALIFY`, `FLATTEN` on `VARIANT`) need macro wrappers or portable alternatives. DuckDB supports `QUALIFY`, which keeps the gap small.
- CI runs the dbt project twice, which adds a few minutes per run.
- Learning value increases: the project demonstrates warehouse-agnostic design, a common real-world requirement.
