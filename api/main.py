"""AI Quant Lab API — on-demand backtest execution.

FastAPI service that wraps the Streamlit AI Quant Lab backtest engine so it
can be called from the Next.js web app (`aiquantlab-web`).

Endpoints:
  GET  /              → basic status
  GET  /health        → health check (used by Render)
  POST /backtest      → run a backtest with user-provided config

Deployment: Render.com blueprint (see repo-root `render.yaml`).
"""

from __future__ import annotations

import logging
import os
import traceback
from datetime import datetime
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from lab_bridge import prepare_shared_data, run_backtest, serialize_results
from factor_backtest import (
    FactorBacktestConfig,
    list_strategies,
    run_factor_backtest,
)
import finnhub_proxy

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


app = FastAPI(
    title="AI Quant Lab API",
    version="0.1.0",
    description="On-demand backtest execution for aiquantlab-web",
)

# CORS: allow the web app to call this API from the browser.
# Configure via env var so dev (localhost) and prod (vercel) both work.
_allowed_origins = os.environ.get(
    "CORS_ALLOW_ORIGINS",
    "http://localhost:3000,https://aiquantlab-web.vercel.app",
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _allowed_origins if o.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ── Request/response models ───────────────────────────────────────


class BacktestRequest(BaseModel):
    """User-supplied backtest configuration. Matches the JSON produced by
    `aiquantlab-web`'s config form (which itself mirrors the Streamlit form)."""

    cap_tiers: list[str] = Field(default_factory=lambda: ["Large Cap"])
    sectors: list[str] = Field(default_factory=lambda: ["Information Technology"])
    rebal_m: int = Field(default=1, ge=1, le=12)
    rolling_w: int = Field(default=12, ge=2, le=24)
    n_stocks: int = Field(default=5, ge=1, le=20)
    tc_pct: float = Field(default=0.3, ge=0, le=5)
    min_dollar_vol: int = Field(default=10_000_000, ge=0)
    use_next_open: bool = True
    use_surv_fix: bool = True
    use_ensemble: bool = False
    use_mom_filter: bool = False
    use_turnover_buffer: bool = True
    start: str = "2023-01-01T00:00:00"
    end: str = "2026-08-20T00:00:00"
    min_test: int = 5
    use_inv_vol_weight: bool = False
    use_momentum_weight: bool = False
    cash_strategy: Literal["none", "vol_target", "regime", "combined"] = "none"


# ── Endpoints ────────────────────────────────────────────────────


@app.get("/")
def root():
    return {
        "service": "aiquantlab-api",
        "version": "0.1.0",
        "endpoints": ["/health", "POST /backtest"],
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/cache/manifest")
def cache_manifest():
    """Returns _manifest.json — useful to verify what data the API sees.
    404 if cache hasn't been generated yet."""
    import cache_loader
    try:
        return cache_loader.load_manifest()
    except cache_loader.CacheMissing as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/debug/paths")
def debug_paths():
    """Diagnostic: what does the API service actually see on disk?
    Helps confirm whether Render cloned the whole repo or only api/."""
    import os
    from pathlib import Path
    from cache_loader import CACHE_DIR

    here = Path(__file__).resolve()
    root = here.parent.parent
    return {
        "cwd": os.getcwd(),
        "__file__": str(here),
        "computed_repo_root": str(root),
        "cache_dir": str(CACHE_DIR),
        "cache_dir_exists": CACHE_DIR.exists(),
        "cache_dir_contents": (
            [str(p.relative_to(CACHE_DIR)) for p in CACHE_DIR.iterdir()]
            if CACHE_DIR.exists() else []
        ),
        "repo_root_top_level": sorted([p.name for p in root.iterdir()]) if root.exists() else [],
        "streamlit_app_exists": (root / "streamlit_app").exists(),
        "streamlit_app_data_exists": (root / "streamlit_app" / "data").exists(),
    }


@app.post("/backtest")
def run_backtest_endpoint(req: BacktestRequest):
    """Run a full backtest. Cold-start requests can take 5-10 min while data
    is prefetched from yfinance; subsequent requests reuse the in-memory cache."""
    stage = "init"
    try:
        cfg = req.model_dump()
        cfg["start"] = datetime.fromisoformat(cfg["start"])
        cfg["end"] = datetime.fromisoformat(cfg["end"])
        logger.info("Received backtest request: %s", cfg)

        stage = "prepare_shared_data"
        logger.info("[%s] starting", stage)
        shared = prepare_shared_data(cfg)
        logger.info("[%s] done — rebal_dates=%d, price_data=%d",
                    stage, len(shared.get("rebal_dates") or []),
                    len(shared.get("price_data") or {}))

        stage = "run_backtest"
        logger.info("[%s] starting", stage)
        results = run_backtest(cfg, shared)
        logger.info("[%s] done", stage)

        stage = "serialize_results"
        results_out = serialize_results(results, dict(cfg))
        logger.info("[%s] done", stage)
        return results_out
    except Exception as e:
        tb = traceback.format_exc()
        logger.exception("Backtest failed at stage=%s", stage)
        # Return the type + repr so cryptic errors like "3" become
        # "KeyError: 3" and traceback tail for quick debugging.
        detail = {
            "stage": stage,
            "type": type(e).__name__,
            "message": repr(e),
            "traceback": tb.splitlines()[-15:],  # last 15 lines
        }
        raise HTTPException(status_code=500, detail=detail)


# ─────── Factor Lab (rule-based) — much lighter than AI Quant Lab ───────


class FactorBacktestRequest(BaseModel):
    """Config for rule-based factor backtest (mirrors Streamlit Factor Lab form)."""
    strategy_key: str
    start_date: str                       # "YYYY-MM-DD"
    end_date: str                         # "YYYY-MM-DD"
    rebalance_months: int = 3
    n_stocks: int = 20
    tc_pct: float = 0.3
    sector: str | None = None             # None = all sectors
    cap_tier: str | None = None            # None = all tiers


@app.get("/factor-backtest/strategies")
def factor_strategies():
    """List all registered factor strategies (for the UI dropdown)."""
    return list_strategies()


@app.post("/factor-backtest")
def run_factor_backtest_endpoint(req: FactorBacktestRequest):
    """Run a rule-based factor backtest. Much lighter than AI Quant Lab
    (no ML training loop). Typical runtime: 5-15 seconds."""
    try:
        cfg = FactorBacktestConfig(
            strategy_key=req.strategy_key,
            start_date=datetime.fromisoformat(req.start_date).date(),
            end_date=datetime.fromisoformat(req.end_date).date(),
            rebalance_months=req.rebalance_months,
            n_stocks=req.n_stocks,
            tc_pct=req.tc_pct,
            sector=req.sector,
            cap_tier=req.cap_tier,
        )
        logger.info("Factor backtest: %s (%s)", req.strategy_key, req.sector or "all sectors")
        result = run_factor_backtest(cfg)
        return {
            "strategy_name": result.strategy_name,
            "strategy_category": result.strategy_category,
            "equity_curve": result.equity_curve,
            "rebalance_history": result.rebalance_history,
            "metrics": result.metrics,
            "benchmark_metrics": result.benchmark_metrics,
            "universe_size": result.universe_size,
            "final_picks": result.final_picks,
            "final_picks_date": result.final_picks_date,
            "warnings": result.warnings,
        }
    except Exception as e:
        tb = traceback.format_exc()
        logger.exception("Factor backtest failed")
        raise HTTPException(status_code=500, detail={
            "type": type(e).__name__,
            "message": repr(e),
            "traceback": tb.splitlines()[-15:],
        })


# ─────── Finnhub proxy (key stays on server) ───────


def _finnhub_call(fn, *args, **kwargs):
    """Common error wrapper so the browser gets a clean 4xx/5xx JSON."""
    try:
        return fn(*args, **kwargs)
    except RuntimeError as e:
        msg = str(e)
        # Missing key → 503 so the client can render a "not configured" state
        # distinctly from an actual server error.
        if "not configured" in msg:
            raise HTTPException(status_code=503, detail=msg)
        raise HTTPException(status_code=502, detail=msg)
    except Exception as e:
        logger.exception("Finnhub proxy call failed")
        raise HTTPException(status_code=500, detail=repr(e))


@app.get("/finnhub/earnings-calendar")
def finnhub_earnings(from_date: str, to_date: str, symbol: str | None = None):
    """Earnings calendar. ISO dates (YYYY-MM-DD), max ~1 month range."""
    return _finnhub_call(finnhub_proxy.earnings_calendar, from_date, to_date, symbol)


@app.get("/finnhub/economic-calendar")
def finnhub_economic(from_date: str, to_date: str):
    """Macro events (CPI, FOMC, NFP, etc.)."""
    return _finnhub_call(finnhub_proxy.economic_calendar, from_date, to_date)


@app.get("/finnhub/company-news")
def finnhub_company_news(symbol: str, from_date: str, to_date: str):
    """Per-ticker news."""
    return _finnhub_call(finnhub_proxy.company_news, symbol, from_date, to_date)


@app.get("/finnhub/market-news")
def finnhub_market_news(category: str = "general"):
    """General market news."""
    return _finnhub_call(finnhub_proxy.market_news, category)


@app.get("/finnhub/recommendation")
def finnhub_recommendation(symbol: str):
    """Analyst rating trend for a ticker."""
    return _finnhub_call(finnhub_proxy.recommendation_trend, symbol)


@app.get("/finnhub/price-target")
def finnhub_price_target(symbol: str):
    """Analyst consensus price target."""
    return _finnhub_call(finnhub_proxy.price_target, symbol)
