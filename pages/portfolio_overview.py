import streamlit as st
import pandas as pd
import plotly.express as px
import json
import os
import random
from datetime import date, timedelta

# ── Global CSS ─────────────────────────────────────────────────────────────────
# STYLE LOCK: Do not remove or modify this CSS block.
st.markdown("""
<style>
    /* Hide Streamlit chrome */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display: none;}
    .block-container {padding-top: 1rem;}

    html, body, [class*="css"] {
        font-family: "Inter", system-ui, -apple-system, "Segoe UI", sans-serif;
        font-size: 15px;
        color: #374151;
    }
    .stApp { background-color: #F3F4F6; }
    h1, h2, h3, h4, h5, h6 {
        font-weight: 700 !important;
        color: #111827 !important;
    }
    h2, h3 {
        margin-top: 2rem !important;
        padding-top: 0.25rem !important;
        border-bottom: none !important;
        padding-bottom: 0 !important;
        border-left: none !important;
        padding-left: 0 !important;
    }
    [data-testid="metric-container"] {
        background: #FFFFFF;
        border: none;
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        border-top: 4px solid #7C3AED;
    }
    .element-container:has([data-testid="stPlotlyChart"]) {
        background: #FFFFFF;
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    }
    .stButton > button[kind="primary"],
    [data-testid="baseButton-primary"] {
        background-color: #7C3AED !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }
</style>
""", unsafe_allow_html=True)

# ── Page header ────────────────────────────────────────────────────────────────
st.markdown("# 📋 Portfolio Overview")
st.markdown("Summary view across all advertisers in your uploaded data.")

# ── Helper: load KPI targets ───────────────────────────────────────────────────
def load_kpi_targets(brand_name):
    """Load KPI targets for a brand from brand_memory.json."""
    try:
        with open("brand_memory.json", "r") as f:
            bm = json.load(f)
    except Exception:
        return {}
    for key, val in bm.items():
        if key.lower() in brand_name.lower() or brand_name.lower() in key.lower():
            return val.get("kpi_targets", {})
    return {}

def rag_status(actual, target, higher_is_better=True):
    """Return RAG colour hex and label."""
    if not target or target == 0 or actual is None:
        return None, "—"
    pct = (actual - target) / target * 100
    if higher_is_better:
        if pct >= -10: return "#10B981", "🟢"
        elif pct >= -25: return "#F59E0B", "🟡"
        else: return "#EF4444", "🔴"
    else:
        if pct <= 10: return "#10B981", "🟢"
        elif pct <= 25: return "#F59E0B", "🟡"
        else: return "#EF4444", "🔴"

# ── Mock data for API/Live mode ─────────────────────────────────────────────────
@st.cache_data
def _generate_portfolio_mock_data():
    """Generate 30 days of mock data for Woolworths, CBA, and Toyota Australia."""
    rng = random.Random(42)
    today = date(2026, 7, 28)
    start = today - timedelta(days=29)

    CAMPAIGNS = [
        {"campaign": "Woolworths",         "imps_r": (110000, 200000), "cpm_r": (5.0, 7.5),  "ctr_r": (0.003, 0.006)},
        {"campaign": "Commonwealth Bank",  "imps_r": (50000,  110000), "cpm_r": (13.0, 20.0), "ctr_r": (0.002, 0.005)},
        {"campaign": "Toyota Australia",   "imps_r": (80000,  160000), "cpm_r": (9.0, 14.0),  "ctr_r": (0.003, 0.006)},
    ]

    rows = []
    for day_offset in range(30):
        current_date = start + timedelta(days=day_offset)
        for camp in CAMPAIGNS:
            imps = rng.randint(*camp["imps_r"])
            ctr  = rng.uniform(*camp["ctr_r"])
            cpm  = rng.uniform(*camp["cpm_r"])
            clicks    = max(round(imps * ctr), 1)
            spend_usd = round(imps / 1000 * cpm, 2)
            conversions = max(round(clicks * rng.uniform(0.02, 0.07)), 0)
            rows.append({
                "campaign":    camp["campaign"],
                "impressions": imps,
                "clicks":      clicks,
                "spend_usd":   spend_usd,
                "conversions": conversions,
            })

    return pd.DataFrame(rows)

# ── Check for shared data (set by Performance & Insights in API mode) ───────────
shared_df = st.session_state.get("portfolio_df", None)

# In API/Live mode, fall back to mock data if no shared data yet
if shared_df is None:
    shared_df = _generate_portfolio_mock_data()
    st.session_state["portfolio_df"] = shared_df

st.markdown("---")

# ── Main portfolio analysis ────────────────────────────────────────────────────
if True:
    df = shared_df.copy()

    if "campaign" not in df.columns:
        st.warning("No 'campaign' / 'advertiser' column found in the data. Cannot build portfolio view.")
    else:
        brands = df["campaign"].dropna().unique()

        # ── Summary metrics ──────────────────────────────────────────────────────
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        total_spend = df["spend_usd"].sum() if "spend_usd" in df.columns else 0
        total_imps = df["impressions"].sum() if "impressions" in df.columns else 0
        total_clicks = df["clicks"].sum() if "clicks" in df.columns else 0

        with col_m1:
            st.metric("Total Advertisers", len(brands))
        with col_m2:
            st.metric("Total Spend", f"${total_spend:,.0f}")
        with col_m3:
            st.metric("Total Impressions", f"{total_imps:,.0f}")
        with col_m4:
            overall_ctr = (total_clicks / total_imps * 100) if total_imps > 0 else 0
            st.metric("Portfolio CTR", f"{overall_ctr:.2f}%")

        st.markdown("---")

        # ── Per-advertiser summary table ─────────────────────────────────────────
        st.markdown("## 📊 Advertiser Summary")

        rows = []
        for brand in brands:
            brand_df = df[df["campaign"] == brand]
            imps = brand_df["impressions"].sum() if "impressions" in brand_df.columns else 0
            clicks = brand_df["clicks"].sum() if "clicks" in brand_df.columns else 0
            spend = brand_df["spend_usd"].sum() if "spend_usd" in brand_df.columns else 0
            convs = brand_df["conversions"].sum() if "conversions" in brand_df.columns else 0

            ctr = (clicks / imps * 100) if imps > 0 else 0
            cpm = (spend / imps * 1000) if imps > 0 else 0
            cpa = (spend / convs) if convs > 0 else 0

            # RAG status from KPI targets
            targets = load_kpi_targets(str(brand))
            rag_overall = "—"
            if targets:
                statuses = []
                if targets.get("target_ctr") and imps > 0:
                    _, s = rag_status(ctr, targets["target_ctr"], higher_is_better=True)
                    statuses.append(s)
                if targets.get("target_cpm") and imps > 0:
                    _, s = rag_status(cpm, targets["target_cpm"], higher_is_better=False)
                    statuses.append(s)
                if targets.get("target_cpa") and convs > 0:
                    _, s = rag_status(cpa, targets["target_cpa"], higher_is_better=False)
                    statuses.append(s)
                if statuses:
                    # Worst status wins
                    if "🔴" in statuses:
                        rag_overall = "🔴"
                    elif "🟡" in statuses:
                        rag_overall = "🟡"
                    else:
                        rag_overall = "🟢"

            rows.append({
                "Advertiser": brand,
                "Total Spend": f"${spend:,.0f}",
                "Impressions": f"{imps:,.0f}",
                "CTR": f"{ctr:.2f}%",
                "CPM": f"${cpm:.2f}",
                "CPA": f"${cpa:.2f}" if convs > 0 else "—",
                "RAG Status": rag_overall,
            })

        summary_df = pd.DataFrame(rows)

        # Clickable filter
        st.markdown("*Click an advertiser name to filter Performance & Insights to that brand.*")

        selected_rows = st.dataframe(
            summary_df,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
        )

        # If a row is selected, set a filter in session state
        if selected_rows and selected_rows.get("selection", {}).get("rows"):
            selected_idx = selected_rows["selection"]["rows"][0]
            selected_brand = summary_df.iloc[selected_idx]["Advertiser"]
            st.session_state["portfolio_brand_filter"] = selected_brand
            st.success(f"✅ Filter set: Performance & Insights will show **{selected_brand}** — navigate there to view.")

        st.markdown("---")

        # ── Portfolio spend chart ────────────────────────────────────────────────
        st.markdown("## 💰 Spend by Advertiser")

        if "spend_usd" in df.columns:
            spend_by_brand = df.groupby("campaign")["spend_usd"].sum().reset_index()
            spend_by_brand.columns = ["Advertiser", "Spend"]
            spend_by_brand = spend_by_brand.sort_values("Spend", ascending=False)

            fig_spend = px.bar(
                spend_by_brand, x="Advertiser", y="Spend",
                color="Spend",
                color_continuous_scale=["#C4B5FD", "#7C3AED", "#4C1D95"],
                title="Total Spend by Advertiser"
            )
            fig_spend.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_family="Inter, sans-serif",
                showlegend=False,
                coloraxis_showscale=False,
                height=400,
                yaxis_title="Spend (USD)",
                xaxis_title="",
            )
            fig_spend.update_traces(marker_line_width=0)
            st.plotly_chart(fig_spend, use_container_width=True)

        st.markdown("---")

        # ── RAG Heatmap ──────────────────────────────────────────────────────────
        st.markdown("## 🗺️ KPI RAG Heatmap")
        st.caption("Shows RAG status per metric per advertiser. Only shown for brands with KPI targets configured in Brand Settings.")

        heatmap_rows = []
        for brand in brands:
            targets = load_kpi_targets(str(brand))
            if not targets:
                continue

            brand_df = df[df["campaign"] == brand]
            imps = brand_df["impressions"].sum() if "impressions" in brand_df.columns else 0
            clicks = brand_df["clicks"].sum() if "clicks" in brand_df.columns else 0
            spend = brand_df["spend_usd"].sum() if "spend_usd" in brand_df.columns else 0
            convs = brand_df["conversions"].sum() if "conversions" in brand_df.columns else 0

            ctr = (clicks / imps * 100) if imps > 0 else 0
            cpm = (spend / imps * 1000) if imps > 0 else 0
            cpa = (spend / convs) if convs > 0 else 0

            row = {"Brand": brand}

            if targets.get("target_ctr"):
                _, s = rag_status(ctr, targets["target_ctr"], True)
                row["CTR"] = s
            if targets.get("target_cpm"):
                _, s = rag_status(cpm, targets["target_cpm"], False)
                row["CPM"] = s
            if targets.get("target_cpa") and convs > 0:
                _, s = rag_status(cpa, targets["target_cpa"], False)
                row["CPA"] = s
            if targets.get("target_roas"):
                row["ROAS"] = "⚪"  # No ROAS in data by default
            if targets.get("target_vtr"):
                row["VTR"] = "⚪"  # No VTR without video data

            heatmap_rows.append(row)

        if heatmap_rows:
            heatmap_df = pd.DataFrame(heatmap_rows).set_index("Brand").fillna("—")
            st.dataframe(heatmap_df, use_container_width=True)
        else:
            st.info("No brands have KPI targets configured. Set targets in **Settings → Brand Settings → KPI Targets**.")

        st.markdown("---")

        # Clear data button
        if st.button("🗑 Clear uploaded data", key="portfolio_clear"):
            st.session_state.pop("portfolio_df", None)
            st.rerun()

print("Done. Portfolio Overview page loaded.")
