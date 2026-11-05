# Job Market Assistant

A data platform and retrieval-augmented generation (RAG) assistant for the data engineering and AI job market.

The system collects public job postings every day, models them in Snowflake, and answers questions about the market. Counting and trend questions are answered with SQL; questions about what postings say are answered with retrieval. Every answer cites its sources.

**Status:** requirements phase.

## Start here

| If you want to… | Read |
|---|---|
| Understand what the system is for | [Product Requirements](requirements/product_requirements.md) |
| See exactly what it must do | [Functional Requirements](requirements/functional_requirements.md) |
| See the quality targets | [Non-Functional Requirements](requirements/non_functional_requirements.md) |
| Know where the data comes from | [Data Sources](requirements/data_sources.md) |
| Know how quality is measured | [Evaluation Plan](requirements/evaluation_plan.md) |
| See the delivery plan | [Roadmap](roadmap.md) |
| Understand why things are built a certain way | [Architecture Decisions](decisions/index.md) |

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
