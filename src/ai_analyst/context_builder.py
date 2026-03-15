"""
Context Builder
================
Prepares a structured "briefing pack" of data for the LLM.

The LLM can't access our database directly. This module reads the data,
calculates summaries, and formats everything as a text briefing that
gets injected into the prompt.

Think of it as writing a memo for a senior analyst before a meeting:
"Here are the numbers, here's what changed, here are the anomalies."
"""

from typing import Dict, Optional
from pathlib import Path
from datetime import datetime, timedelta
import sys

import pandas as pd
import numpy as np

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config.settings import TARGET_ROAS, TARGET_CPA
from src.utils.logger import logger
from src.data_transformation.kpi_calculator import safe_divide


def build_context(
    df_unified: pd.DataFrame,
    df_daily: pd.DataFrame,
    df_anomalies: pd.DataFrame,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
) -> Dict:
    """
    Build the complete context dictionary for the LLM.
    
    Args:
        df_unified: Unified data with KPIs (from transformed_unified)
        df_daily: Daily KPI summary (from kpi_daily)
        df_anomalies: Detected anomalies
        period_start: Start of analysis period (YYYY-MM-DD)
        period_end: End of analysis period (YYYY-MM-DD)
        
    Returns:
        Dictionary with all context sections
    """
    logger.info("Building context for AI analysis...")

    # Default to last 30 days if no period specified
    if period_end is None:
        period_end = df_unified["date"].max().strftime("%Y-%m-%d")
    if period_start is None:
        end_dt = pd.to_datetime(period_end)
        period_start = (end_dt - timedelta(days=29)).strftime("%Y-%m-%d")

    # Filter data to the analysis period
    mask = (df_unified["date"] >= period_start) & (df_unified["date"] <= period_end)
    df_period = df_unified[mask].copy()

    # Previous period for comparison (same length, immediately before)
    period_days = (pd.to_datetime(period_end) - pd.to_datetime(period_start)).days + 1
    prev_end = (pd.to_datetime(period_start) - timedelta(days=1)).strftime("%Y-%m-%d")
    prev_start = (pd.to_datetime(prev_end) - timedelta(days=period_days - 1)).strftime("%Y-%m-%d")

    mask_prev = (df_unified["date"] >= prev_start) & (df_unified["date"] <= prev_end)
    df_prev = df_unified[mask_prev].copy()

    context = {
        "metadata": _build_metadata(period_start, period_end, prev_start, prev_end),
        "performance_summary": _build_performance_summary(df_period, df_prev),
        "channel_performance": _build_channel_performance(df_period, df_prev),
        "notable_changes": _build_notable_changes(df_period, df_prev),
        "anomalies": _build_anomalies_section(df_anomalies, period_start, period_end),
        "budget_allocation": _build_budget_allocation(df_period),
        "top_campaigns": _build_top_campaigns(df_period),
        "business_context": _build_business_context(),
    }

    logger.info(f"  ✅ Context built for period {period_start} to {period_end}")
    return context


def _build_metadata(
    period_start: str,
    period_end: str,
    prev_start: str,
    prev_end: str,
) -> Dict:
    """Basic metadata about the analysis period."""
    return {
        "period": {"start": period_start, "end": period_end},
        "comparison_period": {"start": prev_start, "end": prev_end},
        "generated_at": datetime.now().isoformat(),
    }


def _build_performance_summary(
    df_current: pd.DataFrame,
    df_previous: pd.DataFrame,
) -> Dict:
    """Calculate top-level KPIs for current and previous period."""
    def calc_totals(df):
        if len(df) == 0:
            return {k: 0 for k in ["spend", "revenue", "impressions", "clicks", "conversions"]}
        return {
            "spend": float(df["cost"].sum()),
            "revenue": float(df["revenue"].sum()),
            "impressions": int(df["impressions"].sum()),
            "clicks": int(df["clicks"].sum()),
            "conversions": float(df["conversions"].sum()),
        }

    current = calc_totals(df_current)
    previous = calc_totals(df_previous)

    # Calculate derived KPIs
    def calc_kpis(totals):
        kpis = totals.copy()
        kpis["roas"] = round(totals["revenue"] / totals["spend"], 2) if totals["spend"] > 0 else None
        kpis["cpa"] = round(totals["spend"] / totals["conversions"], 2) if totals["conversions"] > 0 else None
        kpis["cvr"] = round(totals["conversions"] / totals["clicks"], 4) if totals["clicks"] > 0 else None
        kpis["cpc"] = round(totals["spend"] / totals["clicks"], 2) if totals["clicks"] > 0 else None
        kpis["aov"] = round(totals["revenue"] / totals["conversions"], 2) if totals["conversions"] > 0 else None
        return kpis

    current_kpis = calc_kpis(current)
    previous_kpis = calc_kpis(previous)

    # Calculate period-over-period changes
    changes = {}
    for key in current_kpis:
        curr_val = current_kpis[key]
        prev_val = previous_kpis.get(key)
        if curr_val is not None and prev_val is not None and prev_val != 0:
            changes[f"{key}_change"] = round((curr_val - prev_val) / prev_val, 4)
        else:
            changes[f"{key}_change"] = None

    return {
        "current": current_kpis,
        "previous": previous_kpis,
        "changes": changes,
    }


def _build_channel_performance(
    df_current: pd.DataFrame,
    df_previous: pd.DataFrame,
) -> list:
    """Calculate KPIs by channel with period-over-period comparison."""
    channels = []

    for channel in sorted(df_current["channel"].unique()):
        curr = df_current[df_current["channel"] == channel]
        prev = df_previous[df_previous["channel"] == channel]

        spend = float(curr["cost"].sum())
        revenue = float(curr["revenue"].sum())
        clicks = int(curr["clicks"].sum())
        conversions = float(curr["conversions"].sum())
        impressions = int(curr["impressions"].sum())

        prev_spend = float(prev["cost"].sum()) if len(prev) > 0 else 0
        prev_revenue = float(prev["revenue"].sum()) if len(prev) > 0 else 0

        channel_data = {
            "channel": channel,
            "spend": spend,
            "revenue": revenue,
            "impressions": impressions,
            "clicks": clicks,
            "conversions": conversions,
            "roas": round(revenue / spend, 2) if spend > 0 else None,
            "cpa": round(spend / conversions, 2) if conversions > 0 else None,
            "cvr": round(conversions / clicks, 4) if clicks > 0 else None,
            "spend_change": round((spend - prev_spend) / prev_spend, 4) if prev_spend > 0 else None,
            "revenue_change": round((revenue - prev_revenue) / prev_revenue, 4) if prev_revenue > 0 else None,
        }
        channels.append(channel_data)

    return channels


def _build_notable_changes(
    df_current: pd.DataFrame,
    df_previous: pd.DataFrame,
) -> Dict:
    """Identify the biggest improvements and deteriorations."""
    metrics = {
        "spend": ("cost", "sum"),
        "revenue": ("revenue", "sum"),
        "conversions": ("conversions", "sum"),
    }

    improvements = []
    deteriorations = []

    for channel in df_current["channel"].unique():
        curr = df_current[df_current["channel"] == channel]
        prev = df_previous[df_previous["channel"] == channel]

        for metric_name, (col, agg) in metrics.items():
            curr_val = float(curr[col].sum())
            prev_val = float(prev[col].sum()) if len(prev) > 0 else 0

            if prev_val > 0:
                change = (curr_val - prev_val) / prev_val
                entry = {
                    "channel": channel,
                    "metric": metric_name,
                    "current_value": curr_val,
                    "previous_value": prev_val,
                    "change_pct": round(change, 4),
                }
                if change > 0.05:
                    improvements.append(entry)
                elif change < -0.05:
                    deteriorations.append(entry)

    # Sort by magnitude of change
    improvements.sort(key=lambda x: x["change_pct"], reverse=True)
    deteriorations.sort(key=lambda x: x["change_pct"])

    return {
        "improvements": improvements[:5],
        "deteriorations": deteriorations[:5],
    }


def _build_anomalies_section(
    df_anomalies: pd.DataFrame,
    period_start: str,
    period_end: str,
) -> list:
    """Format anomalies for the LLM context."""
    if len(df_anomalies) == 0:
        return []

    # Filter to the analysis period
    if "date" in df_anomalies.columns:
        df_anomalies["date"] = pd.to_datetime(df_anomalies["date"])
        mask = (df_anomalies["date"] >= period_start) & (df_anomalies["date"] <= period_end)
        df_period = df_anomalies[mask]
    else:
        df_period = df_anomalies

    # Take only medium+ severity
    df_notable = df_period[df_period["severity"].isin(["medium", "high", "critical"])]

    anomalies_list = []
    for _, row in df_notable.head(10).iterrows():
        anomalies_list.append({
            "date": str(row.get("date", "")),
            "channel": row.get("channel", ""),
            "kpi": row.get("kpi", ""),
            "severity": row.get("severity", ""),
            "direction": row.get("direction", ""),
            "description": row.get("description", ""),
            "value": row.get("value", 0),
            "expected_value": row.get("expected_value", 0),
        })

    return anomalies_list


def _build_budget_allocation(df_current: pd.DataFrame) -> Dict:
    """Calculate current budget allocation and efficiency."""
    paid = df_current[df_current["cost"] > 0]

    if len(paid) == 0:
        return {"channels": [], "total_spend": 0}

    total_spend = float(paid["cost"].sum())
    total_revenue = float(paid["revenue"].sum())

    allocations = []
    for channel in paid["channel"].unique():
        ch_data = paid[paid["channel"] == channel]
        ch_spend = float(ch_data["cost"].sum())
        ch_revenue = float(ch_data["revenue"].sum())

        spend_share = ch_spend / total_spend if total_spend > 0 else 0
        revenue_share = ch_revenue / total_revenue if total_revenue > 0 else 0
        efficiency = revenue_share / spend_share if spend_share > 0 else 0

        allocations.append({
            "channel": channel,
            "spend": ch_spend,
            "spend_share": round(spend_share, 4),
            "revenue": ch_revenue,
            "revenue_share": round(revenue_share, 4),
            "efficiency_index": round(efficiency, 2),
            "assessment": "over-performing" if efficiency > 1.1 else "under-performing" if efficiency < 0.9 else "balanced",
        })

    return {
        "channels": allocations,
        "total_spend": total_spend,
        "total_revenue": total_revenue,
    }


def _build_top_campaigns(df_current: pd.DataFrame, n: int = 5) -> Dict:
    """Identify top and bottom performing campaigns."""
    paid = df_current[df_current["cost"] > 0]

    if len(paid) == 0:
        return {"top": [], "bottom": []}

    campaigns = paid.groupby(["channel", "campaign_name"]).agg({
        "cost": "sum",
        "revenue": "sum",
        "conversions": "sum",
        "clicks": "sum",
    }).reset_index()

    campaigns["roas"] = campaigns.apply(
        lambda r: round(r["revenue"] / r["cost"], 2) if r["cost"] > 0 else None, axis=1
    )
    campaigns["cpa"] = campaigns.apply(
        lambda r: round(r["cost"] / r["conversions"], 2) if r["conversions"] > 0 else None, axis=1
    )

    campaigns_valid = campaigns.dropna(subset=["roas"])
    top = campaigns_valid.nlargest(n, "roas").to_dict("records")
    bottom = campaigns_valid.nsmallest(n, "roas").to_dict("records")

    return {"top": top, "bottom": bottom}


def _build_business_context() -> Dict:
    """Add business objectives and constraints."""
    return {
        "objectives": [
            f"Achieve ROAS above {TARGET_ROAS}x",
            f"Maintain CPA below ${TARGET_CPA}",
            "Grow revenue while maintaining efficiency",
        ],
        "constraints": [
            "Total monthly budget ~$80K across paid channels",
            "Priority markets: US (primary), UK (secondary)",
        ],
        "notes": [
            "Q3 2024 data — summer period, potential seasonal effects",
        ],
    }


def context_to_text(context: Dict) -> str:
    """
    Convert the context dictionary to a readable text format
    that can be injected into an LLM prompt.
    """
    lines = []

    # Header
    meta = context["metadata"]
    lines.append(f"ANALYSIS PERIOD: {meta['period']['start']} to {meta['period']['end']}")
    lines.append(f"COMPARISON PERIOD: {meta['comparison_period']['start']} to {meta['comparison_period']['end']}")
    lines.append("")

    # Performance Summary
    perf = context["performance_summary"]
    curr = perf["current"]
    changes = perf["changes"]

    lines.append("=" * 50)
    lines.append("OVERALL PERFORMANCE SUMMARY")
    lines.append("=" * 50)
    lines.append(f"Total Spend: ${curr['spend']:,.0f} ({_fmt_change(changes.get('spend_change'))})")
    lines.append(f"Total Revenue: ${curr['revenue']:,.0f} ({_fmt_change(changes.get('revenue_change'))})")
    if curr.get("roas") is not None:
        lines.append(f"Overall ROAS: {curr['roas']}x ({_fmt_change(changes.get('roas_change'))})")
    if curr.get("cpa") is not None:
        lines.append(f"Overall CPA: ${curr['cpa']} ({_fmt_change(changes.get('cpa_change'))})")
    lines.append(f"Total Conversions: {curr['conversions']:,.0f} ({_fmt_change(changes.get('conversions_change'))})")
    if curr.get("cvr") is not None:
        lines.append(f"Overall CVR: {curr['cvr']:.2%} ({_fmt_change(changes.get('cvr_change'))})")
    lines.append("")

    # Channel Performance
    lines.append("=" * 50)
    lines.append("PERFORMANCE BY CHANNEL")
    lines.append("=" * 50)
    for ch in context["channel_performance"]:
        lines.append(f"\n  {ch['channel'].upper()}")
        lines.append(f"    Spend: ${ch['spend']:,.0f} ({_fmt_change(ch.get('spend_change'))})")
        lines.append(f"    Revenue: ${ch['revenue']:,.0f} ({_fmt_change(ch.get('revenue_change'))})")
        if ch.get("roas") is not None:
            lines.append(f"    ROAS: {ch['roas']}x")
        if ch.get("cpa") is not None:
            lines.append(f"    CPA: ${ch['cpa']}")
        if ch.get("cvr") is not None:
            lines.append(f"    CVR: {ch['cvr']:.2%}")
    lines.append("")

    # Anomalies
    anomalies = context["anomalies"]
    if anomalies:
        lines.append("=" * 50)
        lines.append("DETECTED ANOMALIES")
        lines.append("=" * 50)
        for a in anomalies:
            lines.append(f"  [{a['severity'].upper()}] {a['date']} - {a['description']}")
        lines.append("")

    # Budget Allocation
    budget = context["budget_allocation"]
    if budget.get("channels"):
        lines.append("=" * 50)
        lines.append("BUDGET ALLOCATION & EFFICIENCY")
        lines.append("=" * 50)
        for ch in budget["channels"]:
            lines.append(
                f"  {ch['channel']}: {ch['spend_share']:.1%} of spend, "
                f"{ch['revenue_share']:.1%} of revenue, "
                f"efficiency={ch['efficiency_index']:.2f} ({ch['assessment']})"
            )
        lines.append("")

    # Top/Bottom Campaigns
    campaigns = context["top_campaigns"]
    if campaigns.get("top"):
        lines.append("=" * 50)
        lines.append("TOP CAMPAIGNS BY ROAS")
        lines.append("=" * 50)
        for c in campaigns["top"]:
            lines.append(f"  {c['campaign_name']}: ROAS {c['roas']}x | Spend ${c['cost']:,.0f} | Revenue ${c['revenue']:,.0f}")
    if campaigns.get("bottom"):
        lines.append("\nBOTTOM CAMPAIGNS BY ROAS")
        for c in campaigns["bottom"]:
            lines.append(f"  {c['campaign_name']}: ROAS {c['roas']}x | Spend ${c['cost']:,.0f} | Revenue ${c['revenue']:,.0f}")
    lines.append("")

    # Business Context
    biz = context["business_context"]
    lines.append("=" * 50)
    lines.append("BUSINESS CONTEXT")
    lines.append("=" * 50)
    lines.append("Objectives:")
    for obj in biz["objectives"]:
        lines.append(f"  - {obj}")
    lines.append("Constraints:")
    for con in biz["constraints"]:
        lines.append(f"  - {con}")

    return "\n".join(lines)


def _fmt_change(value) -> str:
    """Format a percentage change for display."""
    if value is None:
        return "N/A"
    return f"{value:+.1%}"


if __name__ == "__main__":
    from src.data_ingestion.csv_loader import load_all_sources
    from src.data_transformation.cleaner import clean_all_sources
    from src.data_transformation.normalizer import normalize_all_sources
    from src.data_transformation.kpi_calculator import calculate_kpis, generate_daily_summary
    from src.data_transformation.anomaly_detector import detect_all_anomalies

    raw_data = load_all_sources()
    cleaned_data, _ = clean_all_sources(raw_data)
    df_unified = normalize_all_sources(cleaned_data)
    df_with_kpis = calculate_kpis(df_unified)
    daily = generate_daily_summary(df_with_kpis)
    anomalies = detect_all_anomalies(daily)

    context = build_context(df_with_kpis, daily, anomalies)
    text = context_to_text(context)

    print("\n" + "=" * 60)
    print("CONTEXT FOR LLM (what the AI will receive)")
    print("=" * 60)
    print(text)
    