---
hide:
  - navigation
  - toc
---

# Job Market Assistant

Ask questions about data engineering and AI jobs in **Hyderabad, Bengaluru and remote roles open to candidates in India**, and get answers based on real job postings, with sources.

> **Status:** Phases 0–8 complete. Version 1 needs 14 days of daily runs; see [Release Readiness](evaluation/release.md).

## Where to go

The site has five sections. Each card below is one tab in the top bar.

<div class="grid cards" markdown>

-   :material-school-outline:{ .lg .middle } **Learn**

    ---

    The system explained in plain language, no code needed.

    - [User's Guide](guide.md): what it does and how to use it
    - [Project Story](story.md): how it was built, chapter by chapter
    - [How the Pieces Operate Together](how-it-operates.md): Snowflake, dbt, Airflow, Kafka and the layers
    - [How Data Moves](data-movement.md): where the data is, and which program moves it
    - [Glossary](glossary.md)

-   :material-puzzle-outline:{ .lg .middle } **Components**

    ---

    What each part of the running system contains, and how to run it.

    - Pipeline: [Bronze](pipeline/bronze.md), [Silver](pipeline/silver.md), [Gold](pipeline/gold.md), [Snowflake](pipeline/snowflake.md), [Retrieval Index](pipeline/retrieval_index.md)
    - Serving: [API](serving/api.md)
    - Operations: [Orchestration](operations/orchestration.md), [Streaming](operations/streaming.md), [Delivery](operations/delivery.md)
    - Evaluation: [Results](evaluation/results.md), [Release Readiness](evaluation/release.md)

-   :material-file-tree-outline:{ .lg .middle } **Code Map**

    ---

    The source code, piece by piece: the main parts, how they connect and which folder holds each one.

    [:octicons-arrow-right-24: Start at the overview](code/index.md)

-   :material-sitemap-outline:{ .lg .middle } **Decisions**

    ---

    Why the system is built this way.

    - [Decisions, Explained](architecture.md): each choice along the data flow, as one story
    - [All Decision Records](decisions/index.md): the eleven ADRs

-   :material-clipboard-text-outline:{ .lg .middle } **Project**

    ---

    Planning and working on the project.

    - [Roadmap](roadmap.md)
    - [Requirements](requirements/product_requirements.md): product, functional, non-functional, data sources, evaluation plan
    - [Development Setup](development/setup.md) and [Conventions](development/conventions.md)

</div>

---

## What it does

The assistant answers questions such as:

- "Which skills do most data engineer jobs ask for?"
- "Which companies are hiring AI engineers in Bengaluru?"
- "What do companies mean by 'strong Kafka experience'?"
- "Which jobs fit my skills, and what am I missing?"

Questions about **counts and trends** are answered with SQL over organised tables. Questions about **what postings say** are answered by finding the most relevant postings and having a language model summarise them. This second approach is called retrieval-augmented generation (RAG). Every answer cites the postings it is based on.

## Why it exists

To answer those questions well, you need everything a data engineer builds in practice: collecting data, cleaning it, storing it, organising it and serving it to an AI model. The project is a complete, working example of that, with an AI assistant as the result.

Most RAG demos index a folder of documents and stop there. In practice, answer quality depends mostly on the data behind the model: whether it's deduplicated, current and well labelled. This project builds that foundation properly and **measures** how much each data-quality step improves the answers.

## How it works

Data moves through stages, much like a kitchen: raw groceries arrive, get washed and prepared, then cooked and served.

| Stage | What happens | Kitchen analogy |
|---|---|---|
| **1. Collect** | Download job postings from public sources | Groceries delivered |
| **2. Bronze** | Store postings exactly as received | Groceries in the fridge, unopened |
| **3. Silver** | Remove duplicates, fix city names, strip personal data, find skills, track changes | Washed and chopped |
| **4. Gold** | Arrange into tables that are easy to count and compare | Dishes ready to serve |
| **5. Index** | Split posting text into passages and turn them into searchable vectors | Menu organised by flavour |
| **6. Answer** | Route each question to SQL or search, then let a language model write a cited answer | The waiter takes the order and brings the dish |

**Bronze, Silver and Gold** are the standard industry names for raw, cleaned and business-ready data (the *Medallion architecture*).

### The full flow

[Open the diagram full screen (zoomable)](flow.html){ .md-button .md-button--primary }

```mermaid
--8<-- "docs/assets/flow.mmd"
```

Read it from top to bottom: postings come in at the top and answers come out at the bottom. Solid arrows show data moving. The dotted arrow is your question going to the service. The supporting tools run, test and measure every stage.

## The tools

| Tool | What it does here | Kitchen analogy | Decision |
|---|---|---|---|
| **Python** | The language for collectors, the API and tests | The chef's hands | — |
| **DuckDB** | A small database on your laptop, for development | A home fridge | [ADR-0005](decisions/0005-portable-warehouse-layer.md) |
| **Snowflake** | A cloud data warehouse, as used by companies | A restaurant's walk-in freezer | [ADR-0003](decisions/0003-snowflake-as-primary-warehouse.md) |
| **dbt** | Turns SQL files into the Silver and Gold tables, with tests | The recipes | [Silver](pipeline/silver.md), [Gold](pipeline/gold.md) |
| **Apache Airflow** | Runs each step on a schedule and retries failures | The kitchen timetable | [ADR-0010](decisions/0010-dbt-in-airflow.md) |
| **Apache Kafka** | Streams new postings in as they appear | A conveyor belt | [ADR-0009](decisions/0009-lambda-architecture-for-streaming.md) |
| **pgvector** (PostgreSQL) | Stores passages so they can be searched by meaning | The menu, organised by flavour | [ADR-0004](decisions/0004-vector-store-selection.md) |
| **Ollama** | Runs AI models on your own laptop: free and private | A home cook | [ADR-0006](decisions/0006-llm-provider-strategy.md) |
| **Gemini and Groq** | Hosted AI models: more powerful, free tiers | A hired chef | [ADR-0006](decisions/0006-llm-provider-strategy.md) |
| **FastAPI** | The web service you send questions to | The waiter | [ADR-0008](decisions/0008-metrics-layer-not-text-to-sql.md), [API](serving/api.md) |
| **Docker** | Packages every service so it starts with one command | A lunchbox: everything travels together | [Delivery](operations/delivery.md) |
| **GitHub Actions** | Tests every change automatically | A food-safety inspector | In place |

## Quick start

```bash
git clone https://github.com/vvanurag/job-market-assistant.git
cd job-market-assistant
make setup     # virtual environment, dependencies, git hooks, .env
make doctor    # checks Python, Docker, DuckDB, Snowflake, Ollama and API keys
```

The full guide, including Snowflake and API key setup, is in [Development Setup](development/setup.md).

## Author

Anurag V V

## Requirement identifiers

| Prefix | Meaning | Defined in |
|---|---|---|
| `G` | Product goal | Product Requirements |
| `US` | User story | Product Requirements |
| `FR-ING`, `FR-TRN`, `FR-ORC`, `FR-STR` | Ingestion, transformation, orchestration and streaming requirements | Functional Requirements |
| `FR-IDX`, `FR-QA`, `FR-API` | Retrieval index, question answering and API requirements | Functional Requirements |
| `FR-EVL`, `FR-OBS` | Evaluation and observability requirements | Functional Requirements |
| `NFR` | Non-functional requirement | Non-Functional Requirements |
| `R`, `Q` | Risk, open question | Product Requirements |
| `ADR` | Architecture decision record | Decisions |
