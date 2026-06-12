#!/usr/bin/env python3
"""
progress_manager.py — per-page state tracker for the OCR pipeline.

Tracks each page through:
  pending → raw_ocr_done → enriched_done → committed

Usage:
  python3 progress_manager.py status          # Show summary
  python3 progress_manager.py next-batch      # Print next 10 page numbers to process
  python3 progress_manager.py mark <page> <stage>
  python3 progress_manager.py list <stage>    # List pages in a given stage
"""

import json, os, sys, glob
from datetime import datetime, timezone

STATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state")
PROGRESS_FILE = os.path.join(STATE_DIR, "progress.json")
PAGES_DIR = "C:/Working Folder/Research/pdf/131812-pages"
RAW_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ocr", "raw")
ENR_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ocr", "enriched")
TOTAL_PAGES = 604


def _load():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save(state):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def _detect_actual_state(page_num):
    """Detect current state based on filesystem."""
    raw_path = os.path.join(RAW_DIR, f"page_{int(page_num):03d}.txt")
    enr_path = os.path.join(ENR_DIR, f"page_{int(page_num):03d}.txt")
    raw_exists = os.path.exists(raw_path) and os.path.getsize(raw_path) > 10
    enr_exists = os.path.exists(enr_path) and os.path.getsize(enr_path) > 10
    if enr_exists:
        return "enriched_done"
    if raw_exists:
        return "raw_ocr_done"
    return "pending"


def rebuild():
    """Scan filesystem to rebuild truth state."""
    state = {}
    for p in range(1, TOTAL_PAGES + 1):
        s = _detect_actual_state(p)
        if s != "pending":
            state[str(p)] = {
                "status": s,
                "updated": datetime.now(timezone.utc).isoformat()
            }
    _save(state)
    return state


def status():
    """Print summary."""
    state = _load()
    counts = {"pending": 0, "raw_ocr_done": 0, "enriched_done": 0, "committed": 0}
    for p in range(1, TOTAL_PAGES + 1):
        s = state.get(str(p), {}).get("status", "pending")
        counts[s] = counts.get(s, 0) + 1

    print(f"Total pages:     {TOTAL_PAGES}")
    print(f"OCR raw done:    {counts['raw_ocr_done'] + counts['enriched_done'] + counts['committed']}")
    print(f"Enriched:        {counts['enriched_done'] + counts['committed']}")
    print(f"Committed:       {counts['committed']}")
    print(f"Pending:         {counts['pending']}")
    
    # Last batch info
    batch_log = os.path.join(STATE_DIR, "batch_log.json")
    if os.path.exists(batch_log):
        with open(batch_log, "r") as f:
            logs = json.load(f)
        if logs:
            last = logs[-1]
            print(f"Last batch:      {last.get('timestamp','?')} — {len(last.get('pages',[]))} pages")


def next_batch(batch_size=10):
    """Return list of page numbers for the next batch to process.
    
    Priority:
    1. Pages marked 'failed' that haven't been retried recently (>24h)
    2. Pages that are 'raw_ocr_done' (OCR done, enrichment pending)
    3. Pending (never processed) pages
    """
    state = _load()
    now = datetime.now(timezone.utc)
    pending = []
    
    # First pass: collect failed pages that are due for retry (>24h since failure)
    failed_due = []
    for p in range(1, TOTAL_PAGES + 1):
        entry = state.get(str(p), {})
        s = entry.get("status", "pending")
        if s == "failed":
            updated_str = entry.get("updated", "")
            if updated_str:
                try:
                    updated = datetime.fromisoformat(updated_str)
                    hours_since = (now - updated).total_seconds() / 3600
                    if hours_since >= 24:
                        failed_due.append(p)
                except (ValueError, TypeError):
                    failed_due.append(p)  # can't parse, retry anyway
            else:
                failed_due.append(p)
    
    # Second pass: raw_ocr_done pages (OCR done, need enrichment)
    raw_only = []
    for p in range(1, TOTAL_PAGES + 1):
        s = state.get(str(p), {}).get("status", "pending")
        if s == "raw_ocr_done":
            raw_only.append(p)
    
    # Third pass: truly pending pages (either explicitly 'pending' or not in state)
    never_processed = []
    for p in range(1, TOTAL_PAGES + 1):
        entry = state.get(str(p), {})
        s = entry.get("status", "pending")
        if s == "pending":
            never_processed.append(p)
    
    # Build batch: failed retries first, then raw_only, then never_processed
    # Deduplicate while preserving order
    seen = set()
    pending = []
    for p in failed_due + raw_only + never_processed:
        if p not in seen:
            seen.add(p)
            pending.append(p)
    pending = pending[:batch_size]
    return pending


def mark(page_num, stage):
    """Mark a page as reaching a stage."""
    state = _load()
    state[str(page_num)] = {
        "status": stage,
        "updated": datetime.now(timezone.utc).isoformat()
    }
    _save(state)


def list_stage(stage):
    """List pages in a given stage."""
    state = _load()
    pages = []
    for p in range(1, TOTAL_PAGES + 1):
        s = state.get(str(p), {}).get("status", "pending")
        if s == stage:
            pages.append(p)
    return pages


def log_batch(timestamp, pages_str, batch_size):
    """Append a batch entry to the batch log."""
    import json as j
    log_path = os.path.join(STATE_DIR, "batch_log.json")
    entry = {"timestamp": timestamp, "pages": pages_str, "batch_size": int(batch_size)}
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            log = j.load(f)
    else:
        log = []
    log.append(entry)
    with open(log_path, "w", encoding="utf-8") as f:
        j.dump(log, f, indent=2, ensure_ascii=False)
    print(f"Batch logged: {timestamp} — {pages_str}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: progress_manager.py <status|rebuild|next-batch|mark|list> [args...]")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "status":
        status()
    elif cmd == "rebuild":
        rebuild()
        print("Progress rebuilt from filesystem.")
    elif cmd == "next-batch":
        batch_size = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        pages = next_batch(batch_size)
        print(" ".join(str(p) for p in pages))
    elif cmd == "mark" and len(sys.argv) >= 4:
        mark(sys.argv[2], sys.argv[3])
        print(f"Page {sys.argv[2]} → {sys.argv[3]}")
    elif cmd == "list":
        stage = sys.argv[2] if len(sys.argv) > 2 else "pending"
        pages = list_stage(stage)
        for p in pages:
            print(f"page_{p:03d}")
    elif cmd == "log-batch" and len(sys.argv) >= 5:
        log_batch(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
