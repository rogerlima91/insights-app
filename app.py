import io
import json
import os
import re
from datetime import date
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import anthropic
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Insights App", layout="wide")

# ── Brand colours ─────────────────────────────────────────────────────────────
NAVY    = "#14113b"
CYAN    = "#00b2a9"
GREEN   = "#34b233"
PURPLE  = "#6e2ca9"
MAGENTA = "#c70099"

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    html, body, [class*="css"] {
        font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
    }
    /* Metric cards */
    [data-testid="metric-container"] {
        background: #ffffff;
        border: 1px solid #e8e8f0;
        border-top: 4px solid #00b2a9;
        border-radius: 10px;
        padding: 16px 20px;
        box-shadow: 0 2px 8px rgba(20,17,59,0.07);
    }
    [data-testid="metric-container"] label {
        font-size: 12px;
        font-weight: 600;
        color: #6b7280;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        font-size: 24px;
        font-weight: 700;
        color: #14113b;
    }
    h3 {
        color: #14113b !important;
        font-weight: 700 !important;
        border-bottom: 2px solid #00b2a9;
        padding-bottom: 6px;
        margin-top: 1.4rem !important;
    }
    /* Upload box */
    [data-testid="stFileUploader"] {
        border: 2px dashed #00b2a9 !important;
        border-radius: 12px;
        padding: 10px;
    }
    .source-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 700;
        margin-left: 6px;
    }
    .badge-dv360   { background: #e8f5e9; color: #34b233; }
    .badge-ttd     { background: #ede7f6; color: #6e2ca9; }
    .badge-generic { background: #e8f4fd; color: #0288d1; }
</style>
""", unsafe_allow_html=True)

# ── Column name normalisation map ─────────────────────────────────────────────
# Maps the many different column names DSPs use → our standard internal names.
# Add more aliases here as you encounter new DSP export formats.
COLUMN_MAP = {
    # Campaign / Brand (high-level grouping)
    "campaign":                    "campaign",
    "campaign name":               "campaign",
    "campaign_name":               "campaign",
    "insertion order":             "campaign",
    "advertiser":                  "campaign",
    "brand name":                  "campaign",
    "brand":                       "campaign",

    # Line item (more granular — used for the top-10 line items chart)
    "line item":                   "line_item",
    "line item name":              "line_item",
    "ad group":                    "line_item",
    "ad group name":               "line_item",
    "creative":                    "line_item",

    # Device type (for pie chart)
    "device type":                 "device_type",
    "device":                      "device_type",
    "device_type":                 "device_type",
    "device category":             "device_type",

    # Environment / inventory type (for pie chart)
    "environment":                 "environment",
    "environment type":            "environment",
    "inventory type":              "environment",
    "supply type":                 "environment",
    "site type":                   "environment",

    # Date
    "date":                        "date",
    "day":                         "date",
    "week":                        "date",
    "month":                       "date",

    # Impressions
    "impressions":                 "impressions",
    "impression":                  "impressions",
    "served impressions":          "impressions",
    "total impressions":           "impressions",

    # Clicks
    "clicks":                      "clicks",
    "click":                       "clicks",
    "total clicks":                "clicks",
    "link clicks":                 "clicks",

    # Spend / cost
    "spend":                       "spend_usd",
    "spend (usd)":                 "spend_usd",
    "total spend":                 "spend_usd",
    "total spend (usd)":           "spend_usd",
    "media cost":                  "spend_usd",
    "media cost (usd)":            "spend_usd",
    "revenue (usd)":               "spend_usd",
    "cost":                        "spend_usd",
    "billed spend":                "spend_usd",

    # Conversions
    "conversions":                 "conversions",
    "total conversions":           "conversions",
    "post-click conversions":      "conversions",

    # CTR (sometimes pre-calculated in export)
    "ctr":                         "ctr_raw",
    "click-through rate":          "ctr_raw",

    # CPM (sometimes pre-calculated)
    "cpm":                         "cpm_raw",
    "avg. cpm":                    "cpm_raw",
    "average cpm":                 "cpm_raw",
}

# ── DSP source detector ───────────────────────────────────────────────────────
# Tries to identify which DSP the CSV came from based on column names.
def detect_source(columns):
    cols_lower = [c.lower() for c in columns]
    if any("revenue (usd)" in c or "insertion order" in c for c in cols_lower):
        return "DV360"
    if any("billed spend" in c or "partner" in c for c in cols_lower):
        return "TTD"
    return "Generic"

# ── Brand memory helpers ──────────────────────────────────────────────────────
# brand_memory.json stores per-brand context that shapes AI commentary.
BRAND_MEMORY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "brand_memory.json")

def load_brand_memory():
    """Load brand memory from JSON file. Returns empty dict if file doesn't exist."""
    if os.path.exists(BRAND_MEMORY_PATH):
        with open(BRAND_MEMORY_PATH, "r") as f:
            return json.load(f)
    return {}

def save_brand_memory(memory):
    """Save brand memory dict back to JSON file."""
    with open(BRAND_MEMORY_PATH, "w") as f:
        json.dump(memory, f, indent=2)

# ── CSV loader and normaliser ─────────────────────────────────────────────────
def load_and_normalise(uploaded_file):
    """
    Reads a CSV file, normalises column names to our standard format,
    and adds a 'source_file' and 'dsp_source' column for traceability.
    """
    df = pd.read_csv(uploaded_file)

    # Detect DSP before renaming columns
    dsp = detect_source(df.columns.tolist())

    # Normalise column names: lowercase + strip whitespace, then remap
    df.columns = [c.strip().lower() for c in df.columns]
    df = df.rename(columns={k: v for k, v in COLUMN_MAP.items() if k in df.columns})

    # Multiple source columns can map to the same standard name (e.g. both
    # "CTR" and "Click-through rate" → "ctr_raw"). Keep the first occurrence.
    df = df.loc[:, ~df.columns.duplicated(keep="first")]

    # Convert numeric columns — DSP exports often include commas or $ signs
    for col in ["impressions", "clicks", "spend_usd", "conversions"]:
        if col in df.columns:
            df[col] = (
                df[col].astype(str)
                .str.replace(r"[$,]", "", regex=True)   # strip $ and commas
                .str.strip()
            )
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Calculate CTR and CPM from raw numbers (more reliable than DSP-provided values)
    if "impressions" in df.columns and "clicks" in df.columns:
        df["ctr"] = df["clicks"] / df["impressions"]
    if "impressions" in df.columns and "spend_usd" in df.columns:
        df["cpm"] = df["spend_usd"] / df["impressions"] * 1000

    # Tag each row with where it came from
    df["source_file"] = uploaded_file.name
    df["dsp_source"]  = dsp

    return df, dsp

# ── PowerPoint builder ───────────────────────────────────────────────────────
# Template lives alongside app.py — inherits DV colors, fonts, and backgrounds.
# Layout[0]  "Title Slide"      — full-slide navy rect + DV logo group
# Layout[16] "Navy_Title Only"  — full-slide navy rect + title placeholder + logo

# RGBColor constants matching the DV brand palette in the template
_NAVY  = RGBColor(0x14, 0x11, 0x3b)
_CYAN  = RGBColor(0x00, 0xb2, 0xa9)
_WHITE = RGBColor(0xFF, 0xFF, 0xFF)
_GREY  = RGBColor(0xBF, 0xBF, 0xBF)
_DARK  = RGBColor(0x37, 0x41, 0x51)

# Template slide dimensions (widescreen 16:9, 13.33" × 7.5")
_W = 13.33
_H = 7.50

def _rect(slide, l, t, w, h, fill):
    """Filled rectangle, no border."""
    s = slide.shapes.add_shape(1, Inches(l), Inches(t), Inches(w), Inches(h))
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    s.line.fill.background()
    return s

def _textbox(slide, l, t, w, h, text, size, bold=False, color=None,
             align=PP_ALIGN.LEFT, wrap=True):
    """Single-run text box using Arial to match the template font."""
    txb = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf  = txb.text_frame
    tf.word_wrap = wrap
    p   = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text           = text
    run.font.name      = "Arial"
    run.font.size      = Pt(size)
    run.font.bold      = bold
    run.font.color.rgb = color or _DARK
    return txb

def _metric_box(slide, l, t, w, h, label, value):
    """Metric card: slightly-lighter navy box with cyan border, label + value."""
    box = slide.shapes.add_shape(1, Inches(l), Inches(t), Inches(w), Inches(h))
    box.fill.solid()
    box.fill.fore_color.rgb = RGBColor(0x1e, 0x1a, 0x52)
    box.line.color.rgb = _CYAN
    box.line.width = Pt(1)
    _textbox(slide, l+0.08, t+0.08, w-0.16, 0.28,
             label, 8, color=_GREY, align=PP_ALIGN.CENTER)
    _textbox(slide, l+0.05, t+0.35, w-0.10, 0.58,
             value, 18, bold=True, color=_WHITE, align=PP_ALIGN.CENTER)

def _footer(slide):
    """Centered footer line just above the template logo bar."""
    _textbox(slide, 1.8, 7.13, 9.8, 0.24,
             f"Generated by Insights App  |  {date.today():%B %d, %Y}",
             8, color=_GREY, align=PP_ALIGN.CENTER)

def _make_rec(row, avg_ctr, avg_cpm):
    """
    One-sentence recommendation built from campaign metrics vs portfolio averages.
    Under 30 words, fully self-contained (no dependency on AI insight text).
    """
    has_ctr = "ctr" in row and pd.notna(row["ctr"])
    has_cpm = "cpm" in row and pd.notna(row["cpm"])
    has_spd = "spend_usd" in row and pd.notna(row["spend_usd"])

    ctr_low  = has_ctr and avg_ctr and row["ctr"] < avg_ctr
    cpm_high = has_cpm and avg_cpm and row["cpm"] > avg_cpm

    if ctr_low and cpm_high:
        return (f"Refresh creatives and tighten inventory targeting — "
                f"CTR of {row['ctr']:.2%} is below average while CPM of ${row['cpm']:,.2f} is above average.")
    elif ctr_low:
        return (f"Test new creatives or audience segments to lift CTR, "
                f"currently at {row['ctr']:.2%} against a portfolio average of {avg_ctr:.2%}.")
    elif cpm_high:
        return (f"Review inventory sources to reduce CPM from ${row['cpm']:,.2f} "
                f"toward the portfolio average of ${avg_cpm:,.2f}.")
    elif has_ctr and has_cpm:
        spend_note = f" — consider scaling budget from ${row['spend_usd']:,.0f}" if has_spd else ""
        return (f"Strong performance — CTR of {row['ctr']:.2%} and CPM of ${row['cpm']:,.2f} "
                f"are both at or above average{spend_note}.")
    else:
        return "Ensure impressions, clicks, and spend data are present for a full recommendation."

def _right_insights(slide, insights_text):
    """
    Fill the right panel with per-campaign AI insight text.
    - Campaign name: 8pt bold cyan
    - Insight body: 7pt white
    - Total text capped at 800 characters; truncates with '...' if longer
    - Text box is tall enough to fill the right column (5.2" tall)
    """
    _textbox(slide, 8.2, 1.2, 4.85, 0.3, "Brand Insights",
             9, bold=True, color=_CYAN)

    txb = slide.shapes.add_textbox(Inches(8.2), Inches(1.55), Inches(4.85), Inches(5.2))
    tf  = txb.text_frame
    tf.word_wrap = True

    char_budget = 800
    chars_used  = 0
    para_idx    = 0

    for cname, text in insights_text.items():
        # Stop if no budget left for at least the campaign name
        if chars_used >= char_budget:
            break
        name_len  = len(cname) + 2        # +2 for ": "
        available = char_budget - chars_used - name_len
        if available <= 0:
            break
        # Truncate insight body if it doesn't fit within the remaining budget
        body = text if len(text) <= available else text[:available - 3] + "..."

        # Campaign name paragraph (bold cyan)
        p1 = tf.paragraphs[0] if para_idx == 0 else tf.add_paragraph()
        r1 = p1.add_run()
        r1.text           = cname + ": "
        r1.font.name      = "Arial"
        r1.font.bold      = True
        r1.font.size      = Pt(8)
        r1.font.color.rgb = _CYAN

        # Insight body paragraph (white, smaller)
        p2 = tf.add_paragraph()
        r2 = p2.add_run()
        r2.text           = body
        r2.font.name      = "Arial"
        r2.font.size      = Pt(7)
        r2.font.color.rgb = _WHITE
        p2.space_after    = Pt(6)

        chars_used += name_len + len(body)
        para_idx   += 1


def _right_recs(slide, camp_summary):
    """
    Fill the right panel with one metric-based recommendation per campaign.
    Same overflow rules as _right_insights: 7-8pt font, 800-char cap.
    """
    _textbox(slide, 8.2, 1.2, 4.85, 0.3, "Recommendations",
             9, bold=True, color=_CYAN)

    avg_ctr_all = camp_summary["ctr"].mean() if "ctr" in camp_summary.columns else None
    avg_cpm_all = camp_summary["cpm"].mean() if "cpm" in camp_summary.columns else None

    txb = slide.shapes.add_textbox(Inches(8.2), Inches(1.55), Inches(4.85), Inches(5.2))
    tf  = txb.text_frame
    tf.word_wrap = True

    char_budget = 800
    chars_used  = 0

    for idx, (_, row) in enumerate(camp_summary.iterrows()):
        if chars_used >= char_budget:
            break
        cname    = str(row["campaign"])
        rec      = _make_rec(row, avg_ctr_all, avg_cpm_all)
        name_len = len(cname) + 3         # +3 for ":  "
        available = char_budget - chars_used - name_len
        if available <= 0:
            break
        rec_body = rec if len(rec) <= available else rec[:available - 3] + "..."

        p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        r1 = p.add_run()
        r1.text           = cname + ":  "
        r1.font.name      = "Arial"
        r1.font.bold      = True
        r1.font.size      = Pt(8)
        r1.font.color.rgb = _CYAN
        r2 = p.add_run()
        r2.text           = rec_body
        r2.font.name      = "Arial"
        r2.font.size      = Pt(8)
        r2.font.color.rgb = _WHITE
        p.space_after     = Pt(8)

        chars_used += name_len + len(rec_body)


def _chart_slide(prs, lay_content, title, buf_chart, fill_right_fn):
    """
    Add one chart slide to prs:
      - Title bar at top
      - Chart image: left 60% of content area (0.3" to 7.9")
      - Right panel:  right 40% of content area (8.2" to 13.0")
      - Footer at bottom
    fill_right_fn(slide) is called to populate the right panel.
    """
    s = prs.slides.add_slide(lay_content)
    _textbox(s, 0.94, 0.28, 11.44, 0.75, title, 22, bold=True, color=_WHITE)

    # Chart image — left 60% (width = 13.33 × 0.60 ≈ 7.6", accounting for margins)
    buf_chart.seek(0)
    s.shapes.add_picture(buf_chart,
                         Inches(0.3), Inches(1.2), Inches(7.6), Inches(5.55))

    # Right panel
    fill_right_fn(s)
    _footer(s)
    return s


def build_pptx(file_info, total_impressions, total_clicks, total_spend,
               avg_ctr, avg_cpm, camp_summary, insights_text,
               buf_impressions, buf_ctr_chart, buf_spend_chart,
               buf_line_items, buf_device, buf_environment):
    """
    Builds and returns a BytesIO .pptx using template.pptx.pptx as the base.

    Slides:
      1. Title — dark navy, app name, date, source files
      2. Executive Summary — 5 metric cards + campaign breakdown table
      3–8. One slide per chart (only included if that chart was rendered):
           Impressions by Campaign, CTR by Campaign, Spend by Campaign,
           Top 10 Line Items, Device Type, Environment
           Each slide: chart left 60%, insights/recommendations right 40%

    The template provides DV colors, Arial fonts, the logo, and the
    full-slide navy background automatically via its slide layouts.
    """
    template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "template.pptx.pptx")
    prs = Presentation(template_path)

    # Remove all existing slides while also dropping their parts from the package
    xml_slides = prs.slides._sldIdLst
    for slide_id in list(xml_slides):
        rId = slide_id.get(qn('r:id'))
        prs.part.drop_rel(rId)
        xml_slides.remove(slide_id)

    lay_title   = prs.slide_layouts[0]   # Title Slide — navy bg + DV logo group
    lay_content = prs.slide_layouts[16]  # Navy_Title Only — navy bg + logo + page#

    # ── Slide 1: Title ────────────────────────────────────────────────────────
    s1 = prs.slides.add_slide(lay_title)
    _rect(s1, 0, 3.65, _W, 0.05, _CYAN)
    _textbox(s1, 0.94, 2.0, 11.44, 1.3,
             "Campaign Performance Report",
             34, bold=True, color=_WHITE, align=PP_ALIGN.CENTER)
    _textbox(s1, 0.94, 3.3, 11.44, 0.5,
             date.today().strftime("%B %d, %Y"),
             16, color=_CYAN, align=PP_ALIGN.CENTER)
    file_names = "  |  ".join(fi["name"] for fi in file_info)
    _textbox(s1, 0.94, 3.9, 11.44, 0.45,
             f"Sources: {file_names}", 11, color=_GREY, align=PP_ALIGN.CENTER)

    # ── Slide 2: Executive Summary ────────────────────────────────────────────
    s2 = prs.slides.add_slide(lay_content)
    _textbox(s2, 0.94, 0.28, 11.44, 0.75, "Executive Summary",
             22, bold=True, color=_WHITE)

    exec_metrics = [
        ("Total Impressions", f"{total_impressions:,.0f}"),
        ("Total Clicks",      f"{total_clicks:,.0f}"),
        ("Total Spend",       f"${total_spend:,.0f}"),
        ("Avg CTR",           f"{avg_ctr:.2%}"   if avg_ctr is not None else "N/A"),
        ("Avg CPM",           f"${avg_cpm:,.2f}" if avg_cpm is not None else "N/A"),
    ]
    bw = 2.35; gap = 0.15; bstart = 0.55
    for i, (lbl, val) in enumerate(exec_metrics):
        _metric_box(s2, bstart + i * (bw + gap), 1.25, bw, 1.1, lbl, val)

    if not camp_summary.empty:
        cols = [c for c in ["campaign", "impressions", "clicks", "spend_usd", "ctr", "cpm"]
                if c in camp_summary.columns]
        col_labels = {"campaign": "Brand", "impressions": "Impressions",
                      "clicks": "Clicks", "spend_usd": "Spend", "ctr": "CTR", "cpm": "CPM"}
        col_widths = {"campaign": 3.5, "impressions": 1.7, "clicks": 1.3,
                      "spend_usd": 1.6, "ctr": 1.3, "cpm": 1.3}

        x_start = 0.55
        y_hdr   = 2.55
        x = x_start
        for col in cols:
            _textbox(s2, x, y_hdr, col_widths[col], 0.3,
                     col_labels[col], 9, bold=True, color=_CYAN)
            x += col_widths[col] + 0.05

        _rect(s2, x_start, y_hdr + 0.32, _W - x_start - 0.45, 0.03, _CYAN)

        for row_i, (_, row) in enumerate(camp_summary.iterrows()):
            y_row = y_hdr + 0.42 + row_i * 0.46
            if y_row + 0.4 > _H - 0.45:
                break
            row_bg = RGBColor(0x1a, 0x17, 0x4a) if row_i % 2 == 0 else _NAVY
            _rect(s2, x_start - 0.02, y_row - 0.03,
                  _W - x_start - 0.43, 0.44, row_bg)
            x = x_start
            for col in cols:
                w = col_widths[col]
                if col == "campaign":
                    val_str = str(row.get(col, ""))
                elif col == "impressions":
                    val_str = f"{int(row[col]):,}"  if pd.notna(row.get(col)) else ""
                elif col == "clicks":
                    val_str = f"{int(row[col]):,}"  if pd.notna(row.get(col)) else ""
                elif col == "spend_usd":
                    val_str = f"${row[col]:,.0f}"   if pd.notna(row.get(col)) else ""
                elif col == "ctr":
                    val_str = f"{row[col]:.2%}"     if pd.notna(row.get(col)) else ""
                elif col == "cpm":
                    val_str = f"${row[col]:,.2f}"   if pd.notna(row.get(col)) else ""
                else:
                    val_str = str(row.get(col, ""))
                _textbox(s2, x, y_row, w, 0.38, val_str, 10, color=_WHITE)
                x += w + 0.05

    _footer(s2)

    # ── Slides 3–8: one per chart ─────────────────────────────────────────────
    # Each entry: (title, buffer, right-panel function).
    # Slides are skipped automatically if the buffer is None (chart not rendered).
    # Charts 1–3 show AI insights on the right; Charts 4–6 show recommendations.
    has_insights = bool(insights_text)
    has_camp     = not camp_summary.empty

    def insights_fn(s):
        if has_insights:
            _right_insights(s, insights_text)
        else:
            _textbox(s, 8.2, 3.5, 4.85, 0.5,
                     "Generate AI insights in the app to populate this panel.",
                     8, color=_GREY)

    def recs_fn(s):
        if has_camp:
            _right_recs(s, camp_summary)
        else:
            _textbox(s, 8.2, 3.5, 4.85, 0.5,
                     "No campaign data available.", 8, color=_GREY)

    chart_slides = [
        ("Impressions by Brand",          buf_impressions, insights_fn),
        ("CTR by Brand",                 buf_ctr_chart,   insights_fn),
        ("Total Spend by Brand",         buf_spend_chart, recs_fn),
        ("Top 10 Line Items",            buf_line_items,  recs_fn),
        ("Impressions by Device Type",   buf_device,      recs_fn),
        ("Impressions by Environment",   buf_environment, recs_fn),
    ]

    for title, buf, fill_fn in chart_slides:
        if buf is not None:
            _chart_slide(prs, lay_content, title, buf, fill_fn)

    # Save to an in-memory buffer and return it
    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.title("Insights App")
st.sidebar.markdown("---")
st.sidebar.subheader("Loaded Files")

# Placeholder — populated after files are uploaded
file_status = st.sidebar.empty()

# ── Main header ───────────────────────────────────────────────────────────────
st.title("Ad Tech Insights & Reporting")
st.markdown(
    "<p style='color:#6b7280;font-size:14px;margin-top:-12px;'>"
    "Upload CSV exports from DV360, TTD or any DSP to generate insights and reports."
    "</p>",
    unsafe_allow_html=True,
)

# ── File uploader ─────────────────────────────────────────────────────────────
st.subheader("Upload DSP Export Files")

uploaded_files = st.file_uploader(
    "Drag and drop CSV files here, or click to browse. Multiple files accepted.",
    type=["csv"],
    accept_multiple_files=True,
)

# ── Process files ─────────────────────────────────────────────────────────────
if not uploaded_files:
    # Show a friendly prompt when nothing is uploaded yet
    st.markdown("""
    <div style='text-align:center;padding:48px 0;color:#9ca3af;'>
        <div style='font-size:48px;margin-bottom:12px;'>📂</div>
        <div style='font-size:16px;font-weight:600;'>No files uploaded yet</div>
        <div style='font-size:13px;margin-top:6px;'>Supports DV360 and TTD CSV exports</div>
    </div>
    """, unsafe_allow_html=True)
    file_status.markdown("_No files loaded yet._")

else:
    # Load and stack all uploaded files into one DataFrame
    frames = []
    file_info = []   # used to populate the sidebar

    with st.spinner("Reading and normalising files…"):
        for f in uploaded_files:
            df_file, dsp = load_and_normalise(f)
            frames.append(df_file)
            file_info.append({"name": f.name, "rows": len(df_file), "dsp": dsp})

    # Combine all files into a single DataFrame
    df_all = pd.concat(frames, ignore_index=True)

    # ── Sidebar file list ─────────────────────────────────────────────────────
    badge_class = {"DV360": "badge-dv360", "TTD": "badge-ttd", "Generic": "badge-generic"}
    sidebar_html = ""
    for fi in file_info:
        bc = badge_class.get(fi["dsp"], "badge-generic")
        sidebar_html += (
            f"<div style='margin-bottom:10px;font-size:13px;'>"
            f"<b>{fi['name']}</b>"
            f"<span class='source-badge {bc}'>{fi['dsp']}</span>"
            f"<br><span style='color:#6b7280;'>{fi['rows']:,} rows</span>"
            f"</div>"
        )
    file_status.markdown(sidebar_html, unsafe_allow_html=True)

    # ── Summary metrics ───────────────────────────────────────────────────────
    st.subheader("Summary Metrics")

    total_impressions = df_all["impressions"].sum()  if "impressions" in df_all.columns else 0
    total_clicks      = df_all["clicks"].sum()       if "clicks"      in df_all.columns else 0
    total_spend       = df_all["spend_usd"].sum()    if "spend_usd"   in df_all.columns else 0
    avg_ctr           = df_all["ctr"].mean()         if "ctr"         in df_all.columns else None
    avg_cpm           = df_all["cpm"].mean()         if "cpm"         in df_all.columns else None

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Impressions", f"{total_impressions:,.0f}")
    col2.metric("Total Clicks",      f"{total_clicks:,.0f}")
    col3.metric("Total Spend",       f"${total_spend:,.0f}")
    col4.metric("Avg CTR",           f"{avg_ctr:.2%}"    if avg_ctr is not None else "N/A")
    col5.metric("Avg CPM",           f"${avg_cpm:,.2f}"  if avg_cpm is not None else "N/A")

    # Build campaign-level summary now so it's available for both insights and PPTX export
    if "campaign" in df_all.columns:
        _agg = {c: (c, "sum") for c in ["impressions", "clicks", "spend_usd"] if c in df_all.columns}
        camp_summary = df_all.groupby("campaign").agg(**_agg).reset_index()
        if "impressions" in camp_summary.columns and "clicks" in camp_summary.columns:
            camp_summary["ctr"] = camp_summary["clicks"] / camp_summary["impressions"]
        if "impressions" in camp_summary.columns and "spend_usd" in camp_summary.columns:
            camp_summary["cpm"] = camp_summary["spend_usd"] / camp_summary["impressions"] * 1000
    else:
        camp_summary = pd.DataFrame()

    # ── Charts ────────────────────────────────────────────────────────────────
    st.subheader("Performance Charts")

    # Colour palette — consistent across all charts
    PALETTE = [CYAN, GREEN, PURPLE, MAGENTA, NAVY,
               "#f59e0b", "#ef4444", "#3b82f6", "#10b981", "#f97316"]

    # Helper: remove top/right spines and style axes consistently
    def style_ax(ax):
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#d1d5db")
        ax.spines["bottom"].set_color("#d1d5db")
        ax.tick_params(colors="#6b7280", labelsize=8)
        ax.set_axisbelow(True)

    # Helper: show a "column not available" placeholder inside a Streamlit column
    def no_data_msg(msg):
        st.markdown(
            f"<div style='text-align:center;padding:40px;color:#9ca3af;"
            f"border:1px dashed #e5e7eb;border-radius:8px;font-size:13px;'>{msg}</div>",
            unsafe_allow_html=True,
        )

    # ── Row 1: Impressions by campaign | CTR by campaign ──────────────────────
    r1_left, r1_right = st.columns(2)

    # Chart 1 — Total impressions by campaign
    with r1_left:
        st.markdown("**Impressions by Brand**")
        if "impressions" in df_all.columns and "campaign" in df_all.columns:
            c1 = (df_all.groupby("campaign")["impressions"]
                  .sum().reset_index()
                  .sort_values("impressions", ascending=False))
            colors1 = [PALETTE[i % len(PALETTE)] for i in range(len(c1))]
            fig, ax = plt.subplots(figsize=(6, 4))
            ax.bar(c1["campaign"], c1["impressions"], color=colors1, edgecolor="white")
            ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x/1e6:.1f}M" if x >= 1e6 else f"{x/1e3:.0f}K"))
            ax.yaxis.grid(True, linestyle="--", linewidth=0.5, alpha=0.6, color="#e5e7eb")
            style_ax(ax)
            plt.xticks(rotation=20, ha="right", fontsize=8)
            plt.tight_layout()
            st.pyplot(fig)
            buf_impr = io.BytesIO()
            fig.savefig(buf_impr, format="png", dpi=150, bbox_inches="tight")
            buf_impr.seek(0)
            st.session_state["chart_impressions"] = buf_impr
            plt.close(fig)
        else:
            no_data_msg("No campaign or impressions column found.")

    # Chart 2 — CTR by campaign (sorted highest to lowest)
    with r1_right:
        st.markdown("**CTR by Brand**")
        if "ctr" in df_all.columns and "campaign" in df_all.columns:
            c2 = (df_all.groupby("campaign")["ctr"]
                  .mean().reset_index()
                  .sort_values("ctr", ascending=False))
            colors2 = [PALETTE[i % len(PALETTE)] for i in range(len(c2))]
            fig, ax = plt.subplots(figsize=(6, 4))
            bars = ax.bar(c2["campaign"], c2["ctr"] * 100, color=colors2, edgecolor="white")
            ax.bar_label(bars, fmt="%.2f%%", padding=3, fontsize=7.5, color="#374151")
            ax.set_ylabel("Avg CTR (%)", fontsize=8, color="#6b7280")
            ax.set_ylim(0, c2["ctr"].max() * 100 * 1.25)
            ax.yaxis.grid(True, linestyle="--", linewidth=0.5, alpha=0.6, color="#e5e7eb")
            style_ax(ax)
            plt.xticks(rotation=20, ha="right", fontsize=8)
            plt.tight_layout()
            st.pyplot(fig)
            # Capture chart image for PPTX export before closing the figure
            buf_ctr = io.BytesIO()
            fig.savefig(buf_ctr, format="png", dpi=150, bbox_inches="tight")
            buf_ctr.seek(0)
            st.session_state["chart_ctr"] = buf_ctr
            plt.close(fig)
        else:
            no_data_msg("No campaign or CTR data found.")

    # ── Row 2: Spend by campaign | Top 10 line items by impressions ───────────
    r2_left, r2_right = st.columns(2)

    # Chart 3 — Total spend by campaign
    with r2_left:
        st.markdown("**Total Spend by Brand**")
        if "spend_usd" in df_all.columns and "campaign" in df_all.columns:
            c3 = (df_all.groupby("campaign")["spend_usd"]
                  .sum().reset_index()
                  .sort_values("spend_usd", ascending=False))
            colors3 = [PALETTE[i % len(PALETTE)] for i in range(len(c3))]
            fig, ax = plt.subplots(figsize=(6, 4))
            bars = ax.bar(c3["campaign"], c3["spend_usd"], color=colors3, edgecolor="white")
            ax.bar_label(bars, labels=[f"${v:,.0f}" for v in c3["spend_usd"]], padding=3, fontsize=7.5, color="#374151")
            ax.set_ylabel("Total Spend (USD)", fontsize=8, color="#6b7280")
            ax.set_ylim(0, c3["spend_usd"].max() * 1.2)
            ax.yaxis.grid(True, linestyle="--", linewidth=0.5, alpha=0.6, color="#e5e7eb")
            style_ax(ax)
            plt.xticks(rotation=20, ha="right", fontsize=8)
            plt.tight_layout()
            st.pyplot(fig)
            # Capture chart image for PPTX export before closing the figure
            buf_spend = io.BytesIO()
            fig.savefig(buf_spend, format="png", dpi=150, bbox_inches="tight")
            buf_spend.seek(0)
            st.session_state["chart_spend"] = buf_spend
            plt.close(fig)
        else:
            no_data_msg("No campaign or spend column found.")

    # Chart 4 — Top 10 line items by impressions (horizontal bar)
    with r2_right:
        st.markdown("**Top 10 Line Items by Impressions**")
        # Use line_item column if available, fall back to campaign
        li_col = "line_item" if "line_item" in df_all.columns else "campaign"
        if "impressions" in df_all.columns:
            c4 = (df_all.groupby(li_col)["impressions"]
                  .sum().reset_index()
                  .sort_values("impressions", ascending=True)
                  .tail(10))   # tail after ascending sort = top 10, largest at top
            colors4 = [PALETTE[i % len(PALETTE)] for i in range(len(c4))]
            fig, ax = plt.subplots(figsize=(6, 4))
            hbars = ax.barh(c4[li_col], c4["impressions"], color=colors4, edgecolor="white", height=0.6)
            ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x/1e6:.1f}M" if x >= 1e6 else f"{x/1e3:.0f}K"))
            ax.xaxis.grid(True, linestyle="--", linewidth=0.5, alpha=0.6, color="#e5e7eb")
            style_ax(ax)
            plt.yticks(fontsize=8)
            plt.tight_layout()
            st.pyplot(fig)
            buf_li = io.BytesIO()
            fig.savefig(buf_li, format="png", dpi=150, bbox_inches="tight")
            buf_li.seek(0)
            st.session_state["chart_line_items"] = buf_li
            plt.close(fig)
        else:
            no_data_msg("No impressions column found.")

    # ── Row 3: Device type pie | Environment pie ───────────────────────────────
    r3_left, r3_right = st.columns(2)

    # Shared pie chart style settings
    PIE_KWARGS = dict(
        autopct="%1.1f%%",
        startangle=140,
        pctdistance=0.78,
        wedgeprops={"edgecolor": "white", "linewidth": 1.5},
    )

    # Chart 5 — Impressions split by device type
    with r3_left:
        st.markdown("**Impressions by Device Type**")
        if "device_type" in df_all.columns and "impressions" in df_all.columns:
            c5 = (df_all.groupby("device_type")["impressions"]
                  .sum().reset_index()
                  .sort_values("impressions", ascending=False))
            colors5 = [PALETTE[i % len(PALETTE)] for i in range(len(c5))]
            fig, ax = plt.subplots(figsize=(6, 4))
            wedges, texts, autotexts = ax.pie(
                c5["impressions"], labels=c5["device_type"], colors=colors5, **PIE_KWARGS
            )
            for t in texts:     t.set_fontsize(8);  t.set_color("#374151")
            for at in autotexts: at.set_fontsize(7.5); at.set_color("white"); at.set_fontweight("bold")
            plt.tight_layout()
            st.pyplot(fig)
            buf_dev = io.BytesIO()
            fig.savefig(buf_dev, format="png", dpi=150, bbox_inches="tight")
            buf_dev.seek(0)
            st.session_state["chart_device"] = buf_dev
            plt.close(fig)
        else:
            no_data_msg("No device_type column found in this export.<br>Add a 'Device Type' column to your CSV.")

    # Chart 6 — Impressions split by environment (Web, App, YouTube, etc.)
    with r3_right:
        st.markdown("**Impressions by Environment**")
        if "environment" in df_all.columns and "impressions" in df_all.columns:
            c6 = (df_all.groupby("environment")["impressions"]
                  .sum().reset_index()
                  .sort_values("impressions", ascending=False))
            colors6 = [PALETTE[i % len(PALETTE)] for i in range(len(c6))]
            fig, ax = plt.subplots(figsize=(6, 4))
            wedges, texts, autotexts = ax.pie(
                c6["impressions"], labels=c6["environment"], colors=colors6, **PIE_KWARGS
            )
            for t in texts:     t.set_fontsize(8);  t.set_color("#374151")
            for at in autotexts: at.set_fontsize(7.5); at.set_color("white"); at.set_fontweight("bold")
            plt.tight_layout()
            st.pyplot(fig)
            buf_env = io.BytesIO()
            fig.savefig(buf_env, format="png", dpi=150, bbox_inches="tight")
            buf_env.seek(0)
            st.session_state["chart_environment"] = buf_env
            plt.close(fig)
        else:
            no_data_msg("No environment column found in this export.<br>Add an 'Environment' column to your CSV.")

    # ── AI Insights ───────────────────────────────────────────────────────────
    st.subheader("AI Brand Insights")

    # Get the Anthropic API key — check Streamlit secrets first, then env var
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
    elif "campaign" not in df_all.columns:
        st.info("A 'Campaign Name' or 'Brand Name' column is required to generate per-brand insights.")
    else:
        # Build an aggregated summary per campaign (recalculate from totals, not averages)
        has_spend  = "spend_usd"   in df_all.columns
        has_clicks = "clicks"      in df_all.columns
        has_imps   = "impressions" in df_all.columns

        agg_cols = {c: (c, "sum") for c in ["impressions", "clicks", "spend_usd"] if c in df_all.columns}
        camp_summary = df_all.groupby("campaign").agg(**agg_cols).reset_index()

        if has_imps and has_clicks:
            camp_summary["ctr"] = camp_summary["clicks"] / camp_summary["impressions"]
        if has_imps and has_spend:
            camp_summary["cpm"] = camp_summary["spend_usd"] / camp_summary["impressions"] * 1000

        # Format the data as a text table for the prompt.
        # Includes campaign-level totals AND a campaign × environment breakdown
        # when an environment column is present (gives Claude the Web/App/YouTube split).
        def format_summary_table(df):
            lines = ["=== Brand Totals ==="]
            for _, r in camp_summary.iterrows():
                parts = [f"Brand: {r['campaign']}"]
                if "impressions" in r and pd.notna(r["impressions"]):
                    parts.append(f"Impressions: {int(r['impressions']):,}")
                if "clicks" in r and pd.notna(r["clicks"]):
                    parts.append(f"Clicks: {int(r['clicks']):,}")
                if "spend_usd" in r and pd.notna(r["spend_usd"]):
                    parts.append(f"Spend: ${r['spend_usd']:,.0f}")
                if "ctr" in r and pd.notna(r["ctr"]):
                    parts.append(f"CTR: {r['ctr']:.2%}")
                if "cpm" in r and pd.notna(r["cpm"]):
                    parts.append(f"CPM: ${r['cpm']:,.2f}")
                lines.append(" | ".join(parts))

            # Helper: aggregate a dimension column and append formatted rows to lines
            def _add_breakdown(label_col, section_title, label_key):
                if label_col not in df.columns:
                    return
                lines.append(f"\n=== {section_title} ===")
                agg = {c: (c, "sum") for c in ["impressions", "clicks", "spend_usd"]
                       if c in df.columns}
                grp = df.groupby(["campaign", label_col]).agg(**agg).reset_index()
                if "impressions" in grp.columns and "clicks" in grp.columns:
                    grp["ctr"] = grp["clicks"] / grp["impressions"]
                if "impressions" in grp.columns and "spend_usd" in grp.columns:
                    grp["cpm"] = grp["spend_usd"] / grp["impressions"] * 1000
                if "clicks" in grp.columns and "spend_usd" in grp.columns:
                    grp["cpc"] = grp["spend_usd"] / grp["clicks"]
                for _, r in grp.iterrows():
                    parts = [f"Brand: {r['campaign']} | {label_key}: {r[label_col]}"]
                    if "impressions" in r and pd.notna(r["impressions"]):
                        parts.append(f"Impressions: {int(r['impressions']):,}")
                    if "clicks" in r and pd.notna(r["clicks"]):
                        parts.append(f"Clicks: {int(r['clicks']):,}")
                    if "spend_usd" in r and pd.notna(r["spend_usd"]):
                        parts.append(f"Spend: ${r['spend_usd']:,.0f}")
                    if "ctr" in r and pd.notna(r["ctr"]):
                        parts.append(f"CTR: {r['ctr']:.2%}")
                    if "cpm" in r and pd.notna(r["cpm"]):
                        parts.append(f"CPM: ${r['cpm']:,.2f}")
                    if "cpc" in r and pd.notna(r["cpc"]):
                        parts.append(f"CPC: ${r['cpc']:,.2f}")
                    lines.append(" | ".join(parts))

            # Breakdown by Environment (Web, App, YouTube, etc.)
            _add_breakdown("environment", "Breakdown by Brand and Environment", "Environment")

            # Breakdown by Insertion Order / Line Item name
            _add_breakdown("line_item", "Breakdown by Brand and Line Item / Creative", "Line Item")

            # Breakdown by Device Type
            _add_breakdown("device_type", "Breakdown by Brand and Device Type", "Device Type")

            return "\n".join(lines)

        all_campaigns_text = format_summary_table(df_all)
        campaign_list = camp_summary["campaign"].tolist()
        # Store brand names in session_state so other pages (e.g. Brand Memory) can read them
        st.session_state["campaign_list"] = campaign_list

        # System prompt — analyst persona, structured output required
        SYSTEM_PROMPT = (
            "You are a senior programmatic advertising analyst with deep expertise in "
            "DSP campaign performance (DV360, TTD). You write clear, concise, data-driven "
            "commentary for ad tech professionals. Be specific — reference actual numbers. "
            "Follow the section headings and structure exactly as specified in each prompt. "
            "Do not add extra sections or deviate from the requested format."
        )

        def stream_insight(campaign_name: str, all_data: str, brand_context: str = ""):
            """
            Stream per-brand analysis using the standard Display / Video / YouTube
            insertion-order structure. Brand memory is injected as an override block
            at the end of the prompt so it takes priority over all default instructions.
            Yields text chunks from the Claude API.
            """
            client_ai = anthropic.Anthropic(api_key=api_key)

            # Default structure: Campaign Overview + three insertion-order sections.
            # The AI skips any section whose insertion order is absent from the data.
            default_structure = (
                f"**{campaign_name} - Campaign Overview**\n"
                f"Summarise overall campaign performance. Focus on total Revenue (Spend) "
                f"and total Impressions for this brand. Keep to 2-3 sentences.\n\n"
                f"**Display**\n"
                f"Summarise performance for the Display insertion order, focusing on "
                f"average CPM. Then identify:\n"
                f"- Best performing Line Item by CPM (state exact CPM, CPC, CTR)\n"
                f"- Worst performing Line Item by CPM (state exact CPM, CPC, CTR)\n"
                f"- Best performing Creative by CPM (state exact CPM, CPC, CTR)\n"
                f"- Worst performing Creative by CPM (state exact CPM, CPC, CTR)\n"
                f"If no Display insertion order data exists for this brand, omit this "
                f"section entirely — do not mention it at all.\n\n"
                f"**Video**\n"
                f"Summarise performance for the Video insertion order, focusing on CPV "
                f"and VTR. Then identify:\n"
                f"- Best performing Line Item by CPV (state exact CPV, VTR)\n"
                f"- Worst performing Line Item by CPV (state exact CPV, VTR)\n"
                f"- Best performing Creative by CPV (state exact CPV, VTR)\n"
                f"- Worst performing Creative by CPV (state exact CPV, VTR)\n"
                f"If no Video insertion order data exists for this brand, omit this "
                f"section entirely — do not mention it at all.\n\n"
                f"**YouTube**\n"
                f"Summarise performance for the YouTube insertion order, focusing on CPV "
                f"and VTR. Then identify:\n"
                f"- Best performing Line Item by CPV (state exact CPV, VTR)\n"
                f"- Worst performing Line Item by CPV (state exact CPV, VTR)\n"
                f"- Best performing Creative by CPV (state exact CPV, VTR)\n"
                f"- Worst performing Creative by CPV (state exact CPV, VTR)\n"
                f"If no YouTube insertion order data exists for this brand, omit this "
                f"section entirely — do not mention it at all."
            )

            # Brand memory override — appended after the default instructions so it
            # takes explicit priority. Only included when brand context exists.
            if brand_context:
                override_section = (
                    f"\n\nBRAND MEMORY OVERRIDE — These instructions take priority over "
                    f"all default instructions above. Where there is any conflict, always "
                    f"follow these brand-specific instructions instead:\n\n"
                    f"{brand_context}"
                )
            else:
                override_section = ""

            prompt = (
                f"Here is the full performance data for all campaigns in this report:\n\n"
                f"{all_data}\n\n"
                f"Write the analysis for the '{campaign_name}' brand using exactly "
                f"this structure and these headings (use ** for bold):\n\n"
                f"{default_structure}"
                f"{override_section}\n\n"
                f"Use only the data provided — do not invent numbers."
            )

            with client_ai.messages.stream(
                model="claude-sonnet-4-6",
                max_tokens=1200,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                for text in stream.text_stream:
                    yield text

        def stream_overall(all_data: str):
            """
            Stream the cross-campaign summary sections:
            Summary, Best & Worst Performers, Optimisation Recommendations.
            Yields text chunks from the Claude API.
            """
            client_ai = anthropic.Anthropic(api_key=api_key)

            prompt = (
                f"Here is the full performance data for all campaigns in this report:\n\n"
                f"{all_data}\n\n"
                f"Write the following three sections using exactly these headings "
                f"(use ** for bold):\n\n"
                f"**Summary**\n"
                f"Overall commentary across all campaigns and environments. 3-4 sentences.\n\n"
                f"**Best & Worst Performers**\n"
                f"- Best performing device type and why\n"
                f"- Worst performing device type and why\n"
                f"- Best performing creative and why\n"
                f"- Worst performing creative and why\n\n"
                f"**Optimisation Recommendations**\n"
                f"3-5 actionable recommendations based on the data above. Use bullet points.\n\n"
                f"Use only the data provided. Be specific with numbers where possible."
            )

            with client_ai.messages.stream(
                model="claude-sonnet-4-6",
                max_tokens=600,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                for text in stream.text_stream:
                    yield text

        # STYLE LOCK: Do not change insights display formatting
        def _insight_html(text):
            """
            Convert the subset of markdown used in insights to explicitly-styled HTML.
            Forces ALL text to plain black (#111111) so Streamlit's theme accent color
            (teal/cyan) is never applied to bold headers or any other element.

            Handles:
              **text**  → <strong> (black, no color override from theme)
              - item    → <ul><li> list
              blank line → paragraph break
            """
            lines  = text.split("\n")
            parts  = []
            in_ul  = False
            p_style = "margin:4px 0;color:#111111;font-size:14px;line-height:1.7;"
            li_style = "margin:2px 0;color:#111111;font-size:14px;"

            def apply_bold(s):
                # Replace **…** with <strong> that explicitly inherits black
                return re.sub(r'\*\*(.+?)\*\*',
                              r'<strong style="color:#111111;">\1</strong>', s)

            for line in lines:
                stripped = line.strip()
                if not stripped:
                    if in_ul:
                        parts.append("</ul>")
                        in_ul = False
                    continue
                if stripped.startswith("- "):
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

        # Generate Insights button — analysis only runs when clicked
        if st.button("✨ Generate Insights", type="primary"):
            st.session_state["insights_triggered"] = True

        if st.session_state.get("insights_triggered"):
            # Load brand memory once so it's available for every campaign
            _insights_bm = load_brand_memory()

            for campaign in campaign_list:
                # Look up brand context using partial matching (case-insensitive).
                # e.g. brand key "Nike" matches campaign "Nike Summer 2024".
                _campaign_brand_context = ""
                for _bm_key, _bm_val in _insights_bm.items():
                    if _bm_key.lower() in campaign.lower():
                        _campaign_brand_context = _bm_val.get("rationale", "")
                        break

                # One expander per campaign, collapsed by default
                with st.expander(f"**{campaign}**", expanded=False):
                    # Show indicator when brand memory is applied
                    if _campaign_brand_context:
                        st.markdown(
                            "<p style='color:#00b2a9;font-size:13px;font-weight:600;"
                            "margin:0 0 8px 0;'>✓ Brand context applied</p>",
                            unsafe_allow_html=True,
                        )
                    placeholder = st.empty()
                    accumulated = ""
                    for chunk in stream_insight(campaign, all_campaigns_text,
                                                _campaign_brand_context):
                        accumulated += chunk
                        placeholder.markdown(_insight_html(accumulated),
                                             unsafe_allow_html=True)
                    # Save completed text for PPTX export
                    st.session_state.setdefault("insights_text", {})[campaign] = accumulated

            # Overall summary — runs once after all per-campaign sections
            with st.expander("**📊 Summary & Recommendations**", expanded=False):
                placeholder = st.empty()
                accumulated = ""
                for chunk in stream_overall(all_campaigns_text):
                    accumulated += chunk
                    placeholder.markdown(_insight_html(accumulated),
                                         unsafe_allow_html=True)
                st.session_state["insights_overall"] = accumulated

    # ── Data preview ──────────────────────────────────────────────────────────
    st.subheader("Data Preview")

    # Show total rows and which files contributed
    total_rows  = len(df_all)
    file_count  = len(uploaded_files)
    st.markdown(
        f"<p style='color:#6b7280;font-size:13px;margin-top:-8px;'>"
        f"{total_rows:,} rows loaded from {file_count} file{'s' if file_count > 1 else ''}.</p>",
        unsafe_allow_html=True,
    )

    # Format the preview table — keep raw numbers readable
    preview_df = df_all.copy()
    if "impressions" in preview_df.columns:
        preview_df["impressions"] = preview_df["impressions"].apply(
            lambda x: f"{x:,.0f}" if pd.notna(x) else ""
        )
    if "clicks" in preview_df.columns:
        preview_df["clicks"] = preview_df["clicks"].apply(
            lambda x: f"{x:,.0f}" if pd.notna(x) else ""
        )
    if "spend_usd" in preview_df.columns:
        preview_df["spend_usd"] = preview_df["spend_usd"].apply(
            lambda x: f"${x:,.2f}" if pd.notna(x) else ""
        )
    if "ctr" in preview_df.columns:
        preview_df["ctr"] = preview_df["ctr"].apply(
            lambda x: f"{x:.2%}" if pd.notna(x) else ""
        )
    if "cpm" in preview_df.columns:
        preview_df["cpm"] = preview_df["cpm"].apply(
            lambda x: f"${x:,.2f}" if pd.notna(x) else ""
        )

    st.dataframe(preview_df, use_container_width=True)

    # ── Sidebar: Download Report button ───────────────────────────────────────
    st.sidebar.markdown("---")
    st.sidebar.subheader("Export")

    # Pull all chart buffers and insights text from session_state (populated above)
    _insights = st.session_state.get("insights_text", {})

    # Build the PPTX file in memory
    pptx_buf = build_pptx(
        file_info         = file_info,
        total_impressions = total_impressions,
        total_clicks      = total_clicks,
        total_spend       = total_spend,
        avg_ctr           = avg_ctr,
        avg_cpm           = avg_cpm,
        camp_summary      = camp_summary,
        insights_text     = _insights,
        buf_impressions   = st.session_state.get("chart_impressions"),
        buf_ctr_chart     = st.session_state.get("chart_ctr"),
        buf_spend_chart   = st.session_state.get("chart_spend"),
        buf_line_items    = st.session_state.get("chart_line_items"),
        buf_device        = st.session_state.get("chart_device"),
        buf_environment   = st.session_state.get("chart_environment"),
    )

    st.sidebar.download_button(
        label     = "📥 Download Report (.pptx)",
        data      = pptx_buf,
        file_name = f"campaign_report_{date.today():%Y-%m-%d}.pptx",
        mime      = "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
