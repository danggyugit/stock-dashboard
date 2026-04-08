"""Watchlist and Alert management service."""

import logging
from datetime import datetime

from core.data_provider import MarketDataProvider
from database import get_connection

logger = logging.getLogger(__name__)
_provider = MarketDataProvider()


# --- Watchlist CRUD ---

def add_to_watchlist(ticker: str, note: str | None = None,
                      user_id: int | None = None) -> bool:
    """Add a ticker to watchlist with current price snapshot."""
    conn = get_connection()
    ticker = ticker.upper().strip()

    # Check if already exists for this user
    existing = conn.execute(
        "SELECT id FROM watchlist WHERE ticker = ? AND user_id IS ?",
        (ticker, user_id),
    ).fetchone()
    if existing:
        return False

    # Get current price for snapshot
    info = _provider.get_stock_info(ticker)
    current_price = info.get("price") if info else None

    conn.execute(
        "INSERT INTO watchlist (user_id, ticker, note, added_price) VALUES (?, ?, ?, ?)",
        (user_id, ticker, note, current_price),
    )
    conn.commit()
    return True


def remove_from_watchlist(ticker: str, user_id: int | None = None) -> bool:
    """Remove a ticker from watchlist."""
    conn = get_connection()
    conn.execute(
        "DELETE FROM watchlist WHERE ticker = ? AND user_id IS ?",
        (ticker.upper(), user_id),
    )
    conn.commit()
    return True


def get_watchlist(user_id: int | None = None) -> list[dict]:
    """Get all watchlist items with current prices."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT id, ticker, note, added_price, added_at FROM watchlist
               WHERE user_id IS ? ORDER BY added_at DESC""",
            (user_id,),
        ).fetchall()
    except Exception:
        return []

    if not rows:
        return []

    tickers = [r[1] for r in rows]
    batch_prices = _provider.get_batch_prices(tickers, period="5d")

    result = []
    for r in rows:
        item_id, ticker, note, added_price, added_at = r
        current_price = None
        change_pct = None
        change_since_added = None

        if ticker in batch_prices and not batch_prices[ticker].empty:
            df = batch_prices[ticker]
            current_price = float(df["close"].iloc[-1])
            if len(df) >= 2:
                prev = df["close"].iloc[-2]
                if prev:
                    change_pct = round(((current_price - prev) / prev) * 100, 2)

            if added_price and added_price > 0:
                change_since_added = round(
                    ((current_price - added_price) / added_price) * 100, 2
                )

        result.append({
            "id": item_id,
            "ticker": ticker,
            "note": note,
            "added_price": added_price,
            "added_at": added_at,
            "current_price": current_price,
            "change_pct": change_pct,
            "change_since_added": change_since_added,
        })

    return result


# --- Alert CRUD ---

def create_alert(ticker: str, condition: str, threshold: float,
                  note: str | None = None, user_id: int | None = None) -> int:
    """Create a price alert."""
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO alerts (user_id, ticker, condition, threshold, note)
           VALUES (?, ?, ?, ?, ?)""",
        (user_id, ticker.upper().strip(), condition, threshold, note),
    )
    conn.commit()
    return cur.lastrowid


def delete_alert(alert_id: int, user_id: int | None = None) -> None:
    """Delete an alert. Verifies ownership if user_id given."""
    conn = get_connection()
    if user_id is not None:
        owner = conn.execute(
            "SELECT user_id FROM alerts WHERE id = ?", (alert_id,)
        ).fetchone()
        if not owner or owner[0] != user_id:
            return
    conn.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
    conn.commit()


def get_alerts(active_only: bool = False, user_id: int | None = None) -> list[dict]:
    """Get all alerts for a user."""
    conn = get_connection()
    sql = ("SELECT id, ticker, condition, threshold, note, active, triggered, "
           "triggered_at, created_at FROM alerts WHERE user_id IS ?")
    params: list = [user_id]
    if active_only:
        sql += " AND active = 1 AND triggered = 0"
    sql += " ORDER BY created_at DESC"

    try:
        rows = conn.execute(sql, params).fetchall()
    except Exception:
        return []
    return [
        {
            "id": r[0], "ticker": r[1], "condition": r[2], "threshold": r[3],
            "note": r[4], "active": bool(r[5]), "triggered": bool(r[6]),
            "triggered_at": r[7], "created_at": r[8],
        }
        for r in rows
    ]


def check_alerts(user_id: int | None = None) -> list[dict]:
    """Check active alerts for a user against current prices.

    Returns list of alerts that just triggered (newly).
    """
    conn = get_connection()
    try:
        active = conn.execute(
            """SELECT id, ticker, condition, threshold, note FROM alerts
               WHERE active = 1 AND triggered = 0 AND user_id IS ?""",
            (user_id,),
        ).fetchall()
    except Exception:
        return []

    if not active:
        return []

    # Group by ticker for batch price fetch
    tickers = list({r[1] for r in active})
    batch_prices = _provider.get_batch_prices(tickers, period="5d")

    newly_triggered: list[dict] = []
    for r in active:
        alert_id, ticker, condition, threshold, note = r
        if ticker not in batch_prices or batch_prices[ticker].empty:
            continue

        df = batch_prices[ticker]
        current = float(df["close"].iloc[-1])

        triggered = False
        if condition == "above" and current >= threshold:
            triggered = True
        elif condition == "below" and current <= threshold:
            triggered = True
        elif condition in ("change_above", "change_below") and len(df) >= 2:
            prev = df["close"].iloc[-2]
            if prev:
                change_pct = ((current - prev) / prev) * 100
                if condition == "change_above" and change_pct >= threshold:
                    triggered = True
                elif condition == "change_below" and change_pct <= threshold:
                    triggered = True

        if triggered:
            now = datetime.now().isoformat()
            conn.execute(
                "UPDATE alerts SET triggered = 1, triggered_at = ? WHERE id = ?",
                (now, alert_id),
            )
            newly_triggered.append({
                "id": alert_id, "ticker": ticker, "condition": condition,
                "threshold": threshold, "note": note, "current": current,
            })

    if newly_triggered:
        conn.commit()

    return newly_triggered


def reactivate_alert(alert_id: int, user_id: int | None = None) -> None:
    """Reactivate a triggered alert."""
    conn = get_connection()
    if user_id is not None:
        owner = conn.execute(
            "SELECT user_id FROM alerts WHERE id = ?", (alert_id,)
        ).fetchone()
        if not owner or owner[0] != user_id:
            return
    conn.execute(
        "UPDATE alerts SET triggered = 0, triggered_at = NULL WHERE id = ?",
        (alert_id,),
    )
    conn.commit()


# --- Cache freshness tracking ---

def get_cache_age(key: str) -> int | None:
    """Return age of a cache entry in seconds, or None if not found."""
    conn = get_connection()
    row = conn.execute(
        "SELECT updated_at FROM cache_meta WHERE key = ?", (key,)
    ).fetchone()
    if not row or not row[0]:
        return None
    try:
        last = datetime.fromisoformat(row[0])
        return int((datetime.now() - last).total_seconds())
    except Exception:
        return None


def touch_cache(key: str) -> None:
    """Mark a cache entry as fresh."""
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO cache_meta (key, updated_at) VALUES (?, ?)""",
        (key, datetime.now().isoformat()),
    )
    conn.commit()
