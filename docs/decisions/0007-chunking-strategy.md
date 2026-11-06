# ADR-0007: Chunking strategy

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-11-06 |
| **Deciders** | Anurag V V |

## Context

Job descriptions average about 5,000 characters, and are written in sections (about the company, responsibilities, requirements, benefits) followed by legal boilerplate. Questions usually target one section: "what does this company mean by strong Kafka experience?" is answered by a requirements section, not the benefits. FR-IDX-01 requires a documented strategy covering size, overlap and section awareness.

## Options considered

1. **Whole posting as one chunk.** Simple, but one vector has to represent every topic in the posting, and long postings exceed what the LLM should read per citation.
2. **Fixed-size windows** (for example 1,000 characters, with overlap). Ignores structure: a window can mix the end of the benefits with the start of the requirements.
3. **Section-aware chunks with a size cap.** Split at headings, merge tiny sections, and split long ones with overlap.

## Decision

**Option 3**, implemented in `src/jobmarket/index/chunking.py` (`CHUNKER_VERSION = "sections-v2"`):

| Parameter | Value | Why |
|---|---|---|
| Section split | At heading lines: short lines ending in ":" or containing words such as "Responsibilities", "Requirements", "What you'll…" | Keeps one topic per chunk |
| Boilerplate | Sections headed by equal-opportunity, privacy, accommodation or fraud notices are dropped | Identical across postings; only adds noise |
| Maximum size | 1,200 characters per chunk, including the header (about 300 tokens) | Big enough for a whole requirements list, small enough to cite precisely |
| Minimum size | Sections under 300 characters merge with the next | Avoids chunks that are just a heading and two bullets |
| Overlap | 200 characters when a long section is split | A requirement cut at the boundary appears whole in one of the two chunks |
| Header | Every chunk starts with "{title} at {company} ({city})" and its section name | A chunk read alone still says which job it belongs to; improves retrieval for company and role questions |

## Consequences

- 1,872 jobs give about 12,400 chunks (about 6.6 per job).
- Changing any parameter means changing `CHUNKER_VERSION`. The next index build sees the new version and re-embeds every job, and the version is recorded in `index_builds` (FR-IDX-07).
- Phase 7 measures retrieval quality with this strategy. Alternatives can be compared on the same evaluation set by building a second index.
