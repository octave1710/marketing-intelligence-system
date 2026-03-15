"""
Anomaly Detector
=================
Detects unusual patterns in marketing KPIs using 3 statistical methods:

1. Z-Score: How many standard deviations away from the rolling average?
   |z| > 2.5 = anomaly

2. Percentage Change: Did the metric change more than 30% day-over-day?
   (ignores low-volume rows to avoid false positives)

3. IQR (Interquartile Range): Is the value outside the "normal" range?
   Below Q1 - 1.5*IQR or above Q3 + 1.5*IQR = outlier

Each detected anomaly gets:
- A severity level: low, medium, high, critical
- A direction: up or down
- An auto-generated description
"""

from typing import List, Dict, Optional
from pathlib import Path
import sys

import pandas as pd
import numpy as np

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config.settings import (
    ZSCORE_THRESHOLD,
    PCT_CHANGE_THRESHOLD,
    IQR_MULTIPLIER,
    MIN_IMPRESSIONS_FILTER,
)
from src.utils.logger import logger


def classify_severity(deviation_pct: float) -> str:
    """
    Classify how severe an anomaly is based on how far it deviates.
    
    Args:
        deviation_pct: Absolute percentage deviation (e.g., 0.45 = 45%)
        
    Returns:
        "low", "medium", "high", or "critical"
    """
    abs_dev = abs(deviation_pct)
    if abs_dev >= 2.0:
        return "critical"
    elif abs_dev >= 1.0:
        return "high"
    elif abs_dev >= 0.5:
        return "medium"
    else:
        return "low"


def detect_zscore_anomalies(
    df: pd.DataFrame,
    kpi_cols: List[str],
    window: int = 7,
    threshold: float = ZSCORE_THRESHOLD,
) -> pd.DataFrame:
    """
    Detect anomalies using rolling z-score method.
    
    For each KPI, we calculate:
    - Rolling mean over the last 'window' days
    - Rolling standard deviation over the last 'window' days
    - Z-score = (value - rolling_mean) / rolling_std
    
    If |z-score| > threshold, it's an anomaly.
    
    Args:
        df: DataFrame with date, channel, and KPI columns
        kpi_cols: Which KPI columns to check
        window: Rolling window size in days
        threshold: Z-score threshold for flagging
        
    Returns:
        DataFrame of detected anomalies
    """
    anomalies = []

    # Process each channel separately (Google Ads anomalies shouldn't be
    # compared against Meta Ads baseline)
    for channel in df["channel"].unique():
        df_channel = df[df["channel"] == channel].sort_values("date").copy()

        # Skip channels with too few data points
        if len(df_channel) < window + 1:
            continue

        for kpi in kpi_cols:
            if kpi not in df_channel.columns:
                continue

            series = df_channel[kpi].astype(float)

            # Skip if all values are the same or all null
            if series.nunique() <= 1 or series.isnull().all():
                continue

            rolling_mean = series.rolling(window=window, min_periods=3).mean()
            rolling_std = series.rolling(window=window, min_periods=3).std()

            # Calculate z-score
            zscore = (series - rolling_mean) / rolling_std

            # Find anomalies
            mask = zscore.abs() > threshold
            mask = mask & series.notna() & rolling_mean.notna()

            for idx in df_channel[mask].index:
                row = df_channel.loc[idx]
                z = zscore.loc[idx]
                val = series.loc[idx]
                expected = rolling_mean.loc[idx]

                if expected == 0 or pd.isna(expected):
                    continue

                deviation = (val - expected) / expected

                anomalies.append({
                    "date": row["date"],
                    "channel": channel,
                    "campaign_id": row.get("campaign_id", ""),
                    "market": row.get("market", ""),
                    "kpi": kpi,
                    "value": round(val, 4),
                    "expected_value": round(expected, 4),
                    "deviation_pct": round(deviation, 4),
                    "detection_method": "zscore",
                    "severity": classify_severity(deviation),
                    "direction": "up" if z > 0 else "down",
                    "description": (
                        f"{kpi.upper()} for {channel} was {val:.2f} "
                        f"(expected ~{expected:.2f}, {deviation:+.1%} deviation)"
                    ),
                })

    return pd.DataFrame(anomalies)


def detect_pct_change_anomalies(
    df: pd.DataFrame,
    kpi_cols: List[str],
    threshold: float = PCT_CHANGE_THRESHOLD,
    min_impressions: int = MIN_IMPRESSIONS_FILTER,
) -> pd.DataFrame:
    """
    Detect anomalies using day-over-day percentage change.
    
    If a KPI changes more than ±30% from one day to the next, flag it.
    Ignore low-volume days (< 100 impressions) to avoid false alarms.
    
    Args:
        df: DataFrame with date, channel, and KPI columns
        kpi_cols: Which KPI columns to check
        threshold: Minimum % change to flag
        min_impressions: Minimum impressions to consider
        
    Returns:
        DataFrame of detected anomalies
    """
    anomalies = []

    for channel in df["channel"].unique():
        df_channel = df[df["channel"] == channel].sort_values("date").copy()

        # Filter out low-volume days
        if "impressions" in df_channel.columns:
            df_channel = df_channel[df_channel["impressions"] >= min_impressions]

        if len(df_channel) < 2:
            continue

        for kpi in kpi_cols:
            if kpi not in df_channel.columns:
                continue

            series = df_channel[kpi].astype(float)
            pct_change = series.pct_change()

            mask = pct_change.abs() > threshold
            mask = mask & series.notna() & (series.shift(1).notna())

            for idx in df_channel[mask].index:
                row = df_channel.loc[idx]
                change = pct_change.loc[idx]
                val = series.loc[idx]
                prev_val = series.shift(1).loc[idx]

                if pd.isna(change) or pd.isna(prev_val) or prev_val == 0:
                    continue

                anomalies.append({
                    "date": row["date"],
                    "channel": channel,
                    "campaign_id": row.get("campaign_id", ""),
                    "market": row.get("market", ""),
                    "kpi": kpi,
                    "value": round(val, 4),
                    "expected_value": round(prev_val, 4),
                    "deviation_pct": round(change, 4),
                    "detection_method": "pct_change",
                    "severity": classify_severity(change),
                    "direction": "up" if change > 0 else "down",
                    "description": (
                        f"{kpi.upper()} for {channel} changed {change:+.1%} "
                        f"day-over-day ({prev_val:.2f} → {val:.2f})"
                    ),
                })

    return pd.DataFrame(anomalies)


def detect_iqr_anomalies(
    df: pd.DataFrame,
    kpi_cols: List[str],
    window: int = 30,
    multiplier: float = IQR_MULTIPLIER,
) -> pd.DataFrame:
    """
    Detect anomalies using Interquartile Range method.
    
    Q1 = 25th percentile, Q3 = 75th percentile
    IQR = Q3 - Q1
    Outlier if value < Q1 - 1.5*IQR or value > Q3 + 1.5*IQR
    
    Args:
        df: DataFrame with date, channel, and KPI columns
        kpi_cols: Which KPI columns to check
        window: Rolling window for calculating IQR
        multiplier: IQR multiplier (default 1.5)
        
    Returns:
        DataFrame of detected anomalies
    """
    anomalies = []

    for channel in df["channel"].unique():
        df_channel = df[df["channel"] == channel].sort_values("date").copy()

        if len(df_channel) < window:
            continue

        for kpi in kpi_cols:
            if kpi not in df_channel.columns:
                continue

            series = df_channel[kpi].astype(float)

            q1 = series.rolling(window=window, min_periods=10).quantile(0.25)
            q3 = series.rolling(window=window, min_periods=10).quantile(0.75)
            iqr = q3 - q1

            lower = q1 - multiplier * iqr
            upper = q3 + multiplier * iqr

            mask = (series < lower) | (series > upper)
            mask = mask & series.notna() & q1.notna()

            for idx in df_channel[mask].index:
                row = df_channel.loc[idx]
                val = series.loc[idx]
                median = (q1.loc[idx] + q3.loc[idx]) / 2

                if median == 0 or pd.isna(median):
                    continue

                deviation = (val - median) / median

                anomalies.append({
                    "date": row["date"],
                    "channel": channel,
                    "campaign_id": row.get("campaign_id", ""),
                    "market": row.get("market", ""),
                    "kpi": kpi,
                    "value": round(val, 4),
                    "expected_value": round(median, 4),
                    "deviation_pct": round(deviation, 4),
                    "detection_method": "iqr",
                    "severity": classify_severity(deviation),
                    "direction": "up" if val > median else "down",
                    "description": (
                        f"{kpi.upper()} for {channel} is {val:.2f} "
                        f"(outside IQR range, {deviation:+.1%} from median)"
                    ),
                })

    return pd.DataFrame(anomalies)


def detect_all_anomalies(
    df: pd.DataFrame,
    kpi_cols: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Run all 3 detection methods and combine results.
    
    Args:
        df: DataFrame with daily KPI data (from generate_daily_summary)
        kpi_cols: Which KPIs to check. Default: main paid media KPIs.
        
    Returns:
        Combined DataFrame of all anomalies, deduplicated and sorted.
    """
    if kpi_cols is None:
        kpi_cols = ["cpc", "cpa", "roas", "cvr", "ctr", "cpm"]

    logger.info("=" * 50)
    logger.info("DETECTING ANOMALIES")
    logger.info(f"  Methods: z-score, pct_change, IQR")
    logger.info(f"  KPIs monitored: {kpi_cols}")
    logger.info("=" * 50)

    # Run each method
    df_zscore = detect_zscore_anomalies(df, kpi_cols)
    logger.info(f"  Z-score: {len(df_zscore)} anomalies detected")

    df_pct = detect_pct_change_anomalies(df, kpi_cols)
    logger.info(f"  Pct change: {len(df_pct)} anomalies detected")

    df_iqr = detect_iqr_anomalies(df, kpi_cols)
    logger.info(f"  IQR: {len(df_iqr)} anomalies detected")

    # Combine all
    all_anomalies = pd.concat([df_zscore, df_pct, df_iqr], ignore_index=True)

    if len(all_anomalies) == 0:
        logger.info("  No anomalies detected.")
        return pd.DataFrame()

    # Sort by severity then date
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    all_anomalies["severity_rank"] = all_anomalies["severity"].map(severity_order)
    all_anomalies = all_anomalies.sort_values(
        ["severity_rank", "date"]
    ).drop(columns=["severity_rank"]).reset_index(drop=True)

    # Summary
    logger.info(f"\n📊 Total anomalies: {len(all_anomalies)}")
    severity_counts = all_anomalies["severity"].value_counts()
    for sev in ["critical", "high", "medium", "low"]:
        count = severity_counts.get(sev, 0)
        if count > 0:
            emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪"}.get(sev, "")
            logger.info(f"  {emoji} {sev}: {count}")
    logger.info("=" * 50)

    return all_anomalies


if __name__ == "__main__":
    from src.data_ingestion.csv_loader import load_all_sources
    from src.data_transformation.cleaner import clean_all_sources
    from src.data_transformation.normalizer import normalize_all_sources
    from src.data_transformation.kpi_calculator import calculate_kpis, generate_daily_summary

    # Full chain
    raw_data = load_all_sources()
    cleaned_data, _ = clean_all_sources(raw_data)
    df_unified = normalize_all_sources(cleaned_data)
    df_with_kpis = calculate_kpis(df_unified)
    daily = generate_daily_summary(df_with_kpis)

    # Detect anomalies
    anomalies = detect_all_anomalies(daily)

    if len(anomalies) > 0:
        print("\n" + "=" * 60)
        print("TOP 10 ANOMALIES (by severity)")
        print("=" * 60)
        for i, (_, row) in enumerate(anomalies.head(10).iterrows()):
            emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪"}.get(row["severity"], "")
            print(f"\n{emoji} #{i+1} [{row['severity'].upper()}] {row['date'].strftime('%Y-%m-%d')}")
            print(f"   {row['description']}")
            print(f"   Method: {row['detection_method']} | Direction: {row['direction']}")
    else:
        print("No anomalies detected.")
        