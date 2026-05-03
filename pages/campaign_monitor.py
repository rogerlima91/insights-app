import os
import re
import json
import anthropic
import streamlit as st
from datetime import date

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Campaign Monitor — Insights App", layout="wide")

# ── Global CSS (identical to app.py — STYLE LOCK) ─────────────────────────────
# STYLE LOCK: Do not remove or modify this CSS block.
st.markdown("""
<style>
    html, body, [class*="css"] {
        font-family: "Inter", system-ui, -apple-system, "Segoe UI", sans-serif;
        font-size: 15px;
        color: #374151;
    }
    .stApp { background-color: #F3F4F6; }

    [data-testid="stSidebar"] {
        background-color: #7C3AED !important;
        border-right: none !important;
    }
    [data-testid="stSidebar"] *,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] small { color: #FFFFFF !important; }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] h4 {
        color: #FFFFFF !important;
        border-left: none !important;
        padding-left: 0 !important;
        margin-top: 1rem !important;
    }
    /* Sidebar nav container — transparent with subtle border, no white bar */
    [data-testid="stSidebarNav"] {
        background: transparent !important;
        border: 1px solid rgba(255,255,255,0.3) !important;
        border-radius: 8px !important;
    }
    [data-testid="stSidebarNav"] a span {
        color: rgba(255,255,255,0.80) !important;
        font-weight: 500;
        text-transform: capitalize;
    }
    [data-testid="stSidebarNav"] a:hover span { color: #FFFFFF !important; }
    [data-testid="stSidebarNavLink"][aria-selected="true"],
    [data-testid="stSidebarNav"] a[aria-current="page"] {
        background: #FFFFFF !important;
        border-radius: 20px !important;
    }
    [data-testid="stSidebarNavLink"][aria-selected="true"] span,
    [data-testid="stSidebarNav"] a[aria-current="page"] span {
        color: #7C3AED !important;
        font-weight: 700 !important;
    }
    [data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div {
        background: rgba(255,255,255,0.15) !important;
        border-color: rgba(255,255,255,0.35) !important;
    }
    [data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.25) !important; }

    h1, h2, h3, h4, h5, h6 { font-weight: 700 !important; color: #111827 !important; }
    h2, h3 {
        margin-top: 2rem !important;
        padding-top: 0.25rem !important;
        border-bottom: none !important;
        padding-bottom: 0 !important;
        border-left: none !important;
        padding-left: 0 !important;
    }

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
    [data-testid="baseButton-primary"]:hover { background-color: #6D28D9 !important; }
</style>
""", unsafe_allow_html=True)
# STYLE LOCK

# ── Fixed demo date — matches the mock campaign data below ────────────────────
TODAY = date(2026, 5, 2)

# ── Mock campaign data ────────────────────────────────────────────────────────
# Real Captify clients running direct deals across TTD and DV360. All figures in AUD.
# dsp field: "TTD" = The Trade Desk, "DV360" = Display & Video 360
RAW_CAMPAIGNS = [
    {
        "client":    "Grey Goose AU",
        "deal_type": "PG",
        "deal_id":   "DL-44821",
        "dsp":       "TTD",
        "budget":    85_000,
        "spent":     41_200,
        "start":     date(2026, 4, 1),
        "end":       date(2026, 5, 15),
    },
    {
        "client":    "EA Games",
        "deal_type": "PMP",
        "deal_id":   "DL-52190",
        "dsp":       "DV360",
        "budget":    120_000,
        "spent":     72_000,
        "start":     date(2026, 4, 10),
        "end":       date(2026, 5, 20),
    },
    {
        "client":    "Heineken",
        "deal_type": "PG",
        "deal_id":   "DL-39847",
        "dsp":       "DV360",
        "budget":    45_000,
        "spent":     18_900,
        "start":     date(2026, 4, 15),
        "end":       date(2026, 5, 10),
    },
    {
        "client":    "eBay AU",
        "deal_type": "PMP",
        "deal_id":   "DL-61023",
        "dsp":       "TTD",
        "budget":    95_000,
        "spent":     25_800,
        "start":     date(2026, 4, 20),
        "end":       date(2026, 5, 30),
    },
    {
        "client":    "Continental Tyres",
        "deal_type": "PG",
        "deal_id":   "DL-77345",
        "dsp":       "TTD",
        "budget":    60_000,
        "spent":     19_800,
        "start":     date(2026, 4, 25),
        "end":       date(2026, 5, 8),
    },
    {
        "client":    "Bose",
        "deal_type": "PMP",
        "deal_id":   "DL-33891",
        "dsp":       "DV360",
        "budget":    150_000,
        "spent":     122_000,
        "start":     date(2026, 3, 15),
        "end":       date(2026, 5, 15),
    },
]


def calc_pacing(c):
    """
    Compute pacing index and risk tier for a single campaign.
    Pacing index = (spent / expected spend) × 100
    Expected spend = budget × (days elapsed / total days)
    """
    total_days     = (c["end"] - c["start"]).days
    days_elapsed   = (TODAY - c["start"]).days
    days_remaining = (c["end"] - TODAY).days
    expected_spend = c["budget"] * (days_elapsed / total_days) if total_days > 0 else 0
    pacing_index   = (c["spent"] / expected_spend * 100) if expected_spend > 0 else 0

    # Risk tiers: Critical < 75 | At risk 75–92 | On track 92–110 | Overpacing > 110
    if pacing_index < 75:
        risk, risk_color, risk_bg = "Critical",   "#EF4444", "#FEF2F2"
    elif pacing_index < 92:
        risk, risk_color, risk_bg = "At risk",    "#F59E0B", "#FFFBEB"
    elif pacing_index <= 110:
        risk, risk_color, risk_bg = "On track",   "#10B981", "#ECFDF5"
    else:
        risk, risk_color, risk_bg = "Overpacing", "#7C3AED", "#F5F3FF"

    return {
        **c,
        "total_days":     total_days,
        "days_elapsed":   days_elapsed,
        "days_remaining": days_remaining,
        "expected_spend": expected_spend,
        "pacing_index":   pacing_index,
        "risk":           risk,
        "risk_color":     risk_color,
        "risk_bg":        risk_bg,
    }


# Build enriched list and filter to campaigns that need attention
CAMPAIGNS = [calc_pacing(c) for c in RAW_CAMPAIGNS]
AT_RISK   = [c for c in CAMPAIGNS if c["risk"] in ("Critical", "At risk")]

# ── Deal health diagnostics (one entry per at-risk deal) ──────────────────────
# Mimics what the TTD Deal Health API or DV360 Troubleshooter API would return.
# Wording and field names reflect the platform each deal runs on.
DIAGNOSTICS = {
    "DL-44821": {  # Grey Goose AU — TTD · Critical 68.8%
        "health_score": 42,
        "source":       "TTD Deal Health API",
        "blockers": [
            {
                "rank": 1, "impact": "HIGH",
                "description": (
                    'Captify audience segment CAP-7821 "In-market: Premium Spirits" '
                    "matching only 9% of available TTD inventory — severely limiting bid opportunities"
                ),
            },
            {
                "rank": 2, "impact": "HIGH",
                "description": (
                    "Bid floor below publisher minimum on 67% of PG impressions — "
                    "effective CPM bid A$2.40 vs publisher floor A$3.80"
                ),
            },
            {
                "rank": 3, "impact": "MEDIUM",
                "description": (
                    "Frequency cap reached — average user hitting 3/day cap after just "
                    "1.2 days, exhausting available unique reach"
                ),
            },
        ],
        "segment_callout": {
            "segment":         "CAP-7821 In-market: Premium Spirits",
            "match_rate":      "9%",
            "issue":           (
                "This segment is the primary delivery bottleneck, restricting the deal "
                "to a tiny fraction of available TTD supply."
            ),
            "alternatives":    [
                "CAP-4532 Lifestyle: Entertaining & Hosting (est. 4.1× broader reach)",
                "CAP-9103 Demographic: 25–44 Affluent (est. 6.8× broader reach)",
                "CAP-2891 Interest: Wine & Spirits Lifestyle (est. 2.9× broader reach)",
            ],
            "projected_match": "~35%",
        },
    },
    "DL-39847": {  # Heineken — DV360 · Critical 61.8%
        "health_score": 35,
        "source":       "DV360 Troubleshooter API",
        "blockers": [
            {
                "rank": 1, "impact": "HIGH",
                "description": (
                    'Captify audience segment CAP-4412 "Interest: Beer & Brewing" '
                    "matching only 6% of available DV360 inventory — insufficient for required delivery pace"
                ),
            },
            {
                "rank": 2, "impact": "HIGH",
                "description": (
                    "Insertion Order pacing set to PACING_TYPE_EVEN — too conservative "
                    "for remaining budget; PACING_TYPE_AHEAD required to recover A$11,100 underspend"
                ),
            },
            {
                "rank": 3, "impact": "LOW",
                "description": (
                    "Brand safety exclusions (brand_safety_categories: ADULT, POLITICS) "
                    "blocking 38% of eligible DV360 inventory sources"
                ),
            },
        ],
        "segment_callout": {
            "segment":         "CAP-4412 Interest: Beer & Brewing",
            "match_rate":      "6%",
            "issue":           (
                "The narrowly defined beer intent segment cuts the addressable pool to "
                "~6% of the DV360 inventory source group — insufficient for the required delivery pace."
            ),
            "alternatives":    [
                "CAP-8812 Interest: Sports & Social Events (est. 3.2× broader, strong co-indexing)",
                "CAP-5560 Demographic: 18–35 Male (est. 5.1× broader reach)",
                "CAP-1190 Behavioural: Weekend Entertainment Seekers (est. 2.7× broader)",
            ],
            "projected_match": "~28%",
        },
    },
    "DL-61023": {  # eBay AU — TTD · At risk 90.5%
        "health_score": 71,
        "source":       "TTD Deal Health API",
        "blockers": [
            {
                "rank": 1, "impact": "MEDIUM",
                "description": (
                    'Captify audience segment CAP-5503 "In-market: Consumer Electronics" '
                    "matching 23% of available TTD inventory — moderate but improvable"
                ),
            },
            {
                "rank": 2, "impact": "MEDIUM",
                "description": (
                    "PMP deal fill rate at 68% — publisher supply constrained during peak "
                    "AU hours 6–10 PM AEST"
                ),
            },
            {
                "rank": 3, "impact": "LOW",
                "description": (
                    "Device bid adjustments reducing mobile bids by 40%, limiting access "
                    "to prime mobile inventory with higher CTR"
                ),
            },
        ],
        "segment_callout": {
            "segment":         "CAP-5503 In-market: Consumer Electronics",
            "match_rate":      "23%",
            "issue":           (
                "Match rate is moderate but there is meaningful upside. Adding a "
                "complementary segment could raise addressable inventory to ~51% and "
                "close the pacing gap without budget changes."
            ),
            "alternatives":    [
                "CAP-7720 Behavioural: Frequent Online Buyers (additive, est. total match ~52%)",
                "CAP-3310 Interest: Tech & Electronics Shoppers (strong eBay AU co-index)",
                "CAP-6640 Demographic: Digital Natives 18–45 (broad scale + commercial intent)",
            ],
            "projected_match": "~51%",
        },
    },
    "DL-77345": {  # Continental Tyres — TTD · Critical 61.3%, 6 days left
        "health_score": 28,
        "source":       "TTD Deal Health API",
        "blockers": [
            {
                "rank": 1, "impact": "HIGH",
                "description": (
                    'Captify audience segment CAP-9934 "In-market: Automotive" matching '
                    "only 4% of available TTD inventory — smallest addressable segment in portfolio"
                ),
            },
            {
                "rank": 2, "impact": "HIGH",
                "description": (
                    "Bid floor A$12.00 CPM vs PG publisher floor avg A$4.50 — "
                    "89% of impressions not clearing the deal"
                ),
            },
            {
                "rank": 3, "impact": "MEDIUM",
                "description": (
                    "Geo-targeting restricted to Melbourne & Sydney only, excluding "
                    "42% of AU programmatic supply"
                ),
            },
        ],
        "segment_callout": {
            "segment":         "CAP-9934 In-market: Automotive",
            "match_rate":      "4%",
            "issue":           (
                "This hyper-specific segment is critically undersized relative to the "
                "deal's required daily volume. With only 6 days left, this is the single "
                "biggest risk to delivery."
            ),
            "alternatives":    [
                "CAP-2201 In-market: Automotive (18× more inventory, retains automotive intent)",
                "CAP-4450 Intent: Car Ownership & Maintenance (est. 9× broader reach)",
                "CAP-7731 Demographic: Car Owners 30–55 (broad reach, strong proxy signal)",
            ],
            "projected_match": "~31%",
        },
    },
}

# ── Push simulator — mock API response data per at-risk deal ──────────────────
# TTD uses PATCH /v3/deal/{id} — fields: base_bid_cpm, daily_budget, pacing_mode
# DV360 uses PATCH /v2/advertisers/{id}/insertionOrders/{io_id} — fields:
#   pacing.pacingType, bidStrategy.fixedBid.bidAmountMicros, budget.budgetSegments
PUSH_DATA = {
    "DL-44821": {  # TTD
        "bid_from": 2.40,  "bid_to": 3.00,
        "budget_from": 3_142.86, "budget_to": 3_800.00,
        "recovery_aud": 8_420, "projected_pacing": 94.2, "confidence": "MEDIUM",
    },
    "DL-39847": {  # DV360
        "bid_from": 6.20,  "bid_to": 7.75,
        "budget_from": 2_250.00, "budget_to": 2_800.00,
        "recovery_aud": 4_850, "projected_pacing": 91.8, "confidence": "LOW",
    },
    "DL-61023": {  # TTD
        "bid_from": 4.80,  "bid_to": 6.00,
        "budget_from": 6_333.33, "budget_to": 6_800.00,
        "recovery_aud": 3_200, "projected_pacing": 96.1, "confidence": "HIGH",
    },
    "DL-77345": {  # TTD
        "bid_from": 4.50,  "bid_to": 5.63,
        "budget_from": 5_538.46, "budget_to": 6_500.00,
        "recovery_aud": 5_620, "projected_pacing": 88.4, "confidence": "LOW",
    },
}

# ── API key — same loading pattern as app.py ──────────────────────────────────
api_key = (
    st.secrets.get("ANTHROPIC_API_KEY")
    if "ANTHROPIC_API_KEY" in st.secrets
    else os.environ.get("ANTHROPIC_API_KEY")
)

# ── Page header ───────────────────────────────────────────────────────────────
st.title("Campaign Monitor")
st.markdown(
    "<p style='color:#6b7280;font-size:14px;margin-top:-12px;'>"
    "Live pacing, deal health diagnostics and DSP optimisation tools for Captify direct deals "
    "(TTD &amp; DV360). "
    f"All figures in AUD &nbsp;·&nbsp; Reporting date: {TODAY.strftime('%d %b %Y')}"
    "</p>",
    unsafe_allow_html=True,
)

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — Summary metric cards
# ═══════════════════════════════════════════════════════════════════════════════
st.subheader("Portfolio Overview")

# Portfolio-level pacing = total actual spend / total expected spend
total_spent      = sum(c["spent"]          for c in CAMPAIGNS)
total_expected   = sum(c["expected_spend"] for c in CAMPAIGNS)
portfolio_pacing = (total_spent / total_expected * 100) if total_expected > 0 else 0
budget_at_risk   = sum(c["budget"] for c in AT_RISK)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Active Campaigns",  len(CAMPAIGNS))
c2.metric(
    "At-Risk Campaigns",
    len(AT_RISK),
    delta=f"{len(AT_RISK)} require action",
    delta_color="inverse",
)
c3.metric("Budget at Risk",    f"A${budget_at_risk / 1_000:.0f}k")
c4.metric("Portfolio Pacing",  f"{portfolio_pacing:.1f}%")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — Pacing table
# ═══════════════════════════════════════════════════════════════════════════════
st.subheader("Pacing Dashboard")


def dsp_badge(dsp):
    """Coloured pill badge for TTD or DV360."""
    if dsp == "TTD":
        return ("<span style='background:#F5F3FF;color:#7C3AED;border-radius:4px;"
                "padding:2px 8px;font-size:11px;font-weight:700;'>TTD</span>")
    return ("<span style='background:#EFF6FF;color:#2563EB;border-radius:4px;"
            "padding:2px 8px;font-size:11px;font-weight:700;'>DV360</span>")


def deal_type_badge(deal_type):
    """Coloured pill badge for PG or PMP deal type."""
    if deal_type == "PG":
        return ("<span style='background:#F0FDF4;color:#16A34A;border-radius:4px;"
                "padding:2px 8px;font-size:11px;font-weight:700;'>PG</span>")
    return ("<span style='background:#FFF7ED;color:#EA580C;border-radius:4px;"
            "padding:2px 8px;font-size:11px;font-weight:700;'>PMP</span>")


def risk_badge(risk, risk_color, risk_bg):
    """Coloured pill badge for the risk tier."""
    return (
        f"<span style='background:{risk_bg};color:{risk_color};border-radius:4px;"
        f"padding:2px 8px;font-size:11px;font-weight:700;'>{risk}</span>"
    )


def pacing_bar(pacing_index, risk_color):
    """Inline progress bar + percentage label for the pacing column."""
    # Cap the visual bar at 100% — overpacing is communicated by the badge
    bar_pct = min(pacing_index, 100)
    return (
        f"<div style='display:flex;align-items:center;gap:8px;'>"
        f"<div style='background:#E5E7EB;border-radius:99px;height:8px;"
        f"width:130px;flex-shrink:0;'>"
        f"<div style='background:{risk_color};border-radius:99px;height:8px;"
        f"width:{bar_pct:.0f}%;'></div></div>"
        f"<span style='color:{risk_color};font-weight:700;font-size:13px;'>"
        f"{pacing_index:.1f}%</span>"
        f"</div>"
    )


def days_cell(days):
    """Days remaining — red and bold when ≤ 7 days."""
    color  = "#EF4444" if days <= 7 else "#374151"
    weight = "700"     if days <= 7 else "400"
    label  = f"{days}d" if days > 0 else "Ended"
    flag   = " ⚠" if days <= 7 else ""
    return f"<span style='color:{color};font-weight:{weight};'>{label}{flag}</span>"


# Build the HTML table row by row
rows_html = ""
for c in CAMPAIGNS:
    rows_html += (
        f"<tr style='border-bottom:1px solid #F3F4F6;'>"
        f"<td style='padding:14px 16px;font-weight:600;color:#111827;'>{c['client']}</td>"
        f"<td style='padding:14px 16px;'>{dsp_badge(c['dsp'])}</td>"
        f"<td style='padding:14px 16px;'>{deal_type_badge(c['deal_type'])}</td>"
        f"<td style='padding:14px 16px;font-size:12px;color:#6B7280;"
        f"font-family:monospace;'>{c['deal_id']}</td>"
        f"<td style='padding:14px 16px;text-align:right;'>A${c['budget']/1_000:.0f}k</td>"
        f"<td style='padding:14px 16px;text-align:right;'>A${c['spent']/1_000:.1f}k</td>"
        f"<td style='padding:14px 16px;min-width:220px;'>"
        f"{pacing_bar(c['pacing_index'], c['risk_color'])}</td>"
        f"<td style='padding:14px 16px;text-align:center;'>"
        f"{days_cell(c['days_remaining'])}</td>"
        f"<td style='padding:14px 16px;'>"
        f"{risk_badge(c['risk'], c['risk_color'], c['risk_bg'])}</td>"
        f"</tr>"
    )

st.markdown(
    f"""
    <div style='background:#FFFFFF;border-radius:12px;
                box-shadow:0 4px 12px rgba(0,0,0,0.08);overflow:hidden;'>
      <table style='width:100%;border-collapse:collapse;'>
        <thead>
          <tr style='background:#F9FAFB;border-bottom:2px solid #E5E7EB;'>
            <th style='padding:12px 16px;text-align:left;font-size:11px;color:#6B7280;
                       text-transform:uppercase;letter-spacing:0.06em;'>Client</th>
            <th style='padding:12px 16px;text-align:left;font-size:11px;color:#6B7280;
                       text-transform:uppercase;letter-spacing:0.06em;'>DSP</th>
            <th style='padding:12px 16px;text-align:left;font-size:11px;color:#6B7280;
                       text-transform:uppercase;letter-spacing:0.06em;'>Type</th>
            <th style='padding:12px 16px;text-align:left;font-size:11px;color:#6B7280;
                       text-transform:uppercase;letter-spacing:0.06em;'>Deal ID</th>
            <th style='padding:12px 16px;text-align:right;font-size:11px;color:#6B7280;
                       text-transform:uppercase;letter-spacing:0.06em;'>Budget</th>
            <th style='padding:12px 16px;text-align:right;font-size:11px;color:#6B7280;
                       text-transform:uppercase;letter-spacing:0.06em;'>Spent</th>
            <th style='padding:12px 16px;text-align:left;font-size:11px;color:#6B7280;
                       text-transform:uppercase;letter-spacing:0.06em;'>Pacing</th>
            <th style='padding:12px 16px;text-align:center;font-size:11px;color:#6B7280;
                       text-transform:uppercase;letter-spacing:0.06em;'>Days Left</th>
            <th style='padding:12px 16px;text-align:left;font-size:11px;color:#6B7280;
                       text-transform:uppercase;letter-spacing:0.06em;'>Status</th>
          </tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>
    """,
    unsafe_allow_html=True,
)

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — AI analysis
# ═══════════════════════════════════════════════════════════════════════════════
st.subheader("AI Deal Analysis")
st.markdown(
    "<p style='color:#6b7280;font-size:14px;margin-top:-8px;'>"
    "Claude reviews deal pacing as a senior programmatic specialist at Captify, "
    "covering both TTD and DV360.</p>",
    unsafe_allow_html=True,
)

if st.button("✨ Run AI Analysis", type="primary"):
    if not api_key:
        st.warning(
            "No Anthropic API key found. Add `ANTHROPIC_API_KEY` to your "
            "Streamlit secrets or environment variables."
        )
    else:
        # Build plain-text pacing summary including DSP for each campaign
        lines = []
        for c in CAMPAIGNS:
            lines.append(
                f"- {c['client']} | DSP: {c['dsp']} | {c['deal_type']} | {c['deal_id']} | "
                f"Budget: A${c['budget']:,} | Spent: A${c['spent']:,} | "
                f"Expected to date: A${c['expected_spend']:,.0f} | "
                f"Pacing index: {c['pacing_index']:.1f}% ({c['risk']}) | "
                f"Days remaining: {c['days_remaining']}"
            )
        deal_summary = "\n".join(lines)

        prompt = (
            "You are a senior programmatic specialist at Captify reviewing direct deals "
            "running across The Trade Desk (TTD) and Display & Video 360 (DV360) "
            "for the Australian market.\n\n"
            f"Today is {TODAY.strftime('%d %B %Y').lstrip('0')}. Current deal pacing:\n\n"
            f"{deal_summary}\n\n"
            "Provide a structured analysis with exactly these three sections:\n\n"
            "**Priority Flags**\n"
            "List campaigns needing immediate action, ranked by urgency. For each, "
            "state the DSP, AUD underspend to date, days remaining, and consequence of inaction.\n\n"
            "**Recommended Actions by Campaign**\n"
            "For each at-risk or critical campaign, give 2–3 specific DSP actions "
            "appropriate to its platform (TTD: bid adjustments, pacing mode; "
            "DV360: insertionOrder pacing type, bid strategy, budget segments). "
            "Reference the deal ID and specific AUD figures.\n\n"
            "**Portfolio Insight**\n"
            "One paragraph identifying any portfolio-wide pattern — including whether "
            "TTD or DV360 deals are performing differently. "
            "End with one cross-platform portfolio-level recommendation.\n\n"
            "Use only the data provided. Be specific with AUD amounts and percentages."
        )

        client_ai = anthropic.Anthropic(api_key=api_key)
        with st.spinner("Analysing deal pacing…"):
            response = client_ai.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1000,
                system=(
                    "You are a senior programmatic advertising specialist at Captify, "
                    "expert in both TTD and DV360 deal management, PG and PMP deal structures, "
                    "and Australian programmatic advertising. Be concise, specific, "
                    "and action-oriented. Always cite deal IDs, DSP names, and AUD figures."
                ),
                messages=[{"role": "user", "content": prompt}],
            )
        # Store the response so it persists when Streamlit re-runs the page
        st.session_state["cm_ai_analysis"] = response.content[0].text.strip()

# Show the analysis if it has been generated (persists across re-renders)
if "cm_ai_analysis" in st.session_state:
    # Convert **bold** markdown to HTML bold, then wrap in a white card
    analysis_html = re.sub(
        r"\*\*(.+?)\*\*",
        r'<strong style="color:#111827;">\1</strong>',
        st.session_state["cm_ai_analysis"],
    ).replace("\n", "<br>")

    st.markdown(
        f"<div style='background:#FFFFFF;border-radius:12px;padding:24px;"
        f"box-shadow:0 4px 12px rgba(0,0,0,0.08);margin-top:12px;"
        f"font-family:-apple-system,Segoe UI,Roboto,sans-serif;"
        f"font-size:14px;line-height:1.85;color:#374151;'>"
        f"{analysis_html}</div>",
        unsafe_allow_html=True,
    )

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — Delivery troubleshooter
# ═══════════════════════════════════════════════════════════════════════════════
st.subheader("Delivery Troubleshooter")
st.markdown(
    "<p style='color:#6b7280;font-size:14px;margin-top:-8px;'>"
    "Deal health diagnostics for at-risk campaigns. "
    "TTD deals source from the TTD Deal Health API; "
    "DV360 deals source from the DV360 Troubleshooter API.</p>",
    unsafe_allow_html=True,
)

# Impact badge colour map: impact level → (background, foreground)
IMPACT_STYLE = {
    "HIGH":   ("#FEF2F2", "#EF4444"),
    "MEDIUM": ("#FFFBEB", "#F59E0B"),
    "LOW":    ("#F0FDF4", "#10B981"),
}


def health_score_colour(score):
    """Return a hex colour for the deal health score gauge."""
    if score < 40:
        return "#EF4444"
    if score < 70:
        return "#F59E0B"
    return "#10B981"


for c in AT_RISK:
    diag  = DIAGNOSTICS[c["deal_id"]]
    score = diag["health_score"]
    seg   = diag["segment_callout"]
    sc    = health_score_colour(score)
    tier  = "CRITICAL" if score < 40 else "POOR" if score < 70 else "FAIR"

    with st.expander(
        f"{c['client']}  ·  {c['dsp']}  ·  {c['deal_id']}  ·  "
        f"{c['risk']}  ·  {c['days_remaining']}d remaining",
        expanded=False,
    ):
        # Show which API source this diagnostic came from
        st.markdown(
            f"<div style='font-size:11px;color:#6B7280;margin-bottom:12px;'>"
            f"Source: <strong>{diag['source']}</strong></div>",
            unsafe_allow_html=True,
        )

        col_score, col_blockers = st.columns([1, 3])

        # ── Health score gauge ────────────────────────────────────────────────
        with col_score:
            st.markdown(
                f"<div style='background:#FFFFFF;border-radius:12px;padding:20px;"
                f"box-shadow:0 2px 8px rgba(0,0,0,0.06);text-align:center;'>"
                f"<div style='font-size:11px;font-weight:600;color:#6B7280;"
                f"text-transform:uppercase;letter-spacing:0.05em;margin-bottom:8px;'>"
                f"Deal Health Score</div>"
                f"<div style='font-size:52px;font-weight:800;color:{sc};line-height:1;'>"
                f"{score}</div>"
                f"<div style='font-size:13px;color:#9CA3AF;margin-top:2px;'>/100</div>"
                f"<div style='font-size:12px;color:{sc};margin-top:10px;"
                f"font-weight:700;'>{tier}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

        # ── Top 3 blockers ────────────────────────────────────────────────────
        with col_blockers:
            st.markdown(
                "<div style='font-size:11px;font-weight:600;color:#6B7280;"
                "text-transform:uppercase;letter-spacing:0.05em;margin-bottom:10px;'>"
                "Top Blockers by Impact</div>",
                unsafe_allow_html=True,
            )
            for b in diag["blockers"]:
                bg, fg = IMPACT_STYLE[b["impact"]]
                st.markdown(
                    f"<div style='background:#FFFFFF;border:1px solid #E5E7EB;"
                    f"border-left:4px solid {fg};border-radius:8px;"
                    f"padding:12px 14px;margin-bottom:8px;"
                    f"display:flex;align-items:flex-start;gap:10px;'>"
                    f"<span style='background:{bg};color:{fg};border-radius:4px;"
                    f"padding:2px 7px;font-size:10px;font-weight:700;white-space:nowrap;'>"
                    f"#{b['rank']} {b['impact']}</span>"
                    f"<span style='font-size:13px;color:#374151;line-height:1.6;'>"
                    f"{b['description']}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        # ── Captify segment impact callout ────────────────────────────────────
        alts_html = "&nbsp;&nbsp;·&nbsp;&nbsp;".join(
            f"<strong>{a}</strong>" for a in seg["alternatives"]
        )
        st.markdown(
            f"<div style='background:#F0F9FF;border:1px solid #BAE6FD;"
            f"border-radius:8px;padding:14px 16px;margin-top:12px;'>"
            f"<div style='font-size:11px;font-weight:700;color:#0369A1;"
            f"text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px;'>"
            f"Captify Segment Impact</div>"
            f"<div style='font-size:13px;color:#0C4A6E;margin-bottom:6px;'>"
            f"<strong>{seg['segment']}</strong> — inventory match rate: "
            f"<strong>{seg['match_rate']}</strong><br>"
            f"<span style='color:#374151;'>{seg['issue']}</span></div>"
            f"<div style='font-size:13px;color:#0369A1;'>"
            f"Recommended alternatives: {alts_html}</div>"
            f"<div style='font-size:12px;color:#0369A1;margin-top:4px;'>"
            f"Projected match rate after swap: <strong>{seg['projected_match']}</strong>"
            f"</div></div>",
            unsafe_allow_html=True,
        )

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — DSP push simulator
# ═══════════════════════════════════════════════════════════════════════════════
st.subheader("DSP Push Simulator")
st.markdown(
    "<p style='color:#6b7280;font-size:14px;margin-top:-8px;'>"
    "Simulate a platform API call to optimise underperforming deals. "
    "TTD uses <code>PATCH /v3/deal/{id}</code> &nbsp;·&nbsp; "
    "DV360 uses <code>PATCH /v2/advertisers/{id}/insertionOrders/{io_id}</code>. "
    "<strong>Simulation only — no real changes are made.</strong></p>",
    unsafe_allow_html=True,
)

for c in AT_RISK:
    pd_  = PUSH_DATA[c["deal_id"]]
    is_dv360 = c["dsp"] == "DV360"

    col_btn, col_resp = st.columns([1, 3])

    with col_btn:
        if st.button(
            f"⚡ PATCH {c['deal_id']}",
            key=f"push_{c['deal_id']}",
            type="primary",
        ):
            st.session_state[f"pushed_{c['deal_id']}"] = True

        # Campaign summary below the button
        remaining_budget = c["budget"] - c["spent"]
        risk_color = c["risk_color"]
        risk_label = c["risk"]
        st.markdown(
            f"<div style='font-size:12px;color:#6B7280;margin-top:8px;line-height:1.7;'>"
            f"<strong style='color:#111827;'>{c['client']}</strong><br>"
            f"{c['dsp']} &nbsp;·&nbsp; {c['deal_type']}<br>"
            f"Pacing: {c['pacing_index']:.1f}% "
            f"<span style='color:{risk_color};font-weight:700;'>({risk_label})</span><br>"
            f"Remaining: A${remaining_budget/1_000:.1f}k &nbsp;·&nbsp; {c['days_remaining']}d left"
            f"</div>",
            unsafe_allow_html=True,
        )

    with col_resp:
        if st.session_state.get(f"pushed_{c['deal_id']}"):
            budget_change_pct = (
                (pd_["budget_to"] - pd_["budget_from"]) / pd_["budget_from"] * 100
            )
            recovery_note = (
                "Low confidence due to compressed flight end — monitor daily for first 48h"
                if pd_["confidence"] == "LOW"
                else "Monitor pacing daily to avoid overspend"
            )

            if is_dv360:
                # DV360 API response — uses DV360 field names and micros for bid amounts
                # bidAmountMicros: $1.00 = 1,000,000 micros
                bid_from_micros = int(pd_["bid_from"] * 1_000_000)
                bid_to_micros   = int(pd_["bid_to"]   * 1_000_000)
                mock_response = {
                    "status":              200,
                    "message":             "Insertion order updated successfully",
                    "advertiserId":        "7841209",
                    "insertionOrderId":    c["deal_id"],
                    "advertiser":          c["client"],
                    "endpoint":            f"PATCH /v2/advertisers/7841209/insertionOrders/{c['deal_id']}",
                    "changes_applied": {
                        "pacing": {
                            "from": {"pacingPeriod": "PACING_PERIOD_DAILY", "pacingType": "PACING_TYPE_EVEN"},
                            "to":   {"pacingPeriod": "PACING_PERIOD_DAILY", "pacingType": "PACING_TYPE_AHEAD"},
                        },
                        "bidStrategy": {
                            "fixedBid": {
                                "from": {"bidAmountMicros": bid_from_micros},
                                "to":   {"bidAmountMicros": bid_to_micros},
                                "change": "+25.0%",
                            }
                        },
                        "budget_daily_aud": {
                            "from":   round(pd_["budget_from"], 2),
                            "to":     round(pd_["budget_to"],   2),
                            "change": f"+{budget_change_pct:.1f}%",
                        },
                    },
                    "estimated_recovery": {
                        "additional_spend_aud":       pd_["recovery_aud"],
                        "projected_end_pacing_index": pd_["projected_pacing"],
                        "confidence":                 pd_["confidence"],
                        "note":                       recovery_note,
                    },
                    "timestamp": f"{TODAY.isoformat()}T09:14:32+10:00",
                }
            else:
                # TTD API response — uses TTD field names
                mock_response = {
                    "status":     200,
                    "message":    "Deal updated successfully",
                    "deal_id":    c["deal_id"],
                    "advertiser": c["client"],
                    "endpoint":   f"PATCH /v3/deal/{c['deal_id']}",
                    "changes_applied": {
                        "base_bid_cpm_aud": {
                            "from":   pd_["bid_from"],
                            "to":     pd_["bid_to"],
                            "change": "+25.0%",
                        },
                        "daily_budget_aud": {
                            "from":   round(pd_["budget_from"], 2),
                            "to":     round(pd_["budget_to"],   2),
                            "change": f"+{budget_change_pct:.1f}%",
                        },
                        "pacing_mode": {
                            "from": "EVEN",
                            "to":   "AGGRESSIVE",
                        },
                        "bid_shading": {
                            "from": "ENABLED",
                            "to":   "DISABLED",
                        },
                    },
                    "estimated_recovery": {
                        "additional_spend_aud":       pd_["recovery_aud"],
                        "projected_end_pacing_index": pd_["projected_pacing"],
                        "confidence":                 pd_["confidence"],
                        "note":                       recovery_note,
                    },
                    "timestamp": f"{TODAY.isoformat()}T09:14:32+10:00",
                }

            st.code(json.dumps(mock_response, indent=2), language="json")
        else:
            # Placeholder shown before the button is clicked
            st.markdown(
                "<div style='background:#F9FAFB;border:1px dashed #D1D5DB;"
                "border-radius:8px;padding:28px;text-align:center;"
                "color:#9CA3AF;font-size:13px;'>"
                "Click the button to simulate the DSP PATCH call and see the "
                "projected API response.</div>",
                unsafe_allow_html=True,
            )

    st.markdown(
        "<hr style='border:none;border-top:1px solid #E5E7EB;margin:20px 0;'>",
        unsafe_allow_html=True,
    )

print("Campaign Monitor loaded.")
