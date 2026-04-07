"""Market data service for Streamlit app.

Uses @st.cache_data for caching instead of DuckDB.
Stock master data stored in SQLite for persistence.
"""

import logging
from datetime import datetime

import pandas as pd
import streamlit as st

from core.data_provider import MarketDataProvider
from database import get_connection

logger = logging.getLogger(__name__)

_SECTOR_NORMALIZE: dict[str, str] = {
    "Technology": "Information Technology",
    "Healthcare": "Health Care",
    "Financial Services": "Financials",
    "Consumer Cyclical": "Consumer Discretionary",
    "Consumer Defensive": "Consumer Staples",
    "Basic Materials": "Materials",
}

_provider = MarketDataProvider()


@st.cache_data(ttl=900, show_spinner=False)
def get_stock_list() -> pd.DataFrame:
    """Fetch and cache S&P 500 stock list."""
    df = _provider.get_stock_list()
    if not df.empty:
        _store_stocks(df)
    return df


def _store_stocks(df: pd.DataFrame) -> None:
    """Persist stock list to SQLite."""
    conn = get_connection()
    for _, row in df.iterrows():
        conn.execute(
            """INSERT OR REPLACE INTO stocks (ticker, name, sector, industry, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (row["ticker"], row["name"], row["sector"], row["industry"],
             datetime.now().isoformat()),
        )
    conn.commit()


def get_heatmap_data(period: str = "1d") -> dict:
    """Get heatmap data with priority: GitHub cache > SQLite > live fetch."""
    # 1. Try GitHub-prefetched cache (fastest, ~1s)
    from services.cache_loader import get_cached_heatmap
    github_cache = get_cached_heatmap()
    if github_cache and github_cache.get("tickers"):
        return _build_heatmap_from_github_cache(github_cache, period)

    # 2. Try SQLite/Turso cache (fast, populated by manual Refresh)
    conn = get_connection()
    cached_count = conn.execute(
        "SELECT COUNT(*) FROM daily_prices"
    ).fetchone()[0]
    if cached_count > 0:
        return _build_heatmap_from_cache(period)

    # 3. Live fetch (slow, last resort)
    return _fetch_heatmap_live(period)


def _build_heatmap_from_github_cache(cache: dict, period: str) -> dict:
    """Build heatmap dict from GitHub-cached JSON.

    Args:
        cache: JSON dict loaded from data/cache/heatmap.json.
        period: '1d' uses last 2 closes, others use first vs last.

    Returns:
        Heatmap response dict (sectors list + period + updated_at).
    """
    tickers_data = cache.get("tickers", {})
    sectors: dict[str, dict] = {}

    for ticker, info in tickers_data.items():
        sector_name = info.get("sector") or "Other"
        mkt_cap = info.get("market_cap") or 1_000_000_000
        prices = info.get("prices") or []

        if sector_name not in sectors:
            sectors[sector_name] = {
                "name": sector_name, "stocks": [], "total_market_cap": 0,
            }

        change_pct = price = volume = None
        if len(prices) >= 2:
            ref = prices[-2]["close"] if period == "1d" else prices[0]["close"]
            last = prices[-1]["close"]
            if ref and ref != 0 and last:
                change_pct = round(((last - ref) / ref) * 100, 2)
            price = last
            volume = prices[-1].get("volume")
        elif prices:
            price = prices[-1].get("close")

        sectors[sector_name]["stocks"].append({
            "ticker": ticker,
            "name": info.get("name", ticker),
            "market_cap": mkt_cap,
            "price": round(float(price), 2) if price else None,
            "change_pct": change_pct,
            "volume": volume,
        })
        sectors[sector_name]["total_market_cap"] += mkt_cap

    sector_list: list[dict] = []
    for sd in sectors.values():
        changes = [s["change_pct"] for s in sd["stocks"] if s["change_pct"] is not None]
        sd["avg_change_pct"] = round(sum(changes) / len(changes), 2) if changes else None
        sector_list.append(sd)

    sector_list.sort(key=lambda x: x.get("total_market_cap") or 0, reverse=True)
    return {
        "sectors": sector_list,
        "period": period,
        "updated_at": cache.get("updated_at"),
    }


def _build_heatmap_from_cache(period: str) -> dict:
    """Build heatmap from SQLite cached prices + market caps (instant)."""
    conn = get_connection()

    stocks = conn.execute(
        "SELECT ticker, name, sector, market_cap FROM stocks ORDER BY market_cap DESC NULLS LAST"
    ).fetchall()

    if not stocks:
        return {"sectors": [], "period": period, "updated_at": None}

    sectors: dict[str, dict] = {}
    for row in stocks:
        ticker, name, sector_name, mkt_cap = row
        sector_name = sector_name or "Other"
        mkt_cap = mkt_cap or 1_000_000_000

        if sector_name not in sectors:
            sectors[sector_name] = {"name": sector_name, "stocks": [], "total_market_cap": 0}

        # Get price change from cached daily_prices
        prices = conn.execute(
            "SELECT date, close, volume FROM daily_prices WHERE ticker = ? ORDER BY date ASC",
            (ticker,),
        ).fetchall()

        change_pct = price = volume = None
        if prices and len(prices) >= 2:
            if period == "1d":
                ref = prices[-2][1]
            else:
                ref = prices[0][1]
            last = prices[-1][1]
            if ref and ref != 0 and last:
                change_pct = round(((last - ref) / ref) * 100, 2)
            price = last
            volume = prices[-1][2]
        elif prices:
            price = prices[-1][1]

        sectors[sector_name]["stocks"].append({
            "ticker": ticker, "name": name,
            "market_cap": mkt_cap,
            "price": round(float(price), 2) if price else None,
            "change_pct": change_pct, "volume": volume,
        })
        sectors[sector_name]["total_market_cap"] += mkt_cap

    # Get last update time
    updated_at = conn.execute(
        "SELECT MAX(date) FROM daily_prices"
    ).fetchone()[0]

    sector_list = []
    for sd in sectors.values():
        changes = [s["change_pct"] for s in sd["stocks"] if s["change_pct"] is not None]
        sd["avg_change_pct"] = round(sum(changes) / len(changes), 2) if changes else None
        sector_list.append(sd)

    sector_list.sort(key=lambda x: x.get("total_market_cap") or 0, reverse=True)
    return {"sectors": sector_list, "period": period, "updated_at": updated_at}


def _fetch_heatmap_live(period: str) -> dict:
    """Live fetch heatmap data (slow). Used as fallback when cache is empty."""
    stocks_df = get_stock_list()
    if stocks_df.empty:
        return {"sectors": [], "period": period, "updated_at": None}

    all_tickers = stocks_df["ticker"].tolist()
    batch_prices = _provider.get_batch_prices(all_tickers, period=period)
    market_caps = _provider.get_batch_market_caps(all_tickers)

    # Store to SQLite for next time
    _save_heatmap_cache(batch_prices, market_caps)

    sectors: dict[str, dict] = {}
    for _, row in stocks_df.iterrows():
        ticker = row["ticker"]
        sector_name = row["sector"] or "Other"

        if sector_name not in sectors:
            sectors[sector_name] = {"name": sector_name, "stocks": [], "total_market_cap": 0}

        change_pct = price = volume = None
        if ticker in batch_prices:
            pdf = batch_prices[ticker]
            if not pdf.empty and len(pdf) >= 2:
                ref = pdf["close"].iloc[-2] if period == "1d" else pdf["close"].iloc[0]
                last = pdf["close"].iloc[-1]
                if ref and ref != 0:
                    change_pct = round(((last - ref) / ref) * 100, 2)
                price = last
                volume = int(pdf["volume"].iloc[-1]) if pd.notna(pdf["volume"].iloc[-1]) else None
            elif not pdf.empty:
                price = pdf["close"].iloc[-1]

        mkt_cap = market_caps.get(ticker, 1_000_000_000)

        sectors[sector_name]["stocks"].append({
            "ticker": ticker, "name": row["name"],
            "market_cap": mkt_cap,
            "price": round(float(price), 2) if price and pd.notna(price) else None,
            "change_pct": change_pct, "volume": volume,
        })
        sectors[sector_name]["total_market_cap"] += mkt_cap

    sector_list = []
    for sd in sectors.values():
        changes = [s["change_pct"] for s in sd["stocks"] if s["change_pct"] is not None]
        sd["avg_change_pct"] = round(sum(changes) / len(changes), 2) if changes else None
        sector_list.append(sd)

    sector_list.sort(key=lambda x: x.get("total_market_cap") or 0, reverse=True)
    return {"sectors": sector_list, "period": period, "updated_at": datetime.now().isoformat()}


def _save_heatmap_cache(
    batch_prices: dict[str, pd.DataFrame], market_caps: dict[str, int],
) -> None:
    """Store prices and market caps to SQLite."""
    conn = get_connection()

    # Update market caps
    for ticker, cap in market_caps.items():
        conn.execute("UPDATE stocks SET market_cap = ? WHERE ticker = ?", (cap, ticker))

    # Store daily prices
    conn.execute("DELETE FROM daily_prices")
    for ticker, df in batch_prices.items():
        if df.empty:
            continue
        for _, row in df.iterrows():
            try:
                conn.execute(
                    """INSERT OR REPLACE INTO daily_prices (ticker, date, open, high, low, close, volume)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (ticker, row["date"],
                     float(row["open"]) if pd.notna(row["open"]) else None,
                     float(row["high"]) if pd.notna(row["high"]) else None,
                     float(row["low"]) if pd.notna(row["low"]) else None,
                     float(row["close"]) if pd.notna(row["close"]) else None,
                     int(row["volume"]) if pd.notna(row["volume"]) else None),
                )
            except Exception:
                pass
    conn.commit()


def refresh_heatmap_cache(progress_callback=None) -> int:
    """Refresh heatmap price cache from yfinance."""
    stocks_df = get_stock_list()
    if stocks_df.empty:
        return 0

    all_tickers = stocks_df["ticker"].tolist()

    if progress_callback:
        progress_callback(1, 3, "Fetching prices...")

    batch_prices = _provider.get_batch_prices(all_tickers, period="5d")

    if progress_callback:
        progress_callback(2, 3, "Fetching market caps...")

    market_caps = _provider.get_batch_market_caps(all_tickers)

    if progress_callback:
        progress_callback(3, 3, "Saving to cache...")

    _save_heatmap_cache(batch_prices, market_caps)

    # Touch cache_meta
    try:
        conn = get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO cache_meta (key, updated_at) VALUES (?, ?)",
            ("heatmap", datetime.now().isoformat()),
        )
        conn.commit()
    except Exception:
        pass

    return len(batch_prices)


def get_heatmap_cache_status() -> dict:
    """Check heatmap cache status. Prefers GitHub cache, falls back to SQLite."""
    # Try GitHub cache first
    from services.cache_loader import get_cache_meta
    meta = get_cache_meta()
    if meta:
        return {
            "count": meta.get("price_count", 0),
            "last_date": meta.get("updated_at", "")[:19].replace("T", " "),
            "source": "github_cache",
        }

    # Fall back to SQLite/Turso
    conn = get_connection()
    count = conn.execute("SELECT COUNT(DISTINCT ticker) FROM daily_prices").fetchone()[0]
    last_date = conn.execute("SELECT MAX(date) FROM daily_prices").fetchone()[0]
    return {"count": count or 0, "last_date": last_date, "source": "sqlite"}


def heatmap_cache_age_hours() -> float | None:
    """Return age of heatmap cache in hours, based on cache_meta table."""
    conn = get_connection()
    row = conn.execute(
        "SELECT updated_at FROM cache_meta WHERE key = 'heatmap'"
    ).fetchone()
    if not row or not row[0]:
        return None
    try:
        last = datetime.fromisoformat(row[0])
        return (datetime.now() - last).total_seconds() / 3600
    except Exception:
        return None


def auto_refresh_if_stale(max_age_hours: float = 12.0) -> bool:
    """Auto-refresh heatmap cache if older than max_age_hours.

    Returns True if refreshed.
    """
    age = heatmap_cache_age_hours()
    if age is None or age > max_age_hours:
        try:
            refresh_heatmap_cache()
            conn = get_connection()
            conn.execute(
                "INSERT OR REPLACE INTO cache_meta (key, updated_at) VALUES (?, ?)",
                ("heatmap", datetime.now().isoformat()),
            )
            conn.commit()
            return True
        except Exception:
            logger.exception("Auto-refresh failed.")
    return False


@st.cache_data(ttl=900, show_spinner=False)
def _get_indices_cached() -> list[dict]:
    """Internal cached call."""
    return _provider.get_indices()


def get_indices() -> list[dict]:
    """Get major market indices. Retries if cached result has no prices."""
    result = _get_indices_cached()
    # If all prices are None, cache was poisoned by rate limit — clear and retry
    if result and all(idx.get("price") is None for idx in result):
        _get_indices_cached.clear()
        result = _get_indices_cached()
    return result


@st.cache_data(ttl=120, show_spinner=False)
def _get_chart_data_cached(ticker: str, period: str = "1mo", interval: str | None = None) -> list[dict]:
    """Internal cached chart fetch."""
    df = _provider.get_daily_prices(ticker, period=period, interval=interval)
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


def get_chart_data(ticker: str, period: str = "1mo", interval: str | None = None) -> list[dict]:
    """Get chart data. Clears cache if empty result."""
    result = _get_chart_data_cached(ticker, period, interval)
    if not result:
        _get_chart_data_cached.clear()
        result = _get_chart_data_cached(ticker, period, interval)
    return result


@st.cache_data(ttl=900, show_spinner=False)
def _get_stock_detail_cached(ticker: str) -> dict | None:
    """Internal cached call."""
    info = _provider.get_stock_info(ticker)

    # If info is empty or has no price, build minimal detail from history + fast_info
    if not info or (not info.get("price") and not info.get("name")):
        import yfinance as yf
        try:
            fi = yf.Ticker(ticker).fast_info
            hist = yf.Ticker(ticker).history(period="5d")
            price = getattr(fi, "last_price", None)
            prev = getattr(fi, "previous_close", None)
            if not price and not hist.empty:
                price = float(hist["Close"].iloc[-1])
                if len(hist) >= 2:
                    prev = float(hist["Close"].iloc[-2])

            change_pct = None
            if price and prev and prev != 0:
                change_pct = round(((price - prev) / prev) * 100, 2)

            return {
                "ticker": ticker,
                "name": ticker,
                "price": price,
                "prev_close": prev,
                "change_pct": change_pct,
                "market_cap": getattr(fi, "market_cap", None),
                "fifty_two_week_high": getattr(fi, "year_high", None),
                "fifty_two_week_low": getattr(fi, "year_low", None),
                "sector": None, "industry": None, "exchange": None,
                "description": None, "employees": None, "website": None,
                "open": None, "day_high": None, "day_low": None,
                "volume": None, "avg_volume": None,
                "pe_ratio": None, "pb_ratio": None, "ps_ratio": None,
                "eps": None, "roe": None, "debt_to_equity": None,
                "dividend_yield": None, "beta": None,
            }
        except Exception:
            return None

    price = info.get("price")
    prev = info.get("prev_close")
    change_pct = None
    if price and prev and prev != 0:
        change_pct = round(((price - prev) / prev) * 100, 2)

    info["change_pct"] = change_pct
    return info


def get_stock_detail(ticker: str) -> dict | None:
    """Get stock detail. Clears cache if result has no price (rate limit poison)."""
    result = _get_stock_detail_cached(ticker)
    if result and not result.get("price"):
        _get_stock_detail_cached.clear()
        result = _get_stock_detail_cached(ticker)
    return result


def search_stocks(query: str) -> list[dict]:
    """Search stocks by ticker or name from SQLite."""
    conn = get_connection()
    q = f"%{query.upper()}%"
    rows = conn.execute(
        """SELECT ticker, name, sector FROM stocks
           WHERE UPPER(ticker) LIKE ? OR UPPER(name) LIKE ?
           ORDER BY CASE WHEN UPPER(ticker) = ? THEN 0
                        WHEN UPPER(ticker) LIKE ? THEN 1 ELSE 2 END,
                   market_cap DESC
           LIMIT 20""",
        (q, q, query.upper(), f"{query.upper()}%"),
    ).fetchall()
    return [{"ticker": r[0], "name": r[1], "sector": r[2]} for r in rows]


@st.cache_data(ttl=900, show_spinner=False)
def get_screener_data(sector: str | None = None, sort_by: str = "market_cap") -> pd.DataFrame:
    """Get screener data as DataFrame."""
    stocks_df = get_stock_list()
    if stocks_df.empty:
        return pd.DataFrame()

    if sector and sector != "All":
        stocks_df = stocks_df[stocks_df["sector"] == sector]

    return stocks_df.reset_index(drop=True)


# --- Screener Fundamentals Cache ---

def get_fundamentals_cache_status() -> dict:
    """Check fundamentals cache status. Prefers GitHub cache."""
    # Try GitHub cache first
    from services.cache_loader import get_cached_fundamentals
    funds = get_cached_fundamentals()
    if funds and funds.get("tickers"):
        return {
            "count": len(funds["tickers"]),
            "oldest": funds.get("updated_at"),
            "newest": funds.get("updated_at"),
            "source": "github_cache",
        }

    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*), MIN(updated_at), MAX(updated_at) FROM fundamentals"
    ).fetchone()
    return {
        "count": row[0] or 0,
        "oldest": row[1],
        "newest": row[2],
        "source": "sqlite",
    }


def get_screener_from_cache() -> pd.DataFrame:
    """Load screener data. Prefers GitHub cache, falls back to SQLite."""
    # 1. Try GitHub cache first
    from services.cache_loader import get_cached_stocks, get_cached_fundamentals
    stocks_cache = get_cached_stocks()
    funds_cache = get_cached_fundamentals()

    if stocks_cache:
        rows = []
        funds_dict = (funds_cache or {}).get("tickers", {}) if funds_cache else {}
        for s in stocks_cache:
            ticker = s["ticker"]
            f = funds_dict.get(ticker, {})
            rows.append({
                "ticker": ticker,
                "name": s["name"],
                "sector": s["sector"],
                "industry": s["industry"],
                "market_cap": f.get("market_cap"),
                "pe_ratio": f.get("pe_ratio"),
                "pb_ratio": f.get("pb_ratio"),
                "ps_ratio": f.get("ps_ratio"),
                "eps": f.get("eps"),
                "roe": f.get("roe"),
                "debt_to_equity": f.get("debt_to_equity"),
                "dividend_yield": f.get("dividend_yield"),
                "beta": f.get("beta"),
                "fifty_two_week_high": f.get("fifty_two_week_high"),
                "fifty_two_week_low": f.get("fifty_two_week_low"),
                "avg_volume": f.get("avg_volume"),
            })
        # Also enrich market_cap from heatmap cache (more reliable)
        from services.cache_loader import get_cached_heatmap
        heatmap = get_cached_heatmap()
        if heatmap and heatmap.get("tickers"):
            ticker_caps = {t: info.get("market_cap") for t, info in heatmap["tickers"].items()}
            for r in rows:
                if not r.get("market_cap") and r["ticker"] in ticker_caps:
                    r["market_cap"] = ticker_caps[r["ticker"]]
        return pd.DataFrame(rows).sort_values("market_cap", ascending=False, na_position="last").reset_index(drop=True)

    # 2. Fall back to SQLite/Turso
    conn = get_connection()
    rows = conn.execute("""
        SELECT s.ticker, s.name, s.sector, s.industry, s.market_cap,
               f.pe_ratio, f.pb_ratio, f.ps_ratio, f.eps, f.roe,
               f.debt_to_equity, f.dividend_yield, f.beta,
               f.fifty_two_week_high, f.fifty_two_week_low, f.avg_volume
        FROM stocks s
        LEFT JOIN fundamentals f ON s.ticker = f.ticker
        ORDER BY s.market_cap DESC NULLS LAST
    """).fetchall()

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows, columns=[
        "ticker", "name", "sector", "industry", "market_cap",
        "pe_ratio", "pb_ratio", "ps_ratio", "eps", "roe",
        "debt_to_equity", "dividend_yield", "beta",
        "fifty_two_week_high", "fifty_two_week_low", "avg_volume",
    ])


def refresh_fundamentals_cache(progress_callback=None) -> int:
    """Fetch fundamentals for all S&P 500 stocks and store in SQLite.

    Args:
        progress_callback: Optional callable(current, total) for progress updates.

    Returns:
        Number of stocks updated.
    """
    conn = get_connection()
    stocks_df = get_stock_list()
    if stocks_df.empty:
        return 0

    tickers = stocks_df["ticker"].tolist()
    total = len(tickers)

    # Batch fetch market caps first (fast, concurrent)
    caps = _provider.get_batch_market_caps(tickers)

    # Update stocks table with market caps
    for ticker, cap in caps.items():
        conn.execute(
            "UPDATE stocks SET market_cap = ? WHERE ticker = ?",
            (cap, ticker),
        )
    conn.commit()

    # Fetch fundamentals in batches using yfinance
    import yfinance as yf
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _fetch_fund(ticker: str) -> dict | None:
        try:
            info = yf.Ticker(ticker).info
            return {
                "ticker": ticker,
                "pe_ratio": info.get("trailingPE"),
                "pb_ratio": info.get("priceToBook"),
                "ps_ratio": info.get("priceToSalesTrailing12Months"),
                "eps": info.get("trailingEps"),
                "roe": info.get("returnOnEquity"),
                "debt_to_equity": info.get("debtToEquity"),
                "dividend_yield": info.get("dividendYield"),
                "beta": info.get("beta"),
                "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
                "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
                "avg_volume": info.get("averageVolume"),
            }
        except Exception:
            return None

    updated = 0
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_fetch_fund, t): t for t in tickers}
        for i, future in enumerate(as_completed(futures)):
            result = future.result()
            if result:
                conn.execute(
                    """INSERT OR REPLACE INTO fundamentals
                       (ticker, pe_ratio, pb_ratio, ps_ratio, eps, roe,
                        debt_to_equity, dividend_yield, beta,
                        fifty_two_week_high, fifty_two_week_low, avg_volume, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (result["ticker"], result["pe_ratio"], result["pb_ratio"],
                     result["ps_ratio"], result["eps"], result["roe"],
                     result["debt_to_equity"], result["dividend_yield"],
                     result["beta"], result["fifty_two_week_high"],
                     result["fifty_two_week_low"], result["avg_volume"],
                     datetime.now().isoformat()),
                )
                updated += 1

            if progress_callback and (i + 1) % 5 == 0:
                progress_callback(i + 1, total)

        conn.commit()

    logger.info("Refreshed fundamentals for %d/%d stocks.", updated, total)
    return updated
