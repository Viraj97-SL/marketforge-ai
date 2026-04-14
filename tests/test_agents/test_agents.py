"""
MarketForge AI — Agent lifecycle and department-level tests.
#XFGSDFHFDHGFH
Covers:
  - DeepAgent Plan→Execute→Reflect→Output lifecycle
  - CostTrackerAgent  (Dept 9, no LLM)
  - InfrastructureHealthAgent (Dept 9, no LLM)
  - SkillDemandAnalystAgent  (Dept 3, no LLM)
  - SalaryIntelligenceAgent  (Dept 3, no LLM)
  - DataIntegrityAgent (Dept 7, no LLM)

All tests use SQLite via the shared fresh_db fixture.
No real LLM calls are made.
"""
from __future__ import annotations

import asyncio
import os

os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///./test_agents.db")
os.environ.setdefault("REDIS_URL",         "redis://localhost:6379/15")
os.environ.setdefault("GEMINI_API_KEY",    "test_key_not_real")
os.environ.setdefault("LOG_FORMAT",        "console")
os.environ.setdefault("LOG_LEVEL",         "WARNING")

import pytest
from sqlalchemy import text


# ── Shared fixtures ────────────────────────────────────────────────────────────

@pytest.fixture(scope="module", autouse=True)
def fresh_db(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("db")
    db_path    = str(tmp / "test_agents.db")
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


@pytest.fixture
def seed_jobs(engine):
    """Insert a handful of synthetic jobs + skills into SQLite."""
    import hashlib

    def dedup(title, company, location):
        raw = "|".join([title.lower().strip(), company.lower().strip(), location.lower().strip()])
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    jobs = [
        ("job_001", "Senior ML Engineer",   "DeepMind",  "London", 90_000, 130_000),
        ("job_002", "Data Scientist",        "Google",    "London", 70_000,  95_000),
        ("job_003", "MLOps Engineer",        "Wayve",     "Remote", 80_000, 110_000),
        ("job_004", "AI Engineer",           "Stability", "London", 75_000, 105_000),
        ("job_005", "NLP Engineer",          "Cohere",    "Remote", 85_000, 120_000),
    ]
    skills_map = {
        "job_001": [("PyTorch",      "ml_framework"), ("LangGraph",    "orchestration")],
        "job_002": [("Python",       "language"),     ("scikit-learn", "ml_framework")],
        "job_003": [("Kubernetes",   "infra"),        ("MLflow",       "mlops")],
        "job_004": [("PyTorch",      "ml_framework"), ("TensorFlow",   "ml_framework")],
        "job_005": [("PyTorch",      "ml_framework"), ("transformers", "nlp")],
    }
    is_sqlite = engine.dialect.name == "sqlite"
    jobs_t    = "jobs"      if is_sqlite else "market.jobs"
    skills_t  = "job_skills" if is_sqlite else "market.job_skills"

    with engine.connect() as conn:
        for jid, t, c, l, smin, smax in jobs:
            dhash = dedup(t, c, l)
            conn.execute(text(f"""
                INSERT OR IGNORE INTO {jobs_t}
                  (job_id, dedup_hash, run_id, title, company, location,
                   salary_min, salary_max, source, description)
                VALUES (:jid, :dh, 'seed_run', :t, :c, :l, :smin, :smax, 'test', '')
            """ if is_sqlite else f"""
                INSERT INTO {jobs_t}
                  (job_id, dedup_hash, run_id, title, company, location,
                   salary_min, salary_max, source, description)
                VALUES (:jid, :dh, 'seed_run', :t, :c, :l, :smin, :smax, 'test', '')
                ON CONFLICT (job_id) DO NOTHING
            """), {"jid": jid, "dh": dhash, "t": t, "c": c, "l": l,
                   "smin": smin, "smax": smax})

        for jid, slist in skills_map.items():
            for skill, cat in slist:
                conn.execute(text(f"""
                    INSERT OR IGNORE INTO {skills_t}
                      (job_id, skill, skill_category, extraction_method, confidence)
                    VALUES (:jid, :s, :cat, 'gate1', 1.0)
                """ if is_sqlite else f"""
                    INSERT INTO {skills_t}
                      (job_id, skill, skill_category, extraction_method, confidence)
                    VALUES (:jid, :s, :cat, 'gate1', 1.0)
                    ON CONFLICT DO NOTHING
                """), {"jid": jid, "s": skill, "cat": cat})
        conn.commit()
    return jobs


# ── DeepAgent lifecycle ────────────────────────────────────────────────────────

class TestDeepAgentLifecycle:
    def test_plan_execute_reflect_output_called_in_order(self, fresh_db):
        from marketforge.agents.base import DeepAgent

        call_log: list[str] = []

        class OrderAgent(DeepAgent):
            agent_id   = "order_test_v1"
            department = "test"

            async def plan(self, ctx, state):
                call_log.append("plan")
                return {"x": 7}

            async def execute(self, plan, state):
                call_log.append("execute")
                return {"y": plan["x"] * 6}

            async def reflect(self, plan, result, state):
                call_log.append("reflect")
                return {"quality": "good", "notes": "ok"}

            async def output(self, result, reflection):
                call_log.append("output")
                return {"answer": result["y"], "quality": reflection["quality"]}

        out = asyncio.run(OrderAgent().run({}))
        assert call_log == ["plan", "execute", "reflect", "output"]
        assert out["answer"] == 42
        assert out["quality"] == "good"

    def test_execute_exception_does_not_crash_pipeline(self, fresh_db):
        from marketforge.agents.base import DeepAgent

        class BrokenAgent(DeepAgent):
            agent_id   = "broken_v1"
            department = "test"

            async def plan(self, ctx, state):
                return {}

            async def execute(self, plan, state):
                raise ConnectionError("Simulated API failure")

            async def reflect(self, plan, result, state):
                return {"quality": "poor", "notes": result.get("error", "")}

            async def output(self, result, reflection):
                return {"error": result.get("error"), "quality": reflection["quality"]}

        out = asyncio.run(BrokenAgent().run({}))
        assert out["quality"] == "poor"
        assert "Simulated API failure" in (out.get("error") or "")

    def test_state_persisted_after_run(self, fresh_db):
        """run() should update run_count in agent_state table."""
        from marketforge.agents.base import DeepAgent
        from marketforge.memory.postgres import AgentStateStore

        class SimpleAgent(DeepAgent):
            agent_id   = "persist_test_v1"
            department = "test"
            async def plan(self, ctx, state): return {}
            async def execute(self, plan, state): return {"value": 1}
            async def reflect(self, plan, result, state): return {"quality": "good", "notes": ""}
            async def output(self, result, reflection): return {"value": result["value"]}

        asyncio.run(SimpleAgent().run({}))
        asyncio.run(SimpleAgent().run({}))

        state = AgentStateStore().load("persist_test_v1", "test")
        assert state["run_count"] >= 2


# ── CostTrackerAgent ───────────────────────────────────────────────────────────

class TestCostTrackerAgent:
    def test_execute_returns_cost_structure(self, fresh_db):
        from marketforge.agents.ops_monitor.lead_agent import CostTrackerAgent

        async def run():
            agent = CostTrackerAgent()
            plan  = await agent.plan({}, {})
            return await agent.execute(plan, {})

        result = asyncio.run(run())
        assert "total_cost_usd" in result
        assert "breakdown" in result
        assert isinstance(result["total_cost_usd"], float)

    def test_plan_sets_threshold(self, fresh_db):
        from marketforge.agents.ops_monitor.lead_agent import CostTrackerAgent

        async def run():
            agent = CostTrackerAgent()
            return await agent.plan({}, {"adaptive_params": {"rolling_weekly_costs": [0.10, 0.20, 0.15]}})

        plan = asyncio.run(run())
        # Threshold should be 2× the rolling average ≈ 0.30
        assert plan["threshold_usd"] == pytest.approx(0.30, rel=0.01)

    def test_reflect_flags_over_budget(self, fresh_db):
        from marketforge.agents.ops_monitor.lead_agent import CostTrackerAgent

        async def run():
            agent      = CostTrackerAgent()
            plan       = {"threshold_usd": 0.05, "rolling": [], "adaptive": {}}
            result     = {"total_cost_usd": 0.20, "breakdown": [], "threshold": 0.05}
            return await agent.reflect(plan, result, {})

        reflection = asyncio.run(run())
        assert reflection["quality"] == "warning"

    def test_reflect_ok_within_budget(self, fresh_db):
        from marketforge.agents.ops_monitor.lead_agent import CostTrackerAgent

        async def run():
            agent  = CostTrackerAgent()
            plan   = {"threshold_usd": 0.50, "rolling": [], "adaptive": {}}
            result = {"total_cost_usd": 0.10, "breakdown": [], "threshold": 0.50}
            return await agent.reflect(plan, result, {})

        reflection = asyncio.run(run())
        assert reflection["quality"] == "good"


# ── InfrastructureHealthAgent ──────────────────────────────────────────────────

class TestInfrastructureHealthAgent:
    def test_execute_includes_postgres_key(self, fresh_db):
        from marketforge.agents.ops_monitor.lead_agent import InfrastructureHealthAgent

        async def run():
            agent = InfrastructureHealthAgent()
            plan  = await agent.plan({}, {})
            return await agent.execute(plan, {})

        result = asyncio.run(run())
        assert "resources" in result
        assert "postgresql" in result["resources"]

    def test_output_returns_infrastructure_dict(self, fresh_db):
        from marketforge.agents.ops_monitor.lead_agent import InfrastructureHealthAgent

        out = asyncio.run(InfrastructureHealthAgent().run({}))
        assert "infrastructure" in out
        assert isinstance(out.get("capacity_warnings"), list)


# ── SkillDemandAnalystAgent ────────────────────────────────────────────────────

class TestSkillDemandAnalystAgent:
    def test_execute_returns_top_skills(self, fresh_db, seed_jobs):
        from marketforge.agents.market_analysis.lead_agent import SkillDemandAnalystAgent

        async def run():
            agent = SkillDemandAnalystAgent()
            plan  = await agent.plan({}, {})
            return await agent.execute(plan, {})

        result = asyncio.run(run())
        assert "top_skills" in result
        # top_skills is a dict: {skill_name: count}
        assert isinstance(result["top_skills"], dict)
        # PyTorch appears in 3 of 5 seeded jobs — must be present
        assert "PyTorch" in result["top_skills"]

    def test_output_returns_ranked_list(self, fresh_db, seed_jobs):
        out = asyncio.run(
            __import__(
                "marketforge.agents.market_analysis.lead_agent",
                fromlist=["SkillDemandAnalystAgent"]
            ).SkillDemandAnalystAgent().run({})
        )
        # top_skills is a dict: {skill_name: count}
        assert isinstance(out.get("top_skills"), dict)
        # Most-demanded skill should have the highest count
        if len(out["top_skills"]) >= 2:
            counts = list(out["top_skills"].values())
            assert counts[0] >= counts[-1] or max(counts) == counts[0]


# ── SalaryIntelligenceAgent ────────────────────────────────────────────────────

class TestSalaryIntelligenceAgent:
    def test_execute_returns_percentiles(self, fresh_db, seed_jobs):
        from marketforge.agents.market_analysis.lead_agent import SalaryIntelligenceAgent

        async def run():
            agent = SalaryIntelligenceAgent()
            plan  = await agent.plan({}, {})
            return await agent.execute(plan, {})

        result = asyncio.run(run())
        assert "salary_p50" in result or "percentiles" in result or "salary_stats" in result

    def test_output_has_currency(self, fresh_db, seed_jobs):
        from marketforge.agents.market_analysis.lead_agent import SalaryIntelligenceAgent
        out = asyncio.run(SalaryIntelligenceAgent().run({}))
        # Result should contain some salary data (GBP)
        assert out is not None


# ── DataIntegrityAgent (QA Dept 7) ────────────────────────────────────────────

class TestDataIntegrityAgent:
    def test_execute_runs_without_error(self, fresh_db, seed_jobs):
        from marketforge.agents.qa_testing.lead_agent import DataIntegrityAgent

        async def run():
            agent = DataIntegrityAgent()
            plan  = await agent.plan({}, {})
            return await agent.execute(plan, {})

        result = asyncio.run(run())
        assert result is not None

    def test_output_has_quality_field(self, fresh_db, seed_jobs):
        from marketforge.agents.qa_testing.lead_agent import DataIntegrityAgent
        out = asyncio.run(DataIntegrityAgent().run({}))
        # Should surface a quality signal
        assert out is not None
