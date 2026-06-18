import os
import anthropic
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="Channel Budget Optimiser", layout="wide")

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
        background: #FFFFFF; border: none; border-radius: 16px; padding: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08); border-top: 4px solid #7C3AED;
    }
    [data-testid="metric-container"] label {
        font-size: 12px; font-weight: 600; color: #6B7280;
        text-transform: uppercase; letter-spacing: 0.05em;
    }
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        font-size: 26px; font-weight: 700; color: #111827;
    }
    .element-container:has([data-testid="stPlotlyChart"]) {
        background: #FFFFFF; border-radius: 12px; padding: 16px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    }
    .stButton > button[kind="primary"],
    [data-testid="baseButton-primary"] {
        background-color: #7C3AED !important; color: #FFFFFF !important;
        border: none !important; border-radius: 8px !important;
        font-weight: 600 !important; font-size: 15px !important; padding: 0.5rem 1.25rem !important;
    }
    .stButton > button[kind="primary"]:hover,
    [data-testid="baseButton-primary"]:hover { background-color: #6D28D9 !important; }
    .stButton > button[kind="secondary"],
    [data-testid="baseButton-secondary"] { border-radius: 8px !important; font-weight: 600 !important; }
    [data-testid="stDataFrame"] {
        background: #FFFFFF; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.06);
    }
</style>
""", unsafe_allow_html=True)
# STYLE LOCK

# ── Constants ─────────────────────────────────────────────────────────────────

CHART_COLOURS = ["#1E40AF","#2563EB","#3B82F6","#60A5FA","#93C5FD","#BFDBFE","#7C3AED"]

ALL_CHANNELS = [
    "Google Search Brand", "Google Search NonBrand",
    "Programmatic Display", "Programmatic Retargeting",
    "Meta Prospecting", "Meta Retargeting", "Affiliates",
]

# Fallback benchmarks used when no session data from Cross-Channel Dashboard
HARDCODED_BENCHMARKS = {
    "Google Search Brand":      {"cpa": 25.0, "conv_rate": 4.5},
    "Google Search NonBrand":   {"cpa": 45.0, "conv_rate": 2.5},
    "Programmatic Display":     {"cpa": 60.0, "conv_rate": 1.2},
    "Programmatic Retargeting": {"cpa": 38.0, "conv_rate": 2.8},
    "Meta Prospecting":         {"cpa": 50.0, "conv_rate": 1.8},
    "Meta Retargeting":         {"cpa": 35.0, "conv_rate": 3.2},
    "Affiliates":               {"cpa": 22.0, "conv_rate": 8.5},
}

# One-sentence rationale per channel for the allocation table
CHANNEL_RATIONALE = {
    "Google Search Brand":      "Protects brand search, high intent, strongest conv rate.",
    "Google Search NonBrand":   "Captures in-market demand at higher CPA but strong volume.",
    "Programmatic Display":     "Upper funnel awareness; seeds retargeting audiences.",
    "Programmatic Retargeting": "Re-engages warm audiences at lower CPA than prospecting.",
    "Meta Prospecting":         "Lookalike audiences drive new customer acquisition at scale.",
    "Meta Retargeting":         "Converts high-intent social engagers at competitive CPA.",
    "Affiliates":               "Commission-based; lowest CPA channel, highly efficient.",
}

# ── Helper functions ──────────────────────────────────────────────────────────

def get_api_key():
    """Read ANTHROPIC_API_KEY from Streamlit secrets, then fall back to environment variable."""
    try:
        return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        return os.environ.get("ANTHROPIC_API_KEY", "")


def get_benchmarks(telco_data):
    """
    Return (benchmarks_dict, n_hist_days, source) where source is "live" or "mock".
    If live data is available, compute mean CPA and conv rate per channel from the DataFrame.
    Missing channels are filled from HARDCODED_BENCHMARKS.
    """
    if telco_data is not None:
        # Use Display Name if available, otherwise fall back to Channel
        dn_col = "Display Name" if "Display Name" in telco_data.columns else "Channel"

        # Group by channel and compute mean CPA and conversion rate
        agg = (
            telco_data.groupby(dn_col)
            .agg(Spend=("Spend", "sum"), Conversions=("Conversions", "sum"), Impressions=("Impressions", "sum"))
            .reset_index()
        )
        agg["cpa"] = agg["Spend"] / agg["Conversions"].clip(lower=1)
        agg["conv_rate"] = (agg["Conversions"] / agg["Impressions"].clip(lower=1)) * 100

        # Build benchmark dict from live data
        benchmarks = {}
        for _, row in agg.iterrows():
            benchmarks[row[dn_col]] = {
                "cpa": float(row["cpa"]),
                "conv_rate": float(row["conv_rate"]),
            }

        # Fill any missing channels with hardcoded defaults
        for ch, vals in HARDCODED_BENCHMARKS.items():
            if ch not in benchmarks:
                benchmarks[ch] = vals

        n_days = int(telco_data["Date"].nunique()) if "Date" in telco_data.columns else 0
        return benchmarks, n_days, "live"

    else:
        return HARDCODED_BENCHMARKS, 0, "mock"


def compute_allocation(total_budget, selected_channels, benchmarks, objective):
    """
    Compute recommended budget allocation across selected channels based on the chosen objective.
    Returns a list of dicts with keys: Channel, Budget (float), Pct (float),
    Expected Conversions (float), CPA (float), Rationale (str).
    """
    scores = {}
    for ch in selected_channels:
        bench = benchmarks.get(ch, {"cpa": 45, "conv_rate": 2.5})
        efficiency = 1.0 / max(bench["cpa"], 1)      # inverse CPA — higher = cheaper
        volume = bench["conv_rate"] / 100             # conversion rate as a fraction

        # Score each channel differently depending on the objective
        if objective == "Minimise CPA":
            score = efficiency ** 2
        elif objective == "Maximise Conversions":
            score = volume ** 2
        elif objective == "Maximise ROAS":
            score = efficiency * volume * 100
        else:  # Balanced
            score = (efficiency * volume * 50) ** 0.5

        scores[ch] = max(score, 0)

    # Normalise scores so they sum to 1.0
    total_score = sum(scores.values()) or 1.0
    rows = []
    for ch in selected_channels:
        bench = benchmarks.get(ch, {"cpa": 45, "conv_rate": 2.5})
        pct = (scores[ch] / total_score) * 100
        budget = total_budget * (scores[ch] / total_score)
        exp_conv = budget / max(bench["cpa"], 1)
        rows.append({
            "Channel": ch,
            "Budget": float(budget),
            "Pct": float(pct),
            "Expected Conversions": float(exp_conv),
            "CPA": float(bench["cpa"]),
            "Rationale": CHANNEL_RATIONALE.get(ch, ""),
        })
    return rows


def compute_scenarios(total_budget, selected_channels, benchmarks):
    """
    Compute three named scenarios by calling compute_allocation with different objectives.
    Returns {"Efficiency Focus": list, "Volume Focus": list, "Balanced": list}.
    """
    return {
        "Efficiency Focus": compute_allocation(total_budget, selected_channels, benchmarks, "Minimise CPA"),
        "Volume Focus":     compute_allocation(total_budget, selected_channels, benchmarks, "Maximise Conversions"),
        "Balanced":         compute_allocation(total_budget, selected_channels, benchmarks, "Balanced"),
    }


# ── Page title ────────────────────────────────────────────────────────────────

st.title("Channel Budget Optimiser")
st.markdown(
    "<p style='color:#6B7280;font-size:15px;margin-top:-12px;'>"
    "Plan and optimise budget allocation across biddable channels based on historical performance and live data."
    "</p>",
    unsafe_allow_html=True,
)

# ── Data source status ────────────────────────────────────────────────────────

# Pull shared session state set by Cross-Channel Dashboard
telco_data = st.session_state.get("telco_channel_data")       # DataFrame or None
cpa_targets = st.session_state.get("telco_cpa_targets", {})   # dict of {channel: target_cpa}

benchmarks, n_hist_days, bench_source = get_benchmarks(telco_data)

if telco_data is not None:
    n_days = int(telco_data["Date"].nunique()) if "Date" in telco_data.columns else 0
    n_ch = int(telco_data["Channel"].nunique()) if "Channel" in telco_data.columns else 0
    st.success(f"✅ Using live data from Cross-Channel Dashboard ({n_days} days, {n_ch} channels)")
else:
    st.warning("⚠️ No live data available — using mock benchmarks. Upload reports in Cross-Channel Dashboard first.")

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab_plan, tab_live = st.tabs(["📋 Forecast & Plan", "⚡ Live Reallocation"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — FORECAST & PLAN
# ══════════════════════════════════════════════════════════════════════════════

with tab_plan:

    # ── Section 1: Planning Inputs ────────────────────────────────────────────
    st.subheader("Planning Inputs")

    left_col, right_col = st.columns(2)

    with left_col:
        total_budget = st.number_input(
            "Total monthly budget, AUD",
            min_value=1000, max_value=10_000_000,
            value=50_000, step=1000,
            key="plan_budget",
        )
        planning_period = st.selectbox(
            "Planning period",
            ["Next 4 weeks", "Next 8 weeks", "Next Quarter"],
            key="plan_period",
        )
        objective = st.selectbox(
            "Primary objective",
            ["Minimise CPA", "Maximise Conversions", "Maximise ROAS", "Balance efficiency and volume"],
            key="plan_obj",
        )

    with right_col:
        selected_channels = st.multiselect(
            "Channels to include",
            ALL_CHANNELS,
            default=ALL_CHANNELS,
            key="plan_channels",
        )
        # Show where benchmarks came from
        if bench_source == "live":
            st.markdown(
                f"<p style='color:#6B7280;font-size:13px;margin-top:8px;'>"
                f"Benchmarks calculated from {n_hist_days} days of historical data</p>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<p style='color:#6B7280;font-size:13px;margin-top:8px;'>"
                "Using hardcoded benchmarks — upload data in Cross-Channel Dashboard for personalised projections</p>",
                unsafe_allow_html=True,
            )

    # ── Section 2: CPA Target Overrides ──────────────────────────────────────
    with st.expander("🎯 CPA Targets (from Cross-Channel Dashboard)"):
        for ch in selected_channels:
            default_cpa = cpa_targets.get(ch, benchmarks.get(ch, {}).get("cpa", 45))
            st.number_input(
                ch,
                value=float(default_cpa),
                min_value=1.0, max_value=500.0, step=1.0,
                key=f"plan_cpa_{ch}",
            )

    # ── Section 3: Generate Plan button ──────────────────────────────────────
    st.divider()
    _, btn_col, _ = st.columns([1, 2, 1])
    with btn_col:
        generate_clicked = st.button(
            "Generate Budget Plan",
            type="primary",
            use_container_width=True,
            key="plan_gen_btn",
        )

    if generate_clicked:
        # Read any edited CPA targets and merge with benchmark conv rates
        updated_benchmarks = {}
        for ch in selected_channels:
            updated_benchmarks[ch] = {
                "cpa":       st.session_state.get(f"plan_cpa_{ch}", benchmarks.get(ch, {}).get("cpa", 45)),
                "conv_rate": benchmarks.get(ch, {}).get("conv_rate", 2.5),
            }

        allocation = compute_allocation(total_budget, selected_channels, updated_benchmarks, objective)
        scenarios  = compute_scenarios(total_budget, selected_channels, updated_benchmarks)

        # Persist results in session state so they survive reruns
        st.session_state["plan_allocation"] = allocation
        st.session_state["plan_scenarios"]  = scenarios
        st.session_state["plan_inputs"] = {
            "total_budget":      total_budget,
            "planning_period":   planning_period,
            "objective":         objective,
            "selected_channels": selected_channels,
            "benchmarks":        updated_benchmarks,
        }
        # Clear stale AI text when plan is regenerated
        st.session_state.pop("plan_ai_text", None)

    # ── Sections 4-7: Results (shown only after plan is generated) ────────────
    if st.session_state.get("plan_allocation"):
        allocation  = st.session_state["plan_allocation"]
        plan_inputs = st.session_state["plan_inputs"]

        st.divider()

        # ── Section 4: Recommended Allocation Table ───────────────────────────
        st.subheader("Recommended Allocation")

        df_alloc = pd.DataFrame(allocation)

        # Format columns for readable display
        df_display = pd.DataFrame({
            "Channel":              df_alloc["Channel"],
            "Recommended Budget":   df_alloc["Budget"].apply(lambda v: f"A${v:,.0f}"),
            "% of Total":           df_alloc["Pct"].apply(lambda v: f"{v:.1f}%"),
            "Expected Conversions": df_alloc["Expected Conversions"].apply(lambda v: f"{v:,.0f}"),
            "Expected CPA (AUD)":   df_alloc["CPA"].apply(lambda v: f"A${v:.2f}"),
            "Rationale":            df_alloc["Rationale"],
        })
        df_display.index = range(1, len(df_display) + 1)
        st.dataframe(df_display, use_container_width=True)

        # Summary KPI metrics below the table
        total_exp_conv = sum(r["Expected Conversions"] for r in allocation)
        blended_cpa    = plan_inputs["total_budget"] / max(total_exp_conv, 1)
        est_roas       = (total_exp_conv * 80) / max(plan_inputs["total_budget"], 1)  # assume A$80 ARPU per conversion

        t1, t2, t3 = st.columns(3)
        t1.metric("Total Projected Conversions", f"{total_exp_conv:,.0f}")
        t2.metric("Blended CPA", f"A${blended_cpa:.2f}")
        t3.metric("Estimated ROAS", f"{est_roas:.2f}x")

        st.divider()

        # ── Section 5: Allocation Pie Chart ───────────────────────────────────
        st.subheader("Budget Split")

        pie_fig = go.Figure(go.Pie(
            labels=df_alloc["Channel"],
            values=df_alloc["Budget"],
            hole=0.45,
            marker=dict(colors=CHART_COLOURS[:len(df_alloc)]),
            textinfo="label+percent",
            textfont=dict(family="Inter, sans-serif", size=11),
            hovertemplate="%{label}<br>A$%{value:,.0f} (%{percent})<extra></extra>",
        ))
        pie_fig.update_layout(
            showlegend=False,
            height=360,
            margin=dict(t=20, b=30, l=20, r=20),
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, sans-serif"),
        )
        st.plotly_chart(pie_fig, use_container_width=True)

        st.divider()

        # ── Section 6: Scenario Comparison ────────────────────────────────────
        st.subheader("Scenario Comparison")

        scenarios = st.session_state["plan_scenarios"]
        sc_names  = ["Efficiency Focus", "Volume Focus", "Balanced"]
        sc_headers = {
            "Efficiency Focus": ("#6B7280", "#FFFFFF"),
            "Volume Focus":     ("#059669", "#FFFFFF"),
            "Balanced":         ("#2563EB", "#FFFFFF"),
        }

        sc1, sc2, sc3 = st.columns(3)
        for col, sc_name in zip([sc1, sc2, sc3], sc_names):
            sc_rows  = scenarios[sc_name]
            sc_conv  = sum(r["Expected Conversions"] for r in sc_rows)
            sc_cpa   = plan_inputs["total_budget"] / max(sc_conv, 1)
            hdr_bg, hdr_txt = sc_headers[sc_name]

            # Build channel rows as HTML
            row_html = ""
            for r in sc_rows:
                row_html += (
                    f"<div style='display:flex;justify-content:space-between;padding:4px 0;"
                    f"border-bottom:1px solid #F9FAFB;'>"
                    f"<span style='font-size:11px;color:#6B7280;'>{r['Channel']}</span>"
                    f"<span style='font-size:11px;font-weight:600;color:#111827;'>"
                    f"A${r['Budget']:,.0f} ({r['Pct']:.0f}%)</span>"
                    f"</div>"
                )

            with col:
                st.markdown(
                    f"<div style='border:1px solid #E5E7EB;border-radius:12px;overflow:hidden;"
                    f"box-shadow:0 4px 12px rgba(0,0,0,0.08);background:#FFFFFF;'>"
                    f"<div style='background:{hdr_bg};padding:12px 16px;'>"
                    f"<p style='color:{hdr_txt};font-weight:700;font-size:14px;margin:0;'>{sc_name}</p></div>"
                    f"<div style='padding:14px 16px;'>"
                    + row_html +
                    f"<div style='border-top:1px solid #E5E7EB;margin:10px 0 6px;'></div>"
                    f"<div style='display:flex;justify-content:space-between;padding:4px 0;'>"
                    f"<span style='font-size:12px;color:#6B7280;'>Conversions</span>"
                    f"<span style='font-size:12px;font-weight:700;color:#111827;'>{sc_conv:,.0f}</span></div>"
                    f"<div style='display:flex;justify-content:space-between;padding:4px 0;'>"
                    f"<span style='font-size:12px;color:#6B7280;'>Blended CPA</span>"
                    f"<span style='font-size:12px;font-weight:700;color:#111827;'>A${sc_cpa:.2f}</span></div>"
                    f"</div></div>",
                    unsafe_allow_html=True,
                )

        st.divider()

        # ── Section 7: AI Forecast Narrative ──────────────────────────────────
        st.subheader("AI Forecast Narrative")
        api_key = get_api_key()

        if not api_key:
            st.warning("Add `ANTHROPIC_API_KEY` to Streamlit secrets to enable AI narrative.")
        else:
            if st.button("Generate Plan Narrative", type="primary", key="plan_ai_btn"):
                # Build a structured prompt from the allocation and benchmarks
                alloc_lines = "\n".join(
                    f"  - {r['Channel']}: A${r['Budget']:,.0f} ({r['Pct']:.1f}%) — "
                    f"{r['Expected Conversions']:.0f} est. conversions at A${r['CPA']:.2f} CPA"
                    for r in allocation
                )
                bench_lines = "\n".join(
                    f"  - {ch}: CPA A${v['cpa']:.2f}, Conv Rate {v['conv_rate']:.1f}%"
                    for ch, v in plan_inputs["benchmarks"].items()
                )
                prompt = (
                    f"You are a Paid Digital Marketing Specialist at Optus recommending a biddable media "
                    f"budget allocation for {plan_inputs['planning_period']} with a total budget of "
                    f"A${plan_inputs['total_budget']:,.0f}.\n\n"
                    f"Historical performance by channel:\n{bench_lines}\n\n"
                    f"Recommended allocation:\n{alloc_lines}\n\n"
                    f"Primary objective: {plan_inputs['objective']}\n\n"
                    f"Write a strategic budget allocation recommendation suitable for presenting to "
                    f"internal Optus stakeholders:\n"
                    f"1. RECOMMENDED SPLIT — summarise the allocation with rationale\n"
                    f"2. KEY ASSUMPTIONS — what this plan is based on\n"
                    f"3. RISK FLAGS — one risk per channel if any\n"
                    f"4. SUCCESS METRICS — how to measure if the plan is working"
                )
                ai_client = anthropic.Anthropic(api_key=api_key)
                with st.spinner("Generating plan narrative…"):
                    msg = ai_client.messages.create(
                        model="claude-sonnet-4-6",
                        max_tokens=800,
                        system="You are a Paid Digital Marketing Specialist at Optus. Write clear, data-driven budget recommendations for internal stakeholders. Use Australian English.",
                        messages=[{"role": "user", "content": prompt}],
                    )
                st.session_state["plan_ai_text"] = msg.content[0].text.strip()

            # Display saved AI narrative
            if st.session_state.get("plan_ai_text"):
                st.markdown(
                    "<div style='background:#FFFFFF;border-radius:12px;padding:22px 26px;"
                    "box-shadow:0 4px 12px rgba(0,0,0,0.08);margin-top:14px;font-size:14px;"
                    "line-height:1.8;color:#374151;'>"
                    + st.session_state["plan_ai_text"].replace("\n", "<br>") +
                    "</div>",
                    unsafe_allow_html=True,
                )

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — LIVE REALLOCATION
# ══════════════════════════════════════════════════════════════════════════════

with tab_live:

    if telco_data is not None:

        # Determine which column holds the channel display name
        dn_col = "Display Name" if "Display Name" in telco_data.columns else "Channel"

        # Aggregate spend and conversions from live data
        live_agg = (
            telco_data.groupby(dn_col)
            .agg(Spend=("Spend", "sum"), Conversions=("Conversions", "sum"))
            .reset_index()
        )
        # Treat total spend as the budget proxy for this period
        live_agg["Budget"]      = live_agg["Spend"]
        live_agg["Current CPA"] = live_agg["Spend"] / live_agg["Conversions"].clip(lower=1)
        live_agg["Target CPA"]  = live_agg[dn_col].map(
            lambda ch: cpa_targets.get(ch, benchmarks.get(ch, {}).get("cpa", 50))
        )
        live_agg["Spent to Date"] = live_agg["Spend"]
        live_agg["Remaining"]     = 0  # no budget cap available in raw data

        # ── Section 1: Current Performance vs Targets ─────────────────────────
        st.subheader("Current Channel Performance vs Targets")

        def _live_status(row):
            """Return (status_label, colour) based on CPA vs target."""
            if row["Target CPA"] <= 0:
                return "—", "#6B7280"
            ratio = row["Current CPA"] / row["Target CPA"]
            if ratio <= 1.0:
                return "✅ Efficient", "#10B981"
            if ratio <= 1.15:
                return "⚠️ Watch", "#F59E0B"
            return "❌ Reallocate", "#EF4444"

        for _, row in live_agg.iterrows():
            status_text, status_color = _live_status(row)
            st.markdown(
                f"<div style='background:#FFFFFF;border-radius:10px;padding:14px 18px;"
                f"margin-bottom:8px;box-shadow:0 2px 8px rgba(0,0,0,0.06);display:flex;"
                f"justify-content:space-between;align-items:center;'>"
                f"<span style='font-weight:600;font-size:14px;color:#111827;'>{row[dn_col]}</span>"
                f"<span style='font-size:13px;color:#6B7280;'>Spend A${row['Spent to Date']:,.0f}</span>"
                f"<span style='font-size:13px;color:#111827;'>CPA A${row['Current CPA']:.2f}</span>"
                f"<span style='font-size:13px;color:#6B7280;'>Target A${row['Target CPA']:.0f}</span>"
                f"<span style='background:{status_color};color:#FFFFFF;border-radius:6px;"
                f"padding:3px 10px;font-size:11px;font-weight:700;'>{status_text}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

        st.divider()

        # ── Section 2: Reallocation Signals ───────────────────────────────────
        st.subheader("Reallocation Signals")

        underperforming   = live_agg[live_agg["Current CPA"] > live_agg["Target CPA"] * 1.15]
        best_channel_row  = live_agg.loc[live_agg["Current CPA"].idxmin()]
        best_channel      = best_channel_row[dn_col]

        if underperforming.empty:
            st.success("✅ All channels performing within CPA targets. No reallocation needed.")
        else:
            st.markdown(
                "<div style='background:#FFFBEB;border:1px solid #FCD34D;border-radius:12px;"
                "padding:16px 20px;'>",
                unsafe_allow_html=True,
            )
            st.markdown("**Based on current performance, we recommend the following budget shifts:**")
            for _, row in underperforming.iterrows():
                pct_above = (row["Current CPA"] / row["Target CPA"] - 1) * 100
                shift_amt = round(row["Spent to Date"] * 0.15 / 1000) * 1000  # shift ~15% of spend
                st.markdown(
                    f"❌ **{row[dn_col]}** CPA is A${row['Current CPA']:.2f}, "
                    f"{pct_above:.0f}% above target. Recommended action: Reduce budget by "
                    f"A${shift_amt:,.0f} and reallocate to **{best_channel}** "
                    f"(lowest CPA A${best_channel_row['Current CPA']:.2f})."
                )
            st.markdown("</div>", unsafe_allow_html=True)

        st.divider()

        # ── Section 3: Reallocation Simulator ────────────────────────────────
        st.subheader("Budget Reallocation Simulator")
        st.markdown(
            "<p style='color:#6b7280;font-size:14px;margin-top:-8px;'>"
            "Adjust channel budget percentages. Total should equal 100% of your monthly budget.</p>",
            unsafe_allow_html=True,
        )

        total_sim_budget = st.number_input(
            "Total monthly budget, AUD",
            min_value=1000, max_value=10_000_000,
            value=50_000, step=1000,
            key="sim_total_budget",
        )

        channels_sim = list(live_agg[dn_col].values)
        n_ch_sim     = len(channels_sim)
        default_pct  = round(100.0 / n_ch_sim, 1) if n_ch_sim > 0 else 100.0

        # One slider per channel
        sim_pcts = {}
        for ch in channels_sim:
            sim_pcts[ch] = st.slider(
                ch,
                min_value=0, max_value=100,
                value=int(default_pct),
                step=1,
                key=f"sim_pct_{ch}",
                format="%d%%",
            )

        total_pct   = sum(sim_pcts.values())
        pct_color   = "#10B981" if abs(total_pct - 100) < 1 else "#F59E0B" if abs(total_pct - 100) <= 10 else "#EF4444"

        st.markdown(
            f"<div style='background:#F9FAFB;border-radius:8px;padding:12px 16px;margin-top:8px;'>"
            f"<span style='font-size:14px;color:#374151;'>Total allocated: </span>"
            f"<span style='font-size:16px;font-weight:700;color:{pct_color};'>{total_pct:.0f}%</span>"
            f"<span style='font-size:13px;color:#6B7280;'> of 100% target</span></div>",
            unsafe_allow_html=True,
        )

        # Projected impact based on current slider values
        total_pct_safe = max(total_pct, 0.01)
        proj_conv = sum(
            (sim_pcts[ch] / total_pct_safe * total_sim_budget) /
            max(
                live_agg.loc[live_agg[dn_col] == ch, "Current CPA"].values[0]
                if ch in live_agg[dn_col].values else 45,
                1,
            )
            for ch in channels_sim
        )
        proj_cpa = total_sim_budget / max(proj_conv, 1)

        c1, c2 = st.columns(2)
        c1.metric("Estimated new blended CPA", f"A${proj_cpa:.2f}")
        c2.metric("Estimated total conversions", f"{proj_conv:,.0f}")

        st.divider()

        # ── Section 4: Apply Reallocation ─────────────────────────────────────
        _, apply_col, _ = st.columns([1, 2, 1])
        with apply_col:
            apply_clicked = st.button(
                "Apply Reallocation",
                type="primary",
                use_container_width=True,
                key="sim_apply_btn",
            )

        if apply_clicked:
            # Build before/after comparison tables
            before_rows = []
            after_rows  = []
            for _, row in live_agg.iterrows():
                ch         = row[dn_col]
                old_budget = row["Spent to Date"]
                new_budget = sim_pcts.get(ch, default_pct) / max(total_pct, 0.01) * total_sim_budget
                old_conv   = old_budget / max(row["Current CPA"], 1)
                new_conv   = new_budget / max(row["Current CPA"], 1)
                before_rows.append({
                    "Channel":       ch,
                    "Budget":        f"A${old_budget:,.0f}",
                    "Expected Conv": f"{old_conv:.0f}",
                    "CPA":           f"A${row['Current CPA']:.2f}",
                })
                after_rows.append({
                    "Channel":       ch,
                    "Budget":        f"A${new_budget:,.0f}",
                    "Expected Conv": f"{new_conv:.0f}",
                    "CPA":           f"A${row['Current CPA']:.2f}",
                })

            before_total_conv = sum(
                row["Spent to Date"] / max(row["Current CPA"], 1)
                for _, row in live_agg.iterrows()
            )
            after_total_conv = proj_conv

            ba1, ba2 = st.columns(2)
            with ba1:
                st.markdown("**Before**")
                st.dataframe(pd.DataFrame(before_rows), use_container_width=True, hide_index=True)
            with ba2:
                st.markdown("**After**")
                st.dataframe(pd.DataFrame(after_rows), use_container_width=True, hide_index=True)

            # Confidence level based on how many days of data we have
            data_days  = int(telco_data["Date"].nunique()) if "Date" in telco_data.columns else 0
            confidence = "High" if data_days >= 21 else "Medium" if data_days >= 7 else "Low"
            conf_color = "#10B981" if confidence == "High" else "#F59E0B" if confidence == "Medium" else "#EF4444"

            st.markdown(
                f"<div style='background:#FFFFFF;border-radius:12px;padding:16px 20px;"
                f"box-shadow:0 4px 12px rgba(0,0,0,0.08);margin-top:12px;font-size:14px;'>"
                f"Projected CPA improvement: A${live_agg['Current CPA'].mean():.2f} → A${proj_cpa:.2f}<br>"
                f"Estimated conversion change: {after_total_conv - before_total_conv:+,.0f} conversions<br>"
                f"Confidence level: <strong style='color:{conf_color};'>{confidence}</strong> "
                f"(based on {data_days} days of data)"
                f"</div>",
                unsafe_allow_html=True,
            )

        st.divider()

        # ── Section 5: AI Reallocation Recommendation ─────────────────────────
        st.subheader("AI Reallocation Recommendation")
        api_key_live = get_api_key()

        if not api_key_live:
            st.warning("Add `ANTHROPIC_API_KEY` to Streamlit secrets to enable AI recommendation.")
        else:
            if st.button("Get AI Recommendation", type="primary", key="live_ai_btn"):
                live_lines = "\n".join(
                    f"  - {row[dn_col]}: CPA A${row['Current CPA']:.2f} vs target A${row['Target CPA']:.0f} "
                    f"({'ABOVE' if row['Current CPA'] > row['Target CPA'] else 'below'} target)"
                    for _, row in live_agg.iterrows()
                )
                remaining_budget = total_sim_budget
                live_prompt = (
                    f"You are a Paid Digital Marketing Specialist at Optus managing live biddable campaigns. "
                    f"Current channel performance vs targets:\n\n{live_lines}\n\n"
                    f"Total remaining budget: A${remaining_budget:,.0f}\n\n"
                    f"Recommend specific budget reallocation actions:\n"
                    f"1. Which channels to reduce and by how much\n"
                    f"2. Which channels to increase and by how much\n"
                    f"3. Expected impact on blended CPA and total conversions\n"
                    f"4. One risk to flag about this reallocation\n\n"
                    f"Be specific with dollar amounts. Write for an internal Optus stakeholder audience."
                )
                ai_live = anthropic.Anthropic(api_key=api_key_live)
                with st.spinner("Generating reallocation recommendation…"):
                    live_msg = ai_live.messages.create(
                        model="claude-sonnet-4-6",
                        max_tokens=600,
                        system="You are a Paid Digital Marketing Specialist at Optus. Write direct, specific budget recommendations. Use Australian English.",
                        messages=[{"role": "user", "content": live_prompt}],
                    )
                st.session_state["live_ai_text"] = live_msg.content[0].text.strip()

            # Display saved AI recommendation
            if st.session_state.get("live_ai_text"):
                st.markdown(
                    "<div style='background:#FFFFFF;border-radius:12px;padding:22px 26px;"
                    "box-shadow:0 4px 12px rgba(0,0,0,0.08);margin-top:14px;font-size:14px;"
                    "line-height:1.8;color:#374151;'>"
                    + st.session_state["live_ai_text"].replace("\n", "<br>") +
                    "</div>",
                    unsafe_allow_html=True,
                )

    else:
        # No live data available — prompt user to upload in Cross-Channel Dashboard
        st.info("Upload channel reports in the Cross-Channel Dashboard to enable live reallocation analysis.")

print("Channel Budget Optimiser loaded.")
