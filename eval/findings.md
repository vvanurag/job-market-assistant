## Findings

**What the data engineering contributes.** In the data-quality experiment, deduplication removes the duplicate jobs that otherwise fill 9.6% of the top five results. **Metadata filters are the largest single gain**: recall@5 rises from 64% to 94% overall, and from 49% to 93% on questions with filters (city, work mode, seniority, company, dates). Seniority, work mode, skills and status exist only because the Silver layer derives them. Hybrid keyword and vector search adds a little more. Closed-posting handling can't show an effect yet, because no posting has closed in two days of data; the stale rate is 0% in every run.

**Prompt v2.** The first run's misses were diagnosed and fixed, and the effect was measured. Analytical accuracy rose from 88% to 94%: generic phrases like "data and AI jobs" no longer become title filters, and a skill given to `count_jobs` is applied. False refusals fell from 5% to 0%: sources now show their posted date, so "posted this week" questions are answerable.

**A measurement bug, found and fixed.** v2 at first scored *lower* on groundedness (90%). The answering model saw each posting's metadata header (city, work mode, dates), but the judge didn't, so correct statements looked unsupported. The judge now receives exactly what the answering model saw, and every run was re-judged the same way (`jobmarket eval rejudge`).

**Language models.** Groq's `gpt-oss-120b` is the default: high quality at the lowest latency (p95 1.9 s, against a target of 8 s). Gemini 3.5 Flash-Lite scores slightly higher on analytical accuracy and groundedness, but is 3.4× slower at p95, and the full Flash models were often overloaded on the free tier. The local 8–9B models (Gemma 2, Llama 3) can't route reliably: 57–78% routing accuracy, often producing invalid plans. They suit offline use only. See [ADR-0011](../decisions/0011-model-selection.md).

**Embedding models.** `mxbai-embed-large` is marginally better than `nomic-embed-text` (95.6% against 94.8% recall@5: one question), but takes 2.3× longer to index, stores vectors a third bigger, and embeds queries 1.5× slower. `nomic-embed-text` is kept.

**Caveats.** The evaluation set was written by the developer of the system, and relevance is defined by rules over the same metadata the filters use. That rewards correct filtering, which is the intended behaviour, but scores would be lower on independently written questions. The LLM judge (Gemini) also judged its own answers in the Gemini run. A person's review of a 20% sample (`eval/review/v2_groq_human_review.md`) is still pending. Latencies are from the paced runs. The v2 runs ran while other indexes were being built, so their latency is slightly pessimistic.

**The accepted run's two misses.** EV-004 ("demand for Databricks…") was read as the *company* Databricks rather than the skill; the word is both. EV-028 added a count the user didn't ask for, which is harmless but not the expected route.
