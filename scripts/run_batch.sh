#!/bin/bash
# run_batch.sh — CRON ENTRY POINT for Shams al-Ma'arif OCR pipeline.
# Called by cron every 30 minutes. Each execution processes 10 pages.
# Robust version: no set -e, each step handles its own failures.

set -uo pipefail
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

SCRIPT_DIR="$REPO_DIR/scripts"
STATE_DIR="$REPO_DIR/state"
BATCH_LOG="$STATE_DIR/batch_log.json"
BATCH_SIZE=3
LOCK_FILE="$STATE_DIR/run_batch.lock"
CRON_LOG="$STATE_DIR/cron_run.log"
FAILED_RETRIES="$STATE_DIR/failed_retries.json"

# Log helper
log() { echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*" | tee -a "$CRON_LOG"; }

# --- Lock guard ---
if [ -f "$LOCK_FILE" ]; then
    LOCK_PID=$(cat "$LOCK_FILE" 2>/dev/null)
    LOCK_AGE=$(( $(date +%s) - $(stat -c %Y "$LOCK_FILE" 2>/dev/null || echo 0) ))
    if [ "$LOCK_AGE" -gt 3600 ] 2>/dev/null; then
        log "[WARN] Lock file stale ($LOCK_AGE s) — forcing removal"
        rm -f "$LOCK_FILE"
    elif kill -0 "$LOCK_PID" 2>/dev/null; then
        log "[SKIP] Previous batch still running (PID $LOCK_PID)"
        exit 0
    else
        log "[WARN] Stale lock (PID $LOCK_PID dead) — removed"
        rm -f "$LOCK_FILE"
    fi
fi
echo $$ > "$LOCK_FILE"
trap "rm -f '$LOCK_FILE'" EXIT

log "=== BATCH START ==="

# Load API key
if [ -f "$REPO_DIR/.env" ]; then
    set -a
    source "$REPO_DIR/.env"
    set +a
fi

# --- Step 1: Get next batch ---
log "[STEP 1] Identifying next batch..."
python3 "$SCRIPT_DIR/progress_manager.py" rebuild 2>>"$CRON_LOG" || log "  rebuild skipped (no new files)"
PENDING_PAGES=$(python3 "$SCRIPT_DIR/progress_manager.py" next-batch "$BATCH_SIZE" 2>/dev/null || echo "")

if [ -z "$PENDING_PAGES" ]; then
    log "[DONE] No pending pages — all 604 pages processed!"
    exit 0
fi

log "  Next batch: $PENDING_PAGES"

# --- Step 2: OCR ---
log "[STEP 2] Gemini OCR..."
OCR_EXIT=0
OCR_OUTPUT=$(python3 "$SCRIPT_DIR/ocr_gemini.py" $PENDING_PAGES 2>&1) || OCR_EXIT=$?
echo "$OCR_OUTPUT" | tee -a "$CRON_LOG"
if [ "$OCR_EXIT" -ne 0 ]; then
    log "  [WARN] OCR had failures (exit $OCR_EXIT) — continuing"
fi

# Check which pages actually have raw files
OCR_FAILED=""
OCR_OK=""
for PAGE in $PENDING_PAGES; do
    PAD=$(printf '%03d' $PAGE)
    if [ -f "$REPO_DIR/ocr/raw/page_${PAD}.txt" ] && [ -s "$REPO_DIR/ocr/raw/page_${PAD}.txt" ]; then
        OCR_OK="$OCR_OK $PAGE"
    else
        OCR_FAILED="$OCR_FAILED $PAGE"
    fi
done
if [ -n "$OCR_FAILED" ]; then
    log "  [WARN] OCR failed pages:$OCR_FAILED — will still try enrichment on successful ones"
fi

# --- Step 3: Enrichment ---
log "[STEP 3] Gemini enrichment..."
ENR_EXIT=0
ENR_OUTPUT=$(python3 "$SCRIPT_DIR/enrich_gemini.py" $PENDING_PAGES 2>&1) || ENR_EXIT=$?
echo "$ENR_OUTPUT" | tee -a "$CRON_LOG"
if [ "$ENR_EXIT" -ne 0 ]; then
    log "  [WARN] Enrichment had failures (exit $ENR_EXIT) — continuing"
fi

# --- Step 4: Update progress ---
log "[STEP 4] Updating progress state..."
ENR_FAILED=""
for PAGE in $PENDING_PAGES; do
    PAD=$(printf '%03d' $PAGE)
    RAW_FILE="$REPO_DIR/ocr/raw/page_${PAD}.txt"
    ENR_FILE="$REPO_DIR/ocr/enriched/page_${PAD}.txt"

    STATUS="failed"
    if [ -f "$ENR_FILE" ] && [ -s "$ENR_FILE" ]; then
        STATUS="enriched_done"
        log "  Page $PAGE → enriched_done ($(wc -c < "$ENR_FILE") bytes)"
    elif [ -f "$RAW_FILE" ] && [ -s "$RAW_FILE" ]; then
        STATUS="raw_ocr_done"
        log "  Page $PAGE → raw_ocr_done (enrichment pending)"
    else
        ENR_FAILED="$ENR_FAILED $PAGE"
        log "  [WARN] Page $PAGE → failed (no output files)"
    fi

    python3 "$SCRIPT_DIR/progress_manager.py" mark "$PAGE" "$STATUS"
done

# Log batch
TIMESTAMP=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
python3 "$SCRIPT_DIR/progress_manager.py" log-batch "$TIMESTAMP" "$PENDING_PAGES" "$BATCH_SIZE" 2>/dev/null || log "  [WARN] Failed to write batch log"

# --- Step 5: Git commit & push ---
log "[STEP 5] Git commit & push..."
bash "$SCRIPT_DIR/git_auto_push.sh" 2>&1 | tee -a "$CRON_LOG" || log "  [WARN] Git push had issues — will retry on next batch"

# --- Summary ---
TOTAL_DONE=$(python3 -c "
import json
with open('state/progress.json') as f:
    p = json.load(f)
done = sum(1 for v in p.values() if v.get('status') == 'enriched_done')
print(done)
" 2>/dev/null || echo "?")
PCT=$(python3 -c "print(f'{$TOTAL_DONE/604*100:.1f}')" 2>/dev/null || echo "?")

log "=== BATCH COMPLETE ==="
log "  Pages batch: $PENDING_PAGES"
if [ -n "$ENR_FAILED" ]; then
    log "  FAILED pages:${ENR_FAILED} (will be retried next cycle)"
fi
log "  Total enriched: $TOTAL_DONE / 604 ($PCT%)"
log "  Next run: ~30 min"
