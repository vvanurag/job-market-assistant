# ADR-0009: Lambda architecture for the streaming path

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-11-06 |
| **Deciders** | Anurag V V |

## Context

New postings should be searchable within an hour (NFR-02, US-11), but the daily batch makes them searchable only the next morning. FR-STR-04 asks for a recorded choice between a Lambda architecture (a batch layer plus a speed layer) and a Kappa architecture (one streaming pipeline that is replayed to rebuild).

Facts that shape the choice:

- **Sources are polled.** The Greenhouse API returns a board's full list of jobs; it doesn't push changes. A "stream" is therefore a poller that compares snapshots.
- **Closures need full snapshots.** A posting closes when it is *missing* from consecutive runs (FR-TRN-09). An absence isn't an event a stream can carry; it needs the batch comparison.
- **The transformations are batch SQL in dbt**: deduplication, cross-source matching, history, skills and attributes, tested on two warehouses (NFR-24).

## Options considered

1. **Kappa.** All data flows through Kafka; Silver and Gold are built by stream processors, and rebuilt by replaying the topic. That means reimplementing the dbt models in a stream processor, losing the portable warehouse layer, and still needing snapshot comparison for closures.
2. **Lambda.** The daily batch stays the source of truth. A speed layer publishes newly detected postings to Kafka, and a consumer indexes them immediately with a *provisional* document; the next batch run replaces it with the warehouse version.

## Decision

**Lambda** (option 2), implemented in `src/jobmarket/streaming.py`:

| Concern | How it's handled |
|---|---|
| Detection (FR-STR-01) | `jobmarket stream produce` polls every board every 15 minutes. Jobs not already in Bronze become `posting.detected.v1` events on the topic `postings.detected`, keyed by `posting_key`, with an idempotent producer |
| Speed layer (FR-STR-02) | `jobmarket stream consume` writes each event to Bronze in the collector's exact format (batch `stream-<date>`, NFR-26), builds a provisional document and indexes it. The offset is committed only after success, so delivery is at-least-once and processing is idempotent |
| Same rules in both layers | The provisional document is built from the **same seed files** as the dbt models: city aliases, skill dictionary, seniority and work-mode rules, and the target-role pattern read from the dbt macro |
| Reconciliation (FR-STR-03) | `posting_key = md5(source_id | source_posting_id)` in both layers, so a streamed posting and its batch copy are one posting. Provisional documents carry a `provisional:` hash, so the next index build always replaces them with the warehouse version; a posting the batch already indexed is never overwritten by the stream |
| History | Stream batches hold only new postings, so `slv_posting_history` doesn't count them as runs. Counting them would make every other posting look missed |

## Consequences

- Some rules exist twice: the provisional document applies the seeds in Python, the warehouse in SQL. Sharing the seed files limits drift. Where they still differ (for example, years of experience are only parsed in SQL), the provisional document is less complete, and it is replaced within a day.
- Postings detected by the stream appear in search within minutes but in **analytics** only after the next batch: Gold stays the single, tested view.
- Measured on 2026-11-06 by replaying 5 real postings through Kafka: about 0.23 s of processing per event (Bronze write plus embedding plus index), and searchable about 15 s after detection. The target is 60 minutes (NFR-02).
