"""Factor Lab backtest engine — survivorship-corrected + PIT fundamentals.

Design notes:

  - **Survivorship correction**: at each rebalance date, we reconstruct
    the S&P 500 membership that was live on that date using Wikipedia's
    change log (historical_data_service.reconstruct_sp500_at). Without
    this, returns are upward-biased because failed/merged-out tickers
    are excluded.

  - **Point-in-time fundamentals**: at each rebalance date, compute
    PE/PB/ROE/etc. from the most recent *annual* filing that was already
    public at that time (90-day reporting lag). This eliminates the
    look-ahead bias that was present when we used the current fundamentals
    snapshot for every rebalance.

  - **Sector/cap filters** use current metadata for all tickers (current
    + historical). Known caveat: a ticker that changed sector since its
    index exit is misclassified. Minor effect for sector filters,
    negligible for most use cases.

  - **Benchmark**: SPY total return (auto-adjusted).

  - **Data caching**: Price history and fundamentals both live in
    dedicated local SQLite files (price_cache.db, historical_cache.db)
    to bypass Turso write latency.
"""

from __future__ import annotations

import io
import logging
import urllib.request
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Callable

import numpy as np
import pandas as pd
import streamlit as st

from services.cache_loader import get_cached_fundamentals, get_cached_stocks
from services.factor_strategies import Strategy, get_strategy
from services.historical_data_service import (
    get_sp500_change_history, load_pit_fundamentals, pit_factors_at,
    prefetch_pit_fundamentals, reconstruct_sp500_at,
)
from services.price_history_service import (
    compute_returns_and_vol, load_monthly_prices, prefetch,
)

logger = logging.getLogger(__name__)

BENCHMARK_TICKERS = ["SPY", "QQQ", "RSP"]
PIT_FUND_MAX_YEARS = 4   # yfinance annual statements typically go back ~4 years
PIT_FUND_WARN_YEARS = 4

# Delisting return assumption — applied to a held stock that stops trading
# mid-period and has NO price anywhere in the holding window (the common case
# uses the last available price instead). S&P 500 delistings are a mix of M&A
# (often near deal price) and distress (near zero); -30% is the widely-cited
# Shumway (1997) average performance-related delisting return — a conservative
# middle ground that avoids both inflating returns (the old bug) and the over-
# punitive -100%.
DELISTING_RETURN = -0.30


def _default_start() -> date:
    return date.today() - timedelta(days=5 * 365)


@dataclass
class BacktestConfig:
    strategy_key: str
    start_date: date = field(default_factory=_default_start)
    end_date: date = field(default_factory=date.today)
    rebalance_months: int = 3       # 1/3/6/12
    n_stocks: int = 20
    tc_pct: float = 0.3
    min_market_cap: float = 2e9
    sector: str | None = None
    cap_tier: str | None = None


@dataclass
class BacktestResult:
    config: BacktestConfig
    strategy: Strategy
    equity_curve: pd.DataFrame        # cols: portfolio, SPY, QQQ
    rebalance_history: list[dict]
    metrics: dict
    benchmark_metrics: dict            # {"SPY": {...}, "QQQ": {...}}
    universe_size: int
    warnings: list[str] = field(default_factory=list)
    final_picks: list[str] = field(default_factory=list)   # picks at last rebal date
    final_picks_date: date | None = None


# ── Universe metadata ─────────────────────────────────────────────


def _load_current_metadata() -> dict[str, dict]:
    """Map ticker → {name, sector, cap_tier, shares_outstanding} for S&P stocks."""
    stocks = get_cached_stocks() or []
    fund_tickers: dict = (get_cached_fundamentals() or {}).get("tickers", {})
    out: dict[str, dict] = {}
    for s in stocks:
        t = s.get("ticker")
        if not t:
            continue
        fund = fund_tickers.get(t, {})
        out[t] = {
            "name": s.get("name", t),
            "sector": s.get("sector"),
            "cap_tier": s.get("cap_tier"),
            "shares_outstanding": fund.get("shares_outstanding"),
        }
    return out


def _passes_filter(ticker: str, meta: dict[str, dict], cfg: BacktestConfig) -> bool:
    """Apply sector/cap filter. Tickers without metadata fail any filter."""
    m = meta.get(ticker)
    if cfg.sector or cfg.cap_tier:
        if m is None:
            return False
        if cfg.sector and m.get("sector") != cfg.sector:
            return False
        if cfg.cap_tier and m.get("cap_tier") != cfg.cap_tier:
            return False
    return True


def _proxy_mktcap(
    ticker: str, meta: dict[str, dict], prices: pd.DataFrame, as_of: pd.Timestamp,
) -> float | None:
    """Estimate market cap at as_of using current shares × historical price."""
    m = meta.get(ticker)
    if m is None:
        return None
    shares = m.get("shares_outstanding")
    if not shares or shares <= 0:
        return None
    if ticker not in prices.columns:
        return None
    hist = prices[ticker].loc[:as_of].dropna()
    if hist.empty:
        return None
    return shares * float(hist.iloc[-1])


def _tiered_tc_rate(ticker: str, meta: dict[str, dict], base_tc_pct: float) -> float:
    """Return per-position TC rate based on cap_tier (fraction of portfolio weight)."""
    cap = (meta.get(ticker) or {}).get("cap_tier", "Mid")
    if cap == "Large":
        multiplier = 0.5
    elif cap == "Small":
        multiplier = 2.0
    else:
        multiplier = 1.0
    return base_tc_pct * multiplier / 100


@st.cache_data(ttl=86400, show_spinner=False)
def _fetch_fred_tbill() -> pd.Series:
    """Fetch 3-month T-bill rate history from FRED (no API key required)."""
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTB3"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            content = resp.read().decode("utf-8")
        df = pd.read_csv(io.StringIO(content), index_col=0, parse_dates=True)
        df.columns = ["rate"]
        df["rate"] = pd.to_numeric(df["rate"], errors="coerce")
        return df["rate"].dropna() / 100
    except Exception as e:
        logger.warning("FRED T-bill fetch failed: %s", e)
        return pd.Series(dtype=float)


def _get_rf_rate(start: date, end: date) -> float:
    """Return annualized average 3-month T-bill rate over the backtest period."""
    series = _fetch_fred_tbill()
    if series.empty:
        return 0.04
    mask = (series.index >= pd.Timestamp(start)) & (series.index <= pd.Timestamp(end))
    subset = series[mask]
    if subset.empty:
        return float(series.iloc[-1])
    return float(subset.mean())


def _build_historical_universe(
    current_members: list[str], changes: pd.DataFrame,
    start: pd.Timestamp, end: pd.Timestamp,
) -> set[str]:
    """All tickers that were in S&P 500 at any point during [start, end]."""
    universe = set(current_members)
    if changes.empty:
        return universe
    ch = changes.copy()
    ch["date"] = pd.to_datetime(ch["date"])
    # Removals within the backtest window (or shortly before) = historical members
    window = ch[(ch["date"] >= start - pd.Timedelta(days=30)) & (ch["date"] <= end)]
    for _, row in window.iterrows():
        if row.get("removed_ticker"):
            universe.add(row["removed_ticker"])
        if row.get("added_ticker"):
            universe.add(row["added_ticker"])
    return universe


# ── Rebalance dates ───────────────────────────────────────────────


def _rebalance_dates(prices_index: pd.DatetimeIndex, months: int) -> list[pd.Timestamp]:
    """Generate calendar-aligned rebalance dates (last trading day of each N-month period)."""
    if len(prices_index) == 0:
        return []
    start = prices_index.min()
    end = prices_index.max()
    cal_checkpoints = pd.date_range(
        start=start,
        end=end + pd.Timedelta(days=31),
        freq=pd.offsets.MonthEnd(months),
    )
    sorted_idx = prices_index.sort_values()
    result: list[pd.Timestamp] = []
    for cd in cal_checkpoints:
        avail = sorted_idx[sorted_idx <= cd]
        if avail.empty:
            continue
        td = avail[-1]
        if not result or td > result[-1]:
            result.append(td)
    return result


# ── Metrics ───────────────────────────────────────────────────────


def _calc_metrics(equity: pd.Series, rf: float = 0.04) -> dict:
    if equity.empty or len(equity) < 2:
        return {}
    equity = equity.dropna()
    if equity.iloc[0] <= 0:
        return {}
    rets = equity.pct_change().dropna()
    if rets.empty:
        return {}
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    total_ret = equity.iloc[-1] / equity.iloc[0] - 1
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1 if years > 0 else 0
    periods_per_year = len(rets) / years if years > 0 else 12
    ann_vol = rets.std() * np.sqrt(periods_per_year) if rets.std() > 0 else 0
    ann_return = (1 + rets.mean()) ** periods_per_year - 1
    sharpe = (ann_return - rf) / ann_vol if ann_vol > 0 else 0
    running_max = equity.cummax()
    drawdown = equity / running_max - 1
    mdd = drawdown.min()
    win_rate = (rets > 0).mean() if len(rets) > 0 else 0
    return {
        "total_return_pct": round(total_ret * 100, 2),
        "cagr_pct": round(cagr * 100, 2),
        "volatility_pct": round(ann_vol * 100, 2),
        "sharpe": round(sharpe, 2),
        "max_drawdown_pct": round(mdd * 100, 2),
        "period_win_rate_pct": round(win_rate * 100, 2),
        "n_periods": len(rets),
        "years": round(years, 2),
    }


# ── Main ──────────────────────────────────────────────────────────


def run_backtest(
    cfg: BacktestConfig,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> BacktestResult:
    strategy = get_strategy(cfg.strategy_key)
    warnings: list[str] = []
    needs_fundamentals = (strategy.category in ("fundamentals", "hybrid"))

    # 1) Validate window
    start_dt = cfg.start_date
    end_dt = cfg.end_date
    if end_dt <= start_dt:
        raise ValueError("종료일이 시작일보다 빨라야 합니다.")

    # 2) Load current metadata + change history, build historical universe
    current_meta = _load_current_metadata()
    current_members = list(current_meta.keys())
    changes = get_sp500_change_history()
    historical_universe = _build_historical_universe(
        current_members, changes,
        pd.Timestamp(start_dt), pd.Timestamp(end_dt),
    )

    # 3) Apply sector/cap filter
    universe_tickers = sorted(
        t for t in historical_universe if _passes_filter(t, current_meta, cfg)
    )
    if not universe_tickers:
        raise ValueError("Universe is empty after filters. Check sector/cap.")

    # 4) Prefetch prices (batch)
    if progress_callback:
        progress_callback(0, 1, "가격 데이터 준비 중...")
    tickers_to_fetch = list(set(universe_tickers + BENCHMARK_TICKERS))
    buffer_start = start_dt - timedelta(days=365)
    years_back = max(2, int((date.today() - buffer_start).days / 365) + 1)

    def _prog(done: int, total: int, msg: str) -> None:
        if progress_callback:
            progress_callback(done, total, f"가격 배치: {msg}")

    prefetch(tickers_to_fetch, years=years_back, progress_callback=_prog)

    prices = load_monthly_prices(
        tickers_to_fetch,
        buffer_start.isoformat(), end_dt.isoformat(),
    )
    if prices.empty:
        raise ValueError("No price data loaded.")

    # 5) Prefetch PIT fundamentals if strategy needs them
    pit_df = pd.DataFrame()
    if needs_fundamentals:
        fund_years_span = (end_dt - start_dt).days / 365
        if fund_years_span > PIT_FUND_WARN_YEARS:
            warnings.append(
                f"펀더멘털 전략의 PIT 데이터는 최근 약 {PIT_FUND_MAX_YEARS}년까지만 "
                "안정적으로 제공됩니다. 더 긴 구간은 초반 일부 리밸런싱에서 후보가 부족할 수 있음."
            )
        if progress_callback:
            progress_callback(0, len(universe_tickers), "펀더멘털 데이터 준비 중...")

        def _fund_prog(done: int, total: int, ticker: str) -> None:
            if progress_callback:
                progress_callback(done, total, f"재무제표: {ticker}")

        prefetch_pit_fundamentals(
            universe_tickers, progress_callback=_fund_prog,
        )
        pit_df = load_pit_fundamentals(universe_tickers)

    # 6) Filter to tickers with enough price history
    coverage = prices.notna().sum()
    valid_tickers = set(coverage[coverage >= 13].index.tolist())
    for bt in BENCHMARK_TICKERS:
        valid_tickers.discard(bt)   # benchmarks tracked separately

    # 7) Generate rebalance dates
    price_window = prices[prices.index >= pd.Timestamp(start_dt)]
    rebal_dates = _rebalance_dates(price_window.index, cfg.rebalance_months)
    if len(rebal_dates) < 3:
        raise ValueError(
            f"리밸런싱 횟수가 너무 적음 ({len(rebal_dates)}회). "
            "기간을 더 길게 하거나 리밸런싱 주기를 짧게 하세요."
        )

    # 8) Simulate
    equity = 1.0
    bench_equity: dict[str, float] = {b: 1.0 for b in BENCHMARK_TICKERS}
    equity_history: list[dict] = []   # each row: {date, portfolio, SPY, QQQ}
    rebal_history: list[dict] = []
    prev_holdings: set[str] = set()
    bench_series: dict[str, pd.Series] = {
        b: prices[b].dropna()
        for b in BENCHMARK_TICKERS if b in prices.columns
    }

    for i, rd in enumerate(rebal_dates[:-1]):
        next_rd = rebal_dates[i + 1]

        # Reconstruct universe at rd (survivorship correction)
        members_at_rd = reconstruct_sp500_at(rd, current_members, changes)
        # Apply filter + require valid price coverage
        candidates = {
            t for t in members_at_rd
            if t in valid_tickers and _passes_filter(t, current_meta, cfg)
        }
        if not candidates:
            logger.warning("No candidates on %s", rd.date())
            continue

        # Proxy market-cap filter: shares_outstanding × price_at_rd
        if cfg.min_market_cap > 0:
            candidates = {
                t for t in candidates
                if (_proxy_mktcap(t, current_meta, prices, rd) or cfg.min_market_cap) >= cfg.min_market_cap
            }

        cand_list = sorted(candidates)

        # Price-based factors (always PIT)
        metrics_at_rd = compute_returns_and_vol(prices[cand_list], rd)
        if metrics_at_rd.empty:
            continue

        # PIT fundamentals (only if strategy needs them)
        if needs_fundamentals and not pit_df.empty:
            fund_rows: list[dict] = []
            for t in cand_list:
                if t not in prices.columns:
                    continue
                # Find last non-NaN price on or before rd
                col = prices[t]
                px_series = col[col.index <= rd].dropna()
                if px_series.empty:
                    continue
                px = float(px_series.iloc[-1])
                f = pit_factors_at(pit_df, t, rd, px)
                if not f:
                    continue
                f["ticker"] = t
                fund_rows.append(f)
            fund_wide = (
                pd.DataFrame(fund_rows).set_index("ticker")
                if fund_rows else pd.DataFrame()
            )
        else:
            fund_wide = pd.DataFrame()

        # Merge
        merged = metrics_at_rd
        if not fund_wide.empty:
            merged = merged.join(fund_wide, how="outer")
        # Skip this rebalance if any required column is entirely missing
        missing_cols = [c for c in strategy.requires if c not in merged.columns]
        if missing_cols:
            logger.debug("Missing columns %s on %s — skipping", missing_cols, rd.date())
            continue
        merged = merged.dropna(subset=strategy.requires)

        if merged.empty:
            logger.debug("No candidates on %s", rd.date())
            continue
        if len(merged) < cfg.n_stocks:
            logger.debug("Fewer candidates than target on %s (%d/%d)", rd.date(), len(merged), cfg.n_stocks)

        # Score & select
        scores = strategy.rank_fn(merged)
        merged = merged.assign(_score=scores).sort_values("_score", ascending=False)
        picks = merged.head(cfg.n_stocks).index.tolist()
        n_actual = len(picks)

        # Period return (equal-weight) — survivorship-correct.
        # A held stock that delists mid-period has a NaN price at next_rd.
        # Previously such names were dropped (intersection), silently excluding
        # their loss and inflating returns. Now each held name is exited at its
        # last available price within the window (captures the delisting
        # decline); if it has no price anywhere in the window, DELISTING_RETURN
        # is applied instead of dropping it.
        period_ret = 0.0
        if rd in prices.index and next_rd in prices.index:
            px_rd = prices.loc[rd, picks]
            px_next = prices.loc[next_rd, picks]
            # Exit-price search panel EXCLUDING the entry row (rd) — otherwise a
            # stock that never traded after purchase would "exit" at its own
            # entry price (0% return) instead of taking the delisting loss.
            post_window = prices.loc[rd:next_rd, picks].iloc[1:]
            held_rets: list[float] = []
            for tk in picks:
                p0 = px_rd.get(tk)
                if p0 is None or pd.isna(p0) or p0 == 0:
                    continue  # no valid entry price → could not have bought it
                p1 = px_next.get(tk)
                if p1 is not None and pd.notna(p1):
                    held_rets.append(p1 / p0 - 1.0)
                    continue
                # Delisted mid-period: exit at last available price after entry
                col = post_window[tk].dropna() if tk in post_window.columns else pd.Series(dtype=float)
                if len(col) > 0:
                    held_rets.append(float(col.iloc[-1]) / p0 - 1.0)
                else:
                    held_rets.append(DELISTING_RETURN)
            if held_rets:
                period_ret = float(np.mean(held_rets))

        # Transaction cost (tiered by cap_tier: Large 0.5×, Mid 1×, Small 2×)
        holdings_now = set(picks)
        new_picks_set = holdings_now if i == 0 else (holdings_now - prev_holdings)
        if new_picks_set and n_actual > 0:
            tc = sum(
                (1.0 / n_actual) * _tiered_tc_rate(t, current_meta, cfg.tc_pct)
                for t in new_picks_set
            )
        else:
            tc = 0.0
        equity *= (1 + period_ret) * (1 - tc)

        # Benchmarks (SPY, QQQ)
        for bt, bs in bench_series.items():
            try:
                b_rd = bs.loc[:rd].iloc[-1]
                b_next = bs.loc[:next_rd].iloc[-1]
                bench_equity[bt] *= b_next / b_rd
            except Exception:
                pass

        row = {"date": next_rd, "portfolio": equity}
        row.update(bench_equity)
        equity_history.append(row)

        rebal_history.append({
            "date": rd,
            "next_date": next_rd,
            "universe_size": len(cand_list),
            "n_picks": len(picks),
            "picks": picks,
            "period_return_pct": round(period_ret * 100, 2),
            "turnover_pct": round(len(new_picks_set) / cfg.n_stocks * 100, 1),
            "portfolio_equity": round(equity, 4),
        })
        prev_holdings = holdings_now

        if progress_callback:
            progress_callback(i + 1, len(rebal_dates) - 1, f"리밸런싱: {rd.date()}")

    # 8-b) Compute picks at the LAST rebalance date (= near end_date)
    # The main loop covers rebal_dates[:-1]; rebal_dates[-1] is the terminal
    # date used only as next_rd. We score it here to surface "current picks".
    final_picks: list[str] = []
    final_picks_date: date | None = None
    if rebal_dates:
        last_rd = rebal_dates[-1]
        try:
            members_last = reconstruct_sp500_at(last_rd, current_members, changes)
            cands_last = {
                t for t in members_last
                if t in valid_tickers and _passes_filter(t, current_meta, cfg)
            }
            if cands_last:
                if cfg.min_market_cap > 0:
                    cands_last = {
                        t for t in cands_last
                        if (_proxy_mktcap(t, current_meta, prices, last_rd) or cfg.min_market_cap) >= cfg.min_market_cap
                    }
                cand_list_last = sorted(cands_last)
                metrics_last = compute_returns_and_vol(prices[cand_list_last], last_rd)
                if not metrics_last.empty:
                    if needs_fundamentals and not pit_df.empty:
                        fund_rows_last: list[dict] = []
                        for t in cand_list_last:
                            if t not in prices.columns:
                                continue
                            col = prices[t]
                            px_s = col[col.index <= last_rd].dropna()
                            if px_s.empty:
                                continue
                            f = pit_factors_at(pit_df, t, last_rd, float(px_s.iloc[-1]))
                            if not f:
                                continue
                            f["ticker"] = t
                            fund_rows_last.append(f)
                        fund_wide_last = (
                            pd.DataFrame(fund_rows_last).set_index("ticker")
                            if fund_rows_last else pd.DataFrame()
                        )
                    else:
                        fund_wide_last = pd.DataFrame()

                    merged_last = metrics_last
                    if not fund_wide_last.empty:
                        merged_last = merged_last.join(fund_wide_last, how="outer")
                    missing_last = [c for c in strategy.requires if c not in merged_last.columns]
                    if not missing_last:
                        merged_last = merged_last.dropna(subset=strategy.requires)
                        if not merged_last.empty:
                            scores_last = strategy.rank_fn(merged_last)
                            merged_last = (
                                merged_last.assign(_score=scores_last)
                                .sort_values("_score", ascending=False)
                            )
                            final_picks = merged_last.head(cfg.n_stocks).index.tolist()
                            final_picks_date = last_rd.date()
        except Exception as e:
            logger.warning("Could not compute final picks at %s: %s", last_rd.date(), e)

    # 9) Equity curve + metrics
    if not equity_history:
        raise ValueError("Backtest produced no rebalances.")

    curve = pd.DataFrame(equity_history).set_index("date")
    first_date = rebal_dates[0]
    first_row = {"portfolio": 1.0}
    for b in BENCHMARK_TICKERS:
        first_row[b] = 1.0
    curve.loc[first_date] = first_row
    curve = curve.sort_index()

    rf_rate = _get_rf_rate(start_dt, end_dt)
    metrics = _calc_metrics(curve["portfolio"], rf=rf_rate)
    bench_metrics = {
        b: _calc_metrics(curve[b], rf=rf_rate) for b in BENCHMARK_TICKERS if b in curve.columns
    }

    # Surface context info
    warnings.append(
        f"생존편향 보정: 총 {len(historical_universe)}개 후보 (현재 {len(current_members)}개 + 역사적 편입/퇴출 포함)"
    )

    return BacktestResult(
        config=cfg,
        strategy=strategy,
        equity_curve=curve,
        rebalance_history=rebal_history,
        metrics=metrics,
        benchmark_metrics=bench_metrics,
        universe_size=len(universe_tickers),
        warnings=warnings,
        final_picks=final_picks,
        final_picks_date=final_picks_date,
    )


def run_multiple(
    strategy_keys: list[str],
    base_cfg: BacktestConfig,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> list[BacktestResult]:
    results: list[BacktestResult] = []
    total = len(strategy_keys)
    for i, key in enumerate(strategy_keys):
        cfg = BacktestConfig(**{**base_cfg.__dict__, "strategy_key": key})
        if progress_callback:
            progress_callback(i, total, f"전략 실행 중: {key}")
        try:
            r = run_backtest(cfg)
            results.append(r)
        except Exception as e:
            logger.exception("Strategy %s failed: %s", key, e)
    return results
