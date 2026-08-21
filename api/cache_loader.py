"""Load pre-cached backtest data (produced by streamlit_app/scripts/
cache_backtest_data.py on the Windows PC) so the FastAPI backtest
service can serve on-demand backtests without ever calling yfinance
directly — Yahoo blocks datacenter IPs.

Cache files (all under `streamlit_app/data/cache/backtest_data/`):
  - _manifest.json      : cached_at, date range, tickers count, file list
  - metadata.json       : full S&P 1500 metadata (ticker, sector, cap_tier)
  - prices.pkl.gz       : dict[ticker] = OHLCV DataFrame
  - fundamentals.pkl.gz : dict[ticker] = fund_info dict
  - pit.pkl.gz          : dict[ticker] = {income, balance, cashflow, dividends}
  - benchmarks.pkl.gz   : {"SPY": Series, "VIX": Series}
  - sp500_changes.pkl.gz: DataFrame with S&P membership history (or None)

All files are loaded lazily and cached in memory for the process lifetime
(module-level dict). Free-tier Render has 512MB RAM so we're careful with
what stays resident.
"""

from __future__ import annotations

import gzip
import json
import logging
import pickle
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = _REPO_ROOT / "streamlit_app" / "data" / "cache" / "backtest_data"

_data_cache: dict[str, Any] = {}


class CacheMissing(RuntimeError):
    """Raised when required cache file is not on disk.

    Usually means the Windows scheduler hasn't run yet, or the files
    weren't pushed to git.
    """


def _load(name: str, kind: str = "pickle") -> Any:
    """Load a cache file with in-memory caching. `kind` is 'pickle' or 'json'."""
    if name in _data_cache:
        return _data_cache[name]

    path = CACHE_DIR / name
    if not path.exists():
        raise CacheMissing(
            f"Cache file missing: {path.relative_to(_REPO_ROOT)}. "
            "Run `python streamlit_app/scripts/cache_backtest_data.py` "
            "on the Windows PC and push to git."
        )

    if kind == "pickle":
        with gzip.open(path, "rb") as f:
            data = pickle.load(f)
    elif kind == "json":
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        raise ValueError(f"Unknown kind: {kind!r}")

    _data_cache[name] = data
    logger.info("Loaded cache: %s", name)
    return data


# ── Public accessors ────────────────────────────────────────────


def load_manifest() -> dict:
    return _load("_manifest.json", kind="json")


def load_metadata() -> pd.DataFrame:
    """Full S&P 1500 metadata as DataFrame."""
    records = _load("metadata.json", kind="json")
    return pd.DataFrame(records)


def load_all_prices() -> dict[str, pd.DataFrame]:
    """dict[ticker] = OHLCV DataFrame."""
    return _load("prices.pkl.gz")


def load_fundamentals() -> dict[str, dict]:
    return _load("fundamentals.pkl.gz")


def load_pit() -> dict[str, dict]:
    return _load("pit.pkl.gz")


def load_benchmarks() -> dict[str, pd.Series]:
    """{'SPY': Series, 'VIX': Series} — daily closes."""
    return _load("benchmarks.pkl.gz")


def load_sp500_changes():
    """DataFrame with S&P 500 membership add/remove history, or None."""
    return _load("sp500_changes.pkl.gz")


def filter_universe(cfg: dict) -> list[str]:
    """Ticker list matching cfg['sectors'] and cfg['cap_tiers']. Only returns
    tickers that also have price data cached."""
    meta = load_metadata()
    df = meta[meta["cap_tier"].isin(cfg["cap_tiers"])]
    df = df[df["sector"].isin(cfg["sectors"])]
    candidates = df["ticker"].tolist()

    prices = load_all_prices()
    return [t for t in candidates if t in prices]


def build_sector_map() -> dict[str, str]:
    """dict[ticker] = sector — used by backtest for sector-neutral logic."""
    meta = load_metadata()
    return dict(zip(meta["ticker"], meta["sector"]))
