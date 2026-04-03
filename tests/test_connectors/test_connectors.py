"""
MarketForge AI — Connector Tests (mocked HTTP via respx)

Tests AdzunaConnector and ReedConnector parsing and error-handling
without making real network calls.
"""
from __future__ import annotations

import os
os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///./test_marketforge.db")
os.environ.setdefault("REDIS_URL",         "redis://localhost:6379/15")
os.environ.setdefault("GEMINI_API_KEY",    "test_key_not_real")
os.environ.setdefault("LOG_FORMAT",        "console")
os.environ.setdefault("LOG_LEVEL",         "WARNING")

import pytest
import respx
import httpx


# ── Adzuna fixture data ────────────────────────────────────────────────────────

ADZUNA_TWO_RESULTS = {
    "results": [
        {
            "id": "az_001",
            "title": "Senior ML Engineer",
            "company": {"display_name": "DeepMind"},
            "location": {"display_name": "London"},
            "salary_min": 90_000,
            "salary_max": 130_000,
            "description": "PyTorch, LangGraph. Visa sponsorship available. Hybrid London.",
            "redirect_url": "https://api.adzuna.com/redirect/az_001",
            "created": "2026-03-28T00:00:00Z",
        },
        {
            "id": "az_002",
            "title": "Data Scientist",
            "company": {"display_name": "Google DeepMind"},
            "location": {"display_name": "London"},
            "salary_min": None,
            "salary_max": None,
            "description": "Python, scikit-learn, TensorFlow. UK citizens preferred. Remote.",
            "redirect_url": "https://api.adzuna.com/redirect/az_002",
            "created": "2026-03-28T00:00:00Z",
        },
    ]
}

ADZUNA_EMPTY = {"results": []}

# ── Reed fixture data ──────────────────────────────────────────────────────────

REED_ONE_RESULT = {
    "results": [
        {
            "jobId": 9001,
            "jobTitle": "AI Engineer",
            "employerName": "Wayve",
            "locationName": "London",
            "minimumSalary": 70_000,
            "maximumSalary": 100_000,
            "jobDescription": "PyTorch for autonomous vehicles. Hybrid working.",
            "jobUrl": "https://reed.co.uk/jobs/9001",
            "date": "28/03/2026",
        }
    ]
}

REED_EMPTY = {"results": []}


# ── AdzunaConnector tests ──────────────────────────────────────────────────────

class TestAdzunaConnector:

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_returns_correct_count(self):
        respx.get(url__startswith="https://api.adzuna.com").mock(
            return_value=httpx.Response(200, json=ADZUNA_TWO_RESULTS)
        )
        from marketforge.agents.data_collection.adzuna_agent import AdzunaConnector
        connector = AdzunaConnector()
        jobs = await connector.search(["ML Engineer"], max_per_query=10)
        assert len(jobs) == 2

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_parses_title_company_source(self):
        respx.get(url__startswith="https://api.adzuna.com").mock(
            return_value=httpx.Response(200, json=ADZUNA_TWO_RESULTS)
        )
        from marketforge.agents.data_collection.adzuna_agent import AdzunaConnector
        connector = AdzunaConnector()
        jobs = await connector.search(["ML Engineer"])
        assert jobs[0].title == "Senior ML Engineer"
        assert jobs[0].company == "DeepMind"
        assert jobs[0].source == "adzuna"
        assert jobs[0].job_id == "adzuna_az_001"

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_parses_salary(self):
        respx.get(url__startswith="https://api.adzuna.com").mock(
            return_value=httpx.Response(200, json=ADZUNA_TWO_RESULTS)
        )
        from marketforge.agents.data_collection.adzuna_agent import AdzunaConnector
        connector = AdzunaConnector()
        jobs = await connector.search(["ML Engineer"])
        assert jobs[0].salary_min == 90_000
        assert jobs[0].salary_max == 130_000
        assert jobs[1].salary_min is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_detects_work_model(self):
        respx.get(url__startswith="https://api.adzuna.com").mock(
            return_value=httpx.Response(200, json=ADZUNA_TWO_RESULTS)
        )
        from marketforge.agents.data_collection.adzuna_agent import AdzunaConnector
        connector = AdzunaConnector()
        jobs = await connector.search(["ML Engineer"])
        # First job has "Hybrid" in description
        assert jobs[0].work_model == "hybrid"
        # Second job has "Remote" in description
        assert jobs[1].work_model == "remote"

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_returns_empty_on_500(self):
        """HTTP 500 should be caught and return empty list, not raise."""
        respx.get(url__startswith="https://api.adzuna.com").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        from marketforge.agents.data_collection.adzuna_agent import AdzunaConnector
        connector = AdzunaConnector()
        jobs = await connector.search(["ML Engineer"])
        assert jobs == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_returns_empty_on_empty_results(self):
        respx.get(url__startswith="https://api.adzuna.com").mock(
            return_value=httpx.Response(200, json=ADZUNA_EMPTY)
        )
        from marketforge.agents.data_collection.adzuna_agent import AdzunaConnector
        connector = AdzunaConnector()
        jobs = await connector.search(["obscure query"])
        assert jobs == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_quota_stops_execution(self):
        """Connector should stop issuing calls once daily_quota is reached."""
        call_count = 0

        def count_handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, json=ADZUNA_EMPTY)

        respx.get(url__startswith="https://api.adzuna.com").mock(side_effect=count_handler)
        from marketforge.agents.data_collection.adzuna_agent import AdzunaConnector
        connector = AdzunaConnector()
        connector.daily_quota = 2  # type: ignore[assignment]

        await connector.search(["Q1", "Q2", "Q3", "Q4", "Q5"])
        assert call_count <= 2

    @pytest.mark.asyncio
    @respx.mock
    async def test_multiple_queries_aggregate(self):
        """Results across multiple queries are concatenated."""
        respx.get(url__startswith="https://api.adzuna.com").mock(
            return_value=httpx.Response(200, json=ADZUNA_TWO_RESULTS)
        )
        from marketforge.agents.data_collection.adzuna_agent import AdzunaConnector
        connector = AdzunaConnector()
        jobs = await connector.search(["ML Engineer", "Data Scientist"])
        # 2 results × 2 queries = 4 total (same mock response each time)
        assert len(jobs) == 4


# ── ReedConnector tests ────────────────────────────────────────────────────────

class TestReedConnector:

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_returns_jobs(self):
        respx.get("https://www.reed.co.uk/api/1.0/search").mock(
            return_value=httpx.Response(200, json=REED_ONE_RESULT)
        )
        from marketforge.agents.data_collection.reed_agent import ReedConnector
        connector = ReedConnector()
        jobs = await connector.search(["AI Engineer"])
        assert len(jobs) == 1
        assert jobs[0].title == "AI Engineer"
        assert jobs[0].company == "Wayve"
        assert jobs[0].source == "reed"
        assert jobs[0].job_id == "reed_9001"

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_parses_salary(self):
        respx.get("https://www.reed.co.uk/api/1.0/search").mock(
            return_value=httpx.Response(200, json=REED_ONE_RESULT)
        )
        from marketforge.agents.data_collection.reed_agent import ReedConnector
        connector = ReedConnector()
        jobs = await connector.search(["AI Engineer"])
        assert jobs[0].salary_min == 70_000
        assert jobs[0].salary_max == 100_000

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_parses_date(self):
        respx.get("https://www.reed.co.uk/api/1.0/search").mock(
            return_value=httpx.Response(200, json=REED_ONE_RESULT)
        )
        from marketforge.agents.data_collection.reed_agent import ReedConnector
        from datetime import date
        connector = ReedConnector()
        jobs = await connector.search(["AI Engineer"])
        assert jobs[0].posted_date == date(2026, 3, 28)

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_detects_work_model(self):
        respx.get("https://www.reed.co.uk/api/1.0/search").mock(
            return_value=httpx.Response(200, json=REED_ONE_RESULT)
        )
        from marketforge.agents.data_collection.reed_agent import ReedConnector
        connector = ReedConnector()
        jobs = await connector.search(["AI Engineer"])
        # Description has "Hybrid working"
        assert jobs[0].work_model == "hybrid"

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_empty_results(self):
        respx.get("https://www.reed.co.uk/api/1.0/search").mock(
            return_value=httpx.Response(200, json=REED_EMPTY)
        )
        from marketforge.agents.data_collection.reed_agent import ReedConnector
        connector = ReedConnector()
        jobs = await connector.search(["obscure role nobody has"])
        assert jobs == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_handles_auth_error(self):
        """401 Unauthorized should be caught, not raised."""
        respx.get("https://www.reed.co.uk/api/1.0/search").mock(
            return_value=httpx.Response(401, text="Unauthorized")
        )
        from marketforge.agents.data_collection.reed_agent import ReedConnector
        connector = ReedConnector()
        jobs = await connector.search(["AI Engineer"])
        assert jobs == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_auth_header_is_basic(self):
        """Connector must send a Basic Auth header."""
        captured: list[httpx.Request] = []

        def capture(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json=REED_EMPTY)

        respx.get("https://www.reed.co.uk/api/1.0/search").mock(side_effect=capture)
        from marketforge.agents.data_collection.reed_agent import ReedConnector
        connector = ReedConnector()
        await connector.search(["ML"])
        assert captured
        assert captured[0].headers.get("authorization", "").startswith("Basic ")
