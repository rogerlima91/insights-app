import os
import time
import anthropic
import streamlit as st

# ── Global CSS (matches app styling — STYLE LOCK) ──────────────────────────────
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

# ── Mock publisher portfolio data ─────────────────────────────────────────────
# Simulates a PubMatic CSM's ANZ publisher portfolio. All figures in AUD.
# Reporting date: 2 May 2026 (fixed for demo).
PUBLISHERS = [
    {
        "name":     "Nine Entertainment",
        "formats":  "Display + Video",
        "ecpm":     8.40,
        "fill_rate": 0.71,
        "bid_density": 4.2,
        "floor":    7.00,
        "revenue":  284_000,
        "target":   320_000,
    },
    {
        "name":     "News Corp AU",
        "formats":  "Display + CTV",
        "ecpm":     11.20,
        "fill_rate": 0.68,
        "bid_density": 3.1,
        "floor":    12.00,
        "revenue":  412_000,
        "target":   430_000,
    },
    {
        "name":     "Seven Network",
        "formats":  "Video + CTV",
        "ecpm":     16.80,
        "fill_rate": 0.54,
        "bid_density": 2.8,
        "floor":    18.00,
        "revenue":  198_000,
        "target":   290_000,
    },
    {
        "name":     "REA Group",
        "formats":  "Display",
        "ecpm":     9.60,
        "fill_rate": 0.83,
        "bid_density": 5.7,
        "floor":    8.00,
        "revenue":  376_000,
        "target":   380_000,
    },
    {
        "name":     "Seek",
        "formats":  "Display + Video",
        "ecpm":     7.20,
        "fill_rate": 0.62,
        "bid_density": 3.4,
        "floor":    9.00,
        "revenue":  143_000,
        "target":   200_000,
    },
    {
        "name":     "Drive.com.au",
        "formats":  "Display",
        "ecpm":     6.10,
        "fill_rate": 0.78,
        "bid_density": 4.8,
        "floor":    5.50,
        "revenue":  89_000,
        "target":   95_000,
    },
]

# ── Hardcoded yield gap diagnostics per publisher ──────────────────────────────
# Realistic flags a PubMatic CSM would surface from floor price analytics,
# bid stream data, and format configuration audits.
DIAGNOSTICS = {
    "Seven Network": {
        "top_blocking_buyer": "Xandr (AppNexus)",
        "blocking_reason":    "Bid ceiling of A$15.50 on Xandr DSP below Seven's A$18.00 floor — responsible for 41% of lost bid volume",
        "flags": [
            {
                "signal": "Floor vs Clearing Price",
                "impact": "HIGH",
                "detail": (
                    "Floor price of A$18.00 is rejecting 46% of bids — bid density of 2.8 and "
                    "clearing data suggests the market is pricing this inventory at A$14.50. "
                    "Estimated monthly recovery from reducing floor to A$15.00: A$38k"
                ),
            },
            {
                "signal": "Bid Density",
                "impact": "MEDIUM",
                "detail": (
                    "Only 2.8 active buyers competing per auction — well below the 5+ needed "
                    "for healthy price competition on CTV. Activating 2 additional CTV-specialist "
                    "DSPs (e.g. Magnite, FreeWheel) could lift eCPM by 12–18%"
                ),
            },
        ],
    },
    "Seek": {
        "top_blocking_buyer": "DV360 (Google)",
        "blocking_reason":    "DV360 has no video line items targeting Seek — all spend configured against display only, leaving video inventory unmonetised",
        "flags": [
            {
                "signal": "Format Mismatch",
                "impact": "HIGH",
                "detail": (
                    "Fill rate of 62% driven by format mismatch — 74% of unfilled requests are "
                    "video but only display demand is configured across all buyer seats. "
                    "Activating video demand via OpenWrap could recover A$29k/month"
                ),
            },
            {
                "signal": "Floor vs eCPM",
                "impact": "MEDIUM",
                "detail": (
                    "Floor of A$9.00 is 25% above the current eCPM of A$7.20 on display — "
                    "clearing price data shows A$7.80 is the 90th percentile bid. "
                    "Adjusting display floor to A$7.50 would improve fill without sacrificing yield"
                ),
            },
        ],
    },
    "News Corp AU": {
        "top_blocking_buyer": "The Trade Desk",
        "blocking_reason":    "TTD's audience-indexed bids for News Corp inventory average A$10.20 — 15% below the A$12.00 floor, blocking the largest single buyer",
        "flags": [
            {
                "signal": "Floor Above Market",
                "impact": "HIGH",
                "detail": (
                    "Floor above market — 38% of bids are blocked below the A$12.00 floor "
                    "despite clearing at A$10.20 average. The bid stream shows sufficient "
                    "demand at A$10.50–A$11.00. Recovery potential from floor adjustment: A$18k/month"
                ),
            },
            {
                "signal": "CTV Demand Gap",
                "impact": "MEDIUM",
                "detail": (
                    "CTV inventory has only 3.1 active buyers — premium content commands "
                    "higher CPMs but demand hasn't been diversified. Adding Freewheel and "
                    "SpotX as additional CTV demand partners could lift CTV eCPM by A$2–3"
                ),
            },
        ],
    },
}


# ── PubMatic push simulator data ──────────────────────────────────────────────
# Hardcoded but realistic actions and API responses per at-risk publisher.
# Keyed by publisher name. Only publishers with health score < 70 get a panel.
PUBMATIC_PUSH_DATA = {
    "Seven Network": {
        "publisher_id": "PUB-77400",
        "actions": [
            "Reduce video floor  A$18.00 → A$15.50",
            "Activate OpenWrap for CTV supply",
            "Onboard 2 incremental BVOD buyers into ANZ Video PMP pipeline",
        ],
        "recovery_low":  38_000,
        "recovery_high": 46_000,
        "api_response": (
            "PATCH /api/v2/publisher/PUB-77400/settings  →  HTTP 200 OK\n"
            "\n"
            "✓  Floor price updated:          A$18.00 → A$15.50  (Video, CTV)\n"
            "✓  OpenWrap CTV wrapper:          deployed across 4 ad units\n"
            "✓  Buyer onboarding submitted:    ANZ Video PMP pipeline (+2 seats)\n"
            "\n"
            "Projected monthly revenue recovery:  A$38,000 – A$46,000\n"
            "Timestamp: 2026-05-02 09:14:33 UTC"
        ),
    },
    "Seek": {
        "publisher_id": "PUB-58291",
        "actions": [
            "Enable video demand — format mismatch causing 38% unfilled requests",
            "Adjust display floor  A$9.00 → A$7.50",
        ],
        "recovery_low":  29_000,
        "recovery_high": 35_000,
        "api_response": (
            "PATCH /api/v2/publisher/PUB-58291/settings  →  HTTP 200 OK\n"
            "\n"
            "✓  Video demand enabled:          OpenWrap video wrapper activated (6 ad units)\n"
            "✓  Display floor updated:         A$9.00 → A$7.50 across 6 display line items\n"
            "\n"
            "Projected monthly revenue recovery:  A$29,000 – A$35,000\n"
            "Timestamp: 2026-05-02 09:14:33 UTC"
        ),
    },
}


def calc_health(p):
    """
    Calculate yield health score (0–100) for a publisher.
    Each of the four signals scores 0–25. Sum = total health score.
    """
    # eCPM relative to floor — high floor blocking bids pulls this down
    ecpm_score    = min((p["ecpm"] / p["floor"]) * 25, 25)
    # Fill rate — direct signal of inventory monetisation efficiency
    fill_score    = p["fill_rate"] * 25
    # Bid density — more active buyers = better competition = higher CPMs
    density_score = min((p["bid_density"] / 6) * 25, 25)
    # Revenue delivery vs monthly target
    rev_score     = min((p["revenue"] / p["target"]) * 25, 25)

    total = ecpm_score + fill_score + density_score + rev_score

    if total < 50:
        risk, risk_color, risk_bg = "Critical",   "#EF4444", "#FEF2F2"
    elif total < 70:
        risk, risk_color, risk_bg = "At risk",    "#F59E0B", "#FFFBEB"
    elif total <= 85:
        risk, risk_color, risk_bg = "Healthy",    "#10B981", "#ECFDF5"
    else:
        risk, risk_color, risk_bg = "Optimised",  "#7C3AED", "#F5F3FF"

    return {
        **p,
        "ecpm_score":    ecpm_score,
        "fill_score":    fill_score,
        "density_score": density_score,
        "rev_score":     rev_score,
        "health_score":  total,
        "risk":          risk,
        "risk_color":    risk_color,
        "risk_bg":       risk_bg,
        "revenue_gap":   p["target"] - p["revenue"],
    }


# Enrich all publishers with health scores
PORTFOLIO = [calc_health(p) for p in PUBLISHERS]

# Publishers needing attention in diagnostics: anything below Optimised (< 85)
NEEDS_ATTENTION = [p for p in PORTFOLIO if p["health_score"] < 85]

# ── Anthropic API client ───────────────────────────────────────────────────────
api_key = (
    st.secrets.get("ANTHROPIC_API_KEY")
    if "ANTHROPIC_API_KEY" in st.secrets
    else os.environ.get("ANTHROPIC_API_KEY")
)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE HEADER
# ══════════════════════════════════════════════════════════════════════════════
st.title("Publisher Revenue Intelligence")
st.markdown(
    "<p style='color:#6b7280;font-size:14px;margin-top:-12px;'>"
    "PubMatic CSM portfolio view — yield health, gap diagnostics and AI revenue recommendations "
    "for ANZ publishers. "
    "All figures in AUD &nbsp;·&nbsp; Reporting date: 2 May 2026"
    "</p>",
    unsafe_allow_html=True,
)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — Portfolio summary cards
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("Portfolio Overview")

total_revenue    = sum(p["revenue"]      for p in PORTFOLIO)
total_gap        = sum(p["revenue_gap"]  for p in PORTFOLIO)
at_risk_count    = sum(1 for p in PORTFOLIO if p["risk"] in ("Critical", "At risk"))
avg_health       = sum(p["health_score"] for p in PORTFOLIO) / len(PORTFOLIO)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Monthly Revenue",  f"A${total_revenue / 1_000:.0f}k")

# Revenue gap styled red inline if over A$50k
gap_label = f"A${total_gap / 1_000:.0f}k"
c2.metric("Revenue Gap vs Target", gap_label, delta=f"-A${total_gap / 1_000:.0f}k below target", delta_color="inverse")

c3.metric("Publishers At Risk",    at_risk_count, delta=f"{at_risk_count} require action", delta_color="inverse")
c4.metric("Avg Portfolio Health",  f"{avg_health:.1f} / 100")

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — Publisher health table
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("Publisher Health Table")


def health_badge(risk, risk_color, risk_bg, score):
    """Render a coloured health badge with the numeric score."""
    return (
        f"<span style='background:{risk_bg};color:{risk_color};"
        f"padding:3px 10px;border-radius:20px;font-size:12px;"
        f"font-weight:700;white-space:nowrap;'>"
        f"{risk} &nbsp;{score:.0f}"
        f"</span>"
    )


def progress_bar(actual, target):
    """Render a small inline progress bar showing revenue vs target."""
    pct = min(actual / target * 100, 100)
    colour = "#10B981" if pct >= 90 else "#F59E0B" if pct >= 75 else "#EF4444"
    return (
        f"<div style='font-size:13px;'>"
        f"A${actual / 1_000:.0f}k / A${target / 1_000:.0f}k"
        f"<div style='background:#E5E7EB;border-radius:4px;height:5px;margin-top:4px;width:120px;'>"
        f"<div style='background:{colour};width:{pct:.0f}%;height:5px;border-radius:4px;'></div>"
        f"</div></div>"
    )


# Build table header
table_html = """
<table style='width:100%;border-collapse:collapse;background:#FFFFFF;
              border-radius:12px;overflow:hidden;
              box-shadow:0 4px 12px rgba(0,0,0,0.08);font-size:13px;'>
  <thead>
    <tr style='background:#F9FAFB;border-bottom:2px solid #E5E7EB;'>
      <th style='text-align:left;padding:12px 16px;color:#6B7280;font-weight:600;'>Publisher</th>
      <th style='text-align:left;padding:12px 16px;color:#6B7280;font-weight:600;'>Formats</th>
      <th style='text-align:right;padding:12px 16px;color:#6B7280;font-weight:600;'>eCPM</th>
      <th style='text-align:right;padding:12px 16px;color:#6B7280;font-weight:600;'>Fill Rate</th>
      <th style='text-align:right;padding:12px 16px;color:#6B7280;font-weight:600;'>Bid Density</th>
      <th style='text-align:right;padding:12px 16px;color:#6B7280;font-weight:600;'>Floor</th>
      <th style='text-align:left;padding:12px 16px;color:#6B7280;font-weight:600;'>Revenue vs Target</th>
      <th style='text-align:center;padding:12px 16px;color:#6B7280;font-weight:600;'>Health</th>
    </tr>
  </thead>
  <tbody>
"""

for p in PORTFOLIO:
    badge = health_badge(p["risk"], p["risk_color"], p["risk_bg"], p["health_score"])
    bar   = progress_bar(p["revenue"], p["target"])
    table_html += (
        f"<tr style='border-bottom:1px solid #F3F4F6;'>"
        f"<td style='padding:14px 16px;font-weight:600;color:#111827;'>{p['name']}</td>"
        f"<td style='padding:14px 16px;color:#6B7280;'>{p['formats']}</td>"
        f"<td style='padding:14px 16px;text-align:right;'>A${p['ecpm']:.2f}</td>"
        f"<td style='padding:14px 16px;text-align:right;'>{p['fill_rate']*100:.0f}%</td>"
        f"<td style='padding:14px 16px;text-align:right;'>{p['bid_density']:.1f}</td>"
        f"<td style='padding:14px 16px;text-align:right;'>A${p['floor']:.2f}</td>"
        f"<td style='padding:14px 16px;'>{bar}</td>"
        f"<td style='padding:14px 16px;text-align:center;'>{badge}</td>"
        f"</tr>"
    )

table_html += "</tbody></table>"
st.markdown(table_html, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — Yield gap diagnostics
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("Yield Gap Diagnostics")
st.markdown(
    "<p style='color:#6b7280;font-size:14px;margin-top:-8px;margin-bottom:16px;'>"
    "Expanded analysis for publishers below Optimised health score. "
    "Flags are sourced from floor price analytics, bid stream data, and format configuration audits."
    "</p>",
    unsafe_allow_html=True,
)

# Impact colour coding
IMPACT_COLOURS = {
    "HIGH":   ("#EF4444", "#FEF2F2"),
    "MEDIUM": ("#F59E0B", "#FFFBEB"),
    "LOW":    ("#10B981", "#ECFDF5"),
}

for p in NEEDS_ATTENTION:
    diag = DIAGNOSTICS.get(p["name"])

    # Expander label shows name + health badge inline
    label = f"{p['name']}  —  {p['risk']}  ({p['health_score']:.0f}/100)"
    with st.expander(label, expanded=False):

        # ── Health score breakdown ─────────────────────────────────────────
        st.markdown("**Health Score Breakdown**")
        sub_col1, sub_col2, sub_col3, sub_col4 = st.columns(4)

        def score_card(col, label_text, score, tooltip):
            """Render a small score card for one of the four sub-signals."""
            colour = "#10B981" if score >= 20 else "#F59E0B" if score >= 13 else "#EF4444"
            col.markdown(
                f"<div style='background:#F9FAFB;border-radius:10px;padding:12px 14px;"
                f"border-left:4px solid {colour};'>"
                f"<div style='font-size:11px;color:#6B7280;font-weight:600;"
                f"text-transform:uppercase;letter-spacing:0.05em;'>{label_text}</div>"
                f"<div style='font-size:22px;font-weight:700;color:{colour};margin-top:4px;'>"
                f"{score:.1f}<span style='font-size:13px;color:#9CA3AF;'>/25</span></div>"
                f"<div style='font-size:11px;color:#9CA3AF;margin-top:2px;'>{tooltip}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

        score_card(sub_col1, "eCPM vs Floor",   p["ecpm_score"],    f"eCPM A${p['ecpm']:.2f} / Floor A${p['floor']:.2f}")
        score_card(sub_col2, "Fill Rate",        p["fill_score"],    f"{p['fill_rate']*100:.0f}% fill")
        score_card(sub_col3, "Bid Density",      p["density_score"], f"{p['bid_density']:.1f} buyers/auction")
        score_card(sub_col4, "Revenue vs Target",p["rev_score"],     f"A${p['revenue']/1_000:.0f}k / A${p['target']/1_000:.0f}k")

        if not diag:
            st.markdown("_No specific flags available for this publisher._")
            continue

        # ── Top blocking buyer ─────────────────────────────────────────────
        st.markdown("---")
        st.markdown(
            f"**Top Blocking Buyer:** {diag['top_blocking_buyer']}<br>"
            f"<span style='color:#6B7280;font-size:13px;'>{diag['blocking_reason']}</span>",
            unsafe_allow_html=True,
        )

        # ── Yield gap flags ────────────────────────────────────────────────
        st.markdown("**Yield Gap Flags**")
        for flag in diag["flags"]:
            impact_color, impact_bg = IMPACT_COLOURS[flag["impact"]]
            st.markdown(
                f"<div style='background:{impact_bg};border-left:4px solid {impact_color};"
                f"border-radius:8px;padding:12px 16px;margin-bottom:10px;'>"
                f"<div style='display:flex;align-items:center;gap:8px;margin-bottom:6px;'>"
                f"<span style='background:{impact_color};color:#fff;font-size:10px;"
                f"font-weight:700;padding:2px 8px;border-radius:20px;'>{flag['impact']}</span>"
                f"<span style='font-weight:600;color:#111827;'>{flag['signal']}</span>"
                f"</div>"
                f"<p style='margin:0;font-size:13px;color:#374151;line-height:1.6;'>{flag['detail']}</p>"
                f"</div>",
                unsafe_allow_html=True,
            )

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — AI revenue recommendations
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("AI Revenue Recommendations")
st.markdown(
    "<p style='color:#6b7280;font-size:14px;margin-top:-8px;margin-bottom:16px;'>"
    "Claude reviews the full portfolio and identifies the highest-impact actions this week."
    "</p>",
    unsafe_allow_html=True,
)

if st.button("Generate AI Recommendations", type="primary"):
    if not api_key:
        st.warning("No Anthropic API key found. Add `ANTHROPIC_API_KEY` to your Streamlit secrets.")
    else:
        # Build a plain-text portfolio summary to feed into the prompt
        lines = []
        for p in PORTFOLIO:
            lines.append(
                f"- {p['name']} | Formats: {p['formats']} | eCPM: A${p['ecpm']:.2f} | "
                f"Fill rate: {p['fill_rate']*100:.0f}% | Bid density: {p['bid_density']:.1f} | "
                f"Floor: A${p['floor']:.2f} | Revenue: A${p['revenue']/1_000:.0f}k / "
                f"Target: A${p['target']/1_000:.0f}k | Health: {p['health_score']:.0f}/100 ({p['risk']})"
            )
        portfolio_summary = "\n".join(lines)

        prompt = (
            "You are a senior PubMatic Customer Success Manager reviewing an ANZ publisher portfolio. "
            "Today is 2 May 2026. All figures are in AUD.\n\n"
            "Publisher portfolio:\n"
            f"{portfolio_summary}\n\n"
            "Provide an executive-ready analysis structured exactly as follows:\n\n"
            "**Priority Actions This Week**\n"
            "Identify the 2 publishers that need immediate action. For each, give:\n"
            "- The exact floor price change recommended (if applicable)\n"
            "- Any format or demand configuration changes\n"
            "- Specific buyer diversification tactics\n"
            "- Estimated AUD revenue recovery per month\n\n"
            "**Portfolio Health Insight**\n"
            "One paragraph on the overall monetisation health of this portfolio — "
            "patterns across fill rate, bid density, and floor pricing strategy.\n\n"
            "**CTV & Video Opportunity**\n"
            "One forward-looking recommendation about the CTV or video opportunity in the ANZ market "
            "and how this portfolio is positioned to capture it.\n\n"
            "Tone: executive-ready. This is presented to a publisher's Head of Revenue. "
            "Be specific — cite publisher names, AUD figures, and product levers."
        )

        with st.spinner("Analysing portfolio with Claude..."):
            client_ai = anthropic.Anthropic(api_key=api_key)
            response = client_ai.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1200,
                messages=[{"role": "user", "content": prompt}],
            )
            st.session_state["pub_ai_recommendations"] = response.content[0].text

# Display persisted AI recommendations
if "pub_ai_recommendations" in st.session_state:
    st.markdown(
        "<div style='background:#FFFFFF;border-radius:12px;padding:24px 28px;"
        "box-shadow:0 4px 12px rgba(0,0,0,0.08);margin-top:8px;'>"
        + st.session_state["pub_ai_recommendations"].replace("\n", "<br>") +
        "</div>",
        unsafe_allow_html=True,
    )

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — Quarterly growth strategy generator
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("Quarterly Growth Strategy Generator")
st.markdown(
    "<p style='color:#6b7280;font-size:14px;margin-top:-8px;margin-bottom:16px;'>"
    "Select a publisher and set their Q3 revenue target. Claude will generate a structured "
    "3-month growth plan using PubMatic's OpenWrap, Activate, and Convert product suite."
    "</p>",
    unsafe_allow_html=True,
)

publisher_names = [p["name"] for p in PORTFOLIO]
strat_col1, strat_col2 = st.columns([2, 1])

with strat_col1:
    selected_pub_name = st.selectbox("Select publisher", publisher_names)

with strat_col2:
    q_target = st.number_input(
        "Q3 revenue target (AUD)",
        min_value=50_000,
        max_value=5_000_000,
        value=300_000,
        step=10_000,
        format="%d",
    )

if st.button("Generate Strategy", type="primary"):
    if not api_key:
        st.warning("No Anthropic API key found. Add `ANTHROPIC_API_KEY` to your Streamlit secrets.")
    else:
        # Find the selected publisher's data
        selected_pub = next(p for p in PORTFOLIO if p["name"] == selected_pub_name)
        monthly_implied = q_target / 3

        prompt = (
            f"You are a senior PubMatic Customer Success Manager building a 3-month "
            f"growth strategy for {selected_pub_name}.\n\n"
            f"Current publisher profile (AUD):\n"
            f"- Formats: {selected_pub['formats']}\n"
            f"- Current eCPM: A${selected_pub['ecpm']:.2f}\n"
            f"- Fill rate: {selected_pub['fill_rate']*100:.0f}%\n"
            f"- Bid density: {selected_pub['bid_density']:.1f} buyers/auction\n"
            f"- Floor price: A${selected_pub['floor']:.2f}\n"
            f"- Current monthly revenue: A${selected_pub['revenue']/1_000:.0f}k\n"
            f"- Q3 quarterly revenue target: A${q_target:,} "
            f"(implied A${monthly_implied:,.0f}/month)\n"
            f"- Current health score: {selected_pub['health_score']:.0f}/100 ({selected_pub['risk']})\n\n"
            f"Generate a structured Month 1 / Month 2 / Month 3 growth plan. "
            f"For each month provide:\n"
            f"1. The primary action, using specific PubMatic products where relevant:\n"
            f"   - OpenWrap (header bidding — increases bid density and competition)\n"
            f"   - Activate (audience monetisation — overlays first-party data to lift eCPM)\n"
            f"   - Convert (commerce media — connects purchase-intent audiences to retail advertisers)\n"
            f"2. Supporting actions (floor strategy, demand partner additions, format expansions)\n"
            f"3. Projected revenue impact in AUD for that month\n"
            f"4. Key metric to track\n\n"
            f"End with a summary table showing cumulative Q3 revenue projection vs the "
            f"A${q_target:,} target.\n\n"
            f"Tone: executive-ready. Be specific about AUD figures, platform mechanics, "
            f"and expected outcomes. This is presented directly to {selected_pub_name}'s Head of Revenue."
        )

        with st.spinner(f"Building Q3 strategy for {selected_pub_name}..."):
            client_ai = anthropic.Anthropic(api_key=api_key)
            response = client_ai.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1400,
                messages=[{"role": "user", "content": prompt}],
            )
            st.session_state["pub_strategy_output"]    = response.content[0].text
            st.session_state["pub_strategy_publisher"] = selected_pub_name
            st.session_state["pub_strategy_target"]    = q_target

# Display persisted strategy output
if "pub_strategy_output" in st.session_state:
    pub_label    = st.session_state["pub_strategy_publisher"]
    target_label = st.session_state["pub_strategy_target"]
    st.markdown(
        f"<div style='background:#FFFFFF;border-radius:12px;padding:24px 28px;"
        f"box-shadow:0 4px 12px rgba(0,0,0,0.08);margin-top:8px;'>"
        f"<div style='font-size:12px;font-weight:600;color:#7C3AED;text-transform:uppercase;"
        f"letter-spacing:0.05em;margin-bottom:12px;'>"
        f"Q3 Growth Strategy — {pub_label} &nbsp;·&nbsp; Target A${target_label:,}"
        f"</div>"
        + st.session_state["pub_strategy_output"].replace("\n", "<br>") +
        f"</div>",
        unsafe_allow_html=True,
    )

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — PubMatic Optimisation Push
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("PubMatic Optimisation Push")
st.markdown(
    "<p style='color:#6b7280;font-size:14px;margin-top:-8px;'>"
    "Simulate a PubMatic platform API call to action yield improvements on underperforming publishers. "
    "<strong>Simulation only — no real changes are made.</strong>"
    "</p>",
    unsafe_allow_html=True,
)

# Only publishers scored At risk or Critical (health < 70) get a push panel
PUSH_ELIGIBLE = [p for p in PORTFOLIO if p["risk"] in ("Critical", "At risk")]

for p in PUSH_ELIGIBLE:
    pd_ = PUBMATIC_PUSH_DATA.get(p["name"])
    if not pd_:
        continue

    pushed_key = f"pub_pushed_{p['name']}"

    col_btn, col_resp = st.columns([1, 3])

    with col_btn:
        if st.session_state.get(pushed_key):
            # Replace button with green applied label once pushed
            st.markdown(
                "<div style='background:#ECFDF5;border:1px solid #6EE7B7;"
                "border-radius:8px;padding:10px 14px;font-weight:700;"
                "color:#065F46;font-size:14px;text-align:center;'>"
                "✓ Changes applied"
                "</div>",
                unsafe_allow_html=True,
            )
        else:
            if st.button(
                f"⚡ Push {p['name']}",
                key=f"push_btn_{p['name']}",
                type="primary",
            ):
                with st.spinner("Pushing to PubMatic API..."):
                    time.sleep(1.8)
                st.session_state[pushed_key] = True
                st.rerun()

        # Publisher summary below the button / applied label
        risk_color = p["risk_color"]
        risk_label = p["risk"]
        st.markdown(
            f"<div style='font-size:12px;color:#6B7280;margin-top:10px;line-height:1.8;'>"
            f"<strong style='color:#111827;'>{p['name']}</strong><br>"
            f"{p['formats']}<br>"
            f"Health: {p['health_score']:.0f}/100 "
            f"<span style='color:{risk_color};font-weight:700;'>({risk_label})</span><br>"
            f"Gap: A${p['revenue_gap']/1_000:.0f}k below target"
            f"</div>",
            unsafe_allow_html=True,
        )

    with col_resp:
        if st.session_state.get(pushed_key):
            # Show the recommended actions list then the API response block
            actions_html = "".join(
                f"<li style='margin-bottom:6px;'>{a}</li>"
                for a in pd_["actions"]
            )
            st.markdown(
                f"<div style='background:#F9FAFB;border-radius:8px;"
                f"padding:12px 16px;margin-bottom:10px;font-size:13px;'>"
                f"<div style='font-weight:600;color:#111827;margin-bottom:8px;'>"
                f"Actions applied</div>"
                f"<ul style='margin:0;padding-left:18px;color:#374151;line-height:1.7;'>"
                f"{actions_html}"
                f"</ul></div>",
                unsafe_allow_html=True,
            )
            st.code(pd_["api_response"], language="text")
        else:
            # Placeholder shown before the button is clicked
            st.markdown(
                "<div style='background:#F9FAFB;border:1px dashed #D1D5DB;"
                "border-radius:8px;padding:28px;text-align:center;"
                "color:#9CA3AF;font-size:13px;'>"
                "Click the button to simulate the PubMatic API call and see "
                "the projected response.</div>",
                unsafe_allow_html=True,
            )

    st.markdown(
        "<hr style='border:none;border-top:1px solid #E5E7EB;margin:20px 0;'>",
        unsafe_allow_html=True,
    )

# ── Total recovery summary — shown only once at least one push has been applied
pushed_names = [p["name"] for p in PUSH_ELIGIBLE if st.session_state.get(f"pub_pushed_{p['name']}")]
if pushed_names:
    total_recovery = sum(PUBMATIC_PUSH_DATA[name]["recovery_low"] for name in pushed_names)
    st.markdown(
        f"<div style='background:#F5F3FF;border-left:4px solid #7C3AED;"
        f"border-radius:8px;padding:14px 18px;font-size:14px;color:#374151;'>"
        f"<strong style='color:#7C3AED;'>Estimated total recovery across optimised publishers: "
        f"A${total_recovery:,}/month</strong>"
        f"&nbsp; (based on {len(pushed_names)} publisher{'s' if len(pushed_names) > 1 else ''} pushed)"
        f"</div>",
        unsafe_allow_html=True,
    )

print("Done. Publisher Revenue Intelligence page loaded.")
