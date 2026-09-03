"""
MarketForge AI — SalaryIntelligenceAgent validation tests.

Covers the two new integrity fixes in agents/market_analysis/lead_agent.py:
  - currency filter (only salary_currency='GBP' rows counted)
  - real IQR-based outlier trimming (on top of the existing absolute bounds)

Uses SQLite via a fresh_db fixture — same pattern as
tests/test_agents/test_agents.py.
"""
from __future__ import annotations

import asyncio
import os

os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///./test_salary_intel.db")
os.environ.setdefault("REDIS_URL",         "redis://localhost:6379/15")
os.environ.setdefault("GEMINI_API_KEY",    "test_key_not_real")
os.environ.setdefault("LOG_FORMAT",        "console")
os.environ.setdefault("LOG_LEVEL",         "WARNING")

import pytest
from datetime import datetime
from sqlalchemy import text


@pytest.fixture(autouse=True)
def fresh_db(tmp_path_factory):
    # Function-scoped (not module-scoped) — each test needs an isolated jobs
    # table since these tests assert exact sample_size/percentile values.
    tmp = tmp_path_factory.mktemp("db")
    db_path    = str(tmp / "test_salary_intel.db")
    sqlite_url = f"sqlite:///{db_path}"

    from marketforge.memory import postgres
    from marketforge.config.settings import settings as _settings

    old_engine   = postgres._sync_engine
    old_sync_url = _settings.database_url_sync

    postgres._sync_engine       = None
    _settings.database_url_sync = sqlite_url
    os.environ["DATABASE_URL_SYNC"] = sqlite_url

    from marketforge.memory.postgres import init_database
    init_database()
    yield db_path

    if postgres._sync_engine is not None:
        postgres._sync_engine.dispose()
    postgres._sync_engine       = None
    _settings.database_url_sync = old_sync_url
    os.environ["DATABASE_URL_SYNC"] = old_sync_url
    if old_engine is not None:
        postgres._sync_engine = old_engine


@pytest.fixture
def engine():
    from marketforge.memory.postgres import get_sync_engine
    return get_sync_engine()


def _insert_job(conn, job_id: str, salary_min: float, salary_currency: str, now: str):
    conn.execute(text("""
        INSERT INTO jobs
          (job_id, dedup_hash, run_id, title, company, location, source, description,
           salary_min, salary_max, salary_currency, scraped_at)
        VALUES (:jid, :jid, 'seed', 'ML Engineer', 'Co', 'London', 'test', '',
                :smin, :smin, :cur, :now)
    """), {"jid": job_id, "smin": salary_min, "cur": salary_currency, "now": now})


class TestCurrencyFilter:
    def test_non_gbp_rows_excluded_from_percentiles(self, fresh_db, engine):
        now = datetime.utcnow().isoformat()
        with engine.connect() as conn:
            # 10 uniform GBP rows at 60,000 -> p50 should land exactly on 60,000
            for i in range(10):
                _insert_job(conn, f"gbp_{i}", 60_000, "GBP", now)
            # 5 USD rows at 200,000 -> would drag every percentile upward if
            # the currency filter didn't exist
            for i in range(5):
                _insert_job(conn, f"usd_{i}", 200_000, "USD", now)
            conn.commit()

        from marketforge.agents.market_analysis.lead_agent import SalaryIntelligenceAgent
        agent = SalaryIntelligenceAgent()
        out = asyncio.run(agent.run({"week_start": now[:10]}))

        assert out["sample_size"] == 10
        assert out["salary_p50"] == 60_000


class TestIQROutlierTrimming:
    def test_extreme_outlier_excluded_once_sample_large_enough(self, fresh_db, engine):
        now = datetime.utcnow().isoformat()
        with engine.connect() as conn:
            # Tight cluster of 10 GBP salaries, 58k-67k
            for i, val in enumerate(range(58_000, 68_000, 1_000)):
                _insert_job(conn, f"cluster_{i}", val, "GBP", now)
            # One extreme outlier — inside the absolute £20k-£300k bound,
            # but a clear statistical outlier against the tight cluster.
            _insert_job(conn, "outlier_1", 295_000, "GBP", now)
            conn.commit()

        from marketforge.agents.market_analysis.lead_agent import SalaryIntelligenceAgent
        agent = SalaryIntelligenceAgent()
        out = asyncio.run(agent.run({"week_start": now[:10]}))

        # The outlier should have been IQR-trimmed, leaving only the cluster.
        assert out["sample_size"] == 10
        assert out["salary_p90"] < 100_000

    def test_iqr_trim_helper_directly(self):
        from marketforge.agents.market_analysis.lead_agent import SalaryIntelligenceAgent
        values = [58_000, 59_000, 60_000, 61_000, 62_000, 63_000, 64_000, 65_000, 66_000, 67_000, 295_000]
        trimmed = SalaryIntelligenceAgent._iqr_trim(values)
        assert 295_000 not in trimmed
        assert len(trimmed) == 10
