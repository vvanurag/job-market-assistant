# Data Sources

| | |
|---|---|
| **Version** | 0.2 (draft) |
| **Status** | In review; no source approved yet |
| **Owner** | Anurag V V |
| **Last updated** | 2026-11-05 |

This register lists candidate sources and the checks each must pass before use. A source moves to **Approved** only after its terms of use have been read and recorded below (NFR-14).

**Target geography:** Hyderabad and Bengaluru, India. Whether remote roles open to India-based candidates are included is open question Q6.

---

## 1. Selection criteria

A source is suitable when it:

1. **Allows automated access** through an official API or published feed, under terms that permit this project's use.
2. **Covers the target roles** (data engineering, analytics engineering, ML and AI engineering) in the target geographies (open question Q1).
3. **Provides full posting text**, not only titles. RAG depends on the description.
4. **Provides a stable identifier** per posting, so changes and closures can be tracked.
5. **Provides a posting date**, so trends can be measured.

Sources that require scraping pages in breach of their terms are excluded by default. This rules out the largest Indian job sites, such as Naukri, LinkedIn, Foundit and Indeed, which offer no public API for this use. The resulting coverage gap is risk R7 in the [Product Requirements](product_requirements.md#9-dependencies-and-risks). Any exception must be accepted by the owner and recorded in a decision record (NFR-14).

## 2. Candidate sources

| Source | Access | Hyderabad / Bengaluru coverage | Strengths | Limitations | Priority | Status |
|---|---|---|---|---|---|---|
| **Adzuna API** | Official API; free developer key | India endpoint with location filtering | Structured fields, salary data where available, broad volume | Descriptions may be truncated; attribution likely required | Primary | To review |
| **Greenhouse job board API** | Public, per-company endpoint | Companies with offices in either city that use Greenhouse | Full descriptions; stable IDs; direct from the employer | Needs a curated company list (section 3) | Primary | To review |
| **Lever postings API** | Public, per-company endpoint | Companies with offices in either city that use Lever | Full descriptions; stable IDs; direct from the employer | Needs a curated company list (section 3) | Primary | To review |
| **Hacker News "Who is Hiring"** via the HN Algolia API | Public API | Low: few India-based roles | Real posts; good test of free-text extraction | Unstructured; monthly | Optional | To review |
| **Remotive API** | Public API | Remote roles only | Full descriptions | Relevant only if Q6 includes remote roles | Optional, depends on Q6 | To review |
| ~~Arbeitnow API~~ | Public API | Europe only | — | Outside target geography | Dropped | Rejected |
Using **employer career-page APIs** (Greenhouse and Lever) alongside an **aggregator** (Adzuna) deliberately creates overlap. The same role will often appear in both, which gives cross-source deduplication (FR-TRN-03) real work to do.

## 3. Target company list

Greenhouse and Lever are queried per company, so the project keeps a versioned list of target employers with engineering offices in Hyderabad or Bengaluru. Each entry records the company name, careers platform, board identifier, cities and the date it was verified. The list starts with 20 to 40 companies and is reviewed monthly.

## 4. Location and salary conventions

| Topic | Convention |
|---|---|
| **City aliases** | "Bangalore", "Bengaluru" and "Bengaluru Urban" map to **Bengaluru**. "Hyderabad", "Secunderabad", "Cyberabad" and area names such as "HITEC City" and "Gachibowli" map to **Hyderabad**. The alias list is maintained as a seed table. |
| **Multi-city postings** | A posting listing several cities is linked to each target city it names, and counted once per city in city-level figures. |
| **Salary units** | Indian postings often quote **LPA** (lakhs per annum; 1 lakh = 100,000 INR). Salaries are stored as INR per year and may be displayed in LPA. |
| **Salary ranges** | "12–18 LPA" is stored as minimum 1,200,000 and maximum 1,800,000 INR per year. Unparseable salaries are kept as raw text and excluded from statistics. |

## 5. Review checklist

Complete one per source before moving it to **Approved**.

| Check | Record |
|---|---|
| Terms of use URL and date read | |
| Automated access permitted for this purpose | Yes / No |
| Attribution requirements | |
| Rate limits and request quotas | |
| Authentication method and where the secret is stored | |
| Can data be stored and indexed, and for how long | |
| Fields available (title, company, location, description, date, salary, ID, URL) | |
| Personal data present in postings | |
| Reviewer and date | |

## 6. Target field mapping

Every source maps to this common shape in the Silver layer. Fields a source can't provide are left empty, never guessed.

| Field | Type | Required | Notes |
|---|---|---|---|
| `source_id` | string | Yes | |
| `source_posting_id` | string | Yes | Identifier from the source |
| `title` | string | Yes | |
| `company_name` | string | Yes | Normalised later into `company_id` |
| `location_raw` | string | No | As given by the source |
| `cities` | list of strings | Yes | Canonical target cities (`Hyderabad`, `Bengaluru`) resolved from `location_raw` and the description; see section 4 |
| `remote_status` | enum | No | `remote`, `hybrid`, `onsite`, `unknown` |
| `description_text` | string | Yes | HTML removed |
| `posted_at` | timestamp | Yes | Source date; fall back to first-seen date and record that it was a fallback |
| `salary_min`, `salary_max` | number | No | |
| `salary_currency`, `salary_period` | string | No | ISO 4217 currency code (usually `INR`); `year`, `month`, `day` or `hour`. LPA is converted to INR per year |
| `url` | string | Yes | Link shown in citations |
| `first_seen_at`, `last_seen_at` | timestamp | Yes | Set by the pipeline, not the source |
