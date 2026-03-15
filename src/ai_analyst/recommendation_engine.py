"""
Recommendation Engine
======================
Generates actionable recommendations from two sources:

1. RULE-BASED: Deterministic rules (if ROAS < target, recommend X)
   These are predictable and always consistent.

2. AI-GENERATED: Extracted from the LLM's analysis
   These are more nuanced and contextual.

Each recommendation has: priority, category, action, rationale, expected impact, effort.
"""

from typing import List, Dict, Optional
from pathlib import Path
import sys

import pandas as pd

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config.settings import TARGET_ROAS, TARGET_CPA, MAX_FREQUENCY
from src.utils.logger import logger


def generate_rule_based_recommendations(
    context: Dict,
) -> List[Dict]:
    """
    Generate recommendations based on deterministic business rules.
    
    These rules encode marketing best practices that are always true:
    - Low ROAS → reduce spend or optimize
    - High CPA → fix targeting or creatives
    - High frequency → refresh creatives
    - Efficiency imbalance → reallocate budget
    
    Args:
        context: The context dictionary from context_builder
        
    Returns:
        List of recommendation dictionaries
    """
    logger.info("Generating rule-based recommendations...")

    recommendations = []
    rec_id = 0

    # ---- RULE 1: Channel ROAS below target ----
    for ch in context.get("channel_performance", []):
        roas = ch.get("roas")
        if roas is not None and roas < TARGET_ROAS and ch.get("spend", 0) > 0:
            rec_id += 1
            severity = "critical" if roas < TARGET_ROAS * 0.5 else "high"
            recommendations.append({
                "id": f"rec_{rec_id:03d}",
                "priority": severity,
                "category": "budget",
                "channel": ch["channel"],
                "market": "all",
                "title": f"Optimize or reduce {ch['channel']} spend — ROAS {roas}x is below target {TARGET_ROAS}x",
                "rationale": (
                    f"{ch['channel']} is generating {roas}x ROAS against a target of {TARGET_ROAS}x. "
                    f"Current spend: ${ch['spend']:,.0f}, revenue: ${ch['revenue']:,.0f}."
                ),
                "expected_impact": f"Improve blended ROAS by reducing inefficient spend",
                "effort": "medium",
                "source": "rule_based",
            })

    # ---- RULE 2: Channel CPA above target ----
    for ch in context.get("channel_performance", []):
        cpa = ch.get("cpa")
        if cpa is not None and cpa > TARGET_CPA and ch.get("spend", 0) > 0:
            rec_id += 1
            recommendations.append({
                "id": f"rec_{rec_id:03d}",
                "priority": "high",
                "category": "audience",
                "channel": ch["channel"],
                "market": "all",
                "title": f"Reduce CPA on {ch['channel']} — currently ${cpa:.0f} vs target ${TARGET_CPA:.0f}",
                "rationale": (
                    f"CPA of ${cpa:.2f} exceeds the ${TARGET_CPA} target. "
                    f"Review audience targeting, creative performance, and landing page conversion rate."
                ),
                "expected_impact": f"Reduce CPA to target would save ${(cpa - TARGET_CPA) * ch.get('conversions', 0):,.0f}",
                "effort": "medium",
                "source": "rule_based",
            })

    # ---- RULE 3: Budget reallocation based on efficiency ----
    budget = context.get("budget_allocation", {})
    channels = budget.get("channels", [])
    
    over_performers = [c for c in channels if c.get("efficiency_index", 0) > 1.15]
    under_performers = [c for c in channels if c.get("efficiency_index", 0) < 0.85]

    if over_performers and under_performers:
        rec_id += 1
        over_names = ", ".join([c["channel"] for c in over_performers])
        under_names = ", ".join([c["channel"] for c in under_performers])
        recommendations.append({
            "id": f"rec_{rec_id:03d}",
            "priority": "high",
            "category": "budget",
            "channel": "all",
            "market": "all",
            "title": f"Reallocate budget from {under_names} to {over_names}",
            "rationale": (
                f"Efficiency analysis shows {over_names} generating more revenue per dollar "
                f"than {under_names}. Shifting 10-15% of budget could improve overall ROAS."
            ),
            "expected_impact": "Estimated +5-15% improvement in blended ROAS",
            "effort": "low",
            "source": "rule_based",
        })

    # ---- RULE 4: Underperforming campaigns ----
    bottom_campaigns = context.get("top_campaigns", {}).get("bottom", [])
    for camp in bottom_campaigns:
        if camp.get("roas", 999) < TARGET_ROAS * 0.5:
            rec_id += 1
            recommendations.append({
                "id": f"rec_{rec_id:03d}",
                "priority": "high",
                "category": "budget",
                "channel": camp.get("channel", "unknown"),
                "market": "all",
                "title": f"Review '{camp['campaign_name']}' — ROAS only {camp['roas']}x",
                "rationale": (
                    f"This campaign has spent ${camp['cost']:,.0f} but only generated "
                    f"${camp['revenue']:,.0f} in revenue (ROAS {camp['roas']}x). "
                    f"Consider pausing, restructuring, or significantly reducing budget."
                ),
                "expected_impact": f"Save ${camp['cost'] * 0.3:,.0f}/month if budget cut by 30%",
                "effort": "low",
                "source": "rule_based",
            })

    # ---- RULE 5: Declining metrics ----
    changes = context.get("notable_changes", {})
    for det in changes.get("deteriorations", []):
        if abs(det.get("change_pct", 0)) > 0.15:
            rec_id += 1
            recommendations.append({
                "id": f"rec_{rec_id:03d}",
                "priority": "medium",
                "category": "investigation",
                "channel": det["channel"],
                "market": "all",
                "title": f"Investigate {det['metric']} decline on {det['channel']} ({det['change_pct']:+.1%})",
                "rationale": (
                    f"{det['metric'].capitalize()} dropped from ${det['previous_value']:,.0f} "
                    f"to ${det['current_value']:,.0f} ({det['change_pct']:+.1%}). "
                    f"This needs investigation to determine if it's a trend or temporary."
                ),
                "expected_impact": "Prevent further decline and potential revenue loss",
                "effort": "low",
                "source": "rule_based",
            })

    # Sort by priority
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    recommendations.sort(key=lambda x: priority_order.get(x["priority"], 99))

    logger.info(f"  ✅ Generated {len(recommendations)} rule-based recommendations")
    return recommendations


def parse_ai_recommendations(ai_text: str) -> List[Dict]:
    """
    Extract structured recommendations from the AI's markdown response.
    
    Looks for the "Recommendations" section and parses each item.
    This is a best-effort parser — AI output format can vary.
    
    Args:
        ai_text: The raw markdown text from the LLM
        
    Returns:
        List of recommendation dictionaries
    """
    recommendations = []

    # Find the recommendations section
    lines = ai_text.split("\n")
    in_recommendations = False
    current_rec = None
    rec_id = 100

    for line in lines:
        line_stripped = line.strip()

        # Detect start of recommendations section
        if "recommendation" in line_stripped.lower() and "#" in line:
            in_recommendations = True
            continue

        # Detect end (next section header)
        if in_recommendations and line_stripped.startswith("## ") and "recommendation" not in line_stripped.lower():
            in_recommendations = False
            continue

        if not in_recommendations:
            continue

        # Parse recommendation items
        if line_stripped.startswith(("- **", "* **", "1.", "2.", "3.", "4.", "5.")):
            if current_rec:
                recommendations.append(current_rec)

            rec_id += 1
            # Determine priority from emojis or text
            priority = "medium"
            if "🔴" in line_stripped or "critical" in line_stripped.lower():
                priority = "critical"
            elif "🟠" in line_stripped or "high" in line_stripped.lower():
                priority = "high"
            elif "🟡" in line_stripped or "medium" in line_stripped.lower():
                priority = "medium"

            current_rec = {
                "id": f"rec_{rec_id:03d}",
                "priority": priority,
                "category": "ai_insight",
                "channel": "all",
                "market": "all",
                "title": line_stripped.lstrip("-* 0123456789.").strip(),
                "rationale": "",
                "expected_impact": "",
                "effort": "medium",
                "source": "ai_generated",
            }
        elif current_rec and line_stripped:
            # Add details to current recommendation
            lower = line_stripped.lower()
            if "impact" in lower:
                current_rec["expected_impact"] = line_stripped.split(":", 1)[-1].strip() if ":" in line_stripped else line_stripped
            elif "effort" in lower:
                effort_text = line_stripped.lower()
                if "low" in effort_text:
                    current_rec["effort"] = "low"
                elif "high" in effort_text:
                    current_rec["effort"] = "high"
                else:
                    current_rec["effort"] = "medium"
            elif "action" in lower or "**action**" in lower:
                current_rec["title"] = line_stripped.split(":", 1)[-1].strip() if ":" in line_stripped else line_stripped
            else:
                current_rec["rationale"] += " " + line_stripped

    if current_rec:
        recommendations.append(current_rec)

    logger.info(f"  ✅ Parsed {len(recommendations)} AI recommendations from text")
    return recommendations


def combine_recommendations(
    rule_based: List[Dict],
    ai_generated: List[Dict],
    max_total: int = 10,
) -> List[Dict]:
    """
    Combine rule-based and AI recommendations, remove near-duplicates,
    and return top N by priority.
    """
    all_recs = rule_based + ai_generated

    # Sort by priority
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    all_recs.sort(key=lambda x: priority_order.get(x["priority"], 99))

    # Take top N
    final = all_recs[:max_total]

    logger.info(f"  ✅ Final recommendations: {len(final)} (from {len(rule_based)} rules + {len(ai_generated)} AI)")
    return final


if __name__ == "__main__":
    from src.data_ingestion.csv_loader import load_all_sources
    from src.data_transformation.cleaner import clean_all_sources
    from src.data_transformation.normalizer import normalize_all_sources
    from src.data_transformation.kpi_calculator import calculate_kpis, generate_daily_summary
    from src.data_transformation.anomaly_detector import detect_all_anomalies
    from src.ai_analyst.context_builder import build_context

    raw_data = load_all_sources()
    cleaned_data, _ = clean_all_sources(raw_data)
    df_unified = normalize_all_sources(cleaned_data)
    df_with_kpis = calculate_kpis(df_unified)
    daily = generate_daily_summary(df_with_kpis)
    anomalies = detect_all_anomalies(daily)
    context = build_context(df_with_kpis, daily, anomalies)

    # Generate rule-based recommendations
    recs = generate_rule_based_recommendations(context)

    print("\n" + "=" * 60)
    print("RULE-BASED RECOMMENDATIONS")
    print("=" * 60)
    for rec in recs:
        emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪"}.get(rec["priority"], "")
        print(f"\n{emoji} [{rec['priority'].upper()}] {rec['title']}")
        print(f"   Category: {rec['category']} | Channel: {rec['channel']}")
        print(f"   Rationale: {rec['rationale'][:120]}...")
        print(f"   Impact: {rec['expected_impact']}")
        print(f"   Effort: {rec['effort']}")
        