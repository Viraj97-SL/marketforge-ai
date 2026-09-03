"""
MarketForge AI — AI/ML relevance gate tests.

Covers is_ai_ml_relevant() in src/marketforge/nlp/taxonomy.py — the actual
reject-before-store gate wired into
agents/data_collection/lead_agent.py::DataCollectionLeadAgent.execute(),
which stops irrelevant postings (generic "Engineer" titles, clerks,
drivers, etc.) from Adzuna/Reed reaching market.jobs. classify_role()
never rejects anything by itself; this is the function that does.
"""
from __future__ import annotations

from marketforge.nlp.taxonomy import is_ai_ml_relevant


class TestPositiveCases:
    def test_ml_engineer_title_alone(self):
        assert is_ai_ml_relevant("ML Engineer", "") is True

    def test_data_scientist_title_alone(self):
        assert is_ai_ml_relevant("Data Scientist", "") is True

    def test_ai_product_manager_title_alone(self):
        # No "eng"/"scien" match in _ROLE_PATTERNS's keyword regexes, but
        # ai_product_manager is a real classify_role() category.
        assert is_ai_ml_relevant("AI Product Manager", "") is True

    def test_generic_title_with_ai_ml_description(self):
        assert is_ai_ml_relevant(
            "Software Engineer",
            "Build and deploy PyTorch models for our LLM-powered product.",
        ) is True


class TestNegativeCases:
    def test_electrical_engineer_rejected(self):
        assert is_ai_ml_relevant("Electrical Engineer", "Design electrical systems for buildings.") is False

    def test_legal_clerk_rejected(self):
        assert is_ai_ml_relevant("Legal Clerk", "Filing and admin support for a law firm.") is False

    def test_warehouse_operative_rejected(self):
        assert is_ai_ml_relevant("Warehouse Operative", "Pick and pack orders in our distribution centre.") is False

    def test_generic_software_engineer_no_ai_content_rejected(self):
        assert is_ai_ml_relevant(
            "Software Engineer",
            "Build and maintain our e-commerce checkout flow using Java and Spring.",
        ) is False

    def test_negative_title_wins_even_with_stray_positive_keyword(self):
        # A negative title match should short-circuit before the positive
        # keyword scan, even if the description happens to mention an AI
        # term in passing (e.g. company boilerplate).
        assert is_ai_ml_relevant(
            "Warehouse Driver",
            "Our company also has a machine learning team, but this role is purely logistics.",
        ) is False
