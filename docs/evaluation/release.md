# Release Readiness (version 1)

Status against the [version 1 release criteria](../requirements/product_requirements.md#11-release-criteria-for-version-1), as of 2026-11-06.

| Criterion | Status |
|---|---|
| 1. All **Must** user stories meet their acceptance criteria | **Met** (table below) |
| 2. All **Must** non-functional requirements meet their targets for 14 consecutive days | **Not yet.** Every Must target is met or built, but the 14-day window starts with daily scheduled runs |
| 3. The evaluation set meets the thresholds | **Met** by the accepted run; the human check of the LLM judge is pending |
| 4. The data-quality experiment has been run and published | **Met**: [results](results.md#data-quality-experiment) |

**What remains:** run the Airflow DAG daily for 14 days (turn on `jobmarket_daily`), and review the 20% judge sample in `eval/review/v2_groq_human_review.md`.

## Must user stories

| Story | Evidence |
|---|---|
| US-01 Top skills for a role | `top_skills` metric; analytical accuracy 94% against reference SQL |
| US-02 Skill demand over time | `skill_trend` metric, reposts counted once. Trends become meaningful as daily runs accumulate |
| US-05 What employers mean by a requirement, with 3+ citations | Semantic route; citation accuracy 99%, groundedness 98% |
| US-06 Search by meaning plus filters, open roles only | Hybrid search with filters; recall@5 93%; stale rate 0% |
| US-10 Is a posting open, and did it change? | `GET /postings/{id}`: status, first and last seen, version history (SCD2) |
| US-12 Say when it doesn't know | Correct refusal rate 100%, false refusal rate 0% |
| US-13 Alert on source failure or stale data | Airflow failure callbacks and the freshness check write alerts, with an optional webhook |

## Must non-functional requirements

| NFR | Target | Status |
|---|---|---|
| NFR-01 Batch freshness | Gold under 26 h old on 95% of days | Check built (`check_freshness`); needs the daily schedule running |
| NFR-03 Closed postings leave search | Within one batch run | Built (status filter + metadata refresh, unit-tested); no posting has closed yet in real data |
| NFR-04 `/search` p95 | under 1.5 s | Met: p95 about 9 ms for the search, about 65 ms end to end |
| NFR-05 `/ask` p95 / median | under 8 s / under 5 s | Met: 1.9 s / 1.3 s (Groq, evaluation run) |
| NFR-07 Evaluation thresholds | Evaluation Plan section 4 | Met ([results](results.md)) |
| NFR-08 Cost | Free tiers; Snowflake within trial credits | Met: zero LLM spend; X-Small warehouse with 60 s auto-suspend |
| NFR-09 Auto-suspend | 60 s or less | Met (`JMA_WH`) |
| NFR-10 Resume privacy | Nothing stored, logged or sent to free tiers | Met: skills extracted locally (Q5 option C); tested |
| NFR-11 No secrets in git | Secret scanning in CI | Met: gitleaks scans the full history on every push |
| NFR-12 Least privilege | Serving role `SELECT` on Gold only | Met, after turning off secondary roles per session ([details](../pipeline/snowflake.md#secondary-roles)) |
| NFR-13 Generated SQL can't escape Gold | Read-only role plus hostile-prompt tests | Met: the model never writes SQL ([ADR-0008](../decisions/0008-metrics-layer-not-text-to-sql.md)) |
| NFR-14 Terms of use | Review or owner-accepted exception per source | Met: Greenhouse reviewed; the backfill's owner-accepted exception is recorded outside this repository |
| NFR-16 Failure isolation | A failing source doesn't stop the rest | Built: loading runs even when collection fails; boards fail independently. No automated fault-injection test yet |
| NFR-17 Recovery | Re-runs give identical counts | Met: idempotent loaders and builds, tested |
| NFR-21 Style | Lint and format in CI | Met |
| NFR-22 Decisions recorded | One record per decision | Met: 11 decision records |
| NFR-23 Containers | One command starts everything | Met: `docker compose up -d` |
| NFR-24 Portability | Builds and tests on DuckDB and Snowflake | Met: CI builds on DuckDB; `make compare` shows all 12 tables identical |
| NFR-25 Provider portability | Configuration only | Met: four models evaluated by changing settings |
| NFR-26 Raw files kept | Every batch has a file copy | Met for every batch so far; no automated daily reconciliation yet |
