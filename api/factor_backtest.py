"""Standalone factor backtest engine for the API.

Uses factor_strategies.py's rank_fn (pure functions) but computes the
feature DataFrame directly from our cached pickle data instead of the
SQLite pipeline that streamlit_app/services/factor_backtest_service.py
depends on.

Data sources (all from cache_loader.load_all_prices, load_pit, ...):
  - Daily OHLCV per ticker (for ret_1m, ret_12m, vol_90d, mom_lookback)
  - PIT financials per ticker (for pe/pb/roe/debt/dividend/margins)
  - Metadata (sector, cap_tier) for filtering
  - SPY/VIX benchmarks

Supports both price-based and fundamental strategies. Compute time
per backtest: ~5-15 seconds on Render Free (much lighter than the
AI Quant Lab ML pipeline).
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# Ensure streamlit_app is on the path so we can import factor_strategies
_REPO_ROOT = Path(__file__).resolve().parent.parent
_APP_DIR = _REPO_ROOT / "streamlit_app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

# factor_strategies is pure (only imports pandas/numpy). No streamlit deps.
from services.factor_strategies import STRATEGIES, get_strategy  # noqa: E402

import cache_loader  # noqa: E402

logger = logging.getLogger(__name__)


# ── Config / Result ────────────────────────────────────────────────


@dataclass
class FactorBacktestConfig:
    strategy_key: str
    start_date: date
    end_date: date
    rebalance_months: int = 3
    n_stocks: int = 20
    tc_pct: float = 0.3
    sector: str | None = None      # None = all sectors
    cap_tier: str | None = None     # None = all tiers


@dataclass
class FactorBacktestResult:
    strategy_name: str
    strategy_category: str
    equity_curve: list[dict]        # [{date, portfolio, spy}, ...]
    rebalance_history: list[dict]   # per-rebalance: date, picks, period_return
    metrics: dict[str, float]
    benchmark_metrics: dict[str, dict[str, float]]
    universe_size: int
    final_picks: list[str] = field(default_factory=list)
    final_picks_date: str | None = None
    warnings: list[str] = field(default_factory=list)


# ── Feature computation ────────────────────────────────────────────


def _compute_price_features(
    prices_by_ticker: dict[str, pd.DataFrame],
    as_of: pd.Timestamp,
) -> pd.DataFrame:
    """Build per-ticker features from daily prices up to `as_of`.

    Columns produced:
      close, ret_1m, ret_3m, ret_6m, ret_12m, ret_12_1, vol_90d, high_52w_dist
    """
    rows: list[dict] = []
    for ticker, df in prices_by_ticker.items():
        if df is None or df.empty:
            continue
        # Ensure index is datetime and filter up to as_of
        d = df.copy()
        if not isinstance(d.index, pd.DatetimeIndex):
            if "date" in d.columns:
                d = d.set_index("date")
            d.index = pd.to_datetime(d.index)
        d = d[d.index <= as_of]
        if len(d) < 22:
            continue
        close_col = "Close" if "Close" in d.columns else ("close" if "close" in d.columns else None)
        if close_col is None:
            continue
        closes = d[close_col].dropna()
        if len(closes) < 22:
            continue

        cur = float(closes.iloc[-1])

        def _ret(days: int) -> float | None:
            if len(closes) <= days:
                return None
            past = closes.iloc[-1 - days]
            if past <= 0:
                return None
            return cur / past - 1.0

        ret_1m = _ret(21)
        ret_3m = _ret(63)
        ret_6m = _ret(126)
        ret_12m = _ret(252)
        # Momentum 12-1 (Jegadeesh-Titman): 12m return excluding the last month
        if ret_12m is not None and ret_1m is not None:
            ret_12_1 = ((1 + ret_12m) / (1 + ret_1m)) - 1
        else:
            ret_12_1 = None

        # 90-day realized vol (annualized)
        daily_ret = closes.pct_change().dropna()
        vol_90d = float(daily_ret.iloc[-min(90, len(daily_ret)):].std() * np.sqrt(252)) if len(daily_ret) >= 20 else None

        # 52W distance from high (positive = above, negative = below)
        window = closes.iloc[-min(252, len(closes)):]
        high_52w = float(window.max()) if len(window) > 0 else None
        high_52w_dist = ((cur - high_52w) / high_52w) if (high_52w and high_52w > 0) else None

        rows.append({
            "ticker": ticker,
            "close": cur,
            "ret_1m": ret_1m,
            "ret_3m": ret_3m,
            "ret_6m": ret_6m,
            "ret_12m": ret_12m,
            "ret_12_1": ret_12_1,
            "vol_90d": vol_90d,
            "high_52w_dist": high_52w_dist,
        })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).set_index("ticker")


def _compute_pit_features(
    pit_by_ticker: dict[str, dict],
    prices_features: pd.DataFrame,
    as_of: pd.Timestamp,
) -> pd.DataFrame:
    """Compute PIT-safe fundamental factors as of `as_of`.

    Uses the most recent annual filing at least 90 days old
    (Point-in-Time reporting-lag convention).

    Columns produced (added to prices_features):
      eps, book_value_per_share, revenue_per_share, roe, debt_to_equity,
      pe_ratio, pb_ratio, ps_ratio, net_margin, eps_growth, rev_growth,
      dividend_yield
    """
    cutoff = as_of - pd.Timedelta(days=90)
    features = prices_features.copy()

    metrics = ["eps", "book_value_per_share", "revenue_per_share",
               "roe", "debt_to_equity", "pe_ratio", "pb_ratio", "ps_ratio",
               "net_margin", "eps_growth", "rev_growth", "dividend_yield"]
    for m in metrics:
        features[m] = np.nan

    for ticker in features.index:
        pit = pit_by_ticker.get(ticker, {})
        # Prefer annual statements for PIT computation (10-K filings have
        # the 90-day reporting lag we assume; quarterly-only would need
        # different assumptions). Fall back to quarterly if annual missing.
        income = pit.get("annual_income") if pit.get("annual_income") is not None else pit.get("income")
        balance = pit.get("annual_balance") if pit.get("annual_balance") is not None else pit.get("balance")
        div = pit.get("dividends")

        # Compute latest + prior annual rows
        row = _latest_annual_row(income, balance, cutoff)
        prior = _latest_annual_row(income, balance, cutoff, prior=True)
        if row is None:
            continue

        eps = row.get("eps")
        bvps = row.get("bvps")
        rps = row.get("rps")
        roe = row.get("roe")
        de = row.get("de")
        price = features.at[ticker, "close"]

        features.at[ticker, "eps"] = eps
        features.at[ticker, "book_value_per_share"] = bvps
        features.at[ticker, "revenue_per_share"] = rps
        features.at[ticker, "roe"] = roe
        features.at[ticker, "debt_to_equity"] = de

        if eps and eps > 0 and price:
            features.at[ticker, "pe_ratio"] = price / eps
        if bvps and bvps > 0 and price:
            features.at[ticker, "pb_ratio"] = price / bvps
        if rps and rps > 0 and price:
            features.at[ticker, "ps_ratio"] = price / rps
        if eps is not None and rps and rps > 0:
            features.at[ticker, "net_margin"] = eps / rps

        if prior is not None:
            eps_p = prior.get("eps")
            rps_p = prior.get("rps")
            if eps is not None and eps_p is not None and eps_p > 0:
                features.at[ticker, "eps_growth"] = eps / eps_p - 1.0
            if rps is not None and rps_p is not None and rps_p > 0:
                features.at[ticker, "rev_growth"] = rps / rps_p - 1.0

        # Trailing 12-month dividend yield
        if isinstance(div, pd.Series) and not div.empty and price:
            div_dates = pd.to_datetime(div.index)
            mask = (div_dates > as_of - pd.Timedelta(days=365)) & (div_dates <= as_of)
            ttm = float(div[mask].sum()) if mask.any() else 0.0
            if ttm > 0:
                features.at[ticker, "dividend_yield"] = ttm / price

    return features


def _latest_annual_row(
    income: pd.DataFrame | None,
    balance: pd.DataFrame | None,
    cutoff: pd.Timestamp,
    prior: bool = False,
) -> dict | None:
    """Get {eps, bvps, rps, roe, de} for the latest (or prior) annual
    report published before `cutoff`. Returns None if data insufficient.

    yfinance financials/balance_sheet have periods as COLUMNS (Timestamps),
    with items as index (e.g., "Net Income", "Total Revenue").
    """
    if income is None or income.empty or balance is None or balance.empty:
        return None

    def _row(df: pd.DataFrame, names: list[str]) -> pd.Series:
        idx_lower = {str(i).lower(): i for i in df.index}
        for n in names:
            if n.lower() in idx_lower:
                return df.loc[idx_lower[n.lower()]]
        return pd.Series(dtype="float64")

    ni_row = _row(income, [
        "Net Income",
        "Net Income Common Stockholders",
        "Net Income From Continuing Operation Net Minority Interest",
        "Net Income From Continuing And Discontinued Operation",
        "Normalized Income",
    ])
    rev_row = _row(income, ["Total Revenue", "Revenue", "Operating Revenue"])
    eq_row = _row(balance, [
        "Stockholders Equity",
        "Total Stockholder Equity",
        "Common Stock Equity",
        "Total Equity Gross Minority Interest",
    ])
    debt_row = _row(balance, ["Total Debt", "Long Term Debt", "Net Debt"])
    sh_row = _row(balance, [
        "Share Issued",
        "Ordinary Shares Number",
        "Common Stock Shares Issued",
    ])

    # Periods are columns; pick most recent one at or before cutoff
    cols = pd.to_datetime(income.columns, errors="coerce")
    valid = [c for c in cols if pd.notna(c) and c <= cutoff]
    if not valid:
        return None
    valid.sort(reverse=True)
    idx = 1 if prior else 0
    if idx >= len(valid):
        return None
    period = valid[idx]

    def _get(row: pd.Series, p: pd.Timestamp) -> float | None:
        if row.empty:
            return None
        # Match by any column that equals this timestamp (columns may be datetime or str)
        for col in income.columns:
            try:
                if pd.Timestamp(col) == p:
                    val = row.get(col)
                    return float(val) if pd.notna(val) else None
            except Exception:
                pass
        return None

    ni = _get(ni_row, period)
    rev = _get(rev_row, period)
    eq = _get(eq_row, period)
    td = _get(debt_row, period)
    sh = _get(sh_row, period)

    eps = (ni / sh) if (ni is not None and sh and sh > 0) else None
    bvps = (eq / sh) if (eq is not None and sh and sh > 0) else None
    rps = (rev / sh) if (rev is not None and sh and sh > 0) else None
    roe = (ni / eq) if (ni is not None and eq and eq > 0) else None
    de = (td / eq) if (td is not None and eq and eq > 0) else None

    return {"eps": eps, "bvps": bvps, "rps": rps, "roe": roe, "de": de}


# ── Rebalance dates ────────────────────────────────────────────────


def _rebalance_dates(start: date, end: date, months: int) -> list[pd.Timestamp]:
    """First business day of each `months`-th month between start and end."""
    dates: list[pd.Timestamp] = []
    cur = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    while cur <= end_ts:
        dates.append(cur)
        cur = cur + pd.DateOffset(months=months)
    return dates


# ── Universe filter ────────────────────────────────────────────────


def _filter_universe(cfg: FactorBacktestConfig) -> list[str]:
    meta = cache_loader.load_metadata()
    df = meta.copy()
    if cfg.sector:
        df = df[df["sector"] == cfg.sector]
    if cfg.cap_tier:
        df = df[df["cap_tier"] == cfg.cap_tier]
    tickers = df["ticker"].tolist()

    # Only keep tickers with cached price data
    prices = cache_loader.load_all_prices()
    return [t for t in tickers if t in prices]


# ── Metrics ────────────────────────────────────────────────────────


def _calc_metrics(equity: pd.Series, rf: float = 0.04) -> dict:
    if len(equity) < 2:
        return {}
    total_return = float(equity.iloc[-1] / equity.iloc[0] - 1)
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1 if years > 0 else 0
    daily_ret = equity.pct_change().dropna()
    vol = float(daily_ret.std() * np.sqrt(252)) if len(daily_ret) > 0 else 0
    sharpe = (float(daily_ret.mean() * 252) - rf) / vol if vol > 0 else 0

    # Max drawdown
    running_max = equity.cummax()
    dd = (equity - running_max) / running_max
    max_dd = float(dd.min()) if len(dd) > 0 else 0

    # Period win rate (of returns > 0)
    monthly_ret = equity.resample("ME").last().pct_change().dropna()
    win_rate = float((monthly_ret > 0).mean()) if len(monthly_ret) > 0 else 0

    return {
        "total_return_pct": round(total_return * 100, 2),
        "cagr_pct": round(cagr * 100, 2),
        "sharpe": round(sharpe, 2),
        "volatility_pct": round(vol * 100, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "period_win_rate_pct": round(win_rate * 100, 2),
    }


# ── Main engine ────────────────────────────────────────────────────


def run_factor_backtest(cfg: FactorBacktestConfig) -> FactorBacktestResult:
    """Runs one factor backtest end-to-end from cached data."""
    if cfg.end_date <= cfg.start_date:
        raise ValueError("종료일이 시작일보다 빨라야 합니다.")

    strategy = get_strategy(cfg.strategy_key)
    warnings_out: list[str] = []
    needs_pit = strategy.category in ("fundamentals", "hybrid")

    # 1. Universe
    universe = _filter_universe(cfg)
    if not universe:
        raise ValueError("Universe is empty after filters.")

    # 2. Load caches once
    all_prices = cache_loader.load_all_prices()
    all_pit = cache_loader.load_pit() if needs_pit else {}
    benchmarks = cache_loader.load_benchmarks()
    spy = benchmarks.get("SPY") if isinstance(benchmarks, dict) else None

    universe_prices = {t: all_prices[t] for t in universe if t in all_prices}
    universe_pit = {t: all_pit.get(t, {}) for t in universe} if needs_pit else {}

    # 3. Rebalance dates
    rebal_dates = _rebalance_dates(cfg.start_date, cfg.end_date, cfg.rebalance_months)
    if len(rebal_dates) < 2:
        raise ValueError("Need at least 2 rebalance dates.")

    # 4. Backtest loop
    portfolio_equity = 1.0
    rebal_hist: list[dict] = []
    # Seed with 1.0 at the first rebalance date so the equity curve starts
    # at parity with SPY (which is normalized to 1.0 at the same point).
    equity_daily: dict[pd.Timestamp, float] = {rebal_dates[0]: 1.0}
    last_picks: list[str] = []

    tc_rate = cfg.tc_pct / 100.0

    for i, r_date in enumerate(rebal_dates):
        # Compute features as of r_date
        price_features = _compute_price_features(universe_prices, r_date)
        if price_features.empty:
            continue

        features = (
            _compute_pit_features(universe_pit, price_features, r_date)
            if needs_pit else price_features
        )

        # Score using strategy's rank_fn
        try:
            scores = strategy.rank_fn(features)
        except Exception as e:
            logger.warning("Score fn failed at %s: %s", r_date, e)
            continue

        scores = scores.dropna()
        if scores.empty:
            continue

        picks = scores.sort_values(ascending=False).head(cfg.n_stocks).index.tolist()
        last_picks = picks

        # Compute holding period return (r_date → next rebalance date or end)
        next_date = rebal_dates[i + 1] if i + 1 < len(rebal_dates) else pd.Timestamp(cfg.end_date)
        period_returns: list[float] = []
        for t in picks:
            df = universe_prices[t]
            d = df.copy()
            if not isinstance(d.index, pd.DatetimeIndex):
                if "date" in d.columns:
                    d = d.set_index("date")
                d.index = pd.to_datetime(d.index)
            close_col = "Close" if "Close" in d.columns else "close"
            slice_ = d[(d.index >= r_date) & (d.index <= next_date)][close_col].dropna()
            if len(slice_) < 2:
                continue
            period_returns.append(float(slice_.iloc[-1] / slice_.iloc[0] - 1))

        if not period_returns:
            continue

        period_return = float(np.mean(period_returns))
        # Apply 2-way transaction cost on the whole portfolio
        period_return -= 2 * tc_rate
        portfolio_equity *= (1 + period_return)

        rebal_hist.append({
            "date": r_date.strftime("%Y-%m-%d"),
            "period_return_pct": round(period_return * 100, 2),
            "portfolio_equity": round(portfolio_equity, 4),
            "picks": picks,
            "n_picks": len(picks),
        })
        # Record the equity at the END of this holding period only. Overwriting
        # r_date here would erase the seeded 1.0 start point.
        equity_daily[next_date] = portfolio_equity

    # 5. Build equity curve DataFrame
    if not equity_daily:
        raise ValueError("No valid backtest periods produced.")

    equity_series = pd.Series(equity_daily).sort_index()
    # Fill daily for smooth chart
    all_dates = pd.date_range(equity_series.index[0], equity_series.index[-1], freq="D")
    equity_series = equity_series.reindex(all_dates).ffill()

    # SPY overlay (if available and covers this range)
    spy_series = None
    if isinstance(spy, pd.Series) and not spy.empty:
        spy_ranged = spy[(spy.index >= equity_series.index[0]) & (spy.index <= equity_series.index[-1])]
        if len(spy_ranged) > 1:
            spy_series = spy_ranged / spy_ranged.iloc[0]  # normalize to 1

    equity_curve: list[dict] = []
    for d in equity_series.index:
        row = {"date": d.strftime("%Y-%m-%d"), "portfolio": round(float(equity_series[d]), 4)}
        if spy_series is not None and d in spy_series.index:
            row["spy"] = round(float(spy_series[d]), 4)
        equity_curve.append(row)

    # Metrics
    metrics = _calc_metrics(equity_series)
    spy_metrics = _calc_metrics(spy_series) if spy_series is not None else {}

    return FactorBacktestResult(
        strategy_name=strategy.name,
        strategy_category=strategy.category,
        equity_curve=equity_curve,
        rebalance_history=rebal_hist,
        metrics=metrics,
        benchmark_metrics={"SPY": spy_metrics},
        universe_size=len(universe),
        final_picks=last_picks,
        final_picks_date=rebal_dates[-1].strftime("%Y-%m-%d") if rebal_dates else None,
        warnings=warnings_out,
    )


def list_strategies() -> list[dict]:
    """Return metadata for all registered strategies (for the UI dropdown)."""
    return [
        {"key": k, "name": s.name, "short": s.short_description, "category": s.category}
        for k, s in STRATEGIES.items()
    ]
