"""Historical data for survivorship-bias-corrected backtesting.

Two pieces:

1. **S&P 500 membership history** — Wikipedia's change log lets us
   reconstruct exactly which tickers were in the index on any past date.
   Without this, Factor Lab's universe would only include *current*
   constituents, systematically excluding companies that later failed
   (upward-biased returns).

2. **Point-in-time fundamentals** — yfinance quarterly + annual
   statements, cached per ticker. At any rebalance date, we look up the
   most recent filing that was already public at that point and compute
   factors from it (PE, PB, ROE, …) — no look-ahead.

Both datasets live in a dedicated local SQLite file
(`data/historical_cache.db`) — same reasoning as price cache:
bulk-writes to Turso are too slow.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from io import StringIO
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

logger = logging.getLogger(__name__)

_CACHE_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "historical_cache.db"
_CACHE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS sp500_changes (
        date            TEXT NOT NULL,
        added_ticker    TEXT,
        removed_ticker  TEXT,
        PRIMARY KEY (date, added_ticker, removed_ticker)
    )""",
    """CREATE TABLE IF NOT EXISTS sp500_changes_meta (
        key         TEXT PRIMARY KEY,
        updated_at  TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS pit_fundamentals (
        ticker      TEXT NOT NULL,
        period_end  TEXT NOT NULL,      -- fiscal period end date
        frequency   TEXT NOT NULL,      -- 'Q' or 'A'
        eps         REAL,
        book_value_per_share REAL,
        revenue_per_share   REAL,
        roe         REAL,
        debt_to_equity REAL,
        dividend_rate  REAL,
        PRIMARY KEY (ticker, period_end, frequency)
    )""",
    """CREATE TABLE IF NOT EXISTS pit_fundamentals_meta (
        ticker      TEXT PRIMARY KEY,
        updated_at  TEXT
    )""",
]


_conn: sqlite3.Connection | None = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(str(_CACHE_DB_PATH), check_same_thread=False)
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA synchronous=NORMAL")
        for stmt in _SCHEMA:
            _conn.execute(stmt)
        _conn.commit()
    return _conn


# ────────────────────────────────────────────────────────────────────
# S&P 500 membership history
# ────────────────────────────────────────────────────────────────────

_WIKI_SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
_CHANGES_CACHE_KEY = "sp500_changes"
_CHANGES_TTL_DAYS = 7


def _fetch_sp500_changes_from_wiki() -> pd.DataFrame:
    """Scrape Wikipedia's S&P 500 change history (second table on the page)."""
    try:
        resp = requests.get(
            _WIKI_SP500_URL,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=20,
        )
        tables = pd.read_html(StringIO(resp.text))
    except Exception as e:
        logger.warning("Wikipedia SP500 fetch failed: %s", e)
        return pd.DataFrame()
    if len(tables) < 2:
        return pd.DataFrame()
    raw = tables[1]

    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = ["_".join(str(c) for c in col).strip() for col in raw.columns]

    date_col = added_col = removed_col = None
    for c in raw.columns:
        lc = str(c).lower()
        if "date" in lc and date_col is None:
            date_col = c
        elif ("added" in lc and ("ticker" in lc or "symbol" in lc)
              and added_col is None):
            added_col = c
        elif ("removed" in lc and ("ticker" in lc or "symbol" in lc)
              and removed_col is None):
            removed_col = c

    if date_col is None:
        return pd.DataFrame()

    rows: list[dict] = []
    for _, r in raw.iterrows():
        try:
            d = pd.to_datetime(r[date_col], format="mixed")
        except Exception:
            continue
        at = str(r.get(added_col, "")).strip() if added_col else ""
        rt = str(r.get(removed_col, "")).strip() if removed_col else ""
        at = at.replace(".", "-") if at and at.lower() != "nan" else ""
        rt = rt.replace(".", "-") if rt and rt.lower() != "nan" else ""
        if at or rt:
            rows.append({
                "date": d.strftime("%Y-%m-%d"),
                "added_ticker": at, "removed_ticker": rt,
            })

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


def _is_changes_cache_fresh() -> bool:
    conn = _get_conn()
    row = conn.execute(
        "SELECT updated_at FROM sp500_changes_meta WHERE key = ?",
        (_CHANGES_CACHE_KEY,),
    ).fetchone()
    if not row or not row[0]:
        return False
    try:
        age = datetime.utcnow() - datetime.fromisoformat(row[0])
        return age < timedelta(days=_CHANGES_TTL_DAYS)
    except Exception:
        return False


def get_sp500_change_history(force_refresh: bool = False) -> pd.DataFrame:
    """Return S&P 500 change history (cached; refreshed weekly)."""
    conn = _get_conn()
    if not force_refresh and _is_changes_cache_fresh():
        rows = conn.execute(
            "SELECT date, added_ticker, removed_ticker FROM sp500_changes ORDER BY date"
        ).fetchall()
        if rows:
            return pd.DataFrame(rows, columns=["date", "added_ticker", "removed_ticker"])

    df = _fetch_sp500_changes_from_wiki()
    if df.empty:
        # Wikipedia scrape failed or its table schema changed. Fall back to the
        # cached change log, but warn loudly with its age — silently using a
        # stale membership log degrades survivorship correction without notice.
        meta_row = conn.execute(
            "SELECT updated_at FROM sp500_changes_meta WHERE key = ?",
            (_CHANGES_CACHE_KEY,),
        ).fetchone()
        age_str = "unknown age"
        if meta_row and meta_row[0]:
            try:
                age_days = (datetime.utcnow() - datetime.fromisoformat(meta_row[0])).days
                age_str = f"{age_days}d old"
            except Exception:
                pass
        rows = conn.execute(
            "SELECT date, added_ticker, removed_ticker FROM sp500_changes ORDER BY date"
        ).fetchall()
        if rows:
            logger.warning(
                "S&P 500 change log scrape returned no data — using STALE cached "
                "membership log (%s, %d rows). Survivorship correction may be "
                "outdated; check if Wikipedia's table layout changed.",
                age_str, len(rows),
            )
            return pd.DataFrame(rows, columns=["date", "added_ticker", "removed_ticker"])
        logger.error(
            "S&P 500 change log scrape returned no data AND no cache exists — "
            "survivorship correction is DISABLED for this run."
        )
        return pd.DataFrame()

    # Refresh cache
    conn.execute("DELETE FROM sp500_changes")
    conn.executemany(
        "INSERT OR REPLACE INTO sp500_changes (date, added_ticker, removed_ticker) "
        "VALUES (?, ?, ?)",
        [(r["date"], r["added_ticker"], r["removed_ticker"]) for _, r in df.iterrows()],
    )
    conn.execute(
        "INSERT OR REPLACE INTO sp500_changes_meta (key, updated_at) VALUES (?, ?)",
        (_CHANGES_CACHE_KEY, datetime.utcnow().isoformat()),
    )
    conn.commit()
    logger.info("SP500 change history refreshed: %d rows", len(df))
    return df


def reconstruct_sp500_at(
    target_date: pd.Timestamp,
    current_members: list[str],
    changes: pd.DataFrame,
) -> set[str]:
    """Rewind the change log to recover members that were in the index on target_date.

    Algorithm: start from current members, then UNDO every change that
    happened after target_date. An addition after target_date → the added
    ticker wasn't in yet at target_date, so remove it. A removal after
    target_date → the removed ticker was still in at target_date, so add it.
    """
    if changes.empty:
        return set(current_members)

    members = set(current_members)
    td = pd.to_datetime(target_date)

    # Work backwards from most recent
    ch = changes.copy()
    ch["date"] = pd.to_datetime(ch["date"])
    future = ch[ch["date"] > td].sort_values("date", ascending=False)

    for _, row in future.iterrows():
        a = row.get("added_ticker") or ""
        r = row.get("removed_ticker") or ""
        if a and a in members:
            members.discard(a)
        if r:
            members.add(r)
    return members


# ────────────────────────────────────────────────────────────────────
# Point-in-time fundamentals
# ────────────────────────────────────────────────────────────────────

_PIT_CACHE_TTL_DAYS = 30


def _is_pit_cache_fresh(ticker: str) -> bool:
    conn = _get_conn()
    row = conn.execute(
        "SELECT updated_at FROM pit_fundamentals_meta WHERE ticker = ?",
        (ticker,),
    ).fetchone()
    if not row or not row[0]:
        return False
    try:
        age = datetime.utcnow() - datetime.fromisoformat(row[0])
        return age < timedelta(days=_PIT_CACHE_TTL_DAYS)
    except Exception:
        return False


def _fetch_one_ticker_pit(ticker: str) -> list[dict]:
    """Pull quarterly + annual statements from yfinance and compute per-period factors."""
    rows: list[dict] = []
    try:
        tk = yf.Ticker(ticker)
    except Exception:
        return rows

    # Pull data, tolerate missing pieces
    def _safe(fn):
        try:
            df = fn()
            return df if df is not None and not df.empty else pd.DataFrame()
        except Exception:
            return pd.DataFrame()

    q_inc = _safe(lambda: tk.quarterly_financials)
    q_bs = _safe(lambda: tk.quarterly_balance_sheet)
    a_inc = _safe(lambda: tk.financials)
    a_bs = _safe(lambda: tk.balance_sheet)

    def _extract(row_df: pd.DataFrame, keys: list[str]) -> pd.Series:
        """Return the first row whose index (case-insensitive) matches any of keys."""
        if row_df is None or row_df.empty:
            return pd.Series(dtype="float64")
        idx_lower = {str(i).lower(): i for i in row_df.index}
        for k in keys:
            if k.lower() in idx_lower:
                return row_df.loc[idx_lower[k.lower()]]
        return pd.Series(dtype="float64")

    def _build_period_rows(inc: pd.DataFrame, bs: pd.DataFrame, freq: str) -> list[dict]:
        """Build one row per reporting period from income + balance sheet."""
        out: list[dict] = []
        if inc.empty and bs.empty:
            return out

        # Columns in yfinance are Timestamps (period end dates)
        periods = sorted(set(list(inc.columns) + list(bs.columns)), reverse=True)

        net_income = _extract(inc, ["Net Income", "Net Income Common Stockholders"])
        revenue = _extract(inc, ["Total Revenue", "Revenue"])
        equity = _extract(bs, ["Stockholders Equity", "Total Stockholder Equity",
                               "Common Stock Equity"])
        total_debt = _extract(bs, ["Total Debt", "Long Term Debt", "Net Debt"])
        shares = _extract(bs, ["Share Issued", "Ordinary Shares Number",
                               "Common Stock Shares Issued"])

        for p in periods:
            if not hasattr(p, "strftime"):
                try:
                    p = pd.Timestamp(p)
                except Exception:
                    continue
            period_end = p.strftime("%Y-%m-%d")
            ni = float(net_income.get(p)) if p in net_income.index and pd.notna(net_income.get(p)) else None
            rev = float(revenue.get(p)) if p in revenue.index and pd.notna(revenue.get(p)) else None
            eq = float(equity.get(p)) if p in equity.index and pd.notna(equity.get(p)) else None
            td = float(total_debt.get(p)) if p in total_debt.index and pd.notna(total_debt.get(p)) else None
            sh = float(shares.get(p)) if p in shares.index and pd.notna(shares.get(p)) else None

            eps = (ni / sh) if (ni is not None and sh and sh > 0) else None
            bvps = (eq / sh) if (eq is not None and sh and sh > 0) else None
            rps = (rev / sh) if (rev is not None and sh and sh > 0) else None
            # ROE based on this period (annualize later if needed)
            roe = (ni / eq) if (ni is not None and eq and eq > 0) else None
            de = (td / eq) if (td is not None and eq and eq > 0) else None

            out.append({
                "ticker": ticker,
                "period_end": period_end,
                "frequency": freq,
                "eps": eps,
                "book_value_per_share": bvps,
                "revenue_per_share": rps,
                "roe": roe,
                "debt_to_equity": de,
                "dividend_rate": None,  # Populated separately if needed
            })
        return out

    rows.extend(_build_period_rows(q_inc, q_bs, "Q"))
    rows.extend(_build_period_rows(a_inc, a_bs, "A"))
    return rows


def prefetch_pit_fundamentals(
    tickers: list[str], max_workers: int = 6,
    progress_callback=None,
) -> dict[str, int]:
    """Ensure PIT fundamentals coverage for each ticker (monthly-ish refresh).

    yfinance financials calls are per-ticker only; we parallelize modestly.
    """
    conn = _get_conn()
    to_fetch = [t for t in tickers if not _is_pit_cache_fresh(t)]
    total = len(to_fetch)
    logger.info("PIT fundamentals: %d/%d tickers need refresh", total, len(tickers))
    if progress_callback:
        progress_callback(0, total, "")
    if not to_fetch:
        return {}

    result: dict[str, int] = {}
    done = 0

    def _task(t: str) -> tuple[str, list[dict]]:
        return t, _fetch_one_ticker_pit(t)

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_task, t): t for t in to_fetch}
        for fut in as_completed(futures):
            t, rows = fut.result()
            if rows:
                conn.execute("DELETE FROM pit_fundamentals WHERE ticker = ?", (t,))
                conn.executemany(
                    """INSERT OR REPLACE INTO pit_fundamentals
                       (ticker, period_end, frequency, eps, book_value_per_share,
                        revenue_per_share, roe, debt_to_equity, dividend_rate)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    [(r["ticker"], r["period_end"], r["frequency"],
                      r["eps"], r["book_value_per_share"],
                      r["revenue_per_share"], r["roe"],
                      r["debt_to_equity"], r["dividend_rate"])
                     for r in rows],
                )
            conn.execute(
                "INSERT OR REPLACE INTO pit_fundamentals_meta (ticker, updated_at) "
                "VALUES (?, ?)",
                (t, datetime.utcnow().isoformat()),
            )
            conn.commit()
            result[t] = len(rows)
            done += 1
            if progress_callback:
                progress_callback(done, total, t)

    logger.info("PIT fundamentals refresh complete: %d tickers", len(result))
    return result


def load_pit_fundamentals(tickers: list[str]) -> pd.DataFrame:
    """Load all cached PIT fundamentals for the given tickers."""
    if not tickers:
        return pd.DataFrame()
    conn = _get_conn()
    placeholders = ",".join("?" for _ in tickers)
    rows = conn.execute(
        f"""SELECT ticker, period_end, frequency, eps, book_value_per_share,
                   revenue_per_share, roe, debt_to_equity, dividend_rate
            FROM pit_fundamentals
            WHERE ticker IN ({placeholders})
            ORDER BY ticker, period_end""",
        tickers,
    ).fetchall()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=[
        "ticker", "period_end", "frequency", "eps",
        "book_value_per_share", "revenue_per_share",
        "roe", "debt_to_equity", "dividend_rate",
    ])
    df["period_end"] = pd.to_datetime(df["period_end"])
    return df


def pit_factors_at(
    fund_df: pd.DataFrame, ticker: str, as_of: pd.Timestamp,
    price_at_as_of: float | None,
) -> dict:
    """Compute point-in-time factor values for a ticker at `as_of`.

    Uses the most recent *annual* filing that was published before `as_of`
    (assumes a 90-day reporting lag — e.g. FY2023 data isn't usable until
    about April 2024).

    Returns a dict with: pe_ratio, pb_ratio, ps_ratio, roe, debt_to_equity.
    """
    if fund_df.empty or price_at_as_of is None or price_at_as_of <= 0:
        return {}

    sub = fund_df[(fund_df["ticker"] == ticker) & (fund_df["frequency"] == "A")]
    if sub.empty:
        return {}

    # 90-day reporting lag: we can only use a report that's ≥90 days old at as_of
    usable = sub[sub["period_end"] <= as_of - pd.Timedelta(days=90)]
    if usable.empty:
        return {}
    latest = usable.sort_values("period_end").iloc[-1]

    eps = latest.get("eps")
    bvps = latest.get("book_value_per_share")
    rps = latest.get("revenue_per_share")
    roe = latest.get("roe")
    de = latest.get("debt_to_equity")

    out: dict = {}
    if eps and eps > 0:
        out["pe_ratio"] = price_at_as_of / eps
    if bvps and bvps > 0:
        out["pb_ratio"] = price_at_as_of / bvps
    if rps and rps > 0:
        out["ps_ratio"] = price_at_as_of / rps
    if roe is not None:
        out["roe"] = roe
    if de is not None:
        out["debt_to_equity"] = de
    return out
