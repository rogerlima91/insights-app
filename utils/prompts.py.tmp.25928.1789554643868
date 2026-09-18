"""
utils/prompts.py — All Anthropic API prompt builders for the Insights App.

Every prompt lives here as a builder function or constant. Call sites import
the function or constant they need — no prompt text anywhere else in the codebase.

Usage:
    from utils.prompts import brand_insight_prompt, SYSTEM_PROGRAMMATIC_ANALYST
    prompt = brand_insight_prompt(campaign_name, all_data, brand_context)
"""

# ── System prompts ─────────────────────────────────────────────────────────

# Used by stream_insight() and stream_overall() in performance_insights.py
SYSTEM_PROGRAMMATIC_ANALYST = (
    "You are a senior programmatic advertising analyst with deep expertise in "
    "DSP campaign performance (DV360, TTD). You write clear, concise, data-driven "
    "commentary for ad tech professionals. Be specific — reference actual numbers. "
    "Follow the section headings and structure exactly as specified in each prompt. "
    "Do not add extra sections or deviate from the requested format."
)

# Used by _ai_pptx() in performance_insights.py
SYSTEM_PPTX_ANALYST = (
    "You are a senior programmatic advertising analyst. "
    "Write clear, concise, data-driven commentary for ad tech professionals. "
    "Be specific — always reference actual numbers from the data. "
    "Follow formatting instructions exactly — no deviations."
)

# Used by budget_allocation.py — pre-flight allocation rationale
SYSTEM_BUDGET_STRATEGIST = (
    "You are a senior programmatic strategist at a media agency. "
    "Write clear, direct, data-driven recommendations. "
    "Be specific. Use programmatic advertising terminology."
)

# Used by budget_allocation.py — in-flight pacing reallocation
SYSTEM_PACING_TRADER = (
    "You are a senior programmatic trader. Write clear, direct, "
    "data-driven recommendations. Reference actual numbers. "
    "Use programmatic terminology."
)

# Used by uber_roi_calculator.py — pre-campaign business case
SYSTEM_UBER_PARTNER_MANAGER = (
    "You are a Partner Manager at Uber Advertising ANZ. "
    "Write commercially confident, data-driven business cases. "
    "Be specific with numbers. Use Australian English."
)

# Used by uber_roi_calculator.py — post-campaign outcome analysis
SYSTEM_UBER_SENIOR_PM = (
    "You are a senior Uber Advertising ANZ Partner Manager. "
    "Write direct, data-led campaign reviews with clear next steps. "
    "Use Australian English."
)


# ── Brand memory override block ────────────────────────────────────────────
# CRITICAL: Preserve this wording exactly — the exact phrasing is intentional.
# This block is appended to any prompt that supports brand memory context.

def _brand_memory_block(brand_context: str) -> str:
    """Returns the brand memory override block for appending to prompts."""
    return (
        f"\n\nBRAND MEMORY OVERRIDE — These instructions take priority over "
        f"all default instructions above. Where there is any conflict, always "
        f"follow these brand-specific instructions instead:\n\n"
        f"{brand_context}"
    )


# ── Performance Insights: streaming brand analysis ─────────────────────────

def brand_insight_prompt(campaign_name: str, all_data: str,
                         brand_context: str = "") -> str:
    """
    Per-brand streaming insight prompt (stream_insight in performance_insights.py).
    Generates Display / Video / YouTube insertion-order breakdown.
    Brand memory override is appended when brand_context is provided.
    """
    # Fixed structure: Campaign Overview + three insertion-order sections.
    # The AI skips any section whose insertion order is absent from the data.
    structure = (
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

    override = _brand_memory_block(brand_context) if brand_context else ""

    return (
        f"Here is the full performance data for all campaigns in this report:\n\n"
        f"{all_data}\n\n"
        f"Write the analysis for the '{campaign_name}' brand using exactly "
        f"this structure and these headings (use ** for bold):\n\n"
        f"{structure}"
        f"{override}\n\n"
        f"Use only the data provided — do not invent numbers."
    )


def overall_summary_prompt(all_data: str) -> str:
    """
    Cross-campaign summary prompt (stream_overall in performance_insights.py).
    Generates: Summary, Best & Worst Performers, Optimisation Recommendations.
    """
    return (
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


# ── PPTX slide prompts ─────────────────────────────────────────────────────

def pptx_exec_summary_prompt(data_text: str) -> str:
    """Executive summary slide: best and worst performer insight paragraphs."""
    return (
        f"Campaign performance data:\n{data_text}\n\n"
        f"Write two short insight paragraphs for an executive summary slide:\n"
        f"1. Start \"Best performer: [Brand] —\" then 1-2 sentences on WHY, "
        f"citing key metrics (CPM, CTR, or CPV).\n"
        f"2. Start \"Worst performer: [Brand] —\" then 1-2 sentences on WHY, "
        f"citing key metrics.\n\n"
        f"Plain paragraphs only — no headings, no bullets, no extra text."
    )


def pptx_brand_breakdown_prompt(data_text: str, brand: str) -> str:
    """Per-brand performance breakdown slide (Display / Video / YouTube columns)."""
    return (
        f"Campaign performance data:\n{data_text}\n\n"
        f"Write a performance breakdown for brand: \"{brand}\"\n\n"
        f"Use EXACTLY this format — only include sections where data exists "
        f"for this brand:\n\n"
        f"DISPLAY:\n"
        f"• [CPM, CPC, CTR focus — cite best/worst line item, max 15 words]\n"
        f"• [second point]\n"
        f"• [third point — max 3 bullets]\n\n"
        f"VIDEO:\n"
        f"• [CPV, VTR focus — cite best/worst line item, max 15 words]\n"
        f"• [second point]\n"
        f"• [third point — max 3 bullets]\n\n"
        f"YOUTUBE:\n"
        f"• [CPV, VTR focus — cite best/worst creative, max 15 words]\n"
        f"• [second point]\n"
        f"• [third point — max 3 bullets]\n\n"
        f"Only include DISPLAY / VIDEO / YOUTUBE headings that have real data "
        f"for this brand."
    )


def pptx_brand_recommendations_prompt(data_text: str, brand: str) -> str:
    """Per-brand recommendations slide: exactly 5 action-verb bullets."""
    return (
        f"Campaign performance data:\n{data_text}\n\n"
        f"Write exactly 5 optimisation recommendations for brand: \"{brand}\"\n\n"
        f"Rules:\n"
        f"- Each must start with an action verb: Increase / Reduce / Pause / "
        f"Test / Shift / Reallocate\n"
        f"- Reference specific line items, creatives, or metrics from the data\n"
        f"- Max 18 words per line\n"
        f"- Return only the 5 lines — no bullet symbols, no numbering, no extra text"
    )


def pptx_budget_shift_prompt(data_text: str) -> str:
    """Budget Shift Recommendations slide: pipe-separated Brand | IO | Recommendation."""
    return (
        f"Campaign performance data:\n{data_text}\n\n"
        f"For each brand, provide one budget reallocation recommendation.\n"
        f"Format EXACTLY as pipe-separated lines — one line per brand, no header row:\n"
        f"Brand Name | Best Performing IO | One-sentence recommendation starting "
        f"with an action verb\n\n"
        f"Example:\n"
        f"Nike Summer 2024 | Display | Increase Display budget by 20% — lowest CPM at $3.20\n"
        f"Coke Q3 | YouTube | Shift 15% from Display to YouTube — VTR of 68% outperforms\n\n"
        f"Only include brands from the data. Cite actual numbers. No extra text."
    )


def pptx_ai_driven_prompt(data_text: str) -> str:
    """AI-Driven Analysis slide: SUMMARY paragraph + TOP FINDING."""
    return (
        f"Campaign performance data:\n{data_text}\n\n"
        f"Provide a brief AI analysis in two parts:\n"
        f"1. SUMMARY: One paragraph on the most important patterns in this dataset.\n"
        f"2. TOP FINDING: The single most important anomaly or insight.\n\n"
        f"Format exactly as:\n"
        f"SUMMARY: [text]\n"
        f"TOP FINDING: [text]"
    )


# ── AI-Driven chart recommendations ───────────────────────────────────────

def chart_recommendations_prompt(columns_list, sample_rows: str,
                                  brand_ctx_injection: str, seed_val: int) -> str:
    """
    JSON-returning prompt for AI-driven chart recommendations.
    Returns exactly 3 chart suggestions with title, chart_type, x/y axes,
    rationale, and anomaly fields.
    """
    return (
        f"You are an expert data analyst reviewing a programmatic advertising "
        f"dataset. Here are the columns available: {columns_list}. "
        f"Here is a sample of the data:\n\n"
        f"{sample_rows}"
        f"{brand_ctx_injection}\n\n"
        f"Return a JSON response only, no other text, with this exact structure:\n"
        "{{\n"
        "  \"insights\": [\n"
        "    {{\n"
        "      \"title\": \"Chart title\",\n"
        "      \"chart_type\": \"bar|line|scatter|pie\",\n"
        "      \"x_axis\": \"column name\",\n"
        "      \"y_axis\": \"column name\",\n"
        "      \"rationale\": \"Why this chart surfaces a useful insight\",\n"
        "      \"anomaly\": \"Any anomaly detected in this dimension or null\"\n"
        "    }}\n"
        "  ],\n"
        "  \"summary\": \"One paragraph summary of the most important patterns "
        "in this dataset\",\n"
        "  \"top_anomaly\": \"The single most important anomaly or finding across "
        "the whole dataset\"\n"
        "}}\n"
        f"Return exactly 3 chart recommendations. Seed: {seed_val}"
    )


# ── Natural language Q&A ───────────────────────────────────────────────────

def nl_query_prompt(summary_parts: list, agg_sample: str, nl_question: str) -> str:
    """
    Natural language Q&A over uploaded campaign dataset.
    Returns a direct 2-3 sentence answer with specific numbers.
    """
    return (
        f"You are an expert programmatic advertising analyst. The user has "
        f"uploaded a campaign performance dataset.\n\n"
        f"Dataset summary:\n"
        f"{chr(10).join(summary_parts)}\n\n"
        f"Data sample:\n"
        f"{agg_sample}\n\n"
        f"User question: {nl_question}\n\n"
        f"Provide a direct, specific answer in plain English. Include the specific "
        f"numbers from the data. Keep your answer to 2-3 sentences maximum."
    )


# ── Supply Brief: publisher commentary ────────────────────────────────────

def supply_commentary_prompt(week_label: str, cur: dict,
                              yield_findings: list) -> str:
    """
    Publisher-facing weekly supply performance commentary.
    Generates 3 paragraphs: overall performance, key issues, recommended actions.
    Uses sell-side vocabulary (eCPM, fill rate, demand sources, inventory).
    """
    findings_text = "\n".join(
        f"- {f['title']}: {f['detail']}"
        for f in yield_findings[:5]
    )
    return (
        f"You are writing a publisher-facing weekly supply "
        f"performance commentary for {week_label}.\n\n"
        f"Key metrics this week:\n"
        f"  Revenue: A${cur.get('revenue_aud', 0):,.0f}\n"
        f"  Fill Rate: {cur.get('fill_rate', 0):.1%}\n"
        f"  eCPM: A${cur.get('ecpm', 0):.2f}\n"
        f"  Completion Rate: {cur.get('completion_rate', 0):.1%}\n\n"
        f"Top findings:\n"
        f"{findings_text}\n\n"
        f"Write 3 concise paragraphs: (1) overall performance "
        f"summary, (2) key issues and their context, "
        f"(3) recommended actions. Use sell-side vocabulary "
        f"(eCPM, fill rate, demand sources, inventory). "
        f"Be specific and data-driven."
    )


# ── Budget Allocation ──────────────────────────────────────────────────────

def budget_allocation_rationale_prompt(adv_disp, obj_disp, bud_disp,
                                        st_disp, en_disp, alloc_lines: str,
                                        brand_context: str = "") -> str:
    """
    Pre-flight budget allocation rationale (budget_allocation.py).
    Explains DSP/format split, flags one risk, and gives an alternative scenario.
    Appends brand memory override when brand_context is provided.
    """
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
    if brand_context:
        prompt += _brand_memory_block(brand_context)
    return prompt


def pacing_reallocation_prompt(dsp_lines: str, brand_context: str = "") -> str:
    """
    In-flight pacing reallocation recommendation (budget_allocation.py).
    Identifies the worst-pacing DSP and recommends a specific budget shift.
    Appends brand memory override when brand_context is provided.
    """
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
    if brand_context:
        prompt += _brand_memory_block(brand_context)
    return prompt


# ── Uber ROI Calculator ────────────────────────────────────────────────────

def uber_roi_business_case_prompt(fc_inputs: dict, cons: dict,
                                   base: dict, opti: dict) -> str:
    """
    Pre-campaign ROI business case for a restaurant Uber Ads partner.
    3 paragraphs: revenue opportunity, incremental orders rationale, recommended budget.
    """
    campaign_types = ', '.join(fc_inputs['campaign_types']) or 'None'
    dayparts = ', '.join(fc_inputs['dayparts']) or 'All dayparts'
    return (
        f"You are a Partner Manager at Uber Advertising ANZ building a business case "
        f"for a {fc_inputs['category']} restaurant partner to invest in Uber Ads. "
        f"Here are the calculated projections:\n\n"
        f"PARTNER PROFILE\n"
        f"- Category: {fc_inputs['category']}\n"
        f"- Average order value: A${fc_inputs['avg_order_value']:.2f}\n"
        f"- Current monthly organic orders: {fc_inputs['organic_orders']:,}\n"
        f"- Number of Uber Eats locations: {fc_inputs['num_locations']}\n"
        f"- Uber Eats rating: {fc_inputs['rating']:.1f}\n\n"
        f"CAMPAIGN PARAMETERS\n"
        f"- Monthly ad budget: A${fc_inputs['monthly_budget']:,.0f}\n"
        f"- Campaign types: {campaign_types}\n"
        f"- Objective: {fc_inputs['target_objective']}\n"
        f"- Duration: {fc_inputs['campaign_weeks']} weeks\n"
        f"- Daypart focus: {dayparts}\n\n"
        f"PROJECTIONS\n"
        f"Conservative — {cons['orders']:,.0f} total orders, "
        f"{cons['incr_orders']:,.0f} incremental, "
        f"A${cons['revenue']:,.0f} revenue, {cons['roas']:.2f}x ROAS, "
        f"A${cons['cpo']:.2f} CPO\n"
        f"Base Case    — {base['orders']:,.0f} total orders, "
        f"{base['incr_orders']:,.0f} incremental, "
        f"A${base['revenue']:,.0f} revenue, {base['roas']:.2f}x ROAS, "
        f"A${base['cpo']:.2f} CPO\n"
        f"Optimistic   — {opti['orders']:,.0f} total orders, "
        f"{opti['incr_orders']:,.0f} incremental, "
        f"A${opti['revenue']:,.0f} revenue, {opti['roas']:.2f}x ROAS, "
        f"A${opti['cpo']:.2f} CPO\n\n"
        f"Write a compelling 3-paragraph business case that:\n"
        f"1. Opens with the revenue opportunity using base case numbers\n"
        f"2. Explains why incremental orders matter more than total orders\n"
        f"3. Closes with a clear recommended starting budget and expected return\n\n"
        f"Write in a consultative, commercially confident tone suitable for "
        f"presenting to a restaurant partner's marketing director. "
        f"All currency values are in AUD (A$ symbol)."
    )


def uber_campaign_outcome_prompt(oc_inp: dict, oc_met: dict, oc_h: int,
                                  bench_roas: float, bench_cpo: float,
                                  bench_ctr: float, bench_incr: float) -> str:
    """
    Post-campaign outcome analysis and recommendations (uber_roi_calculator.py).
    3 paragraphs: overall performance, strongest/weakest vs benchmark, next-campaign recs.
    """
    restaurant = oc_inp.get('restaurant_name') or oc_inp['category']
    return (
        f"You are a senior Uber Advertising ANZ Partner Manager reviewing a completed "
        f"campaign for a {oc_inp['category']} restaurant.\n\n"
        f"CAMPAIGN DETAILS\n"
        f"- Restaurant: {restaurant}\n"
        f"- Spend: A${oc_inp['spend']:,.0f}\n"
        f"- Duration: {oc_inp['start_date']} to {oc_inp['end_date']}\n\n"
        f"ACTUALS vs TARGETS\n"
        f"- ROAS: {oc_met['actual_roas']:.2f}x (target {oc_inp['target_roas']:.1f}x)\n"
        f"- Total Orders: {oc_inp['total_orders']:,} (target {oc_inp['target_orders']:,})\n"
        f"- Incremental Orders: {oc_inp['incr_orders']:,}\n"
        f"- CPO: A${oc_met['actual_cpo']:.2f}\n"
        f"- CTR: {oc_met['ctr']:.2f}%  |  Conv Rate: {oc_met['conv_rate']:.2f}%\n"
        f"- Incremental Rate: {oc_met['incr_rate']:.1f}%\n"
        f"- Campaign Health Score: {oc_h}/100\n\n"
        f"CATEGORY BENCHMARKS\n"
        f"- Benchmark ROAS: {bench_roas:.1f}x  |  Benchmark CPO: A${bench_cpo:.2f}\n"
        f"- Benchmark CTR: {bench_ctr:.1f}%  |  Benchmark Incremental Rate: {bench_incr:.0f}%\n\n"
        f"Write a 3-paragraph campaign analysis that:\n"
        f"1. Summarises overall campaign performance and health score in context\n"
        f"2. Identifies the 1-2 strongest and weakest metrics vs benchmark\n"
        f"3. Gives 3 specific, actionable recommendations for the next campaign\n\n"
        f"Write in a direct, commercially confident tone for a restaurant marketing "
        f"director. Use A$ for all currency. Be specific with numbers."
    )
