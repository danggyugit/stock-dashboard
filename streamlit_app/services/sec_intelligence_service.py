"""SEC Intelligence — 13F whale tracker + large insider buy scanner.

Data source: SEC EDGAR public API (free, no key required).
Cache: data/cache/sec/ (JSON files, git-pushed by scheduled script).
"""

from __future__ import annotations

import difflib
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import pandas as pd
import requests
import streamlit as st

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "AIQuantLab research@aiquantlab.app",
    "Accept-Encoding": "gzip, deflate",
}
_CACHE_DIR = Path(__file__).parent.parent / "data" / "cache" / "sec"
_RATE_SLEEP = 0.12  # ~8 req/s (EDGAR limit: 10/s)

# ── 20 Whale managers ────────────────────────────────────────────────────────

WHALE_MANAGERS: list[dict] = [
    {"cik": "0001067983", "name": "Berkshire Hathaway",     "manager": "Warren Buffett",       "style": "Value"},
    {"cik": "0002026053", "name": "Pershing Square Holdco",  "manager": "Bill Ackman",           "style": "Activist"},
    {"cik": "0001649339", "name": "Scion Asset Mgmt",        "manager": "Michael Burry",         "style": "Contrarian"},
    {"cik": "0001656456", "name": "Appaloosa LP",            "manager": "David Tepper",          "style": "Event-Driven"},
    {"cik": "0001040273", "name": "Third Point",             "manager": "Dan Loeb",              "style": "Activist"},
    {"cik": "0001489933", "name": "DME Capital (Greenlight)","manager": "David Einhorn",         "style": "Value/Short"},
    {"cik": "0001536411", "name": "Duquesne Family Office",  "manager": "Stan Druckenmiller",    "style": "Macro"},
    {"cik": "0001061768", "name": "Baupost Group",           "manager": "Seth Klarman",          "style": "Value"},
    {"cik": "0001103804", "name": "Viking Global",           "manager": "Andreas Halvorsen",     "style": "L/S Equity"},
    {"cik": "0001135730", "name": "Coatue Mgmt",             "manager": "Philippe Laffont",      "style": "Tech Growth"},
    {"cik": "0001167483", "name": "Tiger Global",            "manager": "Chase Coleman",         "style": "Tech Growth"},
    {"cik": "0001603466", "name": "Point72",                 "manager": "Steve Cohen",           "style": "Multi-Strategy"},
    {"cik": "0001423053", "name": "Citadel Advisors",        "manager": "Ken Griffin",           "style": "Quant"},
    {"cik": "0001037389", "name": "Renaissance Technologies","manager": "Jim Simons",            "style": "Quant"},
    {"cik": "0001061165", "name": "Lone Pine Capital",       "manager": "Stephen Mandel",        "style": "Growth"},
    {"cik": "0000934639", "name": "Maverick Capital",        "manager": "Lee Ainslie",           "style": "L/S Equity"},
    {"cik": "0001418814", "name": "ValueAct Holdings",       "manager": "Jeffrey Ubben",         "style": "Activist"},
    {"cik": "0000949509", "name": "Oaktree Capital Mgmt",    "manager": "Howard Marks",          "style": "Credit/Value"},
    {"cik": "0001647251", "name": "TCI Fund Mgmt",           "manager": "Chris Hohn",            "style": "Activist"},
    {"cik": "0001358706", "name": "Abrams Capital",          "manager": "David Abrams",          "style": "Concentrated Value"},
]

WHALE_BY_CIK: dict[str, dict] = {m["cik"]: m for m in WHALE_MANAGERS}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get(url: str, timeout: int = 15) -> requests.Response:
    resp = requests.get(url, headers=_HEADERS, timeout=timeout)
    resp.raise_for_status()
    time.sleep(_RATE_SLEEP)
    return resp


def _cache_path(subdir: str, filename: str) -> Path:
    p = _CACHE_DIR / subdir
    p.mkdir(parents=True, exist_ok=True)
    return p / filename


def _load_json(path: Path) -> dict | list | None:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _save_json(path: Path, data: dict | list) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_metadata() -> dict:
    p = _cache_path(".", "_metadata.json")
    return _load_json(p) or {}


def _save_metadata(meta: dict) -> None:
    _save_json(_cache_path(".", "_metadata.json"), meta)


# ── Ticker / name mapping ─────────────────────────────────────────────────────

@st.cache_data(ttl=86400, show_spinner=False)
def _load_ticker_name_map() -> dict[str, str]:
    """Build {normalized_company_name: ticker} from SEC company tickers."""
    try:
        r = _get("https://www.sec.gov/files/company_tickers.json")
        data = r.json()
        result = {}
        for entry in data.values():
            name = entry.get("title", "").upper().strip()
            ticker = entry.get("ticker", "").upper().strip()
            if name and ticker:
                result[name] = ticker
                # also store short version (remove common suffixes)
                for sfx in [" INC", " CORP", " CO", " LTD", " LLC", " LP", " GROUP", " HOLDINGS", " CLASS A", " CLASS B", " COM"]:
                    if name.endswith(sfx):
                        result[name[: -len(sfx)].strip()] = ticker
        return result
    except Exception as e:
        logger.warning("Ticker name map load failed: %s", e)
        return {}


def _match_ticker(company_name: str, name_map: dict[str, str]) -> str | None:
    """Fuzzy-match a 13F company name to a ticker symbol."""
    key = company_name.upper().strip()
    # exact match
    if key in name_map:
        return name_map[key]
    # strip common suffixes
    for sfx in [" INC", " CORP", " CO", " LTD", " LLC", " LP", " GROUP", " HOLDINGS", " CLASS A", " CLASS B", " COM"]:
        k2 = key
        if k2.endswith(sfx):
            k2 = k2[: -len(sfx)].strip()
            if k2 in name_map:
                return name_map[k2]
    # fuzzy match (top match with ratio > 0.85)
    candidates = list(name_map.keys())
    matches = difflib.get_close_matches(key, candidates, n=1, cutoff=0.85)
    if matches:
        return name_map[matches[0]]
    return None


# ── 13F filing fetcher ────────────────────────────────────────────────────────

def _fetch_submissions(cik: str) -> dict:
    """Fetch EDGAR submissions JSON for a CIK."""
    padded = cik.lstrip("0").zfill(10)
    return _get(f"https://data.sec.gov/submissions/CIK{padded}.json").json()


def _get_13f_filings(cik: str) -> list[dict]:
    """Return list of 13F-HR filings [{period, accession_no, filed_date}, ...]."""
    data = _fetch_submissions(cik)
    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    periods = recent.get("reportDate", [])
    accessions = recent.get("accessionNumber", [])

    results = []
    for form, filed, period, acc in zip(forms, dates, periods, accessions):
        if form == "13F-HR":
            results.append({
                "period": period,
                "filed_date": filed,
                "accession_no": acc,
            })
    # Also check older filings if available
    for page_key in ("files",):
        for file_entry in data.get("filings", {}).get(page_key, []):
            pass  # older filings via separate pages if needed
    return sorted(results, key=lambda x: x["period"], reverse=True)


def _fetch_info_table_xml(cik: str, accession_no: str) -> str | None:
    """Fetch the INFORMATION TABLE XML from a 13F filing."""
    cik_int = int(cik.lstrip("0") or "0")
    acc_clean = accession_no.replace("-", "")

    # Fetch filing index JSON — the directory listing lives at .../{acc}/index.json
    # (NOT "{acc}-index.json", which 404s)
    index_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_clean}/index.json"
    try:
        idx = _get(index_url).json()
    except Exception as e:
        logger.warning("Filing index fetch failed %s: %s", accession_no, e)
        return None

    # The info table is a separate XML (often an arbitrary name like 56757.xml
    # or infotable.xml). primary_doc.xml is the COVER PAGE — it contains no
    # holdings, so it must only ever be a last resort.
    items = idx.get("directory", {}).get("item", [])
    xml_names = [i.get("name", "") for i in items if i.get("name", "").lower().endswith(".xml")]

    info_table_file = None
    # 1) explicit info-table names
    for name in xml_names:
        if "infotable" in name.lower() or "informationtable" in name.lower():
            info_table_file = name
            break
    # 2) any XML that is NOT the cover page
    if not info_table_file:
        for name in xml_names:
            if name.lower() != "primary_doc.xml":
                info_table_file = name
                break
    # 3) last resort
    if not info_table_file and xml_names:
        info_table_file = xml_names[0]

    if not info_table_file:
        logger.warning("No info table XML found in %s", accession_no)
        return None

    xml_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_clean}/{info_table_file}"
    try:
        return _get(xml_url).text
    except Exception as e:
        logger.warning("Info table XML fetch failed %s: %s", xml_url, e)
        return None


def _parse_13f_xml(xml_text: str) -> list[dict]:
    """Parse 13F informationTable XML into list of holding dicts."""
    try:
        root = ET.fromstring(xml_text.encode("utf-8"))
    except ET.ParseError as e:
        logger.warning("13F XML parse error: %s", e)
        return []

    holdings = []
    # Handle both namespaced and non-namespaced XML
    for info in root.iter():
        if not info.tag.endswith("infoTable"):
            continue

        def _t(tag: str) -> str:
            for child in info:
                if child.tag.endswith(tag):
                    return (child.text or "").strip()
            return ""

        def _nested(parent_tag: str, child_tag: str) -> str:
            for child in info:
                if child.tag.endswith(parent_tag):
                    for gc in child:
                        if gc.tag.endswith(child_tag):
                            return (gc.text or "").strip()
            return ""

        name = _t("nameOfIssuer")
        cusip = _t("cusip")
        value_str = _t("value")
        shares_str = _nested("shrsOrPrnAmt", "sshPrnamt")
        shr_type = _nested("shrsOrPrnAmt", "sshPrnamtType")

        try:
            value_raw = int(float(value_str)) if value_str else 0
        except ValueError:
            value_raw = 0
        try:
            shares = int(float(shares_str)) if shares_str else 0
        except ValueError:
            shares = 0

        # SEC rule change (2023-01): 13F values are reported in WHOLE DOLLARS
        # (previously thousands). We only fetch current filings, so normalize
        # dollars → thousands to keep the value_k semantics used downstream.
        value_k = value_raw // 1000

        if name and (value_k > 0 or shares > 0):
            holdings.append({
                "company": name,
                "cusip": cusip,
                "shares": shares,
                "value_k": value_k,      # value in thousands USD
                "shr_type": shr_type,    # SH or PRN
            })

    return holdings


def _enrich_with_tickers(holdings: list[dict]) -> list[dict]:
    """Add ticker field to holdings via name matching."""
    name_map = _load_ticker_name_map()
    for h in holdings:
        h["ticker"] = _match_ticker(h["company"], name_map) or ""
    return holdings


def _compute_portfolio_pct(holdings: list[dict]) -> list[dict]:
    """Add pct_port field (% of total portfolio value)."""
    total = sum(h["value_k"] for h in holdings)
    for h in holdings:
        h["pct_port"] = round(h["value_k"] / total * 100, 2) if total else 0.0
        h["value_usd"] = h["value_k"] * 1000
    return holdings


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_and_cache_holdings(cik: str, force: bool = False) -> dict | None:
    """Fetch latest 13F for a manager and cache to JSON.

    Returns dict with keys: cik, manager, period, filed_date, holdings, fetched_at.
    """
    meta = _load_metadata()
    manager_info = WHALE_BY_CIK.get(cik, {})

    filings = _get_13f_filings(cik)
    if not filings:
        logger.warning("No 13F filings found for CIK %s", cik)
        return None

    latest = filings[0]
    period = latest["period"]
    accession = latest["accession_no"]

    cache_file = _cache_path("13f", f"{cik}_{period.replace('-', '')}.json")

    # Return cached if available and not forced
    if cache_file.exists() and not force:
        cached = _load_json(cache_file)
        if cached:
            return cached

    xml_text = _fetch_info_table_xml(cik, accession)
    if not xml_text:
        return None

    raw = _parse_13f_xml(xml_text)
    if not raw:
        logger.warning("No holdings parsed for CIK %s period %s", cik, period)
        return None

    enriched = _enrich_with_tickers(raw)
    enriched = _compute_portfolio_pct(enriched)
    enriched.sort(key=lambda x: x["value_k"], reverse=True)

    result = {
        "cik": cik,
        "name": manager_info.get("name", ""),
        "manager": manager_info.get("manager", ""),
        "style": manager_info.get("style", ""),
        "period": period,
        "filed_date": latest["filed_date"],
        "holdings": enriched,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_json(cache_file, result)

    # Update metadata
    meta.setdefault("13f", {})[cik] = {
        "latest_period": period,
        "filed_date": latest["filed_date"],
        "fetched_at": result["fetched_at"],
        "accession_no": accession,
    }
    _save_metadata(meta)
    return result


def load_cached_holdings(cik: str) -> dict | None:
    """Load latest cached 13F holdings for a manager (no network call)."""
    meta = _load_metadata()
    period = meta.get("13f", {}).get(cik, {}).get("latest_period")
    if not period:
        # Try scanning cache dir for any file matching this CIK
        pattern = list(_CACHE_DIR.glob(f"13f/{cik}_*.json"))
        if not pattern:
            return None
        period_file = sorted(pattern)[-1]
        return _load_json(period_file)

    cache_file = _CACHE_DIR / "13f" / f"{cik}_{period.replace('-', '')}.json"
    return _load_json(cache_file)


def load_prev_cached_holdings(cik: str) -> dict | None:
    """Load second-most-recent cached 13F holdings (for QoQ diff)."""
    pattern = sorted(_CACHE_DIR.glob(f"13f/{cik}_*.json"))
    if len(pattern) < 2:
        return None
    return _load_json(pattern[-2])


def compute_holdings_diff(curr: dict, prev: dict) -> dict:
    """Compute QoQ changes between two periods' holdings.

    Returns dict with keys: new, added, reduced, sold (each a list of holdings).
    """
    curr_map = {h["cusip"] or h["company"]: h for h in curr.get("holdings", [])}
    prev_map = {h["cusip"] or h["company"]: h for h in prev.get("holdings", [])}

    new_pos, added, reduced, sold = [], [], [], []

    for key, h in curr_map.items():
        if key not in prev_map:
            new_pos.append({**h, "change_type": "new"})
        else:
            p = prev_map[key]
            if h["shares"] > p["shares"]:
                pct = (h["shares"] - p["shares"]) / p["shares"] * 100 if p["shares"] else 0
                added.append({**h, "shares_prev": p["shares"], "pct_change": round(pct, 1), "change_type": "added"})
            elif h["shares"] < p["shares"]:
                pct = (p["shares"] - h["shares"]) / p["shares"] * 100 if p["shares"] else 0
                reduced.append({**h, "shares_prev": p["shares"], "pct_change": round(-pct, 1), "change_type": "reduced"})

    for key, h in prev_map.items():
        if key not in curr_map:
            sold.append({**h, "change_type": "sold"})

    # Sort each group by value descending
    for lst in (new_pos, added, reduced, sold):
        lst.sort(key=lambda x: x.get("value_k", 0), reverse=True)

    return {"new": new_pos, "added": added, "reduced": reduced, "sold": sold}


def get_consensus_picks(min_managers: int = 3) -> pd.DataFrame:
    """Stocks held by at least min_managers whales in their latest 13F.

    Returns DataFrame sorted by manager_count desc.
    """
    ticker_info: dict[str, dict] = {}

    for m in WHALE_MANAGERS:
        cached = load_cached_holdings(m["cik"])
        if not cached:
            continue
        for h in cached.get("holdings", []):
            ticker = h.get("ticker") or h.get("company", "")
            if not ticker:
                continue
            if ticker not in ticker_info:
                ticker_info[ticker] = {
                    "ticker": ticker,
                    "company": h["company"],
                    "manager_count": 0,
                    "managers": [],
                    "total_value_k": 0,
                }
            ticker_info[ticker]["manager_count"] += 1
            ticker_info[ticker]["managers"].append(m["manager"])
            ticker_info[ticker]["total_value_k"] += h.get("value_k", 0)

    rows = [v for v in ticker_info.values() if v["manager_count"] >= min_managers]
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["managers"] = df["managers"].apply(lambda x: ", ".join(x))
    df["total_value_M"] = (df["total_value_k"] / 1000).round(1)
    df = df.drop(columns=["total_value_k"])
    return df.sort_values("manager_count", ascending=False).reset_index(drop=True)


# ── Insider scan ──────────────────────────────────────────────────────────────

def _fetch_recent_form4_bulk(days: int = 7) -> list[dict]:
    """Fetch all Form 4 filings from past N days via EDGAR EFTS search."""
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=days)
    start_str = start_dt.strftime("%Y-%m-%d")
    end_str = end_dt.strftime("%Y-%m-%d")

    url = (
        "https://efts.sec.gov/LATEST/search-index"
        f"?q=&forms=4&dateRange=custom&startdt={start_str}&enddt={end_str}&hits.hits._source=period_of_report,entity_name,file_date,accession_no,period_of_report"
    )
    try:
        resp = _get(url)
        hits = resp.json().get("hits", {}).get("hits", [])
        return [h.get("_source", {}) for h in hits]
    except Exception as e:
        logger.warning("EFTS Form 4 search failed: %s", e)
        return []


def scan_large_insider_buys(
    tickers: list[str],
    days: int = 7,
    min_value_usd: int = 50_000,
) -> pd.DataFrame:
    """Scan Form 4 filings for given tickers and return large buy transactions.

    Uses the existing insider_service.get_insider_trades() per ticker.
    """
    from services.insider_service import get_insider_trades, _get_cik  # noqa

    results = []
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    for ticker in tickers:
        try:
            df = get_insider_trades(ticker, days=days)
            if df.empty:
                continue
            buys = df[
                (df["Type"] == "Buy")
                & (df["Value ($)"].notna())
                & (df["Value ($)"] >= min_value_usd)
                & (df["Date"] >= cutoff)
            ].copy()
            if buys.empty:
                continue
            buys.insert(0, "Ticker", ticker)
            results.append(buys)
        except Exception as e:
            logger.debug("Insider scan failed for %s: %s", ticker, e)

    if not results:
        return pd.DataFrame()

    combined = pd.concat(results, ignore_index=True)
    return combined.sort_values("Value ($)", ascending=False).reset_index(drop=True)


def load_cached_insider_scan() -> list[dict]:
    """Load pre-cached insider scan results (populated by scheduled script)."""
    p = _CACHE_DIR / "insider_scan.json"
    data = _load_json(p)
    return data if isinstance(data, list) else []


def save_insider_scan(rows: list[dict]) -> None:
    """Save insider scan results to cache."""
    p = _cache_path(".", "insider_scan.json")
    _save_json(p, rows)


# ── SEC filing list ───────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def get_recent_filings(ticker: str, form_types: tuple[str, ...] = ("8-K", "10-K", "10-Q"), limit: int = 20) -> pd.DataFrame:
    """Fetch recent SEC filings for a ticker.

    Returns DataFrame with columns: form_type, filed_date, description, url.
    """
    from services.insider_service import _get_cik, _HEADERS  # reuse CIK lookup

    cik = _get_cik(ticker)
    if not cik:
        return pd.DataFrame()

    try:
        resp = requests.get(
            f"https://data.sec.gov/submissions/CIK{cik}.json",
            headers=_HEADERS, timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning("Submissions fetch failed for %s: %s", ticker, e)
        return pd.DataFrame()

    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    descriptions = recent.get("primaryDocDescription", [recent.get("primaryDocument", [""])] * len(forms))

    cik_int = int(cik.lstrip("0") or "0")
    rows = []
    for form, date_str, acc, desc in zip(forms, dates, accessions, descriptions):
        if form not in form_types:
            continue
        acc_clean = acc.replace("-", "")
        url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_clean}/{acc}-index.htm"
        rows.append({
            "Form": form,
            "Filed": date_str,
            "Description": desc or form,
            "Accession": acc,
            "URL": url,
        })
        if len(rows) >= limit:
            break

    return pd.DataFrame(rows) if rows else pd.DataFrame()


def get_filing_text(ticker: str, accession_no: str) -> str | None:
    """Fetch primary document text for a filing (for AI summary)."""
    from services.insider_service import _get_cik  # noqa

    cik = _get_cik(ticker)
    if not cik:
        return None

    cik_int = int(cik.lstrip("0") or "0")
    acc_clean = accession_no.replace("-", "")
    index_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_clean}/index.json"

    try:
        idx = _get(index_url).json()
        items = idx.get("directory", {}).get("item", [])
    except Exception as e:
        logger.warning("Filing index failed %s: %s", accession_no, e)
        return None

    # Find primary HTML/text document
    primary = None
    for item in items:
        name = item.get("name", "")
        doc_type = item.get("type", "")
        if doc_type in ("8-K", "10-K", "10-Q") or (name.endswith(".htm") and "ex" not in name.lower()):
            primary = name
            break

    if not primary:
        return None

    doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_clean}/{primary}"
    try:
        resp = _get(doc_url)
        # Strip HTML tags crudely
        text = resp.text
        import re
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:8000]  # cap for LLM context
    except Exception as e:
        logger.warning("Filing text fetch failed: %s", e)
        return None


# ── Utility ───────────────────────────────────────────────────────────────────

def get_metadata_summary() -> dict:
    """Return metadata dict for display (last fetch times per manager)."""
    return _load_metadata()


def format_value(value_k: int) -> str:
    """Format value in thousands to human-readable string."""
    if value_k >= 1_000_000:
        return f"${value_k / 1_000_000:.2f}B"
    if value_k >= 1_000:
        return f"${value_k / 1_000:.1f}M"
    return f"${value_k}K"
