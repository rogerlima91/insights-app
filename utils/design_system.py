# ── Pacebird Design System ─────────────────────────────────────────────────────
# DESIGN SYSTEM LOCK — do not modify these values without updating all pages.
# Primary: #F5A623 (warm orange)   Secondary: #1B2A4A (deep navy)
# Success: #10B981   Warning: #F59E0B   Danger: #EF4444
# Background: #EEF1F4   Font: Poppins
# DO NOT revert to old purple (#7C3AED) or blue (#2563EB) values.

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


def get_css():
    """
    Returns the full Pacebird design system CSS block.

    Usage in every page:
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

    /* ── Main area headings ──────────────────────────────────────── */
    h1, h2, h3, h4, h5, h6 {{
        font-weight: 700 !important;
        color: {TEXT_PRI} !important;
    }}
    h2, h3 {{
        margin-top: 2rem !important;
        padding-top: 0.25rem !important;
        border-bottom: none !important;
        padding-bottom: 0 !important;
        border-left: none !important;
        padding-left: 0 !important;
    }}

    /* ── KPI metric cards ───────────────────────────────────────── */
    [data-testid="metric-container"] {{
        background: {WHITE};
        border: none;
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06);
        border-top: 4px solid {PRIMARY};
    }}
    [data-testid="metric-container"] label {{
        font-size: 12px;
        font-weight: 600;
        color: {TEXT_SEC};
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}
    [data-testid="metric-container"] [data-testid="stMetricValue"] {{
        font-size: 26px;
        font-weight: 700;
        color: {TEXT_PRI};
    }}

    /* ── Chart cards — wrap Plotly chart output in white card ───── */
    .element-container:has([data-testid="stPlotlyChart"]) {{
        background: {WHITE};
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06);
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
        border-radius: 12px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06);
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
</style>
"""
