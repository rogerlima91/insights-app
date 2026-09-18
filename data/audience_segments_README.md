# Are Media Audience Segments — Schema Reference

> **Disclaimer:** This file and the accompanying `audience_segments.json` contain entirely fabricated, illustrative data created for demonstration and development purposes. No figures represent real Are Media inventory, actual audience sizes, genuine CPM rates, or any proprietary data. See the `_disclaimer` field in the JSON for the full statement.

---

## Overview

`audience_segments.json` is a mock first-party audience taxonomy for **Are Media**, Australia's largest women's media publisher. It contains **36 audience segments** spanning eight content categories, derived from seven source brands.

The file is structured as:

```json
{
  "_disclaimer": "...",
  "segments": [ ... ]
}
```

Each object in `segments` represents one addressable audience with a consistent schema (documented below).

---

## Categories & Source Brands

| Category  | Segments | Source Brands Used |
|-----------|----------|--------------------|
| Beauty    | 7        | ELLE, marie claire, The Australian Women's Weekly |
| Home      | 5        | Australian House & Garden, Better Homes & Gardens |
| Food      | 4        | Better Homes & Gardens, The Australian Women's Weekly, New Idea |
| Health    | 5        | The Australian Women's Weekly, marie claire, ELLE, New Idea |
| Fashion   | 5        | ELLE, marie claire, The Australian Women's Weekly |
| Parenting | 4        | Bounty Parents, The Australian Women's Weekly, New Idea |
| Travel    | 4        | The Australian Women's Weekly, ELLE, marie claire, Better Homes & Gardens, Bounty Parents |
| Finance   | 4        | The Australian Women's Weekly, ELLE, marie claire, New Idea, Australian House & Garden |

---

## Field Reference

### `segment_id`
**Type:** string

Unique identifier following the pattern `ARE_{CAT}_{NNN}`:
- `ARE` — Are Media prefix
- `{CAT}` — three-letter category code (`BEA`, `HOM`, `FOO`, `HEA`, `FAH`, `PAR`, `TRV`, `FIN`)
- `{NNN}` — zero-padded sequence number within category

Example: `ARE_BEA_004`

---

### `segment_name`
**Type:** string

Short human-readable label for the segment, suitable for UI dropdowns and reports.

---

### `description`
**Type:** string

A rich natural-language sentence describing the audience's content behaviour, engagement signals, and distinguishing characteristics. **This is the primary field for semantic search** — it is written as a full sentence, not a label, specifically so that embedding-based similarity search works well against plain-language queries like *"women buying expensive skincare"* or *"home renovation planners with high budgets"*.

---

### `category`
**Type:** string

One of: `Beauty`, `Home`, `Food`, `Health`, `Fashion`, `Parenting`, `Travel`, `Finance`

---

### `source_brands`
**Type:** array of strings

The Are Media brands whose content and audience data contribute to this segment. Always uses full brand names:

- `"The Australian Women's Weekly"`
- `"ELLE"`
- `"marie claire"`
- `"New Idea"`
- `"Australian House & Garden"`
- `"Bounty Parents"`
- `"Better Homes & Gardens"`

---

### `signal_type`
**Type:** string (enum)

Describes the primary data signal used to construct the segment:

| Value | Meaning |
|-------|---------|
| `contextual` | User was present on relevant content pages; no persistent identifier required |
| `behavioural` | Persistent engagement pattern observed across multiple sessions and visits |
| `declared` | User explicitly stated the qualifying attribute (e.g. child's age at registration, income bracket in survey) |
| `purchase intent` | Signals indicate active in-market research or buying behaviour, not just passive reading |
| `lookalike` | Modelled extension from a seed audience using statistical similarity |

Signal type affects **identity match rate** and **data trust level**. Declared data has the highest confidence; contextual has the lowest.

---

### `reach_monthly`
**Type:** integer

Estimated unique addressable users per month across the Are Media network. Three tiers are represented in this dataset:

| Tier | Reach Range | Description |
|------|-------------|-------------|
| Broad | 800,000 – 1,600,000 | Mass reach, lower index, entry-level CPM |
| Mid | 150,000 – 400,000 | Balanced reach and precision |
| Narrow / High-value | 25,000 – 80,000 | Small pool, high index, premium CPM |

Seasonal segments may report an *average across active months* — check `notes` for peak figures.

---

### `index_general_pop`
**Type:** float

How much more likely this audience is to be in this segment compared to the general Australian online population (1.0 = parity). An index of 4.0 means the audience is four times more likely to exhibit the qualifying behaviour than a random Australian adult online.

- Broad segments: 1.3 – 2.0
- Mid segments: 3.0 – 5.0
- Narrow / high-value: 8.0 – 14.0

---

### `recency_days`
**Type:** integer (30, 60, or 90)

The lookback window used to qualify users into the segment. Shorter windows (30 days) indicate fast-decaying intent signals (e.g. recipe browsing, sun care purchase intent). Longer windows (90 days) reflect categories with extended research cycles (e.g. travel inspiration, luxury finance).

---

### `indicative_cpm_min` / `indicative_cpm_max`
**Type:** float, AUD

Indicative floor and ceiling CPM in Australian dollars for a standard programmatic activation. These are not rate card figures and will vary based on:
- Deal type (PMP vs. PG vs. open market)
- Advertiser category and brand safety requirements
- Season and competitive pressure
- Impression volume committed

CPM generally increases with segment precision (higher index = higher CPM).

---

### `activation`
**Type:** array of strings

Supported deal structures for this segment. One or more of:

| Value | Meaning |
|-------|---------|
| `PMP` | Private Marketplace deal — preferred access, negotiated floor price |
| `PG` | Programmatic Guaranteed — fixed price, guaranteed impression volume |
| `curated` | Pre-packaged curated deal available via SSP marketplace |
| `DSP-onboarded` | Segment can be pushed directly to advertiser's DSP seat |

Not all segments support all activation types. Narrow and declared segments are typically restricted to `PMP` and `PG` only.

---

### `identity_match_rate`
**Type:** float (0.0 – 1.0)

The proportion of this segment's addressable audience that can be matched to a persistent, cookieless identity (e.g. hashed email, authenticated ID) for cross-channel targeting and measurement. Higher rates enable better frequency management, deduplication, and attribution.

- Declared segments: 0.65 – 0.75 (highest)
- Behavioural segments: 0.48 – 0.62
- Contextual segments: 0.42 – 0.50 (lowest)

---

### `min_spend`
**Type:** integer, AUD

Minimum campaign spend required to activate this segment, reflecting the floor needed to generate statistically meaningful delivery and reporting. Narrow, high-value segments have higher minimums due to limited pool size.

---

### `notes`
**Type:** string

Free-text operational notes including:
- **Seasonality** — activation windows, peak periods, recommended booking lead times
- **Overlap warnings** — which other segments share significant audience duplication, and whether stacking is advisable
- **Compliance requirements** — categories requiring TGA, AFSL, or brand safety pre-clearance
- **Brand guidance** — example brand names at the right price point or category
- **Methodology caveats** — data currency, rolling vs. static pools, suppression recommendations

**Always read `notes` before building a media plan** — several segments in this taxonomy have deliberate duplication that makes stack arithmetic non-trivial.

---

## Audience Tier Distribution

| Tier | Count | Reach Range | Index Range | CPM Range (AUD) |
|------|-------|-------------|-------------|-----------------|
| Broad | 8 | 820k – 1.42m | 1.3 – 1.9 | $8 – $16 |
| Mid | 10 | 155k – 390k | 3.3 – 5.1 | $15 – $32 |
| Narrow / High-value | 7 | 35k – 62k | 8.7 – 13.8 | $36 – $82 |
| Seasonal | 5 | 285k – 730k | 1.8 – 3.6 | $11 – $28 |
| Other | 6 | 165k – 390k | 3.3 – 4.7 | $15 – $29 |

---

## Known Overlapping Pairs

The following pairs share meaningful audience duplication. Do not stack without frequency management or suppression lists:

| Pair | Overlap Estimate | Notes |
|------|-----------------|-------|
| ARE_BEA_002 + ARE_BEA_004 | ~70% | Prestige skincare is a subset of skincare routine builders |
| ARE_PAR_001 + ARE_PAR_002 | ~80% | New parents are a subset of the broad parents segment |
| ARE_PAR_002 + ARE_PAR_003 | ~75% | Premium baby buyers are within the new parents pool |
| ARE_HOM_002 + ARE_HOM_003 | ~60% | Luxury renovation is a subset of renovation planners |
| ARE_FAH_002 + ARE_FAH_003 | ~60% | Buyers are a subset of aspirants |
| ARE_BEA_001 + ARE_FAH_001 | ~42% | Cross-category beauty/fashion readership overlap |
| ARE_TRV_001 + ARE_TRV_002 | ~50% | Domestic planners are a subset of travel inspiration browsers |
| ARE_HEA_001 + ARE_HEA_003 | ~55% | Premium wellness buyers are within the health broad segment |
| ARE_FOO_001 + ARE_FOO_002 | ~45% | Entertaining hosts are a subset of recipe seekers |
| ARE_FIN_002 + ARE_FIN_003 | ~40% | HNW investors overlap with super researchers |

For campaigns targeting multiple segments, work with your account team to model net unduplicated reach before committing budgets.

---

## Loading the Data in Python

```python
import json
import pandas as pd

with open("data/audience_segments.json") as f:
    data = json.load(f)

df = pd.DataFrame(data["segments"])

# Quick summary by category
print(df.groupby("category")["reach_monthly"].sum())

# Filter to high-value narrow segments
narrow = df[df["reach_monthly"] < 80000].sort_values("index_general_pop", ascending=False)
print(narrow[["segment_id", "segment_name", "reach_monthly", "index_general_pop", "indicative_cpm_max"]])
```

---

*Schema version 1.0 — fabricated demo data only.*
