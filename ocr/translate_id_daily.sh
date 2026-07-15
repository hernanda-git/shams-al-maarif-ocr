# ══════════════════════════════════════════════════════════════════
# Daily bounded burst for Shams al-Maarif Indonesian translation.
#
# Runs the OpenRouter (tencent/hy3:free) worker in a RESUMABLE burst:
#   - translates as many pending pages as it can within BURST_SECONDS
#   - on throttle / daily free-tier cap the worker self-heals and waits,
#     so we CAP the run so a blocked day can't hog the cron slot
#   - state persists between bursts, so the next daily run resumes
#   - once everything is done it runs the three-language merge
#
# Idempotent per calendar day: a marker file (DAILY_MARKER) records the
# last YYYY-MM-DD that fired. Hermes boot and the 03:00 cron both call
# this; whichever fires first owns the day, the second is a no-op.
#
# Triggered by:
#   - Hermes boot  → hermes-startup.sh calls this (boot mode)
#   - Daily cron   → 0 3 * * * (cronjob skill)
# ══════════════════════════════════════════════════════════════════
set -uo pipefail

# ── paths (RESOLVED TO REAL PROJECT — not this script's location) ──
# This script may live in ~/.hermes/scripts/ (cron) OR in ocr/ (manual),
# so we hard-resolve the project dir instead of deriving from $0.
REPO_DIR="/c/Working Folder/Research/shams-al-maarif-ocr"
OCR_DIR="$REPO_DIR/ocr"
if [[ ! -d "$OCR_DIR" ]]; then
  echo "ERROR: project ocr dir not found at $OCR_DIR"
  exit 1
fi
LOG_DIR="$OCR_DIR/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/translate_id_daily_$(date +%Y%m%d).log"

# ── config ─────────────────────────────────────────────────────────
BURST_SECONDS="${BURST_SECONDS:-21600}"   # 6h hard cap per daily run
MAX_ITER="${MAX_ITER:-4000}"              # safety cap on outer loop
KEY_FILE="$OCR_DIR/.openrouter_key"
PROVIDER="${TRANSLATE_PROVIDER:-openrouter}"
MODEL="${TRANSLATE_MODEL:-tencent/hy3:free}"

# ── per-day idempotency marker ─────────────────────────────────────
# Boot and the 03:00 cron both hit this. First one of the day wins.
MARKER="$LOG_DIR/.last_run_day"
TODAY="$(date +%Y-%m-%d)"
if [[ -f "$MARKER" ]] && [[ "$(cat "$MARKER" 2>/dev/null)" == "$TODAY" ]]; then
  echo "$(date '+%Y-%m-%d %H:%M:%S') already ran today ($TODAY) — skipping (idempotent)." | tee -a "$LOG"
  exit 0
fi

# ── load key (never echo it) ───────────────────────────────────────
if [[ -f "$KEY_FILE" ]]; then
  OPENROUTER_API_KEY="$(head -n1 "$KEY_FILE" | tr -d '[:space:]')"
else
  echo "ERROR: missing $KEY_FILE" | tee -a "$LOG"
  exit 1
fi
if [[ -z "$OPENROUTER_API_KEY" ]]; then
  echo "ERROR: empty OpenRouter key in $KEY_FILE" | tee -a "$LOG"
  exit 1
fi

export TRANSLATE_PROVIDER="$PROVIDER"
export TRANSLATE_MODEL="$MODEL"
export OPENROUTER_API_KEY

echo "──────── $(date '+%Y-%m-%d %H:%M:%S') [boot-mode=${BOOT_MODE:-0}] ────────" | tee -a "$LOG"
echo "provider=$PROVIDER model=$MODEL burst=${BURST_SECONDS}s" | tee -a "$LOG"

cd "$OCR_DIR"

# ── singleton guard (lockfile + PID) ───────────────────────────────
LOCK="$OCR_DIR/.translate_id_daily.lock"
if [[ -f "$LOCK" ]]; then
  OLD_PID="$(head -n1 "$LOCK" 2>/dev/null || echo "")"
  if [[ -n "$OLD_PID" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') another run active (pid $OLD_PID) — exiting." | tee -a "$LOG"
    exit 0
  fi
  # stale lock — remove
  rm -f "$LOCK"
fi
echo "$$" > "$LOCK"
trap 'rm -f "$LOCK"' EXIT

# Mark today as claimed BEFORE the heavy work, so a concurrent/duplicate
# trigger in the same day sees the marker and bails.
echo "$TODAY" > "$MARKER"

iter=0
while (( iter < MAX_ITER )); do
  iter=$((iter + 1))

  # how many pending remain?
  PENDING="$(uv run python -c 'import json,os; s=json.load(open(".translate_state_id.json")); done=set(s.get("completed",[])); print(sum(1 for f in os.listdir("enriched") if f.startswith("page_") and f not in done))' 2>/dev/null || echo "0")"
  echo "[iter $iter] pending ID pages: $PENDING" | tee -a "$LOG"

  if [[ "$PENDING" == "0" ]]; then
    echo "All ID pages translated. Running --retry-failed to catch stragglers..." | tee -a "$LOG"
    timeout 600 uv run python translate_id.py --retry-failed >>"$LOG" 2>&1 || true
    PENDING="$(uv run python -c 'import json,os; s=json.load(open(".translate_state_id.json")); done=set(s.get("completed",[])); print(sum(1 for f in os.listdir("enriched") if f.startswith("page_") and f not in done))' 2>/dev/null || echo "0")"
    if [[ "$PENDING" == "0" ]]; then
      echo "Nothing pending. Building merged chapters..." | tee -a "$LOG"
      cd "$REPO_DIR"
      uv run python scripts/merge_three_languages.py >>"$LOG" 2>&1 || true
      echo "DONE — merged output up to date." | tee -a "$LOG"
      break
    fi
  fi

  # run one bounded burst of the worker (≤ BURST_SECONDS, then timeout kills it)
  START_TS="$(date +%s)"
  timeout "$((BURST_SECONDS + 120))" uv run python translate_id.py --all >>"$LOG" 2>&1 || true
  echo "burst segment ended ($(date +%s) - $START_TS = $(( $(date +%s) - START_TS ))s)" | tee -a "$LOG"

  # stop if burst window exceeded
  if (( $(date +%s) - START_TS >= BURST_SECONDS )); then
    echo "burst window (${BURST_SECONDS}s) reached — stopping, state saved." | tee -a "$LOG"
    break
  fi
done

echo "cron burst finished at $(date '+%Y-%m-%d %H:%M:%S')" | tee -a "$LOG"
