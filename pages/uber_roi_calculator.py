import io
import os

import anthropic
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN


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

    /* ── Secondary / default buttons ────────────────────────────── */
    .stButton > button[kind="secondary"],
    [data-testid="baseButton-secondary"] {
        border-radius: 8px !important;
        font-weight: 600 !important;
    }

    /* ── Data tables ─────────────────────────────────────────────── */
    [data-testid="stDataFrame"] {
        background: #FFFFFF;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.06);
    }
</style>
""", unsafe_allow_html=True)
# STYLE LOCK


# ── Category benchmarks (hardcoded) ─────────────────────────────────────────────
# avg_cpo  = average cost per order in AUD
# avg_roas = average return on ad spend (revenue / ad spend)
# avg_ctr  = average click-through rate (%)
# incr_rate = incremental order rate — share of ad-driven orders that are truly new
CATEGORY_BENCHMARKS = {
    "QSR Burgers":        {"avg_cpo": 9.50,  "avg_roas": 3.4, "avg_ctr": 2.9, "incr_rate": 0.58},
    "Pizza":              {"avg_cpo": 8.20,  "avg_roas": 3.6, "avg_ctr": 3.2, "incr_rate": 0.60},
    "Mexican":            {"avg_cpo": 10.50, "avg_roas": 2.9, "avg_ctr": 2.7, "incr_rate": 0.55},
    "Asian":              {"avg_cpo": 9.80,  "avg_roas": 3.1, "avg_ctr": 2.8, "incr_rate": 0.56},
    "Healthy/Salads":     {"avg_cpo": 11.20, "avg_roas": 2.7, "avg_ctr": 2.5, "incr_rate": 0.52},
    "Coffee & Breakfast": {"avg_cpo": 7.80,  "avg_roas": 3.8, "avg_ctr": 3.5, "incr_rate": 0.62},
    "Other":              {"avg_cpo": 10.00, "avg_roas": 3.0, "avg_ctr": 2.8, "incr_rate": 0.56},
}

# ── Daypart base weight distribution ────────────────────────────────────────────
# Reflects typical Uber Eats order volume distribution across the day
DAYPART_BASE_WEIGHTS = {
    "Breakfast":  0.08,
    "Lunch":      0.25,
    "Afternoon":  0.10,
    "Dinner":     0.42,
    "Late Night": 0.15,
}

# ── Scenario multipliers applied to the adjusted benchmark ROAS ─────────────────
SCENARIO_FACTORS = {
    "Conservative": 0.75,
    "Base Case":    1.00,
    "Optimistic":   1.35,
}

# Column styling: (header_bg, header_text, border_css)
SCENARIO_COLOURS = {
    "Conservative": ("#6B7280", "#FFFFFF", "1px solid #E5E7EB"),
    "Base Case":    ("#2563EB", "#FFFFFF", "2px solid #2563EB"),
    "Optimistic":   ("#059669", "#FFFFFF", "1px solid #E5E7EB"),
}


# ── Small HTML helper for scenario card rows ─────────────────────────────────────
def _metric_row(label, value, value_color="#111827"):
    """Return an HTML label/value row for use inside a scenario card."""
    return (
        f"<div style='display:flex;justify-content:space-between;align-items:center;"
        f"padding:6px 0;border-bottom:1px solid #F9FAFB;'>"
        f"<span style='color:#6B7280;font-size:12px;'>{label}</span>"
        f"<span style='color:{value_color};font-weight:600;font-size:13px;'>{value}</span>"
        f"</div>"
    )


# ── API key loader ───────────────────────────────────────────────────────────────
def get_api_key():
    """Load Anthropic API key from Streamlit secrets or environment variables."""
    if "ANTHROPIC_API_KEY" in st.secrets:
        return st.secrets.get("ANTHROPIC_API_KEY")
    return os.environ.get("ANTHROPIC_API_KEY")


# ── Core ROI calculation ─────────────────────────────────────────────────────────
def compute_roi(category, avg_order_value, num_locations, rating,
                monthly_budget, campaign_types, dayparts):
    """
    Calculate ROI projections for three scenarios using category benchmarks
    and input-based multipliers.

    All multipliers are applied to the benchmark ROAS because ROAS = AOV / CPO,
    meaning any change to CPO or order volume flows through ROAS.

    Returns:
        scenarios  — dict of {name: {roas, revenue, orders, incr_orders, cpo, profit}}
        adj_roas   — the fully adjusted base-case ROAS (before scenario factor)
        base_cpo   — raw benchmark CPO for the selected category (used in break-even text)
    """
    bench         = CATEGORY_BENCHMARKS[category]
    adj_roas      = bench["avg_roas"]
    base_cpo      = bench["avg_cpo"]
    adj_incr_rate = bench["incr_rate"]

    # ── Rating adjustment ─────────────────────────────────────────────────────
    # Higher-rated restaurants convert ad impressions to orders more efficiently
    if rating >= 4.5:
        adj_roas *= 1.15
    elif rating < 4.0:
        adj_roas *= 0.85

    # ── Campaign type adjustments ─────────────────────────────────────────────
    # Sponsored Listings reduce CPO by 10% → equivalent ROAS uplift of 1/0.90
    if "Sponsored Listings" in campaign_types:
        adj_roas *= (1 / 0.90)

    # Homepage Banner drives incremental visibility → ROAS uplift
    if "Homepage Banner" in campaign_types:
        adj_roas *= 1.20

    # ── Daypart adjustments ───────────────────────────────────────────────────
    # Peak meal times drive higher order rates; applied as ROAS multipliers
    if "Dinner" in dayparts:
        adj_roas *= 1.18
    if "Lunch" in dayparts:
        adj_roas *= 1.12

    # ── Multiple locations ────────────────────────────────────────────────────
    # Each additional location generates orders independently on the same budget
    adj_roas *= num_locations

    # ── Three scenario calculations ───────────────────────────────────────────
    scenarios = {}
    for name, factor in SCENARIO_FACTORS.items():
        s_roas    = adj_roas * factor
        s_revenue = monthly_budget * s_roas
        s_orders  = s_revenue / avg_order_value if avg_order_value > 0 else 0
        s_incr    = s_orders * adj_incr_rate
        s_cpo     = monthly_budget / s_orders if s_orders > 0 else 0
        # Profit = gross margin at 30% of revenue, minus advertising spend
        s_profit  = s_revenue * 0.30 - monthly_budget
        scenarios[name] = {
            "roas":        round(s_roas, 2),
            "revenue":     round(s_revenue, 2),
            "orders":      round(s_orders, 1),
            "incr_orders": round(s_incr, 1),
            "cpo":         round(s_cpo, 2),
            "profit":      round(s_profit, 2),
        }

    return scenarios, adj_roas, base_cpo


# ── PowerPoint export ────────────────────────────────────────────────────────────
def build_pptx(inputs, scenarios, ai_text=""):
    """
    Build a dark-themed PowerPoint report using the app's premium dark template.
    Matches the colour palette and font conventions defined in CLAUDE.md.
    Returns a BytesIO buffer containing the .pptx file.
    """
    # Dark premium colour palette
    BG    = RGBColor(0x0D, 0x1B, 0x2A)   # dark navy background
    WHITE = RGBColor(0xFF, 0xFF, 0xFF)
    GREY  = RGBColor(0xA8, 0xB2, 0xBC)   # secondary text
    BLUE  = RGBColor(0x00, 0xA8, 0xE8)   # accent
    GREEN = RGBColor(0x05, 0x96, 0x69)

    prs = Presentation()
    prs.slide_width  = Inches(13.33)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]  # fully blank layout

    def set_bg(slide):
        fill = slide.background.fill
        fill.solid()
        fill.fore_color.rgb = BG

    def add_text(slide, text, left, top, width, height,
                 size=14, bold=False, color=WHITE, align=PP_ALIGN.LEFT):
        """Add a positioned Calibri text box to a slide."""
        tb = slide.shapes.add_textbox(
            Inches(left), Inches(top), Inches(width), Inches(height)
        )
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = align
        run = p.add_run()
        run.text = text
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = color
        run.font.name = "Calibri"
        return tb

    def add_footer(slide, slide_num):
        add_text(slide, "Insights App", 0.3, 7.1, 3, 0.3, size=9, color=GREY)
        add_text(slide, str(slide_num), 12.7, 7.1, 0.4, 0.3, size=9,
                 color=GREY, align=PP_ALIGN.RIGHT)

    # ── Slide 1: Title ───────────────────────────────────────────────────────
    s1 = prs.slides.add_slide(blank_layout)
    set_bg(s1)

    add_text(s1, "Uber Ads ROI Calculator", 0.8, 1.4, 11.5, 1.1,
             size=38, bold=True, color=WHITE)
    add_text(s1, "Model the return on advertising investment for restaurant partners on Uber Eats.",
             0.8, 2.65, 10, 0.55, size=15, color=GREY)

    # Accent bar below subtitle
    bar = s1.shapes.add_shape(1, Inches(0.8), Inches(3.35), Inches(4.5), Inches(0.05))
    bar.fill.solid()
    bar.fill.fore_color.rgb = BLUE
    bar.line.fill.background()

    # Input summary
    campaign_types_str = ", ".join(inputs["campaign_types"]) or "None"
    dayparts_str       = ", ".join(inputs["dayparts"]) or "All dayparts"
    summary = (
        f"Category: {inputs['category']}   |   "
        f"Monthly Budget: A${inputs['monthly_budget']:,.0f}   |   "
        f"AOV: A${inputs['avg_order_value']:.2f}   |   "
        f"Locations: {inputs['num_locations']}   |   "
        f"Rating: {inputs['rating']:.1f}\n"
        f"Objective: {inputs['target_objective']}   |   "
        f"Duration: {inputs['campaign_weeks']} weeks   |   "
        f"Campaign types: {campaign_types_str}   |   "
        f"Dayparts: {dayparts_str}"
    )
    add_text(s1, summary, 0.8, 3.6, 12, 1.2, size=12, color=GREY)
    add_footer(s1, 1)

    # ── Slide 2: ROI Scenarios ────────────────────────────────────────────────
    s2 = prs.slides.add_slide(blank_layout)
    set_bg(s2)

    add_text(s2, "ROI Projections — Three Scenarios", 0.5, 0.25, 12, 0.6,
             size=22, bold=True, color=WHITE)

    col_positions  = [0.5, 4.7, 8.9]
    col_colors     = [GREY, BLUE, GREEN]
    scenario_names = ["Conservative", "Base Case", "Optimistic"]

    # Column header labels
    for pos, col, name in zip(col_positions, col_colors, scenario_names):
        add_text(s2, name, pos, 1.0, 3.8, 0.45, size=15, bold=True, color=col)

    # Metric rows
    metric_defs = [
        ("Total Orders",        "orders",      lambda v: f"{v:,.0f}"),
        ("Incremental Orders",  "incr_orders", lambda v: f"{v:,.0f}"),
        ("Revenue Driven (AUD)","revenue",     lambda v: f"A${v:,.0f}"),
        ("ROAS",                "roas",        lambda v: f"{v:.2f}x"),
        ("CPO (AUD)",           "cpo",         lambda v: f"A${v:.2f}"),
        ("Profit on Ad Spend",  "profit",      lambda v: f"A${v:,.0f}"),
    ]
    row_tops = [1.6, 2.15, 2.7, 3.25, 3.8, 4.5]

    for j, (label, key, fmt) in enumerate(metric_defs):
        add_text(s2, label, 0.5, row_tops[j], 3.5, 0.42, size=10, color=GREY)
        for i, (pos, scen_name) in enumerate(zip(col_positions, scenario_names)):
            val = scenarios[scen_name][key]
            val_col = col_colors[i]
            # Negative profit shown in red regardless of scenario
            if key == "profit" and val < 0:
                val_col = RGBColor(0xEF, 0x44, 0x44)
            add_text(s2, fmt(val), pos, row_tops[j], 3.8, 0.42,
                     size=12, bold=True, color=val_col)

    add_footer(s2, 2)

    # ── Slide 3: Business Case (only included if AI text exists) ─────────────
    if ai_text:
        s3 = prs.slides.add_slide(blank_layout)
        set_bg(s3)
        add_text(s3, "Business Case", 0.5, 0.25, 12, 0.6,
                 size=22, bold=True, color=WHITE)
        # Truncate to ensure text fits on slide
        display_text = ai_text[:1400] + ("…" if len(ai_text) > 1400 else "")
        add_text(s3, display_text, 0.5, 1.1, 12.3, 5.8, size=11, color=GREY)
        add_footer(s3, 3)

    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf


# ════════════════════════════════════════════════════════════════════════════════
# PAGE
# ════════════════════════════════════════════════════════════════════════════════

# ── Header ───────────────────────────────────────────────────────────────────────
st.title("Uber Ads ROI Calculator")
st.markdown(
    "<p style='color:#6b7280;font-size:14px;margin-top:-12px;'>"
    "Model the return on advertising investment for restaurant partners on Uber Eats."
    "</p>",
    unsafe_allow_html=True,
)

st.divider()

# ── Section 1: Partner Inputs ────────────────────────────────────────────────────
st.subheader("Partner Inputs")

col_left, col_right = st.columns(2)

with col_left:
    st.markdown(
        "<p style='font-weight:700;font-size:13px;color:#374151;margin-bottom:2px;'>"
        "Restaurant Profile</p>",
        unsafe_allow_html=True,
    )
    category = st.selectbox(
        "Restaurant category",
        list(CATEGORY_BENCHMARKS.keys()),
        key="uber_category",
    )
    avg_order_value = st.number_input(
        "Average order value, AUD",
        min_value=1.0, max_value=500.0,
        value=28.00, step=0.50, format="%.2f",
        key="uber_aov",
    )
    organic_orders = st.number_input(
        "Current monthly organic orders",
        min_value=0, max_value=1_000_000,
        value=500, step=10,
        key="uber_organic",
    )
    num_locations = st.number_input(
        "Number of locations on Uber Eats",
        min_value=1, max_value=10_000,
        value=1, step=1,
        key="uber_locations",
    )
    rating = st.slider(
        "Current Uber Eats rating",
        min_value=1.0, max_value=5.0,
        value=4.2, step=0.1,
        key="uber_rating",
    )

with col_right:
    st.markdown(
        "<p style='font-weight:700;font-size:13px;color:#374151;margin-bottom:2px;'>"
        "Campaign Parameters</p>",
        unsafe_allow_html=True,
    )
    monthly_budget = st.number_input(
        "Monthly ad budget, AUD",
        min_value=100.0, max_value=10_000_000.0,
        value=5_000.00, step=500.0, format="%.2f",
        key="uber_budget",
    )
    campaign_types = st.multiselect(
        "Campaign type",
        ["Sponsored Listings", "Display Ads", "Homepage Banner", "Carousel Ads"],
        default=["Sponsored Listings"],
        key="uber_campaign_types",
    )
    target_objective = st.selectbox(
        "Target objective",
        ["Maximise Orders", "Maximise ROAS", "New Customer Acquisition", "Reactivation"],
        key="uber_objective",
    )
    campaign_weeks = st.slider(
        "Campaign duration in weeks",
        min_value=1, max_value=12,
        value=4, step=1,
        key="uber_weeks",
    )
    dayparts = st.multiselect(
        "Daypart focus",
        ["Breakfast", "Lunch", "Afternoon", "Dinner", "Late Night"],
        default=["Lunch", "Dinner"],
        key="uber_dayparts",
    )

st.divider()

# ── Section 3: Calculate ROI button (centred) ────────────────────────────────────
_, btn_col, _ = st.columns([1, 2, 1])
with btn_col:
    calculate_clicked = st.button(
        "Calculate ROI",
        type="primary",
        use_container_width=True,
        key="uber_calculate_btn",
    )

# When the button is clicked, run the calculation and cache everything in session state
if calculate_clicked:
    results, adj_roas, base_cpo = compute_roi(
        category        = category,
        avg_order_value = avg_order_value,
        num_locations   = num_locations,
        rating          = rating,
        monthly_budget  = monthly_budget,
        campaign_types  = campaign_types,
        dayparts        = dayparts,
    )
    st.session_state["uber_calculated"] = True
    st.session_state["uber_results"]    = results
    st.session_state["uber_adj_roas"]   = adj_roas
    st.session_state["uber_base_cpo"]   = base_cpo
    st.session_state["uber_inputs"]     = {
        "category":         category,
        "avg_order_value":  avg_order_value,
        "organic_orders":   organic_orders,
        "num_locations":    num_locations,
        "rating":           rating,
        "monthly_budget":   monthly_budget,
        "campaign_types":   campaign_types,
        "target_objective": target_objective,
        "campaign_weeks":   campaign_weeks,
        "dayparts":         dayparts,
    }
    # Clear stale AI / PPTX output whenever inputs change
    st.session_state.pop("uber_ai_case", None)
    st.session_state.pop("uber_pptx",    None)


# ════════════════════════════════════════════════════════════════════════════════
# RESULTS — only rendered after Calculate ROI is clicked
# ════════════════════════════════════════════════════════════════════════════════

if not st.session_state.get("uber_calculated"):
    st.stop()

# Pull cached values
results    = st.session_state["uber_results"]
inputs     = st.session_state["uber_inputs"]
adj_roas   = st.session_state["uber_adj_roas"]
base_cpo   = st.session_state["uber_base_cpo"]

st.divider()

# ── Section 4: Three Scenario Output ────────────────────────────────────────────
st.subheader("ROI Projections")

sc_col1, sc_col2, sc_col3 = st.columns(3)
scenario_cols = {"Conservative": sc_col1, "Base Case": sc_col2, "Optimistic": sc_col3}

for name, col in scenario_cols.items():
    s                            = results[name]
    hdr_bg, hdr_txt, border_css = SCENARIO_COLOURS[name]
    profit_color = "#10B981" if s["profit"] >= 0 else "#EF4444"

    with col:
        st.markdown(
            f"<div style='border:{border_css};border-radius:12px;overflow:hidden;"
            f"box-shadow:0 4px 12px rgba(0,0,0,0.08);background:#FFFFFF;'>"
            # Coloured header
            f"<div style='background:{hdr_bg};padding:14px 16px;'>"
            f"<p style='color:{hdr_txt};font-weight:700;font-size:15px;margin:0;'>{name}</p>"
            f"</div>"
            # Metric rows
            f"<div style='padding:14px 16px;'>"
            + _metric_row("Total Orders",       f"{s['orders']:,.0f}")
            + _metric_row("Incremental Orders", f"{s['incr_orders']:,.0f}")
            + _metric_row("Revenue Driven",     f"A${s['revenue']:,.0f}")
            + _metric_row("ROAS",               f"{s['roas']:.2f}x")
            + _metric_row("CPO",                f"A${s['cpo']:.2f}")
            + "<div style='border-top:1px solid #E5E7EB;margin:8px 0;'></div>"
            + _metric_row("Profit on Ad Spend", f"A${s['profit']:,.0f}",
                          value_color=profit_color)
            + "</div></div>",
            unsafe_allow_html=True,
        )

st.divider()

# ── Section 5: Break-Even Analysis ──────────────────────────────────────────────
st.subheader("Break-Even Analysis")

# With a 30% gross margin: you need revenue * 0.30 >= ad spend
# → ROAS (revenue / spend) must exceed 1 / 0.30 = 3.33x
break_even_roas    = round(1 / 0.30, 2)
base_case_roas     = results["Base Case"]["roas"]
base_case_cpo      = results["Base Case"]["cpo"]
aov                = inputs["avg_order_value"]

st.markdown(
    f"<div style='background:#FFFFFF;border-radius:12px;padding:18px 22px;"
    f"box-shadow:0 4px 12px rgba(0,0,0,0.08);font-size:14px;color:#374151;'>"
    f"At your average order value of <strong>A${aov:.2f}</strong> and a base-case CPO of "
    f"<strong>A${base_case_cpo:.2f}</strong>, you break even when ROAS exceeds "
    f"<strong>{break_even_roas:.2f}x</strong>. "
    f"Your projected base-case ROAS is <strong>{base_case_roas:.2f}x</strong>."
    f"</div>",
    unsafe_allow_html=True,
)

# Gauge chart: projected ROAS vs break-even threshold
gauge_max = max(base_case_roas * 1.5, break_even_roas * 1.5, 6.0)

gauge_fig = go.Figure(go.Indicator(
    mode="gauge+number+delta",
    value=base_case_roas,
    number={"suffix": "x", "font": {"size": 28, "family": "Inter, sans-serif"}},
    delta={
        "reference": break_even_roas,
        "increasing": {"color": "#10B981"},
        "decreasing": {"color": "#EF4444"},
        "suffix": "x vs break-even",
    },
    title={"text": "Projected ROAS (Base Case)", "font": {"size": 14}},
    gauge={
        "axis": {
            "range": [0, gauge_max],
            "tickwidth": 1,
            "tickcolor": "#6B7280",
            "tickfont": {"size": 11},
        },
        "bar": {"color": "#7C3AED", "thickness": 0.3},
        "bgcolor": "white",
        "borderwidth": 0,
        "steps": [
            {"range": [0, break_even_roas],  "color": "#FEF2F2"},
            {"range": [break_even_roas, gauge_max], "color": "#ECFDF5"},
        ],
        "threshold": {
            "line": {"color": "#EF4444", "width": 3},
            "thickness": 0.75,
            "value": break_even_roas,
        },
    },
))
gauge_fig.update_layout(
    height=280,
    margin=dict(t=40, b=20, l=30, r=30),
    paper_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", color="#374151"),
)
st.plotly_chart(gauge_fig, use_container_width=True)

st.divider()

# ── Section 6: Reverse Calculator ───────────────────────────────────────────────
st.subheader("Reverse Calculator")

reverse_on = st.toggle("I know my target — what budget do I need?", key="uber_reverse_toggle")

if reverse_on:
    rev_col1, rev_col2 = st.columns(2)
    with rev_col1:
        target_orders = st.number_input(
            "Target incremental orders per month",
            min_value=1, max_value=1_000_000,
            value=200, step=10,
            key="uber_rev_orders",
        )
    with rev_col2:
        target_roas = st.number_input(
            "Target ROAS",
            min_value=0.1, max_value=50.0,
            value=3.0, step=0.1, format="%.1f",
            key="uber_rev_roas",
        )

    # Incremental orders = total_orders * incr_rate
    # total_orders = target_orders / incr_rate
    incr_rate      = CATEGORY_BENCHMARKS[inputs["category"]]["incr_rate"]
    total_orders   = target_orders / incr_rate if incr_rate > 0 else 0
    req_revenue    = total_orders * inputs["avg_order_value"]
    req_budget     = req_revenue / target_roas if target_roas > 0 else 0
    proj_revenue   = req_budget * target_roas

    st.markdown(
        f"<div style='background:#FFFFFF;border-radius:12px;padding:18px 22px;"
        f"box-shadow:0 4px 12px rgba(0,0,0,0.08);margin-top:12px;'>"
        f"<p style='font-weight:700;font-size:14px;color:#111827;margin-bottom:10px;'>"
        f"Required Budget &amp; Projections</p>"
        + _metric_row("Required monthly budget", f"A${req_budget:,.0f}")
        + _metric_row("Expected total orders",   f"{total_orders:,.0f}")
        + _metric_row("Projected revenue",        f"A${proj_revenue:,.0f}")
        + "</div>",
        unsafe_allow_html=True,
    )

st.divider()

# ── Section 7: Daypart Budget Recommendation ────────────────────────────────────
st.subheader("Daypart Budget Recommendation")

selected_dayparts = inputs["dayparts"]
monthly_bud       = inputs["monthly_budget"]
base_orders       = results["Base Case"]["orders"]

if not selected_dayparts:
    st.info("No dayparts selected — add daypart focus in the inputs above to see a recommended split.")
else:
    st.markdown(
        "<p style='color:#6b7280;font-size:14px;margin-top:-8px;'>"
        "Based on your category and selected dayparts, we recommend:"
        "</p>",
        unsafe_allow_html=True,
    )

    # Normalise weights to the selected dayparts only
    raw_weights = {d: DAYPART_BASE_WEIGHTS[d] for d in selected_dayparts}
    total_w     = sum(raw_weights.values())
    norm_w      = {d: w / total_w for d, w in raw_weights.items()}

    daypart_rows = []
    for d, pct in norm_w.items():
        daypart_rows.append({
            "Daypart":        d,
            "Budget %":       f"{pct * 100:.1f}%",
            "Budget (AUD)":   f"A${monthly_bud * pct:,.0f}",
            "Expected Orders": f"{base_orders * pct:,.0f}",
        })

    df_dayparts = pd.DataFrame(daypart_rows)
    df_dayparts.index = range(1, len(df_dayparts) + 1)
    st.dataframe(df_dayparts, use_container_width=True)

st.divider()

# ── Section 8: AI Business Case ─────────────────────────────────────────────────
st.subheader("AI Business Case")

api_key = get_api_key()

if not api_key:
    st.warning("Add `ANTHROPIC_API_KEY` to Streamlit secrets to enable the AI Business Case.")
else:
    if st.button("Generate Business Case", type="primary", key="uber_ai_btn"):
        # Build a detailed prompt with all scenario numbers
        base = results["Base Case"]
        cons = results["Conservative"]
        opti = results["Optimistic"]

        prompt = (
            f"You are a Partner Manager at Uber Advertising ANZ building a business case "
            f"for a {inputs['category']} restaurant partner to invest in Uber Ads. "
            f"Here are the calculated projections:\n\n"
            f"PARTNER PROFILE\n"
            f"- Category: {inputs['category']}\n"
            f"- Average order value: A${inputs['avg_order_value']:.2f}\n"
            f"- Current monthly organic orders: {inputs['organic_orders']:,}\n"
            f"- Number of Uber Eats locations: {inputs['num_locations']}\n"
            f"- Uber Eats rating: {inputs['rating']:.1f}\n\n"
            f"CAMPAIGN PARAMETERS\n"
            f"- Monthly ad budget: A${inputs['monthly_budget']:,.0f}\n"
            f"- Campaign types: {', '.join(inputs['campaign_types']) or 'None selected'}\n"
            f"- Objective: {inputs['target_objective']}\n"
            f"- Duration: {inputs['campaign_weeks']} weeks\n"
            f"- Daypart focus: {', '.join(inputs['dayparts']) or 'All dayparts'}\n\n"
            f"PROJECTIONS\n"
            f"Conservative — {cons['orders']:,.0f} total orders, "
            f"{cons['incr_orders']:,.0f} incremental, "
            f"A${cons['revenue']:,.0f} revenue, {cons['roas']:.2f}x ROAS, "
            f"A${cons['cpo']:.2f} CPO\n"
            f"Base Case    — {base['orders']:,.0f} total orders, "
            f"{base['incr_orders']:,.0f} incremental, "
            f"A${base['revenue']:,.0f} revenue, {base['roas']:.2f}x ROAS, "
            f"A${base['cpo']:.2f} CPO\n"
            f"Optimistic   — {opti['orders']:,.0f} total orders, "
            f"{opti['incr_orders']:,.0f} incremental, "
            f"A${opti['revenue']:,.0f} revenue, {opti['roas']:.2f}x ROAS, "
            f"A${opti['cpo']:.2f} CPO\n\n"
            f"Write a compelling 3-paragraph business case that:\n"
            f"1. Opens with the revenue opportunity (use the base case numbers)\n"
            f"2. Explains why incremental orders matter more than total orders\n"
            f"3. Closes with a clear recommended starting budget and expected return\n\n"
            f"Write in a consultative, commercially confident tone. "
            f"This will be presented to a restaurant partner's marketing director. "
            f"All currency values are in AUD (use A$ symbol)."
        )

        ai_client = anthropic.Anthropic(api_key=api_key)
        with st.spinner("Generating business case…"):
            msg = ai_client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=700,
                system=(
                    "You are a Partner Manager at Uber Advertising ANZ. "
                    "Write commercially confident, data-driven business cases. "
                    "Be specific with numbers. Use Australian English."
                ),
                messages=[{"role": "user", "content": prompt}],
            )
        st.session_state["uber_ai_case"] = msg.content[0].text.strip()

    # Display AI output if it exists
    if st.session_state.get("uber_ai_case"):
        st.markdown(
            "<div style='background:#FFFFFF;border-radius:12px;padding:22px 26px;"
            "box-shadow:0 4px 12px rgba(0,0,0,0.08);margin-top:14px;font-size:14px;"
            "line-height:1.8;color:#374151;'>"
            + st.session_state["uber_ai_case"].replace("\n", "<br>") +
            "</div>",
            unsafe_allow_html=True,
        )

st.divider()

# ── Section 9: Export ────────────────────────────────────────────────────────────
st.subheader("Export")

if st.button("Download Business Case (.pptx)", key="uber_pptx_btn"):
    ai_text = st.session_state.get("uber_ai_case", "")
    pptx_buf = build_pptx(inputs, results, ai_text)
    st.session_state["uber_pptx"] = pptx_buf

if st.session_state.get("uber_pptx"):
    from datetime import date as _date
    filename = f"{_date.today().isoformat()}_uber_ads_roi.pptx"
    st.download_button(
        label="Save .pptx",
        data=st.session_state["uber_pptx"],
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        key="uber_pptx_download",
    )

print("Uber Ads ROI Calculator page loaded.")
