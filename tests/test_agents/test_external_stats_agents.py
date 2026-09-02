"""
MarketForge AI — External trusted-source stats agent tests.

Covers:
  - OnsVacancyTrendAgent   (ONS generator CSV parsing + graceful fetch failure)
  - SponsorRegisterAgent   (company-name normalization + register matching)
  - AsheSalaryAgent        (skip-if-current-year, workbook header search)

All HTTP calls are mocked — no real network access. All DB access uses
SQLite via the shared fresh_db fixture (see tests/test_agents/test_agents.py
for the same pattern).
"""
from __future__ import annotations

import asyncio
import os

os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///./test_external_stats.db")
os.environ.setdefault("REDIS_URL",         "redis://localhost:6379/15")
os.environ.setdefault("GEMINI_API_KEY",    "test_key_not_real")
os.environ.setdefault("LOG_FORMAT",        "console")
os.environ.setdefault("LOG_LEVEL",         "WARNING")

import pytest
from sqlalchemy import text


# ── Shared fixtures (mirrors tests/test_agents/test_agents.py) ─────────────────

@pytest.fixture(scope="module", autouse=True)
def fresh_db(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("db")
    db_path    = str(tmp / "test_external_stats.db")
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


class _FakeResponse:
    def __init__(self, content: bytes = b"", json_data=None, status_code: int = 200):
        self.content      = content
        self._json_data   = json_data
        self.status_code  = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError("error", request=None, response=self)

    def json(self):
        return self._json_data


class _FakeAsyncClient:
    """Drop-in replacement for httpx.AsyncClient — routes by URL substring."""

    def __init__(self, routes: dict[str, _FakeResponse] | None = None, raise_on_get: bool = False):
        self._routes       = routes or {}
        self._raise_on_get = raise_on_get

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, params=None, **kwargs):
        if self._raise_on_get:
            raise ConnectionError("simulated network failure")
        for key, resp in self._routes.items():
            if key in url:
                return resp
        return _FakeResponse(content=b"", status_code=404)


# ══════════════════════════════════════════════════════════════════════════════
# OnsVacancyTrendAgent
# ══════════════════════════════════════════════════════════════════════════════

_ONS_GENERATOR_CSV = b"""\
"Title","UK Job Vacancies (thousands) - Information & Communication."
"CDID","JP9P"
"Source dataset ID","LMS"
"PreUnit",""
"Unit",""
"Release date","18-08-2026"
"Next release","15 September 2026"
"Important notes",
"2024","40"
"2025","35"
"2025 Q1","36"
"2025 Q2","35"
"2025 MAY","34"
"2025 JUN","35"
"2025 JUL","36"
"""


class TestOnsVacancyTrendAgent:
    def test_parses_only_monthly_rows(self, fresh_db, monkeypatch):
        import httpx
        from marketforge.agents.research.ons_vacancy_agent import OnsVacancyTrendAgent

        fake = _FakeAsyncClient(routes={"ons.gov.uk/generator": _FakeResponse(content=_ONS_GENERATOR_CSV)})
        monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: fake)

        agent = OnsVacancyTrendAgent()
        out = asyncio.run(agent.run({}))

        assert out["ons_vacancy_rows"] == 3
        assert out["quality"] == "good"

        from marketforge.memory.postgres import get_sync_engine
        engine = get_sync_engine()
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT month, vacancies_index FROM external_ons_vacancies ORDER BY month"
            )).fetchall()
        assert rows == [("2025-05", 34.0), ("2025-06", 35.0), ("2025-07", 36.0)]

    def test_fetch_failure_returns_poor_quality_without_crashing(self, fresh_db, monkeypatch):
        import httpx
        from marketforge.agents.research.ons_vacancy_agent import OnsVacancyTrendAgent

        fake = _FakeAsyncClient(raise_on_get=True)
        monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: fake)

        agent = OnsVacancyTrendAgent()
        out = asyncio.run(agent.run({}))

        assert out["ons_vacancy_rows"] == 0
        assert out["quality"] == "poor"


# ══════════════════════════════════════════════════════════════════════════════
# SponsorRegisterAgent
# ══════════════════════════════════════════════════════════════════════════════

_CONTENT_API_JSON = {
    "details": {
        "attachments": [
            {"content_type": "application/pdf", "url": "https://example.gov.uk/notes.pdf"},
            {"content_type": "text/csv", "url": "https://assets.gov.uk/register.csv"},
        ]
    }
}

_REGISTER_CSV = (
    b"Organisation Name,Town/City,County,Type & Rating,Route\n"
    b"DEEPMIND TECHNOLOGIES LIMITED,London,Greater London,Worker (A rating),Skilled Worker\n"
    b"ACME WIDGETS LTD,Manchester,Greater Manchester,Worker (A rating),Skilled Worker\n"
)


class TestSponsorRegisterAgent:
    def test_normalize_strips_suffixes_and_punctuation(self):
        from marketforge.agents.research.sponsor_register_agent import normalize_company_name

        assert normalize_company_name("DeepMind Technologies Limited") == "DEEPMIND TECHNOLOGIES"
        assert normalize_company_name("Acme Widgets Ltd.") == "ACME WIDGETS"
        assert normalize_company_name("") == ""

    def test_matches_seeded_companies_against_register(self, fresh_db, engine, monkeypatch):
        import httpx
        from datetime import datetime
        from marketforge.agents.research.sponsor_register_agent import SponsorRegisterAgent

        is_sqlite = engine.dialect.name == "sqlite"
        jobs_t = "jobs" if is_sqlite else "market.jobs"
        with engine.connect() as conn:
            for jid, company in [("j1", "DeepMind Technologies Limited"), ("j2", "Totally Unlicensed Co")]:
                conn.execute(text(f"""
                    INSERT OR IGNORE INTO {jobs_t}
                      (job_id, dedup_hash, run_id, title, company, location, source, description, scraped_at)
                    VALUES (:jid, :jid, 'seed', 'Engineer', :co, 'London', 'test', '', :now)
                """), {"jid": jid, "co": company, "now": datetime.utcnow().isoformat()})
            conn.commit()

        fake = _FakeAsyncClient(routes={
            "gov.uk/api/content": _FakeResponse(json_data=_CONTENT_API_JSON),
            "assets.gov.uk/register.csv": _FakeResponse(content=_REGISTER_CSV),
        })
        monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: fake)

        agent = SponsorRegisterAgent()
        out = asyncio.run(agent.run({}))

        assert out["sponsor_matches_updated"] == 2
        assert out["quality"] == "good"

        with engine.connect() as conn:
            rows = dict(conn.execute(text(
                "SELECT company_name_normalized, is_licensed_sponsor FROM external_sponsor_matches"
            )).fetchall())
        assert rows["DEEPMIND TECHNOLOGIES"] in (1, True)
        assert rows["TOTALLY UNLICENSED CO"] in (0, False)

    def test_no_csv_attachment_returns_empty_without_crashing(self, fresh_db, engine, monkeypatch):
        import httpx
        from marketforge.agents.research.sponsor_register_agent import SponsorRegisterAgent

        with engine.connect() as conn:
            conn.execute(text(f"""
                INSERT OR IGNORE INTO {"jobs" if engine.dialect.name == "sqlite" else "market.jobs"}
                  (job_id, dedup_hash, run_id, title, company, location, source, description, scraped_at)
                VALUES ('j3', 'j3', 'seed', 'Engineer', 'Some Co', 'London', 'test', '', '2026-01-01')
            """))
            conn.commit()

        fake = _FakeAsyncClient(routes={
            "gov.uk/api/content": _FakeResponse(json_data={"details": {"attachments": []}}),
        })
        monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: fake)

        agent = SponsorRegisterAgent()
        out = asyncio.run(agent.run({}))

        assert out["sponsor_matches_updated"] == 0
        assert out["quality"] == "poor"


# ══════════════════════════════════════════════════════════════════════════════
# AsheSalaryAgent
# ══════════════════════════════════════════════════════════════════════════════

class TestAsheSalaryAgent:
    def test_skips_when_current_year_already_stored(self, fresh_db, engine):
        from datetime import date
        from marketforge.agents.research.ashe_salary_agent import AsheSalaryAgent, _SOC_CODE

        this_year = date.today().year
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO external_ashe_salary
                  (role_category, soc_code, soc_title, year, salary_p25, salary_p50, salary_p75)
                VALUES ('ml_engineer', :soc, 'Programmers', :yr, 40000, 55000, 75000)
            """), {"soc": _SOC_CODE, "yr": this_year})
            conn.commit()

        agent = AsheSalaryAgent()
        out = asyncio.run(agent.run({}))

        assert out["ashe_benchmark_updated"] is False
        assert out["quality"] == "good"

    def test_parses_workbook_and_persists_all_role_categories(self, fresh_db, engine, monkeypatch):
        import httpx
        import pandas as pd
        from io import BytesIO
        from marketforge.agents.research.ashe_salary_agent import AsheSalaryAgent, _SOC_CODE, _ROLE_CATEGORIES

        # Clear any row from the previous test so this run isn't skipped.
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM external_ashe_salary"))
            conn.commit()

        df = pd.DataFrame([
            ["SOC", "Description", "25%", "Median", "75%"],
            [_SOC_CODE, "Programmers and software development professionals", 42000, 58000, 79000],
        ])
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="All", header=False, index=False)
        xlsx_bytes = buf.getvalue()

        html = '<a href="/file?uri=/datasets/table14/current/table14.xlsx">Download</a>'

        class _FakeTextResponse(_FakeResponse):
            @property
            def text(self):
                return self.content.decode()

        fake = _FakeAsyncClient(routes={
            "occupation4digitsoc2010ashetable14": _FakeTextResponse(content=html.encode()),
            "table14.xlsx": _FakeResponse(content=xlsx_bytes),
        })
        monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: fake)

        agent = AsheSalaryAgent()
        out = asyncio.run(agent.run({}))

        assert out["ashe_benchmark_updated"] is True
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT role_category, salary_p50 FROM external_ashe_salary"
            )).fetchall()
        assert len(rows) == len(_ROLE_CATEGORIES)
        assert all(p50 == 58000 for _, p50 in rows)
