"""yfinance wrapper for market data retrieval.

Provides methods to fetch stock information, prices, fundamentals,
and dividends using batch requests where possible.
"""

import io
import logging
from datetime import datetime, timedelta

import pandas as pd
import requests
import yfinance as yf

logger = logging.getLogger(__name__)

# Period mapping for yfinance
VALID_PERIODS = {"1d", "5d", "1w", "1mo", "1m", "3mo", "3m", "6mo", "6m", "ytd", "1y", "5y", "max"}

# Normalize period aliases
PERIOD_MAP = {
    "1d": "1d",
    "5d": "5d",
    "1w": "5d",
    "1m": "1mo",
    "1mo": "1mo",
    "3m": "3mo",
    "3mo": "3mo",
    "6m": "6mo",
    "6mo": "6mo",
    "ytd": "ytd",
    "1y": "1y",
    "5y": "5y",
    "max": "max",
}

# Interval mapping based on period
INTERVAL_MAP = {
    "1d": "5m",
    "5d": "30m",
    "1mo": "1d",
    "3mo": "1d",
    "6mo": "1d",
    "ytd": "1d",
    "1y": "1wk",
    "5y": "1wk",
    "max": "1mo",
}


import threading
from datetime import datetime as _dt

# Global lock and cache for yfinance batch downloads
_yf_lock = threading.Lock()
_yf_cache: dict[str, tuple[dict[str, pd.DataFrame], float]] = {}
_YF_CACHE_TTL = 300  # 5 minutes


class MarketDataProvider:
    """Wrapper around yfinance for market data retrieval."""

    def get_stock_list(self) -> pd.DataFrame:
        """Fetch S&P 500 stock list from Wikipedia.

        Returns:
            DataFrame with columns: ticker, name, sector, industry.
            Returns empty DataFrame on error.
        """
        try:
            url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
            resp = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                timeout=15,
            )
            resp.raise_for_status()
            tables = pd.read_html(io.StringIO(resp.text))
            df = tables[0]
            result = pd.DataFrame({
                "ticker": df["Symbol"].str.replace(".", "-", regex=False),
                "name": df["Security"],
                "sector": df["GICS Sector"],
                "industry": df["GICS Sub-Industry"],
            })
            logger.info("Fetched %d S&P 500 stocks from Wikipedia.", len(result))
            return result
        except Exception:
            logger.exception("Failed to fetch S&P 500 stock list.")
            return pd.DataFrame(columns=["ticker", "name", "sector", "industry"])

    def get_stock_info(self, ticker: str) -> dict:
        """Fetch detailed information for a single stock.

        Args:
            ticker: Stock ticker symbol.

        Returns:
            Dictionary with stock info fields. Empty dict on error.
        """
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            return {
                "ticker": ticker,
                "name": info.get("longName") or info.get("shortName", ticker),
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "market_cap": info.get("marketCap"),
                "exchange": info.get("exchange"),
                "description": info.get("longBusinessSummary"),
                "employees": info.get("fullTimeEmployees"),
                "website": info.get("website"),
                "price": info.get("currentPrice") or info.get("regularMarketPrice"),
                "prev_close": info.get("previousClose"),
                "open": info.get("open") or info.get("regularMarketOpen"),
                "day_high": info.get("dayHigh") or info.get("regularMarketDayHigh"),
                "day_low": info.get("dayLow") or info.get("regularMarketDayLow"),
                "volume": info.get("volume") or info.get("regularMarketVolume"),
                "avg_volume": info.get("averageVolume"),
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
            }
        except Exception:
            logger.exception("Failed to fetch stock info for %s.", ticker)
            return {}

    def get_daily_prices(
        self, ticker: str, period: str = "1mo", interval: str | None = None
    ) -> pd.DataFrame:
        """Fetch daily OHLCV price data for a stock.

        Thread-safe with global lock and 5-minute memory cache.

        Args:
            ticker: Stock ticker symbol.
            period: Time period (e.g., '1d', '1mo', '1y').
            interval: Data interval (e.g., '1d', '1h'). Auto-selected if None.

        Returns:
            DataFrame with columns: date, open, high, low, close, adj_close, volume.
            Returns empty DataFrame on error.
        """
        yf_period = PERIOD_MAP.get(period, period)
        if interval is None:
            interval = INTERVAL_MAP.get(yf_period, "1d")

        empty_df = pd.DataFrame(
            columns=["date", "open", "high", "low", "close", "adj_close", "volume"]
        )

        # Check cache
        cache_key = f"daily:{ticker}:{yf_period}:{interval}"
        if cache_key in _yf_cache:
            cached_data, cached_at = _yf_cache[cache_key]
            if (_dt.now().timestamp() - cached_at) < _YF_CACHE_TTL:
                return cached_data

        with _yf_lock:
            # Double-check
            if cache_key in _yf_cache:
                cached_data, cached_at = _yf_cache[cache_key]
                if (_dt.now().timestamp() - cached_at) < _YF_CACHE_TTL:
                    return cached_data

            try:
                stock = yf.Ticker(ticker)
                df = stock.history(period=yf_period, interval=interval)
                if df.empty:
                    logger.warning("No price data for %s (period=%s).", ticker, yf_period)
                    return empty_df

                df = df.reset_index()
                date_col = "Date" if "Date" in df.columns else "Datetime"
                result = pd.DataFrame({
                    "date": pd.to_datetime(df[date_col]).dt.strftime("%Y-%m-%d %H:%M:%S")
                    if interval not in ("1d", "1wk", "1mo")
                    else pd.to_datetime(df[date_col]).dt.strftime("%Y-%m-%d"),
                    "open": df["Open"],
                    "high": df["High"],
                    "low": df["Low"],
                    "close": df["Close"],
                    "adj_close": df["Close"],
                    "volume": df["Volume"].astype(int),
                })

                _yf_cache[cache_key] = (result, _dt.now().timestamp())
                return result
            except Exception:
                logger.exception("Failed to fetch daily prices for %s.", ticker)
                return empty_df

    def get_batch_prices(
        self, tickers: list[str], period: str = "1mo"
    ) -> dict[str, pd.DataFrame]:
        """Fetch price data for multiple stocks using batch download.

        Thread-safe with global lock to prevent concurrent yfinance calls.
        Results are cached in memory for 5 minutes.

        Args:
            tickers: List of ticker symbols.
            period: Time period for price data.

        Returns:
            Dictionary mapping ticker to price DataFrame.
        """
        yf_period = PERIOD_MAP.get(period, period)

        # Ensure minimum 5d download so we always have >= 2 data points
        _MIN_PERIOD = {"1d": "5d"}
        download_period = _MIN_PERIOD.get(yf_period, yf_period)

        if not tickers:
            return {}

        # Build cache key from sorted tickers + period
        cache_key = f"{download_period}:{','.join(sorted(tickers))}"

        # Check memory cache (outside lock for speed)
        if cache_key in _yf_cache:
            cached_data, cached_at = _yf_cache[cache_key]
            if (_dt.now().timestamp() - cached_at) < _YF_CACHE_TTL:
                logger.info("Cache hit for %d tickers (period=%s).", len(tickers), download_period)
                return cached_data

        # Acquire lock — only one yfinance download at a time
        with _yf_lock:
            # Double-check cache inside lock (another thread may have filled it)
            if cache_key in _yf_cache:
                cached_data, cached_at = _yf_cache[cache_key]
                if (_dt.now().timestamp() - cached_at) < _YF_CACHE_TTL:
                    return cached_data

            # Also check if a superset of tickers is already cached for this period
            for ck, (cd, ct) in _yf_cache.items():
                if ck.startswith(f"{download_period}:") and (_dt.now().timestamp() - ct) < _YF_CACHE_TTL:
                    # Check if all requested tickers are in this cached result
                    if all(t in cd for t in tickers):
                        logger.info("Cache superset hit for %d tickers.", len(tickers))
                        return {t: cd[t] for t in tickers if t in cd}

            result: dict[str, pd.DataFrame] = {}

            try:
                logger.info("Downloading prices for %d tickers (period=%s)...", len(tickers), download_period)
                data = yf.download(
                    tickers,
                    period=download_period,
                    group_by="ticker",
                    auto_adjust=True,
                    threads=True,
                )

                if data.empty:
                    logger.warning("No batch price data returned.")
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
                        ticker_df = pd.DataFrame({
                            "date": pd.to_datetime(df[date_col]).dt.strftime("%Y-%m-%d"),
                            "open": df["Open"],
                            "high": df["High"],
                            "low": df["Low"],
                            "close": df["Close"],
                            "adj_close": df["Close"],
                            "volume": pd.to_numeric(df["Volume"], errors="coerce")
                            .fillna(0)
                            .astype(int),
                        })
                        ticker_df = ticker_df.dropna(subset=["close"])
                        result[ticker] = ticker_df
                    except (KeyError, TypeError):
                        logger.warning("Failed to extract batch data for %s.", ticker)
                        continue

                logger.info("Batch fetched prices for %d/%d tickers.", len(result), len(tickers))
            except Exception:
                logger.exception("Failed to fetch batch prices.")

            # Store in cache
            if result:
                _yf_cache[cache_key] = (result, _dt.now().timestamp())

            return result

    def get_batch_market_caps(self, tickers: list[str]) -> dict[str, int]:
        """Fetch market cap for multiple stocks using concurrent requests.

        Uses yf.Ticker.fast_info for speed. Processes in batches with threading.

        Args:
            tickers: List of ticker symbols.

        Returns:
            Dictionary mapping ticker to market cap (int).
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        result: dict[str, int] = {}
        if not tickers:
            return result

        def _fetch_one(t: str) -> tuple[str, int | None]:
            try:
                info = yf.Ticker(t).fast_info
                cap = getattr(info, "market_cap", None)
                return t, int(cap) if cap else None
            except Exception:
                return t, None

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = {executor.submit(_fetch_one, t): t for t in tickers}
            for future in as_completed(futures):
                t, cap = future.result()
                if cap:
                    result[t] = cap

        logger.info("Batch fetched market caps for %d/%d tickers.", len(result), len(tickers))
        return result

    def get_fundamentals(self, ticker: str) -> dict:
        """Fetch fundamental financial metrics for a stock.

        Args:
            ticker: Stock ticker symbol.

        Returns:
            Dictionary with fundamental metrics. Empty dict on error.
        """
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
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
            logger.exception("Failed to fetch fundamentals for %s.", ticker)
            return {}

    def get_dividends(self, ticker: str) -> pd.DataFrame:
        """Fetch dividend history for a stock.

        Args:
            ticker: Stock ticker symbol.

        Returns:
            DataFrame with columns: ex_date, amount.
            Returns empty DataFrame on error.
        """
        try:
            stock = yf.Ticker(ticker)
            divs = stock.dividends
            if divs.empty:
                return pd.DataFrame(columns=["ex_date", "amount"])

            df = divs.reset_index()
            result = pd.DataFrame({
                "ex_date": pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d"),
                "amount": df["Dividends"],
            })
            return result
        except Exception:
            logger.exception("Failed to fetch dividends for %s.", ticker)
            return pd.DataFrame(columns=["ex_date", "amount"])

    def get_indices(self) -> list[dict]:
        """Fetch major market indices (S&P 500, NASDAQ, Dow, VIX).

        Returns:
            List of dicts with index info. Empty list on error.
        """
        index_tickers = {
            "^GSPC": "S&P 500",
            "^IXIC": "NASDAQ",
            "^DJI": "Dow Jones",
            "^VIX": "VIX",
        }
        results: list[dict] = []

        for ticker, name in index_tickers.items():
            try:
                stock = yf.Ticker(ticker)
                info = stock.info
                price = info.get("regularMarketPrice") or info.get("currentPrice")
                prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")

                change = None
                change_pct = None
                if price is not None and prev_close is not None and prev_close != 0:
                    change = price - prev_close
                    change_pct = (change / prev_close) * 100

                results.append({
                    "ticker": ticker,
                    "name": name,
                    "price": price,
                    "change": round(change, 2) if change is not None else None,
                    "change_pct": round(change_pct, 2) if change_pct is not None else None,
                })
            except Exception:
                logger.exception("Failed to fetch index data for %s.", ticker)
                results.append({
                    "ticker": ticker,
                    "name": name,
                    "price": None,
                    "change": None,
                    "change_pct": None,
                })

        return results

    def get_vix_current(self) -> float | None:
        """Fetch current VIX value.

        Returns:
            Current VIX value or None on error.
        """
        try:
            vix = yf.Ticker("^VIX")
            info = vix.info
            return info.get("regularMarketPrice") or info.get("currentPrice")
        except Exception:
            logger.exception("Failed to fetch VIX.")
            return None

    def get_sp500_data(self, period: str = "6mo") -> pd.DataFrame:
        """Fetch S&P 500 historical data for momentum calculations.

        Args:
            period: Time period for historical data.

        Returns:
            DataFrame with S&P 500 price history.
        """
        return self.get_daily_prices("^GSPC", period=period)

    def get_market_breadth(self) -> dict:
        """Calculate market breadth metrics (new highs vs new lows).

        Uses S&P 500 component stocks to estimate 52-week high/low counts.

        Returns:
            Dictionary with new_highs and new_lows counts.
        """
        try:
            stock_list = self.get_stock_list()
            sample_tickers = stock_list["ticker"].head(100).tolist()

            batch_data = self.get_batch_prices(sample_tickers, period="1y")

            new_highs = 0
            new_lows = 0

            for ticker, df in batch_data.items():
                if df.empty or len(df) < 2:
                    continue
                close_vals = df["close"].dropna()
                if close_vals.empty:
                    continue
                current = close_vals.iloc[-1]
                high_52w = close_vals.max()
                low_52w = close_vals.min()

                if high_52w > 0 and current >= high_52w * 0.98:
                    new_highs += 1
                if low_52w > 0 and current <= low_52w * 1.02:
                    new_lows += 1

            return {"new_highs": new_highs, "new_lows": new_lows, "total": len(batch_data)}
        except Exception:
            logger.exception("Failed to calculate market breadth.")
            return {"new_highs": 0, "new_lows": 0, "total": 0}
