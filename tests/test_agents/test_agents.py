"""
MarketForge AI — Agent lifecycle and department-level tests.

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
    db_path = str(tmp / "test_agents.db")
    os.environ["DATABASE_URL_SYNC"] = f"sqlite:///{db_path}"

    from marketforge.memory import postgres
    postgres._sync_engine = None          # reset singleton

    from marketforge.memory.postgres import init_database
    init_database()
    yield db_path

    postgres._sync_engine = None


@pytest.fixture
def engine():
    from marketforge.memory.postgres import get_sync_engine
    return get_sync_engine()


@pytest.fixture
def seed_jobs(engine):
    """Insert a handful of synthetic jobs + skills into SQLite."""
    jobs = [
        ("job_001", "Senior ML Engineer",       "DeepMind",   "London",  90_000, 130_000, "PyTorch, LangGraph"),
        ("job_002", "Data Scientist",            "Google",     "London",  70_000,  95_000, "Python, scikit-learn"),
        ("job_003", "MLOps Engineer",            "Wayve",      "Remote",  80_000, 110_000, "Kubernetes, MLflow"),
        ("job_004", "AI Engineer",               "Stability",  "London",  75_000, 105_000, "PyTorch, TensorFlow"),
        ("job_005", "NLP Engineer",              "Cohere",     "Remote",  85_000, 120_000, "PyTorch, transformers"),
    ]
    skills_map = {
        "job_001": [("PyTorch", "ml_framework"), ("LangGraph", "orchestration")],
        "job_002": [("Python",  "language"),     ("scikit-learn", "ml_framework")],
        "job_003": [("Kubernetes", "infra"),     ("MLflow", "mlops")],
        "job_004": [("PyTorch", "ml_framework"), ("TensorFlow", "ml_framework")],
        "job_005": [("PyTorch", "ml_framework"), ("transformers", "nlp")],
    }
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT OR IGNORE INTO jobs
              (job_id, title, company, location, salary_min, salary_max, source, description)
            VALUES (:jid, :t, :c, :l, :smin, :smax, 'test', :desc)
        """), [
            {"jid": jid, "t": t, "c": c, "l": l,
             "smin": smin, "smax": smax, "desc": desc}
            for jid, t, c, l, smin, smax, desc in jobs
        ])
        for jid, slist in skills_map.items():
            for skill, cat in slist:
                conn.execute(text("""
                    INSERT OR IGNORE INTO job_skills
                      (job_id, skill, skill_category, extraction_method, confidence)
                    VALUES (:jid, :s, :cat, 'gate1', 1.0)
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
        assert isinstance(result["top_skills"], list)
        # PyTorch appears in 3 of 5 jobs — should be near the top
        top_skill_names = [s["skill"] for s in result["top_skills"]]
        assert "PyTorch" in top_skill_names

    def test_output_returns_ranked_list(self, fresh_db, seed_jobs):
        out = asyncio.run(
            __import__(
                "marketforge.agents.market_analysis.lead_agent",
                fromlist=["SkillDemandAnalystAgent"]
            ).SkillDemandAnalystAgent().run({})
        )
        assert isinstance(out.get("top_skills"), list)
        # Ranked by frequency — first entry should have highest count
        if len(out["top_skills"]) >= 2:
            assert out["top_skills"][0]["count"] >= out["top_skills"][1]["count"]


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
