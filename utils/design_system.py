# ── Pacebird Design System ─────────────────────────────────────────────────────
# DESIGN SYSTEM LOCK — do not modify these values without updating all pages.
# Primary: #F5A623 (warm orange)   Secondary: #1B2A4A (deep navy)
# Success: #10B981   Warning: #F59E0B   Danger: #EF4444
# Background: #EEF1F4   Font: Poppins
# DO NOT revert to old purple (#7C3AED) or blue (#2563EB) values.

import streamlit as st

# ── Color constants ────────────────────────────────────────────────────────────
PRIMARY        = "#F5A623"   # warm orange — buttons, accents, active nav, card tops
PRIMARY_HOVER  = "#E8951A"   # darker orange — button hover state
SECONDARY      = "#1B2A4A"   # deep navy — sidebar bg, chart bars, secondary elements
SUCCESS        = "#10B981"   # green — on-track RAG / positive status
WARNING        = "#F59E0B"   # amber — at-risk RAG / warning status
DANGER         = "#EF4444"   # red — critical RAG / error status
BG_PAGE        = "#EEF1F4"   # light grey — page background
TEXT_PRI       = "#111827"   # near-black — headings and main body text
TEXT_SEC       = "#6B7280"   # medium grey — captions and secondary labels
WHITE          = "#FFFFFF"   # card backgrounds, sidebar text, button labels
BORDER_LIGHT   = "#E5E7EB"   # subtle borders and dividers

# ── Chart palette (navy/orange alternating for bar charts) ─────────────────────
# Use CHART_PALETTE for multi-series charts; assign SECONDARY/PRIMARY for single-series.
CHART_PALETTE = [
    SECONDARY,        # #1B2A4A navy
    PRIMARY,          # #F5A623 orange
    "#2C4A7A",        # lighter navy variant
    "#F7B84B",        # lighter orange variant
    "#162238",        # darker navy variant
    "#E8951A",        # darker orange variant
    SUCCESS,          # green (for positive/additional series)
    WARNING,          # amber
    DANGER,           # red
    "#4A7AB5",        # mid-blue navy variant
]

# ── Gradient scales for continuous color charts ────────────────────────────────
CHART_SCALE_ORANGE = ["#FDECC8", PRIMARY, SECONDARY]   # light orange → dark navy
CHART_SCALE_NAVY   = ["#C4D3E8", SECONDARY, "#0D1520"]  # light navy → deep navy

# ── Plotly config — pass to every st.plotly_chart() call ──────────────────────
# Hides the camera/zoom/home/modebar toolbar visible above every chart.
PLOTLY_CONFIG = {"displayModeBar": False}


# ─────────────────────────────────────────────────────────────────────────────
# metric_card — reusable KPI card rendered as HTML
# ─────────────────────────────────────────────────────────────────────────────

def metric_card(label, value, delta=None, delta_label=None, icon=None):
    """
    Render a styled KPI metric card as an HTML string.

    Args:
        label:       Card label (uppercase, 12px, navy 60% opacity)
        value:       Main value displayed (28px, weight 600, navy)
        delta:       Optional change — string ("+12%") or number (12.3).
                     Positive → green ▲   Negative → red ▼
        delta_label: Comparison context, e.g. "vs previous period"
        icon:        Optional emoji shown top-right in orange at 20% opacity

    Returns:
        HTML string — pass to st.markdown(..., unsafe_allow_html=True)
    """
    delta_html = ""
    if delta is not None:
        s = str(delta)
        is_pos = (isinstance(delta, (int, float)) and delta > 0) or \
                 (isinstance(delta, str) and s.lstrip().startswith("+"))
        is_neg = (isinstance(delta, (int, float)) and delta < 0) or \
                 (isinstance(delta, str) and s.lstrip().startswith("-"))
        color = SUCCESS if is_pos else (DANGER if is_neg else TEXT_SEC)
        arrow = "\u25b2" if is_pos else ("\u25bc" if is_neg else "\u25cf")
        cmp   = f"&nbsp;{delta_label}" if delta_label else ""
        delta_html = (
            f'<div style="margin-top:6px;font-size:13px;font-weight:500;color:{color};'
            f"font-family:'Poppins',sans-serif;\">{arrow} {s}{cmp}</div>"
        )

    icon_html = ""
    if icon:
        icon_html = (
            f'<div style="position:absolute;top:14px;right:16px;font-size:20px;'
            f'opacity:0.2;color:{PRIMARY};">{icon}</div>'
        )

    return (
        f'<div style="background:{WHITE};border:0.5px solid rgba(27,42,74,0.12);'
        f"border-radius:16px;padding:18px 20px;position:relative;"
        f"font-family:'Poppins',system-ui,sans-serif;\">"
        f"{icon_html}"
        f'<div style="font-size:12px;font-weight:600;text-transform:uppercase;'
        f"letter-spacing:0.04em;color:rgba(27,42,74,0.6);margin-bottom:8px;"
        f"font-family:'Poppins',sans-serif;\">{label}</div>"
        f'<div style="font-size:28px;font-weight:600;color:{SECONDARY};'
        f"line-height:1.1;font-family:'Poppins',sans-serif;\">{value}</div>"
        f"{delta_html}"
        f"</div>"
    )


# ─────────────────────────────────────────────────────────────────────────────
# apply_plotly_style — shared Plotly visual template
# ─────────────────────────────────────────────────────────────────────────────

def apply_plotly_style(fig, height=420):
    """
    Apply the shared Pacebird Plotly visual style to any figure.
    Call this on every Plotly figure before st.plotly_chart().

    Behaviour:
    - Transparent background (chart sits inside CSS white card)
    - Poppins font, navy colour, 12px base size
    - Horizontal gridlines only (rgba navy 8% opacity)
    - Subtle x-axis baseline, no y-axis line, no zero-line
    - Hover: white bg, navy border, Poppins
    - Legend horizontal, above plot, no border
    - margin: l=50, r=20, t=30, b=50
    - colorway: navy → orange → mid-blues/golds
    """
    fig.update_layout(
        font=dict(
            family="Poppins, system-ui, sans-serif",
            size=12,
            color=SECONDARY,
        ),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=50, r=20, t=30, b=50),
        colorway=["#1B2A4A", "#F5A623", "#3D5A80", "#F7C566", "#6B85A8"],
        hoverlabel=dict(
            bgcolor=WHITE,
            bordercolor=SECONDARY,
            font=dict(
                family="Poppins, system-ui, sans-serif",
                size=12,
                color=SECONDARY,
            ),
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            borderwidth=0,
        ),
        height=height,
    )
    fig.update_xaxes(
        showgrid=False,
        showline=True,
        linecolor="rgba(27,42,74,0.15)",
        linewidth=1,
        tickfont=dict(size=11, color=SECONDARY),
        title_font=dict(size=12, color=SECONDARY),
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor="rgba(27,42,74,0.08)",
        gridwidth=1,
        showline=False,
        zeroline=False,
        tickfont=dict(size=11, color=SECONDARY),
        title_font=dict(size=12, color=SECONDARY),
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# filter_widget — smart selectbox / segmented control
# ─────────────────────────────────────────────────────────────────────────────

def filter_widget(label, options, key, default=None, label_visibility="visible"):
    """
    Renders st.segmented_control (pill style) for ≤4 options, st.selectbox
    for more. Falls back to selectbox if segmented_control is unavailable
    in the current Streamlit version.

    Args:
        label:            Widget label string
        options:          List of string options
        key:              Unique Streamlit widget key
        default:          Pre-selected option (must be in options)
        label_visibility: "visible" | "hidden" | "collapsed"

    Returns the selected option string (never None).
    """
    idx = options.index(default) if (default and default in options) else 0
    if len(options) <= 4:
        try:
            result = st.segmented_control(
                label,
                options,
                key=key,
                default=options[idx],
                label_visibility=label_visibility,
            )
            return result if result is not None else options[0]
        except (AttributeError, TypeError):
            pass  # Fall through to selectbox if st.segmented_control unavailable
    return st.selectbox(
        label, options, index=idx, key=key, label_visibility=label_visibility
    )


# ─────────────────────────────────────────────────────────────────────────────
# get_css — full Pacebird design system CSS
# Applied globally by app.py; cascades to all pages automatically.
# ─────────────────────────────────────────────────────────────────────────────

def get_css():
    """
    Returns the full Pacebird design system CSS string.

    Usage in app.py (already in place — cascades to all pages):
        from utils.design_system import get_css
        st.markdown(get_css(), unsafe_allow_html=True)
    """
    return f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap');

    /* ── Base font and body ─────────────────────────────────────── */
    html, body, [class*="css"] {{
        font-family: "Poppins", system-ui, -apple-system, "Segoe UI", sans-serif;
        font-size: 15px;
        color: {TEXT_PRI};
    }}

    /* ── Page background ────────────────────────────────────────── */
    .stApp {{ background-color: {BG_PAGE}; }}

    /* ── Main content block padding ──────────────────────────────── */
    .block-container {{
        padding-top: 1.5rem !important;
        padding-bottom: 2rem !important;
    }}

    /* ── Heading hierarchy ──────────────────────────────────────── */
    /* h1 = page title (st.title / st.markdown("# …")) */
    h1 {{
        font-size: 30px !important;
        font-weight: 600 !important;
        color: {SECONDARY} !important;
        margin-bottom: 0.25rem !important;
    }}
    /* h2 = section header (st.header / st.markdown("## …")) */
    h2 {{
        font-size: 19px !important;
        font-weight: 600 !important;
        color: {SECONDARY} !important;
        margin-top: 32px !important;
        margin-bottom: 16px !important;
        padding-top: 0 !important;
        border-bottom: none !important;
        border-left: none !important;
        padding-left: 0 !important;
    }}
    /* h3 = sub-section (st.subheader / st.markdown("### …")) */
    h3 {{
        font-size: 19px !important;
        font-weight: 600 !important;
        color: {SECONDARY} !important;
        margin-top: 32px !important;
        margin-bottom: 16px !important;
        padding-top: 0 !important;
        border-bottom: none !important;
        border-left: none !important;
        padding-left: 0 !important;
    }}
    h4, h5, h6 {{
        font-weight: 600 !important;
        color: {SECONDARY} !important;
    }}

    /* ── Hide ad-hoc horizontal rule dividers ────────────────────── */
    /* Rely on heading margins and card borders for visual separation */
    hr {{ display: none !important; }}
    [data-testid="stDivider"] {{ display: none !important; }}

    /* ── KPI metric cards (st.metric fallback for non-converted pages) */
    [data-testid="metric-container"] {{
        background: {WHITE};
        border: 0.5px solid rgba(27,42,74,0.12);
        border-radius: 16px;
        padding: 18px 20px;
        position: relative;
        box-shadow: none;
    }}
    [data-testid="metric-container"] label {{
        font-size: 12px !important;
        font-weight: 600 !important;
        color: rgba(27,42,74,0.6) !important;
        text-transform: uppercase !important;
        letter-spacing: 0.04em !important;
    }}
    [data-testid="metric-container"] [data-testid="stMetricValue"] {{
        font-size: 28px !important;
        font-weight: 600 !important;
        color: {SECONDARY} !important;
    }}
    [data-testid="metric-container"] [data-testid="stMetricDelta"] {{
        font-size: 13px !important;
        font-weight: 500 !important;
    }}

    /* ── Chart card containers — white card around every Plotly chart */
    .element-container:has([data-testid="stPlotlyChart"]) {{
        background: {WHITE};
        border: 0.5px solid rgba(27,42,74,0.12);
        border-radius: 16px;
        padding: 20px 16px 12px 16px;
        margin-bottom: 0;
    }}

    /* ── Gap between columns in the same row ─────────────────────── */
    [data-testid="stHorizontalBlock"] {{
        gap: 16px;
    }}

    /* ── Primary buttons — orange ───────────────────────────────── */
    .stButton > button[kind="primary"],
    [data-testid="baseButton-primary"] {{
        background-color: {PRIMARY} !important;
        color: {WHITE} !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 15px !important;
        padding: 0.5rem 1.25rem !important;
    }}
    .stButton > button[kind="primary"]:hover,
    [data-testid="baseButton-primary"]:hover {{
        background-color: {PRIMARY_HOVER} !important;
    }}

    /* ── Secondary / default buttons ────────────────────────────── */
    .stButton > button[kind="secondary"],
    [data-testid="baseButton-secondary"] {{
        border-radius: 8px !important;
        font-weight: 600 !important;
    }}

    /* ── All buttons: smooth hover lift ─────────────────────────── */
    .stButton > button {{
        border-radius: 10px !important;
        transition: all 0.15s ease !important;
    }}
    .stButton > button:hover {{
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.12) !important;
    }}

    /* ── File upload box ─────────────────────────────────────────── */
    [data-testid="stFileUploader"] {{
        border: 2px dashed {PRIMARY} !important;
        border-radius: 12px;
        padding: 10px;
        background: {WHITE};
    }}

    /* ── Data tables ─────────────────────────────────────────────── */
    [data-testid="stDataFrame"] {{
        background: {WHITE};
        border-radius: 16px !important;
        overflow: hidden !important;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06) !important;
        border: none !important;
    }}
    [data-testid="stDataFrame"] tr:hover > td {{
        background-color: rgba(245,166,35,0.06) !important;
    }}

    /* ── DSP source badges ───────────────────────────────────────── */
    .source-badge {{
        display: inline-block;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 700;
        margin-left: 6px;
    }}
    .badge-dv360   {{ background: #EEF1F4; color: {SECONDARY}; }}
    .badge-ttd     {{ background: #FFF4E0; color: {PRIMARY}; }}
    .badge-generic {{ background: #F0FDF4; color: #16A34A; }}
    .badge-amazon  {{ background: #FFF7ED; color: #C2410C; }}

    /* ── Filter / selectbox widgets — compact, design-system styled ── */
    [data-testid="stSelectbox"],
    [data-testid="stDateInput"],
    [data-testid="stMultiSelect"] {{
        background-color: #EEF1F4;
        border: 1px solid rgba(27,42,74,0.15);
        border-radius: 8px;
        padding: 1px 6px 2px 6px;
    }}
    [data-testid="stSelectbox"] label,
    [data-testid="stMultiSelect"] label,
    [data-testid="stDateInput"] label {{
        font-size: 11px !important;
        font-weight: 600 !important;
        color: {SECONDARY} !important;
        font-family: "Poppins", system-ui, sans-serif !important;
        text-transform: uppercase !important;
        letter-spacing: 0.04em !important;
        margin-bottom: 0px !important;
        padding-bottom: 0px !important;
        line-height: 1.2 !important;
    }}
    [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
    [data-testid="stMultiSelect"] div[data-baseweb="select"] > div {{
        min-height: 30px !important;
        height: 30px !important;
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }}
    [data-testid="stSelectbox"] div[data-baseweb="select"] *,
    [data-testid="stMultiSelect"] div[data-baseweb="select"] * {{
        font-size: 12px !important;
        font-family: "Poppins", system-ui, sans-serif !important;
        color: {SECONDARY} !important;
    }}
    div[data-baseweb="select"] div[data-baseweb="input"],
    div[data-baseweb="select"] [class*="ValueContainer"],
    div[data-baseweb="select"] input {{
        min-height: 28px !important;
        height: 28px !important;
        padding-top: 0 !important;
        padding-bottom: 0 !important;
        line-height: 28px !important;
    }}
    [data-testid="stSelectbox"] [data-testid="stWidgetLabel"],
    [data-testid="stDateInput"] [data-testid="stWidgetLabel"],
    [data-testid="stMultiSelect"] [data-testid="stWidgetLabel"] {{
        min-height: 0 !important;
        margin-bottom: 2px !important;
    }}
    [data-testid="stDateInput"] div[data-baseweb="input"] {{
        min-height: 30px !important;
        height: 30px !important;
    }}
    [data-testid="stDateInput"] input {{
        padding-top: 2px !important;
        padding-bottom: 2px !important;
        min-height: 28px !important;
        font-size: 12px !important;
        font-family: "Poppins", system-ui, sans-serif !important;
    }}
    div[data-baseweb="select"] > div,
    div[data-baseweb="input"] {{
        border-radius: 8px !important;
    }}

    /* ── Segmented control — pill style, navy/orange ─────────────── */
    [data-testid="stSegmentedControl"] label {{
        font-size: 11px !important;
        font-weight: 600 !important;
        color: {SECONDARY} !important;
        text-transform: uppercase !important;
        letter-spacing: 0.04em !important;
    }}
    [data-testid="stSegmentedControl"] [role="group"] {{
        gap: 4px !important;
        background: rgba(27,42,74,0.05) !important;
        border-radius: 24px !important;
        padding: 3px !important;
    }}
    [data-testid="stSegmentedControl"] button {{
        border-radius: 20px !important;
        font-family: "Poppins", sans-serif !important;
        font-size: 12px !important;
        font-weight: 600 !important;
        color: {SECONDARY} !important;
        border: none !important;
        padding: 3px 14px !important;
        background: transparent !important;
        transition: all 0.15s ease !important;
    }}
    [data-testid="stSegmentedControl"] button[aria-checked="true"] {{
        background-color: {PRIMARY} !important;
        color: {WHITE} !important;
    }}

    /* ── Onboarding highlight ────────────────────────────────────── */
    .onboarding-highlight {{
        border: 3px solid {PRIMARY} !important;
        border-radius: 8px !important;
        animation: pulse-border 2s infinite !important;
    }}
    @keyframes pulse-border {{
        0%   {{ box-shadow: 0 0 0 0   rgba(245,166,35,0.4); }}
        70%  {{ box-shadow: 0 0 0 10px rgba(245,166,35,0);   }}
        100% {{ box-shadow: 0 0 0 0   rgba(245,166,35,0);   }}
    }}
</style>
"""
