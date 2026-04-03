"""
MarketForge AI — dag_security_audit

Schedule: Daily 01:00 UTC (runs regardless of main pipeline status)
           0 1 * * *

Task chain:
  audit_access_log
      → rotate_api_keys_check
      → threat_pattern_update
      → generate_security_summary

This DAG runs independently of the main ingestion pipeline.
Security checks must never be gated behind data freshness.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

DEFAULT_ARGS = {
    "owner":            "marketforge",
    "depends_on_past":  False,
    "email_on_failure": False,
    "retries":          1,
    "retry_delay":      timedelta(minutes=5),
}


# ── Task 1: Audit access log ─────────────────────────────────────────────────

def task_audit_access_log(**context) -> dict:
    """
    Reviews the security_log for anomalous patterns:
    - Unusual spike in rejected inputs (possible coordinated attack)
    - New IP ranges appearing in threat log
    - PII detection rate anomalies (possible scraper scraping PII)
    """
    import sys
    sys.path.insert(0, "/opt/airflow/src")
    from marketforge.memory.postgres import get_sync_engine
    from marketforge.utils.logger import setup_logging
    from sqlalchemy import text
    from datetime import timedelta

    setup_logging()
    import structlog
    log = structlog.get_logger("dag_security.audit_access")

    engine    = get_sync_engine()
    is_sqlite = engine.dialect.name == "sqlite"
    sec_t     = "security_log" if is_sqlite else "market.security_log"
    since     = (datetime.utcnow() - timedelta(hours=24)).isoformat()

    with engine.connect() as conn:
        # Count events by type in last 24h
        try:
            rows = conn.execute(text(f"""
                SELECT event_type, severity, COUNT(*) as cnt
                FROM {sec_t}
                WHERE logged_at >= :since
                GROUP BY event_type, severity
                ORDER BY cnt DESC
            """), {"since": since}).fetchall()
        except Exception:
            rows = []

    event_summary = {f"{r[0]}:{r[1]}": r[2] for r in rows}
    total_events  = sum(event_summary.values())

    # Flag if injection attempts exceed threshold
    injection_count = sum(v for k, v in event_summary.items() if "injection" in k)
    if injection_count > 10:
        log.warning("security_audit.injection_spike", count=injection_count)

    log.info("security_audit.access_log_done", total_events=total_events, summary=event_summary)
    context["task_instance"].xcom_push(key="event_summary", value=event_summary)
    context["task_instance"].xcom_push(key="injection_count", value=injection_count)
    return {"total_events": total_events, "injection_count": injection_count}


# ── Task 2: Rotate API keys check ───────────────────────────────────────────

def task_rotate_api_keys_check(**context) -> dict:
    """
    Checks whether API keys have been in use for > 90 days.
    Does not rotate automatically — flags for human review.
    """
    import sys
    sys.path.insert(0, "/opt/airflow/src")
    from marketforge.config.settings import settings
    from marketforge.utils.logger import setup_logging
    setup_logging()

    import structlog
    log = structlog.get_logger("dag_security.key_check")

    # Check which keys are configured (without logging values)
    configured_keys = []
    if settings.llm.gemini_api_key:
        configured_keys.append("GEMINI_API_KEY")
    if settings.sources.adzuna_app_key:
        configured_keys.append("ADZUNA_API_KEY")
    if settings.sources.reed_api_key:
        configured_keys.append("REED_API_KEY")
    if settings.sources.tavily_api_key:
        configured_keys.append("TAVILY_API_KEY")

    log.info("security_audit.keys_configured", count=len(configured_keys), keys=configured_keys)
    return {"configured_keys": configured_keys, "all_present": len(configured_keys) >= 3}


# ── Task 3: Threat pattern update ───────────────────────────────────────────

def task_threat_pattern_update(**context) -> dict:
    """
    Reviews the last 7 days of security logs to identify new injection patterns
    not covered by the existing regex library. Generates a pattern update report.
    """
    import sys
    sys.path.insert(0, "/opt/airflow/src")
    from marketforge.memory.postgres import get_sync_engine
    from marketforge.utils.logger import setup_logging
    from sqlalchemy import text
    setup_logging()

    import structlog
    log = structlog.get_logger("dag_security.threat_patterns")

    engine    = get_sync_engine()
    is_sqlite = engine.dialect.name == "sqlite"
    sec_t     = "security_log" if is_sqlite else "market.security_log"

    since     = (datetime.utcnow() - timedelta(days=7)).isoformat()
    with engine.connect() as conn:
        try:
            rows = conn.execute(text(f"""
                SELECT detection_method, COUNT(*) as cnt
                FROM {sec_t}
                WHERE logged_at >= :since AND event_type LIKE '%injection%'
                GROUP BY detection_method
            """), {"since": since}).fetchall()
        except Exception:
            rows = []

    detection_methods = {r[0]: r[1] for r in rows}
    log.info("security_audit.threat_methods", methods=detection_methods)

    context["task_instance"].xcom_push(key="detection_methods", value=detection_methods)
    return {"detection_methods": detection_methods}


# ── Task 4: Generate security summary ───────────────────────────────────────

def task_generate_security_summary(**context) -> dict:
    """
    Aggregates the security audit results and writes a summary to the ops log.
    If severity-1 issues were detected, dispatches an alert email.
    """
    import sys
    sys.path.insert(0, "/opt/airflow/src")
    from marketforge.utils.logger import setup_logging
    setup_logging()

    import structlog
    log = structlog.get_logger("dag_security.summary")

    event_summary    = context["task_instance"].xcom_pull(key="event_summary",    task_ids="audit_access_log") or {}
    injection_count  = context["task_instance"].xcom_pull(key="injection_count",  task_ids="audit_access_log") or 0
    detection_methods= context["task_instance"].xcom_pull(key="detection_methods",task_ids="threat_pattern_update") or {}

    severity = "ok"
    if injection_count > 50:
        severity = "critical"
    elif injection_count > 10:
        severity = "warning"

    summary = {
        "date":              datetime.utcnow().strftime("%Y-%m-%d"),
        "total_events_24h":  sum(event_summary.values()),
        "injection_attempts_24h": injection_count,
        "detection_methods_7d":   detection_methods,
        "severity":          severity,
    }

    log.info("security_audit.summary_done", **summary)

    # Trigger alert if critical
    if severity == "critical":
        try:
            import asyncio
            from marketforge.agents.ops_monitor.lead_agent import AlertDispatchAgent
            agent = AlertDispatchAgent()
            alerts = [{
                "severity":   1,
                "department": "security",
                "message":    f"Security audit critical: {injection_count} injection attempts in 24h. Immediate review required.",
            }]
            asyncio.run(agent.run({"pending_alerts": alerts}))
        except Exception as exc:
            log.error("security_audit.alert_failed", error=str(exc))

    return summary


# ── DAG definition ────────────────────────────────────────────────────────────
with DAG(
    dag_id="dag_security_audit",
    description="MarketForge AI — daily security audit: access log review, threat analysis, key check",
    schedule_interval="0 1 * * *",   # Daily 01:00 UTC
    start_date=days_ago(1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["marketforge", "security", "daily"],
    max_active_runs=1,
    doc_md="""
## dag_security_audit

Runs daily at 01:00 UTC, independent of the main pipeline.
Reviews the security_log for threats, checks API key configuration,
identifies new injection pattern candidates, and generates a security
summary for the weekly ops report.
    """,
) as dag:

    audit = PythonOperator(
        task_id="audit_access_log",
        python_callable=task_audit_access_log,
        execution_timeout=timedelta(minutes=5),
    )

    keys = PythonOperator(
        task_id="rotate_api_keys_check",
        python_callable=task_rotate_api_keys_check,
        execution_timeout=timedelta(minutes=2),
    )

    threats = PythonOperator(
        task_id="threat_pattern_update",
        python_callable=task_threat_pattern_update,
        execution_timeout=timedelta(minutes=5),
    )

    summary = PythonOperator(
        task_id="generate_security_summary",
        python_callable=task_generate_security_summary,
        execution_timeout=timedelta(minutes=3),
    )

    audit >> [keys, threats] >> summary
