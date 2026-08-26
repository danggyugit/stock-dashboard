#!/bin/bash
source "$(dirname "$0")/_common.sh"

run_and_commit \
  "fetch_cache" \
  "streamlit_app/scripts/fetch_cache.py" \
  "chore(cache): daily fetch_cache refresh (heatmap/snapshot/stocks/meta)" \
  streamlit_app/data/cache/heatmap.json \
  streamlit_app/data/cache/market_snapshot.json \
  streamlit_app/data/cache/stocks.json \
  streamlit_app/data/cache/meta.json \
  streamlit_app/data/cache/market_caps_persistent.json
