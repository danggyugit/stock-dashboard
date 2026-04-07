"""GitHub-cached data loader.

Loads pre-fetched JSON cache files from GitHub raw URLs (or local fallback).
The cache is updated by .github/workflows/cache-update.yml on a cron schedule.

Priority order:
1. GitHub raw URL (deployed mode, fast CDN)
2. Local file (development mode)
3. None (caller should fall back to live fetch)
"""

import json
import logging
from pathlib import Path

import requests
import streamlit as st

logger = logging.getLogger(__name__)

# GitHub raw URL prefix — change if repo moves
_GITHUB_RAW_BASE = (
    "https://raw.githubusercontent.com/"
    "danggyugit/stock-dashboard/main/streamlit_app/data/cache/"
)

_LOCAL_CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"


@st.cache_data(ttl=900, show_spinner=False)
def load_cache_file(filename: str) -> dict | list | None:
    """Load a JSON cache file. Tries GitHub first, then local."""
    # 1. Try GitHub raw
    try:
        resp = requests.get(_GITHUB_RAW_BASE + filename, timeout=10)
        if resp.status_code == 200:
            logger.info("Loaded %s from GitHub cache", filename)
            return resp.json()
    except Exception as e:
        logger.debug("GitHub cache load failed for %s: %s", filename, e)

    # 2. Try local file
    local = _LOCAL_CACHE_DIR / filename
    if local.exists():
        try:
            data = json.loads(local.read_text(encoding="utf-8"))
            logger.info("Loaded %s from local cache", filename)
            return data
        except Exception as e:
            logger.warning("Local cache parse failed for %s: %s", filename, e)

    return None


def get_cached_heatmap() -> dict | None:
    """Return cached heatmap data dict, or None if unavailable."""
    return load_cache_file("heatmap.json")


def get_cached_stocks() -> list | None:
    """Return cached S&P 500 stock list."""
    return load_cache_file("stocks.json")


def get_cached_fundamentals() -> dict | None:
    """Return cached fundamentals dict."""
    return load_cache_file("fundamentals.json")


def get_cache_meta() -> dict | None:
    """Return cache update metadata."""
    return load_cache_file("meta.json")
