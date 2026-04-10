"""Macro / Economy data service — FRED CSV + yfinance."""

import logging
from datetime import timedelta

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

logger = logging.getLogger(__name__)

_FRED_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv"


def _fred_csv(series_id: str, start: str = "2021-01-01") -> pd.DataFrame:
    """Fetch a single FRED series as DataFrame with columns [date, value]."""
    try:
        url = f"{_FRED_BASE}?id={series_id}&cosd={start}"
        df = pd.read_csv(url)
        date_col = [c for c in df.columns if "date" in c.lower()][0]
        val_col = [c for c in df.columns if c != date_col][0]
        df = df.rename(columns={date_col: "date", val_col: "value"})
        df["date"] = pd.to_datetime(df["date"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        return df.dropna(subset=["value"]).reset_index(drop=True)
    except Exception as e:
        logger.warning(f"FRED fetch failed for {series_id}: {e}")
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
    """Effective Federal Funds Rate (daily). DFF series."""
    return _fred_csv("DFF", "2021-01-01")


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
