# MarketForge AI

**UK AI Job Market Intelligence Platform — Core Package**

Autonomous multi-department agentic AI system that continuously monitors, analyses, and distils the UK AI/ML job market into actionable intelligence. Nine specialised departments — each a compiled LangGraph `StateGraph` — run on a twice-weekly schedule and produce skill demand rankings, salary benchmarks, sponsorship rates, career gap analysis, and emerging research signals.

[![CI](https://github.com/viraj97-sl/marketforge-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/viraj97-sl/marketforge-ai/actions)
![Python 3.11](https://img.shields.io/badge/python-3.11-blue)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2.x-green)
![PostgreSQL 16](https://img.shields.io/badge/PostgreSQL-16-blue)

---

## Repository layout (3-repo architecture)

| Repo | Purpose |
|---|---|
| **`marketforge-ai`** ← you are here | Core Python package: all 9 agents, LangGraph graphs, ML/NLP pipelines |
| [`marketforge-backend`](https://github.com/Viraj97-SL/marketforge-backend) | FastAPI + APScheduler worker — imports core as a git dependency |
| `marketforge-frontend` | Next.js frontend dashboard |

The backend and frontend consume this package. Agent and graph code lives here only — never duplicated.

---

## What It Does

| Capability | Detail |
|---|---|
| **Job ingestion** | Scrapes Adzuna, Reed, Wellfound, specialist boards — ~200–800 roles/run |
| **NLP extraction** | 3-gate pipeline: taxonomy exact match → spaCy NER → Gemini LLM fallback |
| **Market analysis** | Skill demand index, salary percentiles, sponsorship rates, city distribution |
| **Career advisor** | Enter skills manually → AI gap analysis benchmarked against live data |
| **CV analyser** | Upload PDF/DOCX → instant ATS score (0–100, A+→D), skill gap plan, GDPR-compliant |
| **Research signals** | arXiv + tech blogs monitored; predicts emerging skills 4–8 weeks early |
| **Weekly report** | Auto-generated LinkedIn-quality market briefing |
| **LangSmith tracing** | Every graph run traced end-to-end — interactive node view in Studio |

---

## Architecture

Nine departments, each a compiled LangGraph `StateGraph` wrapping a `DeepAgent` hierarchy (Plan → Execute → Reflect → Output lifecycle). All state persists in the `market` schema in PostgreSQL via `AsyncPostgresSaver` on Railway; falls back to `MemorySaver` for local dev.

```
  START
    │
    ▼
 dept1_data_collection   ──►  dept7_qa_post_ingestion
    │                               │
    │ (qa_pass)                     │
    ▼                               │
 dept3_market_analysis              │
    │                               │
    ▼                               │
 dept4_research_intelligence        │
    │                               │
    ▼                               │
 dept5_content_studio               │
    │                               │
    ▼                               │
 dept7_qa_pre_dispatch  ◄───────────┘
    │
    ▼
 finalize_pipeline  ──►  END
```

Parallel fan-out patterns per department:

| # | Department | Graph pattern |
|---|---|---|
| 1 | Data Collection | `Send` API — 8 scrapers in parallel |
| 2 | ML Engineering | Conditional drift check → retrain or evaluate |
| 3 | Market Analysis | 7 analyst nodes in parallel → `compile_snapshot` fan-in |
| 4 | Research Intelligence | `arxiv_monitor` + `emerging_signal` parallel → merge |
| 5 | Content Studio | Linear: load → generate → write → self_review |
| 6 | User Insights | Security gate → parse → gaps → sector_fit → narrative |
| 7 | QA & Testing | 3 parallel health checks → merge → conditional report |
| 8 | Security | Linear: sanitise → inject_detect → scrub_pii → validate → log |
| 9 | Ops & Observability | 3 parallel health nodes → merge → dispatch_alerts |

| # | Department | Lead Agent | Responsibility |
|---|---|---|---|
| 1 | Data Collection | `DataCollectionLeadAgent` | Ingest 15+ UK job sources via connectors |
| 2 | ML Engineering | `MLEngineerLeadAgent` | Feature engineering, PSI drift, model registry gate |
| 3 | Market Analysis | `MarketAnalystLeadAgent` | Skill demand trends, salary intelligence, sponsorship |
| 4 | Research Intelligence | `ResearchLeadAgent` | arXiv monitoring, emerging tech signal detection |
| 5 | Content Studio | `ContentLeadAgent` | Weekly LinkedIn-quality market report |
| 6 | User Insights | `UserInsightsLeadAgent` | Personalised career gap analysis |
| 7 | QA & Testing | `QALeadAgent` | Data integrity, LLM output validation, model drift |
| 8 | Security | `SecurityLeadAgent` | Input sanitisation, PII scrubbing, prompt injection defence |
| 9 | Ops & Observability | `OpsLeadAgent` | Cost tracking, pipeline health, alert dispatch |

---

## Tech Stack

| Layer | Technology | Version |
|---|---|---|
| Agent orchestration | LangGraph | 0.2.x |
| Graph checkpointing | langgraph-checkpoint-postgres + AsyncPostgresSaver | 2.x |
| Pipeline scheduling | APScheduler (Railway) / Apache Airflow (local) | 3.x / 2.9.x |
| LLM | Google Gemini 2.5 Flash + Pro | — |
| LLM observability | LangSmith Studio | — |
| ML tracking | MLflow | 2.x |
| NLP (gate 2) | spaCy + en_core_web_sm | 3.8.x |
| Embeddings / dedup | sentence-transformers MiniLM | 3.x |
| Taxonomy matching | flashtext | 2.7 |
| Primary database | PostgreSQL (Railway) | 16 |
| Cache | Redis (Railway) | 7.x |
| Vector store | ChromaDB | — |
| REST API | FastAPI + uvicorn | — |
| Dashboard | Streamlit | — |
| Metrics | Prometheus | 2.52 |

---

## Project Structure

```
marketforge-ai/
├── src/marketforge/
│   ├── agents/
│   │   ├── graphs/                  # LangGraph compiled StateGraphs (one per dept)
│   │   │   ├── states.py            # TypedDict state definitions (Annotated reducers)
│   │   │   ├── data_collection.py   # Dept 1 — Send API fan-out
│   │   │   ├── ml_engineering.py    # Dept 2 — conditional drift/retrain
│   │   │   ├── market_analysis.py   # Dept 3 — 7 parallel nodes
│   │   │   ├── research.py          # Dept 4
│   │   │   ├── content_studio.py    # Dept 5
│   │   │   ├── user_insights.py     # Dept 6 — stateless per-request
│   │   │   ├── qa_testing.py        # Dept 7
│   │   │   ├── security.py          # Dept 8 — no checkpointer, always linear
│   │   │   ├── ops_monitor.py       # Dept 9
│   │   │   └── master.py            # Top-level pipeline chaining all depts
│   │   ├── base.py                  # DeepAgent ABC (Plan→Execute→Reflect→Output)
│   │   ├── data_collection/         # Dept 1 sub-agents + lead
│   │   ├── ml_engineering/          # Dept 2 sub-agents + lead
│   │   ├── market_analysis/         # Dept 3 sub-agents + lead
│   │   ├── research/                # Dept 4 sub-agents + lead
│   │   ├── content_studio/          # Dept 5 sub-agents + lead
│   │   ├── user_insights/           # Dept 6 sub-agents + lead
│   │   ├── qa_testing/              # Dept 7 sub-agents + lead
│   │   ├── security/                # Dept 8 sub-agents + lead + guardrails
│   │   └── ops_monitor/             # Dept 9 sub-agents + lead
│   ├── cv/                          # CV analysis module (GDPR-compliant, in-memory)
│   │   ├── scanner.py               # Magic bytes, PDF JS detection, ClamAV
│   │   ├── parser.py                # PDF (pdfplumber → pypdf) + DOCX
│   │   ├── ats_scorer.py            # 5-dimension ATS score (A+→D)
│   │   ├── gdpr.py                  # PII scrubbing, consent gate, anonymous token
│   │   └── gap_analyser.py          # demand × salary × recency scoring
│   ├── memory/
│   │   ├── postgres.py              # Engines, stores, get_pg_checkpointer()
│   │   └── redis_cache.py           # DashboardCache with TTL + invalidation
│   ├── ml/                          # Trained model wrappers (prescreen, salary, etc.)
│   ├── models/                      # Pydantic data models
│   ├── nlp/
│   │   └── taxonomy.py              # Gate1 (flashtext), Gate2 (spaCy), Gate3 (Gemini)
│   ├── config/
│   │   └── settings.py              # Pydantic BaseSettings — all env vars
│   └── utils/
│       ├── cost_tracker.py
│       └── logger.py
├── tests/
│   ├── test_graphs/
│   │   └── test_smoke.py            # 15 smoke tests — zero DB/LLM I/O
│   ├── test_cv/
│   ├── test_core.py
│   └── ...
├── scripts/
│   ├── bootstrap.py                 # DB init + taxonomy seed
│   └── run_pipeline.py              # Manual one-shot pipeline runner
├── airflow/dags/                    # Airflow DAGs (local dev only)
├── dashboard/app.py                 # 7-page Streamlit dashboard
├── pyproject.toml
└── .env                             # API keys + DB URLs (never commit)
```

---

## Quick Start

### Prerequisites

- Python 3.11
- Docker Desktop (for PostgreSQL + Redis locally)
- Google Gemini API key ([AI Studio](https://aistudio.google.com/) — free tier)
- Adzuna API key (free — [register](https://developer.adzuna.com/))
- Reed API key (free — [register](https://www.reed.co.uk/developers/jobseeker))

### 1 — Clone and install

```bash
git clone https://github.com/viraj97-sl/marketforge-ai.git
cd marketforge-ai
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -e ".[dev]"
python -m spacy download en_core_web_sm
```

### 2 — Configure environment

Create a `.env` file in the project root (never commit it):

```env
# ── Database ─────────────────────────────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://marketforge:marketforge@localhost:5432/marketforge
DATABASE_URL_SYNC=postgresql+psycopg2://marketforge:marketforge@localhost:5432/marketforge
REDIS_URL=redis://localhost:6379/0

# ── LLM ──────────────────────────────────────────────────────────────────────
GEMINI_API_KEY=your_gemini_api_key

# ── Scraping APIs ─────────────────────────────────────────────────────────────
ADZUNA_APP_ID=your_adzuna_app_id
ADZUNA_APP_KEY=your_adzuna_app_key
REED_API_KEY=your_reed_api_key
TAVILY_API_KEY=your_tavily_key

# ── LangSmith tracing (required for Studio graph view) ───────────────────────
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_key
LANGCHAIN_PROJECT=marketforge-ai
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com

# ── MLflow ────────────────────────────────────────────────────────────────────
MLFLOW_TRACKING_URI=http://localhost:5001
```

### 3 — Start infrastructure

```bash
docker-compose up -d postgres redis
# Wait ~10 seconds for PostgreSQL to initialise
python scripts/bootstrap.py    # creates all tables + seeds skill taxonomy
```

### 4 — Run the pipeline

```bash
python scripts/run_pipeline.py
```

### 5 — Start API + dashboard (for local dev)

```bash
# API
uvicorn api.main:app --reload --port 8000
# PYTHONPATH not needed — package is installed via pip install -e .

# Dashboard
streamlit run dashboard/app.py
```

API docs at `http://localhost:8000/docs`. Dashboard at `http://localhost:8501`.

---

## LangSmith Studio — viewing graph traces

With `LANGCHAIN_TRACING_V2=true` and `LANGCHAIN_API_KEY` set in `.env`, every `graph.ainvoke()` call automatically traces to LangSmith. No code changes needed.

**To view:**
1. Trigger any pipeline run (e.g. `python scripts/run_pipeline.py` or call `/api/v1/career/analyse`)
2. Go to [studio.langsmith.com](https://studio.langsmith.com) → **Projects** → **marketforge-ai**
3. Click any run → **View Trace** → interactive node graph with input/output at each node

**To browse graphs without running a pipeline** (view structure only):
```python
from marketforge.agents.graphs import master_graph, security_graph
# These objects are compiled StateGraphs — import them in a Python session
# and LangSmith will show the static graph structure if LANGCHAIN_TRACING_V2=true
```

---

## Pipeline schedule (Railway / production)

APScheduler in `worker.py` triggers the same schedule as the Airflow DAGs:

```
Tuesday  + Thursday  07:00 UTC  — full ingestion (scrape → NLP → market analysis)
Monday               07:00 UTC  — weekly analysis only (snapshot + report, no scrape)
Sunday               02:00 UTC  — model retrain (PSI drift check → retrain if needed)
Every 6h                        — Redis cache refresh
```

For local one-off runs: `python scripts/run_pipeline.py`

---

## Smoke tests

```bash
pytest tests/test_graphs/test_smoke.py -v
```

15 tests, no DB or LLM required. Covers: all 10 graphs importable, security graph injection detection, PII scrubbing, field length enforcement, checkpointer fallback, state TypedDicts.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/health` | System status, data freshness, job count |
| `GET` | `/api/v1/market/snapshot` | Latest weekly snapshot (skills, salary, sponsorship) |
| `GET` | `/api/v1/market/skills` | Skill demand by role category |
| `GET` | `/api/v1/market/trending` | Rising / declining skills (week-on-week) |
| `GET` | `/api/v1/market/salary` | Salary benchmarks |
| `POST` | `/api/v1/career/analyse` | Career gap analysis (LangGraph security gate → SBERT → Gemini) |
| `POST` | `/api/v1/career/cv-analyse` | Upload PDF/DOCX → ATS score + skill gap plan (GDPR-compliant) |
| `GET` | `/api/v1/jobs` | Browse indexed roles with filters |
| `GET` | `/api/v1/pipeline/runs` | Recent pipeline execution history |
| `GET` | `/metrics` | Prometheus metrics |

---

## NLP Extraction Pipeline

```
Description text
      │
      ▼
 Gate 1 — flashtext taxonomy match   (~85–90% of extractions, zero-cost)
      │
      ▼
 Gate 2 — spaCy NER (en_core_web_sm) (~8–12%, catches novel entities)
      │
      ▼
 Gate 3 — Gemini Flash LLM fallback  (~2–5%, highest recall ~$0.002/job)
```

---

## Cost Model

| Item | Cost |
|---|---|
| Gemini Flash (gate 3, ~50 jobs/run) | ~$0.02/run |
| Gemini 2.5 Pro (career analysis, on-demand) | ~$0.01/query |
| PostgreSQL (Railway) | ~$0/month (hobby tier) |
| Redis (Railway) | ~$0/month (hobby tier) |
| **Total at 2 runs/week** | **~$0.20–0.40/month** |

---

## Local Services

| Service | URL | Credentials |
|---|---|---|
| Dashboard | http://localhost:8501 | — |
| FastAPI docs | http://localhost:8000/docs | — |
| MLflow | http://localhost:5001 | — |
| Prometheus | http://localhost:9090 | — |
| PostgreSQL | localhost:5432 | marketforge / marketforge |
| Redis | localhost:6379 | — |

---

## Author

Viraj Bulugahapitiya ·AI Engineer - MSc Data Science (University of Hertfordshire, UK) · 2026

Portfolio project demonstrating production-grade AI engineering: LangGraph multi-agent orchestration, NLP pipelines, async FastAPI, Railway-deployed PostgreSQL + Redis, MLflow, LangSmith tracing — sub-$5/month infrastructure budget.
#