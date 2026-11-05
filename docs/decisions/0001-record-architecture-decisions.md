# ADR-0001: Record architecture decisions

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-11-05 |
| **Deciders** | Anurag V V |

## Context

The project makes many technical choices (warehouse, vector store, models, streaming architecture). Without a record, the reasons are forgotten, and choices get revisited without new information. Reviewers also need to understand why the system looks the way it does.

## Options considered

1. **No formal record:** decisions live in commit messages and memory. Simple, but reasons are lost.
2. **A single design document:** one place, but it becomes long and gets out of date.
3. **Architecture decision records:** one short file per decision, numbered and immutable.

## Decision

Use architecture decision records in `docs/decisions/`, one per significant decision, following [the template](template.md). A decision is changed only by writing a new record that supersedes the old one.

## Consequences

- Every significant choice has a short, findable explanation.
- Writing a record takes a few minutes per decision.
- Reviewers can follow the system's evolution without reading the code.
