# Evaluation Plan

| | |
|---|---|
| **Version** | 0.1 (draft) |
| **Status** | In review |
| **Owner** | Anurag V V |
| **Last updated** | 2026-11-05 |

This plan defines how the assistant's answers are measured, so that changes to data, retrieval, prompts or models are judged by numbers rather than impressions.

---

## 1. Evaluation set

A versioned file of at least **50 questions** stored in the repository (FR-EVL-01): [`eval/eval_set_v1.yaml`](https://github.com/vvanurag/job-market-assistant/blob/main/eval/eval_set_v1.yaml), with 54 questions. Each entry records:

| Field | Description |
|---|---|
| `id` | Stable identifier, such as `EV-012` |
| `question` | The question as a user would ask it |
| `category` | One of the categories below |
| `expected_route` | `analytical`, `semantic`, `combined` or `unanswerable` |
| `relevant` | For semantic questions: a rule over Gold (skills, city, work mode, seniority, company, title, recency) that defines which jobs are relevant. A rule rather than a hand-picked list, so the reference doesn't depend on what the system happened to retrieve, and it stays valid as data changes |
| `reference_sql` | For analytical questions: the reference SQL, whose result is the correct answer |
| `notes` | Why the question is included and what it tests |

### Categories and minimum counts

| Category | Count | Tests |
|---|---|---|
| Analytical: counts and rankings | 10 | Routing, correct SQL, deduplicated counts |
| Analytical: trends over time | 6 | Date handling, history, deduplication |
| Semantic: explain a requirement | 8 | Retrieval relevance, summarisation, citations |
| Semantic with filters | 8 | Metadata quality and filtering |
| Company-specific | 5 | Company normalisation and filtering |
| Resume matching and gap analysis | 5 | Skill extraction and ranking |
| Freshness and history | 4 | Closed postings, change tracking |
| Unanswerable or out of scope | 4 | Refusal instead of invention |

Because postings change daily, the evaluation runs against a **frozen snapshot** of the Gold layer and index. The snapshot date is recorded with every result.

## 2. Metrics

| Metric | Applies to | Definition |
|---|---|---|
| **Routing accuracy** | All | Share of questions sent to the expected route |
| **Analytical accuracy** | Analytical | Share of answers whose figures match the reference SQL result |
| **Recall@5** | Semantic | Relevant jobs among the first 5 distinct jobs retrieved, divided by min(5, number of relevant jobs). This is plain recall when 5 or fewer jobs are relevant, and precision@5 when more are, so it is always between 0 and 1 |
| **MRR** (mean reciprocal rank) | Semantic | Average of 1 ÷ rank of the first expected posting |
| **Duplicate rate@5** | Semantic | Share of top-5 results that are the same underlying posting |
| **Stale rate@5** | Semantic | Share of top-5 results that are closed postings |
| **Citation accuracy** | Semantic | Share of cited postings that actually support the statement they are cited for |
| **Groundedness** | Semantic | Share of answer statements supported by retrieved text; judged by an LLM and spot-checked by a person |
| **Correct refusal rate** | Unanswerable | Share of unanswerable questions correctly declined |
| **Latency and cost** | All | Median and 95th percentile latency; average cost per question |

## 3. Method

1. Build or refresh the frozen snapshot.
2. Run every question through the API with the configuration under test.
3. Score automatically where possible (routing, analytical accuracy, recall, MRR, duplicate and stale rates).
4. Score groundedness and citation accuracy with an LLM judge, and have a person review a random 20% sample to check the judge. (For the version 1 baseline, the owner waived this review on 2026-11-06.)
5. Store results with the configuration: commit, embedding model, LLM, chunking settings, prompt version and snapshot date.
6. Compare with the last accepted run and report the differences.

## 4. Acceptance thresholds

Initial targets for version 1. They will be revised after the first baseline run.

| Metric | Threshold |
|---|---|
| Routing accuracy | ≥ 90% |
| Analytical accuracy | ≥ 90% |
| Recall@5 | ≥ 80% |
| Duplicate rate@5 | ≤ 5% |
| Stale rate@5 | ≤ 2% |
| Citation accuracy | ≥ 95% |
| Groundedness | ≥ 90% |
| Correct refusal rate | 100% |

## 5. Data-quality experiment

This experiment supports goal G4: showing in numbers what data engineering contributes to RAG quality. The same evaluation set is run against indexes built from progressively better data:

| Run | Index built from | Expected effect |
|---|---|---|
| A | Raw Bronze text, no deduplication, no metadata | Baseline |
| B | A + deduplication | Lower duplicate rate, higher recall |
| C | B + closed-posting handling | Lower stale rate |
| D | C + metadata (skills, seniority, remote status, dates) and filtering | Better filtered and company questions |
| E | D + hybrid retrieval | Better recall on exact skill names |

The results table and a short write-up are published in the documentation as a release criterion for version 1.

## 6. Model comparison

The same method compares at least two LLMs and two embedding models (FR-EVL-04). Each comparison reports quality metrics alongside latency and cost, and the chosen models are recorded in a decision record.

The planned comparison covers the providers shortlisted in [ADR-0006](../decisions/0006-llm-provider-strategy.md):

| Role | Candidates |
|---|---|
| Answer generation and routing | A local model; a Gemini model through Google AI Studio; an open-weight model through Groq Cloud |
| Embeddings | A local embedding model; a Gemini embedding model |

Free-tier rate limits apply, so evaluation runs are throttled and resumable (NFR-27). Changing the embedding model requires re-embedding the whole index, so the embedding comparison runs once, early in Phase 7, before generation models are compared.
