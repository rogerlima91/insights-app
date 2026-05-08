import streamlit as st

# ── Page config — called once here, not in individual page files ───────────────
st.set_page_config(page_title="Insights App", layout="wide")

# ── Navigation — dict syntax groups pages into sidebar sections ───────────────
# Brand Settings is nested under "Performance & Insights" as a sub-item.
# Streamlit doesn't support collapsible nav natively, so we use a section
# header + arrow prefix to create the visual sub-item effect.
pg = st.navigation({
    "Performance & Insights": [
        st.Page("pages/performance_insights.py", title="Performance & Insights"),
        st.Page("pages/brand_settings.py",       title="↳ Brand Settings"),
    ],
    "Operations": [
        st.Page("pages/live_campaigns.py", title="Live Campaigns"),
    ],
})
pg.run()
