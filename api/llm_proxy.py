"""LLM proxy for AI-generated stock summaries.

Uses Gemini 2.5 Flash via REST (no google-genai SDK dependency needed).
Key stays on the server; the browser calls our proxy, we call Gemini.

Free tier is 10 RPM / 250 RPD — plenty for on-demand summaries with our
5-minute per-symbol cache.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash:generateContent"
)

# Cache: (symbol, cache_key) -> (fetched_at, text)
_CACHE: dict[tuple[str, str], tuple[float, str]] = {}
_CACHE_TTL_SECONDS = 3600 * 6  # 6 hours — earnings context doesn't change intraday


def _key() -> str:
    return os.environ.get("GEMINI_API_KEY", "").strip()


def _cached_generate(prompt: str, cache_key: str) -> str:
    """POST to Gemini, cache by cache_key. Raises RuntimeError on failure."""
    api_key = _key()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not configured on the server.")

    now = time.time()
    hit = _CACHE.get((cache_key, "")) if False else _CACHE.get(("prompt", cache_key))
    if hit and (now - hit[0]) < _CACHE_TTL_SECONDS:
        return hit[1]

    body: dict[str, Any] = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 800,
        },
    }
    resp = requests.post(
        f"{GEMINI_ENDPOINT}?key={api_key}",
        headers={"Content-Type": "application/json"},
        data=json.dumps(body),
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Gemini returned {resp.status_code}: {resp.text[:300]}")

    payload = resp.json()
    try:
        text = payload["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"Unexpected Gemini response shape: {e} · {str(payload)[:300]}")

    text = text.strip()
    _CACHE[("prompt", cache_key)] = (now, text)
    return text


# ── Public wrappers ───────────────────────────────────────────────


def earnings_summary(symbol: str, context: dict) -> str:
    """Generate a structured earnings summary in Korean-friendly markdown.

    `context` should include: ticker, name, price, market_cap, pe, sector,
    forward_eps, revenue_growth_yoy, gross_margin, analyst_target_mean,
    earnings_history (list of {period, actual, estimate, surprisePercent}).
    """
    # Cache key: symbol + hash of earnings history + latest quarter (so a new
    # quarter's earnings release busts the cache)
    hist = context.get("earnings_history") or []
    latest = hist[0].get("period") if hist else "no-earnings"
    cache_key = f"earnings_summary:{symbol}:{latest}:{len(hist)}"

    prompt = f"""You are a concise financial analyst. Analyze the following earnings data for {symbol} ({context.get('name', '')}) and respond IN KOREAN with a structured markdown summary.

Data:
{json.dumps(context, ensure_ascii=False, indent=2, default=str)}

Produce these five sections, using markdown headings (## ...). Keep the ENTIRE response under 350 words.

## 1. 실적 품질
2-3 문장. 최근 4분기 Beat/Miss 추세, EPS 궤적, 일관성.

## 2. 주요 강점
2-3 bullet. 데이터에서 확인되는 잘 되고 있는 점.

## 3. 주요 우려
2-3 bullet. 데이터의 리스크나 약점.

## 4. 애널리스트 컨센서스
1-2 문장. 현재가 vs 애널리스트 목표가.

## 5. 종합 판정
1 문장. 실적 품질 총평.

Base ALL claims on the numbers provided — no speculation. If a metric is missing, say "데이터 부족" rather than guessing.
"""
    return _cached_generate(prompt, cache_key)
