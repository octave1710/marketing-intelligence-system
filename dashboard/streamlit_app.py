"""
Marketing Intelligence System — Streamlit Dashboard
=====================================================
Main entry point for the interactive dashboard.

Launch with:
    streamlit run dashboard/streamlit_app.py

Features:
- KPI cards with period-over-period changes
- Trend charts (revenue, spend, ROAS, conversions)
- Channel comparison (spend vs revenue, efficiency)
- Anomaly alerts
- AI-generated executive report
- Sidebar filters and controls
"""

import sys
from pathlib import Path

# Add project root to path so imports work
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import streamlit as st
import pandas as pd
from datetime import datetime

# Import project modules
from config.settings import DATABASE_PATH, LLM_MODEL
from src.utils.logger import logger
from src.storage.database_manager import DatabaseManager
from src.data_transformation.kpi_calculator import aggregate_kpis, safe_divide

# Import dashboard components
from dashboard.components.kpi_cards import render_kpi_cards
from dashboard.components.trend_charts import render_trend_charts
from dashboard.components.channel_comparison import render_channel_comparison
from dashboard.components.anomaly_alerts import render_anomaly_alerts
from dashboard.components.ai_report_panel import render_ai_report

# ================================================================
# PAGE CONFIG — must be first Streamlit command
# ================================================================
st.set_page_config(
    page_title="Marketing Intelligence System",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ================================================================
# LOAD CUSTOM CSS
# ================================================================
css_path = Path(__file__).parent / "style" / "custom.css"
if css_path.exists():
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


# ================================================================
# CACHED DATA LOADING
# ================================================================
@st.cache_resource
def get_database():
    """Create a single database connection (cached)."""
    return DatabaseManager()


@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_unified_data():
    """Load all unified data from database."""
    db = get_database()
    df = db.get_unified_data()
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    return df


@st.cache_data(ttl=300)
def load_daily_kpis():
    """Load daily KPI summary from database."""
    db = get_database()
    df = db.get_daily_kpis()
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    return df


@st.cache_data(ttl=300)
def load_anomalies():
    """Load anomalies from database."""
    db = get_database()
    return db.get_anomalies()


@st.cache_data(ttl=300)
def load_latest_report():
    """Load the latest AI report from database."""
    db = get_database()
    return db.get_latest_ai_report()


# ================================================================
# SIDEBAR
# ================================================================
def render_sidebar():
    """Render the sidebar with filters and controls."""
    
    st.sidebar.markdown("# 📊 Marketing Intelligence")
    st.sidebar.markdown("---")

    # Data status
    db = get_database()
    counts = db.get_table_counts()

    st.sidebar.markdown("### 📁 Data Status")
    total_rows = sum(counts.values())
    st.sidebar.caption(f"Total records: {total_rows:,}")

    for table, count in counts.items():
        emoji = "✅" if count > 0 else "⬜"
        st.sidebar.caption(f"{emoji} {table}: {count:,}")

    st.sidebar.markdown("---")

    # Date range filter
    st.sidebar.markdown("### 📅 Filters")

    df_unified = load_unified_data()
    if len(df_unified) == 0:
        st.sidebar.warning("No data loaded. Run the pipeline first.")
        return {}, None, None

    min_date = df_unified["date"].min().date()
    max_date = df_unified["date"].max().date()

    date_range = st.sidebar.date_input(
        "Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )

    # Handle single date selection
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date = end_date = date_range

    # Channel filter
    all_channels = sorted(df_unified["channel"].unique().tolist())
    selected_channels = st.sidebar.multiselect(
        "Channels",
        options=all_channels,
        default=all_channels,
    )

    # Market filter
    all_markets = sorted(df_unified["market"].unique().tolist())
    selected_markets = st.sidebar.multiselect(
        "Markets",
        options=all_markets,
        default=all_markets,
    )

    st.sidebar.markdown("---")

    # Generate report button
    st.sidebar.markdown("### 🤖 AI Analysis")
    generate_report = st.sidebar.button(
        "🔄 Generate AI Report",
        use_container_width=True,
        type="primary",
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### ℹ️ About")
    st.sidebar.caption(
        "AI-powered marketing analytics system. "
        "Analyzes Google Ads, Meta Ads, and GA4 data. "
        f"Using {LLM_MODEL} for AI analysis."
    )

    filters = {
        "start_date": str(start_date),
        "end_date": str(end_date),
        "channels": selected_channels,
        "markets": selected_markets,
    }

    return filters, generate_report, df_unified


# ================================================================
# MAIN DASHBOARD
# ================================================================
def main():
    """Main dashboard layout."""
    
    # Render sidebar and get filters
    filters, generate_report, df_all = render_sidebar()

    if df_all is None or len(df_all) == 0:
        st.title("📊 Marketing Intelligence System")
        st.error(
            "No data found in the database. Please run the pipeline first:\n\n"
            "```\npython src/storage/database_manager.py\n```"
        )
        return

    # Apply filters
    df_filtered = df_all.copy()
    df_filtered = df_filtered[
        (df_filtered["date"] >= pd.to_datetime(filters["start_date"]))
        & (df_filtered["date"] <= pd.to_datetime(filters["end_date"]))
    ]
    if filters.get("channels"):
        df_filtered = df_filtered[df_filtered["channel"].isin(filters["channels"])]
    if filters.get("markets"):
        df_filtered = df_filtered[df_filtered["market"].isin(filters["markets"])]

    if len(df_filtered) == 0:
        st.warning("No data matches the selected filters.")
        return

    # ---- Calculate KPIs for filtered data ----
    total_spend = float(df_filtered["cost"].sum())
    total_revenue = float(df_filtered["revenue"].sum())
    total_clicks = int(df_filtered["clicks"].sum())
    total_conversions = float(df_filtered["conversions"].sum())
    total_impressions = int(df_filtered["impressions"].sum())

    kpi_data = {
        "spend": total_spend,
        "revenue": total_revenue,
        "roas": total_revenue / total_spend if total_spend > 0 else None,
        "cpa": total_spend / total_conversions if total_conversions > 0 else None,
        "conversions": total_conversions,
        "cvr": total_conversions / total_clicks if total_clicks > 0 else None,
    }

    # ---- Calculate comparison period ----
    period_days = (pd.to_datetime(filters["end_date"]) - pd.to_datetime(filters["start_date"])).days + 1
    prev_end = pd.to_datetime(filters["start_date"]) - pd.Timedelta(days=1)
    prev_start = prev_end - pd.Timedelta(days=period_days - 1)

    df_prev = df_all[
        (df_all["date"] >= prev_start)
        & (df_all["date"] <= prev_end)
    ]
    if filters.get("channels"):
        df_prev = df_prev[df_prev["channel"].isin(filters["channels"])]
    if filters.get("markets"):
        df_prev = df_prev[df_prev["market"].isin(filters["markets"])]

    prev_spend = float(df_prev["cost"].sum())
    prev_revenue = float(df_prev["revenue"].sum())
    prev_conversions = float(df_prev["conversions"].sum())
    prev_clicks = int(df_prev["clicks"].sum())

    def calc_change(current, previous):
        if previous and previous > 0:
            return (current - previous) / previous
        return None

    changes = {
        "spend_change": calc_change(total_spend, prev_spend),
        "revenue_change": calc_change(total_revenue, prev_revenue),
        "roas_change": calc_change(
            total_revenue / total_spend if total_spend > 0 else 0,
            prev_revenue / prev_spend if prev_spend > 0 else 0,
        ),
        "cpa_change": calc_change(
            total_spend / total_conversions if total_conversions > 0 else 0,
            prev_spend / prev_conversions if prev_conversions > 0 else 0,
        ),
        "conversions_change": calc_change(total_conversions, prev_conversions),
        "cvr_change": calc_change(
            total_conversions / total_clicks if total_clicks > 0 else 0,
            prev_conversions / prev_clicks if prev_clicks > 0 else 0,
        ),
    }

    # ---- Header ----
    st.markdown("# 📊 Marketing Intelligence System")
    st.caption(
        f"Analyzing {filters['start_date']} to {filters['end_date']} | "
        f"{len(df_filtered):,} data points | "
        f"{len(filters.get('channels', [])):,} channels"
    )

    # ---- ROW 1: KPI Cards ----
    render_kpi_cards(kpi_data, changes)

    st.markdown("---")

    # ---- ROW 2: Trend Charts ----
    df_daily = load_daily_kpis()
    df_daily_filtered = df_daily[
        (df_daily["date"] >= pd.to_datetime(filters["start_date"]))
        & (df_daily["date"] <= pd.to_datetime(filters["end_date"]))
    ]
    if filters.get("channels"):
        # Keep "total" channel + selected channels
        keep_channels = filters["channels"] + ["total"]
        df_daily_filtered = df_daily_filtered[df_daily_filtered["channel"].isin(keep_channels)]

    if len(df_daily_filtered) > 0:
        render_trend_charts(df_daily_filtered)
    else:
        st.info("No daily KPI data available for the selected period.")

    st.markdown("---")

    # ---- ROW 3: Channel Comparison ----
    channel_data = []
    for channel in df_filtered["channel"].unique():
        ch_df = df_filtered[df_filtered["channel"] == channel]
        ch_spend = float(ch_df["cost"].sum())
        ch_revenue = float(ch_df["revenue"].sum())
        ch_clicks = int(ch_df["clicks"].sum())
        ch_conversions = float(ch_df["conversions"].sum())

        channel_data.append({
            "channel": channel,
            "spend": ch_spend,
            "revenue": ch_revenue,
            "roas": ch_revenue / ch_spend if ch_spend > 0 else None,
            "cpa": ch_spend / ch_conversions if ch_conversions > 0 else None,
            "cvr": ch_conversions / ch_clicks if ch_clicks > 0 else None,
        })

    # Top campaigns
    paid_df = df_filtered[df_filtered["cost"] > 0]
    campaigns = paid_df.groupby(["channel", "campaign_name"]).agg({
        "cost": "sum", "revenue": "sum", "conversions": "sum",
    }).reset_index()
    campaigns["roas"] = campaigns.apply(
        lambda r: round(r["revenue"] / r["cost"], 2) if r["cost"] > 0 else None, axis=1
    )
    top_5 = campaigns.dropna(subset=["roas"]).nlargest(5, "roas").to_dict("records")
    bottom_5 = campaigns.dropna(subset=["roas"]).nsmallest(5, "roas").to_dict("records")

    render_channel_comparison(channel_data, {"top": top_5, "bottom": bottom_5})

    st.markdown("---")

    # ---- ROW 4: Anomaly Alerts ----
    df_anomalies = load_anomalies()
    if len(df_anomalies) > 0:
        df_anomalies_filtered = df_anomalies.copy()
        if "date" in df_anomalies_filtered.columns:
            df_anomalies_filtered["date"] = pd.to_datetime(df_anomalies_filtered["date"])
            df_anomalies_filtered = df_anomalies_filtered[
                (df_anomalies_filtered["date"] >= pd.to_datetime(filters["start_date"]))
                & (df_anomalies_filtered["date"] <= pd.to_datetime(filters["end_date"]))
            ]
        render_anomaly_alerts(df_anomalies_filtered)
    else:
        st.info("No anomalies detected.")

    st.markdown("---")

    # ---- ROW 5: AI Report Panel ----
    # Handle report generation
    if generate_report:
        with st.spinner("🤖 Generating AI analysis... This may take 10-30 seconds."):
            try:
                from src.ai_analyst.report_compiler import compile_report
                from src.data_transformation.anomaly_detector import detect_all_anomalies
                from src.data_transformation.kpi_calculator import calculate_kpis, generate_daily_summary

                df_kpis = calculate_kpis(df_filtered)
                daily_for_report = generate_daily_summary(df_kpis)
                anomalies_for_report = detect_all_anomalies(daily_for_report)

                result = compile_report(
                    df_kpis,
                    daily_for_report,
                    anomalies_for_report,
                    period_start=filters["start_date"],
                    period_end=filters["end_date"],
                )

                # Save to database
                db = get_database()
                report_json = result["json"]
                db.save_ai_report(
                    report_id=report_json["metadata"]["report_id"],
                    report_type=report_json["metadata"]["report_type"],
                    period_start=report_json["metadata"]["period"]["start"],
                    period_end=report_json["metadata"]["period"]["end"],
                    content_json=report_json,
                    content_markdown=result["markdown"],
                    model_used=report_json["metadata"]["model_used"],
                    tokens_used=report_json["metadata"]["tokens_used"],
                    cost_usd=report_json["metadata"]["cost_usd"],
                )

                st.success("✅ AI report generated and saved!")
                # Clear cache to load new report
                load_latest_report.clear()
                st.rerun()

            except Exception as e:
                st.error(f"Failed to generate report: {str(e)}")
                logger.error(f"Report generation failed: {e}")

    # Display latest report
    report = load_latest_report()
    if report:
        render_ai_report(report.get("content", report))
    else:
        st.info(
            "No AI report generated yet. Click '🔄 Generate AI Report' "
            "in the sidebar to create one."
        )


# ================================================================
# RUN
# ================================================================
if __name__ == "__main__":
    main()
    