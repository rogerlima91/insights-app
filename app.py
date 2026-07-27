import streamlit as st
import json
import os

# ── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="Pacebird", layout="wide")

# ── DESIGN SYSTEM LOCK — do not modify these values ─────────────────────────
# Primary: #7C3AED  Secondary: #2563EB  Success: #10B981
# Warning: #F59E0B  Danger: #EF4444
# Background Light: #F8F9FA  Background Dark: #0F1117
# Text Primary: #111827  Text Secondary: #6B7280

# ── Global CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Hide Streamlit default UI chrome */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display: none;}
    .block-container {padding-top: 1rem;}

    /* Base font */
    html, body, [class*="css"] {
        font-family: "Inter", system-ui, -apple-system, "Segoe UI", sans-serif;
        font-size: 15px;
    }
</style>
""", unsafe_allow_html=True)

# ── Dark mode CSS (applied when dark mode is active) ─────────────────────────
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
        [data-testid="baseButton-primary"] {
            background-color: #7C3AED !important;
        }
    </style>
    """, unsafe_allow_html=True)

# ── Sidebar: logo + dark/light toggle ────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🐦 Pacebird")
    st.markdown("---")

    # Dark/Light mode toggle
    dark_mode = st.toggle("🌙 Dark mode", value=st.session_state.get("dark_mode", False))
    st.session_state["dark_mode"] = dark_mode

# ── Onboarding flow ───────────────────────────────────────────────────────────
PREFS_FILE = "user_prefs.json"

def load_prefs():
    if os.path.exists(PREFS_FILE):
        with open(PREFS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_prefs(prefs):
    with open(PREFS_FILE, "w") as f:
        json.dump(prefs, f, indent=2)

prefs = load_prefs()

if not prefs.get("onboarding_complete", False):
    @st.dialog("Welcome to Pacebird 👋", width="large")
    def show_onboarding():
        step = st.session_state.get("onboarding_step", 1)

        if step == 1:
            st.markdown("### Welcome to Pacebird 👋")
            st.markdown("""
            **Pacebird** is your programmatic advertising insights platform.

            Upload DSP exports (DV360, TTD) to get instant performance charts,
            AI-generated insights, and PowerPoint reports ready for clients.
            """)
            if st.button("Get Started →", type="primary"):
                st.session_state["onboarding_step"] = 2
                st.rerun()

        elif step == 2:
            st.markdown("### Upload your first report")
            st.markdown("""
            Drag and drop your DSP CSV export to get started.

            **Accepted formats:**
            - DV360 CSV exports
            - The Trade Desk (TTD) CSV reports
            - Generic programmatic CSV files

            Find the upload panel in **Performance & Insights** (One-Off section).
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
            st.markdown("### Set up your first brand")
            st.markdown("""
            Brand Settings lets you store context about each advertiser —
            objectives, KPIs, and notes — so AI insights are tailored to your clients.

            Navigate to **Settings → Brand Settings** to set up your brands.
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
            st.markdown("### You're ready! 🚀")
            st.markdown("""
            Here's how to navigate Pacebird:

            **Ongoing** — Live API-connected workflows
            &nbsp;&nbsp;📊 Performance & Insights · 📋 Portfolio Overview · 🎯 Live Campaigns

            **One-Off** — Drag-and-drop file analysis
            &nbsp;&nbsp;📊 Performance & Insights · ⏱ Pacing Checker · 📡 Telco

            **Settings** — Brand memory, KPI targets, scheduled reports
            """)
            if st.button("Start exploring →", type="primary"):
                prefs_data = load_prefs()
                prefs_data["onboarding_complete"] = True
                save_prefs(prefs_data)
                st.session_state.pop("onboarding_step", None)
                st.rerun()

    show_onboarding()

# ── Navigation ────────────────────────────────────────────────────────────────
pg = st.navigation({
    "Ongoing": [
        st.Page("pages/ongoing_performance.py",   title="Performance & Insights"),
        st.Page("pages/portfolio_overview.py",     title="Portfolio Overview"),
        st.Page("pages/live_campaigns.py",         title="Live Campaigns"),
    ],
    "One-Off": [
        st.Page("pages/performance_insights.py",   title="Performance & Insights"),
        st.Page("pages/pacing_checker.py",         title="Pacing Checker"),
        st.Page("pages/telco_cross_channel.py",    title="Cross-Channel Dashboard"),
        st.Page("pages/telco_budget_optimiser.py", title="Channel Budget Optimiser"),
    ],
    "Settings": [
        st.Page("pages/brand_settings.py",         title="Brand Settings"),
    ],
})
pg.run()
