#!/bin/bash
# Refreshes the pickle files (backtest_data/*.pkl.gz) used by both
# run_preset_backtests.py and api/factor_backtest.py. Must run BEFORE
# preset_backtests to feed fresh price/PIT data into the ML pipeline.
source "$(dirname "$0")/_common.sh"

run_and_commit \
  "cache_backtest_data" \
  "streamlit_app/scripts/cache_backtest_data.py" \
  "chore(cache): daily backtest pickle refresh" \
  streamlit_app/data/cache/backtest_data
