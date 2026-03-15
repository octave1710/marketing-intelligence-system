"""
CSV Loader
==========
Loads raw marketing CSV files from data/raw/ and returns them as DataFrames.
"""

from pathlib import Path
from typing import Optional, Dict
import sys

import pandas as pd

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config.settings import RAW_DATA_DIR
from src.utils.logger import logger


REQUIRED_COLUMNS = {
    "google_ads": [
        "date", "campaign_id", "campaign_name", "campaign_type",
        "market", "device", "impressions", "clicks", "cost",
        "conversions", "conversion_value",
    ],
    "meta_ads": [
        "date", "campaign_id", "campaign_name", "objective",
        "placement", "market", "device", "impressions", "reach",
        "clicks", "link_clicks", "cost", "purchases", "purchase_value",
        "add_to_cart", "landing_page_views", "frequency",
    ],
    "ga4": [
        "date", "source", "medium", "market", "device_category",
        "sessions", "users", "new_users", "engaged_sessions",
        "engagement_rate", "avg_session_duration", "events",
        "conversions", "total_revenue", "bounce_rate",
    ],
}


def load_csv(source_name: str, filename: Optional[str] = None) -> pd.DataFrame:
    """
    Load a single CSV file and validate it.

    Args:
        source_name: One of "google_ads", "meta_ads", "ga4"
        filename: Optional custom filename.

    Returns:
        Validated pandas DataFrame with date column as datetime.
    """
    if filename is None:
        filename = f"sample_{source_name}.csv"
    filepath = RAW_DATA_DIR / filename

    if not filepath.exists():
        raise FileNotFoundError(f"Data file not found: {filepath}")

    logger.info(f"Loading {source_name} data from {filepath.name}...")

    df = pd.read_csv(filepath)

    if source_name in REQUIRED_COLUMNS:
        required = REQUIRED_COLUMNS[source_name]
        missing = [col for col in required if col not in df.columns]
        if missing:
            raise ValueError(f"{source_name}: Missing required columns: {missing}")

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])

    logger.info(
        f"  ✅ {source_name}: {len(df):,} rows | "
        f"{df['date'].min().strftime('%Y-%m-%d')} to "
        f"{df['date'].max().strftime('%Y-%m-%d')}"
    )

    return df


def load_all_sources() -> Dict[str, pd.DataFrame]:
    """
    Load all 3 data sources at once.

    Returns:
        Dictionary with keys "google_ads", "meta_ads", "ga4"
    """
    logger.info("=" * 50)
    logger.info("LOADING ALL DATA SOURCES")
    logger.info("=" * 50)

    sources = {}
    for source_name in ["google_ads", "meta_ads", "ga4"]:
        try:
            sources[source_name] = load_csv(source_name)
        except (FileNotFoundError, ValueError) as e:
            logger.error(f"Failed to load {source_name}: {e}")
            raise

    total_rows = sum(len(df) for df in sources.values())
    logger.info(f"Total rows loaded: {total_rows:,}")
    logger.info("=" * 50)

    return sources


if __name__ == "__main__":
    data = load_all_sources()
    for name, df in data.items():
        print(f"\n{name}: {df.shape[0]} rows, {df.shape[1]} columns")
        print(f"Columns: {list(df.columns)}")
        