# Job Market Assistant

Ask questions about data engineering and AI jobs in **Hyderabad, Bengaluru and remote roles open to candidates in India**, and get answers based on real job postings, with sources.

> **Status:** Phases 0–8 complete. Version 1 needs 14 days of daily runs; see [Release Readiness](evaluation/release.md).

<div class="grid cards" markdown>

-   :material-book-open-page-variant:{ .lg .middle } **User's Guide**

    ---

    What the project does, how the system and pipeline work, how to use it, and lessons for a beginner data engineer, with diagrams throughout.

    [:octicons-arrow-right-24: Read the guide](guide.md)

-   :material-script-text-outline:{ .lg .middle } **The Story of the Project**

    ---

    How it was built, chapter by chapter: the decisions, the dead ends and the bugs, from the first idea to a measured system.

    [:octicons-arrow-right-24: Read the story](story.md)

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

## Documentation

| Document | Purpose |
|---|---|
| [Product Requirements](requirements/product_requirements.md) | Vision, goals, users, scope, user stories |
| [Functional Requirements](requirements/functional_requirements.md) | What the system must do, by component |
| [Non-Functional Requirements](requirements/non_functional_requirements.md) | Measurable quality targets and service levels |
| [Data Sources](requirements/data_sources.md) | Candidate sources, fields and compliance checks |
| [Evaluation Plan](requirements/evaluation_plan.md) | How answer quality is measured |
| [Roadmap](roadmap.md) | Delivery phases and exit criteria |
| [Architecture Decisions](decisions/index.md) | Record of significant technical decisions |
| [Development Setup](development/setup.md) | Getting a working local environment |
| [Conventions](development/conventions.md) | Repository layout, code style, git and documentation rules |
| [Glossary](glossary.md) | Terms used across the project |


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
