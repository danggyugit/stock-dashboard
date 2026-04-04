"""Pydantic models for portfolio endpoints."""

from datetime import date, datetime

from pydantic import BaseModel, Field


class PortfolioCreate(BaseModel):
    """Request body for creating a new portfolio."""

    name: str
    description: str | None = None


class PortfolioResponse(BaseModel):
    """Portfolio information response."""

    id: int
    name: str
    description: str | None = None
    created_at: datetime | None = None
    total_value: float | None = None
    total_cost: float | None = None
    total_gain: float | None = None
    total_gain_pct: float | None = None


class TradeCreate(BaseModel):
    """Request body for creating a new trade."""

    ticker: str
    trade_type: str = Field(description="BUY or SELL")
    quantity: float
    price: float
    commission: float = 0.0
    trade_date: date
    note: str | None = None


class TradeUpdate(BaseModel):
    """Request body for updating an existing trade."""

    ticker: str | None = None
    trade_type: str | None = None
    quantity: float | None = None
    price: float | None = None
    commission: float | None = None
    trade_date: date | None = None
    note: str | None = None


class TradeResponse(BaseModel):
    """Trade information response."""

    id: int
    portfolio_id: int
    ticker: str
    trade_type: str
    quantity: float
    price: float
    commission: float = 0.0
    trade_date: date
    note: str | None = None
    created_at: datetime | None = None


class HoldingInfo(BaseModel):
    """Current holding position with P&L."""

    ticker: str
    name: str | None = None
    sector: str | None = None
    quantity: float
    avg_cost: float
    current_price: float | None = None
    market_value: float | None = None
    total_cost: float
    unrealized_gain: float | None = None
    unrealized_gain_pct: float | None = None


class PortfolioSummary(BaseModel):
    """Portfolio summary with holdings and P&L."""

    id: int
    name: str
    description: str | None = None
    holdings: list[HoldingInfo] = Field(default_factory=list)
    total_value: float = 0.0
    total_cost: float = 0.0
    total_unrealized_gain: float = 0.0
    total_unrealized_gain_pct: float = 0.0
    realized_gain: float = 0.0
    cash: float = 0.0


class AllocationItem(BaseModel):
    """Single allocation slice (by ticker or sector)."""

    label: str
    value: float
    percentage: float
    color: str | None = None


class AllocationResponse(BaseModel):
    """Portfolio allocation breakdown."""

    by_stock: list[AllocationItem] = Field(default_factory=list)
    by_sector: list[AllocationItem] = Field(default_factory=list)
    total_value: float = 0.0


class PerformancePoint(BaseModel):
    """Single point in performance timeline."""

    date: str
    portfolio_value: float
    total_cost: float
    gain_pct: float
    spy_pct: float | None = None
    qqq_pct: float | None = None


class PerformanceResponse(BaseModel):
    """Portfolio performance over time."""

    points: list[PerformancePoint] = Field(default_factory=list)
    total_return_pct: float = 0.0
    spy_return_pct: float | None = None
    qqq_return_pct: float | None = None


class DividendEvent(BaseModel):
    """Dividend event for calendar."""

    ticker: str
    name: str | None = None
    ex_date: date
    payment_date: date | None = None
    amount: float
    quantity: float | None = None
    total_amount: float | None = None


class DividendSummary(BaseModel):
    """Dividend summary response."""

    events: list[DividendEvent] = Field(default_factory=list)
    total_annual: float = 0.0
    monthly_breakdown: dict[str, float] = Field(default_factory=dict)


class TaxSummary(BaseModel):
    """Tax calculation summary."""

    year: int
    realized_gains: float = 0.0
    realized_losses: float = 0.0
    net_gain: float = 0.0
    short_term_gain: float = 0.0
    long_term_gain: float = 0.0
    short_term_loss: float = 0.0
    long_term_loss: float = 0.0
    trades: list[TradeResponse] = Field(default_factory=list)
