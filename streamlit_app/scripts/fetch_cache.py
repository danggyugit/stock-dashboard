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

_SECTOR_ETFS = {
    "XLK": "Technology", "XLF": "Financials", "XLV": "Health Care",
    "XLY": "Consumer Discretionary", "XLP": "Consumer Staples",
    "XLE": "Energy", "XLI": "Industrials", "XLB": "Materials",
    "XLRE": "Real Estate", "XLU": "Utilities", "XLC": "Communication",
}


def _trend_stats(series: pd.Series, days: int = 30) -> dict:
    """{current,min,max,avg,trend} for the tail of a price series."""
    import numpy as np
    s = series.dropna().tail(days)
    if s.empty:
        return {}
    vals = s.values.astype(float)
    cur = float(vals[-1])
    out = {
        "current": round(cur, 4), "min": round(float(vals.min()), 4),
        "max": round(float(vals.max()), 4), "avg": round(float(vals.mean()), 4),
    }
    if len(vals) >= 5:
        slope = float(np.polyfit(range(len(vals)), vals, 1)[0])
        out["trend"] = "up" if slope > 0.05 else ("down" if slope < -0.05 else "flat")
    else:
        out["trend"] = "flat"
    return out


def build_market_snapshot() -> dict:
    """Daily market indicators snapshot for the remote MCP server.

    The MCP host (Render) can't call yfinance (Yahoo blocks datacenter IPs),
    so this residential-IP run precomputes: VIX, sector-ETF returns, S&P 500
    breadth, XLY/XLP risk ratio, DXY/Gold/Oil, and Fear & Greed.
    """
    snap: dict = {"updated_at": datetime.now(timezone.utc).isoformat()}

    tickers = (
        ["^VIX", "SPY", "QQQ", "XLY", "XLP", "DX-Y.NYB", "GC=F", "CL=F"]
        # Global indices (major economies)
        + ["^N225", "^HSI", "^GDAXI", "^FTSE", "^KS11", "^STOXX50E"]
        # Major FX pairs (relevant to USD flows / KR investors)
        + ["KRW=X", "JPY=X", "EURUSD=X", "GBPUSD=X", "CNY=X"]
        # Copper futures — leading indicator for cyclicals
        + ["HG=F"]
        + list(_SECTOR_ETFS)
    )
    data = yf.download(tickers, period="1y", auto_adjust=True,
                       group_by="ticker", progress=False, threads=True)

    def _close(tkr: str) -> pd.Series:
        try:
            return data[tkr]["Close"].dropna()
        except Exception:
            return pd.Series(dtype=float)

    # VIX — 90d history + trend
    vix = _close("^VIX")
    if not vix.empty:
        snap["vix"] = {
            **_trend_stats(vix, 30),
            "history": [{"date": d.strftime("%Y-%m-%d"), "close": round(float(v), 2)}
                        for d, v in vix.tail(90).items()],
        }

    # Sector ETF returns — 1d / 1w / 1m / 3m / 6m / ytd / 1y
    # (drives the /heatmap page's period selector — must cover every UI option)
    def _pct_change(series: pd.Series, n_bars_back: int) -> float | None:
        if len(series) <= n_bars_back:
            return None
        return round((float(series.iloc[-1]) / float(series.iloc[-1 - n_bars_back]) - 1) * 100, 2)

    def _ytd_return(series: pd.Series) -> float | None:
        # First trading day of the current calendar year (fall back to first available).
        this_year = series.index[-1].year
        year_slice = series[series.index.year == this_year]
        if year_slice.empty:
            return None
        first = year_slice.iloc[0]
        return round((float(series.iloc[-1]) / float(first) - 1) * 100, 2)

    sectors = []
    for etf, name in _SECTOR_ETFS.items():
        c = _close(etf)
        if len(c) < 22:
            continue
        sectors.append({
            "ticker": etf, "sector": name,
            "ret_1d_pct":  _pct_change(c, 1),
            "ret_1w_pct":  _pct_change(c, 5),
            "ret_1m_pct":  _pct_change(c, 21),
            "ret_3m_pct":  _pct_change(c, 63),
            "ret_6m_pct":  _pct_change(c, 126),
            "ret_ytd_pct": _ytd_return(c),
            "ret_1y_pct":  _pct_change(c, 252) or _pct_change(c, len(c) - 1),
        })
    if sectors:
        snap["sectors"] = sorted(sectors, key=lambda x: x["ret_1m_pct"], reverse=True)

    # Breadth — SPY vs 200DMA (+ 90d SPY history for the home mini chart)
    spy = _close("SPY")
    if len(spy) >= 200:
        sma200 = float(spy.rolling(200).mean().iloc[-1])
        cur = float(spy.iloc[-1])
        snap["breadth"] = {
            "spy_close": round(cur, 2), "sma200": round(sma200, 2),
            "above_pct": round((cur / sma200 - 1) * 100, 2),
            "history": [{"date": d.strftime("%Y-%m-%d"), "close": round(float(v), 2)}
                        for d, v in spy.tail(90).items()],
        }

    # SPY per-period returns — RS screener needs these to compute excess-vs-SPY.
    if len(spy) >= 22:
        snap["spy_returns"] = {
            "1d":  _pct_change(spy, 1),
            "1w":  _pct_change(spy, 5),
            "1m":  _pct_change(spy, 21),
            "3m":  _pct_change(spy, 63),
            "6m":  _pct_change(spy, 126),
            "ytd": _ytd_return(spy),
            "1y":  _pct_change(spy, 252) or _pct_change(spy, len(spy) - 1),
        }

    # Risk on/off — XLY/XLP ratio
    xly, xlp = _close("XLY"), _close("XLP")
    if not xly.empty and not xlp.empty:
        ratio = (xly / xlp).dropna()
        snap["risk_on_off"] = _trend_stats(ratio, 60)

    # Commodities / DXY (with 90d history for the home mini charts)
    comms = {}
    for key, tkr, label in [("dxy", "DX-Y.NYB", "DXY"), ("gold", "GC=F", "Gold"),
                            ("oil_wti", "CL=F", "WTI Oil"), ("copper", "HG=F", "Copper")]:
        c = _close(tkr)
        if not c.empty:
            comms[key] = {
                "label": label,
                **_trend_stats(c, 30),
                "history": [{"date": d.strftime("%Y-%m-%d"), "close": round(float(v), 2)}
                            for d, v in c.tail(90).items()],
            }
    if comms:
        snap["commodities"] = comms

    # Global indices — key markets we want on the Home / Macro view
    _INDICES = [
        ("nikkei",   "^N225",     "Nikkei 225"),
        ("hsi",      "^HSI",      "Hang Seng"),
        ("dax",      "^GDAXI",    "DAX"),
        ("ftse",     "^FTSE",     "FTSE 100"),
        ("kospi",    "^KS11",     "KOSPI"),
        ("stoxx50", "^STOXX50E",  "Euro Stoxx 50"),
        ("qqq",     "QQQ",        "Nasdaq 100 (QQQ)"),
    ]
    global_idx = {}
    for key, tkr, label in _INDICES:
        c = _close(tkr)
        if not c.empty:
            global_idx[key] = {
                "label": label,
                **_trend_stats(c, 30),
                "history": [{"date": d.strftime("%Y-%m-%d"), "close": round(float(v), 2)}
                            for d, v in c.tail(90).items()],
            }
    if global_idx:
        snap["global_indices"] = global_idx

    # Major FX pairs. Naming: dictionary key is the "quote currency" — a KR
    # user's mental model — while `label` is the standard "USD/XXX" form.
    _FX = [
        ("krw",     "KRW=X",     "USD/KRW"),
        ("jpy",     "JPY=X",     "USD/JPY"),
        ("eur",     "EURUSD=X",  "EUR/USD"),
        ("gbp",     "GBPUSD=X",  "GBP/USD"),
        ("cny",     "CNY=X",     "USD/CNY"),
    ]
    fx = {}
    for key, tkr, label in _FX:
        c = _close(tkr)
        if not c.empty:
            fx[key] = {
                "label": label,
                **_trend_stats(c, 30),
                "history": [{"date": d.strftime("%Y-%m-%d"), "close": round(float(v), 4)}
                            for d, v in c.tail(90).items()],
            }
    if fx:
        snap["fx"] = fx

    # Fear & Greed Index — inlined (streamlit_app/services/sentiment_service.py
    # depends on the streamlit runtime, which we can't import from the API venv).
    # Uses the same formulas: VIX score + momentum vs 125d MA + up/down volume ratio.
    try:
        vix_series = _close("^VIX")
        spy_series = _close("SPY")
        spy_full = data["SPY"] if data.columns.nlevels > 1 and "SPY" in data.columns.get_level_values(0) else None

        def _vix_score(v: float) -> float:
            return max(0.0, min(100.0, ((40.0 - v) / 28.0) * 100.0))

        def _momentum_score(close: pd.Series) -> float | None:
            if len(close) < 20:
                return None
            ma_window = min(125, len(close))
            ma = float(close.tail(ma_window).mean())
            if ma == 0:
                return 50.0
            pct = ((float(close.iloc[-1]) - ma) / ma) * 100.0
            return max(0.0, min(100.0, 50.0 + pct * 5.0))

        def _volume_score(spy_df) -> float | None:
            if spy_df is None or spy_df.empty:
                return None
            recent = spy_df.tail(63)  # ~3 months
            close = pd.to_numeric(recent["Close"], errors="coerce")
            vol = pd.to_numeric(recent["Volume"], errors="coerce")
            changes = close.diff()
            up_vol = float(vol[changes > 0].sum())
            down_vol = float(vol[changes < 0].sum())
            if down_vol == 0:
                return 80.0
            if up_vol == 0:
                return 20.0
            ratio = up_vol / down_vol
            return max(0.0, min(100.0, (ratio - 0.5) * 100.0))

        vix_s = _vix_score(float(vix_series.iloc[-1])) if not vix_series.empty else None
        mom_s = _momentum_score(spy_series) if not spy_series.empty else None
        vol_s = _volume_score(spy_full)

        components = [s for s in (vix_s, mom_s, vol_s) if s is not None]
        if components:
            overall = round(sum(components) / len(components), 1)
            if overall >= 75:
                label = "Extreme Greed"
            elif overall >= 55:
                label = "Greed"
            elif overall >= 45:
                label = "Neutral"
            elif overall >= 25:
                label = "Fear"
            else:
                label = "Extreme Fear"
            snap["fear_greed"] = {
                "score": overall,
                "label": label,
                "vix_score": round(vix_s, 1) if vix_s is not None else None,
                "momentum_score": round(mom_s, 1) if mom_s is not None else None,
                "volume_score": round(vol_s, 1) if vol_s is not None else None,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
    except Exception as e:
        logger.warning("Fear&Greed snapshot failed: %s", e)

    return snap


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
            raw = None
            for tbl in tables[:6]:
                cols_lower = [str(c).lower() for c in tbl.columns]
                if any("symbol" in c or "ticker" in c for c in cols_lower):
                    raw = tbl
                    break
            if raw is None:
                raise ValueError("ticker column not found in any table")
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
            if "ticker" not in df.columns:
                raise ValueError("ticker column not found after mapping")
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


def fetch_batch_prices_and_returns(
    tickers: list[str],
) -> tuple[dict[str, list[dict]], dict[str, dict]]:
    """Download 1y daily prices for all tickers.

    Returns two dicts:
      (a) prices — last 5 days per ticker (for the mini sparkline / current
          price / prev-close change fields — matches the pre-existing schema)
      (b) returns — per-period % change: 1d / 1w / 1m / 3m / 6m / ytd / 1y.
          Feeds the /heatmap page's period selector so the map recolors
          without requiring a fresh fetch per period.
    """
    logger.info("Fetching batch prices+returns (1y) for %d tickers...", len(tickers))
    prices_out: dict[str, list[dict]] = {}
    returns_out: dict[str, dict] = {}

    try:
        data = yf.download(
            tickers, period="1y",
            group_by="ticker", auto_adjust=True, threads=True,
            progress=False,
        )
        if data.empty:
            return prices_out, returns_out

        def _ret(series, n_bars_back):
            if len(series) <= n_bars_back:
                return None
            base = series.iloc[-1 - n_bars_back]
            if pd.isna(base) or base == 0:
                return None
            return round((float(series.iloc[-1]) / float(base) - 1) * 100, 2)

        def _ytd(series):
            this_year = series.index[-1].year
            year_slice = series[series.index.year == this_year]
            if year_slice.empty:
                return None
            first = year_slice.iloc[0]
            if pd.isna(first) or first == 0:
                return None
            return round((float(series.iloc[-1]) / float(first) - 1) * 100, 2)

        for ticker in tickers:
            try:
                if data.columns.nlevels > 1:
                    if ticker in data.columns.get_level_values(0):
                        df = data[ticker]
                    else:
                        continue
                else:
                    df = data

                if df.empty or df.dropna(how="all").empty:
                    continue

                close = df["Close"].dropna()
                if close.empty:
                    continue

                # Recent 5 trading days for the price array
                tail = df.dropna(subset=["Close"]).tail(5).reset_index()
                date_col = "Date" if "Date" in tail.columns else "Datetime"
                rows = []
                for _, row in tail.iterrows():
                    rows.append({
                        "date": pd.to_datetime(row[date_col]).strftime("%Y-%m-%d"),
                        "open": float(row["Open"]) if pd.notna(row["Open"]) else None,
                        "high": float(row["High"]) if pd.notna(row["High"]) else None,
                        "low": float(row["Low"]) if pd.notna(row["Low"]) else None,
                        "close": float(row["Close"]) if pd.notna(row["Close"]) else None,
                        "volume": int(row["Volume"]) if pd.notna(row["Volume"]) else 0,
                    })
                if rows:
                    prices_out[ticker] = rows

                returns_out[ticker] = {
                    "1d":  _ret(close, 1),
                    "1w":  _ret(close, 5),
                    "1m":  _ret(close, 21),
                    "3m":  _ret(close, 63),
                    "6m":  _ret(close, 126),
                    "ytd": _ytd(close),
                    "1y":  _ret(close, 252) or _ret(close, len(close) - 1),
                }
            except (KeyError, TypeError):
                continue
    except Exception:
        logger.exception("Batch prices+returns fetch failed.")

    logger.info(
        "Got prices for %d/%d, returns for %d/%d tickers.",
        len(prices_out), len(tickers), len(returns_out), len(tickers),
    )
    return prices_out, returns_out


def fetch_batch_prices(tickers: list[str]) -> dict[str, list[dict]]:
    """Backwards-compat shim — old callers only wanted prices."""
    prices, _ = fetch_batch_prices_and_returns(tickers)
    return prices


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

            # 2. Heatmap (prices + returns + caps)
            prices, returns = fetch_batch_prices_and_returns(tickers)
            caps = fetch_market_caps(tickers)

            # yfinance fast_info is aggressively rate-limited when called ~1500
            # times in a row — a run can succeed for prices but return caps for
            # only 20-30 tickers. Two-tier fallback so caps never permanently
            # disappear once we've fetched them:
            #   (1) persistent snapshot — never loses a cap, only accumulates
            #       new ones. Prevents the "cascade of Nones" bug where a bad
            #       run overwrites the prior heatmap, then next run's prior
            #       fallback is also empty.
            #   (2) previous heatmap — belt-and-suspenders (backward compat).
            prior_caps: dict[str, int] = {}
            persistent_path = CACHE_DIR / "market_caps_persistent.json"
            try:
                if persistent_path.exists():
                    persistent = json.loads(persistent_path.read_text(encoding="utf-8"))
                    for t, c in (persistent.get("caps") or {}).items():
                        if c:
                            prior_caps[t] = int(c)
            except Exception:
                pass
            try:
                prior_path = CACHE_DIR / "heatmap.json"
                if prior_path.exists():
                    prior = json.loads(prior_path.read_text(encoding="utf-8"))
                    for t, row in (prior.get("tickers") or {}).items():
                        c = row.get("market_cap")
                        if c and t not in prior_caps:
                            prior_caps[t] = c
            except Exception:
                pass

            # Update the persistent snapshot with any fresh caps we got today.
            # This is the "sticky" store — once a ticker's cap is here, it
            # survives even if every future fetch fails.
            persistent_caps = dict(prior_caps)  # start with everything known
            for t, c in caps.items():
                if c:
                    persistent_caps[t] = c
            try:
                persistent_path.write_text(
                    json.dumps(
                        {
                            "updated_at": now_iso,
                            "count": len(persistent_caps),
                            "caps": persistent_caps,
                        },
                        separators=(",", ":"),
                    ),
                    encoding="utf-8",
                )
                logger.info("Persistent market_caps snapshot: %d tickers",
                            len(persistent_caps))
            except Exception as e:
                logger.warning("Persistent caps snapshot write failed: %s", e)

            merged_caps = 0
            heatmap = {
                "updated_at": now_iso,
                "tickers": {},
            }
            for ticker in tickers:
                row = stocks_df[stocks_df["ticker"] == ticker].iloc[0]
                cap = caps.get(ticker)
                if not cap and ticker in prior_caps:
                    cap = prior_caps[ticker]
                    merged_caps += 1
                heatmap["tickers"][ticker] = {
                    "name": row["name"],
                    "sector": row["sector"],
                    "market_cap": cap,
                    "prices": prices.get(ticker, []),
                    "returns": returns.get(ticker),  # {1d, 1w, 1m, 3m, 6m, ytd, 1y}
                }
            if merged_caps:
                logger.info(
                    "Filled %d/%d market caps from prior cache (yfinance rate-limited)",
                    merged_caps, len(tickers),
                )
            write_json("heatmap.json", heatmap)

            # Market snapshot for the remote MCP server (VIX/sectors/breadth/...)
            try:
                snap = build_market_snapshot()
                if snap and len(snap) > 1:
                    write_json("market_snapshot.json", snap)
            except Exception:
                logger.exception("market snapshot build failed (non-critical)")
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

        # 4. Meta — in --fundamentals-only mode prices/heatmap are NOT refreshed,
        #    so carry forward the prior counts instead of overwriting with 0
        #    (otherwise meta.json falsely reports price_count: 0 even though
        #     heatmap.json still holds valid prices from the last full fetch).
        prev_meta = {}
        try:
            _mp = CACHE_DIR / "meta.json"
            if _mp.exists():
                prev_meta = json.loads(_mp.read_text(encoding="utf-8"))
        except Exception:
            prev_meta = {}

        if fundamentals_only:
            price_count = prev_meta.get("price_count", 0)
            cap_count = prev_meta.get("market_cap_count", 0)
            # keep the timestamp of the last real price refresh
            prices_updated_at = prev_meta.get("prices_updated_at") or prev_meta.get("updated_at")
        else:
            price_count = len(prices)
            cap_count = len(caps)
            prices_updated_at = now_iso

        meta = {
            "updated_at": now_iso,
            "stock_count": len(stocks_df),
            "price_count": price_count,
            "market_cap_count": cap_count,
            "prices_updated_at": prices_updated_at,
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
