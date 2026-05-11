import io
import os
import re
from datetime import date, datetime
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
    "FMCG":              {"ctr": 0.25, "cpm": 18.00, "cpc": 7.20},
    "Alcohol & Spirits": {"ctr": 0.20, "cpm": 27.00, "cpc": 13.50},
    "Technology":        {"ctr": 0.35, "cpm": 21.00, "cpc": 6.00},
    "Retail":            {"ctr": 0.45, "cpm": 15.00, "cpc": 3.33},
    "Automotive":        {"ctr": 0.18, "cpm": 30.00, "cpc": 16.67},
    "Entertainment":     {"ctr": 0.30, "cpm": 17.00, "cpc": 5.67},
    "Finance":           {"ctr": 0.22, "cpm": 33.00, "cpc": 15.00},
    "Travel":            {"ctr": 0.28, "cpm": 24.00, "cpc": 8.57},
    "Other":             {"ctr": 0.25, "cpm": 23.00, "cpc": 9.20},
}

VIDEO_BENCHMARKS = {
    "FMCG":              {"vtr": 72, "cpv": 0.06, "cpm": 42.00},
    "Alcohol & Spirits": {"vtr": 75, "cpv": 0.08, "cpm": 53.00},
    "Technology":        {"vtr": 70, "cpv": 0.05, "cpm": 38.00},
    "Retail":            {"vtr": 71, "cpv": 0.05, "cpm": 33.00},
    "Automotive":        {"vtr": 74, "cpv": 0.08, "cpm": 57.00},
    "Entertainment":     {"vtr": 73, "cpv": 0.06, "cpm": 42.00},
    "Finance":           {"vtr": 69, "cpv": 0.08, "cpm": 60.00},
    "Travel":            {"vtr": 76, "cpv": 0.06, "cpm": 48.00},
    "Other":             {"vtr": 72, "cpv": 0.06, "cpm": 42.00},
}

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
    # Use hardcoded industry benchmarks (no live data stored in session state).
    # For Video and YouTube formats, use video benchmarks.
    # For Mixed, use display benchmarks as the base.
    is_video = fmt in ("Video", "YouTube")

    if is_video:
        bm = VIDEO_BENCHMARKS.get(vertical, VIDEO_BENCHMARKS["Other"])
        cpm = bm["cpm"]
        vtr = bm["vtr"]       # percentage, e.g. 72 means 72%
        cpv = bm["cpv"]
        ctr = None
        cpc = None
    else:
        bm  = DISPLAY_BENCHMARKS.get(vertical, DISPLAY_BENCHMARKS["Other"])
        cpm = bm["cpm"]
        ctr = bm["ctr"]       # percentage, e.g. 0.25 means 0.25%
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

print("Done. Forecasting tool loaded.")
