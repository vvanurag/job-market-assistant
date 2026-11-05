# Development Setup

This guide takes a new machine to a working environment. It targets macOS on Apple Silicon; Linux works with the equivalent packages. Expected time: under 60 minutes (NFR-19).

When you finish, `make doctor` should report no failures.

---

## 1. Prerequisites

| Tool | Version | Install (macOS) | Used for |
|---|---|---|---|
| Python | 3.12 | `brew install python@3.12` | All project code |
| Git | any recent | Included with Xcode Command Line Tools | Version control |
| Docker | any recent | [OrbStack](https://orbstack.dev) (recommended on Apple Silicon) or Docker Desktop | Running services locally |
| Ollama | any recent | [ollama.com/download](https://ollama.com/download) | Local language and embedding models |
| Make | any | Included with Xcode Command Line Tools | Project commands |

## 2. Clone and install

```bash
git clone https://github.com/vvanurag/job-market-assistant.git
cd job-market-assistant
make setup
```

`make setup` creates a virtual environment in `.venv`, installs the project with its development tools, installs the git pre-commit hooks, and creates `.env` from `.env.example`.

Run `make` on its own to list every available command.

## 3. Local models (Ollama)

Start Ollama (the desktop app starts it automatically, or run `ollama serve`), then pull the default models:

```bash
ollama pull llama3            # chat model
ollama pull nomic-embed-text  # embedding model
```

Different models can be set with `OLLAMA_CHAT_MODEL` and `OLLAMA_EMBED_MODEL` in `.env`. Model choice is evaluated in Phase 7 ([ADR-0006](../decisions/0006-llm-provider-strategy.md)).

## 4. Hosted model API keys

Both providers offer free tiers. Store keys only in `.env`, which git ignores (NFR-11).

| Provider | Where to get a key | `.env` variable |
|---|---|---|
| Google AI Studio (Gemini) | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | `GEMINI_API_KEY` |
| Groq Cloud | [console.groq.com/keys](https://console.groq.com/keys) | `GROQ_API_KEY` |

!!! warning "Free tiers and personal data"
    Free-tier terms may allow the provider to use submitted content to improve its products. Never send personal data, such as resume text, to a free-tier API (NFR-10).

## 5. Snowflake

### 5.1 Create the warehouse, database and roles

1. Sign in to Snowsight with a user that has `SYSADMIN` and `SECURITYADMIN` (on a trial account, `ACCOUNTADMIN`).
2. Open a new SQL worksheet and paste [`infra/snowflake/01_setup.sql`](https://github.com/vvanurag/job-market-assistant/blob/main/infra/snowflake/01_setup.sql).
3. Choose **Run All** (Cmd+Shift+Enter). The script grants the new roles to the user running it, so nothing needs editing.
4. Check the first result: it shows which user receives the roles and which account you're in.

This creates:

| Object | Name | Notes |
|---|---|---|
| Warehouse | `JMA_WH` | X-Small, suspends after 60 seconds idle (NFR-09) |
| Database | `JOB_MARKET` | |
| Schemas | `BRONZE`, `SILVER`, `GOLD` | Medallion layers |
| Stage | `BRONZE.RAW_FILES` | Landing area for raw files |
| Role | `JMA_INGEST` | Writes Bronze only |
| Role | `JMA_TRANSFORM` | Reads Bronze, builds Silver and Gold |
| Role | `JMA_SERVE` | Reads Gold only (NFR-12, NFR-13) |

### 5.2 Set up key-pair authentication (recommended)

Snowflake is phasing out password-only sign-in for programmatic access, so use a key pair:

```bash
mkdir -p ~/.snowflake
openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out ~/.snowflake/jma_key.p8 -nocrypt
openssl rsa -in ~/.snowflake/jma_key.p8 -pubout -out ~/.snowflake/jma_key.pub
chmod 600 ~/.snowflake/jma_key.p8
```

Copy the contents of `jma_key.pub` without the `-----BEGIN/END PUBLIC KEY-----` lines, and run in Snowsight:

```sql
set me = '"' || current_user() || '"';
alter user identifier($me) set rsa_public_key = '<PASTE_KEY_HERE>';
```

### 5.3 Find your login name

Key-pair login uses your **login name**, which can differ from your user name. For example, accounts created with an email address often have the email as the login name. Run:

```sql
set me = '"' || current_user() || '"';
desc user identifier($me);
select "property", "value" from table(result_scan(last_query_id(-1)))
where "property" in ('NAME', 'LOGIN_NAME');
```

Use the `LOGIN_NAME` value as `SNOWFLAKE_USER` in `.env`.

The private key stays outside the repository.

### 5.4 Configure `.env`

```ini
SNOWFLAKE_ACCOUNT=<account identifier, e.g. orgname-accountname>
SNOWFLAKE_USER=<your LOGIN_NAME from 5.3>
SNOWFLAKE_PRIVATE_KEY_PATH=~/.snowflake/jma_key.p8
SNOWFLAKE_ROLE=JMA_TRANSFORM
```

Find the account identifier in Snowsight under your profile menu, **Connect a tool to Snowflake**.

## 6. Verify

```bash
make doctor        # fast checks
make doctor-deep   # also calls each model and API to prove it works
```

Expected result once everything is configured:

```
  PASS  Python            3.12.x (need >= 3.12)
  PASS  Docker            ... on OrbStack
  PASS  Secrets           .env is not tracked by git
  PASS  DuckDB            v..., schemas bronze/silver/gold at .../data/dev/jobmarket.duckdb
  PASS  Snowflake         role JMA_TRANSFORM, warehouse JMA_WH, database JOB_MARKET
  PASS  Ollama            running; models llama3, nomic-embed-text installed
  PASS  Google AI Studio  API key set (not verified; use --deep)
  PASS  Groq Cloud        API key set (not verified; use --deep)
```

## 7. Everyday commands

| Command | What it does |
|---|---|
| `make lint` | Check code style without changing files |
| `make format` | Fix code style |
| `make test` | Run the test suite |
| `make check` | Run everything CI runs |
| `make docs` | Serve this documentation at <http://127.0.0.1:8000> |

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Docker: daemon not reachable` | Start OrbStack or Docker Desktop |
| `Ollama: not reachable` | Start the Ollama app, or run `ollama serve` |
| `Ollama: models missing` | Run the `ollama pull` command shown in the message |
| `Snowflake: ... JWT token is invalid` | `SNOWFLAKE_USER` must be the `LOGIN_NAME` (section 5.3), not the user name. Also check `RSA_PUBLIC_KEY_FP` in `desc user` matches your key |
| `Snowflake: missing schemas` | Re-run `infra/snowflake/01_setup.sql`, or check `SNOWFLAKE_ROLE` has usage on the database |
| Setup script: `User '...' does not exist or not authorized` | The user name didn't match the user object. The current script uses `current_user()` to avoid this; make sure you ran the latest version with **Run All** |
