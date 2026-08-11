import streamlit as st
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.design_system import get_css, PRIMARY, SECONDARY, WHITE, TEXT_SEC

# ── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="Pacebird", page_icon="assets/logo.png", layout="wide", initial_sidebar_state="expanded")

# ── DESIGN SYSTEM LOCK — do not modify these values ─────────────────────────
# Primary: #F5A623 (warm orange)   Secondary: #1B2A4A (deep navy)
# Success: #10B981   Warning: #F59E0B   Danger: #EF4444
# Background: #EEF1F4 (light grey)   Font: Poppins
# Text Primary: #111827   Text Secondary: #6B7280
# DO NOT revert to old purple (#7C3AED) or blue (#2563EB) values.
# Central design system: utils/design_system.py

# ── Config helpers ───────────────────────────────────────────────────────────
CONFIG_FILE  = "config.json"
PREFS_FILE   = "user_prefs.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"current_tier": "full_access"}

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

def load_prefs():
    if os.path.exists(PREFS_FILE):
        try:
            with open(PREFS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_prefs(p):
    with open(PREFS_FILE, "w") as f:
        json.dump(p, f, indent=2)

cfg   = load_config()
prefs = load_prefs()

TIER_MAP = {
    "full_access":  {"label": "✨ Full Access",  "visible": ["API Data", "Upload Report", "Sell Side"]},
    "api_only":     {"label": "📡 API Mode",     "visible": ["API Data"]},
    "upload_only":  {"label": "📁 Upload Mode",  "visible": ["Upload Report"]},
    "sell_side":    {"label": "📈 Sell Side",    "visible": ["Sell Side"]},
}
current_tier     = cfg.get("current_tier", "full_access")
visible_sections = TIER_MAP.get(current_tier, TIER_MAP["full_access"])["visible"]
tier_label       = TIER_MAP.get(current_tier, TIER_MAP["full_access"])["label"]

# ── Navigation — must be the FIRST Streamlit command after set_page_config ────
# Streamlit requires st.navigation() before any other st.* calls.
# All CSS, sidebar content, and page rendering come after this block.
API_DATA_PAGES = [
    st.Page("pages/ongoing_performance.py",      title="Performance & Insights"),
    st.Page("pages/portfolio_overview.py",        title="Portfolio Overview"),
    st.Page("pages/live_campaigns.py",            title="Live Campaigns"),
    st.Page("pages/telco_cross_channel.py",       title="Cross-Channel Dashboard"),
    st.Page("pages/settings.py",                  title="Settings"),
]

UPLOAD_REPORT_PAGES = [
    st.Page("pages/performance_insights.py",         title="Performance & Insights"),
    st.Page("pages/portfolio_overview_upload.py",    title="Portfolio Overview"),
    st.Page("pages/pacing_checker.py",               title="Live Campaigns"),
    st.Page("pages/telco_cross_channel_upload.py",   title="Cross-Channel Dashboard"),
    st.Page("pages/settings_link.py",                title="Settings"),
]

SELL_SIDE_PAGES = [
    st.Page("pages/publisher_qbr.py",      title="QBR Generator"),
    st.Page("pages/publisher_yield.py",    title="Yield Dashboard"),
]

nav_sections = {}
if "API Data" in visible_sections:
    nav_sections["📡 API DATA"] = API_DATA_PAGES
if "Upload Report" in visible_sections:
    nav_sections["📁 UPLOAD REPORT"] = UPLOAD_REPORT_PAGES
if "Sell Side" in visible_sections:
    nav_sections["📈 SELL SIDE"] = SELL_SIDE_PAGES

# ── Sidebar logo: st.logo() places the image natively above stSidebarNav ─────
# ── Official Streamlit API for sidebar logos (Streamlit >= 1.35). No CSS hacks needed.
st.logo("assets/logo.png")
pg = st.navigation(nav_sections)

# ── Session state and onboarding step ────────────────────────────────────────
st.session_state["current_tier"] = current_tier
ob_step = st.session_state.get("onboarding_step", 1)

# ── Global CSS — Pacebird design system ───────────────────────────────────────
st.markdown(get_css(), unsafe_allow_html=True)
st.markdown(f"""
<style>
    /* ── Sidebar: deep navy background, white text ──────────────── */
    section[data-testid="stSidebar"] {{
        background-color: {SECONDARY} !important;
        box-shadow: 2px 0 16px rgba(0,0,0,0.15) !important;
    }}
    section[data-testid="stSidebar"] > div:first-child {{
        padding-top: 0 !important;
    }}
    /* Logo area rendered by st.logo() above stSidebarNav — match navy sidebar */
    [data-testid="stSidebarNav"] {{
        margin-top: 16px !important;
    }}
    [data-testid="stSidebarHeader"] {{
        background-color: {SECONDARY} !important;
        padding: 16px 12px 12px 12px !important;
        text-align: center !important;
        border-bottom: 1px solid rgba(255,255,255,0.15) !important;
    }}
    [data-testid="stSidebarHeader"] img {{
        width: 170px !important;
        height: auto !important;
        display: inline-block !important;
    }}
    section[data-testid="stSidebar"] * {{
        color: {WHITE} !important;
    }}
    section[data-testid="stSidebar"] a {{
        color: {WHITE} !important;
        text-decoration: none !important;
    }}
    /* Active nav item: orange highlight */
    section[data-testid="stSidebar"] [aria-current="page"],
    section[data-testid="stSidebar"] [aria-selected="true"] {{
        background-color: {PRIMARY} !important;
        border-radius: 8px !important;
        color: {WHITE} !important;
    }}
    /* Nav section headers (API DATA / UPLOAD REPORT labels) */
    section[data-testid="stSidebar"] [data-testid="stSidebarNavSeparator"] span,
    section[data-testid="stSidebar"] .st-emotion-cache-1rtdyuf,
    section[data-testid="stSidebar"] [data-testid="stSidebarNavItems"] > div > p {{
        font-size: 11px !important;
        font-weight: 700 !important;
        letter-spacing: 1.5px !important;
        color: {PRIMARY} !important;
        text-transform: uppercase !important;
        padding-top: 12px !important;
    }}

    /* ── Table row hover: orange tint ────────────────────────────── */
    [data-testid="stDataFrame"] tr:hover > td {{
        background-color: rgba(245,166,35,0.06) !important;
    }}

    /* ── Filter / selectbox widgets — compact, design-system styled ── */
    /* Outer container: minimal vertical padding */
    [data-testid="stSelectbox"],
    [data-testid="stDateInput"],
    [data-testid="stMultiSelect"] {{
        background-color: #EEF1F4;
        border: 1px solid rgba(27,42,74,0.15);
        border-radius: 8px;
        padding: 1px 6px 2px 6px;
    }}
    /* Label: smaller font, tighter bottom margin */
    [data-testid="stSelectbox"] label,
    [data-testid="stMultiSelect"] label,
    [data-testid="stDateInput"] label {{
        font-size: 11px !important;
        font-weight: 600 !important;
        color: {SECONDARY} !important;
        font-family: "Poppins", system-ui, sans-serif !important;
        text-transform: uppercase !important;
        letter-spacing: 0.04em !important;
        margin-bottom: 0px !important;
        padding-bottom: 0px !important;
        line-height: 1.2 !important;
    }}
    /* Input field: reduced internal padding and min-height */
    [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
    [data-testid="stMultiSelect"] div[data-baseweb="select"] > div {{
        min-height: 28px !important;
        padding-top: 1px !important;
        padding-bottom: 1px !important;
    }}
    [data-testid="stSelectbox"] div[data-baseweb="select"] *,
    [data-testid="stMultiSelect"] div[data-baseweb="select"] * {{
        font-size: 12px !important;
        font-family: "Poppins", system-ui, sans-serif !important;
        color: {SECONDARY} !important;
    }}
    /* Date input: tighter field height */
    [data-testid="stDateInput"] input {{
        padding-top: 2px !important;
        padding-bottom: 2px !important;
        min-height: 28px !important;
        font-size: 12px !important;
        font-family: "Poppins", system-ui, sans-serif !important;
    }}

    /* ── Selectbox / multiselect inner BaseWeb node height ──────── */
    [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
    [data-testid="stMultiSelect"] div[data-baseweb="select"] > div {{
        min-height: 30px !important;
        height: 30px !important;
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }}
    div[data-baseweb="select"] div[data-baseweb="input"],
    div[data-baseweb="select"] [class*="ValueContainer"],
    div[data-baseweb="select"] input {{
        min-height: 28px !important;
        height: 28px !important;
        padding-top: 0 !important;
        padding-bottom: 0 !important;
        line-height: 28px !important;
    }}
    [data-testid="stSelectbox"] [data-testid="stWidgetLabel"],
    [data-testid="stDateInput"] [data-testid="stWidgetLabel"],
    [data-testid="stMultiSelect"] [data-testid="stWidgetLabel"] {{
        min-height: 0 !important;
        margin-bottom: 2px !important;
    }}
    [data-testid="stDateInput"] div[data-baseweb="input"] {{
        min-height: 30px !important;
        height: 30px !important;
    }}

    /* ── Inputs and selectboxes: rounded corners ─────────────────── */
    div[data-baseweb="select"] > div,
    div[data-baseweb="input"] {{
        border-radius: 8px !important;
    }}

    /* ── Buttons: smooth hover ───────────────────────────────────── */
    .stButton > button {{
        border-radius: 10px !important;
        transition: all 0.15s ease !important;
    }}
    .stButton > button:hover {{
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.12) !important;
    }}

    /* ── Tables: rounded, no hard border ─────────────────────────── */
    [data-testid="stDataFrame"] {{
        border-radius: 16px !important;
        overflow: hidden !important;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06) !important;
        border: none !important;
    }}

    /* ── Onboarding highlight ────────────────────────────────────── */
    .onboarding-highlight {{
        border: 3px solid {PRIMARY} !important;
        border-radius: 8px !important;
        animation: pulse-border 2s infinite !important;
    }}
    @keyframes pulse-border {{
        0%   {{ box-shadow: 0 0 0 0   rgba(245,166,35,0.4); }}
        70%  {{ box-shadow: 0 0 0 10px rgba(245,166,35,0);   }}
        100% {{ box-shadow: 0 0 0 0   rgba(245,166,35,0);   }}
    }}
</style>
""", unsafe_allow_html=True)

# ── Step-specific onboarding highlight CSS ───────────────────────────────────
if not prefs.get("onboarding_complete", False):
    if ob_step == 2:
        # Step 2: highlight file upload area
        st.markdown(f"""
        <style>
        [data-testid="stFileUploader"] {{
            border: 3px solid {PRIMARY} !important;
            border-radius: 8px !important;
            animation: pulse-border 2s infinite !important;
        }}
        </style>""", unsafe_allow_html=True)
    elif ob_step == 3:
        # Step 3: highlight Settings nav items in sidebar
        st.markdown(f"""
        <style>
        section[data-testid="stSidebar"] a[href*="settings"] {{
            border: 2px solid {PRIMARY} !important;
            border-radius: 6px !important;
            animation: pulse-border 2s infinite !important;
        }}
        </style>""", unsafe_allow_html=True)
    elif ob_step == 4:
        # Step 4: highlight Performance & Insights nav links
        st.markdown(f"""
        <style>
        section[data-testid="stSidebar"] a[href*="performance"] {{
            border: 2px solid {PRIMARY} !important;
            border-radius: 6px !important;
            animation: pulse-border 2s infinite !important;
        }}
        </style>""", unsafe_allow_html=True)

# ── Onboarding flow ───────────────────────────────────────────────────────────
if not prefs.get("onboarding_complete", False):
    @st.dialog("Welcome to Pacebird 👋", width="large")
    def show_onboarding():
        step = st.session_state.get("onboarding_step", 1)

        # Floating step indicator
        st.markdown(f"""
        <div style="
            position:fixed; bottom:24px; right:24px;
            background:{PRIMARY}; color:#fff;
            padding:8px 16px; border-radius:20px;
            font-size:13px; font-weight:600;
            box-shadow: 0 4px 12px rgba(245,166,35,0.4);
            z-index:9999;">
            Step {{step}} of 4
        </div>
        """.replace("{step}", str(step)), unsafe_allow_html=True)

        if step == 1:
            st.markdown("### Welcome to Pacebird 👋")
            st.markdown("""
            **Pacebird** is your programmatic advertising insights platform.

            Upload DSP exports (DV360, TTD) to get instant performance charts,
            AI-generated insights, and PowerPoint reports ready for clients.
            """)
            col1, col2 = st.columns([3, 1])
            with col2:
                if st.button("Get Started →", type="primary"):
                    st.session_state["onboarding_step"] = 2
                    st.rerun()

        elif step == 2:
            st.markdown("### 📁 Upload your first report")
            st.markdown("""
            Drag and drop your DSP CSV export to get started.

            **Accepted formats:** CSV, XLSX, XLS, TSV
            - DV360 CSV exports
            - The Trade Desk (TTD) CSV reports
            - Generic programmatic CSV files

            Find the upload panel in **Upload Report → Performance & Insights**.

            *(The file upload area is now highlighted in orange on that page.)*
            """)
            col1, col2 = st.columns(2)
            with col1:
                if st.button("← Back"):
                    st.session_state["onboarding_step"] = 1
                    st.rerun()
            with col2:
                if st.button("Next →", type="primary"):
                    st.session_state["onboarding_step"] = 3
                    st.rerun()

        elif step == 3:
            st.markdown("### ⚙️ Set up your first brand")
            st.markdown("""
            **Settings** lets you store context about each advertiser —
            objectives, KPIs, and notes — so AI insights are tailored to your clients.

            Navigate to **Settings** (in the sidebar) to set up your brands.

            *(The Settings nav link is now highlighted in orange.)*
            """)
            col1, col2 = st.columns(2)
            with col1:
                if st.button("← Back"):
                    st.session_state["onboarding_step"] = 2
                    st.rerun()
            with col2:
                if st.button("Next →", type="primary"):
                    st.session_state["onboarding_step"] = 4
                    st.rerun()

        elif step == 4:
            st.markdown("### 🚀 You're ready!")
            st.markdown("""
            Here's how to navigate Pacebird:

            **📡 API Data** — Live API-connected workflows
            &nbsp;&nbsp;📊 Performance & Insights · 📋 Portfolio Overview · 🎯 Live Campaigns · 📡 Cross-Channel

            **📁 Upload Report** — Drag-and-drop file analysis
            &nbsp;&nbsp;📊 Performance & Insights · 📋 Portfolio Overview · 📋 Live Campaigns · 📡 Cross-Channel

            **⚙️ Settings** — Brand memory, KPI targets, alert settings, scheduled reports

            *(Navigate to Performance & Insights and click **Generate Insights** to get started.)*
            """)
            col1, col2 = st.columns(2)
            with col1:
                if st.button("← Back"):
                    st.session_state["onboarding_step"] = 3
                    st.rerun()
            with col2:
                if st.button("Start exploring →", type="primary"):
                    p = load_prefs()
                    p["onboarding_complete"] = True
                    save_prefs(p)
                    st.session_state.pop("onboarding_step", None)
                    st.rerun()

    show_onboarding()

# ── Run the selected page ─────────────────────────────────────────────────────
pg.run()

# ── Sidebar Block 2: very bottom — rendered AFTER pg.run() so it appears
# ── below all nav links and below any page-specific sidebar content (Export)
with st.sidebar:
    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    dark_mode = st.toggle("🌙 Dark mode", value=st.session_state.get("dark_mode", False))
    st.session_state["dark_mode"] = dark_mode
