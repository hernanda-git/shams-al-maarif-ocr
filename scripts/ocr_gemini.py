#!/usr/bin/env python3
"""
ocr_gemini.py — Stage 1 OCR using Google Gemini API.
Uses multi-key rotation from gemini_rotate.py (8 keys).

Sends a page PDF to Gemini with a carefully crafted prompt to extract
Arabic text VERBATIM — no summarisation, no rephrasing, no invention.

Output is saved to ocr/raw/page_NNN.txt completely unmodified.
"""

import os
import sys
import base64
import json
import time
import argparse
import urllib.request
import urllib.error
from pathlib import Path

# ── Multi-key rotation (8 Gemini keys) ──────────────────────────────────────
_SCRIPTS_DIR = os.path.expanduser("~/.hermes/scripts")
if os.path.isdir(_SCRIPTS_DIR):
    sys.path.insert(0, _SCRIPTS_DIR)

# Import rotator — handles 8 keys with persistent state
from gemini_rotate import GeminiKeyManager, KEY_COUNT, ALL_KEYS_EXHAUSTED

KEY_MGR = GeminiKeyManager()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
# Source pages — auto-detect WSL vs native Windows
_PAGES_DIR_CANDIDATES = [
    "C:/Working Folder/Research/pdf/131812-pages",                          # Windows native
    "/mnt/c/Working Folder/Research/pdf/131812-pages",                     # WSL
    os.path.expanduser("~/../../mnt/c/Working Folder/Research/pdf/131812-pages"),  # fallback
]
PAGES_DIR_SRC = next((p for p in _PAGES_DIR_CANDIDATES if os.path.isdir(p)), _PAGES_DIR_CANDIDATES[0])

# Output directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(SCRIPT_DIR)
RAW_DIR = os.path.join(REPO_DIR, "ocr", "raw")

# Gemini endpoint
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent"


def get_api_key():
    """Retrieve API key from env var, .env, or — now — the key rotator."""
    key = os.environ.get("GEMINI_API_KEY", "")
    if key:
        return key
    # Fallback: use the rotator's current key
    _, key = KEY_MGR.get_key()
    return key


def encode_pdf_to_base64(pdf_path):
    """Read a PDF and return base64-encoded string."""
    with open(pdf_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _sleep_with_backoff(attempt, max_delay=60):
    """Sleep with exponential backoff + jitter. Max delay clamped to 60s."""
    import random
    delay = min(2 ** attempt * 3, max_delay)  # 6, 12, 24, 48, 60...
    jitter = random.uniform(0, 0.5 * delay)
    total = delay + jitter
    print(f"  Waiting {total:.0f}s (backoff attempt {attempt})...", flush=True)
    time.sleep(total)


def _post_to_gemini(api_key, payload):
    """Single HTTP call to Gemini. Raises urllib.error.HTTPError on failure."""
    headers = {
        "Content-Type": "application/json",
        "X-goog-api-key": api_key,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(API_URL, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=45) as resp:
        return json.loads(resp.read().decode("utf-8"))


def ocr_page(page_num):
    """
    Send one page PDF to Gemini OCR.
    Tries every available key in sequence; returns raw text on first success,
    None on quota exhaustion or persistent failure.
    """
    pdf_path = os.path.join(PAGES_DIR_SRC, f"page_{page_num:03d}.pdf")
    if not os.path.exists(pdf_path):
        print(f"[ERROR] PDF not found: {pdf_path}", flush=True)
        return None

    pdf_b64 = encode_pdf_to_base64(pdf_path)
    pdf_size = len(pdf_b64)
    print(f"  [OCR] page_{page_num:03d}.pdf ({pdf_size / 1024:.0f} KB base64)", flush=True)

    prompt_text = (
        "Extract all visible text from this page verbatim. "
        "Output ONLY the extracted text."
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": "application/pdf",
                            "data": pdf_b64
                        }
                    },
                    {
                        "text": prompt_text
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.0,
            "topP": 1.0,
            "topK": 1,
            "maxOutputTokens": 8192
        }
    }

    result = KEY_MGR.call_with_key_rotation(_post_to_gemini, payload)

    if result is ALL_KEYS_EXHAUSTED:
        print(f"  [FAIL] All {KEY_COUNT} keys exhausted for page {page_num} — top up credits", flush=True)
        return None

    if not isinstance(result, dict):
        return None

    candidates = result.get("candidates", [])
    if not candidates:
        block_reason = result.get("promptFeedback", {}).get("blockReason", "unknown")
        print(f"  [WARN] No candidates (blocked: {block_reason})", flush=True)
        return None

    text_parts = []
    for part in candidates[0].get("content", {}).get("parts", []):
        if "text" in part:
            text_parts.append(part["text"])

    raw_text = "\n".join(text_parts).strip()

    if len(raw_text) < 5:
        print(f"  [WARN] Very short response ({len(raw_text)} chars) — may be blank page", flush=True)
        return raw_text if raw_text else ""

    print(f"  [OK] {len(raw_text)} characters extracted", flush=True)
    return raw_text


def save_raw(page_num, text):
    """Save raw OCR text to ocr/raw/page_NNN.txt"""
    os.makedirs(RAW_DIR, exist_ok=True)
    out_path = os.path.join(RAW_DIR, f"page_{page_num:03d}.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"  [SAVED] {out_path}", flush=True)
    return out_path


def process_batch(page_numbers):
    """Process a list of page numbers sequentially. Rotates through ALL keys per page."""
    results = {"success": [], "failed": [], "empty": [], "exhausted": False}
    for i, p in enumerate(page_numbers):
        print(f"\n[{i+1}/{len(page_numbers)}] Processing page {p}...", flush=True)
        text = ocr_page(p)

        if text is None:
            # ocr_page returns None for both single-key failure and ALL_KEYS_EXHAUSTED.
            # We can't easily distinguish them here without extra plumbing, but if
            # the helper printed "All N keys exhausted" the operator should see it.
            results["failed"].append(p)
        else:
            save_raw(p, text)
            if len(text) < 5:
                results["empty"].append(p)
            else:
                results["success"].append(p)

        # Generous delay between pages to avoid rate limiting
        if i < len(page_numbers) - 1:
            delay = 5
            print(f"  Cooling down {delay}s before next page...", flush=True)
            time.sleep(delay)

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gemini OCR for Shams al-Ma'arif")
    parser.add_argument("pages", nargs="+", type=int, help="Page numbers to OCR")
    parser.add_argument("--api-key", help="Gemini API key (override; uses rotator by default)")
    args = parser.parse_args()

    api_key = args.api_key or get_api_key()

    if not api_key:
        print("ERROR: No Gemini API key available. Provide via --api-key or check rotator state.")
        sys.exit(1)

    print(f"  [KEYS] 8-key rotator active — rotating before each API call", flush=True)
    os.makedirs(RAW_DIR, exist_ok=True)
    results = process_batch(args.pages)
    print(f"\n{'='*50}", flush=True)
    print(f"Batch complete:", flush=True)
    print(f"  Success: {len(results['success'])} pages", flush=True)
    print(f"  Failed:  {len(results['failed'])} pages", flush=True)
    print(f"  Empty:   {len(results['empty'])} pages", flush=True)
    if results["failed"]:
        print(f"  Failed pages: {results['failed']}", flush=True)
