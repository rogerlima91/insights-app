import json
import os
from datetime import date, timedelta
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import anthropic

# STYLE LOCK: Pacebird design system — primary #F5A623 orange, secondary #1B2A4A navy, font Poppins. Do not revert to purple (#7C3AED) or blue (#2563EB).
st.markdown("""
<style>
    /* ── Base font and body ─────────────────────────────────────── */
    html, body, [class*="css"] {
        font-family: "Poppins", system-ui, -apple-system, "Segoe UI", sans-serif;
        font-size: 15px;
        color: #374151;
    }

    /* ── Page background ────────────────────────────────────────── */
    .stApp { background-color: #EEF1F4; }

    /* ── Main area headings ──────────────────────────────────────── */
    h1, h2, h3, h4, h5, h6 { font-weight: 700 !important; color: #111827 !important; }
    h2, h3 {
        margin-top: 2rem !important;
        padding-top: 0.25rem !important;
        border-bottom: none !important;
        padding-bottom: 0 !important;
        border-left: none !important;
        padding-left: 0 !important;
    }

    /* ── KPI metric cards ───────────────────────────────────────── */
    [data-testid="metric-container"] {
        background: #FFFFFF;
        border: none;
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        border-top: 4px solid #F5A623;
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

    /* ── Chart cards — wrap Plotly chart output in white card ───── */
    .element-container:has([data-testid="stPlotlyChart"]) {
        background: #FFFFFF;
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    }

    /* ── Primary buttons — orange ───────────────────────────────── */
    .stButton > button[kind="primary"],
    [data-testid="baseButton-primary"] {
        background-color: #F5A623 !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 15px !important;
        padding: 0.5rem 1.25rem !important;
    }
    .stButton > button[kind="primary"]:hover,
    [data-testid="baseButton-primary"]:hover {
        background-color: #E8951A !important;
    }

    /* ── Secondary / default buttons ────────────────────────────── */
    .stButton > button[kind="secondary"],
    [data-testid="baseButton-secondary"] {
        border-radius: 8px !important;
        font-weight: 600 !important;
    }

    /* ── File upload box ─────────────────────────────────────────── */
    [data-testid="stFileUploader"] {
        border: 2px dashed #F5A623 !important;
        border-radius: 12px;
        padding: 10px;
        background: #FFFFFF;
    }

    /* ── Data tables ─────────────────────────────────────────────── */
    [data-testid="stDataFrame"] {
        background: #FFFFFF;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.06);
    }
</style>
""", unsafe_allow_html=True)
# STYLE LOCK

# ── Brand memory helpers ──────────────────────────────────────────────────────
# Reads brand_memory.json from the project root for AI context injection.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRAND_MEMORY_PATH = os.path.join(_ROOT, "brand_memory.json")


def load_brand_memory():
    """Load brand_memory.json. Returns {} if file doesn't exist."""
    if os.path.exists(BRAND_MEMORY_PATH):
        with open(BRAND_MEMORY_PATH, "r") as f:
            return json.load(f)
    return {}


def get_brand_context(advertiser, brand_memory):
    """Return stored rationale for an advertiser using partial/case-insensitive matching."""
    if not advertiser or not brand_memory:
        return ""
    for key, val in brand_memory.items():
        if key.lower() in advertiser.lower() or advertiser.lower() in key.lower():
            return val.get("rationale", "")
    return ""


# ── Hardcoded DSP benchmarks ──────────────────────────────────────────────────
# Default CPM, CTR, VTR, VCR values per DSP and format.
# These are used when no historical data has been uploaded.
DSP_BENCHMARKS = {
    ("DV360", "Display"):  {"cpm": 12.00, "ctr": 0.25},
    ("DV360", "YouTube"):  {"cpm": 25.00, "vtr": 72.0},
    ("TTD",   "Display"):  {"cpm": 14.00, "ctr": 0.22},
    ("TTD",   "BVOD"):     {"cpm": 44.00, "vcr": 91.0},
    ("TTD",   "Video"):    {"cpm": 20.00, "vtr": 65.0},
    ("Amazon DSP", "Display"):         {"cpm": 10.00, "ctr": 0.35},
    ("Amazon DSP", "Retail/eCommerce"):{"cpm": 10.00, "ctr": 0.35, "dpv_rate": 15.0},
}

# Objective-to-metric mapping: which metric matters most for each objective
OBJECTIVE_METRIC = {
    "Brand Awareness":     "impressions",
    "Performance/Clicks":  "clicks",
    "Video Views":         "views",
    "Conversions":         "clicks",   # use CTR as efficiency proxy
    "Reach":               "impressions",
}

# DSP affinity weights by objective — higher = preferred for this goal
OBJECTIVE_WEIGHTS = {
    "Brand Awareness": {
        "DV360": 0.40, "TTD": 0.35, "Amazon DSP": 0.25,
    },
    "Performance/Clicks": {
        "DV360": 0.30, "TTD": 0.30, "Amazon DSP": 0.40,
    },
    "Video Views": {
        "DV360": 0.50, "TTD": 0.30, "Amazon DSP": 0.20,
    },
    "Conversions": {
        "DV360": 0.30, "TTD": 0.25, "Amazon DSP": 0.45,
    },
    "Reach": {
        "DV360": 0.40, "TTD": 0.40, "Amazon DSP": 0.20,
    },
}

# Format-to-DSP availability mapping (which DSPs support which formats)
FORMAT_DSP_SUPPORT = {
    "Display":         ["DV360", "TTD", "Amazon DSP"],
    "Video":           ["DV360", "TTD"],
    "YouTube":         ["DV360"],
    "BVOD":            ["TTD"],
    "Retail/eCommerce":["Amazon DSP"],
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_api_key():
    """Load Anthropic API key from Streamlit secrets or environment."""
    if "ANTHROPIC_API_KEY" in st.secrets:
        return st.secrets.get("ANTHROPIC_API_KEY")
    return os.environ.get("ANTHROPIC_API_KEY")


def compute_preflight_allocation(total_budget, objective, selected_dsps, selected_formats):
    """
    Return a list of allocation dicts: {dsp, format, budget, pct, benchmark_source}.
    Uses objective weights + DSP-format compatibility to split the budget.
    """
    rows = []
    # Filter formats to those compatible with at least one selected DSP
    valid_combos = []
    for fmt in selected_formats:
        for dsp in selected_dsps:
            if dsp in FORMAT_DSP_SUPPORT.get(fmt, []):
                valid_combos.append((dsp, fmt))

    if not valid_combos:
        return []

    # Score each valid (dsp, format) combo
    obj_weights = OBJECTIVE_WEIGHTS.get(objective, {})
    scored = []
    for dsp, fmt in valid_combos:
        dsp_weight = obj_weights.get(dsp, 0.33)
        # Penalise formats that are less central to the objective
        fmt_boost = 1.3 if (
            (objective == "Video Views" and fmt in ["Video", "YouTube", "BVOD"]) or
            (objective == "Brand Awareness" and fmt in ["Display", "Video"]) or
            (objective in ["Performance/Clicks", "Conversions"] and fmt in ["Display", "Retail/eCommerce"])
        ) else 1.0
        scored.append({"dsp": dsp, "fmt": fmt, "score": dsp_weight * fmt_boost})

    total_score = sum(s["score"] for s in scored) or 1
    for s in scored:
        pct    = s["score"] / total_score * 100
        budget = total_budget * pct / 100
        bench  = DSP_BENCHMARKS.get((s["dsp"], s["fmt"]), {})
        bench_str = (
            f"CPM A${bench.get('cpm', '—'):.2f}"
            + (f", CTR {bench.get('ctr', '')}%" if "ctr" in bench else "")
            + (f", VTR {bench.get('vtr', '')}%" if "vtr" in bench else "")
            + (f", VCR {bench.get('vcr', '')}%" if "vcr" in bench else "")
            + (f", DPV Rate {bench.get('dpv_rate', '')}%" if "dpv_rate" in bench else "")
        ) if bench else "No benchmark available"
        rows.append({
            "DSP":     s["dsp"],
            "Format":  s["fmt"],
            "Budget (A$)": round(budget, 0),
            "%":       round(pct, 1),
            "Benchmark": bench_str,
        })

    # Sort by Budget descending
    rows.sort(key=lambda r: r["Budget (A$)"], reverse=True)
    return rows


# ── Page header ───────────────────────────────────────────────────────────────
st.title("Budget Allocation Recommender")
st.markdown(
    "<p style='color:#6b7280;font-size:14px;margin-top:-12px;'>"
    "Optimise budget distribution across DSPs based on historical performance "
    "and campaign objectives."
    "</p>",
    unsafe_allow_html=True,
)

# ── Two modes via tabs ────────────────────────────────────────────────────────
tab_preflight, tab_inflight = st.tabs(["Pre-flight Planning", "In-flight Reallocation"])


# ══════════════════════════════════════════════════════════════════════════════
# MODE A — PRE-FLIGHT PLANNING
# ══════════════════════════════════════════════════════════════════════════════
with tab_preflight:
    st.subheader("Pre-flight Planning")
    st.markdown(
        "<p style='color:#6b7280;font-size:14px;margin-top:-8px;'>"
        "Recommend a budget split across DSPs before a campaign goes live."
        "</p>",
        unsafe_allow_html=True,
    )

    # ── Input form ────────────────────────────────────────────────────────────
    with st.form("preflight_form"):
        col_a, col_b = st.columns(2)

        with col_a:
            # Load brand names from brand_memory.json as options
            _bm_for_form = load_brand_memory()
            _bm_brands   = sorted(_bm_for_form.keys()) if _bm_for_form else []
            _adv_options = ["(type your own)"] + _bm_brands

            adv_choice = st.selectbox("Advertiser", _adv_options, key="pf_adv_choice")
            if adv_choice == "(type your own)":
                adv_name = st.text_input("Advertiser Name", placeholder="e.g. Coca-Cola", key="pf_adv_text")
            else:
                adv_name = adv_choice
                st.text_input("Advertiser Name", value=adv_name, disabled=True, key="pf_adv_text")

            total_budget = st.number_input(
                "Total Budget (A$)", min_value=1_000, max_value=10_000_000,
                value=100_000, step=1_000, key="pf_budget",
            )
            objective = st.selectbox(
                "Campaign Objective",
                ["Brand Awareness", "Performance/Clicks", "Video Views",
                 "Conversions", "Reach"],
                key="pf_objective",
            )

        with col_b:
            flight_start = st.date_input("Flight Start", value=date.today(), key="pf_start")
            flight_end   = st.date_input("Flight End",   value=date.today() + timedelta(days=30), key="pf_end")
            selected_dsps = st.multiselect(
                "DSPs Available",
                ["DV360", "TTD", "Amazon DSP"],
                default=["DV360", "TTD"],
                key="pf_dsps",
            )
            selected_formats = st.multiselect(
                "Format Mix",
                ["Display", "Video", "YouTube", "BVOD", "Retail/eCommerce"],
                default=["Display", "Video"],
                key="pf_formats",
            )

        submitted = st.form_submit_button("Generate Allocation", type="primary")

    # ── Generate allocation when form is submitted ─────────────────────────────
    if submitted:
        if not selected_dsps:
            st.error("Select at least one DSP.")
        elif not selected_formats:
            st.error("Select at least one format.")
        elif flight_end <= flight_start:
            st.error("Flight end date must be after flight start.")
        else:
            allocation_rows = compute_preflight_allocation(
                total_budget, objective, selected_dsps, selected_formats
            )
            if not allocation_rows:
                st.warning(
                    "No valid DSP/format combinations found. "
                    "Check that the selected DSPs support the selected formats."
                )
            else:
                st.session_state["pf_allocation"] = allocation_rows
                st.session_state["pf_adv_name"]   = adv_name
                st.session_state["pf_budget"]      = total_budget
                st.session_state["pf_objective"]   = objective
                st.session_state["pf_start"]       = flight_start
                st.session_state["pf_end"]         = flight_end
                st.session_state["pf_ai_text"]     = ""   # clear previous AI output

    # ── Show results when allocation is available ──────────────────────────────
    if st.session_state.get("pf_allocation"):
        rows     = st.session_state["pf_allocation"]
        adv_disp = st.session_state.get("pf_adv_name", "")
        obj_disp = st.session_state.get("pf_objective", "")
        bud_disp = st.session_state.get("pf_budget", 0)
        st_disp  = st.session_state.get("pf_start",  date.today())
        en_disp  = st.session_state.get("pf_end",    date.today())

        st.markdown("---")
        st.markdown(f"### Recommended Allocation — {adv_disp or 'Campaign'}")

        # ── Allocation table ──────────────────────────────────────────────────
        df_alloc = pd.DataFrame(rows)
        # Format budget column as currency string for display
        df_alloc["Budget (A$)"] = df_alloc["Budget (A$)"].apply(lambda v: f"${v:,.0f}")
        df_alloc["%"]           = df_alloc["%"].apply(lambda v: f"{v:.1f}%")
        df_alloc.index = range(1, len(df_alloc) + 1)
        st.dataframe(df_alloc, use_container_width=True)

        # ── Pie chart showing recommended split ───────────────────────────────
        labels = [f"{r['DSP']} — {r['Format']}" for r in rows]
        values = [r["Budget (A$)"] if isinstance(r["Budget (A$)"], (int, float))
                  else float(str(r["Budget (A$)"]).replace("$", "").replace(",", ""))
                  for r in st.session_state["pf_allocation"]]

        pie_fig = go.Figure(go.Pie(
            labels=labels,
            values=values,
            hole=0.45,
            marker=dict(colors=[
                "#F5A623", "#1B2A4A", "#10B981", "#F59E0B",
                "#EF4444", "#F7B84B", "#2C4A7A", "#14B8A6",
            ]),
            textinfo="label+percent",
            textfont=dict(family="Poppins, sans-serif", size=12),
            hovertemplate="%{label}<br>A$%{value:,.0f} (%{percent})<extra></extra>",
        ))
        pie_fig.update_layout(
            showlegend=False,
            margin=dict(t=20, b=30, l=20, r=20),
            height=360,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Poppins, sans-serif"),
        )
        st.plotly_chart(pie_fig, use_container_width=True)

        # ── Key assumptions ───────────────────────────────────────────────────
        with st.expander("Key Assumptions", expanded=False):
            st.markdown(
                f"- **Objective:** {obj_disp}\n"
                f"- **Flight:** {st_disp.strftime('%d %b %Y')} → {en_disp.strftime('%d %b %Y')} "
                f"({(en_disp - st_disp).days} days)\n"
                f"- **Total Budget:** A${bud_disp:,.0f}\n"
                f"- **Benchmark Source:** Hardcoded industry defaults "
                f"(upload historical data to Feasibility Checker for personalised benchmarks)\n"
                f"- **Allocation Method:** Objective-weighted DSP affinity scores, "
                f"adjusted for format-objective fit"
            )

        # ── AI rationale ──────────────────────────────────────────────────────
        api_key = get_api_key()
        if not api_key:
            st.warning(
                "Add `ANTHROPIC_API_KEY` to Streamlit secrets to enable AI rationale."
            )
        else:
            if st.button("✨ Get AI Rationale", type="primary", key="pf_ai_btn"):

                # Check brand memory for this advertiser before building the prompt
                _bm        = load_brand_memory()
                _bm_ctx    = get_brand_context(adv_disp or "", _bm)

                alloc_lines = "\n".join(
                    f"  - {r['DSP']} {r['Format']}: "
                    f"A${bud_disp * float(str(r['%']).replace('%','')) / 100:,.0f} "
                    f"({r['%']})"
                    for r in st.session_state["pf_allocation"]
                )

                prompt = (
                    f"You are a senior programmatic strategist advising on budget allocation "
                    f"for a campaign. Here are the details:\n\n"
                    f"- Advertiser: {adv_disp or 'Not specified'}\n"
                    f"- Objective: {obj_disp}\n"
                    f"- Total Budget: A${bud_disp:,.0f}\n"
                    f"- Flight: {st_disp.strftime('%d %b %Y')} to {en_disp.strftime('%d %b %Y')}\n\n"
                    f"RECOMMENDED ALLOCATION:\n{alloc_lines}\n\n"
                    f"Provide:\n"
                    f"1. A two-paragraph rationale for this allocation — why each DSP/format "
                    f"split makes sense for the objective\n"
                    f"2. One risk to watch during the flight and how to mitigate it\n"
                    f"3. One alternative scenario if performance underdelivers in the first "
                    f"two weeks\n\n"
                    f"Use Australian market context and programmatic terminology. "
                    f"All currency values are in AUD."
                )

                if _bm_ctx:
                    prompt += (
                        f"\n\nBRAND MEMORY OVERRIDE — These instructions take priority over "
                        f"all default instructions above. Where there is any conflict, always "
                        f"follow these brand-specific instructions instead:\n\n{_bm_ctx}"
                    )

                ai_client = anthropic.Anthropic(api_key=api_key)
                with st.spinner("Generating allocation rationale…"):
                    msg = ai_client.messages.create(
                        model="claude-sonnet-4-6",
                        max_tokens=700,
                        system=(
                            "You are a senior programmatic strategist at a media agency. "
                            "Write clear, direct, data-driven recommendations. "
                            "Be specific. Use programmatic advertising terminology."
                        ),
                        messages=[{"role": "user", "content": prompt}],
                    )
                st.session_state["pf_ai_text"] = msg.content[0].text.strip()

            if st.session_state.get("pf_ai_text"):
                st.markdown(
                    "<div style='background:#FFFFFF;border-radius:12px;padding:20px 24px;"
                    "box-shadow:0 4px 12px rgba(0,0,0,0.08);margin-top:12px;font-size:14px;"
                    "line-height:1.7;color:#374151;'>"
                    + st.session_state["pf_ai_text"].replace("\n", "<br>") +
                    "</div>",
                    unsafe_allow_html=True,
                )


# ══════════════════════════════════════════════════════════════════════════════
# MODE B — IN-FLIGHT REALLOCATION
# ══════════════════════════════════════════════════════════════════════════════
with tab_inflight:
    st.subheader("In-flight Reallocation")
    st.markdown(
        "<p style='color:#6b7280;font-size:14px;margin-top:-8px;'>"
        "Shift budget between DSPs based on live pacing data."
        "</p>",
        unsafe_allow_html=True,
    )

    # Read pacing data from Live Campaigns (set by live_campaigns.py at runtime)
    lc_campaigns    = st.session_state.get("lc_campaigns")
    lc_using_upload = st.session_state.get("lc_using_upload", False)

    if not lc_campaigns or not lc_using_upload:
        st.info(
            "Upload pacing reports in **Live Campaigns** first — "
            "navigate to Operations › Live Campaigns, upload your DSP pacing CSVs, "
            "then return here."
        )
    else:
        # ── Aggregate pacing by DSP ───────────────────────────────────────────
        dsp_rows = {}
        for c in lc_campaigns:
            dsp  = c.get("dsp", "Unknown")
            if dsp not in dsp_rows:
                dsp_rows[dsp] = {"budget": 0, "spent": 0, "expected": 0}
            dsp_rows[dsp]["budget"]   += c.get("budget",         0)
            dsp_rows[dsp]["spent"]    += c.get("spent",          0)
            dsp_rows[dsp]["expected"] += c.get("expected_spend",  0)

        dsp_df = pd.DataFrame([
            {
                "DSP":            dsp,
                "Budget (A$)":    v["budget"],
                "Spent (A$)":     v["spent"],
                "Expected (A$)":  v["expected"],
                "Pacing %":       round(v["spent"] / v["expected"] * 100, 1)
                                  if v["expected"] > 0 else 0,
            }
            for dsp, v in dsp_rows.items()
        ]).sort_values("Pacing %")

        # ── Pacing summary — colour code by status ────────────────────────────
        st.markdown("#### Current Pacing by DSP")
        for _, row in dsp_df.iterrows():
            pct = row["Pacing %"]
            if pct < 75:
                bg, txt, label = "#FEF2F2", "#EF4444", "Critical"
            elif pct < 92:
                bg, txt, label = "#FFFBEB", "#F59E0B", "At risk"
            elif pct <= 110:
                bg, txt, label = "#ECFDF5", "#10B981", "On track"
            else:
                bg, txt, label = "#FFF4E0", "#F5A623", "Overpacing"

            # Build bar using styled div
            bar_pct_display = min(pct, 130)
            bar_fill = "#10B981" if pct <= 110 else "#F5A623"
            if pct < 75:
                bar_fill = "#EF4444"
            elif pct < 92:
                bar_fill = "#F59E0B"

            st.markdown(
                f"<div style='background:#FFFFFF;border-radius:10px;padding:14px 18px;"
                f"margin-bottom:8px;box-shadow:0 2px 8px rgba(0,0,0,0.06);'>"
                f"<div style='display:flex;justify-content:space-between;align-items:center;"
                f"margin-bottom:6px;'>"
                f"<span style='font-weight:600;font-size:14px;color:#111827;'>{row['DSP']}</span>"
                f"<span style='background:{bg};color:{txt};border-radius:4px;padding:2px 10px;"
                f"font-size:11px;font-weight:700;'>{label}</span>"
                f"</div>"
                f"<div style='background:#F3F4F6;border-radius:4px;height:8px;width:100%;'>"
                f"<div style='background:{bar_fill};border-radius:4px;height:8px;"
                f"width:{bar_pct_display:.0f}%;max-width:100%;'></div>"
                f"</div>"
                f"<div style='display:flex;justify-content:space-between;margin-top:6px;"
                f"font-size:12px;color:#6B7280;'>"
                f"<span>Spent A${row['Spent (A$)']:,.0f} of A${row['Budget (A$)']:,.0f}</span>"
                f"<span><strong style='color:{txt};'>{pct:.1f}%</strong> paced</span>"
                f"</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

        # ── AI reallocation recommendation ────────────────────────────────────
        st.markdown("#### Reallocation Recommendation")
        api_key = get_api_key()

        if not api_key:
            st.warning("Add `ANTHROPIC_API_KEY` to Streamlit secrets to enable AI reallocation advice.")
        else:
            if st.button("✨ Get Reallocation Recommendation", type="primary", key="if_ai_btn"):

                dsp_lines = "\n".join(
                    f"  - {row['DSP']}: "
                    f"Budget A${row['Budget (A$)']:,.0f}, "
                    f"Spent A${row['Spent (A$)']:,.0f}, "
                    f"Expected A${row['Expected (A$)']:,.0f}, "
                    f"Pacing {row['Pacing %']:.1f}%"
                    for _, row in dsp_df.iterrows()
                )

                # Check brand memory — use the first client name found
                clients = list({c.get("client", "") for c in lc_campaigns if c.get("client")})
                adv_label = clients[0] if len(clients) == 1 else (", ".join(clients[:3]) if clients else "")
                _bm     = load_brand_memory()
                _bm_ctx = get_brand_context(adv_label, _bm)

                prompt = (
                    f"You are a senior programmatic trader reviewing live campaign pacing. "
                    f"Here is the current budget and pacing status by DSP:\n\n"
                    f"{dsp_lines}\n\n"
                    f"Provide:\n"
                    f"1. Which DSP is underpacing most severely and why this is a risk\n"
                    f"2. A specific budget shift recommendation: how much to move from which "
                    f"DSP to which DSP (with AUD amounts)\n"
                    f"3. What the projected pacing improvement would be after the shift\n\n"
                    f"Use Australian market context and programmatic terminology. "
                    f"All currency values are in AUD."
                )

                if _bm_ctx:
                    prompt += (
                        f"\n\nBRAND MEMORY OVERRIDE — These instructions take priority over "
                        f"all default instructions above. Where there is any conflict, always "
                        f"follow these brand-specific instructions instead:\n\n{_bm_ctx}"
                    )

                ai_client = anthropic.Anthropic(api_key=api_key)
                with st.spinner("Generating reallocation recommendation…"):
                    msg = ai_client.messages.create(
                        model="claude-sonnet-4-6",
                        max_tokens=500,
                        system=(
                            "You are a senior programmatic trader. Write clear, direct, "
                            "data-driven recommendations. Reference actual numbers. "
                            "Use programmatic terminology."
                        ),
                        messages=[{"role": "user", "content": prompt}],
                    )
                st.session_state["if_ai_text"]    = msg.content[0].text.strip()
                st.session_state["if_dsp_df"]     = dsp_df.to_dict("records")
                st.session_state["if_ai_done"]    = True

            # Display AI output
            if st.session_state.get("if_ai_text"):
                st.markdown(
                    "<div style='background:#FFFFFF;border-radius:12px;padding:20px 24px;"
                    "box-shadow:0 4px 12px rgba(0,0,0,0.08);margin-top:12px;font-size:14px;"
                    "line-height:1.7;color:#374151;'>"
                    + st.session_state["if_ai_text"].replace("\n", "<br>") +
                    "</div>",
                    unsafe_allow_html=True,
                )

            # ── Simulate Reallocation ─────────────────────────────────────────
            # Only shown after AI recommendation has been generated
            if st.session_state.get("if_ai_done"):
                st.markdown("#### Simulate Reallocation")
                st.markdown(
                    "<p style='color:#6b7280;font-size:14px;margin-top:-8px;'>"
                    "Manually enter a budget shift to see the projected delivery impact."
                    "</p>",
                    unsafe_allow_html=True,
                )

                sim_col1, sim_col2, sim_col3 = st.columns(3)
                dsp_options = list(dsp_rows.keys())
                with sim_col1:
                    from_dsp = st.selectbox("Shift FROM", dsp_options, key="sim_from_dsp")
                with sim_col2:
                    to_dsp   = st.selectbox("Shift TO",   dsp_options, key="sim_to_dsp")
                with sim_col3:
                    shift_amt = st.number_input(
                        "Amount to shift (A$)", min_value=0, max_value=1_000_000,
                        value=5_000, step=1_000, key="sim_shift_amt",
                    )

                if st.button("Simulate Reallocation", key="sim_btn"):
                    if from_dsp == to_dsp:
                        st.warning("FROM and TO DSPs must be different.")
                    else:
                        # Recalculate projected pacing for affected DSPs
                        from_data = dsp_rows.get(from_dsp, {})
                        to_data   = dsp_rows.get(to_dsp,   {})

                        from_new_budget = max(from_data["budget"] - shift_amt, from_data["spent"])
                        to_new_budget   = to_data["budget"] + shift_amt

                        from_old_pacing = (from_data["spent"] / from_data["expected"] * 100
                                           if from_data["expected"] > 0 else 0)
                        to_old_pacing   = (to_data["spent"] / to_data["expected"] * 100
                                           if to_data["expected"] > 0 else 0)

                        # New expected spend scales with new budget
                        from_new_exp = from_data["expected"] * (from_new_budget / from_data["budget"]) if from_data["budget"] > 0 else 0
                        to_new_exp   = to_data["expected"]   * (to_new_budget   / to_data["budget"])   if to_data["budget"]   > 0 else 0

                        from_new_pacing = (from_data["spent"] / from_new_exp * 100 if from_new_exp > 0 else 0)
                        to_new_pacing   = (to_data["spent"]   / to_new_exp   * 100 if to_new_exp   > 0 else 0)

                        # Clamp to a reasonable range for display
                        from_new_pacing = min(from_new_pacing, 200)
                        to_new_pacing   = min(to_new_pacing,   200)

                        st.markdown(
                            f"<div style='background:#ECFDF5;border:1px solid #6EE7B7;"
                            f"border-radius:10px;padding:16px 20px;margin-top:12px;"
                            f"font-size:14px;line-height:1.8;'>"
                            f"<strong>Simulation result:</strong> If you shift "
                            f"<strong>A${shift_amt:,.0f}</strong> from "
                            f"<strong>{from_dsp}</strong> to <strong>{to_dsp}</strong>:<br>"
                            f"&nbsp;&nbsp;• {from_dsp} pacing: "
                            f"{from_old_pacing:.1f}% → {from_new_pacing:.1f}%<br>"
                            f"&nbsp;&nbsp;• {to_dsp} pacing: "
                            f"{to_old_pacing:.1f}% → {to_new_pacing:.1f}%"
                            f"</div>",
                            unsafe_allow_html=True,
                        )

print("Budget Allocation Recommender page loaded.")
