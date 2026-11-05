# Silver Layer

The Silver layer turns raw Bronze records into **clean, trustworthy rows**: typed columns, a known city, no personal contact details, and reposts identified. It's built with **dbt**, as SQL models in `transform/`.

| | |
|---|---|
| **Requirements** | FR-ING-01 (two sources), FR-TRN-01 (typed columns), FR-TRN-02 (latest version), FR-TRN-11 (grain and tests), FR-TRN-12 (target cities), NFR-15 (personal data removed), NFR-24 (portable SQL) |
| **Models** | `transform/models/staging/stg_postings.sql`, `transform/models/silver/slv_postings.sql` |
| **Engine** | DuckDB locally; Snowflake through the same models ([ADR-0005](../decisions/0005-portable-warehouse-layer.md)) |

---

## Models

```mermaid
flowchart LR
    B[("bronze.raw_postings<br/>raw JSON")] --> S1["stg_postings__backfill"] & S2["stg_postings__greenhouse"]
    S1 & S2 --> S["stg_postings<br/>view<br/>all sources, one shape"]
    A[/"city_aliases<br/>seed (CSV)"/] --> P
    S --> P[("slv_postings<br/>table<br/>clean · located ·<br/>private · deduplicated")]
```

### Staging views

Each source stores a different raw format, so each has its own staging model that maps it to one common set of columns. `stg_postings` combines them.

| Model | Source format | Notes |
|---|---|---|
| `stg_postings__backfill` | Flat JSON records from the initial backfill batch | "Not Applicable" seniority becomes NULL |
| `stg_postings__greenhouse` | Greenhouse API job objects | HTML descriptions converted to plain text by the `html_to_text` macro; `first_published` is the posted date |
| `stg_postings` | All of the above, combined | To add a source, add a model with the same columns and list it here |

Nothing is removed or interpreted in staging, apart from trimming text and casting types.

**Grain:** one row per Bronze record (`source_id`, `batch_id`, `source_posting_id`).

### `slv_postings` (table)

**Grain:** one row per posting per source (`source_id`, `source_posting_id`). Key: `posting_key`.

| Step | What it does | Why |
|---|---|---|
| 1. Latest version | If a posting arrived in several batches, keep the most recent | One current row per posting (FR-TRN-02) |
| 2. City | Match the location text against `city_aliases`, preferring a city name over an area name over a state | Every row belongs to Hyderabad or Bengaluru; others are excluded (FR-TRN-12) |
| 3. Privacy | Replace email addresses and Indian mobile numbers with `[email removed]` / `[phone removed]` | Personal data never reaches Gold or the search index (NFR-15) |
| 4. Fingerprint | md5 of company name plus the description with whitespace normalised | The same text at the same company is a repost |
| 5. Canonical | In each repost group, the earliest-posted row becomes canonical | Gold counts each real job once |
| 6. Target role | Flag titles that are data engineering, analytics, ML or AI roles (`is_target_role`) | Some sources return every role at a company; Gold and the assistant use only target roles |

Reposts are **flagged, not deleted** (`is_canonical`, `canonical_posting_key`, `copies_in_group`), so the duplicate rate can be measured and the data-quality experiment can compare indexes built with and without deduplication.

## City aliases

`transform/seeds/city_aliases.csv` lists the text that identifies each city:

| `match_level` | Examples | Used when |
|---|---|---|
| `city` | hyderabad, secunderabad, bengaluru, bangalore | The city is named |
| `area` | kondapur, gachibowli, whitefield, anekal | Only a neighbourhood or nearby town is named |
| `state` | telangana, karnataka | Only the state is given |

To support a new spelling, add a row and rebuild.

## Portable SQL

Engine-specific functions are wrapped in macros in `transform/macros/portability.sql`, each with a DuckDB and a Snowflake version:

| Macro | DuckDB | Snowflake |
|---|---|---|
| `json_str(col, path)` | `json_extract_string(col, '$.path')` | `col:path::varchar` |
| `replace_all(expr, pattern, repl)` | `regexp_replace(..., 'g')` | `regexp_replace(...)` |
| `matches(expr, pattern)` | `regexp_matches(...)` | `regexp_instr(...) > 0` |

Regex patterns avoid backslashes (`[.]` instead of `\.`), because the two engines treat backslashes in string literals differently.

## Tests

`make dbt-build` builds every model and runs its tests:

| Test | Checks |
|---|---|
| `unique`, `not_null` on keys | Grain holds |
| `accepted_values` on `city` and `city_match_level` | Only expected values |
| `relationships` on `canonical_posting_key` | Every repost points at a real posting |
| `assert_no_pii_in_silver_descriptions` | No email or phone number remains |
| `assert_one_canonical_per_repost_group` | Each repost group has exactly one canonical row |

## Running it

```bash
make bronze        # load raw files first
make dbt-build     # build and test staging and Silver on DuckDB
```

Results on 2026-11-05, two sources:

| | Backfill | Greenhouse |
|---|---|---|
| Postings in Silver | 2,000 | 628 |
| Unique after reposts removed | 1,816 | 614 |
| Target data/AI roles | 1,998 | 65 |

Known gap: Silver resolves the city from a job's main location only. Greenhouse jobs whose main location is, say, "Remote", but which list a Hyderabad or Bengaluru office, are collected but not yet included.
