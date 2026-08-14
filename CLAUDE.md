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
- **python-pptx** — PowerPoint export (built from scratch, no template file)
- **Streamlit** — interactive dashboard and multi-page UI
- **anthropic** — Claude API for AI-generated insights and PPTX content
- **openai** — Whisper API for meeting transcription
- **google-api-python-client** — Gmail integration for email context

## Quick Commands

| `make` | PowerShell | What it does |
|--------|-----------|-------------|
| `make install` | `.\tasks.ps1 install` | Install dependencies from `requirements.txt` |
| `make run` | `.\run.ps1` | Launch the Streamlit app |
| `make dev` | `.\dev.ps1` | Launch with auto-reload on file save |
| `make clean` | `.\tasks.ps1 clean` | Remove `__pycache__` and `.pyc` files |
| `make freeze` | `.\tasks.ps1 freeze` | Update `requirements.txt` from current environment |

`make` is not installed by default on Windows. Install via `winget install GnuWin32.Make` or `choco install make`. Until then, use the `.ps1` scripts.

## Code Rules
1. Always use **pandas** for data work
2. Add **comments** explaining what each section of code does — especially anything non-obvious
3. End every script with a **confirmation print message** (e.g. `print("Done. Report exported.")`)
4. Keep code **simple and readable** — no clever one-liners, no unnecessary abstractions
5. Column names from DSP exports vary — always check and normalise headers early in any script
6. After every significant change or completed feature, automatically run `git add .` and `git commit` with a descriptive commit message — do this without asking for confirmation

## Design System (Pacebird Brand)
- **Primary:** `#F5A623` warm orange — buttons, accents, active nav, card top borders
- **Secondary:** `#1B2A4A` deep navy — sidebar background, chart bars
- **Success:** `#10B981` · **Warning:** `#F59E0B` · **Danger:** `#EF4444` (RAG — do not change)
- **Page background:** `#EEF1F4` · **Cards:** white, 16px radius, `0 2px 12px rgba(0,0,0,0.06)` shadow
- **Font:** Poppins (Google Fonts)
- **Sidebar:** navy (`#1B2A4A`) background, white text, orange active nav item
- **Central design system file:** `utils/design_system.py` — import colors and `get_css()` from here
- **DO NOT revert to old purple (`#7C3AED`) or blue (`#2563EB`) values**

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
├── app.py                      ← Entry point: nav, global CSS, sidebar, onboarding
├── config.json                 ← Access tier config — controls which nav sections are visible
├── brand_memory.json           ← Stores brand context for AI insights
├── credentials.json            ← Google OAuth credentials (never commit)
├── token.json                  ← Google OAuth token (never commit)
├── requirements.txt
├── .env                        ← Local environment variables
├── .gitignore                  ← Excludes credentials.json, token.json, secrets.toml
├── .streamlit/
│   └── secrets.toml            ← API keys (never commit)
├── pages/
│   ├── brand_memory.py              ← Brand Memory page (three tabs — see below)
│   ├── publisher_qbr.py             ← QBR Generator (Sell Side)
│   ├── publisher_yield.py           ← Yield Dashboard (Sell Side)
│   └── audience_solutions.py        ← Audience Solutions (Audiences & Deals Pipeline)
├── data/
│   ├── audience_segments.json       ← Are Media mock first-party audience taxonomy (36 segments)
│   └── audience_segments_README.md  ← Schema reference for audience_segments.json
├── outputs/                    ← Generated PowerPoint and chart files
└── utils/
    └── design_system.py        ← Central design system: colour constants and shared CSS
```

## Navigation Sections (sidebar order)
```
Pacebird logo
📡 API DATA              — live API-connected workflows
📁 UPLOAD REPORT         — drag-and-drop DSP CSV analysis
📈 SELL SIDE             — publisher QBR and yield tools
🎯 AUDIENCES & DEALS PIPELINE — audience segment matching and proposal builder
```

### Access tier gating (config.json → current_tier)
| Tier | Sections visible |
|------|-----------------|
| `full_access` | All four sections |
| `api_only` | 📡 API DATA only |
| `upload_only` | 📁 UPLOAD REPORT only |
| `sell_side` | 📈 SELL SIDE + 🎯 AUDIENCES & DEALS PIPELINE |

---

## Page: app.py (Main)

### What it does
1. Accepts one or more CSV uploads from DV360, TTD, or generic DSPs
2. Detects DSP source automatically from column names
3. Normalises all column names to internal standard names (see Column Map below)
4. Displays summary metrics (Impressions, Clicks, Spend, CTR, CPM)
5. Renders four performance charts
6. Generates AI insights per brand using Claude (with Brand Memory applied)
7. Exports a PowerPoint report via the sidebar Generate Report button

### Charts
| # | Title | Type | Notes |
|---|-------|------|-------|
| 1 | Total Spend by Brand | Vertical bar | Y-axis formatted as $K / $M |
| 2 | CPM by Brand | Vertical bar | Recalculated from totals |
| 3 | Best Performing Line Items by CPM | Horizontal bar | Lowest CPM = most efficient; brand filter dropdown |
| 4 | Worst Performing Line Items by CPM | Horizontal bar | Highest CPM = least efficient; brand filter dropdown |

All charts share consistent styling: Calibri-equivalent fonts, 11pt tick labels, 12pt axis labels, 10pt bold data labels, bar width 0.5, solid colours from the brand palette.

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
| `campaign_list` | List of brand names from the current upload — read by Brand Memory page |
| `chart_spend` | PNG buffer — Spend by Brand |
| `chart_cpm` | PNG buffer — CPM by Brand |
| `chart_best_li` | PNG buffer — Best Line Items by CPM (reflects active brand filter) |
| `chart_worst_li` | PNG buffer — Worst Line Items by CPM (reflects active brand filter) |
| `insights_triggered` | Boolean — whether Generate Insights has been clicked |
| `insights_text` | Dict of `{brand_name: insight_text}` |
| `insights_overall` | Overall summary + recommendations text |
| `pptx_report` | BytesIO buffer of the generated PPTX — set after Generate Report is clicked |

### PowerPoint export
Built entirely from scratch using python-pptx — no template file required.

**Dark premium template:**
- Background: `#0D1B2A` dark navy
- Primary text: `#FFFFFF` white
- Secondary text: `#A8B2BC` light grey
- Accent: `#00A8E8` electric blue
- Font: Calibri throughout
- Footer: "Insights App" bottom-left, slide number bottom-right

**Export flow:**
1. Click **📊 Generate Report** in sidebar → AI generates all slide content (10–30s)
2. Click **📥 Download Report (.pptx)** → saves `YYYY-MM-DD_campaign_report.pptx`

**Slide structure:**
| Slide | Title | Content |
|-------|-------|---------|
| 1 | Campaign Performance Summary | 3 KPI cards (Impressions, Revenue, Brands) + Revenue by Brand chart + AI best/worst insight |
| 2 per brand | [Brand] — Performance Breakdown | Display / Video / YouTube columns, max 3 bullets each, citing CPM/CPV/VTR |
| 3 per brand | [Brand] — Recommendations | 5 action-verb bullets with specific line item / metric references |
| Last | Budget Shift Recommendations | Table: Brand \| Best IO \| Recommendation (positive actions in blue) |

All slide text is generated via synchronous Anthropic API calls at export time.

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

This is a single Streamlit page containing three tabs.

### Tab 1 — 📋 Brand Memory
- Stores brand context (objectives, KPIs, instructions) that the AI reads when generating insights
- Brand memory is matched to campaigns using **partial/case-insensitive matching** — e.g. key `"Nike"` matches campaign `"Nike Summer 2024"`
- Each brand can have multiple entries (manual notes, emails, transcripts), each individually deletable
- **Add Entry form** — select existing brand or create new; text area adds a new dated entry
- **Saved Brands view** — each entry shown as a card with type badge, date, and Delete button
- Brands are auto-deleted when their last entry is removed

### Tab 2 — 📧 Email Context
- Searches the user's Gmail for emails related to a brand
- Displays results in a checkbox table (checkbox | date | sender | subject | snippet)
- Saves selected emails individually to Brand Memory (one entry per email)
- **Search logic:** brand name picker + keyword multi-select (12 defaults) + custom keywords
- **Name expansion:** each word > 3 chars is OR'd into the Gmail query (e.g. `"Coke Festive Campaign"` → searches `"Coke Festive Campaign" OR "Coke" OR "Festive" OR "Campaign"`)
- **Auth:** OAuth2 via `credentials.json`; token cached in `token.json`; scope `gmail.readonly`

### Tab 3 — 🎙 Meeting Transcription
- Accepts audio/video upload (mp3, mp4, wav, m4a, webm, max 25 MB)
- Sends to OpenAI Whisper (`whisper-1`) for transcription
- Displays full transcript in a scrollable box
- Shows an audio player and a Download Audio button after transcription
- Saves transcript to Brand Memory as a `"transcript"` entry

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

## API Keys
All keys are loaded from **Streamlit secrets first, then environment variables**.
Secrets file: `.streamlit/secrets.toml` (never commit this file).

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
OPENAI_API_KEY = "sk-proj-..."
```

| Key | Used by | Purpose |
|-----|---------|---------|
| `ANTHROPIC_API_KEY` | app.py | Claude insights generation + PPTX slide content |
| `OPENAI_API_KEY` | pages/brand_memory.py (Tab 3) | Whisper transcription |
| Google OAuth | pages/brand_memory.py (Tab 2) | Gmail search — credentials.json + token.json |

---

## Deployment

### Streamlit Cloud
The app is deployed (or being prepared for deployment) on Streamlit Cloud.

**What works on Cloud:**
- CSV upload, charts, AI insights (Claude), PPTX export
- Brand Memory manual entries
- Meeting Transcription (Whisper) — requires `OPENAI_API_KEY` in Cloud secrets

**What does NOT work on Cloud — Gmail (Email Context tab):**
The Gmail integration uses `InstalledAppFlow.run_local_server()` which opens a browser window on the local machine to complete OAuth. This cannot work on Streamlit Cloud because there is no local browser on a cloud server. The tab will load but authentication will fail.
- **Workaround:** Use the Email Context tab locally only; save emails to Brand Memory before deploying, so the context is already in `brand_memory.json`
- **Future fix:** Would require replacing `InstalledAppFlow` with a server-side OAuth flow using `st.query_params` to handle the redirect

**Pre-deployment checklist:**
- [ ] Push latest code to GitHub
- [ ] Add secrets in Streamlit Cloud dashboard: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`
- [ ] Confirm `credentials.json`, `token.json`, `.streamlit/secrets.toml` are NOT in the repo (all in `.gitignore`)
- [ ] `brand_memory.json` can be committed if you want brand context to be available at deploy time

**requirements.txt** includes all required packages:
```
streamlit
pandas
matplotlib
python-pptx
anthropic
openai
google-api-python-client
google-auth-httplib2
google-auth-oauthlib
```
