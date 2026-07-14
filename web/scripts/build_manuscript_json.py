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

OCR_DIR = os.environ.get(
    "SHAMS_OCR_DIR",
    r"C:/Working Folder/Research/shams-al-maarif-ocr/ocr",
)
OUT = os.environ.get(
    "SHAMS_OUT",
    r"C:/Workspace/shams-al-maarif/public/manuscript.json",
)
TOTAL = 600

LABEL_RE = re.compile(r"^\s*(Arabic|English|Indonesia)\s*[:：]?\s*$", re.IGNORECASE)


def parse_blocks(text: str) -> dict:
    """Return {lang_key: body} from a labelled-block file."""
    blocks = {"ar": "", "en": "", "id": ""}
    cur = None
    buf = []
    for line in text.splitlines():
        m = LABEL_RE.match(line)
        if m:
            if cur is not None:
                blocks[cur] = "\n".join(buf).strip()
            label = m.group(1).lower()
            cur = {"arabic": "ar", "english": "en", "indonesia": "id"}.get(label)
            buf = []
        else:
            if cur is not None:
                buf.append(line)
    if cur is not None:
        blocks[cur] = "\n".join(buf).strip()
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
