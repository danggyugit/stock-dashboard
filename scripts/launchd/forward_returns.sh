#!/bin/bash
# Weekly forward-return joiner for Live Picks (out-of-sample eval).
# Reads data/cache/forward_test/log_*.jsonl, computes T+21 forward
# returns + IC + decile spread + alpha vs SPY, writes eval_*.json.
# Runs weekly — nothing changes day-to-day until snapshots age into
# the evaluable range.
source "$(dirname "$0")/_common.sh"

run_and_commit \
  "forward_returns" \
  "streamlit_app/scripts/compute_forward_returns.py" \
  "chore(cache): weekly forward-return eval" \
  streamlit_app/data/cache/forward_test
