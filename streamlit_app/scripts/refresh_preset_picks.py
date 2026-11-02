"""Daily refresh of the AI-ensemble presets' "today's picks".

The full preset matrix (run_preset_backtests.py) re-runs 55 backtests from
2012 and takes hours, so it runs weekly. The model that produces today's
picks only changes at a monthly rebalance anyway: this script loads the
models saved by the last full run, builds today's snapshot from the fresh
price/fundamentals cache, re-scores the universe and rewrites only the
`today_*` fields of each preset JSON (summary, equity curve and history
stay as computed by the weekly run). It also appends the forward-test log
so out-of-sample evaluation keeps one row per preset per day.

Shares all plumbing with run_preset_backtests.py (universe, membership,
PIT, _predict_today, metadata, git push). Honors PRESET_NO_PUSH and the
PRESET_SECTOR_FILTER / PRESET_STRATEGY_FILTER env vars.
"""

from __future__ import annotations

import gzip
import importlib.util
import json
import logging
import pickle
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("preset-picks")

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("run_preset_backtests", _HERE / "run_preset_backtests.py")
rpb = importlib.util.module_from_spec(_spec)
sys.modules["run_preset_backtests"] = rpb
_spec.loader.exec_module(rpb)


def _load_artifacts(pid: str) -> dict | None:
    path = rpb.MODELS_DIR / f"{pid}.pkl.gz"
    if not path.exists():
        return None
    with gzip.open(path, "rb") as f:
        return pickle.load(f)


def main() -> int:
    import numpy as np
    import pandas as pd

    cache_dir = (Path(rpb._OUTPUT_DIR_ENV) if rpb._OUTPUT_DIR_ENV
                 else rpb._APP_DIR / "data" / "cache" / "backtests")
    common_base = rpb._common_config()

    by_sector: dict[tuple, list] = defaultdict(list)
    for pid, preset in rpb.PRESETS.items():
        by_sector[tuple(preset["sectors"])].append((pid, preset))

    updated: dict[str, dict] = {}
    skipped: list[str] = []
    for sector_tuple, presets in by_sector.items():
        common = dict(common_base)
        common["sectors"] = list(sector_tuple)
        try:
            shared = rpb.prepare_shared_data(common)
        except Exception as e:
            logger.exception("Sector prefetch failed (%s): %s", sector_tuple, e)
            skipped += [pid for pid, _ in presets]
            continue
        if not shared["tech_map"]:
            logger.error("Sector %s: empty inputs — skipping", sector_tuple[0])
            skipped += [pid for pid, _ in presets]
            continue
        for pid, preset in presets:
            art = _load_artifacts(pid)
            out_path = cache_dir / f"{pid}.json"
            if art is None or not out_path.exists():
                logger.warning("%s: no saved model or result — run the full matrix first", pid)
                skipped.append(pid)
                continue
            cfg = dict(common)
            cfg.update(preset["overrides"])
            try:
                picks = rpb._predict_today(art, shared, cfg, n_stocks=cfg["n_stocks"], np=np, pd=pd)
            except Exception as e:
                logger.exception("%s: prediction failed: %s", pid, e)
                skipped.append(pid)
                continue
            result = json.loads(out_path.read_text(encoding="utf-8"))
            result["today_picks"] = picks.get("picks", [])
            result["today_full_ranking"] = picks.get("full_ranking", [])
            result["today_picks_at"] = picks.get("picks_at")
            result["today_regime"] = picks.get("regime")
            result["today_cash_ratio_pct"] = picks.get("cash_ratio_pct")
            result["picks_model_trained_at"] = art.get("trained_at")
            result["updated_at"] = datetime.now(timezone.utc).isoformat()
            out_path.write_text(
                json.dumps(rpb._json_safe(result), ensure_ascii=False, indent=2,
                           default=str, allow_nan=False),
                encoding="utf-8",
            )
            updated[pid] = result
            if not rpb.NO_PUSH:
                try:
                    rpb._append_forward_test_log(pid, result)
                except Exception as e:
                    logger.warning("Forward log append failed (%s): %s", pid, e)
            logger.info("%s: %d picks (model of %s)", pid, len(result["today_picks"]),
                        art.get("last_rebalance_date"))

    if updated:
        rpb._write_metadata(cache_dir, common_base, updated, skipped, partial=True)
    logger.info("Done. %d presets refreshed, %d skipped", len(updated), len(skipped))
    if not updated:
        return 1
    rpb._git_commit_and_push("daily picks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
