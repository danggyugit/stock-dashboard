"""Economic calendar service for Streamlit app."""

import logging
from datetime import date, datetime

import requests
import streamlit as st

logger = logging.getLogger(__name__)


def _get_finnhub_key() -> str:
    try:
        return st.secrets.get("FINNHUB_API_KEY", "")
    except Exception:
        return ""


def _get_finnhub_client():
    key = _get_finnhub_key()
    if key:
        try:
            import finnhub
            return finnhub.Client(api_key=key)
        except Exception:
            pass
    return None


@st.cache_data(ttl=86400, show_spinner="Loading economic calendar...")
def get_economic_events(from_date: str, to_date: str) -> list[dict]:
    """Get economic indicator events."""
    key = _get_finnhub_key()
    events: list[dict] = []

    if key:
        try:
            resp = requests.get(
                "https://finnhub.io/api/v1/calendar/economic",
                params={"from": from_date, "to": to_date, "token": key},
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                raw = data.get("economicCalendar", data.get("result", []))
                for ev in raw:
                    country = ev.get("country", "US")
                    if country not in ("US", ""):
                        continue
                    imp = ev.get("impact", "medium")
                    if imp in ("1", "high"):
                        imp = "high"
                    elif imp in ("2", "medium"):
                        imp = "medium"
                    else:
                        imp = "low"
                    name = ev.get("event", "")
                    if not name:
                        continue
                    events.append({
                        "event_name": name, "country": "US",
                        "event_date": ev.get("date", from_date),
                        "event_time": ev.get("time"),
                        "actual": ev.get("actual"),
                        "forecast": ev.get("estimate") or ev.get("forecast"),
                        "previous": ev.get("prev") or ev.get("previous"),
                        "importance": imp, "unit": ev.get("unit"),
                    })
        except Exception:
            logger.exception("Finnhub economic calendar fetch failed.")

    if not events:
        events = _get_builtin_events(from_date, to_date)

    return events


def _get_builtin_events(from_date: str, to_date: str) -> list[dict]:
    """Seed recurring US economic events."""
    from_d = date.fromisoformat(from_date)
    to_d = date.fromisoformat(to_date)

    recurring = [
        ("FOMC Interest Rate Decision", "high", [1, 3, 5, 6, 7, 9, 11, 12], [28, 18, 6, 17, 29, 16, 4, 16]),
        ("US CPI (YoY)", "high", list(range(1, 13)), [14, 12, 12, 10, 13, 11, 10, 14, 10, 14, 12, 10]),
        ("US Nonfarm Payrolls", "high", list(range(1, 13)), [10, 7, 7, 4, 2, 6, 3, 1, 5, 3, 7, 5]),
        ("US GDP (QoQ)", "high", [1, 4, 7, 10], [30, 30, 30, 30]),
        ("US Retail Sales (MoM)", "medium", list(range(1, 13)), [16, 14, 14, 16, 15, 17, 16, 13, 16, 17, 14, 16]),
        ("US PPI (MoM)", "medium", list(range(1, 13)), [14, 13, 13, 11, 14, 12, 11, 12, 11, 15, 13, 11]),
        ("ISM Manufacturing PMI", "medium", list(range(1, 13)), [3, 3, 3, 1, 1, 2, 1, 1, 2, 1, 3, 1]),
        ("US Consumer Confidence", "medium", list(range(1, 13)), [28, 25, 25, 29, 27, 24, 29, 26, 30, 28, 25, 23]),
    ]

    events: list[dict] = []
    for years in range(from_d.year, to_d.year + 1):
        for name, imp, months, days in recurring:
            for i, m in enumerate(months):
                d = min(days[i], 28)
                try:
                    ev_date = date(years, m, d)
                except ValueError:
                    continue
                if ev_date < from_d or ev_date > to_d:
                    continue
                events.append({
                    "event_name": name, "country": "US",
                    "event_date": ev_date.isoformat(),
                    "event_time": None, "actual": None, "forecast": None,
                    "previous": None, "importance": imp, "unit": None,
                })

    return sorted(events, key=lambda x: x["event_date"])


@st.cache_data(ttl=86400, show_spinner="Loading earnings calendar...")
def get_earnings_events(from_date: str, to_date: str) -> list[dict]:
    """Get earnings calendar from Finnhub (SDK first, then REST fallback)."""
    events: list[dict] = []

    # Try SDK first
    client = _get_finnhub_client()
    if client:
        try:
            data = client.earnings_calendar(
                _from=from_date, to=to_date, symbol="", international=False,
            )
            raw = data.get("earningsCalendar", [])
            events = [
                {
                    "ticker": ev.get("symbol", ""),
                    "company_name": None,
                    "earnings_date": ev.get("date", from_date),
                    "eps_estimate": ev.get("epsEstimate"),
                    "eps_actual": ev.get("epsActual"),
                    "revenue_estimate": ev.get("revenueEstimate"),
                    "revenue_actual": ev.get("revenueActual"),
                }
                for ev in raw if ev.get("symbol")
            ]
        except Exception:
            logger.warning("Finnhub SDK earnings call failed, trying REST API.")

    # REST API fallback
    if not events:
        key = _get_finnhub_key()
        if key:
            try:
                resp = requests.get(
                    "https://finnhub.io/api/v1/calendar/earnings",
                    params={"from": from_date, "to": to_date, "token": key},
                    timeout=15,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    raw = data.get("earningsCalendar", [])
                    events = [
                        {
                            "ticker": ev.get("symbol", ""),
                            "company_name": None,
                            "earnings_date": ev.get("date", from_date),
                            "eps_estimate": ev.get("epsEstimate"),
                            "eps_actual": ev.get("epsActual"),
                            "revenue_estimate": ev.get("revenueEstimate"),
                            "revenue_actual": ev.get("revenueActual"),
                        }
                        for ev in raw if ev.get("symbol")
                    ]
            except Exception:
                logger.exception("Finnhub REST earnings call failed.")

    # Last fallback: yfinance earnings for major stocks
    if not events:
        events = _get_yfinance_earnings(from_date, to_date)

    return events


def _get_yfinance_earnings(from_date: str, to_date: str) -> list[dict]:
    """Fallback: get earnings from yfinance for major S&P 500 stocks."""
    import yfinance as yf

    major_tickers = [
        "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "BRK-B",
        "JPM", "V", "UNH", "JNJ", "WMT", "PG", "MA", "HD", "XOM", "CVX",
        "COST", "ABBV", "MRK", "KO", "PEP", "AVGO", "LLY", "CRM", "NFLX",
        "AMD", "INTC", "DIS", "CSCO", "ADBE", "ORCL", "QCOM", "TXN",
    ]
    events: list[dict] = []
    from_d = date.fromisoformat(from_date)
    to_d = date.fromisoformat(to_date)

    for ticker in major_tickers:
        try:
            cal = yf.Ticker(ticker).calendar
            if cal is not None and isinstance(cal, dict):
                earn_date = cal.get("Earnings Date")
                if earn_date:
                    if isinstance(earn_date, list):
                        earn_date = earn_date[0]
                    if hasattr(earn_date, "date"):
                        earn_date = earn_date.date()
                    elif isinstance(earn_date, str):
                        earn_date = date.fromisoformat(earn_date[:10])
                    if from_d <= earn_date <= to_d:
                        events.append({
                            "ticker": ticker,
                            "company_name": None,
                            "earnings_date": earn_date.isoformat(),
                            "eps_estimate": cal.get("Earnings Average"),
                            "eps_actual": None,
                            "revenue_estimate": cal.get("Revenue Average"),
                            "revenue_actual": None,
                        })
        except Exception:
            pass

    return events


def get_combined(from_date: str, to_date: str) -> dict:
    """Get combined economic + earnings calendar."""
    return {
        "economic_events": get_economic_events(from_date, to_date),
        "earnings_events": get_earnings_events(from_date, to_date),
        "from_date": from_date,
        "to_date": to_date,
    }
