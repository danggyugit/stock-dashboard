"""Cache FRED macro time-series so the SPA Macro page can render the exact
same charts as the Streamlit `services/macro_service.py` uses.

Fetches ~14 FRED series via the public CSV endpoint (no API key needed).
Runs in ~30-60 seconds. Output saved to
`streamlit_app/data/cache/macro/*.json` — small (~500 KB total).

Schedule: run daily on the Mac/Windows PC after markets close, then git
commit + push. The Next.js app loads via GitHub raw URL (15-min ISR).
"""

from __future__ import annotations

import io
import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# We shell out to /usr/bin/curl because Python's HTTP stack (requests +
# urllib both) times out consistently against fred.stlouisfed.org even
# when curl completes in <1s. This is FRED-specific — the CSV graph
# endpoint doesn't play well with Python's TLS negotiation.
_CURL = "/usr/bin/curl"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("cache-macro")

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache" / "macro"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}

# All series used by streamlit_app/services/macro_service.py.
# key: friendly slug for JSON file name.
# id:  FRED series ID.
# freq: 'D'=daily, 'W'=weekly, 'M'=monthly (documented only, we serialize as-is).
SERIES: list[tuple[str, str, str]] = [
    # Liquidity
    ("walcl",       "WALCL",         "W"),   # Fed Balance Sheet Total Assets
    ("rrp",         "RRPONTSYD",     "D"),   # Overnight Reverse Repo
    ("tga",         "WTREGEN",       "W"),   # Treasury General Account
    ("reserves",    "WRESBAL",       "W"),   # Bank Reserves
    ("hy_oas",      "BAMLH0A0HYM2",  "D"),   # High Yield OAS Spread
    ("m1",          "M1SL",          "M"),   # M1 Money Supply
    ("m2",          "M2SL",          "M"),   # M2 Money Supply

    # Interest Rates — full curve for slope + spread analysis
    ("fed_funds",   "FEDFUNDS",      "M"),   # Effective Fed Funds
    ("dgs3mo",      "DGS3MO",        "D"),   # 3M Treasury
    ("dgs2",        "DGS2",          "D"),   # 2Y Treasury
    ("dgs5",        "DGS5",          "D"),   # 5Y Treasury
    ("dgs10",       "DGS10",         "D"),   # 10Y Treasury
    ("dgs30",       "DGS30",         "D"),   # 30Y Treasury

    # Inflation (YoY % computed by consumer of cache)
    ("cpi",         "CPIAUCSL",      "M"),   # Headline CPI (index)
    ("core_pce",    "PCEPILFE",      "M"),   # Core PCE (index)

    # Dollar & Commodities
    ("dxy",         "DTWEXBGS",      "D"),   # Trade-Weighted USD Index
    ("gold",        "GOLDPMGBD228NLBM", "D"), # LBMA Gold PM Fix
    ("wti",         "DCOILWTICO",    "D"),   # WTI Crude Oil
    ("copper",      "PCOPPUSDM",     "M"),   # Copper (Dr. Copper — 경기 선행)
    ("natgas",      "DHHNGSP",       "D"),   # Henry Hub Natural Gas
]

START = "2021-01-01"


def fetch_series(series_id: str) -> list[dict]:
    """Fetch a FRED series as list of {date, value} dicts via curl."""
    url = f"{FRED_CSV}?id={series_id}&cosd={START}"
    result = subprocess.run(
        [_CURL, "-sS", "--max-time", "30", url],
        capture_output=True,
        text=True,
        timeout=45,
    )
    if result.returncode != 0:
        raise RuntimeError(f"curl exit {result.returncode}: {result.stderr}")
    df = pd.read_csv(io.StringIO(result.stdout))
    # FRED CSV header: observation_date, {series_id} → normalize to date, value
    df.columns = ["date", "value"]
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"])
    return [
        {"date": str(row["date"]), "value": float(row["value"])}
        for _, row in df.iterrows()
    ]


def main() -> None:
    logger.info("Fetching %d FRED series into %s", len(SERIES), CACHE_DIR)
    manifest: dict = {
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "start": START,
        "series": {},
    }

    for slug, series_id, freq in SERIES:
        try:
            data = fetch_series(series_id)
            (CACHE_DIR / f"{slug}.json").write_text(
                json.dumps({"series_id": series_id, "freq": freq, "data": data},
                           ensure_ascii=False),
                encoding="utf-8",
            )
            manifest["series"][slug] = {
                "series_id": series_id,
                "freq": freq,
                "points": len(data),
                "latest": data[-1] if data else None,
            }
            logger.info("  %s (%s): %d points", slug, series_id, len(data))
        except Exception as e:
            logger.error("  %s (%s) FAILED: %s", slug, series_id, e)
            manifest["series"][slug] = {"series_id": series_id, "error": str(e)}

    (CACHE_DIR / "_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Done. Manifest saved.")


if __name__ == "__main__":
    main()
