"""Valuation service — fair value estimation based on yfinance + Finnhub.

Provides:
  - Core financial metrics (price, EPS TTM/fwd, revenue, margins, YoY/QoQ)
  - Multiple-based fair value (P/E × scenarios)
  - Analyst consensus (mean/median/high/low price targets, recommendation counts)
  - Scenario bands (Bear / Base / Bull)

All data comes from free APIs — no Claude/LLM required.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# 1. Core metrics
# ═══════════════════════════════════════════════════════════

@st.cache_data(ttl=1800, show_spinner=False)
def get_valuation_core(ticker: str) -> dict[str, Any]:
    """Gather core valuation inputs for a single ticker.

    Returns dict with:
      current_price, market_cap, shares_out,
      trailing_eps, forward_eps, trailing_pe, forward_pe,
      ttm_revenue, revenue_growth_yoy, earnings_growth_yoy,
      gross_margin, operating_margin,
      latest_q_revenue, q_yoy, q_qoq,
      forward_revenue_estimate,
    """
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
    except Exception as e:
        logger.warning("yfinance info failed for %s: %s", ticker, e)
        return {}

    core = {
        "ticker": ticker,
        "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "market_cap": info.get("marketCap"),
        "shares_out": info.get("sharesOutstanding"),
        "trailing_eps": info.get("trailingEps"),
        "forward_eps": info.get("forwardEps"),
        "trailing_pe": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "ttm_revenue": info.get("totalRevenue"),
        "revenue_growth_yoy": info.get("revenueGrowth"),
        "earnings_growth_yoy": info.get("earningsGrowth"),
        "gross_margin": info.get("grossMargins"),
        "operating_margin": info.get("operatingMargins"),
        "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
        "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
    }

    # Quarterly revenue YoY / QoQ
    try:
        q_fin = t.quarterly_financials
        if q_fin is not None and not q_fin.empty and "Total Revenue" in q_fin.index:
            rev = q_fin.loc["Total Revenue"]
            rev = rev.dropna().sort_index(ascending=False)
            if len(rev) >= 1:
                core["latest_q_revenue"] = float(rev.iloc[0])
                core["latest_q_label"] = rev.index[0].strftime("%Y-Q%q").replace(
                    f"Q{(rev.index[0].month - 1) // 3 + 1}", f"Q{(rev.index[0].month - 1) // 3 + 1}"
                )
            if len(rev) >= 2:
                core["q_qoq"] = float(rev.iloc[0] / rev.iloc[1] - 1)
            if len(rev) >= 5:
                core["q_yoy"] = float(rev.iloc[0] / rev.iloc[4] - 1)
    except Exception as e:
        logger.debug("quarterly_financials failed for %s: %s", ticker, e)

    # Forward revenue estimate — derived from forward P/S if available
    fwd_ps = info.get("forwardPS") or info.get("priceToSalesTrailing12Months")
    if fwd_ps and core.get("market_cap"):
        try:
            core["forward_revenue_estimate"] = float(core["market_cap"] / fwd_ps)
        except Exception:
            pass

    return core


# ═══════════════════════════════════════════════════════════
# 2. Multiple-based fair value
# ═══════════════════════════════════════════════════════════

_PE_SCENARIOS = [
    ("Conservative", 10, "Cyclical trough multiple"),
    ("Base",         12, "Historical average"),
    ("Premium",      15, "Growth / quality premium"),
    ("Bull",         18, "Peak-cycle / high growth"),
]


def build_fair_value_table(core: dict) -> pd.DataFrame:
    """Build multiple-based fair value table using forward EPS."""
    fwd_eps = core.get("forward_eps") or core.get("trailing_eps")
    cur_price = core.get("current_price")
    if not fwd_eps or fwd_eps <= 0:
        return pd.DataFrame()

    rows = []
    for label, mult, rationale in _PE_SCENARIOS:
        fv = round(fwd_eps * mult, 2)
        upside = (fv / cur_price - 1) * 100 if cur_price and cur_price > 0 else None
        rows.append({
            "Scenario": f"{label} ({mult}x)",
            "EPS Base": f"${fwd_eps:.2f}",
            "Multiple": f"{mult}x",
            "Fair Value": f"${fv:,.2f}",
            "Upside": f"{upside:+.1f}%" if upside is not None else "—",
            "Rationale": rationale,
            "_fv": fv,
            "_upside": upside or 0,
        })
    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════
# 3. Analyst consensus
# ═══════════════════════════════════════════════════════════

@st.cache_data(ttl=1800, show_spinner=False)
def get_analyst_consensus(ticker: str) -> dict[str, Any]:
    """Analyst price targets + recommendation counts.

    Tries yfinance first; falls back to Finnhub if available.
    """
    result = {
        "target_mean": None, "target_median": None,
        "target_high": None, "target_low": None,
        "n_analysts": None,
        "rec_mean": None, "rec_key": None,
        "rec_strong_buy": 0, "rec_buy": 0, "rec_hold": 0,
        "rec_sell": 0, "rec_strong_sell": 0,
    }

    # yfinance
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        result["target_mean"]   = info.get("targetMeanPrice")
        result["target_median"] = info.get("targetMedianPrice")
        result["target_high"]   = info.get("targetHighPrice")
        result["target_low"]    = info.get("targetLowPrice")
        result["n_analysts"]    = info.get("numberOfAnalystOpinions")
        result["rec_mean"]      = info.get("recommendationMean")
        result["rec_key"]       = info.get("recommendationKey")
    except Exception as e:
        logger.debug("yfinance consensus failed for %s: %s", ticker, e)

    # Recommendation breakdown via yfinance
    try:
        recs = yf.Ticker(ticker).recommendations
        if recs is not None and not recs.empty:
            latest = recs.iloc[0]  # most recent period
            result["rec_strong_buy"]  = int(latest.get("strongBuy", 0) or 0)
            result["rec_buy"]          = int(latest.get("buy", 0) or 0)
            result["rec_hold"]         = int(latest.get("hold", 0) or 0)
            result["rec_sell"]         = int(latest.get("sell", 0) or 0)
            result["rec_strong_sell"]  = int(latest.get("strongSell", 0) or 0)
    except Exception as e:
        logger.debug("yfinance recommendations failed for %s: %s", ticker, e)

    # Finnhub fallback/supplement
    try:
        import finnhub
        api_key = st.secrets.get("FINNHUB_API_KEY")
        if api_key and result.get("target_mean") is None:
            client = finnhub.Client(api_key=api_key)
            pt = client.price_target(ticker)
            if pt:
                result["target_mean"]   = pt.get("targetMean")   or result["target_mean"]
                result["target_median"] = pt.get("targetMedian") or result["target_median"]
                result["target_high"]   = pt.get("targetHigh")   or result["target_high"]
                result["target_low"]    = pt.get("targetLow")    or result["target_low"]
    except Exception as e:
        logger.debug("Finnhub consensus failed for %s: %s", ticker, e)

    return result


# ═══════════════════════════════════════════════════════════
# 4. Scenario bands
# ═══════════════════════════════════════════════════════════

@st.cache_data(ttl=1800, show_spinner=False)
def get_individual_analyst_targets(ticker: str, limit: int = 20) -> pd.DataFrame:
    """Fetch individual analyst firms' latest price targets via yfinance.

    Uses `Ticker.upgrades_downgrades` which exposes per-firm data.
    Deduplicates to the most recent entry per firm.

    Returns DataFrame with columns: date, firm, target, prior_target, action, grade.
    """
    try:
        t = yf.Ticker(ticker)
        ud = t.upgrades_downgrades
    except Exception as e:
        logger.debug("upgrades_downgrades failed for %s: %s", ticker, e)
        return pd.DataFrame()

    if ud is None or ud.empty:
        return pd.DataFrame()

    df = ud.reset_index().copy()
    # Normalize columns
    col_map = {c: c.lower() for c in df.columns}
    df = df.rename(columns=col_map)
    # Expected: gradedate, firm, tograde, fromgrade, action, pricetargetaction,
    #          currentpricetarget, priorpricetarget

    date_col = next((c for c in df.columns if "date" in c), None)
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

    # Keep only rows with a current target
    if "currentpricetarget" not in df.columns:
        return pd.DataFrame()
    df = df[df["currentpricetarget"].notna() & (df["currentpricetarget"] > 0)]
    if df.empty:
        return pd.DataFrame()

    # Most recent per firm
    if "firm" in df.columns and date_col:
        df = df.sort_values(date_col, ascending=False).drop_duplicates("firm", keep="first")

    out = pd.DataFrame({
        "date":   df[date_col].dt.strftime("%Y-%m-%d") if date_col else "",
        "firm":   df.get("firm", ""),
        "target": df["currentpricetarget"].astype(float),
        "prior":  df.get("priorpricetarget", pd.Series([None]*len(df))).astype(float),
        "action": df.get("action", ""),
        "grade":  df.get("tograde", ""),
    }).reset_index(drop=True)

    # Sort by target desc for visualization
    out = out.sort_values("target", ascending=False).head(limit)
    return out


@st.cache_data(ttl=86400, show_spinner=False)
def get_historical_pe_percentiles(ticker: str, years: int = 5) -> dict:
    """Compute a ticker's own historical P/E percentile bands.

    Uses monthly closing price / TTM EPS estimate to build a P/E time series
    over the last N years, then extracts percentile-based bands:
      Bear = P10 ~ P25
      Base = P40 ~ P60
      Bull = P75 ~ P90
      Median, Current percentile rank (vs own history)

    Fallback to fixed bands if history is too short.
    """
    default = {
        "available": False,
        "bear":   (8, 11),
        "base":   (12, 15),
        "bull":   (17, 22),
        "median": None,
        "current_pe": None,
        "current_percentile": None,
        "n_obs": 0,
    }
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period=f"{years}y", interval="1mo", auto_adjust=True)
        if hist is None or hist.empty:
            return default

        info = t.info or {}
        shares = info.get("sharesOutstanding")
        if not shares:
            return default

        NI_KEYS = (
            "Net Income",
            "Net Income Common Stockholders",
            "Net Income Continuous Operations",
            "Net Income From Continuing Operation Net Minority Interest",
        )

        # ── Gather EPS observations from multiple sources ──
        eps_points: dict = {}  # {timestamp: eps}

        # 1) Quarterly TTM rolling (short history but recent, most accurate)
        q_fin = t.quarterly_financials
        if q_fin is not None and not q_fin.empty:
            ni_row = None
            for key in NI_KEYS:
                if key in q_fin.index:
                    row = q_fin.loc[key].dropna()
                    if len(row) >= 1:
                        ni_row = row if ni_row is None else ni_row.combine_first(row)
            if ni_row is not None and len(ni_row) >= 4:
                ni = ni_row.sort_index()
                ttm = ni.rolling(4).sum().dropna()
                for ts, val in ttm.items():
                    eps_points[pd.to_datetime(ts)] = float(val) / shares

        # 2) Annual statements (longer history, fills 5-year gap)
        ann = t.financials
        if ann is not None and not ann.empty:
            ni_row_a = None
            for key in NI_KEYS:
                if key in ann.index:
                    row = ann.loc[key].dropna()
                    if len(row) >= 1:
                        ni_row_a = row if ni_row_a is None else ni_row_a.combine_first(row)
            if ni_row_a is not None:
                for ts, val in ni_row_a.items():
                    ts_pd = pd.to_datetime(ts)
                    # Only add if quarterly TTM hasn't covered this timeframe
                    if ts_pd not in eps_points:
                        eps_points[ts_pd] = float(val) / shares

        if len(eps_points) < 3:
            logger.debug("pe percentiles %s: only %d EPS points, fallback",
                         ticker, len(eps_points))
            return default

        # Build sorted time series
        ttm_eps = pd.Series(eps_points).sort_index()
        ttm_eps = ttm_eps[ttm_eps > 0]  # discard loss periods (P/E negative is meaningless)
        if len(ttm_eps) < 3:
            return default

        # Align with monthly close price: forward-fill EPS between report dates
        monthly_close = hist["Close"].copy()
        monthly_close.index = pd.to_datetime(monthly_close.index).tz_localize(None)
        # Limit monthly close to range where we have EPS
        first_eps_date = ttm_eps.index.min()
        monthly_close = monthly_close[monthly_close.index >= first_eps_date]

        eps_series = ttm_eps.reindex(monthly_close.index, method="ffill")
        pe_series = (monthly_close / eps_series).dropna()
        # Filter extreme (negative EPS gives negative/huge P/E)
        # Cap based on trimmed distribution to avoid cyclical trough distortion
        pe_series = pe_series[(pe_series > 0) & (pe_series < 100)]
        if len(pe_series) >= 10:
            # Secondary filter: drop top 5% as outliers (cyclical trough EPS spikes)
            cap = np.percentile(pe_series.values, 95)
            pe_series = pe_series[pe_series <= cap]

        if len(pe_series) < 6:  # at least 6 monthly observations
            logger.debug("pe percentiles %s: only %d P/E obs after filter, fallback",
                         ticker, len(pe_series))
            return default

        values = pe_series.values
        p10, p25, p40, p60, p75, p90 = np.percentile(
            values, [10, 25, 40, 60, 75, 90]
        )
        current_pe = info.get("trailingPE")
        if current_pe:
            pct_rank = (values < current_pe).mean() * 100
        else:
            pct_rank = None

        return {
            "available": True,
            "bear":   (round(p10, 1), round(p25, 1)),
            "base":   (round(p40, 1), round(p60, 1)),
            "bull":   (round(p75, 1), round(p90, 1)),
            "median": round(float(np.median(values)), 1),
            "current_pe": round(current_pe, 1) if current_pe else None,
            "current_percentile": round(pct_rank, 0) if pct_rank is not None else None,
            "n_obs": len(pe_series),
        }
    except Exception as e:
        logger.debug("pe percentiles failed for %s: %s", ticker, e)
        return default


def build_scenario_bands(core: dict, ticker: str = None) -> dict:
    """Bear / Base / Bull ranges derived from the ticker's own historical
    P/E percentile bands (fallback to fixed bands if history insufficient).
    """
    fwd_eps = core.get("forward_eps") or core.get("trailing_eps")
    if not fwd_eps or fwd_eps <= 0:
        return {}

    pct = get_historical_pe_percentiles(ticker) if ticker else None
    if pct and pct.get("available"):
        bear_lo, bear_hi = pct["bear"]
        base_lo, base_hi = pct["base"]
        bull_lo, bull_hi = pct["bull"]
        src_note = (f"5y history (n={pct['n_obs']}) · "
                    f"median P/E {pct['median']}x · "
                    f"current {pct['current_pe']}x (P{pct['current_percentile']:.0f})"
                    if pct["current_pe"] else "5y P/E history")
    else:
        bear_lo, bear_hi = 8, 11
        base_lo, base_hi = 12, 15
        bull_lo, bull_hi = 17, 22
        src_note = "Fallback: insufficient P/E history"

    return {
        "bear": {
            "low":  round(fwd_eps * bear_lo, 2),
            "high": round(fwd_eps * bear_hi, 2),
            "note": "Historical P10–P25 (downside band)",
            "mult_range": f"{bear_lo}x–{bear_hi}x",
        },
        "base": {
            "low":  round(fwd_eps * base_lo, 2),
            "high": round(fwd_eps * base_hi, 2),
            "note": "Historical P40–P60 (fair value range)",
            "mult_range": f"{base_lo}x–{base_hi}x",
        },
        "bull": {
            "low":  round(fwd_eps * bull_lo, 2),
            "high": round(fwd_eps * bull_hi, 2),
            "note": "Historical P75–P90 (upside band)",
            "mult_range": f"{bull_lo}x–{bull_hi}x",
        },
        "_source": src_note,
    }
