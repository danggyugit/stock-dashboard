"""AI-powered valuation analysis via Gemini 2.0 Flash (free tier).

Generates scenario narratives on top of the data-based valuation produced
by `valuation_service`. Runs only when the user clicks the "AI analysis"
button — caches results 24h per ticker to stay within the 1,500/day free
quota comfortably.

Returns structured dict with:
  - bear_narrative, base_narrative, bull_narrative (short, data-grounded)
  - multiple_rationale (why these P/E ranges make sense for this ticker)
  - sector_context (cyclical/secular/defensive classification + current state)
  - key_risks (3 bullets)
  - key_catalysts (3 bullets)
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import streamlit as st

logger = logging.getLogger(__name__)

_MODEL = "gemini-2.5-flash"  # free tier: 10 RPM, 250 RPD (default)

MODEL_FLASH = "gemini-2.5-flash"
MODEL_FLASH_LITE = "gemini-2.5-flash-lite"


def _get_client():
    """Return a google-genai Client, or None if not configured."""
    try:
        api_key = st.secrets.get("GEMINI_API_KEY")
    except Exception:
        api_key = None
    if not api_key:
        return None
    try:
        from google import genai
        return genai.Client(api_key=api_key)
    except Exception as e:
        logger.warning("genai Client init failed: %s", e)
        return None


def is_available() -> bool:
    """Whether AI analysis is configured and usable."""
    return _get_client() is not None


def _build_prompt(ticker: str, core: dict, consensus: dict, bands: dict) -> str:
    """Build a grounded prompt using the numeric inputs from valuation_service."""
    cur_price = core.get("current_price")
    mcap = core.get("market_cap")
    ttm_eps = core.get("trailing_eps")
    fwd_eps = core.get("forward_eps")
    ttm_rev = core.get("ttm_revenue")
    rev_yoy = core.get("revenue_growth_yoy") or core.get("q_yoy")
    gm = core.get("gross_margin")
    om = core.get("operating_margin")

    t_mean = consensus.get("target_mean")
    t_high = consensus.get("target_high")
    t_low = consensus.get("target_low")
    n_ana = consensus.get("n_analysts")
    rec_key = consensus.get("rec_key") or ""

    bear = bands.get("bear", {})
    base = bands.get("base", {})
    bull = bands.get("bull", {})
    src = bands.get("_source", "")

    def _fmt_money(v):
        if v is None: return "N/A"
        if abs(v) >= 1e12: return f"${v/1e12:.2f}T"
        if abs(v) >= 1e9:  return f"${v/1e9:.2f}B"
        if abs(v) >= 1e6:  return f"${v/1e6:.0f}M"
        return f"${v:,.2f}"

    def _fmt_pct(v):
        return f"{v*100:+.1f}%" if v is not None else "N/A"

    return f"""You are an equity analyst producing independent scenario-based target prices.

TICKER: {ticker}

DATA (yfinance + 5y historical P/E percentiles):
- Current price: {_fmt_money(cur_price)}
- Market cap: {_fmt_money(mcap)}
- TTM EPS: ${ttm_eps if ttm_eps else 'N/A'} / Forward EPS: ${fwd_eps if fwd_eps else 'N/A'}
- TTM revenue: {_fmt_money(ttm_rev)} (YoY {_fmt_pct(rev_yoy)})
- Gross margin (TTM): {_fmt_pct(gm)} / Operating margin (TTM): {_fmt_pct(om)}
- Analyst consensus: n={n_ana}, mean {_fmt_money(t_mean)}, high {_fmt_money(t_high)}, low {_fmt_money(t_low)}, recommendation: {rec_key}

REFERENCE (data-based, for context only — you may diverge):
- Bear:  ${bear.get('low')} – ${bear.get('high')} (P/E {bear.get('mult_range')})
- Base:  ${base.get('low')} – ${base.get('high')} (P/E {base.get('mult_range')})
- Bull:  ${bull.get('low')} – ${bull.get('high')} (P/E {bull.get('mult_range')})
- Bands source: {src}

TASK:
Produce YOUR OWN judgment-based Bear/Base/Bull target price bands. Do NOT just echo the reference above — apply your own view of:
  - Cycle position (peak/mid/trough for cyclicals)
  - Sector norms (memory ≠ software ≠ utility)
  - Whether the current earnings are sustainable or cyclical-peak
  - Whether a "normalized" EPS (lower than forward EPS) should be used for cyclicals
  - Whether the historical P/E median still applies given current growth rate

Return JSON ONLY (no markdown, no prose outside JSON):

{{
  "sector_classification": "One short phrase (e.g. 'Cyclical memory — value on mid-cycle EPS')",
  "multiple_rationale": "1-2 sentences explaining which EPS base and multiple range you chose and why.",
  "eps_basis": {{
    "value": <number you used for valuation>,
    "label": "e.g. 'Forward EPS', 'Mid-cycle EPS (3yr avg)', 'Normalized EPS at 20% NI margin'"
  }},
  "bear": {{
    "low": <number>, "high": <number>,
    "multiple_low": <number>, "multiple_high": <number>,
    "narrative": "1 sentence: what assumption makes this case real"
  }},
  "base": {{
    "low": <number>, "high": <number>,
    "multiple_low": <number>, "multiple_high": <number>,
    "narrative": "1 sentence"
  }},
  "bull": {{
    "low": <number>, "high": <number>,
    "multiple_low": <number>, "multiple_high": <number>,
    "narrative": "1 sentence"
  }},
  "key_risks": ["risk 1 (short)", "risk 2", "risk 3"],
  "key_catalysts": ["catalyst 1", "catalyst 2", "catalyst 3"]
}}

IMPORTANT:
- Every target price must equal eps_basis.value × multiple (so the math is auditable).
- Prefer a lower EPS basis for cyclicals at peak (e.g., mid-cycle EPS) rather than peak forward EPS.
- Numbers must be plain numbers (no $, no commas). E.g. 725.50 not "$725.50".
- Keep narratives grounded — use generic sector language, don't fabricate product names or guidance dates.
- Output ONLY valid JSON."""


def _parse_json_response(text: str) -> dict | None:
    """Extract JSON object from Gemini response (handles markdown fences)."""
    if not text:
        return None
    # Strip markdown code fences if present
    text = text.strip()
    if text.startswith("```"):
        # Remove ``` and optional language tag
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    # Find first { to last }
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < 0:
        return None
    try:
        return json.loads(text[start:end + 1])
    except Exception as e:
        logger.warning("AI valuation JSON parse failed: %s", e)
        return None


@st.cache_data(ttl=86400, show_spinner=False)
def get_ai_scenario_analysis(
    ticker: str,
    core: dict,
    consensus: dict,
    bands: dict,
    model: str = MODEL_FLASH,
) -> dict[str, Any] | None:
    """Call Gemini and return parsed scenario analysis. Cached 24h per ticker+model.

    Returns None if Gemini not configured or call fails.
    """
    client = _get_client()
    if client is None:
        return None

    prompt = _build_prompt(ticker, core, consensus, bands)

    try:
        resp = client.models.generate_content(
            model=model,
            contents=prompt,
        )
        text = getattr(resp, "text", None) or ""
    except Exception as e:
        logger.warning("Gemini call failed for %s (%s): %s", ticker, model, e)
        return {"error": str(e), "_model": model}

    parsed = _parse_json_response(text)
    if not parsed:
        return {"error": "Could not parse AI response",
                "raw": text[:500], "_model": model}

    parsed["_model"] = model
    parsed["_ticker"] = ticker
    return parsed


def get_ai_scenario_analysis_dual(
    ticker: str, core: dict, consensus: dict, bands: dict,
) -> dict[str, dict | None]:
    """Run both Flash and Flash-Lite, return both for side-by-side comparison."""
    return {
        "flash":      get_ai_scenario_analysis(ticker, core, consensus, bands, MODEL_FLASH),
        "flash_lite": get_ai_scenario_analysis(ticker, core, consensus, bands, MODEL_FLASH_LITE),
    }
