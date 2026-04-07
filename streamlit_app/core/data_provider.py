"""yfinance wrapper for market data retrieval.

Simplified for Streamlit. Uses .history() as primary data source
to avoid .info rate limiting. Falls back to .info with delay.
"""

import io
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests
import yfinance as yf

logger = logging.getLogger(__name__)

PERIOD_MAP = {
    "1d": "1d", "5d": "5d", "1w": "5d",
    "1m": "1mo", "1mo": "1mo", "3m": "3mo", "3mo": "3mo",
    "6m": "6mo", "6mo": "6mo", "ytd": "ytd",
    "1y": "1y", "5y": "5y", "max": "max",
}

INTERVAL_MAP = {
    "1d": "5m", "5d": "30m", "1mo": "1d", "3mo": "1d",
    "6mo": "1d", "ytd": "1d", "1y": "1wk", "5y": "1wk", "max": "1mo",
}


def _safe_info(ticker: str, retries: int = 2) -> dict:
    """Fetch yf.Ticker.info with retry on rate limit."""
    for attempt in range(retries):
        try:
            return yf.Ticker(ticker).info or {}
        except Exception as e:
            if "Too Many Requests" in str(e) or "Rate" in str(e):
                wait = 2 ** attempt
                logger.warning("Rate limited on %s, waiting %ds...", ticker, wait)
                time.sleep(wait)
            else:
                logger.debug("info() failed for %s: %s", ticker, e)
                return {}
    return {}


def _fast_price(ticker: str) -> dict:
    """Get current price using fast_info (no rate limit)."""
    try:
        fi = yf.Ticker(ticker).fast_info
        return {
            "price": getattr(fi, "last_price", None),
            "prev_close": getattr(fi, "previous_close", None),
            "market_cap": getattr(fi, "market_cap", None),
            "fifty_two_week_high": getattr(fi, "year_high", None),
            "fifty_two_week_low": getattr(fi, "year_low", None),
        }
    except Exception:
        return {}


class MarketDataProvider:
    """Wrapper around yfinance for market data retrieval."""

    def get_stock_list(self) -> pd.DataFrame:
        """Fetch S&P 500 stock list from Wikipedia."""
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
            return pd.DataFrame({
                "ticker": df["Symbol"].str.replace(".", "-", regex=False),
                "name": df["Security"],
                "sector": df["GICS Sector"],
                "industry": df["GICS Sub-Industry"],
            })
        except Exception:
            logger.exception("Failed to fetch S&P 500 stock list.")
            return pd.DataFrame(columns=["ticker", "name", "sector", "industry"])

    def get_stock_info(self, ticker: str) -> dict:
        """Fetch detailed info. Uses fast_info first, then .info as fallback."""
        # fast_info for price data (no rate limit)
        fast = _fast_price(ticker)
        price = fast.get("price")
        prev_close = fast.get("prev_close")

        # If fast_info failed for price, try history
        if not price:
            try:
                hist = yf.Ticker(ticker).history(period="5d")
                if not hist.empty:
                    price = float(hist["Close"].iloc[-1])
                    if len(hist) >= 2:
                        prev_close = float(hist["Close"].iloc[-2])
            except Exception:
                pass

        # Try .info for detailed data (may rate limit)
        info = _safe_info(ticker, retries=1)

        return {
            "ticker": ticker,
            "name": info.get("longName") or info.get("shortName", ticker),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": fast.get("market_cap") or info.get("marketCap"),
            "exchange": info.get("exchange"),
            "description": info.get("longBusinessSummary"),
            "employees": info.get("fullTimeEmployees"),
            "website": info.get("website"),
            "price": price or info.get("currentPrice") or info.get("regularMarketPrice"),
            "prev_close": prev_close or info.get("previousClose"),
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
            "fifty_two_week_high": fast.get("fifty_two_week_high") or info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": fast.get("fifty_two_week_low") or info.get("fiftyTwoWeekLow"),
        }

    def get_daily_prices(
        self, ticker: str, period: str = "1mo", interval: str | None = None,
    ) -> pd.DataFrame:
        """Fetch daily OHLCV price data for a stock."""
        yf_period = PERIOD_MAP.get(period, period)
        if interval is None:
            interval = INTERVAL_MAP.get(yf_period, "1d")

        empty = pd.DataFrame(
            columns=["date", "open", "high", "low", "close", "adj_close", "volume"]
        )
        try:
            df = yf.Ticker(ticker).history(period=yf_period, interval=interval)
            if df.empty:
                return empty

            df = df.reset_index()
            date_col = "Date" if "Date" in df.columns else "Datetime"
            fmt = "%Y-%m-%d %H:%M:%S" if interval not in ("1d", "1wk", "1mo") else "%Y-%m-%d"
            return pd.DataFrame({
                "date": pd.to_datetime(df[date_col]).dt.strftime(fmt),
                "open": df["Open"],
                "high": df["High"],
                "low": df["Low"],
                "close": df["Close"],
                "adj_close": df["Close"],
                "volume": df["Volume"].astype(int),
            })
        except Exception:
            logger.exception("Failed to fetch daily prices for %s.", ticker)
            return empty

    def get_batch_prices(
        self, tickers: list[str], period: str = "1mo",
    ) -> dict[str, pd.DataFrame]:
        """Fetch price data for multiple stocks using batch download."""
        yf_period = PERIOD_MAP.get(period, period)
        _MIN_PERIOD = {"1d": "5d"}
        download_period = _MIN_PERIOD.get(yf_period, yf_period)

        if not tickers:
            return {}

        result: dict[str, pd.DataFrame] = {}
        try:
            data = yf.download(
                tickers, period=download_period,
                group_by="ticker", auto_adjust=True, threads=True,
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
                    ticker_df = pd.DataFrame({
                        "date": pd.to_datetime(df[date_col]).dt.strftime("%Y-%m-%d"),
                        "open": df["Open"],
                        "high": df["High"],
                        "low": df["Low"],
                        "close": df["Close"],
                        "adj_close": df["Close"],
                        "volume": pd.to_numeric(df["Volume"], errors="coerce").fillna(0).astype(int),
                    })
                    ticker_df = ticker_df.dropna(subset=["close"])
                    result[ticker] = ticker_df
                except (KeyError, TypeError):
                    continue
        except Exception:
            logger.exception("Failed to fetch batch prices.")

        return result

    def get_batch_market_caps(self, tickers: list[str]) -> dict[str, int]:
        """Fetch market cap using fast_info (no rate limit)."""
        result: dict[str, int] = {}
        if not tickers:
            return result

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
        return result

    def get_fundamentals(self, ticker: str) -> dict:
        """Fetch fundamental financial metrics."""
        info = _safe_info(ticker)
        if not info:
            return {}
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

    def get_dividends(self, ticker: str) -> pd.DataFrame:
        """Fetch dividend history."""
        try:
            divs = yf.Ticker(ticker).dividends
            if divs.empty:
                return pd.DataFrame(columns=["ex_date", "amount"])
            df = divs.reset_index()
            return pd.DataFrame({
                "ex_date": pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d"),
                "amount": df["Dividends"],
            })
        except Exception:
            return pd.DataFrame(columns=["ex_date", "amount"])

    def get_indices(self) -> list[dict]:
        """Fetch major market indices using fast_info + history (no rate limit)."""
        index_tickers = {
            "^GSPC": "S&P 500", "^IXIC": "NASDAQ",
            "^DJI": "Dow Jones", "^VIX": "VIX",
        }
        results: list[dict] = []
        for ticker, name in index_tickers.items():
            try:
                # Use fast_info first (most reliable, no rate limit)
                fi = yf.Ticker(ticker).fast_info
                price = getattr(fi, "last_price", None)
                prev = getattr(fi, "previous_close", None)

                # Fallback to history if fast_info fails
                if not price:
                    hist = yf.Ticker(ticker).history(period="5d")
                    if not hist.empty:
                        price = float(hist["Close"].iloc[-1])
                        if len(hist) >= 2:
                            prev = float(hist["Close"].iloc[-2])

                change = change_pct = None
                if price and prev and prev != 0:
                    change = round(price - prev, 2)
                    change_pct = round((change / prev) * 100, 2)

                results.append({
                    "ticker": ticker, "name": name, "price": price,
                    "change": change, "change_pct": change_pct,
                })
            except Exception:
                results.append({
                    "ticker": ticker, "name": name,
                    "price": None, "change": None, "change_pct": None,
                })
        return results

    def get_vix_current(self) -> float | None:
        """Fetch current VIX value."""
        try:
            return getattr(yf.Ticker("^VIX").fast_info, "last_price", None)
        except Exception:
            return None

    def get_market_breadth(self) -> dict:
        """Calculate market breadth (new highs vs new lows)."""
        try:
            stock_list = self.get_stock_list()
            sample = stock_list["ticker"].head(100).tolist()
            batch = self.get_batch_prices(sample, period="1y")
            new_highs = new_lows = 0
            for _, df in batch.items():
                if df.empty or len(df) < 2:
                    continue
                close = df["close"].dropna()
                if close.empty:
                    continue
                current = close.iloc[-1]
                if current >= close.max() * 0.98:
                    new_highs += 1
                if current <= close.min() * 1.02:
                    new_lows += 1
            return {"new_highs": new_highs, "new_lows": new_lows, "total": len(batch)}
        except Exception:
            return {"new_highs": 0, "new_lows": 0, "total": 0}
