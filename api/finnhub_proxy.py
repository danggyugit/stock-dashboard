"""Finnhub REST API proxy.

Keeps the FINNHUB_API_KEY on the server so the Next.js browser bundle never
sees it. Adds a short in-process cache so repeat hits within a minute don't
re-bill Finnhub quota.

Endpoints wrapped:
  - /calendar/earnings              (earnings dates + estimates)
  - /calendar/economic              (macro events)
  - /company-news                   (per-ticker news)
  - /news?category=...              (general market news)
  - /stock/recommendation           (analyst rating trend)
  - /stock/price-target             (target price consensus)
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

FINNHUB_BASE = "https://finnhub.io/api/v1"


def _key() -> str:
    return os.environ.get("FINNHUB_API_KEY", "").strip()


# Simple TTL cache: (endpoint, sorted-params) -> (fetched_at, payload)
_CACHE: dict[tuple[str, str], tuple[float, Any]] = {}
_CACHE_TTL_SECONDS = 300  # 5 min — Finnhub free tier is 60 req/min


def _cached_get(endpoint: str, params: dict[str, Any], ttl: int = _CACHE_TTL_SECONDS) -> Any:
    """GET with TTL cache. Raises RuntimeError on any HTTP-level failure."""
    key = _key()
    if not key:
        raise RuntimeError("FINNHUB_API_KEY not configured on the server.")

    # Cache key excludes the token but includes all other params.
    params_for_call = {**params, "token": key}
    cache_key_params = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    cache_key = (endpoint, cache_key_params)

    now = time.time()
    hit = _CACHE.get(cache_key)
    if hit and (now - hit[0]) < ttl:
        return hit[1]

    url = f"{FINNHUB_BASE}{endpoint}"
    resp = requests.get(url, params=params_for_call, timeout=15)
    if resp.status_code != 200:
        raise RuntimeError(f"Finnhub {endpoint} returned {resp.status_code}: {resp.text[:200]}")

    payload = resp.json()
    _CACHE[cache_key] = (now, payload)
    return payload


# ── Public wrappers ───────────────────────────────────────────────


def quote(symbol: str) -> dict:
    """Real-time-ish quote (15-min delayed on free tier).

    Returns {c: current, d: change, dp: percent change, h: high,
    l: low, o: open, pc: prev close, t: unix timestamp}.

    Cached 25s — matches typical 30s poll interval, keeps us well
    under the 60 req/min free-tier limit even with several symbols.
    """
    return _cached_get("/quote", {"symbol": symbol}, ttl=25)


def earnings_calendar(from_date: str, to_date: str, symbol: str | None = None) -> list[dict]:
    """Upcoming earnings between two ISO dates (max ~1 month window)."""
    params: dict[str, Any] = {"from": from_date, "to": to_date}
    if symbol:
        params["symbol"] = symbol
    data = _cached_get("/calendar/earnings", params, ttl=1800)  # 30 min
    return data.get("earningsCalendar") or []


def economic_calendar(from_date: str, to_date: str) -> list[dict]:
    """Macro events (CPI, FOMC, NFP, etc.)."""
    data = _cached_get("/calendar/economic", {"from": from_date, "to": to_date}, ttl=1800)
    # Finnhub returns the list under either key depending on tier/version.
    return data.get("economicCalendar") or data.get("result") or []


def company_news(symbol: str, from_date: str, to_date: str) -> list[dict]:
    """Per-ticker news."""
    return _cached_get(
        "/company-news",
        {"symbol": symbol, "from": from_date, "to": to_date},
        ttl=600,  # 10 min
    ) or []


def market_news(category: str = "general") -> list[dict]:
    """General market news."""
    return _cached_get("/news", {"category": category}, ttl=600) or []


def recommendation_trend(symbol: str) -> list[dict]:
    """Analyst rating distribution (strongBuy/buy/hold/sell/strongSell) by month."""
    return _cached_get("/stock/recommendation", {"symbol": symbol}, ttl=3600) or []


def price_target(symbol: str) -> dict:
    """Analyst price target consensus (target{Low,Mean,Median,High})."""
    return _cached_get("/stock/price-target", {"symbol": symbol}, ttl=3600) or {}


def earnings_surprise(symbol: str) -> list[dict]:
    """Last 4 quarters of actual vs estimate EPS with surprise%.
    Response items: {actual, estimate, period, quarter, surprise, surprisePercent, symbol, year}.
    """
    data = _cached_get("/stock/earnings", {"symbol": symbol}, ttl=3600)
    # Finnhub returns a bare list here (unlike calendar endpoints)
    if isinstance(data, list):
        return data
    return []


def insider_transactions(symbol: str, from_date: str | None = None, to_date: str | None = None) -> list[dict]:
    """SEC Form 4 insider transactions for a ticker (default: last 6 months)."""
    params: dict[str, Any] = {"symbol": symbol}
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date
    data = _cached_get("/stock/insider-transactions", params, ttl=1800)
    # Finnhub returns {data: [...], symbol}
    if isinstance(data, dict):
        return data.get("data") or []
    return []


def basic_metrics(symbol: str) -> dict:
    """Comprehensive metric snapshot — growth rates, margins, valuation multiples,
    dividend info, all in one call. Cache 6h since the metrics move slowly."""
    data = _cached_get("/stock/metric", {"symbol": symbol, "metric": "all"}, ttl=6 * 3600)
    if isinstance(data, dict):
        return data.get("metric") or {}
    return {}


def financials_reported(symbol: str, freq: str = "quarterly") -> list[dict]:
    """SEC-reported financial statements (Income/Balance/CashFlow).

    freq = "quarterly" | "annual". Returns list of filings (most recent first),
    each with `report` = {ic, bs, cf} where each sub-object is a list of
    {concept, value, unit, label} line items.
    """
    data = _cached_get(
        "/stock/financials-reported",
        {"symbol": symbol, "freq": freq},
        ttl=6 * 3600,
    )
    if isinstance(data, dict):
        return data.get("data") or []
    return []


def dividend_history(symbol: str, from_date: str, to_date: str) -> list[dict]:
    """Historical dividend payments between two ISO dates."""
    data = _cached_get(
        "/stock/dividend",
        {"symbol": symbol, "from": from_date, "to": to_date},
        ttl=6 * 3600,
    )
    if isinstance(data, list):
        return data
    return []


def eps_estimate(symbol: str, freq: str = "quarterly") -> list[dict]:
    """Analyst EPS estimates (past + upcoming quarters).

    freq = "quarterly" | "annual". Each row: {period, epsAvg, epsHigh, epsLow,
    numberAnalysts}. Comparing past periods' estimates to actuals shows
    "revision trend" (analysts revising up = strong signal).
    """
    data = _cached_get(
        "/stock/eps-estimate",
        {"symbol": symbol, "freq": freq},
        ttl=3600,
    )
    if isinstance(data, dict):
        return data.get("data") or []
    return []
