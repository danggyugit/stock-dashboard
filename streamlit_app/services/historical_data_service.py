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
    # Raw dividend ex-date history (for point-in-time trailing dividend yield)
    """CREATE TABLE IF NOT EXISTS pit_dividends (
        ticker   TEXT NOT NULL,
        ex_date  TEXT NOT NULL,
        amount   REAL,
        PRIMARY KEY (ticker, ex_date)
    )""",
]

# Columns added to pit_fundamentals after the original schema shipped — applied
# via ALTER TABLE on existing DBs (CREATE TABLE IF NOT EXISTS won't add them).
_PIT_MIGRATION_COLUMNS = {
    "shares_out": "REAL",       # shares outstanding (buyback yield)
    "ebit": "REAL",             # operating income (EBIT/EV magic formula)
    "cash": "REAL",             # cash & equivalents (enterprise value)
    "total_debt_abs": "REAL",   # absolute total debt (enterprise value)
}


def _migrate_pit_columns(conn: sqlite3.Connection) -> None:
    """Add any missing pit_fundamentals columns (idempotent).

    When new columns are added the first time, clear the freshness meta so the
    next backtest refetches the universe and populates the new fields
    (shares/EBIT/cash/debt + dividends) on demand.
    """
    existing = {row[1] for row in conn.execute("PRAGMA table_info(pit_fundamentals)")}
    added = False
    for col, typ in _PIT_MIGRATION_COLUMNS.items():
        if col not in existing:
            conn.execute(f"ALTER TABLE pit_fundamentals ADD COLUMN {col} {typ}")
            added = True
    if added:
        conn.execute("DELETE FROM pit_fundamentals_meta")


_conn: sqlite3.Connection | None = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(str(_CACHE_DB_PATH), check_same_thread=False)
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA synchronous=NORMAL")
        for stmt in _SCHEMA:
            _conn.execute(stmt)
        _migrate_pit_columns(_conn)
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
        ebit = _extract(inc, ["EBIT", "Operating Income", "Total Operating Income As Reported"])
        equity = _extract(bs, ["Stockholders Equity", "Total Stockholder Equity",
                               "Common Stock Equity"])
        total_debt = _extract(bs, ["Total Debt", "Long Term Debt", "Net Debt"])
        cash = _extract(bs, ["Cash And Cash Equivalents",
                             "Cash Cash Equivalents And Short Term Investments",
                             "Cash And Cash Equivalents And Short Term Investments"])
        shares = _extract(bs, ["Share Issued", "Ordinary Shares Number",
                               "Common Stock Shares Issued"])

        def _val(series: pd.Series, p) -> float | None:
            return float(series.get(p)) if p in series.index and pd.notna(series.get(p)) else None

        for p in periods:
            if not hasattr(p, "strftime"):
                try:
                    p = pd.Timestamp(p)
                except Exception:
                    continue
            period_end = p.strftime("%Y-%m-%d")
            ni = _val(net_income, p)
            rev = _val(revenue, p)
            eq = _val(equity, p)
            td = _val(total_debt, p)
            sh = _val(shares, p)
            ebit_v = _val(ebit, p)
            cash_v = _val(cash, p)

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
                "dividend_rate": None,  # legacy column (unused; PIT yield via pit_dividends)
                "shares_out": sh,
                "ebit": ebit_v,
                "cash": cash_v,
                "total_debt_abs": td,
            })
        return out

    rows.extend(_build_period_rows(q_inc, q_bs, "Q"))
    rows.extend(_build_period_rows(a_inc, a_bs, "A"))

    # Dividend ex-date history (point-in-time trailing yield source)
    div_rows: list[dict] = []
    try:
        divs = tk.dividends  # Series indexed by ex-date
        if divs is not None and not divs.empty:
            for ex_date, amt in divs.items():
                if pd.notna(amt) and amt > 0:
                    div_rows.append({
                        "ticker": ticker,
                        "ex_date": pd.Timestamp(ex_date).strftime("%Y-%m-%d"),
                        "amount": float(amt),
                    })
    except Exception:
        pass

    return rows, div_rows


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

    def _task(t: str) -> tuple[str, list[dict], list[dict]]:
        rows, div_rows = _fetch_one_ticker_pit(t)
        return t, rows, div_rows

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_task, t): t for t in to_fetch}
        for fut in as_completed(futures):
            t, rows, div_rows = fut.result()
            if rows:
                conn.execute("DELETE FROM pit_fundamentals WHERE ticker = ?", (t,))
                conn.executemany(
                    """INSERT OR REPLACE INTO pit_fundamentals
                       (ticker, period_end, frequency, eps, book_value_per_share,
                        revenue_per_share, roe, debt_to_equity, dividend_rate,
                        shares_out, ebit, cash, total_debt_abs)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    [(r["ticker"], r["period_end"], r["frequency"],
                      r["eps"], r["book_value_per_share"],
                      r["revenue_per_share"], r["roe"],
                      r["debt_to_equity"], r["dividend_rate"],
                      r.get("shares_out"), r.get("ebit"),
                      r.get("cash"), r.get("total_debt_abs"))
                     for r in rows],
                )
            if div_rows:
                conn.execute("DELETE FROM pit_dividends WHERE ticker = ?", (t,))
                conn.executemany(
                    "INSERT OR REPLACE INTO pit_dividends (ticker, ex_date, amount) "
                    "VALUES (?, ?, ?)",
                    [(d["ticker"], d["ex_date"], d["amount"]) for d in div_rows],
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
                   revenue_per_share, roe, debt_to_equity, dividend_rate,
                   shares_out, ebit, cash, total_debt_abs
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
        "shares_out", "ebit", "cash", "total_debt_abs",
    ])
    df["period_end"] = pd.to_datetime(df["period_end"])
    return df


def load_pit_dividends(tickers: list[str]) -> pd.DataFrame:
    """Load raw dividend ex-date history for the given tickers."""
    if not tickers:
        return pd.DataFrame()
    conn = _get_conn()
    placeholders = ",".join("?" for _ in tickers)
    rows = conn.execute(
        f"SELECT ticker, ex_date, amount FROM pit_dividends "
        f"WHERE ticker IN ({placeholders}) ORDER BY ticker, ex_date",
        tickers,
    ).fetchall()
    if not rows:
        return pd.DataFrame(columns=["ticker", "ex_date", "amount"])
    df = pd.DataFrame(rows, columns=["ticker", "ex_date", "amount"])
    df["ex_date"] = pd.to_datetime(df["ex_date"])
    return df


def pit_factors_at(
    fund_df: pd.DataFrame, ticker: str, as_of: pd.Timestamp,
    price_at_as_of: float | None,
    div_df: pd.DataFrame | None = None,
) -> dict:
    """Compute point-in-time factor values for a ticker at `as_of`.

    Uses the most recent *annual* filing that was published before `as_of`
    (assumes a 90-day reporting lag — e.g. FY2023 data isn't usable until
    about April 2024).

    Returns a dict that may include: pe_ratio, pb_ratio, ps_ratio, roe,
    debt_to_equity, net_margin, eps_growth, rev_growth, margin_change, f_score,
    dividend_yield, buyback_yield, shareholder_yield, ebit_ev_yield, roic.
    """
    if fund_df.empty or price_at_as_of is None or price_at_as_of <= 0:
        return {}

    sub = fund_df[(fund_df["ticker"] == ticker) & (fund_df["frequency"] == "A")]
    if sub.empty:
        return {}

    # 90-day reporting lag: we can only use a report that's ≥90 days old at as_of
    usable = sub[sub["period_end"] <= as_of - pd.Timedelta(days=90)].sort_values("period_end")
    if usable.empty:
        return {}
    latest = usable.iloc[-1]
    prior = usable.iloc[-2] if len(usable) >= 2 else None  # 직전 연도 (성장 팩터용)

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

    # Net margin (순이익률) = EPS / 매출주당 = 순이익/매출
    net_margin = (eps / rps) if (eps is not None and rps and rps > 0) else None
    if net_margin is not None:
        out["net_margin"] = net_margin

    # ── 성장·개선 팩터 (직전 연도 보고서 필요 → 백테스트 가능 기간 1년 단축) ──
    if prior is not None:
        eps_p = prior.get("eps")
        rps_p = prior.get("revenue_per_share")
        roe_p = prior.get("roe")
        de_p = prior.get("debt_to_equity")

        if eps is not None and eps_p is not None and eps_p > 0:
            out["eps_growth"] = eps / eps_p - 1.0
        if rps is not None and rps_p is not None and rps_p > 0:
            out["rev_growth"] = rps / rps_p - 1.0

        net_margin_p = (eps_p / rps_p) if (eps_p is not None and rps_p and rps_p > 0) else None
        if net_margin is not None and net_margin_p is not None:
            out["margin_change"] = net_margin - net_margin_p

        # Mini Piotroski F-Score (0~4): 수익성·개선·재무건전성 4개 항목
        if roe is not None and roe_p is not None and de is not None and de_p is not None \
                and net_margin is not None and net_margin_p is not None:
            fscore = 0
            fscore += 1 if roe > 0 else 0              # 흑자
            fscore += 1 if roe > roe_p else 0          # ROE 개선
            fscore += 1 if de < de_p else 0            # 부채비율 감소
            fscore += 1 if net_margin > net_margin_p else 0  # 마진 개선
            out["f_score"] = float(fscore)

        # Buyback yield = 발행주식수 감소율 (자사주 매입). 직전 연도 대비.
        sh = latest.get("shares_out")
        sh_p = prior.get("shares_out")
        buyback_yield = None
        if sh is not None and sh_p is not None and sh_p > 0:
            buyback_yield = (sh_p - sh) / sh_p
            out["buyback_yield"] = buyback_yield

    # ── EBIT/EV earnings yield + ROIC (Greenblatt 원전 Magic Formula) ──
    ebit = latest.get("ebit")
    sh_latest = latest.get("shares_out")
    debt_abs = latest.get("total_debt_abs") or 0.0
    cash = latest.get("cash") or 0.0
    if ebit is not None and sh_latest and sh_latest > 0:
        market_cap = price_at_as_of * sh_latest
        ev = market_cap + debt_abs - cash
        if ev > 0:
            out["ebit_ev_yield"] = ebit / ev
        invested_capital = debt_abs + (bvps * sh_latest if (bvps and bvps > 0) else 0.0) - cash
        if invested_capital > 0:
            out["roic"] = ebit / invested_capital

    # ── Trailing-12-month dividend yield (point-in-time via ex-dates) ──
    if div_df is not None and not div_df.empty:
        dsub = div_df[div_df["ticker"] == ticker]
        if not dsub.empty:
            window_start = as_of - pd.Timedelta(days=365)
            ttm = dsub[(dsub["ex_date"] > window_start) & (dsub["ex_date"] <= as_of)]
            ttm_div = float(ttm["amount"].sum()) if not ttm.empty else 0.0
            # only emit when the stock actually pays a dividend
            if ttm_div > 0:
                out["dividend_yield"] = ttm_div / price_at_as_of

    # Shareholder yield = 배당수익률 + 자사주매입수익률 (총 주주환원)
    _div_y = out.get("dividend_yield")
    _bb_y = out.get("buyback_yield")
    if _div_y is not None or _bb_y is not None:
        out["shareholder_yield"] = (_div_y or 0.0) + (_bb_y or 0.0)

    return out
