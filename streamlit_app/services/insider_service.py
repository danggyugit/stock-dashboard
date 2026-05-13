"""Insider trading data from SEC EDGAR Form 4 filings."""

import logging
import time
from datetime import datetime, timedelta
from xml.etree import ElementTree as ET

import pandas as pd
import requests
import streamlit as st

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "AIQuantLab research@aiquantlab.app",
    "Accept-Encoding": "gzip, deflate",
}

_TXN_TYPE = {
    "P": "Buy", "S": "Sell", "A": "Award",
    "D": "Dispose", "G": "Gift", "F": "Tax Withhold",
    "M": "Option Exercise", "J": "Other",
}


@st.cache_data(ttl=86400, show_spinner=False)
def _load_cik_map() -> dict[str, str]:
    """Load SEC ticker → CIK mapping (cached 24h)."""
    try:
        r = requests.get(
            "https://www.sec.gov/files/company_tickers.json",
            headers=_HEADERS, timeout=15,
        )
        r.raise_for_status()
        return {v["ticker"].upper(): str(v["cik_str"]).zfill(10) for v in r.json().values()}
    except Exception as e:
        logger.warning("CIK map load failed: %s", e)
        return {}


def _get_cik(ticker: str) -> str | None:
    return _load_cik_map().get(ticker.upper())


def _parse_form4(xml_text: str, filing_date: str) -> list[dict]:
    """Parse Form 4 XML and return non-derivative transactions."""
    results = []
    try:
        root = ET.fromstring(xml_text)
        reporter = (root.findtext(".//rptOwnerName") or "Unknown").strip()
        title = (root.findtext(".//officerTitle") or "").strip()
        is_director = root.findtext(".//isDirector", "0") == "1"
        is_officer = root.findtext(".//isOfficer", "0") == "1"
        role = title if title else ("Director" if is_director else ("Officer" if is_officer else "Insider"))

        for txn in root.findall(".//nonDerivativeTransaction"):
            code_el = txn.find(".//transactionCode")
            code = (code_el.text or "").strip() if code_el is not None else ""
            shares_el = txn.find(".//transactionShares/value")
            price_el = txn.find(".//transactionPricePerShare/value")

            try:
                shares = float(shares_el.text) if shares_el is not None and shares_el.text else None
            except ValueError:
                shares = None
            try:
                price = float(price_el.text) if price_el is not None and price_el.text else None
            except ValueError:
                price = None

            results.append({
                "Date": filing_date,
                "Insider": reporter,
                "Role": role,
                "Type": _TXN_TYPE.get(code, code),
                "Shares": shares,
                "Price": price,
                "Value ($)": round(shares * price) if shares and price else None,
            })
    except ET.ParseError:
        pass
    except Exception as e:
        logger.debug("Form 4 parse error: %s", e)
    return results


@st.cache_data(ttl=3600 * 4, show_spinner=False)
def get_insider_trades(ticker: str, days: int = 180) -> pd.DataFrame:
    """Return recent insider trades for a ticker from SEC EDGAR Form 4.

    Args:
        ticker: Stock ticker symbol.
        days: Look-back window in calendar days.

    Returns:
        DataFrame with columns Date, Insider, Role, Type, Shares, Price, Value ($).
    """
    cik = _get_cik(ticker)
    if not cik:
        logger.warning("CIK not found for %s", ticker)
        return pd.DataFrame()

    try:
        resp = requests.get(
            f"https://data.sec.gov/submissions/CIK{cik}.json",
            headers=_HEADERS, timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning("EDGAR submissions fetch failed for %s: %s", ticker, e)
        return pd.DataFrame()

    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])

    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    cik_int = int(cik)
    transactions: list[dict] = []
    fetched = 0

    for form, date_str, acc, doc in zip(forms, dates, accessions, primary_docs):
        if form != "4":
            continue
        if date_str < cutoff:
            break  # newest-first order
        if fetched >= 40:
            break  # cap to avoid long load times

        acc_clean = acc.replace("-", "")
        xml_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_clean}/{doc}"
        try:
            xr = requests.get(xml_url, headers=_HEADERS, timeout=10)
            txns = _parse_form4(xr.text, date_str)
            transactions.extend(txns)
            fetched += 1
            time.sleep(0.05)
        except Exception as e:
            logger.debug("Form 4 XML fetch failed %s: %s", acc, e)

    if not transactions:
        return pd.DataFrame()

    df = pd.DataFrame(transactions)
    df = df[df["Type"].isin(["Buy", "Sell", "Award", "Option Exercise"])].copy()
    return df.sort_values("Date", ascending=False).reset_index(drop=True)
