# Conventions

How code and documentation are organised and written in this repository.

---

## Repository layout

```
job-market-assistant/
├── src/jobmarket/        Python package (installed in editable mode)
│   ├── settings.py       Configuration from environment variables and .env
│   ├── checks.py         Environment checks used by `jobmarket doctor`
│   └── cli.py            Command-line entry point
├── tests/                Pytest suite, mirroring src/ module names
├── transform/            dbt project: staging, Silver and Gold models, seeds, tests
├── infra/snowflake/      Numbered, idempotent SQL scripts for Snowflake objects
├── docs/                 This documentation site (MkDocs)
├── data/                 Local data (git-ignored): DuckDB file, Bronze files
├── .github/workflows/    CI pipelines
├── Makefile              Entry point for every routine command
└── pyproject.toml        Package metadata, dependencies and tool settings
```

New components get their own subpackage under `src/jobmarket/` when their phase starts, for example `ingestion/` in Phase 1 and `api/` in Phase 6. The dbt project lives in `transform/`.

## Python

| Topic | Convention |
|---|---|
| Version | Python 3.12 or newer |
| Style | Enforced by Ruff (lint and format); line length 120 |
| Configuration | Read through `jobmarket.settings.Settings`, never `os.environ` directly |
| Secrets | Typed as `SecretStr`; never logged or printed |
| Errors | External calls (APIs, databases) handle failures explicitly and report them; they never fail silently |
| Tests | Pytest. Tests make no network calls; external services are replaced with `httpx.MockTransport` or fakes |

## SQL

| Topic | Convention |
|---|---|
| Keywords | Lowercase |
| Names | `snake_case`; tables named for their grain (`fct_postings`, `dim_company`) |
| Portability | Standard SQL where possible; engine-specific features only inside dbt macros ([ADR-0005](../decisions/0005-portable-warehouse-layer.md)) |
| Infrastructure scripts | Numbered (`01_setup.sql`) and idempotent (`create ... if not exists`) |

## Git

| Topic | Convention |
|---|---|
| Branches | `main` is always releasable. Work on short-lived branches named `<type>/<short-description>`, such as `feat/adzuna-extractor` |
| Commit messages | Imperative summary under 72 characters, then a blank line and the reason for the change. Reference requirement IDs where relevant, such as `Implements FR-ING-04` |
| Pull requests | CI must pass. Describe what changed, why, and how it was tested |
| Hooks | `pre-commit` runs style, secret and file-hygiene checks before each commit |

## Documentation

| Topic | Convention |
|---|---|
| Requirements | Every requirement has a stable ID. IDs are never reused; removed requirements are marked as withdrawn |
| Decisions | Significant technical choices get an ADR, using the [template](../decisions/template.md) |
| Versioning | Requirement documents carry a version and revision history; bump the version on each substantive change |
| Writing | Plain, direct English. Tables for comparisons, numbered steps for procedures |
