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

    # Process in market-cap-desc order (no shuffle). Shuffle made the
    # request stream look like bot traffic to yfinance and triggered
    # immediate rate limiting on every batch attempt. Sequential desc
    # order matches the natural order normal users browse in.
    work = list(tickers)

    logger.info("Fetching fundamentals for %d tickers (mcap desc, sequential)...",
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


def fetch_fundamentals_chunked(
    tickers: list[str],
    chunk_size: int = 100,
    rest_seconds: int = 240,
    delay: float = 0.5,
) -> dict[str, dict]:
    """Chunked fundamentals fetch — built to bypass yfinance bot detection.

    AI Quant Lab successfully processes 76 tickers from Streamlit Cloud
    (data-center IP) by using a single short-lived session at low
    cadence. This function applies the same pattern to a much larger
    universe by splitting it into N chunks of `chunk_size`, with:

      - A FRESH curl_cffi session per chunk (resets bot reputation)
      - Sequential calls inside the chunk at `delay`s between requests
      - A `rest_seconds` cooldown between chunks (lets yfinance's
        sliding rate-limit window drain to zero)

    Args:
        tickers: list of tickers (assume sorted by importance)
        chunk_size: tickers per chunk (default 100, mirrors AI Quant
                    Lab's per-session footprint)
        rest_seconds: cooldown between chunks (default 240 = 4 min)
        delay: seconds between requests inside a chunk (default 0.5)

    Returns:
        dict {ticker: fundamentals_dict}

    Estimated runtime for 1500 tickers @ chunk=100, rest=240, delay=0.5:
        15 chunks × (100 × 0.5s + 240s rest) ≈ 73 minutes
    """
    try:
        from curl_cffi import requests as cf_requests
    except ImportError:
        cf_requests = None
        logger.warning("curl_cffi not available, falling back to default session")

    total = len(tickers)
    n_chunks = (total + chunk_size - 1) // chunk_size
    logger.info(
        "Chunked fetch: %d tickers in %d chunks of %d (rest=%ds, delay=%.1fs)",
        total, n_chunks, chunk_size, rest_seconds, delay,
    )

    result: dict[str, dict] = {}

    for chunk_idx in range(n_chunks):
        chunk_start = chunk_idx * chunk_size
        chunk = tickers[chunk_start:chunk_start + chunk_size]
        logger.info(
            "── Chunk %d/%d (tickers %d–%d) ──",
            chunk_idx + 1, n_chunks,
            chunk_start + 1, chunk_start + len(chunk),
        )

        # Fresh session per chunk — yfinance treats this as a new visitor
        if cf_requests is not None:
            session = cf_requests.Session(impersonate="chrome")
        else:
            session = None

        chunk_got = 0
        chunk_rate_limited = 0
        for i, ticker in enumerate(chunk):
            try:
                t = (yf.Ticker(ticker, session=session)
                     if session else yf.Ticker(ticker))
                info = t.info
                if info and len(info) > 5:
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
                    chunk_got += 1
            except Exception as e:
                if "RateLimit" in type(e).__name__ or "Too Many" in str(e):
                    chunk_rate_limited += 1
            time.sleep(delay)

        logger.info(
            "Chunk %d/%d done: got %d/%d (rate-limited %d). Cumulative: %d/%d",
            chunk_idx + 1, n_chunks, chunk_got, len(chunk),
            chunk_rate_limited, len(result), total,
        )

        # Early abort: if a whole chunk got nothing, the IP is hopelessly
        # blocked — sleeping won't help, just exit so we don't waste hours.
        if chunk_got == 0 and chunk_idx == 0:
            logger.error(
                "First chunk got 0 tickers — IP is rate-limited. Aborting."
            )
            break

        # Rest between chunks (skip after the last one)
        if chunk_idx + 1 < n_chunks:
            logger.info("Resting %ds before next chunk…", rest_seconds)
            time.sleep(rest_seconds)

    logger.info("Chunked fetch complete: %d/%d tickers", len(result), total)
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

    # --fundamentals-only: skip heatmap/prices, just fetch fundamentals
    # This avoids rate-limit contamination from batch yf.download() calls
    fundamentals_only = "--fundamentals-only" in sys.argv

    try:
        # 1. Stock list (S&P 1500: Large + Mid + Small Cap)
        stocks_df = fetch_sp1500_list()
        if stocks_df.empty:
            logger.error("Failed to fetch stock list.")
            return 1

        tickers = stocks_df["ticker"].tolist()

        if not fundamentals_only:
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
        else:
            logger.info("--fundamentals-only: skipping heatmap/prices")
            caps = {}  # empty — sort by ticker list order

        # 3. Fundamentals (slower, optional flags)
        #
        # Modes:
        #   --fundamentals          → top 500, single session, residential IP
        #   --fundamentals-all      → full 1500, single session, residential IP
        #   --fundamentals-only     → full 1500, NO heatmap fetch first
        #   --fundamentals-chunked  → full 1500, 100/chunk + rest, data-center IP
        #
        # --fundamentals-only is the safest for local scheduler — no batch
        # yf.download() calls that trigger rate limits before .info calls.
        if (
            "--fundamentals" in sys.argv
            or "--fundamentals-all" in sys.argv
            or "--fundamentals-chunked" in sys.argv
            or fundamentals_only
        ):
            # Sort tickers by market cap desc so the top N are the most valuable
            sorted_tickers = sorted(
                tickers,
                key=lambda t: caps.get(t) or 0,
                reverse=True,
            )

            if "--fundamentals-chunked" in sys.argv:
                funds = fetch_fundamentals_chunked(
                    sorted_tickers,
                    chunk_size=100,
                    rest_seconds=240,
                    delay=0.5,
                )
            elif fundamentals_only or "--fundamentals-all" in sys.argv:
                funds = fetch_fundamentals(sorted_tickers, max_count=None)
            else:
                funds = fetch_fundamentals(sorted_tickers, max_count=500)

            # Load existing cache for merge / safety check
            existing_tickers = {}
            existing_count = 0
            try:
                existing_path = CACHE_DIR / "fundamentals.json"
                if existing_path.exists():
                    existing = json.loads(existing_path.read_text(encoding="utf-8"))
                    existing_tickers = existing.get("tickers") or {}
                    existing_count = len(existing_tickers)
            except Exception:
                pass

            if len(funds) == 0:
                logger.error(
                    "Fundamentals fetch returned 0 tickers — keeping existing "
                    "cache (%d tickers) instead of overwriting.", existing_count,
                )
            else:
                # Incremental merge: keep existing data, overwrite only
                # tickers that were successfully fetched this run.
                # This means partial failures don't wipe out old data.
                if "--merge" in sys.argv and existing_tickers:
                    merged = dict(existing_tickers)  # start with old
                    merged.update(funds)              # overwrite with new
                    logger.info(
                        "Incremental merge: %d existing + %d new → %d total "
                        "(%d updated, %d added)",
                        existing_count, len(funds), len(merged),
                        len(set(funds) & set(existing_tickers)),
                        len(set(funds) - set(existing_tickers)),
                    )
                    funds = merged
                elif existing_count > 0 and len(funds) < existing_count // 2:
                    logger.error(
                        "Fundamentals fetch returned %d tickers, less than half "
                        "of existing %d — keeping existing cache to avoid "
                        "regression. Use --merge to do incremental update.",
                        len(funds), existing_count,
                    )
                    funds = None  # skip write

                if funds is not None:
                    fund_data = {
                        "updated_at": now_iso,
                        "tickers": funds,
                    }
                    write_json("fundamentals.json", fund_data)

        # 4. Meta (prices/caps may be absent in --fundamentals-only mode)
        meta = {
            "updated_at": now_iso,
            "stock_count": len(stocks_df),
            "price_count": len(prices) if "prices" in dir() else 0,
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
