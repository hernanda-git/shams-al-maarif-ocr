#!/bin/bash
# run_batch.sh — CRON ENTRY POINT for Shams al-Ma'arif OCR pipeline.
# Called by cron every 30 minutes. Each execution processes 10 pages.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

SCRIPT_DIR="$REPO_DIR/scripts"
STATE_DIR="$REPO_DIR/state"
BATCH_LOG="$STATE_DIR/batch_log.json"
BATCH_SIZE=10
LOCK_FILE="$STATE_DIR/run_batch.lock"

# Prevent concurrent runs
if [ -f "$LOCK_FILE" ]; then
    LOCK_PID=$(cat "$LOCK_FILE" 2>/dev/null)
    if kill -0 "$LOCK_PID" 2>/dev/null; then
        echo "[SKIP] Previous batch still running (PID $LOCK_PID) — skipping this tick"
        exit 0
    else
        echo "[WARN] Stale lock file found — removing"
        rm -f "$LOCK_FILE"
    fi
fi
echo $$ > "$LOCK_FILE"
trap "rm -f '$LOCK_FILE'" EXIT

echo ""
echo "=============================================="
echo "  run_batch.sh — $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "=============================================="

# Load API key from .env if present
if [ -f "$REPO_DIR/.env" ]; then
    set -a
    source "$REPO_DIR/.env"
    set +a
fi

# --- Step 1: Rebuild progress from filesystem ---
echo "[STEP 1] Rebuilding progress from filesystem..."
python3 "$SCRIPT_DIR/progress_manager.py" rebuild 2>/dev/null || true
PENDING_PAGES=$(python3 "$SCRIPT_DIR/progress_manager.py" next-batch "$BATCH_SIZE" 2>/dev/null || echo "")

if [ -z "$PENDING_PAGES" ]; then
    echo "[DONE] No pending pages — all 604 pages processed!"
    exit 0
fi

echo "[DONE] Next batch: $PENDING_PAGES"
echo ""

# --- Step 2: Run OCR ---
echo "[STEP 2] Gemini OCR on $PENDING_PAGES..."
OCR_RESULT=$(python3 "$SCRIPT_DIR/ocr_gemini.py" $PENDING_PAGES 2>&1) || echo "[WARN] OCR step had failures (see above)"
echo "$OCR_RESULT"
echo ""

# --- Step 3: Run enrichment ---
echo "[STEP 3] Enrichment pass on $PENDING_PAGES..."
ENR_RESULT=$(python3 "$SCRIPT_DIR/enrich_gemini.py" $PENDING_PAGES 2>&1) || echo "[WARN] Enrichment step had failures (see above)"
echo "$ENR_RESULT"
echo ""

# --- Step 4: Update progress ---
echo "[STEP 4] Updating progress state..."
for PAGE in $PENDING_PAGES; do
    PAD=$(printf '%03d' $PAGE)
    RAW_FILE="$REPO_DIR/ocr/raw/page_${PAD}.txt"
    ENR_FILE="$REPO_DIR/ocr/enriched/page_${PAD}.txt"

    STATUS="raw_ocr_done"
    if [ -f "$ENR_FILE" ] && [ -s "$ENR_FILE" ]; then
        STATUS="enriched_done"
    elif [ -f "$RAW_FILE" ] && [ -s "$RAW_FILE" ]; then
        STATUS="raw_ocr_done"
    else
        STATUS="failed"
        echo "  [WARN] Page $PAGE: no output files found"
    fi

    python3 "$SCRIPT_DIR/progress_manager.py" mark "$PAGE" "$STATUS"
done
# Log this batch — use a Python script file to avoid shell quoting issues
TIMESTAMP=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
python3 "$SCRIPT_DIR/progress_manager.py" log-batch "$TIMESTAMP" "$PENDING_PAGES" "$BATCH_SIZE" 2>/dev/null || echo "  [WARN] Failed to write batch log"

# --- Step 5: Commit & push ---
echo ""
echo "[STEP 5] Git commit & push..."
bash "$SCRIPT_DIR/git_auto_push.sh"

echo ""
echo "=============================================="
echo "  BATCH COMPLETE — $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "  Pages processed: $PENDING_PAGES"
echo "=============================================="
echo ""
