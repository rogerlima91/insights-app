import streamlit as st
import json
import os
import sys
import io
import math
from datetime import date
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from utils.design_system import (
    get_css, PRIMARY, SECONDARY, SUCCESS, WARNING, DANGER,
    WHITE, TEXT_SEC, TEXT_PRI, BORDER_LIGHT, BG_PAGE,
)

# ── Apply Pacebird design system CSS ─────────────────────────────────────────
# STYLE LOCK: primary #F5A623 orange, secondary #1B2A4A navy, font Poppins.
st.markdown(get_css(), unsafe_allow_html=True)

# ── Media type badge palette (one distinct color per media type) ───────────
# These are stable constants; do not change without updating all references below.
MEDIA_COLORS = {
    "Broadcast TV": ("#1B2A4A", "#FFFFFF"),   # navy bg  / white text
    "BVOD":         ("#F5A623", "#FFFFFF"),   # orange bg / white text
    "Audio":        ("#10B981", "#FFFFFF"),   # green bg  / white text
    "Publishing":   ("#D97706", "#FFFFFF"),   # amber-brown / white text
    "Digital":      ("#4A7AB5", "#FFFFFF"),   # mid-blue  / white text
}
# Ordered for consistent grouping / chart display
MEDIA_ORDER = ["Broadcast TV", "BVOD", "Audio", "Publishing", "Digital"]

# ── Page-specific CSS ─────────────────────────────────────────────────────────
st.markdown(f"""
<style>
    /* ── Segment cards ─────────────────────────────────────────────── */
    .seg-card {{
        background: {WHITE};
        border-radius: 16px;
        border-top: 4px solid {PRIMARY};
        padding: 16px 20px 14px 20px;
        margin-bottom: 10px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06);
    }}
    .seg-card-selected {{
        border-top: 4px solid {SUCCESS};
        box-shadow: 0 2px 18px rgba(16,185,129,0.15);
    }}
    /* ── Badges ─────────────────────────────────────────────────────── */
    .badge-cat {{
        display: inline-block;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 700;
        background: rgba(245,166,35,0.14);
        color: {PRIMARY};
    }}
    .badge-match {{
        display: inline-block;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 700;
    }}
    .match-high {{ background: rgba(16,185,129,0.14);  color: {SUCCESS}; }}
    .match-mid  {{ background: rgba(245,158,11,0.14);  color: {WARNING}; }}
    .match-low  {{ background: rgba(107,114,128,0.10); color: {TEXT_SEC}; }}
    .badge-signal {{
        display: inline-block;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 10px;
        font-weight: 600;
        background: rgba(27,42,74,0.08);
        color: {SECONDARY};
    }}
    .badge-media {{
        display: inline-block;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 700;
    }}
    .badge-act {{
        display: inline-block;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 10px;
        font-weight: 600;
        background: {BG_PAGE};
        color: {TEXT_SEC};
        margin-right: 3px;
    }}
    .badge-noaddr {{
        display: inline-block;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 10px;
        font-weight: 600;
        background: rgba(239,68,68,0.10);
        color: {DANGER};
        margin-right: 3px;
    }}
    /* ── Meta labels and values inside cards ────────────────────────── */
    .mlabel {{
        font-size: 10px;
        color: {TEXT_SEC};
        text-transform: uppercase;
        letter-spacing: 0.06em;
        font-weight: 700;
        margin-bottom: 2px;
    }}
    .mval {{
        font-size: 14px;
        font-weight: 700;
        color: {TEXT_PRI};
    }}
    /* ── Media type group header ────────────────────────────────────── */
    .media-group-header {{
        display: flex;
        align-items: center;
        gap: 10px;
        margin: 18px 0 10px 0;
    }}
    /* ── Stack and deal panels ──────────────────────────────────────── */
    .stack-panel {{
        background: {WHITE};
        border-radius: 16px;
        border-top: 4px solid {SECONDARY};
        padding: 20px 24px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06);
        margin-bottom: 12px;
    }}
    .deal-panel {{
        background: {WHITE};
        border-radius: 16px;
        border-top: 4px solid {PRIMARY};
        padding: 20px 24px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06);
    }}
    /* ── Warning callouts ───────────────────────────────────────────── */
    .warn-box {{
        background: #FFFBEB;
        border: 1px solid {WARNING};
        border-left: 4px solid {WARNING};
        border-radius: 8px;
        padding: 10px 14px;
        font-size: 13px;
        color: #92400E;
        margin-top: 8px;
        line-height: 1.6;
    }}
    .info-box {{
        background: #EFF6FF;
        border: 1px solid #BFDBFE;
        border-left: 4px solid #3B82F6;
        border-radius: 8px;
        padding: 10px 14px;
        font-size: 13px;
        color: #1E3A8A;
        margin-top: 8px;
        line-height: 1.6;
    }}
    /* ── Sense-check block ──────────────────────────────────────────── */
    .sense-check {{
        background: {BG_PAGE};
        border-radius: 8px;
        padding: 10px 14px;
        font-size: 13px;
        color: {TEXT_PRI};
        margin-top: 14px;
    }}
    /* ── Section dividers ───────────────────────────────────────────── */
    .sec-rule {{
        border: none;
        border-top: 2px solid {BORDER_LIGHT};
        margin: 28px 0 20px 0;
    }}
    /* ── Disclaimer bar ─────────────────────────────────────────────── */
    .disclaimer-bar {{
        background: #FFF4E0;
        border: 1px solid {WARNING};
        border-radius: 8px;
        padding: 6px 14px;
        font-size: 12px;
        color: #92400E;
        margin-bottom: 16px;
    }}
    /* ── Dedup disclaimer ───────────────────────────────────────────── */
    .dedup-note {{
        background: {BG_PAGE};
        border-radius: 8px;
        padding: 8px 12px;
        font-size: 11px;
        color: {TEXT_SEC};
        font-style: italic;
        margin-top: 10px;
        line-height: 1.5;
    }}
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# DATA & MODEL HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data
def load_segments():
    """Load the Seven West Media cross-media audience segment taxonomy from JSON."""
    seg_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "data", "audience_segments.json"
    )
    with open(seg_path) as f:
        return json.load(f)["segments"]


@st.cache_resource(show_spinner="Loading semantic model (first run only)...")
def load_model():
    """Load all-MiniLM-L6-v2. Cached globally — only downloads once."""
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("all-MiniLM-L6-v2")


@st.cache_data(show_spinner=False)
def embed_descriptions(desc_tuple):
    """
    Embed all segment descriptions once and cache the result.
    Takes a tuple so st.cache_data can hash it reliably.
    """
    model = load_model()
    return model.encode(list(desc_tuple))


def cosine_sim(a, b):
    """Cosine similarity between two numpy-compatible vectors."""
    a = np.array(a, dtype=float)
    b = np.array(b, dtype=float)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / (denom + 1e-10))


def match_badge_class(score):
    """Return CSS class for the match % badge based on score."""
    if score >= 0.50:
        return "badge-match match-high"
    if score >= 0.30:
        return "badge-match match-mid"
    return "badge-match match-low"


def media_badge_html(media_type):
    """Return an inline HTML badge for the given media_type string."""
    bg, fg = MEDIA_COLORS.get(media_type, ("#888888", "#FFFFFF"))
    return (
        f'<span class="badge-media" '
        f'style="background:{bg};color:{fg};">'
        f'{media_type}</span>'
    )


def estimate_deduplicated_reach(selected_segs, same_group_overlap, cross_media_overlap):
    """
    Estimate deduplicated reach across a cross-media stack.

    Method:
    - Sort segments by reach descending — largest anchors the estimate.
    - First segment gets full reach.
    - Each subsequent segment contributes incremental reach based on:
        • Shares an overlap_group with an already-added segment →
          incremental = reach × (1 - same_group_overlap)  [heavily duplicated]
        • Different media_type from all already-added, no shared overlap_group →
          incremental = reach × (1 - cross_media_overlap)  [lightly duplicated]
        • Same media_type, no shared overlap_group →
          incremental = reach × (1 - mid_overlap)  [moderate duplication]

    Returns:
        dedup_reach (int), incremental_by_media_type (dict[str, int])
    """
    if not selected_segs:
        return 0, {}

    mid_overlap = (same_group_overlap + cross_media_overlap) / 2

    # Sort descending by reach so the biggest segment anchors the calculation
    sorted_segs = sorted(selected_segs, key=lambda s: s["reach_monthly"], reverse=True)

    added_groups     = set()   # overlap_group tags already in the stack
    added_media_types = set()  # media_type strings already in the stack

    dedup_reach = 0
    incremental_by_type = {}

    for seg in sorted_segs:
        # Collect this segment's overlap_group tag(s) as a set
        og = seg.get("overlap_group", "")
        seg_groups = {og} if og else set()

        seg_media = seg["media_type"]
        reach     = seg["reach_monthly"]

        if not added_media_types:
            # First segment — full reach
            incremental = reach
        else:
            has_group_overlap = bool(seg_groups & added_groups)
            is_new_media_type = seg_media not in added_media_types

            if has_group_overlap:
                # Shares a named overlap group → heavily duplicated
                incremental = int(reach * (1 - same_group_overlap))
            elif is_new_media_type:
                # New media type with no shared group → lightly duplicated
                incremental = int(reach * (1 - cross_media_overlap))
            else:
                # Same media type, no shared group → moderate duplication
                incremental = int(reach * (1 - mid_overlap))

        dedup_reach += incremental
        added_groups.update(seg_groups)
        added_media_types.add(seg_media)

        incremental_by_type[seg_media] = incremental_by_type.get(seg_media, 0) + incremental

    return int(dedup_reach), incremental_by_type


def build_package_recommendation(selected_segs, budget, flight_days, objective,
                                  dedup_reach, wt_cpm_min, wt_cpm_max):
    """
    Build a rules-based package recommendation dict.

    Returns a dict with keys:
        media_types_in_stack  list of media type strings
        budget_split          dict[media_type → suggested A$ amount]
        split_rationale       dict[media_type → one-line rationale]
        activation_route      dict[media_type → activation method string]
        sense_check           string (or empty)
        caption               disclaimer string
    """
    if not selected_segs:
        return {}

    # Which media types are in the stack?
    media_types_present = []
    for mt in MEDIA_ORDER:
        if any(s["media_type"] == mt for s in selected_segs):
            media_types_present.append(mt)

    # Base budget weight per media type (reflects brand-building priority)
    BASE_WEIGHTS = {
        "Broadcast TV": 35,
        "BVOD":         25,
        "Audio":        15,
        "Publishing":   15,
        "Digital":      10,
    }

    # Rationale per media type
    SPLIT_RATIONALE = {
        "Broadcast TV": "Mass reach anchor — establishes brand at scale in a high-attention environment.",
        "BVOD":         "Addressable video extending broadcast reach into registered streaming audiences.",
        "Audio":        "Intimate, habit-driven touchpoint complementing screen-based media.",
        "Publishing":   "High-index contextual alignment with engaged, topic-loyal readership.",
        "Digital":      "Performance and retargeting layer; closes reach gaps and enables frequency management.",
    }

    # Activation route logic
    def activation_route(mt, budget_for_type):
        if mt == "Broadcast TV":
            return "Direct IO — Linear TV buy"
        if mt == "BVOD":
            return "Programmatic Guaranteed (PG)" if (budget_for_type or 0) >= 15000 else "PMP"
        if mt == "Audio":
            has_podcast = any(
                "Podcast" in s.get("activation", [])
                for s in selected_segs if s["media_type"] == mt
            )
            has_linear  = any(
                "Audio" in s.get("activation", [])
                for s in selected_segs if s["media_type"] == mt
            )
            parts = []
            if has_linear:
                parts.append("Direct IO — Radio")
            if has_podcast:
                parts.append("Programmatic Podcast (LiSTNR)")
            return " + ".join(parts) if parts else "Direct IO"
        if mt == "Publishing":
            return "PMP / Native Direct IO"
        if mt == "Digital":
            return "PMP" if (budget_for_type or 0) >= 10000 else "Open Market / PMP"
        return "Confirm with sales team"

    # Filter weights to present media types and normalise
    raw_weights = {mt: BASE_WEIGHTS[mt] for mt in media_types_present}
    total_w = sum(raw_weights.values())
    norm_weights = {mt: w / total_w for mt, w in raw_weights.items()}

    # Compute suggested A$ split
    budget_split = {}
    split_rationale = {}
    routes = {}
    if budget and budget > 0:
        for mt in media_types_present:
            alloc = int(budget * norm_weights[mt])
            budget_split[mt]    = alloc
            split_rationale[mt] = SPLIT_RATIONALE[mt]
            routes[mt]          = activation_route(mt, alloc)
    else:
        for mt in media_types_present:
            budget_split[mt]    = None
            split_rationale[mt] = SPLIT_RATIONALE[mt]
            routes[mt]          = activation_route(mt, None)

    # Sense-check string
    sense_check = ""
    mid_cpm = (wt_cpm_min + wt_cpm_max) / 2
    if budget and budget > 0 and flight_days and flight_days > 0 and mid_cpm > 0:
        implied_imps = int((budget / mid_cpm) * 1000)
        flight_mo    = flight_days / 30
        avail_imps   = int(dedup_reach * flight_mo)
        sense_check = (
            f"A${budget:,} at A${mid_cpm:.2f} blended CPM implies ~{implied_imps:,} impressions "
            f"over {flight_days} days against an estimated deduplicated reach of ~{dedup_reach:,}. "
            f"Approximate available impressions for this flight: ~{avail_imps:,}."
        )

    return {
        "media_types_in_stack": media_types_present,
        "budget_split":         budget_split,
        "split_rationale":      split_rationale,
        "activation_route":     routes,
        "sense_check":          sense_check,
        "caption":              (
            "Indicative only. Validate availability and reach against planning tools before committing."
        ),
    }


def make_incremental_reach_chart(incremental_by_type):
    """
    Build a horizontal bar chart showing the incremental reach contribution
    of each media type in the stack. Returns a matplotlib figure.
    """
    # Only include media types that have incremental reach and are in MEDIA_ORDER
    labels   = [mt for mt in MEDIA_ORDER if incremental_by_type.get(mt, 0) > 0]
    values   = [incremental_by_type[mt] for mt in labels]
    colors   = [MEDIA_COLORS.get(mt, ("#888888", "#FFFFFF"))[0] for mt in labels]

    if not labels:
        return None

    fig, ax = plt.subplots(figsize=(10, max(2.5, len(labels) * 0.7)))
    bars = ax.barh(labels, values, color=colors, height=0.55)

    # Data labels
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_width() + max(values) * 0.01,
            bar.get_y() + bar.get_height() / 2,
            f"{val:,}",
            va="center", ha="left",
            fontsize=10, fontweight="bold", color=TEXT_PRI,
        )

    ax.set_xlabel("Incremental deduplicated reach", fontsize=10, color=TEXT_SEC)
    ax.set_title("Incremental reach contribution by media type",
                 fontsize=11, fontweight="bold", color=TEXT_PRI, pad=10)
    ax.tick_params(labelsize=10, colors=TEXT_SEC)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(BORDER_LIGHT)
    ax.spines["bottom"].set_color(BORDER_LIGHT)
    ax.set_facecolor(WHITE)
    fig.patch.set_facecolor(WHITE)
    # Invert y so largest bar is at top
    ax.invert_yaxis()
    ax.set_xlim(0, max(values) * 1.18)
    fig.tight_layout()
    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# PPTX BUILDER
# ═══════════════════════════════════════════════════════════════════════════════

def _build_proposal_pptx(ctx, sections):
    """
    Build a PowerPoint proposal deck from the stack context dict.
    Dark premium template — same visual language as the rest of the app.

    ctx keys:
        selected_segs, brief_text, budget, flight_start, flight_end,
        flight_days, objective, raw_reach, dedup_reach, same_group_overlap,
        cross_media_overlap, incremental_by_type, wt_cpm_min, wt_cpm_max,
        max_min_spend, wt_index, pkg_rec, sense_check
    """
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN

    def rgb(h):
        h = h.lstrip("#")
        return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

    BG_    = rgb("#0D1B2A")
    WHITE_ = rgb("#FFFFFF")
    GREY_  = rgb("#A8B2BC")
    ORANGE = rgb("#F5A623")
    NAVY_  = rgb("#1B2A4A")
    GREEN_ = rgb("#10B981")

    prs = Presentation()
    prs.slide_width  = Inches(13.33)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    def new_slide():
        sl = prs.slides.add_slide(blank)
        bg = sl.background
        fill = bg.fill
        fill.solid()
        fill.fore_color.rgb = BG_
        return sl

    def txt(sl, text, l, t, w, h,
            size=12, bold=False, color=None, align=PP_ALIGN.LEFT, italic=False):
        tb = sl.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = align
        r = p.add_run()
        r.text = str(text)
        r.font.size   = Pt(size)
        r.font.bold   = bold
        r.font.italic = italic
        r.font.color.rgb = color or WHITE_

    def footer(sl, n):
        txt(sl, "Pacebird — Audience Solutions", 0.3, 7.1, 6, 0.3, size=9, color=GREY_)
        txt(sl, str(n), 12.8, 7.1, 0.5, 0.3, size=9, color=GREY_, align=PP_ALIGN.RIGHT)

    # Unpack context
    segs        = ctx["selected_segs"]
    brief       = ctx.get("brief_text", "")
    bgt         = ctx.get("budget", 0)
    fstart      = ctx.get("flight_start")
    fend        = ctx.get("flight_end")
    fdays       = ctx.get("flight_days")
    obj         = ctx.get("objective", "")
    raw_reach   = ctx.get("raw_reach", 0)
    dedup_reach = ctx.get("dedup_reach", 0)
    cpm_lo      = ctx.get("wt_cpm_min", 0)
    cpm_hi      = ctx.get("wt_cpm_max", 0)
    min_sp      = ctx.get("max_min_spend", 0)
    wt_idx      = ctx.get("wt_index", 0)
    pkg         = ctx.get("pkg_rec", {})
    sense       = ctx.get("sense_check", "")
    sg_ovlp     = ctx.get("same_group_overlap", 0.70)
    cm_ovlp     = ctx.get("cross_media_overlap", 0.20)

    slide_n = 1

    # ── Slide 1: Title ─────────────────────────────────────────────────────────
    sl = new_slide()
    txt(sl, "Cross-Media Audience Package", 1.0, 1.8, 11.0, 1.0, size=30, bold=True)
    txt(sl, "Seven West Media — Portfolio Audience Solutions",
        1.0, 2.85, 11.0, 0.6, size=18, color=ORANGE)
    txt(sl,
        f"Prepared {date.today().strftime('%d %B %Y')}  ·  "
        "Fabricated demo data — not real inventory",
        1.0, 3.85, 11.0, 0.4, size=10, color=GREY_, italic=True)
    footer(sl, slide_n); slide_n += 1

    # ── Slide: Brief Summary ───────────────────────────────────────────────────
    if sections.get("brief_summary") and brief.strip():
        sl = new_slide()
        txt(sl, "Client Brief", 0.5, 0.3, 12.0, 0.6, size=22, bold=True)
        brief_s = (brief.strip()[:500] + "…") if len(brief.strip()) > 500 else brief.strip()
        txt(sl, brief_s, 0.5, 1.1, 12.0, 3.5, size=12)
        params = []
        if bgt and bgt > 0:
            params.append(f"Budget: A${bgt:,}")
        if fstart and fend:
            params.append(f"Flight: {fstart.strftime('%d %b %Y')} → {fend.strftime('%d %b %Y')} ({fdays} days)")
        params.append(f"Objective: {obj}")
        for i, p in enumerate(params):
            txt(sl, f"• {p}", 0.5, 4.9 + i * 0.45, 12.0, 0.4, size=12, color=ORANGE)
        footer(sl, slide_n); slide_n += 1

    # ── Slides: Segments by Media Type (3 per slide) ──────────────────────────
    if sections.get("segments_by_media") and segs:
        # Group by media type in MEDIA_ORDER
        by_type = {}
        for s in segs:
            mt = s.get("media_type", "Unknown")
            by_type.setdefault(mt, []).append(s)

        for mt in MEDIA_ORDER:
            type_segs = by_type.get(mt, [])
            if not type_segs:
                continue
            mt_bg, mt_fg = MEDIA_COLORS.get(mt, ("#888888", "#FFFFFF"))

            chunk_sz = 3
            for c_start in range(0, len(type_segs), chunk_sz):
                chunk = type_segs[c_start:c_start + chunk_sz]
                sl = new_slide()
                txt(sl, f"Recommended Segments — {mt}",
                    0.5, 0.3, 12.0, 0.6, size=20, bold=True)
                if len(type_segs) > chunk_sz:
                    txt(sl, f"({c_start+1}–{c_start+len(chunk)} of {len(type_segs)})",
                        0.5, 0.85, 6.0, 0.3, size=10, color=GREY_)

                col_w = 12.0 / max(len(chunk), 1)
                for i, seg in enumerate(chunk):
                    x = 0.5 + i * col_w
                    card = sl.shapes.add_shape(
                        1, Inches(x), Inches(1.3), Inches(col_w - 0.15), Inches(5.5)
                    )
                    card.fill.solid()
                    card.fill.fore_color.rgb = NAVY_
                    card.line.color.rgb = rgb(mt_bg)

                    txt(sl, seg["segment_id"],
                        x+0.1, 1.4, col_w-0.25, 0.3, size=8, color=GREY_)
                    txt(sl, seg["segment_name"],
                        x+0.1, 1.68, col_w-0.25, 0.5, size=11, bold=True)
                    txt(sl, seg["category"],
                        x+0.1, 2.22, col_w-0.25, 0.3, size=9, color=ORANGE)

                    desc_s = seg["description"][:200] + "…" if len(seg["description"]) > 200 else seg["description"]
                    txt(sl, desc_s, x+0.1, 2.58, col_w-0.25, 1.55, size=8, color=GREY_)

                    addr_txt = "Addressable" if seg.get("addressable") else "Contextual only"
                    txt(sl, addr_txt,
                        x+0.1, 4.18, col_w-0.25, 0.28, size=8, color=GREY_)
                    txt(sl, f"Reach: {seg['reach_monthly']:,}",
                        x+0.1, 4.48, col_w-0.25, 0.28, size=10)
                    txt(sl, f"Index: {seg['index_general_pop']:.1f}×",
                        x+0.1, 4.78, col_w-0.25, 0.28, size=10)
                    txt(sl, f"CPM: A${seg['indicative_cpm_min']:.0f}–A${seg['indicative_cpm_max']:.0f}",
                        x+0.1, 5.08, col_w-0.25, 0.28, size=10)
                    txt(sl, ", ".join(seg.get("activation", [])),
                        x+0.1, 5.38, col_w-0.25, 0.3, size=8, color=GREY_)

                footer(sl, slide_n); slide_n += 1

    # ── Slide: Cross-Media Stack Summary ──────────────────────────────────────
    if sections.get("stack_summary") and segs:
        sl = new_slide()
        txt(sl, "Cross-Media Stack Summary", 0.5, 0.3, 12.0, 0.6, size=22, bold=True)

        metric_cards = [
            ("Raw Combined Reach",      f"{raw_reach:,}",       "sum before deduplication"),
            ("Est. Deduplicated Reach",  f"{dedup_reach:,}",
             f"same-group {sg_ovlp:.0%} / cross-media {cm_ovlp:.0%} overlap assumed"),
            ("Blended CPM",             f"A${cpm_lo:.0f}–A${cpm_hi:.0f}", "reach-weighted"),
            ("Min Spend Required",       f"A${min_sp:,}",       "highest across stack"),
        ]
        for i, (lbl, val, sub) in enumerate(metric_cards):
            x = 0.5 + i * 3.1
            c = sl.shapes.add_shape(1, Inches(x), Inches(1.2), Inches(2.85), Inches(1.8))
            c.fill.solid(); c.fill.fore_color.rgb = NAVY_; c.line.color.rgb = ORANGE
            txt(sl, lbl,  x+0.1, 1.3,  2.6, 0.3, size=9,  color=GREY_)
            txt(sl, val,  x+0.1, 1.62, 2.6, 0.55, size=16, bold=True)
            txt(sl, sub,  x+0.1, 2.28, 2.6, 0.3, size=8,  color=GREY_, italic=True)

        txt(sl, "Segments in stack:", 0.5, 3.3, 12.0, 0.35, size=11, color=GREY_)
        for j, seg in enumerate(segs[:8]):
            txt(sl,
                f"• [{seg.get('media_type','?')}]  {seg['segment_id']}  {seg['segment_name']}",
                0.5, 3.68 + j * 0.38, 12.0, 0.35, size=10)

        txt(sl,
            "Estimated. Overlap assumptions are adjustable and would be validated against "
            "panel data (OzTAM, GfK) in production. Do not present as measured reach.",
            0.5, 6.7, 12.0, 0.4, size=8, color=GREY_, italic=True)
        footer(sl, slide_n); slide_n += 1

    # ── Slide: Package Recommendation ─────────────────────────────────────────
    if sections.get("package_recommendation") and pkg:
        sl = new_slide()
        txt(sl, "Package Recommendation", 0.5, 0.3, 12.0, 0.6, size=22, bold=True)

        media_list = pkg.get("media_types_in_stack", [])
        budget_split = pkg.get("budget_split", {})
        routes = pkg.get("activation_route", {})
        rationales = pkg.get("split_rationale", {})

        for j, mt in enumerate(media_list[:6]):
            y = 1.2 + j * 0.88
            mt_bg, _ = MEDIA_COLORS.get(mt, ("#888888", "#FFFFFF"))
            alloc = budget_split.get(mt)
            alloc_str = f"A${alloc:,}" if alloc else "—"
            txt(sl, mt,       0.5, y,       2.2, 0.35, size=12, bold=True, color=rgb(mt_bg))
            txt(sl, alloc_str, 2.8, y,       1.5, 0.35, size=12, bold=True)
            txt(sl, routes.get(mt, ""), 4.4, y,  5.5, 0.35, size=10, color=GREY_)
            txt(sl, rationales.get(mt, ""),
                0.5, y+0.42, 12.0, 0.38, size=9, color=GREY_, italic=True)

        if sense:
            txt(sl, f"Sense-check: {sense}",
                0.5, 6.0, 12.0, 0.55, size=10, color=GREEN_)
        txt(sl, pkg.get("caption", ""),
            0.5, 6.75, 12.0, 0.3, size=8, color=GREY_, italic=True)
        footer(sl, slide_n); slide_n += 1

    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORT DIALOG
# ═══════════════════════════════════════════════════════════════════════════════

@st.dialog("Generate Proposal")
def show_proposal_dialog():
    """Section-picker dialog for PPTX export."""
    ctx = st.session_state.get("_as_ctx")
    if not ctx or not ctx.get("selected_segs"):
        st.error("No stack data found. Select segments and try again.")
        return

    st.caption("Select the sections to include in your PowerPoint export.")

    defaults = st.session_state.get("_as_section_defaults", {
        "brief_summary":         True,
        "segments_by_media":     True,
        "stack_summary":         True,
        "package_recommendation": True,
        "ai_commentary":         False,   # Off by default — costs AI credits
    })

    sc = st.columns(2)
    with sc[0]:
        if st.button("Select all", key="as_sel_all"):
            st.session_state["_as_section_defaults"] = {k: True for k in defaults}
            st.rerun()
    with sc[1]:
        if st.button("Deselect all", key="as_desel_all"):
            st.session_state["_as_section_defaults"] = {k: False for k in defaults}
            st.rerun()

    st.markdown("")
    s1 = st.checkbox("Brief Summary",             value=defaults.get("brief_summary", True),          key="as_cb_brief")
    s2 = st.checkbox("Matched Segments by Media", value=defaults.get("segments_by_media", True),      key="as_cb_segs")
    s3 = st.checkbox("Cross-Media Stack Summary", value=defaults.get("stack_summary", True),          key="as_cb_stack")
    s4 = st.checkbox("Package Recommendation",    value=defaults.get("package_recommendation", True), key="as_cb_pkg")
    s5 = st.checkbox(
        "AI Commentary  *(Uses AI credits)*",
        value=defaults.get("ai_commentary", False),
        key="as_cb_ai",
    )

    st.markdown("")
    bc = st.columns(2)
    with bc[0]:
        if st.button("Build Proposal", type="primary", key="as_gen_btn"):
            st.session_state["_as_section_defaults"] = {
                "brief_summary":          s1,
                "segments_by_media":      s2,
                "stack_summary":          s3,
                "package_recommendation": s4,
                "ai_commentary":          s5,
            }
            secs = st.session_state["_as_section_defaults"]
            if not any(secs.values()):
                st.warning("Select at least one section.")
                return
            with st.spinner("Building proposal deck..."):
                try:
                    buf = _build_proposal_pptx(ctx, secs)
                    st.session_state["_as_pptx"]    = buf
                    st.session_state["_as_filename"] = (
                        f"AudienceSolutions_{date.today().isoformat()}.pptx"
                    )
                except Exception as e:
                    st.error(f"Export failed: {e}")
                    return
    with bc[1]:
        if st.button("Cancel", key="as_cancel_btn"):
            st.rerun()

    if "_as_pptx" in st.session_state:
        st.success("Proposal ready!")
        st.download_button(
            "📥 Download Proposal (.pptx)",
            data=st.session_state["_as_pptx"],
            file_name=st.session_state.get("_as_filename", "AudienceSolutions_Proposal.pptx"),
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            key="as_dl_btn",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE CONTENT
# ═══════════════════════════════════════════════════════════════════════════════

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("# 🎯 Audience Solutions")
st.markdown(
    '<div class="disclaimer-bar">'
    "⚠️ Demo using fabricated segment data. Not real inventory."
    "</div>",
    unsafe_allow_html=True,
)
st.markdown(
    "Build cross-media audience packages spanning Broadcast TV, BVOD, Audio, "
    "Publishing and Digital across the Seven West Media portfolio."
)

segments   = load_segments()
desc_tuple = tuple(s["description"] for s in segments)


# ── SECTION 1: BRIEF INPUT ───────────────────────────────────────────────────
st.markdown('<hr class="sec-rule">', unsafe_allow_html=True)
st.markdown("### 1 — Client Brief")

brief_text = st.text_area(
    "Paste the client brief or campaign details",
    height=130,
    placeholder=(
        "Example: We're launching a new WA regional insurance product targeting homeowners "
        "35–60 in the Perth metro area. Six-week flight, A$90,000 budget. We need broad "
        "reach to build brand awareness, plus a news-aligned, trusted environment. "
        "AFL and morning news contexts are ideal."
    ),
    key="as_brief",
)

ci1, ci2, ci3, ci4 = st.columns([2, 2, 2, 3])
with ci1:
    budget = st.number_input(
        "Budget (A$)", min_value=0, step=1000, value=0, key="as_budget",
        help="Leave at 0 to skip the budget sense-check",
    )
with ci2:
    flight_start = st.date_input("Flight start", value=None, key="as_start")
with ci3:
    flight_end   = st.date_input("Flight end",   value=None, key="as_end")
with ci4:
    objective = st.selectbox(
        "Primary objective",
        ["Awareness", "Consideration", "Conversion"],
        key="as_objective",
    )

find_btn = st.button("🔍 Find matching segments", type="primary", key="as_find")

if find_btn:
    if not brief_text.strip():
        st.warning("Please paste a brief before searching.")
    else:
        with st.spinner("Embedding brief and scoring segments..."):
            try:
                model     = load_model()
                seg_embs  = embed_descriptions(desc_tuple)
                query_vec = model.encode(brief_text.strip())
                scored = sorted(
                    [
                        (cosine_sim(query_vec, seg_embs[i]), segments[i])
                        for i in range(len(segments))
                    ],
                    key=lambda x: x[0],
                    reverse=True,
                )
                st.session_state["as_results"] = scored
                # Clear prior selections when a new search runs
                for seg in segments:
                    st.session_state.pop(f"as_sel_{seg['segment_id']}", None)
            except Exception as e:
                st.error(f"Semantic search failed: {e}")


# ── SECTION 2: SEGMENT MATCHES ────────────────────────────────────────────────
if "as_results" in st.session_state:
    st.markdown('<hr class="sec-rule">', unsafe_allow_html=True)
    st.markdown("### 2 — Segment Matches")

    threshold = st.slider(
        "Relevance threshold — hide segments below this match score",
        min_value=0.05, max_value=0.80, value=0.15, step=0.01,
        format="%.2f", key="as_threshold",
    )

    all_results = st.session_state["as_results"]
    above_threshold = [(score, seg) for score, seg in all_results if score >= threshold]

    if not above_threshold:
        st.info("No segments meet the threshold. Try lowering the slider.")
    else:
        # Group by media type, cap at 3 per type to keep display manageable
        per_type = {}
        for score, seg in above_threshold:
            mt = seg.get("media_type", "Unknown")
            per_type.setdefault(mt, [])
            if len(per_type[mt]) < 3:
                per_type[mt].append((score, seg))

        total_shown = sum(len(v) for v in per_type.values())
        st.caption(
            f"{total_shown} segment{'s' if total_shown != 1 else ''} shown "
            f"(up to 3 per media type at or above {threshold:.0%} match). "
            "Check a segment to add it to your stack."
        )

        for mt in MEDIA_ORDER:
            type_results = per_type.get(mt, [])
            if not type_results:
                continue

            mt_bg, mt_fg = MEDIA_COLORS.get(mt, ("#888888", "#FFFFFF"))
            st.markdown(
                f'<div class="media-group-header">'
                f'<span style="font-size:14px;font-weight:700;color:{SECONDARY};">{mt}</span>'
                f'<span class="badge-media" style="background:{mt_bg};color:{mt_fg};">'
                f'{len(type_results)} segment{"s" if len(type_results) != 1 else ""}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

            for score, seg in type_results:
                sid    = seg["segment_id"]
                is_sel = st.session_state.get(f"as_sel_{sid}", False)

                card_cls  = "seg-card seg-card-selected" if is_sel else "seg-card"
                badge_cls = match_badge_class(score)
                act_html  = "".join(
                    f'<span class="badge-act">{a}</span>' for a in seg.get("activation", [])
                )
                addr_badge = (
                    '<span class="badge-act" style="background:rgba(16,185,129,0.10);'
                    f'color:{SUCCESS};">✓ Addressable</span>'
                    if seg.get("addressable")
                    else '<span class="badge-noaddr">Contextual only</span>'
                )

                col_card, col_cb = st.columns([11, 1])
                with col_card:
                    st.markdown(f"""
                    <div class="{card_cls}" style="border-top-color:{mt_bg};">
                        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:6px;">
                            <span style="font-weight:700;font-size:15px;color:{SECONDARY};">{seg['segment_name']}</span>
                            <span class="badge-media" style="background:{mt_bg};color:{mt_fg};">{mt}</span>
                            <span class="badge-cat">{seg['category']}</span>
                            <span class="{badge_cls}">{score:.0%} match</span>
                            <span class="badge-signal">{seg['signal_type']}</span>
                            {addr_badge}
                        </div>
                        <div style="color:{TEXT_SEC};font-size:12px;line-height:1.55;">{seg['description'][:280]}{'…' if len(seg['description']) > 280 else ''}</div>
                        <div style="display:flex;flex-wrap:wrap;gap:18px;margin-top:10px;align-items:flex-start;">
                            <div>
                                <div class="mlabel">Monthly Reach</div>
                                <div class="mval">{seg['reach_monthly']:,}</div>
                            </div>
                            <div>
                                <div class="mlabel">Index vs Pop</div>
                                <div class="mval">{seg['index_general_pop']:.1f}×</div>
                            </div>
                            <div>
                                <div class="mlabel">CPM Range</div>
                                <div class="mval">A${seg['indicative_cpm_min']:.0f}–A${seg['indicative_cpm_max']:.0f}</div>
                            </div>
                            <div>
                                <div class="mlabel">Min Spend</div>
                                <div class="mval">A${seg['min_spend']:,}</div>
                            </div>
                            <div>
                                <div class="mlabel">Activation</div>
                                <div style="margin-top:3px;">{act_html}</div>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                with col_cb:
                    st.markdown("<div style='margin-top:22px;'>", unsafe_allow_html=True)
                    st.checkbox(
                        "Select",
                        value=is_sel,
                        key=f"as_sel_{sid}",
                        label_visibility="collapsed",
                    )
                    st.markdown("</div>", unsafe_allow_html=True)

    # Collect all checked segments across all results (not just those shown)
    selected_segs = [
        seg for _, seg in st.session_state["as_results"]
        if st.session_state.get(f"as_sel_{seg['segment_id']}", False)
    ]


    # ── SECTION 3: CROSS-MEDIA STACK BUILDER ─────────────────────────────────
    st.markdown('<hr class="sec-rule">', unsafe_allow_html=True)
    st.markdown("### 3 — Cross-Media Stack Builder")

    if not selected_segs:
        st.info("Check segments above to add them to your stack.")
    else:
        # Derive flight_days before warning checks
        flight_days = None
        if flight_start and flight_end:
            flight_days = max(1, (flight_end - flight_start).days)

        # ── Overlap assumption sliders ─────────────────────────────────────────
        with st.expander("⚙️ Overlap assumptions (adjustable)", expanded=False):
            st.caption(
                "These sliders control the duplication assumptions used to estimate "
                "deduplicated reach. They are illustrative only — in production, "
                "overlap would be validated against OzTAM, GfK, or first-party panel data."
            )
            ov_col1, ov_col2 = st.columns(2)
            with ov_col1:
                same_group_overlap = st.slider(
                    "Overlap within same overlap_group (e.g. AFL viewers across TV/BVOD/Audio)",
                    min_value=0.30, max_value=0.95, value=0.70, step=0.05,
                    format="%.0%%", key="as_sg_overlap",
                )
            with ov_col2:
                cross_media_overlap = st.slider(
                    "Overlap across different media types with no shared group",
                    min_value=0.05, max_value=0.50, value=0.20, step=0.05,
                    format="%.0%%", key="as_cm_overlap",
                )

        # ── Core metrics ───────────────────────────────────────────────────────
        reaches   = [s["reach_monthly"]     for s in selected_segs]
        cpm_mins  = [s["indicative_cpm_min"] for s in selected_segs]
        cpm_maxs  = [s["indicative_cpm_max"] for s in selected_segs]
        min_spds  = [s["min_spend"]          for s in selected_segs]
        indexes   = [s["index_general_pop"]  for s in selected_segs]
        n_segs    = len(selected_segs)
        raw_reach = sum(reaches)

        # Deduplicated reach via transparent algorithm
        try:
            dedup_reach, incremental_by_type = estimate_deduplicated_reach(
                selected_segs, same_group_overlap, cross_media_overlap
            )
        except Exception as e:
            st.error(f"Reach estimation failed: {e}")
            dedup_reach, incremental_by_type = raw_reach, {}

        # Reach-weighted averages
        wt_cpm_min = sum(r * c for r, c in zip(reaches, cpm_mins)) / raw_reach
        wt_cpm_max = sum(r * c for r, c in zip(reaches, cpm_maxs)) / raw_reach
        wt_index   = sum(r * i for r, i in zip(reaches, indexes))  / raw_reach
        max_min_spend = max(min_spds)

        # How many distinct media types are in the stack?
        media_types_in_stack = sorted({s["media_type"] for s in selected_segs},
                                       key=lambda x: MEDIA_ORDER.index(x) if x in MEDIA_ORDER else 99)
        n_media_types = len(media_types_in_stack)

        # ── Stack summary panel ────────────────────────────────────────────────
        media_badges_html = "".join(media_badge_html(mt) for mt in media_types_in_stack)

        st.markdown(f"""
        <div class="stack-panel">
            <div style="font-weight:700;font-size:16px;color:{SECONDARY};margin-bottom:4px;">
                Stack Summary — {n_segs} segment{'s' if n_segs > 1 else ''} across {n_media_types} media type{'s' if n_media_types > 1 else ''}
            </div>
            <div style="margin-bottom:16px;">{media_badges_html}</div>
            <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:16px;">
                <div>
                    <div class="mlabel">Raw Combined Reach</div>
                    <div style="font-size:22px;font-weight:700;color:{TEXT_PRI};">{raw_reach:,}</div>
                    <div style="font-size:11px;color:{TEXT_SEC};margin-top:2px;">sum before deduplication</div>
                </div>
                <div>
                    <div class="mlabel">Est. Deduplicated Reach</div>
                    <div style="font-size:22px;font-weight:700;color:{SUCCESS};">{dedup_reach:,}</div>
                    <div style="font-size:11px;color:{TEXT_SEC};margin-top:2px;">overlap-adjusted estimate</div>
                </div>
                <div>
                    <div class="mlabel">Blended CPM</div>
                    <div style="font-size:22px;font-weight:700;color:{TEXT_PRI};">A${wt_cpm_min:.0f}–A${wt_cpm_max:.0f}</div>
                    <div style="font-size:11px;color:{TEXT_SEC};margin-top:2px;">reach-weighted average</div>
                </div>
                <div>
                    <div class="mlabel">Min Spend Required</div>
                    <div style="font-size:22px;font-weight:700;color:{TEXT_PRI};">A${max_min_spend:,}</div>
                    <div style="font-size:11px;color:{TEXT_SEC};margin-top:2px;">highest across stack</div>
                </div>
                <div>
                    <div class="mlabel">Wtd Avg Index</div>
                    <div style="font-size:22px;font-weight:700;color:{TEXT_PRI};">{wt_index:.1f}×</div>
                    <div style="font-size:11px;color:{TEXT_SEC};margin-top:2px;">vs general population</div>
                </div>
            </div>
            <div style="margin-top:12px;font-size:12px;color:{TEXT_SEC};">
                <strong>Stack:</strong> {' · '.join(s['segment_id'] for s in selected_segs)}
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(
            '<div class="dedup-note">'
            "⚠️ Estimated. Overlap assumptions are adjustable above and would be validated "
            "against panel data (OzTAM, GfK) in production. "
            f"Segments sharing an overlap group assume {same_group_overlap:.0%} duplication; "
            f"cross-media segments with no shared group assume {cross_media_overlap:.0%}. "
            "Do not present the deduplicated figure as a measured number."
            "</div>",
            unsafe_allow_html=True,
        )

        # ── Incremental reach chart ────────────────────────────────────────────
        if len(incremental_by_type) > 1:
            try:
                fig = make_incremental_reach_chart(incremental_by_type)
                if fig:
                    st.pyplot(fig, use_container_width=True)
                    plt.close(fig)
                    st.caption(
                        "Each bar shows the incremental deduplicated reach contributed by that "
                        "media type on top of the media types above it. Reflects the adjustable "
                        "overlap assumptions."
                    )
            except Exception as e:
                st.error(f"Incremental reach chart failed: {e}")

        # ── Automatic warnings ─────────────────────────────────────────────────

        # 1. Single-media stack — note incremental opportunity
        if n_media_types == 1:
            other_types = [mt for mt in MEDIA_ORDER if mt != media_types_in_stack[0]]
            st.markdown(
                f'<div class="info-box">ℹ️  Your stack uses only <strong>{media_types_in_stack[0]}</strong>. '
                f"Adding segments from {', '.join(other_types[:3])} would contribute "
                "incremental reach against audiences not reached by this channel alone. "
                "Search again and add a second media type to see the incremental reach chart.</div>",
                unsafe_allow_html=True,
            )

        # 2. Narrow deduplicated reach
        if dedup_reach < 100000:
            st.markdown(
                f'<div class="warn-box">⚠️  Estimated deduplicated reach is narrow '
                f"({dedup_reach:,} — under 100,000). This stack may be too small to "
                "deliver at scale. Consider adding a broader segment or lowering the "
                "overlap assumption sliders.</div>",
                unsafe_allow_html=True,
            )

        # 3. Budget vs available impressions
        if budget and budget > 0 and flight_days:
            mid_cpm = (wt_cpm_min + wt_cpm_max) / 2
            if mid_cpm > 0:
                implied_imps  = int((budget / mid_cpm) * 1000)
                flight_months = flight_days / 30
                avail_imps    = int(dedup_reach * flight_months)
                if implied_imps > avail_imps:
                    st.markdown(
                        f'<div class="warn-box">⚠️  Requested volume may exceed available reach. '
                        f"A${budget:,} at A${mid_cpm:.2f} blended CPM implies {implied_imps:,} impressions "
                        f"over {flight_days} days — the stack has ~{avail_imps:,} estimated "
                        "impressions available for this flight length. Consider increasing flight "
                        "length, reducing budget, or adding higher-reach segments.</div>",
                        unsafe_allow_html=True,
                    )

        # 4. Non-addressable segments in stack
        non_addr = [s for s in selected_segs if not s.get("addressable")]
        if non_addr:
            names = ", ".join(s["segment_name"] for s in non_addr[:3])
            suffix = f" +{len(non_addr)-3} more" if len(non_addr) > 3 else ""
            st.markdown(
                f'<div class="info-box">ℹ️  <strong>{len(non_addr)} segment{"s" if len(non_addr)>1 else ""} '
                f"in your stack cannot be individually targeted</strong>: {names}{suffix}. "
                "These are contextual/linear buys — they reach audiences by content alignment, "
                "not individual addressability. Frequency capping and cross-channel identity "
                "resolution are not available for these placements.</div>",
                unsafe_allow_html=True,
            )

        # 5. Notes-based stacking caveats
        stack_kws = ["do not stack", "avoid stacking", "stacking", "saturation",
                     "frequency cap", "over-invest", "exhaust"]
        seen_caveats = set()
        for seg in selected_segs:
            notes_lower = seg.get("notes", "").lower()
            if any(kw in notes_lower for kw in stack_kws):
                if seg["segment_id"] not in seen_caveats:
                    seen_caveats.add(seg["segment_id"])
                    st.markdown(
                        f'<div class="warn-box">⚠️  <strong>{seg["segment_id"]} — '
                        f'{seg["segment_name"]}:</strong> {seg["notes"][:280]}'
                        f'{"…" if len(seg["notes"]) > 280 else ""}</div>',
                        unsafe_allow_html=True,
                    )


        # ── SECTION 4: PACKAGE RECOMMENDATION ────────────────────────────────
        st.markdown('<hr class="sec-rule">', unsafe_allow_html=True)
        st.markdown("### 4 — Package Recommendation")

        try:
            pkg_rec = build_package_recommendation(
                selected_segs, budget, flight_days, objective,
                dedup_reach, wt_cpm_min, wt_cpm_max,
            )
        except Exception as e:
            st.error(f"Package recommendation failed: {e}")
            pkg_rec = {}

        if pkg_rec:
            media_list   = pkg_rec["media_types_in_stack"]
            budget_split = pkg_rec["budget_split"]
            routes       = pkg_rec["activation_route"]
            rationales   = pkg_rec["split_rationale"]
            sense_check  = pkg_rec["sense_check"]

            # Budget split table
            st.markdown(f"""
            <div class="deal-panel">
                <div style="font-weight:700;font-size:16px;color:{SECONDARY};margin-bottom:18px;">
                    Suggested Media Mix & Activation
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:18px;">
            """, unsafe_allow_html=True)

            for mt in media_list:
                mt_bg, mt_fg = MEDIA_COLORS.get(mt, ("#888888", "#FFFFFF"))
                alloc = budget_split.get(mt)
                alloc_str = f"A${alloc:,}" if alloc else "—"
                st.markdown(f"""
                    <div style="padding:12px;background:{BG_PAGE};border-radius:8px;border-left:4px solid {mt_bg};">
                        <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
                            <span class="badge-media" style="background:{mt_bg};color:{mt_fg};">{mt}</span>
                            <span style="font-size:18px;font-weight:700;color:{TEXT_PRI};">{alloc_str}</span>
                        </div>
                        <div style="font-size:12px;font-weight:600;color:{TEXT_PRI};margin-bottom:3px;">{routes.get(mt,'')}</div>
                        <div style="font-size:11px;color:{TEXT_SEC};font-style:italic;">{rationales.get(mt,'')}</div>
                    </div>
                """, unsafe_allow_html=True)

            st.markdown("</div>", unsafe_allow_html=True)

            # CPM range line
            st.markdown(f"""
                <div style="margin-top:16px;padding:10px 14px;background:{BG_PAGE};border-radius:8px;">
                    <span class="mlabel">Indicative blended CPM range</span><br>
                    <span style="font-size:20px;font-weight:700;color:{TEXT_PRI};">
                        A${wt_cpm_min:.0f} – A${wt_cpm_max:.0f}
                    </span>
                    <span style="font-size:12px;color:{TEXT_SEC};margin-left:8px;">
                        reach-weighted across selected segments
                    </span>
                </div>
            """, unsafe_allow_html=True)

            # Sense-check
            if sense_check:
                st.markdown(
                    f'<div class="sense-check"><strong>Sense-check:</strong> {sense_check}</div>',
                    unsafe_allow_html=True,
                )

            st.markdown(
                f'<div style="margin-top:12px;font-size:11px;color:{TEXT_SEC};font-style:italic;">'
                f'{pkg_rec["caption"]}</div>',
                unsafe_allow_html=True,
            )
            st.markdown("</div>", unsafe_allow_html=True)

        # Store full context for the PPTX builder
        st.session_state["_as_ctx"] = {
            "selected_segs":      selected_segs,
            "brief_text":         brief_text,
            "budget":             budget,
            "flight_start":       flight_start,
            "flight_end":         flight_end,
            "flight_days":        flight_days,
            "objective":          objective,
            "raw_reach":          raw_reach,
            "dedup_reach":        dedup_reach,
            "same_group_overlap": same_group_overlap if "as_sg_overlap" in st.session_state else 0.70,
            "cross_media_overlap": cross_media_overlap if "as_cm_overlap" in st.session_state else 0.20,
            "incremental_by_type": incremental_by_type,
            "wt_cpm_min":         wt_cpm_min,
            "wt_cpm_max":         wt_cpm_max,
            "max_min_spend":      max_min_spend,
            "wt_index":           wt_index,
            "pkg_rec":            pkg_rec,
            "sense_check":        sense_check if pkg_rec else "",
        }

        # ── SECTION 5: EXPORT ─────────────────────────────────────────────────
        st.markdown('<hr class="sec-rule">', unsafe_allow_html=True)

        col_btn, col_dl, _ = st.columns([2, 3, 4])
        with col_btn:
            if st.button("📋 Generate Proposal", type="primary", key="as_open_dialog"):
                show_proposal_dialog()
        with col_dl:
            if "_as_pptx" in st.session_state:
                st.download_button(
                    "📥 Download Proposal (.pptx)",
                    data=st.session_state["_as_pptx"],
                    file_name=st.session_state.get(
                        "_as_filename", "AudienceSolutions_Proposal.pptx"
                    ),
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    key="as_dl_persistent",
                )
