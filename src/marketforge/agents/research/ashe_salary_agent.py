"""
MarketForge AI — Department 4 (Research): ASHE Salary Benchmark Agent

Authoritative salary benchmark from the ONS Annual Survey of Hours and
Earnings (ASHE), Table 14 — earnings by 4-digit SOC — to sit alongside our
own scraped salary percentiles.

Honesty caveat carried through to storage and the API: ONS does not publish
a distinct SOC unit group for "Data Scientist", "ML Engineer" etc. The only
AI/tech-relevant SOC 2020 unit group we can point to with confidence is
2134 "Programmers and software development professionals". Every one of our
role_category values is therefore benchmarked against that single occupation
code — presented as "closest ONS occupational proxy", not a per-role figure
the ONS itself publishes. Fabricating a more granular mapping would be worse
than this admitted approximation.

ASHE publishes annually (each autumn) and is distributed as a spreadsheet,
not a clean API — the dataset page is scraped for its current .xlsx link,
which is the most fragile step in this pipeline (see risk notes in the
market-story implementation plan). Any parse failure leaves prior rows
untouched rather than blanking the benchmark table.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from io import BytesIO
from typing import Any

import httpx
import structlog

from marketforge.agents.base import DeepAgent
from marketforge.memory.postgres import get_sync_engine

logger = structlog.get_logger(__name__)

_DATASET_PAGE = (
    "https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/"
    "earningsandworkinghours/datasets/occupation4digitsoc2010ashetable14"
)
_XLSX_LINK_RE = re.compile(r'href="([^"]+\.xlsx)"', re.IGNORECASE)

_SOC_CODE  = "2134"
_SOC_TITLE = "Programmers and software development professionals"

# Every MarketForge role_category is benchmarked against the single closest
# ONS occupation — see module docstring.
_ROLE_CATEGORIES = [
    "ai_engineer", "ml_engineer", "mlops_engineer", "nlp_engineer",
    "data_scientist", "data_engineer", "computer_vision_engineer",
    "research_scientist", "applied_scientist", "ai_safety_researcher",
]


def _t(name: str) -> str:
    engine = get_sync_engine()
    return name if engine.dialect.name == "sqlite" else f"market.{name}"


class AsheSalaryAgent(DeepAgent):
    """
    Fetches ONS ASHE Table 14 and extracts the SOC 2134 pay percentiles.

    plan():    Skips the (slow, fragile) refetch if we already have a row
               for the current calendar year, unless adaptive state has no
               successful fetch on record yet.

    execute(): Locates the current .xlsx via the dataset page HTML, downloads
               it, and scans for the SOC 2134 row using a header-search
               rather than a hardcoded row/column index (ASHE table layout
               shifts slightly release to release). Returns {} on any
               failure.

    reflect(): "poor" if nothing was parsed — this is expected to fire rarely
               (annual cadence) and loudly enough to prompt a manual check.
    """

    agent_id   = "ashe_salary_benchmark_v1"
    department = "research"

    async def plan(self, context: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        from sqlalchemy import text
        engine = get_sync_engine()
        this_year = date.today().year
        have_current_year = False
        try:
            with engine.connect() as conn:
                row = conn.execute(text(f"""
                    SELECT COUNT(*) FROM {_t('external_ashe_salary')}
                    WHERE soc_code = :soc AND year = :yr
                """), {"soc": _SOC_CODE, "yr": this_year}).fetchone()
            have_current_year = bool(row and row[0])
        except Exception as exc:
            logger.warning(f"{self.agent_id}.plan.read_error", error=str(exc))

        return {
            "have_current_year": have_current_year,
            "year": this_year,
            "adaptive": state.get("adaptive_params", {}),
        }

    async def execute(self, plan: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        if plan["have_current_year"]:
            return {"skipped": True, "reason": "already have this year's ASHE figure"}

        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                page_resp = await client.get(f"{_DATASET_PAGE}/current")
                page_resp.raise_for_status()
                xlsx_url = self._find_xlsx_url(page_resp.text)
                if not xlsx_url:
                    logger.warning(f"{self.agent_id}.execute.no_xlsx_link")
                    return {"benchmark": None}

                xlsx_resp = await client.get(xlsx_url)
                xlsx_resp.raise_for_status()
                benchmark = self._parse_workbook(xlsx_resp.content)
        except Exception as exc:
            logger.warning(f"{self.agent_id}.execute.fetch_error", error=str(exc))
            return {"benchmark": None, "year": plan["year"]}

        return {"benchmark": benchmark, "year": plan["year"]}

    def _find_xlsx_url(self, html: str) -> str | None:
        matches = _XLSX_LINK_RE.findall(html)
        for m in matches:
            if "table14" in m.lower() or re.search(r"\btable ?14\b", m.lower()):
                return self._absolute(m)
        return self._absolute(matches[0]) if matches else None

    @staticmethod
    def _absolute(url: str) -> str:
        if url.startswith("http"):
            return url
        return f"https://www.ons.gov.uk{url}"

    def _parse_workbook(self, raw: bytes) -> dict | None:
        import pandas as pd

        wb = pd.ExcelFile(BytesIO(raw))
        # ASHE table sheets are usually named "All" / "Full-Time" — scan all
        # sheets since the exact name varies by release.
        for sheet_name in wb.sheet_names:
            df = wb.parse(sheet_name, header=None)
            hit = self._scan_sheet_for_soc(df)
            if hit:
                return hit
        return None

    def _scan_sheet_for_soc(self, df) -> dict | None:
        """
        Header-search: find the header row containing percentile columns
        (25%, Median, 75%), then scan data rows for one whose SOC code cell
        equals 2134, reading percentile values from those same columns.
        """
        import re as _re

        header_row_idx = None
        col_idx: dict[str, int] = {}
        for i in range(min(20, len(df))):
            row_vals = [str(v).strip().lower() for v in df.iloc[i].tolist()]
            found = {}
            for j, v in enumerate(row_vals):
                if v in ("25", "25%", "lower quartile"):
                    found["p25"] = j
                elif v in ("median", "50", "50%"):
                    found["p50"] = j
                elif v in ("75", "75%", "upper quartile"):
                    found["p75"] = j
            if "p25" in found and "p50" in found and "p75" in found:
                header_row_idx = i
                col_idx = found
                break
        if header_row_idx is None:
            return None

        soc_col = None
        for j in range(min(3, df.shape[1])):
            col_vals = df.iloc[header_row_idx + 1:, j].astype(str)
            if col_vals.str.strip().eq(_SOC_CODE).any():
                soc_col = j
                break
        if soc_col is None:
            return None

        for i in range(header_row_idx + 1, len(df)):
            cell = str(df.iat[i, soc_col]).strip()
            if cell == _SOC_CODE:
                try:
                    p25 = float(df.iat[i, col_idx["p25"]])
                    p50 = float(df.iat[i, col_idx["p50"]])
                    p75 = float(df.iat[i, col_idx["p75"]])
                except (ValueError, TypeError):
                    return None
                return {"p25": p25, "p50": p50, "p75": p75}
        return None

    async def reflect(
        self, plan: dict[str, Any], result: dict[str, Any], state: dict[str, Any]
    ) -> dict[str, Any]:
        adaptive = plan.get("adaptive", {})
        if result.get("skipped"):
            return {"quality": "good", "notes": result.get("reason", "skipped")}

        benchmark = result.get("benchmark")
        state["last_yield"] = 1 if benchmark else 0
        if not benchmark:
            adaptive["ashe_last_failure"] = datetime.utcnow().isoformat()
            state["adaptive_params"] = adaptive
            return {"quality": "poor", "notes": "SOC 2134 row not found — dataset layout may have changed"}

        adaptive["ashe_last_success"] = datetime.utcnow().isoformat()
        state["adaptive_params"] = adaptive
        return {"quality": "good", "notes": f"p50={benchmark['p50']}"}

    async def output(self, result: dict[str, Any], reflection: dict[str, Any]) -> dict[str, Any]:
        benchmark = result.get("benchmark")
        if benchmark:
            self._persist(benchmark, result.get("year") or date.today().year)
        return {"ashe_benchmark_updated": bool(benchmark), "quality": reflection.get("quality")}

    # `execute()` short-circuits with {"skipped": True, "reason": ...} when a
    # current-year row already exists — no "year" key in that branch, but
    # output() is never called with a truthy benchmark in that case either.

    def _persist(self, benchmark: dict, year: int) -> None:
        from sqlalchemy import text
        engine = get_sync_engine()
        is_sqlite = engine.dialect.name == "sqlite"
        table = _t("external_ashe_salary")
        now = datetime.utcnow().isoformat()

        with engine.connect() as conn:
            for role_category in _ROLE_CATEGORIES:
                if is_sqlite:
                    conn.execute(text(f"""
                        INSERT INTO {table}
                            (role_category, soc_code, soc_title, year, salary_p25, salary_p50, salary_p75, fetched_at)
                        VALUES (:rc, :soc, :title, :yr, :p25, :p50, :p75, :now)
                        ON CONFLICT(role_category, soc_code, year) DO UPDATE SET
                            salary_p25 = excluded.salary_p25,
                            salary_p50 = excluded.salary_p50,
                            salary_p75 = excluded.salary_p75,
                            fetched_at = excluded.fetched_at
                    """), {"rc": role_category, "soc": _SOC_CODE, "title": _SOC_TITLE, "yr": year,
                            "p25": benchmark["p25"], "p50": benchmark["p50"], "p75": benchmark["p75"], "now": now})
                else:
                    conn.execute(text(f"""
                        INSERT INTO {table}
                            (role_category, soc_code, soc_title, year, salary_p25, salary_p50, salary_p75, fetched_at)
                        VALUES (:rc, :soc, :title, :yr, :p25, :p50, :p75, :now)
                        ON CONFLICT(role_category, soc_code, year) DO UPDATE SET
                            salary_p25 = EXCLUDED.salary_p25,
                            salary_p50 = EXCLUDED.salary_p50,
                            salary_p75 = EXCLUDED.salary_p75,
                            fetched_at = EXCLUDED.fetched_at
                    """), {"rc": role_category, "soc": _SOC_CODE, "title": _SOC_TITLE, "yr": year,
                            "p25": benchmark["p25"], "p50": benchmark["p50"], "p75": benchmark["p75"], "now": now})
            conn.commit()
