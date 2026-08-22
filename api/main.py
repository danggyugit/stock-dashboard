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
