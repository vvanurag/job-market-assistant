# Delivery

How the system is built, checked and started.

| | |
|---|---|
| **Requirements** | FR-EVL-03, FR-OBS-03, NFR-11, NFR-20, NFR-21, NFR-23, NFR-24 |
| **Code** | `.github/workflows/ci.yml`, `Dockerfile`, `orchestration/Dockerfile`, `docker-compose.yml`, `src/jobmarket/api/status.py` |

---

## One command to start everything (NFR-23)

```bash
docker compose up -d
```

| Service | Address | Image (pinned) |
|---|---|---|
| `vectordb`: PostgreSQL + pgvector | `localhost:5433` | `pgvector/pgvector:0.8.0-pg17` |
| `api`: the assistant | <http://localhost:8000/docs> | built from `Dockerfile` (`python:3.12.16-slim`) |
| `airflow`: the daily pipeline | <http://localhost:8080> | built from `orchestration/Dockerfile` (`apache/airflow:3.3.2-python3.12`) |
| `kafka`: the streaming broker | `localhost:9094` | `apache/kafka:4.4.0` |

Ollama runs on the host (it uses the Mac's GPU), and the containers reach it at `host.docker.internal:11434`.

Before the first start, the warehouse and the index need data: run `make setup`, `make bronze`, `make dbt-build` and `make index`, or let the Airflow DAG run once.

## Continuous integration

Every push and pull request runs:

| Check | Requirement |
|---|---|
| Pre-commit hooks: ruff lint and format, YAML/TOML checks, private-key detection | NFR-21 |
| Secret scan of the **full git history** with gitleaks | NFR-11 |
| Tests with coverage, failing below 80% on extractors, routing and API contracts (82% on 2026-11-06) | NFR-20 |
| **dbt build and every test on DuckDB**, using a synthetic Bronze fixture (`tests/fixtures/bronze`) that includes a repost, a cross-source copy, personal data, a remote-India role and out-of-scope postings | NFR-24 |
| Evaluation guard: changes to retrieval, prompts, models or the evaluation set must come with a new run in `eval/results/` | FR-EVL-03 |
| Documentation builds with `--strict` | NFR-22 |
| API and Airflow container images build | NFR-23 |

The full evaluation needs the local data, the index and model access, so it runs on the developer's machine: `make eval`, then `jobmarket eval compare <run>` against the accepted run. CI enforces that it was done.

## Health view (FR-OBS-03)

<http://localhost:8000/status?key=YOUR_API_KEY> shows, on one page:

- freshness of each daily source (NFR-01)
- jobs in Gold per source, and how many are open
- the last pipeline runs, with dbt test results and embedding counts
- index builds, with embedding model and chunker version
- API usage over 7 days: requests, p50/p95 latency, tokens and paid-equivalent cost
- streaming latency and recent alerts

## Secrets (NFR-11)

- All secrets live in `.env`, which git ignores and `make doctor` checks isn't tracked. The Snowflake private key stays in `~/.snowflake/` and is mounted read-only into containers.
- Settings types secrets as `SecretStr`, so they are never printed by accident.
- The API key is compared in constant time, and `/health` is the only endpoint without it.
