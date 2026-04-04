"""Portfolio management business logic service.

Handles portfolio CRUD, trade management, holdings calculation,
allocation analysis, performance tracking, dividends, and tax computation.
"""

import logging
from datetime import date, datetime, timedelta

import pandas as pd

from db import get_connection
from providers.data_provider import MarketDataProvider

logger = logging.getLogger(__name__)


class PortfolioService:
    """Service layer for portfolio operations."""

    def __init__(self) -> None:
        """Initialize PortfolioService with data provider."""
        self._provider = MarketDataProvider()

    # --- Portfolio CRUD ---

    def create_portfolio(self, name: str, description: str | None = None) -> dict:
        """Create a new portfolio.

        Args:
            name: Portfolio name.
            description: Optional portfolio description.

        Returns:
            Dict with created portfolio info.
        """
        conn = get_connection()
        new_id = conn.execute("SELECT nextval('seq_portfolio_id')").fetchone()[0]
        conn.execute(
            """
            INSERT INTO portfolios (id, name, description, created_at)
            VALUES (?, ?, ?, current_timestamp)
            """,
            [new_id, name, description],
        )
        logger.info("Created portfolio id=%d name=%s.", new_id, name)
        return {
            "id": new_id,
            "name": name,
            "description": description,
            "created_at": datetime.now().isoformat(),
        }

    def get_portfolios(self) -> list[dict]:
        """Get all portfolios with summary values.

        Returns:
            List of portfolio dicts with total value and cost.
        """
        conn = get_connection()
        rows = conn.execute(
            "SELECT id, name, description, created_at FROM portfolios ORDER BY created_at DESC"
        ).fetchall()

        portfolios = []
        for r in rows:
            portfolio = {
                "id": r[0],
                "name": r[1],
                "description": r[2],
                "created_at": r[3].isoformat() if r[3] else None,
                "total_value": None,
                "total_cost": None,
                "total_gain": None,
                "total_gain_pct": None,
            }
            # Quick summary from holdings
            try:
                holdings = self._calculate_holdings(r[0])
                total_cost = sum(h["total_cost"] for h in holdings)
                total_value = sum(h.get("market_value") or h["total_cost"] for h in holdings)
                portfolio["total_cost"] = round(total_cost, 2)
                portfolio["total_value"] = round(total_value, 2)
                gain = total_value - total_cost
                portfolio["total_gain"] = round(gain, 2)
                portfolio["total_gain_pct"] = (
                    round((gain / total_cost) * 100, 2) if total_cost != 0 else 0.0
                )
            except Exception:
                logger.debug("Could not compute summary for portfolio %d.", r[0])

            portfolios.append(portfolio)

        return portfolios

    def delete_portfolio(self, portfolio_id: int) -> bool:
        """Delete a portfolio and all associated data.

        Args:
            portfolio_id: Portfolio ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        conn = get_connection()
        existing = conn.execute(
            "SELECT id FROM portfolios WHERE id = ?", [portfolio_id]
        ).fetchone()
        if not existing:
            return False

        conn.execute("DELETE FROM trades WHERE portfolio_id = ?", [portfolio_id])
        conn.execute("DELETE FROM portfolio_snapshots WHERE portfolio_id = ?", [portfolio_id])
        conn.execute("DELETE FROM portfolios WHERE id = ?", [portfolio_id])
        logger.info("Deleted portfolio id=%d and associated data.", portfolio_id)
        return True

    # --- Trade CRUD ---

    def add_trade(self, portfolio_id: int, data: dict) -> dict:
        """Add a trade to a portfolio.

        Args:
            portfolio_id: Target portfolio ID.
            data: Trade data dict (ticker, trade_type, quantity, price, etc.).

        Returns:
            Dict with created trade info.
        """
        conn = get_connection()
        new_id = conn.execute("SELECT nextval('seq_trade_id')").fetchone()[0]
        conn.execute(
            """
            INSERT INTO trades (id, portfolio_id, ticker, trade_type, quantity, price,
                                commission, trade_date, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, current_timestamp)
            """,
            [
                new_id,
                portfolio_id,
                data["ticker"].upper(),
                data["trade_type"].upper(),
                data["quantity"],
                data["price"],
                data.get("commission", 0.0),
                data["trade_date"],
                data.get("note"),
            ],
        )
        logger.info("Added trade id=%d to portfolio %d.", new_id, portfolio_id)
        return {
            "id": new_id,
            "portfolio_id": portfolio_id,
            "ticker": data["ticker"].upper(),
            "trade_type": data["trade_type"].upper(),
            "quantity": data["quantity"],
            "price": data["price"],
            "commission": data.get("commission", 0.0),
            "trade_date": str(data["trade_date"]),
            "note": data.get("note"),
            "created_at": datetime.now().isoformat(),
        }

    def update_trade(self, portfolio_id: int, trade_id: int, data: dict) -> dict | None:
        """Update an existing trade.

        Args:
            portfolio_id: Portfolio ID containing the trade.
            trade_id: Trade ID to update.
            data: Partial trade data to update.

        Returns:
            Updated trade dict or None if not found.
        """
        conn = get_connection()
        existing = conn.execute(
            "SELECT * FROM trades WHERE id = ? AND portfolio_id = ?",
            [trade_id, portfolio_id],
        ).fetchone()
        if not existing:
            return None

        set_clauses: list[str] = []
        params: list = []
        field_map = {
            "ticker": 2,
            "trade_type": 3,
            "quantity": 4,
            "price": 5,
            "commission": 6,
            "trade_date": 7,
            "note": 8,
        }

        for field, idx in field_map.items():
            if field in data and data[field] is not None:
                value = data[field]
                if field == "ticker":
                    value = value.upper()
                elif field == "trade_type":
                    value = value.upper()
                set_clauses.append(f"{field} = ?")
                params.append(value)

        if not set_clauses:
            return None

        params.extend([trade_id, portfolio_id])
        conn.execute(
            f"UPDATE trades SET {', '.join(set_clauses)} WHERE id = ? AND portfolio_id = ?",
            params,
        )

        # Fetch updated
        updated = conn.execute(
            "SELECT * FROM trades WHERE id = ?", [trade_id]
        ).fetchone()
        return {
            "id": updated[0],
            "portfolio_id": updated[1],
            "ticker": updated[2],
            "trade_type": updated[3],
            "quantity": updated[4],
            "price": updated[5],
            "commission": updated[6],
            "trade_date": str(updated[7]),
            "note": updated[8],
            "created_at": updated[9].isoformat() if updated[9] else None,
        }

    def delete_trade(self, portfolio_id: int, trade_id: int) -> bool:
        """Delete a trade.

        Args:
            portfolio_id: Portfolio ID containing the trade.
            trade_id: Trade ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        conn = get_connection()
        existing = conn.execute(
            "SELECT id FROM trades WHERE id = ? AND portfolio_id = ?",
            [trade_id, portfolio_id],
        ).fetchone()
        if not existing:
            return False

        conn.execute("DELETE FROM trades WHERE id = ?", [trade_id])
        logger.info("Deleted trade id=%d from portfolio %d.", trade_id, portfolio_id)
        return True

    def get_trades(self, portfolio_id: int, page: int = 1, page_size: int = 50) -> dict:
        """Get paginated trades for a portfolio.

        Args:
            portfolio_id: Portfolio ID.
            page: Page number (1-based).
            page_size: Items per page.

        Returns:
            Dict with 'trades' list, 'total' count, and pagination info.
        """
        conn = get_connection()
        offset = (page - 1) * page_size

        total = conn.execute(
            "SELECT COUNT(*) FROM trades WHERE portfolio_id = ?", [portfolio_id]
        ).fetchone()[0]

        rows = conn.execute(
            """
            SELECT id, portfolio_id, ticker, trade_type, quantity, price,
                   commission, trade_date, note, created_at
            FROM trades
            WHERE portfolio_id = ?
            ORDER BY trade_date DESC, created_at DESC
            LIMIT ? OFFSET ?
            """,
            [portfolio_id, page_size, offset],
        ).fetchall()

        trades = [
            {
                "id": r[0],
                "portfolio_id": r[1],
                "ticker": r[2],
                "trade_type": r[3],
                "quantity": r[4],
                "price": r[5],
                "commission": r[6],
                "trade_date": str(r[7]),
                "note": r[8],
                "created_at": r[9].isoformat() if r[9] else None,
            }
            for r in rows
        ]

        return {"trades": trades, "total": total, "page": page, "page_size": page_size}

    # --- Holdings & P&L ---

    def _calculate_holdings(self, portfolio_id: int) -> list[dict]:
        """Calculate current holdings from trade history using FIFO.

        Args:
            portfolio_id: Portfolio ID.

        Returns:
            List of holding dicts with quantity, avg_cost, total_cost.
        """
        conn = get_connection()
        trades = conn.execute(
            """
            SELECT ticker, trade_type, quantity, price, commission
            FROM trades
            WHERE portfolio_id = ?
            ORDER BY trade_date ASC, created_at ASC
            """,
            [portfolio_id],
        ).fetchall()

        positions: dict[str, dict] = {}

        for trade in trades:
            ticker, trade_type, qty, price, commission = trade
            if ticker not in positions:
                positions[ticker] = {"quantity": 0.0, "total_cost": 0.0}

            pos = positions[ticker]
            if trade_type == "BUY":
                pos["total_cost"] += (qty * price) + commission
                pos["quantity"] += qty
            elif trade_type == "SELL":
                if pos["quantity"] > 0:
                    avg_cost = pos["total_cost"] / pos["quantity"]
                    sold_cost = avg_cost * qty
                    pos["total_cost"] -= sold_cost
                    pos["quantity"] -= qty

        holdings = []
        for ticker, pos in positions.items():
            if pos["quantity"] > 0.001:  # Filter out dust
                avg_cost = pos["total_cost"] / pos["quantity"] if pos["quantity"] > 0 else 0
                holdings.append({
                    "ticker": ticker,
                    "quantity": round(pos["quantity"], 6),
                    "avg_cost": round(avg_cost, 4),
                    "total_cost": round(pos["total_cost"], 2),
                })

        return holdings

    def get_holdings(self, portfolio_id: int) -> dict:
        """Get current holdings with live prices and P&L.

        Args:
            portfolio_id: Portfolio ID.

        Returns:
            Portfolio summary dict with holdings, totals, and P&L.
        """
        conn = get_connection()

        portfolio = conn.execute(
            "SELECT id, name, description FROM portfolios WHERE id = ?",
            [portfolio_id],
        ).fetchone()
        if not portfolio:
            return None

        holdings_raw = self._calculate_holdings(portfolio_id)

        if not holdings_raw:
            return {
                "id": portfolio[0],
                "name": portfolio[1],
                "description": portfolio[2],
                "holdings": [],
                "total_value": 0.0,
                "total_cost": 0.0,
                "total_unrealized_gain": 0.0,
                "total_unrealized_gain_pct": 0.0,
                "realized_gain": self._calculate_realized_gain(portfolio_id),
                "cash": 0.0,
            }

        # Fetch current prices
        tickers = [h["ticker"] for h in holdings_raw]
        batch_prices = self._provider.get_batch_prices(tickers, period="5d")

        # Get stock names from DB
        ticker_names = {}
        ticker_sectors = {}
        for ticker in tickers:
            row = conn.execute(
                "SELECT name, sector FROM stocks WHERE ticker = ?", [ticker]
            ).fetchone()
            if row:
                ticker_names[ticker] = row[0]
                ticker_sectors[ticker] = row[1]

        holdings = []
        total_value = 0.0
        total_cost = 0.0

        for h in holdings_raw:
            ticker = h["ticker"]
            current_price = None
            if ticker in batch_prices and not batch_prices[ticker].empty:
                current_price = float(batch_prices[ticker]["close"].iloc[-1])

            market_value = current_price * h["quantity"] if current_price else None
            unrealized_gain = (market_value - h["total_cost"]) if market_value else None
            unrealized_gain_pct = (
                (unrealized_gain / h["total_cost"]) * 100
                if unrealized_gain is not None and h["total_cost"] != 0
                else None
            )

            holding = {
                "ticker": ticker,
                "name": ticker_names.get(ticker),
                "sector": ticker_sectors.get(ticker),
                "quantity": h["quantity"],
                "avg_cost": h["avg_cost"],
                "current_price": round(current_price, 2) if current_price else None,
                "market_value": round(market_value, 2) if market_value else None,
                "total_cost": h["total_cost"],
                "unrealized_gain": round(unrealized_gain, 2) if unrealized_gain else None,
                "unrealized_gain_pct": (
                    round(unrealized_gain_pct, 2) if unrealized_gain_pct else None
                ),
            }
            holdings.append(holding)

            total_cost += h["total_cost"]
            if market_value is not None:
                total_value += market_value
            else:
                total_value += h["total_cost"]

        total_unrealized = total_value - total_cost
        total_unrealized_pct = (
            (total_unrealized / total_cost) * 100 if total_cost != 0 else 0.0
        )

        return {
            "id": portfolio[0],
            "name": portfolio[1],
            "description": portfolio[2],
            "holdings": holdings,
            "total_value": round(total_value, 2),
            "total_cost": round(total_cost, 2),
            "total_unrealized_gain": round(total_unrealized, 2),
            "total_unrealized_gain_pct": round(total_unrealized_pct, 2),
            "realized_gain": self._calculate_realized_gain(portfolio_id),
            "cash": 0.0,
        }

    def _calculate_realized_gain(self, portfolio_id: int) -> float:
        """Calculate total realized gain/loss from completed sell trades.

        Args:
            portfolio_id: Portfolio ID.

        Returns:
            Total realized gain/loss amount.
        """
        conn = get_connection()
        trades = conn.execute(
            """
            SELECT ticker, trade_type, quantity, price, commission
            FROM trades
            WHERE portfolio_id = ?
            ORDER BY trade_date ASC, created_at ASC
            """,
            [portfolio_id],
        ).fetchall()

        cost_basis: dict[str, list[tuple[float, float]]] = {}  # ticker -> [(qty, price)]
        realized = 0.0

        for trade in trades:
            ticker, trade_type, qty, price, commission = trade
            if ticker not in cost_basis:
                cost_basis[ticker] = []

            if trade_type == "BUY":
                cost_basis[ticker].append((qty, price))
            elif trade_type == "SELL":
                remaining = qty
                proceeds = (qty * price) - commission
                cost = 0.0

                # FIFO: match against earliest buys
                while remaining > 0 and cost_basis.get(ticker):
                    buy_qty, buy_price = cost_basis[ticker][0]
                    matched = min(remaining, buy_qty)
                    cost += matched * buy_price
                    remaining -= matched

                    if matched >= buy_qty:
                        cost_basis[ticker].pop(0)
                    else:
                        cost_basis[ticker][0] = (buy_qty - matched, buy_price)

                realized += proceeds - cost

        return round(realized, 2)

    # --- Allocation ---

    def get_allocation(self, portfolio_id: int) -> dict:
        """Get portfolio allocation breakdown by stock and sector.

        Args:
            portfolio_id: Portfolio ID.

        Returns:
            Dict with by_stock and by_sector allocation lists.
        """
        holdings_data = self.get_holdings(portfolio_id)
        if not holdings_data or not holdings_data.get("holdings"):
            return {"by_stock": [], "by_sector": [], "total_value": 0.0}

        total_value = holdings_data["total_value"]
        if total_value == 0:
            return {"by_stock": [], "by_sector": [], "total_value": 0.0}

        # Colors for chart
        colors = [
            "#3B82F6", "#EF4444", "#10B981", "#F59E0B", "#8B5CF6",
            "#EC4899", "#06B6D4", "#F97316", "#14B8A6", "#6366F1",
            "#84CC16", "#E11D48", "#0EA5E9", "#D946EF", "#22C55E",
        ]

        by_stock = []
        sector_totals: dict[str, float] = {}

        for i, h in enumerate(holdings_data["holdings"]):
            value = h.get("market_value") or h["total_cost"]
            pct = (value / total_value) * 100 if total_value > 0 else 0

            by_stock.append({
                "label": h["ticker"],
                "value": round(value, 2),
                "percentage": round(pct, 2),
                "color": colors[i % len(colors)],
            })

            sector = h.get("sector") or "Unknown"
            sector_totals[sector] = sector_totals.get(sector, 0) + value

        by_sector = []
        for i, (sector, value) in enumerate(
            sorted(sector_totals.items(), key=lambda x: x[1], reverse=True)
        ):
            pct = (value / total_value) * 100 if total_value > 0 else 0
            by_sector.append({
                "label": sector,
                "value": round(value, 2),
                "percentage": round(pct, 2),
                "color": colors[i % len(colors)],
            })

        return {
            "by_stock": by_stock,
            "by_sector": by_sector,
            "total_value": round(total_value, 2),
        }

    # --- Performance ---

    def get_performance(self, portfolio_id: int, period: str = "1m") -> dict:
        """Get portfolio performance over time with benchmark comparison.

        Args:
            portfolio_id: Portfolio ID.
            period: Time period (1m, 3m, 6m, 1y, ytd).

        Returns:
            Performance response dict with data points and return metrics.
        """
        conn = get_connection()

        # Determine date range
        period_days = {"1m": 30, "3m": 90, "6m": 180, "1y": 365, "ytd": None}
        if period == "ytd":
            start_date = date(date.today().year, 1, 1)
        else:
            days = period_days.get(period, 30)
            start_date = date.today() - timedelta(days=days)

        # Get trades up to each date
        trades = conn.execute(
            """
            SELECT ticker, trade_type, quantity, price, commission, trade_date
            FROM trades
            WHERE portfolio_id = ?
            ORDER BY trade_date ASC
            """,
            [portfolio_id],
        ).fetchall()

        if not trades:
            return {"points": [], "total_return_pct": 0.0, "benchmark_return_pct": None}

        # Get unique tickers
        tickers = list({t[0] for t in trades})

        # Fetch historical prices for holdings
        batch_prices = self._provider.get_batch_prices(tickers, period=period)

        # Fetch benchmark (S&P 500)
        benchmark_df = self._provider.get_daily_prices("^GSPC", period=period)

        # Build daily portfolio values
        points: list[dict] = []
        current_date = start_date
        end_date = date.today()

        # Pre-calculate positions at start_date
        while current_date <= end_date:
            current_date += timedelta(days=1)

        # Simplified: use snapshots or calculate from trades
        # For now, return snapshots if available, else estimate
        snapshots = conn.execute(
            """
            SELECT date, total_value, total_cost
            FROM portfolio_snapshots
            WHERE portfolio_id = ? AND date >= ?
            ORDER BY date ASC
            """,
            [portfolio_id, start_date],
        ).fetchall()

        if snapshots:
            for s in snapshots:
                cost = s[2] or 0
                value = s[1] or 0
                gain_pct = ((value - cost) / cost * 100) if cost > 0 else 0
                points.append({
                    "date": str(s[0]),
                    "portfolio_value": round(value, 2),
                    "total_cost": round(cost, 2),
                    "gain_pct": round(gain_pct, 2),
                    "benchmark_pct": None,
                })

        # Add benchmark returns
        if not benchmark_df.empty and points:
            bench_first = benchmark_df["close"].iloc[0]
            bench_map = {}
            for _, row in benchmark_df.iterrows():
                if bench_first and bench_first != 0:
                    bench_map[row["date"]] = round(
                        ((row["close"] - bench_first) / bench_first) * 100, 2
                    )
            for p in points:
                p["benchmark_pct"] = bench_map.get(p["date"])

        total_return_pct = points[-1]["gain_pct"] if points else 0.0
        benchmark_return_pct = None
        if not benchmark_df.empty and len(benchmark_df) >= 2:
            b_first = benchmark_df["close"].iloc[0]
            b_last = benchmark_df["close"].iloc[-1]
            if b_first and b_first != 0:
                benchmark_return_pct = round(((b_last - b_first) / b_first) * 100, 2)

        return {
            "points": points,
            "total_return_pct": total_return_pct,
            "benchmark_return_pct": benchmark_return_pct,
        }

    # --- Dividends ---

    def get_dividends(self, portfolio_id: int, year: int | None = None) -> dict:
        """Get dividend events for portfolio holdings.

        Args:
            portfolio_id: Portfolio ID.
            year: Filter year. Defaults to current year.

        Returns:
            Dividend summary dict with events and totals.
        """
        if year is None:
            year = date.today().year

        holdings = self._calculate_holdings(portfolio_id)
        if not holdings:
            return {"events": [], "total_annual": 0.0, "monthly_breakdown": {}}

        events: list[dict] = []
        monthly: dict[str, float] = {}
        conn = get_connection()

        for h in holdings:
            ticker = h["ticker"]
            qty = h["quantity"]

            # Check DB cache for dividends
            cached = conn.execute(
                """
                SELECT ex_date, payment_date, amount
                FROM dividends
                WHERE ticker = ? AND EXTRACT(YEAR FROM ex_date) = ?
                ORDER BY ex_date ASC
                """,
                [ticker, year],
            ).fetchall()

            if not cached:
                # Fetch from provider and cache
                div_df = self._provider.get_dividends(ticker)
                if not div_df.empty:
                    for _, row in div_df.iterrows():
                        try:
                            conn.execute(
                                """
                                INSERT OR REPLACE INTO dividends (ticker, ex_date, amount)
                                VALUES (?, ?, ?)
                                """,
                                [ticker, row["ex_date"], row["amount"]],
                            )
                        except Exception:
                            pass

                cached = conn.execute(
                    """
                    SELECT ex_date, payment_date, amount
                    FROM dividends
                    WHERE ticker = ? AND EXTRACT(YEAR FROM ex_date) = ?
                    ORDER BY ex_date ASC
                    """,
                    [ticker, year],
                ).fetchall()

            # Get stock name
            name_row = conn.execute(
                "SELECT name FROM stocks WHERE ticker = ?", [ticker]
            ).fetchone()
            stock_name = name_row[0] if name_row else None

            for div in cached:
                ex_dt = div[0]
                amount = div[2] or 0.0
                total = amount * qty

                events.append({
                    "ticker": ticker,
                    "name": stock_name,
                    "ex_date": str(ex_dt),
                    "payment_date": str(div[1]) if div[1] else None,
                    "amount": amount,
                    "quantity": qty,
                    "total_amount": round(total, 2),
                })

                month_key = ex_dt.strftime("%Y-%m") if hasattr(ex_dt, "strftime") else str(ex_dt)[:7]
                monthly[month_key] = monthly.get(month_key, 0) + total

        total_annual = sum(e["total_amount"] for e in events)

        return {
            "events": events,
            "total_annual": round(total_annual, 2),
            "monthly_breakdown": {k: round(v, 2) for k, v in monthly.items()},
        }

    # --- Tax ---

    def get_tax_summary(self, portfolio_id: int, year: int | None = None) -> dict:
        """Calculate tax summary for realized trades.

        Args:
            portfolio_id: Portfolio ID.
            year: Tax year. Defaults to current year.

        Returns:
            Tax summary dict with gains, losses, and trade details.
        """
        if year is None:
            year = date.today().year

        conn = get_connection()
        trades = conn.execute(
            """
            SELECT id, portfolio_id, ticker, trade_type, quantity, price,
                   commission, trade_date, note, created_at
            FROM trades
            WHERE portfolio_id = ?
            ORDER BY trade_date ASC, created_at ASC
            """,
            [portfolio_id],
        ).fetchall()

        cost_basis: dict[str, list[tuple[float, float, date]]] = {}
        short_term_gain = 0.0
        long_term_gain = 0.0
        short_term_loss = 0.0
        long_term_loss = 0.0
        realized_trades: list[dict] = []

        for trade in trades:
            tid, pid, ticker, ttype, qty, price, comm, trade_date, note, created_at = trade
            if ticker not in cost_basis:
                cost_basis[ticker] = []

            if ttype == "BUY":
                cost_basis[ticker].append((qty, price, trade_date))
            elif ttype == "SELL":
                # Only count sells in the target year
                sell_date = trade_date
                if hasattr(sell_date, "year"):
                    sell_year = sell_date.year
                else:
                    sell_year = int(str(sell_date)[:4])

                if sell_year != year:
                    # Still process to update cost basis
                    remaining = qty
                    while remaining > 0 and cost_basis.get(ticker):
                        buy_qty, buy_price, buy_date = cost_basis[ticker][0]
                        matched = min(remaining, buy_qty)
                        remaining -= matched
                        if matched >= buy_qty:
                            cost_basis[ticker].pop(0)
                        else:
                            cost_basis[ticker][0] = (buy_qty - matched, buy_price, buy_date)
                    continue

                remaining = qty
                proceeds = (qty * price) - comm
                cost_total = 0.0
                is_long_term = True

                while remaining > 0 and cost_basis.get(ticker):
                    buy_qty, buy_price, buy_date = cost_basis[ticker][0]
                    matched = min(remaining, buy_qty)
                    cost_total += matched * buy_price
                    remaining -= matched

                    # Check holding period
                    if hasattr(buy_date, "year") and hasattr(sell_date, "year"):
                        holding_days = (sell_date - buy_date).days
                        if holding_days < 365:
                            is_long_term = False

                    if matched >= buy_qty:
                        cost_basis[ticker].pop(0)
                    else:
                        cost_basis[ticker][0] = (buy_qty - matched, buy_price, buy_date)

                gain = proceeds - cost_total
                if gain >= 0:
                    if is_long_term:
                        long_term_gain += gain
                    else:
                        short_term_gain += gain
                else:
                    if is_long_term:
                        long_term_loss += abs(gain)
                    else:
                        short_term_loss += abs(gain)

                realized_trades.append({
                    "id": tid,
                    "portfolio_id": pid,
                    "ticker": ticker,
                    "trade_type": ttype,
                    "quantity": qty,
                    "price": price,
                    "commission": comm,
                    "trade_date": str(trade_date),
                    "note": note,
                    "created_at": created_at.isoformat() if created_at else None,
                })

        realized_gains = short_term_gain + long_term_gain
        realized_losses = short_term_loss + long_term_loss
        net_gain = realized_gains - realized_losses

        return {
            "year": year,
            "realized_gains": round(realized_gains, 2),
            "realized_losses": round(realized_losses, 2),
            "net_gain": round(net_gain, 2),
            "short_term_gain": round(short_term_gain, 2),
            "long_term_gain": round(long_term_gain, 2),
            "short_term_loss": round(short_term_loss, 2),
            "long_term_loss": round(long_term_loss, 2),
            "trades": realized_trades,
        }

    # --- CSV Import ---

    def import_trades_csv(self, portfolio_id: int, csv_content: str) -> dict:
        """Import trades from CSV content.

        Expected columns: ticker, trade_type, quantity, price, trade_date,
        commission (optional), note (optional).

        Args:
            portfolio_id: Target portfolio ID.
            csv_content: Raw CSV string.

        Returns:
            Dict with import results (imported count, errors).
        """
        import io

        try:
            df = pd.read_csv(io.StringIO(csv_content), encoding="utf-8")
        except Exception:
            logger.exception("Failed to parse CSV.")
            return {"imported": 0, "errors": ["Failed to parse CSV file"]}

        required = {"ticker", "trade_type", "quantity", "price", "trade_date"}
        if not required.issubset(set(df.columns)):
            missing = required - set(df.columns)
            return {"imported": 0, "errors": [f"Missing columns: {missing}"]}

        imported = 0
        errors: list[str] = []

        for idx, row in df.iterrows():
            try:
                self.add_trade(portfolio_id, {
                    "ticker": str(row["ticker"]),
                    "trade_type": str(row["trade_type"]),
                    "quantity": float(row["quantity"]),
                    "price": float(row["price"]),
                    "trade_date": str(row["trade_date"]),
                    "commission": float(row.get("commission", 0)),
                    "note": str(row.get("note", "")) if pd.notna(row.get("note")) else None,
                })
                imported += 1
            except Exception as e:
                errors.append(f"Row {idx + 1}: {e}")

        return {"imported": imported, "errors": errors}
