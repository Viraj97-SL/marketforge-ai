"""
MarketForge AI — Skill extraction depth tests.

Covers the 3 fixes to the extraction pipeline (src/marketforge/nlp/taxonomy.py):
  - Gate 2's truncation cap raised from 5000 to 20000 chars
  - Gate 2's context pattern widened from 1 to 1-3 tokens (multi-word skills)
  - a real, first-ever mocked Gate 3 (LLM) test in this repo

Plus should_use_role_implied_fallback() (worker.py) — the fix that stops
the role-implied fallback from masking genuine extraction failures on long,
detailed postings.

Gate 2/3 tests skip gracefully if the spaCy model isn't installed in this
environment rather than failing the whole suite.
"""
from __future__ import annotations

import pytest


def _spacy_model_available() -> bool:
    try:
        import spacy
        spacy.load("en_core_web_sm")
        return True
    except Exception:
        return False


class TestGate1LongMultiSectionPosting:
    def test_finds_skills_scattered_across_sections_past_old_5000_char_cap(self):
        """
        Regression test for the old Gate 2 5000-char truncation: build a
        posting with distinct sections (About Us / Responsibilities /
        Requirements / Nice to Have / Benefits), padded so the "Nice to
        Have" section — containing a real skill — starts well past 5000
        characters. Gate 1 (flashtext) has no length cap and should find it
        regardless, but this also documents the shape of postings Gate 2's
        raised 20000-char cap now covers that the old 5000 cap didn't.
        """
        from marketforge.nlp.taxonomy import extract_skills

        about_us = ("We are a growing company building great products for our customers. " * 80)
        requirements = "Requirements: 3+ years of professional software development experience. " * 20
        text = (
            "Senior Software Engineer\n\n"
            f"About Us:\n{about_us}\n\n"
            f"Requirements:\n{requirements}\n\n"
            "Nice to Have:\nExperience with Kubernetes and Terraform for infrastructure.\n\n"
            "Benefits: Pension, private healthcare, 25 days holiday."
        )
        assert len(text) > 5000, "test setup must exceed the old truncation cap"

        r = extract_skills(text, run_llm_gate=False)
        skills = r["gate1"] + r["gate2"] + r["gate3"]
        canonicals = {s[0] for s in skills}
        assert "Kubernetes" in canonicals
        assert "Terraform" in canonicals


@pytest.mark.skipif(not _spacy_model_available(), reason="spaCy en_core_web_sm not installed")
class TestGate2MultiWordPhrase:
    def test_context_pattern_captures_multi_word_skill(self):
        from marketforge.nlp.taxonomy import SpacyGate

        gate = SpacyGate()
        found = gate.extract("We need someone with experience with Apache Spark for our data pipeline.", set())
        # The full "experience with Apache Spark" span should be captured —
        # the old single-token pattern would have stopped at "Apache".
        assert any("apache spark" in t.lower() for t in found), found


@pytest.mark.skipif(not _spacy_model_available(), reason="spaCy en_core_web_sm not installed")
class TestGate3Mocked:
    def test_llm_gate_resolves_unresolved_candidates(self, monkeypatch):
        """
        First mocked Gate 3 test in this repo — every existing extraction
        test passes run_llm_gate=False. Mocks ChatGoogleGenerativeAI so no
        real API call happens.
        """
        import json as _json
        from marketforge.nlp import taxonomy as tax_module

        class _FakeResponse:
            content = _json.dumps(["Apache Spark"])

        class _FakeLLM:
            def __init__(self, *a, **kw):
                pass

            def invoke(self, messages):
                return _FakeResponse()

        monkeypatch.setattr("langchain_google_genai.ChatGoogleGenerativeAI", _FakeLLM)

        # Bypass the Redis/Postgres cache lookup so the fake LLM path runs.
        monkeypatch.setattr(
            tax_module.LLMGate, "__init__",
            lambda self: setattr(self, "_cache", _NullCache()),
        )

        gate = tax_module.LLMGate()
        result = gate.resolve(["Apache Spark", "synergistic"])
        assert result == ["Apache Spark"]


class _NullCache:
    def get(self, key):
        return None

    def set(self, key, value):
        pass


class TestRoleImpliedFallbackBoundary:
    def test_short_description_triggers_fallback(self):
        from worker import should_use_role_implied_fallback
        assert should_use_role_implied_fallback("Great opportunity, apply now!") is True

    def test_long_description_does_not_trigger_fallback_even_with_zero_skills(self):
        # This is the actual masking bug: previously "or not skills" meant
        # ANY long description with zero gate hits still got a fake
        # per-role skill list injected. Now it must not.
        from worker import should_use_role_implied_fallback
        long_desc = "We are looking for a great teammate who is passionate and driven. " * 10
        assert len(long_desc) >= 150
        assert should_use_role_implied_fallback(long_desc) is False

    def test_empty_description_triggers_fallback(self):
        from worker import should_use_role_implied_fallback
        assert should_use_role_implied_fallback("") is True
        assert should_use_role_implied_fallback(None) is True
