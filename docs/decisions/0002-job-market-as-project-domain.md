# ADR-0002: Job market as the project domain

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-11-05 |
| **Deciders** | Anurag V V |

## Context

The project needs a domain that exercises the full data engineering stack (batch and streaming ingestion, modeling, history, orchestration) and makes a RAG assistant genuinely useful. The domain needs both structured data, to show what SQL does well, and unstructured text, to show what retrieval does well.

## Options considered

1. **TPC-H sample data:** already available in Snowflake, but synthetic, has no free text, and answers have no real-world use.
2. **Personal documentation:** easy to index, but too small and too static to need serious data engineering.
3. **SEC EDGAR filings:** public, large, structured financial data plus long report text. A strong technical fit, but of limited personal use to the owner.
4. **Job postings:** public APIs, daily change, duplicates across sources, rich free text and structured fields, and direct value to the owner's career planning.

## Decision

Build the assistant over data engineering and AI job postings.

## Consequences

- The data has real quality problems (duplicates, closures, inconsistent fields) that justify each data engineering component.
- The answers are useful to the owner, which keeps the project motivating.
- Source terms of use must be reviewed and respected (NFR-14), and the set of sources may change over time.
- SEC EDGAR remains a possible second domain if the design is later generalised.
