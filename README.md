# MarketForge AI

**UK AI Job Market Intelligence Platform**

Autonomous multi-department agentic system that continuously monitors, analyses, and distils the UK AI/ML job market into actionable intelligence.

[![CI](https://github.com/viraj97-sl/marketforge-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/viraj97-sl/marketforge-ai/actions)

## Architecture

Nine departments, each a LangGraph DeepAgent hierarchy:

| # | Department | Lead Agent | Purpose |
|---|---|---|---|
| 1 | Data Collection | DataCollectionLeadAgent | Ingest 15+ UK job sources |
| 2 | ML Engineering | MLEngineerLeadAgent | Train + deploy all ML models |
| 3 | Market Analysis | MarketAnalystLeadAgent | Trends, salary, skill demand |
| 4 | Research Intelligence | ResearchLeadAgent | arXiv → job market signal detection |
| 5 | Content Studio | ContentLeadAgent | Weekly LinkedIn-quality report |
| 6 | User Career Insights | UserInsightsLeadAgent | Personalised gap analysis |
| 7 | QA & Testing | QALeadAgent | Data quality + model drift |
| 8 | Security & Guardrails | SecurityLeadAgent | Prompt injection + PII protection |
| 9 | Ops & Observability | OpsLeadAgent | Cost tracking + health monitoring |

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/viraj97-sl/marketforge-ai.git
cd marketforge-ai
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 2. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 3. Start local services
docker-compose up -d

# 4. Bootstrap (creates DB tables, seeds taxonomy, verifies connectivity)
python scripts/bootstrap.py

# 5. Run first ingestion
python scripts/run_pipeline.py

# 6. Start the API
uvicorn api.main:app --reload

# 7. Start the dashboard
streamlit run dashboard/app.py
```

## Tech Stack

| Layer | Technology |
|---|---|
| Agent orchestration | LangGraph 0.2.x |
| Pipeline scheduling | Apache Airflow 2.9.x |
| LLM | Google Gemini Flash + Pro |
| Observability | LangSmith + Prometheus |
| ML tracking | MLflow 2.x |
| NLP | spaCy 3.x + flashtext |
| Embeddings | sentence-transformers (MiniLM) |
| Primary DB | PostgreSQL 16 |
| Vector DB | ChromaDB |
| Cache | Redis 7.x |
| API | FastAPI |
| Dashboard | Streamlit |

## Pipeline Schedule

```
Tuesday  07:00 UTC  — dag_ingest_primary  (captures Mon/Tue peak)
Thursday 07:00 UTC  — dag_ingest_primary  (captures Wed/Thu volume)
Monday   07:00 UTC  — dag_weekly_analysis (email report + snapshot)
Sunday   02:00 UTC  — dag_model_retrain   (off-peak ML cycle)
Every 6h            — dag_dashboard_refresh
```

## Cost Model

~$0.60/month total at 2 ingestion runs/week. Well within $5/month target.

## Build Phases

- **Phase 1** (2-3 wks): Data Foundation — PostgreSQL, taxonomy, 4 connectors, NLP gates 1+2
- **Phase 2** (2 wks): Analysis Core — Market Analysis dept, Redis, MLflow, basic dashboard
- **Phase 3** (2 wks): Agentic Intelligence — full ML Engineering, Research, Content Studio, LangSmith
- **Phase 4** (2 wks): User Features — Career Advisor, FastAPI, Security dept
- **Phase 5** (ongoing): Ops, remaining connectors, Grafana, public launch

## Author

Viraj Bulugahapitiya · MSc Data Science (Hertfordshire) · March 2026

---

*Specification: [MarketForge_AI_Software_Spec_v1.0](docs/MarketForge_AI_Software_Spec_v1_0.docx)*
