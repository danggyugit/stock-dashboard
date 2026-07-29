"""Long-term trend-channel breakout screener.

For each ticker we fit a linear regression channel on the log of its monthly
closes over a user-chosen look-back window, then detect whether a *fresh* break
above the channel's upper band (the sloped trend resistance) occurred within the
last N months (N = user-selectable scan window; N=1 means the current month).

Why log-price + regression channel:
  - log price makes a constant-% trend a straight line (fair across price levels)
  - the regression line ± k·σ(residuals) is an objective, reproducible stand-in
    for the hand-drawn "trend upper / lower" lines on a monthly chart

Why each tested month excludes itself from the fit:
  - the channel at month m is fit on the `lookback` bars ending at m-1, then
    projected to m and compared to m's close — a genuine break of a channel
    that existed *before* that month (no look-ahead, latest bar can't tilt it).
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

MIN_MONTHS = 18   # 채널을 의미있게 적합하려면 최소 이 정도 월봉이 필요


def _fit_channel(log_prices: np.ndarray, k: float) -> tuple[float, float, float, float] | None:
    """Fit a line on all-but-last points; project band to the last index.

    Args:
        log_prices: 1-D array of log(close), oldest→newest. The LAST element is
            the bar being tested; the fit uses the preceding ones.
        k: band half-width in residual standard deviations.

    Returns:
        (upper, lower, slope, r2) at the last index (log space), or None.
    """
    n = len(log_prices)
    if n < 4:
        return None
    fit_y = log_prices[:-1]                 # establish channel up to prior month
    x = np.arange(len(fit_y), dtype=float)
    slope, intercept = np.polyfit(x, fit_y, 1)
    fitted = slope * x + intercept
    resid = fit_y - fitted
    sigma = float(resid.std(ddof=1)) if len(resid) > 2 else float(resid.std())
    if not np.isfinite(sigma) or sigma == 0:
        return None
    ss_res = float((resid ** 2).sum())
    ss_tot = float(((fit_y - fit_y.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    line_last = slope * len(fit_y) + intercept
    return line_last + k * sigma, line_last - k * sigma, float(slope), float(r2)


def _test_pos(s: pd.Series, pos: int, lookback: int, k: float) -> dict | None:
    """Evaluate the channel at series position `pos` (0-based).

    Window = up to `lookback` bars ending at pos (inclusive); the channel is fit
    on all but `pos`, then `pos` is tested against the projected band.
    """
    if pos < 3:
        return None
    start = max(0, pos - lookback + 1)
    win = s.iloc[start:pos + 1]
    if len(win) < 4:
        return None
    y = np.log(win.to_numpy(dtype=float))
    fit = _fit_channel(y, k)
    if fit is None:
        return None
    upper, lower, slope, r2 = fit
    cur_log = y[-1]
    return {
        "broke": bool(cur_log > upper),
        "upper": float(np.exp(upper)),
        "lower": float(np.exp(lower)),
        "slope": float(slope),
        "r2": float(r2),
        "close": float(win.iloc[-1]),
        "pct_above": (float(np.exp(cur_log - upper)) - 1.0) * 100.0,
    }


def compute_breakouts(
    monthly_wide: pd.DataFrame,
    lookback: int,
    k: float = 2.0,
    scan_months: int = 1,
    min_months: int = MIN_MONTHS,
) -> pd.DataFrame:
    """Find tickers whose close made a fresh upper-channel break in the last N months.

    Args:
        monthly_wide: month-end closes, index=date, columns=tickers.
        lookback: channel window length in months (user-selectable).
        k: channel width in residual std-devs.
        scan_months: look for a fresh breakout within this many most-recent months
            (1 = current month only; up to e.g. 12).
        min_months: skip tickers with fewer months than this (young listings still
            qualify — uses since-IPO data).

    Returns:
        DataFrame indexed by ticker (only tickers with a breakout in the window),
        columns: breakout_month (YYYY-MM), months_ago (0=current), close_at_bo,
        upper_at_bo, pct_above_bo, slope_ann_pct, r2 (trend at breakout),
        cur_close, cur_pct_above (status now vs current channel), still_above, n_months.
    """
    if monthly_wide.empty:
        return pd.DataFrame()

    rows: list[dict] = []
    for ticker in monthly_wide.columns:
        s = monthly_wide[ticker].dropna()
        if len(s) < min_months:
            continue
        last = len(s) - 1

        # scan most-recent `scan_months` months for the latest FRESH crossing
        found = None
        for back in range(scan_months):
            pos = last - back
            if pos < min_months - 1:
                break
            t = _test_pos(s, pos, lookback, k)
            if t is None or not t["broke"]:
                continue
            prev = _test_pos(s, pos - 1, lookback, k)
            fresh = (prev is None) or (not prev["broke"])  # crossed above THIS month
            if fresh:
                found = (back, pos, t)
                break
        if found is None:
            continue

        back, pos, t = found
        cur = _test_pos(s, last, lookback, k) or t
        rows.append({
            "ticker": ticker,
            "breakout_month": s.index[pos].strftime("%Y-%m"),
            "months_ago": int(back),
            "close_at_bo": round(t["close"], 2),
            "upper_at_bo": round(t["upper"], 2),
            "pct_above_bo": round(t["pct_above"], 1),
            "slope_ann_pct": round((np.exp(t["slope"] * 12) - 1.0) * 100.0, 1),
            "r2": round(t["r2"], 2),
            "cur_close": round(cur["close"], 2),
            "cur_pct_above": round(cur["pct_above"], 1),
            "still_above": bool(cur["broke"]),
            "n_months": int(len(s)),
        })

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).set_index("ticker")
