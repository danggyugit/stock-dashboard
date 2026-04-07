"""Sentiment analysis service for Streamlit app."""

import logging
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import streamlit as st

from core.data_provider import MarketDataProvider
from core.news_provider import NewsProvider
from core.llm_provider import LLMProvider

logger = logging.getLogger(__name__)

_data_provider = MarketDataProvider()
_news_provider = NewsProvider()
_llm_provider = LLMProvider()


def _score_to_label(score: float) -> str:
    if score <= 20:
        return "Extreme Fear"
    elif score <= 40:
        return "Fear"
    elif score <= 60:
        return "Neutral"
    elif score <= 80:
        return "Greed"
    return "Extreme Greed"


def _quick_sentiment(headline: str) -> tuple[float, str]:
    """Fast keyword-based sentiment scoring."""
    hl = headline.lower()
    pos = ["surge", "soar", "rally", "jump", "gain", "record", "beat",
           "upgrade", "bullish", "strong", "outperform", "buy", "boom",
           "profit", "growth", "optimis", "recover", "upside", "high"]
    neg = ["crash", "plunge", "drop", "fall", "loss", "miss", "downgrade",
           "bearish", "weak", "underperform", "sell", "slump", "decline",
           "fear", "risk", "cut", "layoff", "recession", "warn", "worst"]
    p = sum(1 for w in pos if w in hl)
    n = sum(1 for w in neg if w in hl)
    if p + n == 0:
        return 0.0, "Neutral"
    score = round((p - n) / (p + n), 2)
    if score > 0.3:
        return score, "Bullish"
    elif score < -0.3:
        return score, "Bearish"
    return score, "Neutral"


@st.cache_data(ttl=900, show_spinner="Calculating Fear & Greed Index...")
def get_fear_greed() -> dict:
    """Calculate current Fear & Greed index."""
    vix_score = _calc_vix_score()
    momentum_score = _calc_momentum_score()
    volume_score = _calc_volume_score()

    components = [s for s in [vix_score, momentum_score, volume_score] if s is not None]
    overall = round(max(0, min(100, sum(components) / len(components))), 1) if components else 50.0
    label = _score_to_label(overall)

    return {
        "score": overall, "label": label,
        "vix_score": round(vix_score, 1) if vix_score is not None else None,
        "momentum_score": round(momentum_score, 1) if momentum_score is not None else None,
        "volume_score": round(volume_score, 1) if volume_score is not None else None,
        "updated_at": datetime.now().isoformat(),
    }


def _calc_vix_score() -> float | None:
    vix = _data_provider.get_vix_current()
    if vix is None:
        return None
    return max(0, min(100, ((40 - vix) / 28) * 100))


def _calc_momentum_score() -> float | None:
    df = _data_provider.get_daily_prices("^GSPC", period="6mo")
    if df.empty or len(df) < 20:
        return None
    close = pd.to_numeric(df["close"], errors="coerce").dropna()
    if len(close) < 20:
        return None
    current = close.iloc[-1]
    ma = close.tail(min(125, len(close))).mean()
    if ma == 0:
        return 50.0
    pct_diff = ((current - ma) / ma) * 100
    return max(0, min(100, 50 + pct_diff * 5))


def _calc_volume_score() -> float | None:
    df = _data_provider.get_daily_prices("^GSPC", period="3m")
    if df.empty or len(df) < 10:
        return None
    close = pd.to_numeric(df["close"], errors="coerce")
    volume = pd.to_numeric(df["volume"], errors="coerce")
    changes = close.diff()
    up_vol = volume[changes > 0].sum()
    down_vol = volume[changes < 0].sum()
    if down_vol == 0:
        return 80.0
    if up_vol == 0:
        return 20.0
    ratio = up_vol / down_vol
    return max(0, min(100, (ratio - 0.5) * 100))


def get_market_news() -> list[dict]:
    """Get market news with auto-sentiment. Cached in session_state."""
    cache_key = "_market_news_cache"
    if cache_key not in st.session_state:
        articles = _news_provider.get_market_news()
        for a in articles:
            score, label = _quick_sentiment(a.get("headline", ""))
            a["sentiment"] = score
            a["sentiment_label"] = label
        if articles:
            st.session_state[cache_key] = articles
        return articles
    return st.session_state[cache_key]


def get_stock_news(ticker: str) -> list[dict]:
    """Get stock news with auto-sentiment. Cached in session_state per ticker."""
    cache_key = f"_stock_news_{ticker}"
    if cache_key not in st.session_state:
        articles = _news_provider.get_stock_news(ticker)
        for a in articles:
            score, label = _quick_sentiment(a.get("headline", ""))
            a["sentiment"] = score
            a["sentiment_label"] = label
        if articles:
            st.session_state[cache_key] = articles
        return articles
    return st.session_state[cache_key]


def analyze_with_ai(headlines: list[str]) -> list[dict] | None:
    """Run Claude sentiment analysis (user-triggered only)."""
    return _llm_provider.analyze_sentiment(headlines)


def generate_report() -> str | None:
    """Generate AI market report (user-triggered only)."""
    indices = _data_provider.get_indices()
    market_data = {"date": str(date.today()), "indices": indices}
    return _llm_provider.generate_market_report(market_data)
