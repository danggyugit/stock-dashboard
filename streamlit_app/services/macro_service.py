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
    """Fetch a FRED series.

    Order depends on whether an API key is configured:
      key present → official API first (works from datacenter IPs — the
                    anonymous CSV endpoint blocks/hangs on cloud hosts like
                    Render), CSV as fallback
      no key      → CSV only (fine from residential IPs / Streamlit Cloud)
    """

    def _parse(text: str) -> pd.DataFrame:
        df = pd.read_csv(io.StringIO(text))
        date_col = [c for c in df.columns if "date" in c.lower()][0]
        val_col = [c for c in df.columns if c != date_col][0]
        df = df.rename(columns={date_col: "date", val_col: "value"})
        df["date"] = pd.to_datetime(df["date"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        return df.dropna(subset=["value"]).reset_index(drop=True)

    def _try_csv() -> pd.DataFrame:
        try:
            url = f"{_FRED_BASE}?id={series_id}&cosd={start}"
            resp = requests.get(url, headers=_FRED_HEADERS, timeout=12)
            resp.raise_for_status()
            return _parse(resp.text)
        except Exception as e:
            logger.warning("FRED CSV failed for %s: %s", series_id, e)
            return pd.DataFrame()

    def _try_api(api_key: str) -> pd.DataFrame:
        try:
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

    try:
        api_key = st.secrets.get("FRED_API_KEY", "") or ""
    except Exception:
        api_key = ""

    if api_key:
        df = _try_api(api_key)
        if not df.empty:
            return df
        return _try_csv()
    df = _try_csv()
    if not df.empty:
        return df
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


@st.cache_data(ttl=86400, show_spinner=False)
def get_rrp() -> pd.DataFrame:
    """Overnight Reverse Repo (daily, $Trillions). RRPONTSYD series.

    연준이 역레포로 흡수해 둔 유동성 — 감소하면 시중으로 방출.
    """
    df = _fred_csv("RRPONTSYD", "2021-01-01")
    if df.empty:
        return pd.DataFrame()
    df["value"] = df["value"] / 1000  # billions → trillions
    return df


@st.cache_data(ttl=86400, show_spinner=False)
def get_tga() -> pd.DataFrame:
    """Treasury General Account (weekly, $Trillions). WTREGEN series.

    재무부가 연준에 쌓아둔 현금 — 증가하면 시중 유동성 흡수.
    """
    df = _fred_csv("WTREGEN", "2021-01-01")
    if df.empty:
        return pd.DataFrame()
    df["value"] = df["value"] / 1_000_000  # millions → trillions
    return df


@st.cache_data(ttl=86400, show_spinner=False)
def get_bank_reserves() -> pd.DataFrame:
    """Bank reserve balances at the Fed (weekly, $Trillions). WRESBAL series."""
    df = _fred_csv("WRESBAL", "2021-01-01")
    if df.empty:
        return pd.DataFrame()
    df["value"] = df["value"] / 1_000_000  # millions → trillions
    return df


@st.cache_data(ttl=86400, show_spinner=False)
def get_hy_spread() -> pd.DataFrame:
    """ICE BofA US High-Yield OAS (daily, %). BAMLH0A0HYM2 series.

    자금경색·위험선호 온도계 — 급등하면 신용시장 스트레스.
    """
    return _fred_csv("BAMLH0A0HYM2", "2021-01-01")


@st.cache_data(ttl=86400, show_spinner=False)
def get_net_liquidity() -> pd.DataFrame:
    """Net Liquidity = Fed 총자산(WALCL) − 역레포(RRP) − 재무부계정(TGA).

    시장이 가장 주시하는 합성 유동성 지표 (S&P500과 높은 상관).
    주간(WALCL 기준일) 스파인에 RRP(일간)·TGA(주간)를 as-of 병합.

    Returns:
        DataFrame [date, net_liq, walcl, rrp, tga, spx] — $Trillions, spx는 지수.
    """
    walcl = get_fed_balance_sheet()
    rrp = get_rrp()
    tga = get_tga()
    if walcl.empty or rrp.empty or tga.empty:
        return pd.DataFrame()

    base = walcl.rename(columns={"value": "walcl"}).sort_values("date")
    rrp_s = rrp.rename(columns={"value": "rrp"}).sort_values("date")
    tga_s = tga.rename(columns={"value": "tga"}).sort_values("date")

    # CSV vs API paths can yield different datetime64 resolutions (s/us/ns);
    # merge_asof requires identical dtypes — normalize all to ns.
    for _df in (base, rrp_s, tga_s):
        _df["date"] = pd.to_datetime(_df["date"]).astype("datetime64[ns]")

    df = pd.merge_asof(base, rrp_s, on="date", direction="backward")
    df = pd.merge_asof(df, tga_s, on="date", direction="backward")
    df = df.dropna(subset=["walcl", "rrp", "tga"])
    df["net_liq"] = df["walcl"] - df["rrp"] - df["tga"]

    spx = _yf_close("^GSPC", period="5y")
    if not spx.empty:
        spx = spx.rename(columns={"value": "spx"}).sort_values("date")
        spx["date"] = pd.to_datetime(spx["date"]).dt.tz_localize(None)
        df["date"] = pd.to_datetime(df["date"])
        df = pd.merge_asof(df, spx, on="date", direction="backward")

    return df.reset_index(drop=True)


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
    """10Y and 2Y Treasury yields + spread. FRED primary, yfinance ^TNX/^IRX fallback."""
    y10 = _fred_csv("DGS10", "2021-01-01")
    y2 = _fred_csv("DGS2", "2021-01-01")
    if not y10.empty and not y2.empty:
        y10 = y10.rename(columns={"value": "10Y"})
        y2 = y2.rename(columns={"value": "2Y"})
        df = pd.merge(y10, y2, on="date", how="inner").sort_values("date")
        df["Spread"] = df["10Y"] - df["2Y"]
        return df.dropna().reset_index(drop=True)

    # Fallback: ^TNX (10Y) + ^IRX (3M short-rate proxy for 2Y)
    logger.warning("FRED DGS10/DGS2 unavailable — using ^TNX/^IRX as proxy")
    t10 = _yf_close("^TNX", period="5y")
    t_short = _yf_close("^IRX", period="5y")
    if t10.empty:
        return pd.DataFrame()
    t10 = t10.rename(columns={"value": "10Y"})
    if not t_short.empty:
        t_short = t_short.rename(columns={"value": "2Y"})
        df = pd.merge(t10, t_short, on="date", how="inner").sort_values("date")
        df["Spread"] = df["10Y"] - df["2Y"]
        return df.dropna().reset_index(drop=True)
    t10["2Y"] = np.nan
    t10["Spread"] = np.nan
    return t10.sort_values("date").reset_index(drop=True)


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
