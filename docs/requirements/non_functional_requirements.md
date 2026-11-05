# Non-Functional Requirements

| | |
|---|---|
| **Version** | 0.2 (draft): added NFR-24 to NFR-27; NFR-10 and NFR-18 revised |
| **Status** | In review |
| **Owner** | Anurag V V |
| **Last updated** | 2026-11-05 |

Non-functional requirements define *how well* the system must work. Each one has a measurable target and a stated way of measuring it, so it can be checked rather than argued about.

Service levels follow the usual terms:

- **SLI** (service level indicator): what is measured, such as the age of the newest posting.
- **SLO** (service level objective): the target for that measure, such as "under 26 hours on 95% of days".
- **SLA** (service level agreement): a commitment to someone else, with consequences if missed. This is a personal project, so there are no formal SLAs; the targets below are SLOs.

---

## 1. Freshness

| ID | Requirement | Target (SLO) | Measured by | Priority |
|---|---|---|---|---|
| NFR-01 | Batch freshness: the Gold layer includes postings collected by the latest scheduled run. | Gold data no older than 26 hours on at least 95% of days | Max `loaded_at` per source, checked after each run | M |
| NFR-02 | Streaming freshness: a new posting detected by the stream is searchable. | Within 60 minutes for 95% of streamed postings | Difference between detection time and index time | S |
| NFR-03 | Closed postings stop appearing as open in search results. | Within one batch run of being marked closed | Spot check of closed postings in the index | M |

## 2. Performance

| ID | Requirement | Target (SLO) | Measured by | Priority |
|---|---|---|---|---|
| NFR-04 | `POST /search` latency | 95th percentile under 1.5 s | API request logs | M |
| NFR-05 | `POST /ask` latency, end to end including the LLM | 95th percentile under 8 s; median under 5 s | API request logs | M |
| NFR-06 | Daily batch pipeline duration | Under 60 minutes end to end | Orchestrator run history | S |

## 3. Quality of answers

| ID | Requirement | Target | Measured by | Priority |
|---|---|---|---|---|
| NFR-07 | Answer quality meets the evaluation thresholds | As defined in [Evaluation Plan section 4](evaluation_plan.md#4-acceptance-thresholds) | Evaluation runs | M |

## 4. Cost

| ID | Requirement | Target | Measured by | Priority |
|---|---|---|---|---|
| NFR-08 | Total monthly running cost (warehouse, LLM, hosting) stays within budget | Free tiers only during development (LLM cost of zero); Snowflake within trial credits. Any paid budget is set only after Phase 7 evaluation; alert at 80% of it | Provider billing and per-request cost logs | M |
| NFR-09 | Warehouse compute suspends when idle | Auto-suspend at 60 s or less on all warehouses | Warehouse configuration | M |

## 5. Security and privacy

| ID | Requirement | Target | Measured by | Priority |
|---|---|---|---|---|
| NFR-10 | Resume contents are personal data and are not stored after the request completes, not written to logs, and not used for any other purpose. Raw resume text is never sent to a free-tier API. | Zero resume content in logs, tables or free-tier API requests | Log review; automated test that sends a marker string and searches logs and outbound request records for it | M |
| NFR-11 | Secrets are never stored in the repository. | Zero secrets in git history | Secret scanning in CI | M |
| NFR-12 | Warehouse access follows least privilege, with separate roles for ingestion, transformation and read-only serving. | Serving role has `SELECT` only on Gold | Role and grant review | M |
| NFR-13 | Generated SQL can only read approved Gold objects. | No write, DDL or access outside Gold possible | Read-only role plus a test suite of hostile prompts | M |

## 6. Compliance

| ID | Requirement | Target | Measured by | Priority |
|---|---|---|---|---|
| NFR-14 | Every source is used within its terms of use, including rate limits and attribution. Any exception must be accepted by the owner and recorded in a decision record. | 100% of active sources have a recorded terms review or an owner-accepted exception | [Data Sources](data_sources.md) register | M |
| NFR-15 | Personal data of individuals in postings (for example recruiter names, emails, phone numbers) is removed before indexing. | Not present in Gold or the index | Automated pattern checks | S |

## 7. Reliability

| ID | Requirement | Target | Measured by | Priority |
|---|---|---|---|---|
| NFR-16 | Failure isolation: a failing source does not stop the rest of the pipeline. | Other sources complete normally | Fault-injection test in CI | M |
| NFR-17 | Recovery: a failed run can be re-run without manual clean-up or duplicates. | Re-run produces identical row counts | Idempotency test | M |
| NFR-18 | API availability. Version 1 runs on the owner's machine for demonstrations only. | Best effort; no formal target for version 1 | — | W |

## 8. Maintainability and reproducibility

| ID | Requirement | Target | Measured by | Priority |
|---|---|---|---|---|
| NFR-19 | A new developer can set up the local environment from the README. | Under 60 minutes on a clean machine | Timed walkthrough | S |
| NFR-20 | Python code has automated tests for extractors, routing and API contracts. | At least 80% line coverage on these modules | CI coverage report | S |
| NFR-21 | Code style is enforced automatically. | Lint and format checks pass in CI | CI | M |
| NFR-22 | Significant technical decisions are recorded. | One decision record per decision listed in the [decision index](../decisions/index.md) | Review | M |
| NFR-23 | Runtime services run in containers with pinned dependency versions. | All services start locally with one documented command (`docker compose up`) | CI build | M |

## 9. Portability

| ID | Requirement | Target | Measured by | Priority |
|---|---|---|---|---|
| NFR-24 | Warehouse portability: the transformation layer can run on a second engine, so the Snowflake continuation decision (open question Q3) stays cheap to make. | All Silver and Gold models build and pass tests on DuckDB as well as Snowflake | CI job building the dbt project against DuckDB | M |
| NFR-25 | Model provider portability: switching between local models, Google AI Studio and Groq Cloud requires only configuration. | No provider-specific code outside the model interface module | Code review; evaluation runs on each provider | M |
| NFR-26 | Raw data is kept as files outside the warehouse, so Bronze can be rebuilt in any engine. | 100% of Bronze batches have a matching file copy | Daily reconciliation of batch IDs | M |
| NFR-27 | Free-tier operation: the system works within the free-tier rate limits of the chosen API providers. | Evaluation runs complete without manual intervention; rate-limit errors are retried, not failed | Evaluation logs | S |
