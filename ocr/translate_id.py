#!/usr/bin/env python3
"""
Verbatim Arabic→Bahasa Indonesia translation of Shams al-Ma'arif enriched OCR pages.
Mirror of translate_en.py (same model, keys, batch logic) — only the target
language and system prompt differ. NO generation, paraphrasing, or summarization:
the output must be EXACT Bahasa Indonesia translation following the same rules
as the English workers in this repo.

Uses OpenAI gpt-5.4-mini via Responses API with multi-key rotation.

Key rotation: 8 API keys shared across calls. On 429 rate limit, rotates
to next key. Index persists in state file across runs.

Batch mode: packs 3 pages per API call to respect free tier limits.

Usage:
  python3 translate_id.py --gentle   # Process 6 pages (2 API calls, 15s apart)
  python3 translate_id.py --range 1-50
  python3 translate_id.py --status
  python3 translate_id.py --retry-failed
  python3 translate_id.py --all
"""

import os
import re
import json
import time
import sys
import argparse
import requests
from translate_keys import DECODED_KEYS as API_KEYS

# ─────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_DIR = os.path.join(BASE_DIR, "enriched")
OUTPUT_DIR = os.path.join(BASE_DIR, "enriched_id")
STATE_FILE = os.path.join(BASE_DIR, ".translate_state_id.json")

MODEL = "gpt-4.1-mini"
PAGES_PER_BATCH = 3     # pages packed in a single API call
API_DELAY = 15           # seconds between API calls
GENTLE_RUNS = 2          # API calls per --gentle run (= 6 pages)
KEY_COUNT = len(API_KEYS)

if KEY_COUNT == 0:
    print("ERROR: No API keys loaded from translate_keys.py")
    sys.exit(1)


# ─────────────────────────────────────────────────────────
# STATE
# ─────────────────────────────────────────────────────────

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                s = json.load(f)
                # Ensure key_index exists
                if "key_index" not in s:
                    s["key_index"] = 0
                return s
        except Exception:
            return {"completed": [], "failed": [], "key_index": 0}
    return {"completed": [], "failed": [], "key_index": 0}


def save_state(state):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def get_api_key(state):
    """Return current API key and its index. Auto-wraps to 0 if index is out of range."""
    idx = state.get("key_index", 0) % KEY_COUNT
    return idx, API_KEYS[idx]


def rotate_key(state):
    """Advance to next API key. Returns (new_index, new_key)."""
    new_idx = (state.get("key_index", 0) + 1) % KEY_COUNT
    state["key_index"] = new_idx
    save_state(state)
    return new_idx, API_KEYS[new_idx]


def get_page_files():
    all_files = [f for f in os.listdir(SOURCE_DIR) if f.startswith("page_") and f.endswith(".txt")]
    all_files.sort(key=lambda x: int(re.search(r'(\d+)', x).group(1)))
    return all_files


def get_page_num(fn):
    m = re.search(r'(\d+)', fn)
    return int(m.group(1)) if m else 0


# ─────────────────────────────────────────────────────────
# PROMPT
# ─────────────────────────────────────────────────────────
SYSTEM_PROMPT = """Anda adalah penerjemah setia naskah okultisme dan esoterisme Arab ke dalam Bahasa Indonesia. Tugas ANDA SATU-SATUNYA adalah terjemahan VERBATIM (harfiah).

## Aturan Wajib
1. JANGAN meringkas. 2. JANGAN memparafrasa. 3. JANGAN menyederhanakan. 4. JANGAN memodernisasi. 5. JANGAN menafsirkan ulang.
6. JANGAN menjelaskan di dalam terjemahan. 7. JANGAN mengubah struktur kalimat kecuali tata bahasa Indonesia mewajibkannya.
8. JANGAN menghilangkan frasa berulang, gelar kehormatan, invokasi, terminologi teknis, penekanan retoris, atau keambiguan.

## Istilah Teknis
Jika tidak ada padanan Bahasa Indonesia yang tepat, pertahankan transliterasi Arab.
Contoh: رمل→Raml, شكل→Shakl, وتد→Watad, طالع→Tali', روحانية→Ruhaniyyah

## Konten Petak/Diagram
Terjemahkan teks penjelasan di sekitarnya. Pertahankan semua huruf Arab, angka, dan struktur petak apa adanya.
Tandai sebagai [Konten petak dipertahankan apa adanya] dan sertakan yang asli.

## Format Keluaran
Untuk setiap halaman, hasilkan:

Arabic:
[teks asli]

Indonesia:
[terjemahan verbatim]

Notes:
[hanya bila perlu]

## Aturan Akhir
Ketepatan di atas keterbacaan. Kesetiaan di atas keanggunan. Pelestarian verbatim di atas kelancaran gaya."""


# ─────────────────────────────────────────────────────────
# TRANSLATION CORE (with key rotation)
# ─────────────────────────────────────────────────────────

def translate_batch(page_files):
    """Translate 2-3 pages in a single API call. On any error, falls back to next key.
    Cycles through all 8 keys before giving up. Returns list of (filename, result|None, error|None)."""
    if not page_files:
        return []

    state = load_state()
    key_idx, api_key = get_api_key(state)

    # Build input
    parts = []
    for pf in page_files:
        fp = os.path.join(SOURCE_DIR, pf)
        with open(fp, 'r', encoding='utf-8') as f:
            text = f.read().strip()
        if text == "There is no text on this page." or not text:
            text = "[No text on this page]"
        if len(text) > 5000:
            text = text[:5000] + "\n[...truncated...]"
        parts.append(f"--- PAGE {get_page_num(pf)} ---\n{text}")

    combined = "\n\n".join(parts)
    user_msg = (
        f"Terjemahkan setiap halaman di bawah ini secara verbatim dari Arab ke Bahasa Indonesia. "
        f"PENTING: Mulai keluaran setiap halaman dengan penanda halamannya — untuk halaman N, tulis "
        f"--- PAGE N --- lalu bagian Arabic: dan Indonesia:. "
        f"JANGAN gabungkan halaman. Keluarkan BAGIAN TERPISAH untuk setiap halaman.\n\n"
        f"{combined}"
    )

    tried_keys = set()

    for attempt in range(KEY_COUNT * 2):  # enough to try all keys + 1 full cycle
        # Mark current key as tried
        tried_keys.add(key_idx)

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": MODEL,
            "input": [
                {"role": "developer", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg}
            ],
            "max_output_tokens": 8192,
            "temperature": 0.1
        }

        try:
            resp = requests.post(
                "https://api.openai.com/v1/responses",
                headers=headers,
                json=payload,
                timeout=300
            )

            if resp.status_code == 429:
                # Rate limited — rotate to next key
                old_idx = key_idx
                key_idx, api_key = rotate_key(state)
                print(f"⚠ key[{old_idx}] rate-limited → key[{key_idx}]", end=" ", flush=True)
                time.sleep(2)
                continue

            if resp.status_code != 200:
                # Non-429 error — also try next key as fallback
                old_idx = key_idx
                key_idx, api_key = rotate_key(state)
                print(f"⚠ key[{old_idx}] HTTP {resp.status_code} → key[{key_idx}]", end=" ", flush=True)
                time.sleep(5)
                continue

            data = resp.json()

            # Extract output text
            output_text = ""
            for item in data.get("output", []):
                if item.get("type") == "message":
                    for c in item.get("content", []):
                        if c.get("type") == "output_text":
                            output_text += c.get("text", "")

            if not output_text:
                print(f"  key[{key_idx}] empty response → rotating...", end=" ", flush=True)
                key_idx, api_key = rotate_key(state)
                time.sleep(3)
                continue

            # Success! Return results
            return _split_and_write(page_files, output_text)

        except requests.exceptions.Timeout:
            old_idx = key_idx
            key_idx, api_key = rotate_key(state)
            print(f"⚠ key[{old_idx}] timeout → key[{key_idx}]", end=" ", flush=True)
            time.sleep(5)
            continue
        except Exception as e:
            old_idx = key_idx
            key_idx, api_key = rotate_key(state)
            print(f"⚠ key[{old_idx}] error: {str(e)[:50]} → key[{key_idx}]", end=" ", flush=True)
            time.sleep(5)
            continue

    # All keys exhausted — wait 60s for TPM window to reset, then try once more from key[0]
    print(f"\n  ⚠ All {KEY_COUNT} keys exhausted. Waiting 60s for TPM reset...")
    time.sleep(60)

    # Reset to key[0] for last attempt
    state = load_state()
    state["key_index"] = 0
    save_state(state)
    api_key = API_KEYS[0]
    print("  Retrying with key[0] after 60s pause...", end=" ", flush=True)

    try:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        resp = requests.post(
            "https://api.openai.com/v1/responses",
            headers=headers,
            json=payload,
            timeout=300
        )
        if resp.status_code == 200:
            data = resp.json()
            output_text = ""
            for item in data.get("output", []):
                if item.get("type") == "message":
                    for c in item.get("content", []):
                        if c.get("type") == "output_text":
                            output_text += c.get("text", "")
            if output_text:
                print("OK after reset!")
                return _split_and_write(page_files, output_text)
        print(f"Still failing: HTTP {resp.status_code}")
    except Exception as e:
        print(f"Still failing: {e}")

    # Definitely failed
    results = []
    for pf in page_files:
        results.append((pf, None, "All keys exhausted + 60s wait failed"))
    return results


def _split_and_write(page_files, output_text):
    """Split API output into per-page files. Returns results list."""
    results = []
    by_page = {}
    page_nums = {get_page_num(pf) for pf in page_files}

    # Strategy 1: "--- PAGE N ---" markers (with optional trailing word)
    # Strategy 2: "--- PAGE N ---" markers (input format echoed back)
    for pattern in [
        r'--- PAGE (\d+)(?:\s+\w+)?\s*---\n?(.*?)(?=--- PAGE \d+(?:\s+\w+)?\s*---|\Z)',
        r'--- PAGE (\d+) ---\n?(.*?)(?=--- PAGE \d+ ---|\Z)'
    ]:
        if len(by_page) >= len(page_files):
            break
        matches = re.finditer(pattern, output_text, re.DOTALL)
        for m in matches:
            pn = int(m.group(1))
            if pn in page_nums:
                by_page[pn] = m.group(2).strip()

    # Strategy 3: Split on "Arabic:" sections
    if len(by_page) < len(page_files):
        sections = re.split(r'\n(?=Arabic:)', output_text)
        if len(sections) >= len(page_files):
            for idx, pf in enumerate(page_files):
                pn = get_page_num(pf)
                if idx < len(sections):
                    by_page[pn] = sections[idx].strip()

    # Write files
    for pf in page_files:
        pn = get_page_num(pf)
        outpath = os.path.join(OUTPUT_DIR, pf)
        content = by_page.get(pn, "")
        # A valid result must contain an Indonesia: section with real text.
        has_indo = bool(re.search(r'Indonesia:\s*\n\s*\S', content, re.DOTALL))
        if content and has_indo:
            with open(outpath, 'w', encoding='utf-8') as f:
                f.write(content)
            results.append((pf, content, None))
        else:
            # No usable translation — do not write junk. Mark for retry.
            results.append((pf, None, "empty or incomplete translation output"))

    return results


def get_pending_pages():
    state = load_state()
    completed = set(state.get("completed", []))
    return [pf for pf in get_page_files() if pf not in completed]


def process_next_batch(pages_per_run=None, api_delay=None, only_pages=None):
    """Gentle mode: process next batch with key rotation.

    If `only_pages` is given (a set of filenames), only those are processed
    (used by --range). Otherwise the next pending pages are taken.
    """
    if pages_per_run is None:
        pages_per_run = PAGES_PER_BATCH * GENTLE_RUNS
    if api_delay is None:
        api_delay = API_DELAY

    if only_pages is not None:
        all_files = get_page_files()
        pending = [pf for pf in all_files if pf in only_pages
                   and pf not in load_state().get("completed", [])]
    else:
        pending = get_pending_pages()

    if not pending:
        print("All pages translated!")
        return

    batch = pending[:pages_per_run]
    state = load_state()
    key_idx, _ = get_api_key(state)

    print(f"\n{'='*56}")
    print(f"  GENTLE RUN — {len(batch)} pages ({batch[0]} → {batch[-1]})")
    print(f"  Key index:   key[{key_idx}] (rotation on 429)")
    print(f"  API calls:   ~{(len(batch)+PAGES_PER_BATCH-1)//PAGES_PER_BATCH} × {api_delay}s spacing")
    print(f"  Remaining:   {len(pending)} pages")
    print(f"{'='*56}\n")

    sub_batches = [batch[i:i+PAGES_PER_BATCH] for i in range(0, len(batch), PAGES_PER_BATCH)]
    done = fail = 0

    for idx, sub in enumerate(sub_batches):
        labels = ", ".join(s.replace(".txt", "") for s in sub)
        print(f"  [{idx+1}/{len(sub_batches)}] {labels}...", end=" ", flush=True)

        results = translate_batch(sub)

        state = load_state()  # load ONCE before the loop
        for pf, result, error in results:
            if error:
                print(f"\n  FAIL: {pf} — {error}")
                if pf not in state.get("failed", []):
                    state.setdefault("failed", []).append(pf)
                fail += 1
            else:
                state.setdefault("completed", []).append(pf)
                if pf in state.get("failed", []):
                    state["failed"].remove(pf)
                done += 1

        save_state(state)  # save ONCE after all pages in this sub-batch

        if idx < len(sub_batches) - 1:
            print(f"⏳ {api_delay}s")
            time.sleep(api_delay)
        else:
            print()

    remaining = len(get_pending_pages())
    key_idx, _ = get_api_key(load_state())
    print(f"\n  Batch done: {done} ok, {fail} fail, {remaining} remain")
    print(f"  Next key:   key[{key_idx}]\n")


def show_status():
    state = load_state()
    all_pages = get_page_files()
    completed = set(state.get("completed", []))
    failed = set(state.get("failed", []))
    key_idx, _ = get_api_key(state)

    done = len(completed & set(all_pages))
    total = len(all_pages)
    pct = done / total * 100 if total > 0 else 0

    print(f"\n{'='*56}")
    print(f"  TRANSLATION STATUS")
    print(f"{'='*56}")
    print(f"  Model:        {MODEL}")
    print(f"  Total pages:  {total}")
    print(f"  Completed:    {done} ({pct:.1f}%)")
    print(f"  Remaining:    {total - done}")
    print(f"  Failed:       {len(failed)}")
    print(f"  Active key:   key[{key_idx}]")
    print(f"  Total keys:   {KEY_COUNT}")

    out_count = len([f for f in os.listdir(OUTPUT_DIR) if f.startswith("page_")]) if os.path.exists(OUTPUT_DIR) else 0
    print(f"  Output files: {out_count} in enriched_id/")
    print(f"{'='*56}")

    est_req = (total - done + PAGES_PER_BATCH - 1) // PAGES_PER_BATCH
    est_per_key = est_req // KEY_COUNT if KEY_COUNT > 0 else est_req
    print(f"\n  Est. API calls remaining: ~{est_req}")
    print(f"  Per key:                  ~{est_per_key}")
    print(f"  Keys × 50 RPD capacity:   {KEY_COUNT * 50} RPD")

    if failed:
        print("\nFailed:")
        for pf in sorted(failed, key=get_page_num):
            print(f"  - {pf}")

    pending = [pf for pf in all_pages if pf not in completed]
    if pending:
        print(f"\nPending (next 10):")
        for pf in pending[:10]:
            print(f"  - {pf}")
        if len(pending) > 10:
            print(f"  ... and {len(pending)-10} more")
    print()


def retry_failed():
    state = load_state()
    failed = list(state.get("failed", []))
    if not failed:
        print("No failures to retry.")
        return

    print(f"Retrying {len(failed)} failed pages...\n")
    for pf in failed:
        fp = os.path.join(SOURCE_DIR, pf)
        with open(fp, 'r', encoding='utf-8') as f:
            text = f.read()

        if text.strip() == "There is no text on this page." or not text.strip():
            outpath = os.path.join(OUTPUT_DIR, pf)
            with open(outpath, 'w', encoding='utf-8') as f:
                f.write(text)
            state = load_state()
            state["completed"].append(pf)
            if pf in state["failed"]:
                state["failed"].remove(pf)
            save_state(state)
            print(f"  {pf} — no-text, copied")
            continue

        print(f"  {pf}...", end=" ", flush=True)
        result, err = _translate_single(text)
        if err:
            print(f"FAIL: {err}")
        else:
            outpath = os.path.join(OUTPUT_DIR, pf)
            with open(outpath, 'w', encoding='utf-8') as f:
                f.write(result)
            state = load_state()
            state["completed"].append(pf)
            if pf in state["failed"]:
                state["failed"].remove(pf)
            save_state(state)
            print("OK")
        time.sleep(API_DELAY)

    state = load_state()
    if not state.get("failed"):
        print("\nAll failures recovered!")
    else:
        print(f"\n{len(state['failed'])} still failing")


def _translate_single(text):
    """Translate one page. On any error, falls back to next key through all 8 keys."""
    if len(text) > 8000:
        text = text[:8000] + "\n[...truncated...]"

    payload_template = {
        "model": MODEL,
        "input": [
            {"role": "developer", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Terjemahkan halaman Arab ini secara verbatim ke Bahasa Indonesia (Arabic: lalu Indonesia:):\n\n{text}"}
        ],
        "max_output_tokens": 8192,
        "temperature": 0.1
    }

    for attempt in range(KEY_COUNT * 2):
        state = load_state()
        key_idx, api_key = get_api_key(state)
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        try:
            resp = requests.post(
                "https://api.openai.com/v1/responses",
                headers=headers, json=payload_template, timeout=180
            )

            if resp.status_code == 429:
                rotate_key(state)
                print(f"⚠ key[{key_idx}] rate-limited → key[{(key_idx+1)%KEY_COUNT}]", end=" ", flush=True)
                time.sleep(2)
                continue

            if resp.status_code != 200:
                rotate_key(state)
                print(f"⚠ key[{key_idx}] HTTP {resp.status_code} → key[{(key_idx+1)%KEY_COUNT}]", end=" ", flush=True)
                time.sleep(5)
                continue

            data = resp.json()
            output_text = ""
            for item in data.get("output", []):
                if item.get("type") == "message":
                    for c in item.get("content", []):
                        if c.get("type") == "output_text":
                            output_text += c.get("text", "")
            return output_text or None, ("Empty response" if not output_text else None)

        except Exception as e:
            rotate_key(state)
            print(f"⚠ key[{key_idx}] {str(e)[:50]} → key[{(key_idx+1)%KEY_COUNT}]", end=" ", flush=True)
            time.sleep(5)
            continue

    # All keys exhausted — wait 60s, try key[0] once more
    print(f"\n  All {KEY_COUNT} keys exhausted. Waiting 60s...")
    time.sleep(60)
    state = load_state()
    state["key_index"] = 0
    save_state(state)
    try:
        headers = {"Authorization": f"Bearer {API_KEYS[0]}", "Content-Type": "application/json"}
        resp = requests.post(
            "https://api.openai.com/v1/responses",
            headers=headers, json=payload_template, timeout=180
        )
        if resp.status_code == 200:
            data = resp.json()
            output_text = ""
            for item in data.get("output", []):
                if item.get("type") == "message":
                    for c in item.get("content", []):
                        if c.get("type") == "output_text":
                            output_text += c.get("text", "")
            if output_text:
                return output_text, None
    except Exception:
        pass
    return None, "All keys exhausted + 60s wait"


# ─────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Shams al-Ma'arif verbatim translation (multi-key)")
    parser.add_argument("--gentle", action="store_true", help=f"Process ~{PAGES_PER_BATCH*GENTLE_RUNS} pages")
    parser.add_argument("--range", type=str, help="Page range like '1-50'")
    parser.add_argument("--status", action="store_true", help="Show progress")
    parser.add_argument("--retry-failed", action="store_true", help="Retry failed pages")
    parser.add_argument("--all", action="store_true", help="Process ALL remaining pages")

    args = parser.parse_args()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if args.status:
        show_status()
    elif args.retry_failed:
        retry_failed()
    elif args.all:
        process_next_batch(pages_per_run=9999, api_delay=API_DELAY)
    elif args.range:
        m = re.match(r'(\d+)-(\d+)', args.range)
        if m:
            start, end = int(m.group(1)), int(m.group(2))
            in_range = {f"page_{n:03d}.txt" for n in range(start, end + 1)}
            pending = [pf for pf in get_pending_pages() if pf in in_range]
            if not pending:
                print(f"All pages in range {start}-{end} already done.")
                return
            process_next_batch(pages_per_run=len(pending), api_delay=API_DELAY,
                              only_pages=in_range)
        else:
            print(f"Invalid range: {args.range}")
    else:
        process_next_batch()


if __name__ == "__main__":
    main()
