"""Finnhub-based news collection provider.

Fetches market and stock-specific news from Finnhub API.
Gracefully handles missing API key by returning empty results.
"""

import logging
from datetime import date, datetime, timedelta

from config import get_settings

logger = logging.getLogger(__name__)


class NewsProvider:
    """News data provider using Finnhub API."""

    def __init__(self) -> None:
        """Initialize NewsProvider with Finnhub client if API key is available."""
        self._client = None
        settings = get_settings()
        if settings.FINNHUB_API_KEY:
            try:
                import finnhub

                self._client = finnhub.Client(api_key=settings.FINNHUB_API_KEY)
                logger.info("Finnhub client initialized.")
            except ImportError:
                logger.warning("finnhub-python package not installed.")
            except Exception:
                logger.exception("Failed to initialize Finnhub client.")
        else:
            logger.warning("FINNHUB_API_KEY not set. News features disabled.")

    def get_market_news(self, category: str = "general") -> list[dict]:
        """Fetch general market news.

        Args:
            category: News category (e.g., 'general', 'forex', 'crypto').

        Returns:
            List of news article dicts with headline, summary, source, url,
            published_at. Returns empty list if API unavailable.
        """
        if self._client is None:
            logger.debug("Finnhub client not available. Returning empty news list.")
            return []

        try:
            news = self._client.general_news(category, min_id=0)
            articles: list[dict] = []
            for item in news[:50]:  # Limit to 50 articles
                articles.append({
                    "headline": item.get("headline", ""),
                    "summary": item.get("summary", ""),
                    "source": item.get("source", ""),
                    "url": item.get("url", ""),
                    "published_at": datetime.fromtimestamp(item["datetime"]).isoformat()
                    if item.get("datetime")
                    else None,
                    "ticker": None,
                })
            logger.info("Fetched %d market news articles.", len(articles))
            return articles
        except Exception:
            logger.exception("Failed to fetch market news.")
            return []

    def get_stock_news(
        self,
        ticker: str,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[dict]:
        """Fetch news for a specific stock.

        Args:
            ticker: Stock ticker symbol.
            from_date: Start date for news search. Defaults to 7 days ago.
            to_date: End date for news search. Defaults to today.

        Returns:
            List of news article dicts for the specified ticker.
            Returns empty list if API unavailable.
        """
        if self._client is None:
            logger.debug("Finnhub client not available. Returning empty news list.")
            return []

        if from_date is None:
            from_date = date.today() - timedelta(days=7)
        if to_date is None:
            to_date = date.today()

        try:
            news = self._client.company_news(
                ticker,
                _from=from_date.strftime("%Y-%m-%d"),
                to=to_date.strftime("%Y-%m-%d"),
            )
            articles: list[dict] = []
            for item in news[:50]:  # Limit to 50 articles
                articles.append({
                    "headline": item.get("headline", ""),
                    "summary": item.get("summary", ""),
                    "source": item.get("source", ""),
                    "url": item.get("url", ""),
                    "published_at": datetime.fromtimestamp(item["datetime"]).isoformat()
                    if item.get("datetime")
                    else None,
                    "ticker": ticker,
                })
            logger.info("Fetched %d news articles for %s.", len(articles), ticker)
            return articles
        except Exception:
            logger.exception("Failed to fetch news for %s.", ticker)
            return []
