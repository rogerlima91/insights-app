import streamlit as st
import pandas as pd
import os

# ── Global CSS (STYLE LOCK) ───────────────────────────────────────────────────
st.markdown("""
<style>
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
    h1, h2, h3, h4, h5, h6 { font-weight: 700 !important; color: #111827 !important; }

    [data-testid="metric-container"] {
        background: #FFFFFF;
        border: none;
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06);
        border-top: 4px solid #7C3AED;
    }
    .stButton > button[kind="primary"],
    [data-testid="baseButton-primary"] {
        background-color: #7C3AED !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
    }
</style>
""", unsafe_allow_html=True)

# ── Page header ────────────────────────────────────────────────────────────────
st.markdown("# 📋 Live Campaigns")
st.markdown(
    "<p style='color:#6B7280;margin-top:-10px;'>Upload a DSP pacing export to check campaign delivery.</p>",
    unsafe_allow_html=True,
)

# ── File uploader ──────────────────────────────────────────────────────────────
uploaded_file = st.file_uploader(
    "Upload pacing export",
    type=["csv", "xlsx", "xls"],
    key="pacing_upload",
    label_visibility="collapsed",
)

# ── Empty state ────────────────────────────────────────────────────────────────
if uploaded_file is None:
    st.markdown("""
    <div style="text-align:center;padding:60px 20px;background:#FFFFFF;
    border-radius:16px;box-shadow:0 2px 12px rgba(0,0,0,0.06);margin:20px 0;">
        <div style="font-size:48px;margin-bottom:16px;">📂</div>
        <div style="font-size:20px;font-weight:700;color:#111827;margin-bottom:8px;">
            No pacing data loaded yet
        </div>
        <div style="font-size:15px;color:#6B7280;margin-bottom:4px;">
            Upload your DSP pacing export to get started
        </div>
        <div style="font-size:13px;color:#9CA3AF;">
            Accepted formats: CSV, XLSX, XLS
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ── Parse uploaded file ────────────────────────────────────────────────────────
try:
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
except Exception as e:
    st.error(f"Could not read file: {e}")
    st.stop()

st.success(f"✅ Loaded {len(df):,} rows from **{uploaded_file.name}**")

# ── Show data preview ──────────────────────────────────────────────────────────
st.markdown("## Data Preview")
st.dataframe(df, use_container_width=True)

# ── Basic pacing summary ───────────────────────────────────────────────────────
# Look for spend/budget columns to compute pacing if available
spend_col   = next((c for c in df.columns if c.lower() in ["spend", "cost", "media cost", "billed spend"]), None)
budget_col  = next((c for c in df.columns if c.lower() in ["budget", "total budget", "planned spend"]), None)
name_col    = next((c for c in df.columns if c.lower() in ["campaign", "campaign name", "line item"]), None)

if spend_col and budget_col:
    st.markdown("## 💰 Pacing Summary")
    group_col = name_col or spend_col

    summary = df.groupby(group_col)[[spend_col, budget_col]].sum().reset_index()
    summary["Pacing %"] = (summary[spend_col] / summary[budget_col] * 100).round(1)

    # RAG status based on pacing %
    def pacing_rag(pct):
        if pct >= 90: return "🟢 On track"
        elif pct >= 70: return "🟡 At risk"
        else: return "🔴 Critical"

    summary["Status"] = summary["Pacing %"].apply(pacing_rag)
    summary[spend_col]  = summary[spend_col].apply(lambda x: f"${x:,.0f}")
    summary[budget_col] = summary[budget_col].apply(lambda x: f"${x:,.0f}")
    summary["Pacing %"] = summary["Pacing %"].apply(lambda x: f"{x:.1f}%")

    st.dataframe(summary, use_container_width=True, hide_index=True)
else:
    st.info("Add **Spend** and **Budget** columns to your export to see pacing status.")

print("Done. Live Campaigns (pacing) page loaded.")
