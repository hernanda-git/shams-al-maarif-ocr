#!/bin/bash
# batch_process_all.sh — Process ALL remaining pending pages
# Runs OCR + enrichment + progress update in a loop.
# Each page processed one at a time (BATCH_SIZE=1 equivalent).
set -uo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

SCRIPT_DIR="$REPO_DIR/scripts"
STATE_DIR="$REPO_DIR/state"
CRON_LOG="$STATE_DIR/cron_run.log"
LOG="$STATE_DIR/batch_all.log"

log() { echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*" | tee -a "$LOG"; }

# Load API keys
if [ -f "$REPO_DIR/.env" ]; then
    set -a
    source "$REPO_DIR/.env"
    set +a
fi

TOTAL_PAGES=604
MAX_PAGES=250  # safety cap (242 remaining)

page=363
processed=0
failed=0

while [ "$page" -le "$TOTAL_PAGES" ] && [ "$processed" -lt "$MAX_PAGES" ]; do
    # Check if already enriched_done
    STATUS=$(python3 -c "
import json
with open('$STATE_DIR/progress.json') as f:
    p = json.load(f)
print(p.get(str($page), {}).get('status', 'pending'))
" 2>/dev/null || echo "pending")
    
    if [ "$STATUS" = "enriched_done" ] || [ "$STATUS" = "committed" ]; then
        page=$((page + 1))
        continue
    fi
    
    log "=== Processing page $page ($processed/$MAX_PAGES) ==="
    
    # --- OCR ---
    python3 "$SCRIPT_DIR/ocr_gemini.py" "$page" 2>&1 | tee -a "$LOG"
    OCR_EXIT=${PIPESTATUS[0]}
    
    # Check if raw was created
    PAD=$(printf '%03d' $page)
    if [ -f "$REPO_DIR/ocr/raw/page_${PAD}.txt" ] && [ -s "$REPO_DIR/ocr/raw/page_${PAD}.txt" ]; then
        log "  Page $page: OCR OK ($(wc -c < "$REPO_DIR/ocr/raw/page_${PAD}.txt") bytes)"
    else
        # Check if empty response (blank page)
        if [ -f "$REPO_DIR/ocr/raw/page_${PAD}.txt" ]; then
            log "  Page $page: OCR empty (blank page?)"
        else
            log "  Page $page: OCR FAILED (exit $OCR_EXIT) — skipping"
            python3 "$SCRIPT_DIR/progress_manager.py" mark "$page" "failed" 2>/dev/null
            failed=$((failed + 1))
            page=$((page + 1))
            continue
        fi
    fi
    
    # --- Enrichment ---
    python3 "$SCRIPT_DIR/enrich_gemini.py" "$page" 2>&1 | tee -a "$LOG"
    ENR_EXIT=${PIPESTATUS[0]}
    
    # Check result
    if [ -f "$REPO_DIR/ocr/enriched/page_${PAD}.txt" ] && [ -s "$REPO_DIR/ocr/enriched/page_${PAD}.txt" ]; then
        log "  Page $page: Enriched OK ($(wc -c < "$REPO_DIR/ocr/enriched/page_${PAD}.txt") bytes)"
        python3 "$SCRIPT_DIR/progress_manager.py" mark "$page" "enriched_done" 2>/dev/null
    else
        log "  Page $page: Enrich FAILED — marking raw_ocr_done"
        python3 "$SCRIPT_DIR/progress_manager.py" mark "$page" "raw_ocr_done" 2>/dev/null
    fi
    
    processed=$((processed + 1))
    page=$((page + 1))
    
    # Small delay between pages to avoid rate limits
    sleep 2
done

log "=== COMPLETE ==="
log "Processed: $processed pages"
log "Failed: $failed pages"

# Git commit & push
bash "$SCRIPT_DIR/git_auto_push.sh" 2>&1 | tee -a "$LOG" || log "Git push skipped"
