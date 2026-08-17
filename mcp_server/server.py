"""Stock Dashboard MCP Server — Phase 1 (5 core tools).

Exposes our existing data/valuation services as MCP tools so Claude can
call them directly in natural-language conversations.

Tools:
  1. get_quote              — price, market cap, 52w range, day change
  2. get_fundamentals       — P/E, P/B, ROE, EPS, beta, dividend yield, D/E
  3. get_analyst_consensus  — mean/median/high/low target, recommendation
  4. get_scenario_bands     — Bear/Base/Bull price bands (P/E percentile)
  5. search_stocks          — ticker/name search
  6. compare_stocks         — side-by-side multi-ticker comparison
  7. screen_stocks          — filter by fundamental criteria
  8. get_analyst_targets    — per-firm analyst price targets
  9. get_pe_rank            — historical P/E percentile rank
  10. get_vix               — VIX level + trend
  11. get_fear_greed        — Fear & Greed Index
  12. get_market_breadth    — S&P 500 vs 200-day MA
  13. get_risk_on_off       — XLY/XLP risk sentiment ratio
  14. get_sector_rotation   — 1-week/1-month sector ETF returns
  15. get_macro_snapshot    — Fed, yields, CPI, PCE, M2
  16. get_commodities       — DXY, Gold, WTI
  17. get_news              — news headlines with sentiment
  18. get_earnings_events   — upcoming earnings
  19. get_economic_events   — economic calendar (CPI, FOMC, NFP...)

Run locally via Claude Desktop (stdio transport).
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any


# ── Streamlit stubs ────────────────────────────────────────────────────────
# Services import streamlit for @st.cache_data / st.secrets.
# We replace them with no-ops so the services work outside Streamlit.

class _NullCM:
    def __enter__(self): return self
    def __exit__(self, *a, **kw): pass


def _passthrough_decorator(*args, **kwargs):
    """Drop-in for @st.cache_data / @st.cache_resource."""
    if len(args) == 1 and callable(args[0]):
        return args[0]
    return _passthrough_decorator


class _Secrets(dict):
    def get(self, key, default=None):
        return os.environ.get(key, super().get(key, default))

    def __getattr__(self, key):
        return os.environ.get(key)


class _StreamlitStub:
    cache_data = staticmethod(_passthrough_decorator)
    cache_resource = staticmethod(_passthrough_decorator)
    secrets = _Secrets({
        "FINNHUB_API_KEY": os.environ.get("FINNHUB_API_KEY", ""),
    })

    @staticmethod
    def markdown(*a, **kw): pass

    @staticmethod
    def caption(*a, **kw): pass


sys.modules.setdefault("streamlit", _StreamlitStub())  # type: ignore[arg-type]
import streamlit as st  # noqa: E402 — must come after stub injection

st.cache_data = _passthrough_decorator      # type: ignore[assignment]
st.cache_resource = _passthrough_decorator  # type: ignore[assignment]
st.secrets = _Secrets({                     # type: ignore[assignment]
    "FINNHUB_API_KEY": os.environ.get("FINNHUB_API_KEY", ""),
})


# ── Path setup ─────────────────────────────────────────────────────────────
_REPO = Path(__file__).resolve().parent.parent
_STREAMLIT_APP = _REPO / "streamlit_app"
sys.path.insert(0, str(_STREAMLIT_APP))


# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("stock-dashboard-mcp")


# ── Service imports ────────────────────────────────────────────────────────
from services.cache_loader import (       # noqa: E402
    get_cached_fundamentals,
    get_cached_heatmap,
    get_cached_stocks,
)
from services.calendar_service import (   # noqa: E402
    get_earnings_events as _svc_earnings_events,
    get_economic_events as _svc_econ_events,
)
from services.macro_service import (      # noqa: E402
    get_core_pce as _svc_core_pce,
    get_cpi as _svc_cpi,
    get_dxy as _svc_dxy,
    get_fed_funds_rate as _svc_fed_rate,
    get_gold as _svc_gold,
    get_money_supply as _svc_money_supply,
    get_oil as _svc_oil,
    get_treasury_yields as _svc_yields,
)
from services.sentiment_service import (  # noqa: E402
    get_fear_greed as _svc_fear_greed,
    get_market_breadth as _svc_market_breadth,
    get_market_news as _svc_market_news,
    get_risk_on_off as _svc_risk_on_off,
    get_sector_returns as _svc_sector_returns,
    get_stock_news as _svc_stock_news,
    get_vix_history as _svc_vix_history,
)
from services.valuation_service import (  # noqa: E402
    build_scenario_bands as _svc_build_scenario_bands,
    get_analyst_consensus as _svc_get_analyst_consensus,
    get_historical_pe_percentiles as _svc_get_pe_percentiles,
    get_individual_analyst_targets as _svc_get_individual_analyst_targets,
    get_valuation_core,
)


# ── MCP server ─────────────────────────────────────────────────────────────
from mcp.server.fastmcp import FastMCP    # noqa: E402

mcp = FastMCP("stock-dashboard")


# ── Helpers ────────────────────────────────────────────────────────────────

def _json(obj: Any) -> Any:
    """Recursively convert pandas/numpy types to JSON-safe Python types."""
    import numpy as np
    import pandas as pd

    if isinstance(obj, dict):
        return {k: _json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json(v) for v in obj]
    if isinstance(obj, pd.DataFrame):
        return obj.to_dict(orient="records")
    if isinstance(obj, pd.Series):
        return obj.tolist()
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return None if np.isnan(obj) else float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if hasattr(obj, "item"):  # generic numpy scalar
        return obj.item()
    return obj


def _latest_with_trend(df, value_col: str, days: int = 30) -> dict:
    """Return {value, min, max, avg, trend} from a date-indexed DataFrame."""
    import numpy as np

    if df is None or df.empty:
        return {}
    df = df.dropna(subset=[value_col]).tail(days)
    if df.empty:
        return {}
    vals = df[value_col].values.astype(float)
    cur = float(vals[-1])
    avg = float(np.mean(vals))
    if len(vals) >= 5:
        slope = float(np.polyfit(range(len(vals)), vals, 1)[0])
        trend = "up" if slope > 0.05 else ("down" if slope < -0.05 else "flat")
    else:
        trend = "flat"
    return {
        "current": round(cur, 4),
        "min": round(float(vals.min()), 4),
        "max": round(float(vals.max()), 4),
        "avg": round(avg, 4),
        "trend": trend,
    }


# ══════════════════════════════════════════════════════════════════════════
# Stock tools
# ══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def get_quote(ticker: str) -> dict:
    """Get current quote: price, market cap, 52-week range, day change.

    Args:
        ticker: Stock symbol (e.g. "NVDA", "AAPL", "BRK-B").

    Returns:
        dict with current_price, market_cap, change_pct, 52w high/low, volume
    """
    ticker = ticker.upper()
    try:
        core = get_valuation_core(ticker)
    except Exception as e:
        return {"error": str(e)}

    if not core:
        return {"error": "No data"}

    import yfinance as yf
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:
        info = {}

    return _json({
        "ticker": ticker,
        "current_price": core.get("current_price"),
        "market_cap": core.get("market_cap"),
        "change_pct": info.get("regularMarketChangePercent"),
        "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
        "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
        "volume": info.get("regularMarketVolume"),
        "ttm_revenue": core.get("ttm_revenue"),
    })


@mcp.tool()
def get_fundamentals(ticker: str) -> dict:
    """Get core fundamentals: P/E, P/B, P/S, EPS, ROE, D/E, dividend, beta.

    Prefers GitHub-cached `fundamentals.json` (fresh daily) then falls back
    to live yfinance.

    Args:
        ticker: Stock symbol.
    """
    ticker = ticker.upper()

    # Try GitHub cache first
    try:
        cache = get_cached_fundamentals() or {}
        if ticker in cache:
            return _json({"ticker": ticker, "source": "cache", **cache[ticker]})
    except Exception:
        pass

    # Live fallback
    try:
        core = get_valuation_core(ticker)
    except Exception as e:
        return {"error": str(e)}

    import yfinance as yf
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:
        info = {}

    return _json({
        "ticker": ticker,
        "source": "live",
        "trailing_pe": core.get("trailing_pe"),
        "forward_pe": core.get("forward_pe"),
        "pb_ratio": info.get("priceToBook"),
        "ps_ratio": info.get("priceToSalesTrailing12Months"),
        "trailing_eps": core.get("trailing_eps"),
        "ttm_eps": core.get("trailing_eps"),
        "forward_eps": core.get("forward_eps"),
        "roe": info.get("returnOnEquity"),
        "roa": info.get("returnOnAssets"),
        "debt_to_equity": info.get("debtToEquity"),
        "dividend_yield": info.get("dividendYield"),
        "beta": info.get("beta"),
        "gross_margin": core.get("gross_margin"),
        "operating_margin": core.get("operating_margin"),
        "earnings_growth_yoy": core.get("earnings_growth_yoy"),
    })


@mcp.tool()
def get_analyst_consensus(ticker: str) -> dict:
    """Get Wall Street analyst consensus: target prices + recommendation breakdown.

    Returns mean/median/high/low target prices, number of analysts,
    and Strong Buy/Buy/Hold/Sell counts from yfinance/Finnhub.

    Args:
        ticker: Stock symbol.
    """
    ticker = ticker.upper()
    try:
        core = get_valuation_core(ticker)
        cons = _svc_get_analyst_consensus(ticker)
    except Exception as e:
        return {"error": str(e)}

    cur = core.get("current_price") if core else None
    mean = cons.get("target_mean")
    high = cons.get("target_high")

    result = {
        "ticker": ticker,
        "current_price": cur,
        **cons,
    }
    if cur and mean:
        result["mean_upside_pct"] = round((mean / cur - 1) * 100, 1)
    if cur and high:
        result["high_upside_pct"] = round((high / cur - 1) * 100, 1)

    return _json(result)


@mcp.tool()
def get_scenario_bands(ticker: str) -> dict:
    """Get Bear/Base/Bull price bands based on ticker's own 5-year P/E percentiles.

    Bear  = P10–P25 (downside band)
    Base  = P40–P60 (fair value range)
    Bull  = P75–P90 (upside band)

    Uses Forward EPS × percentile multiples. Falls back to fixed bands if
    history insufficient.

    Args:
        ticker: Stock symbol.
    """
    ticker = ticker.upper()
    try:
        core = get_valuation_core(ticker)
    except Exception as e:
        return {"error": str(e)}

    if not core:
        return {"error": "No valuation core data"}

    fwd_eps = core.get("forward_eps") or core.get("trailing_eps")
    if not fwd_eps:
        return {"error": "Forward EPS unavailable"}

    try:
        bands = _svc_build_scenario_bands(core, ticker=ticker)
    except Exception as e:
        return {"error": str(e)}

    cur = core.get("current_price")
    base_mid = None
    if bands.get("base"):
        b = bands["base"]
        base_mid = (b.get("low", 0) + b.get("high", 0)) / 2 if isinstance(b, dict) else None

    result = {
        "ticker": ticker,
        "current_price": cur,
        "forward_eps": fwd_eps,
        "trailing_eps": core.get("trailing_eps"),
        **bands,
    }
    if cur and base_mid:
        result["mid_upside_pct"] = round((base_mid / cur - 1) * 100, 1)

    return _json(result)


@mcp.tool()
def search_stocks(query: str, limit: int = 10) -> dict:
    """Search S&P 1500 stocks by ticker or company name.

    Args:
        query: Search term (ticker or name fragment, e.g. "NVDA", "Micron").
        limit: Max number of results (default 10).

    Returns:
        List of {ticker, name, sector, cap_tier, market_cap}
    """
    q = query.upper()
    try:
        tickers = get_cached_stocks() or []
    except Exception as e:
        return {"error": str(e)}

    matches = [
        t for t in tickers
        if q in t.get("ticker", "").upper() or q in t.get("name", "").upper()
    ]
    matches.sort(key=lambda x: x.get("market_cap") or 0, reverse=True)

    return _json({
        "query": query,
        "count": len(matches),
        "results": [
            {
                "ticker": t.get("ticker"),
                "name": t.get("name"),
                "sector": t.get("sector"),
                "cap_tier": t.get("cap_tier"),
                "market_cap": t.get("market_cap"),
            }
            for t in matches[:limit]
        ],
    })


@mcp.tool()
def compare_stocks(tickers: list[str]) -> dict:
    """Compare multiple tickers side-by-side: price, market cap, P/E, margins,
    analyst consensus, and scenario bands.

    Great for: "A vs B vs C — which looks most attractive?"

    Args:
        tickers: List of stock symbols (max 8 recommended).

    Returns:
        {tickers: [...], rows: [{ticker, current_price, pe, ...}, ...]}
    """
    if not tickers:
        return {"error": "No tickers provided"}

    rows = []
    for tkr in tickers[:8]:
        tkr = tkr.upper()
        try:
            core = get_valuation_core(tkr) or {}
            cons = _svc_get_analyst_consensus(tkr) or {}
            bands = _svc_build_scenario_bands(core, ticker=tkr) if core else {}
        except Exception:
            core, cons, bands = {}, {}, {}

        base = bands.get("base", {})
        base_high = base.get("high") if isinstance(base, dict) else None

        rows.append({
            "ticker": tkr,
            "current_price": core.get("current_price"),
            "trailing_pe": core.get("trailing_pe"),
            "pe_ratio": core.get("trailing_pe"),
            "pb_ratio": None,
            "forward_eps": core.get("forward_eps"),
            "gross_margin": core.get("gross_margin"),
            "operating_margin": core.get("operating_margin"),
            "earnings_growth_yoy": core.get("earnings_growth_yoy"),
            "market_cap": core.get("market_cap"),
            "target_mean": cons.get("target_mean"),
            "base_high": base_high,
            "rec_key": cons.get("rec_key"),
        })

    return _json({"tickers": [r["ticker"] for r in rows], "rows": rows})


@mcp.tool()
def screen_stocks(
    sector: str | None = None,
    min_market_cap: float | None = None,
    max_market_cap: float | None = None,
    min_pe: float | None = None,
    max_pe: float | None = None,
    min_roe: float | None = None,
    min_dividend_yield: float | None = None,
    max_debt_to_equity: float | None = None,
    limit: int = 25,
) -> dict:
    """Filter S&P 1500 stocks by fundamental criteria.

    All filters are optional — only non-None filters are applied. Uses the
    GitHub-cached fundamentals.json (refreshed daily).

    Args:
        sector: Exact GICS sector name, e.g. "Information Technology",
                "Health Care", "Financials", "Consumer Discretionary".
        min_market_cap / max_market_cap: Dollar amount (e.g. 10_000_000_000 for $10B).
        min_pe / max_pe: P/E ratio bounds.
        min_roe: Minimum Return on Equity (decimal, e.g. 0.15 for 15%).
        min_dividend_yield: Minimum yield (decimal, e.g. 0.03 for 3%).
        max_debt_to_equity: Maximum D/E ratio.
        limit: Max results (default 25).

    Returns:
        {count, matches: [{ticker, name, sector, market_cap, pe, pb, roe, ...}]}
    """
    try:
        cache = get_cached_fundamentals() or {}
        tickers_list = get_cached_stocks() or []
    except Exception as e:
        return {"error": str(e)}

    name_map = {t["ticker"]: t.get("name", "") for t in tickers_list if "ticker" in t}
    matches = []

    for tkr, data in cache.items():
        mcap = data.get("market_cap") or 0
        pe = data.get("trailing_pe") or data.get("pe_ratio")
        roe = data.get("roe") or data.get("return_on_equity")
        dy = data.get("dividend_yield")
        de = data.get("debt_to_equity")
        sec = data.get("sector", "")

        if sector and sector.lower() not in sec.lower():
            continue
        if min_market_cap and mcap < min_market_cap:
            continue
        if max_market_cap and mcap > max_market_cap:
            continue
        if min_pe and (not pe or pe < min_pe):
            continue
        if max_pe and (pe and pe > max_pe):
            continue
        if min_roe and (not roe or roe < min_roe):
            continue
        if min_dividend_yield and (not dy or dy < min_dividend_yield):
            continue
        if max_debt_to_equity and (de and de > max_debt_to_equity):
            continue

        matches.append({
            "ticker": tkr,
            "name": name_map.get(tkr, data.get("name", "")),
            "sector": sec,
            "market_cap": mcap,
            "pe_ratio": pe,
            "pb_ratio": data.get("pb_ratio") or data.get("price_to_book"),
            "roe": roe,
            "dividend_yield": dy,
            "debt_to_equity": de,
        })

    matches.sort(key=lambda x: x.get("market_cap") or 0, reverse=True)

    return _json({"count": len(matches), "matches": matches[:limit]})


@mcp.tool()
def get_analyst_targets(ticker: str, limit: int = 20) -> dict:
    """Get per-firm analyst price targets (KeyBanc, JPMorgan, Rosenblatt, etc).

    Unlike `get_analyst_consensus` which returns aggregate stats, this returns
    each firm's most recent target with the report date.

    Args:
        ticker: Stock symbol.
        limit: Max firms to return (default 20, sorted by target DESC).

    Returns:
        {ticker, current_price, count, firms: [{date, firm, target, prior, action, grade}]}
    """
    ticker = ticker.upper()
    try:
        core = get_valuation_core(ticker) or {}
        df = _svc_get_individual_analyst_targets(ticker, limit=limit)
    except Exception as e:
        return {"error": str(e)}

    cur = core.get("current_price")
    firms = []
    if df is not None and not df.empty:
        for row in df.itertuples():
            entry = {
                "date": str(getattr(row, "date", "")),
                "firm": getattr(row, "firm", None),
                "target": getattr(row, "target", None),
                "prior": getattr(row, "prior", None),
                "action": getattr(row, "action", None),
                "grade": getattr(row, "grade", None),
            }
            if cur and entry["target"]:
                entry["upside_pct"] = round((entry["target"] / cur - 1) * 100, 1)
            firms.append(entry)

    return _json({
        "ticker": ticker,
        "current_price": cur,
        "count": len(firms),
        "firms": firms,
    })


@mcp.tool()
def get_pe_rank(ticker: str) -> dict:
    """Quick check: where does the current P/E rank vs the ticker's own 5-year history?

    Returns:
        - current P/E, historical median, min, max
        - current rank as percentile (0-100, higher = more expensive)
        - P10/P25/P40/P60/P75/P90 reference points

    Args:
        ticker: Stock symbol.
    """
    ticker = ticker.upper()
    try:
        result = _svc_get_pe_percentiles(ticker)
    except Exception as e:
        return {"error": str(e)}

    if not result.get("available"):
        return {"ticker": ticker, "available": False, "note": "Insufficient history"}

    return _json({"ticker": ticker, **result})


# ══════════════════════════════════════════════════════════════════════════
# Market sentiment tools
# ══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def get_vix(days: int = 30) -> dict:
    """Get VIX (volatility index) current level + recent trend.

    Interpretation:
      < 15  → Complacency (very calm)
      15-20 → Normal
      20-30 → Elevated fear
      > 30  → High fear / stress

    Args:
        days: Lookback window (default 30).

    Returns:
        {current, min, max, avg, trend (up/down/flat), label}
    """
    try:
        df = _svc_vix_history(days=max(days, 30))
    except Exception as e:
        return {"error": str(e)}

    if df is None or df.empty:
        return {"error": "VIX data unavailable"}

    result = _latest_with_trend(df, "VIX", days=days)
    if not result:
        return {"error": "Insufficient VIX data"}

    cur = result["current"]
    if cur < 15:
        label = "Complacency"
    elif cur < 20:
        label = "Normal"
    elif cur < 30:
        label = "Elevated"
    else:
        label = "High fear"

    return {**result, "label": label}


@mcp.tool()
def get_fear_greed() -> dict:
    """Get the Fear & Greed Index (0-100) based on VIX, momentum, and volume.

    Interpretation:
      0-20  → Extreme Fear
      20-40 → Fear
      40-60 → Neutral
      60-80 → Greed
      80-100 → Extreme Greed
    """
    try:
        data = _svc_fear_greed()
    except Exception as e:
        return {"error": str(e)}

    return _json(data or {})


@mcp.tool()
def get_market_breadth() -> dict:
    """Get S&P 500 market breadth: current level vs 200-day moving average.

    Positive spread = market above long-term trend (bullish).
    Negative = below trend (bearish).
    """
    try:
        data = _svc_market_breadth()
    except Exception as e:
        return {"error": str(e)}

    if not data:
        return {"error": "Breadth data unavailable"}

    cur = data.get("current_close") or data.get("current_price")
    sma = data.get("current_sma200") or data.get("sma200")
    above = None
    if cur and sma:
        above = round((cur / sma - 1) * 100, 2)

    return _json({
        **data,
        "above_pct": above,
        "label": "Bullish (above 200d)" if (above or 0) > 0 else "Bearish (below 200d)",
    })


@mcp.tool()
def get_risk_on_off() -> dict:
    """Get Risk-On/Off indicator via XLY (Consumer Discretionary) / XLP
    (Consumer Staples) ratio.

    Rising ratio = Risk-On (investors prefer cyclicals → market bullish).
    Falling = Risk-Off (flight to defensives → cautious market).
    """
    try:
        df = _svc_risk_on_off()
    except Exception as e:
        return {"error": str(e)}

    if df is None or df.empty:
        return {"error": "Risk-On/Off data unavailable"}

    ratio_col = "ratio" if "ratio" in df.columns else df.columns[-1]
    result = _latest_with_trend(df, ratio_col)
    if not result:
        return {"ticker": "XLY/XLP", "error": "Insufficient data"}

    avg = result.get("avg", 0)
    cur = result.get("current", 0)
    mode = "Risk-On" if cur >= avg else "Risk-Off"
    label = "Above avg (Risk-On)" if cur >= avg else "Below avg (Risk-Off)"

    return {
        "ticker": "XLY/XLP",
        **result,
        "mode": mode,
        "label": label,
    }


@mcp.tool()
def get_sector_rotation() -> dict:
    """Get 1-week and 1-month returns for the 11 GICS sector ETFs.

    Tells you which sectors are leading/lagging the market right now.
    """
    try:
        df = _svc_sector_returns()
    except Exception as e:
        return {"error": str(e)}

    if df is None or df.empty:
        return {"error": "Sector data unavailable"}

    records = df.to_dict(orient="records") if hasattr(df, "to_dict") else df
    # sort by 1M return descending
    try:
        records = sorted(records, key=lambda x: x.get("1M %") or x.get("1m_pct") or 0, reverse=True)
    except Exception:
        pass

    return _json({"sectors": records})


# ══════════════════════════════════════════════════════════════════════════
# Macro tools
# ══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def get_macro_snapshot() -> dict:
    """Get a macro snapshot: Fed Funds, Treasury yields + curve, CPI, Core PCE,
    and M1/M2 money supply.

    One call returns everything needed for a macro context briefing.
    """
    result: dict[str, Any] = {}

    # Fed Funds Rate
    try:
        df = _svc_fed_rate()
        if df is not None and not df.empty:
            ffr = df.dropna(subset=["value"]).iloc[-1]
            result["fed_funds_rate"] = {"value": round(float(ffr["value"]), 3), "date": str(ffr["date"])}
    except Exception as e:
        result["fed_funds_rate"] = {"error": str(e)}

    # Treasury yields
    try:
        df = _svc_yields()
        if df is not None and not df.empty:
            latest = df.dropna().iloc[-1]
            yields = {col: round(float(latest[col]), 4) for col in df.columns if col != "date" and col in latest.index}
            two_yr = yields.get("2Y") or yields.get("DGS2")
            ten_yr = yields.get("10Y") or yields.get("DGS10")
            spread = None
            if two_yr and ten_yr:
                spread = round(ten_yr - two_yr, 4)
            result["treasury_yields"] = {
                "yields": yields,
                "2y10y_spread": spread,
                "curve_label": "Inverted ⚠️" if (spread or 0) < 0 else "Normal",
            }
    except Exception as e:
        result["treasury_yields"] = {"error": str(e)}

    # CPI
    try:
        df = _svc_cpi()
        if df is not None and not df.empty:
            r = df.dropna(subset=["value"]).iloc[-1]
            result["cpi_yoy"] = {"value": round(float(r["value"]), 3), "date": str(r["date"])}
    except Exception as e:
        result["cpi_yoy"] = {"error": str(e)}

    # Core PCE
    try:
        df = _svc_core_pce()
        if df is not None and not df.empty:
            r = df.dropna(subset=["value"]).iloc[-1]
            result["core_pce_yoy"] = {"value": round(float(r["value"]), 3), "date": str(r["date"])}
    except Exception as e:
        result["core_pce_yoy"] = {"error": str(e)}

    # Money supply (get_money_supply returns columns date/M1/M2 in $T)
    try:
        df = _svc_money_supply()
        if df is not None and not df.empty:
            r = df.dropna(subset=["M2"]).iloc[-1]
            entry = {"m2_trillions": round(float(r["M2"]), 2),
                     "m1_trillions": round(float(r["M1"]), 2),
                     "date": str(r["date"])}
            if len(df) >= 13:
                entry["m2_yoy_pct"] = round((df["M2"].iloc[-1] / df["M2"].iloc[-13] - 1) * 100, 2)
            result["money_supply"] = entry
    except Exception as e:
        result["money_supply"] = {"error": str(e)}

    return _json(result)


@mcp.tool()
def get_commodities() -> dict:
    """Get current levels of DXY (USD index), Gold, and WTI Oil plus short-term
    trends.
    """
    result: dict[str, Any] = {}

    for key, fn, label in [
        ("dxy", _svc_dxy, "DXY"),
        ("gold", _svc_gold, "Gold"),
        ("oil_wti", _svc_oil, "WTI Oil"),
    ]:
        try:
            df = fn()
            if df is None or df.empty:
                result[key] = {"error": f"{label} data unavailable"}
                continue
            val_col = [c for c in df.columns if c != "date"][0]
            info = _latest_with_trend(df, val_col)
            if not info:
                result[key] = {"error": "Insufficient data"}
            else:
                result[key] = {"label": label, **info}
        except Exception as e:
            result[key] = {"error": str(e)}

    return _json(result)


# ══════════════════════════════════════════════════════════════════════════
# Quant / SEC / Liquidity tools (synced with aiquantlab.streamlit.app)
# ══════════════════════════════════════════════════════════════════════════

_PRESET_IDS = ["it_momentum", "it_invvol", "it_equal", "it_invvol_regime", "it_ensemble"]


@mcp.tool()
def get_ai_picks(preset: str = "it_momentum") -> dict:
    """Get today's AI-recommended stocks from the daily preset backtests
    (AI Quant Lab — ML ensemble ranking of IT-sector large caps, refreshed
    daily at 11:00 KST).

    Args:
        preset: One of "it_momentum" (momentum-weighted, highest CAGR),
                "it_invvol" (inverse-volatility), "it_equal" (equal weight),
                "it_invvol_regime" (with HMM regime cash overlay),
                "it_ensemble" (RF+XGB+LGBM ensemble).

    Returns:
        {preset, name, cagr_pct, sharpe, max_dd_pct, updated_at, regime,
         cash_pct, picks: [{ticker, weight, Mom_1m, Mom_3m, Mom_12m}],
         next_ranked: [...]}  — picks are today's buy list.
    """
    from services.cache_loader import load_cache_file

    pid = preset.lower().strip()
    if pid not in _PRESET_IDS:
        return {"error": f"Unknown preset. Choose from {_PRESET_IDS}"}

    data = load_cache_file(f"backtests/{pid}.json")
    if not data:
        return {"error": "Preset cache unavailable"}

    summary = data.get("summary", {})
    picks = data.get("today_picks") or []
    ranking = data.get("today_full_ranking") or []
    pick_set = {p.get("ticker") for p in picks}
    next_ranked = [r for r in ranking if r.get("ticker") not in pick_set][:5]

    def _slim(p: dict) -> dict:
        return {k: p.get(k) for k in ("ticker", "weight", "Mom_1m", "Mom_3m", "Mom_12m")}

    return _json({
        "preset": pid,
        "name": data.get("name"),
        "cagr_pct": summary.get("cagr_pct"),
        "sharpe": summary.get("sharpe"),
        "max_dd_pct": summary.get("max_dd_pct"),
        "picks_as_of": data.get("today_picks_at"),
        "updated_at": data.get("updated_at"),
        "regime": data.get("today_regime"),
        "cash_pct": data.get("today_cash_ratio_pct"),
        "picks": [_slim(p) for p in sorted(picks, key=lambda x: x.get("weight") or 0, reverse=True)],
        "next_ranked": [_slim(r) for r in next_ranked],
        "note": "Backtested strategy output, not investment advice.",
    })


@mcp.tool()
def get_whale_holdings(manager: str, top_n: int = 15) -> dict:
    """Get a famous investor's latest 13F portfolio (from SEC EDGAR filings,
    cached daily). Covers 20 managers: Warren Buffett, Bill Ackman, Michael
    Burry, David Tepper, Dan Loeb, David Einhorn, Stan Druckenmiller, Seth
    Klarman, Andreas Halvorsen, Philippe Laffont, Chase Coleman, Steve Cohen,
    Ken Griffin, Jim Simons, Stephen Mandel, Lee Ainslie, Jeffrey Ubben,
    Howard Marks, Chris Hohn, David Abrams.

    Args:
        manager: Manager or fund name (partial match OK, e.g. "buffett",
                 "Berkshire", "ackman").
        top_n: Number of top holdings to return (default 15).

    Returns:
        {manager, fund, period, filed_date, total_value_usd, n_holdings,
         holdings: [{ticker, company, pct_port, value_usd, shares}]}
    """
    from services.cache_loader import load_cache_file
    from services.sec_intelligence_service import WHALE_MANAGERS

    q = manager.lower().strip()
    match = None
    for m in WHALE_MANAGERS:
        if q in m["manager"].lower() or q in m["name"].lower():
            match = m
            break
    if not match:
        return {"error": f"Manager not found. Available: "
                         f"{[m['manager'] for m in WHALE_MANAGERS]}"}

    meta = load_cache_file("sec/_metadata.json") or {}
    period = meta.get("13f", {}).get(match["cik"], {}).get("latest_period")
    if not period:
        return {"error": "13F cache metadata unavailable for this manager"}

    data = load_cache_file(f"sec/13f/{match['cik']}_{period.replace('-', '')}.json")
    if not data:
        return {"error": "13F holdings cache unavailable"}

    holdings = data.get("holdings", [])
    total = sum(h.get("value_k", 0) for h in holdings) * 1000

    return _json({
        "manager": data.get("manager"),
        "fund": data.get("name"),
        "style": data.get("style"),
        "period": data.get("period"),
        "filed_date": data.get("filed_date"),
        "total_value_usd": total,
        "n_holdings": len(holdings),
        "holdings": [
            {
                "ticker": h.get("ticker") or None,
                "company": h.get("company"),
                "pct_port": h.get("pct_port"),
                "value_usd": h.get("value_k", 0) * 1000,
                "shares": h.get("shares"),
            }
            for h in holdings[:top_n]
        ],
    })


@mcp.tool()
def get_insider_trades(ticker: str, days: int = 180) -> dict:
    """Get recent insider (officer/director) trades for a ticker from SEC
    EDGAR Form 4 filings — live data.

    Args:
        ticker: Stock symbol.
        days: Look-back window in days (default 180).

    Returns:
        {ticker, count, buys_total_usd, sells_total_usd,
         trades: [{date, insider, role, type, shares, price, value_usd}]}
    """
    from services.insider_service import get_insider_trades as _svc_insider

    ticker = ticker.upper()
    try:
        df = _svc_insider(ticker, days=days)
    except Exception as e:
        return {"error": str(e)}

    if df is None or df.empty:
        return {"ticker": ticker, "count": 0, "trades": [],
                "note": "No insider transactions found in window"}

    buys = df[df["Type"] == "Buy"]["Value ($)"].sum()
    sells = df[df["Type"] == "Sell"]["Value ($)"].sum()
    trades = [
        {
            "date": r.get("Date"), "insider": r.get("Insider"),
            "role": r.get("Role"), "type": r.get("Type"),
            "shares": r.get("Shares"), "price": r.get("Price"),
            "value_usd": r.get("Value ($)"),
        }
        for r in df.head(30).to_dict(orient="records")
    ]

    return _json({
        "ticker": ticker, "count": len(df),
        "buys_total_usd": buys, "sells_total_usd": sells,
        "trades": trades,
    })


@mcp.tool()
def get_liquidity() -> dict:
    """Get the US market liquidity dashboard: Net Liquidity (Fed balance
    sheet − reverse repo − Treasury General Account), plus RRP, TGA, bank
    reserves, and high-yield credit spread with 4-week trends.

    Direction guide (liquidity-friendly): RRP↓, TGA↓, reserves↑, HY spread↓.
    """
    from services.macro_service import (
        get_net_liquidity, get_rrp, get_tga, get_bank_reserves, get_hy_spread,
    )

    result: dict[str, Any] = {}

    try:
        nl = get_net_liquidity()
        if nl is not None and not nl.empty:
            r = nl.iloc[-1]
            prior = nl.iloc[-5] if len(nl) >= 5 else nl.iloc[0]
            result["net_liquidity"] = {
                "trillions": round(float(r["net_liq"]), 2),
                "walcl": round(float(r["walcl"]), 2),
                "rrp": round(float(r["rrp"]), 3),
                "tga": round(float(r["tga"]), 2),
                "date": str(r["date"]),
                "chg_4w_trillions": round(float(r["net_liq"] - prior["net_liq"]), 2),
                "spx_at_date": round(float(r["spx"]), 0) if "spx" in nl.columns else None,
            }
    except Exception as e:
        result["net_liquidity"] = {"error": str(e)}

    for key, fn, invert in [("rrp", get_rrp, True), ("tga", get_tga, True),
                            ("bank_reserves", get_bank_reserves, False)]:
        try:
            df = fn()
            if df is None or df.empty:
                continue
            cur = float(df["value"].iloc[-1])
            lb = min(len(df) - 1, 20)
            chg = cur - float(df["value"].iloc[-1 - lb])
            friendly = (chg < 0) if invert else (chg > 0)
            result[key] = {
                "trillions": round(cur, 3),
                "chg_4w": round(chg, 3),
                "liquidity_friendly": bool(friendly),
                "date": str(df["date"].iloc[-1]),
            }
        except Exception as e:
            result[key] = {"error": str(e)}

    try:
        hy = get_hy_spread()
        if hy is not None and not hy.empty:
            cur = float(hy["value"].iloc[-1])
            lb = min(len(hy) - 1, 20)
            chg = cur - float(hy["value"].iloc[-1 - lb])
            result["hy_spread"] = {
                "pct": round(cur, 2), "chg_4w": round(chg, 2),
                "liquidity_friendly": bool(chg < 0),
                "stress": "elevated" if cur >= 5.0 else "normal",
                "date": str(hy["date"].iloc[-1]),
            }
    except Exception as e:
        result["hy_spread"] = {"error": str(e)}

    return _json(result)


# ══════════════════════════════════════════════════════════════════════════
# News tools
# ══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def get_news(ticker: str = "MARKET", limit: int = 10) -> dict:
    """Get recent news headlines for a ticker with sentiment labels.

    Args:
        ticker: Stock symbol. Pass "MARKET" for market-wide news.
        limit: Max articles (default 10, cap 20).

    Returns:
        {ticker, count, articles: [{headline, source, url, sentiment, sentiment_label, published_at}]}
    """
    limit = min(limit, 20)
    try:
        if ticker.upper() == "MARKET":
            articles = _svc_market_news()
        else:
            articles = _svc_stock_news(ticker.upper())
    except Exception as e:
        return {"error": str(e)}

    cleaned = []
    for a in (articles or [])[:limit]:
        entry = {
            "headline": a.get("headline"),
            "source": a.get("source"),
            "url": a.get("url"),
            "sentiment": a.get("sentiment"),
            "published_at": str(a.get("datetime") or a.get("published_at", "")),
        }
        score = a.get("sentiment", 0) or 0
        if a.get("sentiment_label"):
            entry["sentiment_label"] = a["sentiment_label"]
        elif score > 0.3:
            entry["sentiment_label"] = "Bullish"
        elif score < -0.3:
            entry["sentiment_label"] = "Bearish"
        else:
            entry["sentiment_label"] = "Neutral"
        cleaned.append(entry)

    return _json({"ticker": ticker.upper(), "count": len(cleaned), "articles": cleaned})


# ══════════════════════════════════════════════════════════════════════════
# Calendar tools
# ══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def get_earnings_events(
    from_date: str,
    to_date: str,
    tickers: list[str] | None = None,
) -> dict:
    """Get earnings announcements in a date range, optionally filtered by tickers.

    Args:
        from_date: Start date YYYY-MM-DD.
        to_date: End date YYYY-MM-DD.
        tickers: Optional list of tickers to filter (default: all).

    Returns:
        {from, to, count, events: [{ticker, company, date, eps_estimate, revenue_estimate}]}
    """
    try:
        raw = _svc_earnings_events(from_date, to_date)
    except Exception as e:
        return {"error": str(e)}

    filter_set = {t.upper() for t in (tickers or [])}
    events = []
    for ev in (raw or []):
        tkr = ev.get("ticker") or ev.get("symbol", "")
        if filter_set and tkr.upper() not in filter_set:
            continue
        events.append({
            "ticker": tkr,
            "company": ev.get("company_name") or ev.get("name", ""),
            "date": ev.get("earnings_date") or ev.get("date", ""),
            "eps_estimate": ev.get("eps_estimate"),
            "eps_actual": ev.get("eps_actual"),
            "revenue_estimate": ev.get("revenue_estimate"),
            "revenue_actual": ev.get("revenue_actual"),
        })

    return _json({"from": from_date, "to": to_date, "count": len(events), "events": events})


@mcp.tool()
def get_economic_events(
    from_date: str,
    to_date: str,
    importance: str = "all",
) -> dict:
    """Get US economic events (CPI, FOMC, NFP, etc.) in a date range.

    Args:
        from_date: Start date YYYY-MM-DD.
        to_date: End date YYYY-MM-DD.
        importance: "high" | "medium" | "all" (default "all").

    Returns:
        {from, to, count, events: [{event, date, time, actual, forecast, previous, importance}]}
    """
    try:
        raw = _svc_econ_events(from_date, to_date)
    except Exception as e:
        return {"error": str(e)}

    events = []
    for ev in (raw or []):
        imp = ev.get("impact") or ev.get("importance", "medium")
        if importance == "high" and imp != "high":
            continue
        if importance == "medium" and imp not in ("medium", "high"):
            continue
        events.append({
            "event": ev.get("event"),
            "date": ev.get("date"),
            "time": ev.get("time"),
            "actual": ev.get("actual"),
            "forecast": ev.get("forecast"),
            "previous": ev.get("previous"),
            "importance": imp,
        })

    return _json({"from": from_date, "to": to_date, "count": len(events), "events": events})


# ── Entry point ────────────────────────────────────────────────────────────
# Two transports:
#   default        — stdio (Claude Desktop local MCP config)
#   --http / env   — streamable HTTP for remote hosting (Render etc.)
#                    PORT is set by the host; MCP_PATH lets you mount the
#                    endpoint on an unguessable path as lightweight auth
#                    (e.g. MCP_PATH=/mcp-x7k2p9). Add the full URL as a
#                    custom connector in Claude settings.
if __name__ == "__main__":
    use_http = "--http" in sys.argv or os.environ.get("MCP_TRANSPORT", "").lower() in ("http", "streamable-http")
    if use_http:
        from mcp.server.transport_security import TransportSecuritySettings

        mcp.settings.host = "0.0.0.0"
        mcp.settings.port = int(os.environ.get("PORT", "8000"))
        mcp.settings.streamable_http_path = os.environ.get("MCP_PATH", "/mcp")
        mcp.settings.stateless_http = True  # survives host restarts / scale-to-zero
        # The SDK's DNS-rebinding protection only allows localhost Hosts by
        # default → public hosts (Render etc.) get "421 Invalid Host header".
        # Access control for this personal server is the unguessable MCP_PATH,
        # so disable the Host allowlist (or set MCP_ALLOWED_HOSTS to restrict).
        allowed = [h.strip() for h in os.environ.get("MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]
        mcp.settings.transport_security = (
            TransportSecuritySettings(allowed_hosts=allowed, allowed_origins=["*"])
            if allowed else
            TransportSecuritySettings(enable_dns_rebinding_protection=False)
        )
        logger.info("Starting streamable-http on :%s%s",
                    mcp.settings.port, mcp.settings.streamable_http_path)
        mcp.run(transport="streamable-http")
    else:
        mcp.run()
