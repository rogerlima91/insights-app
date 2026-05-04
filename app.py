import streamlit as st

# ── Page config — called once here, not in individual page files ───────────────
st.set_page_config(page_title="Insights App", layout="wide")

# ── Navigation — defines sidebar labels exactly as shown ──────────────────────
pg = st.navigation([
    st.Page("pages/performance_insights.py", title="Performance & Insights"),
    st.Page("pages/brand_settings.py",       title="Brand Settings"),
    st.Page("pages/live_campaigns.py",        title="Live Campaigns"),
])
pg.run()
