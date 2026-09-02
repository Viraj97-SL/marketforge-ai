"""
MarketForge AI — Department 4 (Research): Sponsor Register Agent

Replaces the offers_sponsorship heuristic (parsed from job-post text, see
SponsorshipTrackerAgent in agents/market_analysis/lead_agent.py) with a
verifiable check against the official GOV.UK Register of Licensed Sponsors:
Workers — the authoritative list of companies actually licensed to sponsor
Skilled Worker / Temporary Worker visas.

The register's CSV download URL changes on every publish (it's dated), so it
is never hardcoded — it's resolved each run via the GOV.UK Content API, which
is stable:
    https://www.gov.uk/api/content/government/publications/register-of-licensed-sponsors-workers
"""
from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timedelta
from typing import Any

import httpx
import structlog

from marketforge.agents.base import DeepAgent
from marketforge.memory.postgres import get_sync_engine

logger = structlog.get_logger(__name__)

_CONTENT_API_URL = (
    "https://www.gov.uk/api/content/government/publications/"
    "register-of-licensed-sponsors-workers"
)

# Common UK company suffixes stripped before matching — the register and our
# scraped job postings rarely agree on whether "Ltd" is present or spelled out.
_SUFFIX_RE = re.compile(
    r"\b(LIMITED|LTD|PLC|LLP|LP|INC|INCORPORATED|CORP|CORPORATION|GROUP|HOLDINGS?)\b\.?"
)


def _t(name: str) -> str:
    engine = get_sync_engine()
    return name if engine.dialect.name == "sqlite" else f"market.{name}"


def normalize_company_name(name: str) -> str:
    """Normalize a company name for register matching. Exported for tests."""
    if not name:
        return ""
    upper = name.upper()
    upper = re.sub(r"[.,&/\\()'\-]", " ", upper)
    upper = _SUFFIX_RE.sub("", upper)
    upper = re.sub(r"\s+", " ", upper).strip()
    return upper


class SponsorRegisterAgent(DeepAgent):
    """
    Matches this window's distinct employer names against the official
    sponsor register.

    plan():    Resolves the current CSV attachment URL via the GOV.UK Content
               API (never hardcoded — the register republishes under a new
               dated filename regularly). Reads the distinct company names
               seen in market.jobs over the last 90 days as the match set.

    execute(): Streams the register CSV, builds a normalized name set, and
               checks each of our companies against it. On any fetch/parse
               failure, returns an empty match set so reflect()/output()
               leave existing rows untouched rather than wiping the table.

    reflect(): Flags "poor" if the register fetch failed outright, "warning"
               if the match rate looks implausibly low (< 1%, suggesting a
               normalization regression) given a large enough sample.
    """

    agent_id   = "sponsor_register_v1"
    department = "research"

    async def plan(self, context: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        from sqlalchemy import text
        engine = get_sync_engine()
        since = str((datetime.utcnow() - timedelta(days=90)).date())

        companies: list[str] = []
        try:
            with engine.connect() as conn:
                rows = conn.execute(text(f"""
                    SELECT DISTINCT company FROM {_t('jobs')}
                    WHERE company IS NOT NULL AND scraped_at >= :since
                """), {"since": since}).fetchall()
            companies = [r[0] for r in rows if r[0]]
        except Exception as exc:
            logger.warning(f"{self.agent_id}.plan.read_error", error=str(exc))

        return {"companies": companies, "adaptive": state.get("adaptive_params", {})}

    async def execute(self, plan: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        companies: list[str] = plan["companies"]
        if not companies:
            return {"matches": {}, "register_size": 0}

        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                content_resp = await client.get(_CONTENT_API_URL)
                content_resp.raise_for_status()
                csv_url = self._find_csv_url(content_resp.json())
                if not csv_url:
                    logger.warning(f"{self.agent_id}.execute.no_csv_attachment")
                    return {"matches": {}, "register_size": 0}

                csv_resp = await client.get(csv_url)
                csv_resp.raise_for_status()
                register_names = self._parse_register(csv_resp.content)
        except Exception as exc:
            logger.warning(f"{self.agent_id}.execute.fetch_error", error=str(exc))
            return {"matches": {}, "register_size": 0}

        matches: dict[str, dict] = {}
        for company in companies:
            norm = normalize_company_name(company)
            if not norm:
                continue
            hit = register_names.get(norm)
            matches[norm] = {
                "is_licensed_sponsor":   hit is not None,
                "matched_register_name": hit or None,
            }

        return {"matches": matches, "register_size": len(register_names)}

    def _find_csv_url(self, content_json: dict) -> str | None:
        attachments = (
            content_json.get("details", {}).get("attachments", [])
            if isinstance(content_json, dict) else []
        )
        for att in attachments:
            content_type = (att.get("content_type") or "").lower()
            url = att.get("url", "")
            if content_type == "text/csv" or url.lower().endswith(".csv"):
                return url
        return None

    def _parse_register(self, raw: bytes) -> dict[str, str]:
        text_data = raw.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text_data))
        # Header casing has varied across publishes ("Organisation Name" vs
        # "Organisation name") — match case-insensitively.
        name_key = None
        if reader.fieldnames:
            for field in reader.fieldnames:
                if field and field.strip().lower() == "organisation name":
                    name_key = field
                    break

        result: dict[str, str] = {}
        if not name_key:
            return result
        for row in reader:
            raw_name = (row.get(name_key) or "").strip()
            if not raw_name:
                continue
            norm = normalize_company_name(raw_name)
            if norm and norm not in result:
                result[norm] = raw_name
        return result

    async def reflect(
        self, plan: dict[str, Any], result: dict[str, Any], state: dict[str, Any]
    ) -> dict[str, Any]:
        matches = result.get("matches", {})
        register_size = result.get("register_size", 0)
        adaptive = plan.get("adaptive", {})
        state["last_yield"] = len(matches)

        if register_size == 0:
            adaptive["sponsor_register_last_failure"] = datetime.utcnow().isoformat()
            state["adaptive_params"] = adaptive
            return {"quality": "poor", "notes": "register fetch/parse failed — kept prior data"}

        verified = sum(1 for m in matches.values() if m["is_licensed_sponsor"])
        rate = verified / max(len(matches), 1)
        adaptive["sponsor_register_last_rate"] = round(rate, 3)
        state["adaptive_params"] = adaptive

        if len(matches) >= 30 and rate < 0.01:
            return {"quality": "warning", "notes": f"implausibly low match rate={rate:.1%} — check normalization"}
        return {"quality": "good", "notes": f"n={len(matches)}, verified_rate={rate:.1%}"}

    async def output(self, result: dict[str, Any], reflection: dict[str, Any]) -> dict[str, Any]:
        matches = result.get("matches", {})
        if matches:
            self._persist(matches)
        return {"sponsor_matches_updated": len(matches), "quality": reflection.get("quality")}

    def _persist(self, matches: dict[str, dict]) -> None:
        from sqlalchemy import text
        engine = get_sync_engine()
        is_sqlite = engine.dialect.name == "sqlite"
        table = _t("external_sponsor_matches")
        now = datetime.utcnow().isoformat()

        with engine.connect() as conn:
            for norm_name, info in matches.items():
                if is_sqlite:
                    conn.execute(text(f"""
                        INSERT INTO {table}
                            (company_name_normalized, is_licensed_sponsor, matched_register_name, fetched_at)
                        VALUES (:name, :is_lic, :matched, :now)
                        ON CONFLICT(company_name_normalized) DO UPDATE SET
                            is_licensed_sponsor    = excluded.is_licensed_sponsor,
                            matched_register_name  = excluded.matched_register_name,
                            fetched_at              = excluded.fetched_at
                    """), {"name": norm_name, "is_lic": info["is_licensed_sponsor"],
                            "matched": info["matched_register_name"], "now": now})
                else:
                    conn.execute(text(f"""
                        INSERT INTO {table}
                            (company_name_normalized, is_licensed_sponsor, matched_register_name, fetched_at)
                        VALUES (:name, :is_lic, :matched, :now)
                        ON CONFLICT(company_name_normalized) DO UPDATE SET
                            is_licensed_sponsor    = EXCLUDED.is_licensed_sponsor,
                            matched_register_name  = EXCLUDED.matched_register_name,
                            fetched_at              = EXCLUDED.fetched_at
                    """), {"name": norm_name, "is_lic": info["is_licensed_sponsor"],
                            "matched": info["matched_register_name"], "now": now})
            conn.commit()
