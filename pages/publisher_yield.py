import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from utils.design_system import get_css, PRIMARY, SECONDARY, SUCCESS, WARNING, DANGER, WHITE, TEXT_SEC, TEXT_PRI, CHART_PALETTE

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

# ── Filters ───────────────────────────────────────────────────────────────────
col_f1, col_f2, col_f3 = st.columns([2, 2, 2])
with col_f1:
    pub_options  = ["All Publishers"] + sorted(df_all["publisher"].unique().tolist())
    selected_pub = st.selectbox("Publisher", pub_options, key="yield_pub")
with col_f2:
    date_from = st.date_input("From", value=min_date, min_value=min_date, max_value=max_date, key="yield_from")
with col_f3:
    date_to   = st.date_input("To",   value=max_date, min_value=min_date, max_value=max_date, key="yield_to")

# Apply date and publisher filters
df = df_all[(df_all["date"] >= date_from) & (df_all["date"] <= date_to)]
if selected_pub != "All Publishers":
    df = df[df["publisher"] == selected_pub]

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
    st.metric("Total Revenue", f"A${total_rev:,.0f}")
with m2:
    st.metric("Impressions", f"{total_imp:,.0f}")
with m3:
    st.metric("Avg eCPM", f"A${avg_ecpm:.2f}")
with m4:
    st.metric("Avg Fill Rate", f"{avg_fill:.1f}%")

# ── Three-level expandable hierarchy: Publisher → Placement → Format ───────────
# Mirrors the Live Campaigns pattern (Client → Campaign → Line Item).
# Timeout RAG threshold: 5% for column-level coloring in the hierarchy.
st.markdown("### Inventory Hierarchy")
st.caption(
    "Expand each publisher to see placement detail, then expand a placement for format breakdown. "
    "Fill Rate and eCPM RAG vs benchmarks. Timeout Rate 🔴 above 10%, 🟡 above 5%, 🟢 below 5%."
)

# Aggregate publisher-level summary once (used for header rows)
pub_agg = df.groupby("publisher").agg(
    revenue_aud=("revenue_aud",  "sum"),
    impressions=("impressions",  "sum"),
    fill_rate=("fill_rate",      "mean"),
    fill_target=("fill_target",  "first"),
    ecpm_target=("ecpm_target",  "first"),
    bid_rate=("bid_rate",        "mean"),
    win_rate=("win_rate",        "mean"),
    timeout_rate=("timeout_rate","mean"),
).reset_index()
pub_agg["ecpm"] = (pub_agg["revenue_aud"] / pub_agg["impressions"] * 1000).round(2)
pub_agg[["bid_rate", "win_rate", "timeout_rate"]] = pub_agg[["bid_rate", "win_rate", "timeout_rate"]].round(1)

for _, pub_row in pub_agg.iterrows():
    pub_name = pub_row["publisher"]
    fill_rag, fill_clr = rag_status(pub_row["fill_rate"], pub_row["fill_target"], higher_is_better=True)
    to_rag,   _        = timeout_rag(pub_row["timeout_rate"], threshold=5.0)

    with st.expander(
        f"{fill_rag} **{pub_name}**"
        f"  ·  A${pub_row['revenue_aud']:,.0f}"
        f"  ·  eCPM A${pub_row['ecpm']:.2f}"
        f"  ·  Fill {pub_row['fill_rate']:.1f}%"
        f"  ·  {to_rag} Timeout {pub_row['timeout_rate']:.1f}%",
        expanded=False,
    ):
        # Publisher summary banner
        st.markdown(
            f"<div style='background:#f0fdf4;border-left:4px solid {fill_clr};"
            f"padding:8px 12px;border-radius:6px;margin-bottom:8px;font-size:13px;'>"
            f"Fill Rate: <b>{pub_row['fill_rate']:.1f}%</b> vs target {pub_row['fill_target']:.0f}%"
            f"&nbsp;|&nbsp; eCPM: <b>A${pub_row['ecpm']:.2f}</b> vs target A${pub_row['ecpm_target']:.2f}"
            f"&nbsp;|&nbsp; Bid Rate: <b>{pub_row['bid_rate']:.1f}%</b>"
            f"&nbsp;|&nbsp; Win Rate: <b>{pub_row['win_rate']:.1f}%</b>"
            f"&nbsp;|&nbsp; Timeout: <b>{pub_row['timeout_rate']:.1f}%</b>"
            f"</div>",
            unsafe_allow_html=True,
        )

        # Placement-level breakdown
        place_agg = (
            df[df["publisher"] == pub_name]
            .groupby("placement")
            .agg(
                revenue_aud=("revenue_aud",  "sum"),
                impressions=("impressions",  "sum"),
                fill_rate=("fill_rate",      "mean"),
                fill_target=("fill_target",  "first"),
                ecpm_target=("ecpm_target",  "first"),
                bid_rate=("bid_rate",        "mean"),
                win_rate=("win_rate",        "mean"),
                timeout_rate=("timeout_rate","mean"),
            )
            .reset_index()
        )
        place_agg["ecpm"] = (place_agg["revenue_aud"] / place_agg["impressions"] * 1000).round(2)

        for _, pl_row in place_agg.iterrows():
            p_fill_rag, p_fill_clr = rag_status(pl_row["fill_rate"], pl_row["fill_target"])
            p_to_rag,   _           = timeout_rag(pl_row["timeout_rate"], threshold=5.0)

            with st.expander(
                f"{p_fill_rag} {pl_row['placement']}"
                f"  ·  A${pl_row['revenue_aud']:,.0f}"
                f"  ·  eCPM A${pl_row['ecpm']:.2f}"
                f"  ·  Fill {pl_row['fill_rate']:.1f}%"
                f"  ·  {p_to_rag} Timeout {pl_row['timeout_rate']:.1f}%",
                expanded=False,
            ):
                # Format-level breakdown table
                fmt_df = (
                    df[df["placement"] == pl_row["placement"]]
                    .groupby("format")
                    .agg(
                        revenue_aud=("revenue_aud",  "sum"),
                        impressions=("impressions",  "sum"),
                        fill_rate=("fill_rate",      "mean"),
                        bid_rate=("bid_rate",        "mean"),
                        win_rate=("win_rate",        "mean"),
                        timeout_rate=("timeout_rate","mean"),
                    )
                    .reset_index()
                )
                fmt_df["ecpm"] = (fmt_df["revenue_aud"] / fmt_df["impressions"] * 1000).round(2)
                fmt_df = fmt_df.sort_values("revenue_aud", ascending=False)

                display_fmt = fmt_df.copy()
                display_fmt["revenue_aud"]  = display_fmt["revenue_aud"].apply(lambda x: f"A${x:,.0f}")
                display_fmt["ecpm"]         = display_fmt["ecpm"].apply(lambda x: f"A${x:.2f}")
                display_fmt["fill_rate"]    = display_fmt["fill_rate"].apply(lambda x: f"{x:.1f}%")
                display_fmt["impressions"]  = display_fmt["impressions"].apply(lambda x: f"{x:,.0f}")
                display_fmt["bid_rate"]     = display_fmt["bid_rate"].apply(lambda x: f"{x:.1f}%")
                display_fmt["win_rate"]     = display_fmt["win_rate"].apply(lambda x: f"{x:.1f}%")
                display_fmt["timeout_rate"] = display_fmt["timeout_rate"].apply(lambda x: f"{x:.1f}%")
                display_fmt.columns = ["Format", "Revenue", "Impressions", "Fill Rate", "Bid Rate %", "Win Rate %", "Timeout Rate %", "eCPM"]

                st.dataframe(
                    display_fmt[["Format", "Revenue", "Impressions", "eCPM", "Fill Rate", "Bid Rate %", "Win Rate %", "Timeout Rate %"]],
                    use_container_width=True,
                    hide_index=True,
                )

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
fig_rev.update_layout(
    showlegend=False,
    plot_bgcolor="white",
    paper_bgcolor="white",
    yaxis_tickprefix="A$",
    yaxis_tickformat=",.0f",
    font=dict(family="Poppins, sans-serif", size=12),
    margin=dict(t=20, b=40, l=60, r=20),
    height=320,
)
st.plotly_chart(fig_rev, use_container_width=True)

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
fig_ecpm.update_layout(
    plot_bgcolor="white",
    paper_bgcolor="white",
    yaxis_tickprefix="A$",
    font=dict(family="Poppins, sans-serif", size=12),
    margin=dict(t=20, b=40, l=60, r=20),
    height=340,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
)
st.plotly_chart(fig_ecpm, use_container_width=True)

# ── Fill rate heatmap by placement ────────────────────────────────────────────
st.markdown("### Fill Rate Heatmap by Placement")
st.caption("Average fill rate per placement over the selected date range. Darker = higher fill.")

heatmap_df = (
    df.groupby(["placement", "format"])
    .agg(fill_rate=("fill_rate", "mean"))
    .reset_index()
)
heatmap_pivot = heatmap_df.pivot(index="placement", columns="format", values="fill_rate").fillna(0)

fig_heat = go.Figure(data=go.Heatmap(
    z=heatmap_pivot.values,
    x=heatmap_pivot.columns.tolist(),
    y=heatmap_pivot.index.tolist(),
    colorscale=[
        [0.0, "#EEF1F4"],
        [0.5, "#F5A623"],
        [1.0, "#1B2A4A"],
    ],
    text=[[f"{v:.1f}%" if v > 0 else "" for v in row] for row in heatmap_pivot.values],
    texttemplate="%{text}",
    textfont=dict(size=11),
    colorbar=dict(title="Fill %", ticksuffix="%"),
    zmin=0,
    zmax=100,
))
fig_heat.update_layout(
    xaxis_title="Format",
    yaxis_title="",
    plot_bgcolor="white",
    paper_bgcolor="white",
    font=dict(family="Poppins, sans-serif", size=11),
    margin=dict(t=20, b=60, l=20, r=60),
    height=400,
)
st.plotly_chart(fig_heat, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# ── Integration Health (Teads platform delivery metrics) ──────────────────────
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 🔄 Integration Health")
st.caption(
    "Teads platform delivery quality per publisher. "
    "Diagnosis thresholds: Latency issue > 8% timeout · "
    "Low bid density < 30% bid rate · "
    "Price competitive > 55% bid rate with < 25% win rate."
)

# Aggregate Teads metrics at publisher level across the filtered date range
health_agg = df.groupby("publisher").agg(
    bid_rate=("bid_rate",        "mean"),
    win_rate=("win_rate",        "mean"),
    timeout_rate=("timeout_rate","mean"),
).reset_index()
health_agg["bid_rate"]     = health_agg["bid_rate"].round(1)
health_agg["win_rate"]     = health_agg["win_rate"].round(1)
health_agg["timeout_rate"] = health_agg["timeout_rate"].round(1)

# Apply diagnosis and health score to each publisher row
health_agg[["diagnosis", "rag_icon", "rag_color"]] = health_agg.apply(
    lambda r: pd.Series(integration_diagnosis(r["bid_rate"], r["win_rate"], r["timeout_rate"])),
    axis=1,
)
health_agg["health_score"] = health_agg.apply(
    lambda r: integration_health_score(r["bid_rate"], r["win_rate"], r["timeout_rate"]),
    axis=1,
)

# ── Integration Health summary table ─────────────────────────────────────────
summary_tbl = health_agg[[
    "publisher", "bid_rate", "win_rate", "timeout_rate", "health_score", "rag_icon", "diagnosis"
]].copy()
summary_tbl["status"]       = summary_tbl["rag_icon"] + " " + summary_tbl["diagnosis"]
summary_tbl["bid_rate"]     = summary_tbl["bid_rate"].apply(lambda x: f"{x:.1f}%")
summary_tbl["win_rate"]     = summary_tbl["win_rate"].apply(lambda x: f"{x:.1f}%")
summary_tbl["timeout_rate"] = summary_tbl["timeout_rate"].apply(lambda x: f"{x:.1f}%")
summary_tbl = summary_tbl.rename(columns={
    "publisher":    "Publisher",
    "bid_rate":     "Bid Rate %",
    "win_rate":     "Win Rate %",
    "timeout_rate": "Timeout Rate %",
    "health_score": "Health Score",
    "status":       "Diagnosis",
})
st.dataframe(
    summary_tbl[["Publisher", "Bid Rate %", "Win Rate %", "Timeout Rate %", "Health Score", "Diagnosis"]],
    use_container_width=True,
    hide_index=True,
)

# ── Integration Health cards (Delivery Troubleshooter pattern) ────────────────
st.markdown("#### Publisher Health Cards")
cols_per_row = 3
sorted_health = health_agg.sort_values("health_score", ascending=False)
rows_needed   = -(-len(sorted_health) // cols_per_row)  # ceiling division

for row_i in range(rows_needed):
    card_cols = st.columns(cols_per_row)
    for col_i in range(cols_per_row):
        idx = row_i * cols_per_row + col_i
        if idx >= len(sorted_health):
            break
        r     = sorted_health.iloc[idx]
        score = int(r["health_score"])
        clr   = r["rag_color"]
        diag  = r["diagnosis"]
        rag   = r["rag_icon"]

        # Build issue bullets specific to this publisher's metrics
        bullets = []
        if r["timeout_rate"] > 8.0:
            bullets.append("▸ Timeout rate above 8% — check latency / endpoint config")
        if r["bid_rate"] < 30.0:
            bullets.append("▸ Bid rate below 30% — review demand setup and targeting")
        if r["bid_rate"] > 55.0 and r["win_rate"] < 25.0:
            bullets.append("▸ Bidding often but winning rarely — review floor prices")
        if not bullets:
            bullets.append("▸ All delivery metrics within healthy thresholds")

        issues_html = "<br>".join(bullets[:3])

        with card_cols[col_i]:
            st.markdown(
                f"""<div style="background:white;border-radius:12px;padding:16px;
                     box-shadow:0 2px 12px rgba(0,0,0,0.06);
                     border-top:4px solid {clr};margin-bottom:8px;">
                  <div style="font-weight:700;font-size:15px;color:#111827;">{rag} {r['publisher']}</div>
                  <div style="font-size:22px;font-weight:700;color:{clr};margin:6px 0;">{score}/100</div>
                  <div style="font-size:11px;font-weight:600;color:#6B7280;
                       text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px;">{diag}</div>
                  <div style="font-size:12px;color:#374151;line-height:1.6;">{issues_html}</div>
                </div>""",
                unsafe_allow_html=True,
            )

# ── Timeout rate bar chart per publisher ──────────────────────────────────────
st.markdown("#### Timeout Rate by Publisher")
st.caption("Dashed line marks the 8% diagnosis threshold — publishers above this are flagged as a 'Latency issue'.")

timeout_pub = health_agg[["publisher", "timeout_rate"]].sort_values("timeout_rate", ascending=False)
timeout_pub = timeout_pub.copy()
# Color bars red above diagnosis threshold (8%), navy below
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

# Threshold reference line at 8% (diagnosis threshold)
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
    plot_bgcolor="white",
    paper_bgcolor="white",
    font=dict(family="Poppins, sans-serif", size=12),
    margin=dict(t=20, b=60, l=60, r=20),
    height=300,
    showlegend=False,
)
st.plotly_chart(fig_timeout, use_container_width=True)

print("Done. Yield Dashboard page loaded.")
