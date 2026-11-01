"""Point-in-time fundamentals from SEC EDGAR XBRL company facts.

Why: yfinance statements reach back only ~4-5 quarters / 4 years and carry
no filing dates, so the backtests had to *assume* when each report became
public (45/75/90-day lags) and fundamentals strategies could not start
before 2023. EDGAR's companyfacts API has every XBRL fact a company ever
filed, each with the `filed` date of the form it came from, back to ~2009.

For each ticker we pull the facts, keep the FIRST filing of every period
(the number investors actually saw; restatements are ignored on purpose),
rebuild quarterly values where companies only report year-to-date figures
(cash-flow statements especially), derive Q4 from the 10-K, and emit the
same statement frames the engines already consume from yfinance — plus a
`filed` map so they can use real availability dates instead of lags.

Storage (under the backtest_data cache dir):
  sec/facts/<TICKER>.pkl.gz   compact per-ticker series (period → value, filed)
  sec/_state.json             cik, fetched_at, last_filed per ticker
  sec/company_tickers.json    SEC ticker → CIK map (refreshed weekly)

EDGAR asks for a descriptive User-Agent and ≤10 requests/second.
"""

from __future__ import annotations

import gzip
import json
import logging
import pickle
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

logger = logging.getLogger(__name__)

# EDGAR rejects user agents containing URLs/parentheses (403); keep it to
# "name email" as their fair-access policy shows.
SEC_UA = "aiquantlab research sksk28y@gmail.com"
_HEADERS = {"User-Agent": SEC_UA, "Accept-Encoding": "gzip, deflate"}
_MIN_INTERVAL = 0.12          # seconds between requests (≤10/s)
_FORMS = {"10-Q", "10-K", "10-QT", "10-KT"}
_last_call = 0.0

# label → (kind, concepts in priority order). kind: "dur" (period) | "inst" (point)
CONCEPTS: dict[str, tuple[str, list[str]]] = {
    "Total Revenue": ("dur", [
        "Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet",
        "SalesRevenueGoodsNet", "RevenuesNetOfInterestExpense",
        "InterestAndDividendIncomeOperating",
    ]),
    "Gross Profit": ("dur", ["GrossProfit"]),
    "Operating Income": ("dur", ["OperatingIncomeLoss"]),
    "Net Income": ("dur", [
        "NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic",
    ]),
    "Interest Expense": ("dur", ["InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt"]),
    "Basic EPS": ("dur", ["EarningsPerShareBasic"]),
    "Depreciation": ("dur", [
        "DepreciationDepletionAndAmortization", "DepreciationAndAmortization",
        "DepreciationAmortizationAndAccretionNet", "Depreciation",
    ]),
    "Operating Cash Flow": ("dur", [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ]),
    "Capital Expenditure": ("dur", [
        "PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets",
    ]),
    "Stockholders Equity": ("inst", [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ]),
    "Total Assets": ("inst", ["Assets"]),
    "Current Assets": ("inst", ["AssetsCurrent"]),
    "Current Liabilities": ("inst", ["LiabilitiesCurrent"]),
    "Cash And Cash Equivalents": ("inst", [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ]),
    "Long Term Debt": ("inst", [
        "LongTermDebtNoncurrent", "LongTermDebt", "LongTermDebtAndCapitalLeaseObligations",
    ]),
    "Short Term Debt": ("inst", ["DebtCurrent", "LongTermDebtCurrent", "ShortTermBorrowings"]),
    "Ordinary Shares Number": ("inst", ["CommonStockSharesOutstanding"]),
    # Fallback when the balance sheet carries no share count (banks often):
    # period-average shares from the income statement.
    "Weighted Shares": ("dur", [
        "WeightedAverageNumberOfSharesOutstandingBasic",
        "WeightedAverageNumberOfDilutedSharesOutstanding",
    ]),
}
_INCOME = ["Total Revenue", "Gross Profit", "Operating Income", "Net Income",
           "Interest Expense", "Basic EPS", "Depreciation"]
_BALANCE = ["Stockholders Equity", "Total Assets", "Current Assets", "Current Liabilities",
            "Cash And Cash Equivalents", "Long Term Debt", "Short Term Debt",
            "Ordinary Shares Number", "Weighted Shares"]
_CASHFLOW = ["Operating Cash Flow", "Capital Expenditure"]


# ── HTTP ─────────────────────────────────────────────────────────────


def _get_json(url: str) -> dict | None:
    global _last_call
    for attempt in range(3):
        wait = _MIN_INTERVAL - (time.time() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.time()
        try:
            r = requests.get(url, headers=_HEADERS, timeout=30)
        except Exception:
            time.sleep(1.5 * (attempt + 1))
            continue
        if r.status_code == 200:
            return r.json()
        if r.status_code == 404:
            return None
        if r.status_code in (403, 429, 503):
            time.sleep(5.0 * (attempt + 1))
            continue
        return None
    return None


def load_cik_map(cache_dir: Path, max_age_days: int = 7) -> dict[str, int]:
    """ticker → CIK from SEC's company_tickers.json (cached)."""
    sec_dir = cache_dir / "sec"
    sec_dir.mkdir(parents=True, exist_ok=True)
    path = sec_dir / "company_tickers.json"
    fresh = path.exists() and (time.time() - path.stat().st_mtime) < max_age_days * 86400
    if not fresh:
        data = _get_json("https://www.sec.gov/files/company_tickers.json")
        if data:
            path.write_text(json.dumps(data), encoding="utf-8")
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(v["ticker"]).upper().replace(".", "-"): int(v["cik_str"]) for v in data.values()}


# ── Parsing ──────────────────────────────────────────────────────────


def _days(a: str, b: str) -> int:
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def _kind(days: int) -> str | None:
    if 80 <= days <= 100:
        return "Q"
    if 170 <= days <= 195:
        return "H"
    if 255 <= days <= 290:
        return "N"
    if 350 <= days <= 380:
        return "Y"
    return None


def _first_filed(facts: list[dict]) -> dict[tuple, tuple[float, str]]:
    """{(start, end): (val, filed)} keeping the earliest filing per period."""
    out: dict[tuple, tuple[float, str]] = {}
    for f in facts:
        if f.get("form") not in _FORMS or f.get("val") is None:
            continue
        key = (f.get("start"), f["end"])
        prev = out.get(key)
        if prev is None or f["filed"] < prev[1]:
            out[key] = (float(f["val"]), f["filed"])
    return out


def _duration_series(facts: list[dict]) -> tuple[dict, dict]:
    """→ (quarterly {end: (val, filed)}, annual {end: (val, filed)}).

    Direct quarterly facts win; otherwise a quarter is the difference of two
    year-to-date facts with the same start (Q2 = H − Q1, Q3 = 9M − H,
    Q4 = FY − 9M). The derived quarter's filed date is that of the longer
    (later) YTD fact.
    """
    ff = _first_filed(facts)
    quarterly: dict[str, tuple[float, str]] = {}
    annual: dict[str, tuple[float, str]] = {}
    by_start: dict[str, dict[str, tuple[str, float, str]]] = {}   # start → kind → (end, val, filed)
    for (start, end), (val, filed) in ff.items():
        if not start:
            continue
        k = _kind(_days(start, end))
        if k is None:
            continue
        if k == "Q":
            quarterly[end] = (val, filed)
        if k == "Y":
            annual[end] = (val, filed)
        by_start.setdefault(start, {})[k] = (end, val, filed)
    order = ["Q", "H", "N", "Y"]
    for start, kinds in by_start.items():
        for i in range(1, len(order)):
            longer, shorter = kinds.get(order[i]), kinds.get(order[i - 1])
            if longer is None or shorter is None:
                continue
            end, val, filed = longer
            if end not in quarterly:
                quarterly[end] = (val - shorter[1], max(filed, shorter[2]))
    return quarterly, annual


def _instant_series(facts: list[dict]) -> dict[str, tuple[float, str]]:
    ff = _first_filed(facts)
    return {end: v for (start, end), v in ff.items() if not start}


def parse_companyfacts(doc: dict) -> dict:
    """companyfacts JSON → {"q": {label: {end: (val, filed)}},
                            "a": {label: {end: (val, filed)}}, "last_filed": str}"""
    gaap = (doc.get("facts") or {}).get("us-gaap") or {}
    dei = (doc.get("facts") or {}).get("dei") or {}
    q: dict[str, dict] = {}
    a: dict[str, dict] = {}
    last_filed = ""
    for label, (kind, concepts) in CONCEPTS.items():
        merged_q: dict[str, tuple[float, str]] = {}
        merged_a: dict[str, tuple[float, str]] = {}
        for concept in concepts:
            units = (gaap.get(concept) or {}).get("units") or {}
            facts: list[dict] = []
            for unit, vals in units.items():
                if unit in ("USD", "shares", "USD/shares"):
                    facts.extend(vals)
            if not facts:
                continue
            for f in facts:
                if f.get("filed", "") > last_filed:
                    last_filed = f["filed"]
            if kind == "dur":
                sq, sa = _duration_series(facts)
            else:
                sq, sa = _instant_series(facts), {}
            # Lower-priority concepts only fill periods the better one lacks.
            for end, v in sq.items():
                merged_q.setdefault(end, v)
            for end, v in sa.items():
                merged_a.setdefault(end, v)
        if label == "Ordinary Shares Number" and not merged_q:
            dei_units = (dei.get("EntityCommonStockSharesOutstanding") or {}).get("units") or {}
            facts = [f for vals in dei_units.values() for f in vals]
            merged_q = _instant_series(facts)
        if merged_q:
            q[label] = merged_q
        if merged_a:
            a[label] = merged_a
    return {"q": q, "a": a, "last_filed": last_filed}


# ── Storage / refresh ────────────────────────────────────────────────


def _facts_path(cache_dir: Path, ticker: str) -> Path:
    return cache_dir / "sec" / "facts" / f"{ticker}.pkl.gz"


def _load_state(cache_dir: Path) -> dict:
    p = cache_dir / "sec" / "_state.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(cache_dir: Path, state: dict) -> None:
    p = cache_dir / "sec" / "_state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=0), encoding="utf-8")


def fetch_ticker(ticker: str, cik: int, cache_dir: Path) -> dict | None:
    doc = _get_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json")
    if not doc:
        return None
    parsed = parse_companyfacts(doc)
    if not parsed["q"] and not parsed["a"]:
        return None
    path = _facts_path(cache_dir, ticker)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with gzip.open(tmp, "wb") as f:
        pickle.dump(parsed, f, protocol=pickle.HIGHEST_PROTOCOL)
    tmp.replace(path)
    return parsed


def refresh(tickers: list[str], cache_dir: Path, budget_min: int = 60,
            max_fetch: int = 3000) -> dict:
    """Fetch or refresh company facts for `tickers` within a time budget.

    A ticker is due when it has never been fetched, when its last known
    filing is ≥ 80 days old (the next 10-Q/10-K is probably out) and it
    was last checked ≥ 3 days ago, or when its stored facts are older than
    120 days regardless. Never-fetched tickers go first.
    """
    cik_map = load_cik_map(cache_dir)
    state = _load_state(cache_dir)
    today = date.today()
    due: list[tuple[int, str]] = []
    no_cik = 0
    for t in tickers:
        cik = cik_map.get(t)
        if cik is None:
            no_cik += 1
            continue
        st = state.get(t) or {}
        fetched = st.get("fetched_at")
        if not fetched or not _facts_path(cache_dir, t).exists():
            due.append((0, t))
            continue
        fetched_d = date.fromisoformat(fetched[:10])
        last_filed = st.get("last_filed") or "1900-01-01"
        stale_filing = (today - date.fromisoformat(last_filed)).days >= 80
        checked_ago = (today - fetched_d).days
        if (stale_filing and checked_ago >= 3) or checked_ago >= 120:
            due.append((1, t))
    due.sort()
    logger.info("SEC facts: %d tickers, %d due (%d never fetched), %d without CIK",
                len(tickers), len(due), sum(1 for p, _ in due if p == 0), no_cik)

    deadline = time.time() + budget_min * 60
    done = failed = 0
    for _, t in due[:max_fetch]:
        if time.time() > deadline:
            logger.warning("SEC facts: time budget reached after %d fetches", done)
            break
        parsed = fetch_ticker(t, cik_map[t], cache_dir)
        now = datetime.now(timezone.utc).isoformat()
        if parsed is None:
            failed += 1
            state[t] = {**(state.get(t) or {}), "cik": cik_map[t], "fetched_at": now,
                        "last_filed": (state.get(t) or {}).get("last_filed", "1900-01-01"),
                        "empty": True}
            continue
        done += 1
        state[t] = {"cik": cik_map[t], "fetched_at": now, "last_filed": parsed["last_filed"]}
        if done % 100 == 0:
            _save_state(cache_dir, state)
            logger.info("SEC facts: %d fetched...", done)
    _save_state(cache_dir, state)
    logger.info("SEC facts: %d fetched, %d empty/failed, %d still due",
                done, failed, max(0, len(due) - done - failed))
    return state


# ── Engine-shaped output ─────────────────────────────────────────────


def _frame(series_by_label: dict[str, dict], labels: list[str]) -> tuple[pd.DataFrame, dict]:
    """Statement frame (rows = labels, columns = period-end Timestamps,
    newest first) and {period → filed Timestamp} (latest filed among items)."""
    ends: set[str] = set()
    for label in labels:
        ends.update((series_by_label.get(label) or {}).keys())
    if not ends:
        return pd.DataFrame(), {}
    cols = sorted(ends, reverse=True)
    data = {}
    filed: dict[pd.Timestamp, pd.Timestamp] = {}
    for label in labels:
        s = series_by_label.get(label) or {}
        data[label] = [s[c][0] if c in s else np.nan for c in cols]
        for c, (_, f) in s.items():
            ts = pd.Timestamp(c)
            fts = pd.Timestamp(f)
            if ts not in filed or fts > filed[ts]:
                filed[ts] = fts
    df = pd.DataFrame(data, index=[pd.Timestamp(c) for c in cols]).T
    return df, filed


def _derive(df: pd.DataFrame, kind: str) -> pd.DataFrame:
    """Add the composite rows the engines read (EBIT, EBITDA, Total Debt, FCF…)."""
    if df.empty:
        return df
    def row(name):
        return df.loc[name] if name in df.index else pd.Series(np.nan, index=df.columns)
    if kind == "income":
        ebit = row("Operating Income")
        df.loc["EBIT"] = ebit
        df.loc["EBITDA"] = ebit + row("Depreciation").fillna(0).where(ebit.notna())
        df.loc["Interest Expense Non Operating"] = row("Interest Expense")
        df = df.drop(index=["Depreciation"], errors="ignore")
    elif kind == "balance":
        ltd, std = row("Long Term Debt"), row("Short Term Debt")
        df.loc["Total Debt"] = ltd.fillna(0) + std.fillna(0)
        df.loc["Total Debt"] = df.loc["Total Debt"].where(ltd.notna() | std.notna())
        df.loc["Long Term Debt And Capital Lease Obligation"] = ltd
        df.loc["Common Stock Equity"] = row("Stockholders Equity")
        df.loc["Total Equity Gross Minority Interest"] = row("Stockholders Equity")
        df.loc["Cash Cash Equivalents And Short Term Investments"] = row("Cash And Cash Equivalents")
        shares = row("Ordinary Shares Number").fillna(row("Weighted Shares"))
        df.loc["Ordinary Shares Number"] = shares
        df.loc["Share Issued"] = shares
        df = df.drop(index=["Short Term Debt", "Weighted Shares"], errors="ignore")
    elif kind == "cashflow":
        ocf, capex = row("Operating Cash Flow"), row("Capital Expenditure")
        # yfinance convention: capex negative, FCF = OCF + capex
        df.loc["Capital Expenditure"] = -capex.abs()
        df.loc["Free Cash Flow"] = ocf - capex.abs()
    return df


def build_pit_entry(parsed: dict) -> dict:
    """One ticker's engine-shaped PIT entry from parsed company facts."""
    q, a = parsed.get("q") or {}, parsed.get("a") or {}
    # Balance-sheet items are instants: they belong to both the quarterly
    # and the annual view (annual = the fiscal-year-end instants).
    inc_q, f1 = _frame(q, _INCOME)
    bal_q, f2 = _frame(q, _BALANCE)
    cf_q, f3 = _frame(q, _CASHFLOW)
    # Instants also appear at odd dates (acquisition balance sheets, cover
    # pages); keep only balance columns that sit on a reporting period end.
    if not bal_q.empty:
        period_ends = sorted(set(inc_q.columns) | set(cf_q.columns))
        keep = [c for c in bal_q.columns
                if any(abs((c - p).days) <= 10 for p in period_ends)]
        bal_q = bal_q[keep]
        f2 = {k: v for k, v in f2.items() if k in set(keep)}
    inc_a, f4 = _frame(a, _INCOME)
    cf_a, f5 = _frame(a, _CASHFLOW)
    annual_ends = set(inc_a.columns) | set(cf_a.columns)
    bal_a = bal_q[[c for c in bal_q.columns if c in annual_ends]] if not bal_q.empty else bal_q
    filed: dict = {}
    for m in (f1, f2, f3):
        for k, v in m.items():
            if k not in filed or v > filed[k]:
                filed[k] = v
    annual_filed: dict = {}
    for m in (f4, f5):
        for k, v in m.items():
            if k not in annual_filed or v > annual_filed[k]:
                annual_filed[k] = v
    for k in bal_a.columns if not bal_a.empty else []:
        if k in f2 and (k not in annual_filed or f2[k] > annual_filed[k]):
            annual_filed[k] = f2[k]
    return {
        "income": _derive(inc_q, "income"),
        "balance": _derive(bal_q, "balance"),
        "cashflow": _derive(cf_q, "cashflow"),
        "annual_income": _derive(inc_a, "income"),
        "annual_balance": _derive(bal_a.copy(), "balance"),
        "annual_cashflow": _derive(cf_a, "cashflow"),
        "filed": filed,
        "annual_filed": annual_filed,
        "source": "sec",
    }


def build_pit_map(tickers: list[str], cache_dir: Path) -> dict:
    """{ticker: pit entry} for every ticker with stored SEC facts."""
    out = {}
    for t in tickers:
        path = _facts_path(cache_dir, t)
        if not path.exists():
            continue
        try:
            with gzip.open(path, "rb") as f:
                parsed = pickle.load(f)
            entry = build_pit_entry(parsed)
            if not entry["income"].empty or not entry["annual_income"].empty:
                out[t] = entry
        except Exception as e:
            logger.warning("SEC facts: could not build %s (%s)", t, e)
    return out


_PER_SHARE_DIVIDE = ["Basic EPS"]
_SHARE_COUNT_MULTIPLY = ["Ordinary Shares Number", "Share Issued"]


def split_adjust(entry: dict, splits: pd.Series) -> None:
    """Put as-reported per-share figures on today's share basis, in place.

    `splits` is yfinance's 'Stock Splits' column (ratio on the ex-date, 0
    elsewhere). For a period ending at p the cumulative factor is the
    product of ratios dated after p: EPS is divided by it, share counts are
    multiplied by it, so EPS × shares (≈ net income) is unchanged and both
    match split-adjusted prices.
    """
    s = splits[splits > 0].dropna()
    if s.empty:
        return
    ratios = s.sort_index()

    def factor(period_end: pd.Timestamp) -> float:
        later = ratios[ratios.index > period_end]
        return float(later.prod()) if len(later) else 1.0

    for key in ("income", "annual_income", "balance", "annual_balance"):
        df = entry.get(key)
        if df is None or df.empty:
            continue
        factors = pd.Series({c: factor(pd.Timestamp(c)) for c in df.columns})
        for row in _PER_SHARE_DIVIDE:
            if row in df.index:
                df.loc[row] = df.loc[row] / factors.values
        for row in _SHARE_COUNT_MULTIPLY:
            if row in df.index:
                df.loc[row] = df.loc[row] * factors.values


def available_periods(df: pd.DataFrame, as_of: pd.Timestamp, lag_days: int,
                      filed: dict | None) -> list:
    """Columns of a statement frame that were public on `as_of`, newest first.

    With a `filed` map (SEC data) a period counts from its actual filing
    date; without one (yfinance data) from period end + the assumed lag.
    """
    fallback = as_of - pd.Timedelta(days=lag_days)
    cols = []
    for c in df.columns:
        try:
            ts = pd.Timestamp(c)
        except Exception:
            continue
        if filed and ts in filed:
            if filed[ts] <= as_of:
                cols.append(c)
        elif ts <= fallback:
            cols.append(c)
    return sorted(cols, key=pd.Timestamp, reverse=True)
