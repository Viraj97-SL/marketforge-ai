"""
MarketForge AI — Department 4 (Research): ONS Vacancy Trend Agent

Real national vacancy trend line to sit behind the "Hiring Velocity" section —
independent of how much of our own scraped sample exists for a given role.

ONS does not publish an AI/ML-specific vacancy series. The closest official
proxy is CDID JP9P (dataset LMS): "UK Job Vacancies (thousands) — Information
& Communication", the SIC section covering software/tech employers. That
caveat is carried through to the stored row and the API response — this is
presented as sector context, not a literal AI-jobs count.

Source: ONS "generator" CSV export for a timeseries — a long-standing public
mechanism (no key required) for fetching any ONS CDID as CSV:
    https://www.ons.gov.uk/generator?format=csv&uri=<timeseries page uri>
"""
from __future__ import annotations

import csv
import io
import re
from datetime import datetime
from typing import Any

import httpx
import structlog

from marketforge.agents.base import DeepAgent
from marketforge.memory.postgres import get_sync_engine

logger = structlog.get_logger(__name__)

_MONTH_MAP = {
    "JAN": "01", "FEB": "02", "MAR": "03", "APR": "04",
    "MAY": "05", "JUN": "06", "JUL": "07", "AUG": "08",
    "SEP": "09", "OCT": "10", "NOV": "11", "DEC": "12",
}
_MONTH_ROW_RE = re.compile(r"^(\d{4})\s+([A-Z]{3})$")

_CDID          = "JP9P"
_SOURCE_DATASET = "LMS"
_INDUSTRY_LABEL = "Information & Communication (ONS proxy for tech sector)"
_GENERATOR_URL = (
    "https://www.ons.gov.uk/generator"
    "?format=csv"
    "&uri=/employmentandlabourmarket/peopleinwork/employmentandemployeetypes"
    "/timeseries/jp9p/lms"
)


def _t(name: str) -> str:
    engine = get_sync_engine()
    return name if engine.dialect.name == "sqlite" else f"market.{name}"


class OnsVacancyTrendAgent(DeepAgent):
    """
    Pulls the ONS Information & Communication vacancy series (CDID JP9P).

    plan():    Reads the most recent stored month to decide whether a refetch
               is worthwhile (ONS publishes monthly; skip if we already have
               this month's figure and it's not a forced run).

    execute(): Downloads the generator CSV, parses only the monthly rows
               ("YYYY MON" pattern — annual/quarterly rows are ignored), and
               keeps the most recent 24 months. Never raises past this point:
               any parse failure returns an empty list so reflect()/output()
               degrade gracefully instead of blanking the table.

    reflect(): Flags "poor" if zero rows were parsed (source format likely
               changed) so this doesn't silently go stale forever.
    """

    agent_id   = "ons_vacancy_trend_v1"
    department = "research"

    async def plan(self, context: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        from sqlalchemy import text
        engine = get_sync_engine()
        latest_month = None
        try:
            with engine.connect() as conn:
                row = conn.execute(text(f"""
                    SELECT MAX(month) FROM {_t('external_ons_vacancies')}
                    WHERE industry_code = :cdid
                """), {"cdid": _CDID}).fetchone()
            latest_month = row[0] if row else None
        except Exception as exc:
            logger.warning(f"{self.agent_id}.plan.read_error", error=str(exc))
        return {"latest_month": latest_month, "adaptive": state.get("adaptive_params", {})}

    async def execute(self, plan: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
                resp = await client.get(_GENERATOR_URL)
                resp.raise_for_status()
                rows = self._parse_csv(resp.content)
        except Exception as exc:
            logger.warning(f"{self.agent_id}.execute.fetch_error", error=str(exc))
            return {"rows": []}
        return {"rows": rows[-24:]}

    def _parse_csv(self, raw: bytes) -> list[dict]:
        text_data = raw.decode("utf-8-sig", errors="replace")
        reader = csv.reader(io.StringIO(text_data))
        rows: list[dict] = []
        for cells in reader:
            if len(cells) < 2:
                continue
            key, value = cells[0].strip(), cells[1].strip()
            m = _MONTH_ROW_RE.match(key)
            if not m:
                continue
            year, mon_abbr = m.group(1), m.group(2)
            month_num = _MONTH_MAP.get(mon_abbr)
            if not month_num:
                continue
            try:
                vacancies = float(value)
            except ValueError:
                continue
            rows.append({"month": f"{year}-{month_num}", "vacancies_index": vacancies})
        rows.sort(key=lambda r: r["month"])
        return rows

    async def reflect(
        self, plan: dict[str, Any], result: dict[str, Any], state: dict[str, Any]
    ) -> dict[str, Any]:
        rows = result.get("rows", [])
        adaptive = plan.get("adaptive", {})
        adaptive["last_ons_vacancy_row_count"] = len(rows)
        state["adaptive_params"] = adaptive
        state["last_yield"] = len(rows)
        if not rows:
            return {"quality": "poor", "notes": "zero rows parsed — check generator CSV format"}
        return {"quality": "good", "notes": f"n={len(rows)}, latest={rows[-1]['month']}"}

    async def output(self, result: dict[str, Any], reflection: dict[str, Any]) -> dict[str, Any]:
        rows = result.get("rows", [])
        if rows:
            self._persist(rows)
        return {"ons_vacancy_rows": len(rows), "quality": reflection.get("quality")}

    def _persist(self, rows: list[dict]) -> None:
        from sqlalchemy import text
        engine = get_sync_engine()
        is_sqlite = engine.dialect.name == "sqlite"
        table = _t("external_ons_vacancies")
        now = datetime.utcnow().isoformat()

        with engine.connect() as conn:
            for r in rows:
                if is_sqlite:
                    conn.execute(text(f"""
                        INSERT INTO {table} (month, industry_code, industry_label, vacancies_index, fetched_at)
                        VALUES (:month, :cdid, :label, :val, :now)
                        ON CONFLICT(month, industry_code) DO UPDATE SET
                            vacancies_index = excluded.vacancies_index,
                            fetched_at      = excluded.fetched_at
                    """), {"month": r["month"], "cdid": _CDID, "label": _INDUSTRY_LABEL,
                            "val": r["vacancies_index"], "now": now})
                else:
                    conn.execute(text(f"""
                        INSERT INTO {table} (month, industry_code, industry_label, vacancies_index, fetched_at)
                        VALUES (:month, :cdid, :label, :val, :now)
                        ON CONFLICT(month, industry_code) DO UPDATE SET
                            vacancies_index = EXCLUDED.vacancies_index,
                            fetched_at      = EXCLUDED.fetched_at
                    """), {"month": r["month"], "cdid": _CDID, "label": _INDUSTRY_LABEL,
                            "val": r["vacancies_index"], "now": now})
            conn.commit()
