#!/bin/bash
# 55 preset backtests (10 sectors + cross-sector, × 5 strategies) on the
# S&P 1500 universe. The 5 strategies of a sector share one training pass.
# Auto-commits ALL backtest JSONs at the end (uses -A on the backtests
# directory since files are added/overwritten during the long run).
source "$(dirname "$0")/_common.sh"

# Backtest universe = full S&P 1500 (Large + Mid + Small, 10 sectors).
# cache_backtest_data.sh sets the same value — keep the two in sync.
export BACKTEST_CAP_TIERS=all

# The 02:00 data refresh now takes ~45-50 min for ~1,440 tickers and is
# still writing its pickles when this job fires at 02:30. Reading them
# mid-write is what produced the empty-input runs, so wait for it to
# finish (up to 3h) before starting. The short initial sleep covers the
# case where both jobs fire in the same second after a wake-from-sleep.
sleep 30
for _ in $(seq 1 180); do
  _dpid="$(cat "$LOGDIR/cache_backtest_data.pid" 2>/dev/null)"
  [ -n "$_dpid" ] && kill -0 "$_dpid" 2>/dev/null || break
  sleep 60
done

run_and_commit \
  "preset_backtests" \
  "streamlit_app/scripts/run_preset_backtests.py" \
  "chore(cache): daily preset backtest matrix" \
  streamlit_app/data/cache/backtests
