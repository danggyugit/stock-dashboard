"""Sentiment analysis API router.

Provides endpoints for Fear & Greed index, news with sentiment,
sentiment trends, and AI-generated market reports.
"""

import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from models.sentiment import (
    DailyReport,
    FearGreedData,
    FearGreedHistory,
    NewsResponse,
    SentimentTrendResponse,
)
from services.sentiment_service import SentimentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sentiment", tags=["sentiment"])

_service: SentimentService | None = None


def _get_service() -> SentimentService:
    """Get or create SentimentService singleton."""
    global _service  # noqa: PLW0603
    if _service is None:
        _service = SentimentService()
    return _service


@router.get("/fear-greed", response_model=FearGreedData)
def get_fear_greed() -> dict:
    """Get current Fear & Greed index value and components.

    Returns:
        Fear & Greed score (0-100), label, and component breakdown.
    """
    try:
        service = _get_service()
        return service.get_fear_greed()
    except Exception:
        logger.exception("Error calculating Fear & Greed index.")
        raise HTTPException(status_code=500, detail="Failed to calculate Fear & Greed index.")


@router.get("/fear-greed/history", response_model=list[FearGreedHistory])
def get_fear_greed_history(
    days: int = Query(default=30, description="Number of days (30 or 90)"),
) -> list[dict]:
    """Get Fear & Greed score history.

    Args:
        days: Number of days to look back.

    Returns:
        List of daily F&G scores.
    """
    if days not in (30, 90):
        days = 30

    try:
        service = _get_service()
        return service.get_fear_greed_history(days=days)
    except Exception:
        logger.exception("Error fetching Fear & Greed history.")
        raise HTTPException(status_code=500, detail="Failed to fetch Fear & Greed history.")


@router.get("/news", response_model=NewsResponse)
def get_news(
    ticker: str | None = Query(default=None, description="Filter by ticker"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    """Get news articles with sentiment analysis data.

    Args:
        ticker: Optional ticker filter.
        page: Page number.
        page_size: Items per page.

    Returns:
        Paginated news list with sentiment scores.
    """
    try:
        service = _get_service()
        return service.get_news(ticker=ticker, page=page, page_size=page_size)
    except Exception:
        logger.exception("Error fetching news.")
        raise HTTPException(status_code=500, detail="Failed to fetch news.")


class AnalyzeRequest(BaseModel):
    """Request body for triggering sentiment analysis."""
    ticker: str | None = None


@router.post("/analyze")
def analyze_news(request: AnalyzeRequest | None = None) -> dict:
    """Trigger news sentiment analysis using LLM (manual trigger).

    Fetches latest news and runs Claude sentiment analysis.
    This is a manual trigger to control API costs.

    Args:
        request: Optional request with ticker filter.

    Returns:
        Analysis results with count and status.
    """
    ticker = request.ticker if request else None
    try:
        service = _get_service()
        return service.analyze_news(ticker=ticker)
    except Exception:
        logger.exception("Error analyzing news sentiment.")
        raise HTTPException(status_code=500, detail="Failed to analyze news.")


@router.get("/trend/{ticker}", response_model=SentimentTrendResponse)
def get_sentiment_trend(
    ticker: str,
    days: int = Query(default=30, ge=7, le=90),
) -> dict:
    """Get sentiment trend for a specific stock.

    Args:
        ticker: Stock ticker symbol.
        days: Number of days to look back.

    Returns:
        Daily sentiment scores and article counts.
    """
    try:
        service = _get_service()
        return service.get_sentiment_trend(ticker.upper(), days=days)
    except Exception:
        logger.exception("Error fetching sentiment trend for %s.", ticker)
        raise HTTPException(status_code=500, detail="Failed to fetch sentiment trend.")


@router.get("/report", response_model=DailyReport)
def get_daily_report() -> dict:
    """Get today's AI-generated market report.

    Returns:
        Daily report content or 404 if not generated yet.
    """
    try:
        service = _get_service()
        result = service.get_daily_report()
        if result is None:
            raise HTTPException(
                status_code=404,
                detail="No report generated for today. Use POST /api/sentiment/report/generate.",
            )
        return result
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error fetching daily report.")
        raise HTTPException(status_code=500, detail="Failed to fetch daily report.")


@router.post("/report/generate")
def generate_report() -> dict:
    """Generate AI daily market report (manual trigger).

    Collects market data and uses Claude to generate analysis.
    This is a manual trigger to control API costs.

    Returns:
        Generated report content and status.
    """
    try:
        service = _get_service()
        return service.generate_report()
    except Exception:
        logger.exception("Error generating daily report.")
        raise HTTPException(status_code=500, detail="Failed to generate report.")
