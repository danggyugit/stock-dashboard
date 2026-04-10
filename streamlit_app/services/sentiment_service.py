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


@st.cache_data(ttl=900, show_spinner=False)
def get_market_news() -> list[dict]:
    """Get market news with auto-sentiment. Cached 15 min."""
    articles = _news_provider.get_market_news()
    for a in articles:
        score, label = _quick_sentiment(a.get("headline", ""))
        a["sentiment"] = score
        a["sentiment_label"] = label
    return articles


@st.cache_data(ttl=900, show_spinner=False)
def get_stock_news(ticker: str) -> list[dict]:
    """Get stock news with auto-sentiment. Cached 15 min per ticker."""
    articles = _news_provider.get_stock_news(ticker)
    for a in articles:
        score, label = _quick_sentiment(a.get("headline", ""))
        a["sentiment"] = score
        a["sentiment_label"] = label
    return articles


# ═══════════════════════════════════════════════════════════
# Market Sentiment Indicators (yfinance-based)
# ═══════════════════════════════════════════════════════════

@st.cache_data(ttl=1800, show_spinner=False)
def get_vix_history(days: int = 90) -> pd.DataFrame:
    """VIX closing prices for the last N days."""
    import yfinance as yf
    try:
        df = yf.download("^VIX", period=f"{days}d", auto_adjust=True, progress=False)
        if df.empty:
            return pd.DataFrame()
        close = df["Close"].squeeze()
        return pd.DataFrame({"date": close.index, "VIX": close.values})
    except Exception:
        return pd.DataFrame()


_SECTOR_ETFS = {
    "XLK": "Technology", "XLF": "Financials", "XLV": "Healthcare",
    "XLY": "Cons. Disc.", "XLP": "Cons. Staples", "XLE": "Energy",
    "XLI": "Industrials", "XLB": "Materials", "XLRE": "Real Estate",
    "XLC": "Comm. Svc.", "XLU": "Utilities",
}


@st.cache_data(ttl=1800, show_spinner=False)
def get_sector_returns() -> pd.DataFrame:
    """1-week and 1-month returns for 11 GICS sector ETFs."""
    import yfinance as yf
    tickers = list(_SECTOR_ETFS.keys())
    try:
        df = yf.download(tickers, period="35d", auto_adjust=True, progress=False)
        if df.empty:
            return pd.DataFrame()
        close = df["Close"]
        if isinstance(close, pd.Series):
            close = close.to_frame()
    except Exception:
        return pd.DataFrame()

    rows = []
    for tk, name in _SECTOR_ETFS.items():
        if tk not in close.columns:
            continue
        s = close[tk].dropna()
        if len(s) < 6:
            continue
        ret_1w = (s.iloc[-1] / s.iloc[-5] - 1) * 100 if len(s) >= 6 else np.nan
        ret_1m = (s.iloc[-1] / s.iloc[0] - 1) * 100
        rows.append({"Sector": name, "Ticker": tk, "1W %": round(ret_1w, 2), "1M %": round(ret_1m, 2)})
    return pd.DataFrame(rows)


@st.cache_data(ttl=3600, show_spinner=False)
def get_market_breadth() -> dict:
    """Percentage of S&P 500 stocks above their 200-day SMA."""
    import yfinance as yf
    try:
        # Use a pre-built breadth indicator proxy
        # S&P 500 vs SMA200 ratio as breadth estimate
        df = yf.download("^GSPC", period="250d", auto_adjust=True, progress=False)
        if df.empty or len(df) < 200:
            return {}
        close = df["Close"].squeeze()
        sma200 = close.rolling(200).mean()
        # Latest: is S&P above its SMA200?
        above_pct = (close.iloc[-1] / sma200.iloc[-1] - 1) * 100

        # Build daily breadth-like series: close vs SMA200 spread
        spread = ((close / sma200) - 1) * 100
        spread = spread.dropna()
        return {
            "above_pct": round(above_pct, 2),
            "spread_series": spread,
            "current_close": round(float(close.iloc[-1]), 2),
            "current_sma200": round(float(sma200.iloc[-1]), 2),
        }
    except Exception:
        return {}


@st.cache_data(ttl=1800, show_spinner=False)
def get_risk_on_off(days: int = 90) -> pd.DataFrame:
    """XLY/XLP ratio as Risk-On/Off indicator."""
    import yfinance as yf
    try:
        df = yf.download(["XLY", "XLP"], period=f"{days}d", auto_adjust=True, progress=False)
        if df.empty:
            return pd.DataFrame()
        close = df["Close"]
        ratio = (close["XLY"] / close["XLP"]).dropna()
        result = pd.DataFrame({"date": ratio.index, "XLY/XLP": ratio.values})
        return result
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=86400, show_spinner=False)
def get_money_supply() -> pd.DataFrame:
    """M1 & M2 money supply from FRED (monthly, seasonally adjusted)."""
    try:
        m1_url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=M1SL&cosd=2021-01-01"
        m2_url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=M2SL&cosd=2021-01-01"
        m1 = pd.read_csv(m1_url)
        m2 = pd.read_csv(m2_url)
        # FRED CSV uses 'observation_date' as the date column
        m1_date_col = [c for c in m1.columns if "date" in c.lower()][0]
        m2_date_col = [c for c in m2.columns if "date" in c.lower()][0]
        m1 = m1.rename(columns={m1_date_col: "date"})
        m2 = m2.rename(columns={m2_date_col: "date"})
        m1["date"] = pd.to_datetime(m1["date"])
        m2["date"] = pd.to_datetime(m2["date"])
        m1_val_col = [c for c in m1.columns if c != "date"][0]
        m2_val_col = [c for c in m2.columns if c != "date"][0]
        m1 = m1.rename(columns={m1_val_col: "M1"})
        m2 = m2.rename(columns={m2_val_col: "M2"})
        df = pd.merge(m1[["date", "M1"]], m2[["date", "M2"]], on="date", how="outer").sort_values("date")
        df["M1"] = pd.to_numeric(df["M1"], errors="coerce")
        df["M2"] = pd.to_numeric(df["M2"], errors="coerce")
        df = df.dropna(subset=["M1", "M2"])
        # Convert billions to trillions for readability
        df["M1"] = df["M1"] / 1000
        df["M2"] = df["M2"] / 1000
        return df
    except Exception:
        return pd.DataFrame()


def analyze_with_ai(headlines: list[str]) -> list[dict] | None:
    """Run Claude sentiment analysis (user-triggered only)."""
    return _llm_provider.analyze_sentiment(headlines)


def generate_report() -> str | None:
    """Generate AI market report (user-triggered only)."""
    indices = _data_provider.get_indices()
    market_data = {"date": str(date.today()), "indices": indices}
    return _llm_provider.generate_market_report(market_data)
