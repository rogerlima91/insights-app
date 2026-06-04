import os
import json
import pandas as pd
import streamlit as st
from datetime import date, timedelta

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
TODAY = date(2026, 6, 4)

# ── Mock campaign data ─────────────────────────────────────────────────────────
# Optus campaigns running across DV360, TTD, and Amazon DSP. All figures in AUD.
# Flight dates: 2026-05-01 → 2026-07-31 (91 days total).
# As of 2026-06-04 (day 34 of 91, 37.4% elapsed) spent values below give
# a realistic mix of Critical / At risk / On track / Overpacing.
RAW_CAMPAIGNS = [
    {
        "client":        "Optus",
        "campaign_name": "Optus — Mobile Plans Winter Offer — Display",
        "buy_type":      "PG",
        "campaign_id":   "IO-881421",
        "dsp":           "DV360",
        "budget":        110_000,
        "spent":         33_000,   # pacing ~80% → At risk
        "start":         date(2026, 5, 1),
        "end":           date(2026, 7, 31),
    },
    {
        "client":        "Optus",
        "campaign_name": "Optus | NBN Broadband | Prospecting | AU | May-Jul 2026",
        "buy_type":      "PMP",
        "campaign_id":   "CMP-774032",
        "dsp":           "TTD",
        "budget":        85_000,
        "spent":         19_100,   # pacing ~60% → Critical
        "start":         date(2026, 5, 1),
        "end":           date(2026, 7, 31),
    },
    {
        "client":        "Optus",
        "campaign_name": "Optus — Business Solutions Q2 2026 — B2B Display",
        "buy_type":      "PG",
        "campaign_id":   "IO-882155",
        "dsp":           "DV360",
        "budget":        60_000,
        "spent":         13_500,   # pacing ~60% → Critical
        "start":         date(2026, 5, 1),
        "end":           date(2026, 7, 31),
    },
    {
        "client":        "Optus",
        "campaign_name": "Optus | Entertainment Bundle | Retargeting | AU | May-Jul 2026",
        "buy_type":      "PMP",
        "campaign_id":   "CMP-774581",
        "dsp":           "TTD",
        "budget":        45_000,
        "spent":         16_500,   # pacing ~98% → On track
        "start":         date(2026, 5, 1),
        "end":           date(2026, 7, 31),
    },
    {
        "client":        "Optus",
        "campaign_name": "Optus_CTV_BrandAwareness_2026Q2",
        "buy_type":      "PMP",
        "campaign_id":   "AMZ-330921",
        "dsp":           "Amazon DSP",
        "budget":        75_000,
        "spent":         29_500,   # pacing ~105% → On track
        "start":         date(2026, 5, 1),
        "end":           date(2026, 7, 31),
    },
    {
        "client":        "Optus",
        "campaign_name": "Optus — Mobile Handset Upgrade — Mid 2026",
        "buy_type":      "PG",
        "campaign_id":   "IO-883047",
        "dsp":           "DV360",
        "budget":        95_000,
        "spent":         19_500,   # pacing ~55% → Critical
        "start":         date(2026, 5, 1),
        "end":           date(2026, 7, 31),
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


# Build enriched mock data (used as fallback when no files are uploaded)
MOCK_CAMPAIGNS = [calc_pacing(c) for c in RAW_CAMPAIGNS]

# ── Mock campaign and line item breakdown per campaign ID ─────────────────────
# Budgets and spends at each level sum to the client totals in RAW_CAMPAIGNS.
MOCK_CAMPAIGN_BREAKDOWN = {
    "IO-881421": {  # Optus DV360 — Mobile Plans — budget 110k, spent 33k
        "campaigns": [
            {
                "name":   "Optus — Mobile Plans — Brand Awareness — Display",
                "budget": 70_000, "spent": 21_000,
                "line_items": [
                    {"name": "Prospecting Display — Desktop",          "budget": 28_000, "spent":  9_500},
                    {"name": "In-Market Telecom Switchers — Mobile",   "budget": 24_000, "spent":  7_500},
                    {"name": "YouTube TrueView — All Devices",         "budget": 18_000, "spent":  4_000},
                ],
            },
            {
                "name":   "Optus — Mobile Plans — Retargeting",
                "budget": 40_000, "spent": 12_000,
                "line_items": [
                    {"name": "Site Retargeting — Display",             "budget": 22_000, "spent":  7_200},
                    {"name": "CRM Match — Programmatic Display",       "budget": 18_000, "spent":  4_800},
                ],
            },
        ],
    },
    "CMP-774032": {  # Optus TTD — NBN Broadband — budget 85k, spent 19.1k
        "campaigns": [
            {
                "name":   "Optus | NBN Broadband | Prospecting | Display | AU",
                "budget": 55_000, "spent": 12_500,
                "line_items": [
                    {"name": "In-Market Broadband Researchers — Desktop", "budget": 22_000, "spent":  5_500},
                    {"name": "Home Movers Audience — Display",            "budget": 18_000, "spent":  4_000},
                    {"name": "Tech Enthusiasts — Mobile",                 "budget": 15_000, "spent":  3_000},
                ],
            },
            {
                "name":   "Optus | NBN Broadband | Retargeting | Video | AU",
                "budget": 30_000, "spent":  6_600,
                "line_items": [
                    {"name": "Site Visitors — Pre-roll Video",            "budget": 18_000, "spent":  3_800},
                    {"name": "Cart Abandoners — Display",                 "budget": 12_000, "spent":  2_800},
                ],
            },
        ],
    },
    "IO-882155": {  # Optus DV360 — Business Solutions — budget 60k, spent 13.5k
        "campaigns": [
            {
                "name":   "Optus — Business Solutions — SMB Prospecting — Display",
                "budget": 38_000, "spent":  8_600,
                "line_items": [
                    {"name": "SMB Decision Makers — Desktop Display",     "budget": 16_000, "spent":  3_800},
                    {"name": "LinkedIn Matched Audience — Programmatic",  "budget": 12_000, "spent":  2_800},
                    {"name": "Business Context Targeting — Mobile",       "budget": 10_000, "spent":  2_000},
                ],
            },
            {
                "name":   "Optus — Business Solutions — Enterprise Video",
                "budget": 22_000, "spent":  4_900,
                "line_items": [
                    {"name": "Enterprise Audience — CTV",                 "budget": 13_000, "spent":  2_900},
                    {"name": "IT Decision Makers — Pre-roll",             "budget":  9_000, "spent":  2_000},
                ],
            },
        ],
    },
    "CMP-774581": {  # Optus TTD — Entertainment Bundle — budget 45k, spent 16.5k
        "campaigns": [
            {
                "name":   "Optus | Entertainment Bundle | Sports Context | Display | AU",
                "budget": 28_000, "spent": 10_300,
                "line_items": [
                    {"name": "Sports Fans — Desktop Display",             "budget": 12_000, "spent":  4_600},
                    {"name": "Streaming Intent Audience — Mobile",        "budget": 10_000, "spent":  3_800},
                    {"name": "Premium Content — Video Pre-roll",          "budget":  6_000, "spent":  1_900},
                ],
            },
            {
                "name":   "Optus | Entertainment Bundle | Retargeting | All Formats | AU",
                "budget": 17_000, "spent":  6_200,
                "line_items": [
                    {"name": "Optus Website Visitors — Display",          "budget": 10_000, "spent":  3_900},
                    {"name": "App Download Intent — Mobile",              "budget":  7_000, "spent":  2_300},
                ],
            },
        ],
    },
    "AMZ-330921": {  # Optus Amazon DSP — CTV Brand Awareness — budget 75k, spent 29.5k
        "campaigns": [
            {
                "name":   "Optus_CTV_BrandAwareness_PrimeTime_2026Q2",
                "budget": 48_000, "spent": 19_000,
                "line_items": [
                    {"name": "Optus_CTV_PrimeTime_AU",                   "budget": 28_000, "spent": 11_500},
                    {"name": "Optus_CTV_SportStreaming_AU",               "budget": 20_000, "spent":  7_500},
                ],
            },
            {
                "name":   "Optus_Display_BrandAwareness_2026Q2",
                "budget": 27_000, "spent": 10_500,
                "line_items": [
                    {"name": "Optus_Display_InMarket_AU",                 "budget": 16_000, "spent":  6_300},
                    {"name": "Optus_Display_Behavioural_AU",              "budget": 11_000, "spent":  4_200},
                ],
            },
        ],
    },
    "IO-883047": {  # Optus DV360 — Mobile Handset Upgrade — budget 95k, spent 19.5k
        "campaigns": [
            {
                "name":   "Optus — Handset Upgrade — Trade-In Offer — Display",
                "budget": 60_000, "spent": 12_300,
                "line_items": [
                    {"name": "Current Mobile Customers — Desktop",        "budget": 25_000, "spent":  5_600},
                    {"name": "Handset Intenders — Mobile Display",        "budget": 20_000, "spent":  4_300},
                    {"name": "Tech Upgrade Audience — Video Pre-roll",    "budget": 15_000, "spent":  2_400},
                ],
            },
            {
                "name":   "Optus — Handset Upgrade — Retargeting",
                "budget": 35_000, "spent":  7_200,
                "line_items": [
                    {"name": "Store & Web Visitors — Display",            "budget": 20_000, "spent":  4_800},
                    {"name": "Product Page Visitors — Mobile",            "budget": 15_000, "spent":  2_400},
                ],
            },
        ],
    },
}

# ── Campaign health diagnostics (one entry per at-risk campaign) ───────────────
# Mimics what the TTD Deal Health API, DV360 Troubleshooter API, or Amazon DSP
# reporting would return for campaigns with delivery issues.
DIAGNOSTICS = {
    "IO-881421": {  # Optus DV360 — Mobile Plans — At risk 75.3%
        "health_score": 62,
        "source":       "DV360 Troubleshooter API",
        "blockers": [
            {
                "rank": 1, "impact": "HIGH",
                "description": (
                    "Insertion order pacing set to PACING_TYPE_EVEN — too conservative; "
                    "switch to PACING_TYPE_AHEAD to recover A$17,200 underspend over 18 days remaining"
                ),
            },
            {
                "rank": 2, "impact": "HIGH",
                "description": (
                    "Audience targeting match rate 12% — In-Market: Telco Switchers segment "
                    "narrowing available DV360 inventory to a small addressable pool"
                ),
            },
            {
                "rank": 3, "impact": "MEDIUM",
                "description": (
                    "Brand safety exclusions blocking 28% of eligible premium publisher inventory; "
                    "POLITICS and GAMBLING categories applied more broadly than required"
                ),
            },
        ],
        "targeting_callout": {
            "segment":         "In-Market: Telco Switchers",
            "match_rate":      "12%",
            "issue":           (
                "Narrow intent segment limiting addressable DV360 inventory; "
                "broadening to complementary audiences could raise match rate to ~38% "
                "without sacrificing relevance."
            ),
            "alternatives":    [
                "In-Market: Broadband & Internet Plans (est. 3.4× broader reach)",
                "Demographic: 25–44 Urban Professionals (est. 5.2× broader reach)",
                "Behavioural: Mobile Plan Researchers (est. 2.8× broader reach)",
            ],
            "projected_match": "~38%",
        },
    },
    "CMP-774032": {  # Optus TTD — NBN Broadband — At risk 77.2%
        "health_score": 55,
        "source":       "TTD Deal Health API",
        "blockers": [
            {
                "rank": 1, "impact": "HIGH",
                "description": (
                    "PMP fill rate 61% — publisher supply constrained during peak AU hours "
                    "6–10 PM AEST; bid floor A$3.20 below publisher minimum A$4.50 on 44% of impressions"
                ),
            },
            {
                "rank": 2, "impact": "HIGH",
                "description": (
                    "Frequency cap reached — average user hitting 3/day cap after 1.4 days, "
                    "exhausting unique reach faster than new users are entering the pool"
                ),
            },
            {
                "rank": 3, "impact": "MEDIUM",
                "description": (
                    "Pacing mode set to EVEN — insufficient to recover A$12,200 underspend "
                    "with 13 days remaining; switch to AGGRESSIVE pacing recommended"
                ),
            },
        ],
        "targeting_callout": {
            "segment":         "NBN Researchers — Search Behavioural",
            "match_rate":      "18%",
            "issue":           (
                "Behavioural segment built on search intent is too narrow for the available "
                "PMP inventory pool. Expanding to broader home-internet audiences "
                "could raise addressable reach to ~44%."
            ),
            "alternatives":    [
                "In-Market: Home Internet & Broadband (est. 2.6× broader, retains intent signal)",
                "Demographic: Homeowners 30–55 (strong NBN co-index, est. 4.1× broader)",
                "Behavioural: Frequent Online Streamers (est. 2.2× broader, relevant proxy)",
            ],
            "projected_match": "~44%",
        },
    },
    "IO-882155": {  # Optus DV360 — Business Solutions — Critical 60.8%
        "health_score": 31,
        "source":       "DV360 Troubleshooter API",
        "blockers": [
            {
                "rank": 1, "impact": "HIGH",
                "description": (
                    "Audience targeting match rate 5% — SMB Decision Makers segment "
                    "is critically undersized relative to the required daily impression volume"
                ),
            },
            {
                "rank": 2, "impact": "HIGH",
                "description": (
                    "Geo-targeting restricted to Sydney CBD only — excluding 71% of AU programmatic "
                    "supply; Melbourne and Brisbane represent major untapped B2B markets"
                ),
            },
            {
                "rank": 3, "impact": "MEDIUM",
                "description": (
                    "Viewability threshold set to 80%+ — reducing eligible inventory pool significantly; "
                    "industry standard for B2B display is 70%"
                ),
            },
        ],
        "targeting_callout": {
            "segment":         "SMB Decision Makers — B2B Intent",
            "match_rate":      "5%",
            "issue":           (
                "Hyper-specific B2B segment is severely undersized. With only 8 days remaining, "
                "this is the single biggest risk to delivery. Geo-restriction compounds the problem."
            ),
            "alternatives":    [
                "Business Professionals 30–55 (est. 8× broader, strong B2B proxy)",
                "In-Market: Business Software & Services (retains intent, est. 5× broader)",
                "LinkedIn Audience Match — Programmatic (precise but needs list refresh)",
            ],
            "projected_match": "~29%",
        },
    },
    "IO-883047": {  # Optus DV360 — Handset Upgrade — Critical 57.4%, 6 days left
        "health_score": 22,
        "source":       "DV360 Troubleshooter API",
        "blockers": [
            {
                "rank": 1, "impact": "HIGH",
                "description": (
                    "Severe underpacing with only 6 days remaining — A$65,600 unspent against "
                    "A$95,000 budget; PACING_TYPE_EVEN cannot recover at current daily run rate"
                ),
            },
            {
                "rank": 2, "impact": "HIGH",
                "description": (
                    "Creative approval pending for 3 of 5 ad formats — limiting available ad server "
                    "inventory and preventing full line item activation"
                ),
            },
            {
                "rank": 3, "impact": "HIGH",
                "description": (
                    "Bid floor A$5.50 below publisher minimum A$7.20 on 62% of targeted inventory; "
                    "effective CPM uncompetitive for premium handset-adjacent placements"
                ),
            },
        ],
        "targeting_callout": {
            "segment":         "Current Mobile Customers — Upgrade Intent",
            "match_rate":      "21%",
            "issue":           (
                "Match rate is moderate but creative approval blockers and low bid floors mean "
                "even the addressable audience is not being reached. Resolving creative and bid "
                "issues is the immediate priority before audience expansion."
            ),
            "alternatives":    [
                "Handset Upgrade Intenders — Broad (est. 2.9× broader, retains commercial signal)",
                "Tech Early Adopters 25–45 (est. 4.7× broader, strong device upgrade co-index)",
                "Telco Contract Renewal Window — Behavioural (precision timing signal)",
            ],
            "projected_match": "~41%",
        },
    },
}

# ── Delivery push data — mock API response values per at-risk campaign ─────────
# TTD: PATCH /v3/deal/{id} — fields: base_bid_cpm, daily_budget, pacing_mode
# DV360: PATCH /v2/advertisers/{id}/insertionOrders/{io_id}
# Amazon DSP: PATCH /dsp/campaigns/{id}
PUSH_DATA = {
    "IO-881421": {  # DV360
        "bid_from": 3.20,  "bid_to": 4.00,
        "budget_from": 5_238.10, "budget_to": 6_300.00,
        "recovery_aud": 9_800, "projected_pacing": 93.4, "confidence": "MEDIUM",
    },
    "CMP-774032": {  # TTD
        "bid_from": 3.20,  "bid_to": 4.50,
        "budget_from": 5_588.24, "budget_to": 6_500.00,
        "recovery_aud": 7_600, "projected_pacing": 92.1, "confidence": "MEDIUM",
    },
    "IO-882155": {  # DV360
        "bid_from": 6.20,  "bid_to": 7.75,
        "budget_from": 3_000.00, "budget_to": 3_800.00,
        "recovery_aud": 5_200, "projected_pacing": 89.6, "confidence": "LOW",
    },
    "IO-883047": {  # DV360
        "bid_from": 5.50,  "bid_to": 7.15,
        "budget_from": 10_923.08, "budget_to": 13_500.00,
        "recovery_aud": 14_200, "projected_pacing": 86.2, "confidence": "LOW",
    },
}

# ── Performance data — KPI diagnostics and optimisation push per campaign ──────
PERFORMANCE_DATA = {
    "IO-881421": {
        "performance_score": 52,
        "issues": [
            {"rank": 1, "impact": "HIGH",
             "description": "CTR 0.04% — below display benchmark 0.08%; creative fatigue after 14 days without asset rotation"},
            {"rank": 2, "impact": "HIGH",
             "description": "CPM A$18.20 running 34% above planned A$13.60; narrow targeting driving premium inventory costs"},
            {"rank": 3, "impact": "MEDIUM",
             "description": "Mobile serving 71% of impressions vs planned 50/50 split; desktop line items underperforming"},
        ],
        "recommendations": [
            "Rotate display creative — introduce 3 new banner variants to counter frequency fatigue",
            "Broaden audience targeting to reduce CPM inflation — add broadband-to-mobile switcher segments",
            "Increase desktop line item bids by 15% to rebalance impression distribution",
        ],
        "push_data": {
            "optimisation": "Creative rotation + audience broadening + desktop bid uplift",
            "projected_ctr": "0.07%", "projected_cpm": "A$15.40", "confidence": "MEDIUM",
        },
    },
    "CMP-774032": {
        "performance_score": 61,
        "issues": [
            {"rank": 1, "impact": "HIGH",
             "description": "PMP fill rate 61% during peak AU hours 6–10 PM AEST; publisher supply too constrained for evening inventory"},
            {"rank": 2, "impact": "MEDIUM",
             "description": "VTR 38% on pre-roll video units — below 50% benchmark; creative hook not landing in first 5 seconds"},
            {"rank": 3, "impact": "LOW",
             "description": "Bid shading reducing effective CPM competitiveness on priority PMP packages during peak demand"},
        ],
        "recommendations": [
            "Add 2–3 alternative PMP packages for evening hours to improve fill rate",
            "A/B test video creative opening — lead message should land within first 3 seconds",
            "Disable bid shading on PMP deals to maximise fill during constrained inventory windows",
        ],
        "push_data": {
            "optimisation": "PMP package expansion + bid shading disabled + video creative refresh",
            "projected_ctr": "0.06%", "projected_cpm": "A$16.20", "confidence": "MEDIUM",
        },
    },
    "IO-882155": {
        "performance_score": 38,
        "issues": [
            {"rank": 1, "impact": "HIGH",
             "description": "Severe underdelivery — 41% of budgeted impressions served; insufficient data volume for reliable performance analysis"},
            {"rank": 2, "impact": "HIGH",
             "description": "CTR 0.02% — extremely low for B2B display; likely wrong audience mix for business decision-maker targeting"},
            {"rank": 3, "impact": "MEDIUM",
             "description": "Geo-restriction to Sydney CBD reducing addressable inventory by 71%; Melbourne and Brisbane untapped"},
        ],
        "recommendations": [
            "Expand geo-targeting to Melbourne and Brisbane — major B2B markets outside Sydney",
            "Replace SMB Decision Makers segment with broader Business Professionals audience",
            "Reduce viewability threshold from 80% to 70% to increase available inventory pool",
        ],
        "push_data": {
            "optimisation": "Geo expansion + audience broadening + viewability threshold reduction",
            "projected_ctr": "0.05%", "projected_cpm": "A$14.80", "confidence": "LOW",
        },
    },
    "CMP-774581": {
        "performance_score": 74,
        "issues": [
            {"rank": 1, "impact": "MEDIUM",
             "description": "CTR 0.06% — slightly below benchmark 0.08%; engagement dipping after 3 weeks of same creative"},
            {"rank": 2, "impact": "LOW",
             "description": "Evening delivery 68% of impressions vs 24h planned pacing; morning slots underutilised"},
            {"rank": 3, "impact": "LOW",
             "description": "CPC A$2.10 above planned A$1.80; smart bidding rules could optimise during low-competition hours"},
        ],
        "recommendations": [
            "Refresh entertainment creative with current sports season messaging to boost CTR",
            "Adjust dayparting to increase morning bids — lower CPM competition in 6–10 AM window",
            "Enable automated bid rules for CPC target — set A$1.80 CPC cap across line items",
        ],
        "push_data": {
            "optimisation": "Creative refresh + dayparting adjustment + CPC bid cap rules",
            "projected_ctr": "0.08%", "projected_cpm": "A$14.20", "confidence": "HIGH",
        },
    },
    "AMZ-330921": {
        "performance_score": 81,
        "issues": [
            {"rank": 1, "impact": "LOW",
             "description": "VCR 94% and CPM A$42 tracking 5% above planned A$40; strong performance but monitor for budget overrun"},
            {"rank": 2, "impact": "LOW",
             "description": "Reach frequency at 4.2× — approaching saturation for prime-time audience; diminishing returns likely within 7 days"},
            {"rank": 3, "impact": "LOW",
             "description": "Daytime CTV slots underperforming vs prime-time by 3.1× on VCR — budget allocation suboptimal"},
        ],
        "recommendations": [
            "Maintain current execution — VCR and brand safety metrics are strong",
            "Introduce frequency cap of 3× weekly to preserve reach quality for final 2 weeks",
            "Shift 15% of daytime budget to prime-time 7–10 PM slots for better VCR efficiency",
        ],
        "push_data": {
            "optimisation": "Frequency cap + prime-time budget reallocation",
            "projected_ctr": "N/A (CTV)", "projected_cpm": "A$41.50", "confidence": "HIGH",
        },
    },
    "IO-883047": {
        "performance_score": 29,
        "issues": [
            {"rank": 1, "impact": "HIGH",
             "description": "Severe underpacing with 6 days remaining — A$65,600 unspent; performance data insufficient for reliable optimisation"},
            {"rank": 2, "impact": "HIGH",
             "description": "Creative approval pending for 3 of 5 ad formats — limiting available inventory and preventing full line item activation"},
            {"rank": 3, "impact": "HIGH",
             "description": "CPA A$18.40 running 47% above planned A$12.50; low volume makes this statistically unreliable"},
        ],
        "recommendations": [
            "Escalate creative approval with trafficking team — clear blockers within 24 hours",
            "Switch immediately to approved ad formats while full creative approval is pending",
            "Extend flight by 5 days or reallocate budget to active campaigns with remaining capacity",
        ],
        "push_data": {
            "optimisation": "Creative unblock + bid uplift + pacing mode switch to AHEAD",
            "projected_ctr": "0.09%", "projected_cpm": "A$13.20", "confidence": "LOW",
        },
    },
}

# ── Page header ───────────────────────────────────────────────────────────────
st.title("Live Campaigns")
st.markdown(
    "<p style='color:#6b7280;font-size:14px;margin-top:-12px;'>"
    "Live pacing, campaign health diagnostics and DSP optimisation tools. "
    f"All figures in AUD &nbsp;·&nbsp; Reporting date: {TODAY.strftime('%d %b %Y')}"
    "</p>",
    unsafe_allow_html=True,
)

# ── Column aliases: internal name → list of accepted CSV headers ──────────────
# Matching is case-insensitive. The first alias that exists in the file wins.
COLUMN_ALIASES = {
    "date":          ["date"],
    "advertiser":    ["client", "advertiser", "partner", "brand name"],
    "campaign":      ["campaign", "campaign name", "order"],
    "line_item":     ["line item", "ad group", "line item name"],
    "campaign_id":   ["campaign id", "deal id", "campaign_id", "insertion order id"],
    "buy_type":      ["buy type", "deal type", "type"],
    "budget":        ["budget (aud)", "budget (usd)", "budget", "total budget (aud)", "total budget"],
    "spend":         ["spend (aud)", "total spend (aud)", "spend (usd)", "total spend (usd)",
                      "revenue (aud)", "revenue (usd)", "spend", "cost"],
    "dsp":           ["dsp"],
    "impressions":   ["impressions"],
    "clicks":        ["clicks"],
    "cpm":           ["cpm", "cpm (usd)", "cpm (aud)"],
    "ctr":           ["ctr", "ctr (%)"],
    "video_views":   ["video views", "views"],
    "vtr":           ["vtr", "vtr (%)"],
    "flight_start":  ["flight start", "start date"],
    "flight_end":    ["flight end", "end date"],
}


def map_columns(df):
    """
    Rename a DataFrame's columns to internal standard names using COLUMN_ALIASES.
    Matching is case-insensitive and strips leading/trailing spaces.
    """
    rename = {}
    lower_to_orig = {col.lower().strip(): col for col in df.columns}
    for internal, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in lower_to_orig:
                rename[lower_to_orig[alias]] = internal
                break  # stop at the first matching alias for this internal name
    return df.rename(columns=rename)


def detect_dsp_from_filename(filename):
    """Infer DSP from the upload filename — returns 'TTD', 'DV360', 'Amazon DSP', or 'Unknown'."""
    name = filename.lower()
    if "ttd" in name or "thetradedesk" in name or "trade_desk" in name:
        return "TTD"
    if "dv360" in name or "dv_360" in name or "displayvideo" in name:
        return "DV360"
    if "amazon" in name or "amz" in name or "dsp" in name:
        return "Amazon DSP"
    return "Unknown"


def build_campaigns_from_df(df):
    """
    Convert a merged, column-mapped DataFrame into:
      - CAMPAIGNS list  (one dict per advertiser, same shape as mock data)
      - CAMPAIGN_BREAKDOWN dict  (keyed by campaign_id, same shape as mock data)
    Pacing is calculated relative to today's real date.
    """
    today = date.today()

    # Ensure all required columns exist; fill with defaults if absent
    defaults = {
        "advertiser": "Unknown", "campaign": "Unknown", "line_item": "Unknown",
        "campaign_id": "N/A", "buy_type": "Unknown", "dsp": "Unknown",
        "budget": 0, "spend": 0, "impressions": 0, "clicks": 0, "video_views": 0,
        "flight_start": None, "flight_end": None,
    }
    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    # Convert flight date columns to Python date objects
    df["flight_start"] = pd.to_datetime(df["flight_start"], errors="coerce").dt.date
    df["flight_end"]   = pd.to_datetime(df["flight_end"],   errors="coerce").dt.date

    # Fill missing dates: start = today, end = today + 30 days
    df["flight_start"] = df["flight_start"].apply(lambda x: x if pd.notna(x) and x else today)
    df["flight_end"]   = df["flight_end"].apply(
        lambda x: x if pd.notna(x) and x else today + timedelta(days=30)
    )

    # Coerce numeric delivery columns
    for col in ("budget", "spend", "impressions", "clicks", "video_views"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # First agg: sum spend per (client, dsp, campaign, line_item); budget is static so take last.
    agg = (
        df.groupby(["advertiser", "dsp", "campaign", "line_item"], as_index=False)
        .agg(
            campaign_id  = ("campaign_id",  "last"),
            buy_type     = ("buy_type",     "last"),
            budget       = ("budget",       "last"),
            spend        = ("spend",        "sum"),
            impressions  = ("impressions",  "sum"),
            clicks       = ("clicks",       "sum"),
            video_views  = ("video_views",  "sum"),
            flight_start = ("flight_start", "min"),
            flight_end   = ("flight_end",   "max"),
        )
    )

    campaigns = []
    breakdown = {}

    # One row per (client, dsp, campaign) so multiple DSPs per client show separately.
    for (advertiser, dsp, campaign_name), grp_df in agg.groupby(["advertiser", "dsp", "campaign"]):
        start       = grp_df["flight_start"].min()
        end         = grp_df["flight_end"].max()
        budget      = grp_df["budget"].sum()
        spent       = grp_df["spend"].sum()
        campaign_id = grp_df["campaign_id"].iloc[0]
        buy_type    = grp_df["buy_type"].iloc[0]

        # Pacing calculation — same formula as calc_pacing()
        total_days     = (end - start).days
        days_elapsed   = max((today - start).days, 0)
        days_remaining = (end - today).days
        expected_spend = budget * (days_elapsed / total_days) if total_days > 0 else 0
        pacing_index   = (spent / expected_spend * 100) if expected_spend > 0 else 0

        if pacing_index < 75:
            risk, risk_color, risk_bg = "Critical",   "#EF4444", "#FEF2F2"
        elif pacing_index < 92:
            risk, risk_color, risk_bg = "At risk",    "#F59E0B", "#FFFBEB"
        elif pacing_index <= 110:
            risk, risk_color, risk_bg = "On track",   "#10B981", "#ECFDF5"
        else:
            risk, risk_color, risk_bg = "Overpacing", "#7C3AED", "#F5F3FF"

        # Composite key used to look up the line-item breakdown in the pacing table.
        breakdown_key = f"{advertiser}|{dsp}|{campaign_name}"

        campaigns.append({
            "client":         advertiser,
            "campaign_name":  campaign_name,
            "buy_type":       buy_type,
            "campaign_id":    campaign_id,
            "dsp":            dsp,
            "budget":         budget,
            "spent":          spent,
            "start":          start,
            "end":            end,
            "total_days":     total_days,
            "days_elapsed":   days_elapsed,
            "days_remaining": days_remaining,
            "expected_spend": expected_spend,
            "pacing_index":   pacing_index,
            "risk":           risk,
            "risk_color":     risk_color,
            "risk_bg":        risk_bg,
            "_breakdown_key": breakdown_key,
        })

        # Build line item list for the drill-down; wrap in "campaigns" shape so the
        # rendering loop works identically for mock data and uploaded data.
        li_list = [
            {"name": row["line_item"], "budget": row["budget"], "spent": row["spend"]}
            for _, row in grp_df.iterrows()
        ]
        breakdown[breakdown_key] = {
            "campaigns": [{
                "name":       campaign_name,
                "budget":     budget,
                "spent":      spent,
                "line_items": li_list,
            }]
        }

    return campaigns, breakdown


# ── File uploader — collapsed by default ──────────────────────────────────────
with st.expander("Upload Pacing Reports", expanded=False):
    uploaded_files = st.file_uploader(
        "Upload DSP pacing reports",
        type=["csv"],
        accept_multiple_files=True,
        label_visibility="collapsed",
        help="Upload one or more CSV exports from TTD, DV360, or Amazon DSP. Columns are mapped automatically.",
    )

    if uploaded_files:
        dfs = []
        for f in uploaded_files:
            df_raw = pd.read_csv(f)
            # Tag each row with the filename-detected DSP before mapping.
            df_raw["_dsp_hint"] = detect_dsp_from_filename(f.name)
            # Map columns per-file so DSP-specific headers (e.g. Amazon uses
            # "Order" instead of "Campaign") are resolved before merging.
            # If we merged first, a DV360 "Campaign" column would shadow
            # Amazon's "Order" column and Amazon rows would lose their campaign name.
            df_mapped = map_columns(df_raw)
            dfs.append(df_mapped)

        # Concatenate already-mapped files — columns are now standardised.
        merged_df = pd.concat(dfs, ignore_index=True)

        # Use the filename-detected DSP wherever the data has no DSP value.
        if "dsp" not in merged_df.columns:
            merged_df["dsp"] = merged_df["_dsp_hint"]
        else:
            merged_df["dsp"] = merged_df["dsp"].fillna(merged_df["_dsp_hint"])
        merged_df = merged_df.drop(columns=["_dsp_hint"])

        # Upload summary line
        num_rows = len(merged_df)
        num_adv  = merged_df["advertiser"].nunique() if "advertiser" in merged_df.columns else "?"
        dsp_vals = sorted(merged_df["dsp"].dropna().unique()) if "dsp" in merged_df.columns else []
        dsp_str  = " & ".join(dsp_vals) if dsp_vals else "Unknown"
        n_files  = len(uploaded_files)
        st.caption(
            f"Loaded **{n_files}** file{'s' if n_files > 1 else ''}  ·  "
            f"**{num_rows:,}** rows  ·  "
            f"**{num_adv}** advertisers across **{dsp_str}**"
        )

        CAMPAIGNS, CAMPAIGN_BREAKDOWN = build_campaigns_from_df(merged_df)
        _using_upload = True
        _upload_date  = date.today()

    else:
        # Fall back to hardcoded mock data when no files are uploaded
        CAMPAIGNS          = MOCK_CAMPAIGNS
        CAMPAIGN_BREAKDOWN = MOCK_CAMPAIGN_BREAKDOWN
        _using_upload      = False

# When no files were uploaded (expander closed), also fall back to mock data
if not uploaded_files:
    CAMPAIGNS          = MOCK_CAMPAIGNS
    CAMPAIGN_BREAKDOWN = MOCK_CAMPAIGN_BREAKDOWN
    _using_upload      = False

# Data status indicator — shown below the uploader
if _using_upload:
    total_camps = sum(len(b["campaigns"]) for b in CAMPAIGN_BREAKDOWN.values())
    num_adv_str = len(CAMPAIGNS)
    st.markdown(
        f"<div style='background:#ECFDF5;border:1px solid #6EE7B7;border-radius:8px;"
        f"padding:10px 14px;font-size:13px;color:#065F46;margin-bottom:4px;'>"
        f"✅ Pacing data loaded from upload — <strong>{total_camps}</strong> campaigns across "
        f"<strong>{num_adv_str}</strong> advertisers — "
        f"last updated <strong>{_upload_date.strftime('%d %b %Y')}</strong>"
        f"</div>",
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        "<div style='background:#FFFBEB;border:1px solid #FDE68A;border-radius:8px;"
        "padding:10px 14px;font-size:13px;color:#92400E;margin-bottom:4px;'>"
        "⚠️ Showing mock data — upload DSP reports above for live pacing"
        "</div>",
        unsafe_allow_html=True,
    )

# ── Date range filter ─────────────────────────────────────────────────────────
all_starts = [c["start"] for c in CAMPAIGNS]
all_ends   = [c["end"]   for c in CAMPAIGNS]

st.markdown("**Filter by campaign date range**")
filter_col1, filter_col2 = st.columns(2)
with filter_col1:
    filter_start = st.date_input("From", value=min(all_starts), min_value=min(all_starts), max_value=max(all_ends))
with filter_col2:
    filter_end = st.date_input("To", value=max(all_ends), min_value=min(all_starts), max_value=max(all_ends))

# ── Operations filters ────────────────────────────────────────────────────────
st.markdown("**Operations**")
ops_col1, ops_col2, ops_col3, ops_col4, ops_col5 = st.columns(5)

all_clients      = sorted(set(c["client"]      for c in CAMPAIGNS if c["client"]      is not None))
all_buy_types    = sorted(set(c["buy_type"]    for c in CAMPAIGNS if c["buy_type"]    is not None))
all_dsps         = sorted(set(c["dsp"]         for c in CAMPAIGNS if c["dsp"]         is not None))
all_campaign_ids = sorted(set(c["campaign_id"] for c in CAMPAIGNS if c["campaign_id"] is not None))
all_statuses     = ["Critical", "At risk", "On track", "Overpacing"]

with ops_col1:
    filter_clients = st.multiselect("Client", all_clients, placeholder="All clients")
with ops_col2:
    filter_buy_types = st.multiselect("Buy Type", all_buy_types, placeholder="All types")
with ops_col3:
    filter_dsps = st.multiselect("DSP", all_dsps, placeholder="All DSPs")
with ops_col4:
    filter_campaign_ids = st.multiselect("Campaign ID", all_campaign_ids, placeholder="All campaigns")
with ops_col5:
    filter_statuses = st.multiselect("Status", all_statuses, placeholder="All statuses")

# Keep campaigns whose date range overlaps the selected window, then apply operations filters
FILTERED_CAMPAIGNS = [
    c for c in CAMPAIGNS
    if c["start"] <= filter_end and c["end"] >= filter_start
    and (not filter_clients      or c["client"]      in filter_clients)
    and (not filter_buy_types    or c["buy_type"]    in filter_buy_types)
    and (not filter_dsps         or c["dsp"]         in filter_dsps)
    and (not filter_campaign_ids or c["campaign_id"] in filter_campaign_ids)
    and (not filter_statuses     or c["risk"]        in filter_statuses)
]
FILTERED_AT_RISK = [c for c in FILTERED_CAMPAIGNS if c["risk"] in ("Critical", "At risk")]

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — Portfolio Overview
# ═══════════════════════════════════════════════════════════════════════════════
st.subheader("Portfolio Overview")

total_spent      = sum(c["spent"]          for c in FILTERED_CAMPAIGNS)
total_expected   = sum(c["expected_spend"] for c in FILTERED_CAMPAIGNS)
portfolio_pacing = (total_spent / total_expected * 100) if total_expected > 0 else 0
budget_at_risk   = sum(c["budget"] for c in FILTERED_AT_RISK)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Active Campaigns",  len(FILTERED_CAMPAIGNS))
c2.metric(
    "At-Risk Campaigns",
    len(FILTERED_AT_RISK),
    delta=f"{len(FILTERED_AT_RISK)} require action",
    delta_color="inverse",
)
c3.metric("Budget at Risk",   f"A${budget_at_risk / 1_000:.0f}k")
c4.metric("Portfolio Pacing", f"{portfolio_pacing:.1f}%")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — Pacing Dashboard
# ═══════════════════════════════════════════════════════════════════════════════
st.subheader("Pacing Dashboard")


def dsp_badge(dsp):
    """Coloured pill badge for DSP."""
    if dsp == "TTD":
        return ("<span style='background:#F5F3FF;color:#7C3AED;border-radius:4px;"
                "padding:2px 8px;font-size:11px;font-weight:700;'>TTD</span>")
    if dsp == "DV360":
        return ("<span style='background:#EFF6FF;color:#2563EB;border-radius:4px;"
                "padding:2px 8px;font-size:11px;font-weight:700;'>DV360</span>")
    if dsp == "Amazon DSP":
        return ("<span style='background:#FFF7ED;color:#EA580C;border-radius:4px;"
                "padding:2px 8px;font-size:11px;font-weight:700;'>Amazon</span>")
    return (f"<span style='background:#F3F4F6;color:#6B7280;border-radius:4px;"
            f"padding:2px 8px;font-size:11px;font-weight:700;'>{dsp}</span>")


def buy_type_badge(buy_type):
    """Coloured pill badge for PG or PMP buy type."""
    if buy_type == "PG":
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


def calc_sub_pacing(budget, spent, start, end):
    """
    Calculate pacing index and risk tier for a campaign or line item.
    Uses the same formula as calc_pacing() but takes raw values instead of a campaign dict.
    """
    total_days     = (end - start).days
    days_elapsed   = (TODAY - start).days
    expected_spend = budget * (days_elapsed / total_days) if total_days > 0 else 0
    pacing_index   = (spent / expected_spend * 100) if expected_spend > 0 else 0

    if pacing_index < 75:
        risk, risk_color, risk_bg = "Critical",   "#EF4444", "#FEF2F2"
    elif pacing_index < 92:
        risk, risk_color, risk_bg = "At risk",    "#F59E0B", "#FFFBEB"
    elif pacing_index <= 110:
        risk, risk_color, risk_bg = "On track",   "#10B981", "#ECFDF5"
    else:
        risk, risk_color, risk_bg = "Overpacing", "#7C3AED", "#F5F3FF"

    return {
        "pacing_index": pacing_index,
        "risk": risk, "risk_color": risk_color, "risk_bg": risk_bg,
    }


# Table header (rendered once above all client rows)
st.markdown(
    """
    <div style='background:#F9FAFB;border-radius:12px 12px 0 0;
                border-bottom:2px solid #E5E7EB;margin-bottom:0;'>
      <table style='width:100%;border-collapse:collapse;'>
        <thead>
          <tr>
            <th style='padding:12px 16px;text-align:left;font-size:11px;color:#6B7280;
                       text-transform:uppercase;letter-spacing:0.06em;width:28px;'></th>
            <th style='padding:12px 16px;text-align:left;font-size:11px;color:#6B7280;
                       text-transform:uppercase;letter-spacing:0.06em;'>Client</th>
            <th style='padding:12px 16px;text-align:left;font-size:11px;color:#6B7280;
                       text-transform:uppercase;letter-spacing:0.06em;'>DSP</th>
            <th style='padding:12px 16px;text-align:left;font-size:11px;color:#6B7280;
                       text-transform:uppercase;letter-spacing:0.06em;'>Type</th>
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
      </table>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Group campaigns by client for the one-client-row hierarchy ────────────────
# One white card per client; inside a "Campaigns" expander one row per campaign;
# inside each campaign a "Line Items" expander with line item detail.
clients_map = {}
for c in FILTERED_CAMPAIGNS:
    clients_map.setdefault(c["client"], []).append(c)

for client_name, client_campaigns in clients_map.items():
    # Aggregate totals across all campaigns for this client
    total_budget   = sum(c["budget"]         for c in client_campaigns)
    total_spent    = sum(c["spent"]           for c in client_campaigns)
    total_expected = sum(c["expected_spend"]  for c in client_campaigns)
    agg_pacing     = (total_spent / total_expected * 100) if total_expected > 0 else 0
    min_days_left  = min(c["days_remaining"]  for c in client_campaigns)

    if agg_pacing < 75:
        agg_risk, agg_rc, agg_rb = "Critical",   "#EF4444", "#FEF2F2"
    elif agg_pacing < 92:
        agg_risk, agg_rc, agg_rb = "At risk",    "#F59E0B", "#FFFBEB"
    elif agg_pacing <= 110:
        agg_risk, agg_rc, agg_rb = "On track",   "#10B981", "#ECFDF5"
    else:
        agg_risk, agg_rc, agg_rb = "Overpacing", "#7C3AED", "#F5F3FF"

    n_camps = len(client_campaigns)
    client_row = (
        f"<tr style='border-bottom:1px solid #F3F4F6;'>"
        f"<td style='padding:14px 16px;width:28px;color:#9CA3AF;font-size:11px;'>▶</td>"
        f"<td style='padding:14px 16px;font-weight:600;color:#111827;'>{client_name}"
        f"<span style='font-size:11px;color:#6B7280;font-weight:400;margin-left:8px;'>"
        f"{n_camps} campaign{'s' if n_camps != 1 else ''}</span></td>"
        f"<td style='padding:14px 16px;'></td>"
        f"<td style='padding:14px 16px;'></td>"
        f"<td style='padding:14px 16px;text-align:right;'>A${total_budget/1_000:.0f}k</td>"
        f"<td style='padding:14px 16px;text-align:right;'>A${total_spent/1_000:.1f}k</td>"
        f"<td style='padding:14px 16px;min-width:220px;'>"
        f"{pacing_bar(agg_pacing, agg_rc)}</td>"
        f"<td style='padding:14px 16px;text-align:center;'>"
        f"{days_cell(min_days_left)}</td>"
        f"<td style='padding:14px 16px;'>"
        f"{risk_badge(agg_risk, agg_rc, agg_rb)}</td>"
        f"</tr>"
    )
    st.markdown(
        f"<div style='background:#FFFFFF;box-shadow:0 1px 0 #F3F4F6;'>"
        f"<table style='width:100%;border-collapse:collapse;'>"
        f"<tbody>{client_row}</tbody>"
        f"</table></div>",
        unsafe_allow_html=True,
    )

    # "Campaigns" expander — one row per campaign under this client
    with st.expander("Campaigns", expanded=False):
        for c in client_campaigns:
            _lookup_key = c.get("_breakdown_key", c["campaign_id"])
            breakdown = CAMPAIGN_BREAKDOWN.get(_lookup_key, {})

            # Campaign row — DSP badge, type, budget, spent, pacing, days left, status
            camp_row = (
                f"<tr style='border-bottom:1px solid #E5E7EB;background:#F9FAFB;'>"
                f"<td style='padding:10px 16px;width:28px;color:#9CA3AF;font-size:11px;'>📊</td>"
                f"<td style='padding:10px 16px;font-size:13px;font-weight:600;"
                f"color:#374151;'>{c['campaign_name']}</td>"
                f"<td style='padding:10px 16px;'>{dsp_badge(c['dsp'])}</td>"
                f"<td style='padding:10px 16px;'>{buy_type_badge(c['buy_type'])}</td>"
                f"<td style='padding:10px 16px;text-align:right;font-size:13px;'>"
                f"A${c['budget']/1_000:.0f}k</td>"
                f"<td style='padding:10px 16px;text-align:right;font-size:13px;'>"
                f"A${c['spent']/1_000:.1f}k</td>"
                f"<td style='padding:10px 16px;min-width:200px;'>"
                f"{pacing_bar(c['pacing_index'], c['risk_color'])}</td>"
                f"<td style='padding:10px 16px;text-align:center;font-size:13px;'>"
                f"{days_cell(c['days_remaining'])}</td>"
                f"<td style='padding:10px 16px;'>"
                f"{risk_badge(c['risk'], c['risk_color'], c['risk_bg'])}</td>"
                f"</tr>"
            )
            st.markdown(
                f"<div style='background:#F9FAFB;border-radius:8px;"
                f"overflow:hidden;margin-bottom:4px;'>"
                f"<table style='width:100%;border-collapse:collapse;'>"
                f"<tbody>{camp_row}</tbody>"
                f"</table></div>",
                unsafe_allow_html=True,
            )

            # "Line Items" expander — flatten line items from all sub-campaigns
            if breakdown:
                all_li = [
                    li
                    for sub in breakdown.get("campaigns", [])
                    for li in sub.get("line_items", [])
                ]
                if all_li:
                    with st.expander("Line Items", expanded=False):
                        li_rows = ""
                        for li in all_li:
                            lp = calc_sub_pacing(li["budget"], li["spent"], c["start"], c["end"])
                            li_rows += (
                                f"<tr style='border-bottom:1px solid #F3F4F6;'>"
                                f"<td style='padding:10px 14px 10px 24px;color:#374151;"
                                f"font-size:13px;'>{li['name']}</td>"
                                f"<td style='padding:10px 14px;text-align:right;"
                                f"font-size:13px;'>A${li['budget']/1_000:.0f}k</td>"
                                f"<td style='padding:10px 14px;text-align:right;"
                                f"font-size:13px;'>A${li['spent']/1_000:.1f}k</td>"
                                f"<td style='padding:10px 14px;min-width:200px;'>"
                                f"{pacing_bar(lp['pacing_index'], lp['risk_color'])}</td>"
                                f"<td style='padding:10px 14px;'>"
                                f"{risk_badge(lp['risk'], lp['risk_color'], lp['risk_bg'])}</td>"
                                f"</tr>"
                            )

                        st.markdown(
                            f"<div style='background:#F9FAFB;border-radius:8px;"
                            f"overflow:hidden;margin-top:8px;'>"
                            f"<table style='width:100%;border-collapse:collapse;'>"
                            f"<thead><tr style='background:#F3F4F6;border-bottom:1px solid #E5E7EB;'>"
                            f"<th style='padding:8px 14px 8px 24px;text-align:left;font-size:11px;"
                            f"color:#6B7280;text-transform:uppercase;letter-spacing:0.05em;'>"
                            f"Line Item</th>"
                            f"<th style='padding:8px 14px;text-align:right;font-size:11px;"
                            f"color:#6B7280;text-transform:uppercase;letter-spacing:0.05em;'>"
                            f"Budget</th>"
                            f"<th style='padding:8px 14px;text-align:right;font-size:11px;"
                            f"color:#6B7280;text-transform:uppercase;letter-spacing:0.05em;'>"
                            f"Spent</th>"
                            f"<th style='padding:8px 14px;text-align:left;font-size:11px;"
                            f"color:#6B7280;text-transform:uppercase;letter-spacing:0.05em;'>"
                            f"Pacing</th>"
                            f"<th style='padding:8px 14px;text-align:left;font-size:11px;"
                            f"color:#6B7280;text-transform:uppercase;letter-spacing:0.05em;'>"
                            f"Status</th>"
                            f"</tr></thead>"
                            f"<tbody>{li_rows}</tbody>"
                            f"</table></div>",
                            unsafe_allow_html=True,
                        )

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — Delivery Troubleshooter
# Each at-risk campaign shows its diagnostic panel + DSP Push button together.
# ═══════════════════════════════════════════════════════════════════════════════
st.subheader("Delivery Troubleshooter")
st.markdown(
    "<p style='color:#6b7280;font-size:14px;margin-top:-8px;'>"
    "Campaign health diagnostics for at-risk campaigns. "
    "TTD campaigns source from the TTD Deal Health API; "
    "DV360 and Amazon DSP campaigns source from their respective troubleshooter APIs.</p>",
    unsafe_allow_html=True,
)

# ── Fallback diagnostic generators ────────────────────────────────────────────
# Used when a campaign has no pre-defined entry in DIAGNOSTICS / PUSH_DATA /
# PERFORMANCE_DATA (e.g. uploaded data). Returns the same dict shape so the
# rendering code works identically regardless of the data source.

def _fallback_delivery_diag(c):
    """Return a realistic delivery diagnostic based on the campaign's DSP."""
    dsp = c.get("dsp", "")
    if dsp == "TTD":
        return {
            "health_score": 45,
            "source":       "TTD Deal Health API",
            "blockers": [
                {"rank": 1, "impact": "HIGH",
                 "description": "Audience segment matching only 9% of available TTD inventory — severely limiting bid opportunities"},
                {"rank": 2, "impact": "HIGH",
                 "description": "Bid floor below publisher minimum on 67% of impressions — effective CPM uncompetitive for priority supply"},
                {"rank": 3, "impact": "MEDIUM",
                 "description": "Frequency cap reached — avg user hitting cap after 1.2 days, exhausting available unique reach"},
            ],
            "targeting_callout": {
                "segment":         "Primary Audience Segment",
                "match_rate":      "9%",
                "issue":           "Narrow segment is the primary delivery bottleneck, restricting the campaign to a small fraction of available TTD supply.",
                "alternatives":    [
                    "Broader demographic segment (est. 3× broader reach)",
                    "In-market intent audience (est. 2× broader reach)",
                    "Contextual targeting expansion (est. 4× broader reach)",
                ],
                "projected_match": "~32%",
            },
        }
    if dsp == "Amazon DSP":
        return {
            "health_score": 51,
            "source":       "Amazon DSP Reporting API",
            "blockers": [
                {"rank": 1, "impact": "HIGH",
                 "description": "Audience overlap with exclusion lists reducing addressable reach by 28%"},
                {"rank": 2, "impact": "HIGH",
                 "description": "Bid too low for sponsored placements — below floor price on 45% of targeted inventory"},
                {"rank": 3, "impact": "MEDIUM",
                 "description": "Creative not approved for all ad sizes in this placement — limiting delivery to 2 of 5 formats"},
            ],
            "targeting_callout": {
                "segment":         "Primary Audience Segment",
                "match_rate":      "18%",
                "issue":           "Exclusion list overlap and creative approval gaps are the primary delivery constraints on this campaign.",
                "alternatives":    [
                    "Reduced exclusion list scope (est. 2× broader reach)",
                    "Additional ad size approvals (unlocks 3 more formats)",
                    "Broader Amazon audience segment (est. 3× broader reach)",
                ],
                "projected_match": "~41%",
            },
        }
    # Default: DV360
    return {
        "health_score": 38,
        "source":       "DV360 Troubleshooter API",
        "blockers": [
            {"rank": 1, "impact": "HIGH",
             "description": "Brand safety targeting excluding 34% of eligible inventory — categories applied more broadly than required"},
            {"rank": 2, "impact": "HIGH",
             "description": "Viewability threshold too high — limiting eligible supply to premium-only placements"},
            {"rank": 3, "impact": "MEDIUM",
             "description": "Budget pacing set to EVEN — consider switching to ASAP to recover underspend in remaining flight window"},
        ],
        "targeting_callout": {
            "segment":         "Primary Audience Segment",
            "match_rate":      "14%",
            "issue":           "Combination of brand safety restrictions and viewability threshold is severely limiting the addressable inventory pool.",
            "alternatives":    [
                "Relaxed brand safety categories (est. 2.5× broader reach)",
                "Lower viewability threshold to 70% (est. 3× broader reach)",
                "Broader audience targeting (est. 4× broader reach)",
            ],
            "projected_match": "~38%",
        },
    }


def _fallback_push_data(c):
    """Return generic push recovery data when no pre-defined entry exists."""
    dsp = c.get("dsp", "")
    if dsp == "TTD":
        return {"bid_from": 3.20, "bid_to": 4.00, "budget_from": 4_000, "budget_to": 5_000,
                "recovery_aud": 8_000, "projected_pacing": 91.0, "confidence": "MEDIUM"}
    if dsp == "Amazon DSP":
        return {"bid_from": 8.00, "bid_to": 10.00, "budget_from": 5_000, "budget_to": 6_200,
                "recovery_aud": 7_500, "projected_pacing": 90.0, "confidence": "LOW"}
    # Default: DV360
    return {"bid_from": 5.00, "bid_to": 6.25, "budget_from": 3_500, "budget_to": 4_400,
            "recovery_aud": 6_500, "projected_pacing": 89.5, "confidence": "MEDIUM"}


def _fallback_perf_diag(c):
    """Return realistic performance diagnostics based on the campaign's DSP."""
    dsp  = c.get("dsp", "")
    name = (c.get("campaign_name") or "").lower()

    if dsp == "DV360" and any(kw in name for kw in ("youtube", "trueview", "bumper")):
        return {
            "performance_score": 62,
            "issues": [
                {"rank": 1, "impact": "HIGH",
                 "description": "View Rate 61% — below TrueView benchmark of 70%; first 5 seconds not engaging viewers"},
                {"rank": 2, "impact": "MEDIUM",
                 "description": "Bumper ads driving 2× CTR vs TrueView at lower CPM — budget allocation suboptimal"},
                {"rank": 3, "impact": "LOW",
                 "description": "Mobile view rate 8% below Desktop — dedicated mobile edit may improve completion"},
            ],
            "recommendations": [
                "Rework TrueView opening hook — lead message must land within first 3 seconds",
                "Shift 20% of TrueView budget to bumper ads to capitalise on CTR efficiency",
                "Create a 15s mobile edit with larger text overlay and tighter framing",
            ],
            "push_data": {
                "optimisation":  "Creative hook rework + bumper budget shift",
                "projected_ctr": "0.14%", "projected_cpm": "A$11.20", "confidence": "MEDIUM",
            },
        }

    if dsp == "TTD":
        if any(kw in name for kw in ("bvod", "9now", "7plus", "broadcast")):
            return {
                "performance_score": 71,
                "issues": [
                    {"rank": 1, "impact": "MEDIUM",
                     "description": "VCR 91% — strong but 9Now outperforming 7Plus by 4 percentage points"},
                    {"rank": 2, "impact": "MEDIUM",
                     "description": "Connected TV CPM A$46 — above BVOD benchmark of A$40"},
                    {"rank": 3, "impact": "LOW",
                     "description": "15s creative outperforming 30s on completion rate — rebalance creative mix"},
                ],
                "recommendations": [
                    "Increase 9Now bid weighting by 15% to capitalise on its higher VCR",
                    "Negotiate 7Plus CPM floor or reduce 7Plus allocation to improve blended CPM",
                    "Shift 30% of 30s budget to 15s creative to improve completion rates",
                ],
                "push_data": {
                    "optimisation":  "Publisher bid weighting + creative length rebalance",
                    "projected_ctr": "N/A (BVOD)", "projected_cpm": "A$41.50", "confidence": "HIGH",
                },
            }
        return {
            "performance_score": 58,
            "issues": [
                {"rank": 1, "impact": "HIGH",
                 "description": "CTR 0.06% — below Display benchmark of 0.25%; creative may need refreshing after 3 weeks"},
                {"rank": 2, "impact": "MEDIUM",
                 "description": "Mobile CPM A$18 — 40% above Desktop at A$13; review mobile bid adjustments"},
                {"rank": 3, "impact": "LOW",
                 "description": "Retargeting line items outperforming prospecting 3:1 on CTR — consider budget reallocation"},
            ],
            "recommendations": [
                "Rotate display creative — introduce new variants to lift CTR toward 0.25% benchmark",
                "Reduce mobile bid adjustment by 20% to bring mobile CPM in line with desktop",
                "Shift 15% of prospecting budget to retargeting line items to improve overall CTR",
            ],
            "push_data": {
                "optimisation":  "Creative rotation + mobile bid reduction + budget reallocation",
                "projected_ctr": "0.18%", "projected_cpm": "A$14.50", "confidence": "MEDIUM",
            },
        }

    if dsp == "Amazon DSP":
        return {
            "performance_score": 55,
            "issues": [
                {"rank": 1, "impact": "HIGH",
                 "description": "DPV rate 12% — below benchmark of 18% for Telco vertical; landing page may need review"},
                {"rank": 2, "impact": "MEDIUM",
                 "description": "Cart abandoner retargeting ROAS 3.2× vs prospecting 1.8× — significant budget upside available"},
                {"rank": 3, "impact": "MEDIUM",
                 "description": "Mobile CTR 0.4% vs Desktop 0.7% — mobile creative review needed"},
            ],
            "recommendations": [
                "Audit landing page experience for mobile — DPV rate suggests drop-off post-click",
                "Increase cart abandoner retargeting budget by 30% — ROAS is 78% higher than prospecting",
                "Produce dedicated mobile creative with clearer CTA and faster load time",
            ],
            "push_data": {
                "optimisation":  "Landing page audit + retargeting budget uplift + mobile creative refresh",
                "projected_ctr": "0.62%", "projected_cpm": "A$16.80", "confidence": "MEDIUM",
            },
        }

    # Default: DV360 Display
    return {
        "performance_score": 58,
        "issues": [
            {"rank": 1, "impact": "HIGH",
             "description": "CTR 0.08% — below Display benchmark of 0.25%; creative fatigue likely"},
            {"rank": 2, "impact": "MEDIUM",
             "description": "Mobile CPM A$18 — 40% above Desktop at A$13; review mobile bid adjustments"},
            {"rank": 3, "impact": "LOW",
             "description": "Retargeting line items outperforming prospecting 3:1 on CTR — consider budget reallocation"},
        ],
        "recommendations": [
            "Rotate display creative — introduce new variants to lift CTR toward 0.25% benchmark",
            "Reduce mobile bid adjustment by 20% to bring mobile CPM in line with desktop",
            "Shift 15% of prospecting budget to retargeting line items to improve overall CTR",
        ],
        "push_data": {
            "optimisation":  "Creative rotation + mobile bid reduction + budget reallocation",
            "projected_ctr": "0.18%", "projected_cpm": "A$14.50", "confidence": "MEDIUM",
        },
    }


# Impact badge colour map
IMPACT_STYLE = {
    "HIGH":   ("#FEF2F2", "#EF4444"),
    "MEDIUM": ("#FFFBEB", "#F59E0B"),
    "LOW":    ("#F0FDF4", "#10B981"),
}


def health_score_colour(score):
    """Return a hex colour for the campaign health score gauge."""
    if score < 40:
        return "#EF4444"
    if score < 70:
        return "#F59E0B"
    return "#10B981"


for c in FILTERED_AT_RISK:
    # Unique key for widgets — _breakdown_key is always set for uploaded data;
    # fall back to campaign_id, then client+dsp if both are None.
    _ck = c.get("_breakdown_key") or c.get("campaign_id") or f"{c['client']}_{c['dsp']}"

    # Use pre-defined diagnostics when available; fall back to DSP-specific mock data.
    diag = DIAGNOSTICS.get(c["campaign_id"]) or _fallback_delivery_diag(c)
    pd_  = PUSH_DATA.get(c["campaign_id"])   or _fallback_push_data(c)
    score = diag["health_score"]
    tgt   = diag["targeting_callout"]
    sc    = health_score_colour(score)
    tier  = "CRITICAL" if score < 40 else "POOR" if score < 70 else "FAIR"

    with st.expander(
        f"{c['client']}  ·  {c['dsp']}  ·  {c['risk']}  ·  {c['days_remaining']}d remaining",
        expanded=False,
    ):
        # API source label
        st.markdown(
            f"<div style='font-size:11px;color:#6B7280;margin-bottom:12px;'>"
            f"Source: <strong>{diag['source']}</strong></div>",
            unsafe_allow_html=True,
        )

        col_score, col_blockers = st.columns([1, 3])

        # ── Campaign health score gauge ───────────────────────────────────────
        with col_score:
            st.markdown(
                f"<div style='background:#FFFFFF;border-radius:12px;padding:20px;"
                f"box-shadow:0 2px 8px rgba(0,0,0,0.06);text-align:center;'>"
                f"<div style='font-size:11px;font-weight:600;color:#6B7280;"
                f"text-transform:uppercase;letter-spacing:0.05em;margin-bottom:8px;'>"
                f"Campaign Health Score</div>"
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

        # ── Audience targeting impact callout ────────────────────────────────
        alts_html = "&nbsp;&nbsp;·&nbsp;&nbsp;".join(
            f"<strong>{a}</strong>" for a in tgt["alternatives"]
        )
        st.markdown(
            f"<div style='background:#F0F9FF;border:1px solid #BAE6FD;"
            f"border-radius:8px;padding:14px 16px;margin-top:12px;'>"
            f"<div style='font-size:11px;font-weight:700;color:#0369A1;"
            f"text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px;'>"
            f"Audience Targeting Impact</div>"
            f"<div style='font-size:13px;color:#0C4A6E;margin-bottom:6px;'>"
            f"<strong>{tgt['segment']}</strong> — inventory match rate: "
            f"<strong>{tgt['match_rate']}</strong><br>"
            f"<span style='color:#374151;'>{tgt['issue']}</span></div>"
            f"<div style='font-size:13px;color:#0369A1;'>"
            f"Recommended alternatives: {alts_html}</div>"
            f"<div style='font-size:12px;color:#0369A1;margin-top:4px;'>"
            f"Projected match rate after swap: <strong>{tgt['projected_match']}</strong>"
            f"</div></div>",
            unsafe_allow_html=True,
        )

        # ── Select fixes to push ───────────────────────────────────────────────
        st.markdown(
            "<div style='font-size:12px;font-weight:700;color:#374151;"
            "text-transform:uppercase;letter-spacing:0.05em;"
            "margin-top:16px;margin-bottom:6px;'>"
            "Select Fixes to Push</div>",
            unsafe_allow_html=True,
        )
        select_all_delivery = st.checkbox("Select All", key=f"deliv_all_{_ck}", value=False)
        selected_blockers = []
        for i, b in enumerate(diag["blockers"]):
            checked = st.checkbox(
                b["description"],
                key=f"deliv_cb_{_ck}_{i}",
                value=select_all_delivery,
            )
            if checked or select_all_delivery:
                selected_blockers.append(b)

        # ── DSP Push button — disabled until at least one fix is selected ──────
        st.markdown("<div style='margin-top:16px;'>", unsafe_allow_html=True)
        is_dv360 = c["dsp"] == "DV360"
        remaining_budget = c["budget"] - c["spent"]
        no_delivery_selection = len(selected_blockers) == 0

        col_btn, col_resp = st.columns([1, 3])
        with col_btn:
            if st.button(
                f"⚡ Push Delivery Fix — {c['client']}",
                key=f"push_{_ck}",
                type="primary",
                disabled=no_delivery_selection,
                help="Select at least one optimisation to push" if no_delivery_selection else None,
            ):
                st.session_state[f"pushed_{_ck}"] = True
                # Store the selected fixes at push time so the response stays stable
                st.session_state[f"pushed_blockers_{_ck}"] = [b["description"] for b in selected_blockers]

            st.markdown(
                f"<div style='font-size:12px;color:#6B7280;margin-top:8px;line-height:1.7;'>"
                f"<strong style='color:#111827;'>{c['client']}</strong><br>"
                f"{c['dsp']} &nbsp;·&nbsp; {c['buy_type']}<br>"
                f"Pacing: {c['pacing_index']:.1f}% "
                f"<span style='color:{c['risk_color']};font-weight:700;'>({c['risk']})</span><br>"
                f"Remaining: A${remaining_budget/1_000:.1f}k &nbsp;·&nbsp; {c['days_remaining']}d left"
                f"</div>",
                unsafe_allow_html=True,
            )

        with col_resp:
            if st.session_state.get(f"pushed_{_ck}"):
                # Use the fixes that were selected at push time
                pushed_fixes = st.session_state.get(
                    f"pushed_blockers_{_ck}",
                    [b["description"] for b in selected_blockers],
                )
                budget_change_pct = (
                    (pd_["budget_to"] - pd_["budget_from"]) / pd_["budget_from"] * 100
                )
                recovery_note = (
                    "Low confidence due to compressed flight end — monitor daily for first 48h"
                    if pd_["confidence"] == "LOW"
                    else "Monitor pacing daily to avoid overspend"
                )

                if is_dv360:
                    bid_from_micros = int(pd_["bid_from"] * 1_000_000)
                    bid_to_micros   = int(pd_["bid_to"]   * 1_000_000)
                    mock_response = {
                        "status":           200,
                        "message":          "Insertion order updated successfully",
                        "advertiserId":     "7841209",
                        "insertionOrderId": c["campaign_id"],
                        "advertiser":       c["client"],
                        "endpoint":         f"PATCH /v2/advertisers/7841209/insertionOrders/{c['campaign_id']}",
                        "selected_fixes":   pushed_fixes,
                        "changes_applied": {
                            "pacing": {
                                "from": {"pacingPeriod": "PACING_PERIOD_DAILY", "pacingType": "PACING_TYPE_EVEN"},
                                "to":   {"pacingPeriod": "PACING_PERIOD_DAILY", "pacingType": "PACING_TYPE_AHEAD"},
                            },
                            "bidStrategy": {
                                "fixedBid": {
                                    "from":   {"bidAmountMicros": bid_from_micros},
                                    "to":     {"bidAmountMicros": bid_to_micros},
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
                    # TTD API response
                    mock_response = {
                        "status":        200,
                        "message":       "Campaign updated successfully",
                        "campaign_id":   c["campaign_id"],
                        "advertiser":    c["client"],
                        "endpoint":      f"PATCH /v3/campaign/{c['campaign_id']}",
                        "selected_fixes": pushed_fixes,
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
                st.markdown(
                    "<div style='background:#F9FAFB;border:1px dashed #D1D5DB;"
                    "border-radius:8px;padding:28px;text-align:center;"
                    "color:#9CA3AF;font-size:13px;'>"
                    "Select fixes above then click the button to simulate the DSP PATCH call "
                    "and see the projected API response.</div>",
                    unsafe_allow_html=True,
                )
        st.markdown("</div>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — Campaign Performance Troubleshooter
# Shows performance KPI diagnostics and an optimisation push per campaign.
# ═══════════════════════════════════════════════════════════════════════════════
st.subheader("Campaign Performance Troubleshooter")
st.markdown(
    "<p style='color:#6b7280;font-size:14px;margin-top:-8px;'>"
    "Performance KPI diagnostics, top issues, and optimisation recommendations per campaign.</p>",
    unsafe_allow_html=True,
)

for c in FILTERED_CAMPAIGNS:
    # Unique key for widgets — same pattern as the delivery troubleshooter loop.
    _ck = c.get("_breakdown_key") or c.get("campaign_id") or f"{c['client']}_{c['dsp']}"

    # Use pre-defined performance data when available; fall back to DSP-specific mock data.
    perf = PERFORMANCE_DATA.get(c["campaign_id"]) or _fallback_perf_diag(c)

    score      = perf["performance_score"]
    sc         = health_score_colour(score)
    perf_tier  = "CRITICAL" if score < 40 else "POOR" if score < 70 else "FAIR" if score < 80 else "GOOD"

    with st.expander(
        f"{c['client']}  ·  {c['dsp']}  ·  {c['campaign_id']}  ·  "
        f"Performance score: {score}/100",
        expanded=False,
    ):
        col_pscore, col_issues = st.columns([1, 3])

        # ── Performance score gauge ───────────────────────────────────────────
        with col_pscore:
            st.markdown(
                f"<div style='background:#FFFFFF;border-radius:12px;padding:20px;"
                f"box-shadow:0 2px 8px rgba(0,0,0,0.06);text-align:center;'>"
                f"<div style='font-size:11px;font-weight:600;color:#6B7280;"
                f"text-transform:uppercase;letter-spacing:0.05em;margin-bottom:8px;'>"
                f"Performance Score</div>"
                f"<div style='font-size:52px;font-weight:800;color:{sc};line-height:1;'>"
                f"{score}</div>"
                f"<div style='font-size:13px;color:#9CA3AF;margin-top:2px;'>/100</div>"
                f"<div style='font-size:12px;color:{sc};margin-top:10px;"
                f"font-weight:700;'>{perf_tier}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

        # ── Top 3 performance issues ──────────────────────────────────────────
        with col_issues:
            st.markdown(
                "<div style='font-size:11px;font-weight:600;color:#6B7280;"
                "text-transform:uppercase;letter-spacing:0.05em;margin-bottom:10px;'>"
                "Top Issues by Impact</div>",
                unsafe_allow_html=True,
            )
            for issue in perf["issues"]:
                bg, fg = IMPACT_STYLE[issue["impact"]]
                st.markdown(
                    f"<div style='background:#FFFFFF;border:1px solid #E5E7EB;"
                    f"border-left:4px solid {fg};border-radius:8px;"
                    f"padding:12px 14px;margin-bottom:8px;"
                    f"display:flex;align-items:flex-start;gap:10px;'>"
                    f"<span style='background:{bg};color:{fg};border-radius:4px;"
                    f"padding:2px 7px;font-size:10px;font-weight:700;white-space:nowrap;'>"
                    f"#{issue['rank']} {issue['impact']}</span>"
                    f"<span style='font-size:13px;color:#374151;line-height:1.6;'>"
                    f"{issue['description']}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        # ── Recommendations with checkboxes — select what to push ────────────
        st.markdown(
            "<div style='font-size:11px;font-weight:700;color:#15803D;"
            "text-transform:uppercase;letter-spacing:0.05em;"
            "margin-top:14px;margin-bottom:6px;'>"
            "Select Recommendations to Push</div>",
            unsafe_allow_html=True,
        )
        select_all_perf = st.checkbox("Select All", key=f"perf_all_{_ck}", value=False)
        selected_recs = []
        for i, rec in enumerate(perf["recommendations"]):
            checked = st.checkbox(
                rec,
                key=f"perf_cb_{_ck}_{i}",
                value=select_all_perf,
            )
            if checked or select_all_perf:
                selected_recs.append(rec)

        # ── Push Optimisation button — disabled until at least one rec selected ─
        push = perf["push_data"]
        st.markdown("<div style='margin-top:16px;'>", unsafe_allow_html=True)
        no_perf_selection = len(selected_recs) == 0

        col_pbtn, col_presp = st.columns([1, 3])
        with col_pbtn:
            if st.button(
                f"🚀 Push Optimisation — {c['client']}",
                key=f"perf_push_{_ck}",
                type="primary",
                disabled=no_perf_selection,
                help="Select at least one optimisation to push" if no_perf_selection else None,
            ):
                st.session_state[f"perf_pushed_{_ck}"] = True
                # Store the selected recommendations at push time so the response stays stable
                st.session_state[f"perf_pushed_recs_{_ck}"] = selected_recs[:]

            st.markdown(
                f"<div style='font-size:12px;color:#6B7280;margin-top:8px;line-height:1.7;'>"
                f"<strong style='color:#111827;'>{c['campaign_id']}</strong><br>"
                f"{c['dsp']} &nbsp;·&nbsp; {c['buy_type']}<br>"
                f"Performance score: <span style='color:{sc};font-weight:700;'>{score}/100</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

        with col_presp:
            if st.session_state.get(f"perf_pushed_{_ck}"):
                # Use the recommendations that were selected at push time
                pushed_recs = st.session_state.get(
                    f"perf_pushed_recs_{_ck}",
                    selected_recs,
                )
                perf_response = {
                    "status":       200,
                    "message":      "Performance optimisation applied successfully",
                    "campaign_id":  c["campaign_id"],
                    "advertiser":   c["client"],
                    "dsp":          c["dsp"],
                    "optimisation": pushed_recs,
                    "projected_outcomes": {
                        "ctr":                     push["projected_ctr"],
                        "cpm":                     push["projected_cpm"],
                        "confidence":              push["confidence"],
                        "applied_recommendations": pushed_recs,
                    },
                    "timestamp": f"{TODAY.isoformat()}T09:14:32+10:00",
                }
                st.code(json.dumps(perf_response, indent=2), language="json")
            else:
                st.markdown(
                    "<div style='background:#F9FAFB;border:1px dashed #D1D5DB;"
                    "border-radius:8px;padding:28px;text-align:center;"
                    "color:#9CA3AF;font-size:13px;'>"
                    "Select recommendations above then click the button to simulate "
                    "pushing the performance optimisation and see the projected API response.</div>",
                    unsafe_allow_html=True,
                )

        st.markdown("</div>", unsafe_allow_html=True)

print("Campaign Monitor loaded.")
