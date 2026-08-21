"""
Shared API mock data for all API-section pages (Performance & Insights, Live Campaigns).

generate_api_mock_data() — 30-day performance DataFrame (used by Performance & Insights)
get_pacing_mock_data()   — campaign + line item pacing dicts (used by Live Campaigns)

Both functions use the same underlying dataset so campaign names, line items,
and DSPs are consistent across every API-section page.
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta

# ── Reference dates ────────────────────────────────────────────────────────────
# MOCK_TODAY  = last day of the 30-day performance data window
# MOCK_Q3_*   = Q3 2026 flight dates used for pacing calculations
MOCK_TODAY    = date(2026, 7, 28)
MOCK_Q3_START = date(2026, 7, 1)
MOCK_Q3_END   = date(2026, 9, 30)

# ── Q3 campaign budgets (AUD) and flight dates ────────────────────────────────
# Used by get_pacing_mock_data() to compute pacing against actual spend.
# Budgets are set so the 28-day spend (Jul 1–28) produces a realistic mix of
# On track, At risk, Critical, and Overpacing statuses.
CAMPAIGN_BUDGETS = {
    "Woolworths_Fresh_Food_Brand_Q3_2026":             {"budget": 280_000, "start": MOCK_Q3_START, "end": MOCK_Q3_END},
    "CBA_HomeLoan_Prospecting_Q3_2026":                {"budget": 185_000, "start": MOCK_Q3_START, "end": MOCK_Q3_END},
    "Toyota_GR_Sport_Prospecting_Q3_2026":             {"budget": 100_000, "start": MOCK_Q3_START, "end": MOCK_Q3_END},
    "Woolworths_Everyday_Rewards_Retargeting_Q3_2026": {"budget": 140_000, "start": MOCK_Q3_START, "end": MOCK_Q3_END},
    "CBA_NetBank_Retargeting_Q3_2026":                 {"budget": 200_000, "start": MOCK_Q3_START, "end": MOCK_Q3_END},
    "Toyota_RAV4_Launch_Q3_2026":                      {"budget": 220_000, "start": MOCK_Q3_START, "end": MOCK_Q3_END},
}


@st.cache_data
def generate_api_mock_data():
    """
    Generate 30 days of realistic mock data for Woolworths, Commonwealth Bank,
    and Toyota Australia programmatic campaigns across DV360, TTD, and Amazon DSP.
    Uses a fixed random seed so numbers are consistent across reruns.
    Returns a DataFrame with the same column structure as a normalised DSP export.

    DSP split: DV360 (3 campaigns) · TTD (2 campaigns) · Amazon (1 campaign)
    Environment values: Web · In-App · CTV · Audio
    Buy type values: Open Auction · Programmatic Guaranteed · Preferred Deal · Private Auction
    """
    import random as _rnd
    from datetime import date as _date, timedelta as _td
    rng   = _rnd.Random(42)
    today = _date(2026, 7, 28)
    start = today - _td(days=29)

    # Each campaign config includes:
    #   dsp         — explicit DSP assignment (guarantees all 3 DSPs always appear)
    #   environments — Web / In-App / CTV / Audio per line item
    #   is_video     — True for line items that generate VTR / video_views
    CAMPAIGNS = [
        # ── DV360 campaigns (3) ──────────────────────────────────────────────
        {
            "advertiser":      "Woolworths",
            "campaign":        "Woolworths_Fresh_Food_Brand_Q3_2026",
            "insertion_order": "WOW_FreshFood_Brand_IO_Q3",
            "dsp":             "DV360",
            "line_items":      [
                "Fresh Food Display - Desktop",
                "Fresh Food Display - Mobile",
                "Fresh Food Video - YouTube",
                "Brand Awareness - CTV",
            ],
            "environments":    ["Web", "In-App", "Web", "CTV"],
            "devices":         ["Desktop", "Mobile", "Desktop", "Connected TV"],
            "is_video":        [False, False, True, True],
            "imp_range":       (90000, 160000),
            "ctr_range":       (0.003, 0.005),
            "cpm_range":       (4.5, 7.0),
            "vtr_range":       (0.48, 0.62),
        },
        {
            "advertiser":      "Commonwealth Bank",
            "campaign":        "CBA_HomeLoan_Prospecting_Q3_2026",
            "insertion_order": "CBA_HomeLoan_Prospecting_IO",
            "dsp":             "DV360",
            "line_items":      [
                "Home Loan - Premium Finance Sites",
                "Home Loan - Desktop Prospecting",
                "Home Loan - Mobile Display",
                "Home Loan - News Premium",
            ],
            "environments":    ["Web", "Web", "In-App", "Web"],
            "devices":         ["Desktop", "Desktop", "Mobile", "Desktop"],
            "is_video":        [False, False, False, False],
            "imp_range":       (35000, 70000),
            "ctr_range":       (0.002, 0.004),
            "cpm_range":       (14.0, 22.0),
            "vtr_range":       (0.0, 0.0),
        },
        {
            "advertiser":      "Toyota Australia",
            "campaign":        "Toyota_GR_Sport_Prospecting_Q3_2026",
            "insertion_order": "Toyota_GR_Sport_Prospecting_IO",
            "dsp":             "DV360",
            "line_items":      [
                "GR Sport Display - Premium Sports Sites",
                "GR Sport Video - Pre-roll",
                "GR Sport - Auto Enthusiasts Display",
            ],
            "environments":    ["Web", "Web", "Web"],
            "devices":         ["Desktop", "Desktop", "Mobile"],
            "is_video":        [False, True, False],
            "imp_range":       (25000, 55000),
            "ctr_range":       (0.003, 0.006),
            "cpm_range":       (16.0, 24.0),
            "vtr_range":       (0.50, 0.65),
        },
        # ── TTD campaigns (2) ────────────────────────────────────────────────
        {
            "advertiser":      "Woolworths",
            "campaign":        "Woolworths_Everyday_Rewards_Retargeting_Q3_2026",
            "insertion_order": "WOW_EverydayRewards_Retargeting_IO",
            "dsp":             "TTD",
            "line_items":      [
                "Rewards Retargeting - Desktop Web",
                "Rewards Retargeting - Mobile In-App",
                "Rewards Audio - Podcast Streaming",
                "Rewards CTV - Connected TV",
            ],
            "environments":    ["Web", "In-App", "Audio", "CTV"],
            "devices":         ["Desktop", "Mobile", "Mobile", "Connected TV"],
            "is_video":        [False, False, False, True],
            "imp_range":       (20000, 45000),
            "ctr_range":       (0.008, 0.016),
            "cpm_range":       (5.5, 8.5),
            "vtr_range":       (0.38, 0.52),
        },
        {
            "advertiser":      "Commonwealth Bank",
            "campaign":        "CBA_NetBank_Retargeting_Q3_2026",
            "insertion_order": "CBA_NetBank_Retargeting_IO",
            "dsp":             "TTD",
            "line_items":      [
                "NetBank Retargeting - Web Display",
                "NetBank Video - Pre-roll Web",
                "NetBank Mobile App Retargeting",
                "NetBank Audio - Streaming Radio",
            ],
            "environments":    ["Web", "Web", "In-App", "Audio"],
            "devices":         ["Desktop", "Desktop", "Mobile", "Mobile"],
            "is_video":        [False, True, False, False],
            "imp_range":       (18000, 40000),
            "ctr_range":       (0.005, 0.012),
            "cpm_range":       (12.0, 18.0),
            "vtr_range":       (0.52, 0.68),
        },
        # ── Amazon DSP campaign (1) ──────────────────────────────────────────
        {
            "advertiser":      "Toyota Australia",
            "campaign":        "Toyota_RAV4_Launch_Q3_2026",
            "insertion_order": "Toyota_RAV4_Launch_IO",
            "dsp":             "Amazon",
            "line_items":      [
                "RAV4 CTV - Connected TV",
                "RAV4 Display - Auto Enthusiast Sites",
                "RAV4 Video - Mobile In-App",
                "RAV4 In-App Display",
            ],
            "environments":    ["CTV", "Web", "In-App", "In-App"],
            "devices":         ["Connected TV", "Desktop", "Mobile", "Mobile"],
            "is_video":        [True, False, True, False],
            "imp_range":       (60000, 120000),
            "ctr_range":       (0.002, 0.005),
            "cpm_range":       (8.0, 14.0),
            "vtr_range":       (0.58, 0.74),
        },
    ]

    # Buy type pool — weighted: Open Auction ~55%, PG ~20%, Preferred Deal ~15%, Private Auction ~10%
    _BUY_TYPE_POOL = (
        ["Open Auction"] * 11 +
        ["Programmatic Guaranteed"] * 4 +
        ["Preferred Deal"] * 3 +
        ["Private Auction"] * 2
    )

    rows = []
    for day_offset in range(30):
        current_date = start + _td(days=day_offset)

        for camp in CAMPAIGNS:
            dsp = camp["dsp"]
            for i, li in enumerate(camp["line_items"]):
                env      = camp["environments"][i]
                device   = camp["devices"][i]
                is_video = camp["is_video"][i]

                impressions = rng.randint(*camp["imp_range"])
                ctr         = rng.uniform(*camp["ctr_range"])
                clicks      = max(round(impressions * ctr), 1)
                cpm         = rng.uniform(*camp["cpm_range"])
                spend_usd   = round(impressions / 1000 * cpm, 2)
                conversions = max(round(clicks * rng.uniform(0.02, 0.08)), 0)

                # VTR only applies to video line items (CTV, pre-roll, etc.)
                vtr         = rng.uniform(*camp["vtr_range"]) if is_video else 0.0
                video_views = round(impressions * vtr)         if is_video else 0

                rows.append({
                    "date":            pd.Timestamp(current_date),
                    "advertiser":      camp["advertiser"],
                    "campaign":        camp["campaign"],
                    "insertion_order": camp["insertion_order"],
                    "line_item":       li,
                    "creative":        f"{li} - Creative 1",
                    "device_type":     device,
                    "environment":     env,
                    "impressions":     impressions,
                    "clicks":          clicks,
                    "spend_usd":       spend_usd,
                    "conversions":     conversions,
                    "video_views":     video_views,
                    "dsp_source":      dsp,
                    "buy_type":        rng.choice(_BUY_TYPE_POOL),
                    "source_file":     "api_mock_data",
                })

    df = pd.DataFrame(rows)
    # Recalculate CTR and CPM from raw numbers
    df["ctr"] = df["clicks"] / df["impressions"]
    df["cpm"] = df["spend_usd"] / df["impressions"] * 1000
    return df


def get_pacing_mock_data():
    """
    Derive campaign and line item pacing data from the shared API mock dataset.

    Filters the performance DataFrame to the Q3 flight period (Jul 1–28),
    aggregates spend per campaign and line item, then joins with CAMPAIGN_BUDGETS
    to compute pacing indices.

    Returns (campaigns_list, campaign_breakdown_dict) in the shape that
    live_campaigns.py expects for MOCK_CAMPAIGNS and MOCK_CAMPAIGN_BREAKDOWN.

    Pacing index = (actual spend / expected spend) × 100
    Expected spend = budget × (days elapsed / total flight days)
    """
    # Buy type short-code mapping for the pacing page badges
    BUY_TYPE_MAP = {
        "open auction":            "Open",
        "programmatic guaranteed": "PG",
        "preferred deal":          "PMP",
        "private auction":         "PMP",
    }

    # DSP label mapping — performance data uses "Amazon"; pacing page badge expects "Amazon DSP"
    DSP_LABEL_MAP = {"Amazon": "Amazon DSP"}

    df = generate_api_mock_data()

    # Filter to Q3 flight period: Jul 1 to Jul 28 (28 days of data within the flight)
    df_q3 = df[
        (df["date"].dt.date >= MOCK_Q3_START) &
        (df["date"].dt.date <= MOCK_TODAY)
    ].copy()

    # Pacing reference date is MOCK_TODAY (Jul 28)
    today = MOCK_TODAY

    # Aggregate spend and impressions per (advertiser, campaign, dsp, line_item)
    li_agg = (
        df_q3.groupby(["advertiser", "campaign", "dsp_source", "line_item"])
        .agg(
            spend       = ("spend_usd",   "sum"),
            impressions = ("impressions", "sum"),
        )
        .reset_index()
    )

    # Get the modal buy_type per campaign for the campaign-level badge
    camp_buy_type = (
        df_q3.groupby("campaign")["buy_type"]
        .agg(lambda x: x.mode().iloc[0] if not x.empty else "Open Auction")
        .to_dict()
    )

    campaigns  = []
    breakdown  = {}

    for (advertiser, campaign_name, dsp_raw), grp in li_agg.groupby(
        ["advertiser", "campaign", "dsp_source"]
    ):
        cfg          = CAMPAIGN_BUDGETS.get(campaign_name, {})
        total_budget = cfg.get("budget", 0)
        start        = cfg.get("start", MOCK_Q3_START)
        end          = cfg.get("end",   MOCK_Q3_END)
        total_spent  = grp["spend"].sum()

        # Pacing calculation — same formula as calc_pacing() in live_campaigns.py
        total_days     = (end - start).days
        days_elapsed   = (today - start).days
        days_remaining = (end - today).days
        expected_spend = (total_budget * days_elapsed / total_days) if total_days > 0 else 0
        pacing_index   = (total_spent / expected_spend * 100) if expected_spend > 0 else 0

        if pacing_index < 75:
            risk, risk_color, risk_bg = "Critical",   "#EF4444", "#FEF2F2"
        elif pacing_index < 92:
            risk, risk_color, risk_bg = "At risk",    "#F59E0B", "#FFFBEB"
        elif pacing_index <= 110:
            risk, risk_color, risk_bg = "On track",   "#10B981", "#ECFDF5"
        else:
            risk, risk_color, risk_bg = "Overpacing", "#F5A623", "#FFF4E0"

        # Short-code buy type for the badge
        raw_bt  = camp_buy_type.get(campaign_name, "Open Auction")
        buy_type_code = BUY_TYPE_MAP.get(raw_bt.lower(), "Open")

        # Normalise DSP label
        dsp = DSP_LABEL_MAP.get(dsp_raw, dsp_raw)

        # Use campaign name as the lookup key (consistent with how CAMPAIGN_BREAKDOWN is keyed)
        campaign_id = campaign_name

        campaigns.append({
            "client":         advertiser,
            "campaign_name":  campaign_name,
            "buy_type":       buy_type_code,
            "campaign_id":    campaign_id,
            "dsp":            dsp,
            "budget":         total_budget,
            "spent":          total_spent,
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
        })

        # Build line item budget + spend entries.
        # Budget per line item = campaign budget × (line item spend share).
        li_list = []
        for _, li_row in grp.iterrows():
            li_budget = (
                total_budget * (li_row["spend"] / total_spent)
                if total_spent > 0 else 0
            )
            li_list.append({
                "name":   li_row["line_item"],
                "budget": li_budget,
                "spent":  li_row["spend"],
            })

        breakdown[campaign_id] = {
            "campaigns": [{
                "name":       campaign_name,
                "budget":     total_budget,
                "spent":      total_spent,
                "line_items": li_list,
            }]
        }

    return campaigns, breakdown


print("Done. mock_data module loaded.")
