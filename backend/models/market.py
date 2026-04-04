"""Pydantic models for market data endpoints."""

from pydantic import BaseModel, Field


class StockInfo(BaseModel):
    """Basic stock information."""

    ticker: str
    name: str
    sector: str | None = None
    industry: str | None = None
    market_cap: int | None = None
    exchange: str | None = None


class HeatmapStock(BaseModel):
    """Individual stock in the heatmap."""

    ticker: str
    name: str
    market_cap: int | None = None
    price: float | None = None
    change_pct: float | None = None
    volume: int | None = None


class HeatmapSector(BaseModel):
    """Sector grouping for heatmap."""

    name: str
    stocks: list[HeatmapStock] = Field(default_factory=list)
    total_market_cap: int | None = None
    avg_change_pct: float | None = None


class HeatmapResponse(BaseModel):
    """Response for heatmap endpoint."""

    sectors: list[HeatmapSector] = Field(default_factory=list)
    period: str = "1d"
    updated_at: str | None = None


class ScreenerParams(BaseModel):
    """Query parameters for stock screener."""

    sector: str | None = None
    industry: str | None = None
    min_cap: int | None = None
    max_cap: int | None = None
    min_pe: float | None = None
    max_pe: float | None = None
    min_dividend_yield: float | None = None
    max_dividend_yield: float | None = None
    min_volume: int | None = None
    sort_by: str = "market_cap"
    sort_order: str = "desc"
    page: int = 1
    page_size: int = 50


class ScreenerResult(BaseModel):
    """Single stock result from screener."""

    ticker: str
    name: str
    sector: str | None = None
    industry: str | None = None
    price: float | None = None
    change_pct: float | None = None
    market_cap: int | None = None
    pe_ratio: float | None = None
    pb_ratio: float | None = None
    dividend_yield: float | None = None
    volume: int | None = None
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None


class StockDetail(BaseModel):
    """Detailed stock information for stock detail page."""

    ticker: str
    name: str
    sector: str | None = None
    industry: str | None = None
    market_cap: int | None = None
    exchange: str | None = None
    description: str | None = None
    employees: int | None = None
    website: str | None = None
    price: float | None = None
    change_pct: float | None = None
    prev_close: float | None = None
    open: float | None = None
    day_high: float | None = None
    day_low: float | None = None
    volume: int | None = None
    avg_volume: int | None = None
    pe_ratio: float | None = None
    pb_ratio: float | None = None
    ps_ratio: float | None = None
    eps: float | None = None
    roe: float | None = None
    debt_to_equity: float | None = None
    dividend_yield: float | None = None
    beta: float | None = None
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None


class ChartDataPoint(BaseModel):
    """Single data point for stock charts."""

    date: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: int | None = None


class CompareStock(BaseModel):
    """Stock data for comparison view."""

    ticker: str
    name: str
    chart_data: list[ChartDataPoint] = Field(default_factory=list)
    price: float | None = None
    change_pct: float | None = None
    market_cap: int | None = None
    pe_ratio: float | None = None
    pb_ratio: float | None = None
    dividend_yield: float | None = None
    beta: float | None = None
    roe: float | None = None
    eps: float | None = None


class CompareResponse(BaseModel):
    """Response for compare endpoint."""

    stocks: list[CompareStock] = Field(default_factory=list)
    period: str = "1m"


class SearchResult(BaseModel):
    """Search result for stock autocomplete."""

    ticker: str
    name: str
    sector: str | None = None
    exchange: str | None = None


class IndexInfo(BaseModel):
    """Major market index information."""

    ticker: str
    name: str
    price: float | None = None
    change: float | None = None
    change_pct: float | None = None
