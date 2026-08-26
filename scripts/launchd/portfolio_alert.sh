#!/bin/bash
# Portfolio risk alert — sends Telegram notification if user's Turso portfolio
# breaches risk thresholds. No cache side effects to commit.
source "$(dirname "$0")/_common.sh"

STAMP="$(date +%Y%m%d-%H%M%S)"
LOG="$LOGDIR/portfolio_alert-${STAMP}.log"
export LOG

log_line INFO "start portfolio_alert"
cd "$REPO"

if "$VENV_PY" streamlit_app/scripts/portfolio_risk_alert.py >> "$LOG" 2>&1; then
  log_line INFO "done"
  find "$LOGDIR" -maxdepth 1 -type f -name '*.log' -mtime +30 -delete 2>/dev/null || true
  exit 0
else
  rc=$?
  log_line ERROR "portfolio_alert exit $rc"
  exit $rc
fi
