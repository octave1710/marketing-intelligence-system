"""
Report Compiler
================
Assembles the final AI-powered marketing report from all components:
- KPI data from context_builder
- AI narrative from insight_generator
- Recommendations from recommendation_engine

Outputs:
- JSON (structured, for storage and API use)
- Markdown (human-readable, for dashboard display)
"""

from typing import Dict, Optional, List
from pathlib import Path
from datetime import datetime
import sys
import json

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config.settings import LLM_MODEL
from src.utils.logger import logger
from src.ai_analyst.context_builder import build_context, context_to_text
from src.ai_analyst.prompt_engine import get_prompt
from src.ai_analyst.insight_generator import generate_insight
from src.ai_analyst.recommendation_engine import (
    generate_rule_based_recommendations,
    parse_ai_recommendations,
    combine_recommendations,
)


def compile_report(
    df_unified,
    df_daily,
    df_anomalies,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
    report_type: str = "weekly_summary",
) -> Dict:
    """
    Generate a complete AI-powered marketing report.
    
    This is the main orchestration function that:
    1. Builds the data context
    2. Creates the prompt
    3. Calls the LLM
    4. Generates rule-based recommendations
    5. Parses AI recommendations
    6. Assembles everything into a structured report
    
    Args:
        df_unified: Unified DataFrame with KPIs
        df_daily: Daily KPI summary
        df_anomalies: Detected anomalies
        period_start: Start date (YYYY-MM-DD)
        period_end: End date (YYYY-MM-DD)
        report_type: Type of analysis to generate
        
    Returns:
        Complete report as a dictionary with JSON and Markdown content
    """
    logger.info("=" * 50)
    logger.info("COMPILING AI MARKETING REPORT")
    logger.info("=" * 50)

    start_time = datetime.now()

    # Step 1: Build context
    logger.info("Step 1/5: Building context...")
    context = build_context(df_unified, df_daily, df_anomalies, period_start, period_end)
    context_text = context_to_text(context)

    # Step 2: Create prompt
    logger.info("Step 2/5: Creating prompt...")
    prompt = get_prompt(report_type, context_text=context_text)

    # Step 3: Call LLM
    logger.info("Step 3/5: Calling AI model...")
    ai_narrative, ai_metadata = generate_insight(
        system_prompt=prompt["system"],
        user_prompt=prompt["user"],
    )

    # Step 4: Generate recommendations
    logger.info("Step 4/5: Generating recommendations...")
    rule_recs = generate_rule_based_recommendations(context)
    ai_recs = parse_ai_recommendations(ai_narrative)
    all_recs = combine_recommendations(rule_recs, ai_recs)

    # Step 5: Assemble report
    logger.info("Step 5/5: Assembling final report...")
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    # Get period info
    meta = context["metadata"]
    perf = context["performance_summary"]["current"]

    report_id = f"rpt_{meta['period']['end'].replace('-', '')}_{report_type}"

    report = {
        "metadata": {
            "report_id": report_id,
            "report_type": report_type,
            "generated_at": end_time.isoformat(),
            "period": meta["period"],
            "comparison_period": meta["comparison_period"],
            "model_used": ai_metadata.get("model", "unknown"),
            "tokens_used": ai_metadata.get("total_tokens", 0),
            "cost_usd": ai_metadata.get("cost_usd", 0),
            "generation_seconds": round(duration, 1),
        },
        "executive_summary": {
            "overall_sentiment": _determine_sentiment(context),
            "key_metrics": perf,
            "changes": context["performance_summary"]["changes"],
        },
        "channel_performance": context["channel_performance"],
        "anomalies": context["anomalies"],
        "recommendations": all_recs,
        "ai_narrative": ai_narrative,
        "budget_allocation": context["budget_allocation"],
        "top_campaigns": context["top_campaigns"],
    }

    # Generate markdown version
    markdown = _compile_markdown(report)

    logger.info(f"\n✅ Report compiled successfully!")
    logger.info(f"  Report ID: {report_id}")
    logger.info(f"  AI model: {ai_metadata.get('model', 'unknown')}")
    logger.info(f"  Tokens: {ai_metadata.get('total_tokens', 0):,}")
    logger.info(f"  Cost: ${ai_metadata.get('cost_usd', 0):.4f}")
    logger.info(f"  Duration: {duration:.1f}s")
    logger.info("=" * 50)

    return {
        "json": report,
        "markdown": markdown,
        "metadata": report["metadata"],
    }


def _determine_sentiment(context: Dict) -> str:
    """Determine overall sentiment based on KPI changes."""
    changes = context["performance_summary"]["changes"]
    
    positive_signals = 0
    negative_signals = 0
    
    for key, value in changes.items():
        if value is None:
            continue
        # For metrics where up is good
        if key in ["revenue_change", "roas_change", "conversions_change", "cvr_change"]:
            if value > 0.02:
                positive_signals += 1
            elif value < -0.02:
                negative_signals += 1
        # For metrics where down is good
        elif key in ["cpa_change", "cpc_change"]:
            if value < -0.02:
                positive_signals += 1
            elif value > 0.02:
                negative_signals += 1

    if positive_signals > negative_signals + 1:
        return "positive"
    elif negative_signals > positive_signals + 1:
        return "negative"
    elif positive_signals > 0 and negative_signals > 0:
        return "mixed"
    else:
        return "neutral"


def _compile_markdown(report: Dict) -> str:
    """Convert the report dictionary into a readable Markdown document."""
    lines = []
    meta = report["metadata"]
    
    lines.append(f"# Marketing Intelligence Report")
    lines.append(f"**Period:** {meta['period']['start']} to {meta['period']['end']}")
    lines.append(f"**Generated:** {meta['generated_at'][:19]}")
    lines.append(f"**Model:** {meta['model_used']} | **Cost:** ${meta['cost_usd']:.4f}")
    lines.append("")

    # AI Narrative (the main analysis)
    lines.append("---")
    lines.append("")
    lines.append(report.get("ai_narrative", "No AI analysis available."))
    lines.append("")

    # Recommendations
    lines.append("---")
    lines.append("## 📋 All Recommendations (Rules + AI)")
    lines.append("")
    
    recs = report.get("recommendations", [])
    if recs:
        lines.append("| # | Priority | Action | Impact | Effort | Source |")
        lines.append("|---|----------|--------|--------|--------|--------|")
        for i, rec in enumerate(recs, 1):
            emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪"}.get(rec["priority"], "")
            title_short = rec["title"][:60] + "..." if len(rec["title"]) > 60 else rec["title"]
            impact_short = rec["expected_impact"][:40] if rec["expected_impact"] else "—"
            lines.append(f"| {i} | {emoji} {rec['priority']} | {title_short} | {impact_short} | {rec['effort']} | {rec['source']} |")
    lines.append("")

    # Channel Performance Summary
    lines.append("## 📊 Channel Performance")
    lines.append("")
    lines.append("| Channel | Spend | Revenue | ROAS | CPA | CVR |")
    lines.append("|---------|-------|---------|------|-----|-----|")
    for ch in report.get("channel_performance", []):
        roas = f"{ch['roas']}x" if ch.get('roas') is not None else "N/A"
        cpa = f"${ch['cpa']:.0f}" if ch.get('cpa') is not None else "N/A"
        cvr = f"{ch['cvr']:.2%}" if ch.get('cvr') is not None else "N/A"
        lines.append(f"| {ch['channel']} | ${ch['spend']:,.0f} | ${ch['revenue']:,.0f} | {roas} | {cpa} | {cvr} |")
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    from src.data_ingestion.csv_loader import load_all_sources
    from src.data_transformation.cleaner import clean_all_sources
    from src.data_transformation.normalizer import normalize_all_sources
    from src.data_transformation.kpi_calculator import calculate_kpis, generate_daily_summary
    from src.data_transformation.anomaly_detector import detect_all_anomalies

    # Full pipeline
    raw_data = load_all_sources()
    cleaned_data, _ = clean_all_sources(raw_data)
    df_unified = normalize_all_sources(cleaned_data)
    df_with_kpis = calculate_kpis(df_unified)
    daily = generate_daily_summary(df_with_kpis)
    anomalies = detect_all_anomalies(daily)

    # Compile report
    result = compile_report(df_with_kpis, daily, anomalies)

    # Display
    print("\n" + "=" * 60)
    print("GENERATED REPORT (Markdown)")
    print("=" * 60)
    print(result["markdown"])

    # Save report to file
    output_path = project_root / "data" / "processed" / "latest_report.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result["markdown"])
    print(f"\n📄 Report saved to {output_path}")
    
    