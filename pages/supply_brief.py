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
    get_anthropic_api_key,
)
from utils.prompts import supply_commentary_prompt

# Publisher → properties mapping — used by data generation, commentary section,
# and PPTX export. Adding a publisher here automatically includes it everywhere.
PUBLISHER_PROPERTIES = {
    "Paramount":              ["Paramount+", "Pluto TV", "10 play"],
    "Warner Bros. Discovery": ["HBO Max", "Discovery+", "CNN International"],
    "Vevo":                   ["Vevo CTV", "Vevo FAST", "Vevo Mobile"],
}

# STYLE LOCK: Pacebird design system — #F5A623 orange, #1B2A4A navy, Poppins.
# Shared CSS applied globally by app.py. Do not override.

# ── File path for cached supply data ─────────────────────────────────────────
_APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(_APP_ROOT, "data", "supply_performance.json")

# ── Data generation ───────────────────────────────────────────────────────────

def _generate_supply_data():
    """
    Generate 12 weeks of daily supply-side performance data.
    Produces 1,512 rows (18 combos × 84 days).
    Uses a fixed seed (42) for reproducible results.

    Publishers and properties:
      Paramount              — Paramount+, Pluto TV, 10 play
      Warner Bros. Discovery — HBO Max, Discovery+, CNN International
      Vevo                   — Vevo CTV, Vevo FAST, Vevo Mobile
                               (Vevo skews heavily to Connected TV and music-video inventory)

    Two deliberate anomalies (in different accounts):
      A1 — Week 10 (week_num=9): Warner Bros. Discovery / Discovery+ / Pre-roll / CTV (idx=8)
           fill rate crashes from ~88% to ~52% (demand partner withdrawal)
      A2 — Week 11 (week_num=10): Vevo / Vevo CTV / Pre-roll / CTV (idx=12)
           eCPM spikes from ~A$48 to ~A$62 (floor price increase)
      Weekend — Vevo FAST CTV Pre-roll (idx=14): eCPM +35% and fill +5% on Sat/Sun
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
        # ── Paramount / Paramount+ (CTV-heavy premium) ────────────────────────────
        # idx=0
        ("Paramount","Paramount+",  "pplus_PreRoll_CTV",   "Pre-roll",          "Connected TV","Programmatic Guaranteed","DV360",          "PG-PAR-001", 180_000, 0.93, 46.0, 0.95),
        # idx=1
        ("Paramount","Paramount+",  "pplus_MidRoll_CTV",   "Mid-roll",          "Connected TV","Preferred Deal",         "The Trade Desk", "PD-PAR-001", 130_000, 0.89, 42.0, 0.93),
        # ── Paramount / Pluto TV ──────────────────────────────────────────────────
        # idx=2
        ("Paramount","Pluto TV",    "pluto_PreRoll_CTV",   "Pre-roll",          "Connected TV","Open Auction",           "Amazon DSP",     "",           210_000, 0.78, 28.0, 0.88),
        # idx=3
        ("Paramount","Pluto TV",    "pluto_PreRoll_MOB",   "Pre-roll",          "Mobile",      "Open Auction",           "Yahoo DSP",      "",           350_000, 0.65, 12.0, 0.68),
        # ── Paramount / 10 play ───────────────────────────────────────────────────
        # idx=4
        ("Paramount","10 play",     "10play_PreRoll_DSK",  "Pre-roll",          "Desktop",     "Open Auction",           "Yahoo DSP",      "",           420_000, 0.61, 10.5, 0.64),
        # idx=5
        ("Paramount","10 play",     "10play_PreRoll_MOB",  "Pre-roll",          "Mobile",      "Open Auction",           "The Trade Desk", "",           280_000, 0.72, 11.5, 0.70),
        # ── Warner Bros. Discovery / HBO Max (premium CTV) ────────────────────────
        # idx=6
        ("Warner Bros. Discovery","HBO Max",          "hbomax_PreRoll_CTV",  "Pre-roll",  "Connected TV","Programmatic Guaranteed","DV360",          "PG-WBD-001", 160_000, 0.92, 44.0, 0.94),
        # idx=7
        ("Warner Bros. Discovery","HBO Max",          "hbomax_MidRoll_CTV",  "Mid-roll",  "Connected TV","Preferred Deal",         "The Trade Desk", "PD-WBD-001", 110_000, 0.87, 40.0, 0.91),
        # ── Warner Bros. Discovery / Discovery+ ───────────────────────────────────
        # idx=8  A1: Week 10 fill-rate crash
        ("Warner Bros. Discovery","Discovery+",       "disc_PreRoll_CTV",    "Pre-roll",  "Connected TV","Open Auction",           "Amazon DSP",     "",           190_000, 0.88, 35.0, 0.90),
        # idx=9
        ("Warner Bros. Discovery","Discovery+",       "disc_MidRoll_MOB",    "Mid-roll",  "Mobile",      "Open Auction",           "The Trade Desk", "",           300_000, 0.76, 18.0, 0.73),
        # ── Warner Bros. Discovery / CNN International ────────────────────────────
        # idx=10
        ("Warner Bros. Discovery","CNN International","cnn_PreRoll_DSK",     "Pre-roll",  "Desktop",     "Open Auction",           "Yahoo DSP",      "",           520_000, 0.58,  9.5, 0.62),
        # idx=11
        ("Warner Bros. Discovery","CNN International","cnn_Display_DSK",     "Display Companion","Desktop","Direct IO",            "Direct",         "DIO-WBD-001",180_000, 0.70,  6.0, 0.00),
        # ── Vevo / Vevo CTV (music-video, heavily CTV) ────────────────────────────
        # idx=12  A2: Week 11 eCPM spike
        ("Vevo","Vevo CTV",  "vevo_ctv_PreRoll_CTV",  "Pre-roll", "Connected TV","Programmatic Guaranteed","DV360",          "PG-VEV-001", 250_000, 0.91, 48.0, 0.96),
        # idx=13
        ("Vevo","Vevo CTV",  "vevo_ctv_MidRoll_CTV",  "Mid-roll", "Connected TV","Preferred Deal",         "The Trade Desk", "PD-VEV-001", 200_000, 0.87, 44.0, 0.94),
        # ── Vevo / Vevo FAST (weekend CTV spike) ──────────────────────────────────
        # idx=14  weekend eCPM/fill spike
        ("Vevo","Vevo FAST", "vevo_fast_PreRoll_CTV", "Pre-roll", "Connected TV","Open Auction",           "Amazon DSP",     "",           280_000, 0.82, 32.0, 0.92),
        # idx=15
        ("Vevo","Vevo FAST", "vevo_fast_MidRoll_CTV", "Mid-roll", "Connected TV","Open Auction",           "The Trade Desk", "",           220_000, 0.79, 30.0, 0.90),
        # ── Vevo / Vevo Mobile ────────────────────────────────────────────────────
        # idx=16
        ("Vevo","Vevo Mobile","vevo_mob_PreRoll_MOB",  "Pre-roll", "Mobile",      "Open Auction",           "Yahoo DSP",      "",           320_000, 0.68, 14.0, 0.71),
        # idx=17
        ("Vevo","Vevo Mobile","vevo_mob_MidRoll_MOB",  "Mid-roll", "Mobile",      "Open Auction",           "The Trade Desk", "",           260_000, 0.65, 13.0, 0.68),
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

            # ── Anomaly A1: Week 10 (week_num=9), WBD Discovery+ PreRoll CTV (idx=8)
            # Fill rate crashes from ~88% to ~52% — demand partner withdrawal
            if combo_idx == 8 and week_num == 9:
                fill_rate = 0.52 + random.uniform(-0.04, 0.04)

            # ── Anomaly A2: Week 11 (week_num=10), Vevo CTV PreRoll CTV (idx=12)
            # eCPM spikes ~A$48 → ~A$62 — floor price increase
            if combo_idx == 12 and week_num == 10:
                ecpm = 62.0 + random.uniform(-1.5, 2.5)

            # ── Vevo FAST weekend spike (idx=14): eCPM +35%, fill +5% on Sat/Sun
            if combo_idx == 14 and d.weekday() in (5, 6):
                ecpm      = ecpm * 1.35
                fill_rate = min(0.99, fill_rate * 1.05)

            fill_rate = max(0.10, min(0.99, fill_rate))

            ad_impressions       = int(ad_requests * fill_rate)
            unfilled_impressions = ad_requests - ad_impressions
            revenue_aud          = round(ad_impressions / 1_000.0 * ecpm, 2)

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
            "All performance figures are fabricated and do not represent "
            "real client data. For demonstration purposes only. "
            "Not for distribution."
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

def build_supply_pptx(df_week, yield_findings, sections, sel_week_label, cur, ai_narratives=None):
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

    # ── Slide 3+ (optional): AI Commentary — one slide per publisher ──────────
    if sections.get("ai_commentary", False) and ai_narratives:
        for pub_name, narrative in ai_narratives.items():
            if not narrative:
                continue
            slide = add_slide()
            add_text(slide, f"Publisher Commentary — {pub_name}", 0.4, 0.2, 12.5, 0.55,
                     size=20, bold=True, color=WHT_RGB)
            add_text(slide, "AI-generated narrative — for internal review before sharing",
                     0.4, 0.78, 12.5, 0.3, size=11, color=GREY_RGB)
            add_text(slide, narrative[:1800], 0.4, 1.25, 12.5, 5.8,
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

def _generate_commentary(api_key, publisher, properties, week_label, cur, yield_findings):
    """
    Call Claude to write a publisher-facing weekly supply commentary for
    a single named publisher.

    Both the page's Publisher Commentary section and the PPTX export
    dialog call this function.

    Returns the commentary string. Raises on API failure.
    """
    import anthropic as _ant

    prompt = supply_commentary_prompt(publisher, properties, week_label, cur, yield_findings)

    client = _ant.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text


# ══════════════════════════════════════════════════════════════════════════════
# UPLOAD HELPERS
# ══════════════════════════════════════════════════════════════════════════════

# Column mapping is saved here (local only — not committed to git).
_MAPPING_FILE = os.path.join(_APP_ROOT, "data", ".supply_column_mapping.json")

# Internal field names that the page understands.
_INTERNAL_FIELDS = [
    "date", "publisher", "property", "ad_unit", "format", "device",
    "demand_source", "buyer", "ad_requests", "ad_impressions",
    "unfilled_impressions", "revenue_aud", "completed_views",
    "timeout_count", "error_count",
]

# Rate fields — never imported from uploaded files; always recalculated from counts.
_RATE_FIELDS = {"fill_rate", "ecpm", "completion_rate", "timeout_rate"}


def _load_saved_mapping():
    """Load previously saved column mapping from disk. Returns {} if none found."""
    try:
        with open(_MAPPING_FILE, "r", encoding="utf-8") as _mf:
            return json.load(_mf)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_mapping(mapping: dict):
    """Persist column mapping to disk so the next upload maps automatically."""
    try:
        os.makedirs(os.path.dirname(_MAPPING_FILE), exist_ok=True)
        with open(_MAPPING_FILE, "w", encoding="utf-8") as _mf:
            json.dump(mapping, _mf, indent=2)
    except Exception:
        pass  # Non-fatal — mapping simply won't persist


def _apply_mapping(df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    """
    Rename columns per mapping (skip entries marked '(Skip)'), then add
    placeholder columns for any internal field that was not mapped.
    Rate metrics are intentionally excluded — calc_rates() derives them
    from summed raw counts.
    """
    rename = {src: tgt for src, tgt in mapping.items()
              if tgt and tgt != "(Skip)" and src in df.columns}
    df = df.rename(columns=rename)

    # Drop any columns that are rate metrics — never import averaged rates.
    for _rf in _RATE_FIELDS:
        if _rf in df.columns:
            df = df.drop(columns=[_rf])

    # Fill in any unmapped internal fields with safe defaults.
    for field in _INTERNAL_FIELDS:
        if field not in df.columns:
            if field == "date":
                df[field] = pd.NaT
            elif field in ("ad_requests", "ad_impressions", "unfilled_impressions",
                           "completed_views", "timeout_count", "error_count"):
                df[field] = 0
            elif field == "revenue_aud":
                df[field] = 0.0
            else:
                df[field] = "Unknown"

    # Coerce numeric columns so downstream sums work correctly.
    for _nc in ("ad_requests", "ad_impressions", "unfilled_impressions",
                "revenue_aud", "completed_views", "timeout_count", "error_count"):
        df[_nc] = pd.to_numeric(df[_nc], errors="coerce").fillna(0)

    # Parse date column.
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    return df


# ══════════════════════════════════════════════════════════════════════════════
# PAGE RENDER
# ══════════════════════════════════════════════════════════════════════════════

st.title("Weekly Supply Brief")

# ── Config — read allow_ai_on_uploaded_data setting ───────────────────────────
def _load_page_config():
    try:
        with open(os.path.join(_APP_ROOT, "config.json"), "r", encoding="utf-8") as _cf:
            return json.load(_cf)
    except Exception:
        return {}

_page_cfg = _load_page_config()
_allow_ai_on_upload = _page_cfg.get("allow_ai_on_uploaded_data", False)

# ── Upload control ────────────────────────────────────────────────────────────
# A unique counter in session state lets us reset the file_uploader widget
# (changing its key forces Streamlit to create a fresh widget).
_uploader_key = f"supply_uploader_{st.session_state.get('_supply_uploader_reset', 0)}"

_upl = st.file_uploader(
    "Upload a supply report (CSV, XLSX or TSV) — or leave empty to use demo data",
    type=["csv", "xlsx", "tsv"],
    key=_uploader_key,
)

_using_uploaded_data = False   # default: demo data

if _upl is not None:
    # If this is a different file than what's already processed, reset state.
    if st.session_state.get("_supply_upload_file_id") != _upl.name:
        from utils.file_loader import read_file as _read_file
        _raw_df, _read_err = _read_file(_upl)
        if _read_err:
            st.error(f"Could not read file: {_read_err}")
            st.stop()
        st.session_state["_supply_upload_file_id"]   = _upl.name
        st.session_state["_supply_upload_raw_df"]    = _raw_df
        # Clear any previously confirmed mapping when a new file is loaded.
        st.session_state.pop("_supply_upload_confirmed_df", None)

    if "_supply_upload_raw_df" in st.session_state:
        _raw_df = st.session_state["_supply_upload_raw_df"]

        if "_supply_upload_confirmed_df" not in st.session_state:
            # ── Column mapping step ───────────────────────────────────────────
            st.markdown("---")
            st.markdown("**Map columns to supply fields**")
            st.caption(
                "Match each detected column to a supply field. "
                "Any field left as '(Skip)' will default to 0 or 'Unknown'. "
                "Rate metrics (fill rate, eCPM, etc.) are always recalculated — "
                "leave those unmapped."
            )

            with st.expander("Preview uploaded data (first 3 rows)", expanded=False):
                st.dataframe(_raw_df.head(3), use_container_width=True)

            _saved_map = _load_saved_mapping()
            _detected_cols = list(_raw_df.columns)
            _map_opts = ["(Skip)"] + _INTERNAL_FIELDS

            _mc_left, _mc_right = st.columns(2)
            _new_mapping = {}
            for _ci, _col in enumerate(_detected_cols):
                _default = _saved_map.get(_col, "(Skip)")
                _def_idx = _map_opts.index(_default) if _default in _map_opts else 0
                _target_col = _mc_left if _ci % 2 == 0 else _mc_right
                with _target_col:
                    _new_mapping[_col] = st.selectbox(
                        f"`{_col}`",
                        _map_opts,
                        index=_def_idx,
                        key=f"supply_map_{_ci}_{_col}",
                    )

            st.markdown("")
            _apply_col, _cancel_col, _ = st.columns([1, 1, 4])
            with _apply_col:
                if st.button("Apply mapping", type="primary", key="supply_apply_mapping"):
                    _save_mapping(_new_mapping)
                    _confirmed = _apply_mapping(_raw_df.copy(), _new_mapping)
                    st.session_state["_supply_upload_confirmed_df"] = _confirmed
                    st.session_state["_supply_upload_filename"]     = _upl.name
                    st.rerun()
            with _cancel_col:
                if st.button("Cancel", key="supply_cancel_upload"):
                    st.session_state["_supply_uploader_reset"] = (
                        st.session_state.get("_supply_uploader_reset", 0) + 1
                    )
                    for _k in ["_supply_upload_file_id", "_supply_upload_raw_df",
                                "_supply_upload_confirmed_df", "_supply_upload_filename"]:
                        st.session_state.pop(_k, None)
                    st.rerun()

            # Stop rendering the rest of the page until mapping is confirmed.
            st.stop()

        else:
            # ── Mapping confirmed — show data source label + clear button ─────
            _using_uploaded_data = True
            _upload_filename = st.session_state.get("_supply_upload_filename", _upl.name)

            _src_c1, _src_c2, _src_c3 = st.columns([3, 1, 4])
            with _src_c1:
                st.markdown(
                    f'<div style="font-family:Poppins,system-ui,sans-serif;'
                    f'font-size:13px;font-weight:600;color:{SUCCESS};padding:6px 0;">'
                    f'Showing: {_html.escape(_upload_filename)}</div>',
                    unsafe_allow_html=True,
                )
            with _src_c2:
                if st.button("Clear upload", key="supply_clear_upload"):
                    st.session_state["_supply_uploader_reset"] = (
                        st.session_state.get("_supply_uploader_reset", 0) + 1
                    )
                    for _k in ["_supply_upload_file_id", "_supply_upload_raw_df",
                                "_supply_upload_confirmed_df", "_supply_upload_filename"]:
                        st.session_state.pop(_k, None)
                    st.rerun()
            with _src_c3:
                if st.button("Edit column mapping", key="supply_edit_mapping"):
                    st.session_state.pop("_supply_upload_confirmed_df", None)
                    st.rerun()

else:
    # No file in uploader — clear any stale upload state.
    for _k in ["_supply_upload_file_id", "_supply_upload_raw_df",
                "_supply_upload_confirmed_df", "_supply_upload_filename"]:
        st.session_state.pop(_k, None)
    st.markdown(
        f'<div style="font-family:Poppins,system-ui,sans-serif;'
        f'font-size:13px;color:{TEXT_SEC};padding:6px 0;">'
        f'Showing: demo data</div>',
        unsafe_allow_html=True,
    )

# ── API key — resolved once, used by commentary section and Generate Brief ────
_brief_api_key = get_anthropic_api_key()
# AI is disabled when using uploaded data unless explicitly enabled in config.
if _using_uploaded_data and not _allow_ai_on_upload:
    _ai_avail = False
else:
    _ai_avail = bool(_brief_api_key)

# Show AI safety notice when AI is off due to uploaded data.
if _using_uploaded_data and not _allow_ai_on_upload:
    st.info(
        "AI features are off while client data is loaded. "
        "To enable them, set \"allow_ai_on_uploaded_data\": true in config.json."
    )

# ── Load data ─────────────────────────────────────────────────────────────────
if _using_uploaded_data:
    df_all = st.session_state["_supply_upload_confirmed_df"].copy()
    # Ensure date is datetime and drop un-parseable rows.
    df_all["date"] = pd.to_datetime(df_all["date"], errors="coerce")
    df_all = df_all.dropna(subset=["date"])
else:
    df_all = load_supply_data()
    st.caption("Demo using fabricated data. Not real publisher inventory.")

if df_all.empty:
    st.error("No data available for the current source. Check your upload or supply data file.")
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
_current_ctx = f"week ending {sel_week_label}"

try:
    # Build context label for filter state tracking
    _ctx_parts = [p for p in [
        sel_prop if sel_prop != "All" else None,
        sel_fmt  if sel_fmt  != "All" else None,
        sel_dev  if sel_dev  != "All" else None,
        sel_dem  if sel_dem  != "All" else None,
        f"week ending {sel_week_label}",
    ] if p]
    _current_ctx = " · ".join(_ctx_parts)

    # Publisher selector — defaults to page-level publisher filter if set
    _all_pubs = list(PUBLISHER_PROPERTIES.keys())
    _comm_pub_default = sel_pub if sel_pub != "All" else _all_pubs[0]
    _comm_pub_idx = _all_pubs.index(_comm_pub_default) if _comm_pub_default in _all_pubs else 0

    st.caption("AI-written narrative for the weekly publisher brief. Scoped to one publisher at a time.")

    _comm_pub = st.selectbox(
        "Publisher",
        _all_pubs,
        index=_comm_pub_idx,
        key="commentary_pub_select",
    )
    _comm_props = PUBLISHER_PROPERTIES[_comm_pub]

    # Per-publisher data and metrics
    _comm_df = df_week[df_week["publisher"] == _comm_pub]
    _comm_cur = week_totals(_comm_df) if not _comm_df.empty else {}

    # Per-publisher yield findings — filter yield_findings to this publisher
    _comm_yield = [f for f in yield_findings if _comm_pub.lower() in f.get("detail", "").lower()
                   or _comm_pub.lower() in f.get("title", "").lower()]
    if not _comm_yield:
        _comm_yield = yield_findings  # fallback: use all findings if none tagged to publisher

    # Session-state key for this publisher's commentary
    _comm_ss_key  = f"supply_commentary_{_comm_pub}"
    _comm_ctx_key = f"supply_commentary_ctx_{_comm_pub}"

    _existing_text = st.session_state.get(_comm_ss_key, "")
    _existing_ctx  = st.session_state.get(_comm_ctx_key, "")
    _full_ctx = f"{_comm_pub} · {_current_ctx}"

    with st.container():
        if _existing_text:
            # Show which publisher + filter state the text was generated under
            if _existing_ctx:
                _ctx_color = TEXT_SEC if _existing_ctx == _full_ctx else "#F59E0B"
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

            st.markdown('<div style="margin-top:10px;"></div>', unsafe_allow_html=True)
            if st.button("🔄 Regenerate", key="commentary_regen_btn"):
                st.session_state.pop(_comm_ss_key, None)
                st.session_state.pop(_comm_ctx_key, None)
                st.rerun()

        else:
            # Placeholder card shown before first generation
            st.markdown(
                f'<div style="background:{WHITE};border:0.5px solid rgba(27,42,74,0.12);'
                f'border-radius:16px;padding:22px 26px;">'
                f'<p style="font-family:Poppins,system-ui,sans-serif;font-size:14px;'
                f'color:{TEXT_SEC};font-style:italic;margin:0;">'
                f'Click "Generate commentary" to produce an AI-written narrative '
                f'for {_comm_pub} based on this week\'s metrics and yield findings.</p>'
                f'</div>',
                unsafe_allow_html=True,
            )

            st.markdown('<div style="margin-top:10px;"></div>', unsafe_allow_html=True)

            if _ai_avail:
                _gcol1, _gcol2 = st.columns([2, 3])
                with _gcol1:
                    if st.button("Generate commentary", key="commentary_gen_btn", type="primary"):
                        with st.spinner(f"Writing commentary for {_comm_pub}…"):
                            _text = _generate_commentary(
                                _brief_api_key, _comm_pub, _comm_props,
                                sel_week_label, _comm_cur, _comm_yield,
                            )
                            st.session_state[_comm_ss_key]  = _text
                            st.session_state[_comm_ctx_key] = _full_ctx
                        st.rerun()
                with _gcol2:
                    st.caption("Uses AI credits.")

                st.markdown('<div style="margin-top:6px;"></div>', unsafe_allow_html=True)
                st.info(
                    f"'Generate for all publishers' will make {len(_all_pubs)} API calls "
                    f"(one per publisher).",
                )
                if st.button("Generate for all publishers", key="commentary_all_btn"):
                    for _pname in _all_pubs:
                        _sk  = f"supply_commentary_{_pname}"
                        _ck  = f"supply_commentary_ctx_{_pname}"
                        if not st.session_state.get(_sk):
                            _pdf = df_week[df_week["publisher"] == _pname]
                            _pcu = week_totals(_pdf) if not _pdf.empty else {}
                            _pyd = [f for f in yield_findings
                                    if _pname.lower() in f.get("detail","").lower()
                                    or _pname.lower() in f.get("title","").lower()] or yield_findings
                            with st.spinner(f"Writing commentary for {_pname}…"):
                                try:
                                    _pt = _generate_commentary(
                                        _brief_api_key, _pname,
                                        PUBLISHER_PROPERTIES[_pname],
                                        sel_week_label, _pcu, _pyd,
                                    )
                                    st.session_state[_sk] = _pt
                                    st.session_state[_ck] = f"{_pname} · {_current_ctx}"
                                except Exception as _pae:
                                    st.warning(f"Could not generate commentary for {_pname}: {_pae}")
                    st.rerun()
            else:
                if _using_uploaded_data and not _allow_ai_on_upload:
                    st.caption("⚠ AI features are off while client data is loaded.")
                else:
                    st.caption("⚠ Requires ANTHROPIC_API_KEY in Streamlit secrets to generate commentary.")

    # If all-publishers commentary exists (2+ publishers), display in expanders
    _generated_pubs = [p for p in _all_pubs if st.session_state.get(f"supply_commentary_{p}")]
    if len(_generated_pubs) > 1:
        section_header("All Publisher Commentaries")
        for _pname in _generated_pubs:
            _sk = f"supply_commentary_{_pname}"
            _ck = f"supply_commentary_ctx_{_pname}"
            with st.expander(f"**{_pname}**", expanded=(_pname == _comm_pub)):
                _ctx_val = st.session_state.get(_ck, "")
                if _ctx_val:
                    st.markdown(
                        f'<p style="font-family:Poppins,system-ui,sans-serif;'
                        f'font-size:11px;color:{TEXT_SEC};margin:0 0 12px 0;">'
                        f'Generated for: {_html.escape(_ctx_val)}</p>',
                        unsafe_allow_html=True,
                    )
                _psafe = (
                    _html.escape(st.session_state.get(_sk, ""))
                    .replace("\n\n", "</p><p style='margin:10px 0;'>")
                    .replace("\n", "<br>")
                )
                st.markdown(
                    f'<div style="background:{WHITE};border:0.5px solid rgba(27,42,74,0.12);'
                    f'border-radius:16px;padding:22px 26px;">'
                    f'<div style="font-family:Poppins,system-ui,sans-serif;font-size:14px;'
                    f'color:#374151;line-height:1.75;">'
                    f'<p style="margin:0 0 10px 0;">{_psafe}</p>'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )

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
# _brief_api_key and _ai_avail are resolved once near the top of the page render
# (after load_supply_data) — no re-definition needed here.
section_header("Generate Weekly Brief")

# Check how many publishers already have commentary cached — used to enable the
# "AI Commentary (all publishers)" checkbox in the dialog.
_all_pubs_for_dialog = list(PUBLISHER_PROPERTIES.keys())
_any_generated_pubs_all = sum(
    1 for p in _all_pubs_for_dialog if st.session_state.get(f"supply_commentary_{p}")
) >= 2


@st.dialog("Generate Weekly Brief")
def _show_brief_dialog():
    """Section-picker dialog for the PowerPoint export."""
    st.caption("Select sections to include in the PowerPoint export.")

    # Restore previous section defaults from session state
    _b_defs = st.session_state.get("_brief_section_defs", {
        "headline_summary":    True,
        "yield_opportunities": True,
        "ai_commentary":       False,   # unchecked by default — uses AI credits
        "ai_commentary_all":   False,
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
        "AI Commentary (selected publisher)  *(Uses AI credits)*",
        value=_b_defs.get("ai_commentary", False),
        key="brief_cb_ai",
        disabled=not _ai_avail,
        help=(
            "Includes AI narrative for the publisher selected in the commentary section."
            if _ai_avail
            else (
                "AI features are off while client data is loaded."
                if (_using_uploaded_data and not _allow_ai_on_upload)
                else "Requires ANTHROPIC_API_KEY in Streamlit secrets."
            )
        ),
    )
    s_ai_all = st.checkbox(
        "AI Commentary (all publishers)  *(Uses AI credits)*",
        value=_b_defs.get("ai_commentary_all", False),
        key="brief_cb_ai_all",
        disabled=(not _ai_avail or not _any_generated_pubs_all),
        help=(
            "Includes AI narrative for all publishers — one slide each. "
            "Generate commentary for at least 2 publishers first."
            if _ai_avail
            else (
                "AI features are off while client data is loaded."
                if (_using_uploaded_data and not _allow_ai_on_upload)
                else "Requires ANTHROPIC_API_KEY in Streamlit secrets."
            )
        ),
    )

    if not _ai_avail:
        if _using_uploaded_data and not _allow_ai_on_upload:
            st.caption("⚠ AI features are off while client data is loaded.")
        else:
            st.caption("⚠ AI Commentary requires ANTHROPIC_API_KEY in Streamlit secrets.")
    elif not _any_generated_pubs_all:
        st.caption("Generate commentary for 2+ publishers to enable 'all publishers' export.")

    st.markdown("")

    _act = st.columns(2)
    with _act[0]:
        if st.button("Generate PowerPoint", type="primary", key="brief_gen_btn"):
            # Persist section choices for next dialog open
            st.session_state["_brief_section_defs"] = {
                "headline_summary":    s_headline,
                "yield_opportunities": s_yield,
                "ai_commentary":       s_ai,
                "ai_commentary_all":   s_ai_all,
            }
            sections = st.session_state["_brief_section_defs"]

            if not any(sections.values()):
                st.warning("Select at least one section.")
                return

            # Build ai_narratives dict for the PPTX
            ai_narratives = {}
            if s_ai and _ai_avail:
                # Single publisher — selected in commentary section
                _sp = st.session_state.get("commentary_pub_select", _all_pubs_for_dialog[0])
                cached = st.session_state.get(f"supply_commentary_{_sp}", "")
                if cached:
                    ai_narratives[_sp] = cached
                else:
                    with st.spinner(f"Generating AI commentary for {_sp}…"):
                        try:
                            _pdf = df_week[df_week["publisher"] == _sp]
                            _pcu = week_totals(_pdf) if not _pdf.empty else {}
                            _pyd = [f for f in yield_findings
                                    if _sp.lower() in f.get("detail","").lower()
                                    or _sp.lower() in f.get("title","").lower()] or yield_findings
                            _pt = _generate_commentary(
                                _brief_api_key, _sp, PUBLISHER_PROPERTIES[_sp],
                                sel_week_label, _pcu, _pyd,
                            )
                            ai_narratives[_sp] = _pt
                            st.session_state[f"supply_commentary_{_sp}"] = _pt
                            st.session_state[f"supply_commentary_ctx_{_sp}"] = f"{_sp} · {_current_ctx}"
                        except Exception as _ae:
                            st.warning(f"AI commentary could not be generated: {_ae}")

            if s_ai_all and _ai_avail:
                # All publishers — use cached commentaries
                for _pname in PUBLISHER_PROPERTIES:
                    cached_p = st.session_state.get(f"supply_commentary_{_pname}", "")
                    if cached_p:
                        ai_narratives[_pname] = cached_p

            # Build the PPTX
            with st.spinner("Building PowerPoint…"):
                try:
                    pptx_buf = build_supply_pptx(
                        df_week, yield_findings, sections,
                        sel_week_label, cur, ai_narratives,
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
