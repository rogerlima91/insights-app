# Insights App — Project Guide

## About This Project
This is Roger's main project: an ad tech insights and reporting app built for programmatic advertising professionals.

The app reads CSV exports from DSPs (Demand-Side Platforms) such as:
- **DV360** (Display & Video 360 by Google)
- **TTD** (The Trade Desk)

It processes that data to generate performance charts, automated insights, and exports everything into PowerPoint reports ready to share with clients or internal teams.

## About Roger
- **Background:** Deep expertise in ad tech and programmatic advertising
- **Coding level:** Beginner — keep explanations clear, avoid unnecessary complexity
- **Learns best:** Through practical examples tied to ad tech concepts he already knows

## Tech Stack
- **pandas** — all data loading, cleaning, and analysis (always use pandas, never raw Python lists/dicts for data work)
- **matplotlib** — charts and visualisations
- **python-pptx** — PowerPoint export
- **Streamlit** — any interactive dashboard or UI layer

## Code Rules
1. Always use **pandas** for data work
2. Add **comments** explaining what each section of code does — especially anything non-obvious
3. End every script with a **confirmation print message** (e.g. `print("Done. Report exported.")`)
4. Keep code **simple and readable** — no clever one-liners, no unnecessary abstractions
5. Column names from DSP exports vary — always check and normalise headers early in any script

## Key Ad Tech Metrics to Know
- **CTR** = clicks / impressions
- **CPM** = (spend / impressions) × 1000
- **CPC** = spend / clicks
- **CPA** = spend / conversions
- **VCR** = video completions / video starts (View Completion Rate)
- **Viewability** = measured impressions / served impressions

## Project Structure (planned)
```
insights-app/
├── app.py               ← Streamlit UI (main entry point)
├── data/                ← Raw CSV exports from DSPs go here
├── outputs/             ← Generated PowerPoint and chart files
├── utils/               ← Helper scripts (data loading, chart builders, etc.)
└── requirements.txt
```
