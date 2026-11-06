# ADR-0008: Analytical answers through a metrics layer, not generated SQL

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-11-06 |
| **Deciders** | Anurag V V |

## Context

Analytical questions ("which skills are growing?", "Hyderabad or Bengaluru for Databricks?") must be answered from Gold through a controlled interface (FR-QA-02). Generated SQL must never be able to write, change structure, or read outside Gold (NFR-13). The answer must state its filters, date range and the number of jobs counted (FR-QA-04).

## Options considered

1. **Text-to-SQL.** The model writes SQL; a validator checks it, and it runs as a read-only role. Flexible, but the validator has to parse arbitrary SQL correctly, a prompt injection can still produce expensive or misleading queries, and every answer's correctness depends on the model writing correct joins.
2. **Metrics layer.** A fixed set of parameterised queries. The model only chooses a metric and fills in typed parameters (cities, work modes, seniority, title keywords, skills, company, recency), and the parameters are validated and bound, never pasted into the SQL.
3. **A semantic-layer product** (dbt Semantic Layer, Cube). The right idea, but an extra service and licence for five metrics.

## Decision

**Option 2**, in `src/jobmarket/api/metrics.py`. The metrics are `top_skills`, `skill_trend`, `compare_cities`, `count_jobs` and `top_companies`. They take shared filters and cover every analytical example question in the PRD except salaries, which aren't collected.

Defence in depth:

| Layer | Protection |
|---|---|
| Plan schema | The router's JSON must validate against `RoutePlan`. Unknown metrics are rejected, and unknown fields (for example a `"sql"` key) are ignored |
| SQL | Written in code. User text only ever becomes a bound parameter |
| Role | The API reads the warehouse as `JMA_SERVE`: `SELECT` on Gold only, with secondary roles turned off for the session (NFR-12) |
| Tests | `tests/test_api.py` sends hostile plans ("drop table …", injected SQL, "ignore previous instructions…") and checks that no model text reaches SQL |

## Consequences

- A new kind of question needs a new metric, written and tested in code. That is slower than text-to-SQL, but each metric is correct by construction and testable.
- Questions the metrics can't express fall back to semantic search, or to a "not enough information" answer.
- The answer text for analytical questions is generated from the result, not by the model, so its numbers are exact.
