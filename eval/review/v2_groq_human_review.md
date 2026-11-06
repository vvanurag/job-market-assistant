# Human review: 20% sample of judged answers

> **Status:** waived by the owner on 2026-11-06. Kept so anyone can check the LLM judge.

Run `v2_groq_nomic` (groq:openai/gpt-oss-120b). Sample of 5 of 27 judged answers, drawn with seed 20261106.

For each answer, check every statement against the cited sources and fill in the two lines at the end.
Record agreement with the judge in docs/evaluation/results.md when done.

## EV-018: What does hands-on Databricks experience usually involve in these postings?

**Answer**

Across the postings, "hands‑on Databricks experience" consistently means:
• Developing and maintaining large‑scale ETL/ELT pipelines with PySpark or Spark SQL, often using Delta Lake and DataFrames.
• Optimizing queries and Spark jobs for performance, scalability and cost (partitioning, tuning, resource management).
• Integrating Databricks with cloud services (Azure – ADF, Synapse, ADLS; AWS – [2], Glue, Lambda; GCP) and using Databricks Workflows/Unity Catalog.
• Implementing CI/CD and DevOps practices (Git, Azure DevOps, Jenkins) for automated deployment.
• Applying data‑modeling concepts (dimensional, Medallion architecture) and managing lakehouse/warehouse solutions.
These elements appear in [1], [2], [3], [4], and [5].

**Judge:** groundedness 100%, citation accuracy 100%

<details><summary>Source [1]</summary>

```text
Senior Databricks Engineer — DataBeat.io Media (Hyderabad; unknown; open; posted 2026-06-30)
(Requirements) 8+ years of experience in Data Engineering, Big Data, and Analytics platforms. Minimum 5+ years of hands-on experience working with Databricks, Apache Spark, PySpark, and SQL. Strong expertise in designing and implementing enterprise-scale Data Lake, Lakehouse, and Data Warehouse solutions. Deep understanding of Spark internals, cluster management, performance tuning, partitioning strategies, and resource optimization. Extensive experience working with Delta Lake, schema evolution, ACID transactions, and large-scale distributed data processing. Hands-on experience integrating Databricks with Azure (ADF, Synapse) and/or AWS (S3, Glue, Lambda) services. Proven experience handling end-to-end project delivery and managing technical engagements with clients and stakeholders. Experience leading development teams and mentoring engineers in enterprise environments. Strong understanding of data modeling, dimensional modeling, Medallion Architecture, and modern data platform design principles. Expertise in implementing CI/CD pipelines, DevOps practices, and automated deployment strategies.
```

</details>

<details><summary>Source [2]</summary>

```text
Databricks Data Engineer — Infosys (Bengaluru; unknown; open; posted 2026-10-27)
(Overview) Strong hands-on experience with Databricks. Proficiency in PySpark or Spark SQL for distributed data processing. Strong SQL skills with experience in query optimization and performance tuning. Experience in designing and developing ETL/ELT pipelines. Hands-on experience with Delta Lake, DataFrames, and Spark architecture. Knowledge of data warehousing concepts, dimensional modeling, and data lake architectures. Experience working with cloud platforms such as Azure, AWS, or GCP. Familiarity with Git-based source code management and DevOps practices. Strong analytical, debugging, and problem-solving skills. Design, develop, and maintain scalable data pipelines using Databricks and Apache Spark. Build and optimize ETL/ELT workflows for processing large-scale structured and unstructured datasets. Develop data ingestion frameworks to integrate data from multiple sources, including databases, APIs, applications, and cloud storage. Implement and manage Lakehouse architecture using Databricks and Delta Lake. Optimize Spark jobs and Databricks workloads for performance, scalability, and cost efficiency.
```

</details>

<details><summary>Source [3]</summary>

```text
Senior Data Engineer - Databricks — Anblicks (Hyderabad; unknown; open; posted 2026-09-16)
(Required Skills & Experience) 6+ years of experience in Data Engineering, with focus on data warehousing, distributed processing, and cloud platforms. 4+ years of hands-on experience in Databricks: PySpark, Delta Lake Proficient in SQL, data modeling, and performance tuning for analytical workloads. Experience building scalable pipelines on Azure (ADF, Synapse, or Azure Functions). Understanding of data governance principles, RBAC, and metadata management.
```

</details>

<details><summary>Source [4]</summary>

```text
Databricks Engineer — Infosys (Bengaluru; unknown; open; posted 2026-11-04)
(Overview) 5-8 years of experience in Data Engineering and Big Data technologies. Strong hands-on experience with Databricks, PySpark, and Spark SQL. Experience with Delta Lake, Databricks Workflows, and Unity Catalog. Proficiency in Python and SQL. Experience with Azure/AWS/GCP cloud platforms. Knowledge of Azure Data Factory (ADF), Apache Airflow, or similar orchestration tools. Understanding of data warehousing concepts and ETL/ELT methodologies. Experience with Kafka/Event Hub for streaming data processing is preferred. Familiarity with Git, CI/CD pipelines, and DevOps practices. Strong problem-solving, analytical, and communication skills. Roles & Responsibilities Design, develop, and maintain data pipelines using Databricks. Build ETL/ELT workflows for large-scale data processing. Develop and optimize data transformation logic using PySpark and Spark SQL. Implement and manage Delta Lake for reliable and efficient data storage. Work with batch and real-time data ingestion frameworks. Monitor and optimize data pipelines for performance and scalability.
```

</details>

<details><summary>Source [5]</summary>

```text
Databricks Developer — Kumaran Systems (Hyderabad; unknown; open; posted 2026-10-23)
(Required Skills & Qualifications) Core Technologies 3–5+ years of experience with Databricks, Apache Spark, and Python (PySpark). Strong experience building scalable ETL/ELT pipelines. SQL Expertise Advanced knowledge of Spark SQL or Databricks SQL for data transformation and analysis. Cloud Platforms Hands-on experience with Azure Databricks, AWS, or Google Cloud Platform (GCP). Data Modeling Experience with Delta Lake and Medallion Architecture (Bronze/Silver/Gold layers). Strong understanding of data modeling and data warehouse concepts. Version Control & CI/CD Proficiency with Git and CI/CD tools such as Azure DevOps or Jenkins.
```

</details>

- Statements supported by the sources (yes / partly / no):
- Agree with the judge (yes / no):

## EV-019: What do job postings expect from candidates who know dbt?

**Answer**

Job postings expect candidates with dbt knowledge to have solid hands‑on experience (often 2+ years) and deep technical expertise. They should be familiar with core dbt concepts such as models, tests, sources, seeds, snapshots, macros and exposures, and be able to integrate dbt into CI/CD pipelines and automated data workflows. Candidates are expected to design, build, and own production‑grade data products or pipelines, often on modern cloud warehouses like Snowflake or BigQuery, and to apply strong SQL and data‑modeling skills. Senior roles also look for the ability to coach other engineers and contribute to architecture decisions.

**Judge:** groundedness 100%, citation accuracy 100%

<details><summary>Source [1]</summary>

```text
Lead Data Engineer — Aqilea (Bengaluru; unknown; open; posted 2026-09-24)
(Work Location : Bangalore(Hybrid)) Notice : Immediate Joiners Lead Data Engineer - Inventory Flow Assistant (Google Cloud / BigQuery / dbt) About The Role: We are looking for a highly experienced, hands-on Lead Data Engineer to join the Emerging Technology team and help build the next generation of AI-powered supply chain products. You will be a key technical contributor in the development of the Inventory Flow Assistant (IFA), an enterprise-scale data and AI platform designed to improve inventory visibility, inventory health monitoring, decision intelligence and AI-driven recommendations across the supply chain. This is a senior individual contributor role requiring deep technical expertise in Google Cloud, BigQuery, dbt, modern data architecture and large-scale data processing. You will be expected to design, build and own production-grade data products that serve machine learning models, AI agents and other business applications. The ideal candidate combines strong architecture thinking with extensive hands-on development experience and can independently deliver complex solutions while coaching other engineers.
```

</details>

<details><summary>Source [2]</summary>

```text
DBT/Snowflake Engineer — NTT DATA North America (Bengaluru; unknown; open; posted 2026-10-28)
(Experience & Skills) 7+ years of experience in Data Engineering / ETL / DW, with 2+ years working with dbt (Core or Cloud). Strong SQL skills, especially on Snowflake or another modern cloud DW. Experience with dbt concepts: models, tests, sources, seeds, snapshots, macros, exposures. Prior experience with Informatica (developer-level understanding of mappings/workflows) is highly desirable. Understanding of CI/CD practices and integrating dbt into automated pipelines. Knowledge of data modeling (dimensional models, SCDs, fact/dimension design). Experience working in offshore delivery with onshore coordination. Good communication skills and ability to read/understand existing ETL logic and requirements documentation.
```

</details>

<details><summary>Source [3]</summary>

```text
Snowflake DBT Engineer — Anblicks (Hyderabad; unknown; open; posted 2026-10-19)
(We are seeking an experienced) Senior Snowflake & dbt Engineer with 6+ years of experience in Data Engineering, Cloud Data Warehousing, and Analytics Engineering. The ideal candidate will have strong expertise in Snowflake, dbt (Data Build Tool), SQL, ETL/ELT development, and Azure cloud platform . The candidate will be responsible for designing, developing, optimizing, and maintaining scalable data pipelines and modern data warehouse solutions to support enterprise analytics and reporting initiatives.
```

</details>

- Statements supported by the sources (yes / partly / no):
- Agree with the judge (yes / no):

## EV-021: What kind of Airflow experience are employers asking for?

**Answer**

Employers are looking for hands‑on experience building and managing production‑grade Airflow pipelines. Requirements include: • Proven expertise with Apache Airflow for workflow orchestration, DAG design, scheduling, dependency and state management ([1], [2], [3]). • Ability to develop, optimize and troubleshoot Airflow DAGs using Python, including advanced features such as dynamic task mapping, custom operators, XComs, variables, pools and the TaskFlow API ([4]). • Experience deploying Airflow in cloud or container environments, especially on Kubernetes or AWS services, and handling job scheduling, scaling and upgrades without downtime ([3], [4]). • Knowledge of integrating Airflow with other data‑engineering tools (Spark, Snowflake, DBT, Azure, GCP) and managing end‑to‑end data pipelines ([2], a source, a source).

**Judge:** groundedness 75%, citation accuracy 100%

<details><summary>Source [1]</summary>

```text
AWS & Airflow Developer — LPL Financial Global Capability Center (Hyderabad; unknown; open; posted 2026-10-29)
(Requirements) Bachelor's degree in Computer Science, Information Technology, Engineering, or a related field. 4-6 years of experience in Data Engineering, ETL Development, or Data Integration. Strong proficiency in Python programming. Strong hands-on experience with Apache Airflow for workflow orchestration and scheduling.
```

</details>

<details><summary>Source [2]</summary>

```text
Senior Data Engineering Analyst-Data Bricks, Airflow, Snowflake, AI — Optum India (Hyderabad; unknown; open; posted 2026-09-03)
(Required Qualifications) B.Tech. / MCA / Graduation 4+ years of total experience: Solid hands-on experience with Databricks (Spark / PySpark) in production environments Experience building and hosting REST APIs / data services using Python frameworks Solid experience with Microsoft Azure, including cloud-native architecture and best practices Solid working experience with Snowflake, including data modeling and performance tuning Solid understanding of data warehousing, ELT patterns, and modern cloud data architecture Proven expertise with Apache Airflow for workflow orchestration and dependency management Proven advanced Python programming skills for data engineering and API development Demonstrated ability to independently own, design, and deliver end-to-end data engineering solutions
```

</details>

<details><summary>Source [3]</summary>

```text
Senior Big Data Engineer (AWS | PySpark | EMR) — ITC Infotech (Bengaluru; hybrid; open; posted 2026-10-12)
(Orchestration (Must Have)) Apache Airflow AWS Step Functions Workflow orchestration DAG design and optimization Job scheduling and dependency management State management for enterprise data pipelines Required Experience: 8+ years of Data Engineering / Big Data experience Strong experience handling: TB/PB-scale datasets Expertise in Spark optimization techniques: Partitioning Caching Broadcast joins Shuffle optimization Memory tuning Cluster tuning
```

</details>

<details><summary>Source [4]</summary>

```text
Senior Developer, Data Engineer — ICE (Hyderabad; unknown; open; posted 2026-10-16)
(Knowledge And Experience) Apache Airflow: Expert level, with at least three years running Airflow in production. You should know the scheduler internals, executor types, XComs, Connections, Variables, pools, and the TaskFlow API well enough to make trade-off decisions and explain them clearly. Airflow on Kubernetes: Real experience deploying and operating Airflow on Kubernetes via KubernetesExecutor or CeleryKubernetesExecutor: pod templates, resource tuning, persistent volume claims, Helm chart management, and upgrades that do not take the scheduler offline. DAG Development: Strong Python applied to DAG authoring: dynamic task mapping, custom operators and sensors, cross-DAG triggers, parameterised pipelines, and proper test coverage. Writing testable DAGs should feel natural, not optional. ETL and ELT Pipelines: Demonstrated experience building batch and incremental pipelines at scale. You understand transformation logic, data quality validation, and lineage capture, and you have shipped pipelines that other people maintain without you.
```

</details>

- Statements supported by the sources (yes / partly / no):
- Agree with the judge (yes / no):

## EV-024: What does MLOps experience mean in these postings?

**Answer**

Across the postings, MLOps experience refers to hands‑on work that spans the full machine‑learning lifecycle: building and operating platforms for model training, deployment, monitoring and automated retraining.  Candidates are expected to be proficient in Python and cloud services (AWS, Azure or GCP) and to use containerisation (Docker, Kubernetes) and CI/CD pipelines (GitHub Actions, Jenkins, Azure DevOps, Argo, etc.) to move models from experiment to production.  They should also work with ML‑specific tooling such as MLflow, feature stores, experiment tracking, model registries, and orchestration tools (Airflow, Databricks, Delta Lake, Kubeflow) and be able to implement monitoring, drift detection and governance for production models.  The role blends software‑engineering, DevOps and data‑engineering skills to deliver reliable, scalable AI services.

**Judge:** groundedness 100%, citation accuracy 100%

<details><summary>Source [1]</summary>

```text
MLOps Architect With (Databricks) — Anblicks (Hyderabad; hybrid; open; posted 2026-05-31)
(Required Skills & Experience) 12–18 years of experience in MLOps, Machine Learning Platform Engineering, AI Platform Architecture, or Data Engineering. Proven experience architecting and implementing enterprise MLOps platforms from scratch. Deep expertise in architecting the end-to-end ML lifecycle, including Feature Engineering, Feature Stores, Experiment Tracking, MLflow, Model Registry, Distributed Training, Hyperparameter Optimization, Model Deployment, Batch & Real-time Inference, Monitoring, Drift Detection, Explainability, AI Governance, Lineage, and Automated Retraining for enterprise-scale AI platforms. Strong expertise with Databricks, MLflow, Unity Catalog, Delta Lake, Delta Live Tables (DLT), Mosaic AI, Apache Spark, PySpark, Structured Streaming, and Lakehouse Architecture. Experience building large-scale AI platforms supporting thousands of production ML models and high-volume distributed data workloads. Strong programming skills in Python, PySpark, SQL, and distributed data processing. Experience working on Azure (Preferred), AWS, or GCP.
```

</details>

<details><summary>Source [2]</summary>

```text
MLOps Engineer — Contentverse by Computhink (Bengaluru; unknown; open; posted 2026-08-05)
(Overview) Hands on Experience in MLOps or AI integration projects. Hands -on experience in DevOps or software engineering. Hands-on with RAG architectures for LLMs. Hands-on with Python, REST APIs, Bash scripting. Experience with Docker, containerization, and CI/CD workflows. Familiarity with cloud platforms (Azure, AWS, or GCP). Knowledge of AI pipeline tools (MLflow, FastAPI, Airflow, LangChain, etc.). Experience with at least one vector database (e.g., FAISS, Weaviate, and Chroma). Understanding of deploying AI services securely and efficiently. Experience with Agile and DevOps software development principles/methodologies and working on teams focused on delivering business value.
```

</details>

<details><summary>Source [3]</summary>

```text
MLOps Engineer — C5i (Bengaluru; unknown; open; posted 2026-07-09)
(Required Skills & Qualifications) Experience: 3-5 years in MLOps, DevOps, or related fields with direct experience in ML model deployment and monitoring. Cloud Platforms: Proficient in Databricks Azure, and AWS environments. MLOps Tools: Hands-on with Kubernetes, Docker, Apache Airflow, MLflow, Databricks, and Delta Lake. CI/CD: Experience building robust CI/CD pipelines for ML using Git, Azure DevOps, Jenkins, or GitHub Actions. Automation & Scripting: Strong programming/scripting in Python. Familiarity with shell scripting is a plus. IaC: Experience in provisioning infrastructure using Terraform or similar tools. Model Governance: Understanding of model versioning, governance, reproducibility, and compliance in enterprise environments. Problem Solving: Ability to identify bottlenecks, optimize workflows, and deliver scalable solutions across the ML lifecycle. C5i is proud to be an equal opportunity employer. We are committed to equal employment opportunity regardless of race, color, religion, sex, sexual orientation, age, marital status, disability, gender identity, etc.
```

</details>

- Statements supported by the sources (yes / partly / no):
- Agree with the judge (yes / no):

## EV-037: What is Amgen looking for in data and AI candidates?

**Answer**

Amgen seeks candidates who can blend deep AI/ML engineering skills with a strong understanding of biopharmaceutical and scientific contexts.  They want hands‑on AI and data engineers who can work close to process‑development problems, build credible technical solutions, and produce delivery evidence for adoption.  Required capabilities include experience with cloud‑based data platforms, APIs, notebooks, and deployment of reusable analytical or AI services; strong communication to document assumptions, data lineage, and validation evidence; and the ability to operate in a matrixed, global environment with scientists, engineers, and platform teams.  Preferred expertise adds LLMs, agentic AI, RAG, vector databases, knowledge‑graph architectures, and experience integrating domain‑specific AI models, plus a track record of measuring accuracy, reliability, scientific relevance, and responsible‑AI governance.  Strong programming (Python, Scala), cloud (AWS, Azure, Databricks), MLOps tools, and the ability to translate scientific requirements into scalable AI solutions are also emphasized.[1][2][3]

**Judge:** groundedness 100%, citation accuracy 100%

<details><summary>Source [1]</summary>

```text
Sr Data Scientist/AI Applications Engineer — Amgen (Hyderabad; unknown; open; posted 2026-08-13)
(Required Skills) The ideal candidate is a hands-on AI and data engineer who can operate close to Process Development problems, build credible technical solutions, and create the delivery evidence needed for adoption. They should be comfortable moving between scientific workflow context, data strategy, AI experimentation, software delivery, and stakeholder communication.
...
(Required Skills) plans, and measurable outcomes. Understanding of biopharmaceutical development, process development, manufacturing science, analytical development, or related regulated technical environments. Experience with cloud, data platform, API, notebook, or application development patterns used to deploy reusable analytical or AI capabilities to internal users. Strong written and verbal communication skills, including the ability to document technical assumptions, limitations, data lineage, validation evidence, and user guidance. Demonstrated ability to independently uncover, structure, and resolve issues associated with scientific, engineering, data, or AI-enabled delivery projects. Ability to work effectively in a matrixed global environment across AIN and U.S. time zones, with scientists, engineers, product owners, data strategists, and software/platform partners. Candidate Profile The ideal candidate is a hands-on AI and data engineer who can operate close to Process Development problems, build credible technical solutions, and create the delivery evidence needed for adoption.
```

</details>

<details><summary>Source [2]</summary>

```text
Sr Associate Data Scientist — Amgen (Hyderabad; unknown; open; posted 2026-07-14)
(Preferred Qualifications) Experience with LLMs, agentic AI systems, and workflow orchestration Experience with RAG, vector databases, and knowledge-driven AI architectures Experience integrating scientific or domain-specific AI models: Familiarity with biological, biomedical, or life sciences data Experience with cloud AI platforms (AWS Bedrock, SageMaker, Azure AI, or equivalent) Familiarity with knowledge graphs, Graph-RAG, or scientific knowledge systems Experience working closely with researchers and domain experts.
...
(Establish approaches for measuring) Accuracy Reliability Scientific relevance Hallucination rates Workflow effectiveness User adoption and impact Support responsible AI practices including transparency, traceability, and governance requirements. Collaboration & Scientific Partnership Partner closely with: AI domain leads Scientists and researchers Data engineering teams Platform engineering teams Enterprise AI platform teams Translate scientific requirements into technical solutions and provide guidance on AI capabilities, limitations, and implementation approaches. Contribute to technical design reviews and mentor junior team members where appropriate. Core Competencies Strong engineering background in AI and machine learning systems.
```

</details>

<details><summary>Source [3]</summary>

```text
Sr Machine Learning Engineer — Amgen (Hyderabad; unknown; open; posted 2026-10-21)
(Must-Have Skills) 3-5 years in AI/ML and enterprise software. Comprehensive command of machine-learning algorithms—regression, tree-based ensembles, clustering, dimensionality reduction, time-series models, deep-learning architectures (CNNs, RNNs, transformers) and modern LLM/RAG techniques—with the judgment to choose, tune and operationalise the right method for a given business problem. Proven track record selecting and integrating AI SaaS/PaaS offerings and building custom ML services at scale. Expert knowledge of GenAI tooling: vector databases, RAG pipelines, prompt-engineering DSLs and agent frameworks (e.g., LangChain, Semantic Kernel). Proficiency in Python and Java; containerisation (Docker/K8s); cloud (AWS, Azure or GCP) and modern DevOps/MLOps (GitHub Actions, Bedrock/SageMaker Pipelines). Strong business-case skills—able to model TCO vs. NPV and present trade-offs to executives. Exceptional stakeholder management; can translate complex technical concepts into concise, outcome-oriented narratives.
```

</details>

- Statements supported by the sources (yes / partly / no):
- Agree with the judge (yes / no):
