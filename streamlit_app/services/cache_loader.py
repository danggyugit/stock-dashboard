"""GitHub-cached data loader.

Loads pre-fetched JSON cache files from GitHub raw URLs (or local fallback).
The cache is updated by .github/workflows/cache-update.yml on a cron schedule.

Priority order:
1. GitHub raw URL (deployed mode, fast CDN)
2. Local file (development mode)
3. Tmp stale cache (last successful load, even if expired)
"""

import json
import logging
import tempfile
import time
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
_TMP_CACHE_DIR = Path(tempfile.gettempdir()) / "stock_dashboard_cache"
_TMP_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _tmp_path(filename: str) -> Path:
    """안전한 tmp 파일 경로 반환 (/ → _ 치환)."""
    return _TMP_CACHE_DIR / filename.replace("/", "_")


def _save_tmp(filename: str, data: dict | list) -> None:
    try:
        _tmp_path(filename).write_text(
            json.dumps({"data": data, "saved_at": time.time()}, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as e:
        logger.debug("Tmp cache write failed for %s: %s", filename, e)


def _load_tmp(filename: str) -> tuple[dict | list | None, float | None]:
    """(data, age_hours) 반환. 파일 없으면 (None, None)."""
    p = _tmp_path(filename)
    if not p.exists():
        return None, None
    try:
        entry = json.loads(p.read_text(encoding="utf-8"))
        age_h = (time.time() - entry.get("saved_at", 0)) / 3600
        return entry.get("data"), round(age_h, 1)
    except Exception:
        return None, None


@st.cache_data(ttl=900, show_spinner=False)
def load_cache_file(filename: str) -> dict | list | None:
    """JSON 캐시 파일 로드. GitHub → 로컬 → tmp 스테일 캐시 순으로 시도."""
    # 1. GitHub raw
    try:
        resp = requests.get(_GITHUB_RAW_BASE + filename, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            _save_tmp(filename, data)
            logger.info("Loaded %s from GitHub cache", filename)
            return data
        logger.warning("GitHub cache HTTP %d for %s", resp.status_code, filename)
    except Exception as e:
        logger.warning("GitHub cache load failed for %s: %s", filename, e)

    # 2. 로컬 파일 (개발 환경)
    local = _LOCAL_CACHE_DIR / filename
    if local.exists():
        try:
            data = json.loads(local.read_text(encoding="utf-8"))
            logger.info("Loaded %s from local cache", filename)
            return data
        except Exception as e:
            logger.warning("Local cache parse failed for %s: %s", filename, e)

    # 3. Tmp 스테일 캐시 (마지막 성공 데이터)
    data, age_h = _load_tmp(filename)
    if data is not None:
        logger.warning("Using stale tmp cache for %s (%.1fh old)", filename, age_h)
        return data

    logger.error("All cache sources failed for %s", filename)
    return None


def get_cache_age(filename: str) -> float | None:
    """tmp 캐시의 경과 시간(시간 단위) 반환. 없으면 None."""
    _, age_h = _load_tmp(filename)
    return age_h


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


def get_cached_valuation(ticker: str) -> dict | None:
    """Return cached valuation_core + analyst consensus for one ticker.

    Cache file at data/cache/valuation/{TICKER}.json with shape:
      {"core": {...}, "consensus": {...}, "individual": [...], "updated_at": "..."}
    """
    return load_cache_file(f"valuation/{ticker.upper()}.json")
