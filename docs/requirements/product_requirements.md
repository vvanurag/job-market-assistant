# Product Requirements

| | |
|---|---|
| **Document** | Product Requirements Document (PRD) |
| **Version** | 0.3 (draft) |
| **Status** | In review |
| **Owner** | Anurag V V |
| **Last updated** | 2026-11-05 |

### Revision history

| Version | Date | Changes |
|---|---|---|
| 0.1 | 2026-11-05 | First draft |
| 0.3 | 2026-11-06 | Answered Q5 (option C) and Q6 (remote roles in India included). |
| 0.2 | 2026-11-05 | Answered Q1–Q4: geography set to Hyderabad and Bengaluru, LLM options shortlisted, warehouse kept portable, local-only demos. Added Q6, R7, R8 and Bengaluru/Hyderabad example questions. |

---

## 1. Summary

The Job Market Assistant collects public job postings for data engineering and AI roles in **Hyderabad and Bengaluru, India**, models them in a data warehouse, and answers natural-language questions about the market. It routes each question to the right engine: SQL for counts, trends and comparisons, and semantic retrieval for questions about the content of postings. Every answer cites the postings it is based on.

## 2. Problem statement

People preparing for data and AI roles need to know which skills employers ask for, how demand is changing, and which open roles match their profile. Today this means reading hundreds of postings by hand across several sites. The information is:

- **Scattered** across job boards, company career pages and community threads.
- **Duplicated**, because the same role is reposted on several boards.
- **Unstructured**, because skills, seniority and salary are buried in free text.
- **Short-lived**, because postings close and change without notice.

Keyword search on a job board can't answer questions such as "Which skills are growing?" or "What does this company mean by this requirement?", and a generic chatbot has no current, verifiable posting data.

## 3. Goals

| ID | Goal | Measured by |
|---|---|---|
| G1 | Answer analytical questions about the job market accurately | Analytical questions in the evaluation set; see [Evaluation Plan](evaluation_plan.md) |
| G2 | Answer content questions with grounded, cited evidence | Retrieval recall and citation accuracy |
| G3 | Keep the data current | Freshness targets in [NFR-01 and NFR-02](non_functional_requirements.md) |
| G4 | Show, with numbers, how data engineering quality affects RAG quality | The data-quality experiment in the [Evaluation Plan](evaluation_plan.md#5-data-quality-experiment) |
| G5 | Run at personal-project cost | Monthly budget in [NFR-08](non_functional_requirements.md) |

## 4. Non-goals

The following are out of scope for version 1:

- Applying to jobs, or contacting recruiters, on the user's behalf.
- Collecting data from sites whose terms prohibit automated access.
- Multiple user accounts, sign-up or billing.
- A mobile application.
- Hosting the API on a cloud service. Version 1 runs on the owner's machine.
- Locations other than Hyderabad, Bengaluru and remote roles open to candidates in India (Q6).
- Predicting salaries or hiring outcomes with machine learning models.
- Coverage of roles outside data engineering, analytics engineering, machine learning and AI engineering.

## 5. Users

| Persona | Description | Primary needs |
|---|---|---|
| **Job seeker** (primary) | An engineer moving into data engineering or AI roles. Uses the assistant to decide what to learn and where to apply. | Skill trends, role matching, gap analysis against a resume |
| **Technical reviewer** (secondary) | An interviewer or peer reviewing the project as a portfolio piece | Clear architecture, reproducible setup, evidence of quality |
| **Operator** (internal) | The person running the platform; in version 1, the same person as the job seeker | Pipeline health, freshness, cost and failure alerts |

## 6. User stories

Priority uses MoSCoW: **M**ust, **S**hould, **C**ould, **W**on't (this release).

### 6.1 Market analysis

| ID | Story | Priority | Acceptance criteria |
|---|---|---|---|
| US-01 | As a job seeker, I want to see which skills appear most often in postings for a role, so that I can prioritise what to learn. | M | Returns a ranked list with counts and the date range covered. Counts match a direct SQL query on the Gold layer. |
| US-02 | As a job seeker, I want to see how demand for a skill changes over time, so that I can spot rising and falling technologies. | M | Returns weekly or monthly counts for a chosen period. Duplicate postings are counted once. |
| US-03 | As a job seeker, I want to compare Hyderabad and Bengaluru by role, work mode and seniority, so that I can target my search. | S | Supports filters on city, work mode (remote, hybrid, on-site) and seniority, alone or combined. City name variants (for example Bangalore and Bengaluru) are treated as one city. |
| US-04 | As a job seeker, I want salary ranges for a role where they are published, so that I can set expectations. | C | Reports figures in INR per year (also shown in LPA), and how many postings disclosed a salary. Currencies are not mixed in one figure. |

### 6.2 Search and understanding

| ID | Story | Priority | Acceptance criteria |
|---|---|---|---|
| US-05 | As a job seeker, I want to ask what employers mean by a requirement, so that I understand what is expected. | M | The answer summarises the relevant postings and cites at least three of them by title, company and link. |
| US-06 | As a job seeker, I want to search postings by meaning together with exact filters, so that I find relevant open roles quickly. | M | Supports a free-text query plus filters (posted within N days, remote, location, skills). Only open postings are returned unless I ask otherwise. |
| US-07 | As a job seeker, I want to ask what a specific company looks for, so that I can prepare for that company. | S | Answers use only that company's postings. If none exist, the assistant says so. |

### 6.3 Personal fit

| ID | Story | Priority | Acceptance criteria |
|---|---|---|---|
| US-08 | As a job seeker, I want to provide my resume and see the best-matching open roles, so that I apply where I fit. | S | Returns ranked postings, each with a short reason for the match. |
| US-09 | As a job seeker, I want to see the skills I am missing for a target role, so that I can plan my learning. | S | Lists skills that are frequent in the target postings and absent from my resume, with how often each appears. |

### 6.4 Freshness and history

| ID | Story | Priority | Acceptance criteria |
|---|---|---|---|
| US-10 | As a job seeker, I want to know whether a posting is still open and whether it changed, so that I don't waste effort on stale roles. | M | Shows first-seen and last-seen dates, current status and any changes to tracked fields. |
| US-11 | As a job seeker, I want new postings to be searchable soon after they appear, so that I can apply early. | S | Meets the streaming freshness target in NFR-02. |

### 6.5 Trust and operations

| ID | Story | Priority | Acceptance criteria |
|---|---|---|---|
| US-12 | As a job seeker, I want the assistant to say when it doesn't know, so that I can trust what it does say. | M | Questions outside the data return a clear "not enough information" answer and no invented postings. |
| US-13 | As an operator, I want to be alerted when a source fails or data goes stale, so that I can fix it before answers degrade. | M | An alert is raised within one scheduled run of a failure or freshness breach. |
| US-14 | As a technical reviewer, I want to set up and run the project from the README, so that I can verify it works. | S | A clean machine reaches a working local environment by following the documented steps. |

## 7. Example questions

These questions define what "useful" means. They seed the [evaluation set](evaluation_plan.md).

| Question | Answered by |
|---|---|
| Which 10 skills grew fastest in data engineering postings over the last 90 days? | Analytical (SQL) |
| How many analytics engineering roles were posted each week this quarter in Bengaluru? | Analytical (SQL) |
| Is demand for Databricks higher in Hyderabad or Bengaluru? | Analytical (SQL) |
| What salary range do senior data engineer postings in Hyderabad publish? | Analytical (SQL) |
| What do employers mean by "strong Kafka experience"? Give three examples. | Semantic (RAG) |
| Hybrid roles in Hyderabad posted this week that mention dbt and Snowflake. | Semantic with metadata filters |
| What does Company X look for in data engineers? | Semantic, filtered by company |
| Given my resume, which open roles fit best and what am I missing? | Semantic and analytical combined |
| Is this posting still open, and has the salary changed? | Analytical, from posting history |
| What is the average salary for prompt engineers on Mars? | Should decline: no supporting data |

## 8. Assumptions

- At least two public sources with suitable terms of use cover Hyderabad and Bengaluru. See [Data Sources](data_sources.md).
- A Snowflake account is available during development. How it continues after the trial is decided later; the design keeps that decision reversible ([ADR-0005](../decisions/0005-portable-warehouse-layer.md)).
- Language models come from three interchangeable options: local models, the Google AI Studio (Gemini) API and the Groq Cloud API. The final choice is made from evaluation results ([ADR-0006](../decisions/0006-llm-provider-strategy.md)).
- Free API tiers are sufficient for development and evaluation, within their rate limits.

## 9. Dependencies and risks

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | A source changes its API or terms | Medium | High | Isolate each source behind its own extractor; keep at least two sources; review terms each quarter |
| R2 | The same role appears on several sources | High | Medium | Cross-source deduplication in Silver (FR-TRN-03) |
| R3 | Skill extraction from free text is inaccurate | Medium | High | Maintain a skill dictionary, measure extraction precision, fall back to LLM extraction only where it measurably helps |
| R4 | LLM or warehouse costs exceed budget | Medium | Medium | Cost tracking (NFR-08), caching, re-embedding only changed postings |
| R5 | The assistant invents postings or facts | Medium | High | Citation requirement, groundedness checks in evaluation, refusal behaviour (US-12) |
| R6 | Personal data in resumes leaks | Low | High | Privacy requirements in NFR-10 |
| R7 | Public sources under-represent the Indian market. The largest Indian job sites (such as Naukri, LinkedIn and Foundit) offer no public API. | High | Medium | State coverage limits in answers; combine an aggregator with employer career-page APIs for companies with Hyderabad or Bengaluru offices; report postings per source |
| R8 | Free-tier API limits or terms change, or free-tier data is used by the provider to improve its products | Medium | Medium | Provider-agnostic interface (NFR-25); local models as fallback; never send raw personal data to free tiers (NFR-10) |

## 10. Open questions

| ID | Question | Status | Answer |
|---|---|---|---|
| Q1 | Which geographies matter most? | Answered | Hyderabad and Bengaluru, India |
| Q2 | Which LLM provider and monthly budget? | Partly answered | Shortlist: local models, Google AI Studio (Gemini), Groq Cloud. Final choice from Phase 7 evaluation. Budget: free tiers during development; a paid budget is set only if evaluation justifies it. See [ADR-0006](../decisions/0006-llm-provider-strategy.md). |
| Q3 | How will Snowflake continue after the trial? | Deferred | Decided later. The design keeps any choice cheap to make ([ADR-0005](../decisions/0005-portable-warehouse-layer.md)); verified on 2026-11-05: identical results on DuckDB and Snowflake ([Running on Snowflake](../pipeline/snowflake.md)). |
| Q4 | Where is the API hosted for demos? | Answered | On the owner's machine |
| Q5 | Should the resume stay local, or may it be sent to an LLM provider? | Answered (2026-11-06) | The owner doesn't require resume privacy and left the choice open. **Option C** is used: skills are extracted locally with the skill dictionary, and only the skill list goes to a model. The dictionary already extracts skills reliably without a model, so sending the full text would add cost and risk for no gain. NFR-10 is kept. |
| Q6 | Should remote roles open to candidates in India be included alongside Hyderabad and Bengaluru roles? | Answered (2026-11-06) | Yes. They form a third location, **Remote (India)**. A posting naming a target city stays in that city. |

## 11. Release criteria for version 1

Version 1 is complete when:

1. All **Must** user stories meet their acceptance criteria.
2. All non-functional requirements marked **Must** meet their targets for 14 consecutive days.
3. The evaluation set meets the thresholds in the [Evaluation Plan](evaluation_plan.md#4-acceptance-thresholds).
4. The data-quality experiment has been run and its results are published in the documentation.
