"""Sentiment analysis business logic service.

Handles Fear & Greed index calculation, news sentiment analysis,
trend tracking, and AI report generation.
"""

import logging
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

from db import get_connection
from providers.data_provider import MarketDataProvider
from providers.news_provider import NewsProvider
from providers.llm_provider import LLMProvider

logger = logging.getLogger(__name__)


def _score_to_label(score: float) -> str:
    """Convert a 0-100 Fear & Greed score to a label.

    Args:
        score: Numeric score from 0 to 100.

    Returns:
        Label string: Extreme Fear, Fear, Neutral, Greed, or Extreme Greed.
    """
    if score <= 20:
        return "Extreme Fear"
    elif score <= 40:
        return "Fear"
    elif score <= 60:
        return "Neutral"
    elif score <= 80:
        return "Greed"
    else:
        return "Extreme Greed"


class SentimentService:
    """Service layer for sentiment analysis operations."""

    def __init__(self) -> None:
        """Initialize SentimentService with providers."""
        self._data_provider = MarketDataProvider()
        self._news_provider = NewsProvider()
        self._llm_provider = LLMProvider()

    # --- Fear & Greed ---

    def get_fear_greed(self) -> dict:
        """Calculate current Fear & Greed index.

        Components (each 0-100, equal weight 25%):
        - VIX: Volatility index (inverted - low VIX = greed)
        - Momentum: S&P 500 vs 125-day moving average
        - Volume: Market trading volume vs average
        - High/Low: New 52-week highs vs lows ratio

        Returns:
            Dict with overall score, label, and component scores.
        """
        vix_score = self._calc_vix_score()
        momentum_score = self._calc_momentum_score()
        volume_score = self._calc_volume_score()
        high_low_score = self._calc_high_low_score()

        # Weighted average (25% each)
        components = [vix_score, momentum_score, volume_score, high_low_score]
        valid = [c for c in components if c is not None]

        if valid:
            overall = sum(valid) / len(valid)
        else:
            overall = 50.0  # Default to neutral

        overall = round(max(0, min(100, overall)), 1)
        label = _score_to_label(overall)

        result = {
            "score": overall,
            "label": label,
            "vix_score": round(vix_score, 1) if vix_score is not None else None,
            "momentum_score": round(momentum_score, 1) if momentum_score is not None else None,
            "put_call_score": None,  # Would require CBOE data
            "high_low_score": round(high_low_score, 1) if high_low_score is not None else None,
            "volume_score": round(volume_score, 1) if volume_score is not None else None,
            "updated_at": datetime.now().isoformat(),
        }

        # Save to history
        self._save_fear_greed(result)

        return result

    def _calc_vix_score(self) -> float | None:
        """Calculate VIX component score (0-100).

        Low VIX (~12) = Extreme Greed (100), High VIX (~40+) = Extreme Fear (0).
        """
        vix = self._data_provider.get_vix_current()
        if vix is None:
            return None

        # Linear mapping: VIX 12 -> 100, VIX 40 -> 0
        score = max(0, min(100, ((40 - vix) / 28) * 100))
        return score

    def _calc_momentum_score(self) -> float | None:
        """Calculate market momentum score (0-100).

        S&P 500 above 125-day MA = Greed, below = Fear.
        """
        df = self._data_provider.get_daily_prices("^GSPC", period="6mo")
        if df.empty or len(df) < 20:
            return None

        close = pd.to_numeric(df["close"], errors="coerce").dropna()
        if len(close) < 20:
            return None

        current = close.iloc[-1]
        # Use available data for moving average (up to 125 days)
        ma_period = min(125, len(close))
        ma = close.tail(ma_period).mean()

        if ma == 0:
            return 50.0

        # Percentage above/below MA
        pct_diff = ((current - ma) / ma) * 100

        # Map: +10% above MA = 100, -10% below MA = 0
        score = max(0, min(100, 50 + (pct_diff * 5)))
        return score

    def _calc_volume_score(self) -> float | None:
        """Calculate market volume score (0-100).

        Higher than average volume during up days = Greed.
        Higher volume on down days = Fear.
        """
        df = self._data_provider.get_daily_prices("^GSPC", period="3m")
        if df.empty or len(df) < 10:
            return None

        close = pd.to_numeric(df["close"], errors="coerce")
        volume = pd.to_numeric(df["volume"], errors="coerce")

        if close.isna().all() or volume.isna().all():
            return None

        # Calculate up/down volume ratio
        changes = close.diff()
        avg_volume = volume.mean()

        up_volume = volume[changes > 0].sum()
        down_volume = volume[changes < 0].sum()

        if down_volume == 0:
            return 80.0
        if up_volume == 0:
            return 20.0

        ratio = up_volume / down_volume
        # Map ratio: 1.5 = 100 (greed), 0.5 = 0 (fear)
        score = max(0, min(100, (ratio - 0.5) * 100))
        return score

    def _calc_high_low_score(self) -> float | None:
        """Calculate new highs vs new lows score (0-100).

        More new highs = Greed, more new lows = Fear.
        """
        breadth = self._data_provider.get_market_breadth()
        highs = breadth.get("new_highs", 0)
        lows = breadth.get("new_lows", 0)
        total = breadth.get("total", 0)

        if total == 0:
            return None

        if highs + lows == 0:
            return 50.0

        # Ratio of highs to total highs+lows
        ratio = highs / (highs + lows)
        score = ratio * 100
        return score

    def _save_fear_greed(self, data: dict) -> None:
        """Save Fear & Greed score to history table.

        Args:
            data: Fear & Greed data dict with component scores.
        """
        conn = get_connection()
        today = date.today()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO fear_greed_history
                (date, score, label, vix_score, momentum_score, put_call_score,
                 high_low_score, volume_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    today,
                    data["score"],
                    data["label"],
                    data.get("vix_score"),
                    data.get("momentum_score"),
                    data.get("put_call_score"),
                    data.get("high_low_score"),
                    data.get("volume_score"),
                ],
            )
        except Exception:
            logger.exception("Failed to save Fear & Greed history.")

    def get_fear_greed_history(self, days: int = 30) -> list[dict]:
        """Get Fear & Greed score history.

        Args:
            days: Number of days of history (30 or 90).

        Returns:
            List of daily F&G data points.
        """
        conn = get_connection()
        since = date.today() - timedelta(days=days)
        rows = conn.execute(
            """
            SELECT date, score, label
            FROM fear_greed_history
            WHERE date >= ?
            ORDER BY date ASC
            """,
            [since],
        ).fetchall()

        return [
            {"date": str(r[0]), "score": r[1], "label": r[2]}
            for r in rows
        ]

    # --- News ---

    def get_news(
        self, ticker: str | None = None, page: int = 1, page_size: int = 20
    ) -> dict:
        """Get news articles with sentiment data.

        Args:
            ticker: Optional ticker filter. None for market-wide news.
            page: Page number.
            page_size: Items per page.

        Returns:
            Dict with articles list, total count, and pagination.
        """
        conn = get_connection()
        offset = (page - 1) * page_size

        if ticker:
            total = conn.execute(
                "SELECT COUNT(*) FROM news_articles WHERE ticker = ?", [ticker]
            ).fetchone()[0]
            rows = conn.execute(
                """
                SELECT id, ticker, headline, summary, source, url, published_at,
                       sentiment, sentiment_label, ai_summary, analyzed_at
                FROM news_articles
                WHERE ticker = ?
                ORDER BY published_at DESC NULLS LAST
                LIMIT ? OFFSET ?
                """,
                [ticker, page_size, offset],
            ).fetchall()
        else:
            total = conn.execute("SELECT COUNT(*) FROM news_articles").fetchone()[0]
            rows = conn.execute(
                """
                SELECT id, ticker, headline, summary, source, url, published_at,
                       sentiment, sentiment_label, ai_summary, analyzed_at
                FROM news_articles
                ORDER BY published_at DESC NULLS LAST
                LIMIT ? OFFSET ?
                """,
                [page_size, offset],
            ).fetchall()

        articles = [
            {
                "id": r[0],
                "ticker": r[1],
                "headline": r[2],
                "summary": r[3],
                "source": r[4],
                "url": r[5],
                "published_at": r[6].isoformat() if r[6] else None,
                "sentiment": r[7],
                "sentiment_label": r[8],
                "ai_summary": r[9],
                "analyzed_at": r[10].isoformat() if r[10] else None,
            }
            for r in rows
        ]

        return {
            "articles": articles,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def analyze_news(self, ticker: str | None = None) -> dict:
        """Fetch and analyze news sentiment using LLM.

        Fetches news from Finnhub, stores in DB, then runs Claude
        sentiment analysis on headlines.

        Args:
            ticker: Optional ticker for stock-specific news.

        Returns:
            Dict with analysis results (count analyzed, status).
        """
        # Fetch news
        if ticker:
            articles = self._news_provider.get_stock_news(ticker)
        else:
            articles = self._news_provider.get_market_news()

        if not articles:
            return {"analyzed": 0, "status": "no_news", "message": "No news articles found."}

        conn = get_connection()

        # Store articles in DB
        for article in articles:
            new_id = conn.execute("SELECT nextval('seq_news_id')").fetchone()[0]
            try:
                conn.execute(
                    """
                    INSERT INTO news_articles (id, ticker, headline, summary, source, url, published_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        new_id,
                        article.get("ticker"),
                        article["headline"],
                        article.get("summary"),
                        article.get("source"),
                        article.get("url"),
                        article.get("published_at"),
                    ],
                )
            except Exception:
                logger.debug("Duplicate or failed insert for news article.")

        # Run sentiment analysis via LLM
        headlines = [a["headline"] for a in articles if a.get("headline")]
        if not headlines:
            return {"analyzed": 0, "status": "no_headlines"}

        sentiments = self._llm_provider.analyze_sentiment(headlines)
        if sentiments is None:
            return {
                "analyzed": 0,
                "status": "llm_unavailable",
                "message": "LLM analysis unavailable. News articles stored without sentiment.",
            }

        # Update articles with sentiment
        analyzed_count = 0
        for sent in sentiments:
            headline = sent.get("headline", "")
            score = sent.get("score", 0)
            label = sent.get("label", "Neutral")
            try:
                conn.execute(
                    """
                    UPDATE news_articles
                    SET sentiment = ?, sentiment_label = ?, analyzed_at = current_timestamp
                    WHERE headline = ? AND analyzed_at IS NULL
                    """,
                    [score, label, headline],
                )
                analyzed_count += 1
            except Exception:
                logger.debug("Failed to update sentiment for article.")

        return {
            "analyzed": analyzed_count,
            "status": "ok",
            "message": f"Analyzed {analyzed_count} articles.",
        }

    def get_sentiment_trend(self, ticker: str, days: int = 30) -> dict:
        """Get sentiment trend for a specific stock.

        Args:
            ticker: Stock ticker symbol.
            days: Number of days to look back.

        Returns:
            Dict with ticker and trend data points.
        """
        conn = get_connection()
        since = date.today() - timedelta(days=days)

        rows = conn.execute(
            """
            SELECT
                CAST(published_at AS DATE) as pub_date,
                AVG(sentiment) as avg_sentiment,
                COUNT(*) as article_count
            FROM news_articles
            WHERE ticker = ?
                AND published_at >= ?
                AND sentiment IS NOT NULL
            GROUP BY CAST(published_at AS DATE)
            ORDER BY pub_date ASC
            """,
            [ticker, since],
        ).fetchall()

        trend = []
        for r in rows:
            avg_sent = r[1] if r[1] is not None else 0
            label = "Neutral"
            if avg_sent > 0.3:
                label = "Bullish"
            elif avg_sent > 0.6:
                label = "Very Bullish"
            elif avg_sent < -0.3:
                label = "Bearish"
            elif avg_sent < -0.6:
                label = "Very Bearish"

            trend.append({
                "date": str(r[0]),
                "avg_sentiment": round(avg_sent, 3),
                "article_count": r[2],
                "label": label,
            })

        return {"ticker": ticker, "trend": trend}

    # --- Daily Report ---

    def get_daily_report(self) -> dict | None:
        """Get today's AI-generated market report.

        Returns:
            Report dict or None if no report exists for today.
        """
        conn = get_connection()
        today = date.today()
        row = conn.execute(
            "SELECT date, content, generated_at FROM daily_reports WHERE date = ?",
            [today],
        ).fetchone()

        if not row:
            return None

        return {
            "date": str(row[0]),
            "content": row[1],
            "generated_at": row[2].isoformat() if row[2] else None,
        }

    def generate_report(self) -> dict:
        """Generate AI daily market report using Claude.

        Collects market data (indices, top movers) and sends to LLM
        for analysis and report generation.

        Returns:
            Dict with report content and status.
        """
        # Collect market data for report
        indices = self._data_provider.get_indices()

        # Get S&P 500 prices for top movers
        sp500 = self._data_provider.get_stock_list()
        sample_tickers = sp500["ticker"].head(50).tolist() if not sp500.empty else []
        batch = self._data_provider.get_batch_prices(sample_tickers, period="5d")

        # Find top gainers/losers
        changes: list[tuple[str, float]] = []
        for ticker, df in batch.items():
            if not df.empty and len(df) >= 2:
                first = df["close"].iloc[0]
                last = df["close"].iloc[-1]
                if first and first != 0:
                    pct = ((last - first) / first) * 100
                    changes.append((ticker, round(pct, 2)))

        changes.sort(key=lambda x: x[1], reverse=True)
        top_gainers = changes[:5] if changes else []
        top_losers = changes[-5:] if changes else []

        market_data = {
            "date": str(date.today()),
            "indices": indices,
            "top_gainers": [{"ticker": t, "change_pct": c} for t, c in top_gainers],
            "top_losers": [{"ticker": t, "change_pct": c} for t, c in top_losers],
        }

        report_content = self._llm_provider.generate_market_report(market_data)
        if report_content is None:
            return {
                "date": str(date.today()),
                "content": None,
                "generated_at": None,
                "status": "llm_unavailable",
                "message": "LLM unavailable. Cannot generate report.",
            }

        # Save to DB
        conn = get_connection()
        conn.execute(
            """
            INSERT OR REPLACE INTO daily_reports (date, content, generated_at)
            VALUES (?, ?, current_timestamp)
            """,
            [date.today(), report_content],
        )

        return {
            "date": str(date.today()),
            "content": report_content,
            "generated_at": datetime.now().isoformat(),
            "status": "ok",
        }
