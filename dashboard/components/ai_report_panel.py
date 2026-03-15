"""
AI Report Panel Component
===========================
Displays the AI-generated analysis in an expandable panel.
"""

import streamlit as st
from typing import Dict, Optional


def render_ai_report(report_data: Optional[Dict]):
    """
    Render the AI analysis panel.
    
    Args:
        report_data: The compiled report dictionary (from report_compiler)
    """
    st.markdown("### 🤖 AI Executive Analysis")

    if report_data is None:
        st.warning("No AI report available. Click 'Generate Report' to create one.")
        return

    # Report metadata
    metadata = report_data.get("metadata", {})
    col1, col2, col3 = st.columns(3)
    with col1:
        st.caption(f"📅 Period: {metadata.get('period', {}).get('start', 'N/A')} to {metadata.get('period', {}).get('end', 'N/A')}")
    with col2:
        st.caption(f"🤖 Model: {metadata.get('model_used', 'N/A')}")
    with col3:
        st.caption(f"💰 Cost: ${metadata.get('cost_usd', 0):.4f} | ⏱️ {metadata.get('generation_seconds', 0):.1f}s")

    # AI Narrative — the main analysis
    ai_text = report_data.get("ai_narrative", "No analysis generated.")

    with st.expander("📊 Full AI Analysis", expanded=True):
        st.markdown(ai_text)

    # Recommendations
    recommendations = report_data.get("recommendations", [])
    if recommendations:
        with st.expander(f"🎯 Recommendations ({len(recommendations)})"):
            for rec in recommendations:
                emoji = {
                    "critical": "🔴",
                    "high": "🟠",
                    "medium": "🟡",
                    "low": "⚪",
                }.get(rec.get("priority", "medium"), "⚪")

                source_badge = "🤖 AI" if rec.get("source") == "ai_generated" else "📏 Rule"

                st.markdown(f"""
                **{emoji} [{rec.get('priority', 'medium').upper()}]** {rec.get('title', 'No title')}
                
                {rec.get('rationale', '')}
                
                *Impact: {rec.get('expected_impact', 'N/A')} | Effort: {rec.get('effort', 'N/A')} | Source: {source_badge}*
                
                ---
                """)

    # Sentiment indicator
    sentiment = report_data.get("executive_summary", {}).get("overall_sentiment", "neutral")
    sentiment_display = {
        "positive": "🟢 Positive",
        "negative": "🔴 Negative",
        "mixed": "🟡 Mixed",
        "neutral": "⚪ Neutral",
    }.get(sentiment, "⚪ Unknown")

    st.markdown(f"**Overall Sentiment:** {sentiment_display}")
    
    