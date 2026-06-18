import streamlit as st

# ── Page config — called once here, not in individual page files ───────────────
st.set_page_config(page_title="Insights App", layout="wide")

# ── Navigation ────────────────────────────────────────────────────────────────
pg = st.navigation({
    "Reporting": [
        st.Page("pages/performance_insights.py",  title="Performance & Insights"),
    ],
    "Operations": [
        st.Page("pages/live_campaigns.py",         title="Live Campaigns"),
    ],
    "Planning": [
        st.Page("pages/budget_allocation.py",      title="Budget Allocation Recommender"),
    ],
    "Settings": [
        st.Page("pages/brand_settings.py",         title="Brand Settings"),
    ],
    # "Retail Media": [
    #     st.Page("pages/uber_roi_calculator.py",    title="Uber Ads ROI Calculator"),
    # ],
    "Telco": [
        st.Page("pages/telco_cross_channel.py",    title="Cross-Channel Dashboard"),
        st.Page("pages/telco_budget_optimiser.py", title="Channel Budget Optimiser"),
    ],
})
pg.run()
