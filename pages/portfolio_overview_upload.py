import streamlit as st
import pandas as pd
import plotly.express as px
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.design_system import metric_card, apply_plotly_style, PLOTLY_CONFIG
# STYLE LOCK: Pacebird design system — primary #F5A623 orange, secondary #1B2A4A navy, font Poppins.

# ── Column normalisation maps (mirrors performance_insights.py) ───────────────
# Dimension columns: internal name → list of possible source column names.
COLUMN_MAP = {
    "advertiser":      ["Advertiser", "Partner", "Brand"],
    "campaign":        ["Campaign", "Campaign Name", "Brand Name", "Order"],
    "insertion_order": ["Insertion Order", "Campaign", "Campaign Name", "Order"],
    "line_item":       ["Line Item", "Line Item Name", "Ad Group", "Ad Group Name"],
    "creative":        ["Creative", "Ad"],
}

# Metric columns: lowercased source name → internal name.
METRIC_MAP = {
    "device type":              "device_type",
    "device":                   "device_type",
    "device_type":              "device_type",
    "device category":          "device_type",
    "environment":              "environment",
    "environment type":         "environment",
    "inventory type":           "environment",
    "supply type":              "environment",
    "site type":                "environment",
    "date":                     "date",
    "day":                      "date",
    "week":                     "date",
    "month":                    "date",
    "impressions":              "impressions",
    "impression":               "impressions",
    "served impressions":       "impressions",
    "total impressions":        "impressions",
    "clicks":                   "clicks",
    "click":                    "clicks",
    "total clicks":             "clicks",
    "link clicks":              "clicks",
    "spend":                    "spend_usd",
    "spend (usd)":              "spend_usd",
    "spend (aud)":              "spend_usd",
    "total spend":              "spend_usd",
    "total spend (usd)":        "spend_usd",
    "total spend (aud)":        "spend_usd",
    "media cost":               "spend_usd",
    "media cost (usd)":         "spend_usd",
    "revenue (usd)":            "spend_usd",
    "revenue (aud)":            "spend_usd",
    "cost":                     "spend_usd",
    "billed spend":             "spend_usd",
    "conversions":              "conversions",
    "total conversions":        "conversions",
    "post-click conversions":   "conversions",
    "ctr":                      "ctr_raw",
    "click-through rate":       "ctr_raw",
    "cpm":                      "cpm_raw",
    "cpm (usd)":                "cpm_raw",
    "cpm (aud)":                "cpm_raw",
    "avg. cpm":                 "cpm_raw",
    "average cpm":              "cpm_raw",
}


def detect_source(columns):
    """Identify which DSP the file came from based on column names."""
    cols_lower = [c.strip().lower() for c in columns]
    if any("detail page views" in c for c in cols_lower):
        return "Amazon"
    if any("ad format" in c for c in cols_lower):
        return "DV360 YouTube"
    if any("supply vendor" in c for c in cols_lower):
        return "TTD"
    if any("insertion order" in c for c in cols_lower):
        return "DV360"
    if any("ad group" in c for c in cols_lower):
        return "TTD"
    if any(c == "order" for c in cols_lower):
        return "Amazon"
    if any("revenue (usd)" in c for c in cols_lower):
        return "DV360"
    if any("billed spend" in c for c in cols_lower):
        return "TTD"
    return "Generic"


def load_and_normalise(uploaded_file):
    """
    Reads a CSV, TSV, or Excel file, normalises column names to our internal
    standard, converts numeric columns, and calculates CTR/CPM from raw numbers.
    """
    name = uploaded_file.name.lower()
    if name.endswith(".xlsx") or name.endswith(".xls"):
        df = pd.read_excel(uploaded_file)
    elif name.endswith(".tsv"):
        df = pd.read_csv(uploaded_file, sep="\t")
    else:
        df = pd.read_csv(uploaded_file)

    # Detect DSP before renaming columns
    dsp = detect_source(df.columns.tolist())

    # Lowercase and strip all column names for consistent matching
    df.columns = [c.strip().lower() for c in df.columns]

    # Apply dimension column map — first match wins, already-claimed columns skipped
    _used_src = set()
    _dim_rename = {}
    for _internal, _src_list in COLUMN_MAP.items():
        for _src in _src_list:
            _src_lower = _src.lower()
            if _src_lower in df.columns and _src_lower not in _used_src:
                _dim_rename[_src_lower] = _internal
                _used_src.add(_src_lower)
                break

    # Apply metric column map for all remaining columns
    _metric_rename = {k: v for k, v in METRIC_MAP.items()
                      if k in df.columns and k not in _used_src}

    # Rename in one pass
    df = df.rename(columns={**_dim_rename, **_metric_rename})

    # Drop duplicate columns that can arise when multiple source columns map to the same name
    df = df.loc[:, ~df.columns.duplicated(keep="first")]

    # Convert numeric columns — DSP exports often have commas or $ signs
    for col in ["impressions", "clicks", "spend_usd", "conversions"]:
        if col in df.columns:
            df[col] = (
                df[col].astype(str)
                .str.replace(r"[$,]", "", regex=True)
                .str.strip()
            )
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Recalculate CTR and CPM from raw numbers (more reliable than DSP values)
    if "impressions" in df.columns and "clicks" in df.columns:
        df["ctr"] = df["clicks"] / df["impressions"]
    if "impressions" in df.columns and "spend_usd" in df.columns:
        df["cpm"] = df["spend_usd"] / df["impressions"] * 1000

    df["source_file"] = uploaded_file.name
    df["dsp_source"]  = dsp

    return df, dsp


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


# ── Page header ────────────────────────────────────────────────────────────────
st.markdown("# 📋 Portfolio Overview")
st.markdown("Upload your DSP report files to see a summary across all advertisers.")

# ── File uploader ──────────────────────────────────────────────────────────────
with st.expander("📤 Upload Report", expanded=st.session_state.get("portfolio_upload_df") is None):
    uploaded_files = st.file_uploader(
        "Drag and drop files here, or click to browse. "
        "Accepts CSV, TSV, Excel (.xlsx / .xls). Multiple files accepted.",
        type=["csv", "tsv", "xlsx", "xls"],
        accept_multiple_files=True,
        key="portfolio_uploader",
    )

    if uploaded_files:
        frames = []
        with st.spinner("Reading and normalising files…"):
            for f in uploaded_files:
                df_file, dsp = load_and_normalise(f)
                frames.append(df_file)

        df_all = pd.concat(frames, ignore_index=True)

        # Parse date column if present
        if "date" in df_all.columns:
            df_all["date"] = pd.to_datetime(df_all["date"], errors="coerce")

        # Store under a dedicated key so this page's data is independent of
        # whatever the API Data section may have loaded into portfolio_df
        st.session_state["portfolio_upload_df"] = df_all
        st.rerun()

# ── Empty state — shown when no files have been uploaded yet ───────────────────
if st.session_state.get("portfolio_upload_df") is None:
    st.markdown("""
    <div style="text-align:center;padding:60px 20px;background:#FFFFFF;
    border-radius:16px;box-shadow:0 2px 12px rgba(0,0,0,0.06);margin:20px 0;">
        <div style="font-size:48px;margin-bottom:16px;">📂</div>
        <div style="font-size:20px;font-weight:700;color:#111827;margin-bottom:8px;">
            No data loaded yet
        </div>
        <div style="font-size:15px;color:#6B7280;margin-bottom:4px;">
            Use the Upload Report panel above to load your DSP exports
        </div>
        <div style="font-size:13px;color:#9CA3AF;">
            Accepted formats: CSV, XLSX, XLS
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ── Main portfolio analysis ─────────────────────────────────────────────────────
df = st.session_state["portfolio_upload_df"].copy()

if "campaign" not in df.columns:
    st.warning("No 'campaign' / 'advertiser' column found in the uploaded data. Cannot build portfolio view.")
    st.stop()

brands = df["campaign"].dropna().unique()

# ── Summary metrics ────────────────────────────────────────────────────────────
col_m1, col_m2, col_m3, col_m4 = st.columns(4)
total_spend = df["spend_usd"].sum() if "spend_usd" in df.columns else 0
total_imps  = df["impressions"].sum() if "impressions" in df.columns else 0
total_clicks = df["clicks"].sum() if "clicks" in df.columns else 0

overall_ctr = (total_clicks / total_imps * 100) if total_imps > 0 else 0
with col_m1:
    st.markdown(metric_card("Total Advertisers", str(len(brands))), unsafe_allow_html=True)
with col_m2:
    st.markdown(metric_card("Total Spend", f"${total_spend:,.0f}"), unsafe_allow_html=True)
with col_m3:
    st.markdown(metric_card("Total Impressions", f"{total_imps:,.0f}"), unsafe_allow_html=True)
with col_m4:
    st.markdown(metric_card("Portfolio CTR", f"{overall_ctr:.2f}%"), unsafe_allow_html=True)

# ── Per-advertiser summary table ───────────────────────────────────────────────
st.markdown("## 📊 Advertiser Summary")

rows = []
for brand in brands:
    brand_df = df[df["campaign"] == brand]
    imps   = brand_df["impressions"].sum() if "impressions" in brand_df.columns else 0
    clicks = brand_df["clicks"].sum()      if "clicks"      in brand_df.columns else 0
    spend  = brand_df["spend_usd"].sum()   if "spend_usd"   in brand_df.columns else 0
    convs  = brand_df["conversions"].sum() if "conversions" in brand_df.columns else 0

    ctr = (clicks / imps * 100) if imps > 0 else 0
    cpm = (spend / imps * 1000) if imps > 0 else 0
    cpa = (spend / convs)       if convs > 0 else 0

    # RAG status from KPI targets in brand_memory.json
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
            if "🔴" in statuses:    rag_overall = "🔴"
            elif "🟡" in statuses:  rag_overall = "🟡"
            else:                   rag_overall = "🟢"

    rows.append({
        "Advertiser":   brand,
        "Total Spend":  f"${spend:,.0f}",
        "Impressions":  f"{imps:,.0f}",
        "CTR":          f"{ctr:.2f}%",
        "CPM":          f"${cpm:.2f}",
        "CPA":          f"${cpa:.2f}" if convs > 0 else "—",
        "RAG Status":   rag_overall,
    })

summary_df = pd.DataFrame(rows)

st.markdown("*Click an advertiser name to filter the table.*")

selected_rows = st.dataframe(
    summary_df,
    use_container_width=True,
    hide_index=True,
    on_select="rerun",
    selection_mode="single-row",
)

if selected_rows and selected_rows.get("selection", {}).get("rows"):
    selected_idx   = selected_rows["selection"]["rows"][0]
    selected_brand = summary_df.iloc[selected_idx]["Advertiser"]
    st.session_state["portfolio_brand_filter"] = selected_brand
    st.success(f"✅ Filter set to **{selected_brand}**.")

# ── Portfolio spend chart ──────────────────────────────────────────────────────
st.markdown("## 💰 Spend by Advertiser")

if "spend_usd" in df.columns:
    spend_by_brand = df.groupby("campaign")["spend_usd"].sum().reset_index()
    spend_by_brand.columns = ["Advertiser", "Spend"]
    spend_by_brand = spend_by_brand.sort_values("Spend", ascending=False)

    fig_spend = px.bar(
        spend_by_brand, x="Advertiser", y="Spend",
        color="Spend",
        color_continuous_scale=["#FDECC8", "#F5A623", "#1B2A4A"],
        title="Total Spend by Advertiser",
    )
    fig_spend.update_layout(
        showlegend=False,
        coloraxis_showscale=False,
        yaxis_title="Spend (USD)",
        xaxis_title="",
    )
    fig_spend.update_traces(marker_line_width=0)
    apply_plotly_style(fig_spend)
    st.plotly_chart(fig_spend, use_container_width=True, config=PLOTLY_CONFIG)

# ── RAG Heatmap ────────────────────────────────────────────────────────────────
st.markdown("## 🗺️ KPI RAG Heatmap")
st.caption("Shows RAG status per metric per advertiser. Only shown for brands with KPI targets configured in Brand Settings.")

heatmap_rows = []
for brand in brands:
    targets = load_kpi_targets(str(brand))
    if not targets:
        continue

    brand_df = df[df["campaign"] == brand]
    imps   = brand_df["impressions"].sum() if "impressions" in brand_df.columns else 0
    clicks = brand_df["clicks"].sum()      if "clicks"      in brand_df.columns else 0
    spend  = brand_df["spend_usd"].sum()   if "spend_usd"   in brand_df.columns else 0
    convs  = brand_df["conversions"].sum() if "conversions" in brand_df.columns else 0

    ctr = (clicks / imps * 100) if imps > 0 else 0
    cpm = (spend / imps * 1000) if imps > 0 else 0
    cpa = (spend / convs)       if convs > 0 else 0

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
        row["ROAS"] = "⚪"
    if targets.get("target_vtr"):
        row["VTR"] = "⚪"

    heatmap_rows.append(row)

if heatmap_rows:
    heatmap_df = pd.DataFrame(heatmap_rows).set_index("Brand").fillna("—")
    st.dataframe(heatmap_df, use_container_width=True)
else:
    st.info("No brands have KPI targets configured. Set targets in **Settings → Brand Settings → KPI Targets**.")

# ── Clear uploaded data ────────────────────────────────────────────────────────
if st.button("🗑 Clear uploaded data", key="portfolio_upload_clear"):
    st.session_state.pop("portfolio_upload_df", None)
    st.rerun()

print("Done. Portfolio Overview (Upload) page loaded.")
