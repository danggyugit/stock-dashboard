"""RS Rating — IBD-style Relative Strength Rating (1–99)."""

import logging

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

logger = logging.getLogger(__name__)

_WINDOWS = [
    (63,  0.2),   # 3-month
    (126, 0.2),   # 6-month
    (189, 0.2),   # 9-month
    (252, 0.4),   # 12-month (highest weight — IBD style)
]


def _weighted_return(s: pd.Series) -> float:
    """Compute IBD-style weighted return score for a price series."""
    score = 0.0
    clean = s.dropna()
    if len(clean) < 63:
        return np.nan
    for days, w in _WINDOWS:
        if len(clean) >= days:
            score += w * (clean.iloc[-1] / clean.iloc[-days] - 1)
    return score


@st.cache_data(ttl=3600 * 6, show_spinner=False)
def get_rs_ratings(tickers: tuple[str, ...]) -> pd.Series:
    """Compute RS ratings (1–99) for the given tickers.

    Args:
        tickers: Tuple of ticker symbols (tuple for cache-key stability).

    Returns:
        Series indexed by ticker, values 1–99 (99 = strongest).
    """
    if not tickers:
        return pd.Series(dtype=float)

    end = pd.Timestamp.now()
    start = (end - pd.Timedelta(days=375)).strftime("%Y-%m-%d")

    try:
        raw = yf.download(
            list(tickers),
            start=start,
            auto_adjust=True,
            progress=False,
            timeout=60,
        )["Close"]
    except Exception as e:
        logger.warning("RS batch download failed: %s", e)
        return pd.Series(dtype=float)

    if raw.empty:
        return pd.Series(dtype=float)
    if isinstance(raw, pd.Series):
        raw = raw.to_frame(tickers[0])

    scores: dict[str, float] = {}
    for t in raw.columns:
        scores[t] = _weighted_return(raw[t])

    score_series = pd.Series(scores).dropna()
    if score_series.empty:
        return pd.Series(dtype=float)

    rated = (score_series.rank(pct=True) * 98 + 1).round(0).astype(int)
    return rated
