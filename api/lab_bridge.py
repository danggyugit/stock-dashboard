"""Bridge module — load `2_AI_Quant_Lab.py` as a Python module in batch mode.

The Streamlit page contains the actual backtest logic (`run_backtest`, data
prefetch helpers, serializers). Running it headlessly requires stubbing out
every `st.*` call the page uses at import time.

This module replicates the exact pattern used by
`streamlit_app/scripts/run_preset_backtests.py` (the daily preset runner),
so we know it works — but exposes the loaded module for on-demand HTTP use.
"""

from __future__ import annotations

import importlib.util
import logging
import os
import sys
import types
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Paths (relative to repo root) ─────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parent.parent
_APP_DIR = _REPO_ROOT / "streamlit_app"
_PAGE_PATH = _APP_DIR / "app_pages" / "2_AI_Quant_Lab.py"

# Ensure streamlit_app packages are importable
for p in (str(_APP_DIR), str(_REPO_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)


# ── Streamlit stubs (must be set BEFORE loading the page module) ──


class _NullCM:
    """No-op context manager for st.spinner, st.progress, st.empty, etc."""
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
    """Replaces @st.cache_data / @st.cache_resource — noop in batch mode."""
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
        for k in ("FINNHUB_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "FRED_API_KEY"):
            v = os.environ.get(k)
            if v:
                self[k] = v

    def get(self, k, default=None):
        return super().get(k, default)


def _install_streamlit_stub() -> None:
    """Install a fake `streamlit` module into sys.modules."""
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
    _st.header = lambda *a, **k: None
    _st.write = lambda *a, **k: None
    _st.plotly_chart = lambda *a, **k: None
    _st.altair_chart = lambda *a, **k: None
    _st.pyplot = lambda *a, **k: None
    _st.dataframe = lambda *a, **k: None
    _st.table = lambda *a, **k: None
    _st.metric = lambda *a, **k: None
    _st.divider = lambda *a, **k: None
    _st.set_page_config = lambda *a, **k: None
    _st.stop = lambda: None
    _st.rerun = lambda: None
    _st.form = lambda *a, **k: _NullCM()
    _st.expander = lambda *a, **k: _NullCM()
    _st.container = lambda *a, **k: _NullCM()
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
    _st.download_button = lambda *a, **k: False
    _st.image = lambda *a, **k: None

    sys.modules["streamlit"] = _st


def _install_dashboard_stubs() -> None:
    """Stub out modules the page imports that aren't safe headlessly."""
    _auth = types.ModuleType("services.auth_service")
    _auth.require_auth = lambda: {"id": 1, "email": "api@local", "name": "api"}
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


# ── Module cache (load once per process) ──────────────────────────

_lab_module = None


def load_lab():
    """Return the loaded AI Quant Lab module (initializes on first call)."""
    global _lab_module
    if _lab_module is not None:
        return _lab_module

    _install_streamlit_stub()
    _install_dashboard_stubs()

    logger.info("Loading AI Quant Lab module from %s", _PAGE_PATH)
    spec = importlib.util.spec_from_file_location("_quant_lab_api", _PAGE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module spec for {_PAGE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    logger.info("AI Quant Lab module loaded successfully")
    _lab_module = module
    return module


# ── Data prefetch (mirrors run_preset_backtests.prepare_shared_data) ──


def prepare_shared_data(cfg: dict) -> dict:
    """Fetch all market data needed for a backtest (universe → prices → PIT
    financials → technicals → benchmarks). Slow on cold cache (minutes)."""
    import yfinance as yf
    lab = load_lab()

    sp1500_df, _ = lab.get_sp1500_info()
    cap_filter = sp1500_df[sp1500_df["cap_tier"].isin(cfg["cap_tiers"])]
    universe = cap_filter[cap_filter["sector"].isin(cfg["sectors"])]["ticker"].tolist()
    logger.info("Universe: %d tickers", len(universe))

    sp500_changes = None
    current_sp500 = None
    extra_tickers = []
    if cfg.get("use_surv_fix"):
        sp500_changes = lab.get_sp500_changes()
        current_sp500 = sp1500_df[sp1500_df["cap_tier"] == "Large Cap"]["ticker"].tolist()
        if sp500_changes is not None and not sp500_changes.empty:
            bt_start = pd.Timestamp(cfg["start"])
            removed = sp500_changes[
                (sp500_changes["date"] >= bt_start)
                & (sp500_changes["removed_ticker"] != "")
            ]["removed_ticker"].unique().tolist()
            sel = set(cfg["sectors"])
            for t in removed:
                m = sp1500_df[sp1500_df["ticker"] == t]
                if not m.empty and m.iloc[0].get("sector", "") in sel:
                    extra_tickers.append(t)
            extra_tickers = [t for t in extra_tickers if t not in universe]

    all_tickers = list(set(universe + extra_tickers))
    logger.info("Universe including historical: %d", len(all_tickers))

    data_start = cfg["start"] - timedelta(days=400)
    price_data = lab.download_price_data(
        tuple(all_tickers),
        data_start.strftime("%Y-%m-%d"),
        cfg["end"].strftime("%Y-%m-%d"),
    )
    available = list(price_data.keys())
    logger.info("Prices: %d tickers", len(price_data))

    fund_map = lab.get_fundamental_yf(tuple(available))
    pit_map = lab.get_pit_financials(tuple(available))

    # SPY / VIX benchmarks
    spy_close = None
    vix_close = None
    try:
        spy_df = yf.download(
            "SPY",
            start=data_start.strftime("%Y-%m-%d"),
            end=cfg["end"].strftime("%Y-%m-%d"),
            auto_adjust=True,
            progress=False,
        )
        if not spy_df.empty:
            spy_close = spy_df["Close"].squeeze()
    except Exception as e:
        logger.warning("SPY fetch failed: %s", e)
    try:
        vix_df = yf.download(
            "^VIX",
            start=data_start.strftime("%Y-%m-%d"),
            end=cfg["end"].strftime("%Y-%m-%d"),
            auto_adjust=True,
            progress=False,
        )
        if not vix_df.empty:
            vix_close = vix_df["Close"].squeeze()
    except Exception as e:
        logger.warning("VIX fetch failed: %s", e)

    sector_map = {
        row["ticker"]: row.get("sector", "Unknown") for _, row in sp1500_df.iterrows()
    }

    tech_map = {}
    for t, ohlcv in price_data.items():
        try:
            tech_map[t] = lab.calc_all_technical(ohlcv, spy_close=spy_close)
        except Exception:
            pass

    rebal_dates = lab.generate_rebalance_dates(cfg["start"], cfg["end"], cfg["rebal_m"])

    return {
        "price_data": price_data,
        "fund_map": fund_map,
        "pit_map": pit_map,
        "tech_map": tech_map,
        "spy_close": spy_close,
        "vix_close": vix_close,
        "sector_map": sector_map,
        "rebal_dates": rebal_dates,
        "sp500_changes": sp500_changes,
        "current_sp500": current_sp500,
    }


def run_backtest(cfg: dict, shared: dict) -> dict:
    """Invoke the AI Quant Lab backtest engine with a resolved config."""
    lab = load_lab()
    return lab.run_backtest(
        price_data=shared["price_data"],
        fund_map=shared["fund_map"],
        tech_map=shared["tech_map"],
        rebal_dates=shared["rebal_dates"],
        n_stocks=cfg["n_stocks"],
        tc_pct=cfg["tc_pct"],
        rolling_win=cfg["rolling_w"],
        progress=lambda pct, msg="": logger.info("  [%.0f%%] %s", pct * 100, msg),
        pit_map=shared["pit_map"],
        min_dollar_vol=cfg["min_dollar_vol"],
        use_next_open=cfg["use_next_open"],
        sp500_changes=shared["sp500_changes"],
        current_sp500=shared["current_sp500"],
        use_ensemble=cfg["use_ensemble"],
        spy_close=shared["spy_close"],
        vix_close=shared["vix_close"],
        sector_map=shared["sector_map"],
        use_mom_filter=cfg["use_mom_filter"],
        use_turnover_buffer=cfg["use_turnover_buffer"],
        use_inv_vol_weight=cfg["use_inv_vol_weight"],
        use_momentum_weight=cfg.get("use_momentum_weight", False),
        cash_strategy=cfg["cash_strategy"],
    )


# ── Serialization (mirrors run_preset_backtests._serialize_full_results) ──


def _serialize_datetime(v):
    if v is None:
        return None
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if hasattr(v, "isoformat"):
        try:
            return v.isoformat()
        except Exception:
            pass
    return str(v)


def _serialize_ticker_df(df):
    if df is None or df.empty:
        return []
    out = []
    for _, row in df.iterrows():
        d = {}
        for col, val in row.items():
            if pd.isna(val):
                d[col] = None
            elif isinstance(val, (np.integer,)):
                d[col] = int(val)
            elif isinstance(val, (np.floating, float)):
                d[col] = float(val) if not np.isinf(val) else None
            else:
                d[col] = val
        out.append(d)
    return out


def _serialize_fimp(df):
    if df is None or df.empty:
        return []
    out = []
    for idx, row in df.iterrows():
        entry = {"date": _serialize_datetime(idx)}
        for col, val in row.items():
            if pd.isna(val):
                entry[col] = None
            else:
                try:
                    entry[col] = float(val)
                except Exception:
                    entry[col] = val
        out.append(entry)
    return out


def serialize_results(results: dict, cfg: dict) -> dict:
    """Convert backtest output to JSON-safe dict matching backtests/*.json format."""
    lab = load_lab()

    port_dates = [_serialize_datetime(d) for d in results.get("port_dates", [])]
    port_values = [float(v) for v in results.get("port_values", [])]

    rebal_hist_out = []
    for h in results.get("rebal_hist", []):
        entry = {}
        for k, v in h.items():
            if k == "ticker_df":
                entry[k] = _serialize_ticker_df(v)
            elif k in ("rebalance_date", "next_date"):
                entry[k] = _serialize_datetime(v)
            elif isinstance(v, (np.integer,)):
                entry[k] = int(v)
            elif isinstance(v, (np.floating, float)):
                entry[k] = float(v) if not np.isinf(v) else None
            elif isinstance(v, list):
                entry[k] = list(v)
            else:
                entry[k] = v
        rebal_hist_out.append(entry)

    # Cash history
    cash_history = []
    for c in results.get("cash_history", []):
        entry = {}
        for k, v in c.items():
            if k == "date":
                entry[k] = _serialize_datetime(v)
            elif isinstance(v, (np.floating, float)):
                entry[k] = float(v) if not np.isinf(v) else None
            else:
                entry[k] = v
        cash_history.append(entry)

    # IC records
    ic_records = []
    for r in results.get("ic_records", []):
        entry = {}
        for k, v in r.items():
            if k == "date":
                entry[k] = _serialize_datetime(v)
            elif isinstance(v, (np.floating, float)):
                entry[k] = float(v) if not np.isinf(v) else None
            else:
                entry[k] = v
        ic_records.append(entry)

    # Feature importance dataframes (may be missing for some models)
    fimp_data = _serialize_fimp(results.get("fimp_df"))
    fimp_rf = _serialize_fimp(results.get("fimp_rf_df"))
    fimp_xgb = _serialize_fimp(results.get("fimp_xgb_df"))
    fimp_lgbm = _serialize_fimp(results.get("fimp_lgbm_df"))

    last_full_ranking = _serialize_ticker_df(results.get("last_full_ranking"))

    # Summary metrics
    summary: dict = {"n_rebalances": len(rebal_hist_out)}
    try:
        if len(port_values) >= 2:
            port_active = pd.Series(port_values, index=pd.DatetimeIndex(port_dates))
            m = lab.calc_metrics(port_active, "AI", rf=0.04)
            summary.update({
                "total_return_pct": round(m.get("total_return_pct", 0), 2),
                "cagr_pct": round(m.get("cagr_pct", 0), 2),
                "sharpe": round(m.get("sharpe", 0), 3),
                "sortino": round(m.get("sortino", 0), 3),
                "max_dd_pct": round(m.get("max_dd_pct", 0), 2),
                "monthly_win_rate_pct": round(m.get("monthly_win_rate_pct", 0), 2),
                "volatility_pct": m.get("volatility_pct"),
            })
    except Exception as e:
        logger.warning("Metric calc failed: %s", e)

    # Rebalancing win rate
    rets = [h.get("실제수익률") for h in rebal_hist_out if isinstance(h.get("실제수익률"), (int, float))]
    if rets:
        wins = sum(1 for r in rets if r > 0)
        summary["rebal_win_rate_pct"] = round(wins / len(rets) * 100, 2)
        summary["avg_period_return_pct"] = round(sum(rets) / len(rets) * 100, 2)
        pos = sum(r for r in rets if r > 0)
        neg = -sum(r for r in rets if r < 0)
        summary["profit_factor"] = round(pos / neg, 2) if neg > 0 else None

    return {
        "config": {**cfg, "start": _serialize_datetime(cfg.get("start")), "end": _serialize_datetime(cfg.get("end"))},
        "summary": summary,
        "last_rebalance_date": rebal_hist_out[-1]["rebalance_date"] if rebal_hist_out else None,
        "latest_picks": rebal_hist_out[-1]["ticker_df"][:10] if rebal_hist_out else [],
        "full": {
            "port_dates": port_dates,
            "port_values": port_values,
            "rebal_hist": rebal_hist_out,
            "cash_history": cash_history,
            "ic_records": ic_records,
            "fimp_data": fimp_data,
            "fimp_rf_data": fimp_rf,
            "fimp_xgb_data": fimp_xgb,
            "fimp_lgbm_data": fimp_lgbm,
            "last_full_ranking": last_full_ranking,
            "use_ensemble": cfg.get("use_ensemble", False),
            "rebal_m": cfg.get("rebal_m", 1),
            "cash_strategy": cfg.get("cash_strategy", "none"),
        },
    }
