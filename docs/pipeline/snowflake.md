# Running on Snowflake

The pipeline runs on two engines: **DuckDB** on your laptop for development, and **Snowflake** in the cloud. The same code and the same dbt models produce identical results on both ([ADR-0005](../decisions/0005-portable-warehouse-layer.md), NFR-24).

| | |
|---|---|
| **Requirements** | NFR-24 (portable transformation layer), NFR-26 (file copy of Bronze), NFR-12 (least-privilege roles) |
| **Code** | `src/jobmarket/bronze/snowflake_loader.py`, `src/jobmarket/portability.py`, `transform/profiles.yml` (target `snowflake`) |
| **Prerequisite** | Snowflake set up and `make doctor` passing; see [Development Setup](../development/setup.md) |

---

## Commands

```bash
make bronze-snowflake      # load raw files into Snowflake Bronze   (role JMA_INGEST)
make dbt-build-snowflake   # build and test Silver and Gold         (role JMA_TRANSFORM)
make compare               # check Silver and Gold match DuckDB, table by table
```

## Which role does what

Each step connects with the least-privileged role that can do the job:

| Step | Role | Can | Cannot |
|---|---|---|---|
| Load Bronze | `JMA_INGEST` | Create and write tables in `BRONZE`; write to the `RAW_FILES` stage | Read or change Silver or Gold |
| Build Silver and Gold | `JMA_TRANSFORM` | Read `BRONZE`; create tables and views in `SILVER` and `GOLD` | Write Bronze |
| Serve answers (Phase 6) | `JMA_SERVE` | Read `GOLD` | Anything else |

## How the Snowflake Bronze load works

The Snowflake loader keeps the same contract as the DuckDB loader: the same table, the same key, the same fingerprints, safe to re-run.

1. **Upload:** `PUT` copies the batch's files into the internal stage `BRONZE.RAW_FILES/<source>/<batch>/postings/`, compressed. They stay there as the file copy of Bronze (NFR-26).
2. **Read as text:** `COPY INTO` a temporary table reads each file as **one text value**: no splitting into fields or lines, and no escape processing. The text is byte-for-byte the file on disk.
3. **Fingerprint and parse:** `sha2(content, 256)` gives the same fingerprint DuckDB computes; `try_parse_json` turns the text into a `VARIANT` payload, or NULL if it isn't valid JSON.
4. **Insert new rows only:** exactly as in DuckDB. Unchanged rows are counted, changed content is reported as a conflict, and nothing is overwritten.

Reading the files as text rather than as JSON is deliberate. It's what makes the fingerprints identical across engines, which in turn proves both warehouses hold exactly the same raw records.

## Proving the engines agree

`make compare` reads the meaningful columns of every Silver and Gold table from both engines and compares them row by row: keys, cities, flags, fingerprints, counts and dates.

Result on 2026-11-05:

| Table | DuckDB | Snowflake | Result |
|---|---|---|---|
| Bronze fingerprints | 2,648 | 2,648 | identical |
| `silver.slv_postings` | 2,628 | 2,628 | identical |
| `silver.slv_posting_skills` | 31,606 | 31,606 | identical |
| `gold.fct_postings` | 1,877 | 1,877 | identical |
| `gold.fct_posting_skills` | 26,343 | 26,343 | identical |
| `gold.dim_company` | 805 | 805 | identical |
| `gold.dim_skill` | 128 | 128 | identical |
| `gold.dim_location` | 2 | 2 | identical |
| `gold.dim_date` | 3,287 | 3,287 | identical |

The Silver `content_fingerprint` is computed from descriptions **after** HTML decoding and personal-data removal. Matching fingerprints therefore show that the `html_to_text`, `redact_pii` and `replace_all` macros produce identical text on both engines.

All 77 dbt tests pass on both engines. A Snowflake build takes about 17 seconds on an X-Small warehouse.

## What this means for the Snowflake decision

Open question Q3 (how to continue after the Snowflake trial) can now be decided at any time without risk:

| Option | Work needed |
|---|---|
| Keep Snowflake | None |
| Move to DuckDB only | Stop running the Snowflake commands; everything already works locally |
| Move to another warehouse supported by dbt | Add that engine's versions of the macros in `transform/macros/portability.sql`, then use `make compare` to confirm |

## Limitations

- CI can't run `make compare`, because it has neither the data nor Snowflake credentials. CI checks that the dbt project compiles; the comparison is run locally after changes to models or macros.
- `JMA_TRANSFORM` builds Silver and Gold, so it can also read Silver. The serving role, which reads Gold only, is used from Phase 6.
