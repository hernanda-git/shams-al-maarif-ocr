#!/usr/bin/env python3
"""
enrich_gemini.py — Stage 2 Enrichment using Google Gemini API.
Uses multi-key rotation from gemini_rotate.py (8 keys).

Takes raw OCR output (which may have noise from page artefacts, broken
letterforms, ink smudges, etc.) and produces a CLEANED version that:
  - Fixes obvious OCR artefacts (merged/split words, wrong letter guesses)
  - Reconstructs broken letterforms based on context
  - NEVER deletes, rephrases, or summarises
  - If uncertain, keeps the raw text and marks with [?]
"""

import os
import sys
import json
import time
import argparse
import random
import urllib.request
import urllib.error
from pathlib import Path

# ── Multi-key rotation (8 Gemini keys) ──────────────────────────────────────
_SCRIPTS_DIR = os.path.expanduser("~/.hermes/scripts")
if os.path.isdir(_SCRIPTS_DIR):
    sys.path.insert(0, _SCRIPTS_DIR)

from gemini_rotate import GeminiKeyManager, KEY_COUNT

KEY_MGR = GeminiKeyManager()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(SCRIPT_DIR)
RAW_DIR = os.path.join(REPO_DIR, "ocr", "raw")
ENR_DIR = os.path.join(REPO_DIR, "ocr", "enriched")

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent"


def get_api_key():
    """Retrieve API key from env var, .env, or — now — the key rotator."""
    key = os.environ.get("GEMINI_API_KEY", "")
    if key:
        return key
    # Fallback: use the rotator's current key
    _, key = KEY_MGR.get_key()
    return key


def _sleep_with_backoff(attempt, max_delay=60):
    """Sleep with exponential backoff + jitter. Max delay clamped to 60s."""
    delay = min(2 ** attempt * 3, max_delay)
    jitter = random.uniform(0, 0.5 * delay)
    total = delay + jitter
    print(f"  Waiting {total:.0f}s (backoff attempt {attempt})...", flush=True)
    time.sleep(total)


def enrich_page_text(page_num, raw_text, api_key):
    """
    Send raw OCR text to Gemini for conservative correction.
    Returns the enriched text.
    """
    prompt_text = (
        "You are a Classical Arabic text restoration expert. Your task is to "
        "clean OCR noise while preserving EVERY character of the original.\n\n"
        "RULES — FOLLOW THEM STRICTLY:\n"
        "1. Fix ONLY obvious OCR errors: broken letterforms, merged words that should be split, "
        "wrong character substitutions common in Arabic Naskh OCR.\n"
        "2. NEVER delete any content — if you can't read it, keep the raw text as-is.\n"
        "3. NEVER rephrase, summarise, rewrite, or modernise the language.\n"
        "4. NEVER add explanatory notes or commentary.\n"
        "5. Preserve ALL line breaks and paragraph structure exactly.\n"
        "6. Restore diacritical marks (tashkeel) where they are clearly visible in context.\n"
        "7. If a word appears to have broken/missing letters but the context is clear, "
        "reconstruct it conservatively and mark with [~] only if uncertain.\n"
        "8. If an entire passage is garbled beyond recognition, leave it verbatim.\n"
        "9. Preserve ALL numerals, page numbers, and formatting.\n"
        "10. Output ONLY the restored text — no preamble, no commentary.\n\n"
        "RAW OCR TEXT:\n"
        "---\n"
        f"{raw_text}\n"
        "---\n\n"
        "RESTORED TEXT:"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt_text}
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
                print(f"  [WARN] No candidates for enrichment", flush=True)
                return raw_text  # Fallback: return raw

            text_parts = []
            for part in candidates[0].get("content", {}).get("parts", []):
                if "text" in part:
                    text_parts.append(part["text"])

            enriched = "\n".join(text_parts).strip()

            # Safety check: enriched should not be dramatically shorter than raw
            if len(enriched) < len(raw_text) * 0.5:
                print(f"  [WARN] Enriched text is <50% of raw length ({len(enriched)} vs {len(raw_text)}) — using raw", flush=True)
                return raw_text

            # Safety check: enriched should not be dramatically longer (avoid hallucination)
            if len(enriched) > len(raw_text) * 3:
                print(f"  [WARN] Enriched >3x raw length ({len(enriched)} vs {len(raw_text)}) — using raw", flush=True)
                return raw_text

            print(f"  [ENRICHED] {len(raw_text)} → {len(enriched)} chars", flush=True)
            return enriched

        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            print(f"  [RETRY {attempt}/{max_retries}] HTTP {e.code}: {error_body[:200]}", flush=True)
            if e.code == 429:
                # Rate limited — rotate to next key!
                old_idx, _ = KEY_MGR.get_key()
                new_idx, new_key = KEY_MGR.rotate_key()
                api_key = new_key
                print(f"  [ROTATE] Key {old_idx} → key {new_idx} (429 rate limit)", flush=True)
                _sleep_with_backoff(attempt, max_delay=60)
            elif e.code >= 500:
                _sleep_with_backoff(attempt, max_delay=60)
            else:
                time.sleep(10)
        except Exception as e:
            print(f"  [RETRY {attempt}/{max_retries}] {type(e).__name__}: {e}", flush=True)
            _sleep_with_backoff(attempt, max_delay=60)

    print(f"  [FAIL] Enrichment failed — falling back to raw text", flush=True)
    return raw_text


def process_batch(page_numbers):
    """Enrich a batch of pages from their raw OCR files, rotating Gemini key each call."""
    results = {"enriched": [], "failed": [], "fallback_raw": []}

    for i, p in enumerate(page_numbers):
        raw_path = os.path.join(RAW_DIR, f"page_{p:03d}.txt")
        if not os.path.exists(raw_path):
            print(f"\n[{i+1}/{len(page_numbers)}] Page {p}: no raw OCR found, skipping", flush=True)
            results["failed"].append(p)
            continue

        with open(raw_path, "r", encoding="utf-8") as f:
            raw_text = f.read()

        if not raw_text.strip():
            print(f"\n[{i+1}/{len(page_numbers)}] Page {p}: empty raw OCR, copying empty", flush=True)
            os.makedirs(ENR_DIR, exist_ok=True)
            enr_path = os.path.join(ENR_DIR, f"page_{p:03d}.txt")
            with open(enr_path, "w", encoding="utf-8") as f:
                f.write("")
            results["enriched"].append(p)
            continue

        # Rotate to a fresh key before every API call
        idx, api_key = KEY_MGR.rotate_key()
        print(f"\n[{i+1}/{len(page_numbers)}] Enriching page {p} ({len(raw_text)} chars) with key [{idx}]...", flush=True)
        enriched = enrich_page_text(p, raw_text, api_key)

        os.makedirs(ENR_DIR, exist_ok=True)
        enr_path = os.path.join(ENR_DIR, f"page_{p:03d}.txt")
        with open(enr_path, "w", encoding="utf-8") as f:
            f.write(enriched)
        print(f"  [SAVED] {enr_path}", flush=True)

        if enriched == raw_text:
            results["fallback_raw"].append(p)
        else:
            results["enriched"].append(p)

        if i < len(page_numbers) - 1:
            time.sleep(3)  # Increased delay to avoid rate limiting

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gemini Enrichment for OCR output")
    parser.add_argument("pages", nargs="+", type=int, help="Page numbers to enrich")
    parser.add_argument("--api-key", help="Gemini API key (override; uses rotator by default)")
    args = parser.parse_args()

    api_key = args.api_key or get_api_key()
    if not api_key:
        print("ERROR: No Gemini API key available.")
        sys.exit(1)

    print(f"  [KEYS] 8-key rotator active — rotating before each API call", flush=True)
    os.makedirs(ENR_DIR, exist_ok=True)
    results = process_batch(args.pages)
    print(f"\n{'='*50}", flush=True)
    print(f"Enrichment complete:", flush=True)
    print(f"  Enriched: {len(results['enriched'])} pages", flush=True)
    print(f"  Fallback (raw kept): {len(results['fallback_raw'])}", flush=True)
    print(f"  Failed:  {len(results['failed'])}", flush=True)
