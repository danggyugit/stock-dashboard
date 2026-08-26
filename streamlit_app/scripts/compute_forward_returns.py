"""Forward-return evaluator for AI Live Picks.

Reads the append-only log written by ``run_preset_backtests.py``
(``data/cache/forward_test/log_YYYY.jsonl``), computes T+N forward
returns against SPY, and emits per-preset evaluation JSON files that
the web app renders in a "Live 검증" tab.

Ans wers three questions per preset:
  1. Do the model's pred_mean scores correlate with realized returns?
     → Spearman IC per snapshot
  2. Does the top decile beat the bottom decile?
     → Decile spread (top10% avg − bottom10% avg)
  3. Do the top-N picks that we actually served users beat SPY?
     → Top-N avg return − SPY return over the same window

Output: ``data/cache/forward_test/eval_{preset_id}.json`` for each preset
that has ≥ ``MIN_ELIGIBLE_ENTRIES`` snapshots aged ≥ T+N business days.

Run manually or from a scheduler (weekly is plenty — nothing changes
day-to-day until an old snapshot ages into evaluable range).
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import yfinance as yf

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("forward-eval")

_APP_DIR = Path(__file__).resolve().parent.parent
_LOG_DIR = _APP_DIR / "data" / "cache" / "forward_test"

# ── Config ─────────────────────────────────────────────────────────
FORWARD_WINDOWS = [21]           # trading days after picks_at. Extend later.
TOP_N_PICKS = 5                  # matches n_stocks in the batch config
MIN_ELIGIBLE_ENTRIES = 5         # too few snapshots → stats are noisy, skip
LOOKBACK_YEARS = [datetime.now().year, datetime.now().year - 1]


# ── Log loading ────────────────────────────────────────────────────

def _load_log_entries() -> list[dict]:
    """Read every log_YYYY.jsonl and dedupe on (picks_at, preset_id).

    Later entries win (a rerun on the same day overrides earlier writes).
    """
    if not _LOG_DIR.exists():
        return []
    seen: dict[tuple[str, str], dict] = {}
    for f in sorted(_LOG_DIR.glob("log_*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = (e.get("picks_at"), e.get("preset_id"))
            if all(key):
                seen[key] = e
    entries = list(seen.values())
    logger.info("Loaded %d unique log entries from %s", len(entries), _LOG_DIR)
    return entries


# ── Price fetching (batched via yfinance) ──────────────────────────

def _fetch_prices(tickers: Iterable[str], start: date, end: date) -> pd.DataFrame:
    """Fetch adjusted-close prices for all tickers in one batch.

    Returns a wide DataFrame indexed by date, one column per ticker.
    Tickers with no data are silently dropped by yfinance.
    """
    tickers = sorted({t for t in tickers if t})
    if not tickers:
        return pd.DataFrame()
    logger.info("Fetching %d tickers %s → %s", len(tickers), start, end)
    df = yf.download(
        tickers,
        start=start.isoformat(),
        end=(pd.Timestamp(end) + pd.Timedelta(days=1)).date().isoformat(),
        auto_adjust=True,
        progress=False,
        threads=True,
        group_by="column",
    )
    # yfinance returns MultiIndex when multiple tickers, single-level when one.
    if isinstance(df.columns, pd.MultiIndex):
        # Prefer "Close" (auto-adjusted); fall back to "Adj Close" for older yfinance.
        level_zero = df.columns.get_level_values(0)
        col = "Close" if "Close" in level_zero else "Adj Close"
        prices = df[col]
    else:
        col = "Close" if "Close" in df.columns else "Adj Close"
        prices = df[[col]].rename(columns={col: tickers[0]})
    prices.index = pd.to_datetime(prices.index).normalize()
    return prices.sort_index()


# ── Per-snapshot forward return calc ───────────────────────────────

def _t_plus_n(prices: pd.DataFrame, from_date: pd.Timestamp, n_bdays: int) -> pd.Timestamp | None:
    """Return the trading date that is `n_bdays` sessions after `from_date`,
    using the price index as the trading calendar. None if we don't have
    enough sessions yet (snapshot too young)."""
    idx = prices.index[prices.index >= from_date]
    if len(idx) < n_bdays + 1:
        return None
    return idx[n_bdays]


def _forward_returns(
    entry: dict, prices: pd.DataFrame, spy: pd.Series, window: int
) -> dict | None:
    """Compute one snapshot's forward-return stats. Returns None if the
    snapshot is younger than `window` trading days."""
    picks_at = pd.Timestamp(entry["picks_at"])
    end_date = _t_plus_n(prices, picks_at, window)
    if end_date is None:
        return None  # not enough forward history yet

    ranking = entry.get("ranking_top50") or []
    if len(ranking) < 4:  # decile needs breadth
        return None

    # Build per-ticker forward returns from the price panel
    ticker_rets: dict[str, float] = {}
    for r in ranking:
        t = r.get("ticker")
        if not t or t not in prices.columns:
            continue
        try:
            p0 = prices.loc[picks_at:, t].dropna().iloc[0]
            p1 = prices.loc[end_date, t]
            if pd.isna(p0) or pd.isna(p1) or p0 <= 0:
                continue
            ticker_rets[t] = float(p1 / p0 - 1)
        except (KeyError, IndexError):
            continue

    if len(ticker_rets) < 4:
        return None

    # Spearman IC — rank of pred_mean vs rank of realized return
    df_ic = pd.DataFrame([
        {"pred": r.get("pred_mean") if isinstance(r.get("pred_mean"), (int, float)) else r.get("composite_score"),
         "ret": ticker_rets.get(r["ticker"])}
        for r in ranking
        if r.get("ticker") in ticker_rets
    ]).dropna()
    ic = float(df_ic["pred"].rank().corr(df_ic["ret"].rank())) if len(df_ic) >= 4 else None

    # Decile spread: mean of top decile minus mean of bottom decile (by pred rank)
    n = len(df_ic)
    decile_spread = None
    if n >= 10:
        df_sorted = df_ic.sort_values("pred", ascending=False)
        k = max(1, n // 10)
        top_mean = df_sorted["ret"].iloc[:k].mean()
        bot_mean = df_sorted["ret"].iloc[-k:].mean()
        decile_spread = float(top_mean - bot_mean)

    # Top-N picks (as served to users) forward return
    picks_tickers = [p.get("ticker") for p in (entry.get("picks") or [])][:TOP_N_PICKS]
    picks_rets = [ticker_rets[t] for t in picks_tickers if t in ticker_rets]
    top_n_avg = float(np.mean(picks_rets)) if picks_rets else None

    # SPY over the same window
    try:
        spy_p0 = spy.loc[picks_at:].dropna().iloc[0]
        spy_p1 = spy.loc[end_date]
        spy_ret = float(spy_p1 / spy_p0 - 1) if pd.notna(spy_p1) and spy_p0 > 0 else None
    except (KeyError, IndexError):
        spy_ret = None

    alpha = (top_n_avg - spy_ret) if (top_n_avg is not None and spy_ret is not None) else None

    return {
        "picks_at": entry["picks_at"],
        "eval_date": end_date.strftime("%Y-%m-%d"),
        "n_ranked": int(n),
        "ic": ic,
        "decile_spread": decile_spread,
        "top_n_ret": top_n_avg,
        "spy_ret": spy_ret,
        "alpha": alpha,
    }


# ── Aggregate per preset ───────────────────────────────────────────

def _summarise(evaluations: list[dict]) -> dict:
    """Reduce a list of per-snapshot dicts into a single preset summary."""
    ics = [e["ic"] for e in evaluations if e.get("ic") is not None]
    ds = [e["decile_spread"] for e in evaluations if e.get("decile_spread") is not None]
    tn = [e["top_n_ret"] for e in evaluations if e.get("top_n_ret") is not None]
    sp = [e["spy_ret"] for e in evaluations if e.get("spy_ret") is not None]
    al = [e["alpha"] for e in evaluations if e.get("alpha") is not None]

    def _stats(xs: list[float]) -> dict:
        if not xs:
            return {"n": 0}
        return {
            "n": len(xs),
            "mean": float(np.mean(xs)),
            "std": float(np.std(xs, ddof=1)) if len(xs) > 1 else 0.0,
            "positive_rate": float(sum(1 for x in xs if x > 0) / len(xs)),
        }

    return {
        "ic": _stats(ics),
        "decile_spread": _stats(ds),
        "top_n_return": _stats(tn),
        "spy_return": _stats(sp),
        "alpha": _stats(al),
    }


def main() -> int:
    entries = _load_log_entries()
    if not entries:
        logger.warning("No log entries found — run run_preset_backtests.py first.")
        return 0

    # Group by preset for per-preset ticker universe fetch
    by_preset: dict[str, list[dict]] = defaultdict(list)
    for e in entries:
        by_preset[e["preset_id"]].append(e)

    # Global date range for one big yfinance batch (per preset would over-fetch).
    all_dates = sorted({pd.Timestamp(e["picks_at"]) for e in entries})
    fetch_start = (all_dates[0] - pd.Timedelta(days=5)).date()
    fetch_end = date.today()

    all_tickers: set[str] = set()
    for e in entries:
        for r in e.get("ranking_top50") or []:
            if r.get("ticker"):
                all_tickers.add(r["ticker"])
    all_tickers.add("SPY")

    prices = _fetch_prices(all_tickers, fetch_start, fetch_end)
    if prices.empty or "SPY" not in prices.columns:
        logger.error("Failed to fetch benchmark or price panel")
        return 1
    spy = prices["SPY"].dropna()

    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    for preset_id, preset_entries in sorted(by_preset.items()):
        per_window: dict[str, dict] = {}
        for w in FORWARD_WINDOWS:
            per_snapshot = []
            for e in preset_entries:
                r = _forward_returns(e, prices, spy, w)
                if r is not None:
                    per_snapshot.append(r)
            if len(per_snapshot) < MIN_ELIGIBLE_ENTRIES:
                logger.info(
                    "%s @ T+%d: only %d evaluable snapshots (<%d) — skipping",
                    preset_id, w, len(per_snapshot), MIN_ELIGIBLE_ENTRIES,
                )
                continue
            per_snapshot.sort(key=lambda x: x["picks_at"])
            per_window[f"{w}d"] = {
                "series": per_snapshot,
                "summary": _summarise(per_snapshot),
            }

        if not per_window:
            continue

        out_path = _LOG_DIR / f"eval_{preset_id}.json"
        out_path.write_text(
            json.dumps(
                {
                    "preset_id": preset_id,
                    "windows": per_window,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "min_eligible_entries": MIN_ELIGIBLE_ENTRIES,
                    "top_n_picks": TOP_N_PICKS,
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
        written += 1
        logger.info("Wrote %s", out_path.name)

    logger.info("Done — %d/%d presets evaluated", written, len(by_preset))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
