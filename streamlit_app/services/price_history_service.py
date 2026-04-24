"""Long-horizon price history cache for backtesting.

Stores month-end close prices for S&P 500 tickers in a **dedicated local
SQLite file** (`data/price_cache.db`). Kept separate from the main
Turso-backed dashboard DB because price history is bulk, high-write data
with no cross-device sync benefit — writing to Turso adds tens of
milliseconds of network latency per row which devastates bulk-loads.

Downloads use yfinance's batch API (`yf.download([tickers])`) with
`group_by='ticker'`, which fetches many tickers in a single request
tree. Much faster than one-ticker-at-a-time calls.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

_CACHE_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "price_cache.db"
_CACHE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS price_history_monthly (
    ticker TEXT NOT NULL,
    date   TEXT NOT NULL,
    close  REAL NOT NULL,
    PRIMARY KEY (ticker, date)
)
"""

BATCH_SIZE = 40   # yfinance batch download chunk size (smaller = safer vs rate limits)


def _get_local_conn() -> sqlite3.Connection:
    """Dedicated local SQLite connection for price cache.

    Single persistent handle with WAL mode for safe concurrent reads while
    the Streamlit runtime might be writing on another thread.
    """
    conn = sqlite3.connect(str(_CACHE_DB_PATH), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute(_SCHEMA)
    return conn


_conn: sqlite3.Connection | None = None


def _conn_get() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = _get_local_conn()
    return _conn


def get_covered_tickers() -> set[str]:
    rows = _conn_get().execute(
        "SELECT DISTINCT ticker FROM price_history_monthly"
    ).fetchall()
    return {r[0] for r in rows}


def get_coverage(ticker: str) -> tuple[str | None, str | None, int]:
    row = _conn_get().execute(
        "SELECT MIN(date), MAX(date), COUNT(*) "
        "FROM price_history_monthly WHERE ticker = ?",
        (ticker,),
    ).fetchone()
    if not row:
        return None, None, 0
    return row[0], row[1], row[2] or 0


def _parse_batch_result(df: pd.DataFrame, tickers: list[str]) -> dict[str, pd.DataFrame]:
    """Parse yf batch DataFrame (MultiIndex columns: ticker × field)."""
    out: dict[str, pd.DataFrame] = {}
    if df is None or df.empty:
        return out

    # Single-ticker fallback (yfinance returns flat columns if one ticker)
    if len(tickers) == 1:
        t = tickers[0]
        if "Close" in df.columns:
            close = df["Close"]
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]
            sub = pd.DataFrame({
                "date": pd.to_datetime(df.index).strftime("%Y-%m-%d"),
                "close": pd.to_numeric(close.values, errors="coerce"),
            }).dropna(subset=["close"])
            if not sub.empty:
                out[t] = sub
        return out

    for t in tickers:
        try:
            sub_df = df[t] if t in df.columns.get_level_values(0) else None
            if sub_df is None or "Close" not in sub_df.columns:
                continue
            close = sub_df["Close"].dropna()
            if close.empty:
                continue
            out[t] = pd.DataFrame({
                "date": pd.to_datetime(close.index).strftime("%Y-%m-%d"),
                "close": pd.to_numeric(close.values, errors="coerce"),
            }).dropna(subset=["close"])
        except Exception as e:
            logger.debug("parse failed for %s: %s", t, e)
    return out


def _fetch_batch(tickers: list[str], start: str, end: str) -> dict[str, pd.DataFrame]:
    """Download month-end closes for a batch of tickers in ONE yfinance call."""
    try:
        df = yf.download(
            tickers, start=start, end=end,
            interval="1mo", auto_adjust=True, progress=False,
            threads=True, group_by="ticker",
        )
        return _parse_batch_result(df, tickers)
    except Exception as e:
        logger.warning("Batch fetch failed for %d tickers: %s", len(tickers), e)
        return {}


def _bulk_store(ticker_to_df: dict[str, pd.DataFrame]) -> int:
    """Insert all (ticker, date, close) rows in a single transaction."""
    if not ticker_to_df:
        return 0
    rows: list[tuple[str, str, float]] = []
    for t, df in ticker_to_df.items():
        if df.empty:
            continue
        for _, r in df.iterrows():
            if pd.notna(r["close"]):
                rows.append((t, r["date"], float(r["close"])))
    if not rows:
        return 0
    conn = _conn_get()
    conn.executemany(
        "INSERT OR REPLACE INTO price_history_monthly (ticker, date, close) "
        "VALUES (?, ?, ?)",
        rows,
    )
    conn.commit()
    return len(rows)


def load_monthly_prices(tickers: list[str], start: str, end: str) -> pd.DataFrame:
    """Return wide DataFrame of month-end closes (index=date, columns=tickers)."""
    if not tickers:
        return pd.DataFrame()
    conn = _conn_get()
    placeholders = ",".join("?" for _ in tickers)
    rows = conn.execute(
        f"SELECT ticker, date, close FROM price_history_monthly "
        f"WHERE ticker IN ({placeholders}) AND date >= ? AND date <= ? "
        f"ORDER BY date",
        (*tickers, start, end),
    ).fetchall()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["ticker", "date", "close"])
    df["date"] = pd.to_datetime(df["date"])
    return df.pivot(index="date", columns="ticker", values="close").sort_index()


def prefetch(
    tickers: list[str], years: int = 6,
    progress_callback=None,
) -> dict[str, int]:
    """Ensure monthly price coverage for the requested tickers."""
    end_dt = date.today()
    start_dt = end_dt - timedelta(days=years * 365 + 90)
    start, end = start_dt.isoformat(), end_dt.isoformat()

    # Figure out which tickers need (re)fetch
    conn = _conn_get()
    to_fetch: list[str] = []
    for t in tickers:
        row = conn.execute(
            "SELECT MIN(date), MAX(date) FROM price_history_monthly WHERE ticker = ?",
            (t,),
        ).fetchone()
        if not row or not row[0]:
            to_fetch.append(t)
            continue
        min_d, max_d = row[0], row[1]
        if min_d > start or max_d < (end_dt - timedelta(days=45)).isoformat():
            to_fetch.append(t)

    total = len(to_fetch)
    logger.info("Prefetch: %d/%d tickers need download", total, len(tickers))
    if progress_callback:
        progress_callback(0, total, "")
    if not to_fetch:
        return {}

    result: dict[str, int] = {}
    done = 0
    # Batch into chunks for speed
    for i in range(0, total, BATCH_SIZE):
        chunk = to_fetch[i : i + BATCH_SIZE]
        batch_data = _fetch_batch(chunk, start, end)
        n_stored = _bulk_store(batch_data)
        for t in chunk:
            result[t] = len(batch_data.get(t, pd.DataFrame()))
        done += len(chunk)
        if progress_callback:
            progress_callback(done, total, f"배치 {i // BATCH_SIZE + 1}/{(total + BATCH_SIZE - 1) // BATCH_SIZE}")
        logger.info(
            "Batch %d: fetched %d/%d tickers, stored %d rows",
            i // BATCH_SIZE + 1, len(batch_data), len(chunk), n_stored,
        )

    logger.info("Prefetch complete: %d tickers covered", len([v for v in result.values() if v > 0]))
    return result


def compute_returns_and_vol(
    prices_wide: pd.DataFrame, as_of: pd.Timestamp,
) -> pd.DataFrame:
    """For a given rebalance date, compute per-ticker metrics from prices.

    PIT-safe: uses only rows on or before `as_of`.
    """
    if prices_wide.empty:
        return pd.DataFrame()

    df = prices_wide[prices_wide.index <= as_of].dropna(how="all")
    if df.empty or len(df) < 2:
        return pd.DataFrame()

    last = df.iloc[-1]

    def _ret(months: int) -> pd.Series:
        if len(df) <= months:
            return pd.Series(index=df.columns, dtype="float64")
        past = df.iloc[-1 - months]
        return last / past - 1.0

    pct = df.pct_change(fill_method=None).dropna(how="all")
    vol = pct.tail(3).std()

    return pd.DataFrame({
        "ret_1m":  _ret(1),
        "ret_3m":  _ret(3),
        "ret_6m":  _ret(6),
        "ret_12m": _ret(12),
        "vol_90d": vol,
    })
