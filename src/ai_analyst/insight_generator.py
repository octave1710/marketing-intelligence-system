"""
Insight Generator
==================
Calls the OpenAI API with the structured prompt and returns the AI analysis.

Handles:
- API authentication
- Rate limiting with exponential backoff
- Response parsing
- Error handling and fallbacks
- Cost tracking
"""

from typing import Dict, Optional, Tuple
from pathlib import Path
import sys
import time

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config.settings import OPENAI_API_KEY, LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS
from src.utils.logger import logger

# Import OpenAI
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI library not installed. AI analysis will not be available.")


def generate_insight(
    system_prompt: str,
    user_prompt: str,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    max_retries: int = 3,
) -> Tuple[str, Dict]:
    """
    Send a prompt to the OpenAI API and get the response.
    
    Args:
        system_prompt: The system instructions (who the AI is)
        user_prompt: The actual question/data
        model: Override the default model
        temperature: Override the default temperature
        max_tokens: Override the default max tokens
        max_retries: Number of retry attempts on failure
        
    Returns:
        Tuple of (response_text, metadata_dict)
        metadata includes: model, tokens_used, cost_usd, latency_seconds
    """
    if not OPENAI_AVAILABLE:
        return _fallback_response("OpenAI library not installed")

    if not OPENAI_API_KEY:
        return _fallback_response("OPENAI_API_KEY not set in .env file")

    model = model or LLM_MODEL
    temperature = temperature if temperature is not None else LLM_TEMPERATURE
    max_tokens = max_tokens or LLM_MAX_TOKENS

    logger.info(f"Generating AI insight...")
    logger.info(f"  Model: {model} | Temp: {temperature} | Max tokens: {max_tokens}")
    logger.info(f"  System prompt: {len(system_prompt):,} chars")
    logger.info(f"  User prompt: {len(user_prompt):,} chars")

    client = OpenAI(api_key=OPENAI_API_KEY)

    for attempt in range(1, max_retries + 1):
        try:
            start_time = time.time()

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )

            latency = time.time() - start_time

            # Extract response
            content = response.choices[0].message.content
            usage = response.usage

            # Calculate cost (approximate pricing)
            cost = _estimate_cost(model, usage.prompt_tokens, usage.completion_tokens)

            metadata = {
                "model": model,
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
                "cost_usd": cost,
                "latency_seconds": round(latency, 2),
                "attempt": attempt,
                "status": "success",
            }

            logger.info(f"  ✅ AI response received:")
            logger.info(f"    Tokens: {usage.total_tokens:,} (prompt: {usage.prompt_tokens:,}, completion: {usage.completion_tokens:,})")
            logger.info(f"    Cost: ${cost:.4f}")
            logger.info(f"    Latency: {latency:.1f}s")
            logger.info(f"    Response length: {len(content):,} chars")

            return content, metadata

        except Exception as e:
            error_msg = str(e)
            logger.warning(f"  ⚠️ Attempt {attempt}/{max_retries} failed: {error_msg}")

            if attempt < max_retries:
                # Exponential backoff: wait 2^attempt seconds
                wait_time = 2 ** attempt
                logger.info(f"  Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.error(f"  ❌ All {max_retries} attempts failed")
                return _fallback_response(error_msg)

    return _fallback_response("Unknown error")


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """
    Estimate the API call cost based on model and token usage.
    Prices as of 2024 (may change — check OpenAI pricing page).
    """
    pricing = {
        "gpt-4o-mini": {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000},
        "gpt-4o": {"input": 2.50 / 1_000_000, "output": 10.00 / 1_000_000},
        "gpt-4-turbo": {"input": 10.00 / 1_000_000, "output": 30.00 / 1_000_000},
    }

    if model in pricing:
        p = pricing[model]
        return prompt_tokens * p["input"] + completion_tokens * p["output"]
    else:
        # Default estimate for unknown models
        return (prompt_tokens + completion_tokens) * 0.001 / 1_000


def _fallback_response(error_message: str) -> Tuple[str, Dict]:
    """
    Generate a basic fallback response when the API is unavailable.
    This ensures the pipeline doesn't crash if OpenAI is down.
    """
    logger.warning(f"  Using fallback response: {error_message}")

    fallback_text = f"""## 📊 AI Analysis Unavailable

The AI analysis could not be generated due to: {error_message}

Please review the data manually using the dashboard KPI cards and charts.
The anomaly detection results are still available in the Anomalies section.

**To fix this:**
1. Check that your OPENAI_API_KEY is set correctly in the .env file
2. Verify you have API credits at platform.openai.com
3. Try running the pipeline again
"""

    metadata = {
        "model": "fallback",
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "cost_usd": 0.0,
        "latency_seconds": 0.0,
        "attempt": 0,
        "status": "fallback",
        "error": error_message,
    }

    return fallback_text, metadata


if __name__ == "__main__":
    # Quick test: call the API with a simple prompt
    print("=" * 60)
    print("TESTING OPENAI API CONNECTION")
    print("=" * 60)

    test_response, test_meta = generate_insight(
        system_prompt="You are a helpful marketing analyst. Be very brief.",
        user_prompt="In one sentence, what is ROAS and why does it matter?",
        max_tokens=100,
    )

    print(f"\nResponse:\n{test_response}")
    print(f"\nMetadata: {test_meta}")
    