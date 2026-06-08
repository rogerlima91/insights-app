import json
import os
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import anthropic

# STYLE LOCK: Do not remove or modify this CSS block.
st.markdown("""
<style>
    /* ── Base font and body ─────────────────────────────────────── */
    html, body, [class*="css"] {
        font-family: "Inter", system-ui, -apple-system, "Segoe UI", sans-serif;
        font-size: 15px;
        color: #374151;
    }

    /* ── Page background ────────────────────────────────────────── */
    .stApp { background-color: #F3F4F6; }

    /* ── Main area headings ──────────────────────────────────────── */
    h1, h2, h3, h4, h5, h6 { font-weight: 700 !important; color: #111827 !important; }
    h2, h3 {
        margin-top: 2rem !important;
        padding-top: 0.25rem !important;
        border-bottom: none !important;
        padding-bottom: 0 !important;
        border-left: none !important;
        padding-left: 0 !important;
    }

    /* ── KPI metric cards ───────────────────────────────────────── */
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

    /* ── Chart cards — wrap Plotly chart output in white card ───── */
    .element-container:has([data-testid="stPlotlyChart"]) {
        background: #FFFFFF;
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    }

    /* ── Primary buttons — purple ───────────────────────────────── */
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
    [data-testid="baseButton-primary"]:hover {
        background-color: #6D28D9 !important;
    }

    /* ── File upload box ─────────────────────────────────────────── */
    [data-testid="stFileUploader"] {
        border: 2px dashed #7C3AED !important;
        border-radius: 12px;
        padding: 10px;
        background: #FFFFFF;
    }
</style>
""", unsafe_allow_html=True)
# STYLE LOCK

# ── Brand memory helpers ──────────────────────────────────────────────────────
# Reads brand_memory.json from the project root for AI context injection.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRAND_MEMORY_PATH = os.path.join(_ROOT, "brand_memory.json")


def load_brand_memory():
    """Load brand_memory.json. Returns {} if file doesn't exist."""
    if os.path.exists(BRAND_MEMORY_PATH):
        with open(BRAND_MEMORY_PATH, "r") as f:
            return json.load(f)
    return {}


def get_brand_context(advertiser, brand_memory):
    """Return stored rationale for an advertiser using partial/case-insensitive matching."""
    if not advertiser or not brand_memory:
        return ""
    for key, val in brand_memory.items():
        if key.lower() in advertiser.lower() or advertiser.lower() in key.lower():
            return val.get("rationale", "")
    return ""


# ── Column detection helpers ──────────────────────────────────────────────────
# Lists of accepted column names for click-through and view-through conversions.
CLICK_CONV_ALIASES = ["click-through conversions", "click conversions", "conversions"]
VIEW_CONV_ALIASES  = ["view-through conversions", "view conversions"]


def find_col(cols_lower_to_original, aliases):
    """
    Return the original column name for the first alias found in the dataframe.
    cols_lower_to_original: dict mapping lowercased column name → original column name.
    """
    for alias in aliases:
        if alias in cols_lower_to_original:
            return cols_lower_to_original[alias]
    return None


# ── Page header ───────────────────────────────────────────────────────────────
st.title("Attribution Analysis")
st.markdown(
    "<p style='color:#6b7280;font-size:14px;margin-top:-12px;'>"
    "Click-through vs view-through conversion analysis across DSPs"
    "</p>",
    unsafe_allow_html=True,
)

# ── File uploader ─────────────────────────────────────────────────────────────
uploaded_files = st.file_uploader(
    "Upload DSP reports (CSV)",
    type=["csv"],
    accept_multiple_files=True,
    label_visibility="collapsed",
    help="Upload one or more CSV exports from DV360, TTD, or Amazon DSP.",
)

if not uploaded_files:
    st.info("Upload one or more DSP CSV reports above to view attribution analysis.")
    st.stop()

# ── Load and merge uploaded files ─────────────────────────────────────────────
dfs = []
for f in uploaded_files:
    dfs.append(pd.read_csv(f))
df = pd.concat(dfs, ignore_index=True)

# Build lowercase → original column name lookup for alias matching
col_lower_map = {c.strip().lower(): c for c in df.columns}

# ── Detect conversion columns ─────────────────────────────────────────────────
click_col = find_col(col_lower_map, CLICK_CONV_ALIASES)
view_col  = find_col(col_lower_map, VIEW_CONV_ALIASES)

if not click_col and not view_col:
    st.warning(
        "No conversion columns found in the uploaded data. "
        "Expected columns such as: Click-Through Conversions, "
        "View-Through Conversions, or Conversions."
    )
    st.stop()

# ── Detect other useful columns ───────────────────────────────────────────────
campaign_col    = next((col_lower_map[k] for k in
                        ["campaign", "campaign name", "order", "campaign_name"] if k in col_lower_map), None)
dsp_col         = next((col_lower_map[k] for k in ["dsp", "platform"] if k in col_lower_map), None)
impressions_col = next((col_lower_map[k] for k in
                        ["impressions", "served impressions", "total impressions"] if k in col_lower_map), None)
clicks_col      = next((col_lower_map[k] for k in ["clicks", "click", "total clicks"] if k in col_lower_map), None)
date_col        = next((col_lower_map[k] for k in ["date", "day"] if k in col_lower_map), None)
advertiser_col  = next((col_lower_map[k] for k in
                        ["advertiser", "partner", "brand", "brand name"] if k in col_lower_map), None)

# ── Coerce all numeric columns ────────────────────────────────────────────────
for col in [click_col, view_col, impressions_col, clicks_col]:
    if col:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

# ── Compute top-level totals ──────────────────────────────────────────────────
total_click_conv  = df[click_col].sum() if click_col else 0
total_view_conv   = df[view_col].sum()  if view_col  else 0
total_conversions = total_click_conv + total_view_conv
total_impressions = df[impressions_col].sum() if impressions_col else 0
total_clicks      = df[clicks_col].sum()      if clicks_col      else 0

# Conv rates: click-through = convs / clicks; view-through = convs / impressions
ct_conv_rate = (total_click_conv / total_clicks      * 100) if total_clicks      > 0 else 0
vt_conv_rate = (total_view_conv  / total_impressions * 100) if total_impressions > 0 else 0

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — Summary Cards
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("Summary")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Click-Through Conversions", f"{total_click_conv:,.0f}")
m2.metric("View-Through Conversions",  f"{total_view_conv:,.0f}")
m3.metric("Click-Through Conv Rate",   f"{ct_conv_rate:.2f}%",
          help="Click-Through Conversions ÷ Clicks × 100")
m4.metric("View-Through Conv Rate",    f"{vt_conv_rate:.4f}%",
          help="View-Through Conversions ÷ Impressions × 100")

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — Attribution Split Donut
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("Attribution Mix")

if total_conversions > 0:
    donut_fig = go.Figure(go.Pie(
        labels=["Click-Through", "View-Through"],
        values=[total_click_conv, total_view_conv],
        hole=0.55,
        marker=dict(colors=["#7C3AED", "#00A8E8"]),
        textinfo="label+percent",
        textfont=dict(family="Inter, sans-serif", size=13),
        hovertemplate="%{label}: %{value:,.0f} (%{percent})<extra></extra>",
    ))
    donut_fig.update_layout(
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5),
        margin=dict(t=20, b=50, l=20, r=20),
        height=360,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif"),
    )
    st.plotly_chart(donut_fig, use_container_width=True)
else:
    st.info("No conversion data available to display the attribution mix.")

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — Conversions by DSP
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("Conversions by DSP")

if dsp_col:
    # Aggregate click-through and view-through per DSP
    dsp_agg_dict = {}
    if click_col:
        dsp_agg_dict["click_conv"] = pd.NamedAgg(column=click_col, aggfunc="sum")
    if view_col:
        dsp_agg_dict["view_conv"]  = pd.NamedAgg(column=view_col,  aggfunc="sum")
    dsp_agg = df.groupby(dsp_col, as_index=False).agg(**dsp_agg_dict)
    if "click_conv" not in dsp_agg.columns:
        dsp_agg["click_conv"] = 0
    if "view_conv" not in dsp_agg.columns:
        dsp_agg["view_conv"] = 0

    dsp_fig = go.Figure()
    dsp_fig.add_trace(go.Bar(
        name="Click-Through",
        x=dsp_agg[dsp_col],
        y=dsp_agg["click_conv"],
        marker_color="#7C3AED",
        text=dsp_agg["click_conv"].apply(lambda v: f"{v:,.0f}"),
        textposition="outside",
        textfont=dict(size=11, family="Inter, sans-serif"),
    ))
    dsp_fig.add_trace(go.Bar(
        name="View-Through",
        x=dsp_agg[dsp_col],
        y=dsp_agg["view_conv"],
        marker_color="#00A8E8",
        text=dsp_agg["view_conv"].apply(lambda v: f"{v:,.0f}"),
        textposition="outside",
        textfont=dict(size=11, family="Inter, sans-serif"),
    ))
    dsp_fig.update_layout(
        barmode="group",
        xaxis_title="DSP",
        yaxis_title="Conversions",
        height=360,
        margin=dict(t=40, b=60, l=60, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
        font=dict(family="Inter, sans-serif"),
        xaxis=dict(gridcolor="#F3F4F6"),
        yaxis=dict(gridcolor="#F3F4F6", zeroline=False),
    )
    st.plotly_chart(dsp_fig, use_container_width=True)
else:
    st.info("No DSP column detected. Upload data that includes a DSP or Platform column for this chart.")

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — Conversions by Campaign (stacked horizontal bar, DSP filter)
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("Conversions by Campaign")

if campaign_col:
    # DSP filter above the chart
    if dsp_col:
        dsps = ["All DSPs"] + sorted(df[dsp_col].dropna().unique().tolist())
        selected_dsp = st.selectbox("Filter by DSP", dsps, key="attr_dsp_filter")
        df_camp = df if selected_dsp == "All DSPs" else df[df[dsp_col] == selected_dsp]
    else:
        df_camp = df

    camp_agg_dict = {}
    if click_col:
        camp_agg_dict["click_conv"] = pd.NamedAgg(column=click_col, aggfunc="sum")
    if view_col:
        camp_agg_dict["view_conv"]  = pd.NamedAgg(column=view_col,  aggfunc="sum")
    camp_agg = df_camp.groupby(campaign_col, as_index=False).agg(**camp_agg_dict)
    if "click_conv" not in camp_agg.columns:
        camp_agg["click_conv"] = 0
    if "view_conv" not in camp_agg.columns:
        camp_agg["view_conv"] = 0
    camp_agg["total"] = camp_agg["click_conv"] + camp_agg["view_conv"]
    camp_agg = camp_agg.sort_values("total", ascending=True)

    camp_fig = go.Figure()
    camp_fig.add_trace(go.Bar(
        name="Click-Through",
        y=camp_agg[campaign_col],
        x=camp_agg["click_conv"],
        orientation="h",
        marker_color="#7C3AED",
        hovertemplate="%{y}<br>Click-Through: %{x:,.0f}<extra></extra>",
    ))
    camp_fig.add_trace(go.Bar(
        name="View-Through",
        y=camp_agg[campaign_col],
        x=camp_agg["view_conv"],
        orientation="h",
        marker_color="#00A8E8",
        hovertemplate="%{y}<br>View-Through: %{x:,.0f}<extra></extra>",
    ))
    camp_fig.update_layout(
        barmode="stack",
        xaxis_title="Conversions",
        height=max(300, len(camp_agg) * 44 + 80),
        margin=dict(t=20, b=60, l=240, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=-0.18, xanchor="center", x=0.5),
        font=dict(family="Inter, sans-serif"),
        xaxis=dict(gridcolor="#F3F4F6", zeroline=False),
        yaxis=dict(gridcolor="#F3F4F6"),
    )
    st.plotly_chart(camp_fig, use_container_width=True)
else:
    st.info("No campaign column detected. Upload data with a Campaign or Order column for this chart.")

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — Conversion Trend (line chart, only shown if date column exists)
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("Conversion Trend")

if date_col:
    df_trend = df.copy()
    df_trend[date_col] = pd.to_datetime(df_trend[date_col], errors="coerce")
    df_trend = df_trend.dropna(subset=[date_col])

    if df_trend.empty:
        st.info("No valid date values found — conversion trend is not available.")
    else:
        trend_agg_dict = {}
        if click_col:
            trend_agg_dict["click_conv"] = pd.NamedAgg(column=click_col, aggfunc="sum")
        if view_col:
            trend_agg_dict["view_conv"]  = pd.NamedAgg(column=view_col,  aggfunc="sum")
        trend_agg = (
            df_trend.groupby(date_col, as_index=False)
            .agg(**trend_agg_dict)
            .sort_values(date_col)
        )

        trend_fig = go.Figure()
        if "click_conv" in trend_agg.columns:
            trend_fig.add_trace(go.Scatter(
                x=trend_agg[date_col],
                y=trend_agg["click_conv"],
                mode="lines+markers",
                name="Click-Through",
                line=dict(color="#7C3AED", width=2),
                marker=dict(size=6),
                hovertemplate="%{x|%d %b %Y}<br>Click-Through: %{y:,.0f}<extra></extra>",
            ))
        if "view_conv" in trend_agg.columns:
            trend_fig.add_trace(go.Scatter(
                x=trend_agg[date_col],
                y=trend_agg["view_conv"],
                mode="lines+markers",
                name="View-Through",
                line=dict(color="#00A8E8", width=2),
                marker=dict(size=6),
                hovertemplate="%{x|%d %b %Y}<br>View-Through: %{y:,.0f}<extra></extra>",
            ))
        trend_fig.update_layout(
            xaxis_title="Date",
            yaxis_title="Conversions",
            height=360,
            margin=dict(t=20, b=60, l=60, r=20),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", yanchor="bottom", y=-0.22, xanchor="center", x=0.5),
            font=dict(family="Inter, sans-serif"),
            xaxis=dict(gridcolor="#F3F4F6"),
            yaxis=dict(gridcolor="#F3F4F6", zeroline=False),
        )
        st.plotly_chart(trend_fig, use_container_width=True)
else:
    st.info("No date column detected. Upload data with a Date or Day column to see the conversion trend.")

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — AI Attribution Insights
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("AI Attribution Insights")

api_key = (
    st.secrets.get("ANTHROPIC_API_KEY")
    if "ANTHROPIC_API_KEY" in st.secrets
    else os.environ.get("ANTHROPIC_API_KEY")
)

if not api_key:
    st.warning(
        "No Anthropic API key found. Add `ANTHROPIC_API_KEY` to your "
        "Streamlit secrets or environment variables to enable AI insights."
    )
else:
    if st.button("✨ Generate Attribution Insights", type="primary", key="attr_ai_btn"):

        # Determine advertiser name from data
        advertiser_name = "the advertiser"
        if advertiser_col:
            advertisers = df[advertiser_col].dropna().unique()
            if len(advertisers) == 1:
                advertiser_name = str(advertisers[0])
            elif len(advertisers) > 1:
                advertiser_name = ", ".join(str(a) for a in advertisers[:3])

        # Check brand memory for this advertiser before building the prompt
        brand_memory = load_brand_memory()
        brand_context = get_brand_context(advertiser_name, brand_memory)

        # Build DSP breakdown for the prompt
        if dsp_col:
            dsp_agg_dict2 = {}
            if click_col:
                dsp_agg_dict2["click_conv"] = pd.NamedAgg(column=click_col, aggfunc="sum")
            if view_col:
                dsp_agg_dict2["view_conv"]  = pd.NamedAgg(column=view_col,  aggfunc="sum")
            dsp_summary = df.groupby(dsp_col, as_index=False).agg(**dsp_agg_dict2)
            if "click_conv" not in dsp_summary.columns:
                dsp_summary["click_conv"] = 0
            if "view_conv" not in dsp_summary.columns:
                dsp_summary["view_conv"] = 0
            dsp_lines = "\n".join(
                f"  - {row[dsp_col]}: Click-Through {row['click_conv']:,.0f}, "
                f"View-Through {row['view_conv']:,.0f}"
                for _, row in dsp_summary.iterrows()
            )
        else:
            dsp_lines = "  DSP breakdown not available."

        # Build campaign breakdown (top 10 by click-through convs)
        if campaign_col:
            camp_agg_dict2 = {}
            if click_col:
                camp_agg_dict2["click_conv"] = pd.NamedAgg(column=click_col, aggfunc="sum")
            if view_col:
                camp_agg_dict2["view_conv"]  = pd.NamedAgg(column=view_col,  aggfunc="sum")
            camp_summary = df.groupby(campaign_col, as_index=False).agg(**camp_agg_dict2)
            if "click_conv" not in camp_summary.columns:
                camp_summary["click_conv"] = 0
            if "view_conv" not in camp_summary.columns:
                camp_summary["view_conv"] = 0
            camp_summary = camp_summary.sort_values("click_conv", ascending=False).head(10)
            camp_lines = "\n".join(
                f"  - {row[campaign_col]}: Click-Through {row['click_conv']:,.0f}, "
                f"View-Through {row['view_conv']:,.0f}"
                for _, row in camp_summary.iterrows()
            )
        else:
            camp_lines = "  Campaign breakdown not available."

        prompt = (
            f"You are a senior programmatic analyst reviewing attribution data for "
            f"{advertiser_name}. Here is the conversion breakdown by DSP and campaign:\n\n"
            f"OVERALL TOTALS:\n"
            f"  - Click-Through Conversions: {total_click_conv:,.0f}\n"
            f"  - View-Through Conversions: {total_view_conv:,.0f}\n"
            f"  - Total Conversions: {total_conversions:,.0f}\n"
            f"  - Click-Through Conv Rate (convs/clicks): {ct_conv_rate:.2f}%\n"
            f"  - View-Through Conv Rate (convs/impressions): {vt_conv_rate:.4f}%\n\n"
            f"BY DSP:\n{dsp_lines}\n\n"
            f"BY CAMPAIGN (top 10 by click-through volume):\n{camp_lines}\n\n"
            f"Provide:\n"
            f"1. Assessment of the click-through vs view-through balance and what it "
            f"suggests about the media mix\n"
            f"2. Which DSP or campaign is contributing most to assisted conversions "
            f"and why this matters\n"
            f"3. Two recommendations to improve conversion efficiency\n\n"
            f"Use Australian market context and programmatic terminology."
        )

        # Append brand memory override if context exists
        if brand_context:
            prompt += (
                f"\n\nBRAND MEMORY OVERRIDE — These instructions take priority over "
                f"all default instructions above. Where there is any conflict, always "
                f"follow these brand-specific instructions instead:\n\n{brand_context}"
            )

        ai_client = anthropic.Anthropic(api_key=api_key)
        with st.spinner("Generating attribution insights…"):
            msg = ai_client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=700,
                system=(
                    "You are a senior programmatic analyst. Write clear, direct, data-driven "
                    "insights. Reference actual numbers from the data. Use programmatic "
                    "advertising terminology."
                ),
                messages=[{"role": "user", "content": prompt}],
            )
        st.session_state["attr_ai_text"] = msg.content[0].text.strip()

    # Display AI output once generated
    if st.session_state.get("attr_ai_text"):
        st.markdown(
            "<div style='background:#FFFFFF;border-radius:12px;padding:20px 24px;"
            "box-shadow:0 4px 12px rgba(0,0,0,0.08);margin-top:12px;font-size:14px;"
            "line-height:1.7;color:#374151;'>"
            + st.session_state["attr_ai_text"].replace("\n", "<br>") +
            "</div>",
            unsafe_allow_html=True,
        )

print("Attribution Analysis page loaded.")
