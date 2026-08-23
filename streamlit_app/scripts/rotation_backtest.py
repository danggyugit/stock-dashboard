"""Two-stage sector rotation post-processor.

Reads every ``data/cache/backtests/{sector}_{strategy}.json`` written by
``run_preset_backtests.py`` and simulates a two-stage strategy:

  Stage 1 (top-down) — at each rebalance date T, rank the 10 sectors by
    a rule that uses only info available AT T.
  Stage 2 (bottom-up) — take the ``selected`` picks the ranked sectors
    already produced, aggregate them equal-weight across sectors, then
    the sector's own weights within.

Zero incremental model training — everything below is a projection of
per-sector snapshots already committed to git.

Rules ranked:
  * ``mom_1m``  — trailing 1-rebalance sector-strategy portfolio return
  * ``mom_3m``  — trailing 3-rebalance sector-strategy portfolio return
  * ``conf``    — average ``pred_mean`` of that day's top-N picks (model
                  self-confidence on the sector)

Aggregations tested per rule:
  * ``top1``    — best sector, use its 5 picks (matches n_stocks base)
  * ``top3``    — 3 best sectors, equal-weight across sectors

Output: ``data/cache/rotation/eval_{strategy}.json`` per strategy — the
same shape as a normal preset JSON so the frontend can render it in the
existing result-tabs UI with minimal work.

Run daily after ``run_preset_backtests.py`` completes.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("rotation-eval")

_APP_DIR = Path(__file__).resolve().parent.parent
_BT_DIR = _APP_DIR / "data" / "cache" / "backtests"
_OUT_DIR = _APP_DIR / "data" / "cache" / "rotation"

# Match SECTORS in run_preset_backtests.py (10 sector keys, order matters
# for consistent output).
SECTOR_KEYS = ["it", "hc", "fin", "cd", "cs", "ind", "staples",
               "en", "mat", "re"]
STRATEGY_KEYS = ["equal", "momentum", "invvol", "ensemble", "regime"]

# Rules that we backtest for each strategy.
RULES = ["mom_1m", "mom_3m", "conf"]
TOP_K_OPTIONS = [1, 3]


# ── Data loading ───────────────────────────────────────────────────

def _load_sector_presets(strategy: str) -> dict[str, dict]:
    """Return {sector_key: preset_dict} for the given strategy. Missing
    files are silently skipped — a full 10-sector matrix isn't required
    (we just get fewer rotation candidates)."""
    out: dict[str, dict] = {}
    for sk in SECTOR_KEYS:
        pid = f"{sk}_{strategy}"
        f = _BT_DIR / f"{pid}.json"
        if not f.exists():
            continue
        try:
            out[sk] = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("Failed to load %s: %s", pid, e)
    return out


def _rebal_matrix(presets: dict[str, dict]) -> tuple[list[str], dict[str, dict[str, dict]]]:
    """Return ``(dates, matrix)`` where ``dates[i]`` is the ISO rebalance
    date and ``matrix[date][sector_key]`` is that sector's per-rebalance
    dict. Only dates present in ALL loaded sectors are kept — otherwise
    the rotation would have holes."""
    dates_per_sector: list[set[str]] = []
    per_sector: dict[str, dict[str, dict]] = {}
    for sk, p in presets.items():
        rows = p.get("full", {}).get("rebal_hist", [])
        by_date = {r["rebalance_date"][:10]: r for r in rows if r.get("rebalance_date")}
        per_sector[sk] = by_date
        dates_per_sector.append(set(by_date.keys()))
    if not dates_per_sector:
        return [], {}
    common = sorted(set.intersection(*dates_per_sector))
    matrix: dict[str, dict[str, dict]] = {d: {} for d in common}
    for sk, by_date in per_sector.items():
        for d in common:
            matrix[d][sk] = by_date[d]
    return common, matrix


# ── Rule scoring (only uses info available at time T) ─────────────

def _score_sector_at(
    sk: str,
    date_idx: int,
    dates: list[str],
    matrix: dict[str, dict[str, dict]],
    rule: str,
) -> float | None:
    """Score sector ``sk`` at ``dates[date_idx]`` — higher = pick this sector.

    All rules use only rows with rebalance_date < dates[date_idx], so no
    lookahead. Returns None if not enough history for the rule."""
    row = matrix[dates[date_idx]].get(sk)
    if row is None:
        return None

    if rule == "conf":
        # Average pred_mean of the top-N picks the sector's model chose today.
        # pred_mean lives on ticker_df entries after Wave 1; older cached
        # JSONs may not have it → fall back to precision as a coarse proxy.
        tdf = row.get("ticker_df") or []
        preds = [t.get("pred_mean") for t in tdf
                 if isinstance(t.get("pred_mean"), (int, float))]
        if preds:
            return float(np.mean(preds))
        # Fallback: sector precision on the previous rebalance (proxy for
        # "model has been confident-and-right lately"). Uses date_idx-1
        # to stay lookahead-safe.
        if date_idx > 0:
            prev = matrix[dates[date_idx - 1]].get(sk)
            if prev is not None and isinstance(prev.get("precision"), (int, float)):
                return float(prev["precision"])
        return None

    # Momentum rules — trailing sector-strategy portfolio return.
    lookback = {"mom_1m": 1, "mom_3m": 3}.get(rule)
    if lookback is None:
        return None
    if date_idx < lookback:
        return None
    rets = []
    for j in range(date_idx - lookback, date_idx):
        prev = matrix[dates[j]].get(sk)
        if prev is None:
            continue
        r = prev.get("port_return")
        if isinstance(r, (int, float)):
            rets.append(float(r))
    if not rets:
        return None
    # Compound: (1+r1)(1+r2)...(1+rn) - 1
    total = 1.0
    for r in rets:
        total *= (1.0 + r)
    return total - 1.0


# ── Rotation simulation ────────────────────────────────────────────

def _simulate_rotation(
    dates: list[str],
    matrix: dict[str, dict[str, dict]],
    rule: str,
    top_k: int,
) -> dict:
    """Compound period returns by picking the top-K sectors at each rebalance."""
    period_returns: list[float] = []
    rebalance_log: list[dict] = []

    for i, d in enumerate(dates):
        scores: list[tuple[str, float]] = []
        for sk in matrix[d].keys():
            s = _score_sector_at(sk, i, dates, matrix, rule)
            if s is not None:
                scores.append((sk, s))
        if not scores:
            # No decision possible at this date (typically the first few
            # rebalances for momentum rules — insufficient history).
            continue
        scores.sort(key=lambda x: -x[1])
        chosen = [sk for sk, _ in scores[:top_k]]

        # Realized return for period [T, T+1] = equal-weight average of
        # each chosen sector's port_return.
        realized = []
        chosen_summary = []
        for sk in chosen:
            row = matrix[d].get(sk, {})
            r = row.get("port_return")
            if isinstance(r, (int, float)):
                realized.append(float(r))
                chosen_summary.append({
                    "sector": sk,
                    "score": next((s for k, s in scores if k == sk), None),
                    "port_return": float(r),
                    "picks": row.get("selected", []),
                })
        if not realized:
            continue
        period_ret = float(np.mean(realized))
        period_returns.append(period_ret)
        rebalance_log.append({
            "rebalance_date": d,
            "period_return": period_ret,
            "chosen_sectors": chosen_summary,
        })

    # Compound into equity curve
    values = [1.0]
    for r in period_returns:
        values.append(values[-1] * (1.0 + r))
    port_dates = [dates[0]] + [rebalance_log[i]["rebalance_date"]
                                for i in range(len(rebalance_log))]
    # Guard: values length must match dates length
    port_dates = port_dates[:len(values)]

    return {
        "rule": rule,
        "top_k": top_k,
        "period_returns": period_returns,
        "port_dates": port_dates,
        "port_values": values,
        "rebalance_log": rebalance_log,
    }


# ── Summary metrics ────────────────────────────────────────────────

def _summarise(sim: dict, benchmark_series: list[dict] | None) -> dict:
    """CAGR/Sharpe/MDD/alpha aligned to the sim's date range."""
    values = sim["port_values"]
    if len(values) < 2:
        return {"n_rebalances": 0}
    dates = pd.to_datetime(sim["port_dates"])
    total_ret = values[-1] / values[0] - 1
    years = max((dates[-1] - dates[0]).days / 365.25, 1e-6)
    cagr = (1 + total_ret) ** (1 / years) - 1 if total_ret > -1 else -1

    # Period-return based Sharpe (assumes monthly rebalance → annualise by √12)
    prets = np.array(sim["period_returns"])
    ann_factor = 12  # assumes rebal_m=1
    sharpe = float(np.mean(prets) / np.std(prets, ddof=1) * np.sqrt(ann_factor)) \
        if len(prets) > 1 and np.std(prets, ddof=1) > 0 else None

    # MDD from equity curve
    peaks = np.maximum.accumulate(values)
    dd = (np.array(values) - peaks) / peaks
    mdd = float(dd.min())

    # Win rate
    wins = sum(1 for r in prets if r > 0)
    win_rate = float(wins / len(prets)) if len(prets) else None

    out = {
        "n_rebalances": len(prets),
        "total_return_pct": round(total_ret * 100, 2),
        "cagr_pct": round(cagr * 100, 2),
        "sharpe": round(sharpe, 2) if sharpe is not None else None,
        "max_dd_pct": round(mdd * 100, 2),
        "monthly_win_rate_pct": round(win_rate * 100, 2) if win_rate is not None else None,
        "avg_period_return_pct": round(float(np.mean(prets)) * 100, 2) if len(prets) else None,
    }

    # SPY alpha vs same window
    if benchmark_series:
        by_date = {b["date"]: b["value"] for b in benchmark_series}
        first_d = dates[0].strftime("%Y-%m-%d")
        last_d = dates[-1].strftime("%Y-%m-%d")
        v0 = by_date.get(first_d) or next((v for d, v in by_date.items() if d >= first_d), None)
        v1 = by_date.get(last_d) or next((v for d, v in sorted(by_date.items(), reverse=True) if d <= last_d), None)
        if v0 and v1 and v0 > 0:
            spy_ret = v1 / v0 - 1
            spy_cagr = (1 + spy_ret) ** (1 / years) - 1 if spy_ret > -1 else -1
            out["spy_cagr_pct"] = round(spy_cagr * 100, 2)
            out["alpha_annual_pct"] = round((cagr - spy_cagr) * 100, 2)

    return out


# ── Main ───────────────────────────────────────────────────────────

def main() -> int:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    strategies_done: list[str] = []

    for strategy in STRATEGY_KEYS:
        presets = _load_sector_presets(strategy)
        if len(presets) < 3:
            logger.info("skip %s — only %d sector preset(s) available",
                        strategy, len(presets))
            continue
        dates, matrix = _rebal_matrix(presets)
        if len(dates) < 6:
            logger.info("skip %s — only %d common rebalance date(s)",
                        strategy, len(dates))
            continue

        # SPY benchmark — reuse from any sector preset (all should share
        # the same normalised series over the same backtest window).
        bench = next(
            (p.get("full", {}).get("benchmark_series") for p in presets.values()
             if p.get("full", {}).get("benchmark_series")),
            None,
        )

        variants: dict[str, dict] = {}
        for rule in RULES:
            for k in TOP_K_OPTIONS:
                sim = _simulate_rotation(dates, matrix, rule, k)
                if sim["port_values"] and len(sim["port_values"]) > 1:
                    key = f"{rule}_top{k}"
                    variants[key] = {
                        "summary": _summarise(sim, bench),
                        "port_dates": sim["port_dates"],
                        "port_values": sim["port_values"],
                        "rebalance_log": sim["rebalance_log"],
                    }
                    s = variants[key]["summary"]
                    logger.info(
                        "  %s/%s: CAGR %s%%, Sharpe %s, MDD %s%%, alpha %s%%",
                        strategy, key, s.get("cagr_pct"), s.get("sharpe"),
                        s.get("max_dd_pct"), s.get("alpha_annual_pct"),
                    )

        if not variants:
            continue

        out_path = _OUT_DIR / f"eval_{strategy}.json"
        out_path.write_text(
            json.dumps(
                {
                    "strategy": strategy,
                    "sectors_included": sorted(presets.keys()),
                    "n_common_dates": len(dates),
                    "date_range": [dates[0], dates[-1]],
                    "benchmark_series": bench,
                    "variants": variants,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                ensure_ascii=False, indent=2, default=str,
            ),
            encoding="utf-8",
        )
        strategies_done.append(strategy)
        logger.info("wrote %s (%d variants)", out_path.name, len(variants))

    logger.info("done — %d strategy eval(s) written", len(strategies_done))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
