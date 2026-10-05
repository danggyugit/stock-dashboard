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

Universe: 10 SPDR sectors × BACKTEST_CAP_TIERS. Default Large Cap ≈ 470
tickers; the launchd job sets "all" (S&P 1500 ≈ 1,440 tickers).
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

# BACKTEST_DATA_DIR overrides the output dir so a trial universe can be
# collected next to the production cache without replacing it.
_DATA_DIR_ENV = os.environ.get("BACKTEST_DATA_DIR", "").strip()
CACHE_DIR = (Path(_DATA_DIR_ENV) if _DATA_DIR_ENV
             else _APP_DIR / "data" / "cache" / "backtest_data")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# BACKTEST_CAP_TIERS: "large" (default, S&P 500) | "all" (S&P 1500) | comma
# list of tier names. run_preset_backtests.py reads the same variable.
_ALL_CAP_TIERS = ["Large Cap", "Mid Cap", "Small Cap"]
_tiers_env = os.environ.get("BACKTEST_CAP_TIERS", "").strip()
if not _tiers_env or _tiers_env.lower() == "large":
    CAP_TIERS = ["Large Cap"]
elif _tiers_env.lower() == "all":
    CAP_TIERS = list(_ALL_CAP_TIERS)
else:
    CAP_TIERS = [t.strip() for t in _tiers_env.split(",") if t.strip()]
    _unknown = [t for t in CAP_TIERS if t not in _ALL_CAP_TIERS]
    if _unknown:
        raise ValueError(f"BACKTEST_CAP_TIERS: unknown tier(s) {_unknown}")

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
    """Pickle + gzip, written atomically.

    This job takes hours, and run_preset_backtests.py reads these same
    files on its own schedule. A plain open-and-write leaves the file
    truncated for the whole write window, so an overlapping reader hits
    `EOFError: Compressed file ended before the end-of-stream marker was
    reached` and every preset fails. Write to a temp file in the same
    directory, then os.replace() — atomic on POSIX, so readers always
    see either the old complete file or the new complete file.
    """
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with gzip.open(tmp, "wb") as f:
            pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    size_mb = path.stat().st_size / 1_000_000
    logger.info("Saved %s (%.2f MB)", path.name, size_mb)


def _load_prev_pickle(name: str):
    """Yesterday's copy of a cache file, or None if missing/unreadable."""
    path = CACHE_DIR / name
    if not path.exists():
        return None
    try:
        with gzip.open(path, "rb") as f:
            return pickle.load(f)
    except Exception as e:
        logger.warning("Could not read previous %s (%s) — starting fresh", name, e)
        return None


def _fund_is_empty(info: dict | None) -> bool:
    """True when a fundamentals row carries no data (rate-limited .info)."""
    if not info:
        return True
    for v in info.values():
        if isinstance(v, (int, float)) and v == v and v != 0:
            return False
    return True


def _pit_has_data(entry: dict | None) -> bool:
    df = (entry or {}).get("income")
    return df is not None and not df.empty


# ── PIT collection under Yahoo's rate limit ──────────────────────
#
# Statements cost 6 requests per ticker. Yahoo cuts a client off after
# roughly 3,000 of them and then answers with *empty frames* (no error) for
# a long while — the 1,441-ticker universe got data for the first 495
# tickers and nothing for the other 946. So a single pass can't cover the
# S&P 1500, and an unguarded one silently wipes whatever it didn't reach.
#
# Quarterly statements only change four times a year, so instead of
# refetching everything nightly we: carry yesterday's entries forward,
# fetch in batches starting with tickers that have no data yet and then the
# stalest, and stop once Yahoo starts returning empties. Coverage builds up
# The limit lifts again within minutes (measured: ~350-500 tickers per
# window), so while tickers are still missing data we wait and resume; once
# everything is covered, the first limit simply ends the night's refresh
# and each ticker gets refetched every few days.
PIT_BATCH = 50
PIT_BUDGET_MIN = int(os.environ.get("PIT_BUDGET_MIN", "120"))     # wall-clock cap
PIT_COOLDOWN_MIN = int(os.environ.get("PIT_COOLDOWN_MIN", "10"))  # wait when limited
PIT_MAX_COOLDOWNS = int(os.environ.get("PIT_MAX_COOLDOWNS", "6"))
PIT_PROBE_TICKER = "AAPL"
PIT_STAMP_FILE = "pit_fetched.json"


def _pit_rate_limited() -> bool:
    """Probe with a ticker that always has statements. Tells a rate limit
    (probe comes back empty too) apart from a batch of names that simply
    have no statements on Yahoo."""
    got = _lab.get_pit_financials((PIT_PROBE_TICKER,))
    return not _pit_has_data(got.get(PIT_PROBE_TICKER))


def collect_pit(tickers: list[str]) -> dict:
    """Incremental, rate-limit-aware PIT refresh. Never drops existing data."""
    import time

    prev = _load_prev_pickle("pit.pkl.gz") or {}
    stamp_path = CACHE_DIR / PIT_STAMP_FILE
    try:
        stamps: dict = json.loads(stamp_path.read_text(encoding="utf-8"))
    except Exception:
        stamps = {}

    pit_map = {t: prev[t] for t in tickers if t in prev}
    have = sum(1 for t in tickers if _pit_has_data(pit_map.get(t)))
    logger.info("PIT carry-forward: %d/%d tickers already have statements",
                have, len(tickers))

    # No data first, then oldest fetch date ("" sorts before any date).
    queue = sorted(tickers, key=lambda t: (_pit_has_data(pit_map.get(t)),
                                           stamps.get(t, "")))
    today = date.today().isoformat()
    deadline = time.time() + PIT_BUDGET_MIN * 60
    cooldowns = 0
    fetched_ok = 0
    i = 0
    while i < len(queue) and time.time() < deadline:
        batch = queue[i:i + PIT_BATCH]
        got = _lab.get_pit_financials(tuple(batch))
        ok = [t for t in batch if _pit_has_data(got.get(t))]
        for t in ok:
            pit_map[t] = got[t]
            stamps[t] = today
        fetched_ok += len(ok)
        if len(ok) >= len(batch) * 0.5 or not _pit_rate_limited():
            # Stamp the empties too: they were genuinely tried, and without
            # a stamp they would head the queue again every night.
            for t in batch:
                stamps[t] = today
            i += PIT_BATCH
            continue
        # Rate limited. Keep what came through, then wait it out and retry
        # the same batch — but only while some ticker still has no data at
        # all; a pure staleness refresh isn't worth waiting for.
        missing_left = any(not _pit_has_data(pit_map.get(t)) for t in queue[i:])
        if not missing_left or cooldowns >= PIT_MAX_COOLDOWNS or \
                time.time() + PIT_COOLDOWN_MIN * 60 >= deadline:
            logger.warning("PIT: rate limited at ticker %d/%d — stopping for "
                           "tonight, the rest keeps its previous data",
                           i + len(ok), len(queue))
            break
        cooldowns += 1
        logger.warning("PIT: rate limited at ticker %d/%d — cooling down %d min "
                       "(%d/%d)", i + len(ok), len(queue), PIT_COOLDOWN_MIN,
                       cooldowns, PIT_MAX_COOLDOWNS)
        time.sleep(PIT_COOLDOWN_MIN * 60)

    for t in tickers:
        pit_map.setdefault(t, {})
    save_json({t: stamps[t] for t in tickers if t in stamps}, stamp_path)
    logger.info("PIT: refreshed %d tickers tonight", fetched_ok)
    return pit_map


def save_json(obj, path: Path) -> None:
    """Atomic JSON write — same rationale as save_pickle_gz."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
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
        (sp1500_df["cap_tier"].isin(CAP_TIERS))
        & (sp1500_df["sector"].isin(TARGET_SECTORS))
    ]
    tickers = target_df["ticker"].tolist()
    logger.info("Universe: %d tickers (%d sectors × %s)",
                len(tickers), len(TARGET_SECTORS), " + ".join(CAP_TIERS))

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
    prev_fund = _load_prev_pickle("fundamentals.pkl.gz") or {}
    fund_map = _lab.get_fundamental_yf(tuple(available))
    # A rate-limited .info comes back as an all-NaN row. Keep yesterday's
    # row for those tickers instead of overwriting good data with blanks.
    kept = 0
    for t in available:
        if _fund_is_empty(fund_map.get(t)) and not _fund_is_empty(prev_fund.get(t)):
            fund_map[t] = prev_fund[t]
            kept += 1
    logger.info("Fundamentals: %d tickers with data (%d carried forward)",
                sum(1 for v in fund_map.values() if not _fund_is_empty(v)), kept)
    save_pickle_gz(fund_map, CACHE_DIR / "fundamentals.pkl.gz")

    # 5. Point-in-Time financials (SEC EDGAR — slow, 5-15 min)
    logger.info("Downloading PIT financials (5-15 min)...")
    pit_map = collect_pit(available)
    with_data = sum(1 for v in pit_map.values()
                    if not v.get("income", pd.DataFrame()).empty)
    logger.info("PIT: %d/%d tickers with income statements", with_data, len(available))
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
        "cap_tiers": CAP_TIERS,
        "pit_with_data": with_data,
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
