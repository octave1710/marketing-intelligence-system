"""
KPI Calculator
===============
Calculates all derived marketing KPIs from the unified dataset.

Takes the unified DataFrame (from normalizer.py) and adds calculated columns:
CTR, CPC, CPM, CPA, ROAS, CVR, AOV, efficiency_index

Also provides aggregation functions to summarize KPIs by:
- Day
- Week
- Month
- Channel
- Market
- Campaign

Key rule: Division by zero returns None (never inf, never NaN, never 0).
"""

from typing import Optional, List
from pathlib import Path
import sys

import pandas as pd
import numpy as np

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils.logger import logger


def safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """
    Divide two Series safely — returns None where denominator is 0.
    
    This is critical for marketing KPIs because:
    - A campaign with 0 clicks has undefined CPC (not $0, not infinity)
    - A campaign with 0 cost has undefined ROAS (not 0x, not infinity)
    
    Args:
        numerator: The top number (e.g., clicks)
        denominator: The bottom number (e.g., impressions)
        
    Returns:
        Series with result where denominator > 0, None where denominator = 0
    """
    result = pd.Series(index=numerator.index, dtype=float)
    mask = denominator > 0
    result[mask] = numerator[mask] / denominator[mask]
    result[~mask] = None
    return result


def calculate_kpis(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add KPI columns to the unified DataFrame.
    
    Input columns needed: impressions, clicks, cost, conversions, revenue
    
    Output columns added: ctr, cpc, cpm, cpa, roas, cvr, aov
    
    Args:
        df: Unified DataFrame from normalizer
        
    Returns:
        Same DataFrame with 7 new KPI columns added
    """
    logger.info(f"Calculating KPIs on {len(df):,} rows...")

    df = df.copy()

    # CTR = clicks / impressions (what % of people who see the ad click it)
    df["ctr"] = safe_divide(df["clicks"], df["impressions"])

    # CPC = cost / clicks (how much each click costs)
    df["cpc"] = safe_divide(df["cost"], df["clicks"])

    # CPM = (cost / impressions) * 1000 (cost per thousand impressions)
    df["cpm"] = safe_divide(df["cost"], df["impressions"]) * 1000

    # CPA = cost / conversions (how much each conversion costs)
    df["cpa"] = safe_divide(df["cost"], df["conversions"])

    # ROAS = revenue / cost (how much revenue per dollar spent)
    df["roas"] = safe_divide(df["revenue"], df["cost"])

    # CVR = conversions / clicks (what % of clickers convert)
    df["cvr"] = safe_divide(df["conversions"], df["clicks"])

    # AOV = revenue / conversions (average order value)
    df["aov"] = safe_divide(df["revenue"], df["conversions"])

    # Count how many KPI values are None (due to division by zero)
    null_counts = df[["ctr", "cpc", "cpm", "cpa", "roas", "cvr", "aov"]].isnull().sum()
    total_nulls = null_counts.sum()

    logger.info(f"  ✅ 7 KPIs calculated | {total_nulls} null values (division by zero)")

    return df


def aggregate_kpis(
    df: pd.DataFrame,
    group_by: List[str],
    period_name: str = "",
) -> pd.DataFrame:
    """
    Aggregate raw metrics and recalculate KPIs at a higher level.
    
    IMPORTANT: You can't average KPIs directly!
    Wrong: average of daily ROAS values
    Right: sum(revenue) / sum(cost) over the period
    
    This is a common mistake. If Day 1 has ROAS 10x on $10 spend and Day 2
    has ROAS 2x on $1000 spend, the average ROAS is NOT 6x. It's:
    (10*10 + 2*1000) / (10 + 1000) = 2100/1010 = 2.08x
    
    Args:
        df: DataFrame with raw metrics (impressions, clicks, cost, conversions, revenue)
        group_by: Columns to group by (e.g., ["channel"], ["market"], ["date", "channel"])
        period_name: Optional label for logging
        
    Returns:
        Aggregated DataFrame with recalculated KPIs
    """
    label = period_name or ", ".join(group_by)
    logger.info(f"Aggregating KPIs by [{label}]...")

    # Sum the raw metrics (the only valid way to aggregate)
    agg_dict = {
        "impressions": "sum",
        "clicks": "sum",
        "cost": "sum",
        "conversions": "sum",
        "revenue": "sum",
    }

    # Only aggregate columns that exist in the DataFrame
    agg_dict = {k: v for k, v in agg_dict.items() if k in df.columns}

    df_agg = df.groupby(group_by, as_index=False).agg(agg_dict)

    # Recalculate KPIs from aggregated raw metrics
    df_agg["ctr"] = safe_divide(df_agg["clicks"], df_agg["impressions"])
    df_agg["cpc"] = safe_divide(df_agg["cost"], df_agg["clicks"])
    df_agg["cpm"] = safe_divide(df_agg["cost"], df_agg["impressions"]) * 1000
    df_agg["cpa"] = safe_divide(df_agg["cost"], df_agg["conversions"])
    df_agg["roas"] = safe_divide(df_agg["revenue"], df_agg["cost"])
    df_agg["cvr"] = safe_divide(df_agg["conversions"], df_agg["clicks"])
    df_agg["aov"] = safe_divide(df_agg["revenue"], df_agg["conversions"])

    logger.info(f"  ✅ Aggregated: {len(df_agg):,} rows by [{label}]")

    return df_agg


def calculate_spend_and_revenue_shares(
    df_agg: pd.DataFrame,
    group_col: str = "channel",
) -> pd.DataFrame:
    """
    Calculate spend share, revenue share, and efficiency index per group.
    
    spend_share = channel cost / total cost
    revenue_share = channel revenue / total revenue
    efficiency_index = revenue_share / spend_share
        > 1 means the channel generates more revenue than its budget share
        < 1 means the channel is less efficient than average
    
    Args:
        df_agg: Aggregated DataFrame (one row per channel)
        group_col: Column to calculate shares for
        
    Returns:
        DataFrame with spend_share, revenue_share, efficiency_index added
    """
    df_agg = df_agg.copy()

    total_cost = df_agg["cost"].sum()
    total_revenue = df_agg["revenue"].sum()

    df_agg["spend_share"] = safe_divide(df_agg["cost"], pd.Series([total_cost] * len(df_agg)))
    df_agg["revenue_share"] = safe_divide(df_agg["revenue"], pd.Series([total_revenue] * len(df_agg)))
    df_agg["efficiency_index"] = safe_divide(df_agg["revenue_share"], df_agg["spend_share"])

    logger.info(f"  ✅ Shares and efficiency index calculated by {group_col}")

    return df_agg


def calculate_period_over_period(
    df: pd.DataFrame,
    date_col: str = "date",
    metric_cols: Optional[List[str]] = None,
    period: str = "week",
) -> pd.DataFrame:
    """
    Calculate week-over-week (WoW) or month-over-month (MoM) changes.
    
    Args:
        df: DataFrame with a date column and metric columns
        date_col: Name of the date column
        metric_cols: Which metrics to calculate changes for
        period: "week" for WoW, "month" for MoM
        
    Returns:
        DataFrame with _change columns added (e.g., cost_change, revenue_change)
    """
    if metric_cols is None:
        metric_cols = ["impressions", "clicks", "cost", "conversions", "revenue"]

    df = df.copy()
    df = df.sort_values(date_col)

    if period == "week":
        df["period_key"] = df[date_col].dt.isocalendar().week.astype(int)
        shift_by = 1
    elif period == "month":
        df["period_key"] = df[date_col].dt.month
        shift_by = 1
    else:
        raise ValueError(f"Unknown period: {period}. Use 'week' or 'month'.")

    # For each metric, calculate the % change vs previous period
    for col in metric_cols:
        if col in df.columns:
            col_change = f"{col}_change"
            prev = df[col].shift(shift_by)
            df[col_change] = safe_divide(df[col] - prev, prev)

    logger.info(f"  ✅ {period}-over-{period} changes calculated for {len(metric_cols)} metrics")

    return df


def generate_daily_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create a daily summary with KPIs aggregated by date + channel.
    This is the main table that feeds the dashboard.
    
    Args:
        df: Unified DataFrame with KPIs calculated
        
    Returns:
        Daily summary DataFrame: one row per date per channel
    """
    logger.info("Generating daily summary...")

    daily = aggregate_kpis(df, group_by=["date", "channel"], period_name="daily by channel")

    # Also add a "total" row per day (all channels combined)
    daily_total = aggregate_kpis(df, group_by=["date"], period_name="daily total")
    daily_total["channel"] = "total"

    daily = pd.concat([daily, daily_total], ignore_index=True)
    daily = daily.sort_values(["date", "channel"]).reset_index(drop=True)

    logger.info(f"  ✅ Daily summary: {len(daily):,} rows")

    return daily


if __name__ == "__main__":
    from src.data_ingestion.csv_loader import load_all_sources
    from src.data_transformation.cleaner import clean_all_sources
    from src.data_transformation.normalizer import normalize_all_sources

    # Full chain: load -> clean -> normalize -> calculate KPIs
    raw_data = load_all_sources()
    cleaned_data, _ = clean_all_sources(raw_data)
    df_unified = normalize_all_sources(cleaned_data)
    df_with_kpis = calculate_kpis(df_unified)

    # Show KPIs by channel
    print("\n" + "=" * 60)
    print("KPIs BY CHANNEL")
    print("=" * 60)
    by_channel = aggregate_kpis(df_with_kpis, group_by=["channel"])
    by_channel = calculate_spend_and_revenue_shares(by_channel)

    for _, row in by_channel.iterrows():
        print(f"\n  {row['channel'].upper()}")
        print(f"    Spend: ${row['cost']:,.0f} ({row['spend_share']:.1%} of total)" if row['spend_share'] is not None else f"    Spend: ${row['cost']:,.0f}")
        print(f"    Revenue: ${row['revenue']:,.0f} ({row['revenue_share']:.1%} of total)" if row['revenue_share'] is not None else f"    Revenue: ${row['revenue']:,.0f}")
        if row['roas'] is not None:
            print(f"    ROAS: {row['roas']:.2f}x")
        if row['cpa'] is not None:
            print(f"    CPA: ${row['cpa']:.2f}")
        if row['cvr'] is not None:
            print(f"    CVR: {row['cvr']:.2%}")
        if row.get('efficiency_index') is not None:
            print(f"    Efficiency Index: {row['efficiency_index']:.2f}")

    # Show daily summary sample
    print("\n" + "=" * 60)
    print("DAILY SUMMARY (first 5 rows)")
    print("=" * 60)
    daily = generate_daily_summary(df_with_kpis)
    print(daily.head(5).to_string())
    