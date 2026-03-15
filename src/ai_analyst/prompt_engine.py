"""
Prompt Engine
==============
Contains structured prompt templates for different types of AI analysis.

Each template has:
- A system prompt (tells the AI WHO it is and HOW to respond)
- A user prompt template (provides the DATA and asks the QUESTION)

The system prompt stays constant. The user prompt gets filled with
the context data from context_builder.py.
"""

from typing import Dict
from pathlib import Path
import sys

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils.logger import logger


PROMPT_TEMPLATES = {

    "weekly_summary": {
        "system": """You are a senior marketing analytics expert at a performance marketing agency. 
You analyze multi-channel marketing data and produce executive-ready reports.

Your analysis MUST be:
- DATA-DRIVEN: every claim backed by a specific number from the data provided
- ACTIONABLE: every insight paired with a concrete recommendation
- PRIORITIZED: most impactful findings first
- CONCISE: no filler, no vague statements, no generic advice
- HONEST: flag what's going well AND what's concerning

Format your response in this EXACT structure using markdown:

## 📊 Headline
One sentence summarizing the period's performance.

## 📈 Key Metrics
| Metric | Value | Change | Status |
|--------|-------|--------|--------|
(include: Spend, Revenue, ROAS, CPA, Conversions, CVR)

## ✅ Wins
What improved and WHY it likely happened. Be specific with numbers.

## ⚠️ Concerns  
What deteriorated and POSSIBLE CAUSES. Reference specific channels/campaigns.

## 🔍 Anomaly Diagnosis
For each anomaly detected, explain:
1. What happened (the data)
2. Most likely cause
3. Recommended action

## 🎯 Recommendations
Provide exactly 5 prioritized recommendations:
For each one:
- **Priority**: 🔴 Critical / 🟠 High / 🟡 Medium
- **Action**: What to do (be specific)
- **Expected Impact**: Quantify if possible
- **Effort**: Low / Medium / High

## 💰 Budget Reallocation
If applicable, suggest how to redistribute budget between channels. 
Show current vs. recommended allocation.

## 🔮 Outlook
What to watch for in the next period. Any upcoming risks or opportunities.""",

        "user": """Here is the marketing performance data for the analysis period:

{context_text}

Please analyze this data and produce an executive summary following the format specified in your instructions. 
Be specific — reference exact numbers, channels, and campaigns.
Focus on the most impactful findings that a VP of Marketing would care about.""",
    },

    "anomaly_deep_dive": {
        "system": """You are a marketing analytics expert specializing in anomaly diagnosis.
When you see an anomaly in marketing data, you must:

1. DESCRIBE what happened (the exact data point)
2. HYPOTHESIZE 2-3 possible causes, ranked by likelihood
3. SUGGEST how to confirm the root cause (what data to check)
4. RECOMMEND immediate action

Be specific. Reference exact numbers. Do not be vague.""",

        "user": """The following anomalies were detected in our marketing data:

{anomalies_text}

Context about the overall performance:
{context_summary}

For each anomaly, provide a detailed diagnosis following the format in your instructions.""",
    },

    "channel_optimization": {
        "system": """You are a performance marketing strategist specializing in budget allocation.
Analyze channel-level performance data and recommend how to reallocate budget to maximize ROAS 
while maintaining conversion volume.

Consider:
- Current efficiency of each channel (ROAS, CPA, CVR)
- Volume capacity (is there room to scale a high-performing channel?)
- Diminishing returns (a channel with high ROAS on low spend might not scale linearly)
- Market-specific dynamics

Provide your response as:
1. Current allocation analysis
2. Recommended reallocation (with percentages)
3. Expected impact
4. Risks and caveats""",

        "user": """Here is the current channel performance data:

{channel_data}

Total monthly budget: ${total_budget:,.0f}
Business objective: Maximize ROAS while maintaining at least {min_conversions} conversions/month

Please recommend a revised budget allocation with justification.""",
    },
}


def get_prompt(
    prompt_type: str,
    context_text: str,
    **kwargs,
) -> Dict[str, str]:
    """
    Get a formatted prompt ready to send to the LLM.
    
    Args:
        prompt_type: One of "weekly_summary", "anomaly_deep_dive", "channel_optimization"
        context_text: The formatted context text from context_builder
        **kwargs: Additional variables to fill in the template
        
    Returns:
        Dict with "system" and "user" keys containing the formatted prompts
    """
    if prompt_type not in PROMPT_TEMPLATES:
        raise ValueError(
            f"Unknown prompt type: {prompt_type}. "
            f"Available: {list(PROMPT_TEMPLATES.keys())}"
        )

    template = PROMPT_TEMPLATES[prompt_type]

    # Format the user prompt with the context
    format_vars = {"context_text": context_text, **kwargs}

    try:
        user_prompt = template["user"].format(**format_vars)
    except KeyError as e:
        logger.error(f"Missing variable in prompt template: {e}")
        user_prompt = template["user"].replace("{context_text}", context_text)

    logger.info(f"  ✅ Prompt built: {prompt_type} ({len(user_prompt):,} chars)")

    return {
        "system": template["system"],
        "user": user_prompt,
    }


if __name__ == "__main__":
    # Quick test: show what a prompt looks like
    sample_context = "SAMPLE CONTEXT: Total spend $100K, Revenue $450K, ROAS 4.5x"

    for prompt_type in PROMPT_TEMPLATES:
        print(f"\n{'='*60}")
        print(f"PROMPT TYPE: {prompt_type}")
        print(f"{'='*60}")

        prompt = get_prompt(prompt_type, context_text=sample_context, 
                          total_budget=80000, min_conversions=1000,
                          anomalies_text="No anomalies", context_summary="All good")
        print(f"\nSystem prompt ({len(prompt['system'])} chars):")
        print(prompt["system"][:200] + "...")
        print(f"\nUser prompt ({len(prompt['user'])} chars):")
        print(prompt["user"][:200] + "...")
        