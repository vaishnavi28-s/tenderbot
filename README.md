# TenderBot: Agentic Procurement Intelligence

**A Multi-Agent Orchestration System for German Public Tender Intelligence**
<img width="1169" height="825" alt="Gemini_Generated_Image_xqb02ixqb02ixqb0" src="https://github.com/user-attachments/assets/9ad5d1de-78dc-4edc-be34-a3e48784a64b" />



TenderBot is a multi-language (Python/TypeScript) AI pipeline that automates the discovery, verification, and enrichment of German public procurement tenders (service.bund.de). It's a public-data rebuild of a LangGraph tender-intelligence agent originally built for Bertelsmann, reconstructed on public data to work around the original's confidentiality constraints. It uses a **Hybrid RAG** approach combining **Semantic Vector Search** with **Text2SQL**.

---

## How it Works

### The "Intelligence" Loop

We achieve high-fidelity procurement data through a five-stage **"Data Refinery"** process:

1. **Discovery (The Signal):** `fetch_tenders.py` monitors service.bund.de via RSS across three categories (digitalisierung, scandienstleistungen, wahlunterlagen), crawling announcement pages with Selenium + crawl4ai.
2. **Enrichment (The Scout):** **TypeScript (Mastra)** agents extract sector, keywords, and summary from collected content — deterministic fields (title, deadline, authority) are never re-derived by the LLM.
3. **Validation (The Gatekeeper):** A **Python (LangGraph/CrewAI)** layer performs an automated "Double-Check," using Tavily web search to verify the tender genuinely exists.
4. **Auditing (Three Layers):** Data passes through **DeepEval** (LLM-as-a-Judge faithfulness scoring), a second **LangGraph** fact-check guardrail that compares AI-claimed facts against the raw crawled source text, and a **fit-check** that evaluates eligibility against a company profile.
5. **Alerting (The Human Touch):** When the fact-check guardrail flags a tender, **n8n** sends an email alert for manual review.

### Smart Discovery

#### Semantic Search
Users search naturally (e.g., *"IT tenders under €500k"*) via our **Qdrant** vector store matching intent to tender characteristics.

#### Analytical Intelligence (Text2SQL)
Via **Text2SQL**, users ask analytical questions (e.g., *"how many tenders are open this month"*). The system generates and executes SQL against our **PostgreSQL** archive.

#### Fit Scoring
A LinkedIn-style eligibility check compares each tender's requirements against a company profile — category-aware, so an IT tender is judged on IT/cloud-relevant fields, not scanning- or election-specific ones.

---

## The Technical Architecture

* **Multi-Agent Orchestration:**
  * **LangGraph:** Two separate graphs — existence verification, and the fact-check guardrail (with real conditional branching).
  * **CrewAI:** A sequential two-agent crew — fact-checker, then procurement analyst.
  * **Mastra:** TypeScript agent layer for enrichment.

* **LLM Infrastructure:**
  * **LiteLLM:** Unified gateway with fallbacks across **Gemini, Groq, OpenRouter** (Cerebras/SambaNova removed after both required payment on this account).
  * **LangSmith:** Tracing for both LangGraph workflows.

* **Data Strategy & Storage:**
  * **Qdrant:** Vector DB for semantic search.
  * **PostgreSQL:** Raw crawled source text archive + historical tender archive for Text2SQL.
  * **n8n:** Fact-check-flagged-tender email alerting.

* **Reliability & Evaluation:**
  * **DeepEval:** LLM-as-a-Judge faithfulness auditing.
  * **Fact-Check Guardrail:** Deterministic (non-AI) comparison of claimed facts against source text — catches hallucinated details like fabricated reference numbers.

* **Interface Layer:**
  * **GraphQL (Strawberry)** + **REST (FastAPI)** + **Uvicorn**.
  * **React dashboard:** deadline urgency, fit tier, and estimated value — replacing an earlier map-based UI, since geography isn't decision-relevant for tenders the way it is for events.

---

## Step-by-Step Deployment Guide

### 1. Initial Setup
```bash
git clone https://github.com/vaishnavi28-s/tenderbot.git
cd tenderbot
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cd frontend && npm install
cd ../my_mastra_app && npm install
```
Copy `.env.example` to `.env` and fill in API keys.

### 2. Infrastructure Initialization
```bash
docker-compose up -d
```

### 3. LLM Proxy Gateway
```bash
litellm --config litellm_config.yaml --port 4000 --drop_params
```

### 4. Agentic Validation Engine
```bash
cd agents_python && python main.py
```

### 5. Mastra Signal Processor
```bash
cd my_mastra_app && npx tsx src/server.ts
```

### 6. Run the Discovery Pipeline
```bash
cd agents_python && python fetch_tenders.py
```

### 7. (Optional) Fact-Check Alerts via n8n
Import `n8n/FactCheckAlert.json` into a running n8n instance for email alerts on flagged tenders.

### 8. GraphQL Backend
```bash
cd backend && python main.py
```

### 9. Launch the Dashboard
```bash
cd frontend && npm start
```
