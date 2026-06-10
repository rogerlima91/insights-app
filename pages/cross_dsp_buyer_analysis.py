import pandas as pd
import streamlit as st
import plotly.graph_objects as go

# STYLE LOCK: Do not remove or modify this CSS block.
st.markdown("""
<style>
    html, body, [class*="css"] {
        font-family: "Inter", system-ui, -apple-system, "Segoe UI", sans-serif;
        font-size: 15px;
        color: #374151;
    }
    .stApp { background-color: #F3F4F6; }
    h1, h2, h3, h4, h5, h6 { font-weight: 700 !important; color: #111827 !important; }
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
    [data-testid="metric-container"] label {
        font-size: 12px;
        font-weight: 600;
        color: #6B7280;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        font-size: 26px;
        font-weight: 700;
        color: #111827;
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
        font-size: 15px !important;
        padding: 0.5rem 1.25rem !important;
    }
    .stButton > button[kind="primary"]:hover,
    [data-testid="baseButton-primary"]:hover { background-color: #6D28D9 !important; }
    [data-testid="stDataFrame"] {
        background: #FFFFFF;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.06);
    }
</style>
""", unsafe_allow_html=True)
# STYLE LOCK

# ── Mock deal data ────────────────────────────────────────────────────────────
# Represents GPT SSP deal performance across agencies and DSPs.
# Columns: Agency, DSP, Centre, Deal Type, Deal ID, Floor CPM, Clearing CPM,
#          Impressions Booked, Impressions Delivered, Spend AUD,
#          Fill Rate %, Flight Start, Flight End
RAW_DEALS = [
    ("Publicis Media", "DV360", "Melbourne Central",      "PMP",  "GPT-PMP-001",  28, 31.50, 500000, 487000, 15340, 97.4, "2026-05-01", "2026-07-31"),
    ("GroupM",         "TTD",   "Highpoint",              "PMP",  "GPT-PMP-002",  22, 24.80, 350000, 298000,  7398, 85.1, "2026-05-01", "2026-06-30"),
    ("OMD",            "DV360", "Rouse Hill Town Centre", "PG",   "GPT-PG-001",   30, 30.00, 400000, 392000, 11760, 98.0, "2026-04-15", "2026-07-15"),
    ("Mindshare",      "TTD",   "Macquarie Centre",       "PMP",  "GPT-PMP-003",  25, 27.20, 280000, 241000,  6555, 86.1, "2026-05-15", "2026-07-31"),
    ("Dentsu",         "DV360", "Melbourne Central",      "PG",   "GPT-PG-002",   35, 35.00, 600000, 589000, 20615, 98.2, "2026-04-01", "2026-06-30"),
    ("Initiative",     "TTD",   "Sunshine Plaza",         "PMP",  "GPT-PMP-004",  20, 21.50, 220000, 178000,  3827, 80.9, "2026-05-01", "2026-07-15"),
    ("Havas Media",    "DV360", "Macarthur Square",       "Open", "GPT-OPEN-001", 12, 13.20, 180000, 134000,  1769, 74.4, "2026-05-01", "2026-07-31"),
    ("Wavemaker",      "TTD",   "Highpoint",              "PG",   "GPT-PG-003",   28, 28.00, 320000, 315000,  8820, 98.4, "2026-04-15", "2026-07-31"),
    ("Carat",          "DV360", "Casuarina Square",       "PMP",  "GPT-PMP-005",  18, 19.80, 150000, 121000,  2396, 80.7, "2026-05-15", "2026-07-31"),
    ("OMD",            "TTD",   "Melbourne Central",      "PMP",  "GPT-PMP-006",  28, 29.50, 420000, 389000, 11476, 92.6, "2026-05-01", "2026-07-31"),
]

DEAL_COLUMNS = [
    "Agency", "DSP", "Centre", "Deal Type", "Deal ID",
    "Floor CPM", "Clearing CPM",
    "Impressions Booked", "Impressions Delivered",
    "Spend (A$)", "Fill Rate %",
    "Flight Start", "Flight End",
]

df = pd.DataFrame(RAW_DEALS, columns=DEAL_COLUMNS)

# Compute derived columns
df["CPM Uplift %"] = ((df["Clearing CPM"] - df["Floor CPM"]) / df["Floor CPM"] * 100).round(1)
df["Status"] = df["Fill Rate %"].apply(
    lambda r: "On Track" if r >= 95 else ("Watch" if r >= 85 else "At Risk")
)

# ── Page header ───────────────────────────────────────────────────────────────
st.title("Cross-DSP Buyer Analysis")
st.markdown(
    "<p style='color:#6b7280;font-size:14px;margin-top:-12px;'>"
    "Unified view of how agencies and DSPs are buying GPT inventory across all platforms."
    "</p>",
    unsafe_allow_html=True,
)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — At-Risk Deals (shown at top as a warning panel)
# ══════════════════════════════════════════════════════════════════════════════
at_risk = df[df["Fill Rate %"] < 85]
pg_on_floor = df[(df["Deal Type"] == "PG") & (df["Clearing CPM"] == df["Floor CPM"])]
clearing_below_floor = df[df["Clearing CPM"] < df["Floor CPM"]]

has_flags = not at_risk.empty or not clearing_below_floor.empty

if has_flags:
    st.subheader("Flagged Deals")
    for _, row in at_risk.iterrows():
        st.markdown(
            f"<div style='background:#FEF2F2;border:1px solid #FECACA;border-radius:8px;"
            f"padding:12px 16px;margin-bottom:6px;font-size:13px;'>"
            f"⚠️ <strong>{row['Deal ID']}</strong> — {row['Agency']} via {row['DSP']} "
            f"@ {row['Centre']} — Fill Rate {row['Fill Rate %']}% — "
            f"Underdelivering: review targeting or floor price"
            f"</div>",
            unsafe_allow_html=True,
        )
    for _, row in clearing_below_floor.iterrows():
        st.markdown(
            f"<div style='background:#FEF2F2;border:1px solid #FECACA;border-radius:8px;"
            f"padding:12px 16px;margin-bottom:6px;font-size:13px;'>"
            f"❌ <strong>{row['Deal ID']}</strong> — Clearing CPM A${row['Clearing CPM']:.2f} "
            f"below floor A${row['Floor CPM']:.2f} — check deal configuration"
            f"</div>",
            unsafe_allow_html=True,
        )

# Show PG guaranteed status
for _, row in pg_on_floor.iterrows():
    st.markdown(
        f"<div style='background:#ECFDF5;border:1px solid #6EE7B7;border-radius:8px;"
        f"padding:12px 16px;margin-bottom:6px;font-size:13px;'>"
        f"✅ <strong>{row['Deal ID']}</strong> — {row['Agency']} via {row['DSP']} "
        f"@ {row['Centre']} — Guaranteed: delivering as contracted"
        f"</div>",
        unsafe_allow_html=True,
    )

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — Portfolio Summary Cards
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("Portfolio Summary")

total_deals       = len(df)
total_booked      = df["Impressions Booked"].sum()
total_revenue     = df["Spend (A$)"].sum()
avg_fill_rate     = df["Fill Rate %"].mean()
avg_clearing_cpm  = df["Clearing CPM"].mean()
avg_floor_cpm     = df["Floor CPM"].mean()
cpm_uplift        = (avg_clearing_cpm - avg_floor_cpm) / avg_floor_cpm * 100

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Active Deals",       total_deals)
m2.metric("Booked Impressions", f"{total_booked/1_000_000:.1f}M")
m3.metric("Total Revenue",      f"A${total_revenue/1_000:.0f}k")
m4.metric("Avg Fill Rate",      f"{avg_fill_rate:.1f}%")
m5.metric(
    "Avg Clearing CPM",
    f"A${avg_clearing_cpm:.2f}",
    delta=f"+{cpm_uplift:.1f}% vs floor",
)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — Deal Performance Table (with filters)
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("Deal Performance")

# Filters above the table
fc1, fc2, fc3 = st.columns(3)
with fc1:
    dsp_filter = st.multiselect(
        "Filter by DSP",
        sorted(df["DSP"].unique()),
        placeholder="All DSPs",
        key="cda_dsp",
    )
with fc2:
    centre_filter = st.multiselect(
        "Filter by Centre",
        sorted(df["Centre"].unique()),
        placeholder="All Centres",
        key="cda_centre",
    )
with fc3:
    type_filter = st.multiselect(
        "Filter by Deal Type",
        sorted(df["Deal Type"].unique()),
        placeholder="All types",
        key="cda_type",
    )

# Apply filters
filtered = df.copy()
if dsp_filter:
    filtered = filtered[filtered["DSP"].isin(dsp_filter)]
if centre_filter:
    filtered = filtered[filtered["Centre"].isin(centre_filter)]
if type_filter:
    filtered = filtered[filtered["Deal Type"].isin(type_filter)]

# Build display dataframe with formatted columns
display_df = filtered[[
    "Agency", "DSP", "Centre", "Deal Type", "Deal ID",
    "Floor CPM", "Clearing CPM", "CPM Uplift %", "Fill Rate %",
    "Spend (A$)", "Status",
]].copy()

# Colour-code fill rate with an inline HTML table for better visual control
def fill_rate_cell(r):
    if r >= 95:
        return f"<span style='color:#10B981;font-weight:700;'>{r:.1f}%</span>"
    elif r >= 85:
        return f"<span style='color:#F59E0B;font-weight:700;'>{r:.1f}%</span>"
    else:
        return f"<span style='color:#EF4444;font-weight:700;'>{r:.1f}%</span>"

def status_badge(s):
    colors = {
        "On Track": ("#ECFDF5", "#10B981"),
        "Watch":    ("#FFFBEB", "#F59E0B"),
        "At Risk":  ("#FEF2F2", "#EF4444"),
    }
    bg, fg = colors.get(s, ("#F3F4F6", "#6B7280"))
    return (
        f"<span style='background:{bg};color:{fg};border-radius:4px;"
        f"padding:2px 8px;font-size:11px;font-weight:700;'>{s}</span>"
    )

# Build HTML table rows
header_cols = [
    "Agency", "DSP", "Centre", "Deal Type", "Deal ID",
    "Floor CPM", "Clearing CPM", "Uplift %", "Fill Rate", "Spend", "Status",
]
header_html = "".join(
    f"<th style='padding:10px 14px;text-align:left;font-size:11px;color:#6B7280;"
    f"text-transform:uppercase;letter-spacing:0.06em;border-bottom:2px solid #E5E7EB;'>"
    f"{h}</th>"
    for h in header_cols
)

rows_html = ""
for _, row in filtered.iterrows():
    rows_html += (
        f"<tr style='border-bottom:1px solid #F3F4F6;'>"
        f"<td style='padding:10px 14px;font-size:13px;'>{row['Agency']}</td>"
        f"<td style='padding:10px 14px;font-size:13px;'>{row['DSP']}</td>"
        f"<td style='padding:10px 14px;font-size:13px;'>{row['Centre']}</td>"
        f"<td style='padding:10px 14px;font-size:13px;'>{row['Deal Type']}</td>"
        f"<td style='padding:10px 14px;font-size:12px;color:#6B7280;'>{row['Deal ID']}</td>"
        f"<td style='padding:10px 14px;font-size:13px;'>A${row['Floor CPM']:.2f}</td>"
        f"<td style='padding:10px 14px;font-size:13px;'>A${row['Clearing CPM']:.2f}</td>"
        f"<td style='padding:10px 14px;font-size:13px;color:#10B981;font-weight:600;'>"
        f"+{row['CPM Uplift %']:.1f}%</td>"
        f"<td style='padding:10px 14px;'>{fill_rate_cell(row['Fill Rate %'])}</td>"
        f"<td style='padding:10px 14px;font-size:13px;'>A${row['Spend (A$)']:,.0f}</td>"
        f"<td style='padding:10px 14px;'>{status_badge(row['Status'])}</td>"
        f"</tr>"
    )

st.markdown(
    f"<div style='background:#FFFFFF;border-radius:12px;overflow:hidden;"
    f"box-shadow:0 4px 12px rgba(0,0,0,0.07);margin-bottom:16px;'>"
    f"<table style='width:100%;border-collapse:collapse;'>"
    f"<thead><tr style='background:#F9FAFB;'>{header_html}</tr></thead>"
    f"<tbody>{rows_html}</tbody>"
    f"</table></div>",
    unsafe_allow_html=True,
)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — Revenue by Agency (horizontal bar, sorted descending)
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("Revenue by Agency")

agency_rev = (
    df.groupby("Agency", as_index=False)["Spend (A$)"].sum()
    .sort_values("Spend (A$)", ascending=True)
)

agency_fig = go.Figure(go.Bar(
    x=agency_rev["Spend (A$)"],
    y=agency_rev["Agency"],
    orientation="h",
    marker_color="#2563EB",
    text=agency_rev["Spend (A$)"].apply(lambda v: f"A${v:,.0f}"),
    textposition="outside",
    textfont=dict(size=11, family="Inter, sans-serif"),
    hovertemplate="%{y}<br>Revenue: A$%{x:,.0f}<extra></extra>",
))
agency_fig.update_layout(
    xaxis_title="Total Spend (A$)",
    height=360,
    margin=dict(t=20, b=40, l=160, r=80),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif"),
    xaxis=dict(gridcolor="#F3F4F6", zeroline=False),
    yaxis=dict(gridcolor="#F3F4F6"),
)
st.plotly_chart(agency_fig, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — Fill Rate by Centre (bar + 90% reference line)
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("Fill Rate by Centre")

centre_fill = (
    df.groupby("Centre", as_index=False)["Fill Rate %"].mean()
    .sort_values("Fill Rate %", ascending=True)
)

# Colour each bar based on fill rate threshold
bar_colours = [
    "#10B981" if v >= 95 else ("#F59E0B" if v >= 85 else "#EF4444")
    for v in centre_fill["Fill Rate %"]
]

fill_fig = go.Figure()
fill_fig.add_trace(go.Bar(
    x=centre_fill["Centre"],
    y=centre_fill["Fill Rate %"],
    marker_color=bar_colours,
    text=centre_fill["Fill Rate %"].apply(lambda v: f"{v:.1f}%"),
    textposition="outside",
    textfont=dict(size=11, family="Inter, sans-serif"),
    hovertemplate="%{x}<br>Fill Rate: %{y:.1f}%<extra></extra>",
))
# 90% reference line
fill_fig.add_hline(
    y=90, line_dash="dash", line_color="#7C3AED", line_width=2,
    annotation_text="90% target", annotation_position="top right",
    annotation_font_color="#7C3AED",
)
fill_fig.update_layout(
    yaxis_title="Fill Rate %",
    yaxis_range=[0, 115],
    height=360,
    margin=dict(t=20, b=80, l=60, r=20),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif"),
    xaxis=dict(gridcolor="#F3F4F6"),
    yaxis=dict(gridcolor="#F3F4F6"),
)
st.plotly_chart(fill_fig, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — Deal Type Mix (donut — % of revenue)
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("Deal Type Revenue Mix")

type_rev = df.groupby("Deal Type", as_index=False)["Spend (A$)"].sum()

donut_fig = go.Figure(go.Pie(
    labels=type_rev["Deal Type"],
    values=type_rev["Spend (A$)"],
    hole=0.55,
    marker=dict(colors=["#2563EB", "#7C3AED", "#10B981"]),
    textinfo="label+percent",
    textfont=dict(family="Inter, sans-serif", size=13),
    hovertemplate="%{label}: A$%{value:,.0f} (%{percent})<extra></extra>",
    customdata=type_rev["Spend (A$)"].apply(lambda v: f"A${v:,.0f}"),
))
donut_fig.update_layout(
    showlegend=True,
    legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5),
    margin=dict(t=20, b=50, l=20, r=20),
    height=360,
    paper_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif"),
)
st.plotly_chart(donut_fig, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — Price Discovery: Floor vs Clearing CPM (grouped bar per deal)
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("Price Discovery — Floor vs Clearing CPM")

# Colour clearing CPM bar green if above floor, red if below or equal (non-PG)
clearing_colours = [
    "#10B981" if row["Clearing CPM"] >= row["Floor CPM"] else "#EF4444"
    for _, row in df.iterrows()
]

price_fig = go.Figure()
price_fig.add_trace(go.Bar(
    name="Floor CPM",
    x=df["Deal ID"],
    y=df["Floor CPM"],
    marker_color="#6B7280",
    opacity=0.7,
    hovertemplate="%{x}<br>Floor: A$%{y:.2f}<extra></extra>",
))
price_fig.add_trace(go.Bar(
    name="Clearing CPM",
    x=df["Deal ID"],
    y=df["Clearing CPM"],
    marker_color=clearing_colours,
    hovertemplate="%{x}<br>Clearing: A$%{y:.2f}<extra></extra>",
))
price_fig.update_layout(
    barmode="group",
    xaxis_title="Deal ID",
    yaxis_title="CPM (A$)",
    height=380,
    margin=dict(t=20, b=80, l=60, r=20),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    legend=dict(orientation="h", yanchor="bottom", y=-0.30, xanchor="center", x=0.5),
    font=dict(family="Inter, sans-serif"),
    xaxis=dict(gridcolor="#F3F4F6", tickangle=-30),
    yaxis=dict(gridcolor="#F3F4F6", zeroline=False),
)
st.plotly_chart(price_fig, use_container_width=True)

print("Cross-DSP Buyer Analysis page loaded.")
