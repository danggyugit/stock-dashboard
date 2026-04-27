"""Build valuation cache JSON files for Streamlit Cloud fallback.

Fetches yfinance valuation data (core financials + analyst consensus +
individual analyst targets) for S&P 500 or S&P 1500 universe and writes
one JSON per ticker under `streamlit_app/data/cache/valuation/`.

The Streamlit Cloud app reads these via `cache_loader.get_cached_valuation()`
when yfinance is rate-limited.

Usage:
  python build_valuation_cache.py --universe sp500    # daily (~12 min, 500 tickers)
  python build_valuation_cache.py --universe sp1500   # weekly (~37 min, 1500 tickers)

Schedule (via .github/workflows/update_valuation_cache.yml):
  Daily 03:00 UTC (12:00 KST)  → sp500
  Sunday 04:00 UTC (13:00 KST) → sp1500
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("build-valuation-cache")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CACHE_DIR = REPO_ROOT / "streamlit_app" / "data" / "cache" / "valuation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

WIKI_SOURCES = {
    "sp500":  [("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", "Large Cap")],
    "sp1500": [
        ("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", "Large Cap"),
        ("https://en.wikipedia.org/wiki/List_of_S%26P_400_companies", "Mid Cap"),
        ("https://en.wikipedia.org/wiki/List_of_S%26P_600_companies", "Small Cap"),
    ],
}


def get_universe(universe: str) -> list[str]:
    """Fetch ticker list from Wikipedia."""
    sources = WIKI_SOURCES[universe]
    all_tickers = []
    headers = {"User-Agent": "Mozilla/5.0"}

    for url, _ in sources:
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            tables = pd.read_html(StringIO(resp.text))
            raw = tables[0]
            for c in raw.columns:
                if "symbol" in str(c).lower() or "ticker" in str(c).lower():
                    tickers = (
                        raw[c].astype(str)
                              .str.replace(".", "-", regex=False)
                              .str.strip()
                              .tolist()
                    )
                    all_tickers.extend(tickers)
                    break
        except Exception as e:
            logger.error("Failed to fetch %s: %s", url, e)

    # Dedupe while preserving order
    seen = set()
    unique = []
    for t in all_tickers:
        if t and t not in seen and t.replace("-", "").isalnum():
            seen.add(t)
            unique.append(t)
    return unique


def _safe(v):
    """Convert pandas/numpy values to JSON-safe Python primitives."""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, (int, float, str, bool)):
        return v
    try:
        return float(v)
    except (TypeError, ValueError):
        return str(v)


def fetch_core(ticker: str, info: dict) -> dict:
    """Build core valuation metrics from yfinance info."""
    core = {
        "ticker": ticker,
        "current_price": _safe(info.get("currentPrice") or info.get("regularMarketPrice")),
        "market_cap": _safe(info.get("marketCap")),
        "shares_out": _safe(info.get("sharesOutstanding")),
        "trailing_eps": _safe(info.get("trailingEps")),
        "forward_eps": _safe(info.get("forwardEps")),
        "trailing_pe": _safe(info.get("trailingPE")),
        "forward_pe": _safe(info.get("forwardPE")),
        "ttm_revenue": _safe(info.get("totalRevenue")),
        "revenue_growth_yoy": _safe(info.get("revenueGrowth")),
        "earnings_growth_yoy": _safe(info.get("earningsGrowth")),
        "gross_margin": _safe(info.get("grossMargins")),
        "operating_margin": _safe(info.get("operatingMargins")),
        "fifty_two_week_high": _safe(info.get("fiftyTwoWeekHigh")),
        "fifty_two_week_low": _safe(info.get("fiftyTwoWeekLow")),
    }
    fwd_ps = info.get("forwardPS") or info.get("priceToSalesTrailing12Months")
    if fwd_ps and core.get("market_cap"):
        try:
            core["forward_revenue_estimate"] = float(core["market_cap"]) / float(fwd_ps)
        except Exception:
            pass
    return core


def fetch_consensus(t: yf.Ticker, info: dict) -> dict:
    """Build analyst consensus dict."""
    result = {
        "target_mean":   _safe(info.get("targetMeanPrice")),
        "target_median": _safe(info.get("targetMedianPrice")),
        "target_high":   _safe(info.get("targetHighPrice")),
        "target_low":    _safe(info.get("targetLowPrice")),
        "n_analysts":    _safe(info.get("numberOfAnalystOpinions")),
        "rec_mean":      _safe(info.get("recommendationMean")),
        "rec_key":       info.get("recommendationKey"),
        "rec_strong_buy": 0, "rec_buy": 0, "rec_hold": 0,
        "rec_sell": 0, "rec_strong_sell": 0,
    }
    try:
        recs = t.recommendations
        if recs is not None and not recs.empty:
            latest = recs.iloc[0]
            result["rec_strong_buy"] = int(latest.get("strongBuy", 0) or 0)
            result["rec_buy"]        = int(latest.get("buy", 0) or 0)
            result["rec_hold"]       = int(latest.get("hold", 0) or 0)
            result["rec_sell"]       = int(latest.get("sell", 0) or 0)
            result["rec_strong_sell"] = int(latest.get("strongSell", 0) or 0)
    except Exception:
        pass
    return result


def fetch_individual_targets(t: yf.Ticker, limit: int = 20) -> list[dict]:
    """Build individual analyst firms list."""
    try:
        ud = t.upgrades_downgrades
    except Exception:
        return []
    if ud is None or ud.empty:
        return []

    df = ud.reset_index().copy()
    df.columns = [str(c).lower() for c in df.columns]
    date_col = next((c for c in df.columns if "date" in c), None)
    firm_col = next((c for c in df.columns if "firm" in c), None)
    target_col = next((c for c in df.columns if c == "currentpricetarget"), None)
    prior_col = next((c for c in df.columns if c == "priorpricetarget"), None)
    grade_col = next((c for c in df.columns if "tograde" in c), None)
    action_col = next((c for c in df.columns if "action" in c and "price" not in c), None)

    if not (date_col and firm_col and target_col):
        return []

    df = df[df[target_col].notna() & (df[target_col] > 0)]
    if df.empty:
        return []

    # Most recent per firm
    df = df.sort_values(date_col, ascending=False).drop_duplicates(subset=[firm_col]).head(limit)

    rows = []
    for _, r in df.iterrows():
        rows.append({
            "date":   str(r[date_col])[:10],
            "firm":   str(r[firm_col]),
            "target": _safe(r[target_col]),
            "prior_target": _safe(r[prior_col]) if prior_col else None,
            "action": str(r[action_col]) if action_col and pd.notna(r[action_col]) else None,
            "grade":  str(r[grade_col]) if grade_col and pd.notna(r[grade_col]) else None,
        })
    return rows


def build_one(ticker: str) -> dict | None:
    """Build cache entry for one ticker. Returns None on failure."""
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        if not info:
            return None
        core = fetch_core(ticker, info)
        if not core.get("current_price"):
            return None
        consensus = fetch_consensus(t, info)
        individual = fetch_individual_targets(t)
        return {
            "core": core,
            "consensus": consensus,
            "individual": individual,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.debug("Failed for %s: %s", ticker, e)
        return None


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--universe", choices=["sp500", "sp1500"], required=True)
    p.add_argument("--sleep", type=float, default=1.0,
                    help="Seconds between yfinance calls (rate-limit safety)")
    p.add_argument("--limit", type=int, default=0,
                    help="Limit ticker count (0 = all). For testing.")
    args = p.parse_args()

    logger.info("Fetching %s universe from Wikipedia...", args.universe)
    tickers = get_universe(args.universe)
    if args.limit:
        tickers = tickers[: args.limit]
    logger.info("Got %d tickers", len(tickers))

    saved = 0
    failed = []
    start = time.time()

    for i, ticker in enumerate(tickers, start=1):
        out = build_one(ticker)
        if out is None:
            failed.append(ticker)
        else:
            (CACHE_DIR / f"{ticker}.json").write_text(
                json.dumps(out, ensure_ascii=False), encoding="utf-8"
            )
            saved += 1
        if i % 50 == 0 or i == len(tickers):
            elapsed = time.time() - start
            rate = i / elapsed if elapsed > 0 else 0
            eta = (len(tickers) - i) / rate if rate > 0 else 0
            logger.info("[%d/%d] saved=%d failed=%d  rate=%.1f/s  ETA=%.0fs",
                        i, len(tickers), saved, len(failed), rate, eta)
        time.sleep(args.sleep)

    # Update meta.json
    meta_path = CACHE_DIR / "_meta.json"
    meta = {
        "universe": args.universe,
        "saved": saved,
        "failed": len(failed),
        "total": len(tickers),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    logger.info("Done. Saved %d, failed %d, total %d in %.0fs",
                saved, len(failed), len(tickers), time.time() - start)
    if failed[:10]:
        logger.info("First failed: %s", failed[:10])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
