"""
Database Manager
=================
Handles all SQLite database operations:
- Creating tables
- Inserting/upserting data
- Querying data for the dashboard and AI analyst
- Archiving AI reports

Uses SQLAlchemy for database operations. The database file is stored at
data/database/marketing_data.db (configured in settings.py).
"""

from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime
import sys
import json

import pandas as pd
from sqlalchemy import create_engine, text

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config.settings import DATABASE_PATH
from src.utils.logger import logger


class DatabaseManager:
    """
    Manages all database operations for the Marketing Intelligence System.
    
    Usage:
        db = DatabaseManager()
        db.initialize()  # Creates tables if they don't exist
        db.save_unified_data(df)
        df = db.get_latest_kpis(period="7d")
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to SQLite file. Uses default from settings if None.
        """
        self.db_path = db_path or DATABASE_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # SQLAlchemy engine — the connection manager
        # "sqlite:///" + path creates a connection to the SQLite file
        self.engine = create_engine(f"sqlite:///{self.db_path}", echo=False)

        logger.info(f"Database initialized at {self.db_path}")

    def initialize(self):
        """
        Create all tables if they don't exist.
        This is safe to call multiple times — it won't delete existing data.
        """
        logger.info("Creating database tables...")

        with self.engine.connect() as conn:
            # Raw data tables
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS raw_google_ads (
                    date TEXT,
                    campaign_id TEXT,
                    campaign_name TEXT,
                    campaign_type TEXT,
                    market TEXT,
                    device TEXT,
                    impressions INTEGER,
                    clicks INTEGER,
                    cost REAL,
                    conversions REAL,
                    conversion_value REAL,
                    search_impression_share REAL,
                    PRIMARY KEY (date, campaign_id, market, device)
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS raw_meta_ads (
                    date TEXT,
                    campaign_id TEXT,
                    campaign_name TEXT,
                    objective TEXT,
                    placement TEXT,
                    market TEXT,
                    device TEXT,
                    impressions INTEGER,
                    reach INTEGER,
                    clicks INTEGER,
                    link_clicks INTEGER,
                    cost REAL,
                    purchases REAL,
                    purchase_value REAL,
                    add_to_cart INTEGER,
                    landing_page_views INTEGER,
                    frequency REAL,
                    PRIMARY KEY (date, campaign_id, market, device)
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS raw_ga4 (
                    date TEXT,
                    source TEXT,
                    medium TEXT,
                    market TEXT,
                    device_category TEXT,
                    sessions INTEGER,
                    users INTEGER,
                    new_users INTEGER,
                    engaged_sessions INTEGER,
                    engagement_rate REAL,
                    avg_session_duration REAL,
                    events INTEGER,
                    conversions INTEGER,
                    total_revenue REAL,
                    bounce_rate REAL,
                    PRIMARY KEY (date, source, medium, market, device_category)
                )
            """))

            # Transformed unified data
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS transformed_unified (
                    date TEXT,
                    channel TEXT,
                    channel_detail TEXT,
                    campaign_id TEXT,
                    campaign_name TEXT,
                    market TEXT,
                    device TEXT,
                    impressions INTEGER,
                    clicks INTEGER,
                    cost REAL,
                    conversions REAL,
                    revenue REAL,
                    ctr REAL,
                    cpc REAL,
                    cpm REAL,
                    cpa REAL,
                    roas REAL,
                    cvr REAL,
                    aov REAL,
                    PRIMARY KEY (date, campaign_id, market, device)
                )
            """))

            # KPI summary tables
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS kpi_daily (
                    date TEXT,
                    channel TEXT,
                    impressions INTEGER,
                    clicks INTEGER,
                    cost REAL,
                    conversions REAL,
                    revenue REAL,
                    ctr REAL,
                    cpc REAL,
                    cpm REAL,
                    cpa REAL,
                    roas REAL,
                    cvr REAL,
                    aov REAL,
                    PRIMARY KEY (date, channel)
                )
            """))

            # Anomalies table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS anomalies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT,
                    channel TEXT,
                    campaign_id TEXT,
                    market TEXT,
                    kpi TEXT,
                    value REAL,
                    expected_value REAL,
                    deviation_pct REAL,
                    detection_method TEXT,
                    severity TEXT,
                    direction TEXT,
                    description TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """))

            # AI reports archive
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS ai_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_id TEXT UNIQUE,
                    report_type TEXT,
                    period_start TEXT,
                    period_end TEXT,
                    content_json TEXT,
                    content_markdown TEXT,
                    model_used TEXT,
                    tokens_used INTEGER,
                    cost_usd REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """))

            # Pipeline run log
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS pipeline_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT,
                    completed_at TEXT,
                    duration_seconds REAL,
                    status TEXT,
                    rows_processed INTEGER,
                    anomalies_found INTEGER,
                    errors TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """))

            conn.commit()

        logger.info("  ✅ All tables created successfully")

    # ==============================================================
    # SAVE METHODS
    # ==============================================================

    def save_raw_data(self, df: pd.DataFrame, source_name: str):
        """Save raw data to the corresponding table."""
        table_name = f"raw_{source_name}"
        df_to_save = df.copy()

        # Convert datetime to string for SQLite
        if "date" in df_to_save.columns:
            df_to_save["date"] = df_to_save["date"].astype(str)

        df_to_save.to_sql(table_name, self.engine, if_exists="replace", index=False)
        logger.info(f"  ✅ Saved {len(df_to_save):,} rows to {table_name}")

    def save_unified_data(self, df: pd.DataFrame):
        """Save transformed unified data with KPIs."""
        df_to_save = df.copy()
        if "date" in df_to_save.columns:
            df_to_save["date"] = df_to_save["date"].astype(str)

        df_to_save.to_sql("transformed_unified", self.engine, if_exists="replace", index=False)
        logger.info(f"  ✅ Saved {len(df_to_save):,} rows to transformed_unified")

    def save_daily_kpis(self, df: pd.DataFrame):
        """Save daily KPI summary."""
        df_to_save = df.copy()
        if "date" in df_to_save.columns:
            df_to_save["date"] = df_to_save["date"].astype(str)

        df_to_save.to_sql("kpi_daily", self.engine, if_exists="replace", index=False)
        logger.info(f"  ✅ Saved {len(df_to_save):,} rows to kpi_daily")

    def save_anomalies(self, df: pd.DataFrame):
        """Save detected anomalies."""
        if len(df) == 0:
            logger.info("  No anomalies to save")
            return

        df_to_save = df.copy()
        if "date" in df_to_save.columns:
            df_to_save["date"] = df_to_save["date"].astype(str)

        df_to_save.to_sql("anomalies", self.engine, if_exists="replace", index=False)
        logger.info(f"  ✅ Saved {len(df_to_save):,} anomalies")

    def save_ai_report(
        self,
        report_id: str,
        report_type: str,
        period_start: str,
        period_end: str,
        content_json: Dict,
        content_markdown: str,
        model_used: str,
        tokens_used: int,
        cost_usd: float,
    ):
        """Archive a generated AI report."""
        with self.engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT OR REPLACE INTO ai_reports 
                    (report_id, report_type, period_start, period_end,
                     content_json, content_markdown, model_used, tokens_used, cost_usd)
                    VALUES (:rid, :rtype, :pstart, :pend, :cjson, :cmd, :model, :tokens, :cost)
                """),
                {
                    "rid": report_id,
                    "rtype": report_type,
                    "pstart": period_start,
                    "pend": period_end,
                    "cjson": json.dumps(content_json),
                    "cmd": content_markdown,
                    "model": model_used,
                    "tokens": tokens_used,
                    "cost": cost_usd,
                },
            )
            conn.commit()
        logger.info(f"  ✅ AI report saved: {report_id}")

    def log_pipeline_run(
        self,
        started_at: str,
        completed_at: str,
        duration_seconds: float,
        status: str,
        rows_processed: int,
        anomalies_found: int,
        errors: str = "",
    ):
        """Log a pipeline execution."""
        with self.engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO pipeline_runs 
                    (started_at, completed_at, duration_seconds, status,
                     rows_processed, anomalies_found, errors)
                    VALUES (:started, :completed, :duration, :status,
                            :rows, :anomalies, :errors)
                """),
                {
                    "started": started_at,
                    "completed": completed_at,
                    "duration": duration_seconds,
                    "status": status,
                    "rows": rows_processed,
                    "anomalies": anomalies_found,
                    "errors": errors,
                },
            )
            conn.commit()
        logger.info(f"  ✅ Pipeline run logged: {status}")

    # ==============================================================
    # QUERY METHODS
    # ==============================================================

    def get_unified_data(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        channels: Optional[List[str]] = None,
        markets: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Query unified data with optional filters.
        
        Args:
            start_date: Filter from this date (YYYY-MM-DD)
            end_date: Filter to this date
            channels: Filter to specific channels
            markets: Filter to specific markets
        """
        query = "SELECT * FROM transformed_unified WHERE 1=1"
        params = {}

        if start_date:
            query += " AND date >= :start"
            params["start"] = start_date
        if end_date:
            query += " AND date <= :end"
            params["end"] = end_date
        if channels:
            placeholders = ", ".join([f":ch{i}" for i in range(len(channels))])
            query += f" AND channel IN ({placeholders})"
            for i, ch in enumerate(channels):
                params[f"ch{i}"] = ch
        if markets:
            placeholders = ", ".join([f":mk{i}" for i in range(len(markets))])
            query += f" AND market IN ({placeholders})"
            for i, mk in enumerate(markets):
                params[f"mk{i}"] = mk

        df = pd.read_sql(text(query), self.engine, params=params)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        return df

    def get_daily_kpis(
        self,
        period: str = "all",
        channel: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Get daily KPI summary.
        
        Args:
            period: "7d", "30d", "90d", or "all"
            channel: Optional channel filter
        """
        query = "SELECT * FROM kpi_daily WHERE 1=1"
        params = {}

        if period != "all":
            days = int(period.replace("d", ""))
            query += " AND date >= date('now', :days_ago)"
            params["days_ago"] = f"-{days} days"

        if channel:
            query += " AND channel = :channel"
            params["channel"] = channel

        query += " ORDER BY date, channel"

        df = pd.read_sql(text(query), self.engine, params=params)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        return df

    def get_anomalies(
        self,
        severity: Optional[str] = None,
        limit: int = 50,
    ) -> pd.DataFrame:
        """Get detected anomalies, optionally filtered by severity."""
        query = "SELECT * FROM anomalies WHERE 1=1"
        params = {}

        if severity:
            query += " AND severity = :severity"
            params["severity"] = severity

        query += " ORDER BY date DESC LIMIT :limit"
        params["limit"] = limit

        df = pd.read_sql(text(query), self.engine, params=params)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        return df

    def get_latest_ai_report(self) -> Optional[Dict]:
        """Get the most recent AI report."""
        query = "SELECT * FROM ai_reports ORDER BY created_at DESC LIMIT 1"
        df = pd.read_sql(text(query), self.engine)

        if len(df) == 0:
            return None

        row = df.iloc[0]
        return {
            "report_id": row["report_id"],
            "report_type": row["report_type"],
            "period_start": row["period_start"],
            "period_end": row["period_end"],
            "content": json.loads(row["content_json"]),
            "markdown": row["content_markdown"],
            "model_used": row["model_used"],
            "tokens_used": row["tokens_used"],
            "cost_usd": row["cost_usd"],
            "created_at": row["created_at"],
        }

    def get_channel_summary(self) -> pd.DataFrame:
        """Get aggregated KPIs by channel (for the whole period)."""
        query = """
            SELECT 
                channel,
                SUM(impressions) as impressions,
                SUM(clicks) as clicks,
                SUM(cost) as cost,
                SUM(conversions) as conversions,
                SUM(revenue) as revenue,
                CASE WHEN SUM(impressions) > 0 
                     THEN CAST(SUM(clicks) AS REAL) / SUM(impressions) 
                     ELSE NULL END as ctr,
                CASE WHEN SUM(clicks) > 0 
                     THEN SUM(cost) / SUM(clicks) 
                     ELSE NULL END as cpc,
                CASE WHEN SUM(conversions) > 0 
                     THEN SUM(cost) / SUM(conversions) 
                     ELSE NULL END as cpa,
                CASE WHEN SUM(cost) > 0 
                     THEN SUM(revenue) / SUM(cost) 
                     ELSE NULL END as roas,
                CASE WHEN SUM(clicks) > 0 
                     THEN CAST(SUM(conversions) AS REAL) / SUM(clicks) 
                     ELSE NULL END as cvr
            FROM transformed_unified
            GROUP BY channel
            ORDER BY cost DESC
        """
        return pd.read_sql(text(query), self.engine)

    def get_table_counts(self) -> Dict[str, int]:
        """Get row counts for all tables (for status checking)."""
        tables = [
            "raw_google_ads", "raw_meta_ads", "raw_ga4",
            "transformed_unified", "kpi_daily",
            "anomalies", "ai_reports", "pipeline_runs",
        ]
        counts = {}
        with self.engine.connect() as conn:
            for table in tables:
                try:
                    result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    counts[table] = result.scalar()
                except Exception:
                    counts[table] = 0
        return counts


if __name__ == "__main__":
    from src.data_ingestion.csv_loader import load_all_sources
    from src.data_transformation.cleaner import clean_all_sources
    from src.data_transformation.normalizer import normalize_all_sources
    from src.data_transformation.kpi_calculator import calculate_kpis, generate_daily_summary
    from src.data_transformation.anomaly_detector import detect_all_anomalies

    # Full chain
    print("Running full pipeline into database...\n")

    raw_data = load_all_sources()
    cleaned_data, _ = clean_all_sources(raw_data)
    df_unified = normalize_all_sources(cleaned_data)
    df_with_kpis = calculate_kpis(df_unified)
    daily = generate_daily_summary(df_with_kpis)
    anomalies = detect_all_anomalies(daily)

    # Initialize database and save everything
    db = DatabaseManager()
    db.initialize()

    print("\nSaving to database...")
    db.save_raw_data(cleaned_data["google_ads"], "google_ads")
    db.save_raw_data(cleaned_data["meta_ads"], "meta_ads")
    db.save_raw_data(cleaned_data["ga4"], "ga4")
    db.save_unified_data(df_with_kpis)
    db.save_daily_kpis(daily)
    db.save_anomalies(anomalies)

    # Verify
    print("\n" + "=" * 50)
    print("DATABASE STATUS")
    print("=" * 50)
    counts = db.get_table_counts()
    for table, count in counts.items():
        emoji = "✅" if count > 0 else "⬜"
        print(f"  {emoji} {table}: {count:,} rows")

    # Test a query
    print("\n" + "=" * 50)
    print("CHANNEL SUMMARY (from SQL)")
    print("=" * 50)
    summary = db.get_channel_summary()
    for _, row in summary.iterrows():
        roas = f"{row['roas']:.2f}x" if pd.notna(row['roas']) else "N/A"
        print(f"  {row['channel']:15s} | Spend: ${row['cost']:>10,.0f} | Revenue: ${row['revenue']:>12,.0f} | ROAS: {roas}")
        