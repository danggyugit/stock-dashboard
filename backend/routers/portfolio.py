"""Portfolio management API router.

Provides endpoints for portfolio CRUD, trade management, holdings,
allocation, performance, dividends, and tax calculation.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File

from models.portfolio import (
    AllocationResponse,
    DividendSummary,
    PerformanceResponse,
    PortfolioCreate,
    PortfolioResponse,
    PortfolioSummary,
    TaxSummary,
    TradeCreate,
    TradeResponse,
    TradeUpdate,
)
from services.portfolio_service import PortfolioService
from auth import get_current_user, get_optional_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

_service: PortfolioService | None = None


def _get_service() -> PortfolioService:
    """Get or create PortfolioService singleton."""
    global _service  # noqa: PLW0603
    if _service is None:
        _service = PortfolioService()
    return _service


@router.get("")
def get_portfolios(user_id: int | None = Depends(get_optional_user)) -> list[dict]:
    """Get portfolios for the authenticated user (or all if not logged in).

    Returns:
        List of portfolio summaries.
    """
    try:
        service = _get_service()
        return service.get_portfolios(user_id=user_id)
    except Exception:
        logger.exception("Error fetching portfolios.")
        raise HTTPException(status_code=500, detail="Failed to fetch portfolios.")


@router.post("", response_model=PortfolioResponse)
def create_portfolio(data: PortfolioCreate, user_id: int | None = Depends(get_optional_user)) -> dict:
    """Create a new portfolio.

    Args:
        data: Portfolio creation data (name, description).

    Returns:
        Created portfolio information.
    """
    try:
        service = _get_service()
        return service.create_portfolio(name=data.name, description=data.description, user_id=user_id)
    except Exception:
        logger.exception("Error creating portfolio.")
        raise HTTPException(status_code=500, detail="Failed to create portfolio.")


@router.get("/{portfolio_id}", response_model=PortfolioSummary)
def get_portfolio_detail(portfolio_id: int) -> dict:
    """Get portfolio detail with current holdings and P&L.

    Args:
        portfolio_id: Portfolio ID.

    Returns:
        Portfolio summary with holdings and performance metrics.
    """
    try:
        service = _get_service()
        result = service.get_holdings(portfolio_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Portfolio not found.")
        return result
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error fetching portfolio %d.", portfolio_id)
        raise HTTPException(status_code=500, detail="Failed to fetch portfolio detail.")


@router.delete("/{portfolio_id}")
def delete_portfolio(portfolio_id: int) -> dict:
    """Delete a portfolio and all associated data.

    Args:
        portfolio_id: Portfolio ID to delete.

    Returns:
        Deletion status.
    """
    try:
        service = _get_service()
        deleted = service.delete_portfolio(portfolio_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Portfolio not found.")
        return {"status": "ok", "message": f"Portfolio {portfolio_id} deleted."}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error deleting portfolio %d.", portfolio_id)
        raise HTTPException(status_code=500, detail="Failed to delete portfolio.")


@router.get("/{portfolio_id}/trades")
def get_trades(
    portfolio_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> dict:
    """Get paginated trade history for a portfolio.

    Args:
        portfolio_id: Portfolio ID.
        page: Page number.
        page_size: Items per page.

    Returns:
        Paginated trade list.
    """
    try:
        service = _get_service()
        return service.get_trades(portfolio_id, page=page, page_size=page_size)
    except Exception:
        logger.exception("Error fetching trades for portfolio %d.", portfolio_id)
        raise HTTPException(status_code=500, detail="Failed to fetch trades.")


@router.post("/{portfolio_id}/trades", response_model=TradeResponse)
def add_trade(portfolio_id: int, data: TradeCreate) -> dict:
    """Add a new trade to a portfolio.

    Args:
        portfolio_id: Target portfolio ID.
        data: Trade data.

    Returns:
        Created trade information.
    """
    if data.trade_type.upper() not in ("BUY", "SELL"):
        raise HTTPException(status_code=400, detail="trade_type must be BUY or SELL.")

    try:
        service = _get_service()
        return service.add_trade(portfolio_id, data.model_dump())
    except Exception:
        logger.exception("Error adding trade to portfolio %d.", portfolio_id)
        raise HTTPException(status_code=500, detail="Failed to add trade.")


@router.put("/{portfolio_id}/trades/{trade_id}", response_model=TradeResponse)
def update_trade(portfolio_id: int, trade_id: int, data: TradeUpdate) -> dict:
    """Update an existing trade.

    Args:
        portfolio_id: Portfolio ID.
        trade_id: Trade ID to update.
        data: Partial trade data to update.

    Returns:
        Updated trade information.
    """
    try:
        service = _get_service()
        result = service.update_trade(
            portfolio_id, trade_id, data.model_dump(exclude_none=True)
        )
        if result is None:
            raise HTTPException(status_code=404, detail="Trade not found.")
        return result
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error updating trade %d.", trade_id)
        raise HTTPException(status_code=500, detail="Failed to update trade.")


@router.delete("/{portfolio_id}/trades/{trade_id}")
def delete_trade(portfolio_id: int, trade_id: int) -> dict:
    """Delete a trade.

    Args:
        portfolio_id: Portfolio ID.
        trade_id: Trade ID to delete.

    Returns:
        Deletion status.
    """
    try:
        service = _get_service()
        deleted = service.delete_trade(portfolio_id, trade_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Trade not found.")
        return {"status": "ok", "message": f"Trade {trade_id} deleted."}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error deleting trade %d.", trade_id)
        raise HTTPException(status_code=500, detail="Failed to delete trade.")


@router.post("/{portfolio_id}/trades/import")
async def import_trades_csv(portfolio_id: int, file: UploadFile = File(...)) -> dict:
    """Import trades from a CSV file.

    Expected columns: ticker, trade_type, quantity, price, trade_date,
    commission (optional), note (optional).

    Args:
        portfolio_id: Target portfolio ID.
        file: Uploaded CSV file.

    Returns:
        Import results with count and any errors.
    """
    try:
        content = await file.read()
        csv_content = content.decode("utf-8")
        service = _get_service()
        return service.import_trades_csv(portfolio_id, csv_content)
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded CSV.")
    except Exception:
        logger.exception("Error importing CSV trades.")
        raise HTTPException(status_code=500, detail="Failed to import trades.")


@router.get("/{portfolio_id}/allocation", response_model=AllocationResponse)
def get_allocation(portfolio_id: int) -> dict:
    """Get portfolio allocation breakdown by stock and sector.

    Args:
        portfolio_id: Portfolio ID.

    Returns:
        Allocation data with percentages.
    """
    try:
        service = _get_service()
        return service.get_allocation(portfolio_id)
    except Exception:
        logger.exception("Error fetching allocation for portfolio %d.", portfolio_id)
        raise HTTPException(status_code=500, detail="Failed to fetch allocation.")


@router.get("/{portfolio_id}/performance", response_model=PerformanceResponse)
def get_performance(
    portfolio_id: int,
    period: str = Query(default="1m", description="Period: 1m, 3m, 6m, 1y, ytd"),
) -> dict:
    """Get portfolio performance over time with benchmark comparison.

    Args:
        portfolio_id: Portfolio ID.
        period: Time period for performance analysis.

    Returns:
        Performance data points with returns.
    """
    try:
        service = _get_service()
        return service.get_performance(portfolio_id, period=period)
    except Exception:
        logger.exception("Error fetching performance for portfolio %d.", portfolio_id)
        raise HTTPException(status_code=500, detail="Failed to fetch performance.")


@router.get("/{portfolio_id}/dividends", response_model=DividendSummary)
def get_dividends(
    portfolio_id: int,
    year: int | None = Query(default=None),
) -> dict:
    """Get dividend events and summary for portfolio holdings.

    Args:
        portfolio_id: Portfolio ID.
        year: Filter year. Defaults to current year.

    Returns:
        Dividend events with monthly breakdown.
    """
    try:
        service = _get_service()
        return service.get_dividends(portfolio_id, year=year)
    except Exception:
        logger.exception("Error fetching dividends for portfolio %d.", portfolio_id)
        raise HTTPException(status_code=500, detail="Failed to fetch dividends.")


@router.get("/{portfolio_id}/tax", response_model=TaxSummary)
def get_tax_summary(
    portfolio_id: int,
    year: int | None = Query(default=None),
) -> dict:
    """Calculate tax summary for realized trades.

    Args:
        portfolio_id: Portfolio ID.
        year: Tax year. Defaults to current year.

    Returns:
        Tax summary with gains, losses, and trade breakdown.
    """
    try:
        service = _get_service()
        return service.get_tax_summary(portfolio_id, year=year)
    except Exception:
        logger.exception("Error fetching tax summary for portfolio %d.", portfolio_id)
        raise HTTPException(status_code=500, detail="Failed to fetch tax summary.")
