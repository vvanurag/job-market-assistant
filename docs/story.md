# The Story of the Project

How the Job Market Assistant went from an idea to a working, measured system: the decisions, the dead ends and the bugs, in the order they happened.

For *how the system works*, read the [User's Guide](guide.md). This page is about *how it came to be*.

## Contents

1. [A learning path looking for a purpose](#chapter-1-a-learning-path-looking-for-a-purpose)
2. [Requirements before code](#chapter-2-requirements-before-code)
3. [Foundations, and a fight with Snowflake](#chapter-3-foundations-and-a-fight-with-snowflake)
4. [Getting the data in](#chapter-4-getting-the-data-in)
5. [Turning raw postings into tables](#chapter-5-turning-raw-postings-into-tables)
6. [Two warehouses, one answer](#chapter-6-two-warehouses-one-answer)
7. [Finishing the model](#chapter-7-finishing-the-model)
8. [Search by meaning](#chapter-8-search-by-meaning)
9. [Teaching it to answer](#chapter-9-teaching-it-to-answer)
10. [Running every day](#chapter-10-running-every-day)
11. [New postings within minutes](#chapter-11-new-postings-within-minutes)
12. [Measuring what we built](#chapter-12-measuring-what-we-built)
13. [Shipping it](#chapter-13-shipping-it)
14. [Where it stands](#chapter-14-where-it-stands)

---

## Chapter 1: A learning path looking for a purpose

The project began in a different repository, a personal **Data Engineering** learning path with a list of topics to study one by one. The first topic was *SQL and data modeling*, and it produced a written tutorial.

Partway through, Anurag had a thought: following tutorials one at a time is hard to stay motivated for. If everything learned **built towards one real system**, a retrieval-augmented generation (RAG) assistant, then every topic would have a reason to exist and a visible result.

The test was whether one project could genuinely need all the topics: SQL, data modeling, ELT, Medallion layers, orchestration, streaming, warehouses, embeddings, APIs, CI/CD, evaluation. A **job-market assistant** passed: it needs data collected daily, cleaned, deduplicated and historised, and it naturally asks both "how many?" questions (SQL) and "what does this mean?" questions (RAG).

Two decisions came straight away:

- It would live in **its own repository**, `job-market-assistant`, separate from the learning notes.
- It would be **documented professionally**, as if a team would inherit it.

## Chapter 2: Requirements before code

Before any code, the project got a full set of requirements:

- a **Product Requirements Document**: goals, users, user stories with acceptance criteria, risks;
- **Functional** and **Non-Functional Requirements**, each with an ID (FR-…, NFR-…) that the code and docs still reference;
- a **Data Sources** register, an **Evaluation Plan**, a **Roadmap** of ten phases, and **Architecture Decision Records** (ADRs).

The requirements ended with open questions, and the answers shaped everything after:

| Question | Answer |
|---|---|
| Q1 Which geography? | Hyderabad and Bengaluru, India |
| Q2 Which language models? | Explore three: local models (Ollama), Google AI Studio (Gemini) and Groq Cloud |
| Q3 What happens after the Snowflake trial? | Decide later, **but no decision may be harmful later**. This one sentence produced the "portable warehouse" rule (ADR-0005) |
| Q4 Where does the API run? | On the owner's laptop, for demos |
| Q5 Can a resume be sent to an online model? | Answered at the end: the owner didn't require privacy, and the project chose to extract skills locally anyway |
| Q6 Include remote roles? | Answered at the end: yes, remote roles open to candidates in India |

An early detour was useful too: comparing sources such as job-board APIs, company career-page APIs and community threads. It made one hard fact visible: **the biggest Indian job sites offer no public API**. That became risk R7, and the reason the project combines more than one kind of source.

## Chapter 3: Foundations, and a fight with Snowflake

Phase 0 built the workbench:

- a Python package with a command-line tool (`jobmarket`) and settings that keep secrets out of the code;
- lint, format and test checks on every commit (pre-commit) and on every push (GitHub Actions);
- a documentation site on GitHub Pages, built with MkDocs;
- a `doctor` command that checks every dependency: Python, Docker, DuckDB, Snowflake, Ollama and the API keys.

Snowflake took the longest, and each problem taught something:

1. **"User does not exist."** The setup script granted roles to `ANURAGREGEDIT`, but the user object was named in lowercase. Fixed by using `current_user()`, so nobody types their own name.
2. **"Invalid public key."** The key pasted into Snowsight had been broken by copy-paste line wrapping. Fixed by generating the SQL with the key on one line.
3. **"JWT token is invalid."** Key-pair login needs the user's **login name** (here an email address), not the user name. That one line is now in the setup guide.
4. **Nothing changed after editing `.env`.** The file simply hadn't been saved.

GitHub added two more: pushing over SSH was refused (switched to HTTPS), and pushing a workflow file needed an extra token permission (`workflow` scope).

**Lesson:** most "infrastructure" problems are naming and identity problems. Read the error literally.

## Chapter 4: Getting the data in

The Bronze layer was designed around one promise: **raw data is kept exactly as received, and loading it twice changes nothing**.

- Every record is a JSON file on disk *and* a row in the warehouse (NFR-26).
- Each row stores a SHA-256 fingerprint of its content. Re-loading the same batch inserts nothing, and a changed record is reported as a conflict, never silently overwritten.

Two sources went in:

- **A one-off initial backfill of 2,000 postings**, loaded as its own Bronze source, to start with a realistic volume.
- **The Greenhouse Job Board API**: a public, documented API that many companies use for their career pages. A collector was written for **30 company boards** with Hyderabad or Bengaluru offices, after a terms-of-use review. It kept **648 jobs** in target cities.

By the end of Phase 1 the warehouse held 2,648 raw postings, and the project's first public push deliberately left out anything local-only.

## Chapter 5: Turning raw postings into tables

Phase 2 used **dbt** to build the Silver and Gold layers, and most of the interesting problems were about messy text:

| Problem | Solution |
|---|---|
| Two sources, two formats | One staging model per source, mapped to one shared set of columns |
| "Bangalore", "Bengaluru", "Whitefield", "Karnataka" | A city alias table, preferring city names over areas over states |
| Recruiters' emails and phone numbers in descriptions | Removed before Silver (NFR-15): 137 emails and 3 phone numbers |
| The same job posted again and again | A content fingerprint: 184 reposts in 73 groups, each counted once |
| Greenhouse sends HTML | An `html_to_text` macro, applied twice, because some entities were double-encoded |
| Skills hidden in free text | A dictionary of 128 skills with whole-word matching: "SQL" doesn't match "MySQL" |

The skill dictionary had a memorable bug. **"Excel" matched the verb**: "candidates who excel at communication". The pattern was narrowed to phrases like "MS Excel" and "Excel formulas".

Gold became a **Kimball star schema**: a fact table of unique jobs, a factless fact of job–skill pairs, and dimensions for company, skill, location and date. The first insights came out at once: Python (1,458 jobs), SQL (1,157) and AWS (972) led; generative-AI skills appeared in 52% of jobs; Infosys, Accenture, Deloitte, TCS and Amgen posted the most.

## Chapter 6: Two warehouses, one answer

The Q3 rule ("no decision may be harmful later") was tested for real: the whole pipeline was run on **Snowflake as well as DuckDB**.

Every place where the two engines' SQL differs (JSON access, regular expressions, date functions) had been isolated in small dbt macros with one version per engine. A `compare` command then read every Silver and Gold table from both warehouses and compared them row by row.

The result: **all 2,648 raw fingerprints and every table identical**. Snowflake could now be kept, dropped or replaced at any time with a single command to prove nothing changed.

## Chapter 7: Finishing the model

The rest of Phase 2 added the features that make the data trustworthy over time.

**Seniority and work mode.** Most postings didn't state a level, so it was inferred from evidence in order: the title ("Senior", "Lead II"), then the source's own level, then the years of experience asked for. Seniority became known for 93% of jobs, up from 34%. As a cross-check, title and years agreed within one level 96% of the time. A dbt **unit test** pinned the tricky cases: "Associate Director" is a manager, not a junior; "75 years of experience" describes the company, not the role.

**Remote roles (Q6).** Adding "Remote (India)" as a location immediately exposed a bug: the alias "remote - india" matched **"Remote - Indiana, USA"**. Matching was switched to whole words, in both the collector and Silver.

**A second day of data, by accident.** Re-collecting after midnight UTC created batch `2026-11-06`: exactly what history tracking needed.

**History (SCD Type 2).** Rather than dbt snapshots, history was *derived from every Bronze delivery*: each posting is checked against each run of its source, and missing it for two runs in a row marks it closed. This made history rebuildable from scratch and identical on both warehouses.

**The same job on two sources.** Matching used company, city, title, and the first and last 1,000 *letters* of the description (ignoring HTML and punctuation). Then a trap appeared: **Databricks used identical text for a "Senior" and a "Staff" role**. Including the title in the rule kept them apart. All 10 matches were checked by hand and correct. One real match was missed because the company appeared as "InMobi" and "InMobi Advertising".

## Chapter 8: Search by meaning

Phase 5 built the retrieval index, the "R" in RAG.

- **Chunking** split descriptions at their section headings, merged tiny sections, and capped chunks at 1,200 characters with overlap (ADR-0007). A test caught a bug: an "Equal Opportunity Employer" heading wasn't recognised, so the boilerplate merged into "Requirements", and **the real requirements were dropped along with it**.
- **pgvector or Qdrant?** The ADR demanded a measured spike. Both were loaded with the same 12,444 vectors: they returned the same results (96–100% overlap), both were far inside the latency target, and pgvector could do **keyword plus vector search in a single SQL query**. pgvector won (ADR-0004).
- **Incremental by design.** A rebuild with nothing changed embeds nothing and finishes in under a second. Changing the chunker's version re-embeds everything.

## Chapter 9: Teaching it to answer

Phase 6 built the API and its "brain".

The most important decision: **the language model never writes SQL** (ADR-0008). It picks one of five fixed metrics and fills in typed parameters, which code validates and binds. A hostile question can at worst choose the wrong metric.

Testing it with real questions found three problems:

1. **"What do employers mean by strong Kafka experience?" was refused.** The router read "what employers mean" as interpretation. Worked examples in the prompt fixed it.
2. **A correct plan was thrown away.** The model sent `null` for optional fields, strict validation rejected the whole plan, and the system fell back to plain search. Nulls now mean "use the default".
3. **A posting appeared twice as "two listings",** because each chunk was shown as its own source. Sources are now grouped per posting.

Then came the most serious discovery of the project. A test that expected the read-only serving role to be *blocked* from Silver **succeeded**. Newer Snowflake accounts activate **all of a user's roles, including ACCOUNTADMIN, in every session** as "secondary roles". The careful role design had been meaningless. Every Python connection now turns secondary roles off, and the isolation was verified.

Resume matching (`/match`) took Q5's answer seriously: skills are found **locally** with the same dictionary, and nothing from the resume is stored, logged or sent to a model.

## Chapter 10: Running every day

Phase 3 put the pipeline on a schedule with **Apache Airflow 3**. Instead of one opaque `dbt build`, the DAG reads dbt's manifest and creates **one task per model**, so a failure retries just that model and a failed test stops the index from being refreshed (ADR-0010).

The first full run took **74 seconds** end to end and every task passed. It also revealed that each dbt task overwrote dbt's results file, so the run record only described the last model. Failed tasks are now read from the alerts their failure callbacks raise.

## Chapter 11: New postings within minutes

Phase 4 added **Apache Kafka**. The choice between a Lambda and a Kappa architecture was easy once written down: sources are polled, closures can only be seen by comparing full snapshots, and all the cleaning is batch SQL. So the batch stays the source of truth, and a **speed layer** indexes new postings immediately (ADR-0009).

The first end-to-end test crashed: the consumer assumed the search index already existed, which is never true on a fresh machine. After the fix, five real postings replayed through Kafka were **searchable about 15 seconds after detection**, against a target of 60 minutes.

## Chapter 12: Measuring what we built

Phase 7 asked the question that matters: **is it actually good?**

A versioned set of **54 questions** was written, with reference SQL for numbers and relevance rules for search. Running it surfaced a new kind of problem, the outside world:

- **Google had retired `gemini-2.5-flash` for new keys,** and the newer Flash models were overloaded, so the Gemini option moved to `gemini-3.5-flash-lite`.
- **Groq rejected its own invalid JSON** with an error that crashed the run. Groq calls now retry without strict JSON mode, and one failing question can no longer stop an evaluation.
- **The free tier's 8,000 tokens a minute** turned throttling into fake latency, so runs are now paced and the pauses aren't measured.

The first full run (v1) was already strong. Its misses were studied one by one, and **prompt v2** fixed them: analytical accuracy rose from 88% to 94%, and wrong refusals fell from 5% to 0%.

Then v2 seemed to score *worse* on groundedness. The cause was a **measurement bug**: the answering model saw each posting's city and dates, but the judge didn't, so true statements looked invented. Once the judge saw the same thing, every run was re-scored the same way, and v2's groundedness was 98%.

Two experiments told the bigger story:

- **The data-quality experiment** showed what data engineering contributes: metadata filters raised search recall from 64% to 94%, and deduplication removed the duplicate jobs that filled about 10% of top results.
- **The model comparison** showed Groq's model was the best balance of quality and speed, and the small local models (Llama 3, Gemma 2) couldn't route questions reliably (ADR-0011).

## Chapter 13: Shipping it

Phase 8 made the system easy to start and hard to break:

- **`docker compose up -d`** starts the vector database, the API, Airflow and Kafka.
- **CI** checks lint, tests and coverage (82%), builds and tests the dbt project on DuckDB using a small *synthetic* dataset, builds the container images, and scans the **entire git history for secrets**.

The secret scan promptly failed. It had found an **md5 hash in a dbt unit test** that looked like an API key. It was reviewed and recorded as a false positive, the right way: by fingerprint, not by turning the scanner off.

One more container lesson: installed as a package, the code could no longer find the repository's seed files by its own location, so the repository root became configurable (`JOBMARKET_HOME`).

## Chapter 14: Where it stands

By the end, every phase from 0 to 8 was built, tested and documented:

| | |
|---|---|
| Jobs modeled | 1,872 unique jobs from 3,324 raw postings |
| dbt checks | 147, passing on DuckDB and Snowflake |
| Decision records | 11 |
| Evaluation | Every threshold met by the accepted configuration |
| Pipeline | 74 seconds end to end; new postings searchable in about 15 seconds |

What remains is **time**: version 1's release needs the daily pipeline to meet its targets for 14 consecutive days. Phase 9 (Databricks, Iceberg, fine-tuning) is optional.

And the original goal was met: every topic on the learning path now has a working, measured place in one system. The [User's Guide](guide.md) explains each of them.
