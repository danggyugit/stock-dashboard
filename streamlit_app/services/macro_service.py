"""Macro / Economy data service — FRED CSV + yfinance."""

import io
import logging
from datetime import timedelta

import numpy as np
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

logger = logging.getLogger(__name__)

_FRED_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv"
_FRED_API_BASE = "https://api.stlouisfed.org/fred/series/observations"
_FRED_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def _fred_csv(series_id: str, start: str = "2021-01-01") -> pd.DataFrame:
    """Fetch a FRED series. Tries CSV endpoint first, then FRED API with key."""

    def _parse(text: str) -> pd.DataFrame:
        df = pd.read_csv(io.StringIO(text))
        date_col = [c for c in df.columns if "date" in c.lower()][0]
        val_col = [c for c in df.columns if c != date_col][0]
        df = df.rename(columns={date_col: "date", val_col: "value"})
        df["date"] = pd.to_datetime(df["date"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        return df.dropna(subset=["value"]).reset_index(drop=True)

    # 1. CSV endpoint with proper User-Agent
    try:
        url = f"{_FRED_BASE}?id={series_id}&cosd={start}"
        resp = requests.get(url, headers=_FRED_HEADERS, timeout=12)
        resp.raise_for_status()
        return _parse(resp.text)
    except Exception as e:
        logger.warning("FRED CSV failed for %s: %s", series_id, e)

    # 2. FRED API with API key (if configured)
    try:
        api_key = st.secrets.get("FRED_API_KEY", "")
        if api_key:
            resp = requests.get(
                _FRED_API_BASE,
                params={
                    "series_id": series_id, "api_key": api_key,
                    "file_type": "json", "observation_start": start,
                    "sort_order": "asc",
                },
                headers=_FRED_HEADERS, timeout=12,
            )
            resp.raise_for_status()
            obs = resp.json().get("observations", [])
            df = pd.DataFrame([
                {"date": o["date"], "value": o["value"]}
                for o in obs if o.get("value") != "."
            ])
            if not df.empty:
                df["date"] = pd.to_datetime(df["date"])
                df["value"] = pd.to_numeric(df["value"], errors="coerce")
                return df.dropna(subset=["value"]).reset_index(drop=True)
    except Exception as e:
        logger.warning("FRED API failed for %s: %s", series_id, e)

    return pd.DataFrame()


def _yf_close(ticker: str, period: str = "5y") -> pd.DataFrame:
    """Fetch yfinance closing prices as DataFrame with columns [date, value]."""
    try:
        df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
        if df.empty:
            return pd.DataFrame()
        close = df["Close"].squeeze()
        return pd.DataFrame({"date": close.index, "value": close.values}).reset_index(drop=True)
    except Exception as e:
        logger.warning(f"yfinance fetch failed for {ticker}: {e}")
        return pd.DataFrame()


# ═══════════════════════════════════════════════════════════
# 1. Liquidity
# ═══════════════════════════════════════════════════════════

@st.cache_data(ttl=86400, show_spinner=False)
def get_money_supply() -> pd.DataFrame:
    """M1 & M2 money supply (monthly, $Trillions)."""
    m1 = _fred_csv("M1SL", "2021-01-01")
    m2 = _fred_csv("M2SL", "2021-01-01")
    if m1.empty or m2.empty:
        return pd.DataFrame()
    m1 = m1.rename(columns={"value": "M1"})
    m2 = m2.rename(columns={"value": "M2"})
    df = pd.merge(m1, m2, on="date", how="outer").sort_values("date")
    df["M1"] = df["M1"] / 1000  # billions → trillions
    df["M2"] = df["M2"] / 1000
    return df.dropna(subset=["M1", "M2"]).reset_index(drop=True)


@st.cache_data(ttl=86400, show_spinner=False)
def get_fed_balance_sheet() -> pd.DataFrame:
    """Fed total assets (weekly, $Trillions). WALCL series."""
    df = _fred_csv("WALCL", "2021-01-01")
    if df.empty:
        return pd.DataFrame()
    df["value"] = df["value"] / 1_000_000  # millions → trillions
    return df


# ═══════════════════════════════════════════════════════════
# 2. Interest Rates
# ═══════════════════════════════════════════════════════════

@st.cache_data(ttl=86400, show_spinner=False)
def get_fed_funds_rate() -> pd.DataFrame:
    """Effective Federal Funds Rate (daily). DFF series, yfinance ^IRX as fallback."""
    df = _fred_csv("DFF", "2021-01-01")
    if not df.empty:
        return df
    # Fallback: 13-week T-bill yield (^IRX) closely tracks Fed Funds Rate
    logger.warning("FRED DFF unavailable — using ^IRX (13W T-bill) as proxy")
    return _yf_close("^IRX", period="5y")


@st.cache_data(ttl=86400, show_spinner=False)
def get_treasury_yields() -> pd.DataFrame:
    """10Y and 2Y Treasury yields + spread (daily)."""
    y10 = _fred_csv("DGS10", "2021-01-01")
    y2 = _fred_csv("DGS2", "2021-01-01")
    if y10.empty or y2.empty:
        return pd.DataFrame()
    y10 = y10.rename(columns={"value": "10Y"})
    y2 = y2.rename(columns={"value": "2Y"})
    df = pd.merge(y10, y2, on="date", how="inner").sort_values("date")
    df["Spread"] = df["10Y"] - df["2Y"]
    return df.dropna().reset_index(drop=True)


# ═══════════════════════════════════════════════════════════
# 3. Inflation
# ═══════════════════════════════════════════════════════════

@st.cache_data(ttl=86400, show_spinner=False)
def get_cpi() -> pd.DataFrame:
    """CPI YoY % change (monthly). CPIAUCSL series."""
    df = _fred_csv("CPIAUCSL", "2019-01-01")  # need 2y prior for YoY
    if df.empty or len(df) < 13:
        return pd.DataFrame()
    df["YoY"] = df["value"].pct_change(12) * 100
    df = df[df["date"] >= "2021-01-01"].dropna(subset=["YoY"])
    return df[["date", "YoY"]].reset_index(drop=True)


@st.cache_data(ttl=86400, show_spinner=False)
def get_core_pce() -> pd.DataFrame:
    """Core PCE YoY % change (monthly). PCEPILFE series."""
    df = _fred_csv("PCEPILFE", "2019-01-01")
    if df.empty or len(df) < 13:
        return pd.DataFrame()
    df["YoY"] = df["value"].pct_change(12) * 100
    df = df[df["date"] >= "2021-01-01"].dropna(subset=["YoY"])
    return df[["date", "YoY"]].reset_index(drop=True)


# ═══════════════════════════════════════════════════════════
# 4. Dollar & Commodities
# ═══════════════════════════════════════════════════════════

@st.cache_data(ttl=3600, show_spinner=False)
def get_dxy() -> pd.DataFrame:
    """US Dollar Index (DXY)."""
    return _yf_close("DX-Y.NYB", period="4y")


@st.cache_data(ttl=3600, show_spinner=False)
def get_gold() -> pd.DataFrame:
    """Gold futures."""
    return _yf_close("GC=F", period="4y")


@st.cache_data(ttl=3600, show_spinner=False)
def get_oil() -> pd.DataFrame:
    """WTI Crude Oil futures."""
    return _yf_close("CL=F", period="4y")
