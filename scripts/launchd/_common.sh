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
  # Push with fetch+rebase retry — batches often collide with each other
  # (fetch_cache, cache_macro, valuation cache all racing). Without this
  # every conflict left commits stranded locally and the "next run will
  # catch up" hope silently broke when the next run's Python failed too.
  for attempt in 1 2 3; do
    if git push origin main >> "$LOG" 2>&1; then
      log_line INFO "pushed on attempt $attempt"
      return 0
    fi
    log_line WARN "push failed (attempt $attempt) — fetching + rebasing"
    if ! git fetch origin main >> "$LOG" 2>&1; then
      log_line ERROR "git fetch failed"
      break
    fi
    # Rebase our commit on top of what came in. Cache dirs are the
    # only things we touch so rebase conflicts are extremely rare.
    # Any unstaged files (from a stray concurrent run or a partial
    # write) get stashed so rebase doesn't refuse — then popped back
    # so the next commit-and-push cycle catches them.
    local stashed=0
    if ! git diff --quiet || ! git diff --cached --quiet 2>/dev/null; then
      if git stash push -u -m "auto-stash before rebase (${jobname})" >> "$LOG" 2>&1; then
        stashed=1
        log_line INFO "auto-stashed unstaged changes for rebase"
      fi
    fi
    local rebase_ok=1
    if ! git rebase origin/main >> "$LOG" 2>&1; then
      log_line ERROR "rebase conflict — aborting rebase, leaving commit local"
      git rebase --abort >> "$LOG" 2>&1
      rebase_ok=0
    fi
    if [ "$stashed" = "1" ]; then
      git stash pop >> "$LOG" 2>&1 || log_line WARN "stash pop had conflicts (files kept in stash)"
    fi
    [ "$rebase_ok" = "0" ] && break
  done
  log_line ERROR "git push failed after retries (commit stays local)"
  return 1
}

run_and_commit() {
  # $1 = job name (for log filename)
  # $2 = python script path (relative to REPO)
  # $3 = commit subject
  # $4..N = cache paths to add
  local jobname="$1"; shift
  local script="$1"; shift
  local subject="$1"; shift

  # ── Concurrency guard (PID file) ──────────────────────────────
  # macOS launchd will happily start a second copy of a job while the
  # previous is still running. When multiple batches (preset_backtests
  # especially — often 5-8h+) overlap, they race on the same cache
  # files and produce corrupt half-written JSONs. If the existing PID
  # in the pidfile is still alive, skip this launch and let the next
  # scheduled run try again with a clean slate.
  local pidfile="$LOGDIR/${jobname}.pid"
  if [ -f "$pidfile" ]; then
    local existing_pid=$(cat "$pidfile" 2>/dev/null)
    if [ -n "$existing_pid" ] && kill -0 "$existing_pid" 2>/dev/null; then
      local stamp="$(date +%Y%m%d-%H%M%S)"
      LOG="$LOGDIR/${jobname}-${stamp}.log"
      log_line WARN "another ${jobname} instance (PID $existing_pid) is running — skipping this launch"
      exit 0
    fi
  fi
  echo $$ > "$pidfile"
  # Best-effort cleanup — if the process dies without hitting the end,
  # a stale pidfile is fine because kill -0 will report it dead.
  trap "rm -f '$pidfile'" EXIT

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
