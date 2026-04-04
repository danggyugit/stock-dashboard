"""Market data API router.

Provides endpoints for heatmap, screener, indices, stock detail,
chart data, comparison, and search functionality.
"""

import logging

from fastapi import APIRouter, HTTPException, Query

from models.market import (
    ChartDataPoint,
    CompareResponse,
    HeatmapResponse,
    IndexInfo,
    SearchResult,
    ScreenerResult,
    StockDetail,
)
from services.market_service import MarketService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/market", tags=["market"])

_service: MarketService | None = None


def _get_service() -> MarketService:
    """Get or create MarketService singleton."""
    global _service  # noqa: PLW0603
    if _service is None:
        _service = MarketService()
    return _service


@router.get("/heatmap", response_model=HeatmapResponse)
def get_heatmap(
    period: str = Query(default="1d", description="Period: 1d, 1w, 1m, 3m, ytd, 1y"),
) -> dict:
    """Get sector-grouped heatmap data for market visualization.

    Args:
        period: Time period for change calculation.

    Returns:
        Heatmap data with sectors and stock changes.
    """
    try:
        service = _get_service()
        return service.get_heatmap_data(period=period)
    except Exception:
        logger.exception("Error fetching heatmap data.")
        raise HTTPException(status_code=500, detail="Failed to fetch heatmap data.")


@router.get("/screener")
def get_screener(
    sector: str | None = Query(default=None),
    industry: str | None = Query(default=None),
    min_cap: int | None = Query(default=None),
    max_cap: int | None = Query(default=None),
    min_pe: float | None = Query(default=None),
    max_pe: float | None = Query(default=None),
    min_dividend_yield: float | None = Query(default=None),
    max_dividend_yield: float | None = Query(default=None),
    min_volume: int | None = Query(default=None),
    sort_by: str = Query(default="market_cap"),
    sort_order: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> dict:
    """Get screener results with filtering and pagination.

    Returns:
        Filtered stock list with fundamentals.
    """
    try:
        service = _get_service()
        params = {
            "sector": sector,
            "industry": industry,
            "min_cap": min_cap,
            "max_cap": max_cap,
            "min_pe": min_pe,
            "max_pe": max_pe,
            "min_dividend_yield": min_dividend_yield,
            "max_dividend_yield": max_dividend_yield,
            "min_volume": min_volume,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "page": page,
            "page_size": page_size,
        }
        return service.get_screener_results(params)
    except Exception:
        logger.exception("Error fetching screener results.")
        raise HTTPException(status_code=500, detail="Failed to fetch screener results.")


@router.get("/indices", response_model=list[IndexInfo])
def get_indices() -> list[dict]:
    """Get major market indices (S&P 500, NASDAQ, Dow, VIX).

    Returns:
        List of index information with current prices and changes.
    """
    try:
        service = _get_service()
        return service.get_indices()
    except Exception:
        logger.exception("Error fetching indices.")
        raise HTTPException(status_code=500, detail="Failed to fetch indices.")


@router.get("/stock/{ticker}", response_model=StockDetail)
def get_stock_detail(ticker: str) -> dict:
    """Get detailed information for a specific stock.

    Args:
        ticker: Stock ticker symbol.

    Returns:
        Comprehensive stock information including price, fundamentals, and profile.
    """
    try:
        service = _get_service()
        result = service.get_stock_detail(ticker.upper())
        if result is None:
            raise HTTPException(status_code=404, detail=f"Stock {ticker} not found.")
        return result
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error fetching stock detail for %s.", ticker)
        raise HTTPException(status_code=500, detail="Failed to fetch stock detail.")


@router.get("/stock/{ticker}/chart", response_model=list[ChartDataPoint])
def get_stock_chart(
    ticker: str,
    period: str = Query(default="1mo", description="Period: 1d, 1w, 1m, 3m, 6m, 1y, 5y"),
    interval: str | None = Query(default=None, description="Interval: 1m, 5m, 1h, 1d, 1wk"),
) -> list[dict]:
    """Get chart data points for a stock.

    Args:
        ticker: Stock ticker symbol.
        period: Time period for chart.
        interval: Data granularity interval.

    Returns:
        List of OHLCV data points.
    """
    try:
        service = _get_service()
        return service.get_chart_data(ticker.upper(), period=period, interval=interval)
    except Exception:
        logger.exception("Error fetching chart data for %s.", ticker)
        raise HTTPException(status_code=500, detail="Failed to fetch chart data.")


@router.get("/stock/{ticker}/financials")
def get_stock_financials(ticker: str) -> dict:
    """Get financial metrics for a stock.

    Args:
        ticker: Stock ticker symbol.

    Returns:
        Fundamental financial metrics.
    """
    try:
        service = _get_service()
        result = service.get_financials(ticker.upper())
        if result is None:
            raise HTTPException(status_code=404, detail=f"Financials for {ticker} not found.")
        return result
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error fetching financials for %s.", ticker)
        raise HTTPException(status_code=500, detail="Failed to fetch financials.")


@router.get("/compare", response_model=CompareResponse)
def get_compare(
    tickers: str = Query(description="Comma-separated ticker symbols (2-5)"),
    period: str = Query(default="1m"),
) -> dict:
    """Compare multiple stocks side by side.

    Args:
        tickers: Comma-separated list of ticker symbols.
        period: Time period for comparison.

    Returns:
        Comparison data with price histories and metrics.
    """
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if len(ticker_list) < 2 or len(ticker_list) > 5:
        raise HTTPException(
            status_code=400, detail="Provide 2-5 ticker symbols, comma-separated."
        )

    try:
        service = _get_service()
        return service.get_compare_data(ticker_list, period=period)
    except Exception:
        logger.exception("Error fetching compare data.")
        raise HTTPException(status_code=500, detail="Failed to fetch comparison data.")


@router.get("/search", response_model=list[SearchResult])
def search_stocks(
    q: str = Query(description="Search query (ticker or company name)"),
) -> list[dict]:
    """Search stocks by ticker or company name for autocomplete.

    Args:
        q: Search query string.

    Returns:
        List of matching stocks (max 20).
    """
    if not q or len(q) < 1:
        return []

    try:
        service = _get_service()
        return service.search_stocks(q)
    except Exception:
        logger.exception("Error searching stocks.")
        raise HTTPException(status_code=500, detail="Failed to search stocks.")


@router.get("/stock/{ticker}/close")
def get_close_price(
    ticker: str,
    date: str = Query(description="Date in YYYY-MM-DD format"),
) -> dict:
    """Get closing price for a stock on a specific date.

    Uses yfinance with date range to fetch the exact day's close.

    Args:
        ticker: Stock ticker symbol.
        date: Target date (YYYY-MM-DD).

    Returns:
        Dict with ticker, date, and close price.
    """
    try:
        import yfinance as yf
        from datetime import datetime, timedelta

        target = datetime.strptime(date[:10], "%Y-%m-%d")
        # Fetch a 7-day window around the target to handle weekends/holidays
        start = (target - timedelta(days=5)).strftime("%Y-%m-%d")
        end = (target + timedelta(days=1)).strftime("%Y-%m-%d")

        stock = yf.Ticker(ticker.upper())
        df = stock.history(start=start, end=end)

        if df.empty:
            return {"ticker": ticker.upper(), "date": date, "close": None}

        # Get the closest date <= target
        df = df.reset_index()
        best_price = None
        for _, row in df.iterrows():
            row_date = row["Date"].strftime("%Y-%m-%d") if hasattr(row["Date"], "strftime") else str(row["Date"])[:10]
            if row_date <= date[:10]:
                best_price = float(row["Close"])

        return {
            "ticker": ticker.upper(),
            "date": date,
            "close": round(best_price, 2) if best_price else None,
        }
    except Exception:
        logger.exception("Error fetching close price for %s on %s.", ticker, date)
        return {"ticker": ticker.upper(), "date": date, "close": None}


@router.post("/refresh")
def refresh_market_data() -> dict:
    """Manually trigger market data refresh.

    Fetches latest S&P 500 stock list and updates the database.

    Returns:
        Refresh status with count of updated stocks.
    """
    try:
        service = _get_service()
        return service.refresh_market_data()
    except Exception:
        logger.exception("Error refreshing market data.")
        raise HTTPException(status_code=500, detail="Failed to refresh market data.")
