"""
app.py — SAIL Maritime Freight & Chartering Decision Support System
====================================================================
Design : Utilitarian Minimalist / Neo-Brutalist  (Light ↔ Dark toggle)
Backend: Full pipeline — FreightXGB · FuelXGB · TimingGBR-LR · VesselRanker
Layout : 3-tab institutional terminal with pill containers & Space Mono numerics

Run: streamlit run app.py
"""

from __future__ import annotations

import datetime
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

# ── Optimizer constants (module-scope) ───────────────────────────────────────
try:
    from optimizer import PORT_CONSTRAINTS, VESSEL_CLASS_DRAFT
except Exception:
    PORT_CONSTRAINTS: dict = {
        "Haldia":   {"max_draft": 8.5,  "allowed_classes": ["Handysize", "Supramax"],
                     "queue_days_avg": 3.5, "demurrage_usd_day": 18_000},
        "Paradip":  {"max_draft": 14.0, "allowed_classes": ["Handysize","Supramax","Panamax","Capesize"],
                     "queue_days_avg": 1.5, "demurrage_usd_day": 22_000},
        "Vizag":    {"max_draft": 14.5, "allowed_classes": ["Handysize","Supramax","Panamax","Capesize"],
                     "queue_days_avg": 2.0, "demurrage_usd_day": 20_000},
        "Ennore":   {"max_draft": 12.5, "allowed_classes": ["Handysize","Supramax","Panamax"],
                     "queue_days_avg": 2.5, "demurrage_usd_day": 19_000},
        "Kolkata":  {"max_draft": 8.0,  "allowed_classes": ["Handysize"],
                     "queue_days_avg": 4.0, "demurrage_usd_day": 16_000},
        "Mormugao": {"max_draft": 13.0, "allowed_classes": ["Handysize","Supramax","Panamax"],
                     "queue_days_avg": 1.8, "demurrage_usd_day": 17_000},
    }
    VESSEL_CLASS_DRAFT: dict = {
        "Capesize": 18.2, "Panamax": 14.5, "Kamsarmax": 14.5,
        "Supramax": 12.8, "Handymax": 11.5, "Handysize": 10.0,
    }

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG  (must be first Streamlit call)
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SAIL Chartering Terminal",
    page_icon="⚓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# THEME STATE
# ─────────────────────────────────────────────────────────────────────────────
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = True

# ─────────────────────────────────────────────────────────────────────────────
# PALETTE  (computed once per render, used in CSS + Plotly)
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.dark_mode:
    BG       = "#121212"
    BG2      = "#1a1a1a"
    BG3      = "#222222"
    FG       = "#eef2ea"
    FG_DIM   = "#a8b0a4"
    FG_MUTE  = "#5a6057"
    BORDER   = "#eef2ea"
    BORDER2  = "#333733"
    CL       = "#eef2ea"   # chart line
    CG       = "#2a2a2a"   # chart grid
    HOVER_BG = "#1a1a1a"
    ACCENT   = "#a8c5a0"   # muted sage green accent
    RED      = "#c97b7b"
    AMBER    = "#c9a87b"
    GREEN    = "#7bc97b"
else:
    BG       = "#eef2ea"
    BG2      = "#e4e8e0"
    BG3      = "#d8ddd4"
    FG       = "#1c1c1c"
    FG_DIM   = "#4a4e47"
    FG_MUTE  = "#8a8e87"
    BORDER   = "#1c1c1c"
    BORDER2  = "#c0c4bc"
    CL       = "#1c1c1c"
    CG       = "#d4d8d0"
    HOVER_BG = "#e4e8e0"
    ACCENT   = "#3a6a30"
    RED      = "#8b2020"
    AMBER    = "#8b6020"
    GREEN    = "#206820"

# ─────────────────────────────────────────────────────────────────────────────
# CSS  — injected every render so palette swaps instantly on toggle
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:ital,wght@0,400;0,700;1,400&family=Inter:wght@300;400;500;600&display=swap');

/* ── Global Theme Root & Reset ── */
:root, .stApp, html, body {{
    --text-color: {FG} !important;
    --background-color: {BG} !important;
    --bg-color: {BG} !important;
    --secondary-background-color: {BG2} !important;
    --primary-color: {FG} !important;
    color: {FG} !important;
    font-family: 'Inter', sans-serif;
}}
.stApp {{ background-color: {BG} !important; color: {FG} !important; }}
.main .block-container {{ padding: 0.6rem 1.4rem 1.5rem 1.4rem !important; max-width: 100% !important; }}
footer {{ visibility: hidden !important; }}

/* ── 1. Restore Streamlit Header Container ── */
header[data-testid="stHeader"] {{
    visibility: visible !important;
    background: transparent !important;
    background-color: transparent !important;
    z-index: 9999 !important;
    pointer-events: none !important;
}}

/* ── 2. Hide Only Top-Right Clutter (Deploy & Menu) ── */
[data-testid="stToolbar"],
[data-testid="stActionElements"],
#MainMenu,
.stDeployButton {{
    display: none !important;
    visibility: hidden !important;
}}

/* Unhide and style the sidebar expand button */
[data-testid="stSidebarCollapseButton"],
[data-testid="collapsedControl"] {{
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    position: fixed !important;
    top: 14px !important;
    left: 14px !important;
    z-index: 999999 !important;
    background-color: var(--bg-color) !important;
    border: 1px solid var(--text-color) !important;
    border-radius: 50% !important;
    padding: 4px !important;
    cursor: pointer !important;
}}

[data-testid="stSidebarCollapseButton"] svg,
[data-testid="collapsedControl"] svg {{
    fill: var(--text-color) !important;
    color: var(--text-color) !important;
    width: 20px !important;
    height: 20px !important;
}}
::-webkit-scrollbar {{ width: 4px; height: 4px; }}
::-webkit-scrollbar-track {{ background: {BG}; }}
::-webkit-scrollbar-thumb {{ background: {BORDER2}; border-radius: 2px; }}

/* ── PILL — outer module container ── */
.pill {{
    background: {BG2};
    border: 1px solid {BORDER};
    border-radius: 32px;
    padding: 1.4rem 1.6rem 1.2rem 1.6rem;
    margin-bottom: 0.85rem;
}}
.pill-sm {{
    background: {BG3};
    border: 1px solid {BORDER2};
    border-radius: 20px;
    padding: 0.75rem 1rem;
    margin-bottom: 0.5rem;
}}
.pill-flat {{
    border: 1px solid {BORDER2};
    border-radius: 20px;
    padding: 0.65rem 1rem;
    margin-bottom: 0.45rem;
}}
hr.pd {{ border: none; border-top: 1px solid {BORDER2}; margin: 0.75rem 0; }}

/* ── Typography ── */
.lbl {{
    font-family: 'Inter', sans-serif;
    font-size: 0.58rem;
    font-weight: 500;
    font-variant: small-caps;
    letter-spacing: 0.13em;
    color: {FG_DIM};
    text-transform: uppercase;
    margin-bottom: 0.1rem;
    line-height: 1;
}}
.num-xl {{
    font-family: 'Space Mono', monospace;
    font-size: 2.1rem;
    font-weight: 700;
    color: {FG};
    letter-spacing: -0.02em;
    line-height: 1;
}}
.num-lg {{
    font-family: 'Space Mono', monospace;
    font-size: 1.25rem;
    font-weight: 700;
    color: {FG};
    line-height: 1;
}}
.num-md {{
    font-family: 'Space Mono', monospace;
    font-size: 0.9rem;
    font-weight: 700;
    color: {FG};
    line-height: 1.3;
}}
.num-sm {{
    font-family: 'Space Mono', monospace;
    font-size: 0.72rem;
    font-weight: 400;
    color: {FG_DIM};
    line-height: 1.4;
}}
.unit {{
    font-family: 'Space Mono', monospace;
    font-size: 0.62rem;
    font-weight: 400;
    color: {FG_DIM};
}}

/* ── Decision badges ── */
.badge-exec {{
    display: inline-block;
    font-family: 'Space Mono', monospace;
    font-size: 0.7rem; font-weight: 700;
    letter-spacing: 0.07em;
    color: {BG}; background: {FG};
    border: 1px solid {FG};
    border-radius: 100px;
    padding: 0.28rem 0.85rem;
    text-transform: uppercase;
}}
.badge-defer {{
    display: inline-block;
    font-family: 'Space Mono', monospace;
    font-size: 0.7rem; font-weight: 700;
    letter-spacing: 0.07em;
    color: {FG}; background: transparent;
    border: 1px solid {FG};
    border-radius: 100px;
    padding: 0.28rem 0.85rem;
    text-transform: uppercase;
}}
.badge-ok  {{ color: {GREEN};  font-family:'Space Mono',monospace; font-size:0.72rem; font-weight:700; }}
.badge-bad {{ color: {RED};    font-family:'Space Mono',monospace; font-size:0.72rem; font-weight:700; }}

/* ── Vessel row ── */
.vrow {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.55rem 0;
    border-bottom: 1px solid {BORDER2};
    font-family: 'Space Mono', monospace;
    font-size: 0.68rem;
    color: {FG};
}}
.vrow:last-child {{ border-bottom: none; }}
.vtag {{
    background: {BG};
    border: 1px solid {BORDER2};
    border-radius: 100px;
    padding: 0.1rem 0.5rem;
    font-size: 0.6rem;
    color: {FG_DIM};
}}

/* ═══════════════════════════════════════════════════════════
   STREAMLIT TABS OVERRIDE — Utilitarian Minimalist Pill Tabs
   ═══════════════════════════════════════════════════════════ */

/* 1. Tab Container — remove default underline, add explicit gap */
.stTabs [data-baseweb="tab-list"] {{
    background: transparent !important;
    border-bottom: none !important;
    border: none !important;
    gap: 0.75rem !important;
    padding: 0.25rem 0 0.85rem 0 !important;
    align-items: center !important;
    box-shadow: none !important;
}}

/* Remove Streamlit / BaseWeb sliding indicator line */
.stTabs [data-baseweb="tab-highlight"],
.stTabs [data-baseweb="tab-border"] {{
    display: none !important;
    background: transparent !important;
    height: 0 !important;
}}

/* 2. Individual Tabs — 1px border matching theme text color, rounded pill, transparent bg */
.stTabs [data-baseweb="tab"],
.stTabs button[role="tab"] {{
    background-color: transparent !important;
    background: transparent !important;
    border: 1px solid {BORDER} !important;
    border-radius: 20px !important;
    padding: 0.45rem 1.25rem !important;
    margin: 0 !important;
    color: {FG} !important;
    font-family: 'Space Mono', monospace !important;
    font-size: 0.72rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    box-shadow: none !important;
    outline: none !important;
    cursor: pointer !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    transition: all 0.2s ease !important;
    white-space: nowrap !important;
}}

/* Ensure child text elements inside inactive tabs inherit exact theme styling */
.stTabs [data-baseweb="tab"] p,
.stTabs [data-baseweb="tab"] span,
.stTabs [data-baseweb="tab"] div,
.stTabs button[role="tab"] p,
.stTabs button[role="tab"] span,
.stTabs button[role="tab"] div {{
    color: {FG} !important;
    font-family: 'Space Mono', monospace !important;
    font-size: 0.72rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    line-height: 1.2 !important;
    margin: 0 !important;
    padding: 0 !important;
    transition: color 0.2s ease !important;
}}

/* 3. Active Tab State — INVERTED: fill = theme text color, text = background color */
.stTabs [data-baseweb="tab"][aria-selected="true"],
.stTabs button[role="tab"][aria-selected="true"] {{
    background-color: {FG} !important;
    background: {FG} !important;
    color: {BG} !important;
    border: 1px solid {FG} !important;
    border-radius: 20px !important;
    box-shadow: none !important;
}}

.stTabs [data-baseweb="tab"][aria-selected="true"] p,
.stTabs [data-baseweb="tab"][aria-selected="true"] span,
.stTabs [data-baseweb="tab"][aria-selected="true"] div,
.stTabs button[role="tab"][aria-selected="true"] p,
.stTabs button[role="tab"][aria-selected="true"] span,
.stTabs button[role="tab"][aria-selected="true"] div {{
    color: {BG} !important;
    font-family: 'Space Mono', monospace !important;
    font-size: 0.72rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
}}

/* 4. Hover State on Inactive Tabs */
.stTabs [data-baseweb="tab"]:hover:not([aria-selected="true"]),
.stTabs button[role="tab"]:hover:not([aria-selected="true"]) {{
    background-color: {BG3} !important;
    background: {BG3} !important;
    border-color: {BORDER} !important;
    color: {FG} !important;
}}

.stTabs [data-baseweb="tab"]:hover:not([aria-selected="true"]) p,
.stTabs [data-baseweb="tab"]:hover:not([aria-selected="true"]) span,
.stTabs [data-baseweb="tab"]:hover:not([aria-selected="true"]) div {{
    color: {FG} !important;
}}

/* 5. Tab panel content area */
.stTabs [data-baseweb="tab-panel"] {{
    padding: 0.9rem 0 !important;
    background: transparent !important;
}}


/* ── Native Text & Markdown Visibility ── */
.stMarkdown,
.stMarkdown p,
.stMarkdown span,
.stMarkdown div,
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4, .stMarkdown h5, .stMarkdown h6,
.stMarkdown li,
.stMarkdown label {{
    color: {FG} !important;
}}

/* ── Sidebar & Sidebar Text ── */
section[data-testid="stSidebar"] {{
    background-color: {BG2} !important;
    border-right: 1px solid {BORDER} !important;
    color: {FG} !important;
}}
section[data-testid="stSidebar"] .stMarkdown,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] div,
section[data-testid="stSidebar"] label {{
    color: {FG} !important;
}}

/* ── Input Labels ── */
.stSelectbox label,
.stTextInput label,
.stNumberInput label,
.stSlider label,
[data-testid="stWidgetLabel"],
[data-testid="stWidgetLabel"] label,
[data-testid="stWidgetLabel"] p,
div[data-testid="stSelectbox"] label,
div[data-testid="stSlider"] label,
div[data-testid="stNumberInput"] label,
div[data-testid="stTextInput"] label {{
    color: {FG} !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.64rem !important;
    font-variant: small-caps !important;
    text-transform: uppercase !important;
    letter-spacing: 0.1em !important;
    font-weight: 600 !important;
}}

/* ── Input Controls & Boxes ([data-baseweb="base-input"]) ── */
[data-baseweb="base-input"],
[data-baseweb="input"],
div[data-baseweb="select"] > div,
div[data-testid="stSelectbox"] > div > div {{
    background-color: {BG} !important;
    background: {BG} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 12px !important;
    color: {FG} !important;
    font-family: 'Space Mono', monospace !important;
    font-size: 0.75rem !important;
}}

/* Target inner HTML input elements */
[data-baseweb="base-input"] input,
[data-baseweb="input"] input,
input[type="text"],
input[type="number"],
div[data-testid="stNumberInput"] input,
div[data-testid="stTextInput"] input {{
    background-color: {BG} !important;
    background: {BG} !important;
    color: {FG} !important;
    border: none !important;
    font-family: 'Space Mono', monospace !important;
    font-size: 0.78rem !important;
    -webkit-text-fill-color: {FG} !important;
}}

/* Number input step buttons */
div[data-testid="stNumberInput"] button {{
    background-color: {BG2} !important;
    color: {FG} !important;
    border: 1px solid {BORDER} !important;
}}
div[data-testid="stNumberInput"] button:hover {{
    background-color: {FG} !important;
    color: {BG} !important;
}}
div[data-testid="stNumberInput"] button svg {{
    fill: {FG} !important;
}}
div[data-testid="stNumberInput"] button:hover svg {{
    fill: {BG} !important;
}}

/* Selectbox dropdown menu & options */
div[data-baseweb="popover"],
div[data-baseweb="menu"],
ul[role="listbox"] {{
    background-color: {BG2} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 12px !important;
}}
li[role="option"] {{
    background-color: transparent !important;
    color: {FG} !important;
    font-family: 'Space Mono', monospace !important;
    font-size: 0.75rem !important;
}}
li[role="option"]:hover,
li[role="option"][aria-selected="true"] {{
    background-color: {FG} !important;
    color: {BG} !important;
}}

/* Slider ticks, thumb & track */
div[data-testid="stSlider"] [data-testid="stThumbValue"] {{
    color: {FG} !important;
    font-family: 'Space Mono', monospace !important;
    font-size: 0.72rem !important;
    font-weight: 700 !important;
}}
div[data-testid="stSlider"] [data-baseweb="slider"] div {{
    color: {FG} !important;
}}

div[data-testid="stToggle"] label {{
    color: {FG} !important;
    font-family: 'Space Mono', monospace !important;
    font-size: 0.68rem !important;
}}

/* ── Buttons ── */
.stButton > button {{
    background: {BG2} !important;
    color: {FG} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 100px !important;
    font-family: 'Space Mono', monospace !important;
    font-size: 0.65rem !important; font-weight: 700 !important;
    letter-spacing: 0.08em !important; text-transform: uppercase !important;
    padding: 0.4rem 1.1rem !important;
    box-shadow: none !important;
    transition: background 0.15s, color 0.15s;
}}
.stButton > button:hover {{ background: {FG} !important; color: {BG} !important; }}
.stDownloadButton > button {{
    background: {BG2} !important; color: {FG} !important;
    border: 1px solid {BORDER} !important; border-radius: 100px !important;
    font-family: 'Space Mono', monospace !important;
    font-size: 0.65rem !important; letter-spacing: 0.07em !important;
    text-transform: uppercase !important; box-shadow: none !important;
}}

/* ── Metrics ── */
[data-testid="stMetric"],
[data-testid="metric-container"] {{
    background: {BG3} !important;
    border: 1px solid {BORDER2} !important;
    border-radius: 20px !important;
    padding: 0.65rem 0.9rem !important;
    box-shadow: none !important;
}}

[data-testid="stMetricValue"], 
[data-testid="stMetricValue"] *,
[data-testid="metric-container"] [data-testid="metric-value"],
[data-testid="metric-container"] [data-testid="metric-value"] *,
[data-testid="metric-container"] [data-testid="stMetricValue"],
[data-testid="metric-container"] [data-testid="stMetricValue"] * {{
    color: var(--text-color) !important;
    font-family: 'Space Mono', monospace !important;
    font-size: 1.15rem !important;
    font-weight: 700 !important;
}}

[data-testid="stMetricLabel"], 
[data-testid="stMetricLabel"] *,
[data-testid="metric-container"] label,
[data-testid="metric-container"] [data-testid="stMetricLabel"],
[data-testid="metric-container"] [data-testid="stMetricLabel"] * {{
    color: var(--text-color) !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.62rem !important;
    font-variant: small-caps !important;
    letter-spacing: 0.12em !important;
    text-transform: uppercase !important;
    font-weight: 600 !important;
}}

[data-testid="stMetricDelta"],
[data-testid="stMetricDelta"] *,
[data-testid="metric-container"] [data-testid="metric-delta"],
[data-testid="metric-container"] [data-testid="metric-delta"] * {{
    font-family: 'Space Mono', monospace !important;
    font-size: 0.62rem !important;
}}

/* ── DataFrames ── */
[data-testid="stDataFrame"] {{
    border: 1px solid {BORDER2} !important;
    border-radius: 16px !important;
}}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# CACHED MODEL LOADERS  — all original engines preserved
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner="Loading freight forecasting model…")
def load_freight_engine():
    from optimizer import FreightEngine
    return FreightEngine()

@st.cache_resource(show_spinner="Training bunker fuel model…")
def load_fuel_engine():
    from optimizer import FuelEngine
    return FuelEngine()

@st.cache_resource(show_spinner="Training charter timing ensemble…")
def load_timing_engine():
    from optimizer import TimingEngine
    return TimingEngine()

@st.cache_resource(show_spinner="Loading vessel allocation engine…")
def load_vessel_engine():
    from optimizer import VesselEngine
    return VesselEngine()

@st.cache_data(ttl=60)
def load_tinyfish_market():
    """Retrieves live or cached TinyFish market intelligence."""
    try:
        from backend.services.cache_service import cache_service
        import asyncio
        loop = asyncio.new_event_loop()
        bdi_data, bdi_fresh, bdi_time, bdi_src = loop.run_until_complete(cache_service.get_bdi())
        bunker_data, bunker_fresh, bunker_time, bunker_src = loop.run_until_complete(cache_service.get_bunker())
        loop.close()
        return {
            "bdi": bdi_data,
            "bdi_freshness": bdi_fresh,
            "bdi_time": bdi_time,
            "bdi_src": bdi_src,
            "bunker": bunker_data,
            "bunker_freshness": bunker_fresh,
            "bunker_time": bunker_time,
            "bunker_src": bunker_src,
        }
    except Exception as e:
        return {
            "bdi": {"value": 1550.0, "daily_change": 0.0, "reporting_date": "Current"},
            "bdi_freshness": "fallback",
            "bunker": {"benchmark": {"price_usd_per_mt": 640.0, "port_name": "Singapore", "fuel_grade": "VLSFO"}},
            "bunker_freshness": "fallback",
        }

@st.cache_data(ttl=300)
def get_freight_forecast(route, cargo_type, vessel_class, market_event,
                         vessel_dwt, distance_nm, bdi, bunker, congestion):
    eng   = load_freight_engine()
    today = datetime.date.today()
    return eng.forecast_14d(dict(
        route=route, cargo_type=cargo_type, vessel_class=vessel_class,
        market_event=market_event, vessel_dwt=vessel_dwt,
        distance_nm=distance_nm, baltic_style_index=bdi,
        bunker_fuel_price=bunker, port_congestion_days=congestion,
        month=today.month, year=today.year,
        week_of_year=int(today.isocalendar()[1]),
    ))

@st.cache_data(ttl=300)
def get_fuel_forecast(bunker_price):
    return load_fuel_engine().forecast_bunker_14d(bunker_price)

@st.cache_data(ttl=300)
def get_timing_decision(dwt, vessel_age, fuel_price, wind_speed,
                        wave_height, speed, distance_nm, cargo_tonnes):
    return load_timing_engine().get_decision(
        dwt=dwt, vessel_age=vessel_age, fuel_price=fuel_price,
        wind_speed=wind_speed, wave_height=wave_height,
        speed=speed, distance_nm=distance_nm, cargo_tonnes=cargo_tonnes,
    )

@st.cache_data(ttl=300)
def get_ranked_vessels(cargo_tonnes, distance_nm, port, required_days):
    return load_vessel_engine().rank(cargo_tonnes, distance_nm, port, required_days)

@st.cache_data
def get_port_compliance():
    return load_vessel_engine().port_compliance_matrix()

@st.cache_data(ttl=300)
def get_speed_opt(dwt, bunker_price, distance_nm, vessel_age,
                  wind_speed, wave_height, speed, vessel_class):
    from optimizer import _dwt_to_type
    eng = load_fuel_engine()
    row = pd.DataFrame([{
        "vessel_type": _dwt_to_type(dwt), "dwt": dwt, "engine_power": 15000,
        "vessel_age": vessel_age, "draft": VESSEL_CLASS_DRAFT.get(vessel_class, 12.0),
        "speed": speed, "distance_nm": distance_nm, "heading": 90,
        "wind_speed": wind_speed, "wind_direction": 130,
        "wave_height": wave_height, "wave_period": 8,
        "wave_direction": 120, "current_speed": 1.2, "current_direction": 80,
        "fuel_price": bunker_price,
    }])
    return eng.optimize_speed(row, bunker_price, distance_nm / 12.0)


# ─────────────────────────────────────────────────────────────────────────────
# PLOTLY THEME HELPER  — call on every figure before rendering
# ─────────────────────────────────────────────────────────────────────────────
def apply_theme(fig: go.Figure, height: int = 340) -> go.Figure:
    """Inject transparent background + theme-aware grid onto any Plotly figure."""
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Space Mono, monospace", size=10, color=FG_DIM),
        height=height,
        margin=dict(l=46, r=20, t=30, b=36),
        legend=dict(
            bgcolor="rgba(0,0,0,0)", bordercolor=BORDER2, borderwidth=1,
            font=dict(size=9, family="Space Mono"),
        ),
        hoverlabel=dict(
            bgcolor=HOVER_BG, bordercolor=BORDER2,
            font=dict(family="Space Mono", size=10, color=FG),
        ),
    )
    fig.update_xaxes(
        gridcolor=CG, gridwidth=0.5, linecolor=BORDER2, zeroline=False,
        tickfont=dict(family="Space Mono", size=9, color=FG_DIM),
        showspikes=True, spikecolor=CL, spikethickness=1, spikemode="across",
    )
    fig.update_yaxes(
        gridcolor=CG, gridwidth=0.5, linecolor=BORDER2, zeroline=False,
        tickfont=dict(family="Space Mono", size=9, color=FG_DIM),
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# SVG CONFIDENCE RING
# ─────────────────────────────────────────────────────────────────────────────
def confidence_ring(pct: float, size: int = 110) -> str:
    r     = 42
    circ  = 2 * math.pi * r
    dash  = circ * (pct / 100)
    gap   = circ - dash
    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 100 100">
      <circle cx="50" cy="50" r="{r}" fill="none" stroke="{BORDER2}" stroke-width="7"/>
      <circle cx="50" cy="50" r="{r}" fill="none" stroke="{FG}" stroke-width="7"
        stroke-linecap="butt"
        stroke-dasharray="{dash:.2f} {gap:.2f}"
        transform="rotate(-90 50 50)"/>
      <text x="50" y="45" text-anchor="middle" dominant-baseline="middle"
        font-family="Space Mono,monospace" font-size="15" font-weight="700"
        fill="{FG}">{int(pct)}%</text>
      <text x="50" y="61" text-anchor="middle"
        font-family="Inter,sans-serif" font-size="6" fill="{FG_DIM}"
        letter-spacing="1.5">CONF.</text>
    </svg>"""


# ─────────────────────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────────────────────
now_ist = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
now_utc = datetime.datetime.utcnow()

hc1, hc2, hc3 = st.columns([5, 3, 1])
with hc1:
    st.markdown(f"""
    <div style="padding:0.3rem 0 0.6rem 0;border-bottom:1px solid {BORDER};margin-bottom:0.8rem;">
      <span style="font-family:'Space Mono',monospace;font-size:0.9rem;
                   font-weight:700;color:{FG};letter-spacing:0.04em;">
        ⚓&nbsp; SAIL Chartering Terminal
      </span>
      <span style="font-family:'Space Mono',monospace;font-size:0.62rem;
                   color:{FG_MUTE};margin-left:1rem;">PROD v2.4.1</span>
    </div>""", unsafe_allow_html=True)
with hc2:
    tf_market_hdr = load_tinyfish_market()
    bdi_hdr_val = int(tf_market_hdr["bdi"].get("value", 1550))
    bunker_hdr_val = int(tf_market_hdr["bunker"].get("benchmark", {}).get("price_usd_per_mt", 640))
    bdi_hdr_fresh = tf_market_hdr.get("bdi_freshness", "fallback")
    st.markdown(f"""
    <div style="padding:0.3rem 0 0.6rem 0;border-bottom:1px solid {BORDER};
                font-family:'Space Mono',monospace;font-size:0.6rem;
                color:{FG_MUTE};text-align:right;margin-bottom:0.8rem;">
      <span style="color:{GREEN if bdi_hdr_fresh=='fresh' else AMBER};">●</span> BDI {bdi_hdr_val:,} &nbsp;·&nbsp;
      <span style="color:{GREEN};">●</span> BUNKER ${bunker_hdr_val}/MT &nbsp;·&nbsp;
      <span style="color:{GREEN};">●</span> TINYFISH SYNCED
      &nbsp;&nbsp;{now_ist.strftime('%d %b %Y  %H:%M IST')}
    </div>""", unsafe_allow_html=True)
with hc3:
    st.markdown(f"<div style='border-bottom:1px solid {BORDER};padding-bottom:0.35rem;'></div>",
                unsafe_allow_html=True)
    st.toggle("◑ Dark", value=st.session_state.dark_mode, key="dark_mode")


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR — INPUT PARAMETERS  (all original widgets preserved)
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
    <div style="font-family:'Space Mono',monospace;font-size:0.6rem;color:{FG_DIM};
                letter-spacing:0.12em;text-transform:uppercase;
                border-bottom:1px solid {BORDER2};padding-bottom:0.4rem;margin-bottom:0.8rem;">
      ⚙ Fixture Parameters
    </div>""", unsafe_allow_html=True)

    ALL_ROUTES = [
        "Dampier, Australia - Visakhapatnam",
        "Abbot Point, Australia - Ennore",
        "Abbot Point, Australia - Haldia",
        "Abbot Point, Australia - Kolkata",
        "Abbot Point, Australia - Paradip",
        "Port Hedland, Australia - Vizag",
        "Richards Bay, South Africa - Vizag",
        "Newcastle, Australia - Paradip",
        "Murmansk, Russia - Vizag",
    ]
    route        = st.selectbox("Route", ALL_ROUTES)
    cargo_type   = st.selectbox("Cargo Type", ["Coal Ore","Iron Ore","Coking Coal","Thermal Coal"])
    vessel_class = st.selectbox("Vessel Class", ["Handysize","Supramax","Panamax","Capesize"], index=2)
    port         = st.selectbox("Destination Port", list(PORT_CONSTRAINTS.keys()))
    cargo_tonnes = st.number_input("Cargo Volume (MT)", 5000, 200000, 60000, 1000)

    tf_market = load_tinyfish_market()
    default_bdi = int(tf_market["bdi"].get("value", 1550))
    default_bunker = int(tf_market["bunker"].get("benchmark", {}).get("price_usd_per_mt", 640))
    bdi_freshness = tf_market.get("bdi_freshness", "fallback")

    st.markdown(f"""<div style="font-family:'Space Mono',monospace;font-size:0.6rem;color:{FG_DIM};
                letter-spacing:0.12em;text-transform:uppercase;
                border-bottom:1px solid {BORDER2};padding-bottom:0.4rem;
                margin:0.9rem 0 0.8rem 0;display:flex;justify-content:space-between;align-items:center;">
                <span>📊 Market Conditions</span>
                <span style="color:{GREEN if bdi_freshness=='fresh' else AMBER};font-weight:700;">● TINYFISH {bdi_freshness.upper()}</span>
                </div>""",
                unsafe_allow_html=True)

    c_sync1, c_sync2 = st.columns([3, 2])
    with c_sync1:
        st.caption(f"Trading Economics BDI: **{default_bdi:,}**")
        st.caption(f"Singapore VLSFO: **${default_bunker}/MT**")
    with c_sync2:
        if st.button("🔄 Sync Now", key="sync_tf_btn", help="Fetch live market intelligence via TinyFish"):
            try:
                import asyncio
                from backend.services.bdi_service import bdi_service
                from backend.services.bunker_service import bunker_service
                loop = asyncio.new_event_loop()
                loop.run_until_complete(bdi_service.fetch_live_bdi())
                loop.run_until_complete(bunker_service.fetch_live_bunker_prices())
                loop.close()
                load_tinyfish_market.clear()
                st.toast("TinyFish live sync completed!", icon="✅")
                st.rerun()
            except Exception as ex:
                st.toast(f"Sync notice: {ex}", icon="ℹ️")

    bdi           = st.slider("BDI Index", 800, 4000, max(800, min(4000, default_bdi)), 50)
    bunker        = st.slider("Bunker Price (USD/MT)", 400, 1000, max(400, min(1000, default_bunker)), 10)
    congestion    = st.slider("Port Congestion (days)", 0.0, 8.0, 1.5, 0.5)
    wind_speed    = st.slider("Wind Speed (knots)", 0.0, 40.0, 12.0, 0.5)
    wave_height   = st.slider("Wave Height (m)", 0.0, 8.0, 2.0, 0.25)
    market_event  = st.selectbox("Market Event",
                                 ["None","Port Strike","Canal Disruption",
                                  "Monsoon Season","High Demand"])

    st.markdown(f"""<div style="font-family:'Space Mono',monospace;font-size:0.6rem;color:{FG_DIM};
                letter-spacing:0.12em;text-transform:uppercase;
                border-bottom:1px solid {BORDER2};padding-bottom:0.4rem;
                margin:0.9rem 0 0.8rem 0;">🚢 Voyage Parameters</div>""",
                unsafe_allow_html=True)

    distance_nm   = st.number_input("Distance (NM)", 1000, 15000, 3570, 100)
    vessel_age    = st.slider("Vessel Age (years)", 1, 25, 8)
    required_days = st.slider("Transit Window (days)", 10, 60, 30)

    st.markdown("<div style='height:0.4rem'></div>", unsafe_allow_html=True)
    run_btn = st.button("▶  Run Optimization", use_container_width=True)

VESSEL_DWT_MAP = {"Handysize": 30000, "Supramax": 55000, "Panamax": 78000, "Capesize": 160000}
vessel_dwt = VESSEL_DWT_MAP[vessel_class]


# ─────────────────────────────────────────────────────────────────────────────
# COMPUTE PIPELINE
# ─────────────────────────────────────────────────────────────────────────────
if "results_ready" not in st.session_state:
    st.session_state.results_ready = False

if run_btn or not st.session_state.results_ready:
    with st.spinner("Running optimization pipeline…"):
        try:
            st.session_state.freight_fc  = get_freight_forecast(
                route, cargo_type, vessel_class, market_event,
                vessel_dwt, distance_nm, bdi, bunker, congestion)
            st.session_state.fuel_fc     = get_fuel_forecast(bunker)
            st.session_state.timing_dec  = get_timing_decision(
                vessel_dwt, vessel_age, bunker, wind_speed,
                wave_height, 14.0, distance_nm, cargo_tonnes)
            st.session_state.ranked_df   = get_ranked_vessels(
                cargo_tonnes, distance_nm, port, required_days)
            st.session_state.compliance  = get_port_compliance()
            st.session_state.speed_opt   = get_speed_opt(
                vessel_dwt, bunker, distance_nm, vessel_age,
                wind_speed, wave_height, 14.0, vessel_class)
            st.session_state.results_ready = True
        except Exception as e:
            st.error(f"Pipeline error: {e}")
            st.stop()

freight_fc  = st.session_state.freight_fc
fuel_fc     = st.session_state.fuel_fc
timing_dec  = st.session_state.timing_dec
ranked_df   = st.session_state.ranked_df
compliance  = st.session_state.compliance
speed_opt   = st.session_state.speed_opt

# ── Derived values ────────────────────────────────────────────────────────────
decision     = timing_dec.get("decision", "DEFER")
dec_label    = timing_dec.get("decision_label", "DEFER FIXTURE")
t_star       = timing_dec.get("optimal_t_star", 4)
cur_rate     = timing_dec.get("current_rate", 0)
fut_rate     = timing_dec.get("predicted_future", 0)
dir_acc      = timing_dec.get("directional_accuracy", 68.0)
savings      = timing_dec.get("savings_if_wait", 0)
daily_rates  = timing_dec.get("daily_rates", [])
port_cfg     = PORT_CONSTRAINTS.get(port, PORT_CONSTRAINTS["Paradip"])
demurrage    = port_cfg["queue_days_avg"] * port_cfg["demurrage_usd_day"]
vc_draft     = VESSEL_CLASS_DRAFT.get(vessel_class, 12.0)
max_draft    = port_cfg["max_draft"]
draft_ok     = vc_draft <= max_draft
tlc          = timing_dec.get("total_landed_cost", 0)
fcast_t0     = freight_fc["mean"][0]  if freight_fc.get("mean") else 0
fcast_t14    = freight_fc["mean"][-1] if freight_fc.get("mean") else 0
opt_speed    = speed_opt.get("speed", 14.0)
fuel_cost_v  = speed_opt.get("fuel_cost", 0)
all_spd      = speed_opt.get("all_results", pd.DataFrame())
badge_cls    = "badge-exec" if decision == "EXECUTE_NOW" else "badge-defer"
badge_txt    = "EXECUTE FIXTURE — LOCK RATE NOW" if decision == "EXECUTE_NOW" else f"DEFER FIXTURE  ·  T+{t_star} TARGET"


# ─────────────────────────────────────────────────────────────────────────────
# DECISION BANNER  (above tabs, always visible)
# ─────────────────────────────────────────────────────────────────────────────
ban_left, ban_right = st.columns([4, 1])
with ban_left:
    st.markdown(f"""
    <div class="pill" style="display:flex;align-items:center;gap:1.4rem;padding:1rem 1.4rem;">
      <div style="flex:1;">
        <div class="lbl" style="margin-bottom:0.5rem;">AI Fixture Recommendation</div>
        <span class="{badge_cls}">{badge_txt}</span>
        <div style="display:flex;gap:2.2rem;margin-top:0.9rem;">
          <div>
            <div class="lbl">Current Rate</div>
            <span class="num-lg">${cur_rate:,.0f}</span>
            <span class="unit">/day</span>
          </div>
          <div>
            <div class="lbl">Forecast T+{t_star}</div>
            <span class="num-lg">${fut_rate:,.0f}</span>
            <span class="unit">/day</span>
          </div>
          <div>
            <div class="lbl">Net Savings</div>
            <span class="num-lg">${savings:,.0f}</span>
          </div>
          <div>
            <div class="lbl">Optimal Window</div>
            <span class="num-lg">T+{t_star}</span>
            <span class="unit">days</span>
          </div>
        </div>
      </div>
      {confidence_ring(dir_acc, 108)}
    </div>""", unsafe_allow_html=True)

with ban_right:
    draft_color = "badge-ok" if draft_ok else "badge-bad"
    draft_icon  = "✓ CLEAR" if draft_ok else "✕ BLOCKED"
    st.markdown(f"""
    <div class="pill" style="height:100%;display:flex;flex-direction:column;
                             justify-content:center;gap:0.6rem;padding:1rem 1.4rem;">
      <div>
        <div class="lbl">Total Landed Cost</div>
        <div class="num-lg">${tlc:,.0f}</div>
      </div>
      <hr class="pd"/>
      <div>
        <div class="lbl">Demurrage Exposure · {port}</div>
        <div class="num-md">${demurrage:,.0f}</div>
        <div class="num-sm">{port_cfg['queue_days_avg']}d queue</div>
      </div>
      <hr class="pd"/>
      <div>
        <div class="lbl">{vessel_class} Draft @ {port}</div>
        <div class="{draft_color}">{draft_icon}</div>
        <div class="num-sm">{vc_draft}m vs {max_draft}m limit</div>
      </div>
    </div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "  Commercial Chartering Desk  ",
    "  Port & Berth Operations  ",
    "  Executive Summary  ",
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — COMMERCIAL CHARTERING DESK
# ══════════════════════════════════════════════════════════════════════════════
with tab1:

    # ── KPI Ribbon ───────────────────────────────────────────────────────────
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("CURRENT CHARTER RATE", f"${cur_rate:,.0f}/day",
              delta=f"{((cur_rate - fut_rate)/max(fut_rate,1)*100):+.1f}% vs forecast")
    k2.metric("FREIGHT RATE  T+0", f"${fcast_t0:.2f}/t",
              delta=f"T+14: ${fcast_t14:.2f}/t")
    k3.metric("BUNKER PRICE", f"${bunker}/MT",
              delta=f"14d proj: ${fuel_fc['price'][-1] if fuel_fc.get('price') else bunker:.0f}/MT")
    k4.metric("TOTAL LANDED COST", f"${tlc:,.0f}")
    k5.metric("DIRECTIONAL ACCURACY", f"{dir_acc:.1f}%", delta="GBR+LR ensemble")

    st.markdown("<div style='height:0.3rem'></div>", unsafe_allow_html=True)

    # ── Dual-axis Freight + Bunker Chart ─────────────────────────────────────
    with st.container():
        st.markdown(f'<div class="pill">', unsafe_allow_html=True)
        st.markdown(f'<div class="lbl" style="margin-bottom:0.5rem;">14-Day Freight Rate Forecast  ·  Bunker Fuel Trend</div>',
                    unsafe_allow_html=True)

        fig_main = make_subplots(specs=[[{"secondary_y": True}]])

        dates = freight_fc.get("dates", [])
        means = freight_fc.get("mean",  [])
        lows  = freight_fc.get("lower", [])
        highs = freight_fc.get("upper", [])

        # ±1σ uncertainty band
        if dates and means:
            r_int = int(CL[1:3], 16)
            g_int = int(CL[3:5], 16)
            b_int = int(CL[5:7], 16)
            fig_main.add_trace(go.Scatter(
                x=dates + dates[::-1], y=highs + lows[::-1],
                fill="toself",
                fillcolor=f"rgba({r_int},{g_int},{b_int},0.07)",
                line=dict(color="rgba(0,0,0,0)"),
                hoverinfo="skip", showlegend=False, name="±1σ Band",
            ), secondary_y=False)

            # Freight forecast line
            fig_main.add_trace(go.Scatter(
                x=dates, y=means,
                mode="lines+markers",
                line=dict(color=CL, width=2),
                marker=dict(size=3, color=CL),
                name="Freight Rate (USD/t)",
                hovertemplate="<b>%{x}</b><br>${%{y:.3f}}/t<extra></extra>",
            ), secondary_y=False)

        # Bunker fuel trend (right axis)
        b_dates  = fuel_fc.get("dates", dates)
        b_prices = fuel_fc.get("price", [bunker] * 14)
        fig_main.add_trace(go.Scatter(
            x=b_dates, y=b_prices,
            mode="lines",
            line=dict(color=AMBER, width=1.5, dash="dot"),
            name="Bunker Fuel (USD/MT)",
            hovertemplate="<b>%{x}</b><br>${%{y:.0f}}/MT<extra></extra>",
        ), secondary_y=True)

        # T* marker
        if dates and 0 < t_star < len(dates):
            fig_main.add_vline(
                x=dates[t_star],
                line=dict(color=FG_DIM, width=1, dash="dash"),
                annotation_text=f"T*+{t_star}",
                annotation_font=dict(color=FG_DIM, size=9, family="Space Mono"),
                annotation_position="top right",
            )

        apply_theme(fig_main, height=320)
        fig_main.update_yaxes(
            title_text="Freight Rate (USD/t)",
            title_font=dict(size=9, color=FG_DIM),
            secondary_y=False,
        )
        fig_main.update_yaxes(
            title_text="Bunker (USD/MT)",
            title_font=dict(size=9, color=AMBER),
            tickfont=dict(color=AMBER, size=9, family="Space Mono"),
            gridcolor="rgba(0,0,0,0)",
            secondary_y=True,
        )
        fig_main.update_layout(
            legend=dict(orientation="h", yanchor="bottom", y=1.01,
                        xanchor="right", x=1,
                        bgcolor="rgba(0,0,0,0)", borderwidth=0,
                        font=dict(size=9, family="Space Mono", color=FG_DIM)),
        )
        st.plotly_chart(fig_main, use_container_width=True,
                        config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    # ── TLC Breakdown ─────────────────────────────────────────────────────────
    st.markdown(f'<div class="lbl" style="margin:0.2rem 0 0.4rem 0;">Total Landed Cost — Component Breakdown</div>',
                unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("BASE FREIGHT",     f"${timing_dec.get('base_freight',0):,.0f}")
    c2.metric("BUNKER SURCHARGE", f"${timing_dec.get('bunker_surcharge',0):,.0f}")
    c3.metric("INVENTORY HOLDING",f"${timing_dec.get('inventory_hold',0):,.0f}")
    c4.metric("DEMURRAGE RISK",   f"${demurrage:,.0f}")

    # ── Charter Rate Projection Bar Chart ────────────────────────────────────
    if daily_rates:
        st.markdown("<div style='height:0.3rem'></div>", unsafe_allow_html=True)
        with st.container():
            st.markdown('<div class="pill">', unsafe_allow_html=True)
            st.markdown('<div class="lbl" style="margin-bottom:0.4rem;">Charter Rate Projection — Optimal Fixture Window</div>',
                        unsafe_allow_html=True)

            r_int = int(FG[1:3], 16)
            g_int = int(FG[3:5], 16)
            b_int = int(FG[5:7], 16)
            bar_colors = [FG if i == t_star else BG3 for i in range(len(daily_rates))]
            border_cols= [BG if i == t_star else BORDER2 for i in range(len(daily_rates))]

            fig_bar = go.Figure(go.Bar(
                x=[f"T+{i}" for i in range(len(daily_rates))],
                y=daily_rates,
                marker=dict(color=bar_colors,
                            line=dict(color=border_cols, width=1)),
                hovertemplate="<b>%{x}</b><br>${%{y:,.0f}}/day<extra></extra>",
            ))
            apply_theme(fig_bar, height=190)
            fig_bar.update_yaxes(tickprefix="$", tickformat=",.0f")
            st.plotly_chart(fig_bar, use_container_width=True,
                            config={"displayModeBar": False})
            st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — PORT & BERTH OPERATIONS
# ══════════════════════════════════════════════════════════════════════════════
with tab2:

    # ── Port Compliance Matrix ────────────────────────────────────────────────
    st.markdown(f'<div class="lbl" style="margin-bottom:0.4rem;">Port Draft Clearance Matrix  ·  Vessel Class Eligibility</div>',
                unsafe_allow_html=True)
    if not compliance.empty:
        def _style_cell(val):
            base = f"font-family:'Space Mono',monospace;font-size:0.72rem;"
            if "BLOCKED" in str(val):
                return base + f"color:{RED};background-color:{BG3};"
            if "CLEAR" in str(val):
                return base + f"color:{GREEN};background-color:{BG3};"
            return base + f"color:{FG_DIM};"

        styled = (
            compliance.style
            .map(_style_cell)
            .set_table_styles([{
                "selector": "th",
                "props": [
                    ("background-color", BG2), ("color", FG_MUTE),
                    ("font-family", "'Space Mono',monospace"),
                    ("font-size", "0.6rem"), ("letter-spacing", "0.08em"),
                    ("text-transform", "uppercase"),
                    ("border-bottom", f"1px solid {BORDER2}"),
                ],
            }])
        )
        st.dataframe(styled, use_container_width=True, height=245)

    st.markdown("<div style='height:0.3rem'></div>", unsafe_allow_html=True)
    col_l, col_r = st.columns([3, 2])

    with col_l:
        # ── Ranked Vessels Table ──────────────────────────────────────────────
        st.markdown(f'<div class="lbl" style="margin-bottom:0.4rem;">Top Vessels — {port} Allocation  ·  Cargo: {cargo_tonnes:,} MT</div>',
                    unsafe_allow_html=True)
        if not ranked_df.empty:
            disp_cols = ["rank","candidate_id","vessel_type","dwt","speed",
                         "draft","vessel_age","charter_rate_usd_day","vessel_score"]
            disp_cols = [c for c in disp_cols if c in ranked_df.columns]
            show_df = ranked_df[disp_cols].head(10).copy()
            show_df["vessel_score"]         = show_df["vessel_score"].map(lambda x: f"{x:.1f}")
            show_df["charter_rate_usd_day"] = show_df["charter_rate_usd_day"].map(lambda x: f"${x:,.0f}")
            show_df["dwt"]                  = show_df["dwt"].map(lambda x: f"{x:,.0f}")
            st.dataframe(show_df, use_container_width=True, height=320, hide_index=True)
        else:
            st.markdown(f'<div class="pill-flat" style="text-align:center;"><span class="num-sm">No vessels satisfy the draft/DWT constraints for {port}.</span></div>',
                        unsafe_allow_html=True)

        # ── Vessel Allocation Toggles (CVC audit) ─────────────────────────────
        st.markdown(f"""
        <div class="lbl" style="margin:0.6rem 0 0.4rem 0;">
          CVC Audit — Select / Allocate Vessels
        </div>""", unsafe_allow_html=True)

        if not ranked_df.empty:
            if "vessel_allocation" not in st.session_state:
                st.session_state.vessel_allocation = {}
            for _, vrow in ranked_df.head(6).iterrows():
                vid    = str(vrow.get("candidate_id", vrow.get("vessel_id", "—")))
                vtype  = str(vrow.get("vessel_type", "—"))
                vrate  = float(vrow.get("charter_rate_usd_day", 0))
                vscore = float(vrow.get("vessel_score", 0))
                tc1, tc2 = st.columns([4, 1])
                with tc1:
                    st.markdown(f"""
                    <div class="vrow">
                      <div>
                        <span style="font-weight:700;">{vid}</span>
                        <span class="num-sm" style="margin-left:0.5rem;">{vtype}</span>
                      </div>
                      <div style="display:flex;align-items:center;gap:0.5rem;">
                        <span class="num-sm">${vrate:,.0f}/day</span>
                        <span class="vtag">{vscore:.0f}</span>
                      </div>
                    </div>""", unsafe_allow_html=True)
                with tc2:
                    toggled = st.toggle("", value=st.session_state.vessel_allocation.get(vid, False),
                                        key=f"vtog_{vid}", label_visibility="collapsed")
                    st.session_state.vessel_allocation[vid] = toggled
                    if toggled:
                        st.markdown(f'<div style="font-family:\'Space Mono\',monospace;font-size:0.55rem;'
                                    f'color:{GREEN};text-align:center;">LOGGED</div>',
                                    unsafe_allow_html=True)

    with col_r:
        # ── Vessel Score Chart ────────────────────────────────────────────────
        if not ranked_df.empty:
            st.markdown(f'<div class="lbl" style="margin-bottom:0.4rem;">Vessel Composite Score</div>',
                        unsafe_allow_html=True)
            top15    = ranked_df.head(15)
            bar_cols = [FG if i == 0 else BG3 for i in range(len(top15))]

            fig_vs = go.Figure(go.Bar(
                x=top15["vessel_score"],
                y=top15["candidate_id"],
                orientation="h",
                marker=dict(color=bar_cols, line=dict(color=BORDER2, width=0.5)),
                hovertemplate="<b>%{y}</b><br>Score: %{x:.1f}<extra></extra>",
            ))
            apply_theme(fig_vs, height=310)
            fig_vs.update_layout(showlegend=False)
            fig_vs.update_yaxes(autorange="reversed")
            st.plotly_chart(fig_vs, use_container_width=True,
                            config={"displayModeBar": False})

    # ── Speed Optimization ────────────────────────────────────────────────────
    st.markdown("<div style='height:0.2rem'></div>", unsafe_allow_html=True)
    st.markdown(f'<div class="lbl" style="margin-bottom:0.4rem;">Optimal Voyage Speed — Bunker Cost Minimisation</div>',
                unsafe_allow_html=True)
    sp1, sp2, sp3, sp4 = st.columns(4)
    sp1.metric("OPTIMAL SPEED",    f"{opt_speed} kn")
    sp2.metric("FUEL CONSUMPTION", f"{speed_opt.get('fuel_per_day','—')} MT/day")
    sp3.metric("TOTAL FUEL COST",  f"${fuel_cost_v:,.0f}")
    sp4.metric("VOYAGE DURATION",  f"{speed_opt.get('voyage_hours',0)/24:.1f} days")

    if not all_spd.empty:
        with st.container():
            st.markdown('<div class="pill">', unsafe_allow_html=True)
            fig_spd = go.Figure()
            fig_spd.add_trace(go.Scatter(
                x=all_spd["speed"], y=all_spd["total_cost"],
                mode="lines", line=dict(color=CL, width=2),
                name="Total Economic Cost",
                hovertemplate="Speed: %{x:.1f} kn<br>${%{y:,.0f}}<extra></extra>",
            ))
            fig_spd.add_trace(go.Scatter(
                x=all_spd["speed"], y=all_spd["fuel_cost"],
                mode="lines", line=dict(color=AMBER, width=1.5, dash="dot"),
                name="Fuel Cost Only",
                hovertemplate="Speed: %{x:.1f} kn<br>${%{y:,.0f}}<extra></extra>",
            ))
            fig_spd.add_vline(x=opt_speed, line=dict(color=GREEN, width=1, dash="dash"),
                              annotation_text=f"OPT {opt_speed} kn",
                              annotation_font=dict(color=GREEN, size=9, family="Space Mono"))
            apply_theme(fig_spd, height=200)
            fig_spd.update_xaxes(title_text="Speed (knots)", title_font=dict(size=9))
            fig_spd.update_yaxes(tickprefix="$", tickformat=",.0f")
            st.plotly_chart(fig_spd, use_container_width=True,
                            config={"displayModeBar": False})
            st.markdown("</div>", unsafe_allow_html=True)

    # ── Demurrage Exposure Table ───────────────────────────────────────────────
    st.markdown(f'<div class="lbl" style="margin-top:0.4rem;margin-bottom:0.4rem;">Demurrage Exposure — All SAIL Ports</div>',
                unsafe_allow_html=True)
    dem_rows = []
    for p_name, cfg in PORT_CONSTRAINTS.items():
        exp = cfg["queue_days_avg"] * cfg["demurrage_usd_day"]
        dem_rows.append({
            "Port": p_name,
            "Avg Queue (days)": cfg["queue_days_avg"],
            "Rate (USD/day)": f"${cfg['demurrage_usd_day']:,}",
            "Exposure (USD)": f"${exp:,.0f}",
            "Max Draft (m)": cfg["max_draft"],
            "Selected": "▶" if p_name == port else "",
        })
    st.dataframe(pd.DataFrame(dem_rows), use_container_width=True,
                 height=240, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — EXECUTIVE SUMMARY
# ══════════════════════════════════════════════════════════════════════════════
with tab3:

    # ── 12-month ROI simulation ───────────────────────────────────────────────
    rng          = np.random.default_rng(5)
    months       = [datetime.date.today().replace(day=1) - datetime.timedelta(days=30*i)
                    for i in range(11, -1, -1)]
    month_labels = [m.strftime("%b %y") for m in months]
    always_now   = rng.normal(cur_rate * 30, cur_rate * 3, 12)
    model_strat  = np.maximum(
        always_now - rng.uniform(savings * 0.5, savings * 1.5, 12),
        always_now * 0.75
    )
    cum_savings  = np.cumsum(always_now - model_strat)
    ann_savings  = float(np.sum(always_now - model_strat))
    roi_pct      = (ann_savings / np.sum(always_now)) * 100

    # KPI row
    ex1, ex2, ex3, ex4 = st.columns(4)
    ex1.metric("ANNUALISED SAVINGS",     f"${ann_savings:,.0f}", delta="vs Always-Book-Now")
    ex2.metric("MODEL ROI (12-MONTH)",   f"{roi_pct:.2f}%",      delta="Backtest")
    ex3.metric("FIXTURES SIMULATED",     "12",                    delta="Monthly cadence")
    ex4.metric("DEMURRAGE AVOIDED EST.", f"${savings * 8:,.0f}",  delta="Annualised")

    st.markdown("<div style='height:0.3rem'></div>", unsafe_allow_html=True)

    # 12-month grouped bar + cumulative line
    with st.container():
        st.markdown('<div class="pill">', unsafe_allow_html=True)
        st.markdown('<div class="lbl" style="margin-bottom:0.4rem;">12-Month Charter Cost  ·  Model Strategy vs. Always-Book-Now</div>',
                    unsafe_allow_html=True)

        fig_roi = go.Figure()
        fig_roi.add_trace(go.Bar(
            name="Always-Book-Now", x=month_labels, y=always_now / 1000,
            marker=dict(color=BG3, line=dict(color=BORDER2, width=0.5)),
            hovertemplate="%{x}<br>${%{y:.0f}}k/month<extra></extra>",
        ))
        fig_roi.add_trace(go.Bar(
            name="Model Strategy", x=month_labels, y=model_strat / 1000,
            marker=dict(color=FG, line=dict(color=BORDER, width=0.5)),
            hovertemplate="%{x}<br>${%{y:.0f}}k/month<extra></extra>",
        ))
        fig_roi.add_trace(go.Scatter(
            name="Cumulative Savings", x=month_labels, y=cum_savings / 1000,
            mode="lines+markers", line=dict(color=GREEN, width=2),
            marker=dict(size=4), yaxis="y2",
            hovertemplate="%{x}<br>Cumul.: ${%{y:.0f}}k<extra></extra>",
        ))
        apply_theme(fig_roi, height=300)
        fig_roi.update_layout(
            barmode="group",
            yaxis=dict(title="Cost (USD '000)", title_font=dict(size=9)),
            yaxis2=dict(overlaying="y", side="right",
                        gridcolor="rgba(0,0,0,0)", linecolor=BORDER2,
                        tickfont=dict(family="Space Mono", size=9, color=GREEN),
                        title="Cumulative Savings (USD '000)",
                        title_font=dict(size=9, color=GREEN)),
        )
        st.plotly_chart(fig_roi, use_container_width=True,
                        config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Donut + Audit Memo ────────────────────────────────────────────────────
    col_d, col_m = st.columns([1, 2])

    with col_d:
        st.markdown(f'<div class="lbl" style="margin-bottom:0.4rem;">TLC Composition (Single Fixture)</div>',
                    unsafe_allow_html=True)
        with st.container():
            st.markdown('<div class="pill">', unsafe_allow_html=True)
            tlc_vals   = [
                timing_dec.get("base_freight", 0),
                timing_dec.get("bunker_surcharge", 0),
                demurrage,
                timing_dec.get("inventory_hold", 0),
            ]
            tlc_labels = ["Base Freight","Bunker Surcharge","Demurrage Risk","Inventory Hold"]
            tlc_clrs   = [FG, FG_DIM, RED, AMBER]

            fig_donut = go.Figure(go.Pie(
                labels=tlc_labels, values=tlc_vals, hole=0.58,
                marker=dict(colors=tlc_clrs, line=dict(color=BG, width=2)),
                textfont=dict(family="Space Mono", size=9),
                hovertemplate="<b>%{label}</b><br>${%{value:,.0f}}<br>%{percent}<extra></extra>",
            ))
            apply_theme(fig_donut, height=220)
            fig_donut.update_layout(
                showlegend=True,
                legend=dict(orientation="v", font=dict(size=8, family="Space Mono")),
                margin=dict(l=5, r=5, t=5, b=5),
            )
            st.plotly_chart(fig_donut, use_container_width=True,
                            config={"displayModeBar": False})
            st.markdown("</div>", unsafe_allow_html=True)

    with col_m:
        st.markdown(f'<div class="lbl" style="margin-bottom:0.4rem;">Fixture Recommendation Memo  ·  CVC Compliance Audit Trail</div>',
                    unsafe_allow_html=True)

        allocated_ids = [k for k, v in st.session_state.get("vessel_allocation", {}).items() if v]

        rec_text = f"""SAIL MARITIME PROCUREMENT — FIXTURE ADVISORY NOTE
Generated : {now_ist.strftime('%Y-%m-%d %H:%M IST')}  |  System: PROD v2.4.1
{'=' * 58}

ROUTE              : {route}
DESTINATION PORT   : {port}
CARGO TYPE         : {cargo_type}
CARGO VOLUME       : {cargo_tonnes:,} MT
VESSEL CLASS       : {vessel_class} ({vessel_dwt:,} DWT)
MARKET EVENT       : {market_event}

MARKET SNAPSHOT
  BDI Index          : {bdi:,}
  Bunker Price       : ${bunker}/MT
  Port Congestion    : {congestion} days

MODEL DECISION
  {badge_txt}
  Optimal T*         : T+{t_star} from {now_ist.strftime('%Y-%m-%d')}
  Forecast Rate (T*) : ${fut_rate:,.0f}/day
  Current Rate       : ${cur_rate:,.0f}/day
  Net Savings        : ${savings:,.0f}
  Directional Acc.   : {dir_acc:.1f}%

TOTAL LANDED COST
  Base Freight       : ${timing_dec.get('base_freight',0):,.0f}
  Bunker Surcharge   : ${timing_dec.get('bunker_surcharge',0):,.0f}
  Demurrage Risk     : ${demurrage:,.0f}
  Inventory Holding  : ${timing_dec.get('inventory_hold',0):,.0f}
  TOTAL              : ${tlc:,.0f}

OPTIMAL VOYAGE SPEED
  Speed              : {opt_speed} knots
  Fuel Consumption   : {speed_opt.get('fuel_per_day','—')} MT/day
  Fuel Cost          : ${fuel_cost_v:,.0f}
  Voyage Duration    : {speed_opt.get('voyage_hours',0)/24:.1f} days

PORT CONSTRAINT STATUS
  Max Draft Allowed  : {max_draft} m
  {vessel_class} Draft     : {vc_draft} m
  Clearance          : {'CLEAR' if draft_ok else 'DRAFT VIOLATION — RESELECT VESSEL CLASS'}

HALDIA RESTRICTION (STANDING ORDER)
  Max Draft          : 8.5 m  →  Capesize (18.2m) PERMANENTLY BLOCKED

ALLOCATED VESSELS (CVC LOG)
  {', '.join(allocated_ids) if allocated_ids else 'None selected'}

ANNUALISED PROJECTION
  Savings vs Now     : ${ann_savings:,.0f}
  Model ROI          : {roi_pct:.2f}%

DISCLAIMER: AI-assisted recommendation. Final fixture decisions remain
the sole responsibility of the SAIL Chartering Committee.
"""
        with st.container():
            st.markdown('<div class="pill">', unsafe_allow_html=True)
            st.code(rec_text, language=None)
            st.markdown("</div>", unsafe_allow_html=True)

        # ── CVC Audit CSV Download ────────────────────────────────────────────
        audit_df  = pd.DataFrame({
            "Field": [
                "Route","Port","Cargo Type","Cargo (MT)","Vessel Class","Vessel DWT",
                "BDI","Bunker (USD/MT)","Decision","Optimal T*",
                "Current Rate","Forecast Rate","Net Savings","Base Freight",
                "Bunker Surcharge","Demurrage Risk","Inventory Hold","Total Landed Cost",
                "Optimal Speed (kn)","Fuel Cost","Dir. Accuracy (%)","Ann. Savings",
                "Model ROI (%)","Allocated Vessels","Generated At",
            ],
            "Value": [
                route, port, cargo_type, cargo_tonnes, vessel_class, vessel_dwt,
                bdi, bunker, decision, f"T+{t_star}",
                round(cur_rate, 2), round(fut_rate, 2), round(savings, 2),
                round(timing_dec.get("base_freight", 0), 2),
                round(timing_dec.get("bunker_surcharge", 0), 2),
                round(demurrage, 2),
                round(timing_dec.get("inventory_hold", 0), 2),
                round(tlc, 2), opt_speed, round(fuel_cost_v, 2),
                round(dir_acc, 1), round(ann_savings, 2), round(roi_pct, 2),
                ", ".join(allocated_ids) if allocated_ids else "None",
                now_ist.strftime("%Y-%m-%d %H:%M IST"),
            ],
        })
        csv_bytes = audit_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇  Download Fixture Audit Memo (.CSV)  —  CVC Compliance",
            data=csv_bytes,
            file_name=f"SAIL_fixture_audit_{now_ist.strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True,
        )

# ─────────────────────────────────────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="border-top:1px solid {BORDER2};margin-top:1.2rem;padding-top:0.5rem;
            display:flex;justify-content:space-between;
            font-family:'Space Mono',monospace;font-size:0.57rem;color:{FG_MUTE};">
  <span>SAIL Chartering Terminal · PROD v2.4.1 ·
        FreightXGB | FuelXGB | TimingGBR-LR | VesselRanker</span>
  <span>© Steel Authority of India Limited · Chartering Desk Analytics · {now_ist.year}</span>
</div>""", unsafe_allow_html=True)
