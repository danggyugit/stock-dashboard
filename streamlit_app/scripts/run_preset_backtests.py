"""Daily preset backtest runner — headless execution of AI Quant Lab.

Runs 3 preset configurations on IT sector from 2023-01-01 to yesterday,
saves summary + latest AI recommendations to JSON files for MCP consumption.

Triggered by Windows Task Scheduler (11:00 KST daily) via
  scripts/run_preset_backtests.bat

Output:
  streamlit_app/data/cache/backtests/it_invvol.json
  streamlit_app/data/cache/backtests/it_equal.json
  streamlit_app/data/cache/backtests/it_invvol_regime.json
  streamlit_app/data/cache/backtests/_metadata.json
"""

from __future__ import annotations

import importlib.util
import json
import logging
import os
import sys
import traceback
import types
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

# ════════════════════════════════════════════════════════════
# 1. Environment + Streamlit stubs
# ════════════════════════════════════════════════════════════

os.environ["QUANT_LAB_BATCH"] = "1"   # prevents 2_AI_Quant_Lab.main() auto-run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("preset-backtests")

_APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_APP_DIR))

# ── Telegram 알림 설정 ──────────────────────────────────────
_WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_BRIEFING_ENV = _WORKSPACE_ROOT / "stock_briefing" / ".env"
if _BRIEFING_ENV.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_BRIEFING_ENV, override=False)
    except ImportError:
        pass

_TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
# QUANT_LAB_CHAT_ID가 있으면 그것을 우선 사용 (직접 봇 채팅), 없으면 TELEGRAM_CHAT_ID fallback
_quant_lab_chat = os.environ.get("QUANT_LAB_CHAT_ID", "").strip()
_TG_CHAT_IDS = (
    [_quant_lab_chat]
    if _quant_lab_chat
    else [c.strip() for c in os.environ.get("TELEGRAM_CHAT_ID", "").split(",") if c.strip()]
)


def _notify_telegram(text: str) -> None:
    """배치 결과를 Telegram으로 발송. 실패해도 배치 자체에 영향 없음."""
    if not _TG_TOKEN or not _TG_CHAT_IDS:
        logger.info("Telegram 미설정 — 알림 건너뜀")
        return
    import urllib.parse
    import urllib.request
    for chat_id in _TG_CHAT_IDS:
        try:
            url = f"https://api.telegram.org/bot{_TG_TOKEN}/sendMessage"
            payload = urllib.parse.urlencode({
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
            }).encode()
            req = urllib.request.Request(url, data=payload, method="POST")
            with urllib.request.urlopen(req, timeout=10):
                pass
            logger.info("Telegram 알림 발송: %s", chat_id)
        except Exception as e:
            logger.warning("Telegram 알림 실패 (%s): %s", chat_id, e)


# Minimal Streamlit stub (just enough to satisfy module-level imports)
def _passthrough_decorator(*args, **kwargs):
    if args and callable(args[0]):
        return args[0]
    def _wrap(fn):
        return fn
    return _wrap


class _NullCM:
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def __call__(self, *args, **kwargs): return self


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


def _fake_form(*a, **k): return _NullCM()


def _fake_expander(*a, **k): return _NullCM()


def _fake_columns(spec, **k):
    n = spec if isinstance(spec, int) else len(spec)
    return [_NullCM() for _ in range(n)]


def _fake_tabs(labels): return [_NullCM() for _ in labels]


_st.form = _fake_form
_st.expander = _fake_expander
_st.columns = _fake_columns
_st.tabs = _fake_tabs
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


# Stub dashboard-specific modules that the page imports
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

# i18n: already exists as real module but requires registered keys — use a
# pass-through stub so missing keys don't crash.
_i18n = types.ModuleType("services.i18n")
_i18n.t = lambda key, **kw: key
_i18n.register_strings = lambda d: None
_i18n.get_lang = lambda: "en"
_i18n.set_lang = lambda x: None
_i18n.render_lang_toggle = lambda: None
sys.modules["services.i18n"] = _i18n

# i18n registration module
_i18n_reg = types.ModuleType("app_pages._quant_lab_i18n")
sys.modules["app_pages._quant_lab_i18n"] = _i18n_reg


# ════════════════════════════════════════════════════════════
# 2. Load AI Quant Lab module
# ════════════════════════════════════════════════════════════

_PAGE_PATH = _APP_DIR / "app_pages" / "2_AI_Quant_Lab.py"
_spec = importlib.util.spec_from_file_location("_quant_lab_batch", _PAGE_PATH)
_lab = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_lab)
logger.info("AI Quant Lab module loaded (batch mode)")


# ════════════════════════════════════════════════════════════
# 3. Preset configurations
# ════════════════════════════════════════════════════════════

def _common_config() -> dict:
    """Common settings shared across the 3 presets."""
    today = date.today()
    end_dt = today - timedelta(days=1)           # yesterday
    start_dt = date(2023, 1, 1)
    return {
        "cap_tiers": ["Large Cap"],
        "sectors": ["Information Technology"],
        "rebal_m": 1,
        "rolling_w": 12,
        "n_stocks": 5,
        "tc_pct": 0.3,
        "min_dollar_vol": 10_000_000,
        "use_next_open": True,
        "use_surv_fix": True,
        "use_ensemble": False,
        "use_mom_filter": False,
        "use_turnover_buffer": True,
        "start": datetime(start_dt.year, start_dt.month, start_dt.day),
        "end":   datetime(end_dt.year, end_dt.month, end_dt.day),
        "min_test": 5,
    }


PRESETS = {
    "it_invvol": {
        "name": "IT Inverse-Vol (No Cash)",
        "description": "IT 섹터, Inverse-Vol 가중, 현금 없음",
        "overrides": {
            "use_inv_vol_weight": True,
            "use_momentum_weight": False,
            "cash_strategy": "none",
        },
    },
    "it_equal": {
        "name": "IT Equal-Weight (No Cash)",
        "description": "IT 섹터, 균등 가중, 현금 없음",
        "overrides": {
            "use_inv_vol_weight": False,
            "use_momentum_weight": False,
            "cash_strategy": "none",
        },
    },
    "it_invvol_regime": {
        "name": "IT Inverse-Vol + Regime Cash",
        "description": "IT 섹터, Inverse-Vol 가중, HMM 레짐 현금 전략",
        "overrides": {
            "use_inv_vol_weight": True,
            "use_momentum_weight": False,
            "cash_strategy": "combined",
        },
    },
    "it_momentum": {
        "name": "IT Momentum-Weight (No Cash)",
        "description": "IT 섹터, 모멘텀 비례 가중, 현금 없음",
        "overrides": {
            "use_inv_vol_weight": False,
            "use_momentum_weight": True,
            "cash_strategy": "none",
        },
    },
    "it_ensemble": {
        "name": "IT Ensemble + Inv-Vol (No Cash)",
        "description": "IT 섹터, 앙상블 모델 선별, Inverse-Vol 가중, 현금 없음",
        "overrides": {
            "use_ensemble": True,
            "use_inv_vol_weight": True,
            "use_momentum_weight": False,
            "cash_strategy": "none",
        },
    },
}


# ════════════════════════════════════════════════════════════
# 4. Data preparation (reused across presets)
# ════════════════════════════════════════════════════════════

def prepare_shared_data(cfg: dict):
    """Fetch all market data once, reused by the 3 preset backtests."""
    logger.info("=== Preparing shared data ===")
    import pandas as pd
    import yfinance as yf

    # Universe from S&P 1500 filtered by IT + Large Cap
    sp1500_df, _ = _lab.get_sp1500_info()
    cap_filter = sp1500_df[sp1500_df["cap_tier"].isin(cfg["cap_tiers"])]
    universe = cap_filter[cap_filter["sector"].isin(cfg["sectors"])]["ticker"].tolist()
    logger.info("Universe: %d tickers", len(universe))

    # Survivorship bias fix → S&P 500 change history + historical removals
    sp500_changes = None
    current_sp500 = None
    extra_tickers = []
    if cfg.get("use_surv_fix"):
        sp500_changes = _lab.get_sp500_changes()
        current_sp500 = sp1500_df[sp1500_df["cap_tier"] == "Large Cap"]["ticker"].tolist()
        if sp500_changes is not None and not sp500_changes.empty:
            bt_start = pd.Timestamp(cfg["start"])
            removed = sp500_changes[
                (sp500_changes["date"] >= bt_start) &
                (sp500_changes["removed_ticker"] != "")
            ]["removed_ticker"].unique().tolist()
            sel_sectors = set(cfg["sectors"])
            for t in removed:
                m = sp1500_df[sp1500_df["ticker"] == t]
                if not m.empty and m.iloc[0].get("sector", "") in sel_sectors:
                    extra_tickers.append(t)
            extra_tickers = [t for t in extra_tickers if t not in universe]
    all_tickers = list(set(universe + extra_tickers))
    logger.info("All tickers incl. historical: %d", len(all_tickers))

    # Price data (warm-up 400 days)
    data_start = cfg["start"] - timedelta(days=400)
    price_data = _lab.download_price_data(
        tuple(all_tickers),
        data_start.strftime("%Y-%m-%d"),
        cfg["end"].strftime("%Y-%m-%d"),
    )
    logger.info("Prices: %d tickers", len(price_data))
    available = list(price_data.keys())

    # Fundamentals + PIT financials
    fund_map = _lab.get_fundamental_yf(tuple(available))
    logger.info("Fundamentals: %d tickers", sum(1 for v in fund_map.values() if v))
    pit_map = _lab.get_pit_financials(tuple(available))
    logger.info("PIT: %d tickers", sum(1 for v in pit_map.values()
                                         if not v.get("income", pd.DataFrame()).empty))

    # SPY + VIX
    spy_close = None
    vix_close = None
    try:
        spy_df = yf.download(
            "SPY", start=data_start.strftime("%Y-%m-%d"),
            end=cfg["end"].strftime("%Y-%m-%d"),
            auto_adjust=True, progress=False,
        )
        if not spy_df.empty:
            spy_close = spy_df["Close"].squeeze()
    except Exception as e:
        logger.warning("SPY fetch failed: %s", e)
    try:
        vix_df = yf.download(
            "^VIX", start=data_start.strftime("%Y-%m-%d"),
            end=cfg["end"].strftime("%Y-%m-%d"),
            auto_adjust=True, progress=False,
        )
        if not vix_df.empty:
            vix_close = vix_df["Close"].squeeze()
    except Exception as e:
        logger.warning("VIX fetch failed: %s", e)

    # Sector map
    sector_map = {row["ticker"]: row.get("sector", "Unknown")
                  for _, row in sp1500_df.iterrows()}

    # Technical indicators
    tech_map = {}
    for t, ohlcv in price_data.items():
        try:
            tech_map[t] = _lab.calc_all_technical(ohlcv, spy_close=spy_close)
        except Exception:
            pass
    logger.info("Tech indicators: %d tickers", len(tech_map))

    # Rebalance dates
    rebal_dates = _lab.generate_rebalance_dates(cfg["start"], cfg["end"], cfg["rebal_m"])
    logger.info("Rebalance dates: %d", len(rebal_dates))

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
        "available": available,
    }


# ════════════════════════════════════════════════════════════
# 5. Run single preset + extract summary
# ════════════════════════════════════════════════════════════

def _serialize_datetime(v):
    """Convert pandas/datetime to ISO string safely."""
    import pandas as pd
    from datetime import datetime, date
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
    """Convert ticker_df DataFrame → list of dicts (JSON-safe)."""
    import pandas as pd
    import numpy as np
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
    """Convert feature-importance DataFrame → list of dicts w/ date."""
    import pandas as pd
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


def _serialize_full_results(results: dict, cfg: dict) -> dict:
    """Serialize full backtest results to JSON-safe dict.

    Includes port_dates/values, rebal_hist (with ticker_df), cash_history,
    ic records, and per-model feature importance — enough to reconstruct
    all tabs except AI Picks (which needs the trained ML models).
    """
    import pandas as pd
    import numpy as np

    port_dates = [_serialize_datetime(d) for d in results.get("port_dates", [])]
    port_values = [float(v) for v in results.get("port_values", [])]

    # Rebalance history (keep ticker_df as list of dicts)
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
    cash_hist_out = []
    for c in results.get("cash_history", []):
        entry = {}
        for k, v in c.items():
            if k == "regime_probs":
                # list of 3 floats or None
                entry[k] = list(v) if v is not None else None
            elif k == "date":
                entry[k] = _serialize_datetime(v)
            elif isinstance(v, (np.floating, float)) and v is not None:
                entry[k] = float(v) if not np.isinf(v) else None
            else:
                entry[k] = v
        cash_hist_out.append(entry)

    # IC records → list of dicts
    ic_df = results.get("ic_df")
    ic_records = []
    if ic_df is not None and not ic_df.empty:
        for _, row in ic_df.iterrows():
            d = {}
            for col, val in row.items():
                if col == "date":
                    d[col] = _serialize_datetime(val)
                elif pd.isna(val):
                    d[col] = None
                else:
                    try:
                        d[col] = float(val)
                    except Exception:
                        d[col] = val
            ic_records.append(d)

    # Last-rebalance full universe ranking (so cached Summary tab can show
    # all tickers, not just the top N that ended up in the portfolio).
    ranking_out = []
    full_rank_df = results.get("last_full_ranking_df")
    if full_rank_df is not None and not full_rank_df.empty:
        for _, row in full_rank_df.iterrows():
            rec = {"ticker": str(row.get("ticker", ""))}
            for col in ("composite_score", "Mom_1m", "Mom_3m", "Mom_6m",
                        "Mom_12m", "Volatility_30d"):
                if col in full_rank_df.columns:
                    val = row[col]
                    try:
                        rec[col] = None if pd.isna(val) else float(val)
                    except Exception:
                        rec[col] = None
            ranking_out.append(rec)

    return {
        "port_dates": port_dates,
        "port_values": port_values,
        "rebal_hist": rebal_hist_out,
        "cash_history": cash_hist_out,
        "ic_records": ic_records,
        "fimp_data": _serialize_fimp(results.get("fimp_df")),
        "fimp_rf_data": _serialize_fimp(results.get("fimp_rf_df")),
        "fimp_xgb_data": _serialize_fimp(results.get("fimp_xgb_df")),
        "fimp_lgbm_data": _serialize_fimp(results.get("fimp_lgbm_df")),
        "last_full_ranking": ranking_out,
        "use_ensemble": bool(cfg.get("use_ensemble", False)),
        "rebal_m": int(cfg.get("rebal_m", 1)),
        "cash_strategy": cfg.get("cash_strategy", "none"),
    }


def run_single_preset(preset_id: str, preset: dict, common: dict, shared: dict) -> dict:
    """Run one preset backtest and return a compact result dict."""
    import pandas as pd
    import numpy as np

    logger.info("=== Running preset: %s ===", preset_id)
    cfg = dict(common)
    cfg.update(preset["overrides"])

    def _progress(pct, msg=""):
        if msg:
            logger.info("  [%.0f%%] %s", pct * 100, msg)

    results = _lab.run_backtest(
        price_data=shared["price_data"],
        fund_map=shared["fund_map"],
        tech_map=shared["tech_map"],
        rebal_dates=shared["rebal_dates"],
        n_stocks=cfg["n_stocks"],
        tc_pct=cfg["tc_pct"],
        rolling_win=cfg["rolling_w"],
        progress=_progress,
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

    # ── Build summary metrics ────────────────────────────────
    port_dates = results.get("port_dates") or []
    port_values = results.get("port_values") or []
    rebal_hist = results.get("rebal_hist") or []

    # Use calc_metrics from the lab module if available
    summary: dict = {"n_rebalances": len(rebal_hist)}
    try:
        if len(port_values) >= 2:
            port_active = pd.Series(port_values, index=pd.DatetimeIndex(port_dates))
            m = _lab.calc_metrics(port_active, "AI", rf=0.04)

            def _parse(s):
                try:
                    return float(str(s).strip("%").strip("x"))
                except Exception:
                    return None

            summary.update({
                "total_return_pct": _parse(m.get("총수익률")),
                "cagr_pct": _parse(m.get("CAGR")),
                "sharpe": _parse(m.get("Sharpe")),
                "sortino": _parse(m.get("Sortino")),
                "max_dd_pct": _parse(m.get("Max DD")),
                "monthly_win_rate_pct": _parse(m.get("월승률")),
                "volatility_pct": _parse(m.get("변동성")),
            })
    except Exception as e:
        logger.warning("Metrics calc failed: %s", e)

    # Additional quality stats from rebal history
    if rebal_hist:
        prets = [h["port_return"] for h in rebal_hist]
        wins = sum(1 for r in prets if r > 0)
        summary["rebal_win_rate_pct"] = round(wins / len(prets) * 100, 2) if prets else None
        summary["avg_period_return_pct"] = (
            round(float(np.mean(prets)) * 100, 2) if prets else None
        )

        # Selection quality
        excess = [h["port_return"] - h.get("univ_avg_ret", 0)
                  for h in rebal_hist if not pd.isna(h.get("univ_avg_ret"))]
        if excess:
            summary["avg_excess_return_pct"] = round(float(np.mean(excess)) * 100, 2)

        # Profit factor
        gains = sum(r for r in prets if r > 0)
        losses = sum(abs(r) for r in prets if r < 0)
        summary["profit_factor"] = (
            round(gains / losses, 2) if losses > 0
            else (999 if gains > 0 else 0)
        )

        # Cash allocation stats
        cash_hist = results.get("cash_history") or []
        if cash_hist and cfg["cash_strategy"] != "none":
            cash_vals = [c.get("cash_ratio", 0) for c in cash_hist]
            regimes = [c.get("regime", "N/A") for c in cash_hist]
            summary["avg_cash_pct"] = round(float(np.mean(cash_vals)) * 100, 2)
            summary["max_cash_pct"] = round(float(max(cash_vals)) * 100, 2)
            summary["bull_regime_pct"] = round(
                sum(1 for r in regimes if r == "Bull") / len(regimes) * 100, 1
            )
            summary["bear_regime_pct"] = round(
                sum(1 for r in regimes if r == "Bear") / len(regimes) * 100, 1
            )

    # ── Latest AI picks (last rebalance) ─────────────────────
    latest_picks = []
    if rebal_hist:
        last = rebal_hist[-1]
        tdf = last.get("ticker_df")
        if tdf is not None and not tdf.empty:
            pick_cols = ["ticker", "비중", "평균순위", "예측수익률", "실제수익률"]
            show = [c for c in pick_cols if c in tdf.columns]
            for _, row in tdf[show].iterrows():
                pick = {}
                for c in show:
                    v = row[c]
                    if pd.isna(v):
                        pick[c] = None
                    elif isinstance(v, (int, float)):
                        pick[c] = round(float(v), 4)
                    else:
                        pick[c] = str(v)
                latest_picks.append(pick)

    # Latest regime / cash
    last_cash = None
    last_regime = None
    if rebal_hist:
        last = rebal_hist[-1]
        last_cash = last.get("cash_ratio")
        last_regime = last.get("regime")

    # ── Compact config record (serializable) ─────────────────
    record_cfg = {
        k: (v.isoformat() if isinstance(v, (datetime, date)) else v)
        for k, v in cfg.items()
    }

    # ── Full backtest data (for AI Quant Lab preset loading) ─
    try:
        full_data = _serialize_full_results(results, cfg)
    except Exception as e:
        logger.warning("Full serialization failed for %s: %s", preset_id, e)
        full_data = {}

    # ── Today's forward picks (the actual recommendation for now) ──
    # Use the model trained at the last rebalance to predict on TODAY's
    # snapshot. Distinct from `latest_picks` (which is the last historical
    # rebalance's holdings).
    try:
        today_picks_data = _predict_today(
            results, shared, cfg, n_stocks=cfg["n_stocks"], np=np, pd=pd
        )
    except Exception as e:
        logger.warning("Today-prediction failed for %s: %s", preset_id, e)
        today_picks_data = {}

    return {
        "preset_id": preset_id,
        "name": preset["name"],
        "description": preset["description"],
        "config": record_cfg,
        "summary": summary,
        "last_rebalance_date": (
            rebal_hist[-1]["rebalance_date"].strftime("%Y-%m-%d")
            if rebal_hist else None
        ),
        "last_regime": last_regime,
        "last_cash_ratio_pct": (
            round(last_cash * 100, 1) if last_cash is not None else None
        ),
        "latest_picks": latest_picks,
        # Today's forward prediction (NEW)
        "today_picks": today_picks_data.get("picks", []),
        "today_full_ranking": today_picks_data.get("full_ranking", []),
        "today_picks_at": today_picks_data.get("picks_at"),
        "today_regime": today_picks_data.get("regime"),
        "today_cash_ratio_pct": today_picks_data.get("cash_ratio_pct"),
        # Full data for Streamlit reconstruction (~100-300KB)
        "full": full_data,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _predict_today(results: dict, shared: dict, cfg: dict, n_stocks: int,
                    np, pd) -> dict:
    """Apply the last-trained model to today's snapshot for forward picks.

    Returns dict with keys: picks (list), full_ranking (list), picks_at (str),
    regime (str|None), cash_ratio_pct (float|None).
    """
    today = pd.Timestamp.today().normalize()
    out: dict = {"picks_at": today.isoformat()}

    model_rf = results.get("last_model_rf")
    last_imputer = results.get("last_imputer")
    last_avail_cols = results.get("last_avail_cols", [])
    last_all_cols = results.get("last_all_cols", [])
    last_win_bounds = results.get("last_win_bounds", {})
    last_miss_src = results.get("last_miss_src", [])
    if model_rf is None or last_imputer is None or not last_all_cols:
        logger.warning("predict_today: missing model artifacts")
        return out

    # Build today's snapshot using the same pipeline as backtest
    universe = list(shared["price_data"].keys())
    snap = _lab.build_snapshot_df(
        universe, shared["tech_map"], shared["fund_map"], today,
        pit_map=shared["pit_map"], price_data=shared["price_data"],
        backtest_mode=False,
    )
    if snap.empty:
        logger.warning("predict_today: empty snapshot")
        return out
    snap = _lab.enrich_snapshot(
        snap, today,
        spy_close=shared["spy_close"],
        vix_close=shared["vix_close"],
        sector_map=shared["sector_map"],
    )

    # Same preprocessing as live AI Picks (winsorize, miss-flag, impute)
    avail = [c for c in last_avail_cols if c in snap.columns]
    X_pred = snap[avail].reindex(columns=last_avail_cols)
    for col in last_avail_cols:
        if col in last_win_bounds and col in X_pred.columns:
            lo, hi = last_win_bounds[col]
            X_pred[col] = X_pred[col].clip(lo, hi)
    for mc in last_miss_src:
        X_pred[f"{mc}_miss"] = (
            X_pred[mc].isna().astype(int) if mc in X_pred.columns else 0
        )
    X_pred = X_pred.reindex(columns=last_all_cols)
    X_imp = last_imputer.transform(X_pred)

    # Predict (ensemble or single)
    pred_rf_s = pd.Series(model_rf.predict(X_imp), index=snap.index)
    is_ensemble = bool(cfg.get("use_ensemble", False))
    model_xgb = results.get("last_model_xgb")
    model_lgbm = results.get("last_model_lgbm")
    if is_ensemble and model_xgb is not None and model_lgbm is not None:
        pred_xgb_s = pd.Series(model_xgb.predict(X_imp), index=snap.index)
        pred_lgbm_s = pd.Series(model_lgbm.predict(X_imp), index=snap.index)
        rk = (pred_rf_s.rank(ascending=False) +
              pred_xgb_s.rank(ascending=False) +
              pred_lgbm_s.rank(ascending=False)) / 3
        composite = -rk
    else:
        composite = pred_rf_s

    # Mom filter
    if cfg.get("use_mom_filter", False) and "Mom_1m" in snap.columns:
        mom_ok = snap["Mom_1m"] > 0
        filt = composite[composite.index.isin(snap[mom_ok].index)]
        top = filt.nlargest(n_stocks) if len(filt) >= n_stocks else composite.nlargest(n_stocks)
    else:
        top = composite.nlargest(n_stocks)

    # Weights
    if cfg.get("use_inv_vol_weight", False) and "Volatility_30d" in snap.columns:
        vols = {}
        for t in top.index:
            v = snap.loc[t, "Volatility_30d"] if t in snap.index else np.nan
            vols[t] = v if (not pd.isna(v) and v > 0) else 0.30
        inv_v = {t: 1.0 / v for t, v in vols.items()}
        total = sum(inv_v.values())
        weights = {t: iv / total for t, iv in inv_v.items()}
    elif cfg.get("use_momentum_weight", False):
        mom_s = {}
        for t in top.index:
            m3  = float(snap.loc[t, "Mom_3m"])  if ("Mom_3m"  in snap.columns and t in snap.index and not pd.isna(snap.loc[t, "Mom_3m"]))  else 0.0
            m6  = float(snap.loc[t, "Mom_6m"])  if ("Mom_6m"  in snap.columns and t in snap.index and not pd.isna(snap.loc[t, "Mom_6m"]))  else 0.0
            m12 = float(snap.loc[t, "Mom_12m"]) if ("Mom_12m" in snap.columns and t in snap.index and not pd.isna(snap.loc[t, "Mom_12m"])) else 0.0
            mom_s[t] = max(0.4 * m3 + 0.3 * m6 + 0.3 * m12, 0.0)
        total_ms = sum(mom_s.values())
        weights = {t: s / total_ms for t, s in mom_s.items()} if total_ms > 0 else {t: 1.0 / max(len(top), 1) for t in top.index}
    else:
        w = 1.0 / max(len(top), 1)
        weights = {t: w for t in top.index}

    # Build picks list
    def _safe(v):
        try:
            return None if pd.isna(v) else float(v)
        except Exception:
            return None

    picks = []
    for t in top.index:
        row = {
            "ticker": str(t),
            "weight": float(weights.get(t, 0.0)),
            "composite_score": _safe(composite[t]),
        }
        for col in ("Mom_1m", "Mom_3m", "Mom_6m", "Mom_12m", "Volatility_30d"):
            if col in snap.columns:
                row[col] = _safe(snap.loc[t, col])
        picks.append(row)
    out["picks"] = picks

    # Full universe ranking
    ranking = []
    for t, s in composite.sort_values(ascending=False).items():
        row = {"ticker": str(t), "composite_score": _safe(s)}
        for col in ("Mom_1m", "Mom_3m", "Mom_6m", "Mom_12m", "Volatility_30d"):
            if col in snap.columns:
                row[col] = _safe(snap.loc[t, col])
        ranking.append(row)
    out["full_ranking"] = ranking

    # Regime + cash ratio (only if cash strategy enabled)
    cash_strat = cfg.get("cash_strategy", "none")
    if cash_strat != "none" and shared.get("spy_close") is not None:
        try:
            spy_close = shared["spy_close"]
            past_returns = spy_close.pct_change().dropna()
            past_returns = past_returns[past_returns.index <= today]
            if len(past_returns) > 60:
                hmm = _lab._fit_hmm_regimes(past_returns)
                regime_info = _lab._get_regime_at_date(hmm, spy_close, today)
                pf_vol = _lab._calc_portfolio_vol(
                    shared["price_data"], weights, today
                )
                if cash_strat == "vol_target":
                    cash = round(max(1.0 - 0.15 / pf_vol, 0), 4)
                elif cash_strat == "regime":
                    cash = {0: 0.60, 1: 0.20, 2: 0.0}.get(regime_info["regime"], 0.0)
                else:  # combined
                    cash = _lab._calc_cash_ratio(regime_info, pf_vol)
                out["regime"] = regime_info["label"]
                out["cash_ratio_pct"] = round(min(cash, 0.90) * 100, 1)
        except Exception as e:
            logger.warning("today regime/cash calc failed: %s", e)

    logger.info(
        "  Today picks (%s): %d tickers @ %s",
        cfg.get("name", "?"), len(picks), today.date()
    )
    return out


# ════════════════════════════════════════════════════════════
# 6. Main
# ════════════════════════════════════════════════════════════

def main() -> int:
    cache_dir = _APP_DIR / "data" / "cache" / "backtests"
    cache_dir.mkdir(parents=True, exist_ok=True)

    common = _common_config()
    logger.info(
        "Period: %s → %s (rebal=%dm, rolling=%d)",
        common["start"].date(), common["end"].date(),
        common["rebal_m"], common["rolling_w"],
    )

    # Shared data (1 fetch used by 3 presets)
    try:
        shared = prepare_shared_data(common)
    except Exception as e:
        logger.exception("Data prep failed: %s", e)
        return 1

    results_by_id: dict[str, dict] = {}
    failures: list[str] = []

    for pid, preset in PRESETS.items():
        try:
            r = run_single_preset(pid, preset, common, shared)
            out_path = cache_dir / f"{pid}.json"
            out_path.write_text(
                json.dumps(r, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            logger.info("Saved %s", out_path.name)
            results_by_id[pid] = r
        except Exception as e:
            logger.exception("Preset %s failed: %s", pid, e)
            failures.append(pid)

    # Metadata
    meta = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "common_config": {
            k: (v.isoformat() if isinstance(v, (datetime, date)) else v)
            for k, v in common.items()
        },
        "presets": {
            pid: {
                "name": p["name"],
                "description": p["description"],
                "success": pid in results_by_id,
                "updated_at": results_by_id.get(pid, {}).get("updated_at"),
            }
            for pid, p in PRESETS.items()
        },
        "failures": failures,
    }
    (cache_dir / "_metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Done. %d success, %d failures", len(results_by_id), len(failures))

    # ── Telegram 결과 알림 ──────────────────────────────────
    kst_now = datetime.now().strftime("%m/%d %H:%M")
    if failures:
        _notify_telegram(
            f"⚠️ *프리셋 백테스트 일부 실패* ({kst_now} KST)\n"
            f"❌ 실패: `{'`, `'.join(failures)}`\n"
            f"✅ 성공: `{'`, `'.join(results_by_id.keys()) or '없음'}`\n"
            f"로그를 확인하세요."
        )
    else:
        _notify_telegram(
            f"✅ *프리셋 백테스트 완료* ({kst_now} KST)\n"
            + "\n".join(
                f"• {r['name']}: CAGR {r['summary'].get('cagr_pct', '?')}%"
                for r in results_by_id.values()
            )
        )

    # ── Git push (서버 동기화) ─────────────────────────────
    try:
        import subprocess as _sp
        _repo = Path(__file__).resolve().parents[2]
        _files = [
            "streamlit_app/data/cache/backtests/_metadata.json",
            "streamlit_app/data/cache/backtests/it_invvol.json",
            "streamlit_app/data/cache/backtests/it_equal.json",
            "streamlit_app/data/cache/backtests/it_invvol_regime.json",
            "streamlit_app/data/cache/backtests/it_momentum.json",
            "streamlit_app/data/cache/backtests/it_ensemble.json",
        ]
        _sp.run(["git", "add"] + _files, cwd=_repo, check=True)
        _sp.run(
            ["git", "commit", "-m",
             f"chore: refresh preset backtest cache [skip ci] ({kst_now} KST)"],
            cwd=_repo, check=True,
        )
        # Integrate any remote commits (GitHub Actions valuation cache, etc.)
        # before pushing — otherwise the push is rejected as non-fast-forward.
        # merge -X ours keeps our fresh local cache on conflict while preserving
        # remote-only files. core.protectNTFS=false + sparse-checkout (set on this
        # machine) let the merge tolerate the Windows-illegal valuation/CON.json.
        _sp.run(["git", "fetch", "origin"], cwd=_repo, check=True)
        _sp.run(["git", "merge", "-X", "ours", "origin/main", "--no-edit"],
                cwd=_repo, check=True)
        _sp.run(["git", "push", "origin", "main"], cwd=_repo, check=True)
        logger.info("Git push complete.")
    except Exception as _git_e:
        logger.warning("Git push failed (non-critical): %s", _git_e)

    return 0 if not failures else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
