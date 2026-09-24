"""
MarketForge AI — CV Gap Analyser Tests.

Regression tests for the gap-list contradiction bug: a Gate-3 (LLM) paraphrase
of a skill already on the CV ("Retrieval-Augmented Generation" vs. the CV's
"RAG") must not surface as a gap, near-duplicate concepts under two different
surface forms must not both appear, and broad umbrella labels ("Machine
Learning") must not be listed once the CV already demonstrates the concept
through specific tools.

analyse_gaps() hits the DB via _fetch_market_data() — monkeypatched here so
these tests exercise the dedup/ranking logic in isolation, no DB required.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import marketforge.cv.gap_analyser as gap_analyser
from marketforge.cv.gap_analyser import analyse_gaps


def _mock_market(monkeypatch, top_skills: dict[str, int], rising: list[str] | None = None) -> None:
    monkeypatch.setattr(
        gap_analyser, "_fetch_market_data",
        lambda target_role="": {"top_skills": top_skills, "rising_skills": rising or []},
    )


class TestCanonicalDedupAgainstCV:
    def test_gate3_paraphrase_of_cv_skill_is_not_a_gap(self, monkeypatch):
        # Bug: found "RAG" -> gap "Retrieval-Augmented Generation"
        _mock_market(monkeypatch, {"Retrieval-Augmented Generation": 100, "Docker": 80})
        result = analyse_gaps(cv_skills=["RAG"], target_role="ml_engineer")
        skills = [g.skill for g in result.all_gaps]
        assert "Retrieval-Augmented Generation" not in skills
        assert "Docker" in skills

    def test_gate3_alias_of_cv_skill_is_not_a_gap(self, monkeypatch):
        # Bug: found "LangGraph", "Multi-agent systems" -> gap "Agentic AI / Machine Learning"
        # "Agentic AI" alone is an existing alias of "Multi-agent systems".
        _mock_market(monkeypatch, {"Agentic AI": 100, "Docker": 80})
        result = analyse_gaps(cv_skills=["Multi-agent systems"], target_role="ml_engineer")
        skills = [g.skill for g in result.all_gaps]
        assert "Agentic AI" not in skills
        assert "Docker" in skills


class TestSelfDedupWithinGapList:
    def test_two_surface_forms_of_one_concept_collapse_to_one_gap(self, monkeypatch):
        # Bug: gap list contains both "GenAI" and "Generative AI"
        _mock_market(monkeypatch, {"GenAI": 100, "Generative AI": 90, "Docker": 80})
        result = analyse_gaps(cv_skills=[], target_role="ml_engineer")
        skills = [g.skill for g in result.all_gaps]
        genai_variants = [s for s in skills if s in ("GenAI", "Generative AI")]
        assert len(genai_variants) == 1


class TestUmbrellaSuppression:
    def test_machine_learning_suppressed_when_cv_shows_specific_ml_tools(self, monkeypatch):
        # Bug: found "PyTorch", "scikit-learn", "XGBoost", "LightGBM" -> gap "Machine Learning"
        _mock_market(monkeypatch, {"Machine Learning": 100, "Docker": 80})
        result = analyse_gaps(
            cv_skills=["PyTorch", "scikit-learn", "XGBoost", "LightGBM"],
            target_role="ml_engineer",
        )
        skills = [g.skill for g in result.all_gaps]
        assert "Machine Learning" not in skills
        assert "Docker" in skills

    def test_machine_learning_still_shown_when_cv_has_no_specific_ml_tools(self, monkeypatch):
        # Umbrella suppression must not swallow a genuine gap for a CV with
        # no ML tooling at all.
        _mock_market(monkeypatch, {"Machine Learning": 100})
        result = analyse_gaps(cv_skills=["Docker"], target_role="ml_engineer")
        skills = [g.skill for g in result.all_gaps]
        assert "Machine Learning" in skills

    def test_artificial_intelligence_suppressed_when_cv_shows_llm_and_agent_work(self, monkeypatch):
        _mock_market(monkeypatch, {"Artificial Intelligence": 100, "Docker": 80})
        result = analyse_gaps(
            cv_skills=["LangGraph", "Multi-agent systems"],
            target_role="ml_engineer",
        )
        skills = [g.skill for g in result.all_gaps]
        assert "Artificial Intelligence" not in skills
        assert "Docker" in skills


class TestBaselineBehaviourUnaffected:
    def test_genuinely_missing_specific_skill_still_appears(self, monkeypatch):
        _mock_market(monkeypatch, {"Kubernetes": 100})
        result = analyse_gaps(cv_skills=["Python"], target_role="ml_engineer")
        skills = [g.skill for g in result.all_gaps]
        assert "Kubernetes" in skills

    def test_no_market_data_returns_empty_analysis(self, monkeypatch):
        monkeypatch.setattr(gap_analyser, "_fetch_market_data", lambda target_role="": None)
        result = analyse_gaps(cv_skills=["Python"], target_role="ml_engineer")
        assert result.all_gaps == []
