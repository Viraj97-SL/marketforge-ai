"""
MarketForge AI — dag_weekly_analysis

Schedule: Every Monday 07:00 UTC
           0 7 * * 1

Task chain:
  aggregate_market_stats
      → run_ml_predictions
      → generate_content_draft
      → qa_review_report
      → send_email_report
      → refresh_dashboards

Blocked if the last ingestion run completed more than 72 hours ago.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator, ShortCircuitOperator
from airflow.utils.dates import days_ago

DEFAULT_ARGS = {
    "owner":            "marketforge",
    "depends_on_past":  False,
    "email_on_failure": False,
    "retries":          2,
    "retry_delay":      timedelta(minutes=10),
}


# ── Guard: block if data is stale ────────────────────────────────────────────

def check_data_freshness(**context) -> bool:
    """
    Short-circuits the DAG if the latest ingestion run is > 72 hours old.
    Returns True (proceed) or False (skip).
    """
    import sys
    sys.path.insert(0, "/opt/airflow/src")
    from marketforge.memory.postgres import get_sync_engine
    from marketforge.utils.logger import setup_logging
    from sqlalchemy import text
    from datetime import timezone

    setup_logging()
    engine    = get_sync_engine()
    is_sqlite = engine.dialect.name == "sqlite"
    table     = "pipeline_runs" if is_sqlite else "market.pipeline_runs"

    with engine.connect() as conn:
        row = conn.execute(
            text(f"SELECT MAX(completed_at) FROM {table} WHERE status='running' OR status='success'")
        ).fetchone()

    if not row or not row[0]:
        import structlog
        structlog.get_logger().warning("freshness_check.no_runs_found")
        return False

    last_run = row[0]
    if isinstance(last_run, str):
        last_run = datetime.fromisoformat(last_run)

    age_hours = (datetime.utcnow() - last_run.replace(tzinfo=None)).total_seconds() / 3600
    fresh = age_hours <= 72

    import structlog
    structlog.get_logger().info("freshness_check", age_hours=round(age_hours, 1), proceed=fresh)
    return fresh


# ── Task 1: Market aggregation ────────────────────────────────────────────────

def task_aggregate_market_stats(**context) -> dict:
    """
    Runs the Market Analysis department Lead Agent.
    Computes weekly_snapshots, skill co-occurrence, salary stats,
    hiring velocity, and geographic distribution.
    """
    import sys
    sys.path.insert(0, "/opt/airflow/src")
    from marketforge.utils.logger import setup_logging
    setup_logging()

    import structlog
    log = structlog.get_logger("dag_weekly.aggregate")

    # Determine the week window
    today      = datetime.utcnow().date()
    week_start = today - timedelta(days=today.weekday() + 7)   # previous Monday

    log.info("market_stats.start", week_start=str(week_start))

    # ── Skill frequency aggregation (Phase 2 wires full MarketAnalystLeadAgent) ──
    # Phase 1 stub: run direct SQL aggregation
    from marketforge.memory.postgres import get_sync_engine
    from sqlalchemy import text
    import json

    engine    = get_sync_engine()
    is_sqlite = engine.dialect.name == "sqlite"
    skills_t  = "job_skills"    if is_sqlite else "market.job_skills"
    jobs_t    = "jobs"          if is_sqlite else "market.jobs"
    snap_t    = "weekly_snapshots" if is_sqlite else "market.weekly_snapshots"

    with engine.connect() as conn:
        # Top skills for this week
        rows = conn.execute(text(f"""
            SELECT js.skill, COUNT(*) as cnt
            FROM {skills_t} js
            JOIN {jobs_t} j ON j.job_id = js.job_id
            WHERE j.scraped_at >= :since
            GROUP BY js.skill
            ORDER BY cnt DESC
            LIMIT 30
        """), {"since": week_start.isoformat()}).fetchall()

        top_skills = {r[0]: r[1] for r in rows}

        # Job count
        job_count = conn.execute(text(f"""
            SELECT COUNT(*) FROM {jobs_t}
            WHERE scraped_at >= :since
        """), {"since": week_start.isoformat()}).scalar() or 0

        # Salary stats
        sal_rows = conn.execute(text(f"""
            SELECT salary_min, salary_max FROM {jobs_t}
            WHERE scraped_at >= :since
              AND (salary_min IS NOT NULL OR salary_max IS NOT NULL)
        """), {"since": week_start.isoformat()}).fetchall()

        midpoints = []
        for mn, mx in sal_rows:
            if mn and mx:
                midpoints.append((mn + mx) / 2)
            elif mn:
                midpoints.append(mn)
            elif mx:
                midpoints.append(mx)

        midpoints.sort()
        def pct(data, p):
            if not data:
                return None
            idx = max(0, int(len(data) * p / 100) - 1)
            return round(data[idx])

        salary_stats = {
            "p25": pct(midpoints, 25),
            "p50": pct(midpoints, 50),
            "p75": pct(midpoints, 75),
            "sample_size": len(midpoints),
        }

        # Sponsorship rate
        total_sp = conn.execute(text(f"""
            SELECT COUNT(*) FROM {jobs_t}
            WHERE scraped_at >= :since AND offers_sponsorship IS NOT NULL
        """), {"since": week_start.isoformat()}).scalar() or 1
        sponsored = conn.execute(text(f"""
            SELECT COUNT(*) FROM {jobs_t}
            WHERE scraped_at >= :since AND offers_sponsorship = 1
        """), {"since": week_start.isoformat()}).scalar() or 0

        sponsorship_rate = round(sponsored / max(total_sp, 1), 3)

        # Upsert snapshot
        now = datetime.utcnow().isoformat()
        conn.execute(text(f"""
            INSERT INTO {snap_t}
                (week_start, role_category, top_skills, salary_p25, salary_p50,
                 salary_p75, salary_sample_size, job_count, sponsorship_rate, computed_at)
            VALUES (:ws, 'all', :skills, :p25, :p50, :p75, :ss, :jc, :sr, :now)
            ON CONFLICT(week_start, role_category) DO UPDATE SET
                top_skills         = EXCLUDED.top_skills,
                salary_p25         = EXCLUDED.salary_p25,
                salary_p50         = EXCLUDED.salary_p50,
                salary_p75         = EXCLUDED.salary_p75,
                salary_sample_size = EXCLUDED.salary_sample_size,
                job_count          = EXCLUDED.job_count,
                sponsorship_rate   = EXCLUDED.sponsorship_rate,
                computed_at        = EXCLUDED.computed_at
        """), {
            "ws": str(week_start), "skills": json.dumps(top_skills),
            "p25": salary_stats["p25"], "p50": salary_stats["p50"],
            "p75": salary_stats["p75"], "ss": salary_stats["sample_size"],
            "jc": int(job_count), "sr": sponsorship_rate, "now": now,
        })
        conn.commit()

    stats = {
        "week_start":       str(week_start),
        "job_count":        int(job_count),
        "top_skill":        list(top_skills.keys())[0] if top_skills else "N/A",
        "salary_p50":       salary_stats["p50"],
        "sponsorship_rate": sponsorship_rate,
    }

    context["task_instance"].xcom_push(key="market_stats",  value=stats)
    context["task_instance"].xcom_push(key="week_start",    value=str(week_start))
    log.info("market_stats.done", **stats)
    return stats


# ── Task 2: ML predictions ───────────────────────────────────────────────────

def task_run_ml_predictions(**context) -> dict:
    """
    Triggers ML Engineering department for salary prediction and
    hiring velocity forecast updates. Phase 1 stub — full model
    inference wired in Phase 3.
    """
    import sys
    sys.path.insert(0, "/opt/airflow/src")
    from marketforge.utils.logger import setup_logging
    setup_logging()
    return {"status": "ok", "models_run": 0}


# ── Task 3: Content draft generation ────────────────────────────────────────

def task_generate_content_draft(**context) -> dict:
    """
    Runs the Content Studio Lead Agent to produce the weekly email draft.
    Full LLM call: DataNarrativeAgent → ContrarianInsightAgent → WeeklyReportWriterAgent.
    """
    import sys
    sys.path.insert(0, "/opt/airflow/src")
    from marketforge.utils.logger import setup_logging
    from marketforge.config.settings import settings
    setup_logging()

    import structlog
    log = structlog.get_logger("dag_weekly.content")

    stats      = context["task_instance"].xcom_pull(key="market_stats", task_ids="aggregate_market_stats")
    week_start = context["task_instance"].xcom_pull(key="week_start",   task_ids="aggregate_market_stats")
    stats      = stats or {}

    # Build the report using Gemini Flash for cost efficiency
    prompt = f"""You are a UK AI/ML job market analyst. Write a weekly market intelligence
email report for the week starting {week_start}.

Use ONLY the following data — no invented statistics:

- Total new job postings: {stats.get('job_count', 'N/A')}
- Top in-demand skill: {stats.get('top_skill', 'N/A')}
- Median salary (midpoint): £{stats.get('salary_p50', 'N/A')}
- Visa sponsorship rate: {round((stats.get('sponsorship_rate', 0) or 0) * 100, 1)}%

Format:
1. Opening hook (1 sentence, punchy)
2. Top market signal (2-3 sentences, data-backed)
3. Salary snapshot (2 sentences)
4. Sponsorship pulse (1-2 sentences)
5. Closing action point for job seekers (1-2 sentences)

Write in LinkedIn post quality — concise, professional, specific.
Maximum 300 words. Do not use placeholder text."""

    draft = ""
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage

        llm = ChatGoogleGenerativeAI(
            model=settings.llm.fast_model,
            google_api_key=settings.llm.gemini_api_key,
            temperature=0.3,
        )
        response = llm.invoke([HumanMessage(content=prompt)])
        draft    = response.content.strip()
        log.info("content_draft.generated", chars=len(draft))
    except Exception as exc:
        log.error("content_draft.error", error=str(exc))
        draft = f"Weekly UK AI Market Report — {week_start}\n\n[Report generation failed: {exc}]"

    context["task_instance"].xcom_push(key="report_draft", value=draft)
    return {"draft_chars": len(draft), "week_start": week_start}


# ── Task 4: QA review ───────────────────────────────────────────────────────

def task_qa_review_report(**context) -> dict:
    """
    QA department validates the report draft before dispatch.
    Checks: minimum length, no placeholder text, data citations present.
    Phase 1: rule-based checks. Phase 3: LLM evaluator (ReportQualityAgent).
    """
    import sys
    sys.path.insert(0, "/opt/airflow/src")
    from marketforge.utils.logger import setup_logging
    setup_logging()

    draft = context["task_instance"].xcom_pull(key="report_draft", task_ids="generate_content_draft") or ""

    checks = {
        "min_length":        len(draft) >= 200,
        "no_placeholder":    "[Report generation failed" not in draft,
        "has_numbers":       any(c.isdigit() for c in draft),
    }
    passed = all(checks.values())

    import structlog
    structlog.get_logger().info("qa_review", checks=checks, passed=passed)
    context["task_instance"].xcom_push(key="qa_passed", value=passed)
    return {"passed": passed, "checks": checks}


# ── Task 5: Send email ───────────────────────────────────────────────────────

def task_send_email_report(**context) -> dict:
    """
    Dispatches the weekly report via SMTP.
    Skips dispatch if QA check failed; logs the failure for review.
    """
    import sys
    sys.path.insert(0, "/opt/airflow/src")
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text      import MIMEText
    from marketforge.config.settings import settings
    from marketforge.utils.logger import setup_logging
    setup_logging()

    import structlog
    log = structlog.get_logger("dag_weekly.email")

    qa_passed  = context["task_instance"].xcom_pull(key="qa_passed",    task_ids="qa_review_report")
    draft      = context["task_instance"].xcom_pull(key="report_draft", task_ids="generate_content_draft") or ""
    week_start = context["task_instance"].xcom_pull(key="week_start",   task_ids="aggregate_market_stats")

    if not qa_passed:
        log.warning("email.skipped.qa_failed")
        return {"sent": False, "reason": "qa_failed"}

    cfg = settings.email
    if not cfg.user or not cfg.password:
        log.warning("email.skipped.no_credentials")
        return {"sent": False, "reason": "no_credentials"}

    try:
        msg          = MIMEMultipart()
        msg["From"]  = cfg.user
        msg["To"]    = cfg.recipient_email or cfg.user
        msg["Subject"] = f"MarketForge AI | UK AI Market Report | w/c {week_start}"
        msg.attach(MIMEText(draft, "plain"))

        with smtplib.SMTP(cfg.host, cfg.port) as server:
            server.starttls()
            server.login(cfg.user, cfg.password)
            server.send_message(msg)

        log.info("email.sent", to=cfg.recipient_email, week=week_start)
        return {"sent": True}
    except Exception as exc:
        log.error("email.send_failed", error=str(exc))
        return {"sent": False, "reason": str(exc)}


# ── Task 6: Refresh dashboards ───────────────────────────────────────────────

def task_refresh_dashboards(**context) -> dict:
    """
    Signals the dashboard cache to rebuild all panels.
    Full cache rebuild runs in the dag_dashboard_refresh DAG every 6h;
    this task just invalidates the weekly snapshot keys.
    """
    import sys
    sys.path.insert(0, "/opt/airflow/src")
    from marketforge.memory.redis_cache import DashboardCache
    DashboardCache().invalidate()
    return {"invalidated": True}


# ── DAG definition ─────────────────────────────────────────────────────────────
with DAG(
    dag_id="dag_weekly_analysis",
    description="MarketForge AI — weekly analysis, report generation, and email dispatch",
    schedule_interval="0 7 * * 1",   # Every Monday 07:00 UTC
    start_date=days_ago(1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["marketforge", "weekly", "report"],
    max_active_runs=1,
    doc_md="""
## dag_weekly_analysis

Every Monday morning: aggregates the week's market data, generates a
LinkedIn-quality intelligence report via Gemini, QA-checks it, emails
it to the configured recipient, then refreshes dashboard caches.
    """,
) as dag:

    freshness = ShortCircuitOperator(
        task_id="check_data_freshness",
        python_callable=check_data_freshness,
        doc_md="Skip entire DAG if no ingestion run in last 72 hours.",
    )

    aggregate = PythonOperator(
        task_id="aggregate_market_stats",
        python_callable=task_aggregate_market_stats,
        execution_timeout=timedelta(minutes=15),
    )

    ml_preds = PythonOperator(
        task_id="run_ml_predictions",
        python_callable=task_run_ml_predictions,
        execution_timeout=timedelta(minutes=10),
    )

    content = PythonOperator(
        task_id="generate_content_draft",
        python_callable=task_generate_content_draft,
        execution_timeout=timedelta(minutes=10),
    )

    qa = PythonOperator(
        task_id="qa_review_report",
        python_callable=task_qa_review_report,
        execution_timeout=timedelta(minutes=5),
    )

    email = PythonOperator(
        task_id="send_email_report",
        python_callable=task_send_email_report,
        execution_timeout=timedelta(minutes=5),
    )

    refresh = PythonOperator(
        task_id="refresh_dashboards",
        python_callable=task_refresh_dashboards,
    )

    freshness >> aggregate >> ml_preds >> content >> qa >> email >> refresh
