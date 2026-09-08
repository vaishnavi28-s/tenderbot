# TenderBot: Agentic Procurement Intelligence

**A Multi-Agent Orchestration System for German Public Tender Intelligence**

<img width="1169" height="825" alt="Gemini_Generated_Image_xqb02ixqb02ixqb0" src="https://github.com/user-attachments/assets/9ad5d1de-78dc-4edc-be34-a3e48784a64b" />



TenderBot is a multi-language (Python/TypeScript) AI pipeline that automates the discovery, verification, and enrichment of German public procurement tenders (service.bund.de). It's a public-data rebuild of a LangGraph tender-intelligence agent originally built for Bertelsmann, reconstructed on public data to work around the original's confidentiality constraints. It uses a **Hybrid RAG** approach combining **Semantic Vector Search** with **Text2SQL**.

---
## How it works

**1. Discovery** - `fetch_tenders.py` searches service.bund.de's RSS feed across 3 procurement categories, crawls each tender's announcement page via Selenium and extracts raw content.

**2. Enrichment** - Raw text is passed to a TypeScript service (Mastra), where an LLM agent classifies sector, extracts keywords and generates a summary.

**3. Verification (4 independent checks)**
- **LangGraph** - live web search confirms the tender genuinely exists
- **CrewAI** - a two-agent crew: one cross-checks facts, one writes the final structured record
- **DeepEval** - an independent LLM-as-a-Judge scores summary faithfulness
- **LangGraph (deterministic)** - a second, non-AI graph compares every claimed fact against the raw source text directly

**4. Fit scoring** - An LLM agent compares eligibility criteria against a company profile, returning a tiered rating (Great/Good/Partial/Low fit/Unclear).

**5. Storage**
- **Qdrant** - vector store enabling semantic search (e.g. "IT tenders under €500k" matches by meaning, not exact keywords)
- **PostgreSQL** - archives raw source text and logs failed processing attempts

**6. Interface**
- **Backend** (FastAPI + Strawberry GraphQL) - resolves queries against Qdrant, Postgres and the LLM
- **Frontend** (React) - search interface, tender table, fit-tier badges

**7. Observability** - LangSmith traces every LangGraph run (input, output, latency) which is how a production bug in the verification logic was identified and confirmed fixed.

**8. Alerting** - n8n sends an email notification when the fact-check guardrail flags a tender.
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
Fill in API keys in .env

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
