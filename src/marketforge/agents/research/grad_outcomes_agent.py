"""
MarketForge AI — Department 4 (Research): Graduate Outcomes Agent

Real UK graduate supply/outcomes data for the Market page's "graduate
reality" narrative — how many people enter the pipeline, and what happens
to them. Source: DfE Explore Education Statistics (EES), the open-data
platform behind HESA/DfE releases — CSV downloads, no key required.

Two datasets, two honesty caveats carried through to storage and the API:

1. "Graduate labour market statistics" — England-wide graduate employment/
   unemployment/inactivity rates. This table has NO unsegmented "all
   graduates" row — every row is split by Degree Class, Disability,
   Ethnicity, or Sex. We use the Sex breakdown (the only exhaustive 2-way
   partition among the four dimensions) and average Male+Female, captioned
   exactly as that — an approximation, not an official headline figure.

2. "Higher-Level Learners in England, by Subject" — number_of_qualifiers
   for Computing (people who completed a Computing HE qualification that
   academic year), England only, all levels combined ("Total" rows for
   level / type-of-HE / subject_level_2).
"""
from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any

import httpx
import structlog

from marketforge.agents.base import DeepAgent
from marketforge.memory.postgres import get_sync_engine

logger = structlog.get_logger(__name__)

_EMPLOYMENT_CSV_URL = (
    "https://content.explore-education-statistics.service.gov.uk/api/"
    "data-set-files/14b5ea18-1748-4c75-9d52-736f80557727/download"
)
_HEADCOUNT_CSV_URL = (
    "https://content.explore-education-statistics.service.gov.uk/api/"
    "data-set-files/3e38b2bc-6814-429b-9ba3-4b42b719adcc/download"
)


def _t(name: str) -> str:
    engine = get_sync_engine()
    return name if engine.dialect.name == "sqlite" else f"market.{name}"


class GradOutcomesAgent(DeepAgent):
    """
    Fetches the two DfE EES CSVs and stores the latest year's figures.

    plan():    Skips the refetch if we already have a row for the latest
               time_period seen last run (annual data — cheap to check,
               rarely needs a real refetch).

    execute():  Downloads both CSVs, extracts the England Sex-average
               employment/unemployment/inactivity rates and the Computing
               qualifiers count for the most recent year in each file.
               Returns {} fields as None on any parse failure rather than
               raising — reflect()/output() then leave prior rows in place.

    reflect():  "poor" if neither dataset parsed; "warning" if only one did.
    """

    agent_id   = "grad_outcomes_v1"
    department = "research"

    async def plan(self, context: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        return {"adaptive": state.get("adaptive_params", {})}

    async def execute(self, plan: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        employment = None
        headcount  = None

        try:
            async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
                resp = await client.get(_EMPLOYMENT_CSV_URL)
                resp.raise_for_status()
                employment = self._parse_employment(resp.content)
        except Exception as exc:
            logger.warning(f"{self.agent_id}.execute.employment_fetch_error", error=str(exc))

        try:
            async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
                resp = await client.get(_HEADCOUNT_CSV_URL)
                resp.raise_for_status()
                headcount = self._parse_headcount(resp.content)
        except Exception as exc:
            logger.warning(f"{self.agent_id}.execute.headcount_fetch_error", error=str(exc))

        return {"employment": employment, "headcount": headcount}

    def _parse_employment(self, raw: bytes) -> dict | None:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig", errors="replace")))
        by_year: dict[str, dict[str, list[float]]] = {}
        for row in reader:
            if row.get("graduate_characteristic") != "Sex":
                continue
            year = row.get("time_period", "")
            try:
                emp  = float(row["employment_rate"])
                hs   = float(row["hs_employment_rate"])
                unemp = float(row["unemployment_rate"])
                inact = float(row["inactivity_rate"])
            except (KeyError, ValueError, TypeError):
                continue
            bucket = by_year.setdefault(year, {"emp": [], "hs": [], "unemp": [], "inact": []})
            bucket["emp"].append(emp)
            bucket["hs"].append(hs)
            bucket["unemp"].append(unemp)
            bucket["inact"].append(inact)

        if not by_year:
            return None
        latest_year = max(by_year.keys())
        b = by_year[latest_year]
        if not b["emp"]:
            return None

        def _avg(vals: list[float]) -> float:
            return round(sum(vals) / len(vals), 2)

        return {
            "year": int(latest_year),
            "employment_rate":    _avg(b["emp"]),
            "hs_employment_rate": _avg(b["hs"]),
            "unemployment_rate":  _avg(b["unemp"]),
            "inactivity_rate":    _avg(b["inact"]),
        }

    def _parse_headcount(self, raw: bytes) -> dict | None:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig", errors="replace")))
        latest: dict | None = None
        for row in reader:
            if (
                row.get("subject_level_1") != "Computing"
                or row.get("subject_level_2") != "Total"
                or row.get("level") != "Total"
                or row.get("broad_type_of_higher_education") != "Total"
                or row.get("type_of_higher_education") != "Total"
            ):
                continue
            try:
                qualifiers = int(row["number_of_qualifiers"])
            except (KeyError, ValueError, TypeError):
                continue
            period = row.get("time_period", "")
            if latest is None or period > latest["time_period"]:
                latest = {"time_period": period, "qualifiers": qualifiers}

        if not latest:
            return None
        return {"time_period": latest["time_period"], "qualifiers": latest["qualifiers"]}

    async def reflect(
        self, plan: dict[str, Any], result: dict[str, Any], state: dict[str, Any]
    ) -> dict[str, Any]:
        employment = result.get("employment")
        headcount  = result.get("headcount")
        state["last_yield"] = int(bool(employment)) + int(bool(headcount))

        if not employment and not headcount:
            return {"quality": "poor", "notes": "both DfE EES datasets failed to parse"}
        if not employment or not headcount:
            return {"quality": "warning", "notes": "only one of two DfE EES datasets parsed"}
        return {"quality": "good", "notes": f"employment_year={employment['year']}, headcount_period={headcount['time_period']}"}

    async def output(self, result: dict[str, Any], reflection: dict[str, Any]) -> dict[str, Any]:
        employment = result.get("employment")
        headcount  = result.get("headcount")
        if employment:
            self._persist_employment(employment)
        if headcount:
            self._persist_headcount(headcount)
        return {
            "grad_employment_updated": bool(employment),
            "grad_headcount_updated":  bool(headcount),
            "quality": reflection.get("quality"),
        }

    def _persist_employment(self, employment: dict) -> None:
        from sqlalchemy import text
        engine = get_sync_engine()
        is_sqlite = engine.dialect.name == "sqlite"
        table = _t("external_grad_employment")
        now = datetime.utcnow().isoformat()
        conflict = "excluded" if is_sqlite else "EXCLUDED"
        with engine.connect() as conn:
            conn.execute(text(f"""
                INSERT INTO {table} (year, employment_rate, hs_employment_rate, unemployment_rate, inactivity_rate, fetched_at)
                VALUES (:yr, :emp, :hs, :unemp, :inact, :now)
                ON CONFLICT(year) DO UPDATE SET
                    employment_rate    = {conflict}.employment_rate,
                    hs_employment_rate = {conflict}.hs_employment_rate,
                    unemployment_rate  = {conflict}.unemployment_rate,
                    inactivity_rate    = {conflict}.inactivity_rate,
                    fetched_at         = {conflict}.fetched_at
            """), {
                "yr": employment["year"], "emp": employment["employment_rate"],
                "hs": employment["hs_employment_rate"], "unemp": employment["unemployment_rate"],
                "inact": employment["inactivity_rate"], "now": now,
            })
            conn.commit()

    def _persist_headcount(self, headcount: dict) -> None:
        from sqlalchemy import text
        engine = get_sync_engine()
        is_sqlite = engine.dialect.name == "sqlite"
        table = _t("external_grad_headcount")
        now = datetime.utcnow().isoformat()
        conflict = "excluded" if is_sqlite else "EXCLUDED"
        with engine.connect() as conn:
            conn.execute(text(f"""
                INSERT INTO {table} (year, subject, qualifiers_count, fetched_at)
                VALUES (:yr, 'Computing', :qual, :now)
                ON CONFLICT(year, subject) DO UPDATE SET
                    qualifiers_count = {conflict}.qualifiers_count,
                    fetched_at       = {conflict}.fetched_at
            """), {"yr": headcount["time_period"], "qual": headcount["qualifiers"], "now": now})
            conn.commit()
