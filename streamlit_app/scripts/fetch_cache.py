"""GitHub Actions cache fetcher.

Fetches S&P 500 data from yfinance and saves to JSON files in
streamlit_app/data/cache/. Run by GitHub Actions on a cron schedule.

Outputs:
    streamlit_app/data/cache/heatmap.json     — heatmap (prices + market caps)
    streamlit_app/data/cache/fundamentals.json — screener fundamentals
    streamlit_app/data/cache/stocks.json      — S&P 500 list
    streamlit_app/data/cache/meta.json        — last updated timestamp
"""

import io
import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def fetch_sp1500_list() -> pd.DataFrame:
    """Fetch S&P 1500 (Large + Mid + Small Cap) list from Wikipedia.

    Combines:
    - S&P 500 (Large Cap): ~503 tickers
    - S&P 400 (Mid Cap): ~400 tickers
    - S&P 600 (Small Cap): ~600 tickers
    Total: ~1500 unique tickers.
    """
    logger.info("Fetching S&P 1500 list (Large + Mid + Small Cap)...")
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}
    sources = [
        ("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", "Large Cap"),
        ("https://en.wikipedia.org/wiki/List_of_S%26P_400_companies", "Mid Cap"),
        ("https://en.wikipedia.org/wiki/List_of_S%26P_600_companies", "Small Cap"),
    ]

    frames: list[pd.DataFrame] = []
    for url, cap_tier in sources:
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            tables = pd.read_html(io.StringIO(resp.text))
            raw = tables[0]
            # Wikipedia table column names vary; map flexibly
            col_map: dict[str, str] = {}
            for c in raw.columns:
                lc = str(c).lower()
                if "symbol" in lc or "ticker" in lc:
                    col_map[c] = "ticker"
                elif "gics sector" in lc or (lc == "sector"):
                    col_map[c] = "sector"
                elif "gics sub" in lc or "industry" in lc:
                    col_map[c] = "industry"
                elif "security" in lc or "company" in lc:
                    col_map[c] = "name"
            raw = raw.rename(columns=col_map)
            needed = [c for c in ["ticker", "name", "sector", "industry"] if c in raw.columns]
            df = raw[needed].copy()
            df["ticker"] = df["ticker"].astype(str).str.replace(".", "-", regex=False).str.strip()
            df["cap_tier"] = cap_tier
            # Fill missing columns with empty
            for col in ("name", "sector", "industry"):
                if col not in df.columns:
                    df[col] = ""
            frames.append(df)
            logger.info("  %s: %d tickers", cap_tier, len(df))
        except Exception as e:
            logger.warning("Failed to fetch %s: %s", cap_tier, e)

    if not frames:
        logger.error("All Wikipedia sources failed.")
        return pd.DataFrame(columns=["ticker", "name", "sector", "industry", "cap_tier"])

    combined = pd.concat(frames, ignore_index=True)
    # Drop duplicates (S&P 500 and 400 may overlap occasionally)
    combined = combined.drop_duplicates(subset=["ticker"], keep="first")
    logger.info("Fetched %d unique S&P 1500 stocks.", len(combined))
    return combined


def fetch_batch_prices(tickers: list[str]) -> dict[str, list[dict]]:
    """Fetch 5d daily prices for all tickers."""
    logger.info("Fetching batch prices for %d tickers...", len(tickers))
    result: dict[str, list[dict]] = {}
    try:
        data = yf.download(
            tickers, period="5d",
            group_by="ticker", auto_adjust=True, threads=True,
            progress=False,
        )
        if data.empty:
            return result

        for ticker in tickers:
            try:
                if data.columns.nlevels > 1:
                    if ticker in data.columns.get_level_values(0):
                        df = data[ticker].reset_index()
                    else:
                        continue
                else:
                    df = data.reset_index()

                if df.empty or df.dropna(how="all").empty:
                    continue

                date_col = "Date" if "Date" in df.columns else "Datetime"
                df = df.dropna(subset=["Close"])
                rows = []
                for _, row in df.iterrows():
                    rows.append({
                        "date": pd.to_datetime(row[date_col]).strftime("%Y-%m-%d"),
                        "open": float(row["Open"]) if pd.notna(row["Open"]) else None,
                        "high": float(row["High"]) if pd.notna(row["High"]) else None,
                        "low": float(row["Low"]) if pd.notna(row["Low"]) else None,
                        "close": float(row["Close"]) if pd.notna(row["Close"]) else None,
                        "volume": int(row["Volume"]) if pd.notna(row["Volume"]) else 0,
                    })
                if rows:
                    result[ticker] = rows
            except (KeyError, TypeError):
                continue
    except Exception:
        logger.exception("Batch prices fetch failed.")
    logger.info("Got prices for %d/%d tickers.", len(result), len(tickers))
    return result


def fetch_market_caps(tickers: list[str]) -> dict[str, int]:
    """Fetch market cap using yf.fast_info concurrently."""
    logger.info("Fetching market caps for %d tickers...", len(tickers))
    result: dict[str, int] = {}

    def _fetch_one(t: str) -> tuple[str, int | None]:
        try:
            cap = getattr(yf.Ticker(t).fast_info, "market_cap", None)
            return t, int(cap) if cap else None
        except Exception:
            return t, None

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(_fetch_one, t): t for t in tickers}
        for future in as_completed(futures):
            t, cap = future.result()
            if cap:
                result[t] = cap
    logger.info("Got market caps for %d/%d tickers.", len(result), len(tickers))
    return result


def fetch_fundamentals(tickers: list[str], max_count: int | None = None) -> dict[str, dict]:
    """Fetch fundamentals via yf.Ticker(t).info — sequential to avoid Yahoo's
    crumb authentication race condition.

    Yahoo's quoteSummary API (used by .info) requires a per-session crumb cookie.
    Concurrent requests trigger 'Invalid Crumb' 401 errors. Sequential calls with
    a shared curl_cffi browser-impersonating session work reliably.

    Strategy notes:
      - The first few requests are most likely to hit rate limits, so we
        shuffle the order. The most valuable mega-caps are NOT at the very
        front, where they'd be the ones killed by an early rate limit.
      - A short warmup delay before the first request lets the session settle.
      - On rate limit, exponential backoff and continue (don't give up).
      - On RUNS where the result has gaps in mega caps, the second pass
        retries any of the top 10 names that failed.

    Args:
        tickers: list of tickers to fetch (assumed sorted by importance,
                 e.g. market cap desc)
        max_count: optional cap (for limiting universe to e.g. top 500)

    Returns:
        dict {ticker: fundamentals_dict}
    """
    if max_count:
        tickers = tickers[:max_count]

    # Remember the top 10 mega caps for the retry pass — these matter most
    mega_caps = list(tickers[:10])

    # Shuffle the rest so rate limits don't always hit the same prefix
    import random
    work = list(tickers)
    random.shuffle(work)

    logger.info("Fetching fundamentals for %d tickers (shuffled, sequential)...",
                len(work))

    # Shared browser-impersonating session — bypasses Yahoo's bot detection
    try:
        from curl_cffi import requests as cf_requests
        session = cf_requests.Session(impersonate="chrome")
        logger.info("Using curl_cffi Chrome session.")
    except ImportError:
        session = None
        logger.warning("curl_cffi not available, using default session.")

    # Brief warmup so the session settles before the first real request
    time.sleep(2)

    result: dict[str, dict] = {}

    def _fetch_one(ticker: str) -> bool:
        """Fetch a single ticker. Returns True on success, False on failure."""
        try:
            t = yf.Ticker(ticker, session=session) if session else yf.Ticker(ticker)
            info = t.info
            if not info or len(info) <= 5:
                return False
            result[ticker] = {
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
                "shares_outstanding": info.get("sharesOutstanding"),
                "book_value": info.get("bookValue"),
                "trailing_annual_dividend_rate": info.get("trailingAnnualDividendRate"),
                "revenue_per_share": info.get("revenuePerShare"),
            }
            return True
        except Exception as e:
            if "RateLimit" in type(e).__name__ or "Too Many" in str(e):
                logger.warning("Rate limited at %s — backing off 30s", ticker)
                time.sleep(30)
            return False

    # ── Pass 1: shuffled full list ─────────────────────────────
    consecutive_errors = 0
    delay = 0.8

    for i, ticker in enumerate(work):
        ok = _fetch_one(ticker)
        if ok:
            consecutive_errors = 0
        else:
            consecutive_errors += 1
            if consecutive_errors >= 20:
                logger.error("20 consecutive errors at %s — aborting pass 1.", ticker)
                break

        time.sleep(delay)

        if (i + 1) % 25 == 0:
            logger.info("  Pass 1 progress: %d/%d (got %d)",
                        i + 1, len(work), len(result))

    logger.info("Pass 1 done: %d/%d tickers", len(result), len(work))

    # ── Pass 2: retry any mega caps that failed ────────────────
    missing_megacaps = [t for t in mega_caps if t not in result]
    if missing_megacaps:
        logger.info("Pass 2: retrying %d missing mega caps: %s",
                    len(missing_megacaps), missing_megacaps)
        time.sleep(5)  # cool-down
        for ticker in missing_megacaps:
            ok = _fetch_one(ticker)
            if ok:
                logger.info("  Recovered %s", ticker)
            time.sleep(1.2)

    logger.info("Got fundamentals for %d/%d tickers.", len(result), len(work))
    return result


def write_json(filename: str, data) -> None:
    """Save data as JSON (UTF-8 encoding)."""
    path = CACHE_DIR / filename
    path.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    size_kb = path.stat().st_size / 1024
    logger.info("Wrote %s (%.1f KB)", path.name, size_kb)


def main() -> int:
    start = time.time()
    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        # 1. Stock list (S&P 1500: Large + Mid + Small Cap)
        stocks_df = fetch_sp1500_list()
        if stocks_df.empty:
            logger.error("Failed to fetch stock list.")
            return 1

        tickers = stocks_df["ticker"].tolist()

        # Save stocks.json
        stocks_data = stocks_df.to_dict(orient="records")
        write_json("stocks.json", stocks_data)

        # 2. Heatmap (prices + caps)
        prices = fetch_batch_prices(tickers)
        caps = fetch_market_caps(tickers)

        heatmap = {
            "updated_at": now_iso,
            "tickers": {},
        }
        for ticker in tickers:
            row = stocks_df[stocks_df["ticker"] == ticker].iloc[0]
            heatmap["tickers"][ticker] = {
                "name": row["name"],
                "sector": row["sector"],
                "market_cap": caps.get(ticker),
                "prices": prices.get(ticker, []),
            }
        write_json("heatmap.json", heatmap)

        # 3. Fundamentals (slower, optional flag)
        # Default cap at top 500 by market cap (S&P 500-ish) to keep runtime
        # under ~10 min and reduce Yahoo rate-limit risk. Override with
        # --fundamentals-all to fetch the full S&P 1500 universe.
        if "--fundamentals" in sys.argv or "--fundamentals-all" in sys.argv:
            # Sort tickers by market cap desc so the top N are the most valuable
            sorted_tickers = sorted(
                tickers,
                key=lambda t: caps.get(t) or 0,
                reverse=True,
            )
            cap_n = None if "--fundamentals-all" in sys.argv else 500
            funds = fetch_fundamentals(sorted_tickers, max_count=cap_n)
            fund_data = {
                "updated_at": now_iso,
                "tickers": funds,
            }
            write_json("fundamentals.json", fund_data)

        # 4. Meta
        meta = {
            "updated_at": now_iso,
            "stock_count": len(stocks_df),
            "price_count": len(prices),
            "market_cap_count": len(caps),
            "duration_seconds": round(time.time() - start, 1),
        }
        write_json("meta.json", meta)

        logger.info("Cache update complete in %.1fs", time.time() - start)
        return 0
    except Exception:
        logger.exception("Cache update failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
