#!/bin/bash
source "$(dirname "$0")/_common.sh"

run_and_commit \
  "sec_intelligence" \
  "streamlit_app/scripts/fetch_sec_intelligence.py" \
  "chore(cache): daily 13F SEC intelligence refresh" \
  streamlit_app/data/cache/sec
