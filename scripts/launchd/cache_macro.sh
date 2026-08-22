#!/bin/bash
source "$(dirname "$0")/_common.sh"

run_and_commit \
  "cache_macro" \
  "streamlit_app/scripts/cache_macro_data.py" \
  "chore(cache): daily FRED macro refresh" \
  streamlit_app/data/cache/macro
