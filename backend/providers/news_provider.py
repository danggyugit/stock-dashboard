"""News collection provider using Finnhub + yfinance.

Fetches market and stock-specific news from Finnhub API,
with yfinance as a supplementary source for stock-specific news.
"""

import logging
from datetime import date, datetime, timedelta

import yfinance as yf

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

    def _get_yfinance_news(self, tickers: list[str] | None = None) -> list[dict]:
        """Fetch news via yfinance as supplementary source.

        Args:
            tickers: List of tickers. If None, uses major indices.

        Returns:
            List of news article dicts.
        """
        if tickers is None:
            tickers = ["^GSPC", "^IXIC", "AAPL", "MSFT", "NVDA"]

        articles: list[dict] = []
        seen_titles: set[str] = set()

        for ticker in tickers[:5]:
            try:
                stock = yf.Ticker(ticker)
                news = stock.news or []
                for item in news[:10]:
                    content = item.get("content", {})
                    title = content.get("title") or item.get("title", "")
                    if not title or title in seen_titles:
                        continue
                    seen_titles.add(title)

                    pub_date = content.get("pubDate") or item.get("providerPublishTime")
                    if isinstance(pub_date, (int, float)):
                        pub_date = datetime.fromtimestamp(pub_date).isoformat()

                    provider = content.get("provider", {})
                    source = provider.get("displayName", "") if isinstance(provider, dict) else str(provider)

                    link = content.get("canonicalUrl", {})
                    url = link.get("url", "") if isinstance(link, dict) else ""

                    summary = content.get("summary", "")

                    articles.append({
                        "headline": title,
                        "summary": summary[:300] if summary else "",
                        "source": source,
                        "url": url,
                        "published_at": pub_date,
                        "ticker": ticker if ticker[0] != "^" else None,
                    })
            except Exception:
                logger.debug("Failed to fetch yfinance news for %s.", ticker)

        logger.info("Fetched %d news articles from yfinance.", len(articles))
        return articles

    def get_market_news(self, category: str = "general") -> list[dict]:
        """Fetch general market news from Finnhub + yfinance.

        Args:
            category: News category for Finnhub.

        Returns:
            Combined list of news article dicts.
        """
        articles: list[dict] = []

        # Finnhub
        if self._client is not None:
            try:
                news = self._client.general_news(category, min_id=0)
                for item in news[:30]:
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
                logger.info("Fetched %d market news from Finnhub.", len(articles))
            except Exception:
                logger.exception("Failed to fetch Finnhub market news.")

        # yfinance supplement
        yf_articles = self._get_yfinance_news()
        seen = {a["headline"] for a in articles}
        for a in yf_articles:
            if a["headline"] not in seen:
                articles.append(a)

        return articles[:50]

    def get_stock_news(
        self,
        ticker: str,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[dict]:
        """Fetch news for a specific stock from Finnhub + yfinance.

        Args:
            ticker: Stock ticker symbol.
            from_date: Start date for Finnhub search. Defaults to 7 days ago.
            to_date: End date for Finnhub search. Defaults to today.

        Returns:
            Combined list of news article dicts for the specified ticker.
        """
        if from_date is None:
            from_date = date.today() - timedelta(days=7)
        if to_date is None:
            to_date = date.today()

        articles: list[dict] = []

        # Finnhub — filter to relevant headlines
        if self._client is not None:
            try:
                news = self._client.company_news(
                    ticker,
                    _from=from_date.strftime("%Y-%m-%d"),
                    to=to_date.strftime("%Y-%m-%d"),
                )
                ticker_lower = ticker.lower()
                for item in news[:50]:
                    hl = item.get("headline", "")
                    summary = item.get("summary", "")
                    text = (hl + " " + summary).lower()
                    if ticker_lower not in text:
                        continue
                    articles.append({
                        "headline": hl,
                        "summary": summary,
                        "source": item.get("source", ""),
                        "url": item.get("url", ""),
                        "published_at": datetime.fromtimestamp(item["datetime"]).isoformat()
                        if item.get("datetime")
                        else None,
                        "ticker": ticker,
                    })
                    if len(articles) >= 20:
                        break
                logger.info("Fetched %d relevant Finnhub news for %s.", len(articles), ticker)
            except Exception:
                logger.exception("Failed to fetch Finnhub news for %s.", ticker)

        # yfinance supplement — filter to only headlines mentioning the ticker or company
        yf_articles = self._get_yfinance_news([ticker])
        seen = {a["headline"] for a in articles}

        # Get company name for relevance check
        try:
            company_name = yf.Ticker(ticker).info.get("shortName", "")
        except Exception:
            company_name = ""
        name_words = [w.lower() for w in (company_name or "").split() if len(w) > 3]

        for a in yf_articles:
            hl = a["headline"]
            if hl in seen:
                continue
            hl_lower = hl.lower()
            # Keep only if headline mentions ticker or company name
            relevant = ticker.lower() in hl_lower or any(w in hl_lower for w in name_words)
            if relevant:
                a["ticker"] = ticker
                articles.append(a)

        return articles[:50]
