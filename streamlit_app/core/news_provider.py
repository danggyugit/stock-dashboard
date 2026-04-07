"""News collection provider using Finnhub + yfinance."""

import logging
from datetime import date, datetime, timedelta

import streamlit as st
import yfinance as yf

logger = logging.getLogger(__name__)


def _get_finnhub_key() -> str:
    """Get Finnhub API key from Streamlit secrets."""
    try:
        return st.secrets.get("FINNHUB_API_KEY", "")
    except Exception:
        return ""


class NewsProvider:
    """News data provider using Finnhub API + yfinance."""

    def __init__(self) -> None:
        self._client = None
        key = _get_finnhub_key()
        if key:
            try:
                import finnhub
                self._client = finnhub.Client(api_key=key)
            except Exception:
                logger.warning("Finnhub client init failed.")

    def _get_yfinance_news(self, tickers: list[str] | None = None) -> list[dict]:
        """Fetch news via yfinance as supplementary source."""
        if tickers is None:
            tickers = ["^GSPC", "^IXIC", "AAPL", "MSFT", "NVDA"]

        articles: list[dict] = []
        seen: set[str] = set()

        for ticker in tickers[:5]:
            try:
                news = yf.Ticker(ticker).news or []
                for item in news[:10]:
                    content = item.get("content", {})
                    title = content.get("title") or item.get("title", "")
                    if not title or title in seen:
                        continue
                    seen.add(title)

                    pub_date = content.get("pubDate") or item.get("providerPublishTime")
                    if isinstance(pub_date, (int, float)):
                        pub_date = datetime.fromtimestamp(pub_date).isoformat()

                    provider = content.get("provider", {})
                    source = provider.get("displayName", "") if isinstance(provider, dict) else str(provider)

                    link = content.get("canonicalUrl", {})
                    url = link.get("url", "") if isinstance(link, dict) else ""

                    articles.append({
                        "headline": title,
                        "summary": (content.get("summary", "") or "")[:300],
                        "source": source,
                        "url": url,
                        "published_at": pub_date,
                        "ticker": ticker if not ticker.startswith("^") else None,
                    })
            except Exception:
                pass
        return articles

    def get_market_news(self, category: str = "general") -> list[dict]:
        """Fetch general market news from Finnhub + yfinance."""
        articles: list[dict] = []

        if self._client:
            try:
                news = self._client.general_news(category, min_id=0)
                for item in news[:30]:
                    articles.append({
                        "headline": item.get("headline", ""),
                        "summary": item.get("summary", ""),
                        "source": item.get("source", ""),
                        "url": item.get("url", ""),
                        "published_at": datetime.fromtimestamp(item["datetime"]).isoformat()
                        if item.get("datetime") else None,
                        "ticker": None,
                    })
            except Exception:
                pass

        yf_articles = self._get_yfinance_news()
        seen = {a["headline"] for a in articles}
        for a in yf_articles:
            if a["headline"] not in seen:
                articles.append(a)

        return articles[:50]

    def get_stock_news(
        self, ticker: str,
        from_date: date | None = None, to_date: date | None = None,
    ) -> list[dict]:
        """Fetch news for a specific stock."""
        if from_date is None:
            from_date = date.today() - timedelta(days=7)
        if to_date is None:
            to_date = date.today()

        articles: list[dict] = []

        # Finnhub company_news — accept all results (Finnhub already filters by ticker)
        if self._client:
            try:
                news = self._client.company_news(
                    ticker,
                    _from=from_date.strftime("%Y-%m-%d"),
                    to=to_date.strftime("%Y-%m-%d"),
                )
                for item in news[:20]:
                    hl = item.get("headline", "")
                    if not hl:
                        continue
                    articles.append({
                        "headline": hl,
                        "summary": item.get("summary", ""),
                        "source": item.get("source", ""),
                        "url": item.get("url", ""),
                        "published_at": datetime.fromtimestamp(item["datetime"]).isoformat()
                        if item.get("datetime") else None,
                        "ticker": ticker,
                    })
            except Exception:
                pass

        # yfinance news — accept all (already fetched for this ticker)
        yf_articles = self._get_yfinance_news([ticker])
        seen = {a["headline"] for a in articles}
        for a in yf_articles:
            if a["headline"] not in seen:
                a["ticker"] = ticker
                articles.append(a)

        return articles[:30]
