# Glossary

| Term | Meaning in this project |
|---|---|
| **ADR** | Architecture decision record: a short document explaining one technical decision. See [Decisions](decisions/index.md). |
| **Bronze, Silver, Gold** | The three Medallion layers: raw data as received; cleaned and deduplicated data; business-ready facts and dimensions. |
| **Chunk** | A section of posting text that is embedded and retrieved as one unit. |
| **Citation** | A reference to a specific posting (title, company, link) that supports part of an answer. |
| **Cross-source deduplication** | Recognising that postings from different sources are the same job and linking them to one `posting_id`. |
| **dbt** | Data build tool: runs SQL transformations in the warehouse with tests, dependencies and documentation. |
| **Embedding** | A list of numbers representing the meaning of a piece of text, used for similarity search. |
| **ELT / ETL** | Extract, load, transform (transform inside the warehouse) / extract, transform, load (transform before loading). |
| **Evaluation set** | The versioned list of questions and expected results used to measure answer quality. |
| **Grain** | What one row of a table represents. |
| **Groundedness** | Whether every statement in an answer is supported by the retrieved evidence. |
| **Hybrid retrieval** | Combining keyword search and vector similarity search. |
| **Idempotent** | Producing the same result whether an operation runs once or several times. |
| **Lambda / Kappa** | Streaming architectures: separate batch and speed layers (Lambda) or a single stream-processing path (Kappa). |
| **MoSCoW** | Prioritisation: Must, Should, Could, Won't (this release). |
| **MRR** | Mean reciprocal rank: the average of 1 ÷ the rank of the first relevant result. |
| **Posting** | One job advertisement after deduplication; it may have records in several sources. |
| **RAG** | Retrieval-augmented generation: retrieving relevant text and giving it to an LLM to answer from. |
| **Recall@k** | The share of relevant items that appear in the top *k* results. |
| **Router** | The component that decides whether a question is answered by SQL, retrieval, both or neither. |
| **SCD Type 2** | Slowly changing dimension Type 2: keeping history by closing the old row and adding a new one when attributes change. |
| **SLI / SLO / SLA** | Service level indicator (what is measured), objective (the target), agreement (a commitment with consequences). |
