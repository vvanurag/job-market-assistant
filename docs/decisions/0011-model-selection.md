# ADR-0011: Model selection

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-11-06 |
| **Deciders** | Anurag V V |
| **Supersedes** | The shortlist in [ADR-0006](0006-llm-provider-strategy.md), which remains the provider strategy |

## Context

ADR-0006 shortlisted local models, Google AI Studio (Gemini) and Groq Cloud, and deferred the choice to the Phase 7 evaluation (FR-EVL-04). Five runs of the 54-question set compared four language models; a retrieval-only comparison compared two embedding models. Full results are in [Evaluation Results](../evaluation/results.md).

## Decision

| Role | Choice | Why |
|---|---|---|
| Routing and answering (default) | **Groq `openai/gpt-oss-120b`**, reasoning effort low | Analytical accuracy 94%, groundedness 98%, citation accuracy 99%, no false refusals. p95 1.9 s, the fastest by far |
| Fallback | **Gemini `gemini-3.5-flash-lite`** | Highest quality (analytical 100%, groundedness 99%), but p95 6.5 s, close to the 8 s limit (NFR-05) |
| Local, offline only | Gemma 2 9B through Ollama | Works, but routing is 78% accurate and p95 is 14 s; not suitable as the default |
| Not used | Llama 3 8B | Routing 57%, analytical 19%, and invalid output on 8 of 54 questions |
| Embeddings | **Ollama `nomic-embed-text`** (768 dimensions, local) | Within one question of `mxbai-embed-large`, at less than half the indexing time and smaller vectors |
| Evaluation judge | Gemini `gemini-3.5-flash-lite` | A different provider from the default answering model, so the default isn't judged by itself |

Switching is configuration only: `LLM_PROVIDER`, `LLM_MODEL` and `EMBEDDING_MODEL` (NFR-25).

## Consequences

- Groq's free tier (8,000 tokens a minute) allows about three questions a minute at full speed. Beyond that, requests wait for the quota (NFR-27). Enough for demos; a paid tier or Gemini fallback for heavier use.
- Paid-tier equivalent cost on Groq is about $0.0004 per question (2,358 tokens). The free tier costs nothing (NFR-08).
- Re-evaluate when a provider changes its models: Google closed `gemini-2.5-*` to new keys during this project, which is why the fallback is the 3.5 generation.
