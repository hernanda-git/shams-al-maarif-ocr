#!/usr/bin/env python3
"""Write the exact V2 no-text marker where the Arabic source is blank.

``verify_translation_v2_page.py`` requires that a page whose canonical Arabic is
itself a no-text marker carries exactly ``[NO VISIBLE TEXT]`` (EN) or
``[TIDAK ADA TEKS TERLIHAT]`` (ID). Four pages instead carry loose prose such
as ``There is no text on this page.`` -- a legacy marker the validator does not
accept, and which the builder renders as a visible sentence rather than a
neutral marker.

This is a marker normalisation, not a translation: no content is invented.

Usage:
  uv run --no-project python scripts/fix_blank_markers.py --scan
  uv run --no-project python scripts/fix_blank_markers.py --apply
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from recover_sibling_blocks import blocks_for, clean, parse_blocks  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
OCR = REPO_ROOT / "ocr"
TOTAL_PAGES = 604

EN_MARKER = "[NO VISIBLE TEXT]"
ID_MARKER = "[TIDAK ADA TEKS TERLIHAT]"

# An Arabic layer that is itself a no-text note rather than manuscript text.
BLANK_AR = re.compile(
    r"no (visible )?(arabic )?text|does not contain any|"
    r"tidak ada teks|tidak mengandung teks|"
    r"لا يحتوي على أي|صفحة فارغة|هalaman kosong",
    re.IGNORECASE,
)
# Prose that means the same thing but is NOT the V2 contract.
LOOSE = re.compile(
    r"there is no |no text visible|tidak ada teks|does not contain|"
    r"halaman ini kosong|no visible|this page is empty|"
    r"tidak ada teks arab|berisi teks arab",
    re.IGNORECASE,
)

FOLDERS = {"enriched_en": ("English", EN_MARKER, "en"), "enriched_id": ("Indonesia", ID_MARKER, "id")}


def scan() -> list[dict]:
    out = []
    for folder, (label, marker, lang) in FOLDERS.items():
        for page in range(1, TOTAL_PAGES + 1):
            src_path = OCR / "enriched" / f"page_{page:03d}.txt"
            tgt_path = OCR / folder / f"page_{page:03d}.txt"
            if not (src_path.exists() and tgt_path.exists()):
                continue
            src = clean(src_path.read_text(encoding="utf-8"))
            if len(src) > 200 or not BLANK_AR.search(src):
                continue  # a real content page
            body = ""
            for b in blocks_for(clean(tgt_path.read_text(encoding="utf-8")), label):
                body = b
                break
            if body.strip() == marker:
                continue
            out.append(
                {
                    "page": page,
                    "folder": folder,
                    "label": label,
                    "marker": marker,
                    "lang": lang,
                    "path": tgt_path,
                    "current": body,
                    "canonical": src,
                }
            )
    return out


def apply(finding: dict) -> None:
    finding["path"].write_text(
        f"Arabic:\n{finding['canonical']}\n\n{finding['label']}:\n{finding['marker']}\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    findings = scan()
    for f in findings:
        print(f"  {f['folder']:12s} p{f['page']:03d} {f['marker']}  <- {f['current'][:60]!r}")
    print(f"\nblank pages needing the exact marker: {len(findings)}")

    if args.apply:
        for f in findings:
            apply(f)
        print(f"  normalised {len(findings)} pages")
    elif findings:
        print("\n(dry run - pass --apply to write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
