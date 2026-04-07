"""Portfolio management service for Streamlit app.

Uses SQLite for persistent portfolio/trade storage.
"""

import logging
from datetime import date, datetime, timedelta

import pandas as pd

from core.data_provider import MarketDataProvider
from database import get_connection

logger = logging.getLogger(__name__)

_provider = MarketDataProvider()


# --- Portfolio CRUD ---

def create_portfolio(name: str, description: str | None = None,
                     user_id: int | None = None) -> dict:
    """Create a new portfolio."""
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO portfolios (user_id, name, description) VALUES (?, ?, ?)",
        (user_id, name, description),
    )
    conn.commit()
    return {"id": cur.lastrowid, "name": name, "description": description}


def get_portfolios(user_id: int | None = None) -> list[dict]:
    """Get portfolios for a user (or all if user_id is None)."""
    conn = get_connection()
    if user_id is not None:
        rows = conn.execute(
            """SELECT id, name, description, created_at FROM portfolios
               WHERE user_id = ? ORDER BY created_at DESC""",
            (user_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, name, description, created_at FROM portfolios ORDER BY created_at DESC"
        ).fetchall()

    portfolios = []
    for r in rows:
        p = {
            "id": r[0], "name": r[1], "description": r[2],
            "created_at": r[3],
            "total_value": None, "total_cost": None,
            "total_gain": None, "total_gain_pct": None,
        }
        try:
            holdings = _calculate_holdings(r[0])
            total_cost = sum(h["total_cost"] for h in holdings)
            total_value = sum(h.get("market_value") or h["total_cost"] for h in holdings)
            p["total_cost"] = round(total_cost, 2)
            p["total_value"] = round(total_value, 2)
            gain = total_value - total_cost
            p["total_gain"] = round(gain, 2)
            p["total_gain_pct"] = round((gain / total_cost) * 100, 2) if total_cost else 0.0
        except Exception:
            pass
        portfolios.append(p)
    return portfolios


def delete_portfolio(portfolio_id: int, user_id: int | None = None) -> bool:
    """Delete a portfolio and associated trades. Verifies ownership if user_id given."""
    conn = get_connection()
    if user_id is not None:
        # Verify ownership
        owner = conn.execute(
            "SELECT user_id FROM portfolios WHERE id = ?", (portfolio_id,)
        ).fetchone()
        if not owner or owner[0] != user_id:
            return False
    conn.execute("DELETE FROM trades WHERE portfolio_id = ?", (portfolio_id,))
    conn.execute("DELETE FROM portfolios WHERE id = ?", (portfolio_id,))
    conn.commit()
    return True


# --- Trade CRUD ---

def add_trade(portfolio_id: int, data: dict) -> dict:
    """Add a trade to a portfolio."""
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO trades (portfolio_id, ticker, trade_type, quantity, price,
                               commission, trade_date, note)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (portfolio_id, data["ticker"].upper(), data["trade_type"].upper(),
         data["quantity"], data["price"], data.get("commission", 0.0),
         data["trade_date"], data.get("note")),
    )
    conn.commit()
    return {"id": cur.lastrowid, "portfolio_id": portfolio_id, **data}


def delete_trade(portfolio_id: int, trade_id: int) -> bool:
    """Delete a trade."""
    conn = get_connection()
    conn.execute(
        "DELETE FROM trades WHERE id = ? AND portfolio_id = ?",
        (trade_id, portfolio_id),
    )
    conn.commit()
    return True


def get_trades(portfolio_id: int) -> list[dict]:
    """Get all trades for a portfolio."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT id, portfolio_id, ticker, trade_type, quantity, price,
                  commission, trade_date, note, created_at
           FROM trades WHERE portfolio_id = ?
           ORDER BY trade_date DESC, created_at DESC""",
        (portfolio_id,),
    ).fetchall()
    return [
        {"id": r[0], "portfolio_id": r[1], "ticker": r[2], "trade_type": r[3],
         "quantity": r[4], "price": r[5], "commission": r[6],
         "trade_date": r[7], "note": r[8], "created_at": r[9]}
        for r in rows
    ]


# --- Holdings & P&L ---

def _calculate_holdings(portfolio_id: int) -> list[dict]:
    """Calculate current holdings from trade history (FIFO)."""
    conn = get_connection()
    trades = conn.execute(
        """SELECT ticker, trade_type, quantity, price, commission
           FROM trades WHERE portfolio_id = ?
           ORDER BY trade_date ASC, created_at ASC""",
        (portfolio_id,),
    ).fetchall()

    positions: dict[str, dict] = {}
    for t in trades:
        ticker, ttype, qty, price, comm = t
        if ticker not in positions:
            positions[ticker] = {"quantity": 0.0, "total_cost": 0.0}
        pos = positions[ticker]
        if ttype == "BUY":
            pos["total_cost"] += (qty * price) + (comm or 0)
            pos["quantity"] += qty
        elif ttype == "SELL" and pos["quantity"] > 0:
            avg = pos["total_cost"] / pos["quantity"]
            pos["total_cost"] -= avg * qty
            pos["quantity"] -= qty

    holdings = []
    for ticker, pos in positions.items():
        if pos["quantity"] > 0.001:
            avg_cost = pos["total_cost"] / pos["quantity"] if pos["quantity"] > 0 else 0
            holdings.append({
                "ticker": ticker,
                "quantity": round(pos["quantity"], 6),
                "avg_cost": round(avg_cost, 4),
                "total_cost": round(pos["total_cost"], 2),
            })
    return holdings


def get_holdings(portfolio_id: int) -> dict | None:
    """Get current holdings with live prices and P&L."""
    conn = get_connection()
    portfolio = conn.execute(
        "SELECT id, name, description FROM portfolios WHERE id = ?",
        (portfolio_id,),
    ).fetchone()
    if not portfolio:
        return None

    holdings_raw = _calculate_holdings(portfolio_id)
    if not holdings_raw:
        return {
            "id": portfolio[0], "name": portfolio[1], "description": portfolio[2],
            "holdings": [], "total_value": 0.0, "total_cost": 0.0,
            "total_unrealized_gain": 0.0, "total_unrealized_gain_pct": 0.0,
        }

    tickers = [h["ticker"] for h in holdings_raw]
    batch_prices = _provider.get_batch_prices(tickers, period="5d")

    # Get stock names
    ticker_names = {}
    ticker_sectors = {}
    for ticker in tickers:
        row = conn.execute(
            "SELECT name, sector FROM stocks WHERE ticker = ?", (ticker,)
        ).fetchone()
        if row:
            ticker_names[ticker] = row[0]
            ticker_sectors[ticker] = row[1]

    holdings = []
    total_value = total_cost = 0.0

    for h in holdings_raw:
        ticker = h["ticker"]
        current_price = None
        if ticker in batch_prices and not batch_prices[ticker].empty:
            current_price = float(batch_prices[ticker]["close"].iloc[-1])

        market_value = current_price * h["quantity"] if current_price else None
        unrealized = (market_value - h["total_cost"]) if market_value else None
        unrealized_pct = (
            (unrealized / h["total_cost"]) * 100
            if unrealized is not None and h["total_cost"] != 0 else None
        )

        holdings.append({
            "ticker": ticker,
            "name": ticker_names.get(ticker),
            "sector": ticker_sectors.get(ticker),
            "quantity": h["quantity"],
            "avg_cost": h["avg_cost"],
            "current_price": round(current_price, 2) if current_price else None,
            "market_value": round(market_value, 2) if market_value else None,
            "total_cost": h["total_cost"],
            "unrealized_gain": round(unrealized, 2) if unrealized else None,
            "unrealized_gain_pct": round(unrealized_pct, 2) if unrealized_pct else None,
        })
        total_cost += h["total_cost"]
        total_value += market_value if market_value else h["total_cost"]

    total_unrealized = total_value - total_cost
    return {
        "id": portfolio[0], "name": portfolio[1], "description": portfolio[2],
        "holdings": holdings,
        "total_value": round(total_value, 2),
        "total_cost": round(total_cost, 2),
        "total_unrealized_gain": round(total_unrealized, 2),
        "total_unrealized_gain_pct": round((total_unrealized / total_cost) * 100, 2) if total_cost else 0.0,
    }


# --- Allocation ---

def get_allocation(portfolio_id: int) -> dict:
    """Get portfolio allocation by stock and sector."""
    data = get_holdings(portfolio_id)
    if not data or not data.get("holdings"):
        return {"by_stock": [], "by_sector": [], "total_value": 0.0}

    total = data["total_value"]
    if total == 0:
        return {"by_stock": [], "by_sector": [], "total_value": 0.0}

    colors = [
        "#3B82F6", "#EF4444", "#10B981", "#F59E0B", "#8B5CF6",
        "#EC4899", "#06B6D4", "#F97316", "#14B8A6", "#6366F1",
    ]
    by_stock = []
    sector_totals: dict[str, float] = {}

    for i, h in enumerate(data["holdings"]):
        value = h.get("market_value") or h["total_cost"]
        pct = (value / total) * 100
        by_stock.append({
            "label": h["ticker"], "value": round(value, 2),
            "percentage": round(pct, 2), "color": colors[i % len(colors)],
        })
        sector = h.get("sector") or "Unknown"
        sector_totals[sector] = sector_totals.get(sector, 0) + value

    by_sector = [
        {"label": s, "value": round(v, 2),
         "percentage": round((v / total) * 100, 2), "color": colors[i % len(colors)]}
        for i, (s, v) in enumerate(sorted(sector_totals.items(), key=lambda x: x[1], reverse=True))
    ]

    return {"by_stock": by_stock, "by_sector": by_sector, "total_value": round(total, 2)}


# --- Performance ---

def get_performance(portfolio_id: int, period: str = "1m") -> dict:
    """Get portfolio performance with SPY/QQQ benchmark comparison."""
    conn = get_connection()

    period_days = {"1m": 30, "3m": 90, "6m": 180, "1y": 365, "ytd": None}
    if period == "ytd":
        start_date = date(date.today().year, 1, 1)
    else:
        start_date = date.today() - timedelta(days=period_days.get(period, 30))

    trades = conn.execute(
        """SELECT ticker, trade_type, quantity, price, commission, trade_date
           FROM trades WHERE portfolio_id = ? ORDER BY trade_date ASC""",
        (portfolio_id,),
    ).fetchall()

    if not trades:
        return {"points": [], "total_return_pct": 0.0, "spy_return_pct": None, "qqq_return_pct": None}

    tickers = list({t[0] for t in trades})
    all_tickers = list(set(tickers + ["SPY", "QQQ"]))
    batch_prices = _provider.get_batch_prices(all_tickers, period=period)

    price_lookup: dict[str, dict[str, float]] = {}
    all_dates: set[str] = set()
    for ticker in tickers:
        price_lookup[ticker] = {}
        if ticker in batch_prices:
            for _, row in batch_prices[ticker].iterrows():
                d = str(row["date"])[:10]
                price_lookup[ticker][d] = float(row["close"])
                all_dates.add(d)

    def _bench_map(t: str) -> dict[str, float]:
        m: dict[str, float] = {}
        if t in batch_prices and not batch_prices[t].empty:
            for _, row in batch_prices[t].iterrows():
                m[str(row["date"])[:10]] = float(row["close"])
        return m

    spy_map = _bench_map("SPY")
    qqq_map = _bench_map("QQQ")

    sorted_dates = sorted(d for d in all_dates if d >= str(start_date))

    points: list[dict] = []
    for d in sorted_dates:
        positions: dict[str, dict] = {}
        for t in trades:
            t_ticker, t_type, t_qty, t_price, t_comm, t_date = t
            if str(t_date) > d:
                break
            if t_ticker not in positions:
                positions[t_ticker] = {"qty": 0.0, "cost": 0.0}
            if t_type == "BUY":
                positions[t_ticker]["cost"] += t_qty * t_price + (t_comm or 0)
                positions[t_ticker]["qty"] += t_qty
            else:
                if positions[t_ticker]["qty"] > 0:
                    avg = positions[t_ticker]["cost"] / positions[t_ticker]["qty"]
                    positions[t_ticker]["qty"] -= t_qty
                    positions[t_ticker]["cost"] = avg * max(0, positions[t_ticker]["qty"])

        total_value = total_cost = 0.0
        for tkr, pos in positions.items():
            if pos["qty"] <= 0:
                continue
            total_cost += pos["cost"]
            price = price_lookup.get(tkr, {}).get(d)
            total_value += pos["qty"] * price if price else pos["cost"]

        gain_pct = ((total_value - total_cost) / total_cost * 100) if total_cost > 0 else 0
        points.append({
            "date": d, "portfolio_value": round(total_value, 2),
            "total_cost": round(total_cost, 2), "gain_pct": round(gain_pct, 2),
            "spy_pct": None, "qqq_pct": None,
        })

    if sorted_dates and points:
        spy_first = spy_map.get(sorted_dates[0])
        qqq_first = qqq_map.get(sorted_dates[0])
        for p in points:
            d = p["date"]
            if spy_first and spy_first != 0:
                spy_val = spy_map.get(d)
                if spy_val:
                    p["spy_pct"] = round(((spy_val - spy_first) / spy_first) * 100, 2)
            if qqq_first and qqq_first != 0:
                qqq_val = qqq_map.get(d)
                if qqq_val:
                    p["qqq_pct"] = round(((qqq_val - qqq_first) / qqq_first) * 100, 2)

    total_return = points[-1]["gain_pct"] if points else 0.0

    def _calc_return(m: dict, dates: list) -> float | None:
        if not m or not dates:
            return None
        first, last = m.get(dates[0]), m.get(dates[-1])
        if first and last and first != 0:
            return round(((last - first) / first) * 100, 2)
        return None

    return {
        "points": points,
        "total_return_pct": total_return,
        "spy_return_pct": _calc_return(spy_map, sorted_dates),
        "qqq_return_pct": _calc_return(qqq_map, sorted_dates),
    }


# --- Dividends ---

def get_dividends(portfolio_id: int, year: int | None = None) -> dict:
    """Get dividend events for portfolio holdings."""
    if year is None:
        year = date.today().year

    holdings = _calculate_holdings(portfolio_id)
    if not holdings:
        return {"events": [], "total_annual": 0.0, "monthly_breakdown": {}}

    events: list[dict] = []
    monthly: dict[str, float] = {}

    for h in holdings:
        ticker = h["ticker"]
        qty = h["quantity"]
        div_df = _provider.get_dividends(ticker)
        if div_df.empty:
            continue

        for _, row in div_df.iterrows():
            ex_date = row["ex_date"]
            if not ex_date.startswith(str(year)):
                continue
            amount = row["amount"] or 0.0
            total = amount * qty

            events.append({
                "ticker": ticker, "ex_date": ex_date,
                "amount": amount, "quantity": qty,
                "total_amount": round(total, 2),
            })
            month_key = ex_date[:7]
            monthly[month_key] = monthly.get(month_key, 0) + total

    return {
        "events": events,
        "total_annual": round(sum(e["total_amount"] for e in events), 2),
        "monthly_breakdown": {k: round(v, 2) for k, v in monthly.items()},
    }


# --- Tax ---

def get_tax_summary(portfolio_id: int, year: int | None = None) -> dict:
    """Calculate tax summary for realized trades."""
    if year is None:
        year = date.today().year

    conn = get_connection()
    trades = conn.execute(
        """SELECT ticker, trade_type, quantity, price, commission, trade_date
           FROM trades WHERE portfolio_id = ?
           ORDER BY trade_date ASC, created_at ASC""",
        (portfolio_id,),
    ).fetchall()

    cost_basis: dict[str, list[tuple[float, float, str]]] = {}
    short_gain = long_gain = short_loss = long_loss = 0.0
    realized_trades: list[dict] = []

    for t in trades:
        ticker, ttype, qty, price, comm, trade_date = t
        if ticker not in cost_basis:
            cost_basis[ticker] = []

        if ttype == "BUY":
            cost_basis[ticker].append((qty, price, trade_date))
        elif ttype == "SELL":
            sell_year = int(str(trade_date)[:4])
            if sell_year != year:
                remaining = qty
                while remaining > 0 and cost_basis.get(ticker):
                    bq, bp, bd = cost_basis[ticker][0]
                    matched = min(remaining, bq)
                    remaining -= matched
                    if matched >= bq:
                        cost_basis[ticker].pop(0)
                    else:
                        cost_basis[ticker][0] = (bq - matched, bp, bd)
                continue

            remaining = qty
            proceeds = (qty * price) - (comm or 0)
            cost_total = 0.0
            is_long = True

            while remaining > 0 and cost_basis.get(ticker):
                bq, bp, bd = cost_basis[ticker][0]
                matched = min(remaining, bq)
                cost_total += matched * bp
                remaining -= matched

                try:
                    from datetime import datetime as dt
                    buy_d = dt.strptime(str(bd)[:10], "%Y-%m-%d")
                    sell_d = dt.strptime(str(trade_date)[:10], "%Y-%m-%d")
                    if (sell_d - buy_d).days < 365:
                        is_long = False
                except Exception:
                    pass

                if matched >= bq:
                    cost_basis[ticker].pop(0)
                else:
                    cost_basis[ticker][0] = (bq - matched, bp, bd)

            gain = proceeds - cost_total
            if gain >= 0:
                if is_long:
                    long_gain += gain
                else:
                    short_gain += gain
            else:
                if is_long:
                    long_loss += abs(gain)
                else:
                    short_loss += abs(gain)

            realized_trades.append({
                "ticker": ticker, "quantity": qty, "price": price,
                "trade_date": str(trade_date), "gain": round(gain, 2),
                "type": "Long Term" if is_long else "Short Term",
            })

    return {
        "year": year,
        "realized_gains": round(short_gain + long_gain, 2),
        "realized_losses": round(short_loss + long_loss, 2),
        "net_gain": round((short_gain + long_gain) - (short_loss + long_loss), 2),
        "short_term_gain": round(short_gain, 2),
        "long_term_gain": round(long_gain, 2),
        "short_term_loss": round(short_loss, 2),
        "long_term_loss": round(long_loss, 2),
        "trades": realized_trades,
    }
