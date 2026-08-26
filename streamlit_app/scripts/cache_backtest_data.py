"""Cache all yfinance/SEC data needed for on-demand backtests.

Runs on Windows PC (residential IP — yfinance works). Downloads prices,
fundamentals, PIT financials, and benchmarks for the universe of tickers
that the FastAPI backtest service on Render will need, then saves them
as compressed pickle/JSON files under
`streamlit_app/data/cache/backtest_data/`.

The API service on Render loads these files instead of calling yfinance
directly (Yahoo blocks datacenter IPs with 'Invalid Crumb' errors).

Schedule: run daily via Windows Task Scheduler after the market close,
followed by `git commit + push` so Render pulls the fresh data on next
deploy.

Universe: 10 SPDR sectors × Large Cap ≈ 500 tickers.
Date range: 400-day warm-up before 2023-01-01 through yesterday.
Total output: ~10-30MB compressed.

Companion: cache_backtest_data.bat (Task Scheduler wrapper that also
handles the git commit + push).
"""

from __future__ import annotations

import gzip
import importlib.util
import json
import logging
import os
import pickle
import sys
import types
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# ── Environment (must precede loading the AI Quant Lab page) ─────
os.environ["QUANT_LAB_BATCH"] = "1"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("cache-backtest-data")

_APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_APP_DIR))


# ── Streamlit + dashboard stubs (mirror run_preset_backtests.py) ──


class _NullCM:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def __call__(self, *a, **k): return self
    def __getattr__(self, k): return self
    def progress(self, *a, **k): return None
    def empty(self, *a, **k): return None
    def markdown(self, *a, **k): return None
    def write(self, *a, **k): return None
    def caption(self, *a, **k): return None
    def container(self, *a, **k): return _NullCM()


def _passthrough_decorator(*d_args, **d_kwargs):
    if d_args and callable(d_args[0]):
        return d_args[0]

    def _wrap(fn):
        return fn
    return _wrap


class _SessionState(dict):
    def __getattr__(self, k): return self.get(k)
    def __setattr__(self, k, v): self[k] = v


class _Secrets(dict):
    def __init__(self):
        super().__init__()
        for k in ("FINNHUB_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY"):
            v = os.environ.get(k)
            if v:
                self[k] = v

    def get(self, k, default=None):
        return super().get(k, default)


_st = types.ModuleType("streamlit")
_st.cache_data = _passthrough_decorator
_st.cache_resource = _passthrough_decorator
_st.session_state = _SessionState()
_st.secrets = _Secrets()
_st.spinner = lambda *a, **k: _NullCM()
_st.progress = lambda *a, **k: _NullCM()
_st.empty = lambda *a, **k: _NullCM()
_st.warning = lambda *a, **k: None
_st.error = lambda *a, **k: None
_st.info = lambda *a, **k: None
_st.success = lambda *a, **k: None
_st.caption = lambda *a, **k: None
_st.markdown = lambda *a, **k: None
_st.title = lambda *a, **k: None
_st.subheader = lambda *a, **k: None
_st.write = lambda *a, **k: None
_st.plotly_chart = lambda *a, **k: None
_st.dataframe = lambda *a, **k: None
_st.metric = lambda *a, **k: None
_st.divider = lambda *a, **k: None
_st.set_page_config = lambda *a, **k: None
_st.stop = lambda: None
_st.rerun = lambda: None
_st.form = lambda *a, **k: _NullCM()
_st.expander = lambda *a, **k: _NullCM()
_st.columns = lambda spec, **k: [_NullCM() for _ in range(spec if isinstance(spec, int) else len(spec))]
_st.tabs = lambda labels: [_NullCM() for _ in labels]
_st.form_submit_button = lambda *a, **k: False
_st.button = lambda *a, **k: False
_st.slider = lambda *a, **k: (k.get("value") if "value" in k else 0)
_st.selectbox = lambda *a, **k: (k.get("index") if "index" in k else None)
_st.multiselect = lambda *a, **k: (k.get("default") or [])
_st.checkbox = lambda *a, **k: (k.get("value") or False)
_st.toggle = lambda *a, **k: (k.get("value") or False)
_st.date_input = lambda *a, **k: date.today()
_st.number_input = lambda *a, **k: (k.get("value") or 0)
_st.text_input = lambda *a, **k: (k.get("value") or "")
_st.radio = lambda *a, **k: None
_st.file_uploader = lambda *a, **k: None
sys.modules["streamlit"] = _st

# Dashboard-side stubs
_auth = types.ModuleType("services.auth_service")
_auth.require_auth = lambda: {"id": 1, "email": "batch@local", "name": "batch"}
_auth.render_user_sidebar = lambda: None
_auth.is_logged_in = lambda: True
sys.modules["services.auth_service"] = _auth

_ui = types.ModuleType("components.ui")
_ui.inject_css = lambda: None
_ui.page_header = lambda *a, **k: None
_ui.render_sidebar_info = lambda: None
_ui.stock_logo_url = lambda t: ""
sys.modules["components.ui"] = _ui

_i18n = types.ModuleType("services.i18n")
_i18n.t = lambda key, **kw: key
_i18n.register_strings = lambda d: None
_i18n.get_lang = lambda: "en"
_i18n.set_lang = lambda x: None
_i18n.render_lang_toggle = lambda: None
sys.modules["services.i18n"] = _i18n

_i18n_reg = types.ModuleType("app_pages._quant_lab_i18n")
sys.modules["app_pages._quant_lab_i18n"] = _i18n_reg


# ── Stub ML libs (only needed for run_backtest, not for data caching) ──
# Prevents needing xgboost/lightgbm/hmmlearn to be fully working on the
# machine that only caches data. Even if the packages are installed, they
# may fail to load native libs (e.g. xgboost needs libomp on Mac).
# We only need them to satisfy top-level `from xgboost import XGBRegressor`
# imports in 2_AI_Quant_Lab.py; the actual model classes are never called
# during caching.

for _mod_name, _class_names in [
    ("xgboost", ["XGBRegressor", "XGBClassifier"]),
    ("lightgbm", ["LGBMRegressor", "LGBMClassifier"]),
    ("hmmlearn", []),
    ("hmmlearn.hmm", ["GaussianHMM"]),
]:
    real_load_failed = False
    try:
        __import__(_mod_name)
    except Exception:
        real_load_failed = True

    if real_load_failed or _mod_name not in sys.modules:
        _fake = types.ModuleType(_mod_name)
        for _cn in _class_names:
            setattr(_fake, _cn, type(_cn, (), {"__init__": lambda self, *a, **k: None}))
        sys.modules[_mod_name] = _fake
        logger.info("Stubbed module (native load failed or missing): %s", _mod_name)


# ── Load AI Quant Lab (batch mode) ──────────────────────────────

_PAGE_PATH = _APP_DIR / "app_pages" / "2_AI_Quant_Lab.py"
_spec = importlib.util.spec_from_file_location("_quant_lab_cache", _PAGE_PATH)
_lab = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_lab)
logger.info("AI Quant Lab module loaded")


# ── Configuration ───────────────────────────────────────────────

CACHE_DIR = _APP_DIR / "data" / "cache" / "backtest_data"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# 10 sectors × Large Cap covers the 50-preset matrix (10 sec × 5 strategies).
# Utilities intentionally excluded to keep universe size manageable
# (~500 tickers instead of ~600, and Utilities rarely picks in momentum strategies).
TARGET_SECTORS = [
    "Information Technology",
    "Health Care",
    "Financials",
    "Consumer Discretionary",
    "Communication Services",
    "Industrials",
    "Consumer Staples",
    "Energy",
    "Materials",
    "Real Estate",
]

# Backtest lookback window: 400 warm-up days (RSI, momentum lookback need history)
# before the earliest backtest start date (2023-01-01), through yesterday.
DATA_END = date.today() - timedelta(days=1)
DATA_START = date(2023, 1, 1) - timedelta(days=400)


# ── Save helpers ────────────────────────────────────────────────


def save_pickle_gz(obj, path: Path) -> None:
    """Pickle + gzip. Used for complex nested structures with DataFrames."""
    with gzip.open(path, "wb") as f:
        pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)
    size_mb = path.stat().st_size / 1_000_000
    logger.info("Saved %s (%.2f MB)", path.name, size_mb)


def save_json(obj, path: Path) -> None:
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")
    size_kb = path.stat().st_size / 1_000
    logger.info("Saved %s (%.1f KB)", path.name, size_kb)


# ── Main pipeline ──────────────────────────────────────────────


def main() -> None:
    import pandas as pd
    import yfinance as yf

    logger.info("=" * 60)
    logger.info("Cache backtest data — %s to %s", DATA_START, DATA_END)
    logger.info("Output dir: %s", CACHE_DIR)
    logger.info("=" * 60)

    # 1. Universe: S&P 1500 metadata + filter to Large Cap × target sectors
    sp1500_df, _ = _lab.get_sp1500_info()
    target_df = sp1500_df[
        (sp1500_df["cap_tier"] == "Large Cap")
        & (sp1500_df["sector"].isin(TARGET_SECTORS))
    ]
    tickers = target_df["ticker"].tolist()
    logger.info("Universe: %d tickers (%d sectors × Large Cap)",
                len(tickers), len(TARGET_SECTORS))

    # Full S&P 1500 metadata saved (API uses for sector_map / filter_universe)
    save_json(
        sp1500_df.to_dict(orient="records"),
        CACHE_DIR / "metadata.json",
    )

    # 2. S&P 500 membership changes (for survivorship-bias correction)
    logger.info("Fetching S&P 500 changes...")
    sp500_changes = _lab.get_sp500_changes()
    if sp500_changes is not None and not sp500_changes.empty:
        save_pickle_gz(sp500_changes, CACHE_DIR / "sp500_changes.pkl.gz")
    else:
        logger.warning("sp500_changes empty — saving as None")
        save_pickle_gz(None, CACHE_DIR / "sp500_changes.pkl.gz")

    # 3. Prices — main data payload (10-20 min for 500 tickers × 3 years)
    logger.info("Downloading prices for %d tickers (10-20 min)...", len(tickers))
    price_data = _lab.download_price_data(
        tuple(tickers),
        DATA_START.strftime("%Y-%m-%d"),
        DATA_END.strftime("%Y-%m-%d"),
    )
    logger.info("Got prices for %d tickers", len(price_data))
    save_pickle_gz(price_data, CACHE_DIR / "prices.pkl.gz")

    available = list(price_data.keys())

    # 4. Fundamentals (yfinance .info)
    logger.info("Downloading fundamentals for %d tickers...", len(available))
    fund_map = _lab.get_fundamental_yf(tuple(available))
    logger.info("Fundamentals: %d tickers", sum(1 for v in fund_map.values() if v))
    save_pickle_gz(fund_map, CACHE_DIR / "fundamentals.pkl.gz")

    # 5. Point-in-Time financials (SEC EDGAR — slow, 5-15 min)
    logger.info("Downloading PIT financials (5-15 min)...")
    pit_map = _lab.get_pit_financials(tuple(available))
    with_data = sum(1 for v in pit_map.values()
                    if not v.get("income", pd.DataFrame()).empty)
    logger.info("PIT: %d tickers with income statements", with_data)
    save_pickle_gz(pit_map, CACHE_DIR / "pit.pkl.gz")

    # 6. Benchmarks (SPY + VIX)
    logger.info("Downloading SPY + VIX benchmarks...")
    spy_df = yf.download(
        "SPY",
        start=DATA_START.strftime("%Y-%m-%d"),
        end=DATA_END.strftime("%Y-%m-%d"),
        auto_adjust=True,
        progress=False,
    )
    vix_df = yf.download(
        "^VIX",
        start=DATA_START.strftime("%Y-%m-%d"),
        end=DATA_END.strftime("%Y-%m-%d"),
        auto_adjust=True,
        progress=False,
    )
    spy_close = spy_df["Close"].squeeze() if not spy_df.empty else pd.Series(dtype=float)
    vix_close = vix_df["Close"].squeeze() if not vix_df.empty else pd.Series(dtype=float)
    benchmarks = {"SPY": spy_close, "VIX": vix_close}
    save_pickle_gz(benchmarks, CACHE_DIR / "benchmarks.pkl.gz")

    # 7. Manifest — small JSON that the API reads first to check freshness
    manifest = {
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "data_start": DATA_START.isoformat(),
        "data_end": DATA_END.isoformat(),
        "tickers_count": len(available),
        "target_sectors": TARGET_SECTORS,
        "files": [
            "prices.pkl.gz",
            "fundamentals.pkl.gz",
            "pit.pkl.gz",
            "benchmarks.pkl.gz",
            "sp500_changes.pkl.gz",
            "metadata.json",
        ],
    }
    save_json(manifest, CACHE_DIR / "_manifest.json")

    logger.info("=" * 60)
    logger.info("Cache refresh complete")
    logger.info("Total size: %.1f MB",
                sum(f.stat().st_size for f in CACHE_DIR.iterdir()) / 1_000_000)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
