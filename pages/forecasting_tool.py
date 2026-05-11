import io
import json
import os
import re
import uuid
from datetime import date, datetime
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
    .stApp {
        background-color: #F3F4F6;
    }

    /* ── Main area headings ──────────────────────────────────────── */
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
</style>
""", unsafe_allow_html=True)
# STYLE LOCK

# ── Industry benchmarks ───────────────────────────────────────────────────────
# Used when no live uploaded data is available in the session.
# All CPM/CPC values are in AUD.
DISPLAY_BENCHMARKS = {
    "FMCG":              {"ctr": 0.25, "cpm":  6.00, "cpc": 2.40},
    "Alcohol & Spirits": {"ctr": 0.20, "cpm":  8.00, "cpc": 4.00},
    "Technology":        {"ctr": 0.35, "cpm":  7.00, "cpc": 2.00},
    "Retail":            {"ctr": 0.45, "cpm":  5.00, "cpc": 1.11},
    "Automotive":        {"ctr": 0.18, "cpm":  9.00, "cpc": 5.00},
    "Entertainment":     {"ctr": 0.30, "cpm":  6.00, "cpc": 2.00},
    "Finance":           {"ctr": 0.22, "cpm": 10.00, "cpc": 4.55},
    "Travel":            {"ctr": 0.28, "cpm":  7.00, "cpc": 2.50},
    "Other":             {"ctr": 0.25, "cpm":  6.00, "cpc": 2.40},
}

VIDEO_BENCHMARKS = {
    "FMCG":              {"vtr": 72, "cpv": 0.04, "cpm": 18.00},
    "Alcohol & Spirits": {"vtr": 75, "cpv": 0.05, "cpm": 22.00},
    "Technology":        {"vtr": 70, "cpv": 0.03, "cpm": 16.00},
    "Retail":            {"vtr": 71, "cpv": 0.03, "cpm": 15.00},
    "Automotive":        {"vtr": 74, "cpv": 0.05, "cpm": 20.00},
    "Entertainment":     {"vtr": 73, "cpv": 0.04, "cpm": 17.00},
    "Finance":           {"vtr": 69, "cpv": 0.05, "cpm": 22.00},
    "Travel":            {"vtr": 76, "cpv": 0.04, "cpm": 19.00},
    "Other":             {"vtr": 72, "cpv": 0.04, "cpm": 18.00},
}

# ── Data file paths — all stored in the project root ─────────────────────────
_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

BENCHMARKS_PATH    = os.path.normpath(os.path.join(_ROOT, "benchmarks.json"))
FORECASTS_LOG_PATH = os.path.normpath(os.path.join(_ROOT, "forecasts_log.json"))
ACCURACY_LOG_PATH  = os.path.normpath(os.path.join(_ROOT, "accuracy_log.json"))

# ── Keyword → vertical mapping ────────────────────────────────────────────────
# Matched case-insensitively against the Advertiser column of uploaded files.
VERTICAL_KEYWORDS = {
    "Alcohol & Spirits": ["heineken", "grey goose", "smirnoff", "bacardi"],
    "Technology":        ["samsung", "apple", "sony", "microsoft"],
    "Retail":            ["kmart", "target", "woolworths", "coles"],
    "Automotive":        ["toyota", "bmw", "ford", "hyundai"],
    "Entertainment":     ["netflix", "disney", "spotify"],
    "Finance":           ["anz", "westpac", "commbank", "nab"],
    "Travel":            ["qantas", "airbnb", "booking.com"],
}

# ── Minimal column normaliser for benchmark files ─────────────────────────────
# Maps common DSP column names to the internal names this module expects.
_COL_MAP = {
    # Advertiser / brand
    "advertiser": "advertiser", "partner": "advertiser", "brand": "advertiser",
    "brand name": "advertiser", "insertion order": "advertiser",
    # Impressions
    "impressions": "impressions", "impression": "impressions",
    "served impressions": "impressions", "total impressions": "impressions",
    # Clicks
    "clicks": "clicks", "click": "clicks", "total clicks": "clicks",
    # Spend
    "spend": "spend", "spend (usd)": "spend", "total spend": "spend",
    "media cost": "spend", "media cost (usd)": "spend",
    "revenue (usd)": "spend", "cost": "spend", "billed spend": "spend",
    # CTR
    "ctr": "ctr", "click-through rate": "ctr",
    # CPM
    "cpm": "cpm", "avg. cpm": "cpm", "average cpm": "cpm",
    # VTR / video completion
    "vtr": "vtr", "view-through rate": "vtr",
    "video completion rate": "vtr", "vcr": "vtr",
    # CPV
    "cpv": "cpv", "cost per view": "cpv",
    # Format / environment
    "format": "format", "ad format": "format",
    "environment": "format", "environment type": "format",
    "inventory type": "format",
    # Device
    "device type": "device", "device": "device",
    "device_type": "device", "device category": "device",
}


def detect_vertical(advertiser_name):
    """Map an advertiser name to a vertical using keyword matching."""
    name_lower = str(advertiser_name).lower()
    for vertical, keywords in VERTICAL_KEYWORDS.items():
        if any(kw in name_lower for kw in keywords):
            return vertical
    return "Other"


def _read_upload(uploaded_file):
    """Read a CSV or Excel upload and return a raw DataFrame."""
    name = uploaded_file.name.lower()
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded_file)
    return pd.read_csv(uploaded_file)


def _normalise_bm_df(df):
    """
    Normalise column names to internal standards and clean numeric columns.
    Returns the normalised DataFrame.
    """
    # Lower-case + strip, then remap via _COL_MAP
    df.columns = [c.strip().lower() for c in df.columns]
    df = df.rename(columns={k: v for k, v in _COL_MAP.items() if k in df.columns})
    # Drop duplicate columns that arose from multiple source names mapping to one target
    df = df.loc[:, ~df.columns.duplicated(keep="first")]

    # Strip $, commas from numeric columns and coerce to float
    for col in ["impressions", "clicks", "spend", "ctr", "cpm", "vtr", "cpv"]:
        if col in df.columns:
            df[col] = (
                df[col].astype(str)
                .str.replace(r"[$,%,]", "", regex=True)
                .str.strip()
            )
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Recalculate CPM and CTR from raw totals if not already present
    if "cpm" not in df.columns and "spend" in df.columns and "impressions" in df.columns:
        df["cpm"] = df["spend"] / df["impressions"].clip(lower=1) * 1000
    if "ctr" not in df.columns and "clicks" in df.columns and "impressions" in df.columns:
        df["ctr"] = df["clicks"] / df["impressions"].clip(lower=1) * 100

    return df


def _is_video_row(row, has_format, has_vtr, has_cpv):
    """Return True if this row looks like a video placement."""
    if has_format:
        fmt_val = str(row.get("format", "")).lower()
        if any(kw in fmt_val for kw in ("video", "youtube", "pre-roll", "instream")):
            return True
    if has_vtr and pd.notna(row.get("vtr")) and row.get("vtr", 0) > 0:
        return True
    if has_cpv and pd.notna(row.get("cpv")) and row.get("cpv", 0) > 0:
        return True
    return False


def calculate_benchmarks(df):
    """
    Derive per-vertical Display and Video benchmarks from a normalised DataFrame.
    Returns a dict ready to be written to benchmarks.json.
    """
    # Tag each row with a vertical based on the advertiser name
    adv_col = "advertiser" if "advertiser" in df.columns else None
    df = df.copy()
    df["vertical"] = (
        df[adv_col].apply(detect_vertical) if adv_col else "Other"
    )

    # Tag each row as video or display
    has_format = "format" in df.columns
    has_vtr    = "vtr"    in df.columns
    has_cpv    = "cpv"    in df.columns
    df["is_video"] = df.apply(
        lambda r: _is_video_row(r, has_format, has_vtr, has_cpv), axis=1
    )

    results = {"display": {}, "video": {}}

    for vert in df["vertical"].unique():
        v_df = df[df["vertical"] == vert]

        # ── Display rows ──────────────────────────────────────────────────────
        disp = v_df[~v_df["is_video"]]
        if not disp.empty and "cpm" in disp.columns and disp["cpm"].notna().any():
            bm = {"campaign_count": len(disp)}
            # CPM — recalculate from totals when possible, else use column mean
            if "spend" in disp.columns and "impressions" in disp.columns:
                ts = disp["spend"].sum()
                ti = disp["impressions"].sum()
                bm["cpm"] = round(ts / ti * 1000, 2) if ti > 0 else round(disp["cpm"].mean(), 2)
            else:
                bm["cpm"] = round(disp["cpm"].mean(), 2)

            # CTR (percentage, e.g. 0.25 means 0.25%)
            if "clicks" in disp.columns and "impressions" in disp.columns:
                tc = disp["clicks"].sum()
                ti = disp["impressions"].sum()
                bm["ctr"] = round(tc / ti * 100, 3) if ti > 0 else None
            elif "ctr" in disp.columns:
                bm["ctr"] = round(disp["ctr"].mean(), 3)

            # CPC
            if "spend" in disp.columns and "clicks" in disp.columns:
                ts = disp["spend"].sum()
                tc = disp["clicks"].sum()
                bm["cpc"] = round(ts / tc, 2) if tc > 0 else None

            results["display"][vert] = bm

        # ── Video rows ────────────────────────────────────────────────────────
        vid = v_df[v_df["is_video"]]
        if not vid.empty and "cpm" in vid.columns and vid["cpm"].notna().any():
            bm = {"campaign_count": len(vid)}
            if "spend" in vid.columns and "impressions" in vid.columns:
                ts = vid["spend"].sum()
                ti = vid["impressions"].sum()
                bm["cpm"] = round(ts / ti * 1000, 2) if ti > 0 else round(vid["cpm"].mean(), 2)
            else:
                bm["cpm"] = round(vid["cpm"].mean(), 2)

            if has_vtr and vid["vtr"].notna().any():
                bm["vtr"] = round(vid["vtr"].mean(), 1)
            if has_cpv and vid["cpv"].notna().any():
                bm["cpv"] = round(vid["cpv"].mean(), 3)
            elif "spend" in vid.columns and "clicks" in vid.columns:
                ts = vid["spend"].sum()
                tc = vid["clicks"].sum()
                bm["cpv"] = round(ts / tc, 3) if tc > 0 else None

            results["video"][vert] = bm

    return results


def load_benchmarks():
    """Load custom benchmarks from benchmarks.json. Returns None if absent."""
    if os.path.exists(BENCHMARKS_PATH):
        with open(BENCHMARKS_PATH, "r") as f:
            return json.load(f)
    return None


def save_benchmarks(data):
    """Write the benchmarks dict to benchmarks.json."""
    with open(BENCHMARKS_PATH, "w") as f:
        json.dump(data, f, indent=2)


# ── Forecast + accuracy log helpers ──────────────────────────────────────────

def load_forecasts_log():
    """Load all saved forecasts from forecasts_log.json. Returns [] if absent."""
    if os.path.exists(FORECASTS_LOG_PATH):
        with open(FORECASTS_LOG_PATH, "r") as f:
            return json.load(f)
    return []


def append_forecast(entry):
    """Append one forecast dict to forecasts_log.json."""
    log = load_forecasts_log()
    log.append(entry)
    with open(FORECASTS_LOG_PATH, "w") as f:
        json.dump(log, f, indent=2)


def load_accuracy_log():
    """Load all saved comparisons from accuracy_log.json. Returns [] if absent."""
    if os.path.exists(ACCURACY_LOG_PATH):
        with open(ACCURACY_LOG_PATH, "r") as f:
            return json.load(f)
    return []


def append_accuracy(entry):
    """Append one accuracy comparison dict to accuracy_log.json."""
    log = load_accuracy_log()
    log.append(entry)
    with open(ACCURACY_LOG_PATH, "w") as f:
        json.dump(log, f, indent=2)


# ── Helper: render AI text as styled HTML ─────────────────────────────────────
# Matches the insight display style used in performance_insights.py.
def _insight_html(text):
    lines    = text.split("\n")
    parts    = []
    in_ul    = False
    p_style  = "margin:4px 0;color:#111111;font-size:14px;line-height:1.7;"
    li_style = "margin:2px 0;color:#111111;font-size:14px;"

    def apply_bold(s):
        return re.sub(r'\*\*(.+?)\*\*',
                      r'<strong style="color:#111111;">\1</strong>', s)

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_ul:
                parts.append("</ul>")
                in_ul = False
            continue
        if stripped.startswith("- ") or stripped.startswith("• "):
            if not in_ul:
                parts.append("<ul style='margin:6px 0 6px 18px;padding:0;'>")
                in_ul = True
            parts.append(f"<li style='{li_style}'>{apply_bold(stripped[2:])}</li>")
        else:
            if in_ul:
                parts.append("</ul>")
                in_ul = False
            parts.append(f"<p style='{p_style}'>{apply_bold(stripped)}</p>")

    if in_ul:
        parts.append("</ul>")

    return (
        "<div style='font-family:-apple-system,Segoe UI,Roboto,sans-serif;"
        "color:#111111;'>"
        + "\n".join(parts)
        + "</div>"
    )

# ── Page header ───────────────────────────────────────────────────────────────
st.title("Campaign Feasibility Checker")
st.markdown(
    "<p style='color:#6b7280;font-size:14px;margin-top:-12px;'>"
    "Validate campaign delivery before committing to clients."
    "</p>",
    unsafe_allow_html=True,
)

# ── Benchmark Data section ────────────────────────────────────────────────────
st.subheader("Benchmark Data")

bm_upload = st.file_uploader(
    "Upload historical DSP reports to calibrate benchmarks",
    type=["csv", "xlsx", "xls"],
    accept_multiple_files=True,
    help="Accepts TTD and DV360 exports. Multiple files accepted.",
)
st.caption("Accepts TTD and DV360 exports. Multiple files accepted.")

# Process uploaded files and write benchmarks.json
if bm_upload:
    with st.spinner("Processing uploaded reports…"):
        frames = []
        for f in bm_upload:
            try:
                raw = _read_upload(f)
                frames.append(_normalise_bm_df(raw))
            except Exception as e:
                st.warning(f"Could not read {f.name}: {e}")

        if frames:
            combined    = pd.concat(frames, ignore_index=True)
            total_rows  = len(combined)
            adv_col     = "advertiser" if "advertiser" in combined.columns else None
            adv_count   = combined[adv_col].nunique() if adv_col else 0

            derived = calculate_benchmarks(combined)
            derived["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            derived["row_count"]    = total_rows
            derived["adv_count"]    = adv_count
            save_benchmarks(derived)

            st.success(
                f"✅ Benchmarks updated from {total_rows:,} rows "
                f"across {adv_count} advertisers."
            )

# Benchmark status indicator
_loaded_bm = load_benchmarks()
if _loaded_bm:
    _bm_date = _loaded_bm.get("last_updated", "unknown date")
    st.markdown(
        f"<div style='background:#F0FDF4;border-left:4px solid #22C55E;"
        f"border-radius:6px;padding:10px 14px;font-size:13px;color:#166534;"
        f"margin-top:4px;'>"
        f"✅ Using historical benchmarks — last updated {_bm_date}</div>",
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        "<div style='background:#FFFBEB;border-left:4px solid #F59E0B;"
        "border-radius:6px;padding:10px 14px;font-size:13px;color:#92400E;"
        "margin-top:4px;'>"
        "⚠️ Using industry defaults — upload historical data for more accurate results</div>",
        unsafe_allow_html=True,
    )

# ── Section 1: Seller inputs form ─────────────────────────────────────────────
st.subheader("Campaign Brief")

with st.form("feasibility_form"):
    col_a, col_b = st.columns(2)

    with col_a:
        advertiser_name = st.text_input("Advertiser Name", placeholder="e.g. Coca-Cola")
        target_metric   = st.selectbox(
            "Target Metric",
            ["Impressions", "Revenue", "Clicks", "Video Views", "VTR"],
        )
        target_amount = st.number_input(
            "Target Amount",
            min_value=0.0,
            value=5_000_000.0,
            step=100_000.0,
            help="e.g. 5000000 for 5M impressions, or 75 for 75% VTR",
        )
        budget = st.number_input(
            "Budget (A$)",
            min_value=0.0,
            value=50_000.0,
            step=1_000.0,
        )

    with col_b:
        flight_start = st.date_input("Flight Start Date", value=date.today())
        flight_end   = st.date_input("Flight End Date",   value=date.today())
        vertical     = st.selectbox(
            "Vertical",
            ["FMCG", "Alcohol & Spirits", "Technology", "Retail", "Automotive",
             "Entertainment", "Finance", "Travel", "Other"],
        )
        device_types = st.multiselect(
            "Device Type",
            ["Desktop", "Mobile", "Tablet", "All Devices"],
            default=["All Devices"],
        )
        fmt = st.selectbox("Format", ["Display", "Video", "YouTube", "Mixed"])

    submitted = st.form_submit_button("Check Feasibility", type="primary")

# ── Process on submit ─────────────────────────────────────────────────────────
if submitted:
    # Store all inputs in session state so results persist across reruns
    st.session_state["fc_inputs"] = {
        "advertiser_name": advertiser_name,
        "target_metric":   target_metric,
        "target_amount":   target_amount,
        "budget":          budget,
        "flight_start":    flight_start,
        "flight_end":      flight_end,
        "vertical":        vertical,
        "device_types":    device_types,
        "fmt":             fmt,
    }
    # Clear any previous AI output so it doesn't carry over to a new check
    st.session_state.pop("fc_ai_text", None)
    # Flag so the results block knows to write one log entry for this submission
    st.session_state["fc_just_submitted"] = True

# ── Show results when inputs are stored ───────────────────────────────────────
if "fc_inputs" in st.session_state:
    inp = st.session_state["fc_inputs"]

    adv_name     = inp["advertiser_name"]
    tgt_metric   = inp["target_metric"]
    tgt_amount   = inp["target_amount"]
    budget       = inp["budget"]
    flight_start = inp["flight_start"]
    flight_end   = inp["flight_end"]
    vertical     = inp["vertical"]
    device_types = inp["device_types"]
    fmt          = inp["fmt"]

    # ── Section 2: Benchmark engine ───────────────────────────────────────────
    # Prefer benchmarks calculated from uploaded historical data (benchmarks.json).
    # Fall back to hardcoded industry defaults when no file is present.
    is_video    = fmt in ("Video", "YouTube")
    _custom_bm  = load_benchmarks()          # None if benchmarks.json doesn't exist

    if is_video:
        # Try custom benchmarks first, then fall back to hardcoded
        _custom_vid = (_custom_bm or {}).get("video", {})
        _src = _custom_vid.get(vertical) or _custom_vid.get("Other") or None
        if _src:
            cpm = _src.get("cpm", VIDEO_BENCHMARKS[vertical]["cpm"])
            vtr = _src.get("vtr", VIDEO_BENCHMARKS[vertical]["vtr"])
            cpv = _src.get("cpv", VIDEO_BENCHMARKS[vertical]["cpv"])
        else:
            bm  = VIDEO_BENCHMARKS.get(vertical, VIDEO_BENCHMARKS["Other"])
            cpm = bm["cpm"]
            vtr = bm["vtr"]
            cpv = bm["cpv"]
        ctr = None
        cpc = None
    else:
        _custom_dis = (_custom_bm or {}).get("display", {})
        _src = _custom_dis.get(vertical) or _custom_dis.get("Other") or None
        if _src:
            cpm = _src.get("cpm", DISPLAY_BENCHMARKS[vertical]["cpm"])
            ctr = _src.get("ctr", DISPLAY_BENCHMARKS[vertical]["ctr"])
            cpc = _src.get("cpc", DISPLAY_BENCHMARKS[vertical]["cpc"])
        else:
            bm  = DISPLAY_BENCHMARKS.get(vertical, DISPLAY_BENCHMARKS["Other"])
            cpm = bm["cpm"]
            ctr = bm["ctr"]
            cpc = bm["cpc"]
        vtr = None
        cpv = None

    # ── Section 3: Feasibility calculations ──────────────────────────────────
    flight_days = max((flight_end - flight_start).days, 1)

    # Estimated delivery from budget and benchmarks
    expected_impressions = (budget / cpm * 1000) if cpm > 0 else 0
    expected_clicks      = (expected_impressions * ctr / 100) if ctr else 0
    expected_revenue     = budget   # revenue = spend in this context
    expected_views       = (expected_impressions * vtr / 100) if vtr else 0
    expected_vtr         = vtr if vtr else 0   # benchmark VTR (%)

    # Map target metric to the estimated value we'll compare against
    estimated_for_target = {
        "Impressions":  expected_impressions,
        "Revenue":      expected_revenue,
        "Clicks":       expected_clicks,
        "Video Views":  expected_views,
        "VTR":          expected_vtr,
    }.get(tgt_metric, expected_impressions)

    # Delivery rate: how much of the target we expect to hit (capped display at 200%)
    delivery_rate = (estimated_for_target / tgt_amount * 100) if tgt_amount > 0 else 0

    # Daily pacing
    daily_spend       = budget / flight_days
    daily_impressions = expected_impressions / flight_days

    # Feasibility score = delivery rate (capped at 100) × confidence multiplier
    if flight_days < 7:
        confidence = 0.70
    elif flight_days <= 14:
        confidence = 0.85
    elif flight_days <= 30:
        confidence = 0.95
    else:
        confidence = 1.00

    raw_score = min(delivery_rate, 100) * confidence
    score     = round(raw_score, 1)

    def _score_label(s):
        if s <= 40: return "Not Feasible"
        if s <= 70: return "At Risk"
        if s <= 89: return "Feasible with Caution"
        return "Fully Feasible"

    # ── Auto-save forecast to log (once per submission) ───────────────────────
    if st.session_state.pop("fc_just_submitted", False):
        _bm_source = "Historical benchmarks" if load_benchmarks() else "Industry defaults"
        append_forecast({
            "forecast_id":             str(uuid.uuid4()),
            "created_at":              datetime.now().strftime("%Y-%m-%d"),
            "advertiser":              adv_name or "",
            "vertical":                vertical,
            "format":                  fmt,
            "device":                  ", ".join(device_types) if device_types else "",
            "budget_aud":              budget,
            "flight_days":             flight_days,
            "target_metric":           tgt_metric,
            "target_amount":           tgt_amount,
            "estimated_impressions":   round(expected_impressions),
            "estimated_clicks":        round(expected_clicks),
            "estimated_revenue":       round(expected_revenue),
            "estimated_views":         round(expected_views),
            "feasibility_score":       score,
            "status":                  _score_label(score),
            "benchmarks_source":       _bm_source,
        })

    # ── Section 4: Output display ─────────────────────────────────────────────
    st.subheader("Feasibility Results")

    # A) Feasibility score gauge + B) Traffic light — side by side
    score_col, status_col = st.columns([1, 1])

    with score_col:
        # Colour the gauge needle and arc by score band
        if score <= 40:
            gauge_color = "#EF4444"   # red
        elif score <= 70:
            gauge_color = "#F97316"   # orange
        elif score <= 89:
            gauge_color = "#EAB308"   # yellow
        else:
            gauge_color = "#22C55E"   # green

        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=score,
            number={
                "suffix": "/100",
                "font": {"size": 30, "color": "#111827", "family": "Inter, sans-serif"},
            },
            gauge={
                "axis": {
                    "range": [0, 100],
                    "tickwidth": 1,
                    "tickcolor": "#9CA3AF",
                    "tickfont": {"size": 11},
                },
                "bar":    {"color": gauge_color, "thickness": 0.28},
                "bgcolor": "#FFFFFF",
                "steps": [
                    {"range": [0,  40],  "color": "#FEE2E2"},
                    {"range": [40, 70],  "color": "#FEF3C7"},
                    {"range": [70, 89],  "color": "#FEF9C3"},
                    {"range": [89, 100], "color": "#DCFCE7"},
                ],
                "threshold": {
                    "line":      {"color": gauge_color, "width": 4},
                    "thickness": 0.75,
                    "value":     score,
                },
            },
        ))
        fig_gauge.update_layout(
            height=260,
            margin=dict(t=24, b=8, l=24, r=24),
            paper_bgcolor="#FFFFFF",
            font=dict(family="Inter, system-ui, sans-serif"),
        )
        st.markdown("**Feasibility Score**")
        st.plotly_chart(fig_gauge, use_container_width=True,
                        config={"displaylogo": False}, key="gauge_chart")

    with status_col:
        st.markdown("**Status**")
        if score <= 40:
            status_icon  = "❌"
            status_label = "Not Feasible"
            status_color = "#FEF2F2"
            border_color = "#EF4444"
            status_msg   = (
                "This campaign cannot deliver as promised. "
                "Recommend renegotiating targets or increasing budget."
            )
        elif score <= 70:
            status_icon  = "⚠️"
            status_label = "At Risk"
            status_color = "#FFFBEB"
            border_color = "#F59E0B"
            status_msg   = (
                "Delivery is uncertain. Review targeting and "
                "flight dates before committing."
            )
        elif score <= 89:
            status_icon  = "✅"
            status_label = "Feasible with Caution"
            status_color = "#FEFCE8"
            border_color = "#EAB308"
            status_msg   = (
                "Campaign is likely deliverable but monitor closely."
            )
        else:
            status_icon  = "✅"
            status_label = "Fully Feasible"
            status_color = "#F0FDF4"
            border_color = "#22C55E"
            status_msg   = (
                "Campaign is well-set up to deliver against targets."
            )

        st.markdown(
            f"<div style='background:{status_color};border-left:5px solid {border_color};"
            f"border-radius:8px;padding:20px 24px;margin-top:8px;'>"
            f"<div style='font-size:32px;margin-bottom:8px;'>{status_icon}</div>"
            f"<div style='font-size:20px;font-weight:700;color:#111827;"
            f"margin-bottom:8px;'>{status_label}</div>"
            f"<div style='font-size:14px;color:#374151;line-height:1.6;'>{status_msg}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

        # Key pacing metrics below the status card
        st.markdown("")
        m1, m2 = st.columns(2)
        m1.metric("Flight Duration",    f"{flight_days} days")
        m2.metric("Daily Budget",       f"A${daily_spend:,.0f}")
        m3, m4 = st.columns(2)
        m3.metric("Est. Impressions",   f"{expected_impressions:,.0f}")
        m4.metric("Daily Impressions",  f"{daily_impressions:,.0f}")

    # C) Metrics breakdown table
    st.subheader("Metrics Breakdown")

    # Build rows based on format
    table_rows = []

    def _gap_html(gap, is_pct=False):
        """Format gap value with green (positive) or red (negative) colour."""
        if is_pct:
            txt = f"+{gap:.1f}%" if gap >= 0 else f"{gap:.1f}%"
        else:
            txt = f"+{gap:,.0f}" if gap >= 0 else f"{gap:,.0f}"
        color = "#16A34A" if gap >= 0 else "#DC2626"
        return f"<span style='color:{color};font-weight:600;'>{txt}</span>"

    def _status_dot(ok):
        return "🟢" if ok else "🔴"

    # Impressions row — always shown
    imp_gap = expected_impressions - (tgt_amount if tgt_metric == "Impressions" else 0)
    tgt_imp_display = f"{tgt_amount:,.0f}" if tgt_metric == "Impressions" else "—"
    table_rows.append({
        "Metric": "Impressions",
        "Target": tgt_imp_display,
        "Estimated": f"{expected_impressions:,.0f}",
        "Gap": _gap_html(imp_gap) if tgt_metric == "Impressions" else "—",
        "Status": _status_dot(imp_gap >= 0) if tgt_metric == "Impressions" else "—",
    })

    # Clicks row — display and mixed
    if not is_video:
        clk_gap = expected_clicks - (tgt_amount if tgt_metric == "Clicks" else 0)
        tgt_clk_display = f"{tgt_amount:,.0f}" if tgt_metric == "Clicks" else "—"
        table_rows.append({
            "Metric": "Clicks",
            "Target": tgt_clk_display,
            "Estimated": f"{expected_clicks:,.0f}",
            "Gap": _gap_html(clk_gap) if tgt_metric == "Clicks" else "—",
            "Status": _status_dot(clk_gap >= 0) if tgt_metric == "Clicks" else "—",
        })
        # CTR row
        table_rows.append({
            "Metric": "CTR",
            "Target": "—",
            "Estimated": f"{ctr:.2f}%",
            "Gap": "—",
            "Status": "—",
        })

    # Revenue row — always shown
    rev_gap = expected_revenue - (tgt_amount if tgt_metric == "Revenue" else 0)
    tgt_rev_display = f"A${tgt_amount:,.0f}" if tgt_metric == "Revenue" else "—"
    table_rows.append({
        "Metric": "Revenue (A$)",
        "Target": tgt_rev_display,
        "Estimated": f"A${expected_revenue:,.0f}",
        "Gap": _gap_html(rev_gap) if tgt_metric == "Revenue" else "—",
        "Status": _status_dot(rev_gap >= 0) if tgt_metric == "Revenue" else "—",
    })

    # Video Views + VTR rows — video and YouTube formats
    if is_video:
        vv_gap = expected_views - (tgt_amount if tgt_metric == "Video Views" else 0)
        tgt_vv_display = f"{tgt_amount:,.0f}" if tgt_metric == "Video Views" else "—"
        table_rows.append({
            "Metric": "Video Views",
            "Target": tgt_vv_display,
            "Estimated": f"{expected_views:,.0f}",
            "Gap": _gap_html(vv_gap) if tgt_metric == "Video Views" else "—",
            "Status": _status_dot(vv_gap >= 0) if tgt_metric == "Video Views" else "—",
        })
        vtr_gap = expected_vtr - (tgt_amount if tgt_metric == "VTR" else 0)
        tgt_vtr_display = f"{tgt_amount:.1f}%" if tgt_metric == "VTR" else "—"
        table_rows.append({
            "Metric": "VTR (%)",
            "Target": tgt_vtr_display,
            "Estimated": f"{expected_vtr:.1f}%",
            "Gap": _gap_html(vtr_gap, is_pct=True) if tgt_metric == "VTR" else "—",
            "Status": _status_dot(vtr_gap >= 0) if tgt_metric == "VTR" else "—",
        })
        # CPV row
        table_rows.append({
            "Metric": "CPV (A$)",
            "Target": "—",
            "Estimated": f"A${cpv:.2f}",
            "Gap": "—",
            "Status": "—",
        })

    # CPM row — always shown
    table_rows.append({
        "Metric": "CPM (A$)",
        "Target": "—",
        "Estimated": f"A${cpm:.2f}",
        "Gap": "—",
        "Status": "—",
    })

    # Render the table as HTML so gap colours render properly
    header_style = (
        "background:#7C3AED;color:#FFFFFF;font-size:12px;font-weight:700;"
        "text-transform:uppercase;letter-spacing:0.05em;padding:10px 14px;"
        "text-align:left;"
    )
    row_style_even = "background:#F9FAFB;padding:9px 14px;font-size:14px;"
    row_style_odd  = "background:#FFFFFF;padding:9px 14px;font-size:14px;"

    table_html = (
        "<table style='width:100%;border-collapse:collapse;"
        "border-radius:10px;overflow:hidden;"
        "box-shadow:0 4px 12px rgba(0,0,0,0.08);'>"
        "<thead><tr>"
    )
    for col_name in ["Metric", "Target", "Estimated Delivery", "Gap", "Status"]:
        table_html += f"<th style='{header_style}'>{col_name}</th>"
    table_html += "</tr></thead><tbody>"

    for i, row in enumerate(table_rows):
        rs = row_style_even if i % 2 == 0 else row_style_odd
        table_html += "<tr>"
        table_html += f"<td style='{rs}font-weight:600;'>{row['Metric']}</td>"
        table_html += f"<td style='{rs}'>{row['Target']}</td>"
        table_html += f"<td style='{rs}'>{row['Estimated']}</td>"
        table_html += f"<td style='{rs}'>{row['Gap']}</td>"
        table_html += f"<td style='{rs}'>{row['Status']}</td>"
        table_html += "</tr>"

    table_html += "</tbody></table>"
    st.markdown(table_html, unsafe_allow_html=True)

    # D) Risk flags
    st.subheader("Risk Flags")

    flags = []

    if flight_days < 7:
        flags.append(("warning", "⚠️ Very short flight — high delivery risk"))

    if daily_spend > 5_000:
        flags.append(("warning",
                       f"⚠️ High daily spend required (A${daily_spend:,.0f}/day) — "
                       "check inventory availability"))

    if tgt_metric == "Impressions" and tgt_amount > 10_000_000 and flight_days < 14:
        flags.append(("warning", "⚠️ Very high volume in short window"))

    # Daily budget < CPM means you can't even serve 1,000 impressions per day
    if daily_spend < cpm:
        flags.append(("error",
                       f"❌ Daily budget (A${daily_spend:,.0f}) is below CPM "
                       f"(A${cpm:.2f}) — insufficient to serve even 1,000 impressions per day"))

    if is_video and tgt_metric == "VTR" and tgt_amount > 80:
        flags.append(("warning", "⚠️ VTR target above typical benchmark (usually 69–76%)"))

    if fmt == "Display" and tgt_metric == "VTR":
        flags.append(("error", "❌ VTR is not applicable for Display campaigns"))

    if not flags:
        st.markdown(
            "<div style='background:#F0FDF4;border-left:4px solid #22C55E;"
            "border-radius:8px;padding:12px 16px;font-size:14px;color:#166534;'>"
            "✅ No risk flags detected.</div>",
            unsafe_allow_html=True,
        )
    else:
        for flag_type, flag_text in flags:
            bg    = "#FEF2F2" if flag_type == "error" else "#FFFBEB"
            border = "#EF4444" if flag_type == "error" else "#F59E0B"
            text_c = "#991B1B" if flag_type == "error" else "#92400E"
            st.markdown(
                f"<div style='background:{bg};border-left:4px solid {border};"
                f"border-radius:8px;padding:10px 16px;margin-bottom:8px;"
                f"font-size:14px;color:{text_c};'>{flag_text}</div>",
                unsafe_allow_html=True,
            )

    # ── Section 5: AI Recommendations ────────────────────────────────────────
    st.subheader("AI Recommendations")

    api_key = (
        st.secrets.get("ANTHROPIC_API_KEY")
        if "ANTHROPIC_API_KEY" in st.secrets
        else os.environ.get("ANTHROPIC_API_KEY")
    )

    if not api_key:
        st.warning(
            "No Anthropic API key found. Add `ANTHROPIC_API_KEY` to your "
            "Streamlit secrets or environment variables to enable AI recommendations."
        )
    else:
        if st.button("✨ Get AI Recommendations", type="primary",
                     key="fc_ai_btn"):

            # Build a compact summary of all inputs and calculated results for the prompt
            devices_str = ", ".join(device_types) if device_types else "Not specified"
            flags_str   = "\n".join(f"- {t}" for _, t in flags) if flags else "None"

            prompt = (
                f"You are a senior programmatic trader at Captify reviewing a campaign "
                f"brief from a seller. Here are the campaign details and feasibility results:\n\n"
                f"CAMPAIGN BRIEF:\n"
                f"- Advertiser: {adv_name or 'Not specified'}\n"
                f"- Format: {fmt}\n"
                f"- Vertical: {vertical}\n"
                f"- Device Types: {devices_str}\n"
                f"- Budget: A${budget:,.0f}\n"
                f"- Flight: {flight_start} to {flight_end} ({flight_days} days)\n"
                f"- Target Metric: {tgt_metric}\n"
                f"- Target Amount: {tgt_amount:,.0f}"
                f"{'%' if tgt_metric == 'VTR' else ''}\n\n"
                f"BENCHMARK USED ({vertical} — {fmt}):\n"
                f"- CPM: A${cpm:.2f}\n"
                + (f"- CTR: {ctr:.2f}%\n- CPC: A${cpc:.2f}\n" if ctr else "")
                + (f"- VTR: {vtr:.0f}%\n- CPV: A${cpv:.2f}\n" if vtr else "")
                + f"\nCALCULATED ESTIMATES:\n"
                f"- Expected Impressions: {expected_impressions:,.0f}\n"
                f"- Expected Clicks: {expected_clicks:,.0f}\n"
                + (f"- Expected Video Views: {expected_views:,.0f}\n" if is_video else "")
                + f"- Expected Revenue: A${expected_revenue:,.0f}\n"
                f"- Daily Spend Required: A${daily_spend:,.0f}\n"
                f"- Daily Impressions: {daily_impressions:,.0f}\n\n"
                f"FEASIBILITY SCORE: {score}/100 ({status_label})\n"
                f"DELIVERY RATE: {delivery_rate:.1f}%\n\n"
                f"RISK FLAGS:\n{flags_str}\n\n"
                f"Provide:\n"
                f"1. A one-paragraph plain-English feasibility summary for the seller\n"
                f"2. Three specific actions the trader should take to improve delivery\n"
                f"3. One alternative proposal if the campaign is not feasible as briefed "
                f"(e.g. reduce target, extend flight, increase budget)\n\n"
                f"Be direct and specific. Use real programmatic terminology. "
                f"All currency values are in AUD."
            )

            client_ai = anthropic.Anthropic(api_key=api_key)
            with st.spinner("Generating recommendations…"):
                msg = client_ai.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=700,
                    system=(
                        "You are a senior programmatic trader at Captify. "
                        "Write clear, direct, data-driven recommendations. "
                        "Be specific — reference actual numbers from the brief. "
                        "Use programmatic advertising terminology."
                    ),
                    messages=[{"role": "user", "content": prompt}],
                )
            st.session_state["fc_ai_text"] = msg.content[0].text.strip()
            # Store the context used to generate this AI output (for export)
            st.session_state["fc_status_label"] = status_label
            st.session_state["fc_flags"]         = flags

        # Show AI output if it has been generated
        if "fc_ai_text" in st.session_state:
            st.markdown(
                "<div style='background:#FFFFFF;border-radius:12px;padding:20px 24px;"
                "box-shadow:0 4px 12px rgba(0,0,0,0.08);margin-top:12px;'>"
                + _insight_html(st.session_state["fc_ai_text"])
                + "</div>",
                unsafe_allow_html=True,
            )

    # ── Section 6: Export ─────────────────────────────────────────────────────
    st.subheader("Export Report")

    # Build a plain-text summary of everything — inputs, scores, flags, AI output
    devices_str_exp = ", ".join(device_types) if device_types else "Not specified"
    flags_str_exp   = "\n".join(f"  {t}" for _, t in flags) if flags else "  None"
    ai_text_exp     = st.session_state.get("fc_ai_text", "Not generated")

    report_lines = [
        "=" * 60,
        "CAMPAIGN FEASIBILITY REPORT",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "=" * 60,
        "",
        "CAMPAIGN BRIEF",
        "-" * 40,
        f"Advertiser:      {adv_name or 'Not specified'}",
        f"Format:          {fmt}",
        f"Vertical:        {vertical}",
        f"Device Types:    {devices_str_exp}",
        f"Budget:          A${budget:,.0f}",
        f"Flight:          {flight_start} to {flight_end} ({flight_days} days)",
        f"Target Metric:   {tgt_metric}",
        f"Target Amount:   {tgt_amount:,.0f}"
        + ("%" if tgt_metric == "VTR" else ""),
        "",
        "BENCHMARKS USED",
        "-" * 40,
        f"CPM:             A${cpm:.2f}",
    ]
    if ctr:
        report_lines += [f"CTR:             {ctr:.2f}%", f"CPC:             A${cpc:.2f}"]
    if vtr:
        report_lines += [f"VTR:             {vtr:.0f}%", f"CPV:             A${cpv:.2f}"]

    report_lines += [
        "",
        "ESTIMATED DELIVERY",
        "-" * 40,
        f"Impressions:     {expected_impressions:,.0f}",
        f"Clicks:          {expected_clicks:,.0f}",
    ]
    if is_video:
        report_lines.append(f"Video Views:     {expected_views:,.0f}")
    report_lines += [
        f"Revenue:         A${expected_revenue:,.0f}",
        f"Daily Spend:     A${daily_spend:,.0f}",
        f"Daily Imps:      {daily_impressions:,.0f}",
        "",
        "FEASIBILITY SCORE",
        "-" * 40,
        f"Score:           {score}/100",
        f"Status:          {st.session_state.get('fc_status_label', status_label)}",
        f"Delivery Rate:   {delivery_rate:.1f}%",
        f"Confidence Mult: {confidence}x ({flight_days}-day flight)",
        "",
        "RISK FLAGS",
        "-" * 40,
        flags_str_exp,
        "",
        "AI RECOMMENDATIONS",
        "-" * 40,
        ai_text_exp,
        "",
        "=" * 60,
    ]

    report_text = "\n".join(report_lines)
    report_bytes = report_text.encode("utf-8")

    filename = (
        f"{datetime.now().strftime('%Y-%m-%d')}_"
        f"{(adv_name or 'campaign').replace(' ', '_')}_feasibility.txt"
    )

    st.download_button(
        label="📥 Download Feasibility Report (.txt)",
        data=report_bytes,
        file_name=filename,
        mime="text/plain",
    )

# ═════════════════════════════════════════════════════════════════════════════
# FORECAST ACCURACY TRACKER
# ═════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("Forecast Accuracy Tracker")
st.markdown(
    "<p style='color:#6b7280;font-size:14px;margin-top:-12px;'>"
    "Compare forecasted delivery against actual post-campaign results to "
    "measure and improve forecast precision."
    "</p>",
    unsafe_allow_html=True,
)

# ── Section 1: Upload post-campaign report ────────────────────────────────────
_actual_report = st.file_uploader(
    "Upload post-campaign report to validate forecast",
    type=["csv", "xlsx", "xls"],
    key="accuracy_upload",
)
st.caption(
    "Upload the actual delivery report after a campaign ends to compare "
    "against your forecast."
)

_fc_log = load_forecasts_log()

with st.form("accuracy_form"):
    _acc_c1, _acc_c2 = st.columns(2)
    with _acc_c1:
        _acc_advertiser = st.text_input("Advertiser Name", key="acc_adv_input")
    with _acc_c2:
        _acc_campaign = st.text_input("Campaign Name", key="acc_camp_input")

    if _fc_log:
        # Each option shows date | advertiser | target metric | feasibility score
        _fc_labels = [
            f"{fc.get('created_at','?')}  |  {fc.get('advertiser','?')}  |  "
            f"{fc.get('target_metric','?')}  |  Score: {fc.get('feasibility_score','?')}"
            for fc in _fc_log
        ]
        _sel_fc_idx = st.selectbox(
            "Select a saved forecast to compare against",
            options=range(len(_fc_labels)),
            format_func=lambda i: _fc_labels[i],
        )
    else:
        st.info("No saved forecasts yet. Run a feasibility check first.")
        _sel_fc_idx = None

    _compare_btn = st.form_submit_button("Compare Forecast vs Actual", type="primary")

# ── Run comparison ────────────────────────────────────────────────────────────
if _compare_btn and _actual_report is not None and _sel_fc_idx is not None and _fc_log:
    try:
        _adf      = _normalise_bm_df(_read_upload(_actual_report))
        _fc_entry = _fc_log[_sel_fc_idx]

        # Sum actual totals from the uploaded delivery report
        _act_imps   = float(_adf["impressions"].sum()) if "impressions" in _adf.columns else 0.0
        _act_clicks = float(_adf["clicks"].sum())      if "clicks"      in _adf.columns else 0.0
        _act_rev    = float(_adf["spend"].sum())        if "spend"       in _adf.columns else 0.0
        # Video views: impressions × (VTR/100) per row when both columns exist
        if "impressions" in _adf.columns and "vtr" in _adf.columns:
            _act_views = float((_adf["impressions"] * _adf["vtr"] / 100).sum())
        else:
            _act_views = 0.0

        # Forecasted values from the selected log entry
        _fore_imps   = float(_fc_entry.get("estimated_impressions", 0))
        _fore_clicks = float(_fc_entry.get("estimated_clicks",      0))
        _fore_rev    = float(_fc_entry.get("estimated_revenue",     0))
        _fore_views  = float(_fc_entry.get("estimated_views",       0))

        def _pct_accuracy(forecasted, actual):
            """100 minus absolute percentage error, clamped 0–100. None if no forecast."""
            if not forecasted:
                return None
            return max(0.0, round(100 - abs((actual - forecasted) / forecasted * 100), 1))

        _acc_imps   = _pct_accuracy(_fore_imps,   _act_imps)
        _acc_clicks = _pct_accuracy(_fore_clicks, _act_clicks)
        _acc_rev    = _pct_accuracy(_fore_rev,    _act_rev)
        _acc_views  = _pct_accuracy(_fore_views,  _act_views) if _fore_views else None

        _acc_values  = [v for v in [_acc_imps, _acc_clicks, _acc_rev, _acc_views]
                        if v is not None]
        _overall_acc = round(sum(_acc_values) / len(_acc_values), 1) if _acc_values else 0.0

        st.session_state["fc_comparison"] = {
            "forecast":    _fc_entry,
            "act_imps":    _act_imps,    "act_clicks": _act_clicks,
            "act_rev":     _act_rev,     "act_views":  _act_views,
            "acc_imps":    _acc_imps,    "acc_clicks": _acc_clicks,
            "acc_rev":     _acc_rev,     "acc_views":  _acc_views,
            "overall_acc": _overall_acc,
        }

        # Save to accuracy_log.json
        append_accuracy({
            "comparison_id":          str(uuid.uuid4()),
            "forecast_id":            _fc_entry.get("forecast_id", ""),
            "compared_at":            datetime.now().strftime("%Y-%m-%d"),
            "advertiser":             _acc_advertiser or _fc_entry.get("advertiser", ""),
            "campaign":               _acc_campaign,
            "vertical":               _fc_entry.get("vertical", "Other"),
            "format":                 _fc_entry.get("format", ""),
            "forecasted_impressions": _fore_imps,
            "actual_impressions":     _act_imps,
            "impressions_accuracy":   _acc_imps,
            "forecasted_clicks":      _fore_clicks,
            "actual_clicks":          _act_clicks,
            "clicks_accuracy":        _acc_clicks,
            "forecasted_revenue":     _fore_rev,
            "actual_revenue":         _act_rev,
            "revenue_accuracy":       _acc_rev,
            "forecasted_views":       _fore_views,
            "actual_views":           _act_views,
            "views_accuracy":         _acc_views,
            "overall_accuracy":       _overall_acc,
            "benchmarks_source":      _fc_entry.get("benchmarks_source", "Industry defaults"),
        })
        st.success("✅ Comparison saved to accuracy log.")

    except Exception as _e:
        st.error(f"Could not process the report: {_e}")

# ── Section 3: Comparison output ──────────────────────────────────────────────
if "fc_comparison" in st.session_state:
    _cmp = st.session_state["fc_comparison"]
    _fce = _cmp["forecast"]

    st.markdown("#### Forecast vs Actual")

    # A) Accuracy table
    def _acc_span(acc):
        if acc is None:
            return "—"
        color = "#16A34A" if acc > 85 else "#D97706" if acc >= 70 else "#DC2626"
        return f"<span style='color:{color};font-weight:700;'>{acc:.1f}%</span>"

    def _var_span(fore, actual):
        if not fore:
            return "—"
        gap  = actual - fore
        col  = "#16A34A" if gap >= 0 else "#DC2626"
        sign = "+" if gap >= 0 else ""
        return f"<span style='color:{col};'>{sign}{gap:,.0f}</span>"

    _rows = [
        ("Impressions",
         f"{_fce.get('estimated_impressions',0):,.0f}",
         f"{_cmp['act_imps']:,.0f}",
         _var_span(_fce.get('estimated_impressions',0), _cmp['act_imps']),
         _acc_span(_cmp['acc_imps'])),
        ("Clicks",
         f"{_fce.get('estimated_clicks',0):,.0f}",
         f"{_cmp['act_clicks']:,.0f}",
         _var_span(_fce.get('estimated_clicks',0), _cmp['act_clicks']),
         _acc_span(_cmp['acc_clicks'])),
        ("Revenue (A$)",
         f"A${_fce.get('estimated_revenue',0):,.0f}",
         f"A${_cmp['act_rev']:,.0f}",
         _var_span(_fce.get('estimated_revenue',0), _cmp['act_rev']),
         _acc_span(_cmp['acc_rev'])),
    ]
    if _fce.get("estimated_views", 0) > 0:
        _rows.append((
            "Video Views",
            f"{_fce.get('estimated_views',0):,.0f}",
            f"{_cmp['act_views']:,.0f}",
            _var_span(_fce.get('estimated_views',0), _cmp['act_views']),
            _acc_span(_cmp['acc_views']),
        ))

    _hs = ("background:#7C3AED;color:#FFFFFF;font-size:12px;font-weight:700;"
           "text-transform:uppercase;letter-spacing:0.05em;padding:10px 14px;text-align:left;")
    _tbl = ("<table style='width:100%;border-collapse:collapse;border-radius:10px;"
            "overflow:hidden;box-shadow:0 4px 12px rgba(0,0,0,0.08);'>"
            "<thead><tr>")
    for _h in ["Metric", "Forecasted", "Actual", "Variance", "Accuracy %"]:
        _tbl += f"<th style='{_hs}'>{_h}</th>"
    _tbl += "</tr></thead><tbody>"
    for _ri, (_m, _fo, _ac, _va, _ap) in enumerate(_rows):
        _rs = ("background:#F9FAFB;" if _ri % 2 == 0 else "background:#FFFFFF;") + "padding:9px 14px;font-size:14px;"
        _tbl += (f"<tr><td style='{_rs}font-weight:600;'>{_m}</td>"
                 f"<td style='{_rs}'>{_fo}</td><td style='{_rs}'>{_ac}</td>"
                 f"<td style='{_rs}'>{_va}</td><td style='{_rs}'>{_ap}</td></tr>")
    _tbl += "</tbody></table>"
    st.markdown(_tbl, unsafe_allow_html=True)

    # B) Accuracy score gauge
    st.markdown("")
    _oa      = _cmp["overall_acc"]
    _gc      = "#EF4444" if _oa < 70 else "#F97316" if _oa < 85 else "#22C55E"
    _fig_acc = go.Figure(go.Indicator(
        mode="gauge+number",
        value=_oa,
        number={"suffix": "%", "font": {"size": 30, "color": "#111827",
                                         "family": "Inter, sans-serif"}},
        title={"text": "Overall Forecast Accuracy",
               "font": {"size": 14, "color": "#374151"}},
        gauge={
            "axis":   {"range": [0, 100], "tickwidth": 1, "tickcolor": "#9CA3AF"},
            "bar":    {"color": _gc, "thickness": 0.28},
            "bgcolor": "#FFFFFF",
            "steps":  [{"range": [0,  70],  "color": "#FEE2E2"},
                       {"range": [70, 85],  "color": "#FEF3C7"},
                       {"range": [85, 100], "color": "#DCFCE7"}],
            "threshold": {"line": {"color": _gc, "width": 4},
                          "thickness": 0.75, "value": _oa},
        },
    ))
    _fig_acc.update_layout(
        height=260, margin=dict(t=40, b=8, l=24, r=24),
        paper_bgcolor="#FFFFFF",
        font=dict(family="Inter, system-ui, sans-serif"),
    )
    _g_col, _ = st.columns([1, 1])
    with _g_col:
        st.plotly_chart(_fig_acc, use_container_width=True,
                        config={"displaylogo": False}, key="accuracy_gauge")

# ── Section 4: Precision History Dashboard ────────────────────────────────────
_acc_log = load_accuracy_log()

if _acc_log:
    with st.expander("📊 View Accuracy History", expanded=False):

        _adf_hist = pd.DataFrame(_acc_log)
        # Ensure the date column is parsed for sorting / monthly grouping
        _adf_hist["compared_at"] = pd.to_datetime(
            _adf_hist["compared_at"], errors="coerce"
        )
        _adf_hist = _adf_hist.sort_values("compared_at")

        # A) Accuracy trend over time
        _trend = (_adf_hist[["compared_at", "overall_accuracy"]]
                  .dropna()
                  .sort_values("compared_at"))
        if not _trend.empty:
            st.markdown("**Accuracy Trend Over Time**")
            _fig_trend = go.Figure()
            _fig_trend.add_trace(go.Scatter(
                x=_trend["compared_at"], y=_trend["overall_accuracy"],
                mode="lines+markers",
                line=dict(color="#7C3AED", width=2),
                marker=dict(size=7, color="#7C3AED"),
                name="Overall Accuracy",
                hovertemplate="%{x|%Y-%m-%d}<br>Accuracy: <b>%{y:.1f}%</b><extra></extra>",
            ))
            # 85% reference line
            _fig_trend.add_hline(
                y=85, line_dash="dash", line_color="#22C55E",
                annotation_text="Target (85%)", annotation_position="bottom right",
            )
            _fig_trend.update_layout(
                plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
                margin=dict(t=20, b=40, l=50, r=20),
                yaxis=dict(range=[0, 105], ticksuffix="%",
                           gridcolor="#F3F4F6", title="Accuracy %"),
                xaxis=dict(gridcolor="#F3F4F6"),
                showlegend=False,
            )
            st.plotly_chart(_fig_trend, use_container_width=True,
                            config={"displaylogo": False}, key="trend_chart")

        # B) Accuracy by vertical + C) by format — side by side
        _by_vert_col, _by_fmt_col = st.columns(2)

        with _by_vert_col:
            st.markdown("**Accuracy by Vertical**")
            if "vertical" in _adf_hist.columns:
                _by_vert = (_adf_hist.groupby("vertical")["overall_accuracy"]
                            .mean().reset_index()
                            .sort_values("overall_accuracy", ascending=False))
                _fig_vert = go.Figure(go.Bar(
                    x=_by_vert["vertical"],
                    y=_by_vert["overall_accuracy"],
                    marker_color="#7C3AED",
                    text=[f"{v:.1f}%" for v in _by_vert["overall_accuracy"]],
                    textposition="outside",
                ))
                _fig_vert.update_layout(
                    plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
                    margin=dict(t=20, b=60, l=50, r=10),
                    yaxis=dict(range=[0, 110], ticksuffix="%",
                               gridcolor="#F3F4F6"),
                    bargap=0.4, showlegend=False,
                )
                st.plotly_chart(_fig_vert, use_container_width=True,
                                config={"displaylogo": False}, key="vert_chart")

        with _by_fmt_col:
            st.markdown("**Accuracy by Format**")
            if "format" in _adf_hist.columns:
                _by_fmt = (_adf_hist.groupby("format")["overall_accuracy"]
                           .mean().reset_index()
                           .sort_values("overall_accuracy", ascending=False))
                _fmt_colors = {"Display": "#2563EB", "Video": "#7C3AED",
                               "YouTube": "#EF4444", "Mixed": "#10B981"}
                _fig_fmt = go.Figure(go.Bar(
                    x=_by_fmt["format"],
                    y=_by_fmt["overall_accuracy"],
                    marker_color=[_fmt_colors.get(f, "#6B7280")
                                  for f in _by_fmt["format"]],
                    text=[f"{v:.1f}%" for v in _by_fmt["overall_accuracy"]],
                    textposition="outside",
                ))
                _fig_fmt.update_layout(
                    plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
                    margin=dict(t=20, b=60, l=50, r=10),
                    yaxis=dict(range=[0, 110], ticksuffix="%",
                               gridcolor="#F3F4F6"),
                    bargap=0.4, showlegend=False,
                )
                st.plotly_chart(_fig_fmt, use_container_width=True,
                                config={"displaylogo": False}, key="fmt_chart")

        # D) Accuracy by benchmark source
        st.markdown("**Accuracy by Benchmark Source**")
        if "benchmarks_source" in _adf_hist.columns:
            _by_src = (_adf_hist.groupby("benchmarks_source")["overall_accuracy"]
                       .mean().reset_index())
            _src_colors = {"Industry defaults":     "#F59E0B",
                           "Historical benchmarks": "#22C55E"}
            _fig_src = go.Figure(go.Bar(
                x=_by_src["benchmarks_source"],
                y=_by_src["overall_accuracy"],
                marker_color=[_src_colors.get(s, "#6B7280")
                              for s in _by_src["benchmarks_source"]],
                text=[f"{v:.1f}%" for v in _by_src["overall_accuracy"]],
                textposition="outside",
            ))
            _fig_src.update_layout(
                plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
                margin=dict(t=20, b=60, l=50, r=10),
                yaxis=dict(range=[0, 110], ticksuffix="%", gridcolor="#F3F4F6"),
                bargap=0.5, showlegend=False,
            )
            st.plotly_chart(_fig_src, use_container_width=True,
                            config={"displaylogo": False}, key="src_chart")

        # E) Summary stats cards
        st.markdown("**Summary Statistics**")

        _total_forecasts    = len(load_forecasts_log())
        _total_comparisons  = len(_acc_log)
        _avg_accuracy       = round(_adf_hist["overall_accuracy"].mean(), 1)
        # Best vertical: highest mean accuracy
        _best_vert = "—"
        if "vertical" in _adf_hist.columns and not _adf_hist.empty:
            _bv = (_adf_hist.groupby("vertical")["overall_accuracy"]
                   .mean().idxmax())
            _best_vert = str(_bv)
        # Most improved month: month with biggest accuracy gain vs previous month
        _best_month = "—"
        if not _trend.empty and len(_trend) >= 2:
            _monthly = (_trend.set_index("compared_at")["overall_accuracy"]
                        .resample("ME").mean().dropna())
            if len(_monthly) >= 2:
                _gains = _monthly.diff().dropna()
                if not _gains.empty:
                    _best_month = _gains.idxmax().strftime("%B %Y")

        _sc1, _sc2, _sc3, _sc4, _sc5 = st.columns(5)
        _sc1.metric("Total Forecasts",       str(_total_forecasts))
        _sc2.metric("Comparisons Done",      str(_total_comparisons))
        _sc3.metric("Avg Accuracy",          f"{_avg_accuracy}%")
        _sc4.metric("Best Vertical",         _best_vert)
        _sc5.metric("Most Improved Month",   _best_month)

    # ── Section 5: AI Accuracy Insights ───────────────────────────────────────
    st.markdown("#### Accuracy Insights")

    _ai_api_key = (
        st.secrets.get("ANTHROPIC_API_KEY")
        if "ANTHROPIC_API_KEY" in st.secrets
        else os.environ.get("ANTHROPIC_API_KEY")
    )

    if not _ai_api_key:
        st.warning(
            "No Anthropic API key found — add `ANTHROPIC_API_KEY` to secrets "
            "to enable AI accuracy insights."
        )
    else:
        if st.button("✨ Generate Accuracy Insights", type="primary",
                     key="acc_ai_btn"):
            _log_text = json.dumps(_acc_log, indent=2)
            _acc_prompt = (
                "You are analysing the forecast accuracy of a programmatic campaign "
                "forecasting tool at Captify. Here is the accuracy log data:\n\n"
                f"{_log_text}\n\n"
                "Provide:\n"
                "1. Overall assessment of forecast precision\n"
                "2. Which variables are causing the most forecast error\n"
                "3. Three specific recommendations to improve forecast accuracy\n"
                "4. Whether historical benchmarks are outperforming industry defaults\n\n"
                "Be direct and specific. Reference actual numbers from the log."
            )
            _acc_client = anthropic.Anthropic(api_key=_ai_api_key)
            with st.spinner("Analysing accuracy log…"):
                _acc_msg = _acc_client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=600,
                    system=(
                        "You are a senior programmatic trading analyst at Captify. "
                        "Write clear, data-driven analysis of forecast accuracy. "
                        "Reference actual numbers. Be concise and actionable."
                    ),
                    messages=[{"role": "user", "content": _acc_prompt}],
                )
            st.session_state["acc_ai_text"] = _acc_msg.content[0].text.strip()

        if "acc_ai_text" in st.session_state:
            st.markdown(
                "<div style='background:#FFFFFF;border-radius:12px;padding:20px 24px;"
                "box-shadow:0 4px 12px rgba(0,0,0,0.08);margin-top:12px;'>"
                + _insight_html(st.session_state["acc_ai_text"])
                + "</div>",
                unsafe_allow_html=True,
            )

print("Done. Forecasting tool loaded.")
