"""
MarketForge AI — Streamlit Dashboard

Six pages:
  1. Market Overview      — hiring velocity, top skills, work model
  2. Skill Intelligence   — co-occurrence network, trend indicators
  3. Salary & Geography   — salary box plots, UK heatmap, sponsorship
  4. Career Advisor       — personal skill gap analysis (calls FastAPI)
  5. Research Signals     — emerging tech from arXiv/blogs
  6. Pipeline Status      — DAG run history, department health, cost tracker

All market data is served from Redis cache (via FastAPI or direct DB).
The Career Advisor page calls POST /api/v1/career/analyse.
"""
from __future__ import annotations

import json
import os
import time

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

# ── App config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MarketForge AI",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_BASE = os.getenv("MARKETFORGE_API_URL", "http://localhost:8000")
TIMEOUT  = 30   # seconds


# ── Helpers ───────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def fetch_snapshot() -> dict:
    try:
        r = requests.get(f"{API_BASE}/api/v1/market/snapshot", timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        return {"error": str(exc)}


@st.cache_data(ttl=3600)
def fetch_skills(role_category: str = "all") -> dict:
    try:
        r = requests.get(f"{API_BASE}/api/v1/market/skills", params={"role_category": role_category}, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        return {"error": str(exc)}


@st.cache_data(ttl=3600)
def fetch_trending() -> dict:
    try:
        r = requests.get(f"{API_BASE}/api/v1/market/trending", timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {"rising": [], "declining": [], "top_now": []}


@st.cache_data(ttl=300)
def fetch_health() -> dict:
    try:
        r = requests.get(f"{API_BASE}/api/v1/health", timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def _freshness_badge(freshness_h: float | None) -> str:
    if freshness_h is None:
        return "🔴 No data"
    if freshness_h < 24:
        return f"🟢 {freshness_h:.0f}h ago"
    if freshness_h < 72:
        return f"🟡 {freshness_h:.0f}h ago"
    return f"🔴 {freshness_h:.0f}h ago"


# ── Sidebar navigation ────────────────────────────────────────────────────────

st.sidebar.title("📊 MarketForge AI")
st.sidebar.caption("UK AI Job Market Intelligence")

health  = fetch_health()
freshness_str = _freshness_badge(health.get("data_freshness_h"))
st.sidebar.metric("Data freshness", freshness_str)
st.sidebar.metric("Jobs indexed", f"{health.get('jobs_total', 0):,}")
st.sidebar.caption(f"API: {health.get('status', 'unknown')}")

page = st.sidebar.radio(
    "Navigate",
    ["📈 Market Overview", "🔬 Skill Intelligence", "💰 Salary & Geography",
     "🎯 Career Advisor", "🔭 Research Signals", "⚙️ Pipeline Status"],
)

st.sidebar.divider()
st.sidebar.caption("Data updated twice weekly (Tue/Thu)")
st.sidebar.caption("v0.1.0 · [GitHub](https://github.com/viraj97-sl)")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1: MARKET OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════

if page == "📈 Market Overview":
    st.title("📈 UK AI Job Market — Overview")
    snap = fetch_snapshot()

    if "error" in snap:
        st.error(f"Could not load market data: {snap['error']}")
        st.stop()

    # ── KPIs ──────────────────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Jobs this week",      f"{snap.get('job_count', 0):,}")
    col2.metric("Median salary",       f"£{snap.get('salary_p50') or 0:,.0f}" if snap.get("salary_p50") else "N/A")
    col3.metric("Sponsorship rate",    f"{snap.get('sponsorship_rate', 0)*100:.1f}%")
    col4.metric("Week",                snap.get("week_start", "—"))

    st.divider()

    # ── Top skills bar chart ──────────────────────────────────────────────────
    top_skills = snap.get("top_skills") or {}
    if top_skills:
        df_skills = pd.DataFrame(
            sorted(top_skills.items(), key=lambda x: -x[1])[:20],
            columns=["Skill", "Mentions"],
        )
        fig = px.bar(
            df_skills,
            x="Mentions", y="Skill",
            orientation="h",
            title="Top 20 Skills in UK AI/ML Job Postings",
            color="Mentions",
            color_continuous_scale="Teal",
        )
        fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=500, showlegend=False)
        fig.update_coloraxes(showscale=False)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No skill data available yet. Run an ingestion cycle first.")

    # ── Trending panel ─────────────────────────────────────────────────────────
    trending = fetch_trending()
    col_r, col_d = st.columns(2)
    with col_r:
        st.subheader("📈 Rising")
        for s in (trending.get("rising") or [])[:8]:
            st.write(f"• {s}")
    with col_d:
        st.subheader("📉 Declining")
        for s in (trending.get("declining") or [])[:8]:
            st.write(f"• {s}")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2: SKILL INTELLIGENCE
# ══════════════════════════════════════════════════════════════════════════════

elif page == "🔬 Skill Intelligence":
    st.title("🔬 Skill Intelligence")

    role_options = ["all", "ml_engineer", "data_scientist", "ai_engineer",
                    "mlops_engineer", "nlp_engineer", "computer_vision_engineer"]
    selected_role = st.selectbox("Filter by role category", role_options)
    skills_data   = fetch_skills(selected_role)

    if "error" in skills_data:
        st.error(f"Could not load skill data: {skills_data['error']}")
        st.stop()

    top_skills = skills_data.get("top_skills") or {}
    rising     = skills_data.get("rising_skills") or []
    declining  = skills_data.get("declining_skills") or []

    # ── Skills table with trend indicators ───────────────────────────────────
    if top_skills:
        rows = []
        for i, (skill, count) in enumerate(sorted(top_skills.items(), key=lambda x: -x[1])[:20], 1):
            trend = "📈" if skill in rising else ("📉" if skill in declining else "➡️")
            rows.append({"#": i, "Skill": skill, "Demand Score": count, "Trend": trend})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ── Treemap of skill categories ───────────────────────────────────────────
    if top_skills:
        df_tree = pd.DataFrame([
            {"skill": k, "count": v, "category": "Market Demand"}
            for k, v in list(top_skills.items())[:30]
        ])
        fig = px.treemap(
            df_tree,
            path=["category", "skill"],
            values="count",
            title="Skill Demand Treemap",
            color="count",
            color_continuous_scale="teal",
        )
        fig.update_coloraxes(showscale=False)
        st.plotly_chart(fig, use_container_width=True)

    # ── Rising vs declining comparison ───────────────────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📈 Rising skills")
        for s in rising[:10]:
            st.success(f"↑ {s}")
    with col2:
        st.subheader("📉 Declining skills")
        for s in declining[:10]:
            st.error(f"↓ {s}")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3: SALARY & GEOGRAPHY
# ══════════════════════════════════════════════════════════════════════════════

elif page == "💰 Salary & Geography":
    st.title("💰 Salary Benchmarks & Geography")
    snap = fetch_snapshot()

    if "error" in snap:
        st.error(f"Could not load data: {snap['error']}")
        st.stop()

    # ── Salary box plot (simulated quartiles) ─────────────────────────────────
    p25 = snap.get("salary_p25")
    p50 = snap.get("salary_p50")
    p75 = snap.get("salary_p75")

    if p25 and p50 and p75:
        st.subheader("Salary Distribution (UK AI/ML)")
        fig = go.Figure()
        fig.add_trace(go.Box(
            name="All UK AI/ML roles",
            q1=[p25], median=[p50], q3=[p75],
            lowerfence=[max(p25 * 0.7, 20000)],
            upperfence=[p75 * 1.3],
            boxmean=True,
            marker_color="#0F6E56",
        ))
        fig.update_layout(
            yaxis_title="Salary (£)",
            xaxis_title="",
            height=350,
        )
        st.plotly_chart(fig, use_container_width=True)

        col1, col2, col3 = st.columns(3)
        col1.metric("25th percentile", f"£{p25:,.0f}")
        col2.metric("Median (50th)", f"£{p50:,.0f}")
        col3.metric("75th percentile", f"£{p75:,.0f}")
    else:
        st.info("Salary data not yet available. More data will appear after several ingestion cycles.")

    st.divider()

    # ── Sponsorship gauge ─────────────────────────────────────────────────────
    sp_rate = snap.get("sponsorship_rate", 0) or 0
    st.subheader("Visa Sponsorship Availability")
    fig_sp = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=sp_rate * 100,
        number={"suffix": "%"},
        delta={"reference": 25},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "#0F6E56"},
            "steps": [
                {"range": [0, 20], "color": "#FAECE7"},
                {"range": [20, 40], "color": "#E1F5EE"},
                {"range": [40, 100],"color": "#9FE1CB"},
            ],
        },
        title={"text": "Roles offering visa sponsorship"},
    ))
    fig_sp.update_layout(height=300)
    st.plotly_chart(fig_sp, use_container_width=True)

    # ── City distribution (placeholder until geo data populates) ─────────────
    top_cities = snap.get("top_cities") or {}
    if top_cities:
        st.subheader("Jobs by City")
        df_cities = pd.DataFrame(
            sorted(top_cities.items(), key=lambda x: -x[1])[:10],
            columns=["City", "Jobs"],
        )
        fig_c = px.bar(df_cities, x="City", y="Jobs", color="Jobs", color_continuous_scale="teal")
        fig_c.update_coloraxes(showscale=False)
        st.plotly_chart(fig_c, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4: CAREER ADVISOR
# ══════════════════════════════════════════════════════════════════════════════

elif page == "🎯 Career Advisor":
    st.title("🎯 Personal Career Intelligence")
    st.caption("Enter your profile below. Your data is processed in memory and never stored.")

    with st.form("career_form"):
        skills_raw = st.text_area(
            "Your skills (one per line or comma-separated)",
            placeholder="Python\nPyTorch\nLangChain\nFastAPI\nSQL",
            height=150,
        )
        col_a, col_b = st.columns(2)
        with col_a:
            target_role   = st.selectbox("Target role", [
                "ML Engineer", "Data Scientist", "AI Engineer", "MLOps Engineer",
                "NLP Engineer", "Computer Vision Engineer", "Research Scientist",
            ])
            experience    = st.selectbox("Experience level", ["junior", "mid", "senior", "lead"])
        with col_b:
            location      = st.text_input("Location", value="London")
            sponsorship   = st.checkbox("I need visa sponsorship")

        submitted = st.form_submit_button("Analyse my profile →", type="primary")

    if submitted and skills_raw.strip():
        # Parse skills
        skills = [s.strip() for s in skills_raw.replace(",", "\n").split("\n") if s.strip()]

        with st.spinner("Analysing your profile against live market data…"):
            try:
                resp = requests.post(
                    f"{API_BASE}/api/v1/career/analyse",
                    json={
                        "skills":           skills,
                        "target_role":      target_role,
                        "experience_level": experience,
                        "location":         location,
                        "visa_sponsorship": sponsorship,
                    },
                    timeout=120,
                )
                if resp.status_code == 429:
                    st.warning("Rate limit hit — please wait 1 minute and try again.")
                    st.stop()
                if resp.status_code == 422:
                    st.error(f"Input rejected by security validation: {resp.json().get('detail', 'Unknown reason')}")
                    st.stop()
                resp.raise_for_status()
                report = resp.json()
            except requests.exceptions.ConnectionError:
                st.error("Could not connect to the MarketForge API. Make sure the API server is running.")
                st.stop()
            except Exception as exc:
                st.error(f"Analysis failed: {exc}")
                st.stop()

        # ── Display results ────────────────────────────────────────────────────
        match_pct  = report.get("market_match_pct", 0)
        match_dist = report.get("match_distribution", {})

        col1, col2, col3 = st.columns(3)
        col1.metric("Market match", f"{match_pct:.0f}%",
                    delta="strong fit" if match_pct > 65 else "developing fit")
        col2.metric("Strong role matches", f"{match_dist.get('strong', 0)*100:.0f}%")
        col3.metric("Roles within reach", f"{match_dist.get('moderate', 0)*100:.0f}%")

        st.divider()
        st.subheader("📋 Career Intelligence Summary")
        st.write(report.get("narrative_summary", ""))

        st.subheader("🎯 Top Skill Gaps to Close")
        gaps = report.get("top_skill_gaps", [])
        if gaps:
            df_gaps = pd.DataFrame(gaps)
            st.dataframe(df_gaps, use_container_width=True, hide_index=True)
        else:
            st.success("No critical skill gaps detected — your profile aligns well with market demand.")

        st.subheader("🏭 Best Sector Fits")
        for sector in report.get("sector_fit", []):
            with st.expander(f"**{sector['sector']}** — {sector['fit_score']:.0f}% fit"):
                st.write(f"Sponsorship rate in this sector: **{sector['sponsorship_rate']*100:.0f}%**")

        st.subheader("📅 Your 90-Day Action Plan")
        for i, step in enumerate(report.get("action_plan_90d", []), 1):
            st.write(f"**{i}.** {step}")

        sal = report.get("salary_expectation", {})
        if sal.get("p50"):
            st.info(f"💰 Salary benchmark for your target role: £{sal['p50']:,.0f} median (n={sal.get('sample_size', 0)} roles)")

    elif submitted:
        st.warning("Please enter at least one skill.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 5: RESEARCH SIGNALS
# ══════════════════════════════════════════════════════════════════════════════

elif page == "🔭 Research Signals":
    st.title("🔭 Research Intelligence")
    st.caption("Emerging techniques detected in arXiv and tech blogs — 4-8 weeks before they appear in job postings.")

    # Read from market.research_signals (populated by Research dept in Phase 3)
    try:
        from marketforge.memory.postgres import get_sync_engine
        from sqlalchemy import text
        engine    = get_sync_engine()
        is_sqlite = engine.dialect.name == "sqlite"
        table     = "research_signals" if is_sqlite else "market.research_signals"
        with engine.connect() as conn:
            rows = conn.execute(text(f"""
                SELECT technique_name, source, first_seen, mention_count,
                       first_in_jd, adoption_lag_days, relevance_score, summary
                FROM {table}
                ORDER BY relevance_score DESC, mention_count DESC
                LIMIT 20
            """)).mappings().fetchall()
        signals = [dict(r) for r in rows]
    except Exception as exc:
        signals = []
        st.caption(f"(Research signals will populate after Phase 3 deployment: {exc})")

    if signals:
        for sig in signals:
            with st.expander(f"**{sig['technique_name']}** — {sig['source'].upper()} — score: {sig['relevance_score']:.2f}"):
                col1, col2 = st.columns(2)
                col1.write(f"First seen: **{sig['first_seen']}**")
                col1.write(f"Mentions: **{sig['mention_count']}**")
                col2.write(f"First in job postings: **{sig.get('first_in_jd') or 'Not yet'}**")
                if sig.get("adoption_lag_days"):
                    col2.write(f"Adoption lag: **{sig['adoption_lag_days']} days**")
                if sig.get("summary"):
                    st.write(sig["summary"])
    else:
        st.info("Research signals will appear here after the Research Intelligence department is deployed (Phase 3).")
        st.subheader("What this page will show:")
        st.markdown("""
- **Emerging techniques** from arXiv cs.LG, cs.AI, cs.CL, cs.CV
- **Tech blog signals** from DeepMind, Meta AI, Hugging Face, UK AI companies
- **Adoption lag model** — predicted time from paper publication to job market demand
- **Watch list** — techniques trending in papers likely to appear in job descriptions within 4-8 weeks
        """)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 6: PIPELINE STATUS
# ══════════════════════════════════════════════════════════════════════════════

elif page == "⚙️ Pipeline Status":
    st.title("⚙️ Pipeline Status & Ops")

    health = fetch_health()
    col1, col2, col3 = st.columns(3)
    col1.metric("Platform status",   health.get("status", "unknown").upper())
    col2.metric("Data freshness",    _freshness_badge(health.get("data_freshness_h")))
    col3.metric("Jobs indexed",      f"{health.get('jobs_total', 0):,}")

    st.divider()

    # ── Recent pipeline runs ─────────────────────────────────────────────────
    try:
        from marketforge.memory.postgres import get_sync_engine
        from sqlalchemy import text
        engine    = get_sync_engine()
        is_sqlite = engine.dialect.name == "sqlite"
        runs_t    = "pipeline_runs" if is_sqlite else "market.pipeline_runs"
        cost_t    = "cost_log"      if is_sqlite else "market.cost_log"

        with engine.connect() as conn:
            runs = conn.execute(text(f"""
                SELECT run_id, dag_name, started_at, completed_at, status,
                       jobs_scraped, jobs_new, llm_cost_usd
                FROM {runs_t}
                ORDER BY started_at DESC LIMIT 10
            """)).mappings().fetchall()

            total_cost = conn.execute(text(f"SELECT SUM(cost_usd) FROM {cost_t}")).scalar() or 0.0

        st.subheader("Recent Pipeline Runs")
        if runs:
            df_runs = pd.DataFrame([dict(r) for r in runs])
            df_runs["status"] = df_runs["status"].apply(
                lambda s: f"✅ {s}" if s == "success" else (f"🔄 {s}" if s == "running" else f"❌ {s}")
            )
            st.dataframe(df_runs, use_container_width=True, hide_index=True)
        else:
            st.info("No pipeline runs recorded yet.")

        st.metric("Total LLM spend to date", f"${total_cost:.4f}")

    except Exception as exc:
        st.warning(f"Could not load pipeline history: {exc}")

    st.divider()
    st.subheader("Agent State Monitor")
    try:
        from marketforge.memory.postgres import get_sync_engine
        from sqlalchemy import text
        engine    = get_sync_engine()
        is_sqlite = engine.dialect.name == "sqlite"
        state_t   = "agent_state" if is_sqlite else "market.agent_state"

        with engine.connect() as conn:
            agents = conn.execute(text(f"""
                SELECT agent_id, department, last_run_at, last_yield,
                       consecutive_failures, run_count
                FROM {state_t}
                ORDER BY department, agent_id
            """)).mappings().fetchall()

        if agents:
            df_agents = pd.DataFrame([dict(a) for a in agents])
            df_agents["health"] = df_agents["consecutive_failures"].apply(
                lambda f: "🟢 OK" if f == 0 else (f"🟡 Warning ({f})" if f < 3 else f"🔴 Failed ({f})")
            )
            st.dataframe(df_agents[["department", "agent_id", "health", "last_yield", "run_count", "last_run_at"]],
                         use_container_width=True, hide_index=True)
        else:
            st.info("No agent state recorded yet — agents will appear here after first run.")
    except Exception as exc:
        st.warning(f"Could not load agent state: {exc}")
