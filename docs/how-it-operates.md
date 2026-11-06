# How the Pieces Operate Together

This page shows how **Snowflake, dbt, Airflow, Kafka, the Bronze, Silver and Gold layers, and the Lambda and Kappa architectures** fit together in this project.

These names are different *kinds* of things, which is the most common source of confusion. Sort them first:

| Name | What kind of thing it is | Its job in one phrase | In this project |
|---|---|---|---|
| **Bronze, Silver, Gold** | Data **layers** (the Medallion pattern) | *What state the data is in*: raw, clean, ready to use | Three schemas, in DuckDB or Snowflake |
| **Snowflake** | A cloud **warehouse** (storage + compute) | *Where* the layers live | Optional cloud target; DuckDB is the daily default |
| **dbt** | A **transformation tool** | *How* data moves from Bronze to Silver to Gold: SQL files plus tests | 17 models, run on either warehouse |
| **Airflow** | An **orchestrator** (scheduler) | *When* each step runs, in what order, with retries | The `jobmarket_daily` DAG, 06:00 IST |
| **Kafka** | An **event log** (message broker) | *How fast* new data travels: events as they happen | The topic `postings.detected` |
| **Lambda** | An **architecture pattern** | A batch layer for correctness **plus** a speed layer for freshness | **Used** |
| **Kappa** | An **architecture pattern** | **Only** a streaming layer; rebuild by replaying the log | Considered, **not used** |

The short version: **Airflow** decides *when*, **dbt** decides *how*, **Snowflake** is *where*, **Bronze/Silver/Gold** is *what state*, **Kafka** is *how fast*, and **Lambda vs Kappa** is *how the batch and fast paths are combined*.

---

## 1. The whole machine

Read from top to bottom. The left half is the **batch layer**, the right half is the **speed layer**. Together they are the **Lambda architecture**.

```mermaid
flowchart TB
    SRC["Job-board APIs<br/>(polled, return full lists)"]

    subgraph LAMBDA["LAMBDA ARCHITECTURE"]
        direction TB

        subgraph BATCH["BATCH LAYER: correct and complete, once a day"]
            direction TB
            AF["AIRFLOW<br/>DAG jobmarket_daily, 06:00 IST<br/>schedules every task below"]
            COL["Collect<br/>full daily snapshot"]
            subgraph WH["WAREHOUSE: DuckDB by default, or SNOWFLAKE"]
                direction TB
                BR[("BRONZE<br/>raw, as received<br/>+ fingerprint")]
                SI[("SILVER<br/>clean, deduplicated,<br/>history SCD2")]
                GO[("GOLD<br/>star schema +<br/>posting documents")]
                BR -->|"dbt models + tests"| SI
                SI -->|"dbt models + tests"| GO
            end
            COL -->|"load"| BR
            AF -.->|"1 collect"| COL
            AF -.->|"2 one task per dbt model"| WH
        end

        subgraph SPEED["SPEED LAYER: fast but provisional, every 15 min"]
            direction TB
            PROD["Stream producer<br/>finds postings not yet in Bronze"]
            KAF{{"KAFKA<br/>topic postings.detected"}}
            CONS["Stream consumer<br/>same seed rules as dbt"]
            PROD -->|"event per new posting"| KAF
            KAF --> CONS
        end
    end

    SRC --> COL
    SRC --> PROD
    CONS -->|"stream batch file"| BR

    subgraph SERVE["SERVING LAYER"]
        direction TB
        IDX[("Search index<br/>pgvector")]
        API["API + assistant"]
        IDX --> API
    end

    GO -->|"3 index refresh<br/>(only if all tests passed)"| IDX
    GO -->|"metrics SQL"| API
    CONS -->|"provisional document,<br/>searchable in ~15 s"| IDX
    AF -.->|"3"| IDX
```

What to notice:

- **Airflow doesn't touch data itself.** It only starts tasks (dotted arrows): collect, then each dbt model, then the index refresh.
- **dbt doesn't store data.** It sends SQL to the warehouse, and the warehouse (DuckDB or Snowflake) does the work and keeps the tables.
- **Bronze, Silver and Gold all live inside the warehouse.** They are schemas, not separate systems.
- **Kafka is only in the speed layer.** The batch layer never reads it.
- **Both layers feed the same search index.** The batch version always replaces the speed layer's provisional one on the next run.

---

## 2. Snowflake and dbt: who does what

dbt is often mistaken for a database. It isn't: it turns SQL files into tables by sending them to a warehouse, and checks the result with tests.

```mermaid
sequenceDiagram
    participant AF as Airflow
    participant DBT as dbt
    participant WH as Warehouse (Snowflake or DuckDB)
    AF->>DBT: run task dbt_slv_postings<br/>(dbt build --select slv_postings)
    DBT->>DBT: read slv_postings.sql,<br/>fill in macros for this engine
    DBT->>WH: CREATE TABLE silver.slv_postings AS SELECT ... FROM bronze...
    WH-->>DBT: table built (warehouse did the compute)
    DBT->>WH: run the model's tests (unique, not null, accepted values...)
    WH-->>DBT: 0 failing rows
    DBT-->>AF: task succeeded, so downstream tasks may start
```

On **Snowflake**, each step uses its own least-privileged role:

| Step | Tool | Snowflake role | Writes to |
|---|---|---|---|
| Load raw files | Python loader | `JMA_INGEST` | `BRONZE` |
| Build Silver and Gold | dbt | `JMA_TRANSFORM` | `SILVER`, `GOLD` |
| Answer questions | API | `JMA_SERVE` | nothing (reads `GOLD` only) |

The same dbt project builds on **DuckDB** with no changes, because engine-specific SQL is wrapped in macros. That's why the daily run can use free local DuckDB and Snowflake stays optional ([ADR-0005](decisions/0005-portable-warehouse-layer.md)).

---

## 3. Airflow: the daily timetable

Each box is one Airflow task. A task starts only when the tasks before it have succeeded.

```mermaid
flowchart LR
    C["collect"] --> L["load Bronze"]
    L --> S["dbt seed<br/>(rule files)"]
    S --> M1["dbt: Silver<br/>models"]
    M1 --> M2["dbt: Gold<br/>models"]
    M2 --> F["freshness<br/>check"]
    M2 --> I["refresh<br/>search index"]
    I --> R["record<br/>the run"]
```

In the real DAG, the two dbt boxes are 17 separate tasks, one per model, wired in the same order as dbt's own dependencies ([ADR-0010](decisions/0010-dbt-in-airflow.md)). Each runs its model **and its tests**, so a failing test stops that branch, and the index refresh (which publishes Gold to the assistant) never runs on bad data. Failed tasks retry twice and then raise an alert.

---

## 4. Kafka: the event log

Kafka keeps an ordered log of events. Producers append to it; consumers read from it at their own pace and record how far they've got (their **offset**).

```mermaid
flowchart LR
    P["Producer<br/>every 15 min"] -->|"append event<br/>key = posting_key"| T

    subgraph T["Topic postings.detected (a log)"]
        direction LR
        E1["event 1"] --- E2["event 2"] --- E3["event 3"] --- E4["event 4"]
    end

    T -->|"read next event"| C["Consumer<br/>group jobmarket-indexer"]
    C -->|"1 save to Bronze<br/>2 index it"| D[("Bronze + index")]
    C -->|"3 then commit offset"| T
```

The consumer commits its offset **only after** the posting is saved and indexed. If it crashes halfway, it reads the same event again after restarting, and because processing is idempotent the repeat changes nothing. This is called **at-least-once** delivery. The code is in [streaming.py](https://github.com/vvanurag/job-market-assistant/blob/main/src/jobmarket/streaming.py) and the `stream` commands in [cli.py](https://github.com/vvanurag/job-market-assistant/blob/main/src/jobmarket/cli.py).

---

## 5. Lambda versus Kappa

Both patterns answer the same question: *how do you get data that is both fresh and correct?*

### Lambda (used here): two paths, batch wins

```mermaid
flowchart LR
    S["Sources"] --> B["BATCH LAYER<br/>Airflow + dbt + warehouse<br/>Bronze → Silver → Gold<br/>once a day, complete"]
    S --> SP["SPEED LAYER<br/>Kafka + consumer<br/>new postings only<br/>minutes, provisional"]
    B --> V[("Serving<br/>search index + Gold")]
    SP --> V
    B -.->|"next run replaces<br/>provisional results"| SP
```

### Kappa (not used): one streaming path, replay to rebuild

```mermaid
flowchart LR
    S["Sources"] --> K{{"Kafka<br/>keeps every event<br/>for a long time"}}
    K --> SPR["Stream processor<br/>(e.g. Flink, Spark Streaming)<br/>does ALL cleaning:<br/>dedupe, match, history"]
    SPR --> V[("Serving tables<br/>+ search index")]
    K -.->|"to fix a bug or change a rule:<br/>replay the whole log"| SPR
```

| | Lambda | Kappa |
|---|---|---|
| Paths | Two: batch and speed | One: streaming only |
| Source of truth | The batch layer (Gold) | The Kafka log |
| Fixing a bug | Rerun the batch | Replay the log through the fixed processor |
| Cost | Some rules exist twice (SQL and Python) | Every transformation must be written as a stream job |
| Best when | Sources are snapshots; batch SQL already exists | Sources truly emit events; everything must be real-time |

**Why Lambda here** ([ADR-0009](decisions/0009-lambda-architecture-for-streaming.md)):

1. Job boards are **polled**; they return the full list, not change events.
2. A posting closes by **disappearing**. "Something is missing" isn't an event Kafka can carry; it needs two snapshots compared, which is batch work.
3. All cleaning is already tested **dbt SQL** that runs on two warehouses. Kappa would mean rewriting it as stream jobs.

So the batch layer stays the truth, and Kafka adds only what the batch is slow at: new postings, searchable within seconds instead of the next morning.

---

## 6. One posting's journey through both layers

A new job is published at 10:00. The stream finds it within 15 minutes; the batch confirms it the next morning.

```mermaid
sequenceDiagram
    participant J as Job board
    participant P as Stream producer
    participant K as Kafka
    participant C as Consumer
    participant AF as Airflow daily run
    participant W as Warehouse (Bronze/Silver/Gold)
    participant I as Search index
    J->>P: 10:12 poll finds new posting
    P->>K: posting.detected event
    K->>C: deliver event
    C->>W: save raw copy in Bronze (stream batch)
    C->>I: provisional document, searchable ~15 s later
    Note over I: Searchable now, but not yet in counts
    AF->>J: next day 06:00, collect full snapshot
    AF->>W: load Bronze, then dbt builds Silver and Gold (with tests)
    Note over W: Now deduplicated, matched, in history and in counts
    AF->>I: index refresh replaces the provisional document
```

---

## Related pages

- [Architecture Decisions, Explained](architecture.md): the reasons behind each choice.
- [Orchestration](operations/orchestration.md), [Streaming](operations/streaming.md), [Running on Snowflake](pipeline/snowflake.md): how to run each part.
- [Bronze](pipeline/bronze.md), [Silver](pipeline/silver.md), [Gold](pipeline/gold.md): what each layer contains.
