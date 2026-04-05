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

st.set_page_config(page_title="MarketForge AI", page_icon="◆",
                   layout="wide", initial_sidebar_state="expanded")

API_BASE = os.getenv("MARKETFORGE_API_URL", "http://localhost:8000")
TIMEOUT  = 30

# ── Design tokens ─────────────────────────────────────────────────────────────
CA  = "#00C6A7"   # accent teal
CB  = "#3B82F6"   # blue
BG  = "#060A10"
S1  = "#0B0F18"   # surface 1
S2  = "#0F1520"   # surface 2
S3  = "#141C28"   # surface 3
B1  = "#1C2A3A"   # border 1
B2  = "#243347"   # border 2
T1  = "#E2E8F2"   # text primary
T2  = "#64748B"   # text secondary
T3  = "#334155"   # text muted
OK  = "#10B981"
WRN = "#F59E0B"
ERR = "#EF4444"
PRP = "#8B5CF6"

# ── Plotly base ───────────────────────────────────────────────────────────────
def _chart(fig, height=380):
    """Apply consistent dark theme. automargin prevents label clipping."""
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter,sans-serif", color=T2, size=11),
        margin=dict(l=10, r=10, t=10, b=10),
        height=height,
        showlegend=False,
        hoverlabel=dict(bgcolor=S3, font_color=T1, bordercolor=B2,
                        font_size=12, font_family="Inter"),
        colorway=[CA, CB, PRP, "#F472B6", "#FB923C", "#34D399"],
    )
    fig.update_xaxes(gridcolor=B1, linecolor="rgba(0,0,0,0)",
                     tickfont=dict(color=T2, size=10), zeroline=False,
                     automargin=True)
    fig.update_yaxes(gridcolor=B1, linecolor="rgba(0,0,0,0)",
                     tickfont=dict(color=T2, size=10), zeroline=False,
                     automargin=True)
    return fig

# ── Global CSS ────────────────────────────────────────────────────────────────
# Rules:
#   • No global h1/h2/h3/p overrides — Streamlit hoists them out of HTML blocks
#   • Target Streamlit-specific test-ids for native widget styling
#   • No border on .stPlotlyChart — avoids double-border with chart iframe
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');
html, body, [class*="css"] {{ font-family: 'Inter', sans-serif !important; }}

/* chrome */
#MainMenu, footer, header, .stDeployButton {{ display:none !important; }}
.block-container {{ padding:2rem 2.5rem 4rem !important; max-width:1440px !important; }}

/* app bg */
.stApp {{
    background:{BG};
    background-image:
        radial-gradient(ellipse 80% 45% at -5% -10%, rgba(0,198,167,0.06) 0%, transparent 55%),
        radial-gradient(ellipse 60% 35% at 105% 5%,  rgba(59,130,246,0.045) 0%, transparent 50%);
}}

/* sidebar */
[data-testid="stSidebar"] {{
    background:{S1} !important;
    border-right:1px solid {B1} !important;
}}
[data-testid="stSidebar"] > div:first-child {{ padding:0 !important; }}
section[data-testid="stSidebar"] {{ min-width:220px !important; max-width:220px !important; }}

/* sidebar radio nav */
[data-testid="stSidebar"] .stRadio {{ padding:0 0.5rem !important; }}
[data-testid="stSidebar"] .stRadio > label {{ display:none !important; }}
[data-testid="stSidebar"] .stRadio > div {{ gap:2px !important; }}
[data-testid="stSidebar"] .stRadio label {{
    color:{T2} !important; font-size:0.82rem !important; font-weight:500 !important;
    padding:0.55rem 0.85rem !important; border-radius:8px !important;
    cursor:pointer !important; transition:all 0.1s !important;
    border:1px solid transparent !important; display:flex !important;
    align-items:center !important;
}}
[data-testid="stSidebar"] .stRadio label:hover {{
    color:{T1} !important; background:rgba(255,255,255,0.04) !important;
}}
[data-testid="stSidebar"] .stRadio label[data-checked="true"] {{
    color:{CA} !important;
    background:rgba(0,198,167,0.08) !important;
    border-color:rgba(0,198,167,0.18) !important;
}}

/* sidebar misc */
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {{
    color:{T3} !important; font-size:0.72rem !important; margin:0 !important;
}}
[data-testid="stSidebar"] .stButton button {{
    width:100% !important; background:transparent !important;
    border:1px solid {B2} !important; color:{T2} !important;
    border-radius:7px !important; font-size:0.78rem !important;
    font-weight:500 !important; padding:0.42rem 0.9rem !important;
}}
[data-testid="stSidebar"] .stButton button:hover {{
    border-color:{CA} !important; color:{CA} !important;
    background:rgba(0,198,167,0.05) !important;
}}

/* divider */
hr {{ border:none !important; border-top:1px solid {B1} !important; margin:1.5rem 0 !important; }}

/* native Streamlit text widgets */
[data-testid="stMarkdownContainer"] p {{ color:{T2}; font-size:0.875rem; line-height:1.65; }}
[data-testid="stHeadingWithActionElements"] h1 {{
    color:{T1} !important; font-size:1.6rem !important; font-weight:800 !important;
    letter-spacing:-0.03em !important;
}}
[data-testid="stHeadingWithActionElements"] h2 {{
    color:{T1} !important; font-size:1.1rem !important; font-weight:700 !important;
    letter-spacing:-0.02em !important;
}}
[data-testid="stHeadingWithActionElements"] h3 {{
    color:{T1} !important; font-size:0.95rem !important; font-weight:600 !important;
}}
[data-testid="stCaptionContainer"] p {{
    color:{T2} !important; font-size:0.8rem !important;
}}

/* tabs */
button[data-baseweb="tab"] {{
    background:transparent !important; border:none !important;
    color:{T2} !important; font-size:0.82rem !important; font-weight:500 !important;
    padding:0.6rem 1.1rem !important;
    border-bottom:2px solid transparent !important; border-radius:0 !important;
    transition:color 0.1s, border-color 0.1s !important;
}}
button[data-baseweb="tab"]:hover {{ color:{T1} !important; }}
button[data-baseweb="tab"][aria-selected="true"] {{
    color:{CA} !important; border-bottom-color:{CA} !important;
}}
[data-testid="stTabsContent"] {{ padding-top:1.25rem !important; }}

/* selectbox */
.stSelectbox > div > div {{
    background:{S2} !important; border:1px solid {B1} !important;
    border-radius:8px !important; color:{T1} !important; font-size:0.84rem !important;
}}
.stSelectbox > div > div:focus-within {{
    border-color:{CA} !important; box-shadow:0 0 0 2px rgba(0,198,167,0.1) !important;
}}
.stSelectbox label {{
    color:{T2} !important; font-size:0.72rem !important; font-weight:600 !important;
    text-transform:uppercase !important; letter-spacing:0.07em !important;
}}

/* text inputs */
.stTextInput input, .stTextArea textarea {{
    background:{S2} !important; border:1px solid {B1} !important;
    border-radius:8px !important; color:{T1} !important;
    font-family:Inter,sans-serif !important; font-size:0.875rem !important;
}}
.stTextInput input:focus, .stTextArea textarea:focus {{
    border-color:{CA} !important;
    box-shadow:0 0 0 2px rgba(0,198,167,0.1) !important;
    outline:none !important;
}}
.stTextInput label, .stTextArea label {{
    color:{T2} !important; font-size:0.72rem !important; font-weight:600 !important;
    text-transform:uppercase !important; letter-spacing:0.07em !important;
}}

/* form wrapper */
[data-testid="stForm"] {{
    background:{S1} !important; border:1px solid {B1} !important;
    border-radius:14px !important; padding:1.75rem 2rem !important;
}}

/* primary button */
.stButton > button[kind="primary"] {{
    background:linear-gradient(135deg,{CA},{CB}) !important;
    border:none !important; color:#021A14 !important;
    font-weight:700 !important; font-size:0.875rem !important;
    border-radius:8px !important; padding:0.58rem 1.75rem !important;
}}
.stButton > button[kind="primary"]:hover {{ opacity:0.87 !important; }}

/* expander */
.streamlit-expanderHeader {{
    background:{S2} !important; border:1px solid {B1} !important;
    border-radius:10px !important; color:{T1} !important;
    font-size:0.85rem !important; font-weight:500 !important;
}}
.streamlit-expanderHeader:hover {{ border-color:{B2} !important; }}
.streamlit-expanderContent {{
    background:{S1} !important; border:1px solid {B1} !important;
    border-top:none !important; border-radius:0 0 10px 10px !important;
    padding:1rem !important;
}}

/* dataframe */
[data-testid="stDataFrame"] {{
    border:1px solid {B1} !important; border-radius:12px !important;
    overflow:hidden !important;
}}

/* native metrics */
[data-testid="stMetric"] {{
    background:{S1} !important; border:1px solid {B1} !important;
    border-radius:12px !important; padding:1rem 1.25rem !important;
}}
[data-testid="metric-container"] label {{
    color:{T2} !important; font-size:0.68rem !important; font-weight:700 !important;
    text-transform:uppercase !important; letter-spacing:0.08em !important;
}}
[data-testid="stMetricValue"] {{
    color:{T1} !important; font-size:1.5rem !important;
    font-weight:700 !important; letter-spacing:-0.025em !important;
}}

/* alert */
[data-testid="stAlert"] {{
    background:{S2} !important; border-radius:10px !important;
    font-size:0.84rem !important;
}}

/* checkbox */
.stCheckbox label {{ color:{T2} !important; font-size:0.84rem !important; }}

/* spinner */
.stSpinner > div {{ border-top-color:{CA} !important; }}

/* plotly: transparent bg, no outer border (avoids double border) */
.stPlotlyChart {{ background:transparent !important; border:none !important; padding:0 !important; }}
</style>
""", unsafe_allow_html=True)


# ── HTML-safe component library ───────────────────────────────────────────────
# Rule: NEVER use <h1-6> or <p> tags inside st.markdown — use <div> with inline
# font-size/weight instead. Streamlit hoists heading/p elements out of containers.

def _dot(c):
    return (f'<span style="display:inline-block;width:7px;height:7px;border-radius:50%;'
            f'background:{c};box-shadow:0 0 6px {c}88;flex-shrink:0;"></span>')


def hero(icon, title, desc, badge="", badge_c=OK):
    """Page hero — no heading tags, all divs."""
    bdg = ""
    if badge:
        bdg = (f'<span style="display:inline-flex;align-items:center;gap:5px;'
               f'background:{badge_c}18;border:1px solid {badge_c}33;'
               f'color:{badge_c};font-size:0.68rem;font-weight:700;letter-spacing:.06em;'
               f'padding:.18rem .6rem;border-radius:20px;margin-left:.65rem;">'
               f'{_dot(badge_c)}&nbsp;{badge}</span>')
    st.markdown(f"""
<div style="padding-bottom:1.6rem;margin-bottom:1rem;border-bottom:1px solid {B1};">
  <div style="display:flex;align-items:center;flex-wrap:wrap;margin-bottom:.45rem;">
    <span style="font-size:1.3rem;margin-right:.5rem;line-height:1;">{icon}</span>
    <span style="font-size:1.6rem;font-weight:800;color:{T1};letter-spacing:-.035em;
                 line-height:1.2;">{title}</span>{bdg}
  </div>
  <div style="color:{T2};font-size:.875rem;line-height:1.6;max-width:640px;">{desc}</div>
</div>""", unsafe_allow_html=True)


def kpi(cols_tuple, items):
    """items: list of (label, value, note, accent_top)"""
    for col, (label, value, note, accent) in zip(cols_tuple, items):
        top = f"border-top:2px solid {CA};" if accent else f"border-top:1px solid {B1};"
        note_h = (f'<div style="color:{T3};font-size:.72rem;margin-top:.4rem;'
                  f'line-height:1.4;">{note}</div>') if note else ""
        col.markdown(f"""
<div style="background:{S1};border:1px solid {B1};{top}border-radius:12px;
            padding:1.2rem 1.4rem;height:100%;">
  <div style="color:{T2};font-size:.67rem;font-weight:700;text-transform:uppercase;
              letter-spacing:.09em;margin-bottom:.5rem;">{label}</div>
  <div style="color:{T1};font-size:1.65rem;font-weight:800;letter-spacing:-.03em;
              line-height:1;">{value}</div>
  {note_h}
</div>""", unsafe_allow_html=True)


def chart_header(title, sub="", badge=""):
    """Titled card header above a chart — div only."""
    bdg = (f'<span style="background:rgba(0,198,167,.1);color:{CA};font-size:.65rem;'
           f'font-weight:700;padding:.15rem .5rem;border-radius:20px;letter-spacing:.06em;">'
           f'{badge}</span>') if badge else ""
    sub_h = (f'<div style="color:{T2};font-size:.77rem;margin-top:.15rem;">'
             f'{sub}</div>') if sub else ""
    st.markdown(f"""
<div style="background:{S1};border:1px solid {B1};border-radius:14px 14px 0 0;
            padding:1rem 1.25rem .75rem;border-bottom:1px solid {B1};">
  <div style="display:flex;align-items:center;justify-content:space-between;">
    <span style="color:{T1};font-size:.92rem;font-weight:700;letter-spacing:-.015em;">{title}</span>
    {bdg}
  </div>{sub_h}
</div>""", unsafe_allow_html=True)


def chart_wrap_open():
    st.markdown(f'<div style="background:{S1};border:1px solid {B1};border-top:none;'
                f'border-radius:0 0 14px 14px;padding:.75rem 1rem 1rem;">', unsafe_allow_html=True)

def chart_wrap_close():
    st.markdown("</div>", unsafe_allow_html=True)


def section(title, sub=""):
    sub_h = f'<div style="color:{T2};font-size:.77rem;margin-top:.15rem;">{sub}</div>' if sub else ""
    st.markdown(f"""
<div style="margin:1.75rem 0 .9rem;">
  <span style="color:{T1};font-size:.92rem;font-weight:700;letter-spacing:-.015em;">{title}</span>
  {sub_h}
</div>""", unsafe_allow_html=True)


def pills(items, arrow="", color=T2):
    html = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:3px;'
        f'background:{S3};border:1px solid {B2};color:{T1};font-size:.77rem;'
        f'font-weight:500;padding:.26rem .62rem;border-radius:6px;margin:2px 3px 2px 0;">'
        f'<span style="color:{color};font-size:.65rem;">{arrow}</span>{s}</span>'
        for s in items)
    st.markdown(f'<div style="display:flex;flex-wrap:wrap;padding-top:.25rem;">'
                f'{html}</div>', unsafe_allow_html=True)


def row_item(text, indicator="", ind_color=OK):
    ind = (f'<span style="color:{ind_color};font-size:.72rem;font-weight:700;">'
           f'{indicator}</span>') if indicator else ""
    st.markdown(f"""
<div style="display:flex;align-items:center;justify-content:space-between;
            padding:.48rem .8rem;border-radius:8px;margin-bottom:3px;
            background:{S2};border:1px solid {B1};">
  <span style="color:{T1};font-size:.82rem;font-weight:500;">{text}</span>
  {ind}
</div>""", unsafe_allow_html=True)


def insight(title, body, color=CA):
    st.markdown(f"""
<div style="background:{S2};border:1px solid {B1};border-left:3px solid {color};
            border-radius:0 10px 10px 0;padding:.9rem 1rem;margin-bottom:.5rem;">
  <div style="color:{T1};font-size:.82rem;font-weight:600;margin-bottom:.22rem;">{title}</div>
  <div style="color:{T2};font-size:.77rem;line-height:1.55;">{body}</div>
</div>""", unsafe_allow_html=True)


def empty(icon, title, body):
    st.markdown(f"""
<div style="text-align:center;padding:3rem 2rem;background:{S1};
            border:1px dashed {B2};border-radius:14px;margin:.5rem 0;">
  <div style="font-size:1.8rem;margin-bottom:.65rem;">{icon}</div>
  <div style="color:{T1};font-size:.92rem;font-weight:600;margin-bottom:.35rem;">{title}</div>
  <div style="color:{T2};font-size:.82rem;max-width:340px;margin:0 auto;line-height:1.6;">{body}</div>
</div>""", unsafe_allow_html=True)


def action_step(n, text):
    st.markdown(f"""
<div style="display:flex;gap:.9rem;align-items:flex-start;background:{S2};
            border:1px solid {B1};border-radius:10px;padding:.8rem 1rem;margin-bottom:.45rem;">
  <span style="color:{CA};font-size:.72rem;font-weight:700;font-family:'JetBrains Mono',monospace;
               flex-shrink:0;margin-top:1px;opacity:.75;">0{n}</span>
  <span style="color:{T1};font-size:.875rem;line-height:1.6;">{text}</span>
</div>""", unsafe_allow_html=True)


# ── Data fetchers ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def fetch_snapshot():
    try:
        r = requests.get(f"{API_BASE}/api/v1/market/snapshot", timeout=TIMEOUT)
        r.raise_for_status(); return r.json()
    except Exception as e: return {"error": str(e)}

@st.cache_data(ttl=3600)
def fetch_skills(role="all"):
    try:
        r = requests.get(f"{API_BASE}/api/v1/market/skills",
                         params={"role_category": role}, timeout=TIMEOUT)
        r.raise_for_status(); return r.json()
    except Exception as e: return {"error": str(e)}

@st.cache_data(ttl=3600)
def fetch_trending():
    try:
        r = requests.get(f"{API_BASE}/api/v1/market/trending", timeout=TIMEOUT)
        r.raise_for_status(); return r.json()
    except Exception: return {"rising": [], "declining": [], "top_now": []}

@st.cache_data(ttl=300)
def fetch_health():
    try:
        r = requests.get(f"{API_BASE}/api/v1/health", timeout=TIMEOUT)
        r.raise_for_status(); return r.json()
    except Exception as e: return {"status": "error", "error": str(e)}


# ── Sidebar ───────────────────────────────────────────────────────────────────
health  = fetch_health()
_st     = health.get("status", "unknown")
_fh     = health.get("data_freshness_h")
_jobs   = health.get("jobs_total", 0)
_sc     = OK  if _st == "healthy" else (WRN if _st == "stale" else ERR)
_fc     = OK  if (_fh or 999) < 24 else (WRN if (_fh or 999) < 72 else ERR)
_fs     = f"{_fh:.0f}h ago" if _fh is not None else "No data"

with st.sidebar:
    # Brand
    st.markdown(f"""
<div style="padding:1.55rem 1rem 1.2rem;border-bottom:1px solid {B1};margin-bottom:1rem;">
  <div style="display:flex;align-items:center;gap:.55rem;">
    <div style="width:30px;height:30px;flex-shrink:0;
                background:linear-gradient(135deg,{CA},{CB});border-radius:8px;
                display:flex;align-items:center;justify-content:center;
                font-size:.85rem;font-weight:900;color:#021A14;
                font-family:'JetBrains Mono',monospace;">M</div>
    <div>
      <div style="color:{T1};font-size:.92rem;font-weight:700;letter-spacing:-.02em;
                  line-height:1.15;">MarketForge AI</div>
      <div style="color:{T3};font-size:.63rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:.07em;">UK AI Intelligence</div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

    # Status card
    st.markdown(f"""
<div style="margin:0 .5rem 1.1rem;padding:.8rem .9rem;background:{S2};
            border:1px solid {B1};border-radius:10px;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.5rem;">
    <span style="color:{T3};font-size:.62rem;font-weight:700;text-transform:uppercase;
                 letter-spacing:.08em;">System</span>
    <span style="display:flex;align-items:center;gap:.3rem;color:{_sc};
                 font-size:.72rem;font-weight:600;">{_dot(_sc)}&nbsp;{_st.upper()}</span>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:.3rem;">
    <div style="background:{S1};border-radius:6px;padding:.42rem .5rem;">
      <div style="color:{T3};font-size:.58rem;text-transform:uppercase;letter-spacing:.06em;">Freshness</div>
      <div style="color:{_fc};font-size:.77rem;font-weight:600;margin-top:1px;">{_fs}</div>
    </div>
    <div style="background:{S1};border-radius:6px;padding:.42rem .5rem;">
      <div style="color:{T3};font-size:.58rem;text-transform:uppercase;letter-spacing:.06em;">Jobs</div>
      <div style="color:{T1};font-size:.77rem;font-weight:600;margin-top:1px;">{_jobs:,}</div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

    # Nav label
    st.markdown(f'<div style="padding:0 .5rem .3rem;color:{T3};font-size:.62rem;font-weight:700;'
                f'text-transform:uppercase;letter-spacing:.09em;">Workspace</div>',
                unsafe_allow_html=True)

    NAV = [
        ("◈  Market Overview",    "Market Overview"),
        ("⬡  Skill Intelligence", "Skill Intelligence"),
        ("◇  Salary & Geography", "Salary & Geography"),
        ("◎  Career Advisor",     "Career Advisor"),
        ("◆  Research Signals",   "Research Signals"),
        ("⊕  Job Board",          "Job Board"),
        ("⊟  Pipeline Status",    "Pipeline Status"),
    ]
    nav_sel = st.radio("nav", [n[0] for n in NAV], label_visibility="collapsed")
    page    = dict(NAV)[nav_sel]

    st.markdown(f'<div style="border-top:1px solid {B1};margin:.9rem .5rem .75rem;"></div>',
                unsafe_allow_html=True)
    if st.button("↺  Refresh data"):
        st.cache_data.clear(); st.rerun()
    st.markdown(f'<div style="padding:.4rem .5rem 0;color:{T3};font-size:.69rem;line-height:1.85;">'
                f'Updated Tue &amp; Thu<br>'
                f'<a href="https://github.com/viraj97-sl" '
                f'style="color:{T3};text-decoration:none;">v0.1.0 · GitHub ↗</a></div>',
                unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — MARKET OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════
if page == "Market Overview":
    snap     = fetch_snapshot()
    trending = fetch_trending()

    fresh_badge = f"{_fh:.0f}h ago" if _fh is not None else "LIVE"
    hero("◈", "UK AI Job Market",
         "Live intelligence across UK AI & ML hiring — skills, salaries, and velocity.",
         badge=fresh_badge, badge_c=_fc)

    if "error" in snap:
        empty("⚠", "API Unavailable",
              f"Ensure FastAPI is running.<br><code>{snap['error']}</code>"); st.stop()

    # ── KPI row ──
    salary_v = f"£{snap['salary_p50']:,.0f}" if snap.get("salary_p50") else "—"
    c1, c2, c3, c4 = st.columns(4)
    kpi((c1, c2, c3, c4), [
        ("Active Roles",     f"{snap.get('job_count',0):,}", f"Week {snap.get('week_start','—')}", True),
        ("Median Salary",    salary_v,                        "UK AI/ML benchmark",                False),
        ("Visa Sponsorship", f"{snap.get('sponsorship_rate',0)*100:.1f}%", "of listed roles",     False),
        ("Pipeline Cycle",   snap.get("week_start", "—"),    "current week",                      False),
    ])

    st.markdown("<div style='height:1.75rem'></div>", unsafe_allow_html=True)

    # ── 65/35 split: chart left, signals right ──
    top_skills = snap.get("top_skills") or {}
    rising     = (trending.get("rising")    or [])[:10]
    declining  = (trending.get("declining") or [])[:8]

    col_c, col_s = st.columns([13, 7])

    with col_c:
        chart_header("Top 20 In-Demand Skills",
                     "Mentions in UK AI/ML postings this week", "LIVE")
        if top_skills:
            df_s = pd.DataFrame(
                sorted(top_skills.items(), key=lambda x: -x[1])[:20],
                columns=["Skill", "Mentions"])
            fig = px.bar(df_s, x="Mentions", y="Skill", orientation="h",
                         color="Mentions",
                         color_continuous_scale=[[0,"#0D1E2E"],[.45,"#006B5A"],[1, CA]])
            fig.update_traces(marker_line_width=0)
            fig.update_coloraxes(showscale=False)
            _chart(fig, height=490)
            fig.update_layout(margin=dict(l=0, r=16, t=10, b=10))
            fig.update_yaxes(categoryorder="total ascending",
                             tickfont=dict(color=T1, size=11), automargin=True)
            # chart rendered inside header card
            st.markdown(f'<div style="background:{S1};border:1px solid {B1};border-top:none;'
                        f'border-radius:0 0 14px 14px;padding:.5rem .75rem .75rem;">',
                        unsafe_allow_html=True)
            st.plotly_chart(fig, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="background:{S1};border:1px solid {B1};border-top:none;'
                        f'border-radius:0 0 14px 14px;padding:1rem;">', unsafe_allow_html=True)
            empty("◈", "No skill data", "Run the ingestion pipeline first.")
            st.markdown("</div>", unsafe_allow_html=True)

    with col_s:
        chart_header("Market Signals", "Week-on-week momentum")
        st.markdown(f'<div style="background:{S1};border:1px solid {B1};border-top:none;'
                    f'border-radius:0 0 14px 14px;padding:1rem 1.1rem 1.1rem;">',
                    unsafe_allow_html=True)

        # Rising
        st.markdown(f'<div style="color:{OK};font-size:.65rem;font-weight:800;'
                    f'text-transform:uppercase;letter-spacing:.08em;margin-bottom:.55rem;">'
                    f'↑ Rising Skills</div>', unsafe_allow_html=True)
        if rising:
            pills(rising, "↑", OK)
        else:
            st.markdown(f'<div style="color:{T3};font-size:.78rem;margin-bottom:.5rem;">'
                        f'Not enough history yet</div>', unsafe_allow_html=True)

        st.markdown(f'<div style="border-top:1px solid {B1};margin:1rem 0;"></div>',
                    unsafe_allow_html=True)

        # Declining
        st.markdown(f'<div style="color:{ERR};font-size:.65rem;font-weight:800;'
                    f'text-transform:uppercase;letter-spacing:.08em;margin-bottom:.55rem;">'
                    f'↓ Declining Skills</div>', unsafe_allow_html=True)
        if declining:
            pills(declining, "↓", ERR)
        else:
            st.markdown(f'<div style="color:{T3};font-size:.78rem;margin-bottom:.5rem;">'
                        f'Not enough history yet</div>', unsafe_allow_html=True)

        st.markdown(f'<div style="border-top:1px solid {B1};margin:1rem 0;"></div>',
                    unsafe_allow_html=True)

        # Quick insights
        if snap.get("salary_p50"):
            insight("Salary midpoint",
                    f"Median UK AI/ML role pays <strong style='color:{T1};'>"
                    f"£{snap['salary_p50']:,.0f}</strong> this week.")
        insight("Sponsorship",
                f"<strong style='color:{T1};'>{snap.get('sponsorship_rate',0)*100:.1f}%</strong>"
                f" of active roles offer visa sponsorship.", color=CB)

        st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — SKILL INTELLIGENCE
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Skill Intelligence":
    hero("⬡", "Skill Intelligence",
         "Demand index, taxonomy breakdown, and week-on-week trend signals.")

    role_map = {
        "All Roles":"all","ML Engineer":"ml_engineer","Data Scientist":"data_scientist",
        "AI Engineer":"ai_engineer","MLOps Engineer":"mlops_engineer",
        "NLP Engineer":"nlp_engineer","Computer Vision":"computer_vision_engineer",
    }
    fc, _ = st.columns([3, 9])
    with fc:
        rl = st.selectbox("Role filter", list(role_map.keys()))
    sd = fetch_skills(role_map[rl])

    if "error" in sd:
        empty("⚠", "Data unavailable", sd["error"]); st.stop()

    ts  = sd.get("top_skills") or {}
    ris = sd.get("rising_skills")   or []
    dec = sd.get("declining_skills") or []

    if not ts:
        empty("⬡", "No skill data yet", "Run the ingestion pipeline."); st.stop()

    tab1, tab2, tab3 = st.tabs(["Demand Index", "Visual Breakdown", "Trend Signals"])

    with tab1:
        section("Skill Demand Index", f"{len(ts)} skills · {rl}")
        sorted_s = sorted(ts.items(), key=lambda x: -x[1])[:25]
        mx = sorted_s[0][1] if sorted_s else 1
        rows = [{"#": i, "Skill": sk, "Demand": cnt,
                 "Share %": round(cnt/mx*100, 1),
                 "Signal": "↑ Rising" if sk in ris else ("↓ Fading" if sk in dec else "— Stable")}
                for i, (sk, cnt) in enumerate(sorted_s, 1)]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True,
                     column_config={
                         "#":       st.column_config.NumberColumn(width="small"),
                         "Demand":  st.column_config.NumberColumn(format="%d"),
                         "Share %": st.column_config.ProgressColumn(
                             format="%.0f%%", min_value=0, max_value=100, width="medium"),
                         "Signal":  st.column_config.TextColumn(width="medium"),
                     })

    with tab2:
        section("Demand Treemap", "Area = relative demand weight")
        df_t = pd.DataFrame([{"skill": k, "count": v, "group": "Market Demand"}
                              for k, v in list(ts.items())[:35]])
        fig = px.treemap(df_t, path=["group","skill"], values="count", color="count",
                         color_continuous_scale=[[0,"#0C1A26"],[.5,"#005A4A"],[1,CA]])
        fig.update_traces(marker_line_width=0.5, marker_line_color=BG,
                          textfont_color=T1, textfont_size=12,
                          hovertemplate="<b>%{label}</b><br>Demand: %{value}<extra></extra>")
        fig.update_coloraxes(showscale=False)
        _chart(fig, height=440)
        st.plotly_chart(fig, use_container_width=True)

    with tab3:
        section("Week-on-Week Trend Signals", "Requires ≥2 pipeline cycles")
        cr, cd = st.columns(2)
        with cr:
            st.markdown(f'<div style="color:{OK};font-size:.72rem;font-weight:800;'
                        f'text-transform:uppercase;letter-spacing:.07em;margin-bottom:.8rem;">'
                        f'↑ Gaining momentum</div>', unsafe_allow_html=True)
            if ris:
                for s in ris[:12]: row_item(s, "↑", OK)
            else:
                empty("—", "Insufficient history", "Needs ≥2 cycles.")
        with cd:
            st.markdown(f'<div style="color:{ERR};font-size:.72rem;font-weight:800;'
                        f'text-transform:uppercase;letter-spacing:.07em;margin-bottom:.8rem;">'
                        f'↓ Losing demand</div>', unsafe_allow_html=True)
            if dec:
                for s in dec[:12]: row_item(s, "↓", ERR)
            else:
                empty("—", "Insufficient history", "Needs ≥2 cycles.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — SALARY & GEOGRAPHY
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Salary & Geography":
    hero("◇", "Salary & Geography",
         "Compensation benchmarks, percentile bands, sponsorship rates, and UK geography.")
    snap = fetch_snapshot()
    if "error" in snap:
        empty("⚠", "API unavailable", snap["error"]); st.stop()

    p25, p50, p75 = snap.get("salary_p25"), snap.get("salary_p50"), snap.get("salary_p75")
    spr = snap.get("sponsorship_rate") or 0

    # KPI row
    c1, c2, c3, c4 = st.columns(4)
    kpi((c1, c2, c3, c4), [
        ("25th Percentile", f"£{p25:,.0f}" if p25 else "—", "entry / junior",  True),
        ("Median (P50)",    f"£{p50:,.0f}" if p50 else "—", "market midpoint",  True),
        ("75th Percentile", f"£{p75:,.0f}" if p75 else "—", "senior / lead",    True),
        ("Sponsorship",     f"{spr*100:.1f}%",               "of roles",         False),
    ])

    st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)

    # 55/45 split: salary box | sponsorship gauge
    cl, cr = st.columns([11, 9])

    with cl:
        chart_header("Salary Distribution", "UK AI/ML roles — current cycle")
        if p25 and p50 and p75:
            fig = go.Figure()
            fig.add_trace(go.Box(
                name="UK AI/ML", q1=[p25], median=[p50], q3=[p75],
                lowerfence=[max(p25*.72, 22000)], upperfence=[p75*1.28],
                boxmean=True, whiskerwidth=0.4,
                fillcolor=f"rgba(0,198,167,0.1)",
                line=dict(color=CA, width=1.5),
                marker=dict(color=CA, size=6),
            ))
            _chart(fig, height=280)
            fig.update_layout(margin=dict(l=10, r=10, t=10, b=10))
            fig.update_yaxes(tickprefix="£", tickformat=",.0f",
                             gridcolor=B1, automargin=True)
            fig.update_xaxes(showgrid=False, showticklabels=False)
            st.markdown(f'<div style="background:{S1};border:1px solid {B1};border-top:none;'
                        f'border-radius:0 0 14px 14px;padding:.5rem .75rem .75rem;">',
                        unsafe_allow_html=True)
            st.plotly_chart(fig, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="background:{S1};border:1px solid {B1};border-top:none;'
                        f'border-radius:0 0 14px 14px;padding:1rem;">', unsafe_allow_html=True)
            empty("◇", "Awaiting data", "Salary data populates after several ingestion cycles.")
            st.markdown("</div>", unsafe_allow_html=True)

    with cr:
        chart_header("Visa Sponsorship", "Share of roles explicitly offering sponsorship")
        fig_sp = go.Figure(go.Indicator(
            mode="gauge+number",
            value=spr * 100,
            number={"suffix": "%", "font": {"color": T1, "size": 36, "family": "Inter"}},
            gauge={
                "axis": {"range": [0, 100], "tickcolor": T3,
                         "tickfont": {"color": T3, "size": 9}},
                "bar": {"color": CA, "thickness": 0.22},
                "bgcolor": "rgba(0,0,0,0)", "borderwidth": 0,
                "steps": [
                    {"range": [0,  25], "color": "rgba(239,68,68,0.07)"},
                    {"range": [25, 50], "color": "rgba(245,158,11,0.07)"},
                    {"range": [50,100], "color": "rgba(16,185,129,0.07)"},
                ],
                "threshold": {"line": {"color": WRN, "width": 2},
                              "thickness": 0.8, "value": 25},
            },
            title={"text": "current week",
                   "font": {"color": T2, "size": 11, "family": "Inter"}},
        ))
        _chart(fig_sp, height=265)
        fig_sp.update_layout(margin=dict(l=20, r=20, t=10, b=10))
        st.markdown(f'<div style="background:{S1};border:1px solid {B1};border-top:none;'
                    f'border-radius:0 0 14px 14px;padding:.5rem .75rem .75rem;">',
                    unsafe_allow_html=True)
        st.plotly_chart(fig_sp, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # City chart
    tc = snap.get("top_cities") or {}
    if tc:
        st.markdown("<div style='height:.75rem'></div>", unsafe_allow_html=True)
        chart_header("Geographic Distribution", "Active AI/ML roles by UK city")
        df_c = pd.DataFrame(sorted(tc.items(), key=lambda x:-x[1])[:12],
                            columns=["City","Jobs"])
        fig_c = px.bar(df_c, x="City", y="Jobs", color="Jobs",
                       color_continuous_scale=[[0,"#0C1A26"],[1, CA]])
        fig_c.update_traces(marker_line_width=0)
        fig_c.update_coloraxes(showscale=False)
        _chart(fig_c, height=290)
        fig_c.update_layout(margin=dict(l=10, r=10, t=10, b=40))
        st.markdown(f'<div style="background:{S1};border:1px solid {B1};border-top:none;'
                    f'border-radius:0 0 14px 14px;padding:.5rem .75rem .75rem;">',
                    unsafe_allow_html=True)
        st.plotly_chart(fig_c, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4 — CAREER ADVISOR
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Career Advisor":
    hero("◎", "Career Intelligence",
         "AI-powered gap analysis benchmarked against live UK market data. Processed in-memory — nothing stored.")

    with st.form("career_form"):
        cs, cfg = st.columns([5, 4])
        with cs:
            skills_raw = st.text_area(
                "Your skills (one per line or comma-separated)",
                placeholder="Python\nPyTorch\nLangChain\nFastAPI\nSQL", height=150)
        with cfg:
            target_role = st.selectbox("Target role", [
                "ML Engineer","Data Scientist","AI Engineer","MLOps Engineer",
                "NLP Engineer","Computer Vision Engineer","Research Scientist"])
            experience  = st.selectbox("Experience level", ["junior","mid","senior","lead"])
            location    = st.text_input("Location", value="London")
            sponsorship = st.checkbox("I require visa sponsorship")
        submitted = st.form_submit_button("Analyse Profile →", type="primary")

    if submitted and skills_raw.strip():
        skills = [s.strip() for s in skills_raw.replace(",","\n").split("\n") if s.strip()]
        with st.spinner("Analysing against live UK market data…"):
            try:
                resp = requests.post(
                    f"{API_BASE}/api/v1/career/analyse",
                    json={"skills":skills,"target_role":target_role,
                          "experience_level":experience,"location":location,
                          "visa_sponsorship":sponsorship}, timeout=120)
                if resp.status_code == 429:
                    st.warning("Rate limit — wait 60 seconds."); st.stop()
                if resp.status_code == 422:
                    st.error(f"Input rejected: {resp.json().get('detail')}"); st.stop()
                resp.raise_for_status()
                report = resp.json()
            except requests.exceptions.ConnectionError:
                st.error("Cannot reach the API. Ensure `uvicorn api.main:app` is running.")
                st.stop()
            except Exception as e:
                st.error(f"Analysis failed: {e}"); st.stop()

        mp   = report.get("market_match_pct", 0)
        md   = report.get("match_distribution", {})
        sal  = report.get("salary_expectation", {})
        mc   = OK if mp > 65 else (WRN if mp > 40 else ERR)

        st.divider()

        c1,c2,c3,c4 = st.columns(4)
        kpi((c1,c2,c3,c4), [
            ("Market Match",      f"{mp:.0f}%",
             "strong fit" if mp > 65 else "developing fit", True),
            ("Strong Matches",    f"{md.get('strong',0)*100:.0f}%",  "of live roles",     False),
            ("Within Reach",      f"{md.get('moderate',0)*100:.0f}%","with upskilling",   False),
            ("Salary Benchmark",  f"£{sal['p50']:,.0f}" if sal.get("p50") else "—",
             f"n={sal.get('sample_size',0)} roles", False),
        ])

        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

        t1, t2, t3, t4 = st.tabs(["Summary","Skill Gaps","90-Day Plan","Sector Fit"])

        with t1:
            section("Career Intelligence Summary")
            narrative = report.get("narrative_summary","").replace("\n","<br>")
            st.markdown(
                f'<div style="background:{S1};border:1px solid {B1};border-radius:12px;'
                f'padding:1.4rem 1.5rem;color:{T2};font-size:.875rem;line-height:1.8;">'
                f'{narrative}</div>', unsafe_allow_html=True)

        with t2:
            section("Priority Skill Gaps", "Ranked by market demand")
            gaps = report.get("top_skill_gaps", [])
            if gaps:
                st.dataframe(pd.DataFrame(gaps), use_container_width=True, hide_index=True)
            else:
                st.success("No critical gaps — your profile aligns well with current demand.")

        with t3:
            section("90-Day Action Plan")
            for i, step in enumerate(report.get("action_plan_90d", []), 1):
                action_step(i, step)

        with t4:
            section("Sector Fit")
            for sec in report.get("sector_fit", []):
                with st.expander(f"{sec['sector']} — {sec['fit_score']:.0f}% fit"):
                    ca, cb = st.columns(2)
                    ca.metric("Fit score",        f"{sec['fit_score']:.0f}%")
                    cb.metric("Sponsorship rate", f"{sec['sponsorship_rate']*100:.0f}%")

    elif submitted:
        st.warning("Enter at least one skill to begin.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 5 — RESEARCH SIGNALS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Research Signals":
    hero("◆", "Research Intelligence",
         "Emerging techniques from arXiv & tech blogs detected 4–8 weeks before they appear in job postings.")

    signals = []
    try:
        from marketforge.memory.postgres import get_sync_engine
        from sqlalchemy import text as st_text
        engine = get_sync_engine()
        tbl = "research_signals" if engine.dialect.name=="sqlite" else "market.research_signals"
        with engine.connect() as conn:
            rows = conn.execute(st_text(
                f"SELECT technique_name,source,first_seen,mention_count,"
                f"first_in_jd,adoption_lag_days,relevance_score,summary "
                f"FROM {tbl} ORDER BY relevance_score DESC,mention_count DESC LIMIT 20"
            )).mappings().fetchall()
        signals = [dict(r) for r in rows]
    except Exception as exc:
        st.caption(f"DB: {exc}")

    if signals:
        for sig in signals:
            with st.expander(
                f"{sig['technique_name']}  ·  {sig['source'].upper()}  ·  "
                f"score {sig['relevance_score']:.2f}"):
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(
                        f'<div style="color:{T2};font-size:.83rem;line-height:1.8;">'
                        f'First seen: <strong style="color:{T1};">{sig["first_seen"]}</strong><br>'
                        f'Mentions: <strong style="color:{T1};">{sig["mention_count"]}</strong>'
                        f'</div>', unsafe_allow_html=True)
                with c2:
                    lag = (f'<br>Lag: <strong style="color:{T1};">'
                           f'{sig["adoption_lag_days"]} days</strong>'
                           ) if sig.get("adoption_lag_days") else ""
                    st.markdown(
                        f'<div style="color:{T2};font-size:.83rem;line-height:1.8;">'
                        f'In JDs: <strong style="color:{T1};">'
                        f'{sig.get("first_in_jd") or "Not yet"}</strong>{lag}'
                        f'</div>', unsafe_allow_html=True)
                if sig.get("summary"):
                    st.markdown(
                        f'<div style="color:{T2};font-size:.82rem;margin-top:.6rem;'
                        f'line-height:1.6;">{sig["summary"]}</div>', unsafe_allow_html=True)
    else:
        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
        items = [
            ("arXiv Monitor",       "Tracks cs.LG, cs.AI, cs.CL, cs.CV.<br>Papers ingested daily.",                CA),
            ("Blog Signal Scanner", "Monitors DeepMind, Meta AI, Hugging Face<br>and UK AI labs.",                  CB),
            ("Adoption Lag Model",  "Predicts paper-to-job-posting arrival.<br>Mean lag: 6–14 weeks.",              PRP),
            ("Emerging Watch List", "Surfaces techniques in papers likely to<br>reach JDs within 30–60 days.",      WRN),
        ]
        ca, cb = st.columns(2)
        for i, (ttl, dsc, clr) in enumerate(items):
            with (ca if i%2==0 else cb):
                st.markdown(f"""
<div style="background:{S1};border:1px solid {B1};border-top:2px solid {clr};
            border-radius:12px;padding:1.3rem 1.4rem;margin-bottom:.7rem;">
  <div style="background:{clr}18;border:1px solid {clr}33;color:{clr};
              font-size:.62rem;font-weight:700;padding:.14rem .48rem;border-radius:20px;
              letter-spacing:.07em;display:inline-block;margin-bottom:.55rem;">PHASE 3</div>
  <div style="color:{T1};font-size:.9rem;font-weight:700;margin-bottom:.4rem;
              letter-spacing:-.01em;">{ttl}</div>
  <div style="color:{T2};font-size:.8rem;line-height:1.6;">{dsc}</div>
</div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 6 — JOB BOARD
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Job Board":
    hero("⊕", "Live Job Board",
         "Browse current UK AI/ML postings indexed by the pipeline. Click any card to view the original listing on the job board.")

    # ── Fetch from DB ─────────────────────────────────────────────────────────
    jobs_data = []
    total_indexed = 0
    try:
        from marketforge.memory.postgres import get_sync_engine
        from sqlalchemy import text as st_text
        engine = get_sync_engine()
        tbl    = "jobs" if engine.dialect.name == "sqlite" else "market.jobs"
        sk_tbl = "job_skills" if engine.dialect.name == "sqlite" else "market.job_skills"

        with engine.connect() as conn:
            total_indexed = conn.execute(st_text(f"SELECT COUNT(*) FROM {tbl}")).scalar() or 0

            rows = conn.execute(st_text(f"""
                SELECT j.job_id, j.title, j.company, j.location, j.salary_min, j.salary_max,
                       j.work_model, j.experience_level, j.role_category, j.source,
                       j.offers_sponsorship, j.posted_date, j.scraped_at, j.url,
                       j.is_startup, j.company_stage, j.equity_offered,
                       COALESCE(
                           (SELECT STRING_AGG(skill, ', ' ORDER BY confidence DESC)
                            FROM {sk_tbl} WHERE job_id = j.job_id LIMIT 8),
                           ''
                       ) AS skills
                FROM {tbl} j
                ORDER BY j.scraped_at DESC
                LIMIT 500
            """)).mappings().fetchall()
            jobs_data = [dict(r) for r in rows]
    except Exception as exc:
        st.warning(f"Could not load jobs: {exc}")

    if not jobs_data:
        empty("⊕", "No jobs indexed yet", "Run the ingestion pipeline first: `python scripts/run_pipeline.py`")
        st.stop()

    # ── Filter bar ────────────────────────────────────────────────────────────
    fa, fb, fc, fd, fe = st.columns([3, 2, 2, 2, 3])
    with fa:
        search_q = st.text_input("Search", placeholder="e.g. LLM, PyTorch, NLP…")
    with fb:
        role_opts = ["All roles"] + sorted({j["role_category"] for j in jobs_data if j.get("role_category")})
        role_f = st.selectbox("Role", role_opts)
    with fc:
        wm_opts = ["All modes"] + sorted({j["work_model"] for j in jobs_data if j.get("work_model") and j["work_model"] != "unknown"})
        wm_f = st.selectbox("Work model", wm_opts)
    with fd:
        exp_opts = ["All levels"] + sorted({j["experience_level"] for j in jobs_data if j.get("experience_level")})
        exp_f = st.selectbox("Level", exp_opts)
    with fe:
        src_opts = ["All sources"] + sorted({j["source"] for j in jobs_data if j.get("source")})
        src_f = st.selectbox("Source", src_opts)

    fc2, fd2 = st.columns([3, 5])
    with fc2:
        sponsorship_only = st.checkbox("Visa sponsorship only")

    # ── Apply filters ─────────────────────────────────────────────────────────
    filtered = jobs_data
    if search_q.strip():
        q = search_q.strip().lower()
        filtered = [j for j in filtered if
                    q in (j.get("title") or "").lower() or
                    q in (j.get("company") or "").lower() or
                    q in (j.get("skills") or "").lower() or
                    q in (j.get("location") or "").lower()]
    if role_f != "All roles":
        filtered = [j for j in filtered if j.get("role_category") == role_f]
    if wm_f != "All modes":
        filtered = [j for j in filtered if j.get("work_model") == wm_f]
    if exp_f != "All levels":
        filtered = [j for j in filtered if j.get("experience_level") == exp_f]
    if src_f != "All sources":
        filtered = [j for j in filtered if j.get("source") == src_f]
    if sponsorship_only:
        filtered = [j for j in filtered if j.get("offers_sponsorship")]

    # Summary counts
    st.markdown(
        f'<div style="display:flex;gap:1.2rem;align-items:center;margin:.6rem 0 1.2rem;">'
        f'<span style="color:{T1};font-size:.85rem;font-weight:600;">'
        f'{len(filtered):,} roles shown</span>'
        f'<span style="color:{T3};font-size:.78rem;">of {total_indexed:,} indexed</span>'
        f'</div>', unsafe_allow_html=True)

    # ── Source badge colours ──────────────────────────────────────────────────
    SOURCE_COLORS = {
        "adzuna":           CA,
        "reed":             CB,
        "wellfound":        PRP,
        "linkedin":         "#0A66C2",
        "greenhouse":       WRN,
        "lever":            "#FF6B35",
        "workable":         OK,
    }
    WM_LABELS = {"remote": ("REMOTE", OK), "hybrid": ("HYBRID", CB),
                 "onsite": ("ON-SITE", T2), "unknown": ("", T3)}

    # ── Job cards (2-column grid) ─────────────────────────────────────────────
    PAGE_SIZE = 30
    page_n = st.session_state.get("jb_page", 0)
    paginated = filtered[page_n * PAGE_SIZE : (page_n + 1) * PAGE_SIZE]

    for i in range(0, len(paginated), 2):
        cols = st.columns(2)
        for ci, job in enumerate(paginated[i:i+2]):
            with cols[ci]:
                # ── Salary display ──
                s_min, s_max = job.get("salary_min"), job.get("salary_max")
                if s_min and s_max:
                    sal_txt = f"£{s_min:,.0f} – £{s_max:,.0f}"
                    sal_col = CA
                elif s_max:
                    sal_txt = f"Up to £{s_max:,.0f}"
                    sal_col = CA
                elif s_min:
                    sal_txt = f"From £{s_min:,.0f}"
                    sal_col = CA
                else:
                    sal_txt = "Salary undisclosed"
                    sal_col = T3

                # ── Work model badge ──
                wm_label, wm_color = WM_LABELS.get(job.get("work_model", "unknown"), ("", T3))

                # ── Source badge ──
                src = (job.get("source") or "unknown").lower()
                src_c = SOURCE_COLORS.get(src, T2)

                # ── Sponsorship indicator ──
                spons_h = ""
                if job.get("offers_sponsorship"):
                    spons_h = (f'<span style="background:{OK}18;border:1px solid {OK}33;'
                               f'color:{OK};font-size:.6rem;font-weight:700;'
                               f'padding:.1rem .4rem;border-radius:4px;'
                               f'margin-left:.35rem;">VISA ✓</span>')

                # ── Role category ──
                rc = (job.get("role_category") or "").replace("_", " ").title()

                # ── Skills pills ──
                skills_list = [s.strip() for s in (job.get("skills") or "").split(",") if s.strip()][:6]
                skills_html = "".join(
                    f'<span style="background:{S3};border:1px solid {B2};color:{T2};'
                    f'font-size:.67rem;padding:.15rem .45rem;border-radius:4px;margin:1px 2px 1px 0;">'
                    f'{s}</span>' for s in skills_list)
                skills_block = (f'<div style="margin-top:.55rem;display:flex;flex-wrap:wrap;">'
                                f'{skills_html}</div>') if skills_html else ""

                # ── Posted date ──
                pd_str = str(job.get("posted_date") or job.get("scraped_at") or "")[:10]

                # ── Link button ──
                job_url = job.get("url") or ""
                link_html = ""
                if job_url:
                    link_html = (
                        f'<a href="{job_url}" target="_blank" rel="noopener noreferrer" '
                        f'style="display:inline-flex;align-items:center;gap:.3rem;margin-top:.75rem;'
                        f'background:{CA}14;border:1px solid {CA}33;color:{CA};'
                        f'font-size:.72rem;font-weight:700;padding:.3rem .75rem;'
                        f'border-radius:6px;text-decoration:none;letter-spacing:.03em;">'
                        f'View original posting ↗</a>')
                else:
                    link_html = (
                        f'<span style="display:inline-block;margin-top:.75rem;color:{T3};'
                        f'font-size:.68rem;">URL not captured (re-run pipeline)</span>')

                # ── Startup / equity badges ──
                extra_badges = ""
                if job.get("is_startup"):
                    extra_badges += (f'<span style="background:{PRP}18;border:1px solid {PRP}33;'
                                     f'color:{PRP};font-size:.6rem;font-weight:700;'
                                     f'padding:.1rem .4rem;border-radius:4px;margin-left:.3rem;">'
                                     f'STARTUP</span>')
                if job.get("equity_offered"):
                    extra_badges += (f'<span style="background:{WRN}18;border:1px solid {WRN}33;'
                                     f'color:{WRN};font-size:.6rem;font-weight:700;'
                                     f'padding:.1rem .4rem;border-radius:4px;margin-left:.3rem;">'
                                     f'EQUITY</span>')

                st.markdown(f"""
<div style="background:{S1};border:1px solid {B1};border-radius:14px;
            padding:1.2rem 1.3rem;margin-bottom:.75rem;height:100%;
            transition:border-color 0.15s;">
  <!-- header row: source badge + work model -->
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.55rem;">
    <span style="background:{src_c}18;border:1px solid {src_c}33;color:{src_c};
                 font-size:.62rem;font-weight:800;padding:.12rem .45rem;
                 border-radius:4px;letter-spacing:.06em;text-transform:uppercase;">{src}</span>
    <div style="display:flex;align-items:center;gap:.3rem;">
      {(f'<span style="color:{wm_color};font-size:.62rem;font-weight:700;">{wm_label}</span>') if wm_label else ""}
      <span style="color:{T3};font-size:.65rem;">{pd_str}</span>
    </div>
  </div>
  <!-- title -->
  <div style="color:{T1};font-size:.95rem;font-weight:700;letter-spacing:-.015em;
              line-height:1.3;margin-bottom:.22rem;">{job['title']}{spons_h}{extra_badges}</div>
  <!-- company + location -->
  <div style="color:{T2};font-size:.8rem;margin-bottom:.3rem;">
    <span style="font-weight:600;">{job['company']}</span>
    <span style="color:{T3};margin:0 .3rem;">·</span>
    <span>{job.get('location') or '—'}</span>
  </div>
  <!-- role category -->
  {(f'<div style="color:{T3};font-size:.72rem;margin-bottom:.3rem;">{rc}</div>') if rc else ""}
  <!-- salary -->
  <div style="color:{sal_col};font-size:.85rem;font-weight:700;letter-spacing:-.01em;">{sal_txt}</div>
  <!-- skills -->
  {skills_block}
  <!-- link -->
  {link_html}
</div>""", unsafe_allow_html=True)

    # ── Pagination ────────────────────────────────────────────────────────────
    total_pages = max(1, -(-len(filtered) // PAGE_SIZE))
    if total_pages > 1:
        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
        pp, pc, pn = st.columns([2, 6, 2])
        with pp:
            if st.button("← Prev", disabled=page_n == 0):
                st.session_state["jb_page"] = max(0, page_n - 1); st.rerun()
        with pc:
            st.markdown(
                f'<div style="text-align:center;color:{T2};font-size:.78rem;padding-top:.5rem;">'
                f'Page {page_n + 1} of {total_pages}</div>', unsafe_allow_html=True)
        with pn:
            if st.button("Next →", disabled=page_n >= total_pages - 1):
                st.session_state["jb_page"] = min(total_pages - 1, page_n + 1); st.rerun()
    else:
        st.session_state["jb_page"] = 0


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 7 — PIPELINE STATUS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Pipeline Status":
    hero("⊟", "Pipeline Status",
         "Run history, agent health telemetry, and LLM cost tracking.")

    fresh_v = f"{_fh:.1f}h" if _fh is not None else "—"
    sc2 = OK if (_fh or 999) < 24 else (WRN if (_fh or 999) < 72 else ERR)
    c1, c2, c3 = st.columns(3)
    kpi((c1, c2, c3), [
        ("Platform",       _st.upper(),   "", True),
        ("Data Freshness", fresh_v,       "since last run", False),
        ("Jobs Indexed",   f"{_jobs:,}", "total in DB",    False),
    ])

    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

    tab_r, tab_a = st.tabs(["Run History", "Agent Health"])

    with tab_r:
        section("Recent Pipeline Runs", "Last 10 executions")
        try:
            from marketforge.memory.postgres import get_sync_engine
            from sqlalchemy import text as st_text
            engine = get_sync_engine()
            is_sq  = engine.dialect.name == "sqlite"
            runs_t = "pipeline_runs" if is_sq else "market.pipeline_runs"
            cost_t = "cost_log"      if is_sq else "market.cost_log"

            with engine.connect() as conn:
                runs = conn.execute(st_text(
                    f"SELECT run_id,dag_name,started_at,completed_at,status,"
                    f"jobs_scraped,jobs_new,llm_cost_usd "
                    f"FROM {runs_t} ORDER BY started_at DESC LIMIT 10"
                )).mappings().fetchall()
                total_cost = conn.execute(
                    st_text(f"SELECT COALESCE(SUM(cost_usd),0) FROM {cost_t}")
                ).scalar() or 0.0

            if runs:
                df = pd.DataFrame([dict(r) for r in runs])
                df["status"] = df["status"].apply(
                    lambda s: "✓  success" if s=="success"
                    else ("⟳  running" if s=="running" else "✗  failed"))
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                empty("⊟", "No runs yet", "Pipeline history appears after the first run.")

            st.markdown(
                f'<div style="display:inline-flex;align-items:center;gap:.7rem;'
                f'background:{S2};border:1px solid {B1};border-radius:8px;'
                f'padding:.55rem .95rem;margin-top:.6rem;">'
                f'<span style="color:{T2};font-size:.7rem;font-weight:700;'
                f'text-transform:uppercase;letter-spacing:.07em;">Total LLM spend</span>'
                f'<span style="color:{T1};font-size:.95rem;font-weight:700;'
                f'font-family:\'JetBrains Mono\',monospace;">${total_cost:.4f}</span>'
                f'<span style="color:{T3};font-size:.7rem;">USD · all time</span>'
                f'</div>', unsafe_allow_html=True)

        except Exception as exc:
            st.warning(f"Run history unavailable: {exc}")

    with tab_a:
        section("Agent Health Monitor", "Per-agent state across all 9 departments")
        try:
            from marketforge.memory.postgres import get_sync_engine
            from sqlalchemy import text as st_text
            engine  = get_sync_engine()
            state_t = "agent_state" if engine.dialect.name=="sqlite" else "market.agent_state"
            with engine.connect() as conn:
                agents = conn.execute(st_text(
                    f"SELECT agent_id,department,last_run_at,last_yield,"
                    f"consecutive_failures,run_count "
                    f"FROM {state_t} ORDER BY department,agent_id"
                )).mappings().fetchall()

            if agents:
                df_a = pd.DataFrame([dict(a) for a in agents])
                df_a["Health"] = df_a["consecutive_failures"].apply(
                    lambda f: "● Healthy" if f==0
                    else (f"◉ Warning ({f})" if f<3 else f"○ Failed ({f})"))
                st.dataframe(
                    df_a[["department","agent_id","Health","last_yield","run_count","last_run_at"]],
                    use_container_width=True, hide_index=True)
            else:
                empty("◎", "No agent data yet", "Agents appear after the first pipeline run.")
        except Exception as exc:
            st.warning(f"Agent state unavailable: {exc}")
