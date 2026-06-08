import streamlit as st

# ── Page config — called once here, not in individual page files ───────────────
st.set_page_config(page_title="Insights App", layout="wide")

# ── Navigation ────────────────────────────────────────────────────────────────
pg = st.navigation({
    "Reporting": [
        st.Page("pages/performance_insights.py",  title="Performance & Insights"),
        st.Page("pages/attribution_analysis.py",  title="Attribution Analysis"),
    ],
    "Operations": [
        st.Page("pages/live_campaigns.py",         title="Live Campaigns"),
    ],
    "Planning": [
        st.Page("pages/budget_allocation.py",      title="Budget Allocation Recommender"),
        st.Page("pages/forecasting_tool.py",       title="Feasibility Checker"),
    ],
    "Settings": [
        st.Page("pages/brand_settings.py",         title="Brand Settings"),
    ],
})
pg.run()
