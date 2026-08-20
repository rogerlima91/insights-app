import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from utils.design_system import (
    get_css, metric_card, apply_plotly_style, PLOTLY_CONFIG,
    PRIMARY, SECONDARY, SUCCESS, WARNING, DANGER, WHITE, TEXT_SEC, TEXT_PRI, CHART_PALETTE,
)

# ── Apply Pacebird design system CSS ──────────────────────────────────────────
# STYLE LOCK: Pacebird design system — primary #F5A623 orange, secondary #1B2A4A navy, font Poppins.
st.markdown(get_css(), unsafe_allow_html=True)

# ── Mock data generator ───────────────────────────────────────────────────────
# Generates 30 days of daily publisher yield + Teads platform data.
# All revenue values are in AUD.
# bid_rate, win_rate, timeout_rate are Teads' own platform metrics — not SSP competitor data.
@st.cache_data
def generate_yield_data():
    rng = np.random.default_rng(seed=7)

    publishers = ["Nine.com.au", "news.com.au", "Domain", "realestate.com.au", "Stuff NZ"]
    formats    = ["inRead Video", "inFeed", "Display", "CTV"]

    # Yield benchmarks: fill_rate_target (%), ecpm_target (AUD)
    benchmarks = {
        "Nine.com.au":       {"fill_target": 75.0, "ecpm_target": 16.0},
        "news.com.au":       {"fill_target": 72.0, "ecpm_target": 14.0},
        "Domain":            {"fill_target": 60.0, "ecpm_target": 20.0},
        "realestate.com.au": {"fill_target": 58.0, "ecpm_target": 18.0},
        "Stuff NZ":          {"fill_target": 76.0, "ecpm_target":  9.0},
    }

    # Teads platform bid/win/timeout rates per publisher.
    # Domain and realestate.com.au have high bid rate but low win rate (floor price pressure).
    # Stuff NZ has low bid rate (smaller market, lower demand density).
    teads_rates = {
        "Nine.com.au":       {"bid_rate": 52.0, "win_rate": 35.0, "timeout_rate": 3.5},
        "news.com.au":       {"bid_rate": 48.0, "win_rate": 32.0, "timeout_rate": 4.2},
        "Domain":            {"bid_rate": 62.0, "win_rate": 20.0, "timeout_rate": 5.8},
        "realestate.com.au": {"bid_rate": 58.0, "win_rate": 18.0, "timeout_rate": 9.1},
        "Stuff NZ":          {"bid_rate": 25.0, "win_rate": 18.0, "timeout_rate": 3.0},
    }

    ecpm_table = {
        "Nine.com.au":         {"inRead Video": 18.5, "inFeed": 9.2,  "Display": 4.8, "CTV": 28.0},
        "news.com.au":         {"inRead Video": 16.8, "inFeed": 8.5,  "Display": 4.3, "CTV": 25.5},
        "Domain":              {"inRead Video": 24.0, "inFeed": 14.5, "Display": 6.5, "CTV": 0.0},
        "realestate.com.au":   {"inRead Video": 22.5, "inFeed": 13.0, "Display": 6.0, "CTV": 0.0},
        "Stuff NZ":            {"inRead Video": 12.0, "inFeed": 6.5,  "Display": 3.5, "CTV": 0.0},
    }

    imp_table = {
        "Nine.com.au":         {"inRead Video": 420, "inFeed": 850,  "Display": 2200, "CTV": 95},
        "news.com.au":         {"inRead Video": 380, "inFeed": 780,  "Display": 2000, "CTV": 85},
        "Domain":              {"inRead Video": 120, "inFeed": 220,  "Display": 600,  "CTV": 0},
        "realestate.com.au":   {"inRead Video": 110, "inFeed": 200,  "Display": 550,  "CTV": 0},
        "Stuff NZ":            {"inRead Video": 90,  "inFeed": 180,  "Display": 480,  "CTV": 0},
    }

    fill_table = {
        "Nine.com.au":       78.0,
        "news.com.au":       75.0,
        "Domain":            65.0,
        "realestate.com.au": 62.0,
        "Stuff NZ":          80.0,
    }

    start = date(2025, 7, 1)
    rows  = []
    for day_offset in range(30):
        d = start + timedelta(days=day_offset)
        wknd = 0.70 if d.weekday() >= 5 else 1.0

        for pub in publishers:
            for fmt in formats:
                base_imp  = imp_table[pub].get(fmt, 0)
                base_ecpm = ecpm_table[pub].get(fmt, 0.0)
                if base_imp == 0 or base_ecpm == 0.0:
                    continue

                noise      = rng.normal(1.0, 0.08)
                imps       = int(base_imp * 1000 * wknd * noise)
                imps       = max(imps, 0)

                ecpm_noise = rng.normal(1.0, 0.06)
                ecpm       = round(base_ecpm * ecpm_noise, 2)
                ecpm       = max(ecpm, 1.0)

                revenue    = round(imps / 1000 * ecpm, 2)

                fill_noise = rng.normal(1.0, 0.05)
                fill_rate  = round(min(fill_table[pub] * fill_noise, 99.9), 1)

                # Teads platform metrics — small daily and format-level noise
                t = teads_rates[pub]
                bid_r  = round(min(max(rng.normal(t["bid_rate"],    2.5),  5.0), 95.0), 1)
                win_r  = round(min(max(rng.normal(t["win_rate"],    2.0),  2.0), bid_r), 1)
                to_r   = round(min(max(rng.normal(t["timeout_rate"], 1.0), 0.2), 30.0), 1)

                rows.append({
                    "date":         d,
                    "publisher":    pub,
                    "placement":    f"{pub} — {fmt}",
                    "format":       fmt,
                    "impressions":  imps,
                    "revenue_aud":  revenue,
                    "ecpm":         ecpm,
                    "fill_rate":    fill_rate,
                    "fill_target":  benchmarks[pub]["fill_target"],
                    "ecpm_target":  benchmarks[pub]["ecpm_target"],
                    "bid_rate":     bid_r,
                    "win_rate":     win_r,
                    "timeout_rate": to_r,
                })

    return pd.DataFrame(rows)


def rag_status(actual, target, higher_is_better=True):
    """Return RAG emoji + color hex based on actual vs benchmark target."""
    if not target or target == 0:
        return "⚪", "#6B7280"
    pct = (actual - target) / abs(target) * 100
    if higher_is_better:
        if pct >= -10:
            return "🟢", SUCCESS
        elif pct >= -25:
            return "🟡", WARNING
        else:
            return "🔴", DANGER
    else:  # lower is better (timeout, CPA, etc.)
        if pct <= 10:
            return "🟢", SUCCESS
        elif pct <= 25:
            return "🟡", WARNING
        else:
            return "🔴", DANGER


def timeout_rag(timeout_rate, threshold=5.0):
    """RAG for timeout rate: green below threshold, amber up to 2×, red above."""
    if timeout_rate <= threshold:
        return "🟢", SUCCESS
    elif timeout_rate <= threshold * 2:
        return "🟡", WARNING
    else:
        return "🔴", DANGER


def integration_diagnosis(bid_rate, win_rate, timeout_rate):
    """
    Classify Teads' delivery health into one of four states.
    Diagnosis thresholds (matching Delivery Troubleshooter pattern):
      Latency issue     — timeout_rate > 8%
      Low bid density   — bid_rate < 30%
      Price competitive — bid_rate > 55% AND win_rate < 25%
      Healthy           — none of the above
    Returns: (label, rag_icon, color_hex)
    """
    if timeout_rate > 8.0:
        return "Latency issue", "🔴", DANGER
    if bid_rate < 30.0:
        return "Low bid density", "🟡", WARNING
    if bid_rate > 55.0 and win_rate < 25.0:
        return "Price competitive", "🟡", WARNING
    return "Healthy", "🟢", SUCCESS


def integration_health_score(bid_rate, win_rate, timeout_rate):
    """
    0–100 health score for Teads delivery quality on this publisher.
    Win rate (40 pts) + bid rate (30 pts) + timeout (30 pts).
    """
    win_s = min(win_rate / 40.0, 1.0) * 40
    bid_s = min(bid_rate / 60.0, 1.0) * 30
    to_s  = max(0.0, 1.0 - timeout_rate / 20.0) * 30
    return round(win_s + bid_s + to_s)


# ── Page header ───────────────────────────────────────────────────────────────
st.markdown("# 📊 Yield Dashboard")
st.markdown("Publisher inventory performance across placements and formats. Includes Teads platform delivery metrics. Data covers 30 days of ANZ activity.")

# ── Load data ─────────────────────────────────────────────────────────────────
df_all   = generate_yield_data()
min_date = df_all["date"].min()
max_date = df_all["date"].max()

# ── Filters: Publisher, Format, date range ─────────────────────────────────────
col_f1, col_f2, col_f3, col_f4 = st.columns([2, 2, 2, 2])
with col_f1:
    pub_options  = ["All Publishers"] + sorted(df_all["publisher"].unique().tolist())
    selected_pub = st.selectbox("Publisher", pub_options, key="yield_pub")
with col_f2:
    fmt_options  = ["All Formats"] + sorted(df_all["format"].unique().tolist())
    selected_fmt = st.selectbox("Format", fmt_options, key="yield_fmt")
with col_f3:
    date_from = st.date_input("From", value=min_date, min_value=min_date, max_value=max_date, key="yield_from")
with col_f4:
    date_to   = st.date_input("To",   value=max_date, min_value=min_date, max_value=max_date, key="yield_to")

# Apply all filters to the raw data
df = df_all[(df_all["date"] >= date_from) & (df_all["date"] <= date_to)]
if selected_pub != "All Publishers":
    df = df[df["publisher"] == selected_pub]
if selected_fmt != "All Formats":
    df = df[df["format"] == selected_fmt]

if df.empty:
    st.warning("No data for the selected filters.")
    st.stop()

# ── Summary metric cards ───────────────────────────────────────────────────────
total_rev = df["revenue_aud"].sum()
total_imp = df["impressions"].sum()
avg_ecpm  = (total_rev / total_imp * 1000) if total_imp > 0 else 0
avg_fill  = df["fill_rate"].mean()

st.markdown("### Summary")
m1, m2, m3, m4 = st.columns(4)
with m1:
    st.markdown(metric_card("Total Revenue", f"A${total_rev:,.0f}"), unsafe_allow_html=True)
with m2:
    st.markdown(metric_card("Impressions", f"{total_imp:,.0f}"), unsafe_allow_html=True)
with m3:
    st.markdown(metric_card("Avg eCPM", f"A${avg_ecpm:.2f}"), unsafe_allow_html=True)
with m4:
    st.markdown(metric_card("Avg Fill Rate", f"{avg_fill:.1f}%"), unsafe_allow_html=True)

# ── Inventory table ────────────────────────────────────────────────────────────
st.markdown("### Inventory Hierarchy")
st.caption(
    "Fill Rate, eCPM and Timeout Rate cells are RAG-coloured vs benchmarks. "
    "Diagnosis thresholds: Latency issue > 8% timeout · "
    "Low bid density < 30% bid rate · "
    "Price competitive > 55% bid rate with < 25% win rate."
)

# Granularity toggle — controls how rows are grouped
granularity = st.radio(
    "View by",
    ["Publisher level", "Placement level", "Format level"],
    horizontal=True,
    key="yield_granularity",
)

# Choose group keys based on selected granularity
if granularity == "Publisher level":
    group_cols = ["publisher"]
elif granularity == "Placement level":
    group_cols = ["publisher", "placement"]
else:
    group_cols = ["publisher", "placement", "format"]

# Aggregate all metrics for the chosen granularity
agg_df = df.groupby(group_cols).agg(
    revenue=("revenue_aud",  "sum"),
    impressions=("impressions",  "sum"),
    fill_rate=("fill_rate",      "mean"),
    fill_target=("fill_target",  "first"),
    ecpm_target=("ecpm_target",  "first"),
    bid_rate=("bid_rate",        "mean"),
    win_rate=("win_rate",        "mean"),
    timeout_rate=("timeout_rate","mean"),
).reset_index()
agg_df["ecpm"] = (agg_df["revenue"] / agg_df["impressions"] * 1000).round(2)
agg_df[["fill_rate", "bid_rate", "win_rate", "timeout_rate"]] = (
    agg_df[["fill_rate", "bid_rate", "win_rate", "timeout_rate"]].round(1)
)

# Health score per row (0–100)
agg_df["health_score"] = agg_df.apply(
    lambda r: integration_health_score(r["bid_rate"], r["win_rate"], r["timeout_rate"]),
    axis=1,
)

# Status (RAG icon + diagnosis label) and Recommended Action from diagnosis logic
_action_map = {
    "Latency issue":     "Check latency / endpoint config",
    "Low bid density":   "Review demand setup and targeting",
    "Price competitive": "Review floor prices",
    "Healthy":           "Within healthy thresholds",
}

def build_status_action(row):
    diag, rag_icon, _ = integration_diagnosis(row["bid_rate"], row["win_rate"], row["timeout_rate"])
    return pd.Series({
        "Status":             f"{rag_icon} {diag}",
        "Recommended Action": _action_map.get(diag, ""),
    })

agg_df[["Status", "Recommended Action"]] = agg_df.apply(build_status_action, axis=1)

# Rename raw columns to display labels
agg_df = agg_df.rename(columns={
    "publisher":    "Publisher",
    "placement":    "Placement",
    "format":       "Format",
    "revenue":      "Revenue",
    "impressions":  "Impressions",
    "ecpm":         "eCPM",
    "fill_rate":    "Fill Rate %",
    "bid_rate":     "Bid Rate %",
    "win_rate":     "Win Rate %",
    "timeout_rate": "Timeout Rate %",
    "health_score": "Health Score",
})

# Columns to show depend on granularity — only include dimension cols that apply
_dim_cols = {
    "Publisher level":  ["Publisher"],
    "Placement level":  ["Publisher", "Placement"],
    "Format level":     ["Publisher", "Placement", "Format"],
}
_metric_cols = [
    "Revenue", "Impressions", "eCPM",
    "Fill Rate %", "Bid Rate %", "Win Rate %", "Timeout Rate %",
    "Health Score", "Status", "Recommended Action",
]
show_cols = _dim_cols[granularity] + _metric_cols

# Styler: RAG background on Fill Rate, eCPM, Timeout Rate cells
def style_inventory(row):
    """Apply green/amber/red background to RAG metric cells."""
    styles = pd.Series("", index=row.index)
    fill_rag, _ = rag_status(row["Fill Rate %"], row["fill_target"])
    ecpm_rag, _ = rag_status(row["eCPM"], row["ecpm_target"])
    to_rag, _   = timeout_rag(row["Timeout Rate %"], 5.0)
    rag_bg = {
        "🟢": "background-color: #D1FAE5",
        "🟡": "background-color: #FEF3C7",
        "🔴": "background-color: #FEE2E2",
    }
    styles["Fill Rate %"]    = rag_bg.get(fill_rag, "")
    styles["eCPM"]           = rag_bg.get(ecpm_rag, "")
    styles["Timeout Rate %"] = rag_bg.get(to_rag, "")
    return styles

# Pass show_cols + hidden helper cols to the Styler; hide helpers before display
styled_tbl = (
    agg_df[show_cols + ["fill_target", "ecpm_target"]].style
    .apply(style_inventory, axis=1)
    .format({
        "Revenue":        "A${:,.0f}",
        "eCPM":           "A${:.2f}",
        "Fill Rate %":    "{:.1f}%",
        "Bid Rate %":     "{:.1f}%",
        "Win Rate %":     "{:.1f}%",
        "Timeout Rate %": "{:.1f}%",
        "Impressions":    "{:,.0f}",
    })
    .hide(axis="columns", subset=["fill_target", "ecpm_target"])
)
st.dataframe(styled_tbl, use_container_width=True, hide_index=True)

# ── Revenue by publisher bar chart ─────────────────────────────────────────────
st.markdown("### Revenue by Publisher")

rev_pub = (
    df.groupby("publisher")["revenue_aud"]
    .sum()
    .reset_index()
    .sort_values("revenue_aud", ascending=False)
)
rev_pub.columns = ["Publisher", "Revenue (AUD)"]

fig_rev = px.bar(
    rev_pub,
    x="Publisher",
    y="Revenue (AUD)",
    color="Publisher",
    color_discrete_sequence=CHART_PALETTE,
    text=rev_pub["Revenue (AUD)"].apply(lambda x: f"A${x:,.0f}"),
)
fig_rev.update_traces(textposition="outside", textfont_size=11)
fig_rev.update_layout(showlegend=False, yaxis_tickprefix="A$", yaxis_tickformat=",.0f")
apply_plotly_style(fig_rev, height=320)
st.plotly_chart(fig_rev, use_container_width=True, config=PLOTLY_CONFIG)

# ── eCPM trend line chart ─────────────────────────────────────────────────────
st.markdown("### eCPM Trend by Publisher")

daily_ecpm = (
    df.groupby(["date", "publisher"])
    .agg(revenue_aud=("revenue_aud", "sum"), impressions=("impressions", "sum"))
    .reset_index()
)
daily_ecpm["ecpm"] = (daily_ecpm["revenue_aud"] / daily_ecpm["impressions"] * 1000).round(2)

fig_ecpm = px.line(
    daily_ecpm,
    x="date",
    y="ecpm",
    color="publisher",
    color_discrete_sequence=CHART_PALETTE,
    labels={"date": "Date", "ecpm": "eCPM (A$)", "publisher": "Publisher"},
)
fig_ecpm.update_layout(yaxis_tickprefix="A$")
apply_plotly_style(fig_ecpm, height=340)
st.plotly_chart(fig_ecpm, use_container_width=True, config=PLOTLY_CONFIG)

# ── Timeout rate bar chart per publisher ──────────────────────────────────────
# Aggregated at publisher level regardless of the table granularity toggle.
st.markdown("### Timeout Rate by Publisher")
st.caption("Dashed line marks the 8% diagnosis threshold — publishers above this are flagged as a Latency issue.")

timeout_pub = (
    df.groupby("publisher")
    .agg(timeout_rate=("timeout_rate", "mean"))
    .reset_index()
    .sort_values("timeout_rate", ascending=False)
)
timeout_pub["timeout_rate"] = timeout_pub["timeout_rate"].round(1)
timeout_pub["bar_color"] = timeout_pub["timeout_rate"].apply(
    lambda x: DANGER if x > 8.0 else SECONDARY
)

fig_timeout = go.Figure()
fig_timeout.add_trace(go.Bar(
    x=timeout_pub["publisher"],
    y=timeout_pub["timeout_rate"],
    marker_color=timeout_pub["bar_color"].tolist(),
    text=timeout_pub["timeout_rate"].apply(lambda x: f"{x:.1f}%"),
    textposition="outside",
    textfont=dict(size=11),
    name="Timeout Rate",
))
fig_timeout.add_hline(
    y=8.0,
    line_dash="dot",
    line_color=DANGER,
    line_width=2,
    annotation_text="8% threshold",
    annotation_position="top right",
    annotation_font=dict(color=DANGER, size=11),
)
fig_timeout.update_layout(
    xaxis_title="Publisher",
    yaxis_title="Timeout Rate (%)",
    yaxis_ticksuffix="%",
    yaxis_range=[0, max(timeout_pub["timeout_rate"].max() * 1.4, 12)],
    showlegend=False,
)
apply_plotly_style(fig_timeout, height=300)
st.plotly_chart(fig_timeout, use_container_width=True, config=PLOTLY_CONFIG)

print("Done. Yield Dashboard page loaded.")
