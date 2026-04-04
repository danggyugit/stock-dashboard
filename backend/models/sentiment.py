"""Pydantic models for sentiment endpoints."""

from datetime import datetime

from pydantic import BaseModel, Field


class NewsArticle(BaseModel):
    """News article with optional sentiment analysis."""

    id: int | None = None
    ticker: str | None = None
    headline: str
    summary: str | None = None
    source: str | None = None
    url: str | None = None
    published_at: datetime | None = None
    sentiment: float | None = None
    sentiment_label: str | None = None
    ai_summary: str | None = None
    analyzed_at: datetime | None = None


class NewsResponse(BaseModel):
    """Paginated news list response."""

    articles: list[NewsArticle] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class FearGreedData(BaseModel):
    """Current Fear & Greed index value."""

    score: float
    label: str
    vix_score: float | None = None
    momentum_score: float | None = None
    put_call_score: float | None = None
    high_low_score: float | None = None
    volume_score: float | None = None
    updated_at: str | None = None


class FearGreedHistory(BaseModel):
    """Fear & Greed historical data point."""

    date: str
    score: float
    label: str


class SentimentTrend(BaseModel):
    """Sentiment trend data point for a ticker."""

    date: str
    avg_sentiment: float
    article_count: int
    label: str | None = None


class SentimentTrendResponse(BaseModel):
    """Sentiment trend response."""

    ticker: str
    trend: list[SentimentTrend] = Field(default_factory=list)


class DailyReport(BaseModel):
    """AI-generated daily market report."""

    date: str
    content: str | None = None
    generated_at: str | None = None
