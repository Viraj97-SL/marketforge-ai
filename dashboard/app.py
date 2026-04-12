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
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap');
html, body, [class*="css"] {{ font-family: 'Inter', sans-serif !important; }}

/* ── Keyframe animations ─────────────────────────────────────────────────── */
@keyframes mf-pulse {{
  0%,100% {{ opacity:1; transform:scale(1); }}
  50%      {{ opacity:.65; transform:scale(1.35); }}
}}
@keyframes mf-float {{
  0%,100% {{ transform:translateY(0) rotate(0deg); }}
  33%     {{ transform:translateY(-18px) rotate(1deg); }}
  66%     {{ transform:translateY(-8px) rotate(-1deg); }}
}}
@keyframes mf-float2 {{
  0%,100% {{ transform:translateY(0) rotate(0deg); }}
  40%     {{ transform:translateY(-22px) rotate(-2deg); }}
  70%     {{ transform:translateY(-6px) rotate(1deg); }}
}}
@keyframes mf-glow {{
  0%,100% {{ box-shadow:0 0 18px rgba(0,198,167,.12), 0 0 0 1px rgba(0,198,167,.1); }}
  50%     {{ box-shadow:0 0 35px rgba(0,198,167,.28), 0 0 0 1px rgba(0,198,167,.2); }}
}}
@keyframes mf-shimmer {{
  0%   {{ background-position:-800px 0; }}
  100% {{ background-position:800px 0; }}
}}
@keyframes mf-fadeup {{
  from {{ opacity:0; transform:translateY(16px); }}
  to   {{ opacity:1; transform:translateY(0); }}
}}
@keyframes mf-slide-right {{
  from {{ opacity:0; transform:translateX(-14px); }}
  to   {{ opacity:1; transform:translateX(0); }}
}}
@keyframes mf-spin-slow {{
  from {{ transform:rotate(0deg); }}
  to   {{ transform:rotate(360deg); }}
}}
@keyframes mf-border-glow {{
  0%,100% {{ border-color:rgba(0,198,167,.18); }}
  50%     {{ border-color:rgba(0,198,167,.45); }}
}}
@keyframes mf-bar-fill {{
  from {{ width:0%; }}
  to   {{ width:var(--bar-w); }}
}}
@keyframes mf-count {{
  from {{ opacity:0; transform:scale(.85); }}
  to   {{ opacity:1; transform:scale(1); }}
}}

/* ── Chrome ──────────────────────────────────────────────────────────────── */
#MainMenu, footer, header, .stDeployButton {{ display:none !important; }}
.block-container {{ padding:2rem 2.5rem 4rem !important; max-width:1440px !important; }}

/* ── Scrollbar ───────────────────────────────────────────────────────────── */
::-webkit-scrollbar {{ width:6px; height:6px; }}
::-webkit-scrollbar-track {{ background:{BG}; }}
::-webkit-scrollbar-thumb {{ background:{B2}; border-radius:3px; }}
::-webkit-scrollbar-thumb:hover {{ background:{CA}; }}

/* ── App background — animated radial orbs ───────────────────────────────── */
.stApp {{
    background:{BG};
    background-image:
        radial-gradient(ellipse 90% 50% at -8% -12%, rgba(0,198,167,.075) 0%, transparent 58%),
        radial-gradient(ellipse 65% 40% at 108% 4%,  rgba(59,130,246,.06) 0%, transparent 52%),
        radial-gradient(ellipse 40% 30% at 50% 100%, rgba(139,92,246,.04) 0%, transparent 50%);
}}

/* ── Sidebar ─────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {{
    background:linear-gradient(180deg, {S1} 0%, {BG} 100%) !important;
    border-right:1px solid {B1} !important;
}}
[data-testid="stSidebar"] > div:first-child {{ padding:0 !important; }}
section[data-testid="stSidebar"] {{ min-width:230px !important; max-width:230px !important; }}
[data-testid="stSidebar"] .stRadio {{ padding:0 0.5rem !important; }}
[data-testid="stSidebar"] .stRadio > label {{ display:none !important; }}
[data-testid="stSidebar"] .stRadio > div {{ gap:2px !important; }}
[data-testid="stSidebar"] .stRadio label {{
    color:{T2} !important; font-size:0.82rem !important; font-weight:500 !important;
    padding:0.55rem 0.85rem !important; border-radius:9px !important;
    cursor:pointer !important; transition:all .18s ease !important;
    border:1px solid transparent !important; display:flex !important; align-items:center !important;
}}
[data-testid="stSidebar"] .stRadio label:hover {{
    color:{T1} !important; background:rgba(255,255,255,.04) !important;
    transform:translateX(2px) !important;
}}
[data-testid="stSidebar"] .stRadio label[data-checked="true"] {{
    color:{CA} !important; background:rgba(0,198,167,.1) !important;
    border-color:rgba(0,198,167,.22) !important;
    box-shadow:0 0 12px rgba(0,198,167,.08) !important;
}}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {{
    color:{T3} !important; font-size:0.72rem !important; margin:0 !important;
}}
[data-testid="stSidebar"] .stButton button {{
    width:100% !important; background:transparent !important;
    border:1px solid {B2} !important; color:{T2} !important;
    border-radius:7px !important; font-size:0.78rem !important;
    font-weight:500 !important; padding:0.42rem 0.9rem !important;
    transition:all .18s ease !important;
}}
[data-testid="stSidebar"] .stButton button:hover {{
    border-color:{CA} !important; color:{CA} !important;
    background:rgba(0,198,167,.06) !important;
}}

/* ── Divider ─────────────────────────────────────────────────────────────── */
hr {{ border:none !important; border-top:1px solid {B1} !important; margin:1.5rem 0 !important; }}

/* ── Text ────────────────────────────────────────────────────────────────── */
[data-testid="stMarkdownContainer"] p {{ color:{T2}; font-size:.875rem; line-height:1.65; }}
[data-testid="stHeadingWithActionElements"] h1 {{
    color:{T1} !important; font-size:1.6rem !important; font-weight:800 !important; letter-spacing:-.03em !important;
}}
[data-testid="stHeadingWithActionElements"] h2 {{
    color:{T1} !important; font-size:1.1rem !important; font-weight:700 !important; letter-spacing:-.02em !important;
}}
[data-testid="stHeadingWithActionElements"] h3 {{
    color:{T1} !important; font-size:.95rem !important; font-weight:600 !important;
}}
[data-testid="stCaptionContainer"] p {{ color:{T2} !important; font-size:.8rem !important; }}

/* ── Tabs ────────────────────────────────────────────────────────────────── */
button[data-baseweb="tab"] {{
    background:transparent !important; border:none !important;
    color:{T2} !important; font-size:.82rem !important; font-weight:500 !important;
    padding:.6rem 1.1rem !important;
    border-bottom:2px solid transparent !important; border-radius:0 !important;
    transition:color .15s, border-color .15s !important;
}}
button[data-baseweb="tab"]:hover {{ color:{T1} !important; }}
button[data-baseweb="tab"][aria-selected="true"] {{
    color:{CA} !important; border-bottom-color:{CA} !important;
}}
[data-testid="stTabsContent"] {{ padding-top:1.25rem !important; }}

/* ── Selectbox ───────────────────────────────────────────────────────────── */
.stSelectbox > div > div {{
    background:{S2} !important; border:1px solid {B1} !important;
    border-radius:8px !important; color:{T1} !important; font-size:.84rem !important;
    transition:border-color .15s !important;
}}
.stSelectbox > div > div:focus-within {{
    border-color:{CA} !important; box-shadow:0 0 0 3px rgba(0,198,167,.12) !important;
}}
.stSelectbox label {{
    color:{T2} !important; font-size:.72rem !important; font-weight:600 !important;
    text-transform:uppercase !important; letter-spacing:.07em !important;
}}

/* ── Text inputs ─────────────────────────────────────────────────────────── */
.stTextInput input, .stTextArea textarea {{
    background:{S2} !important; border:1px solid {B1} !important;
    border-radius:8px !important; color:{T1} !important;
    font-family:Inter,sans-serif !important; font-size:.875rem !important;
    transition:border-color .15s, box-shadow .15s !important;
}}
.stTextInput input:focus, .stTextArea textarea:focus {{
    border-color:{CA} !important; box-shadow:0 0 0 3px rgba(0,198,167,.12) !important; outline:none !important;
}}
.stTextInput label, .stTextArea label {{
    color:{T2} !important; font-size:.72rem !important; font-weight:600 !important;
    text-transform:uppercase !important; letter-spacing:.07em !important;
}}

/* ── Form ────────────────────────────────────────────────────────────────── */
[data-testid="stForm"] {{
    background:{S1} !important; border:1px solid {B1} !important;
    border-radius:16px !important; padding:1.75rem 2rem !important;
    box-shadow:0 4px 24px rgba(0,0,0,.25) !important;
    animation:mf-fadeup .4s ease both !important;
}}

/* ── Buttons ─────────────────────────────────────────────────────────────── */
.stButton > button[kind="primary"] {{
    background:linear-gradient(135deg,{CA} 0%,{CB} 100%) !important;
    border:none !important; color:#021A14 !important;
    font-weight:700 !important; font-size:.875rem !important;
    border-radius:9px !important; padding:.58rem 1.75rem !important;
    transition:opacity .15s, transform .15s, box-shadow .15s !important;
    box-shadow:0 4px 14px rgba(0,198,167,.25) !important;
}}
.stButton > button[kind="primary"]:hover {{
    opacity:.9 !important; transform:translateY(-1px) !important;
    box-shadow:0 6px 20px rgba(0,198,167,.35) !important;
}}
.stButton > button[kind="secondary"] {{
    background:{S2} !important; border:1px solid {B2} !important; color:{T2} !important;
    border-radius:9px !important; font-size:.82rem !important; font-weight:500 !important;
    transition:all .15s !important;
}}
.stButton > button[kind="secondary"]:hover {{
    border-color:{CA} !important; color:{CA} !important; background:rgba(0,198,167,.06) !important;
}}

/* ── Role chip buttons (job board) ───────────────────────────────────────── */
.mf-chip-active > button {{
    background:linear-gradient(135deg,{CA}22,{CB}22) !important;
    border:1px solid {CA}55 !important; color:{CA} !important;
    font-size:.78rem !important; font-weight:700 !important;
    border-radius:20px !important; padding:.28rem .85rem !important;
    box-shadow:0 0 12px {CA}22 !important;
}}
.mf-chip-inactive > button {{
    background:{S2} !important; border:1px solid {B1} !important; color:{T2} !important;
    font-size:.78rem !important; font-weight:500 !important;
    border-radius:20px !important; padding:.28rem .85rem !important;
    transition:all .15s !important;
}}
.mf-chip-inactive > button:hover {{
    border-color:{CA}44 !important; color:{T1} !important; background:{S3} !important;
}}

/* ── Expander ────────────────────────────────────────────────────────────── */
.streamlit-expanderHeader {{
    background:{S2} !important; border:1px solid {B1} !important;
    border-radius:10px !important; color:{T1} !important;
    font-size:.85rem !important; font-weight:500 !important;
    transition:border-color .15s !important;
}}
.streamlit-expanderHeader:hover {{ border-color:{CA}44 !important; }}
.streamlit-expanderContent {{
    background:{S1} !important; border:1px solid {B1} !important;
    border-top:none !important; border-radius:0 0 10px 10px !important; padding:1rem !important;
}}

/* ── Dataframe ───────────────────────────────────────────────────────────── */
[data-testid="stDataFrame"] {{
    border:1px solid {B1} !important; border-radius:12px !important; overflow:hidden !important;
}}

/* ── Native metrics ──────────────────────────────────────────────────────── */
[data-testid="stMetric"] {{
    background:{S1} !important; border:1px solid {B1} !important;
    border-radius:12px !important; padding:1rem 1.25rem !important;
    transition:all .2s ease !important;
}}
[data-testid="stMetric"]:hover {{
    border-color:rgba(0,198,167,.3) !important;
    box-shadow:0 4px 16px rgba(0,198,167,.08) !important;
    transform:translateY(-1px) !important;
}}
[data-testid="metric-container"] label {{
    color:{T2} !important; font-size:.68rem !important; font-weight:700 !important;
    text-transform:uppercase !important; letter-spacing:.08em !important;
}}
[data-testid="stMetricValue"] {{
    color:{T1} !important; font-size:1.5rem !important;
    font-weight:700 !important; letter-spacing:-.025em !important;
}}

/* ── Alert ───────────────────────────────────────────────────────────────── */
[data-testid="stAlert"] {{
    background:{S2} !important; border-radius:10px !important; font-size:.84rem !important;
}}

/* ── Checkbox ────────────────────────────────────────────────────────────── */
.stCheckbox label {{ color:{T2} !important; font-size:.84rem !important; }}

/* ── Spinner ─────────────────────────────────────────────────────────────── */
.stSpinner > div {{ border-top-color:{CA} !important; }}

/* ── Plotly ──────────────────────────────────────────────────────────────── */
.stPlotlyChart {{ background:transparent !important; border:none !important; padding:0 !important; }}

/* ── Job card hover ──────────────────────────────────────────────────────── */
.mf-job-card {{
    transition:transform .2s ease, border-color .2s ease, box-shadow .2s ease !important;
}}
.mf-job-card:hover {{
    transform:translateY(-3px) !important;
    border-color:rgba(0,198,167,.32) !important;
    box-shadow:0 8px 32px rgba(0,0,0,.35), 0 0 0 1px rgba(0,198,167,.12) !important;
}}

/* ── KPI card hover ──────────────────────────────────────────────────────── */
.mf-kpi:hover {{
    transform:translateY(-2px) !important;
    box-shadow:0 6px 24px rgba(0,0,0,.3), 0 0 0 1px rgba(0,198,167,.15) !important;
}}

/* ── Page-in animation for main content ──────────────────────────────────── */
.main .block-container > div > div {{ animation:mf-fadeup .35s ease both; }}

/* ── Gradient text utility ───────────────────────────────────────────────── */
.mf-gradient-text {{
    background:linear-gradient(135deg,{CA},{CB});
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
    background-clip:text;
}}

/* ── Glowing accent dot ──────────────────────────────────────────────────── */
.mf-dot-pulse {{
    animation:mf-pulse 2s ease-in-out infinite !important;
}}

/* ── Floating orb ────────────────────────────────────────────────────────── */
.mf-orb-1 {{ animation:mf-float 8s ease-in-out infinite !important; }}
.mf-orb-2 {{ animation:mf-float2 11s ease-in-out infinite !important; }}

/* ── Skill bar animation ─────────────────────────────────────────────────── */
.mf-bar {{
    animation:mf-bar-fill .9s cubic-bezier(.4,0,.2,1) both !important;
}}

/* ── Card entrance ───────────────────────────────────────────────────────── */
.mf-card-enter {{
    animation:mf-fadeup .4s ease both !important;
}}
</style>
""", unsafe_allow_html=True)


# ── HTML-safe component library ───────────────────────────────────────────────
# Rule: NEVER use <h1-6> or <p> tags inside st.markdown — use <div> with inline
# font-size/weight instead. Streamlit hoists heading/p elements out of containers.

def _dot(c):
    return (f'<span class="mf-dot-pulse" style="display:inline-block;width:7px;height:7px;'
            f'border-radius:50%;background:{c};box-shadow:0 0 8px {c}99;flex-shrink:0;"></span>')


def hero(icon, title, desc, badge="", badge_c=OK):
    """Page hero with animated floating orbs."""
    bdg = ""
    if badge:
        bdg = (f'<span style="display:inline-flex;align-items:center;gap:5px;'
               f'background:{badge_c}18;border:1px solid {badge_c}33;'
               f'color:{badge_c};font-size:.68rem;font-weight:700;letter-spacing:.06em;'
               f'padding:.18rem .6rem;border-radius:20px;margin-left:.65rem;">'
               f'{_dot(badge_c)}&nbsp;{badge}</span>')
    st.markdown(f"""
<div style="position:relative;overflow:hidden;padding:2rem 2.2rem 1.8rem;margin-bottom:1.5rem;
            background:linear-gradient(135deg,{S1} 0%,{S2} 100%);
            border:1px solid {B1};border-radius:20px;
            box-shadow:0 4px 32px rgba(0,0,0,.3);">
  <!-- floating orbs -->
  <div class="mf-orb-1" style="position:absolute;top:-60px;right:-40px;width:220px;height:220px;
       border-radius:50%;background:radial-gradient(circle,rgba(0,198,167,.12) 0%,transparent 70%);
       pointer-events:none;"></div>
  <div class="mf-orb-2" style="position:absolute;bottom:-80px;left:30%;width:280px;height:280px;
       border-radius:50%;background:radial-gradient(circle,rgba(59,130,246,.08) 0%,transparent 70%);
       pointer-events:none;"></div>
  <div class="mf-orb-1" style="position:absolute;top:10px;left:-30px;width:140px;height:140px;
       border-radius:50%;background:radial-gradient(circle,rgba(139,92,246,.07) 0%,transparent 70%);
       pointer-events:none;animation-delay:-3s;"></div>
  <!-- content -->
  <div style="position:relative;z-index:1;">
    <div style="display:flex;align-items:center;flex-wrap:wrap;gap:.5rem;margin-bottom:.55rem;">
      <span style="font-size:1.5rem;line-height:1;filter:drop-shadow(0 0 8px {CA}66);">{icon}</span>
      <span style="font-size:1.75rem;font-weight:900;color:{T1};letter-spacing:-.04em;
                   line-height:1.15;background:linear-gradient(135deg,{T1} 40%,{CA} 100%);
                   -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                   background-clip:text;">{title}</span>{bdg}
    </div>
    <div style="color:{T2};font-size:.9rem;line-height:1.65;max-width:640px;
                border-left:2px solid {CA}55;padding-left:.85rem;">{desc}</div>
  </div>
</div>""", unsafe_allow_html=True)


def kpi(cols_tuple, items):
    """items: list of (label, value, note, accent_top)"""
    for col, (label, value, note, accent) in zip(cols_tuple, items):
        accent_style = (f"border-top:2px solid {CA};box-shadow:0 0 16px rgba(0,198,167,.07);"
                        if accent else f"border-top:1px solid {B1};")
        note_h = (f'<div style="color:{T3};font-size:.72rem;margin-top:.45rem;line-height:1.4;">'
                  f'{note}</div>') if note else ""
        col.markdown(f"""
<div class="mf-kpi" style="background:linear-gradient(145deg,{S1},{S2});border:1px solid {B1};
            {accent_style}border-radius:14px;padding:1.25rem 1.4rem;height:100%;
            transition:all .2s ease;cursor:default;animation:mf-fadeup .4s ease both;">
  <div style="color:{T3};font-size:.63rem;font-weight:700;text-transform:uppercase;
              letter-spacing:.1em;margin-bottom:.55rem;display:flex;align-items:center;gap:.35rem;">
    {'<span style="width:4px;height:4px;border-radius:50%;background:'+CA+';display:inline-block;"></span>' if accent else ''}
    {label}
  </div>
  <div style="color:{T1};font-size:1.7rem;font-weight:900;letter-spacing:-.035em;
              line-height:1;animation:mf-count .5s ease both;">{value}</div>
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
    sub_h = (f'<div style="color:{T2};font-size:.78rem;margin-top:.2rem;line-height:1.5;">'
             f'{sub}</div>') if sub else ""
    st.markdown(f"""
<div style="margin:1.8rem 0 1rem;display:flex;align-items:flex-start;gap:.65rem;">
  <div style="width:3px;height:100%;min-height:1.4rem;border-radius:2px;
              background:linear-gradient({CA},{CB});flex-shrink:0;margin-top:.12rem;
              align-self:stretch;"></div>
  <div>
    <span style="color:{T1};font-size:.94rem;font-weight:700;letter-spacing:-.018em;">{title}</span>
    {sub_h}
  </div>
</div>""", unsafe_allow_html=True)


def pills(items, arrow="", color=T2):
    html = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:3px;'
        f'background:{S3};border:1px solid {B2};color:{T1};font-size:.77rem;'
        f'font-weight:500;padding:.26rem .62rem;border-radius:6px;margin:2px 3px 2px 0;'
        f'transition:border-color .15s;">'
        f'<span style="color:{color};font-size:.65rem;">{arrow}</span>{s}</span>'
        for s in items)
    st.markdown(f'<div style="display:flex;flex-wrap:wrap;padding-top:.25rem;">'
                f'{html}</div>', unsafe_allow_html=True)


def row_item(text, indicator="", ind_color=OK):
    ind = (f'<span style="color:{ind_color};font-size:.72rem;font-weight:700;">'
           f'{indicator}</span>') if indicator else ""
    st.markdown(f"""
<div style="display:flex;align-items:center;justify-content:space-between;
            padding:.5rem .85rem;border-radius:9px;margin-bottom:3px;
            background:{S2};border:1px solid {B1};
            transition:border-color .15s,background .15s;">
  <span style="color:{T1};font-size:.83rem;font-weight:500;">{text}</span>
  {ind}
</div>""", unsafe_allow_html=True)


def insight(title, body, color=CA):
    st.markdown(f"""
<div style="background:linear-gradient(135deg,{S2},{S1});border:1px solid {B1};
            border-left:3px solid {color};border-radius:0 12px 12px 0;
            padding:1rem 1.1rem;margin-bottom:.55rem;
            box-shadow:0 2px 12px rgba(0,0,0,.2);">
  <div style="display:flex;align-items:center;gap:.45rem;margin-bottom:.3rem;">
    <span style="color:{color};font-size:.7rem;">◆</span>
    <span style="color:{T1};font-size:.84rem;font-weight:600;">{title}</span>
  </div>
  <div style="color:{T2};font-size:.79rem;line-height:1.6;padding-left:1.1rem;">{body}</div>
</div>""", unsafe_allow_html=True)


def empty(icon, title, body):
    st.markdown(f"""
<div style="text-align:center;padding:3.5rem 2rem;
            background:radial-gradient(ellipse at center,{S2} 0%,{S1} 100%);
            border:1px dashed {B2};border-radius:18px;margin:.5rem 0;
            animation:mf-fadeup .4s ease both;">
  <div style="font-size:2rem;margin-bottom:.75rem;
              filter:drop-shadow(0 0 10px rgba(0,198,167,.3));">{icon}</div>
  <div style="color:{T1};font-size:.95rem;font-weight:700;margin-bottom:.4rem;">{title}</div>
  <div style="color:{T2};font-size:.83rem;max-width:340px;margin:0 auto;line-height:1.65;">{body}</div>
</div>""", unsafe_allow_html=True)


def action_step(n, text):
    st.markdown(f"""
<div style="display:flex;gap:1rem;align-items:flex-start;
            background:linear-gradient(135deg,{S2},{S1});
            border:1px solid {B1};border-radius:12px;
            padding:.9rem 1.1rem;margin-bottom:.5rem;
            transition:border-color .15s,transform .15s;animation:mf-slide-right .35s ease both;
            animation-delay:{(n-1)*0.08}s;">
  <div style="flex-shrink:0;width:26px;height:26px;border-radius:50%;
              background:linear-gradient(135deg,{CA}22,{CB}22);
              border:1px solid {CA}44;display:flex;align-items:center;justify-content:center;">
    <span style="color:{CA};font-size:.68rem;font-weight:800;font-family:'JetBrains Mono',monospace;">
      {n:02d}
    </span>
  </div>
  <span style="color:{T1};font-size:.875rem;line-height:1.65;">{text}</span>
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
<div style="padding:1.6rem 1.1rem 1.25rem;border-bottom:1px solid {B1};margin-bottom:.9rem;
            background:linear-gradient(180deg,rgba(0,198,167,.05) 0%,transparent 100%);">
  <div style="display:flex;align-items:center;gap:.65rem;">
    <div style="position:relative;width:36px;height:36px;flex-shrink:0;">
      <div style="position:absolute;inset:0;border-radius:10px;
                  background:linear-gradient(135deg,{CA},{CB});
                  box-shadow:0 4px 14px rgba(0,198,167,.4);"></div>
      <div style="position:relative;z-index:1;width:100%;height:100%;border-radius:10px;
                  display:flex;align-items:center;justify-content:center;
                  font-size:.95rem;font-weight:900;color:#021A14;
                  font-family:'JetBrains Mono',monospace;">M</div>
    </div>
    <div>
      <div style="color:{T1};font-size:.94rem;font-weight:800;letter-spacing:-.025em;
                  line-height:1.2;">MarketForge AI</div>
      <div style="color:{CA};font-size:.6rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:.1em;opacity:.8;">UK AI Intelligence</div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

    # Status card
    _pulse_anim = "animation:mf-pulse 2s ease-in-out infinite;" if _st == "healthy" else ""
    st.markdown(f"""
<div style="margin:0 .6rem 1rem;padding:.85rem 1rem;
            background:linear-gradient(135deg,{S2},{S3});
            border:1px solid {B1};border-radius:12px;
            box-shadow:0 2px 12px rgba(0,0,0,.2);">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.6rem;">
    <span style="color:{T3};font-size:.6rem;font-weight:700;text-transform:uppercase;
                 letter-spacing:.1em;">System Status</span>
    <span style="display:flex;align-items:center;gap:.35rem;color:{_sc};font-size:.72rem;font-weight:700;">
      <span style="width:7px;height:7px;border-radius:50%;background:{_sc};
                   display:inline-block;box-shadow:0 0 6px {_sc}99;{_pulse_anim}"></span>
      {_st.upper()}
    </span>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:.35rem;">
    <div style="background:{S1};border-radius:8px;padding:.45rem .6rem;border:1px solid {B1};">
      <div style="color:{T3};font-size:.56rem;text-transform:uppercase;letter-spacing:.07em;margin-bottom:2px;">Freshness</div>
      <div style="color:{_fc};font-size:.8rem;font-weight:700;">{_fs}</div>
    </div>
    <div style="background:{S1};border-radius:8px;padding:.45rem .6rem;border:1px solid {B1};">
      <div style="color:{T3};font-size:.56rem;text-transform:uppercase;letter-spacing:.07em;margin-bottom:2px;">Jobs</div>
      <div style="color:{T1};font-size:.8rem;font-weight:700;">{_jobs:,}</div>
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

    # ── CV Upload (role-aware ATS scoring) ───────────────────────────────────
    section("CV Analyser", "Upload your CV for ATS scoring and role-specific gap analysis")

    _ROLE_OPTS = [
        "ML Engineer", "Data Scientist", "AI Engineer", "MLOps Engineer",
        "NLP Engineer", "Computer Vision Engineer", "Research Scientist",
        "Applied Scientist", "Data Engineer",
    ]
    _ROLE_SLUG = {
        "ML Engineer": "ml_engineer", "Data Scientist": "data_scientist",
        "AI Engineer": "ai_engineer", "MLOps Engineer": "mlops_engineer",
        "NLP Engineer": "nlp_engineer", "Computer Vision Engineer": "computer_vision_engineer",
        "Research Scientist": "research_scientist", "Applied Scientist": "applied_scientist",
        "Data Engineer": "data_engineer",
    }

    with st.form("cv_form"):
        cv_col, cfg_col = st.columns([5, 4])
        with cv_col:
            cv_file = st.file_uploader(
                "Upload CV (PDF or DOCX, max 5 MB)",
                type=["pdf", "docx"],
                help="Your file is processed in-memory and never stored (GDPR compliant).",
            )
        with cfg_col:
            cv_role     = st.selectbox("Target role", _ROLE_OPTS, key="cv_role")
            cv_consent  = st.checkbox(
                "I consent to in-memory processing of my CV for analysis purposes",
                help="Required for GDPR compliance. No data is stored after analysis.",
            )
        cv_submitted = st.form_submit_button("Analyse CV →", type="primary")

    if cv_submitted:
        if not cv_file:
            st.warning("Please upload a CV file.")
        elif not cv_consent:
            st.warning("Please tick the consent checkbox to proceed.")
        else:
            with st.spinner("Scanning and scoring your CV against live market data…"):
                try:
                    resp = requests.post(
                        f"{API_BASE}/api/v1/career/cv-analyse",
                        files={"cv_file": (cv_file.name, cv_file.getvalue(), cv_file.type)},
                        params={"target_role": _ROLE_SLUG[cv_role], "consent": "true"},
                        timeout=120,
                    )
                    if resp.status_code == 429:
                        st.warning("Rate limit reached (3 analyses/hour). Please wait."); st.stop()
                    if resp.status_code == 403:
                        st.error(resp.json().get("detail", "Consent required.")); st.stop()
                    if resp.status_code == 422:
                        st.error(f"Rejected: {resp.json().get('detail')}"); st.stop()
                    resp.raise_for_status()
                    cv_report = resp.json()
                except requests.exceptions.ConnectionError:
                    st.error("Cannot reach the API. Ensure `uvicorn api.main:app` is running.")
                    st.stop()
                except Exception as e:
                    st.error(f"CV analysis failed: {e}"); st.stop()

            # ── Results ───────────────────────────────────────────────────────
            ats      = cv_report.get("ats_score", {})
            total    = ats.get("total", 0)
            grade    = ats.get("grade", "—")
            kw_pct   = ats.get("keyword_match_pct", 0)
            mkt_pct  = cv_report.get("market_match_pct", 0)
            grade_c  = OK if total >= 70 else (WRN if total >= 50 else ERR)

            st.divider()
            c1, c2, c3, c4 = st.columns(4)
            kpi((c1, c2, c3, c4), [
                ("ATS Score",       f"{total:.0f}/100",  f"Grade {grade}",          True),
                ("Keyword Match",   f"{kw_pct:.0f}%",    f"vs {cv_role} roles",     False),
                ("Market Match",    f"{mkt_pct:.0f}%",   "SBERT similarity",        False),
                ("Skills Found",    str(len(ats.get("skills_found", []))), "on CV", False),
            ])

            st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

            ct1, ct2, ct3, ct4 = st.tabs(["ATS Breakdown", "Issues & Tips", "Gap Plan", "Missing Skills"])

            with ct1:
                section("Score Breakdown")
                bd = ats.get("breakdown", {})
                if bd:
                    df_bd = pd.DataFrame([
                        {"Dimension": k.replace("_", " ").title(), "Score": f"{v:.0f}/100"}
                        for k, v in bd.items()
                    ])
                    st.dataframe(df_bd, use_container_width=True, hide_index=True)

            with ct2:
                section("ATS Issues", "Fix these to improve your score")
                for issue in ats.get("issues", []):
                    st.markdown(f"- {issue}")

            with ct3:
                section("Career Gap Plan")
                narrative = cv_report.get("narrative_summary", "").replace("\n", "<br>")
                st.markdown(
                    f'<div style="background:{S1};border:1px solid {B1};border-radius:12px;'
                    f'padding:1.4rem 1.5rem;color:{T2};font-size:.875rem;line-height:1.8;">'
                    f'{narrative}</div>', unsafe_allow_html=True)
                st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
                for i, step in enumerate(cv_report.get("action_plan_90d", []), 1):
                    action_step(i, step)

            with ct4:
                section("Missing Skills", f"Top skills demanded for {cv_role} roles you don't yet have")
                missing = cv_report.get("skills_missing", [])
                if missing:
                    for sk in missing:
                        st.markdown(f"- **{sk}**")
                else:
                    st.success("Great coverage — no critical skill gaps detected.")

    st.divider()
    section("Profile Analyser", "Or enter your skills manually for a quick assessment")

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

        is_sqlite = engine.dialect.name == "sqlite"
        if is_sqlite:
            skills_agg = f"(SELECT GROUP_CONCAT(skill, ', ') FROM (SELECT skill FROM {sk_tbl} WHERE job_id = j.job_id ORDER BY confidence DESC LIMIT 8))"
        else:
            skills_agg = f"(SELECT STRING_AGG(skill, ', ' ORDER BY confidence DESC) FROM (SELECT skill, confidence FROM {sk_tbl} WHERE job_id = j.job_id ORDER BY confidence DESC LIMIT 8) _s)"

        with engine.connect() as conn:
            total_indexed = conn.execute(st_text(f"SELECT COUNT(*) FROM {tbl}")).scalar() or 0

            rows = conn.execute(st_text(f"""
                SELECT j.job_id, j.title, j.company, j.location, j.salary_min, j.salary_max,
                       j.work_model, j.experience_level, j.role_category, j.source,
                       j.offers_sponsorship, j.posted_date, j.scraped_at, j.url,
                       j.is_startup, j.company_stage, j.equity_offered,
                       COALESCE({skills_agg}, '') AS skills
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

    # ── Role chip quick-filters ───────────────────────────────────────────────
    # Chips set session_state["jb_role"] and reset the page to 0
    ROLE_CHIPS = [
        ("All",        "All roles"),
        ("ML Eng",     "ml_engineer"),
        ("Data Sci",   "data_scientist"),
        ("AI Eng",     "ai_engineer"),
        ("MLOps",      "mlops_engineer"),
        ("NLP",        "nlp_engineer"),
        ("CV Eng",     "computer_vision_engineer"),
        ("Research",   "research_scientist"),
        ("Data Eng",   "data_engineer"),
    ]
    # Only show chips for roles that actually have data
    available_roles = {j["role_category"] for j in jobs_data if j.get("role_category")}
    visible_chips   = [c for c in ROLE_CHIPS if c[1] == "All roles" or c[1] in available_roles]

    if "jb_role" not in st.session_state:
        st.session_state["jb_role"] = "All roles"

    st.markdown('<div style="display:flex;flex-wrap:wrap;gap:.4rem;margin-bottom:1rem;">',
                unsafe_allow_html=True)
    chip_cols = st.columns(len(visible_chips))
    for ci, (label, value) in enumerate(visible_chips):
        is_active = st.session_state["jb_role"] == value
        css_class = "mf-chip-active" if is_active else "mf-chip-inactive"
        with chip_cols[ci]:
            st.markdown(f'<div class="{css_class}">', unsafe_allow_html=True)
            if st.button(label, key=f"jb_chip_{ci}"):
                st.session_state["jb_role"] = value
                st.session_state["jb_page"] = 0
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Filter bar ────────────────────────────────────────────────────────────
    fa, fb, fc, fd = st.columns([4, 2, 2, 2])
    with fa:
        search_q = st.text_input("Search", placeholder="e.g. LLM, PyTorch, NLP, remote…",
                                 key="jb_search")
    with fb:
        wm_opts = ["All modes"] + sorted({
            j["work_model"] for j in jobs_data
            if j.get("work_model") and j["work_model"] != "unknown"
        })
        wm_f = st.selectbox("Work model", wm_opts, key="jb_wm")
    with fc:
        exp_opts = ["All levels"] + sorted({
            j["experience_level"] for j in jobs_data if j.get("experience_level")
        })
        exp_f = st.selectbox("Level", exp_opts, key="jb_exp")
    with fd:
        src_opts = ["All sources"] + sorted({j["source"] for j in jobs_data if j.get("source")})
        src_f = st.selectbox("Source", src_opts, key="jb_src")

    sp_col, _ = st.columns([3, 5])
    with sp_col:
        sponsorship_only = st.checkbox("Visa sponsorship only", key="jb_spons")

    # ── Detect filter changes → reset page ───────────────────────────────────
    _filter_sig = (search_q, st.session_state["jb_role"], wm_f, exp_f, src_f, sponsorship_only)
    if st.session_state.get("_jb_last_filter") != _filter_sig:
        st.session_state["_jb_last_filter"] = _filter_sig
        st.session_state["jb_page"] = 0

    role_f = st.session_state["jb_role"]

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

    # Active role label for summary
    active_chip_label = next((lbl for lbl, val in ROLE_CHIPS if val == role_f), role_f)

    _role_badge = (
        f'<span style="background:{CA}18;border:1px solid {CA}33;color:{CA};'
        f'font-size:.68rem;font-weight:700;padding:.1rem .45rem;border-radius:20px;">'
        f'{active_chip_label}</span>'
    ) if role_f != "All roles" else ""
    st.markdown(
        f'<div style="display:flex;gap:1rem;align-items:center;margin:.4rem 0 1rem;">'
        f'<span style="color:{T1};font-size:.87rem;font-weight:700;">{len(filtered):,} roles</span>'
        f'<span style="color:{T3};font-size:.78rem;">of {total_indexed:,} indexed</span>'
        f'{_role_badge}</div>',
        unsafe_allow_html=True)

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

                # Pre-build sub-blocks as single-line strings (no HTML comments, no nested div hoisting)
                wm_span = (f'<span style="color:{wm_color};font-size:.62rem;font-weight:700;'
                           f'margin-right:.3rem;">{wm_label}</span>') if wm_label else ""
                header_row = (
                    f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.55rem;">'
                    f'<span style="background:{src_c}18;border:1px solid {src_c}33;color:{src_c};font-size:.62rem;'
                    f'font-weight:800;padding:.12rem .45rem;border-radius:4px;letter-spacing:.06em;'
                    f'text-transform:uppercase;">{src}</span>'
                    f'<span style="display:inline-flex;align-items:center;">{wm_span}'
                    f'<span style="color:{T3};font-size:.65rem;">{pd_str}</span></span>'
                    f'</div>'
                )
                title_row = (
                    f'<div style="color:{T1};font-size:.95rem;font-weight:700;letter-spacing:-.015em;'
                    f'line-height:1.3;margin-bottom:.22rem;">{job["title"]}{spons_h}{extra_badges}</div>'
                )
                company_row = (
                    f'<div style="color:{T2};font-size:.8rem;margin-bottom:.3rem;">'
                    f'<span style="font-weight:600;">{job["company"]}</span>'
                    f'<span style="color:{T3};margin:0 .3rem;">·</span>'
                    f'<span>{job.get("location") or "—"}</span></div>'
                )
                rc_row = (f'<div style="color:{T3};font-size:.72rem;margin-bottom:.3rem;">{rc}</div>') if rc else ""
                salary_row = (
                    f'<div style="color:{sal_col};font-size:.85rem;font-weight:700;'
                    f'letter-spacing:-.01em;margin-top:.1rem;">{sal_txt}</div>'
                )

                # Company initial avatar
                co_init = (job.get("company") or "?")[0].upper()
                co_color = SOURCE_COLORS.get(src, CA)
                avatar_html = (
                    f'<div style="width:36px;height:36px;border-radius:10px;flex-shrink:0;'
                    f'background:linear-gradient(135deg,{co_color}22,{co_color}44);'
                    f'border:1px solid {co_color}44;display:flex;align-items:center;'
                    f'justify-content:center;font-size:.9rem;font-weight:800;color:{co_color};'
                    f'font-family:\'JetBrains Mono\',monospace;">{co_init}</div>'
                )

                st.markdown(
                    f'<div class="mf-job-card" style="background:linear-gradient(145deg,{S1},{S2});'
                    f'border:1px solid {B1};border-radius:16px;'
                    f'padding:1.25rem 1.35rem;margin-bottom:.8rem;cursor:default;">'
                    f'{header_row}'
                    f'<div style="display:flex;gap:.75rem;align-items:flex-start;">'
                    f'{avatar_html}'
                    f'<div style="flex:1;min-width:0;">'
                    f'{title_row}{company_row}{rc_row}'
                    f'</div></div>'
                    f'{salary_row}{skills_block}{link_html}</div>',
                    unsafe_allow_html=True)

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
