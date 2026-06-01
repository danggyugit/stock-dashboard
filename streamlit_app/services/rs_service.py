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
def get_rs_table(tickers: tuple[str, ...]) -> pd.DataFrame:
    """Compute RS ratings and key return metrics for a set of tickers.

    Returns:
        DataFrame with columns: ticker, rs_rating, ret_1m_pct, ret_3m_pct, ret_12m_pct.
        Sorted by rs_rating descending.
    """
    if not tickers:
        return pd.DataFrame(columns=["ticker", "rs_rating", "ret_1m_pct", "ret_3m_pct", "ret_12m_pct"])

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
        logger.warning("RS table download failed: %s", e)
        return pd.DataFrame()

    if raw.empty:
        return pd.DataFrame()
    if isinstance(raw, pd.Series):
        raw = raw.to_frame(tickers[0])

    scores: dict[str, float] = {}
    rows: list[dict] = []

    for t in raw.columns:
        s = raw[t].dropna()
        if len(s) < 63:
            continue
        score = _weighted_return(s)
        if np.isnan(score):
            continue
        scores[t] = score
        row: dict = {"ticker": str(t)}
        for days, key in [(21, "ret_1m_pct"), (63, "ret_3m_pct"), (252, "ret_12m_pct")]:
            row[key] = round((s.iloc[-1] / s.iloc[-days] - 1) * 100, 2) if len(s) >= days else None
        rows.append(row)

    if not scores or not rows:
        return pd.DataFrame()

    rated = (pd.Series(scores).rank(pct=True) * 98 + 1).round(0).astype(int)
    df = pd.DataFrame(rows)
    df["rs_rating"] = df["ticker"].map(rated)
    df = df.dropna(subset=["rs_rating"])
    df["rs_rating"] = df["rs_rating"].astype(int)
    return df.sort_values("rs_rating", ascending=False).reset_index(drop=True)


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
