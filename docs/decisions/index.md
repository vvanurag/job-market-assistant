# Architecture Decision Records

An architecture decision record (ADR) captures one significant technical decision: the context, the options considered, the choice made and its consequences. Records are numbered, never deleted, and replaced only by a later record that supersedes them.

The format is described in [ADR-0001](0001-record-architecture-decisions.md). Copy [the template](template.md) to add a record.

| ADR | Title | Status | Date |
|---|---|---|---|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted | 2026-11-05 |
| [0002](0002-job-market-as-project-domain.md) | Job market as the project domain | Accepted | 2026-11-05 |
| [0003](0003-snowflake-as-primary-warehouse.md) | Snowflake as the primary warehouse | Accepted | 2026-11-05 |
| [0004](0004-vector-store-selection.md) | Vector store selection | Accepted | 2026-11-05 |
| [0005](0005-portable-warehouse-layer.md) | Keep the warehouse layer portable | Accepted | 2026-11-05 |
| [0006](0006-llm-provider-strategy.md) | Language model provider strategy | Accepted (shortlist) | 2026-11-05 |
| [0007](0007-chunking-strategy.md) | Chunking strategy | Accepted | 2026-11-06 |
## Decisions expected later

| Topic | Needed by |
|---|---|
| Lambda vs Kappa for the streaming path | Phase 4 |
| Text-to-SQL approach: generated SQL vs a pre-defined metrics layer | Phase 6 |
| Final LLM and embedding model per role | Phase 7 |
| Snowflake continuation (open question Q3) | When the trial ends |
