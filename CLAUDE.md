## Project Vision
This project serves TWO purposes:
1. **Portfolio**: Demonstrate Python, SQL, AI, data analytics, and marketing analytics skills
2. **Business foundation**: The core engine can be productized as an AI-powered marketing report generation service

Current phase: Portfolio build focused on Google Ads + Meta Ads.
Future business phase: Add more sources (Microsoft Ads, TikTok Ads, Sales data, etc.)

## What This System Does
1. Ingests marketing data from Google Ads and Meta Ads (CSV files with realistic synthetic data)
2. Cleans, normalizes, and unifies the data into a single cross-channel schema
3. Calculates marketing KPIs (ROAS, CPA, CVR, CTR, CPC, CPM, AOV, etc.)
4. Detects anomalies using statistical methods (z-score, IQR, percentage change)
5. Uses OpenAI GPT API to generate executive-ready analysis with actionable recommendations
6. Displays everything in an interactive Streamlit dashboard
7. Produces a structured report (JSON + Markdown) exportable as PDF in future business version

## Tech Stack
- **Language**: Python 3.12
- **Data manipulation**: pandas, numpy
- **Statistics**: scipy (z-scores, IQR calculations)
- **Database**: SQLite via sqlalchemy
- **AI/LLM**: OpenAI API (GPT-4o-mini for development, GPT-4o for final production reports)
- **Dashboard**: Streamlit + Plotly for interactive charts
- **Config**: python-dotenv for secrets, pyyaml for KPI definitions
- **Logging**: loguru
- **Testing**: pytest

## Project Structure

marketing-intelligence-system/
├── CLAUDE.md                  # This file
├── config/
│   ├── settings.py            # All configurable parameters
│   └── kpi_definitions.yaml   # KPI formulas, formats, thresholds
├── data/
│   ├── raw/                   # Source CSV files (generated synthetically)
│   ├── processed/             # Transformed data
│   └── database/              # SQLite database file
├── src/
│   ├── data_ingestion/        # csv_loader.py
│   ├── data_transformation/   # cleaner, normalizer, kpi_calculator, anomaly_detector, segmenter
│   ├── storage/               # database_manager.py (SQLite via sqlalchemy)
│   ├── ai_analyst/            # context_builder, prompt_engine, insight_generator,
│   │                          # recommendation_engine, report_compiler
│   └── utils/                 # logger.py, validators.py
├── dashboard/
│   ├── streamlit_app.py       # Main Streamlit entry point
│   └── components/            # kpi_cards, trend_charts, channel_comparison,
│                              # anomaly_alerts, ai_report_panel
├── scripts/
│   ├── generate_sample_data.py  # Creates realistic synthetic marketing data
│   └── run_pipeline.py          # Orchestrates the full pipeline
└── tests/                     # pytest test files

## Coding Standards

### Python Style
- Type hints on ALL function signatures
- Google-style docstrings for every function
- f-strings for string formatting (never .format() or %)
- pathlib.Path for all file paths (never os.path string concatenation)
- loguru logger for operational messages: from src.utils.logger import logger
- print() only in scripts meant for direct execution

### Naming Conventions
- Files: snake_case (kpi_calculator.py)
- Functions: snake_case (calculate_roas())
- Classes: PascalCase (DatabaseManager)
- Constants: UPPER_SNAKE_CASE (TARGET_ROAS)
- DataFrames: descriptive with df_ prefix (df_google_ads, df_unified, df_kpis)

### Data Conventions
- Column names: always lowercase with underscores
- Dates: datetime type, string format YYYY-MM-DD
- Currency: float, in USD
- Percentages: stored as decimals (0.05 means 5%), displayed as "5.0%"
- Division by zero: return None (NEVER inf, NEVER NaN, NEVER 0)
- Market codes: uppercase 2-letter ("US", "UK", "FR", "DE")
- Device names: lowercase ("desktop", "mobile", "tablet")
- Channel names: lowercase with underscores ("google_ads", "meta_ads")

### Import Order (PEP 8 style, each group separated by blank line)
1. Standard library (os, sys, pathlib, datetime, typing)
2. Third-party (pandas, numpy, plotly, openai, sqlalchemy)
3. Local project (config.settings, src.utils.logger)

### Error Handling
- Specific exceptions only (never bare except:)
- Log errors with context: logger.error(f"Failed to process {campaign_id}: {e}")
- API calls: retry with exponential backoff, max 3 retries
- Data functions: validate input DataFrame has required columns before processing
- Use Optional return types when a function can legitimately return nothing

## Marketing Domain Knowledge

### Data Sources (Portfolio Phase)
Two paid channels + organic analytics:
- **Google Ads**: Search, Display, Shopping, PMax campaigns
- **Meta Ads**: Conversions, Traffic, Awareness campaigns across Feed, Stories, Reels
- **GA4 (organic only)**: organic search, direct, email, referral (cost = 0)

### KPI Reference Table
| KPI | Formula | Good Direction | Display Format |
|-----|---------|---------------|----------------|
| CTR | clicks / impressions | up | percentage (e.g., "3.2%") |
| CPC | cost / clicks | down | currency (e.g., "$1.50") |
| CPM | (cost / impressions) * 1000 | down | currency (e.g., "$12.50") |
| CPA | cost / conversions | down | currency (e.g., "$28.00") |
| ROAS | revenue / cost | up | multiplier (e.g., "4.2x") |
| CVR | conversions / clicks | up | percentage (e.g., "3.5%") |
| AOV | revenue / conversions | up | currency (e.g., "$135.00") |
| Efficiency Index | revenue_share / spend_share | up (>1 = good) | multiplier |

### Google Ads Data Schema
Columns: date, campaign_id, campaign_name, campaign_type, market, device, impressions, clicks, cost, conversions, conversion_value, search_impression_share

### Meta Ads Data Schema
Columns: date, campaign_id, campaign_name, objective, placement, market, device, impressions, reach, clicks, link_clicks, cost, purchases, purchase_value, add_to_cart, landing_page_views, frequency

### GA4 Data Schema
Columns: date, source, medium, market, device_category, sessions, users, new_users, engaged_sessions, engagement_rate, avg_session_duration, events, conversions, total_revenue, bounce_rate

### Unified Schema (after normalization)
All channels normalized to: date, channel, channel_detail, campaign_id, campaign_name, market, device, impressions, clicks, cost, conversions, revenue

Notes:
- For GA4: impressions is proxied by sessions (documented approximation)
- For GA4: clicks is proxied by engaged_sessions
- For GA4: cost is always 0 (organic/owned channels)
- For Meta Ads: clicks uses link_clicks (not total clicks)
- For Meta Ads: conversions uses purchases, revenue uses purchase_value

### Anomaly Detection Methods
Three methods used in combination:
1. Z-Score: flag if |z| > 2.5 on 7-day rolling mean and standard deviation
2. Percentage Change: flag if >30% day-over-day change (ignore rows with <100 impressions)
3. IQR: flag if value outside [Q1 - 1.5*IQR, Q3 + 1.5*IQR] on 30-day window

Severity levels based on deviation percentage:
- low: 30-50% deviation
- medium: 50-100% deviation
- high: 100-200% deviation
- critical: >200% deviation

## Database Schema (SQLite)
Tables:
- raw_google_ads: raw Google Ads data as ingested
- raw_meta_ads: raw Meta Ads data as ingested
- raw_ga4: raw GA4 data as ingested
- transformed_unified: cleaned and normalized cross-channel data
- kpi_daily: KPIs calculated per day/channel/market/device
- kpi_weekly: KPIs aggregated by ISO week
- kpi_monthly: KPIs aggregated by month
- anomalies: detected anomalies with severity and diagnosis
- ai_reports: archived AI-generated reports (JSON content + metadata)
- pipeline_runs: execution log (timestamp, duration, status, errors)

Use sqlalchemy for all database operations. Upsert pattern to avoid duplicates.

## AI Report Output Structure
The LLM must produce analysis following this exact structure:
1. HEADLINE: one-sentence summary of the period
2. KEY METRICS: table of top-level KPIs with period-over-period changes
3. WINS: what improved, with specific numbers and likely causes
4. CONCERNS: what deteriorated, with specific numbers and possible causes
5. ANOMALIES: diagnosis of each detected anomaly (what, why, what to do)
6. RECOMMENDATIONS: 3-5 prioritized actions with expected impact and effort level
7. BUDGET REALLOCATION: suggested budget shifts between channels (if applicable)
8. OUTLOOK: what to monitor in the next period

LLM settings: temperature 0.3 (precision over creativity)
Rule: every claim must reference a specific number from the data

## Configuration Files
- All parameters: config/settings.py
- KPI definitions: config/kpi_definitions.yaml
- API keys: .env (NEVER hardcode, NEVER commit to git)
- To use settings: from config.settings import PARAMETER_NAME

## Common Commands
- python scripts/generate_sample_data.py (generate synthetic data)
- python scripts/run_pipeline.py (run full pipeline end to end)
- streamlit run dashboard/streamlit_app.py (launch dashboard)
- pytest tests/ -v (run all tests)

## Quality Standards
- This is a PORTFOLIO project: code quality, documentation, and presentation matter
- The AI report must be genuinely useful to a VP Marketing, not a toy demo
- Dashboard: dark theme (#0E1117 background), Plotly charts, clean professional layout
- Every module must work independently and be testable in isolation
- Synthetic data must be realistic: weekend dips, growth trends, random noise, injected anomalies
- README.md must have screenshots, architecture diagram, and clear setup instructions

## Current Development Phase
Phase: SETUP COMPLETE
Next: Generate synthetic marketing data (scripts/generate_sample_data.py)