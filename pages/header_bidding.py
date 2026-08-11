import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from utils.design_system import get_css, PRIMARY, SECONDARY, SUCCESS, WARNING, DANGER, WHITE, TEXT_SEC, TEXT_PRI, CHART_PALETTE

# ── Apply Pacebird design system CSS ──────────────────────────────────────────
# STYLE LOCK: Pacebird design system — primary #F5A623 orange, secondary #1B2A4A navy, font Poppins.
st.markdown(get_css(), unsafe_allow_html=True)

# ── Mock data generator ───────────────────────────────────────────────────────
# Generates header bidding stats per publisher × demand partner.
# Diagnostic thresholds:
#   "Price issue"       — bid_rate > 40% AND win_rate < 20%
#   "Integration issue" — bid_rate < 20%
#   "Latency issue"     — timeout_rate > 15%
#   "Healthy"           — none of the above
@st.cache_data
def generate_hb_data():
    rng = np.random.default_rng(seed=99)

    publishers = ["Nine.com.au", "news.com.au", "Domain", "realestate.com.au", "Stuff NZ"]
    partners   = ["Teads", "Magnite", "PubMatic", "Index Exchange", "OpenX", "Xandr"]

    # Base rates per partner — vary by "personality"
    partner_profiles = {
        "Teads":         {"bid_rate": 55, "win_rate": 38, "avg_bid_ecpm": 22.5, "timeout_rate":  4},
        "Magnite":       {"bid_rate": 65, "win_rate": 42, "avg_bid_ecpm": 18.0, "timeout_rate":  6},
        "PubMatic":      {"bid_rate": 60, "win_rate": 15, "avg_bid_ecpm": 12.5, "timeout_rate":  8},  # price issue
        "Index Exchange":{"bid_rate": 14, "win_rate": 10, "avg_bid_ecpm": 16.0, "timeout_rate":  5},  # integration issue
        "OpenX":         {"bid_rate": 48, "win_rate": 32, "avg_bid_ecpm": 14.0, "timeout_rate": 20},  # latency issue
        "Xandr":         {"bid_rate": 70, "win_rate": 45, "avg_bid_ecpm": 20.0, "timeout_rate":  7},
    }

    # Revenue base (AUD) per publisher × partner — proportional to win rate × bid eCPM
    revenue_base = {
        "Nine.com.au":       {"Teads": 12500, "Magnite": 18000, "PubMatic": 5000, "Index Exchange": 3200, "OpenX": 9000, "Xandr": 22000},
        "news.com.au":       {"Teads": 11000, "Magnite": 15500, "PubMatic": 4500, "Index Exchange": 2800, "OpenX": 8200, "Xandr": 19500},
        "Domain":            {"Teads": 5500,  "Magnite": 7000,  "PubMatic": 2200, "Index Exchange": 1400, "OpenX": 3800, "Xandr": 9500},
        "realestate.com.au": {"Teads": 5000,  "Magnite": 6500,  "PubMatic": 2000, "Index Exchange": 1200, "OpenX": 3500, "Xandr": 8800},
        "Stuff NZ":          {"Teads": 3200,  "Magnite": 4500,  "PubMatic": 1500, "Index Exchange":  900, "OpenX": 2200, "Xandr": 5800},
    }

    rows = []
    for pub in publishers:
        for partner in partners:
            profile = partner_profiles[partner]
            # Add publisher-specific noise to rates
            bid_r    = round(min(max(rng.normal(profile["bid_rate"],    4.0),  5.0), 95.0), 1)
            win_r    = round(min(max(rng.normal(profile["win_rate"],    3.0),  2.0), bid_r), 1)
            bid_ecpm = round(max(rng.normal(profile["avg_bid_ecpm"],   1.5),  3.0), 2)
            to_r     = round(min(max(rng.normal(profile["timeout_rate"], 2.0), 0.5), 40.0), 1)
            rev      = round(revenue_base[pub][partner] * rng.normal(1.0, 0.08), 0)

            rows.append({
                "publisher":     pub,
                "partner":       partner,
                "bid_rate":      bid_r,
                "win_rate":      win_r,
                "avg_bid_ecpm":  bid_ecpm,
                "timeout_rate":  to_r,
                "revenue_aud":   rev,
            })

    return pd.DataFrame(rows)


def diagnose(row):
    """
    Classify each demand partner row into one of four diagnostic states.
    Mirrors the Delivery Troubleshooter pattern used in the buy-side pages.
    """
    issues = []

    # Integration issue — partner is barely bidding
    if row["bid_rate"] < 20:
        issues.append("Integration issue")

    # Price issue — bidding a lot but winning very little (floor price mismatch)
    if row["bid_rate"] > 40 and row["win_rate"] < 20:
        issues.append("Price issue")

    # Latency issue — high timeout rate indicates slow response
    if row["timeout_rate"] > 15:
        issues.append("Latency issue")

    if not issues:
        return "Healthy", "🟢", SUCCESS
    if len(issues) == 1:
        label = issues[0]
        return label, "🟡", WARNING
    # Multiple issues
    return " + ".join(issues), "🔴", DANGER


def health_score(row):
    """
    Compute a 0-100 health score for a demand partner.
    Higher is better. Based on win rate (40%), bid rate (30%), timeout (30%).
    """
    win_score     = min(row["win_rate"] / 50.0, 1.0) * 40    # 50% win rate = full points
    bid_score     = min(row["bid_rate"] / 70.0, 1.0) * 30    # 70% bid rate = full points
    timeout_score = max(0, 1 - row["timeout_rate"] / 30.0) * 30  # 0% timeout = full points
    return round(win_score + bid_score + timeout_score)


# ── Page header ───────────────────────────────────────────────────────────────
st.markdown("# 🔄 Header Bidding")
st.markdown("Demand partner diagnostics and health monitoring for ANZ publisher header bidding setups.")

# ── Load data ─────────────────────────────────────────────────────────────────
df_all = generate_hb_data()

# ── Filter ────────────────────────────────────────────────────────────────────
pub_options  = ["All Publishers"] + sorted(df_all["publisher"].unique().tolist())
selected_pub = st.selectbox("Publisher", pub_options, key="hb_pub")

df = df_all if selected_pub == "All Publishers" else df_all[df_all["publisher"] == selected_pub]

# If "All Publishers", aggregate across publishers per partner
if selected_pub == "All Publishers":
    df = (
        df.groupby("partner")
        .agg(
            bid_rate=("bid_rate", "mean"),
            win_rate=("win_rate", "mean"),
            avg_bid_ecpm=("avg_bid_ecpm", "mean"),
            timeout_rate=("timeout_rate", "mean"),
            revenue_aud=("revenue_aud", "sum"),
        )
        .reset_index()
    )
    # Round averages
    df["bid_rate"]     = df["bid_rate"].round(1)
    df["win_rate"]     = df["win_rate"].round(1)
    df["avg_bid_ecpm"] = df["avg_bid_ecpm"].round(2)
    df["timeout_rate"] = df["timeout_rate"].round(1)

# Add diagnostic columns
df = df.copy()
df[["diagnosis", "rag_icon", "rag_color"]] = df.apply(
    lambda r: pd.Series(diagnose(r)), axis=1
)
df["health_score"] = df.apply(health_score, axis=1)

# ── Summary cards ─────────────────────────────────────────────────────────────
healthy_count  = (df["diagnosis"] == "Healthy").sum()
issue_count    = len(df) - healthy_count
avg_bid        = df["bid_rate"].mean()
avg_win        = df["win_rate"].mean()
total_rev      = df["revenue_aud"].sum()

st.markdown("### Overview")
s1, s2, s3, s4 = st.columns(4)
with s1:
    st.metric("Healthy Partners", f"{healthy_count} / {len(df)}")
with s2:
    st.metric("Partners with Issues", str(issue_count))
with s3:
    st.metric("Avg Bid Rate", f"{avg_bid:.1f}%")
with s4:
    st.metric("Total Revenue", f"A${total_rev:,.0f}")

# ── Demand partner table ───────────────────────────────────────────────────────
st.markdown("### Demand Partner Performance")
st.caption("Columns: partner metrics, health score (0–100), and automated diagnosis. Click a column header to sort.")

# Build display table
display = df[[
    "partner", "bid_rate", "win_rate", "avg_bid_ecpm",
    "timeout_rate", "revenue_aud", "health_score", "rag_icon", "diagnosis"
]].copy()

display["bid_rate"]     = display["bid_rate"].apply(lambda x: f"{x:.1f}%")
display["win_rate"]     = display["win_rate"].apply(lambda x: f"{x:.1f}%")
display["avg_bid_ecpm"] = display["avg_bid_ecpm"].apply(lambda x: f"A${x:.2f}")
display["timeout_rate"] = display["timeout_rate"].apply(lambda x: f"{x:.1f}%")
display["revenue_aud"]  = display["revenue_aud"].apply(lambda x: f"A${x:,.0f}")
display["status"]       = display["rag_icon"] + " " + display["diagnosis"]

display = display.rename(columns={
    "partner":       "Partner",
    "bid_rate":      "Bid Rate %",
    "win_rate":      "Win Rate %",
    "avg_bid_ecpm":  "Avg Bid eCPM",
    "timeout_rate":  "Timeout Rate %",
    "revenue_aud":   "Revenue",
    "health_score":  "Health Score",
    "status":        "Diagnosis",
})

st.dataframe(
    display[["Partner", "Bid Rate %", "Win Rate %", "Avg Bid eCPM", "Timeout Rate %", "Revenue", "Health Score", "Diagnosis"]],
    use_container_width=True,
    hide_index=True,
)

# ── Partner health cards with top issues ─────────────────────────────────────
st.markdown("### Partner Health Breakdown")
st.caption("Each card shows the health score and top diagnostic flags. Follows the Delivery Troubleshooter pattern.")

# Sort by health score descending so best partners show first
df_sorted = df.sort_values("health_score", ascending=False)

# Render 3 cards per row
cols_per_row = 3
rows_needed  = -(-len(df_sorted) // cols_per_row)  # ceiling division

for row_i in range(rows_needed):
    card_cols = st.columns(cols_per_row)
    for col_i in range(cols_per_row):
        idx = row_i * cols_per_row + col_i
        if idx >= len(df_sorted):
            break
        partner_row = df_sorted.iloc[idx]
        score       = int(partner_row["health_score"])
        rag         = partner_row["rag_icon"]
        diag        = partner_row["diagnosis"]
        clr         = partner_row["rag_color"]

        # Build top 3 issues text
        issue_lines = []
        if partner_row.get("bid_rate", 100) < 20:
            issue_lines.append("▸ Low bid rate — check adapter config")
        if partner_row.get("bid_rate", 0) > 40 and partner_row.get("win_rate", 100) < 20:
            issue_lines.append("▸ Price mismatch — review floor prices")
        if partner_row.get("timeout_rate", 0) > 15:
            issue_lines.append("▸ High timeouts — check latency / endpoint")
        if not issue_lines:
            issue_lines.append("▸ All metrics within healthy thresholds")

        issues_html = "<br>".join(issue_lines[:3])

        with card_cols[col_i]:
            # Use raw HTML for the card to control styling precisely
            partner_name = partner_row.get("partner", partner_row.name if isinstance(partner_row.name, str) else "Partner")
            st.markdown(
                f"""<div style="background:white;border-radius:12px;padding:16px;
                     box-shadow:0 2px 12px rgba(0,0,0,0.06);
                     border-top:4px solid {clr};margin-bottom:8px;">
                  <div style="font-weight:700;font-size:15px;color:#111827;">{rag} {partner_name}</div>
                  <div style="font-size:22px;font-weight:700;color:{clr};margin:6px 0;">
                    {score}/100
                  </div>
                  <div style="font-size:11px;font-weight:600;color:#6B7280;text-transform:uppercase;
                       letter-spacing:0.05em;margin-bottom:6px;">{diag}</div>
                  <div style="font-size:12px;color:#374151;line-height:1.6;">{issues_html}</div>
                </div>""",
                unsafe_allow_html=True,
            )

# ── Bid rate vs win rate scatter chart ────────────────────────────────────────
st.markdown("### Bid Rate vs Win Rate")
st.caption("Ideal partners appear top-right (high bid AND win rate). Partners far left of the diagonal have a price or integration issue.")

# Use the raw numeric df for charts
df_chart = df_all if selected_pub == "All Publishers" else df_all[df_all["publisher"] == selected_pub]
if selected_pub == "All Publishers":
    df_chart = (
        df_all.groupby("partner")
        .agg(bid_rate=("bid_rate", "mean"), win_rate=("win_rate", "mean"),
             revenue_aud=("revenue_aud", "sum"), timeout_rate=("timeout_rate", "mean"))
        .reset_index()
    )

df_chart = df_chart.copy()
df_chart[["diag_label", "_icon", "_clr"]] = df_chart.apply(lambda r: pd.Series(diagnose(r)), axis=1)

fig_scatter = px.scatter(
    df_chart,
    x="bid_rate",
    y="win_rate",
    color="diag_label",
    size="revenue_aud",
    text="partner",
    color_discrete_map={
        "Healthy":            SUCCESS,
        "Price issue":        WARNING,
        "Integration issue":  DANGER,
        "Latency issue":      "#A855F7",   # purple for latency
        # multi-issue combos also map — default to DANGER
    },
    labels={
        "bid_rate":   "Bid Rate (%)",
        "win_rate":   "Win Rate (%)",
        "diag_label": "Diagnosis",
    },
    size_max=40,
)
fig_scatter.update_traces(textposition="top center", textfont_size=11)

# Reference diagonal — equal bid and win rate
fig_scatter.add_shape(
    type="line", x0=0, y0=0, x1=100, y1=100,
    line=dict(color="#CBD5E1", width=1, dash="dot"),
)
fig_scatter.add_annotation(
    x=60, y=62, text="Bid rate = Win rate",
    showarrow=False, font=dict(size=10, color="#9CA3AF"), textangle=-30,
)

fig_scatter.update_layout(
    plot_bgcolor="white",
    paper_bgcolor="white",
    font=dict(family="Poppins, sans-serif", size=12),
    xaxis=dict(title="Bid Rate (%)", range=[0, 100], ticksuffix="%"),
    yaxis=dict(title="Win Rate (%)", range=[0, 100], ticksuffix="%"),
    margin=dict(t=20, b=60, l=60, r=20),
    height=400,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
)
st.plotly_chart(fig_scatter, use_container_width=True)

# ── Timeout rate bar chart with threshold reference line ───────────────────────
st.markdown("### Timeout Rate by Partner")
st.caption("The dashed line marks the 15% threshold — partners above this are flagged as a 'Latency issue'.")

timeout_df = df_chart[["partner", "timeout_rate"]].sort_values("timeout_rate", ascending=False)

# Assign color based on whether timeout_rate exceeds 15%
timeout_df = timeout_df.copy()
timeout_df["color"] = timeout_df["timeout_rate"].apply(lambda x: DANGER if x > 15 else SECONDARY)

fig_timeout = go.Figure()
fig_timeout.add_trace(go.Bar(
    x=timeout_df["partner"],
    y=timeout_df["timeout_rate"],
    marker_color=timeout_df["color"].tolist(),
    text=timeout_df["timeout_rate"].apply(lambda x: f"{x:.1f}%"),
    textposition="outside",
    textfont=dict(size=11),
    name="Timeout Rate",
))

# Threshold reference line at 15%
fig_timeout.add_hline(
    y=15,
    line_dash="dot",
    line_color=DANGER,
    line_width=2,
    annotation_text="15% threshold",
    annotation_position="top right",
    annotation_font=dict(color=DANGER, size=11),
)

fig_timeout.update_layout(
    xaxis_title="Partner",
    yaxis_title="Timeout Rate (%)",
    yaxis_ticksuffix="%",
    yaxis_range=[0, max(timeout_df["timeout_rate"].max() * 1.3, 20)],
    plot_bgcolor="white",
    paper_bgcolor="white",
    font=dict(family="Poppins, sans-serif", size=12),
    margin=dict(t=20, b=60, l=60, r=20),
    height=320,
    showlegend=False,
)
st.plotly_chart(fig_timeout, use_container_width=True)

print("Done. Header Bidding page loaded.")
