# pages/supply_brief.py
# Weekly Supply Brief — SSP / sell-side performance view
#
# Vocabulary: Revenue, eCPM, Fill Rate, Ad Requests, Demand Source, Deal Type
# Hierarchy: Publisher → Property → Ad Unit → Format
#
# Sections:
#  1. Filters (Publisher | Property | Format | Device | Demand Source | Week ending)
#  2. Headline cards with WoW deltas
#  3. Supply funnel (Ad Requests → Filled → Completed Views)
#  4. Trends 2×2 (Revenue / Fill Rate / eCPM / Unfilled — with prior-4-week avg dotted line)
#  5. Breakdown donuts — Revenue by Format | Device | Demand Source | Buyer
#  6. Yield Opportunities — rules-based, ranked by revenue impact
#  6b. Publisher Commentary — AI-written narrative (on-demand, cached in session state)
#  7. Explore Data — pivot table with dynamic dims / metrics
#  8. Generate Brief — dialog + PPTX export (reuses cached commentary)

import html as _html
import io
import json
import os
import random
import sys
from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Allow importing from utils/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.design_system import (
    CHART_PALETTE, PLOTLY_CONFIG, PRIMARY, SECONDARY, SUCCESS,
    WARNING, DANGER, WHITE, TEXT_SEC, apply_plotly_style, metric_card,
)

# STYLE LOCK: Pacebird design system — #F5A623 orange, #1B2A4A navy, Poppins.
# Shared CSS applied globally by app.py. Do not override.

# ── File path for cached supply data ─────────────────────────────────────────
_APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(_APP_ROOT, "data", "supply_performance.json")

# ── Data generation ───────────────────────────────────────────────────────────

def _generate_supply_data():
    """
    Generate 12 weeks of daily supply-side performance data.
    Produces 1,260 rows (15 combos × 84 days).
    Uses a fixed seed (42) for reproducible results.

    Two deliberate anomalies:
      A1 — Week 10: Nine / 9Now / Pre-roll / CTV fill rate crashes from ~90% to ~52%
      A2 — Week 11: Seven West Media / 7plus / Mid-roll / Mobile eCPM spikes from ~A$22 to ~A$29
    """
    random.seed(42)

    # Compute 12-week window ending on the most recent Sunday
    today = date.today()
    # In Python, Monday = 0, Sunday = 6
    days_to_sunday = (today.weekday() + 1) % 7   # days since last Sunday
    end_date = today - timedelta(days=days_to_sunday)
    start_date = end_date - timedelta(weeks=12) + timedelta(days=1)

    # Each combo: (publisher, property, ad_unit, format, device, demand_source,
    #              buyer, deal_id, base_daily_requests, base_fill_rate,
    #              base_ecpm_aud, base_completion_rate)
    combos = [
        # ── Nine / 9Now ──────────────────────────────────────────────────────
        ("Nine", "9Now", "9Now_PreRoll_CTV",   "Pre-roll",        "Connected TV", "Programmatic Guaranteed", "DV360",           "PG-NINE-001",  250_000, 0.90, 38.0, 0.94),
        ("Nine", "9Now", "9Now_MidRoll_CTV",   "Mid-roll",        "Connected TV", "Open Auction",            "The Trade Desk",  "",             180_000, 0.82, 32.0, 0.88),
        ("Nine", "9Now", "9Now_PreRoll_MOB",   "Pre-roll",        "Mobile",       "Preferred Deal",          "Amazon DSP",      "PD-NINE-002",  320_000, 0.78, 19.0, 0.72),
        ("Nine", "9Now", "9Now_PauseAd_CTV",   "Pause Ad",        "Connected TV", "Direct IO",               "Direct",          "DIO-NINE-001", 100_000, 0.93, 28.0, 0.85),
        # ── Seven West Media / 7plus ─────────────────────────────────────────
        ("Seven West Media", "7plus", "7plus_PreRoll_CTV",  "Pre-roll", "Connected TV", "Programmatic Guaranteed", "DV360",          "PG-SWM-001", 200_000, 0.89, 36.0, 0.93),
        ("Seven West Media", "7plus", "7plus_MidRoll_MOB",  "Mid-roll", "Mobile",       "Open Auction",            "The Trade Desk", "",           280_000, 0.71, 22.0, 0.68),
        # ── Paramount ANZ / 10 play ──────────────────────────────────────────
        ("Paramount ANZ", "10 play", "10play_PreRoll_DSK",  "Pre-roll",  "Desktop",      "Open Auction",  "Yahoo DSP",       "",             450_000, 0.63, 11.50, 0.65),
        ("Paramount ANZ", "10 play", "10play_MidRoll_CTV",  "Mid-roll",  "Connected TV", "Preferred Deal","DV360",           "PD-PAR-001",   150_000, 0.86, 42.0, 0.91),
        ("Paramount ANZ", "10 play", "10play_PostRoll_MOB", "Post-roll", "Mobile",       "Open Auction",  "The Trade Desk",  "",             200_000, 0.68,  9.50, 0.58),
        # ── SBS / SBS On Demand ──────────────────────────────────────────────
        ("SBS", "SBS On Demand", "SBS_PreRoll_CTV",    "Pre-roll",        "Connected TV", "Private Auction", "Amazon DSP", "PA-SBS-001", 120_000, 0.80, 24.0, 0.92),
        ("SBS", "SBS On Demand", "SBS_Display_DSK",    "Display Companion","Desktop",     "Open Auction",    "Yahoo DSP",  "",           300_000, 0.61,  5.50, 0.00),
        # ── Foxtel Media / Binge ─────────────────────────────────────────────
        ("Foxtel Media", "Binge", "Binge_PreRoll_CTV",  "Pre-roll", "Connected TV", "Programmatic Guaranteed", "DV360",          "PG-FOX-001",  180_000, 0.91, 39.0, 0.95),
        ("Foxtel Media", "Binge", "Binge_MidRoll_CTV",  "Mid-roll", "Connected TV", "Preferred Deal",          "The Trade Desk", "PD-FOX-001",  140_000, 0.87, 44.0, 0.89),
        # ── TVNZ / TVNZ+ ─────────────────────────────────────────────────────
        ("TVNZ", "TVNZ+", "TVNZ_PreRoll_CTV",  "Pre-roll", "Connected TV", "Programmatic Guaranteed", "DV360",    "PG-TVNZ-001", 160_000, 0.88, 35.0, 0.92),
        ("TVNZ", "TVNZ+", "TVNZ_PreRoll_MOB",  "Pre-roll", "Mobile",       "Open Auction",            "Yahoo DSP","",            220_000, 0.70, 13.0, 0.71),
    ]

    rows = []
    all_dates = [start_date + timedelta(days=i) for i in range(84)]

    for day_idx, d in enumerate(all_dates):
        week_num = day_idx // 7   # 0 = first week, 11 = last week

        for combo_idx, (pub, prop, unit, fmt, device, demand, buyer, deal,
                        base_req, base_fill, base_ecpm, base_compl) in enumerate(combos):

            # Daily noise — small random variation around baselines
            ad_requests  = int(base_req  * random.uniform(0.85, 1.15))
            fill_rate    = base_fill + random.uniform(-0.04, 0.04)
            ecpm         = base_ecpm * (1.0 + random.uniform(-0.08, 0.08))

            # ── Anomaly A1: Week 10 (week_num=9), Nine PreRoll CTV (combo_idx=0)
            # Fill rate crashes from ~90% to ~52% — demand partner withdrawal
            if combo_idx == 0 and week_num == 9:
                fill_rate = 0.52 + random.uniform(-0.04, 0.04)

            # ── Anomaly A2: Week 11 (week_num=10), SWM MidRoll Mobile (combo_idx=5)
            # eCPM spikes ~30%+ — Preferred Deal floor raised
            if combo_idx == 5 and week_num == 10:
                ecpm = 29.0 + random.uniform(-0.8, 1.5)

            fill_rate = max(0.10, min(0.99, fill_rate))

            ad_impressions      = int(ad_requests * fill_rate)
            unfilled_impressions = ad_requests - ad_impressions
            revenue_aud         = round(ad_impressions / 1_000.0 * ecpm, 2)

            # Completed views: 0 for Display Companion (no video completion)
            if fmt == "Display Companion":
                completed_views = 0
            else:
                compl_rate = max(0.0, min(0.99, base_compl + random.uniform(-0.03, 0.03)))
                completed_views = int(ad_impressions * compl_rate)

            # Timeouts and errors — small proportion of ad_requests
            timeout_count = int(ad_requests * random.uniform(0.008, 0.025))
            error_count   = int(ad_requests * random.uniform(0.003, 0.012))

            rows.append({
                "date":                d.isoformat(),
                "publisher":           pub,
                "property":            prop,
                "ad_unit":             unit,
                "format":              fmt,
                "device":              device,
                "demand_source":       demand,
                "buyer":               buyer,
                "deal_id":             deal,
                "ad_requests":         ad_requests,
                "ad_impressions":      ad_impressions,
                "unfilled_impressions": unfilled_impressions,
                "revenue_aud":         revenue_aud,
                "completed_views":     completed_views,
                "timeout_count":       timeout_count,
                "error_count":         error_count,
            })

    return rows


def load_supply_data():
    """
    Load supply data from JSON. Generates and saves data on first load
    (if the file has empty 'data' or doesn't exist yet).
    """
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            stored = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        stored = {}

    if not stored.get("data"):
        rows = _generate_supply_data()
        stored["_disclaimer"] = (
            "Fabricated data only — not real publisher inventory. "
            "For demo and testing purposes."
        )
        stored["data"] = rows
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            # compact JSON to keep file size reasonable (~5 MB)
            json.dump(stored, f, separators=(",", ":"))

    df = pd.DataFrame(stored["data"])
    df["date"] = pd.to_datetime(df["date"])
    return df


# ── Rate metric helpers ───────────────────────────────────────────────────────

def calc_rates(df):
    """
    Add rate columns to an already-aggregated DataFrame.
    All denominators are .clip(lower=1) to avoid ZeroDivisionError.
    inf values are replaced with 0.

    fill_rate       = ad_impressions / ad_requests
    ecpm            = revenue_aud / ad_impressions * 1000
    completion_rate = completed_views / ad_impressions
    timeout_rate    = timeout_count / ad_requests
    """
    df = df.copy()
    cols = set(df.columns)

    # Each rate is only computed when BOTH required raw columns are present.
    # If either is missing the rate column is simply omitted — the UI shows
    # "—" (or the absent_placeholder) via the existing pattern.

    if {"ad_impressions", "ad_requests"}.issubset(cols):
        df["fill_rate"] = (
            df["ad_impressions"] / df["ad_requests"].clip(lower=1)
        ).replace([float("inf"), float("-inf")], 0)

    if {"revenue_aud", "ad_impressions"}.issubset(cols):
        df["ecpm"] = (
            df["revenue_aud"] / df["ad_impressions"].clip(lower=1) * 1_000
        ).replace([float("inf"), float("-inf")], 0)

    if {"completed_views", "ad_impressions"}.issubset(cols):
        df["completion_rate"] = (
            df["completed_views"] / df["ad_impressions"].clip(lower=1)
        ).replace([float("inf"), float("-inf")], 0)

    if {"timeout_count", "ad_requests"}.issubset(cols):
        df["timeout_rate"] = (
            df["timeout_count"] / df["ad_requests"].clip(lower=1)
        ).replace([float("inf"), float("-inf")], 0)

    return df


def week_totals(df):
    """Sum raw counts for df and compute derived rate metrics. Returns a dict."""
    if df.empty:
        return {}
    t = {
        "ad_requests":    int(df["ad_requests"].sum()),
        "ad_impressions": int(df["ad_impressions"].sum()),
        "revenue_aud":    float(df["revenue_aud"].sum()),
        "completed_views":int(df["completed_views"].sum()),
        "timeout_count":  int(df["timeout_count"].sum()),
    }
    t["fill_rate"]       = t["ad_impressions"] / max(t["ad_requests"], 1)
    t["ecpm"]            = t["revenue_aud"]    / max(t["ad_impressions"], 1) * 1_000
    t["completion_rate"] = t["completed_views"]/ max(t["ad_impressions"], 1)
    t["timeout_rate"]    = t["timeout_count"]  / max(t["ad_requests"], 1)
    return t


def pct_delta(cur_val, prv_val):
    """Return WoW % change as a string (e.g. '+12.3%' or '-5.1%'). None if no prior."""
    if not prv_val:
        return None
    chg = (cur_val - prv_val) / abs(prv_val) * 100
    return f"+{chg:.1f}%" if chg >= 0 else f"{chg:.1f}%"


# ── UI helpers ────────────────────────────────────────────────────────────────

def section_header(title):
    """Render a styled section heading matching the Pacebird design system."""
    st.markdown(
        f'<h3 style="font-family:\'Poppins\',system-ui,sans-serif;font-size:18px;'
        f'font-weight:700;color:{SECONDARY};margin:32px 0 16px 0;padding:0;">'
        f'{title}</h3>',
        unsafe_allow_html=True,
    )


def absent_placeholder(label, height=300):
    """'Not in this report' placeholder matching the existing page pattern."""
    st.markdown(
        f'<div style="background:{WHITE};border:0.5px solid rgba(27,42,74,0.12);'
        f'border-radius:16px;height:{height}px;display:flex;align-items:center;'
        f'justify-content:center;color:{TEXT_SEC};font-family:Poppins,sans-serif;'
        f'font-size:13px;font-style:italic;">'
        f'"{label}" not in this report</div>',
        unsafe_allow_html=True,
    )


# ── Prior 4-week average (for trend reference lines) ──────────────────────────

def prior_4w_avg(df_filt, metric_col, sel_week_end):
    """
    Compute a single float representing the average daily value of metric_col
    over the 4 weeks immediately before the selected week.
    Used as a horizontal dotted reference line in trend charts.
    """
    p4_end   = sel_week_end - timedelta(days=1)       # day before selected week
    p4_start = p4_end - timedelta(days=27)            # 28 days = 4 weeks

    sub = df_filt[
        (df_filt["date"].dt.date >= p4_start) &
        (df_filt["date"].dt.date <= p4_end)
    ]
    if sub.empty:
        return None

    raw_cols = ["ad_requests", "ad_impressions", "revenue_aud",
                "completed_views", "unfilled_impressions"]
    avail = [c for c in raw_cols if c in sub.columns]
    daily = sub.groupby("date")[avail].sum().reset_index()

    if metric_col == "revenue_aud":
        return float(daily["revenue_aud"].mean()) if "revenue_aud" in daily.columns else None
    if metric_col == "fill_rate":
        return daily["ad_impressions"].sum() / max(daily["ad_requests"].sum(), 1)
    if metric_col == "ecpm":
        return daily["revenue_aud"].sum() / max(daily["ad_impressions"].sum(), 1) * 1_000
    if metric_col == "unfilled_impressions":
        uf = daily["ad_requests"] - daily["ad_impressions"]
        return float(uf.mean())
    return None


# ── Trend chart builder ───────────────────────────────────────────────────────

def make_trend_chart(daily_df, y_col, title, ref_avg=None, height=380):
    """
    Plotly line chart for a daily metric, with an optional dotted prior-4-week
    average reference line.
    """
    fig = go.Figure()

    if not daily_df.empty and y_col in daily_df.columns:
        fig.add_trace(go.Scatter(
            x=daily_df["date"],
            y=daily_df[y_col],
            mode="lines",
            name=title,
            line=dict(color=SECONDARY, width=2),
        ))

    if ref_avg is not None and not daily_df.empty:
        x_range = [daily_df["date"].min(), daily_df["date"].max()]
        fig.add_trace(go.Scatter(
            x=x_range,
            y=[ref_avg, ref_avg],
            mode="lines",
            name="Prior 4-wk avg",
            line=dict(color=PRIMARY, width=1.5, dash="dot"),
            hovertemplate=f"Prior 4-wk avg: {ref_avg:,.2f}<extra></extra>",
        ))

    fig = apply_plotly_style(fig, height=height)
    fig.update_layout(
        title=dict(
            text=title,
            font=dict(size=12, family="Poppins", color=SECONDARY),
            x=0,
        ),
        margin=dict(l=50, r=20, t=40, b=50),
        showlegend=True,
    )
    return fig


# ── Donut chart builder ───────────────────────────────────────────────────────

def build_donut(df, group_col, title, height=300):
    """
    Pie / donut chart: Revenue share by group_col.
    Each segment label shows the segment's eCPM.
    """
    if df.empty or group_col not in df.columns:
        return None

    grp = (
        df.groupby(group_col)
        .agg(revenue_aud=("revenue_aud", "sum"),
             ad_impressions=("ad_impressions", "sum"))
        .reset_index()
    )
    grp = grp[grp["revenue_aud"] > 0].sort_values("revenue_aud", ascending=False)
    if grp.empty:
        return None

    grp["ecpm_seg"] = (
        grp["revenue_aud"] / grp["ad_impressions"].clip(lower=1) * 1_000
    ).replace([float("inf"), float("-inf")], 0)

    fig = go.Figure(go.Pie(
        labels=grp[group_col],
        values=grp["revenue_aud"],
        hole=0.4,
        customdata=grp[["ecpm_seg"]].values,
        textinfo="label+percent",
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Revenue: A$%{value:,.0f}<br>"
            "eCPM: A$%{customdata[0]:.2f}<br>"
            "Share: %{percent}<extra></extra>"
        ),
        showlegend=False,
        marker=dict(colors=CHART_PALETTE[:len(grp)]),
    ))
    fig = apply_plotly_style(fig, height=height)
    fig.update_layout(
        title=dict(
            text=title,
            font=dict(size=12, family="Poppins", color=SECONDARY),
            x=0.5, xanchor="center",
        ),
        margin=dict(l=10, r=10, t=40, b=10),
    )
    return fig


# ── PPTX builder ──────────────────────────────────────────────────────────────

def build_supply_pptx(df_week, yield_findings, sections, sel_week_label, cur, ai_narrative=""):
    """
    Build the Weekly Supply Brief PowerPoint from scratch (no template file).
    Matches the Pacebird dark premium template used across the app.
    Returns a BytesIO buffer.
    """
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Inches, Pt

    # Dark premium colours
    BG_RGB    = RGBColor(0x0D, 0x1B, 0x2A)
    WHT_RGB   = RGBColor(0xFF, 0xFF, 0xFF)
    GREY_RGB  = RGBColor(0xA8, 0xB2, 0xBC)
    ORG_RGB   = RGBColor(0xF5, 0xA6, 0x23)
    GRN_RGB   = RGBColor(0x10, 0xB9, 0x81)
    RED_RGB   = RGBColor(0xEF, 0x44, 0x44)

    prs = Presentation()
    prs.slide_width  = Inches(13.33)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    def add_slide():
        slide = prs.slides.add_slide(blank_layout)
        fill = slide.background.fill
        fill.solid()
        fill.fore_color.rgb = BG_RGB
        return slide

    def add_text(slide, text, left, top, width, height,
                 size=14, bold=False, color=None, align=PP_ALIGN.LEFT):
        tb = slide.shapes.add_textbox(
            Inches(left), Inches(top), Inches(width), Inches(height)
        )
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = align
        run = p.add_run()
        run.text = str(text)
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.name = "Calibri"
        run.font.color.rgb = color or WHT_RGB

    def add_footer(slide, pg_num):
        add_text(slide, "Weekly Supply Brief", 0.3, 7.1, 6, 0.3, size=9, color=GREY_RGB)
        add_text(slide, str(pg_num), 12.8, 7.1, 0.5, 0.3, size=9,
                 color=GREY_RGB, align=PP_ALIGN.RIGHT)

    pg = 1

    # ── Slide 1: Headline Summary ─────────────────────────────────────────────
    if sections.get("headline_summary", True):
        slide = add_slide()
        add_text(slide, "Weekly Supply Brief", 0.4, 0.2, 10, 0.55,
                 size=26, bold=True, color=WHT_RGB)
        add_text(slide, f"Week ending {sel_week_label}", 0.4, 0.78, 10, 0.35,
                 size=13, color=GREY_RGB)

        if cur:
            kpis = [
                ("Revenue",         f"A${cur.get('revenue_aud', 0):,.0f}"),
                ("Ad Requests",     f"{cur.get('ad_requests', 0):,.0f}"),
                ("Fill Rate",       f"{cur.get('fill_rate', 0):.1%}"),
                ("eCPM",            f"A${cur.get('ecpm', 0):.2f}"),
                ("Completion Rate", f"{cur.get('completion_rate', 0):.1%}"),
            ]
            for ki, (lbl, val) in enumerate(kpis):
                x = 0.4 + ki * 2.55
                add_text(slide, lbl, x, 1.3, 2.5, 0.3, size=9,  color=GREY_RGB)
                add_text(slide, val, x, 1.6, 2.5, 0.45, size=20, bold=True, color=ORG_RGB)

        # Revenue breakdown by publisher (text table)
        if not df_week.empty:
            add_text(slide, "Revenue by Publisher", 0.4, 2.3, 12.5, 0.3,
                     size=11, bold=True, color=GREY_RGB)
            pub_rev = (
                df_week.groupby("publisher")["revenue_aud"].sum()
                .sort_values(ascending=False)
            )
            for ri, (pub, rev) in enumerate(pub_rev.items()):
                if ri >= 6:
                    break
                add_text(slide, f"{pub}: A${rev:,.0f}", 0.4 + (ri % 3) * 4.2,
                         2.65 + (ri // 3) * 0.38, 4, 0.35, size=11, color=WHT_RGB)

        add_footer(slide, pg); pg += 1

    # ── Slide 2: Yield Opportunities ─────────────────────────────────────────
    if sections.get("yield_opportunities", True) and yield_findings:
        slide = add_slide()
        add_text(slide, "Yield Opportunities", 0.4, 0.2, 12.5, 0.55,
                 size=22, bold=True, color=WHT_RGB)
        add_text(slide, "Rules-based findings this week, ranked by revenue impact",
                 0.4, 0.78, 12.5, 0.3, size=12, color=GREY_RGB)

        for fi, finding in enumerate(yield_findings[:6]):
            y = 1.25 + fi * 1.0
            add_text(slide, f"● {finding['title']}", 0.4, y, 12.5, 0.35,
                     size=12, bold=True, color=ORG_RGB)
            detail = f"{finding['detail']}  |  {finding['impact']}"
            add_text(slide, detail, 0.6, y + 0.38, 12.3, 0.4, size=10, color=GREY_RGB)

        add_footer(slide, pg); pg += 1

    # ── Slide 3 (optional): AI Commentary ────────────────────────────────────
    if sections.get("ai_commentary", False) and ai_narrative:
        slide = add_slide()
        add_text(slide, "Publisher Commentary", 0.4, 0.2, 12.5, 0.55,
                 size=22, bold=True, color=WHT_RGB)
        add_text(slide, "AI-generated narrative — for internal review before sharing",
                 0.4, 0.78, 12.5, 0.3, size=11, color=GREY_RGB)
        # Truncate to fit on one slide (~2000 chars)
        add_text(slide, ai_narrative[:1800], 0.4, 1.25, 12.5, 5.8,
                 size=11, color=WHT_RGB)
        add_footer(slide, pg); pg += 1

    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf


# ── Yield opportunity computation ─────────────────────────────────────────────

def _compute_yield_findings(df_week, df_prior):
    """
    Apply five rules-based checks comparing the current week to the prior week.
    Returns a list of finding dicts sorted by revenue impact (descending).

    Every groupby in this function sums ALL raw count columns before calling
    calc_rates(), so rates are always derived from raw totals — never averaged
    or summed. calc_rates() is defensive and skips any rate whose required
    columns are absent from the DataFrame.
    """
    findings = []

    if df_week.empty:
        return findings

    # ── Per-ad-unit aggregation (Rules 1, 4) ─────────────────────────────────
    # All raw count columns included so calc_rates() can compute every rate.
    _AGG = {
        "publisher":       ("publisher",       "first"),
        "property":        ("property",        "first"),
        "format":          ("format",          "first"),
        "device":          ("device",          "first"),
        "demand_source":   ("demand_source",   "first"),
        "ad_requests":     ("ad_requests",     "sum"),
        "ad_impressions":  ("ad_impressions",  "sum"),
        "revenue_aud":     ("revenue_aud",     "sum"),
        "completed_views": ("completed_views", "sum"),
        "timeout_count":   ("timeout_count",   "sum"),
        "error_count":     ("error_count",     "sum"),
    }
    cur_unit = df_week.groupby("ad_unit").agg(**_AGG).reset_index()
    cur_unit = calc_rates(cur_unit)

    prv_unit = (
        df_prior.groupby("ad_unit")
        .agg(
            ad_requests    =("ad_requests",    "sum"),
            ad_impressions =("ad_impressions", "sum"),
            revenue_aud    =("revenue_aud",    "sum"),
            completed_views=("completed_views","sum"),
            timeout_count  =("timeout_count",  "sum"),
        )
        .reset_index()
    )
    prv_unit = calc_rates(prv_unit)

    # ── Rule 1: Fill rate < 70% on high-request ad units ─────────────────────
    if "fill_rate" in cur_unit.columns and "ad_requests" in cur_unit.columns:
        high_req_thresh = cur_unit["ad_requests"].quantile(0.5)
        low_fill = cur_unit[
            (cur_unit["fill_rate"] < 0.70) &
            (cur_unit["ad_requests"] >= high_req_thresh)
        ]
        for _, row in low_fill.iterrows():
            ecpm_val = row.get("ecpm", 0) or 0
            missed = max(
                row["ad_requests"] * 0.70 / 1_000 * ecpm_val - row["revenue_aud"], 0
            )
            findings.append({
                "title":      (f"Low fill rate — {row['publisher']} / {row['property']} / "
                               f"{row['format']} / {row['device']}"),
                "detail":     (f"Fill rate {row['fill_rate']:.1%} across "
                               f"{row['ad_requests']:,.0f} requests. "
                               f"Review floor price or demand partner mix."),
                "impact":     f"A${missed:,.0f} potential upside vs 70% floor",
                "impact_val": missed,
                "type":       "fill_rate",
            })

    # ── Rule 2: eCPM declined >10% WoW for any format ────────────────────────
    # Sum all raw count cols first — calc_rates() derives eCPM from the totals.
    _fmt_cur = df_week.groupby("format").agg(
        ad_requests    =("ad_requests",    "sum"),
        ad_impressions =("ad_impressions", "sum"),
        revenue_aud    =("revenue_aud",    "sum"),
        completed_views=("completed_views","sum"),
        timeout_count  =("timeout_count",  "sum"),
    ).reset_index()
    _fmt_cur = calc_rates(_fmt_cur)

    _fmt_prv = df_prior.groupby("format").agg(
        ad_requests    =("ad_requests",    "sum"),
        ad_impressions =("ad_impressions", "sum"),
        revenue_aud    =("revenue_aud",    "sum"),
        completed_views=("completed_views","sum"),
        timeout_count  =("timeout_count",  "sum"),
    ).reset_index()
    _fmt_prv = calc_rates(_fmt_prv)

    if "ecpm" in _fmt_cur.columns and "ecpm" in _fmt_prv.columns:
        _fmt_m = _fmt_cur.merge(_fmt_prv, on="format", suffixes=("", "_prv"), how="inner")
        for _, row in _fmt_m.iterrows():
            prv_ecpm = row.get("ecpm_prv", 0) or 0
            if prv_ecpm > 0:
                drop = (row["ecpm"] - prv_ecpm) / prv_ecpm
                if drop < -0.10:
                    impact = abs(drop) * row["revenue_aud"]
                    findings.append({
                        "title":      f"eCPM decline — {row['format']} ({drop:.1%} WoW)",
                        "detail":     (f"eCPM fell from A${prv_ecpm:.2f} to "
                                       f"A${row['ecpm']:.2f}. "
                                       f"Check demand source bid trends and floor settings."),
                        "impact":     f"A${impact:,.0f} revenue impact",
                        "impact_val": impact,
                        "type":       "ecpm_drop",
                    })

    # ── Rule 3: Unfilled impressions rose >15% WoW by property ───────────────
    # Sum all raw count cols first so calc_rates() can compute eCPM for the
    # revenue-impact estimate.
    _prop_cur = df_week.groupby("property").agg(
        ad_requests    =("ad_requests",    "sum"),
        ad_impressions =("ad_impressions", "sum"),
        revenue_aud    =("revenue_aud",    "sum"),
        completed_views=("completed_views","sum"),
        timeout_count  =("timeout_count",  "sum"),
    ).reset_index()
    _prop_cur["unfilled"] = _prop_cur["ad_requests"] - _prop_cur["ad_impressions"]
    _prop_cur = calc_rates(_prop_cur)

    _prop_prv = df_prior.groupby("property").agg(
        ad_requests   =("ad_requests",    "sum"),
        ad_impressions=("ad_impressions", "sum"),
    ).reset_index()
    _prop_prv["unfilled"] = _prop_prv["ad_requests"] - _prop_prv["ad_impressions"]

    _prop_m = _prop_cur.merge(_prop_prv, on="property", suffixes=("", "_prv"), how="inner")
    for _, row in _prop_m.iterrows():
        prv_uf = row.get("unfilled_prv", 0) or 0
        if prv_uf > 0:
            rise = (row["unfilled"] - prv_uf) / prv_uf
            if rise > 0.15:
                ecpm_val = row.get("ecpm", 0) or 0
                missed = (row["unfilled"] - prv_uf) / 1_000 * ecpm_val
                findings.append({
                    "title":      f"Rising unfilled — {row['property']} (+{rise:.1%} WoW)",
                    "detail":     (f"Unfilled impressions rose from {int(prv_uf):,.0f} to "
                                   f"{int(row['unfilled']):,.0f}. "
                                   f"Investigate demand partner health and bid landscape."),
                    "impact":     f"A${max(missed, 0):,.0f} revenue at risk",
                    "impact_val": max(missed, 0),
                    "type":       "unfilled_rise",
                })

    # ── Rule 4: Timeout rate > 5% on any ad unit ─────────────────────────────
    if "timeout_rate" in cur_unit.columns and "ecpm" in cur_unit.columns:
        high_timeout = cur_unit[cur_unit["timeout_rate"] > 0.05]
        for _, row in high_timeout.iterrows():
            ecpm_val = row.get("ecpm", 0) or 0
            lost = row["timeout_count"] / 1_000 * ecpm_val
            findings.append({
                "title":      (f"High timeout rate — {row['ad_unit']} "
                               f"({row['timeout_rate']:.1%})"),
                "detail":     (f"{int(row['timeout_count']):,.0f} timeouts from "
                               f"{int(row['ad_requests']):,.0f} requests. "
                               f"Review ad server latency and creative load time."),
                "impact":     f"A${lost:,.0f} estimated lost revenue",
                "impact_val": lost,
                "type":       "timeout",
            })

    # ── Rule 5: Demand source revenue share fell >15% WoW ────────────────────
    _dem_cur = df_week.groupby("demand_source")["revenue_aud"].sum().reset_index()
    _dem_prv = df_prior.groupby("demand_source")["revenue_aud"].sum().reset_index()
    _dem_cur["share"] = _dem_cur["revenue_aud"] / max(_dem_cur["revenue_aud"].sum(), 1)
    _dem_prv["share"] = _dem_prv["revenue_aud"] / max(_dem_prv["revenue_aud"].sum(), 1)

    _dem_m = _dem_cur.merge(
        _dem_prv, on="demand_source", suffixes=("", "_prv"), how="inner"
    )
    for _, row in _dem_m.iterrows():
        prv_share = row.get("share_prv", 0) or 0
        if prv_share > 0:
            share_drop = (row["share"] - prv_share) / prv_share
            if share_drop < -0.15:
                impact = abs(row.get("revenue_aud_prv", 0) - row["revenue_aud"])
                findings.append({
                    "title":      (f"Demand source revenue share fell — "
                                   f"{row['demand_source']} ({share_drop:.1%} WoW)"),
                    "detail":     (f"Revenue share: {prv_share:.1%} → {row['share']:.1%}. "
                                   f"Review buyer activity and deal health for this source."),
                    "impact":     f"A${impact:,.0f} revenue shift",
                    "impact_val": impact,
                    "type":       "demand_share",
                })

    # Sort by revenue impact descending
    findings.sort(key=lambda x: x.get("impact_val", 0), reverse=True)
    return findings


# ── Shared commentary generator ───────────────────────────────────────────────

def _generate_commentary(api_key, week_label, cur, yield_findings):
    """
    Call Claude to write a publisher-facing weekly supply commentary.

    This is the single source of truth for the prompt — both the page's
    Publisher Commentary section and the PPTX export dialog call this
    function so they always produce identical text.

    Returns the commentary string. Raises on API failure so callers can
    handle the error appropriately.
    """
    import anthropic as _ant

    prompt = (
        f"You are writing a publisher-facing weekly supply "
        f"performance commentary for {week_label}.\n\n"
        f"Key metrics this week:\n"
        f"  Revenue: A${cur.get('revenue_aud', 0):,.0f}\n"
        f"  Fill Rate: {cur.get('fill_rate', 0):.1%}\n"
        f"  eCPM: A${cur.get('ecpm', 0):.2f}\n"
        f"  Completion Rate: {cur.get('completion_rate', 0):.1%}\n\n"
        "Top findings:\n"
        + "\n".join(
            f"- {f['title']}: {f['detail']}"
            for f in yield_findings[:5]
        )
        + "\n\nWrite 3 concise paragraphs: (1) overall performance "
        "summary, (2) key issues and their context, "
        "(3) recommended actions. Use sell-side vocabulary "
        "(eCPM, fill rate, demand sources, inventory). "
        "Be specific and data-driven."
    )

    client = _ant.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text


# ══════════════════════════════════════════════════════════════════════════════
# PAGE RENDER
# ══════════════════════════════════════════════════════════════════════════════

st.title("Weekly Supply Brief")
st.caption("Demo using fabricated data. Not real publisher inventory.")

# ── Load data ─────────────────────────────────────────────────────────────────
df_all = load_supply_data()

if df_all.empty:
    st.error("Supply data could not be loaded. Check data/supply_performance.json.")
    st.stop()

# ── 1. FILTERS ────────────────────────────────────────────────────────────────

# Compute week-ending (Sunday) for each row so the filter shows clean week labels
df_all["_week_end"] = (
    df_all["date"]
    + pd.to_timedelta((6 - df_all["date"].dt.dayofweek) % 7, unit="D")
).dt.date

week_options = sorted(df_all["_week_end"].unique(), reverse=True)
week_labels  = [w.strftime("%d %b %Y") for w in week_options]

# Remove the helper column from df_all (we'll recompute on filtered slice if needed)
df_all = df_all.drop(columns=["_week_end"])

section_header("Filters")

f1, f2, f3, f4, f5, f6 = st.columns(6)

with f1:
    pub_opts = ["All"] + sorted(df_all["publisher"].dropna().unique().tolist())
    sel_pub  = st.selectbox("Publisher",     pub_opts, key="sb_supply_pub")
with f2:
    prop_opts = ["All"] + sorted(df_all["property"].dropna().unique().tolist())
    sel_prop  = st.selectbox("Property",     prop_opts, key="sb_supply_prop")
with f3:
    fmt_opts = ["All"] + sorted(df_all["format"].dropna().unique().tolist())
    sel_fmt  = st.selectbox("Format",        fmt_opts, key="sb_supply_fmt")
with f4:
    dev_opts = ["All"] + sorted(df_all["device"].dropna().unique().tolist())
    sel_dev  = st.selectbox("Device",        dev_opts, key="sb_supply_dev")
with f5:
    dem_opts = ["All"] + sorted(df_all["demand_source"].dropna().unique().tolist())
    sel_dem  = st.selectbox("Demand Source", dem_opts, key="sb_supply_dem")
with f6:
    sel_week_label = st.selectbox("Week ending", week_labels, key="sb_supply_week")

# Resolve selected week boundaries
sel_week_end   = week_options[week_labels.index(sel_week_label)]
sel_week_start = sel_week_end - timedelta(days=6)   # Monday of that week
prior_end      = sel_week_start - timedelta(days=1)  # Sunday before
prior_start    = prior_end - timedelta(days=6)       # Monday of prior week


def apply_dim_filters(df):
    """Apply the non-time dimension filters to a dataframe."""
    if sel_pub  != "All":
        df = df[df["publisher"]     == sel_pub]
    if sel_prop != "All":
        df = df[df["property"]      == sel_prop]
    if sel_fmt  != "All":
        df = df[df["format"]        == sel_fmt]
    if sel_dev  != "All":
        df = df[df["device"]        == sel_dev]
    if sel_dem  != "All":
        df = df[df["demand_source"] == sel_dem]
    return df.copy()


df_filtered = apply_dim_filters(df_all)

# Current week and prior week slices
df_week = df_filtered[
    (df_filtered["date"].dt.date >= sel_week_start) &
    (df_filtered["date"].dt.date <= sel_week_end)
]
df_prior = df_filtered[
    (df_filtered["date"].dt.date >= prior_start) &
    (df_filtered["date"].dt.date <= prior_end)
]

# ── 2. HEADLINE CARDS ─────────────────────────────────────────────────────────
section_header("This Week")

cur = week_totals(df_week)
prv = week_totals(df_prior)

h1, h2, h3, h4, h5 = st.columns(5)
card_specs = [
    (h1, "Revenue",         f"A${cur.get('revenue_aud', 0):,.0f}",     pct_delta(cur.get('revenue_aud', 0),     prv.get('revenue_aud', 0)),     "💰"),
    (h2, "Ad Requests",     f"{cur.get('ad_requests', 0):,.0f}",        pct_delta(cur.get('ad_requests', 0),     prv.get('ad_requests', 0)),     "📡"),
    (h3, "Fill Rate",       f"{cur.get('fill_rate', 0):.1%}",           pct_delta(cur.get('fill_rate', 0),       prv.get('fill_rate', 0)),       "📊"),
    (h4, "eCPM",            f"A${cur.get('ecpm', 0):.2f}",              pct_delta(cur.get('ecpm', 0),            prv.get('ecpm', 0)),            "💵"),
    (h5, "Completion Rate", f"{cur.get('completion_rate', 0):.1%}",     pct_delta(cur.get('completion_rate', 0), prv.get('completion_rate', 0)), "✅"),
]
for col_ui, label, value, delta, icon in card_specs:
    with col_ui:
        st.markdown(
            metric_card(label, value, delta=delta, delta_label="WoW", icon=icon),
            unsafe_allow_html=True,
        )

# ── 3. SUPPLY FUNNEL ─────────────────────────────────────────────────────────
section_header("Supply Funnel")

if cur:
    req_total   = cur["ad_requests"]
    fill_total  = cur["ad_impressions"]
    compl_total = cur["completed_views"]

    fill_pct_initial  = fill_total  / max(req_total, 1)
    compl_pct_initial = compl_total / max(req_total, 1)

    fig_funnel = go.Figure(go.Funnel(
        y=["Ad Requests", "Filled Impressions", "Completed Views"],
        x=[req_total, fill_total, compl_total],
        textposition="inside",
        textinfo="value+percent initial",
        marker=dict(color=[SECONDARY, PRIMARY, SUCCESS]),
        connector=dict(line=dict(color="rgba(255,255,255,0.1)", width=1)),
    ))
    fig_funnel = apply_plotly_style(fig_funnel, height=280)
    fig_funnel.update_layout(margin=dict(l=20, r=20, t=20, b=20))
    fig_funnel.update_traces(
        textfont=dict(family="Poppins, system-ui, sans-serif", size=12)
    )

    st.plotly_chart(fig_funnel, use_container_width=True, config=PLOTLY_CONFIG)

    _fc1, _fc2, _fc3 = st.columns(3)
    unfill_pct = 1 - fill_pct_initial
    drop_compl = 1 - (compl_total / max(fill_total, 1))
    with _fc1:
        st.caption(f"Fill rate: {fill_pct_initial:.1%} of requests filled")
    with _fc2:
        st.caption(f"Unfilled: {unfill_pct:.1%} of requests ({req_total - fill_total:,.0f} impressions)")
    with _fc3:
        st.caption(f"Completion drop-off: {drop_compl:.1%} of filled impressions not completed")
else:
    absent_placeholder("Supply funnel — no data for selected filters", height=280)

# ── 4. TRENDS — 2×2 grid ────────────────────────────────────────────────────
section_header("Trends — Last 12 Weeks")

TREND_HEIGHT = 380

# Build daily aggregates for the full filtered dataset (all 12 weeks)
if not df_filtered.empty:
    _raw_agg_cols = [c for c in
                     ["ad_requests", "ad_impressions", "revenue_aud",
                      "completed_views", "unfilled_impressions",
                      "timeout_count", "error_count"]
                     if c in df_filtered.columns]
    daily = (
        df_filtered.groupby("date")[_raw_agg_cols].sum()
        .reset_index()
        .sort_values("date")
    )

    # Compute unfilled as requests − impressions (reliable over a raw col sum)
    daily["unfilled_impressions"] = daily["ad_requests"] - daily["ad_impressions"]

    # Recalculate rate metrics per day from summed raw counts
    daily["fill_rate"] = (
        daily["ad_impressions"] / daily["ad_requests"].clip(lower=1)
    ).replace([float("inf"), float("-inf")], 0)

    daily["ecpm"] = (
        daily["revenue_aud"] / daily["ad_impressions"].clip(lower=1) * 1_000
    ).replace([float("inf"), float("-inf")], 0)

    # Prior 4-week averages (single horizontal reference value per chart)
    avg_rev    = prior_4w_avg(df_filtered, "revenue_aud",          sel_week_end)
    avg_fill   = prior_4w_avg(df_filtered, "fill_rate",            sel_week_end)
    avg_ecpm   = prior_4w_avg(df_filtered, "ecpm",                 sel_week_end)
    avg_unfill = prior_4w_avg(df_filtered, "unfilled_impressions",  sel_week_end)

    # Render 2×2 grid
    r1c1, r1c2 = st.columns(2)
    r2c1, r2c2 = st.columns(2)

    with r1c1:
        fig = make_trend_chart(daily, "revenue_aud", "Revenue by Day (A$)", avg_rev, TREND_HEIGHT)
        fig.update_traces(
            selector=dict(name="Revenue by Day (A$)"),
            hovertemplate="%{x|%d %b}: A$%{y:,.0f}<extra></extra>",
        )
        if avg_rev is not None:
            fig.update_traces(
                selector=dict(name="Prior 4-wk avg"),
                hovertemplate=f"Prior 4-wk avg: A${avg_rev:,.0f}<extra></extra>",
            )
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    with r1c2:
        fig = make_trend_chart(daily, "fill_rate", "Fill Rate by Day", avg_fill, TREND_HEIGHT)
        fig.update_traces(
            selector=dict(name="Fill Rate by Day"),
            hovertemplate="%{x|%d %b}: %{y:.1%}<extra></extra>",
        )
        fig.update_yaxes(tickformat=".0%")
        if avg_fill is not None:
            fig.update_traces(
                selector=dict(name="Prior 4-wk avg"),
                hovertemplate=f"Prior 4-wk avg: {avg_fill:.1%}<extra></extra>",
            )
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    with r2c1:
        fig = make_trend_chart(daily, "ecpm", "eCPM by Day (A$)", avg_ecpm, TREND_HEIGHT)
        fig.update_traces(
            selector=dict(name="eCPM by Day (A$)"),
            hovertemplate="%{x|%d %b}: A$%{y:.2f}<extra></extra>",
        )
        if avg_ecpm is not None:
            fig.update_traces(
                selector=dict(name="Prior 4-wk avg"),
                hovertemplate=f"Prior 4-wk avg: A${avg_ecpm:.2f}<extra></extra>",
            )
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    with r2c2:
        fig = make_trend_chart(daily, "unfilled_impressions",
                               "Unfilled Impressions by Day", avg_unfill, TREND_HEIGHT)
        fig.update_traces(
            selector=dict(name="Unfilled Impressions by Day"),
            hovertemplate="%{x|%d %b}: %{y:,.0f}<extra></extra>",
        )
        if avg_unfill is not None:
            fig.update_traces(
                selector=dict(name="Prior 4-wk avg"),
                hovertemplate=f"Prior 4-wk avg: {avg_unfill:,.0f}<extra></extra>",
            )
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

else:
    absent_placeholder("Trend data — no data for selected filters", height=TREND_HEIGHT)

# ── 5. BREAKDOWN DONUTS ───────────────────────────────────────────────────────
section_header("Revenue Breakdown — This Week")

DONUT_HEIGHT = 300
_d1, _d2, _d3, _d4 = st.columns(4)

for col_ui, grp_col, donut_title in [
    (_d1, "format",         "By Format"),
    (_d2, "device",         "By Device"),
    (_d3, "demand_source",  "By Demand Source"),
    (_d4, "buyer",          "By Buyer"),
]:
    with col_ui:
        fig = build_donut(df_week, grp_col, donut_title, height=DONUT_HEIGHT)
        if fig:
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
        else:
            absent_placeholder(donut_title, height=DONUT_HEIGHT)

# ── 6. YIELD OPPORTUNITIES ────────────────────────────────────────────────────
section_header("Yield Opportunities")

# Rules applied to the selected week vs the prior week.
# Findings are sorted by revenue impact (descending).
# The entire block is wrapped in try/except so a computation failure shows a
# contained error message rather than blanking the rest of the page.

yield_findings = []
try:
    yield_findings = _compute_yield_findings(df_week, df_prior)
except Exception as _yield_err:
    st.error(f"Yield opportunity analysis encountered an error: {_yield_err}")

# Render findings
_type_border = {
    "fill_rate":    DANGER,
    "ecpm_drop":    WARNING,
    "unfilled_rise":WARNING,
    "timeout":      DANGER,
    "demand_share": TEXT_SEC,
}

if yield_findings:
    for finding in yield_findings[:8]:
        border = _type_border.get(finding["type"], SECONDARY)
        st.markdown(
            f'<div style="background:{WHITE};border-left:4px solid {border};'
            f'border-radius:0 12px 12px 0;padding:14px 18px;margin-bottom:10px;'
            f'box-shadow:0 1px 6px rgba(0,0,0,0.06);">'
            f'<div style="font-weight:600;font-size:14px;color:{SECONDARY};'
            f'font-family:Poppins,system-ui,sans-serif;margin-bottom:4px;">'
            f'{finding["title"]}</div>'
            f'<div style="font-size:13px;color:#374151;'
            f'font-family:Poppins,system-ui,sans-serif;margin-bottom:6px;">'
            f'{finding["detail"]}</div>'
            f'<div style="font-size:12px;font-weight:600;color:{PRIMARY};'
            f'font-family:Poppins,system-ui,sans-serif;">{finding["impact"]}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
else:
    st.info("No yield issues detected for the selected filters and week. "
            "Try viewing week 10 or 11 to see the deliberate anomalies.")

# ── 6b. PUBLISHER COMMENTARY ─────────────────────────────────────────────────
section_header("Publisher Commentary")

# Fallback so the dialog (which closes over this variable) always finds it
# even if the try block below raises before reaching the assignment.
_current_ctx = f"week ending {sel_week_label}"

try:
    # Build a short label describing the active filter state.
    # Shown alongside the commentary so it is obvious if filters have changed
    # since the text was generated.
    _ctx_parts = [p for p in [
        sel_pub  if sel_pub  != "All" else None,
        sel_prop if sel_prop != "All" else None,
        sel_fmt  if sel_fmt  != "All" else None,
        sel_dev  if sel_dev  != "All" else None,
        sel_dem  if sel_dem  != "All" else None,
        f"week ending {sel_week_label}",
    ] if p]
    _current_ctx = " · ".join(_ctx_parts)

    _existing_text = st.session_state.get("supply_commentary", "")
    _existing_ctx  = st.session_state.get("supply_commentary_context", "")

    with st.container():
        st.caption("AI-written narrative for the weekly publisher brief.")

        if _existing_text:
            # Show which filter state the text was generated under.
            # A mismatch with _current_ctx signals the user that a refresh
            # may be needed — but we do not auto-regenerate.
            if _existing_ctx:
                _ctx_color = TEXT_SEC if _existing_ctx == _current_ctx else "#F59E0B"
                st.markdown(
                    f'<p style="font-family:Poppins,system-ui,sans-serif;'
                    f'font-size:11px;color:{_ctx_color};margin:0 0 12px 0;">'
                    f'Generated for: {_html.escape(_existing_ctx)}</p>',
                    unsafe_allow_html=True,
                )

            # Render as readable prose inside a styled card.
            # Dollar signs are HTML-escaped so currency values (A$50,000)
            # never trigger Streamlit's LaTeX math renderer.
            _safe = (
                _html.escape(_existing_text)
                .replace("\n\n", "</p><p style='margin:10px 0;'>")
                .replace("\n", "<br>")
            )
            st.markdown(
                f'<div style="background:{WHITE};border:0.5px solid rgba(27,42,74,0.12);'
                f'border-radius:16px;padding:22px 26px;">'
                f'<div style="font-family:Poppins,system-ui,sans-serif;font-size:14px;'
                f'color:#374151;line-height:1.75;">'
                f'<p style="margin:0 0 10px 0;">{_safe}</p>'
                f'</div></div>',
                unsafe_allow_html=True,
            )

            # Regenerate button — clears session state and reruns so the
            # placeholder + generate button appear again.
            st.markdown('<div style="margin-top:10px;"></div>', unsafe_allow_html=True)
            if st.button("🔄 Regenerate", key="commentary_regen_btn"):
                st.session_state.pop("supply_commentary", None)
                st.session_state.pop("supply_commentary_context", None)
                st.rerun()

        else:
            # Placeholder card shown before first generation
            st.markdown(
                f'<div style="background:{WHITE};border:0.5px solid rgba(27,42,74,0.12);'
                f'border-radius:16px;padding:22px 26px;">'
                f'<p style="font-family:Poppins,system-ui,sans-serif;font-size:14px;'
                f'color:{TEXT_SEC};font-style:italic;margin:0;">'
                f'Click "Generate commentary" to produce an AI-written narrative '
                f'based on the current week\'s metrics and yield findings.</p>'
                f'</div>',
                unsafe_allow_html=True,
            )

            st.markdown('<div style="margin-top:10px;"></div>', unsafe_allow_html=True)

            if _ai_avail:
                _gcol1, _gcol2 = st.columns([2, 5])
                with _gcol1:
                    if st.button("Generate commentary", key="commentary_gen_btn",
                                 type="primary"):
                        with st.spinner("Writing commentary…"):
                            _text = _generate_commentary(
                                _brief_api_key, sel_week_label, cur, yield_findings
                            )
                            st.session_state["supply_commentary"] = _text
                            st.session_state["supply_commentary_context"] = _current_ctx
                        st.rerun()
                with _gcol2:
                    st.caption("Uses AI credits.")
            else:
                st.caption("⚠ Requires ANTHROPIC_API_KEY in Streamlit secrets to generate commentary.")

except Exception as _comm_err:
    st.error(f"Publisher Commentary section error: {_comm_err}")

# ── 7. EXPLORE DATA ───────────────────────────────────────────────────────────
section_header("Explore Data")

# Multiselect tag styling for supply pivot
st.markdown("""
<style>
[data-testid*="sup_pivot_dims"] span[data-baseweb="tag"] {
    background-color: #1B2A4A !important; color: #ffffff !important;
}
[data-testid*="sup_pivot_dims"] span[data-baseweb="tag"] span {
    color: #ffffff !important;
}
[data-testid*="sup_pivot_mets"] span[data-baseweb="tag"] {
    background-color: #F5A623 !important; color: #1B2A4A !important;
}
[data-testid*="sup_pivot_mets"] span[data-baseweb="tag"] span {
    color: #1B2A4A !important;
}
</style>
""", unsafe_allow_html=True)

# Dimension options (in display order)
_S_DIM_OPTIONS = [
    ("publisher",    "Publisher"),
    ("property",     "Property"),
    ("ad_unit",      "Ad Unit"),
    ("format",       "Format"),
    ("device",       "Device"),
    ("demand_source","Demand Source"),
    ("buyer",        "Buyer"),
    ("deal_id",      "Deal ID"),
    ("date",         "Date"),
]
_s_dim_avail  = [(col, lbl) for col, lbl in _S_DIM_OPTIONS
                 if col in df_filtered.columns and df_filtered[col].notna().any()]
_s_dim_labels = [lbl for _, lbl in _s_dim_avail]
_s_dim_map    = {lbl: col for col, lbl in _s_dim_avail}

# Metric options — additive raw cols + calculated rate cols
_S_ADDITIVE = {
    "ad_requests", "ad_impressions", "unfilled_impressions",
    "revenue_aud", "completed_views", "timeout_count", "error_count",
}
_S_RATES = {"fill_rate", "ecpm", "completion_rate", "timeout_rate"}

_S_METRIC_OPTIONS = [
    ("ad_requests",           "Ad Requests"),
    ("ad_impressions",        "Filled Impressions"),
    ("unfilled_impressions",  "Unfilled Impressions"),
    ("revenue_aud",           "Revenue (A$)"),
    ("completed_views",       "Completed Views"),
    ("timeout_count",         "Timeouts"),
    ("error_count",           "Errors"),
    ("fill_rate",             "Fill Rate"),
    ("ecpm",                  "eCPM (A$)"),
    ("completion_rate",       "Completion Rate"),
    ("timeout_rate",          "Timeout Rate"),
]
_s_metric_avail  = [(col, lbl) for col, lbl in _S_METRIC_OPTIONS
                    if col in _S_ADDITIVE or col in _S_RATES]
_s_metric_labels = [lbl for _, lbl in _s_metric_avail]
_s_metric_map    = {lbl: col for col, lbl in _s_metric_avail}

# Default selections
_s_dim_defaults    = [l for l in ["Publisher", "Format"] if l in _s_dim_labels]
_s_metric_defaults = [l for l in ["Ad Requests", "Filled Impressions",
                                   "Revenue (A$)", "Fill Rate", "eCPM (A$)"]
                      if l in _s_metric_labels]

_PCL = ("font-size:11px;font-weight:600;text-transform:uppercase;"
        "letter-spacing:0.04em;color:#1B2A4A;margin:0 0 4px 0;"
        "font-family:'Poppins',system-ui,sans-serif;display:block;")

_ep1, _ep2 = st.columns(2)
with _ep1:
    st.markdown(f'<span style="{_PCL}">Dimensions</span>', unsafe_allow_html=True)
    sel_s_dims = st.multiselect(
        "sup_pivot_dims", _s_dim_labels,
        default=_s_dim_defaults,
        key="sup_pivot_dims",
        label_visibility="collapsed",
    )
with _ep2:
    st.markdown(f'<span style="{_PCL}">Metrics</span>', unsafe_allow_html=True)
    sel_s_mets = st.multiselect(
        "sup_pivot_mets", _s_metric_labels,
        default=_s_metric_defaults,
        key="sup_pivot_mets",
        label_visibility="collapsed",
    )

if not sel_s_mets:
    st.info("Select at least one metric to display the table.")
else:
    _s_dim_cols = [_s_dim_map[l] for l in sel_s_dims]
    _s_met_cols = [_s_metric_map[l] for l in sel_s_mets]

    # Determine which raw additive cols are needed to compute rate metrics
    _s_raw_need = set()
    for _mc in _s_met_cols:
        if _mc in _S_ADDITIVE:
            _s_raw_need.add(_mc)
        elif _mc == "fill_rate":
            _s_raw_need.update(["ad_impressions", "ad_requests"])
        elif _mc == "ecpm":
            _s_raw_need.update(["revenue_aud", "ad_impressions"])
        elif _mc == "completion_rate":
            _s_raw_need.update(["completed_views", "ad_impressions"])
        elif _mc == "timeout_rate":
            _s_raw_need.update(["timeout_count", "ad_requests"])
    _s_pull = [c for c in _s_raw_need if c in df_filtered.columns]

    # Aggregate
    if _s_dim_cols:
        _s_agg = {c: (c, "sum") for c in _s_pull}
        _s_grouped = (
            df_filtered.groupby(_s_dim_cols, dropna=False)
            .agg(**_s_agg)
            .reset_index()
        )
    else:
        _s_grouped = pd.DataFrame(
            [{c: df_filtered[c].sum() for c in _s_pull if c in df_filtered.columns}]
        )

    # Cap to prevent browser freeze
    _s_capped = len(_s_grouped) > 5_000
    if _s_capped:
        _s_grouped = _s_grouped.head(5_000)

    # Recalculate rate metrics from summed raw counts (never average or sum rates)
    _clip = {"lower": 1}
    if "fill_rate" in _s_met_cols and {"ad_impressions","ad_requests"}.issubset(_s_grouped.columns):
        _s_grouped["fill_rate"] = (
            _s_grouped["ad_impressions"] / _s_grouped["ad_requests"].clip(**_clip)
        ).replace([float("inf"), float("-inf")], 0)

    if "ecpm" in _s_met_cols and {"revenue_aud","ad_impressions"}.issubset(_s_grouped.columns):
        _s_grouped["ecpm"] = (
            _s_grouped["revenue_aud"] / _s_grouped["ad_impressions"].clip(**_clip) * 1_000
        ).replace([float("inf"), float("-inf")], 0)

    if "completion_rate" in _s_met_cols and {"completed_views","ad_impressions"}.issubset(_s_grouped.columns):
        _s_grouped["completion_rate"] = (
            _s_grouped["completed_views"] / _s_grouped["ad_impressions"].clip(**_clip)
        ).replace([float("inf"), float("-inf")], 0)

    if "timeout_rate" in _s_met_cols and {"timeout_count","ad_requests"}.issubset(_s_grouped.columns):
        _s_grouped["timeout_rate"] = (
            _s_grouped["timeout_count"] / _s_grouped["ad_requests"].clip(**_clip)
        ).replace([float("inf"), float("-inf")], 0)

    # ── Table-level filters ──────────────────────────────────────────────────
    st.markdown(
        '<p style="font-family:\'Poppins\',sans-serif;font-size:11px;'
        'color:#6B7280;font-style:italic;margin:12px 0 4px 0;">'
        'Table filters — independent of the page-level filters above</p>',
        unsafe_allow_html=True,
    )
    _tf1, _tf2, _tf3, _tf4 = st.columns([2.5, 1, 1.3, 0.9])
    with _tf1:
        _s_search = st.text_input(
            "Search", value="", placeholder="Search dimensions…",
            key="s_pivot_search", label_visibility="collapsed",
        )
    with _tf2:
        _s_topn = st.selectbox(
            "Top N", ["10", "25", "50", "100", "All"],
            key="s_pivot_topn", label_visibility="collapsed",
        )
    with _tf3:
        _s_sort_by = (
            st.selectbox("Sort by", sel_s_mets,
                         key="s_pivot_sort", label_visibility="collapsed")
            if sel_s_mets else None
        )
    with _tf4:
        _s_asc = st.selectbox(
            "Order", ["Descending", "Ascending"],
            key="s_pivot_order", label_visibility="collapsed",
        )

    # Build display DataFrame with only the selected columns
    _s_disp_cols = _s_dim_cols + [c for c in _s_met_cols if c in _s_grouped.columns]
    _s_display   = _s_grouped[_s_disp_cols].copy()

    # Apply free-text search across dimension columns
    if _s_search and _s_dim_cols:
        _mask = pd.Series(False, index=_s_display.index)
        for _dc in _s_dim_cols:
            if _dc in _s_display.columns:
                _mask |= (
                    _s_display[_dc].astype(str)
                    .str.contains(_s_search, case=False, na=False)
                )
        _s_display = _s_display[_mask].copy()

    # Sort by selected metric
    if _s_sort_by and _s_sort_by in _s_metric_map:
        _sc = _s_metric_map[_s_sort_by]
        if _sc in _s_display.columns:
            _s_display = _s_display.sort_values(
                _sc, ascending=(_s_asc == "Ascending")
            )

    # Limit rows
    if _s_topn != "All":
        _s_display = _s_display.head(int(_s_topn))

    _s_row_count = len(_s_display)

    # ── Totals row ───────────────────────────────────────────────────────────
    if _s_dim_cols:
        _tot = {dc: "TOTAL" for dc in _s_dim_cols}
        for mc in _s_met_cols:
            if mc not in _s_display.columns:
                continue
            if mc in _S_RATES:
                # Recalculate rate from the full grouped dataset for totals row
                if mc == "fill_rate" and {"ad_impressions","ad_requests"}.issubset(_s_grouped.columns):
                    _tot[mc] = _s_grouped["ad_impressions"].sum() / max(_s_grouped["ad_requests"].sum(), 1)
                elif mc == "ecpm" and {"revenue_aud","ad_impressions"}.issubset(_s_grouped.columns):
                    _tot[mc] = _s_grouped["revenue_aud"].sum() / max(_s_grouped["ad_impressions"].sum(), 1) * 1_000
                elif mc == "completion_rate" and {"completed_views","ad_impressions"}.issubset(_s_grouped.columns):
                    _tot[mc] = _s_grouped["completed_views"].sum() / max(_s_grouped["ad_impressions"].sum(), 1)
                elif mc == "timeout_rate" and {"timeout_count","ad_requests"}.issubset(_s_grouped.columns):
                    _tot[mc] = _s_grouped["timeout_count"].sum() / max(_s_grouped["ad_requests"].sum(), 1)
                else:
                    _tot[mc] = None
            else:
                _tot[mc] = _s_display[mc].sum() if mc in _s_display.columns else None

        _s_with_totals = pd.concat(
            [_s_display, pd.DataFrame([_tot])], ignore_index=True
        )
    else:
        _s_with_totals = _s_display.copy()

    # Rename columns to friendly display labels
    _s_col_rename = {
        **{col: lbl for lbl, col in _s_dim_map.items()},
        **{col: lbl for lbl, col in _s_metric_map.items()},
    }
    _s_with_totals = _s_with_totals.rename(columns=_s_col_rename)
    _s_export      = _s_display.rename(columns=_s_col_rename)

    # Format spec for metric columns
    _s_fmt = {}
    for lbl in sel_s_mets:
        mc = _s_metric_map.get(lbl, "")
        if lbl not in _s_with_totals.columns:
            continue
        if mc in ("revenue_aud", "ecpm"):
            _s_fmt[lbl] = "A${:,.2f}"
        elif mc in ("fill_rate", "completion_rate", "timeout_rate"):
            _s_fmt[lbl] = "{:.2%}"
        else:
            _s_fmt[lbl] = "{:,.0f}"

    # Bold + grey-bg for the totals row
    def _style_s_totals(df):
        styles = pd.DataFrame("", index=df.index, columns=df.columns)
        if _s_dim_cols:
            styles.iloc[-1] = "font-weight:700;background-color:#F3F4F6;"
        return styles

    # Wide column config for dimension columns
    _s_col_cfg = {
        lbl: st.column_config.TextColumn(label=lbl, width="large")
        for lbl in sel_s_dims
    }

    # Render the table
    try:
        st.dataframe(
            _s_with_totals.style
                .format(_s_fmt, na_rep="—")
                .apply(_style_s_totals, axis=None),
            use_container_width=True,
            height=400,
            column_config=_s_col_cfg,
        )
    except Exception as _te:
        st.dataframe(
            _s_with_totals,
            use_container_width=True,
            height=400,
            column_config=_s_col_cfg,
        )
        st.caption(f"⚠️ Formatting could not be applied: {_te}")

    _rc1, _rc2 = st.columns([3, 1])
    with _rc1:
        st.caption(f"{_s_row_count:,} row{'s' if _s_row_count != 1 else ''}")
    with _rc2:
        try:
            st.download_button(
                "⬇ Download as CSV",
                data=_s_export.to_csv(index=False).encode("utf-8"),
                file_name="supply_explore_data.csv",
                mime="text/csv",
                key="s_pivot_download",
            )
        except Exception:
            pass

    if _s_capped:
        st.warning(
            "Result capped at 5,000 rows. Use page-level filters to narrow the data."
        )

# ── 8. GENERATE BRIEF ────────────────────────────────────────────────────────
section_header("Generate Weekly Brief")

# Check for Anthropic API key (needed for optional AI commentary)
try:
    _brief_api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
except Exception:
    _brief_api_key = ""
if not _brief_api_key:
    _brief_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
_ai_avail = bool(_brief_api_key)


@st.dialog("Generate Weekly Brief")
def _show_brief_dialog():
    """Section-picker dialog for the PowerPoint export."""
    st.caption("Select sections to include in the PowerPoint export.")

    # Restore previous section defaults from session state
    _b_defs = st.session_state.get("_brief_section_defs", {
        "headline_summary":   True,
        "yield_opportunities":True,
        "ai_commentary":      False,   # unchecked by default — uses AI credits
    })

    _bc = st.columns(2)
    with _bc[0]:
        if st.button("Select all", key="brief_sel_all"):
            st.session_state["_brief_section_defs"] = {k: True for k in _b_defs}
            st.rerun()
    with _bc[1]:
        if st.button("Deselect all", key="brief_desel_all"):
            st.session_state["_brief_section_defs"] = {k: False for k in _b_defs}
            st.rerun()

    st.markdown("")

    s_headline = st.checkbox(
        "Headline Summary",
        value=_b_defs.get("headline_summary", True),
        key="brief_cb_headline",
    )
    s_yield = st.checkbox(
        "Yield Opportunities",
        value=_b_defs.get("yield_opportunities", True),
        key="brief_cb_yield",
        disabled=not yield_findings,
        help=None if yield_findings else "No findings for the current filters / week.",
    )
    s_ai = st.checkbox(
        "AI Commentary  *(Uses AI credits)*",
        value=_b_defs.get("ai_commentary", False),
        key="brief_cb_ai",
        disabled=not _ai_avail,
        help=(
            "Writes a short publisher-facing narrative using Claude AI."
            if _ai_avail
            else "Requires ANTHROPIC_API_KEY in Streamlit secrets."
        ),
    )

    if not _ai_avail:
        st.caption("⚠ AI Commentary requires ANTHROPIC_API_KEY in Streamlit secrets.")

    st.markdown("")

    _act = st.columns(2)
    with _act[0]:
        if st.button("Generate PowerPoint", type="primary", key="brief_gen_btn"):
            # Persist section choices for next dialog open
            st.session_state["_brief_section_defs"] = {
                "headline_summary":   s_headline,
                "yield_opportunities":s_yield,
                "ai_commentary":      s_ai,
            }
            sections = st.session_state["_brief_section_defs"]

            if not any(sections.values()):
                st.warning("Select at least one section.")
                return

            # Optional AI commentary — reuse page-section text if already
            # generated; only calls the API when nothing is cached.
            ai_narrative = ""
            if s_ai and _ai_avail:
                cached = st.session_state.get("supply_commentary", "")
                if cached:
                    # Reuse existing text — no additional API call needed
                    ai_narrative = cached
                else:
                    with st.spinner("Generating AI commentary…"):
                        try:
                            ai_narrative = _generate_commentary(
                                _brief_api_key, sel_week_label, cur, yield_findings
                            )
                            # Store so the page section can display the same text
                            st.session_state["supply_commentary"] = ai_narrative
                            st.session_state["supply_commentary_context"] = _current_ctx
                        except Exception as _ae:
                            st.warning(f"AI commentary could not be generated: {_ae}")

            # Build the PPTX
            with st.spinner("Building PowerPoint…"):
                try:
                    pptx_buf = build_supply_pptx(
                        df_week, yield_findings, sections,
                        sel_week_label, cur, ai_narrative,
                    )
                    st.session_state["supply_pptx"] = pptx_buf
                except Exception as _pe:
                    st.error(f"Export failed: {_pe}")
                    return
            st.rerun()

    with _act[1]:
        if st.button("Cancel", key="brief_cancel_btn"):
            st.rerun()


# Centre the trigger button
_, _gb_col, _ = st.columns([2, 2, 2])
with _gb_col:
    if st.button("📊 Generate Brief", type="primary", key="open_brief_dialog_btn"):
        _show_brief_dialog()

# Show download once the brief has been built
if st.session_state.get("supply_pptx"):
    st.success("✅ Brief ready — click below to download.")
    st.download_button(
        label="📥 Download Brief (.pptx)",
        data=st.session_state["supply_pptx"],
        file_name=f"{date.today():%Y-%m-%d}_weekly_supply_brief.pptx",
        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        key="supply_pptx_download",
    )

print("Supply Brief page loaded successfully.")
