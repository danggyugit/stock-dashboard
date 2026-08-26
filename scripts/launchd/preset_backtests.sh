#!/bin/bash
# 50 preset backtests (10 sectors × 5 strategies). Heavy — 4-5 hours.
# Auto-commits ALL backtest JSONs at the end (uses -A on the backtests
# directory since files are added/overwritten during the long run).
source "$(dirname "$0")/_common.sh"

run_and_commit \
  "preset_backtests" \
  "streamlit_app/scripts/run_preset_backtests.py" \
  "chore(cache): daily preset backtest matrix" \
  streamlit_app/data/cache/backtests
