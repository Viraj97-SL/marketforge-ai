"""
MarketForge AI — Entry-level / graduate-reality API endpoint tests.

Covers the four new endpoints behind the Market page's graduate-reality
story: /external/graduate-outcomes, /entry-level/skill-shift,
/entry-level/universal-skills, /entry-level/company-mix.

Uses FastAPI TestClient + a dedicated SQLite DB seeded with jobs across
multiple experience_level / role_category / company_stage combinations —
see tests/test_api.py for the same overall pattern.
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///./test_api_entry_level.db")
os.environ.setdefault("REDIS_URL",         "redis://localhost:6379/15")
os.environ.setdefault("GEMINI_API_KEY",    "test_key_not_real")
os.environ.setdefault("LOG_FORMAT",        "console")
os.environ.setdefault("LOG_LEVEL",         "WARNING")

import pytest
from datetime import datetime
from sqlalchemy import text


@pytest.fixture(scope="module")
def test_db(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("entry_level_db")
    db_path    = str(tmp / "entry_level_test.db")
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


@pytest.fixture(scope="module")
def populated_db(test_db):
    from marketforge.memory.postgres import get_sync_engine
    engine = get_sync_engine()
    now = datetime.utcnow().isoformat()

    jobs = [
        # job_id, role_category, experience_level, company_stage, is_startup
        ("el_001", "ml_engineer",     "junior", "startup",    1),
        ("el_002", "ml_engineer",     "junior", "startup",    1),
        ("el_003", "ml_engineer",     "senior", "enterprise", 0),
        ("el_004", "data_scientist",  "junior", "enterprise", 0),
        ("el_005", "data_scientist",  "senior", "enterprise", 0),
        ("el_006", "ai_engineer",     "junior", "research",   0),
        ("el_007", "ai_engineer",     "mid",    "enterprise", 0),
        # Extra senior-only postings so "Kubernetes" outranks "Excel"
        # overall while never appearing among juniors — this is what
        # makes Excel's rank genuinely better at entry level than overall.
        ("el_008", "ml_engineer",     "senior", "enterprise", 0),
        ("el_009", "ml_engineer",     "senior", "enterprise", 0),
        ("el_010", "data_scientist",  "senior", "enterprise", 0),
        ("el_011", "data_scientist",  "senior", "enterprise", 0),
        ("el_012", "ai_engineer",     "senior", "enterprise", 0),
    ]
    skills = {
        # skill: [job_ids] — SQL spans every role & level; PyTorch is
        # senior-heavy; Excel is junior-only. Kubernetes is senior-only
        # with a HIGHER overall count than Excel, so it pushes Excel's
        # overall rank down while Excel's junior rank stays near the top
        # — the entry-level "rank_delta" signal under test.
        "SQL":        ["el_001", "el_002", "el_003", "el_004", "el_005", "el_006", "el_007"],
        "Git":        ["el_001", "el_004", "el_006"],
        "PyTorch":    ["el_003", "el_005", "el_007"],
        "Excel":      ["el_001", "el_002", "el_004", "el_006"],
        "Kubernetes": ["el_008", "el_009", "el_010", "el_011", "el_012"],
    }

    with engine.connect() as conn:
        for jid, role, level, stage, is_startup in jobs:
            conn.execute(text("""
                INSERT OR IGNORE INTO jobs
                  (job_id, dedup_hash, run_id, title, company, location, source, description,
                   role_category, experience_level, company_stage, is_startup, scraped_at)
                VALUES (:jid, :jid, 'seed', 'Role', 'Co', 'London', 'test', '',
                        :role, :level, :stage, :startup, :now)
            """), {"jid": jid, "role": role, "level": level, "stage": stage,
                    "startup": is_startup, "now": now})

        for skill, job_ids in skills.items():
            for jid in job_ids:
                conn.execute(text("""
                    INSERT INTO job_skills (job_id, skill, skill_category, extraction_method, confidence)
                    VALUES (:jid, :skill, 'general', 'gate1', 1.0)
                """), {"jid": jid, "skill": skill})

        # Graduate outcomes rows
        conn.execute(text("""
            INSERT INTO external_grad_employment
              (year, employment_rate, hs_employment_rate, unemployment_rate, inactivity_rate)
            VALUES (2024, 88.5, 70.6, 3.2, 8.6)
        """))
        conn.execute(text("""
            INSERT INTO external_grad_headcount (year, subject, qualifiers_count)
            VALUES ('201920', 'Computing', 20365)
        """))
        conn.commit()

    return test_db


@pytest.fixture(scope="module")
def client(populated_db):
    from fastapi.testclient import TestClient
    from api.main import app
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


class TestGraduateOutcomesEndpoint:
    def test_returns_seeded_employment_and_headcount(self, client):
        data = client.get("/api/v1/market/external/graduate-outcomes").json()
        assert data["employment"]["year"] == 2024
        assert data["employment"]["employment_rate"] == 88.5
        assert data["computing_qualifiers"]["qualifiers_count"] == 20365
        assert "DfE" in data["source"]
        assert "unsegmented" in data["methodology"]


class TestEntryLevelSkillShiftEndpoint:
    def test_excel_shifts_up_at_entry_level(self, client):
        data = client.get("/api/v1/market/entry-level/skill-shift").json()
        shifted_skills = {s["skill"]: s for s in data["shifts"]}
        # Excel appears only in junior postings -> should rank well among
        # juniors while ranking poorly (or absent) overall -> positive delta
        assert "Excel" in shifted_skills
        assert shifted_skills["Excel"]["rank_delta"] > 0
        assert data["sample_size_junior"] > 0


class TestEntryLevelUniversalSkillsEndpoint:
    def test_sql_has_widest_role_span(self, client):
        data = client.get("/api/v1/market/entry-level/universal-skills").json()
        top_skill = data["skills"][0]
        assert top_skill["skill"] == "SQL"
        assert top_skill["role_span"] == 3  # ml_engineer, data_scientist, ai_engineer
        matrix_roles_for_sql = {m["role_category"] for m in data["matrix"] if m["skill"] == "SQL"}
        assert matrix_roles_for_sql == {"ml_engineer", "data_scientist", "ai_engineer"}


class TestEntryLevelCompanyMixEndpoint:
    def test_buckets_only_junior_postings(self, client):
        data = client.get("/api/v1/market/entry-level/company-mix").json()
        # 4 junior jobs seeded: el_001, el_002 (startup), el_004 (enterprise), el_006 (research)
        assert data["sample_size"] == 4
        by_type = {m["type"]: m["job_count"] for m in data["mix"]}
        assert by_type["Startup (<50)"] == 2
        assert by_type["Enterprise (500+)"] == 1
        assert by_type["Research / Academic"] == 1
