"""Precompute the Factor Lab (rule-based) backtest grid.

The web app used to POST each rule-based backtest to the Render API, which
re-ran the strategy on request. After the universe grew to the S&P 1500 a
single request takes 2+ minutes there (70x slower than this Mac), so the
page became unusable. Like the AI-ensemble presets, the grid is now computed
here every night and published as JSON; the page only reads files.

Engine: api/factor_backtest.py — the same code the API serves, so a
precomputed result equals what the API would have returned for the same
config. Input: data/cache/backtest_data/ (written by cache_backtest_data.py).

Grid (per enabled strategy):
    cap tier        all | Large Cap
    rebalance       1m | 3m
    holdings        5 | 10 | 20
    period          2023-01-01 → data end, tc 0.3%, all sectors
→ 12 variants × ~25 strategies ≈ 300 runs, a few seconds each.

Output: data/cache/factor_backtests/<strategy>/<cap>_<rebal>m_<n>.json
plus _index.json (metrics for every variant, for the comparison table).
Equity curves are stored as parallel arrays to keep the files small.

Env:
    FACTOR_OUTPUT_DIR    override the output dir (dry runs)
    FACTOR_STRATEGIES    comma-separated strategy keys (default: all enabled)
"""

from __future__ import annotations

import json
import logging
import math
import os
import sys
import time
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("factor-backtests")

_APP_DIR = Path(__file__).resolve().parent.parent
_REPO = _APP_DIR.parent
sys.path.insert(0, str(_REPO / "api"))
sys.path.insert(0, str(_APP_DIR))

import factor_backtest as fb  # noqa: E402  (api/)
from services.factor_strategies import list_strategies  # noqa: E402

START_DATE = date(2023, 1, 1)
CAP_TIERS = [("all", None), ("large", "Large Cap")]
REBALANCE_MONTHS = [1, 3]
N_STOCKS = [5, 10, 20]
TC_PCT = 0.3

OUT_DIR = Path(os.environ.get("FACTOR_OUTPUT_DIR", "").strip()
               or _APP_DIR / "data" / "cache" / "factor_backtests")


def variant_id(cap_slug: str, rebal: int, n: int) -> str:
    return f"{cap_slug}_{rebal}m_{n}"


def _json_safe(o):
    """NaN/inf → null, numpy scalars → Python, so the browser can parse it."""
    if isinstance(o, (np.floating, float)):
        f = float(o)
        return f if math.isfinite(f) else None
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, dict):
        return {k: _json_safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_json_safe(v) for v in o]
    return o


def compact_result(res: fb.FactorBacktestResult, cfg: fb.FactorBacktestConfig) -> dict:
    d = asdict(res)
    curve = d.pop("equity_curve") or []
    d["equity"] = {
        "dates": [p["date"] for p in curve],
        "portfolio": [p.get("portfolio") for p in curve],
        "spy": [p.get("spy") for p in curve],
    }
    d["config"] = {
        "strategy_key": cfg.strategy_key,
        "start_date": cfg.start_date.isoformat(),
        "end_date": cfg.end_date.isoformat(),
        "rebalance_months": cfg.rebalance_months,
        "n_stocks": cfg.n_stocks,
        "tc_pct": cfg.tc_pct,
        "cap_tier": cfg.cap_tier,
    }
    return _json_safe(d)


def main() -> int:
    manifest_path = _APP_DIR / "data" / "cache" / "backtest_data" / "_manifest.json"
    if not manifest_path.exists():
        logger.error("backtest_data manifest missing — run cache_backtest_data.py first")
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    data_end = date.fromisoformat(manifest["data_end"])
    logger.info("Data as of %s (%s tickers)", data_end, manifest.get("tickers_count"))

    strategies = list_strategies()
    only = {s.strip() for s in os.environ.get("FACTOR_STRATEGIES", "").split(",") if s.strip()}
    if only:
        strategies = [s for s in strategies if s.key in only]
    logger.info("%d strategies × %d variants", len(strategies),
                len(CAP_TIERS) * len(REBALANCE_MONTHS) * len(N_STOCKS))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    index: dict = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "data_as_of": data_end.isoformat(),
        "start_date": START_DATE.isoformat(),
        "end_date": data_end.isoformat(),
        "tc_pct": TC_PCT,
        "variants": {
            "cap_tiers": [{"id": slug, "label": label or "전체"} for slug, label in CAP_TIERS],
            "rebalance_months": REBALANCE_MONTHS,
            "n_stocks": N_STOCKS,
        },
        "strategies": {},
    }
    ok = failed = 0
    t_all = time.time()
    for strat in strategies:
        entry = {"name": strat.name, "category": strat.category, "variants": {}}
        sdir = OUT_DIR / strat.key
        sdir.mkdir(exist_ok=True)
        t_s = time.time()
        for cap_slug, cap_tier in CAP_TIERS:
            for rebal in REBALANCE_MONTHS:
                for n in N_STOCKS:
                    vid = variant_id(cap_slug, rebal, n)
                    cfg = fb.FactorBacktestConfig(
                        strategy_key=strat.key, start_date=START_DATE, end_date=data_end,
                        rebalance_months=rebal, n_stocks=n, tc_pct=TC_PCT,
                        sector=None, cap_tier=cap_tier,
                    )
                    try:
                        res = fb.run_factor_backtest(cfg)
                        if not res.rebalance_history:
                            # The API engine lacks a feature this strategy
                            # needs (Tier-B PIT columns only the Streamlit
                            # service computes) — an empty curve is not a
                            # result, so leave it out of the grid.
                            raise RuntimeError("no rebalances (missing feature?)")
                        payload = compact_result(res, cfg)
                        (sdir / f"{vid}.json").write_text(
                            json.dumps(payload, ensure_ascii=False, separators=(",", ":"),
                                       allow_nan=False),
                            encoding="utf-8",
                        )
                        entry["variants"][vid] = {
                            "metrics": payload["metrics"],
                            "spy": (payload.get("benchmark_metrics") or {}).get("SPY", {}),
                            "universe_size": payload["universe_size"],
                            "n_rebalances": len(payload["rebalance_history"]),
                            "final_picks": payload["final_picks"],
                            "final_picks_date": payload["final_picks_date"],
                        }
                        ok += 1
                    except Exception as e:
                        logger.warning("%s/%s failed: %s", strat.key, vid, e)
                        failed += 1
        if entry["variants"]:
            index["strategies"][strat.key] = entry
        else:
            logger.warning("%-20s skipped — no usable variants", strat.key)
        logger.info("%-20s %d variants in %.0fs", strat.key, len(entry["variants"]), time.time() - t_s)

    if ok == 0:
        logger.error("Every run failed — leaving the previous index in place")
        return 1
    (OUT_DIR / "_index.json").write_text(
        json.dumps(index, ensure_ascii=False, separators=(",", ":"), allow_nan=False),
        encoding="utf-8",
    )
    total_kb = sum(p.stat().st_size for p in OUT_DIR.rglob("*.json")) / 1024
    logger.info("Done: %d ok, %d failed, %.0f KB, %.0f min",
                ok, failed, total_kb, (time.time() - t_all) / 60)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
