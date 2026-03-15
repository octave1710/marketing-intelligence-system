"""
Data Cleaner
=============
Cleans raw DataFrames: handles missing values, removes duplicates,
standardizes formats, validates data quality.
"""

from typing import Tuple, Dict
from pathlib import Path
import sys

import pandas as pd
import numpy as np

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils.logger import logger


MARKET_MAPPING = {
    "us": "US", "usa": "US", "united states": "US",
    "uk": "UK", "gb": "UK", "united kingdom": "UK",
    "fr": "FR", "france": "FR",
    "de": "DE", "germany": "DE", "deutschland": "DE",
}


def clean_dataframe(df: pd.DataFrame, source_name: str) -> Tuple[pd.DataFrame, Dict]:
    """
    Apply all cleaning steps to a DataFrame.

    Args:
        df: Raw DataFrame to clean.
        source_name: "google_ads", "meta_ads", or "ga4"

    Returns:
        Tuple of (cleaned DataFrame, quality report dict)
    """
    logger.info(f"Cleaning {source_name} data ({len(df):,} rows)...")

    initial_rows = len(df)
    report = {
        "source": source_name,
        "initial_rows": initial_rows,
        "duplicates_removed": 0,
        "nulls_filled": 0,
        "negatives_fixed": 0,
        "final_rows": 0,
    }

    df = df.copy()

    # STEP 1: Remove duplicates
    if source_name == "google_ads":
        dedup_cols = ["date", "campaign_id", "market", "device"]
    elif source_name == "meta_ads":
        dedup_cols = ["date", "campaign_id", "market", "device"]
    elif source_name == "ga4":
        dedup_cols = ["date", "source", "medium", "market", "device_category"]
    else:
        dedup_cols = None

    if dedup_cols:
        before = len(df)
        df = df.drop_duplicates(subset=dedup_cols, keep="first")
        report["duplicates_removed"] = before - len(df)

    # STEP 2: Handle missing values
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    nulls_count = int(df[numeric_cols].isnull().sum().sum())
    df[numeric_cols] = df[numeric_cols].fillna(0)

    string_cols = df.select_dtypes(include=["object"]).columns
    nulls_count += int(df[string_cols].isnull().sum().sum())
    df[string_cols] = df[string_cols].fillna("unknown")

    report["nulls_filled"] = nulls_count

    # STEP 3: Ensure date is datetime
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        invalid_dates = df["date"].isnull().sum()
        if invalid_dates > 0:
            df = df.dropna(subset=["date"])

    # STEP 4: Fix negative values
    metric_cols = [
        "impressions", "clicks", "cost", "conversions", "conversion_value",
        "purchases", "purchase_value", "reach", "link_clicks",
        "sessions", "users", "engaged_sessions", "total_revenue",
        "add_to_cart", "landing_page_views", "events",
    ]
    negatives_fixed = 0
    for col in metric_cols:
        if col in df.columns:
            neg_mask = df[col] < 0
            neg_count = neg_mask.sum()
            if neg_count > 0:
                df.loc[neg_mask, col] = 0
                negatives_fixed += neg_count
    report["negatives_fixed"] = negatives_fixed

    # STEP 5: Standardize market and device names
    if "market" in df.columns:
        df["market"] = df["market"].str.strip().str.lower()
        df["market"] = df["market"].map(MARKET_MAPPING).fillna(df["market"].str.upper())

    device_col = "device" if "device" in df.columns else "device_category"
    if device_col in df.columns:
        df[device_col] = df[device_col].str.strip().str.lower()

    # STEP 6: Cap percentages between 0 and 1
    for col in ["engagement_rate", "bounce_rate", "search_impression_share"]:
        if col in df.columns:
            df[col] = df[col].clip(lower=0, upper=1.0)

    report["final_rows"] = len(df)
    logger.info(f"  ✅ {source_name} cleaned: {initial_rows:,} -> {len(df):,} rows")

    return df, report


def clean_all_sources(data: Dict[str, pd.DataFrame]) -> Tuple[Dict[str, pd.DataFrame], list]:
    """
    Clean all data sources at once.

    Args:
        data: Dict with keys "google_ads", "meta_ads", "ga4"

    Returns:
        Tuple of (cleaned data dict, list of quality reports)
    """
    logger.info("=" * 50)
    logger.info("CLEANING ALL DATA SOURCES")
    logger.info("=" * 50)

    cleaned = {}
    reports = []

    for source_name, df in data.items():
        df_clean, report = clean_dataframe(df, source_name)
        cleaned[source_name] = df_clean
        reports.append(report)

    for r in reports:
        logger.info(
            f"  {r['source']}: {r['initial_rows']:,} -> {r['final_rows']:,} rows | "
            f"dupes: {r['duplicates_removed']} | nulls: {r['nulls_filled']}"
        )
    logger.info("=" * 50)

    return cleaned, reports


if __name__ == "__main__":
    from src.data_ingestion.csv_loader import load_all_sources

    raw_data = load_all_sources()
    cleaned_data, quality_reports = clean_all_sources(raw_data)

    for name, df in cleaned_data.items():
        print(f"\n{name}: {df.shape[0]} rows, {df.shape[1]} columns")
        
        