#!/bin/bash
# Common setup sourced by every launchd wrapper.
#
# launchd starts with a stripped-down environment — no PATH, no LANG, no HOME
# picked up from the login shell. Everything must be set explicitly here.
#
# Wrapper contract:
#   1. source this file first
#   2. call run_and_commit <name> <python-script> <cache-path> [cache-path...]
#      to execute + auto commit + push. See fetch_cache.sh for the pattern.

set -o pipefail

# ── File descriptor limit ────────────────────────────────────────
# macOS launchd starts processes with soft ulimit -n = 256, which is
# not enough for yfinance's per-ticker SQLite cache when downloading
# ~1500 tickers concurrently. Symptoms without this raise:
#   - OSError: [Errno 24] Too many open files (pickle save)
#   - OperationalError('unable to open database file') (yfinance)
# Raising to 8192 is well within macOS hard limit (65536) and gives
# comfortable headroom.
ulimit -n 8192 2>/dev/null || true

# ── PATH: Homebrew (gh, python3) + system (git) ──────────────────
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export LANG="en_US.UTF-8"
export HOME="${HOME:-/Users/danggyu}"

REPO="$HOME/claude/stock-dashboard"
VENV_PY="$REPO/.venv-cache/bin/python"
LOGDIR="$REPO/logs/launchd"
mkdir -p "$LOGDIR"

# ── Small helpers ────────────────────────────────────────────────

log_line() {
  # $1 = level, $2+ = message. Timestamped, appended to $LOG.
  local lvl="$1"; shift
  printf '%s [%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$lvl" "$*" >> "$LOG"
}

_commit_and_push() {
  # $1 = commit message subject; remaining args = paths to add.
  local subject="$1"; shift
  cd "$REPO"
  git add -- "$@"
  if git diff --cached --quiet; then
    log_line INFO "no cache changes to commit"
    return 0
  fi
  # [skip ci] so GitHub Actions doesn't re-trigger for cache-only commits
  git commit -m "${subject} [skip ci]" >> "$LOG" 2>&1
  # Retry-safe push (single attempt; if it fails, next run will pick up the diff)
  if git push origin main >> "$LOG" 2>&1; then
    log_line INFO "pushed"
  else
    log_line ERROR "git push failed (leaving commit locally for next run to catch up)"
    return 1
  fi
}

run_and_commit() {
  # $1 = job name (for log filename)
  # $2 = python script path (relative to REPO)
  # $3 = commit subject
  # $4..N = cache paths to add
  local jobname="$1"; shift
  local script="$1"; shift
  local subject="$1"; shift

  local stamp="$(date +%Y%m%d-%H%M%S)"
  LOG="$LOGDIR/${jobname}-${stamp}.log"
  export LOG

  log_line INFO "start ${jobname} → ${script}"
  cd "$REPO"

  if ! "$VENV_PY" "$script" >> "$LOG" 2>&1; then
    local rc=$?
    log_line ERROR "python exit $rc — skipping commit"
    _cleanup_old_logs
    exit $rc
  fi
  log_line INFO "python done"

  _commit_and_push "$subject" "$@"
  local push_rc=$?
  _cleanup_old_logs
  exit $push_rc
}

_cleanup_old_logs() {
  # Keep last 30 log files per job. Log filename pattern: <job>-YYYYMMDD-HHMMSS.log
  # Runs after each job so the logs dir doesn't grow unbounded.
  find "$LOGDIR" -maxdepth 1 -type f -name '*.log' -mtime +30 -delete 2>/dev/null || true
}
