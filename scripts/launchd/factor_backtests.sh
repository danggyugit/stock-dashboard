#!/bin/bash
# Factor Lab (rule-based) backtest grid — ~25 strategies × 12 variants,
# computed from the backtest_data pickles and published as JSON so the web
# app reads results instead of asking the Render API to compute them.
# Runs after the 02:00 data refresh and the 02:30 preset matrix (done by
# ~04:15); takes 1-2 hours.
source "$(dirname "$0")/_common.sh"

run_and_commit \
  "factor_backtests" \
  "streamlit_app/scripts/run_factor_backtests.py" \
  "chore(cache): daily factor backtest grid" \
  streamlit_app/data/cache/factor_backtests
