#!/usr/bin/env python3
"""
Convert the Shams al-Ma'arif OCR pipeline output into a single
public/manuscript.json consumable by the Next.js reader.

Source layout (Windows path mapped from WSL /mnt/c/...):
  <ocr>/enriched/page_NNN.txt      -> Arabic (original)
  <ocr>/enriched_en/page_NNN.txt   -> English translation
  <ocr>/enriched_id/page_NNN.txt   -> Indonesian translation

Per-file block format (labels vary by file, so we parse robustly):
    Arabic:
    <text>

    English:
    <text>

    Indonesia:
    <text>

Outputs JSON array of:
  { "page": int, "text": { "ar": "...", "en": "...", "id": "..." },
    "scanSrc": "/scans/page-NNN.png" }
Pages missing a language fall back to "(no text on this page)".
"""
import json
import os
import re
import sys
from pathlib import Path

# Resolve paths relative to THIS checkout, never to a hard-coded absolute path.
# A git worktree (or any second clone) must write only to its own tree: an
# absolute default silently overwrote the main clone's manuscript.json and
# clobbered a live translation worker's in-flight output.
REPO_ROOT = Path(__file__).resolve().parents[2]

# The canonical parser lives in scripts/ and handles every real file shape:
# a label alone on its line, a label trailing source text on the same line
# (p543), and two labels sharing one line (p543's Indonesian layer). This
# module used to carry its own LABEL_RE, which only matched a label ALONE on
# its line and therefore read those blocks as empty - p543's 750 characters of
# real Indonesian were replaced with "(tidak ada teks pada halaman ini)" in
# production. One parser, not two.
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from recover_sibling_blocks import clean as _clean  # noqa: E402
from recover_sibling_blocks import parse_blocks as _parse_blocks  # noqa: E402

OCR_DIR = os.environ.get("SHAMS_OCR_DIR", str(REPO_ROOT / "ocr"))
OUT = os.environ.get("SHAMS_OUT", str(REPO_ROOT / "web" / "public" / "manuscript.json"))
# Canonical physical page count. Must match manifest.json and
# web/lib/manuscript.ts (TOTAL_PAGES). Do not hard-code elsewhere.
TOTAL = 604

_LANG_KEY = {"arabic": "ar", "english": "en", "indonesia": "id"}


def parse_blocks(text: str) -> dict:
    """Return ``{lang_key: body}`` from a labelled-block file.

    Delegates to the shared parser so this builder and the validators agree on
    what a label is. A page is reported missing only when the shared parser also
    finds no block for it.
    """
    blocks = {"ar": "", "en": "", "id": ""}
    for label, body, _ in _parse_blocks(text or ""):
        key = _LANG_KEY.get(label.lower())
        if key and body.strip():
            blocks[key] = body
    return blocks


def read_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def main():
    ar_dir = os.path.join(OCR_DIR, "enriched")
    en_dir = os.path.join(OCR_DIR, "enriched_en")
    id_dir = os.path.join(OCR_DIR, "enriched_id")

    out_pages = []
    per_lang_counts = {"ar": 0, "en": 0, "id": 0}

    for n in range(1, TOTAL + 1):
        # files use zero-padded 3-digit names
        name = f"page_{n:03d}.txt"

        # Arabic: raw text (no "Arabic:" label in the source folder)
        ar_raw = read_file(os.path.join(ar_dir, name)).strip()
        ar_text = ar_raw if ar_raw else "(no Arabic text on this page)"

        # English / Indonesian: labelled blocks
        en = parse_blocks(read_file(os.path.join(en_dir, name)))
        idn = parse_blocks(read_file(os.path.join(id_dir, name)))

        # merge
        text = {
            "ar": ar_text,
            "en": en.get("en", "") or "(no English text on this page)",
            "id": idn.get("id", "") or "(tidak ada teks pada halaman ini)",
        }
        for k in ("ar", "en", "id"):
            if text[k] and not text[k].startswith("("):
                per_lang_counts[k] += 1

        out_pages.append(
            {
                "page": n,
                "text": text,
                "scanSrc": f"https://shamsmaarif.warga-digital.com/page-{n:03d}.pdf",
            }
        )

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out_pages, f, ensure_ascii=False, indent=0)

    size_mb = os.path.getsize(OUT) / 1_000_000
    print(f"Wrote {len(out_pages)} pages -> {OUT}")
    print(f"  size: {size_mb:.1f} MB")
    print(f"  with text -> AR:{per_lang_counts['ar']} EN:{per_lang_counts['en']} ID:{per_lang_counts['id']}")


if __name__ == "__main__":
    main()
