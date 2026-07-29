"""Long-term trend-channel breakout screener.

For each ticker we fit a linear regression channel on the log of its monthly
closes over a user-chosen look-back window, then detect whether the *current
month* has broken above the channel's upper band (the sloped trend resistance).

Why log-price + regression channel:
  - log price makes a constant-% trend a straight line (fair across price levels)
  - the regression line ± k·σ(residuals) is an objective, reproducible stand-in
    for the hand-drawn "trend upper / lower" lines on a monthly chart

Why the channel excludes the current month:
  - fitting on months t0..t-1 keeps the latest (breakout) bar from pulling the
    trendline up; the band is then *projected* to the current month and the
    current close is tested against it — a genuine break of a pre-existing channel.
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
        (upper, lower, slope, r2) at the last index, or None if not fittable.
        upper/lower are in log space.
    """
    n = len(log_prices)
    if n < 4:
        return None
    fit_y = log_prices[:-1]                 # establish channel up to prior month
    x = np.arange(len(fit_y), dtype=float)
    # OLS line
    slope, intercept = np.polyfit(x, fit_y, 1)
    fitted = slope * x + intercept
    resid = fit_y - fitted
    sigma = float(resid.std(ddof=1)) if len(resid) > 2 else float(resid.std())
    if not np.isfinite(sigma) or sigma == 0:
        return None
    # R² of the trend fit
    ss_res = float((resid ** 2).sum())
    ss_tot = float(((fit_y - fit_y.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    # project line to the current (last) index = len(fit_y)
    line_last = slope * len(fit_y) + intercept
    return line_last + k * sigma, line_last - k * sigma, float(slope), float(r2)


def compute_breakouts(
    monthly_wide: pd.DataFrame,
    lookback: int,
    k: float = 2.0,
    min_months: int = MIN_MONTHS,
) -> pd.DataFrame:
    """Detect current-month upper-channel breakouts across all tickers.

    Args:
        monthly_wide: month-end closes, index=date, columns=tickers.
        lookback: channel window length in months (user-selectable).
        k: channel width in residual std-devs.
        min_months: skip tickers with fewer months than this (young listings
            still qualify as long as they clear this floor — uses since-IPO data).

    Returns:
        DataFrame indexed by ticker with columns: close, upper, lower,
        slope_ann_pct, r2, pct_above (% above upper band, >0 = broken out),
        breakout (bool, current close above upper), fresh (bool, broke out THIS
        month — was below the band last month), n_months.
    """
    if monthly_wide.empty:
        return pd.DataFrame()

    rows: list[dict] = []
    for ticker in monthly_wide.columns:
        s = monthly_wide[ticker].dropna()
        if len(s) < min_months:
            continue
        # window of up to `lookback` months, including the current (last) bar
        win = s.iloc[-lookback:] if len(s) > lookback else s
        y = np.log(win.to_numpy(dtype=float))
        cur = _fit_channel(y, k)
        if cur is None:
            continue
        upper, lower, slope, r2 = cur
        cur_log = y[-1]
        close = float(win.iloc[-1])

        breakout = cur_log > upper
        pct_above = (np.exp(cur_log - upper) - 1.0) * 100.0

        # "fresh this month": re-fit shifted back one month and check the prior
        # bar was NOT already above its band
        fresh = breakout
        if len(s) >= min_months + 1:
            win_prev = s.iloc[-lookback - 1:-1] if len(s) > lookback else s.iloc[:-1]
            yp = np.log(win_prev.to_numpy(dtype=float))
            prev = _fit_channel(yp, k)
            if prev is not None:
                prev_upper = prev[0]
                was_above = yp[-1] > prev_upper
                fresh = bool(breakout and not was_above)

        rows.append({
            "ticker": ticker,
            "close": round(close, 2),
            "upper": round(float(np.exp(upper)), 2),
            "lower": round(float(np.exp(lower)), 2),
            "slope_ann_pct": round((np.exp(slope * 12) - 1.0) * 100.0, 1),
            "r2": round(r2, 2),
            "pct_above": round(pct_above, 1),
            "breakout": bool(breakout),
            "fresh": bool(fresh),
            "n_months": int(len(s)),
        })

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).set_index("ticker")
