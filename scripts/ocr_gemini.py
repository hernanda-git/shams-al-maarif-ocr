#!/usr/bin/env python3
"""
ocr_gemini.py — Stage 1 OCR using Google Gemini API.

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
    """Retrieve API key from env, .env, or --api-key arg."""
    key = os.environ.get("GEMINI_API_KEY", "")
    if key:
        return key
    env_path = os.path.join(REPO_DIR, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("GEMINI_API_KEY="):
                    parts = line.split("=", 1)
                    if len(parts) >= 2:
                        return parts[1].strip().strip("\"'")
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


def ocr_page(page_num, api_key):
    """
    Send one page PDF to Gemini OCR.
    Returns the raw text response, or None on failure.
    """
    pdf_path = os.path.join(PAGES_DIR_SRC, f"page_{page_num:03d}.pdf")
    if not os.path.exists(pdf_path):
        print(f"[ERROR] PDF not found: {pdf_path}", flush=True)
        return None

    pdf_b64 = encode_pdf_to_base64(pdf_path)
    pdf_size = len(pdf_b64)
    print(f"  [OCR] page_{page_num:03d}.pdf ({pdf_size / 1024:.0f} KB base64)", flush=True)

    prompt_text = (
        "You are an expert OCR system for Classical Arabic in Naskh typeface. "
        "Extract ALL visible Arabic text from this page VERBATIM.\n\n"
        "RULES:\n"
        "1. Transcribe EVERY visible character — do not skip, summarise, or rephrase.\n"
        "2. Preserve original line breaks, paragraph spacing, and page layout.\n"
        "3. Keep all diacritical marks (tashkeel: fatHa, kasra, Damma, sukoon, shadda) "
        "exactly as they appear.\n"
        "4. Keep all numerals and page numbers.\n"
        "5. If a word or character is illegible, output [?] — NEVER guess or omit.\n"
        "6. Do NOT add any commentary, explanations, or translations.\n"
        "7. Do NOT correct spelling — transcribe what you see.\n"
        "8. Preserve the original script style.\n"
        "9. Output ONLY the extracted text, no preamble or postscript.\n\n"
        "Begin extraction:"
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

    max_retries = 5
    for attempt in range(1, max_retries + 1):
        try:
            headers = {
                "Content-Type": "application/json",
                "X-goog-api-key": api_key
            }

            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(API_URL, data=data, headers=headers, method="POST")

            with urllib.request.urlopen(req, timeout=300) as resp:
                result = json.loads(resp.read().decode("utf-8"))

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

        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            print(f"  [RETRY {attempt}/{max_retries}] HTTP {e.code}: {error_body[:200]}", flush=True)
            if e.code == 429:
                _sleep_with_backoff(attempt, max_delay=60)
            elif e.code >= 500:
                _sleep_with_backoff(attempt, max_delay=60)
            else:
                time.sleep(10)
        except Exception as e:
            print(f"  [RETRY {attempt}/{max_retries}] {type(e).__name__}: {e}", flush=True)
            _sleep_with_backoff(attempt, max_delay=60)

    print(f"  [FAIL] All {max_retries} attempts exhausted", flush=True)
    return None


def save_raw(page_num, text):
    """Save raw OCR text to ocr/raw/page_NNN.txt"""
    os.makedirs(RAW_DIR, exist_ok=True)
    out_path = os.path.join(RAW_DIR, f"page_{page_num:03d}.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"  [SAVED] {out_path}", flush=True)
    return out_path


def process_batch(page_numbers, api_key):
    """Process a list of page numbers sequentially with rate-limit awareness."""
    results = {"success": [], "failed": [], "empty": []}
    for i, p in enumerate(page_numbers):
        print(f"\n[{i+1}/{len(page_numbers)}] Processing page {p}...", flush=True)
        text = ocr_page(p, api_key)

        if text is None:
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
    parser.add_argument("--api-key", help="Gemini API key (env: GEMINI_API_KEY)")
    args = parser.parse_args()

    api_key = args.api_key or get_api_key()

    if not api_key:
        print("ERROR: GEMINI_API_KEY not set. Provide via --api-key, env var, or .env file.")
        sys.exit(1)

    os.makedirs(RAW_DIR, exist_ok=True)
    results = process_batch(args.pages, api_key)
    print(f"\n{'='*50}", flush=True)
    print(f"Batch complete:", flush=True)
    print(f"  Success: {len(results['success'])} pages", flush=True)
    print(f"  Failed:  {len(results['failed'])} pages", flush=True)
    print(f"  Empty:   {len(results['empty'])} pages", flush=True)
    if results["failed"]:
        print(f"  Failed pages: {results['failed']}", flush=True)
