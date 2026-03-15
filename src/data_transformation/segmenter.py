"""
Data Segmenter
===============
Segments the unified dataset for specific analysis views.

Creates pre-filtered and pre-grouped DataFrames that the dashboard
and AI analyst can use directly.
"""

from typing import Dict
from pathlib import Path
import sys

import pandas as pd
import numpy as np

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils.logger import logger
from src.data_transformation.kpi_calculator import aggregate_kpis, safe_divide


def segment_by_channel(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate KPIs by channel (google_ads, meta_ads, organic, etc.)."""
    return aggregate_kpis(df, group_by=["channel"], period_name="channel")


def segment_by_market(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate KPIs by market (US, UK, FR, DE)."""
    return aggregate_kpis(df, group_by=["market"], period_name="market")


def segment_by_device(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate KPIs by device (desktop, mobile, tablet)."""
    return aggregate_kpis(df, group_by=["device"], period_name="device")


def segment_by_channel_and_market(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate KPIs by channel × market combination."""
    return aggregate_kpis(df, group_by=["channel", "market"], period_name="channel × market")


def segment_by_campaign(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate KPIs by individual campaign."""
    return aggregate_kpis(
        df,
        group_by=["channel", "campaign_id", "campaign_name"],
        period_name="campaign",
    )


def segment_paid_only(df: pd.DataFrame) -> pd.DataFrame:
    """Filter to only paid channels (google_ads, meta_ads)."""
    return df[df["cost"] > 0].copy()


def segment_organic_only(df: pd.DataFrame) -> pd.DataFrame:
    """Filter to only organic/free channels."""
    return df[df["cost"] == 0].copy()


def classify_campaign_performance(df: pd.DataFrame) -> pd.DataFrame:
    """
    Classify campaigns into performance tiers based on ROAS.
    
    - Top performers: ROAS > median + 1 std dev
    - Average: within median ± 1 std dev
    - Underperformers: ROAS < median - 1 std dev
    
    Only applies to paid campaigns (cost > 0).
    """
    campaigns = segment_by_campaign(df)
    paid = campaigns[campaigns["cost"] > 0].copy()

    if len(paid) == 0 or "roas" not in paid.columns:
        paid["performance_tier"] = "unknown"
        return paid

    roas_values = paid["roas"].dropna()
    if len(roas_values) == 0:
        paid["performance_tier"] = "unknown"
        return paid

    median_roas = roas_values.median()
    std_roas = roas_values.std()

    def classify(roas):
        if pd.isna(roas):
            return "unknown"
        elif roas > median_roas + std_roas:
            return "top_performer"
        elif roas < median_roas - std_roas:
            return "underperformer"
        else:
            return "average"

    paid["performance_tier"] = paid["roas"].apply(classify)

    tier_counts = paid["performance_tier"].value_counts()
    logger.info(f"  Campaign performance tiers: {dict(tier_counts)}")

    return paid


def segment_weekday_vs_weekend(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """
    Split data into weekday and weekend for comparison.
    
    Returns:
        Dict with keys "weekday" and "weekend"
    """
    df = df.copy()
    df["is_weekend"] = df["date"].dt.dayofweek >= 5

    weekday = aggregate_kpis(
        df[~df["is_weekend"]],
        group_by=["channel"],
        period_name="weekday",
    )
    weekday["period_type"] = "weekday"

    weekend = aggregate_kpis(
        df[df["is_weekend"]],
        group_by=["channel"],
        period_name="weekend",
    )
    weekend["period_type"] = "weekend"

    return {"weekday": weekday, "weekend": weekend}


def get_top_campaigns(
    df: pd.DataFrame,
    metric: str = "roas",
    n: int = 5,
    ascending: bool = False,
) -> pd.DataFrame:
    """
    Get top N campaigns by a given metric.
    
    Args:
        df: Unified DataFrame
        metric: KPI to rank by
        n: Number of campaigns to return
        ascending: If True, returns bottom N instead
        
    Returns:
        DataFrame with top/bottom N campaigns
    """
    campaigns = segment_by_campaign(df)
    paid = campaigns[campaigns["cost"] > 0].copy()

    if metric not in paid.columns or len(paid) == 0:
        return paid.head(0)

    result = paid.dropna(subset=[metric]).sort_values(metric, ascending=ascending).head(n)

    label = "Bottom" if ascending else "Top"
    logger.info(f"  {label} {n} campaigns by {metric}: {len(result)} results")

    return result


def generate_all_segments(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """
    Generate all segments at once. Returns a dictionary of DataFrames.
    
    Args:
        df: Unified DataFrame with KPIs
        
    Returns:
        Dict with all segment views
    """
    logger.info("=" * 50)
    logger.info("GENERATING ALL SEGMENTS")
    logger.info("=" * 50)

    segments = {
        "by_channel": segment_by_channel(df),
        "by_market": segment_by_market(df),
        "by_device": segment_by_device(df),
        "by_channel_market": segment_by_channel_and_market(df),
        "by_campaign": segment_by_campaign(df),
        "paid_only": segment_paid_only(df),
        "organic_only": segment_organic_only(df),
        "campaign_tiers": classify_campaign_performance(df),
        "top_5_roas": get_top_campaigns(df, metric="roas", n=5),
        "bottom_5_roas": get_top_campaigns(df, metric="roas", n=5, ascending=True),
        "top_5_conversions": get_top_campaigns(df, metric="conversions", n=5),
    }

    logger.info(f"\n📊 Segments generated: {len(segments)}")
    for name, seg_df in segments.items():
        logger.info(f"  {name}: {len(seg_df)} rows")
    logger.info("=" * 50)

    return segments


if __name__ == "__main__":
    from src.data_ingestion.csv_loader import load_all_sources
    from src.data_transformation.cleaner import clean_all_sources
    from src.data_transformation.normalizer import normalize_all_sources
    from src.data_transformation.kpi_calculator import calculate_kpis

    # Full chain
    raw_data = load_all_sources()
    cleaned_data, _ = clean_all_sources(raw_data)
    df_unified = normalize_all_sources(cleaned_data)
    df_with_kpis = calculate_kpis(df_unified)

    # Generate all segments
    segments = generate_all_segments(df_with_kpis)

    # Show campaign tiers
    print("\n" + "=" * 50)
    print("CAMPAIGN PERFORMANCE TIERS")
    print("=" * 50)
    tiers = segments["campaign_tiers"]
    for _, row in tiers.iterrows():
        tier_emoji = {"top_performer": "🟢", "average": "🟡", "underperformer": "🔴"}.get(row["performance_tier"], "⚪")
        roas_str = f"{row['roas']:.2f}x" if pd.notna(row['roas']) else "N/A"
        print(f"  {tier_emoji} {row['campaign_name'][:45]:45s} | ROAS: {roas_str} | Tier: {row['performance_tier']}")
        
        