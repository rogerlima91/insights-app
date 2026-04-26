# Insights App — Project Guide

## About This Project
This is Roger's main project: an ad tech insights and reporting app built for programmatic advertising professionals.

The app reads CSV exports from DSPs (Demand-Side Platforms) such as:
- **DV360** (Display & Video 360 by Google)
- **TTD** (The Trade Desk)

It processes that data to generate performance charts, AI-written insights, and exports everything into PowerPoint reports ready to share with clients or internal teams.

## About Roger
- **Background:** Deep expertise in ad tech and programmatic advertising
- **Coding level:** Beginner — keep explanations clear, avoid unnecessary complexity
- **Learns best:** Through practical examples tied to ad tech concepts he already knows

## Tech Stack
- **pandas** — all data loading, cleaning, and analysis (always use pandas, never raw Python lists/dicts for data work)
- **matplotlib** — charts and visualisations
- **python-pptx** — PowerPoint export
- **Streamlit** — interactive dashboard and multi-page UI
- **anthropic** — Claude API for AI-generated insights
- **openai** — Whisper API for meeting transcription
- **google-api-python-client** — Gmail integration for email context

## Code Rules
1. Always use **pandas** for data work
2. Add **comments** explaining what each section of code does — especially anything non-obvious
3. End every script with a **confirmation print message** (e.g. `print("Done. Report exported.")`)
4. Keep code **simple and readable** — no clever one-liners, no unnecessary abstractions
5. Column names from DSP exports vary — always check and normalise headers early in any script
6. After every significant change, automatically run `git add .` and `git commit` with a descriptive message summarising what was changed and why

## Key Ad Tech Metrics to Know
- **CTR** = clicks / impressions
- **CPM** = (spend / impressions) × 1000
- **CPC** = spend / clicks
- **CPA** = spend / conversions
- **CPV** = cost per view (video)
- **VTR** = video view-through rate (views / impressions)
- **VCR** = video completions / video starts (View Completion Rate)
- **Viewability** = measured impressions / served impressions

---

## Project Structure
```
insights-app/
├── app.py                      ← Main page: upload, charts, insights, PPTX export
├── brand_memory.json           ← Stores brand context for AI insights
├── credentials.json            ← Google OAuth credentials (never commit)
├── token.json                  ← Google OAuth token (never commit)
├── template.pptx.pptx          ← PowerPoint template (DV brand colours/fonts)
├── requirements.txt
├── .env                        ← Local environment variables
├── .gitignore                  ← Excludes credentials.json, token.json
├── pages/
│   ├── brand_memory.py         ← Manage brand context entries
│   ├── email_context.py        ← Search Gmail and save email context to brands
│   └── meeting_transcription.py← Transcribe meeting recordings via Whisper
├── data/                       ← Raw CSV exports from DSPs go here
├── outputs/                    ← Generated PowerPoint and chart files
└── utils/                      ← Helper scripts (currently unused)
```

---

## Page: app.py (Main)

### What it does
1. Accepts one or more CSV uploads from DV360, TTD, or generic DSPs
2. Detects DSP source automatically from column names
3. Normalises all column names to internal standard names (see Column Map below)
4. Displays summary metrics (Impressions, Clicks, Spend, CTR, CPM)
5. Renders six performance charts
6. Generates AI insights per brand using Claude (with Brand Memory applied)
7. Exports a branded PowerPoint report

### Charts
| # | Title | Type |
|---|-------|------|
| 1 | Impressions by Brand | Bar |
| 2 | CTR by Brand | Bar |
| 3 | Total Spend by Brand | Bar |
| 4 | Top 10 Line Items by Impressions | Horizontal bar |
| 5 | Impressions by Device Type | Pie |
| 6 | Impressions by Environment | Pie |

### AI Insights structure (per brand)
Every brand gets this fixed section structure:
- **[Brand Name] - Campaign Overview** — total Revenue and Impressions
- **Display** — avg CPM, best/worst Line Item and Creative by CPM (CPM, CPC, CTR)
- **Video** — CPV and VTR, best/worst Line Item and Creative (CPV, VTR)
- **YouTube** — CPV and VTR, best/worst Line Item and Creative (CPV, VTR)

Sections are skipped if the insertion order is absent from the data.
Brand Memory overrides are injected at the end of the prompt as `BRAND MEMORY OVERRIDE`.

### AI data passed to the prompt
The prompt receives four aggregated breakdowns (when columns exist):
1. Brand totals (impressions, clicks, spend, CTR, CPM)
2. Brand × Environment
3. Brand × Line Item / Creative
4. Brand × Device Type

### Session state keys set by app.py
| Key | Contents |
|-----|----------|
| `campaign_list` | List of brand names from the current upload — read by Brand Memory and Meeting Transcription pages |
| `chart_impressions` | PNG buffer for PPTX |
| `chart_ctr` | PNG buffer for PPTX |
| `chart_spend` | PNG buffer for PPTX |
| `chart_line_items` | PNG buffer for PPTX |
| `chart_device` | PNG buffer for PPTX |
| `chart_environment` | PNG buffer for PPTX |
| `insights_triggered` | Boolean — whether Generate Insights has been clicked |
| `insights_text` | Dict of `{brand_name: insight_text}` for PPTX |
| `insights_overall` | Overall summary + recommendations text for PPTX |

### PowerPoint export
Uses `template.pptx.pptx` as the base (DV navy/cyan brand colours, Arial font).
Slides: Title → Executive Summary → one slide per chart (chart left 60%, insights/recs right 40%).

---

## Column Map (COLUMN_MAP in app.py)
Normalises every DSP's column naming conventions to internal standard names.

| DSP column names accepted | Internal name |
|---------------------------|---------------|
| campaign, campaign name, campaign_name, insertion order, advertiser, brand name, brand | `campaign` |
| line item, line item name, ad group, ad group name, creative | `line_item` |
| device type, device, device_type, device category | `device_type` |
| environment, environment type, inventory type, supply type, site type | `environment` |
| date, day, week, month | `date` |
| impressions, impression, served impressions, total impressions | `impressions` |
| clicks, click, total clicks, link clicks | `clicks` |
| spend, spend (usd), total spend, media cost, media cost (usd), revenue (usd), cost, billed spend | `spend_usd` |
| conversions, total conversions, post-click conversions | `conversions` |
| ctr, click-through rate | `ctr_raw` |
| cpm, avg. cpm, average cpm | `cpm_raw` |

CTR and CPM are always recalculated from raw numbers rather than using DSP-provided values.

---

## Page: pages/brand_memory.py

### What it does
- Stores brand context (objectives, KPIs, instructions) that the AI reads when generating insights
- Brand memory is matched to campaigns using **partial/case-insensitive matching** — e.g. key `"Nike"` matches campaign `"Nike Summer 2024"`
- Each brand can have multiple entries (manual notes, email context, transcripts), each individually deletable

### UI
- **Add Entry form** — select existing brand or create new; text area adds a new dated entry
- **Saved Brands view** — shows each entry as a card with type badge, date, and Delete button

### brand_memory.json structure
```json
{
  "Brand Name": {
    "rationale": "Concatenated text of all entries — what app.py reads for AI context",
    "entries": [
      {
        "type": "manual",
        "timestamp": "2026-04-25 10:00",
        "text": "Free-text rationale written by the user"
      },
      {
        "type": "email",
        "timestamp": "2026-04-25 10:30",
        "email_date": "Fri, 25 Apr 2026 10:00:00 +0000",
        "sender": "client@example.com",
        "subject": "Campaign brief",
        "snippet": "First 200 chars of the email body"
      },
      {
        "type": "transcript",
        "timestamp": "2026-04-25 11:00",
        "text": "Meeting transcript (saved 2026-04-25 11:00, file: 'meeting.mp3'):\n\n[full transcript]"
      }
    ]
  }
}
```

**Entry type badges:** teal = Manual, purple = Email, amber = Transcript

**Important:** `rationale` is always kept in sync as the concatenation of all entry texts. `app.py` reads only `rationale` — it never reads `entries` directly.

---

## Page: pages/email_context.py

### What it does
- Searches the user's Gmail for emails related to a brand
- Displays results in a checkbox table (checkbox | date | sender | subject | snippet)
- Saves selected emails individually to Brand Memory (one entry per email)

### Search logic
- Brand name picker: dropdown of saved brands + "Type a new name"
- Keyword filter: multi-select from 12 defaults (reporting, insights, KPI, strategy, objectives, brief, performance, targets, goals, optimisation, budget, creative) + free-text custom keywords
- **Name expansion:** brand name is split by spaces and each word > 3 characters is OR'd into the Gmail query. E.g. `"Coke Festive Campaign"` searches for `("Coke Festive Campaign" OR "Coke" OR "Festive" OR "Campaign")`
- Gmail query format: `"brand terms" (keyword1 OR keyword2 OR ...)`

### Auth
- OAuth2 via `credentials.json` (Google Cloud project)
- Token saved to `token.json` after first login — subsequent runs are silent
- Scope: `gmail.readonly` (read-only, never sends or modifies)

### Saving
- Each selected email becomes its own `"email"` entry in `brand_memory.json`
- Save brand dropdown lets you consolidate emails under any existing brand (e.g. save "Coke" search results under "Coke Festive Campaign")

---

## Page: pages/meeting_transcription.py

### What it does
- Accepts an audio/video upload (mp3, mp4, wav, m4a, webm, max 25 MB)
- Sends to OpenAI Whisper (`whisper-1`) for transcription
- Displays full transcript in a scrollable box
- Saves transcript to Brand Memory as a `"transcript"` entry

### Brand selector
- Dropdown of saved brands + CSV brands from `session_state["campaign_list"]` + "Type a new brand name"

---

## API Keys
All keys are loaded from **Streamlit secrets first, then environment variables**.
Secrets file location: `.streamlit/secrets.toml`

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
OPENAI_API_KEY = "sk-proj-..."
```

| Key | Used by | Purpose |
|-----|---------|---------|
| `ANTHROPIC_API_KEY` | app.py | Claude insights generation |
| `OPENAI_API_KEY` | meeting_transcription.py | Whisper transcription |
| Google OAuth | email_context.py | Gmail search (credentials.json + token.json) |
