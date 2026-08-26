#!/bin/bash
# Daily two-stage sector rotation post-processor. Runs after
# preset_backtests (02:30) so it always eats fresh data.
# Cheap (<1 min): just reads 50 JSONs and does arithmetic.
source "$(dirname "$0")/_common.sh"

run_and_commit \
  "rotation_backtest" \
  "streamlit_app/scripts/rotation_backtest.py" \
  "chore(cache): daily sector rotation eval" \
  streamlit_app/data/cache/rotation
