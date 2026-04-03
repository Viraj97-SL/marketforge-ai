"""
MarketForge AI — dag_model_retrain

Schedule: Every Sunday 02:00 UTC (off-peak, low cost)
           0 2 * * 0

Task chain:
  check_retrain_needed
      → load_training_data
      → feature_engineering
      → train_skill_extractor
      → train_prescreen_model
      → evaluate_models
      → register_if_improved
      → alert_on_regression
"""
from __future__ import annotations

from datetime import timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator, ShortCircuitOperator
from airflow.utils.dates import days_ago

DEFAULT_ARGS = {
    "owner":            "marketforge",
    "depends_on_past":  False,
    "retries":          1,
    "retry_delay":      timedelta(minutes=15),
}


def check_retrain_needed(**context) -> bool:
    """Skip retrain if no new data since last retrain cycle."""
    import sys
    sys.path.insert(0, "/opt/airflow/src")
    from marketforge.memory.postgres import get_sync_engine
    from sqlalchemy import text
    from datetime import datetime

    engine    = get_sync_engine()
    is_sqlite = engine.dialect.name == "sqlite"
    jobs_t    = "jobs" if is_sqlite else "market.jobs"

    with engine.connect() as conn:
        count = conn.execute(text(f"""
            SELECT COUNT(*) FROM {jobs_t}
            WHERE scraped_at >= datetime('now', '-7 days')
        """ if is_sqlite else f"""
            SELECT COUNT(*) FROM {jobs_t}
            WHERE scraped_at >= NOW() - INTERVAL '7 days'
        """)).scalar() or 0

    import structlog
    structlog.get_logger().info("retrain_check", new_jobs_7d=count, will_retrain=count >= 50)
    return count >= 50   # need at least 50 new jobs to justify a retrain


def task_load_training_data(**context) -> dict:
    """Load labelled training data from market.job_skills + golden dataset."""
    import sys
    sys.path.insert(0, "/opt/airflow/src")
    from marketforge.memory.postgres import get_sync_engine
    from sqlalchemy import text

    engine    = get_sync_engine()
    is_sqlite = engine.dialect.name == "sqlite"
    skills_t  = "job_skills" if is_sqlite else "market.job_skills"

    with engine.connect() as conn:
        row = conn.execute(text(f"SELECT COUNT(*) FROM {skills_t}")).fetchone()
        total_skill_records = row[0] if row else 0

    context["task_instance"].xcom_push(key="skill_records", value=total_skill_records)
    return {"skill_records": total_skill_records}


def task_feature_engineering(**context) -> dict:
    """Compute ML feature matrix for prescreen model training."""
    import sys
    sys.path.insert(0, "/opt/airflow/src")
    from marketforge.utils.logger import setup_logging
    setup_logging()
    # Phase 2: FeatureEngineeringAgent runs here
    return {"features_computed": 0, "status": "stub"}


def task_train_skill_extractor(**context) -> dict:
    """
    Retrain the spaCy NER component using LLM-confirmed Gate 3 outputs
    as additional training labels. Logs run to MLflow.
    Phase 3: full SkillExtractionModelAgent.
    """
    import sys
    sys.path.insert(0, "/opt/airflow/src")
    from marketforge.utils.logger import setup_logging
    setup_logging()
    return {"model": "skill_extractor", "status": "stub", "f1": None}


def task_train_prescreen_model(**context) -> dict:
    """
    Train LogisticRegression pre-screen gate.
    Features: [embedding_sim, bm25_score, skill_overlap, is_startup, salary_band].
    Target: binary — is this a genuine AI/ML role?
    Phase 3: full PreScreenCalibrationAgent.
    """
    import sys
    sys.path.insert(0, "/opt/airflow/src")
    from marketforge.utils.logger import setup_logging
    setup_logging()
    return {"model": "prescreen", "status": "stub", "auc": None}


def task_evaluate_models(**context) -> dict:
    """Evaluate candidate models against held-out test set."""
    import sys
    sys.path.insert(0, "/opt/airflow/src")
    return {"evaluation": "stub", "all_passed": True}


def task_register_if_improved(**context) -> dict:
    """Promote candidate model to production in MLflow if metrics improved."""
    import sys
    sys.path.insert(0, "/opt/airflow/src")
    all_passed = context["task_instance"].xcom_pull(
        key="return_value", task_ids="evaluate_models"
    ) or {}
    return {"promoted": False, "reason": "stub_phase"}


def task_alert_on_regression(**context) -> dict:
    """Alert if any model regressed vs the prior production version."""
    import sys
    sys.path.insert(0, "/opt/airflow/src")
    import structlog
    structlog.get_logger("dag_model_retrain").info("retrain_cycle.complete")
    return {"regression_detected": False}


with DAG(
    dag_id="dag_model_retrain",
    description="MarketForge AI — weekly ML model retraining pipeline",
    schedule_interval="0 2 * * 0",   # Sunday 02:00 UTC
    start_date=days_ago(1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["marketforge", "mlops", "retrain"],
    max_active_runs=1,
    doc_md="""
## dag_model_retrain
Runs Sunday 02:00 UTC. Retrains the skill extractor (spaCy NER) and
pre-screen gate (LogisticRegression) on accumulated data. Skipped if
fewer than 50 new jobs were ingested in the past 7 days.
    """,
) as dag:

    check = ShortCircuitOperator(
        task_id="check_retrain_needed",
        python_callable=check_retrain_needed,
    )
    load = PythonOperator(task_id="load_training_data",     python_callable=task_load_training_data)
    feat = PythonOperator(task_id="feature_engineering",    python_callable=task_feature_engineering,   execution_timeout=timedelta(minutes=20))
    sk   = PythonOperator(task_id="train_skill_extractor",  python_callable=task_train_skill_extractor, execution_timeout=timedelta(minutes=30))
    ps   = PythonOperator(task_id="train_prescreen_model",  python_callable=task_train_prescreen_model, execution_timeout=timedelta(minutes=20))
    ev   = PythonOperator(task_id="evaluate_models",        python_callable=task_evaluate_models,       execution_timeout=timedelta(minutes=15))
    reg  = PythonOperator(task_id="register_if_improved",   python_callable=task_register_if_improved)
    alrt = PythonOperator(task_id="alert_on_regression",    python_callable=task_alert_on_regression)

    check >> load >> feat >> [sk, ps] >> ev >> reg >> alrt
