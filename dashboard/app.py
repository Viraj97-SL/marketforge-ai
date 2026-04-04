"""
MarketForge AI — Premium Dashboard
"""
from __future__ import annotations

import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

# ── App config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MarketForge AI",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_BASE = os.getenv("MARKETFORGE_API_URL", "http://localhost:8000")
TIMEOUT  = 30

# ── Design tokens ─────────────────────────────────────────────────────────────
ACCENT   = "#00C6A7"
ACCENT_B = "#0EA5E9"
BG       = "#07090F"
SURFACE  = "#0C1018"
SURFACE2 = "#101520"
BORDER   = "#1A2333"
BORDER2  = "#243040"
TEXT1    = "#E8EDF5"
TEXT2    = "#6B7E94"
TEXT3    = "#3D5166"
SUCCESS  = "#10B981"
WARNING  = "#F59E0B"
DANGER   = "#EF4444"


# ── Plotly dark theme ─────────────────────────────────────────────────────────
def _fig(fig: go.Figure, title: str = "", height: int = 400) -> go.Figure:
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color=TEXT2, size=11),
        title=dict(text=title, font=dict(color=TEXT1, size=14, family="Inter"), x=0, xanchor="left", pad=dict(b=16)),
        margin=dict(l=4, r=4, t=48 if title else 16, b=4),
        height=height,
        xaxis=dict(gridcolor=BORDER, linecolor=BORDER2, tickfont=dict(color=TEXT2), zeroline=False),
        yaxis=dict(gridcolor=BORDER, linecolor=BORDER2, tickfont=dict(color=TEXT2), zeroline=False),
        hoverlabel=dict(bgcolor=SURFACE2, font_color=TEXT1, bordercolor=BORDER2, font_size=12),
        legend=dict(font=dict(color=TEXT2), bgcolor="rgba(0,0,0,0)", bordercolor=BORDER),
        showlegend=False,
        colorway=[ACCENT, ACCENT_B, "#818CF8", "#F472B6", "#FB923C", "#34D399"],
    )
    return fig


# ── CSS ───────────────────────────────────────────────────────────────────────
def _css() -> None:
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    html, body, [class*="css"], .stApp {{ font-family: 'Inter', sans-serif !important; }}

    /* hide streamlit chrome */
    #MainMenu, footer, header {{ visibility: hidden !important; }}
    .stDeployButton {{ display: none !important; }}
    .block-container {{ padding: 2rem 2.5rem 4rem !important; max-width: 1400px !important; }}

    /* app background */
    .stApp {{
        background-color: {BG};
        background-image:
            radial-gradient(ellipse 60% 40% at 10% -10%, rgba(0,198,167,0.06) 0%, transparent 60%),
            radial-gradient(ellipse 50% 30% at 90% 0%, rgba(14,165,233,0.05) 0%, transparent 55%);
    }}

    /* sidebar */
    [data-testid="stSidebar"] {{
        background: {SURFACE} !important;
        border-right: 1px solid {BORDER} !important;
    }}
    [data-testid="stSidebar"] > div:first-child {{ padding: 0 !important; }}

    /* sidebar radio nav */
    [data-testid="stSidebar"] .stRadio > div {{ gap: 2px !important; }}
    [data-testid="stSidebar"] .stRadio label {{
        display: flex !important;
        align-items: center !important;
        color: {TEXT2} !important;
        font-size: 0.83rem !important;
        font-weight: 500 !important;
        padding: 0.55rem 1rem !important;
        border-radius: 8px !important;
        transition: all 0.12s ease !important;
        cursor: pointer !important;
        margin: 0 !important;
    }}
    [data-testid="stSidebar"] .stRadio label:hover {{
        color: {TEXT1} !important;
        background: rgba(255,255,255,0.04) !important;
    }}
    [data-testid="stSidebar"] .stRadio [data-checked="true"] label,
    [data-testid="stSidebar"] .stRadio input:checked + div label {{
        color: {ACCENT} !important;
        background: rgba(0,198,167,0.08) !important;
    }}
    [data-testid="stSidebar"] .stRadio [aria-checked="true"] {{
        color: {ACCENT} !important;
    }}

    /* sidebar text */
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] small,
    [data-testid="stSidebar"] .stCaption {{ color: {TEXT3} !important; font-size: 0.75rem !important; }}

    /* sidebar metrics */
    [data-testid="stSidebar"] [data-testid="stMetric"] {{
        background: rgba(0,198,167,0.04) !important;
        border: 1px solid {BORDER} !important;
        border-radius: 10px !important;
        padding: 0.65rem 0.9rem !important;
    }}
    [data-testid="stSidebar"] [data-testid="metric-container"] label {{
        color: {TEXT3} !important;
        font-size: 0.68rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.07em !important;
        font-weight: 600 !important;
    }}
    [data-testid="stSidebar"] [data-testid="stMetricValue"] {{
        color: {TEXT1} !important;
        font-size: 0.95rem !important;
        font-weight: 600 !important;
    }}

    /* sidebar button */
    [data-testid="stSidebar"] .stButton button {{
        width: 100% !important;
        background: transparent !important;
        border: 1px solid {BORDER2} !important;
        color: {TEXT2} !important;
        border-radius: 8px !important;
        font-size: 0.78rem !important;
        font-weight: 500 !important;
        padding: 0.45rem 0.75rem !important;
        transition: all 0.12s ease !important;
        letter-spacing: 0.02em !important;
    }}
    [data-testid="stSidebar"] .stButton button:hover {{
        border-color: {ACCENT} !important;
        color: {ACCENT} !important;
        background: rgba(0,198,167,0.05) !important;
    }}

    /* headings */
    h1 {{ color: {TEXT1} !important; font-size: 1.65rem !important; font-weight: 700 !important; letter-spacing: -0.03em !important; }}
    h2 {{ color: {TEXT1} !important; font-size: 1.25rem !important; font-weight: 600 !important; letter-spacing: -0.02em !important; }}
    h3 {{ color: {TEXT1} !important; font-size: 1rem !important; font-weight: 600 !important; letter-spacing: -0.01em !important; }}
    p, li {{ color: {TEXT2} !important; line-height: 1.65 !important; }}

    /* dividers */
    hr {{ border: none !important; border-top: 1px solid {BORDER} !important; margin: 1.75rem 0 !important; }}

    /* selectbox */
    .stSelectbox > div > div {{
        background: {SURFACE2} !important;
        border: 1px solid {BORDER} !important;
        border-radius: 8px !important;
        color: {TEXT1} !important;
        font-size: 0.85rem !important;
    }}
    .stSelectbox > div > div:focus-within {{
        border-color: {ACCENT} !important;
        box-shadow: 0 0 0 2px rgba(0,198,167,0.12) !important;
    }}
    .stSelectbox label {{
        color: {TEXT2} !important;
        font-size: 0.75rem !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.07em !important;
    }}

    /* text inputs */
    .stTextInput input, .stTextArea textarea {{
        background: {SURFACE2} !important;
        border: 1px solid {BORDER} !important;
        border-radius: 8px !important;
        color: {TEXT1} !important;
        font-size: 0.875rem !important;
        font-family: 'Inter', sans-serif !important;
    }}
    .stTextInput input:focus, .stTextArea textarea:focus {{
        border-color: {ACCENT} !important;
        box-shadow: 0 0 0 2px rgba(0,198,167,0.12) !important;
        outline: none !important;
    }}
    .stTextInput label, .stTextArea label {{
        color: {TEXT2} !important;
        font-size: 0.75rem !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.07em !important;
    }}

    /* primary button */
    .stButton > button[kind="primary"] {{
        background: linear-gradient(135deg, {ACCENT}, {ACCENT_B}) !important;
        border: none !important;
        color: #04090E !important;
        font-weight: 700 !important;
        font-size: 0.875rem !important;
        border-radius: 8px !important;
        padding: 0.55rem 1.5rem !important;
        letter-spacing: 0.01em !important;
    }}
    .stButton > button[kind="primary"]:hover {{
        opacity: 0.88 !important;
    }}

    /* form */
    [data-testid="stForm"] {{
        background: {SURFACE} !important;
        border: 1px solid {BORDER} !important;
        border-radius: 14px !important;
        padding: 1.75rem 2rem !important;
    }}
    [data-testid="stForm"] .stButton button[kind="primary"] {{
        background: linear-gradient(135deg, {ACCENT}, {ACCENT_B}) !important;
        border: none !important;
        color: #04090E !important;
        font-weight: 700 !important;
        padding: 0.6rem 2rem !important;
        border-radius: 8px !important;
        width: auto !important;
    }}

    /* expanders */
    .streamlit-expanderHeader {{
        background: {SURFACE2} !important;
        border: 1px solid {BORDER} !important;
        border-radius: 10px !important;
        color: {TEXT1} !important;
        font-size: 0.875rem !important;
        font-weight: 500 !important;
        padding: 0.75rem 1rem !important;
    }}
    .streamlit-expanderHeader:hover {{
        border-color: {BORDER2} !important;
        background: rgba(255,255,255,0.03) !important;
    }}
    .streamlit-expanderContent {{
        background: {SURFACE} !important;
        border: 1px solid {BORDER} !important;
        border-top: none !important;
        border-radius: 0 0 10px 10px !important;
        padding: 1rem !important;
    }}

    /* dataframe */
    [data-testid="stDataFrame"] {{
        border: 1px solid {BORDER} !important;
        border-radius: 12px !important;
        overflow: hidden !important;
    }}
    [data-testid="stDataFrame"] th {{
        background: {SURFACE2} !important;
        color: {TEXT2} !important;
        font-size: 0.72rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.06em !important;
        font-weight: 600 !important;
        border-bottom: 1px solid {BORDER} !important;
    }}
    [data-testid="stDataFrame"] td {{
        color: {TEXT1} !important;
        font-size: 0.83rem !important;
        border-bottom: 1px solid {BORDER} !important;
    }}
    [data-testid="stDataFrame"] tr:hover td {{
        background: rgba(0,198,167,0.03) !important;
    }}

    /* alerts */
    [data-testid="stAlert"] {{
        background: {SURFACE2} !important;
        border-radius: 10px !important;
        border-left: 3px solid !important;
        color: {TEXT2} !important;
        font-size: 0.85rem !important;
    }}

    /* checkbox */
    .stCheckbox label {{ color: {TEXT2} !important; font-size: 0.85rem !important; }}

    /* spinner */
    .stSpinner > div {{ border-top-color: {ACCENT} !important; }}

    /* metric (main content) */
    [data-testid="stMetric"] {{
        background: {SURFACE} !important;
        border: 1px solid {BORDER} !important;
        border-radius: 12px !important;
        padding: 1.1rem 1.25rem !important;
    }}
    [data-testid="metric-container"] label {{
        color: {TEXT2} !important;
        font-size: 0.72rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.07em !important;
        font-weight: 600 !important;
    }}
    [data-testid="stMetricValue"] {{
        color: {TEXT1} !important;
        font-size: 1.55rem !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em !important;
    }}
    [data-testid="stMetricDelta"] {{ font-size: 0.78rem !important; font-weight: 500 !important; }}

    /* plotly chart wrapper */
    .stPlotlyChart {{
        background: {SURFACE} !important;
        border: 1px solid {BORDER} !important;
        border-radius: 14px !important;
        padding: 1rem !important;
        overflow: hidden !important;
    }}
    </style>
    """, unsafe_allow_html=True)


# ── Reusable components ───────────────────────────────────────────────────────

def page_header(icon: str, title: str, subtitle: str = "") -> None:
    sub = f'<p style="color:{TEXT2};font-size:0.875rem;margin:0.35rem 0 0;font-weight:400;">{subtitle}</p>' if subtitle else ""
    st.markdown(f"""
    <div style="padding-bottom:1.5rem;margin-bottom:0.5rem;border-bottom:1px solid {BORDER};">
        <div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:0.1rem;">
            <span style="font-size:1.4rem;line-height:1;">{icon}</span>
            <h1 style="margin:0;font-size:1.65rem;font-weight:700;color:{TEXT1};letter-spacing:-0.03em;">{title}</h1>
        </div>
        {sub}
    </div>
    """, unsafe_allow_html=True)


def kpi_row(items: list[tuple[str, str, str]]) -> None:
    """items: list of (label, value, sub_text)"""
    cols = st.columns(len(items))
    for col, (label, value, sub) in zip(cols, items):
        with col:
            sub_html = f'<div style="color:{TEXT3};font-size:0.75rem;margin-top:0.4rem;">{sub}</div>' if sub else ""
            st.markdown(f"""
            <div style="background:{SURFACE};border:1px solid {BORDER};border-top:2px solid {ACCENT};
                        border-radius:12px;padding:1.25rem 1.4rem;">
                <div style="color:{TEXT2};font-size:0.68rem;font-weight:700;text-transform:uppercase;
                            letter-spacing:0.09em;margin-bottom:0.55rem;">{label}</div>
                <div style="color:{TEXT1};font-size:1.7rem;font-weight:700;letter-spacing:-0.025em;line-height:1;">{value}</div>
                {sub_html}
            </div>
            """, unsafe_allow_html=True)


def section_label(text: str, badge: str = "") -> None:
    badge_html = (
        f'<span style="background:rgba(0,198,167,0.1);color:{ACCENT};font-size:0.68rem;font-weight:700;'
        f'padding:0.18rem 0.55rem;border-radius:20px;letter-spacing:0.06em;">{badge}</span>'
    ) if badge else ""
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:0.65rem;margin:2rem 0 1rem;">
        <span style="color:{TEXT1};font-size:0.95rem;font-weight:600;letter-spacing:-0.01em;">{text}</span>
        {badge_html}
    </div>
    """, unsafe_allow_html=True)


def tag_list(items: list[str], color: str = ACCENT, icon: str = "") -> None:
    tags = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:0.3rem;background:rgba(0,0,0,0.3);'
        f'border:1px solid {BORDER2};color:{TEXT1};font-size:0.8rem;font-weight:500;'
        f'padding:0.3rem 0.75rem;border-radius:6px;margin:0.2rem;">'
        f'<span style="color:{color};font-size:0.7rem;">{icon}</span>{s}</span>'
        for s in items
    )
    st.markdown(f'<div style="display:flex;flex-wrap:wrap;gap:0.25rem;margin-top:0.25rem;">{tags}</div>',
                unsafe_allow_html=True)


# ── Data fetching ─────────────────────────────────────────────────────────────

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
        r = requests.get(f"{API_BASE}/api/v1/market/skills",
                         params={"role_category": role_category}, timeout=TIMEOUT)
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


# ── Boot ──────────────────────────────────────────────────────────────────────
_css()
health = fetch_health()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    # Brand header
    st.markdown(f"""
    <div style="padding:1.75rem 1.25rem 1.25rem;border-bottom:1px solid {BORDER};margin-bottom:1rem;">
        <div style="display:flex;align-items:center;gap:0.6rem;margin-bottom:0.3rem;">
            <div style="width:28px;height:28px;background:linear-gradient(135deg,{ACCENT},{ACCENT_B});
                        border-radius:7px;display:flex;align-items:center;justify-content:center;
                        font-size:0.8rem;font-weight:900;color:#04090E;flex-shrink:0;">M</div>
            <span style="color:{TEXT1};font-size:1rem;font-weight:700;letter-spacing:-0.02em;">MarketForge AI</span>
        </div>
        <div style="color:{TEXT3};font-size:0.72rem;font-weight:500;letter-spacing:0.04em;
                    text-transform:uppercase;margin-left:2.4rem;">UK AI Intelligence</div>
    </div>
    """, unsafe_allow_html=True)

    # Live status strip
    status_val = health.get("status", "unknown")
    status_color = SUCCESS if status_val == "healthy" else (WARNING if status_val == "stale" else DANGER)
    freshness_h = health.get("data_freshness_h")
    fresh_txt = f"{freshness_h:.0f}h ago" if freshness_h is not None else "—"
    fresh_color = SUCCESS if (freshness_h or 999) < 24 else (WARNING if (freshness_h or 999) < 72 else DANGER)

    st.markdown(f"""
    <div style="margin:0 0.75rem 1rem;padding:0.75rem 1rem;background:{SURFACE2};
                border:1px solid {BORDER};border-radius:10px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem;">
            <span style="color:{TEXT3};font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;">Platform</span>
            <span style="display:flex;align-items:center;gap:0.35rem;color:{status_color};font-size:0.75rem;font-weight:600;">
                <span style="width:6px;height:6px;border-radius:50%;background:{status_color};
                             box-shadow:0 0 5px {status_color}99;display:inline-block;"></span>
                {status_val.upper()}
            </span>
        </div>
        <div style="display:flex;justify-content:space-between;">
            <div>
                <div style="color:{TEXT3};font-size:0.65rem;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:0.1rem;">Data</div>
                <div style="color:{fresh_color};font-size:0.8rem;font-weight:600;">{fresh_txt}</div>
            </div>
            <div style="text-align:right;">
                <div style="color:{TEXT3};font-size:0.65rem;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:0.1rem;">Jobs</div>
                <div style="color:{TEXT1};font-size:0.8rem;font-weight:600;">{health.get("jobs_total", 0):,}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Navigation
    st.markdown(f'<div style="padding:0 0.75rem;margin-bottom:0.35rem;color:{TEXT3};font-size:0.65rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;">Navigation</div>',
                unsafe_allow_html=True)

    page = st.radio(
        "nav",
        ["Market Overview", "Skill Intelligence", "Salary & Geography",
         "Career Advisor", "Research Signals", "Pipeline Status"],
        label_visibility="collapsed",
    )

    st.markdown(f'<div style="border-top:1px solid {BORDER};margin:1rem 0.75rem;"></div>', unsafe_allow_html=True)

    if st.button("↺  Refresh data"):
        st.cache_data.clear()
        st.rerun()

    st.markdown(f"""
    <div style="padding:0 0.75rem;margin-top:0.75rem;">
        <div style="color:{TEXT3};font-size:0.7rem;line-height:1.7;">
            Updated Tue &amp; Thu<br>
            <a href="https://github.com/viraj97-sl" style="color:{TEXT3};text-decoration:none;">
                v0.1.0 · GitHub ↗
            </a>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — MARKET OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════

if page == "Market Overview":
    page_header("◈", "UK AI Job Market", "Real-time intelligence across the UK's AI & ML hiring landscape")
    snap = fetch_snapshot()

    if "error" in snap:
        st.error(f"API unavailable — {snap['error']}")
        st.stop()

    # KPIs
    salary_val = f"£{snap['salary_p50']:,.0f}" if snap.get("salary_p50") else "—"
    kpi_row([
        ("Active roles", f"{snap.get('job_count', 0):,}", f"Week of {snap.get('week_start', '—')}"),
        ("Median salary", salary_val, "UK AI/ML benchmark"),
        ("Visa sponsorship", f"{snap.get('sponsorship_rate', 0)*100:.1f}%", "of roles offer sponsorship"),
        ("Data week", snap.get("week_start", "—"), "pipeline cycle"),
    ])

    st.markdown("<div style='margin-top:2rem;'></div>", unsafe_allow_html=True)

    # Skills chart
    top_skills = snap.get("top_skills") or {}
    if top_skills:
        section_label("Top 20 In-Demand Skills", "LIVE")
        df_s = pd.DataFrame(
            sorted(top_skills.items(), key=lambda x: -x[1])[:20],
            columns=["Skill", "Mentions"],
        )
        fig = px.bar(df_s, x="Mentions", y="Skill", orientation="h", color="Mentions",
                     color_continuous_scale=[[0, "#1A2D40"], [0.5, "#007A67"], [1.0, ACCENT]])
        fig.update_traces(marker_line_width=0)
        fig.update_coloraxes(showscale=False)
        _fig(fig, height=520)
        fig.update_layout(yaxis=dict(categoryorder="total ascending", tickfont=dict(color=TEXT1, size=11)))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No skill data yet. Run the ingestion pipeline first.")

    # Trending split
    trending = fetch_trending()
    rising   = (trending.get("rising") or [])[:8]
    declining = (trending.get("declining") or [])[:8]

    if rising or declining:
        st.markdown("<div style='margin-top:0.5rem;'></div>", unsafe_allow_html=True)
        col_r, col_d = st.columns(2)
        with col_r:
            section_label("Rising Skills")
            if rising:
                tag_list(rising, color=SUCCESS, icon="↑")
            else:
                st.markdown(f'<p style="color:{TEXT3};font-size:0.83rem;">No trend data yet</p>', unsafe_allow_html=True)
        with col_d:
            section_label("Declining Skills")
            if declining:
                tag_list(declining, color=DANGER, icon="↓")
            else:
                st.markdown(f'<p style="color:{TEXT3};font-size:0.83rem;">No trend data yet</p>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — SKILL INTELLIGENCE
# ══════════════════════════════════════════════════════════════════════════════

elif page == "Skill Intelligence":
    page_header("◉", "Skill Intelligence", "Demand signals, trend indicators and taxonomy breakdown")

    role_options = ["all", "ml_engineer", "data_scientist", "ai_engineer",
                    "mlops_engineer", "nlp_engineer", "computer_vision_engineer"]
    role_labels  = ["All Roles", "ML Engineer", "Data Scientist", "AI Engineer",
                    "MLOps Engineer", "NLP Engineer", "Computer Vision"]
    label_map    = dict(zip(role_labels, role_options))

    selected_label = st.selectbox("Role filter", role_labels, label_visibility="visible")
    skills_data    = fetch_skills(label_map[selected_label])

    if "error" in skills_data:
        st.error(f"Could not load data — {skills_data['error']}")
        st.stop()

    top_skills = skills_data.get("top_skills") or {}
    rising     = skills_data.get("rising_skills") or []
    declining  = skills_data.get("declining_skills") or []

    if top_skills:
        # Demand table
        section_label("Skill Demand Index", f"{len(top_skills)} skills tracked")
        rows = []
        for i, (skill, count) in enumerate(sorted(top_skills.items(), key=lambda x: -x[1])[:20], 1):
            trend = "↑" if skill in rising else ("↓" if skill in declining else "—")
            rows.append({"Rank": i, "Skill": skill, "Demand": count, "Trend": trend})
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Rank":   st.column_config.NumberColumn(width="small"),
                "Demand": st.column_config.ProgressColumn(min_value=0, max_value=max(r["Demand"] for r in rows), format="%d"),
                "Trend":  st.column_config.TextColumn(width="small"),
            }
        )

        # Treemap
        section_label("Demand Treemap")
        df_tree = pd.DataFrame([{"skill": k, "count": v, "group": "Market"} for k, v in list(top_skills.items())[:30]])
        fig = px.treemap(df_tree, path=["group", "skill"], values="count",
                         color="count", color_continuous_scale=[[0, "#0D1E2B"], [0.5, "#006A57"], [1.0, ACCENT]])
        fig.update_traces(marker_line_width=0, textfont_color=TEXT1, textfont_size=12)
        fig.update_coloraxes(showscale=False)
        _fig(fig, height=380)
        st.plotly_chart(fig, use_container_width=True)

    # Rising / declining columns
    col1, col2 = st.columns(2)
    with col1:
        section_label("Rising Skills", "GAINING")
        if rising:
            for s in rising[:10]:
                st.markdown(f"""
                <div style="display:flex;align-items:center;justify-content:space-between;
                            padding:0.5rem 0.75rem;border-radius:8px;margin-bottom:4px;
                            background:{SURFACE2};border:1px solid {BORDER};">
                    <span style="color:{TEXT1};font-size:0.83rem;font-weight:500;">{s}</span>
                    <span style="color:{SUCCESS};font-size:0.8rem;font-weight:700;">↑</span>
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f'<p style="color:{TEXT3};font-size:0.83rem;">Insufficient historical data</p>', unsafe_allow_html=True)
    with col2:
        section_label("Declining Skills", "FADING")
        if declining:
            for s in declining[:10]:
                st.markdown(f"""
                <div style="display:flex;align-items:center;justify-content:space-between;
                            padding:0.5rem 0.75rem;border-radius:8px;margin-bottom:4px;
                            background:{SURFACE2};border:1px solid {BORDER};">
                    <span style="color:{TEXT1};font-size:0.83rem;font-weight:500;">{s}</span>
                    <span style="color:{DANGER};font-size:0.8rem;font-weight:700;">↓</span>
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f'<p style="color:{TEXT3};font-size:0.83rem;">Insufficient historical data</p>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — SALARY & GEOGRAPHY
# ══════════════════════════════════════════════════════════════════════════════

elif page == "Salary & Geography":
    page_header("◇", "Salary & Geography", "Compensation benchmarks and geographic distribution across the UK")
    snap = fetch_snapshot()

    if "error" in snap:
        st.error(f"Could not load data — {snap['error']}")
        st.stop()

    p25 = snap.get("salary_p25")
    p50 = snap.get("salary_p50")
    p75 = snap.get("salary_p75")

    if p25 and p50 and p75:
        kpi_row([
            ("25th Percentile", f"£{p25:,.0f}", "entry / junior band"),
            ("Median Salary",   f"£{p50:,.0f}", "market midpoint"),
            ("75th Percentile", f"£{p75:,.0f}", "senior / lead band"),
        ])
        st.markdown("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)

        section_label("Salary Distribution", "UK AI/ML")
        fig = go.Figure()
        fig.add_trace(go.Box(
            name="UK AI/ML",
            q1=[p25], median=[p50], q3=[p75],
            lowerfence=[max(p25 * 0.72, 22000)],
            upperfence=[p75 * 1.28],
            boxmean=True,
            fillcolor=f"rgba(0,198,167,0.12)",
            line=dict(color=ACCENT, width=1.5),
            marker=dict(color=ACCENT),
            whiskerwidth=0.4,
        ))
        _fig(fig, height=300)
        fig.update_layout(
            yaxis=dict(tickprefix="£", tickformat=",.0f", gridcolor=BORDER),
            xaxis=dict(showgrid=False),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Salary data populates after several ingestion cycles.")

    st.markdown(f'<div style="border-top:1px solid {BORDER};margin:2rem 0 1.5rem;"></div>', unsafe_allow_html=True)

    # Sponsorship
    section_label("Visa Sponsorship Rate")
    sp_rate = snap.get("sponsorship_rate", 0) or 0
    fig_sp = go.Figure(go.Indicator(
        mode="gauge+number",
        value=sp_rate * 100,
        number={"suffix": "%", "font": {"color": TEXT1, "size": 40, "family": "Inter"}},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": TEXT3, "tickfont": {"color": TEXT3, "size": 10}},
            "bar": {"color": ACCENT, "thickness": 0.25},
            "bgcolor": "rgba(0,0,0,0)",
            "borderwidth": 0,
            "steps": [
                {"range": [0, 25],  "color": "rgba(239,68,68,0.08)"},
                {"range": [25, 50], "color": "rgba(245,158,11,0.08)"},
                {"range": [50, 100],"color": "rgba(16,185,129,0.08)"},
            ],
            "threshold": {"line": {"color": WARNING, "width": 2}, "thickness": 0.75, "value": 25},
        },
        title={"text": "Roles offering sponsorship", "font": {"color": TEXT2, "size": 12}},
    ))
    _fig(fig_sp, height=260)
    st.plotly_chart(fig_sp, use_container_width=True)

    # City breakdown
    top_cities = snap.get("top_cities") or {}
    if top_cities:
        section_label("Jobs by City", "GEO")
        df_c = pd.DataFrame(
            sorted(top_cities.items(), key=lambda x: -x[1])[:10],
            columns=["City", "Jobs"],
        )
        fig_c = px.bar(df_c, x="City", y="Jobs", color="Jobs",
                       color_continuous_scale=[[0, "#0D1E2B"], [1.0, ACCENT]])
        fig_c.update_traces(marker_line_width=0)
        fig_c.update_coloraxes(showscale=False)
        _fig(fig_c, height=320)
        st.plotly_chart(fig_c, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4 — CAREER ADVISOR
# ══════════════════════════════════════════════════════════════════════════════

elif page == "Career Advisor":
    page_header("◎", "Career Intelligence", "AI-powered gap analysis benchmarked against live UK market data")
    st.markdown(f'<p style="color:{TEXT3};font-size:0.8rem;margin:-0.5rem 0 1.5rem;">Your data is analysed in-memory and never stored.</p>',
                unsafe_allow_html=True)

    with st.form("career_form"):
        skills_raw = st.text_area(
            "Your skills",
            placeholder="Python\nPyTorch\nLangChain\nFastAPI\nSQL",
            height=140,
        )
        col_a, col_b = st.columns(2)
        with col_a:
            target_role = st.selectbox("Target role", [
                "ML Engineer", "Data Scientist", "AI Engineer", "MLOps Engineer",
                "NLP Engineer", "Computer Vision Engineer", "Research Scientist",
            ])
            experience = st.selectbox("Experience level", ["junior", "mid", "senior", "lead"])
        with col_b:
            location    = st.text_input("Location", value="London")
            sponsorship = st.checkbox("I require visa sponsorship")
        submitted = st.form_submit_button("Analyse Profile →", type="primary")

    if submitted and skills_raw.strip():
        skills = [s.strip() for s in skills_raw.replace(",", "\n").split("\n") if s.strip()]
        with st.spinner("Analysing against live market data…"):
            try:
                resp = requests.post(
                    f"{API_BASE}/api/v1/career/analyse",
                    json={"skills": skills, "target_role": target_role,
                          "experience_level": experience, "location": location,
                          "visa_sponsorship": sponsorship},
                    timeout=120,
                )
                if resp.status_code == 429:
                    st.warning("Rate limit — please wait 60 seconds.")
                    st.stop()
                if resp.status_code == 422:
                    st.error(f"Input rejected: {resp.json().get('detail', 'Unknown')}")
                    st.stop()
                resp.raise_for_status()
                report = resp.json()
            except requests.exceptions.ConnectionError:
                st.error("Cannot reach the MarketForge API. Ensure `uvicorn api.main:app` is running.")
                st.stop()
            except Exception as exc:
                st.error(f"Analysis failed: {exc}")
                st.stop()

        match_pct  = report.get("market_match_pct", 0)
        match_dist = report.get("match_distribution", {})
        sal        = report.get("salary_expectation", {})

        st.markdown(f'<div style="border-top:1px solid {BORDER};margin:1.5rem 0;"></div>', unsafe_allow_html=True)

        kpi_row([
            ("Market Match",       f"{match_pct:.0f}%",
             "strong fit" if match_pct > 65 else "developing fit"),
            ("Strong Matches",     f"{match_dist.get('strong', 0)*100:.0f}%", "of roles"),
            ("Within Reach",       f"{match_dist.get('moderate', 0)*100:.0f}%", "with upskilling"),
            ("Salary Benchmark",   f"£{sal['p50']:,.0f}" if sal.get("p50") else "—",
             f"n={sal.get('sample_size', 0)} roles"),
        ])

        st.markdown(f'<div style="border-top:1px solid {BORDER};margin:1.75rem 0 1rem;"></div>', unsafe_allow_html=True)

        section_label("Career Intelligence Summary")
        st.markdown(f'<div style="background:{SURFACE};border:1px solid {BORDER};border-radius:12px;padding:1.25rem 1.5rem;color:{TEXT2};font-size:0.875rem;line-height:1.75;">{report.get("narrative_summary", "").replace(chr(10), "<br>")}</div>',
                    unsafe_allow_html=True)

        gaps = report.get("top_skill_gaps", [])
        if gaps:
            section_label("Priority Skill Gaps")
            st.dataframe(pd.DataFrame(gaps), use_container_width=True, hide_index=True)
        else:
            st.success("Profile aligns well — no critical gaps identified.")

        sector_fits = report.get("sector_fit", [])
        if sector_fits:
            section_label("Sector Fit")
            for sec in sector_fits:
                with st.expander(f"{sec['sector']} — {sec['fit_score']:.0f}% fit"):
                    st.markdown(f'<span style="color:{TEXT2};font-size:0.83rem;">Visa sponsorship rate in this sector: <strong style="color:{TEXT1};">{sec["sponsorship_rate"]*100:.0f}%</strong></span>',
                                unsafe_allow_html=True)

        action_plan = report.get("action_plan_90d", [])
        if action_plan:
            section_label("90-Day Action Plan")
            for i, step in enumerate(action_plan, 1):
                st.markdown(f"""
                <div style="display:flex;gap:1rem;padding:0.75rem 1rem;background:{SURFACE2};
                            border:1px solid {BORDER};border-radius:10px;margin-bottom:0.5rem;">
                    <span style="color:{ACCENT};font-size:0.8rem;font-weight:700;font-family:'JetBrains Mono';
                                flex-shrink:0;margin-top:1px;">0{i}</span>
                    <span style="color:{TEXT1};font-size:0.875rem;line-height:1.6;">{step}</span>
                </div>""", unsafe_allow_html=True)

    elif submitted:
        st.warning("Enter at least one skill to continue.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 5 — RESEARCH SIGNALS
# ══════════════════════════════════════════════════════════════════════════════

elif page == "Research Signals":
    page_header("◈", "Research Intelligence",
                "Emerging techniques from arXiv & tech blogs — 4–8 weeks before they reach job postings")

    signals = []
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
        st.markdown(f'<p style="color:{TEXT3};font-size:0.78rem;">DB note: {exc}</p>', unsafe_allow_html=True)

    if signals:
        for sig in signals:
            with st.expander(f"{sig['technique_name']} · {sig['source'].upper()} · score {sig['relevance_score']:.2f}"):
                col1, col2 = st.columns(2)
                col1.markdown(f'<span style="color:{TEXT2};font-size:0.83rem;">First seen: <strong style="color:{TEXT1};">{sig["first_seen"]}</strong><br>Mentions: <strong style="color:{TEXT1};">{sig["mention_count"]}</strong></span>', unsafe_allow_html=True)
                col2.markdown(f'<span style="color:{TEXT2};font-size:0.83rem;">In job postings: <strong style="color:{TEXT1};">{sig.get("first_in_jd") or "Not yet"}</strong>{("<br>Adoption lag: <strong style=color:" + TEXT1 + ";>" + str(sig["adoption_lag_days"]) + " days</strong>") if sig.get("adoption_lag_days") else ""}</span>', unsafe_allow_html=True)
                if sig.get("summary"):
                    st.markdown(f'<p style="color:{TEXT2};font-size:0.83rem;margin-top:0.75rem;">{sig["summary"]}</p>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div style="border-top:1px solid {BORDER};margin-bottom:1.5rem;"></div>', unsafe_allow_html=True)

        # Preview cards
        preview_items = [
            ("arXiv Monitor", "Tracks cs.LG, cs.AI, cs.CL, cs.CV — new papers daily"),
            ("Blog Signal Extraction", "DeepMind, Meta AI, Hugging Face, UK AI labs"),
            ("Adoption Lag Model", "Predicts paper-to-job-posting lag (avg 6–14 weeks)"),
            ("Watch List", "Techniques trending in papers likely to appear in JDs soon"),
        ]
        cols = st.columns(2)
        for i, (title, desc) in enumerate(preview_items):
            with cols[i % 2]:
                st.markdown(f"""
                <div style="background:{SURFACE};border:1px solid {BORDER};border-radius:12px;
                            padding:1.25rem;margin-bottom:0.75rem;">
                    <div style="color:{ACCENT};font-size:0.72rem;font-weight:700;
                                text-transform:uppercase;letter-spacing:0.07em;margin-bottom:0.5rem;">Upcoming</div>
                    <div style="color:{TEXT1};font-size:0.9rem;font-weight:600;margin-bottom:0.35rem;">{title}</div>
                    <div style="color:{TEXT2};font-size:0.8rem;line-height:1.55;">{desc}</div>
                </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 6 — PIPELINE STATUS
# ══════════════════════════════════════════════════════════════════════════════

elif page == "Pipeline Status":
    page_header("◫", "Pipeline Status", "Run history, agent health and infrastructure telemetry")

    status_val = health.get("status", "unknown")
    freshness_h = health.get("data_freshness_h")
    fresh_txt = f"{freshness_h:.1f}h" if freshness_h is not None else "—"
    kpi_row([
        ("Platform Status", status_val.upper(), ""),
        ("Data Freshness",  fresh_txt,           "since last successful run"),
        ("Jobs Indexed",    f"{health.get('jobs_total', 0):,}", "total in database"),
    ])

    st.markdown(f'<div style="border-top:1px solid {BORDER};margin:2rem 0 1rem;"></div>', unsafe_allow_html=True)

    # Pipeline runs
    section_label("Recent Pipeline Runs")
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
                FROM {runs_t} ORDER BY started_at DESC LIMIT 10
            """)).mappings().fetchall()
            total_cost = conn.execute(text(f"SELECT SUM(cost_usd) FROM {cost_t}")).scalar() or 0.0

        if runs:
            df_runs = pd.DataFrame([dict(r) for r in runs])
            df_runs["status"] = df_runs["status"].apply(
                lambda s: "✓ success" if s == "success" else ("⟳ running" if s == "running" else "✗ failed")
            )
            st.dataframe(df_runs, use_container_width=True, hide_index=True)
        else:
            st.info("No pipeline runs recorded yet.")

        st.markdown(f"""
        <div style="display:inline-flex;align-items:center;gap:0.6rem;background:{SURFACE};
                    border:1px solid {BORDER};border-radius:8px;padding:0.6rem 1rem;margin-top:0.5rem;">
            <span style="color:{TEXT2};font-size:0.75rem;font-weight:600;text-transform:uppercase;letter-spacing:0.06em;">Total LLM spend</span>
            <span style="color:{TEXT1};font-size:1rem;font-weight:700;font-family:'JetBrains Mono';">${total_cost:.4f}</span>
        </div>""", unsafe_allow_html=True)

    except Exception as exc:
        st.warning(f"Pipeline history unavailable: {exc}")

    st.markdown(f'<div style="border-top:1px solid {BORDER};margin:1.75rem 0 1rem;"></div>', unsafe_allow_html=True)

    # Agent state
    section_label("Agent Health Monitor")
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
                FROM {state_t} ORDER BY department, agent_id
            """)).mappings().fetchall()

        if agents:
            df_a = pd.DataFrame([dict(a) for a in agents])
            df_a["health"] = df_a["consecutive_failures"].apply(
                lambda f: "● OK" if f == 0 else (f"◉ Warn ({f})" if f < 3 else f"○ Failed ({f})")
            )
            st.dataframe(
                df_a[["department", "agent_id", "health", "last_yield", "run_count", "last_run_at"]],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("Agent state will appear here after the first pipeline run.")
    except Exception as exc:
        st.warning(f"Agent state unavailable: {exc}")
