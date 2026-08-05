import streamlit as st
import json
import os

# ── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="Pacebird", layout="wide", initial_sidebar_state="expanded")

# ── DESIGN SYSTEM LOCK — do not modify these values ─────────────────────────
# Primary: #7C3AED  Secondary: #2563EB  Success: #10B981
# Warning: #F59E0B  Danger: #EF4444
# Background Light: #F8F9FA  Background Dark: #0F1117
# Text Primary: #111827  Text Secondary: #6B7280

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
    "full_access":  {"label": "✨ Full Access",  "visible": ["API Data", "Upload Report"]},
    "api_only":     {"label": "📡 API Mode",     "visible": ["API Data"]},
    "upload_only":  {"label": "📁 Upload Mode",  "visible": ["Upload Report"]},
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

nav_sections = {}
if "API Data" in visible_sections:
    nav_sections["📡 API DATA"] = API_DATA_PAGES
if "Upload Report" in visible_sections:
    nav_sections["📁 UPLOAD REPORT"] = UPLOAD_REPORT_PAGES

pg = st.navigation(nav_sections)

# ── Session state and onboarding step ────────────────────────────────────────
st.session_state["current_tier"] = current_tier
ob_step = st.session_state.get("onboarding_step", 1)

# ── Global CSS (Change 1: modern SaaS redesign) ───────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* Hide Streamlit default UI chrome */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    [data-testid="stHeader"] {
        background: transparent;
        height: 0;
        min-height: 0;
    }
    [data-testid="stHeader"] > * {
        display: none;
    }
    [data-testid="stToolbar"] {
        display: none;
    }
    [data-testid="stDecoration"] {
        display: none;
    }
    .stDeployButton {display: none;}
    .block-container {padding-top: 1rem;}

    /* Base font — Inter from Google Fonts */
    html, body, [class*="css"] {
        font-family: "Inter", system-ui, -apple-system, "Segoe UI", sans-serif;
        font-size: 15px;
    }

    /* ── Metric cards: 16px radius, 24px padding, lighter background ── */
    [data-testid="metric-container"] {
        border-radius: 16px !important;
        padding: 24px !important;
        background: #FAFAFA !important;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06) !important;
        border: none !important;
    }

    /* ── Chart containers: 20px padding, 16px radius ─────────────── */
    .element-container:has([data-testid="stPlotlyChart"]) {
        border-radius: 16px !important;
        padding: 20px !important;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06) !important;
    }

    /* ── Inputs and selectboxes: 10px radius ─────────────────────── */
    div[data-baseweb="select"] > div,
    div[data-baseweb="input"] {
        border-radius: 10px !important;
    }

    /* ── Buttons: 10px radius, smooth hover ──────────────────────── */
    .stButton > button {
        border-radius: 10px !important;
        transition: all 0.15s ease !important;
    }
    .stButton > button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.12) !important;
    }

    /* ── Tables: rounded, no hard border ─────────────────────────── */
    [data-testid="stDataFrame"] {
        border-radius: 16px !important;
        overflow: hidden !important;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06) !important;
        border: none !important;
    }
    /* Table row hover highlight */
    [data-testid="stDataFrame"] tr:hover > td {
        background-color: rgba(124,58,237,0.04) !important;
    }

    /* ── Sidebar: shadow instead of hard border ───────────────────── */
    section[data-testid="stSidebar"] {
        box-shadow: 2px 0 16px rgba(0,0,0,0.08) !important;
    }
    section[data-testid="stSidebar"] > div:first-child {
        padding-top: 0 !important;
    }

    /* ── Sidebar nav section headers (API DATA / UPLOAD REPORT labels) ── */
    section[data-testid="stSidebar"] [data-testid="stSidebarNavSeparator"] span,
    section[data-testid="stSidebar"] .st-emotion-cache-1rtdyuf,
    section[data-testid="stSidebar"] [data-testid="stSidebarNavItems"] > div > p {
        font-size: 11px !important;
        font-weight: 700 !important;
        letter-spacing: 1.5px !important;
        color: #7C3AED !important;
        text-transform: uppercase !important;
        padding-top: 12px !important;
    }

    /* ── Onboarding highlight class ─────────────────────────────── */
    .onboarding-highlight {
        border: 3px solid #7C3AED !important;
        border-radius: 8px !important;
        animation: pulse-border 2s infinite !important;
    }
    @keyframes pulse-border {
        0%   { box-shadow: 0 0 0 0   rgba(124,58,237,0.4); }
        70%  { box-shadow: 0 0 0 10px rgba(124,58,237,0);   }
        100% { box-shadow: 0 0 0 0   rgba(124,58,237,0);   }
    }
</style>
""", unsafe_allow_html=True)

# ── Step-specific onboarding highlight CSS ───────────────────────────────────
if not prefs.get("onboarding_complete", False):
    if ob_step == 2:
        # Step 2: highlight file upload area
        st.markdown("""
        <style>
        [data-testid="stFileUploader"] {
            border: 3px solid #7C3AED !important;
            border-radius: 8px !important;
            animation: pulse-border 2s infinite !important;
        }
        </style>""", unsafe_allow_html=True)
    elif ob_step == 3:
        # Step 3: highlight Settings nav items in sidebar
        st.markdown("""
        <style>
        section[data-testid="stSidebar"] a[href*="settings"] {
            border: 2px solid #7C3AED !important;
            border-radius: 6px !important;
            animation: pulse-border 2s infinite !important;
        }
        </style>""", unsafe_allow_html=True)
    elif ob_step == 4:
        # Step 4: highlight Performance & Insights nav links
        st.markdown("""
        <style>
        section[data-testid="stSidebar"] a[href*="performance"] {
            border: 2px solid #7C3AED !important;
            border-radius: 6px !important;
            animation: pulse-border 2s infinite !important;
        }
        </style>""", unsafe_allow_html=True)

# ── Dark mode CSS ────────────────────────────────────────────────────────────
if st.session_state.get("dark_mode", False):
    st.markdown("""
    <style>
        .stApp { background-color: #0F1117 !important; }
        section[data-testid="stSidebar"] { background-color: #1A1D27 !important; }
        .stApp [data-testid="stMarkdownContainer"],
        .stApp p, .stApp label, .stApp span { color: #FAFAFA !important; }
        [data-testid="metric-container"] { background: #1E2130 !important; }
        .element-container:has([data-testid="stPlotlyChart"]) { background: #1E2130 !important; }
        h1, h2, h3, h4, h5, h6 { color: #FAFAFA !important; }
        .stButton > button[kind="primary"],
        [data-testid="baseButton-primary"] { background-color: #7C3AED !important; }
    </style>
    """, unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    # Pacebird logo — absolute first element in sidebar
    st.markdown("""
    <div style="padding: 20px 16px 12px 16px;
                border-bottom: 1px solid #E5E7EB;
                margin-bottom: 12px;">
        <div style="font-size: 24px; font-weight: 800;
                    color: #7C3AED; letter-spacing: -0.5px;">
            🐦 Pacebird
        </div>
        <div style="font-size: 12px; color: #6B7280;
                    margin-top: 2px;">
            Programmatic Intelligence
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Dark/Light mode toggle
    dark_mode = st.toggle("🌙 Dark mode", value=st.session_state.get("dark_mode", False))
    st.session_state["dark_mode"] = dark_mode

    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

    # Tier badge
    st.markdown(
        f"<div style='font-size:11px;color:#6B7280;padding:4px 0 2px 0;'>{tier_label}</div>",
        unsafe_allow_html=True
    )

# ── Onboarding flow ───────────────────────────────────────────────────────────
if not prefs.get("onboarding_complete", False):
    @st.dialog("Welcome to Pacebird 👋", width="large")
    def show_onboarding():
        step = st.session_state.get("onboarding_step", 1)

        # Floating step indicator
        st.markdown(f"""
        <div style="
            position:fixed; bottom:24px; right:24px;
            background:#7C3AED; color:#fff;
            padding:8px 16px; border-radius:20px;
            font-size:13px; font-weight:600;
            box-shadow: 0 4px 12px rgba(124,58,237,0.4);
            z-index:9999;">
            Step {step} of 4
        </div>
        """, unsafe_allow_html=True)

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

            *(The file upload area is now highlighted in purple on that page.)*
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

            *(The Settings nav link is now highlighted in purple.)*
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
