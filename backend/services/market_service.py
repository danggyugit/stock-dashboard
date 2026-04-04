"""Market data business logic service.

Handles heatmap generation, stock screening, search, and data caching
via DuckDB. Uses MarketDataProvider for external data retrieval.
"""

import logging
from datetime import datetime, timedelta

import pandas as pd

from db import get_connection
from config import get_settings
from providers.data_provider import MarketDataProvider

logger = logging.getLogger(__name__)


class MarketService:
    """Service layer for market data operations."""

    def __init__(self) -> None:
        """Initialize MarketService with data provider."""
        self._provider = MarketDataProvider()

    def get_heatmap_data(self, period: str = "1d") -> dict:
        """Generate sector-grouped heatmap data.

        Fetches stock data from cache or provider, groups by sector,
        and calculates change percentages for the requested period.

        Args:
            period: Time period for change calculation (1d, 1w, 1m, 3m, ytd, 1y).

        Returns:
            Dict with 'sectors' list and metadata.
        """
        conn = get_connection()

        # Ensure we have stock data
        stock_count = conn.execute("SELECT COUNT(*) FROM stocks").fetchone()[0]
        if stock_count == 0:
            self.refresh_market_data()

        # Get stocks with latest prices
        stocks_df = conn.execute("""
            SELECT s.ticker, s.name, s.sector, s.market_cap
            FROM stocks s
            WHERE s.sector IS NOT NULL
            ORDER BY s.market_cap DESC NULLS LAST
        """).fetchdf()

        if stocks_df.empty:
            return {"sectors": [], "period": period, "updated_at": None}

        # Get price changes - fetch batch prices for top stocks by market cap
        top_tickers = stocks_df["ticker"].head(200).tolist()
        batch_prices = self._provider.get_batch_prices(top_tickers, period=period)

        # Build heatmap sectors
        sectors: dict[str, dict] = {}
        for _, row in stocks_df.iterrows():
            ticker = row["ticker"]
            sector_name = row["sector"] or "Other"

            if sector_name not in sectors:
                sectors[sector_name] = {
                    "name": sector_name,
                    "stocks": [],
                    "total_market_cap": 0,
                }

            change_pct = None
            price = None
            volume = None

            if ticker in batch_prices:
                price_df = batch_prices[ticker]
                if not price_df.empty and len(price_df) >= 2:
                    first_close = price_df["close"].iloc[0]
                    last_close = price_df["close"].iloc[-1]
                    if first_close and first_close != 0:
                        change_pct = round(((last_close - first_close) / first_close) * 100, 2)
                    price = last_close
                    volume = int(price_df["volume"].iloc[-1]) if pd.notna(price_df["volume"].iloc[-1]) else None
                elif not price_df.empty:
                    price = price_df["close"].iloc[-1]

            # Use 1B as default market cap for stocks without data (ensures treemap visibility)
            raw_cap = row["market_cap"]
            mkt_cap = int(raw_cap) if pd.notna(raw_cap) and raw_cap else 1_000_000_000

            sectors[sector_name]["stocks"].append({
                "ticker": ticker,
                "name": row["name"],
                "market_cap": mkt_cap,
                "price": round(price, 2) if price is not None else None,
                "change_pct": change_pct,
                "volume": volume,
            })
            if mkt_cap:
                sectors[sector_name]["total_market_cap"] += mkt_cap

        # Calculate avg change per sector
        sector_list = []
        for sector_data in sectors.values():
            changes = [
                s["change_pct"] for s in sector_data["stocks"] if s["change_pct"] is not None
            ]
            sector_data["avg_change_pct"] = (
                round(sum(changes) / len(changes), 2) if changes else None
            )
            sector_list.append(sector_data)

        sector_list.sort(key=lambda x: x.get("total_market_cap") or 0, reverse=True)

        return {
            "sectors": sector_list,
            "period": period,
            "updated_at": datetime.now().isoformat(),
        }

    def search_stocks(self, query: str) -> list[dict]:
        """Search stocks by ticker or name.

        Args:
            query: Search query string.

        Returns:
            List of matching stock dicts (max 20 results).
        """
        conn = get_connection()
        query_upper = query.upper()
        query_like = f"%{query_upper}%"

        results = conn.execute(
            """
            SELECT ticker, name, sector, exchange
            FROM stocks
            WHERE UPPER(ticker) LIKE ? OR UPPER(name) LIKE ?
            ORDER BY
                CASE WHEN UPPER(ticker) = ? THEN 0
                     WHEN UPPER(ticker) LIKE ? THEN 1
                     ELSE 2
                END,
                market_cap DESC NULLS LAST
            LIMIT 20
            """,
            [query_like, query_like, query_upper, f"{query_upper}%"],
        ).fetchall()

        return [
            {
                "ticker": r[0],
                "name": r[1],
                "sector": r[2],
                "exchange": r[3],
            }
            for r in results
        ]

    def get_screener_results(self, params: dict) -> dict:
        """Filter and sort stocks based on screener parameters.

        Args:
            params: Screener filter parameters (sector, min_cap, max_pe, etc.).

        Returns:
            Dict with 'results' list, 'total' count, and pagination info.
        """
        conn = get_connection()

        where_clauses: list[str] = []
        bind_params: list = []

        if params.get("sector"):
            where_clauses.append("s.sector = ?")
            bind_params.append(params["sector"])

        if params.get("industry"):
            where_clauses.append("s.industry = ?")
            bind_params.append(params["industry"])

        if params.get("min_cap"):
            where_clauses.append("s.market_cap >= ?")
            bind_params.append(params["min_cap"])

        if params.get("max_cap"):
            where_clauses.append("s.market_cap <= ?")
            bind_params.append(params["max_cap"])

        if params.get("min_pe"):
            where_clauses.append("f.pe_ratio >= ?")
            bind_params.append(params["min_pe"])

        if params.get("max_pe"):
            where_clauses.append("f.pe_ratio <= ?")
            bind_params.append(params["max_pe"])

        if params.get("min_dividend_yield"):
            where_clauses.append("f.dividend_yield >= ?")
            bind_params.append(params["min_dividend_yield"])

        if params.get("max_dividend_yield"):
            where_clauses.append("f.dividend_yield <= ?")
            bind_params.append(params["max_dividend_yield"])

        if params.get("min_volume"):
            where_clauses.append("f.avg_volume >= ?")
            bind_params.append(params["min_volume"])

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        # Allowed sort columns
        sort_map = {
            "market_cap": "s.market_cap",
            "pe_ratio": "f.pe_ratio",
            "dividend_yield": "f.dividend_yield",
            "name": "s.name",
            "ticker": "s.ticker",
            "volume": "f.avg_volume",
        }
        sort_col = sort_map.get(params.get("sort_by", "market_cap"), "s.market_cap")
        sort_order = "ASC" if params.get("sort_order", "desc").lower() == "asc" else "DESC"

        page = max(1, params.get("page", 1))
        page_size = min(100, max(1, params.get("page_size", 50)))
        offset = (page - 1) * page_size

        # Count total
        count_sql = f"""
            SELECT COUNT(*)
            FROM stocks s
            LEFT JOIN fundamentals f ON s.ticker = f.ticker
            WHERE {where_sql}
        """
        total = conn.execute(count_sql, bind_params).fetchone()[0]

        # Fetch page
        query_sql = f"""
            SELECT
                s.ticker, s.name, s.sector, s.industry, s.market_cap,
                f.pe_ratio, f.pb_ratio, f.dividend_yield, f.avg_volume,
                f.fifty_two_week_high, f.fifty_two_week_low
            FROM stocks s
            LEFT JOIN fundamentals f ON s.ticker = f.ticker
            WHERE {where_sql}
            ORDER BY {sort_col} {sort_order} NULLS LAST
            LIMIT ? OFFSET ?
        """
        rows = conn.execute(query_sql, bind_params + [page_size, offset]).fetchall()

        results = []
        for r in rows:
            results.append({
                "ticker": r[0],
                "name": r[1],
                "sector": r[2],
                "industry": r[3],
                "market_cap": r[4],
                "price": None,
                "change_pct": None,
                "pe_ratio": r[5],
                "pb_ratio": r[6],
                "dividend_yield": r[7],
                "volume": r[8],
                "fifty_two_week_high": r[9],
                "fifty_two_week_low": r[10],
            })

        return {
            "results": results,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get_stock_detail(self, ticker: str) -> dict | None:
        """Get detailed information for a single stock.

        Checks DB cache first, fetches from provider if stale or missing.

        Args:
            ticker: Stock ticker symbol.

        Returns:
            Stock detail dict or None if not found.
        """
        conn = get_connection()
        settings = get_settings()

        # Check cache freshness
        cached = conn.execute(
            "SELECT *, updated_at FROM stocks WHERE ticker = ?", [ticker]
        ).fetchone()

        use_cache = False
        if cached:
            updated_at = cached[-1]
            if updated_at and isinstance(updated_at, datetime):
                age = (datetime.now() - updated_at).total_seconds()
                if age < settings.MARKET_DATA_TTL:
                    use_cache = True

        # Fetch fresh data if needed
        info = self._provider.get_stock_info(ticker)
        if not info:
            if cached:
                # Use stale cache as fallback
                return self._build_stock_detail_from_cache(ticker, conn)
            return None

        # Update stocks table
        conn.execute(
            """
            INSERT OR REPLACE INTO stocks (ticker, name, sector, industry, market_cap, exchange, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, current_timestamp)
            """,
            [
                ticker,
                info.get("name", ticker),
                info.get("sector"),
                info.get("industry"),
                info.get("market_cap"),
                info.get("exchange"),
            ],
        )

        # Update fundamentals
        conn.execute(
            """
            INSERT OR REPLACE INTO fundamentals
            (ticker, pe_ratio, pb_ratio, ps_ratio, eps, roe, debt_to_equity,
             dividend_yield, beta, fifty_two_week_high, fifty_two_week_low,
             avg_volume, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, current_timestamp)
            """,
            [
                ticker,
                info.get("pe_ratio"),
                info.get("pb_ratio"),
                info.get("ps_ratio"),
                info.get("eps"),
                info.get("roe"),
                info.get("debt_to_equity"),
                info.get("dividend_yield"),
                info.get("beta"),
                info.get("fifty_two_week_high"),
                info.get("fifty_two_week_low"),
                info.get("avg_volume"),
            ],
        )

        # Calculate change_pct
        price = info.get("price")
        prev_close = info.get("prev_close")
        change_pct = None
        if price is not None and prev_close is not None and prev_close != 0:
            change_pct = round(((price - prev_close) / prev_close) * 100, 2)

        return {
            "ticker": ticker,
            "name": info.get("name", ticker),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": info.get("market_cap"),
            "exchange": info.get("exchange"),
            "description": info.get("description"),
            "employees": info.get("employees"),
            "website": info.get("website"),
            "price": info.get("price"),
            "change_pct": change_pct,
            "prev_close": prev_close,
            "open": info.get("open"),
            "day_high": info.get("day_high"),
            "day_low": info.get("day_low"),
            "volume": info.get("volume"),
            "avg_volume": info.get("avg_volume"),
            "pe_ratio": info.get("pe_ratio"),
            "pb_ratio": info.get("pb_ratio"),
            "ps_ratio": info.get("ps_ratio"),
            "eps": info.get("eps"),
            "roe": info.get("roe"),
            "debt_to_equity": info.get("debt_to_equity"),
            "dividend_yield": info.get("dividend_yield"),
            "beta": info.get("beta"),
            "fifty_two_week_high": info.get("fifty_two_week_high"),
            "fifty_two_week_low": info.get("fifty_two_week_low"),
        }

    def _build_stock_detail_from_cache(self, ticker: str, conn) -> dict | None:
        """Build stock detail response from cached DB data.

        Args:
            ticker: Stock ticker symbol.
            conn: DuckDB connection.

        Returns:
            Stock detail dict from cache or None.
        """
        row = conn.execute(
            """
            SELECT s.ticker, s.name, s.sector, s.industry, s.market_cap, s.exchange,
                   f.pe_ratio, f.pb_ratio, f.ps_ratio, f.eps, f.roe, f.debt_to_equity,
                   f.dividend_yield, f.beta, f.fifty_two_week_high, f.fifty_two_week_low,
                   f.avg_volume
            FROM stocks s
            LEFT JOIN fundamentals f ON s.ticker = f.ticker
            WHERE s.ticker = ?
            """,
            [ticker],
        ).fetchone()

        if not row:
            return None

        return {
            "ticker": row[0],
            "name": row[1],
            "sector": row[2],
            "industry": row[3],
            "market_cap": row[4],
            "exchange": row[5],
            "description": None,
            "employees": None,
            "website": None,
            "price": None,
            "change_pct": None,
            "prev_close": None,
            "open": None,
            "day_high": None,
            "day_low": None,
            "volume": None,
            "avg_volume": row[16],
            "pe_ratio": row[6],
            "pb_ratio": row[7],
            "ps_ratio": row[8],
            "eps": row[9],
            "roe": row[10],
            "debt_to_equity": row[11],
            "dividend_yield": row[12],
            "beta": row[13],
            "fifty_two_week_high": row[14],
            "fifty_two_week_low": row[15],
        }

    def get_chart_data(
        self, ticker: str, period: str = "1mo", interval: str | None = None
    ) -> list[dict]:
        """Get chart data points for a stock.

        Args:
            ticker: Stock ticker symbol.
            period: Time period (1d, 1w, 1m, 3m, 6m, 1y, 5y).
            interval: Data interval. Auto-selected if None.

        Returns:
            List of chart data point dicts.
        """
        df = self._provider.get_daily_prices(ticker, period=period, interval=interval)
        if df.empty:
            return []

        points = []
        for _, row in df.iterrows():
            points.append({
                "date": row["date"],
                "open": round(row["open"], 2) if pd.notna(row["open"]) else None,
                "high": round(row["high"], 2) if pd.notna(row["high"]) else None,
                "low": round(row["low"], 2) if pd.notna(row["low"]) else None,
                "close": round(row["close"], 2) if pd.notna(row["close"]) else None,
                "volume": int(row["volume"]) if pd.notna(row["volume"]) else None,
            })

        return points

    def get_compare_data(self, tickers: list[str], period: str = "1m") -> dict:
        """Get comparison data for multiple stocks.

        Args:
            tickers: List of ticker symbols to compare (2-5).
            period: Time period for comparison.

        Returns:
            Dict with 'stocks' list containing price history and metrics.
        """
        if not tickers:
            return {"stocks": [], "period": period}

        batch_prices = self._provider.get_batch_prices(tickers, period=period)

        stocks = []
        for ticker in tickers:
            info = self._provider.get_stock_info(ticker)
            price_df = batch_prices.get(ticker, pd.DataFrame())

            points = []
            if not price_df.empty:
                for _, row in price_df.iterrows():
                    points.append({
                        "date": row["date"],
                        "open": round(row["open"], 2) if pd.notna(row["open"]) else None,
                        "high": round(row["high"], 2) if pd.notna(row["high"]) else None,
                        "low": round(row["low"], 2) if pd.notna(row["low"]) else None,
                        "close": round(row["close"], 2) if pd.notna(row["close"]) else None,
                        "volume": int(row["volume"]) if pd.notna(row["volume"]) else None,
                    })

            # Calculate change_pct over the period
            change_pct = None
            if not price_df.empty and len(price_df) >= 2:
                first = price_df["close"].iloc[0]
                last = price_df["close"].iloc[-1]
                if first and first != 0:
                    change_pct = round(((last - first) / first) * 100, 2)

            stocks.append({
                "ticker": ticker,
                "name": info.get("name", ticker),
                "chart_data": points,
                "price": info.get("price"),
                "change_pct": change_pct,
                "market_cap": info.get("market_cap"),
                "pe_ratio": info.get("pe_ratio"),
                "pb_ratio": info.get("pb_ratio"),
                "dividend_yield": info.get("dividend_yield"),
                "beta": info.get("beta"),
                "roe": info.get("roe"),
                "eps": info.get("eps"),
            })

        return {"stocks": stocks, "period": period}

    def get_indices(self) -> list[dict]:
        """Get major market index information.

        Returns:
            List of index info dicts.
        """
        return self._provider.get_indices()

    def get_financials(self, ticker: str) -> dict | None:
        """Get financial metrics for a stock.

        Args:
            ticker: Stock ticker symbol.

        Returns:
            Dict with fundamental metrics or None.
        """
        conn = get_connection()
        settings = get_settings()

        # Check cache
        cached = conn.execute(
            "SELECT *, updated_at FROM fundamentals WHERE ticker = ?", [ticker]
        ).fetchone()

        if cached:
            updated_at = cached[-1]
            if updated_at and isinstance(updated_at, datetime):
                age = (datetime.now() - updated_at).total_seconds()
                if age < settings.FUNDAMENTALS_TTL:
                    return {
                        "ticker": cached[0],
                        "pe_ratio": cached[1],
                        "pb_ratio": cached[2],
                        "ps_ratio": cached[3],
                        "eps": cached[4],
                        "roe": cached[5],
                        "debt_to_equity": cached[6],
                        "dividend_yield": cached[7],
                        "beta": cached[8],
                        "fifty_two_week_high": cached[9],
                        "fifty_two_week_low": cached[10],
                        "avg_volume": cached[11],
                    }

        # Fetch fresh
        fundamentals = self._provider.get_fundamentals(ticker)
        if not fundamentals:
            return None

        conn.execute(
            """
            INSERT OR REPLACE INTO fundamentals
            (ticker, pe_ratio, pb_ratio, ps_ratio, eps, roe, debt_to_equity,
             dividend_yield, beta, fifty_two_week_high, fifty_two_week_low,
             avg_volume, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, current_timestamp)
            """,
            [
                ticker,
                fundamentals.get("pe_ratio"),
                fundamentals.get("pb_ratio"),
                fundamentals.get("ps_ratio"),
                fundamentals.get("eps"),
                fundamentals.get("roe"),
                fundamentals.get("debt_to_equity"),
                fundamentals.get("dividend_yield"),
                fundamentals.get("beta"),
                fundamentals.get("fifty_two_week_high"),
                fundamentals.get("fifty_two_week_low"),
                fundamentals.get("avg_volume"),
            ],
        )

        return fundamentals

    def refresh_market_data(self) -> dict:
        """Refresh stock master data from S&P 500 list.

        Fetches stock list from Wikipedia and updates the stocks table.

        Returns:
            Dict with refresh status and count.
        """
        conn = get_connection()

        # Fetch S&P 500 list
        stocks_df = self._provider.get_stock_list()
        if stocks_df.empty:
            logger.warning("Failed to refresh market data: empty stock list.")
            return {"status": "error", "message": "Failed to fetch stock list", "count": 0}

        tickers = stocks_df["ticker"].tolist()

        # Insert/update stocks table (market_cap is populated per-stock via get_stock_detail)
        inserted = 0
        for _, row in stocks_df.iterrows():
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO stocks (ticker, name, sector, industry, updated_at)
                    VALUES (?, ?, ?, ?, current_timestamp)
                    """,
                    [row["ticker"], row["name"], row["sector"], row["industry"]],
                )
                inserted += 1
            except Exception:
                logger.warning("Failed to insert stock %s.", row["ticker"])

        logger.info("Refreshed market data: %d stocks updated.", inserted)
        return {"status": "ok", "message": f"Updated {inserted} stocks", "count": inserted}
