# ADR-0006: Language model provider strategy

| | |
|---|---|
| **Status** | Accepted (shortlist); final model choice pending Phase 7 |
| **Date** | 2026-11-05 |
| **Deciders** | Anurag V V |

## Context

The system needs language models for question routing, answer generation, skill extraction and possibly an evaluation judge, and an embedding model for retrieval. Development runs on free tiers (NFR-08). Some inputs, such as a resume, are personal data (NFR-10). The owner also wants to learn how local and hosted models compare.

## Options considered

| Option | Strengths | Weaknesses |
|---|---|---|
| **Local models** (served with Ollama on the owner's Mac) | Private; no cost; works offline; local embedding models are strong | Slower; smaller models produce weaker answers and SQL |
| **Google AI Studio** (Gemini API) | Strong models with long context; offers embeddings; free tier | Free-tier rate limits; under free-tier terms, submitted content may be used to improve Google's products |
| **Groq Cloud** | Very fast inference of open-weight models; free tier | Tight token-per-minute limits; no embeddings API at the time of writing |
| Other paid APIs | Strong models | Not needed while free tiers suffice |

Provider limits and terms change often, so they are re-checked before each evaluation phase.

## Decision

1. **Shortlist:** local models, Google AI Studio and Groq Cloud.
2. **One interface:** all model calls go through a single internal module (FR-QA-08). All three providers offer OpenAI-compatible endpoints, which the module may use to keep provider code minimal.
3. **Embeddings start local.** A local embedding model is the default, compared against a Gemini embedding model early in Phase 7. The embedding choice is fixed before generation models are compared, because changing it means re-embedding the index.
4. **Personal data stays local by default.** Until open question Q5 is answered, resume content is processed only by local models (FR-QA-09), and raw resume text is never sent to a free-tier API (NFR-10).
5. **Final choice by evaluation.** The model for each role is chosen from the Phase 7 comparison and recorded in a new ADR.

## Consequences

- No vendor lock-in; a provider outage or terms change means a configuration change, not a rewrite (risk R8).
- The evaluation set becomes the basis for model choice, which is itself a learning goal.
- Rate limits require throttled, resumable evaluation runs (NFR-27).
- Local models need enough memory on the development machine; model size is chosen accordingly.
