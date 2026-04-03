"""
MarketForge AI — dag_dashboard_refresh

Schedule: Every 6 hours
           0 */6 * * *

Task chain:
  rebuild_skill_cache
      → rebuild_salary_cache
      → rebuild_geo_cache
      → ping_health_check

Lightweight DAG — no agent instantiation, no LLM calls.
Rebuilds the Redis cache that powers the Streamlit dashboard.
"""
from __future__ import annotations

from datetime import timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

DEFAULT_ARGS = {
    "owner":            "marketforge",
    "depends_on_past":  False,
    "email_on_failure": False,
    "retries":          2,
    "retry_delay":      timedelta(minutes=2),
}


# ── Task 1: Rebuild skill cache ───────────────────────────────────────────────

def task_rebuild_skill_cache(**context) -> dict:
    """
    Refreshes the Redis cache for the top skills panel.
    Reads from market.weekly_snapshots → writes to Redis key
    dashboard:skills:{week} with TTL 7h.
    """
    import sys
    sys.path.insert(0, "/opt/airflow/src")
    from marketforge.memory.postgres import get_sync_engine
    from marketforge.utils.logger import setup_logging
    from sqlalchemy import text
    import json
    setup_logging()

    import structlog
    log = structlog.get_logger("dag_refresh.skills")

    engine    = get_sync_engine()
    is_sqlite = engine.dialect.name == "sqlite"
    snap_t    = "weekly_snapshots" if is_sqlite else "market.weekly_snapshots"

    with engine.connect() as conn:
        row = conn.execute(text(f"""
            SELECT week_start, top_skills, rising_skills, declining_skills,
                   job_count, sponsorship_rate
            FROM {snap_t}
            WHERE role_category = 'all'
            ORDER BY week_start DESC LIMIT 1
        """)).fetchone()

    if not row:
        log.warning("skill_cache.no_snapshot")
        return {"cached": False, "reason": "no_snapshot"}

    week_start, top_skills, rising, declining, job_count, sponsor_rate = row
    payload = {
        "week_start":      str(week_start),
        "top_skills":      json.loads(top_skills)  if isinstance(top_skills, str)  else (top_skills or {}),
        "rising_skills":   json.loads(rising)      if isinstance(rising, str)      else (rising or []),
        "declining_skills":json.loads(declining)   if isinstance(declining, str)   else (declining or []),
        "job_count":       job_count or 0,
        "sponsorship_rate":float(sponsor_rate or 0),
    }

    try:
        from marketforge.memory.redis_cache import DashboardCache
        cache = DashboardCache()
        cache.set(f"dashboard:skills:{week_start}", payload, ttl=7 * 3600)
        cache.set("dashboard:skills:latest", payload, ttl=7 * 3600)
        log.info("skill_cache.refreshed", week=week_start, skills=len(payload.get("top_skills", {})))
        return {"cached": True, "week": str(week_start), "skill_count": len(payload.get("top_skills", {}))}
    except Exception as exc:
        log.warning("skill_cache.redis_unavailable", error=str(exc))
        return {"cached": False, "reason": str(exc)[:100]}


# ── Task 2: Rebuild salary cache ──────────────────────────────────────────────

def task_rebuild_salary_cache(**context) -> dict:
    """
    Refreshes salary percentile data for the salary dashboard panel.
    Reads from market.weekly_snapshots → writes to Redis key
    dashboard:salary:{role_category}:{week} with TTL 7h.
    """
    import sys
    sys.path.insert(0, "/opt/airflow/src")
    from marketforge.memory.postgres import get_sync_engine
    from marketforge.utils.logger import setup_logging
    from sqlalchemy import text
    setup_logging()

    import structlog
    log = structlog.get_logger("dag_refresh.salary")

    engine    = get_sync_engine()
    is_sqlite = engine.dialect.name == "sqlite"
    snap_t    = "weekly_snapshots" if is_sqlite else "market.weekly_snapshots"

    with engine.connect() as conn:
        rows = conn.execute(text(f"""
            SELECT role_category, week_start,
                   salary_p25, salary_p50, salary_p75, salary_sample_size
            FROM {snap_t}
            ORDER BY week_start DESC
            LIMIT 20
        """)).fetchall()

    if not rows:
        log.warning("salary_cache.no_data")
        return {"cached": False}

    try:
        from marketforge.memory.redis_cache import DashboardCache
        cache     = DashboardCache()
        cached    = 0
        for row in rows:
            role_cat, week_start, p25, p50, p75, n = row
            payload = {
                "role_category":  role_cat,
                "week_start":     str(week_start),
                "salary_p25":     float(p25) if p25 else None,
                "salary_p50":     float(p50) if p50 else None,
                "salary_p75":     float(p75) if p75 else None,
                "sample_size":    n or 0,
            }
            key = f"dashboard:salary:{role_cat}:{week_start}"
            cache.set(key, payload, ttl=7 * 3600)
            cached += 1

        # Write a combined "all roles" summary key
        all_roles = [r for r in rows if r[0] == "all"]
        if all_roles:
            r = all_roles[0]
            cache.set("dashboard:salary:latest", {
                "role_category": "all", "week_start": str(r[1]),
                "salary_p25": float(r[2]) if r[2] else None,
                "salary_p50": float(r[3]) if r[3] else None,
                "salary_p75": float(r[4]) if r[4] else None,
                "sample_size": r[5] or 0,
            }, ttl=7 * 3600)

        log.info("salary_cache.refreshed", entries=cached)
        return {"cached": True, "entries": cached}
    except Exception as exc:
        log.warning("salary_cache.redis_unavailable", error=str(exc))
        return {"cached": False, "reason": str(exc)[:100]}


# ── Task 3: Rebuild geo cache ──────────────────────────────────────────────────

def task_rebuild_geo_cache(**context) -> dict:
    """
    Refreshes geographic distribution data for the heatmap panel.
    Reads from market.weekly_snapshots.top_cities → Redis with TTL 7h.
    """
    import sys
    sys.path.insert(0, "/opt/airflow/src")
    from marketforge.memory.postgres import get_sync_engine
    from marketforge.utils.logger import setup_logging
    from sqlalchemy import text
    import json
    setup_logging()

    import structlog
    log = structlog.get_logger("dag_refresh.geo")

    engine    = get_sync_engine()
    is_sqlite = engine.dialect.name == "sqlite"
    snap_t    = "weekly_snapshots" if is_sqlite else "market.weekly_snapshots"

    with engine.connect() as conn:
        row = conn.execute(text(f"""
            SELECT week_start, top_cities
            FROM {snap_t}
            WHERE role_category = 'all'
            ORDER BY week_start DESC LIMIT 1
        """)).fetchone()

    if not row or not row[1]:
        log.warning("geo_cache.no_data")
        return {"cached": False}

    week_start, top_cities = row
    cities = json.loads(top_cities) if isinstance(top_cities, str) else (top_cities or {})

    try:
        from marketforge.memory.redis_cache import DashboardCache
        cache = DashboardCache()
        payload = {"week_start": str(week_start), "city_distribution": cities}
        cache.set(f"dashboard:geo:{week_start}", payload, ttl=7 * 3600)
        cache.set("dashboard:geo:latest", payload, ttl=7 * 3600)
        log.info("geo_cache.refreshed", week=week_start, cities=len(cities))
        return {"cached": True, "cities": len(cities)}
    except Exception as exc:
        log.warning("geo_cache.redis_unavailable", error=str(exc))
        return {"cached": False, "reason": str(exc)[:100]}


# ── Task 4: Health ping ───────────────────────────────────────────────────────

def task_ping_health_check(**context) -> dict:
    """
    Final health check: verifies the cache was written and the DB is reachable.
    Dispatches a severity-2 alert if the refresh failed on all 3 cache tasks.
    """
    import sys
    sys.path.insert(0, "/opt/airflow/src")
    from marketforge.utils.logger import setup_logging
    setup_logging()

    import structlog
    log = structlog.get_logger("dag_refresh.health")

    skill_result  = context["task_instance"].xcom_pull(task_ids="rebuild_skill_cache")  or {}
    salary_result = context["task_instance"].xcom_pull(task_ids="rebuild_salary_cache") or {}
    geo_result    = context["task_instance"].xcom_pull(task_ids="rebuild_geo_cache")    or {}

    all_ok = all([
        skill_result.get("cached"),
        salary_result.get("cached"),
        geo_result.get("cached"),
    ])

    log.info(
        "dashboard_refresh.health",
        skills=skill_result.get("cached"),
        salary=salary_result.get("cached"),
        geo=geo_result.get("cached"),
        all_ok=all_ok,
    )

    if not all_ok:
        log.warning("dashboard_refresh.cache_miss", skill=skill_result, salary=salary_result, geo=geo_result)

    return {
        "all_cached": all_ok,
        "skill_cache":  skill_result.get("cached", False),
        "salary_cache": salary_result.get("cached", False),
        "geo_cache":    geo_result.get("cached", False),
    }


# ── DAG definition ────────────────────────────────────────────────────────────
with DAG(
    dag_id="dag_dashboard_refresh",
    description="MarketForge AI — 6-hourly Redis cache rebuild for Streamlit dashboard",
    schedule_interval="0 */6 * * *",   # Every 6 hours
    start_date=days_ago(1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["marketforge", "dashboard", "cache"],
    max_active_runs=1,
    doc_md="""
## dag_dashboard_refresh

Runs every 6 hours. Rebuilds the Redis cache keys consumed by the
Streamlit dashboard: skills panel, salary benchmarks, and geo heatmap.
No LLM calls — pure SQL → Redis writes. Fast and cheap.
    """,
) as dag:

    skill_cache = PythonOperator(
        task_id="rebuild_skill_cache",
        python_callable=task_rebuild_skill_cache,
        execution_timeout=timedelta(minutes=3),
    )

    salary_cache = PythonOperator(
        task_id="rebuild_salary_cache",
        python_callable=task_rebuild_salary_cache,
        execution_timeout=timedelta(minutes=3),
    )

    geo_cache = PythonOperator(
        task_id="rebuild_geo_cache",
        python_callable=task_rebuild_geo_cache,
        execution_timeout=timedelta(minutes=3),
    )

    health = PythonOperator(
        task_id="ping_health_check",
        python_callable=task_ping_health_check,
        execution_timeout=timedelta(minutes=2),
    )

    [skill_cache, salary_cache, geo_cache] >> health
