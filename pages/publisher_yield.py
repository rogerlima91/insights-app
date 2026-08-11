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
# Generates 30 days of daily publisher yield data.
# All revenue values are in AUD. Fill rate, eCPM and impressions vary by publisher and format.
@st.cache_data
def generate_yield_data():
    rng = np.random.default_rng(seed=7)

    publishers = ["Nine.com.au", "news.com.au", "Domain", "realestate.com.au", "Stuff NZ"]
    formats    = ["inRead Video", "inFeed", "Display", "CTV"]

    # Benchmarks: fill_rate_target (%), ecpm_target (AUD)
    benchmarks = {
        "Nine.com.au":       {"fill_target": 75.0, "ecpm_target": 16.0},
        "news.com.au":       {"fill_target": 72.0, "ecpm_target": 14.0},
        "Domain":            {"fill_target": 60.0, "ecpm_target": 20.0},
        "realestate.com.au": {"fill_target": 58.0, "ecpm_target": 18.0},
        "Stuff NZ":          {"fill_target": 76.0, "ecpm_target":  9.0},
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

                noise  = rng.normal(1.0, 0.08)
                imps   = int(base_imp * 1000 * wknd * noise)
                imps   = max(imps, 0)

                ecpm_noise = rng.normal(1.0, 0.06)
                ecpm       = round(base_ecpm * ecpm_noise, 2)
                ecpm       = max(ecpm, 1.0)

                revenue = round(imps / 1000 * ecpm, 2)

                fill_noise = rng.normal(1.0, 0.05)
                fill_rate  = round(min(fill_table[pub] * fill_noise, 99.9), 1)

                rows.append({
                    "date":        d,
                    "publisher":   pub,
                    "placement":   f"{pub} — {fmt}",
                    "format":      fmt,
                    "impressions": imps,
                    "revenue_aud": revenue,
                    "ecpm":        ecpm,
                    "fill_rate":   fill_rate,
                    "fill_target": benchmarks[pub]["fill_target"],
                    "ecpm_target": benchmarks[pub]["ecpm_target"],
                })

    return pd.DataFrame(rows)


def rag_status(actual, target, higher_is_better=True):
    """Return a RAG emoji and color hex based on actual vs target."""
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
    else:
        if pct <= 10:
            return "🟢", SUCCESS
        elif pct <= 25:
            return "🟡", WARNING
        else:
            return "🔴", DANGER


# ── Page header ───────────────────────────────────────────────────────────────
st.markdown("# 📊 Yield Dashboard")
st.markdown("Publisher inventory performance across placements and formats. Data covers 30 days of ANZ sell-side activity.")

# ── Load data ─────────────────────────────────────────────────────────────────
df_all = generate_yield_data()
min_date = df_all["date"].min()
max_date = df_all["date"].max()

# ── Filters ───────────────────────────────────────────────────────────────────
col_f1, col_f2, col_f3 = st.columns([2, 2, 2])
with col_f1:
    pub_options = ["All Publishers"] + sorted(df_all["publisher"].unique().tolist())
    selected_pub = st.selectbox("Publisher", pub_options, key="yield_pub")
with col_f2:
    date_from = st.date_input("From", value=min_date, min_value=min_date, max_value=max_date, key="yield_from")
with col_f3:
    date_to = st.date_input("To", value=max_date, min_value=min_date, max_value=max_date, key="yield_to")

# Apply filters
df = df_all[(df_all["date"] >= date_from) & (df_all["date"] <= date_to)]
if selected_pub != "All Publishers":
    df = df[df["publisher"] == selected_pub]

if df.empty:
    st.warning("No data for the selected filters.")
    st.stop()

# ── Summary metric cards ───────────────────────────────────────────────────────
total_rev  = df["revenue_aud"].sum()
total_imp  = df["impressions"].sum()
avg_ecpm   = (total_rev / total_imp * 1000) if total_imp > 0 else 0
avg_fill   = df["fill_rate"].mean()

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
# This mirrors the Live Campaigns page pattern (Client → Campaign → Line Item).
st.markdown("### Inventory Hierarchy")
st.caption("Expand each publisher to see placement detail. Expand a placement to see format breakdown. RAG status is vs fill rate and eCPM benchmarks.")

# Aggregate once at publisher level for the header card
pub_agg = df.groupby("publisher").agg(
    revenue_aud=("revenue_aud", "sum"),
    impressions=("impressions", "sum"),
    fill_rate=("fill_rate", "mean"),
    fill_target=("fill_target", "first"),
    ecpm_target=("ecpm_target", "first"),
).reset_index()
pub_agg["ecpm"] = (pub_agg["revenue_aud"] / pub_agg["impressions"] * 1000).round(2)

for _, pub_row in pub_agg.iterrows():
    pub_name = pub_row["publisher"]
    fill_rag, fill_clr = rag_status(pub_row["fill_rate"], pub_row["fill_target"], higher_is_better=True)
    ecpm_rag, ecpm_clr = rag_status(pub_row["ecpm"],      pub_row["ecpm_target"], higher_is_better=True)

    # Publisher-level expander header with inline KPIs
    with st.expander(
        f"{fill_rag} **{pub_name}**  ·  A${pub_row['revenue_aud']:,.0f}  ·  eCPM A${pub_row['ecpm']:.2f}  ·  Fill {pub_row['fill_rate']:.1f}%",
        expanded=False,
    ):
        # Publisher summary row
        st.markdown(
            f"<div style='background:#f0fdf4;border-left:4px solid {fill_clr};padding:8px 12px;border-radius:6px;margin-bottom:8px;font-size:13px;'>"
            f"Fill Rate: <b>{pub_row['fill_rate']:.1f}%</b> vs target {pub_row['fill_target']:.0f}%  "
            f"&nbsp;|&nbsp; eCPM: <b>A${pub_row['ecpm']:.2f}</b> vs target A${pub_row['ecpm_target']:.2f}"
            f"</div>",
            unsafe_allow_html=True,
        )

        # Placement-level breakdown within this publisher
        place_agg = (
            df[df["publisher"] == pub_name]
            .groupby("placement")
            .agg(
                revenue_aud=("revenue_aud", "sum"),
                impressions=("impressions", "sum"),
                fill_rate=("fill_rate", "mean"),
                fill_target=("fill_target", "first"),
                ecpm_target=("ecpm_target", "first"),
            )
            .reset_index()
        )
        place_agg["ecpm"] = (place_agg["revenue_aud"] / place_agg["impressions"] * 1000).round(2)

        for _, pl_row in place_agg.iterrows():
            p_fill_rag, p_fill_clr = rag_status(pl_row["fill_rate"], pl_row["fill_target"])
            p_ecpm_rag, _          = rag_status(pl_row["ecpm"],      pl_row["ecpm_target"])

            with st.expander(
                f"{p_fill_rag} {pl_row['placement']}  ·  A${pl_row['revenue_aud']:,.0f}  ·  eCPM A${pl_row['ecpm']:.2f}  ·  Fill {pl_row['fill_rate']:.1f}%",
                expanded=False,
            ):
                # Format-level breakdown within this placement
                fmt_df = (
                    df[df["placement"] == pl_row["placement"]]
                    .groupby("format")
                    .agg(
                        revenue_aud=("revenue_aud", "sum"),
                        impressions=("impressions", "sum"),
                        fill_rate=("fill_rate", "mean"),
                    )
                    .reset_index()
                )
                fmt_df["ecpm"] = (fmt_df["revenue_aud"] / fmt_df["impressions"] * 1000).round(2)
                fmt_df = fmt_df.sort_values("revenue_aud", ascending=False)

                display_fmt = fmt_df.copy()
                display_fmt["revenue_aud"] = display_fmt["revenue_aud"].apply(lambda x: f"A${x:,.0f}")
                display_fmt["ecpm"]        = display_fmt["ecpm"].apply(lambda x: f"A${x:.2f}")
                display_fmt["fill_rate"]   = display_fmt["fill_rate"].apply(lambda x: f"{x:.1f}%")
                display_fmt["impressions"] = display_fmt["impressions"].apply(lambda x: f"{x:,.0f}")
                display_fmt.columns = ["Format", "Revenue", "Impressions", "Fill Rate", "eCPM"]

                st.dataframe(display_fmt[["Format", "Revenue", "Impressions", "eCPM", "Fill Rate"]], use_container_width=True, hide_index=True)

# ── Revenue by publisher bar chart ─────────────────────────────────────────────
st.markdown("### Revenue by Publisher")

rev_pub = df.groupby("publisher")["revenue_aud"].sum().reset_index().sort_values("revenue_aud", ascending=False)
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

# Daily eCPM per publisher — revenue / impressions * 1000
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
st.caption("Average fill rate per placement over the selected date range. Darker orange = higher fill.")

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
        [0.0, "#EEF1F4"],   # light grey for 0 / no data
        [0.5, "#F5A623"],   # orange mid
        [1.0, "#1B2A4A"],   # navy high
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

print("Done. Yield Dashboard page loaded.")
