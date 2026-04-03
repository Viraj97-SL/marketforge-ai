"""
MarketForge AI — dag_ingest_primary

Schedule: Tuesday + Thursday 07:00 UTC
           0 7 * * 2,4

Task chain:
  scrape_all_sources
      → nlp_extraction
      → company_enrichment
      → update_snapshot_cache
      → notify_ops

Each task is thin — it instantiates the relevant Lead Agent or utility
and delegates all reasoning to the agent layer. XCom passes only
lightweight metadata (counts, status codes, run_id).
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

# ── Default task args ──────────────────────────────────────────────────────────
DEFAULT_ARGS = {
    "owner":            "marketforge",
    "depends_on_past":  False,
    "email_on_failure": False,
    "email_on_retry":   False,
    "retries":          3,
    "retry_delay":      timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "max_retry_delay":  timedelta(minutes=30),
}


# ── Task functions ─────────────────────────────────────────────────────────────

def task_scrape_all_sources(**context) -> dict:
    """
    Instantiates DataCollectionLeadAgent and runs the full fan-out.
    Returns a lightweight summary dict for downstream XCom.
    """
    import sys
    sys.path.insert(0, "/opt/airflow/src")

    from marketforge.agents.data_collection.lead_agent import run_data_collection
    from marketforge.utils.cost_tracker import CostTracker
    from marketforge.utils.logger import setup_logging

    setup_logging()
    run_id       = context["dag_run"].run_id or f"airflow_{uuid.uuid4().hex[:8]}"
    cost_tracker = CostTracker(run_id=run_id)

    summary = asyncio.run(run_data_collection(run_id, cost_tracker))
    context["task_instance"].xcom_push(key="run_id",    value=run_id)
    context["task_instance"].xcom_push(key="jobs_new",  value=summary["jobs_new"])
    context["task_instance"].xcom_push(key="quality",   value=summary["quality"])
    return summary


def task_nlp_extraction(**context) -> dict:
    """
    Runs the three-gate NLP pipeline over all new jobs from this run.
    Writes extracted skills to market.job_skills.
    """
    import sys
    sys.path.insert(0, "/opt/airflow/src")

    from marketforge.memory.postgres import get_sync_engine, JobStore
    from marketforge.nlp.taxonomy import extract_skills_flat, classify_role
    from marketforge.utils.logger import setup_logging
    from sqlalchemy import text

    setup_logging()
    run_id = context["task_instance"].xcom_pull(key="run_id", task_ids="scrape_all_sources")
    if not run_id:
        raise ValueError("No run_id in XCom — scrape task may have failed")

    engine    = get_sync_engine()
    job_store = JobStore()
    is_sqlite = engine.dialect.name == "sqlite"
    jobs_t    = "jobs" if is_sqlite else "market.jobs"

    with engine.connect() as conn:
        rows = conn.execute(
            text(f"SELECT job_id, title, description FROM {jobs_t} WHERE run_id = :rid"),
            {"rid": run_id},
        ).fetchall()

    stats = {"gate1": 0, "gate2": 0, "gate3": 0, "total_jobs": len(rows)}
    for job_id, title, description in rows:
        text_blob = f"{title} {description or ''}"
        skills = extract_skills_flat(text_blob)
        job_store.upsert_skills(job_id, [(s, c, m, cf) for s, c, m, cf in skills])
        for _, _, method, _ in skills:
            stats[method] = stats.get(method, 0) + 1

    context["task_instance"].xcom_push(key="nlp_stats", value=stats)
    return stats


def task_company_enrichment(**context) -> dict:
    """
    For each new company in this run, enriches the companies table
    with stage, sector, headcount, and careers URL from the FundingNewsDeepDiscoveryAgent.
    Lightweight — only runs for companies not already in market.companies.
    """
    import sys
    sys.path.insert(0, "/opt/airflow/src")
    from marketforge.utils.logger import setup_logging
    setup_logging()

    run_id  = context["task_instance"].xcom_pull(key="run_id", task_ids="scrape_all_sources")
    # Company enrichment is a low-priority task — runs best-effort, never blocks
    # Full implementation in Phase 2 (FundingNewsDeepDiscoveryAgent)
    return {"run_id": run_id, "status": "ok", "enriched": 0}


def task_update_snapshot_cache(**context) -> dict:
    """
    Triggers the Market Analysis department to recompute weekly_snapshots
    and refresh the Redis dashboard cache.
    In Phase 1 this is a no-op — full analysis wired in Phase 2.
    """
    import sys
    sys.path.insert(0, "/opt/airflow/src")
    from marketforge.memory.redis_cache import DashboardCache
    from marketforge.utils.logger import setup_logging
    setup_logging()

    cache = DashboardCache()
    cache.invalidate("skills")
    cache.invalidate("salary")
    cache.invalidate("snapshot")
    return {"cache_invalidated": True}


def task_notify_ops(**context) -> dict:
    """
    Sends a run summary to the Ops department.
    In Phase 1 this logs to structlog; full alert dispatch in Phase 5.
    """
    import sys
    sys.path.insert(0, "/opt/airflow/src")
    import structlog
    from marketforge.utils.logger import setup_logging
    setup_logging()

    log = structlog.get_logger("dag_ingest_primary.ops")

    run_id   = context["task_instance"].xcom_pull(key="run_id",   task_ids="scrape_all_sources")
    jobs_new = context["task_instance"].xcom_pull(key="jobs_new", task_ids="scrape_all_sources")
    quality  = context["task_instance"].xcom_pull(key="quality",  task_ids="scrape_all_sources")
    nlp      = context["task_instance"].xcom_pull(key="nlp_stats",task_ids="nlp_extraction") or {}

    log.info(
        "ingest_cycle.complete",
        run_id=run_id,
        jobs_new=jobs_new,
        quality=quality,
        nlp_gate1=nlp.get("gate1", 0),
        nlp_gate2=nlp.get("gate2", 0),
        nlp_gate3=nlp.get("gate3", 0),
    )
    return {"run_id": run_id, "jobs_new": jobs_new, "quality": quality}


# ── DAG definition ─────────────────────────────────────────────────────────────
with DAG(
    dag_id="dag_ingest_primary",
    description="MarketForge AI — primary ingestion: scrape → NLP → enrich → cache → notify",
    schedule_interval="0 7 * * 2,4",   # Tuesday + Thursday 07:00 UTC
    start_date=days_ago(1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["marketforge", "ingestion", "phase1"],
    max_active_runs=1,                  # never overlap two ingestion cycles
    doc_md="""
## dag_ingest_primary

Runs every Tuesday and Thursday at 07:00 UTC to capture the peak UK job
posting windows (Mon/Tue and Wed/Thu). Costs approximately $0.04 per run
in LLM tokens. Full documentation in the MarketForge AI Software Spec v1.0.
    """,
) as dag:

    scrape = PythonOperator(
        task_id="scrape_all_sources",
        python_callable=task_scrape_all_sources,
        execution_timeout=timedelta(minutes=45),
        doc_md="Fan-out to all data collection sub-agents in parallel.",
    )

    nlp = PythonOperator(
        task_id="nlp_extraction",
        python_callable=task_nlp_extraction,
        execution_timeout=timedelta(minutes=20),
        doc_md="Three-gate NLP: flashtext → spaCy → Gemini Flash (fallback only).",
    )

    enrich = PythonOperator(
        task_id="company_enrichment",
        python_callable=task_company_enrichment,
        execution_timeout=timedelta(minutes=10),
        doc_md="Enrich new companies with stage/sector signals.",
    )

    cache = PythonOperator(
        task_id="update_snapshot_cache",
        python_callable=task_update_snapshot_cache,
        execution_timeout=timedelta(minutes=5),
        doc_md="Invalidate Redis dashboard cache to trigger rebuild.",
    )

    notify = PythonOperator(
        task_id="notify_ops",
        python_callable=task_notify_ops,
        doc_md="Log run summary; alert on quality degradation.",
    )

    scrape >> nlp >> enrich >> cache >> notify
