# Judge calibration: labelling sheet

Fill in `evals/datasets/human_labels.csv` (one row per proposal id below).

## Rubric (score 0-10, then pass or revise)

Score each proposal on four things, roughly equally weighted:

1. **Fit**: does it address the job's must-have requirements listed above it?
2. **Evidence**: are claims specific and backed by concrete past work (project, numbers), not vague?
3. **Personalisation**: does the opening speak to *this* client's problem, not a generic "Dear Sir / I am passionate"?
4. **Clarity and length**: easy to read, no padding, a clear next step.

**Verdict**: `pass` = you would send it as is (score about 7 or more); `revise` = it needs changes before sending.


---

## jp-01 · Demand forecasting model for our nonprofit business

*Persona:* aiml · *Budget:* hourly 55.0-95.0 · *Job id:* d-aiml-160

**Requirements**
- Experience with time series forecasting
- Experience with python
- Experience with scikit-learn
- Deliver a forecasting model
- Deliver a backtest report
- Deliver a scheduled retraining job

**Cover letter**

You want "Demand forecasting model for our nonprofit business" delivered (a forecasting model, a backtest report, a scheduled retraining job), and the part that decides success is usually time series forecasting.

On time series forecasting: The first version was deliberately boring, and that is why it shipped on time [aiml-case-05]. On python: nlp, python3, plus the usual tooling [aiml-case-08]. On scikit-learn: In December 2022 I was asked to help a mid-sized media company where the retention team contacted the wrong customers [aiml-case-09].

My plan: confirm the scope and acceptance criteria in a short call, deliver a first working version early, then iterate with you on the details.

I propose $85/hr for this scope. Could you share what a successful first milestone looks like for you?

**Screening answers**
- **Q:** What is your availability in the next two weeks?
  **A:** Yes. The first version was deliberately boring, and that is why it shipped on time [aiml-case-05].


---

## jp-02 · Deploy our ML models to production on AWS

*Persona:* aiml · *Budget:* hourly 56.0-97.0 · *Job id:* d-aiml-092

**Requirements**
- Experience with mlops
- Experience with docker
- Experience with kubernetes
- Experience with aws
- Deliver containerised model services
- Deliver monitoring dashboards
- Deliver a retraining pipeline

**Cover letter**

You want "Deploy our ML models to production on AWS" delivered (containerised model services, monitoring dashboards, a retraining pipeline), and the part that decides success is usually mlops.

On mlops: This engagement started with a complaint from the operations lead: models were retrained by hand on a laptop and nobody knew which version was live [aiml-case-10]. On docker: && docker run -p 8000:8000 svc [aiml-repo-03]. On kubernetes: It exists because models were retrained by hand on a laptop and nobody knew which version was live [aiml-repo-05].

My plan: confirm the scope and acceptance criteria in a short call, deliver a first working version early, then iterate with you on the details. I will also cover production reliability.

I propose $85/hr for this scope. Could you share what a successful first milestone looks like for you?

**Screening answers**
- **Q:** What is your availability in the next two weeks?
  **A:** Yes. This engagement started with a complaint from the operations lead: models were retrained by hand on a laptop and nobody knew which version was live [aiml-case-10].
- **Q:** Describe a similar project you have delivered.
  **A:** Yes. This engagement started with a complaint from the operations lead: models were retrained by hand on a laptop and nobody knew which version was live [aiml-case-10].


---

## jp-03 · Document question-answering bot with citations

*Persona:* aiml · *Budget:* fixed 1900.0-2850.0 · *Job id:* d-aiml-122

**Requirements**
- Experience with rag
- Experience with langchain
- Experience with vector databases
- Experience with python
- Experience with prompt engineering
- Deliver a working chatbot with source citations
- Deliver an ingestion script for new documents
- Deliver an evaluation report

**Cover letter**

You want "Document question-answering bot with citations" delivered (a working chatbot with source citations, an ingestion script for new documents, an evaluation report), and the part that decides success is usually rag.

On rag: I used rag to ground answers in the client's own documents [aiml-case-17]. On langchain: I used langchain to wire the prompts, retrievers and output parsers [aiml-case-07]. On vector databases: I used vector databases to store and search the embeddings [aiml-case-02].

My plan: confirm the scope and acceptance criteria in a short call, deliver a first working version early, then iterate with you on the details. I will also cover clear documentation and handover.

I propose $2975 fixed for this scope. Could you share what a successful first milestone looks like for you?

**Screening answers**
- **Q:** What is your experience with rag?
  **A:** Yes. I used rag to ground answers in the client's own documents [aiml-case-17].
- **Q:** What is your availability in the next two weeks?
  **A:** Yes. I used rag to ground answers in the client's own documents [aiml-case-17].


---

## jp-04 · Build a small data warehouse with dbt

*Persona:* data · *Budget:* fixed 4450.0-6670.0 · *Job id:* d-data-059

**Requirements**
- Experience with snowflake
- Experience with sql
- Experience with etl
- Deliver dbt models with tests
- Deliver a lineage diagram
- Deliver a handover session

**Cover letter**

You want "Build a small data warehouse with dbt" delivered (dbt models with tests, a lineage diagram, a handover session), and the part that decides success is usually snowflake.

On snowflake: Warehouse Rebuild in dbt and Snowflake [data-case-02]. On sql: sql, python, pandas, power bi, tableau, excel, dbt, snowflake, bigquery, google analytics, a/b [data-cv]. On etl: It exists because reports used week-old CSV exports [data-repo-05].

My plan: confirm the scope and acceptance criteria in a short call, deliver a first working version early, then iterate with you on the details. I will also cover clear documentation and handover.

I propose $6600 fixed for this scope. Could you share what a successful first milestone looks like for you?

**Screening answers**
- **Q:** How would you approach dbt models with tests?
  **A:** Yes. Warehouse Rebuild in dbt and Snowflake [data-case-02].


---

## jp-05 · Analyse our customer survey results

*Persona:* data · *Budget:* fixed 1260.0-1890.0 · *Job id:* d-data-118

**Requirements**
- Experience with survey analysis
- Experience with r
- Experience with statistics
- Deliver a findings report
- Deliver charts
- Deliver cleaned data

**Cover letter**

You want "Analyse our customer survey results" delivered (a findings report, charts, cleaned data), and the part that decides success is usually survey analysis.

On survey analysis: Customer Satisfaction Survey Study [data-case-06]. On r: This engagement started with a complaint from the operations lead: the district had ten years of results in separate spreadsheets [data-case-15]. On statistics: I used regression to separate [removed] from noise [data-case-03].

My plan: confirm the scope and acceptance criteria in a short call, deliver a first working version early, then iterate with you on the details.

I propose $2050 fixed for this scope. Could you share what a successful first milestone looks like for you?

**Screening answers**
- **Q:** Which part of this project do you see as the biggest risk?
  **A:** Yes. Customer Satisfaction Survey Study [data-case-06].
- **Q:** How would you approach a findings report?
  **A:** Yes. Customer Satisfaction Survey Study [data-case-06].
- **Q:** Describe a similar project you have delivered.
  **A:** Yes. Customer Satisfaction Survey Study [data-case-06].


---

## jp-06 · Statistical analysis of a pricing experiment

*Persona:* data · *Budget:* fixed 520.0-780.0 · *Job id:* d-data-097

**Requirements**
- Experience with a/b testing
- Experience with statistics
- Experience with python
- Deliver a written readout
- Deliver a reproducible notebook

**Cover letter**

You want "Statistical analysis of a pricing experiment" delivered (a written readout, a reproducible notebook), and the part that decides success is usually a/b testing.

On a/b testing: The first version was deliberately boring, and that is why it shipped on time [data-case-03]. On statistics: This engagement started with a complaint from the operations lead: the district had ten years of results in separate spreadsheets [data-case-15]. On python: data quality, python, plus the usual tooling [data-case-07].

My plan: confirm the scope and acceptance criteria in a short call, deliver a first working version early, then iterate with you on the details.

I propose $845 fixed for this scope. Could you share what a successful first milestone looks like for you?

**Screening answers**
- **Q:** Which part of this project do you see as the biggest risk?
  **A:** Yes. The first version was deliberately boring, and that is why it shipped on time [data-case-03].
- **Q:** What is your experience with a/b testing?
  **A:** Yes. The first version was deliberately boring, and that is why it shipped on time [data-case-03].


---

## jp-07 · Set up automated browser testing

*Persona:* fullstack · *Budget:* hourly 33.0-57.0 · *Job id:* d-fullstack-120

**Requirements**
- Experience with playwright testing
- Experience with typescript
- Experience with ci/cd
- Deliver an end-to-end test suite
- Deliver CI integration
- Deliver a flaky-test report

**Cover letter**

You want "Set up automated browser testing" delivered (an end-to-end test suite, CI integration, a flaky-test report), and the part that decides success is usually playwright testing.

On typescript: I used typescript to keep the front and back end type-safe [fullstack-case-08]. On ci/cd: In April 2025 I was asked to help a mid-sized fintech company where deploys were done by SSH-ing into a server on Friday nights [fullstack-case-09].

My plan: confirm the scope and acceptance criteria in a short call, deliver a first working version early, then iterate with you on the details.

I propose $55/hr for this scope. Could you share what a successful first milestone looks like for you?

**Screening answers**
- **Q:** Which part of this project do you see as the biggest risk?
  **A:** Yes. We tracked a small set of numbers weekly and dropped anything nobody looked at [fullstack-case-18].
- **Q:** What is your experience with playwright testing?
  **A:** Yes. We tracked a small set of numbers weekly and dropped anything nobody looked at [fullstack-case-18].


---

## jp-08 · Subscription web app with user accounts and payments

*Persona:* fullstack · *Budget:* hourly 67.0-116.0 · *Job id:* d-fullstack-049

**Requirements**
- Experience with next.js
- Experience with react
- Experience with typescript
- Experience with stripe
- Experience with postgresql
- Deliver a deployed web app
- Deliver Stripe subscription billing
- Deliver an admin area

**Cover letter**

You want "Subscription web app with user accounts and payments" delivered (a deployed web app, Stripe subscription billing, an admin area), and the part that decides success is usually next.js.

On next.js: Donation Platform for a Charity [fullstack-case-13]. On react: React.js, TS, plus the usual tooling [fullstack-case-17]. On typescript: I used typescript to keep the front and back end type-safe [fullstack-case-08].

My plan: confirm the scope and acceptance criteria in a short call, deliver a first working version early, then iterate with you on the details.

I propose $70/hr for this scope. Could you share what a successful first milestone looks like for you?

**Screening answers**
- **Q:** Which part of this project do you see as the biggest risk?
  **A:** Yes. Donation Platform for a Charity [fullstack-case-13].
- **Q:** Describe a similar project you have delivered.
  **A:** Yes. Donation Platform for a Charity [fullstack-case-13].


---

## jp-09 · Dockerize our web app and set up CI/CD on AWS

*Persona:* fullstack · *Budget:* fixed 1250.0-1870.0 · *Job id:* d-fullstack-136

**Requirements**
- Experience with docker
- Experience with ci/cd
- Experience with aws
- Deliver Dockerfiles and compose setup
- Deliver a CI/CD pipeline
- Deliver a runbook

**Cover letter**

You want "Dockerize our web app and set up CI/CD on AWS" delivered (Dockerfiles and compose setup, a CI/CD pipeline, a runbook), and the part that decides success is usually docker.

On docker: In April 2025 I was asked to help a mid-sized fintech company where deploys were done by SSH-ing into a server on Friday nights [fullstack-case-09]. On ci/cd: playwright testing, ci/cd, plus the usual tooling [fullstack-case-18]. On aws:  GraphQL API for a Rental Marketplace: The web and mobile teams kept asking backend for new [fullstack-cv].

My plan: confirm the scope and acceptance criteria in a short call, deliver a first working version early, then iterate with you on the details.

I propose $2055 fixed for this scope. Could you share what a successful first milestone looks like for you?



---

## jp-10 · LangGraph agent to automate healthcare back-office work

*Persona:* aiml · *Budget:* fixed 6920.0-10380.0 · *Job id:* d-aiml-063

**Requirements**
- Experience with langgraph
- Experience with langchain
- Experience with python
- Experience with fastapi
- Deliver an agent workflow with approval steps
- Deliver an API endpoint
- Deliver deployment notes

**Cover letter**

You want "LangGraph agent to automate healthcare back-office work" delivered (an agent workflow with approval steps, an API endpoint, deployment notes), and the part that decides success is usually langgraph.

On langgraph: I used langgraph to orchestrate t [aiml-case-07]. On langchain: the code in this repository uses langchain [aiml-repo-04]. On python: nlp, python3, plus the usual tooling [aiml-case-08].

My plan: confirm the scope and acceptance criteria in a short call, deliver a first working version early, then iterate with you on the details.

I propose $10845 fixed for this scope. Could you share what a successful first milestone looks like for you?

**Screening answers**
- **Q:** What is your experience with langgraph?
  **A:** Yes. I used langgraph to orchestrate t [aiml-case-07].
- **Q:** Which part of this project do you see as the biggest risk?
  **A:** Yes. I used langgraph to orchestrate t [aiml-case-07].
- **Q:** How would you approach an agent workflow with approval steps?
  **A:** Yes. I used langgraph to orchestrate t [aiml-case-07].


---

## jp-11 · LoRA fine-tune of a 7B model on our support data

*Persona:* aiml · *Budget:* fixed 3670.0-5510.0 · *Job id:* d-aiml-136

**Requirements**
- Experience with llm fine-tuning
- Experience with pytorch
- Experience with model evaluation
- Deliver a fine-tuned model checkpoint
- Deliver a training notebook
- Deliver a benchmark against the current model

**Cover letter**

You want "LoRA fine-tune of a 7B model on our support data" delivered (a fine-tuned model checkpoint, a training notebook, a benchmark against the current model), and the part that decides success is usually llm fine-tuning.

On llm fine-tuning: I used llm fine-tuning to adapt an open model to the client's tone and labels [aiml-case-06]. On model evaluation: I used python to glue the data pipeline and model code together [aiml-case-18]. On deliver a fine-tuned model checkpoint: We started from a pretrained encoder checkpoint and only trained the last layers on the client's data [aiml-case-08].

My plan: confirm the scope and acceptance criteria in a short call, deliver a first working version early, then iterate with you on the details.

I propose $5755 fixed for this scope. Could you share what a successful first milestone looks like for you?

**Screening answers**
- **Q:** What is your experience with llm fine-tuning?
  **A:** Yes. I used llm fine-tuning to adapt an open model to the client's tone and labels [aiml-case-06].


---

## jp-12 · Tableau workbook for logistics operations

*Persona:* data · *Budget:* fixed 3690.0-5530.0 · *Job id:* d-data-172

**Requirements**
- Experience with tableau
- Experience with sql
- Experience with dashboard design
- Deliver a published Tableau workbook
- Deliver data source documentation

**Cover letter**

You want "Tableau workbook for logistics operations" delivered (a published Tableau workbook, data source documentation), and the part that decides success is usually tableau.

On tableau: This engagement started with a complaint from the operations lead: bed managers phoned each ward for occupancy every morning [data-case-05]. On sql: sql, python, pandas, power bi, tableau, excel, dbt, snowflake, bigquery, google analytics, a/b [data-cv]. On dashboard design: We tracked a small set of numbers weekly and dropped anything nobody looked at [data-case-01].

My plan: confirm the scope and acceptance criteria in a short call, deliver a first working version early, then iterate with you on the details. I will also cover clear documentation and handover.

I propose $6005 fixed for this scope. Could you share what a successful first milestone looks like for you?

**Screening answers**
- **Q:** What is your experience with tableau?
  **A:** Yes. This engagement started with a complaint from the operations lead: bed managers phoned each ward for occupancy every morning [data-case-05].
- **Q:** Which part of this project do you see as the biggest risk?
  **A:** Yes. This engagement started with a complaint from the operations lead: bed managers phoned each ward for occupancy every morning [data-case-05].


---

## jp-13 · dbt models on Snowflake for our education data

*Persona:* data · *Budget:* fixed 3780.0-5660.0 · *Job id:* d-data-156

**Requirements**
- Experience with snowflake
- Experience with sql
- Experience with etl
- Deliver dbt models with tests
- Deliver a lineage diagram
- Deliver a handover session

**Cover letter**

You want "dbt models on Snowflake for our education data" delivered (dbt models with tests, a lineage diagram, a handover session), and the part that decides success is usually snowflake.

On snowflake: Warehouse Rebuild in dbt and Snowflake [data-case-02]. On sql: sql, python, pandas, power bi, tableau, excel, dbt, snowflake, bigquery, google analytics, a/b [data-cv]. On etl: It exists because reports used week-old CSV exports [data-repo-05].

My plan: confirm the scope and acceptance criteria in a short call, deliver a first working version early, then iterate with you on the details. I will also cover clear documentation and handover.

I propose $6150 fixed for this scope. Could you share what a successful first milestone looks like for you?

**Screening answers**
- **Q:** What is your experience with snowflake?
  **A:** Yes. Warehouse Rebuild in dbt and Snowflake [data-case-02].
- **Q:** What is your availability in the next two weeks?
  **A:** Yes. Warehouse Rebuild in dbt and Snowflake [data-case-02].


---

## jp-14 · Move our deploys to GitHub Actions

*Persona:* fullstack · *Budget:* fixed 1770.0-2660.0 · *Job id:* d-fullstack-114

**Requirements**
- Experience with docker
- Experience with ci/cd
- Experience with aws
- Deliver Dockerfiles and compose setup
- Deliver a CI/CD pipeline
- Deliver a runbook

**Cover letter**

You want "Move our deploys to GitHub Actions" delivered (Dockerfiles and compose setup, a CI/CD pipeline, a runbook), and the part that decides success is usually docker.

On docker: In April 2025 I was asked to help a mid-sized fintech company where deploys were done by SSH-ing into a server on Friday nights [fullstack-case-09]. On ci/cd: playwright testing, ci/cd, plus the usual tooling [fullstack-case-18]. On aws:  GraphQL API for a Rental Marketplace: The web and mobile teams kept asking backend for new [fullstack-cv].

My plan: confirm the scope and acceptance criteria in a short call, deliver a first working version early, then iterate with you on the details.

I propose $2925 fixed for this scope. Could you share what a successful first milestone looks like for you?

**Screening answers**
- **Q:** What is your experience with docker?
  **A:** Yes. In April 2025 I was asked to help a mid-sized fintech company where deploys were done by SSH-ing into a server on Friday nights [fullstack-case-09].
- **Q:** Which part of this project do you see as the biggest risk?
  **A:** Yes. In April 2025 I was asked to help a mid-sized fintech company where deploys were done by SSH-ing into a server on Friday nights [fullstack-case-09].
- **Q:** What is your availability in the next two weeks?
  **A:** Yes. In April 2025 I was asked to help a mid-sized fintech company where deploys were done by SSH-ing into a server on Friday nights [fullstack-case-09].


---

## jp-15 · Live collaboration features with WebSockets

*Persona:* fullstack · *Budget:* hourly 35.0-61.0 · *Job id:* d-fullstack-111

**Requirements**
- Experience with websockets
- Experience with redis
- Experience with react
- Deliver real-time messaging
- Deliver presence indicators
- Deliver load test results

**Cover letter**

You want "Live collaboration features with WebSockets" delivered (real-time messaging, presence indicators, load test results), and the part that decides success is usually websockets.

On websockets: This engagement started with a complaint from the operations lead: the agency's planning lived in a spreadsheet that people overwrote [fullstack-case-03]. On redis: I used redis to cache sessions and rate limits [fullstack-case-12]. On react: React.js, TS, plus the usual tooling [fullstack-case-17].

My plan: confirm the scope and acceptance criteria in a short call, deliver a first working version early, then iterate with you on the details.

I propose $60/hr for this scope. Could you share what a successful first milestone looks like for you?

**Screening answers**
- **Q:** What is your experience with websockets?
  **A:** Yes. This engagement started with a complaint from the operations lead: the agency's planning lived in a spreadsheet that people overwrote [fullstack-case-03].
- **Q:** How would you approach real-time messaging?
  **A:** Yes. This engagement started with a complaint from the operations lead: the agency's planning lived in a spreadsheet that people overwrote [fullstack-case-03].


---

## jp-16 · NLP pipeline to extract entities from nonprofit contracts

*Persona:* aiml · *Budget:* hourly 50.0-86.0 · *Job id:* d-aiml-188

**Requirements**
- Experience with nlp
- Experience with huggingface transformers
- Experience with python
- Deliver an extraction pipeline
- Deliver labelled evaluation data
- Deliver a short report

**Cover letter**

You want "NLP pipeline to extract entities from nonprofit contracts" delivered (an extraction pipeline, labelled evaluation data, a short report), and the part that decides success is usually nlp.

On nlp: This engagement started with a complaint from the operations lead: paralegals copied renewal dates and liability caps out of contracts by hand [aiml-case-03]. On huggingface transformers: I used huggingface transformers [aiml-case-06]. On python: nlp, python3, plus the usual tooling [aiml-case-08].

My plan: confirm the scope and acceptance criteria in a short call, deliver a first working version early, then iterate with you on the details.

I propose $85/hr for this scope. Could you share what a successful first milestone looks like for you?

**Screening answers**
- **Q:** Describe a similar project you have delivered.
  **A:** Yes. This engagement started with a complaint from the operations lead: paralegals copied renewal dates and liability caps out of contracts by hand [aiml-case-03].
- **Q:** Which part of this project do you see as the biggest risk?
  **A:** Yes. This engagement started with a complaint from the operations lead: paralegals copied renewal dates and liability caps out of contracts by hand [aiml-case-03].


---

## jp-17 · Multi-step AI agent with human approval for retail

*Persona:* aiml · *Budget:* hourly 60.0-104.0 · *Job id:* d-aiml-179

**Requirements**
- Experience with langchain
- Experience with python
- Experience with fastapi
- Deliver an agent workflow with approval steps
- Deliver an API endpoint
- Deliver deployment notes

**Cover letter**

You want "Multi-step AI agent with human approval for retail" delivered (an agent workflow with approval steps, an API endpoint, deployment notes), and the part that decides success is usually langchain.

On langchain: KYC Review Agent with Human Approval [aiml-case-07]. On python: nlp, python3, plus the usual tooling [aiml-case-08]. On fastapi: the code in this repository uses fastapi [aiml-repo-04].

My plan: confirm the scope and acceptance criteria in a short call, deliver a first working version early, then iterate with you on the details.

I propose $85/hr for this scope. Could you share what a successful first milestone looks like for you?

**Screening answers**
- **Q:** Which part of this project do you see as the biggest risk?
  **A:** Yes. KYC Review Agent with Human Approval [aiml-case-07].
- **Q:** What is your experience with langchain?
  **A:** Yes. KYC Review Agent with Human Approval [aiml-case-07].


---

## jp-18 · Tableau workbook for legal operations

*Persona:* data · *Budget:* hourly 25.0-44.0 · *Job id:* d-data-186

**Requirements**
- Experience with tableau
- Experience with sql
- Experience with dashboard design
- Deliver a published Tableau workbook
- Deliver data source documentation

**Cover letter**

You want "Tableau workbook for legal operations" delivered (a published Tableau workbook, data source documentation), and the part that decides success is usually tableau.

On tableau: This engagement started with a complaint from the operations lead: bed managers phoned each ward for occupancy every morning [data-case-05]. On sql: I used sql to model and query the sales data [data-case-01]. On dashboard design: Data analyst who turns messy exports into dashboards people actually open [data-cv].

My plan: confirm the scope and acceptance criteria in a short call, deliver a first working version early, then iterate with you on the details. I will also cover clear documentation and handover.

I propose $44/hr for this scope. Could you share what a successful first milestone looks like for you?

**Screening answers**
- **Q:** What is your availability in the next two weeks?
  **A:** Yes. This engagement started with a complaint from the operations lead: bed managers phoned each ward for occupancy every morning [data-case-05].
- **Q:** How would you approach a published Tableau workbook?
  **A:** Yes. This engagement started with a complaint from the operations lead: bed managers phoned each ward for occupancy every morning [data-case-05].


---

## jp-19 · Analyse our A/B test results

*Persona:* data · *Budget:* fixed 720.0-1080.0 · *Job id:* d-data-161

**Requirements**
- Experience with a/b testing
- Experience with statistics
- Experience with python
- Deliver a written readout
- Deliver a reproducible notebook

**Cover letter**

You want "Analyse our A/B test results" delivered (a written readout, a reproducible notebook), and the part that decides success is usually a/b testing.

On a/b testing: I used regression to separate [removed] from noise [data-case-03]. On statistics: testing, statistics, looker studio, etl [data-cv]. On python: data quality, python, plus the usual tooling [data-case-07].

My plan: confirm the scope and acceptance criteria in a short call, deliver a first working version early, then iterate with you on the details.

I propose $1170 fixed for this scope. Could you share what a successful first milestone looks like for you?

**Screening answers**
- **Q:** What is your availability in the next two weeks?
  **A:** Yes. I used regression to separate [removed] from noise [data-case-03].


---

## jp-20 · Statistical analysis of a pricing experiment

*Persona:* data · *Budget:* hourly 21.0-37.0 · *Job id:* d-data-036

**Requirements**
- Experience with a/b testing
- Experience with statistics
- Experience with python
- Deliver a written readout
- Deliver a reproducible notebook

**Cover letter**

You want "Statistical analysis of a pricing experiment" delivered (a written readout, a reproducible notebook), and the part that decides success is usually a/b testing.

On a/b testing: The first version was deliberately boring, and that is why it shipped on time [data-case-03]. On statistics: This engagement started with a complaint from the operations lead: the district had ten years of results in separate spreadsheets [data-case-15]. On python: data quality, python, plus the usual tooling [data-case-07].

My plan: confirm the scope and acceptance criteria in a short call, deliver a first working version early, then iterate with you on the details.

I propose $37/hr for this scope. Could you share what a successful first milestone looks like for you?



---

## jp-21 · React Native app for our nonprofit customers

*Persona:* fullstack · *Budget:* hourly 33.0-57.0 · *Job id:* d-fullstack-147

**Requirements**
- Experience with react native
- Experience with typescript
- Experience with oauth
- Deliver iOS and Android builds
- Deliver login with Google
- Deliver store submission

**Cover letter**

You want "React Native app for our nonprofit customers" delivered (iOS and Android builds, login with Google, store submission), and the part that decides success is usually react native.

On react native: react native, NodeJS, plus the usual tooling [fullstack-case-05]. On typescript: and a shared design-token config instead of hand-written stylesheets [fullstack-case-17]. On oauth: We tracked a small set of numbers weekly and dropped anything nobody looked at [fullstack-case-15].

My plan: confirm the scope and acceptance criteria in a short call, deliver a first working version early, then iterate with you on the details.

I propose $55/hr for this scope. Could you share what a successful first milestone looks like for you?

**Screening answers**
- **Q:** What is your availability in the next two weeks?
  **A:** Yes. react native, NodeJS, plus the usual tooling [fullstack-case-05].
- **Q:** Which part of this project do you see as the biggest risk?
  **A:** Yes. react native, NodeJS, plus the usual tooling [fullstack-case-05].


---

## jp-22 · React Native app for our hospitality customers

*Persona:* fullstack · *Budget:* fixed 6410.0-9610.0 · *Job id:* d-fullstack-087

**Requirements**
- Experience with react native
- Experience with typescript
- Experience with oauth
- Deliver iOS and Android builds
- Deliver login with Google
- Deliver store submission

**Cover letter**

You want "React Native app for our hospitality customers" delivered (iOS and Android builds, login with Google, store submission), and the part that decides success is usually react native.

On react native: A fitness client came to me because the trainer sent workout plans as PDFs on messaging apps [fullstack-case-16]. On typescript: I used typescript to keep the front and back end type-safe [fullstack-case-08]. On oauth: We tracked a small set of numbers weekly and dropped anything nobody looked at [fullstack-case-15].

My plan: confirm the scope and acceptance criteria in a short call, deliver a first working version early, then iterate with you on the details.

I propose $8400 fixed for this scope. Could you share what a successful first milestone looks like for you?

**Screening answers**
- **Q:** What is your availability in the next two weeks?
  **A:** Yes. A fitness client came to me because the trainer sent workout plans as PDFs on messaging apps [fullstack-case-16].


---

## jp-23 · LangGraph agent to automate hospitality back-office work

*Persona:* aiml · *Budget:* fixed 4130.0-6190.0 · *Job id:* d-aiml-018

**Requirements**
- Experience with langgraph
- Experience with langchain
- Experience with python
- Experience with fastapi
- Deliver an agent workflow with approval steps
- Deliver an API endpoint
- Deliver deployment notes

**Cover letter**

You want "LangGraph agent to automate hospitality back-office work" delivered (an agent workflow with approval steps, an API endpoint, deployment notes), and the part that decides success is usually langgraph.

On langgraph: lived in one typed codebase with a small CLI [aiml-case-07]. On langchain: the code in this repository uses langchain [aiml-repo-04]. On python: nlp, python3, plus the usual tooling [aiml-case-08].

My plan: confirm the scope and acceptance criteria in a short call, deliver a first working version early, then iterate with you on the details.

I propose $6470 fixed for this scope. Could you share what a successful first milestone looks like for you?

**Screening answers**
- **Q:** What is your experience with langgraph?
  **A:** Yes. lived in one typed codebase with a small CLI [aiml-case-07].
- **Q:** What is your availability in the next two weeks?
  **A:** Yes. lived in one typed codebase with a small CLI [aiml-case-07].


---

## jp-24 · Build an internal Q&A assistant for nonprofit policies

*Persona:* aiml · *Budget:* hourly 51.0-88.0 · *Job id:* d-aiml-184

**Requirements**
- Experience with rag
- Experience with langchain
- Experience with vector databases
- Experience with python
- Experience with prompt engineering
- Deliver a working chatbot with source citations
- Deliver an ingestion script for new documents
- Deliver an evaluation report

**Cover letter**

You want "Build an internal Q&A assistant for nonprofit policies" delivered (a working chatbot with source citations, an ingestion script for new documents, an evaluation report), and the part that decides success is usually rag.

On rag: I used rag to ground answers in the client's own documents [aiml-case-17]. On langchain: I used langchain to wire the prompts, retrievers and output parsers [aiml-case-07]. On vector databases: in one typed codebase with a small CLI [aiml-case-11].

My plan: confirm the scope and acceptance criteria in a short call, deliver a first working version early, then iterate with you on the details.

I propose $85/hr for this scope. Could you share what a successful first milestone looks like for you?

**Screening answers**
- **Q:** What is your experience with rag?
  **A:** Yes. I used rag to ground answers in the client's own documents [aiml-case-17].


---

## jp-25 · Power BI dashboard for healthcare KPIs

*Persona:* data · *Budget:* hourly 33.0-57.0 · *Job id:* d-data-022

**Requirements**
- Experience with power bi
- Experience with sql
- Experience with dashboard design
- Experience with excel
- Deliver a Power BI report
- Deliver documented measures
- Deliver a refresh schedule

**Cover letter**

You want "Power BI dashboard for healthcare KPIs" delivered (a Power BI report, documented measures, a refresh schedule), and the part that decides success is usually power bi.

On power bi: We tracked a small set of numbers weekly and dropped anything nobody looked at [data-case-13]. On sql: I used sql to model and query the sales data [data-case-01]. On dashboard design: Data analyst who turns messy exports into dashboards people actually open [data-cv].

My plan: confirm the scope and acceptance criteria in a short call, deliver a first working version early, then iterate with you on the details.

I propose $55/hr for this scope. Could you share what a successful first milestone looks like for you?

**Screening answers**
- **Q:** What is your availability in the next two weeks?
  **A:** Yes. We tracked a small set of numbers weekly and dropped anything nobody looked at [data-case-13].
- **Q:** What is your experience with power bi?
  **A:** Yes. We tracked a small set of numbers weekly and dropped anything nobody looked at [data-case-13].
- **Q:** How would you approach a Power BI report?
  **A:** Yes. We tracked a small set of numbers weekly and dropped anything nobody looked at [data-case-13].


---

## jp-26 · Deduplicate and standardise CRM exports

*Persona:* data · *Budget:* fixed 980.0-1470.0 · *Job id:* d-data-099

**Requirements**
- Experience with excel
- Experience with data cleaning
- Experience with pandas
- Deliver a cleaned master file
- Deliver a repeatable cleaning script

**Cover letter**

You want "Deduplicate and standardise CRM exports" delivered (a cleaned master file, a repeatable cleaning script), and the part that decides success is usually excel.

On excel: shipped a fix [data-cv]. On data cleaning: CRM Deduplication and Clean-Up [data-case-07]. On pandas: the code in this repository uses pandas [data-repo-04].

My plan: confirm the scope and acceptance criteria in a short call, deliver a first working version early, then iterate with you on the details.

I propose $1615 fixed for this scope. Could you share what a successful first milestone looks like for you?

**Screening answers**
- **Q:** What is your availability in the next two weeks?
  **A:** Yes. shipped a fix [data-cv].
- **Q:** Describe a similar project you have delivered.
  **A:** Yes. shipped a fix [data-cv].
- **Q:** How would you approach a cleaned master file?
  **A:** Yes. shipped a fix [data-cv].


---

## jp-27 · Analyse our A/B test results

*Persona:* data · *Budget:* fixed 280.0-420.0 · *Job id:* d-data-177

**Requirements**
- Experience with a/b testing
- Experience with statistics
- Experience with python
- Deliver a written readout
- Deliver a reproducible notebook

**Cover letter**

You want "Analyse our A/B test results" delivered (a written readout, a reproducible notebook), and the part that decides success is usually a/b testing.

On a/b testing: I used regression to separate [removed] from noise [data-case-03]. On statistics: This engagement started with a complaint from the operations lead: the district had ten years of results in separate spreadsheets [data-case-15]. On python: data quality, python, plus the usual tooling [data-case-07].

My plan: confirm the scope and acceptance criteria in a short call, deliver a first working version early, then iterate with you on the details.

I propose $455 fixed for this scope. Could you share what a successful first milestone looks like for you?

**Screening answers**
- **Q:** What is your availability in the next two weeks?
  **A:** Yes. I used regression to separate [removed] from noise [data-case-03].
- **Q:** How would you approach a written readout?
  **A:** Yes. I used regression to separate [removed] from noise [data-case-03].
- **Q:** What is your experience with a/b testing?
  **A:** Yes. I used regression to separate [removed] from noise [data-case-03].


---

## jp-28 · Live collaboration features with WebSockets

*Persona:* fullstack · *Budget:* hourly 55.0-96.0 · *Job id:* d-fullstack-032

**Requirements**
- Experience with websockets
- Experience with redis
- Experience with node.js
- Experience with react
- Deliver real-time messaging
- Deliver presence indicators
- Deliver load test results

**Cover letter**

You want "Live collaboration features with WebSockets" delivered (real-time messaging, presence indicators, load test results), and the part that decides success is usually websockets.

On websockets: react, websockets, plus the usual tooling [fullstack-case-03]. On redis: I used redis to cache sessions and rate limits [fullstack-case-12]. On node.js: oauth, node.js, plus the usual tooling [fullstack-case-15].

My plan: confirm the scope and acceptance criteria in a short call, deliver a first working version early, then iterate with you on the details.

I propose $70/hr for this scope. Could you share what a successful first milestone looks like for you?

**Screening answers**
- **Q:** How would you approach real-time messaging?
  **A:** Yes. react, websockets, plus the usual tooling [fullstack-case-03].
- **Q:** Which part of this project do you see as the biggest risk?
  **A:** Yes. react, websockets, plus the usual tooling [fullstack-case-03].


---

## jp-29 · Next.js SaaS dashboard with Stripe billing

*Persona:* fullstack · *Budget:* fixed 11960.0-17930.0 · *Job id:* d-fullstack-046

**Requirements**
- Experience with react
- Experience with typescript
- Experience with stripe
- Experience with postgresql
- Deliver a deployed web app
- Deliver Stripe subscription billing
- Deliver an admin area

**Cover letter**

You want "Next.js SaaS dashboard with Stripe billing" delivered (a deployed web app, Stripe subscription billing, an admin area), and the part that decides success is usually react.

On react: React.js, TS, plus the usual tooling [fullstack-case-17]. On typescript: I used typescript to keep the front and back end type-safe [fullstack-case-08]. On stripe: The first version was deliberately boring, and that is why it shipped on time [fullstack-case-01].

My plan: confirm the scope and acceptance criteria in a short call, deliver a first working version early, then iterate with you on the details.

I propose $19725 fixed for this scope. Could you share what a successful first milestone looks like for you?



---

## jp-30 · LangGraph agent to automate hospitality back-office work

*Persona:* aiml · *Budget:* fixed 3490.0-5240.0 · *Job id:* d-aiml-004

**Requirements**
- Experience with langgraph
- Experience with langchain
- Experience with python
- Experience with fastapi
- Deliver an agent workflow with approval steps
- Deliver an API endpoint
- Deliver deployment notes

**Cover letter**

You want "LangGraph agent to automate hospitality back-office work" delivered (an agent workflow with approval steps, an API endpoint, deployment notes), and the part that decides success is usually langgraph.

On langgraph: Measured against the old process, it saved [aiml-case-13]. On langchain: I used langchain to wire the prompts, retrievers and output parsers [aiml-case-07]. On python: nlp, python3, plus the usual tooling [aiml-case-08].

My plan: confirm the scope and acceptance criteria in a short call, deliver a first working version early, then iterate with you on the details.

I propose $5470 fixed for this scope. Could you share what a successful first milestone looks like for you?

**Screening answers**
- **Q:** Which part of this project do you see as the biggest risk?
  **A:** Yes. Measured against the old process, it saved [aiml-case-13].
