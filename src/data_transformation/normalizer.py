"""
Data Normalizer
================
Takes cleaned DataFrames from 3 different sources (Google Ads, Meta Ads, GA4)
and transforms them into ONE unified schema.

Why? Each platform uses different column names for similar concepts:
- Google Ads calls revenue "conversion_value", Meta calls it "purchase_value", GA4 calls it "total_revenue"
- Google Ads calls conversions "conversions", Meta calls them "purchases"
- Google Ads has "clicks", Meta has "link_clicks" (outbound clicks only)

This module maps everything to a single schema so we can compare channels side by side.

Unified schema:
    date, channel, channel_detail, campaign_id, campaign_name,
    market, device, impressions, clicks, cost, conversions, revenue
"""

from typing import Dict
from pathlib import Path
import sys

import pandas as pd

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils.logger import logger


def normalize_google_ads(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform Google Ads data to unified schema.
    
    Mapping:
        campaign_type -> channel_detail
        clicks -> clicks (direct)
        cost -> cost (direct)
        conversions -> conversions (direct)
        conversion_value -> revenue
    """
    logger.info(f"Normalizing Google Ads ({len(df):,} rows)...")

    normalized = pd.DataFrame({
        "date": df["date"],
        "channel": "google_ads",
        "channel_detail": df["campaign_type"],
        "campaign_id": df["campaign_id"],
        "campaign_name": df["campaign_name"],
        "market": df["market"],
        "device": df["device"],
        "impressions": df["impressions"],
        "clicks": df["clicks"],
        "cost": df["cost"],
        "conversions": df["conversions"],
        "revenue": df["conversion_value"],
    })

    logger.info(f"  ✅ Google Ads normalized: {len(normalized):,} rows")
    return normalized


def normalize_meta_ads(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform Meta Ads data to unified schema.
    
    Mapping:
        objective -> channel_detail
        link_clicks -> clicks (not total clicks, only outbound)
        cost -> cost (direct)
        purchases -> conversions
        purchase_value -> revenue
    """
    logger.info(f"Normalizing Meta Ads ({len(df):,} rows)...")

    normalized = pd.DataFrame({
        "date": df["date"],
        "channel": "meta_ads",
        "channel_detail": df["objective"],
        "campaign_id": df["campaign_id"],
        "campaign_name": df["campaign_name"],
        "market": df["market"],
        "device": df["device"],
        "impressions": df["impressions"],
        "clicks": df["link_clicks"],
        "cost": df["cost"],
        "conversions": df["purchases"],
        "revenue": df["purchase_value"],
    })

    logger.info(f"  ✅ Meta Ads normalized: {len(normalized):,} rows")
    return normalized


def normalize_ga4(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform GA4 data to unified schema.
    
    Mapping:
        medium -> channel_detail
        source + "/" + medium -> campaign_id and campaign_name
        sessions -> impressions (proxy — not the same thing, but best approximation)
        engaged_sessions -> clicks (proxy — engaged visits as "meaningful clicks")
        cost = 0 always (organic/free traffic)
        conversions -> conversions (direct)
        total_revenue -> revenue
        device_category -> device
    """
    logger.info(f"Normalizing GA4 ({len(df):,} rows)...")

    # Determine channel name based on medium
    # "organic" -> "organic", "(none)" -> "direct", "email" -> "email", "referral" -> "referral"
    def get_channel(row):
        medium = str(row["medium"]).lower()
        if medium == "organic":
            return "organic"
        elif medium == "(none)":
            return "direct"
        elif medium == "email":
            return "email"
        elif medium == "referral":
            return "referral"
        else:
            return medium

    normalized = pd.DataFrame({
        "date": df["date"],
        "channel": df.apply(get_channel, axis=1),
        "channel_detail": df["medium"],
        "campaign_id": df["source"] + "/" + df["medium"],
        "campaign_name": df["source"] + " / " + df["medium"],
        "market": df["market"],
        "device": df["device_category"],
        "impressions": df["sessions"],
        "clicks": df["engaged_sessions"],
        "cost": 0.0,
        "conversions": df["conversions"],
        "revenue": df["total_revenue"],
    })

    logger.info(f"  ✅ GA4 normalized: {len(normalized):,} rows")
    return normalized


def normalize_all_sources(
    cleaned_data: Dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """
    Normalize all sources and combine into one unified DataFrame.
    
    Args:
        cleaned_data: Dict with keys "google_ads", "meta_ads", "ga4"
        
    Returns:
        Single DataFrame with unified schema containing all channels.
    """
    logger.info("=" * 50)
    logger.info("NORMALIZING ALL SOURCES TO UNIFIED SCHEMA")
    logger.info("=" * 50)

    frames = []

    if "google_ads" in cleaned_data:
        frames.append(normalize_google_ads(cleaned_data["google_ads"]))

    if "meta_ads" in cleaned_data:
        frames.append(normalize_meta_ads(cleaned_data["meta_ads"]))

    if "ga4" in cleaned_data:
        frames.append(normalize_ga4(cleaned_data["ga4"]))

    # Combine all normalized DataFrames into one
    df_unified = pd.concat(frames, ignore_index=True)

    # Ensure correct types
    df_unified["date"] = pd.to_datetime(df_unified["date"])
    df_unified["cost"] = df_unified["cost"].astype(float)
    df_unified["conversions"] = df_unified["conversions"].astype(float)
    df_unified["revenue"] = df_unified["revenue"].astype(float)
    df_unified["impressions"] = df_unified["impressions"].astype(int)
    df_unified["clicks"] = df_unified["clicks"].astype(int)

    # Sort by date then channel
    df_unified = df_unified.sort_values(["date", "channel", "campaign_id"]).reset_index(drop=True)

    logger.info(f"\n📊 Unified dataset:")
    logger.info(f"  Total rows: {len(df_unified):,}")
    logger.info(f"  Channels: {df_unified['channel'].unique().tolist()}")
    logger.info(f"  Markets: {df_unified['market'].unique().tolist()}")
    logger.info(f"  Date range: {df_unified['date'].min().strftime('%Y-%m-%d')} to {df_unified['date'].max().strftime('%Y-%m-%d')}")
    logger.info(f"  Total spend: ${df_unified['cost'].sum():,.2f}")
    logger.info(f"  Total revenue: ${df_unified['revenue'].sum():,.2f}")
    logger.info("=" * 50)

    return df_unified


if __name__ == "__main__":
    from src.data_ingestion.csv_loader import load_all_sources
    from src.data_transformation.cleaner import clean_all_sources

    # Run the full chain: load -> clean -> normalize
    raw_data = load_all_sources()
    cleaned_data, _ = clean_all_sources(raw_data)
    df_unified = normalize_all_sources(cleaned_data)

    print(f"\nUnified DataFrame shape: {df_unified.shape}")
    print(f"\nChannels present:")
    print(df_unified.groupby("channel")["revenue"].sum().sort_values(ascending=False))
    print(f"\nSample rows:")
    print(df_unified.head(5).to_string())
    