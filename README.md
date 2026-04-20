# MarketForge AI — Core Intelligence Package

**UK AI/ML Job Market Intelligence Platform · 9-Department Autonomous Agent System**

[![CI](https://github.com/viraj97-sl/marketforge-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/viraj97-sl/marketforge-ai/actions)
![Python 3.11](https://img.shields.io/badge/python-3.11-blue)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2.x-green)
![PostgreSQL 16](https://img.shields.io/badge/PostgreSQL-16-blue)
![Redis](https://img.shields.io/badge/Redis-7.x-red)
![Gemini 2.5](https://img.shields.io/badge/Gemini-2.5-orange)
![LangSmith](https://img.shields.io/badge/LangSmith-traced-purple)

> Live at **[marketforge.digital](https://marketforge.digital)**

---

## What Is This?

MarketForge AI is a production-grade AI system that continuously monitors the **UK AI/ML job market** — scraping, extracting, analysing, and surfacing intelligence that job-seekers, hiring managers, and researchers actually use.

It is **not** a job board or a CV-matching app. It is a market intelligence engine: automated data collection from 15+ UK job sources, 3-gate NLP skill extraction, statistical market analysis across 9 parallel LangGraph agents, and a natural-language career advisor — all running on a sub-$5/month infrastructure budget.

### Core Capabilities

| Feature | Detail |
|---|---|
| **Job ingestion** | Scrapes Adzuna, Reed, Wellfound, specialist boards — ~200–800 roles/run with MinHash LSH dedup |
| **3-gate NLP extraction** | flashtext taxonomy → spaCy NER → Gemini Flash fallback — extracts 109 canonical skills + 259 aliases |
| **Market snapshots** | Weekly skill demand rankings, salary p25/p50/p75, sponsorship rates, city distribution |
| **Career gap advisor** | Skills input → SBERT semantic similarity vs live job embeddings → Gemini 2.5 Pro narrative + 90-day action plan |
| **CV analyser** | Upload PDF/DOCX → deterministic 5-dimension ATS score (A+→D) + ML-ranked skill gap plan — zero data retained, GDPR-compliant |
| **Research signals** | arXiv + tech blog monitoring → predicts emerging skills 4–8 weeks before they peak in job postings |
| **Weekly report** | Auto-generated LinkedIn-quality market briefing dispatched via email every Monday |
| **Full observability** | Every LangGraph node traced in LangSmith Studio with per-node input/output |

---

## Three-Repo Architecture

| Repo | Role | Deployed on |
|---|---|---|
| **`marketforge-ai`** ← you are here | Core package: all 9 agents, LangGraph graphs, ML/NLP pipelines, CV analyser | Installed as git package into backend |
| [`marketforge-backend`](https://github.com/Viraj97-SL/marketforge-backend) | FastAPI REST API + APScheduler pipeline worker | Railway |
| `marketforge-frontend` | Next.js 14 dashboard | Vercel |

All agent intelligence lives here. The backend and frontend consume this package — no agent code is duplicated across repos.

---

## Full Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│  INGESTION  (Tue + Thu 07:00 UTC)                                   │
│                                                                     │
│  Adzuna · Reed · Wellfound · ATS Direct · specialist boards         │
│       ↓  ~525 raw jobs per run                                      │
│  DeduplicationCoordinatorAgent                                      │
│    ├── exact hash dedup  (SHA-256[:16] of title+company+location)   │
│    ├── MinHash LSH       (near-duplicate detection)                 │
│    └── SBERT cross-run similarity                                   │
│       ↓  ~9 genuinely new jobs pass filter                          │
│  DataCollectionLeadAgent                                            │
│    ├── touch_scraped_at(ALL 525 raw job_ids) ← refreshes timestamps │
│    └── upsert_job() for new jobs  (ON CONFLICT DO UPDATE scraped_at)│
│       ↓                                                             │
│  market.jobs  (PostgreSQL)                                          │
└─────────────────────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────────────────────┐
│  NLP EXTRACTION  (worker.py job_ingest)                             │
│                                                                     │
│  Gate 1 — flashtext taxonomy    ~85–90%  zero cost, O(n) Aho-Corasick│
│  Gate 2 — spaCy NER             ~8–12%  fast, catches novel entities │
│  Gate 3 — Gemini Flash fallback ~2–5%   ~$0.002/job, highest recall │
│  Fallback — role-implied skills  confidence=0.6, method=role_inference│
│       ↓                                                             │
│  market.job_skills  (PostgreSQL)                                    │
└─────────────────────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────────────────────┐
│  MARKET ANALYSIS  (LangGraph Dept 3 — 7 parallel nodes)             │
│                                                                     │
│  skill_demand ─┐                                                    │
│  salary_intel ─┤                                                    │
│  sponsorship  ─┤                                                    │
│  velocity     ─┼──→ compile_snapshot fan-in                         │
│  cooccurrence ─┤                                                    │
│  geo_dist     ─┤                                                    │
│  techstack    ─┘                                                    │
│       ↓                                                             │
│  market.weekly_snapshots  (PostgreSQL)                              │
└─────────────────────────────────────────────────────────────────────┘
              ↓
  FastAPI /api/v1/market/snapshot  →  Next.js dashboard
```

---

## Nine-Department Agent Architecture

Every department is a compiled LangGraph `StateGraph`. Every agent follows the **DeepAgent** lifecycle:

```
Plan() → Execute() → Reflect() → Output()
```

All agent methods are `async`. Graphs use `MemorySaver` (pipeline runs are stateless; avoids msgpack serialization overhead from PostgreSQL checkpointer).

```
  MASTER PIPELINE
  ───────────────
  dept1_data_collection  ──►  dept7_qa_post_ingestion
        │ (qa_pass)                   │
        ▼                             │
  dept3_market_analysis               │
        │                             │
        ▼                             │
  dept4_research_intelligence         │
        │                             │
        ▼                             │
  dept5_content_studio                │
        │                             │
        ▼                             ▼
  dept7_qa_pre_dispatch  ◄────────────┘
        │
        ▼
  finalize_pipeline  ──►  END
```

| # | Department | Lead Agent | Graph Pattern | Key Responsibility |
|---|---|---|---|---|
| 1 | Data Collection | `DataCollectionLeadAgent` | `Send` API — 8 scrapers in parallel | Ingest 15+ UK job sources, dedup, upsert |
| 2 | ML Engineering | `MLEngineerLeadAgent` | Conditional drift → retrain or evaluate | PSI drift gate, model registry, feature engineering |
| 3 | Market Analysis | `MarketAnalystLeadAgent` | 7 analyst nodes in parallel → fan-in | Skill demand index, salary benchmarks, sponsorship rates |
| 4 | Research Intelligence | `ResearchLeadAgent` | `arxiv_monitor` + `emerging_signal` → merge | arXiv monitoring, emerging-skill signal detection |
| 5 | Content Studio | `ContentLeadAgent` | Linear: load → generate → write → self_review | Weekly LinkedIn-quality market briefing |
| 6 | User Insights | `UserInsightsLeadAgent` | Security gate → parse → gaps → sector_fit → narrative | Personalised career gap analysis |
| 7 | QA & Testing | `QALeadAgent` | 3 parallel health checks → merge → conditional report | Data integrity, LLM output validation, model drift |
| 8 | Security | `SecurityLeadAgent` | Linear, no checkpointer | Input sanitisation, PII scrubbing, prompt-injection defence |
| 9 | Ops & Observability | `OpsLeadAgent` | 3 parallel health nodes → merge → dispatch | Cost tracking, pipeline health, alert dispatch |

---

## CV Analyser — Technical Detail

The CV analyser is a pure in-memory pipeline. No file, extracted text, or PII ever touches the database.

```
Upload (PDF / DOCX ≤ 5 MB)
        ↓
 Security scan
   ├── Magic-bytes file type verification (not extension-based)
   ├── PDF JavaScript execution detection
   └── AV signature scanning
        ↓
 Parser
   ├── PDF: pdfplumber (layout-aware) → pypdf fallback
   └── DOCX: python-docx paragraph extraction
        ↓
 GDPR layer
   ├── Explicit consent gate (403 if consent=false)
   ├── PII scrub: email · UK phone · NI number · postcode · DOB · street address
   ├── Anonymous session token (secrets.token_hex — no PII)
   └── Original bytes discarded immediately after parse
        ↓
 ATS Scorer  (deterministic, no LLM — fast and auditable)
   ├── keyword_match   35%  — CV skills vs top market demand for target role
   ├── structure       20%  — section presence, action verbs, quantified bullets
   ├── readability     15%  — Flesch-Kincaid grade level (target 10–14)
   ├── completeness    20%  — required fields, date ranges, contact info
   └── format_safety   10%  — ATS-hostile elements (tables, images, page count)
        ↓
 Grade: A+ ≥90 · A ≥80 · B ≥70 · C ≥60 · D <60
        ↓
 Gap Analyser  (ML-ranked, demand × salary × recency scoring)
   ├── short_term bucket: quick-win certifications (0–3 months)
   ├── mid_term bucket:   portfolio projects (3–12 months)
   └── long_term bucket:  deep specialisation (12+ months)
        ↓
 LLM Gap Plan  (Gemini 2.5 Flash — seeded with ML-ranked buckets, never raw CV text)
        ↓
 Output guardrails  →  CVAnalysisReport (data_retained=False guaranteed)
```

---

## Tech Stack

| Layer | Technology | Version |
|---|---|---|
| Agent orchestration | **LangGraph** | 0.2.x |
| Graph state | `MemorySaver` | — |
| LLM — deep analysis | **Gemini 2.5 Pro** | — |
| LLM — fast extraction | **Gemini 2.5 Flash** | — |
| Embeddings | **sentence-transformers MiniLM-L6-v2** | 3.x |
| Keyword NLP | **flashtext** | 2.7 |
| NER NLP | **spaCy + en_core_web_sm** | 3.8.x |
| Near-dedup | **MinHash LSH** | — |
| LLM observability | **LangSmith** | — |
| ML tracking | **MLflow** | 2.x |
| Database | **PostgreSQL** (Railway) | 16 |
| Cache | **Redis** (Railway) | 7.x |
| REST API | **FastAPI + uvicorn** | 0.111 |
| Scheduling | **APScheduler** | 3.x |
| Metrics | **Prometheus client** | 2.52 |
| Logging | **structlog** (JSON) | — |
| Data validation | **Pydantic v2** | — |
| Language | **Python** | 3.11 |

---

## Project Structure

```
marketforge-ai/
├── src/marketforge/
│   ├── agents/
│   │   ├── graphs/                  # LangGraph compiled StateGraphs
│   │   │   ├── states.py            # TypedDict state definitions (Annotated reducers)
│   │   │   ├── data_collection.py   # Dept 1 — Send API fan-out (8 scrapers)
│   │   │   ├── ml_engineering.py    # Dept 2 — conditional drift → retrain
│   │   │   ├── market_analysis.py   # Dept 3 — 7 parallel analyst nodes
│   │   │   ├── research.py          # Dept 4 — arXiv + emerging signal
│   │   │   ├── content_studio.py    # Dept 5 — weekly report generation
│   │   │   ├── user_insights.py     # Dept 6 — career gap analysis
│   │   │   ├── qa_testing.py        # Dept 7 — data integrity validation
│   │   │   ├── security.py          # Dept 8 — input sanitisation + PII
│   │   │   ├── ops_monitor.py       # Dept 9 — cost + health monitoring
│   │   │   └── master.py            # Top-level pipeline chaining all depts
│   │   ├── base.py                  # DeepAgent ABC (Plan→Execute→Reflect→Output)
│   │   ├── data_collection/         # Dept 1: scrapers, dedup coordinator, lead
│   │   ├── ml_engineering/          # Dept 2: PSI drift, feature eng, model reg
│   │   ├── market_analysis/         # Dept 3: skill demand, salary, sponsorship
│   │   ├── research/                # Dept 4: arXiv monitor, signal detection
│   │   ├── content_studio/          # Dept 5: report generator, self-review
│   │   ├── user_insights/           # Dept 6: SBERT match, sector fit, narrative
│   │   ├── qa_testing/              # Dept 7: integrity checks, drift alerts
│   │   ├── security/                # Dept 8: guardrails, injection detection
│   │   └── ops_monitor/             # Dept 9: cost tracking, alert dispatch
│   ├── cv/                          # CV analysis — GDPR-compliant, in-memory
│   │   ├── scanner.py               # Magic bytes, JS detection, AV signatures
│   │   ├── parser.py                # PDF (pdfplumber → pypdf) + DOCX
│   │   ├── ats_scorer.py            # 5-dimension deterministic ATS scoring
│   │   ├── gdpr.py                  # PII scrub, consent gate, anonymous token
│   │   └── gap_analyser.py          # demand × salary × recency ML ranking
│   ├── memory/
│   │   ├── postgres.py              # Async + sync engines, stores, checkpointer
│   │   └── redis_cache.py           # DashboardCache with TTL + invalidation
│   ├── ml/                          # Trained model wrappers (prescreen, salary)
│   ├── models/                      # Pydantic v2 data models
│   ├── nlp/
│   │   └── taxonomy.py              # 3-gate extraction (flashtext/spaCy/Gemini)
│   ├── config/
│   │   └── settings.py              # Pydantic BaseSettings — all env vars typed
│   └── utils/
│       ├── cost_tracker.py          # Per-run LLM token + cost tracking
│       └── logger.py                # structlog JSON setup
├── api/
│   └── main.py                      # FastAPI app (kept in sync with backend repo)
├── worker.py                        # APScheduler worker (kept in sync with backend repo)
├── tests/
│   ├── test_graphs/
│   │   └── test_smoke.py            # 15 smoke tests — zero DB/LLM I/O
│   ├── test_cv/
│   └── test_core.py
├── scripts/
│   ├── bootstrap.py                 # DB schema init + 109-skill taxonomy seed
│   └── run_pipeline.py              # Manual one-shot pipeline runner
├── airflow/dags/                    # Reference DAGs (local dev only)
├── dashboard/app.py                 # Streamlit dashboard (local dev)
└── pyproject.toml
```

---

## Quick Start

### Prerequisites

- Python 3.11
- Docker Desktop (PostgreSQL + Redis locally)
- [Google Gemini API key](https://aistudio.google.com/) — free tier
- [Adzuna API key](https://developer.adzuna.com/) — free
- [Reed API key](https://www.reed.co.uk/developers/jobseeker) — free

### 1. Clone and install

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

### 2. Configure environment

```env
# .env — never commit

DATABASE_URL=postgresql+asyncpg://marketforge:marketforge@localhost:5432/marketforge
DATABASE_URL_SYNC=postgresql+psycopg2://marketforge:marketforge@localhost:5432/marketforge
REDIS_URL=redis://localhost:6379/0

GEMINI_API_KEY=your_gemini_api_key

ADZUNA_APP_ID=your_adzuna_app_id
ADZUNA_APP_KEY=your_adzuna_app_key
REED_API_KEY=your_reed_api_key
TAVILY_API_KEY=your_tavily_key

# LangSmith — required for Studio graph view
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_key
LANGCHAIN_PROJECT=marketforge-ai

MLFLOW_TRACKING_URI=http://localhost:5001
```

### 3. Start infrastructure and seed DB

```bash
docker-compose up -d postgres redis
python scripts/bootstrap.py     # creates market schema + seeds skill taxonomy
```

### 4. Run the pipeline

```bash
python scripts/run_pipeline.py
```

### 5. Start API and dashboard

```bash
uvicorn api.main:app --reload --port 8000    # docs at http://localhost:8000/docs
streamlit run dashboard/app.py               # http://localhost:8501
```

---

## Pipeline Schedule (Production)

| Job | Schedule (UTC) | What runs |
|---|---|---|
| `ingest` | Tue + Thu 07:00 | scrape → dedup → NLP → market analysis → cache invalidation |
| `analysis` | Mon 07:00 | market analysis only — weekly snapshot + email report |
| `retrain` | Sun 02:00 | PSI drift check → retrain ML models if drift exceeds threshold |
| `cache` | every 6h | Redis cache refresh |

Manual trigger: `python worker.py --run-now ingest`

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/health` | System status, data freshness, job count |
| `GET` | `/api/v1/market/snapshot` | Weekly snapshot: skills, salary, sponsorship rates |
| `GET` | `/api/v1/market/skills` | Skill demand index by role category |
| `GET` | `/api/v1/market/salary` | Salary p25/p50/p75 benchmarks |
| `GET` | `/api/v1/market/trending` | Rising / declining skills week-on-week |
| `GET` | `/api/v1/jobs` | Browse indexed roles with filters |
| `POST` | `/api/v1/career/analyse` | SBERT match + Gemini 2.5 Pro career narrative (10 req/min) |
| `POST` | `/api/v1/career/cv-analyse` | ATS score + GDPR-compliant gap plan (3 req/hour) |
| `GET` | `/api/v1/pipeline/runs` | Pipeline execution history |
| `GET` | `/metrics` | Prometheus metrics |

---

## Smoke Tests

```bash
pytest tests/test_graphs/test_smoke.py -v
```

15 tests, zero DB or LLM I/O:
- All 10 graphs compile and import cleanly
- Security graph detects prompt injection attempts
- PII scrubbing removes email, UK postcode, NI number
- Field length enforcement (max 5,000 chars)
- Checkpointer falls back to `MemorySaver` when Postgres is unavailable
- State `TypedDict` reducers validate correctly

---

## Cost Model

| Item | Cost |
|---|---|
| Gemini Flash — Gate 3 NLP (~50 jobs/run × 2/week) | ~$0.02/run |
| Gemini 2.5 Pro — career analysis (on-demand) | ~$0.01/query |
| Gemini 2.5 Flash — CV gap plan (on-demand) | ~$0.003/query |
| PostgreSQL (Railway hobby) | $0/month |
| Redis (Railway hobby) | $0/month |
| **Total at 2 pipeline runs/week** | **~$0.20–0.40/month** |

---

## Local Services Reference

| Service | URL | Credentials |
|---|---|---|
| FastAPI docs | http://localhost:8000/docs | — |
| Streamlit dashboard | http://localhost:8501 | — |
| MLflow | http://localhost:5001 | — |
| Prometheus | http://localhost:9090 | — |
| PostgreSQL | localhost:5432 | marketforge / marketforge |
| Redis | localhost:6379 | — |

---

## Author

**Viraj Bulugahapitiya** · AI Engineer · MSc Data Science, University of Hertfordshire (2026)

Portfolio project demonstrating production-grade AI engineering: LangGraph multi-agent orchestration, 3-gate NLP pipelines, async FastAPI, GDPR-compliant CV processing with deterministic ATS scoring, and Railway + Vercel deployment — at sub-$5/month infrastructure cost.

[marketforge.digital](https://marketforge.digital) · [GitHub](https://github.com/Viraj97-SL)
