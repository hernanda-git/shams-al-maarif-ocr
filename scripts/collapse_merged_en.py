#!/usr/bin/env python3
"""Collapse a merged-batch EN file down to one Arabic + one English block.

Three pages (``109``/``110``, ``133``/``134``, ``297``) were produced when the
batch writer merged two physical pages into one file. The result carries:

    Arabic:  [combined output - see batch]   (29c stub)
    English: --- PAGE NNN TRANSLATION ---     (28c stub)
    Arabic:  <real arabic>
    English: <real english>

The stubs are what a naive parser picks up, and the real blocks that follow are
orphaned. The canonical Arabic source (``ocr/enriched/page_NNN.txt``) decides
which Arabic block is correct; the English block is chosen by folio match against
that canonical folio, so a merged pair can never be filed under the wrong page.

Usage:
  uv run --no-project python scripts/collapse_merged_en.py --scan
  uv run --no-project python scripts/collapse_merged_en.py --apply --pages 109,110,133,134,297
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from recover_sibling_blocks import (  # noqa: E402
    blocks_for,
    clean,
    is_translation_like,
    parse_blocks,
    strip_artifacts,
)
from recover_blocks_cli import _to_ascii_digits  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
OCR = REPO_ROOT / "ocr"


def folio_of(text: str) -> str:
    for line in clean(text).split("\n")[:3]:
        digits = "".join(ch for ch in line if ch.isdigit() or "٠" <= ch <= "۹")
        if digits:
            return _to_ascii_digits(digits)
    return ""


def pick_english(canonical: str, file_text: str) -> tuple[str, str]:
    """Choose the English block whose folio matches the canonical source."""
    want = folio_of(canonical)
    candidates = [
        b
        for b in blocks_for(clean(file_text), "English")
        if is_translation_like(b, "en")
    ]
    if not candidates:
        return "", "no valid English block"
    exact = [b for b in candidates if folio_of(b) == want]
    if exact:
        return exact[0], f"folio {want} match"
    same = [b for b in candidates if b.strip() == candidates[0].strip()]
    best = max(candidates, key=len)
    return best, f"no folio match; took the longest of {len(candidates)} candidates"


def scan(pages: list[int]) -> list[dict]:
    out = []
    for page in pages:
        path = OCR / "enriched_en" / f"page_{page:03d}.txt"
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        parsed = parse_blocks(clean(text))
        labels = [l for l, _, _ in parsed]
        if len(labels) == len(set(labels)) and "Indonesia" not in labels:
            continue  # already canonical
        canonical = clean(
            (OCR / "enriched" / f"page_{page:03d}.txt").read_text(encoding="utf-8")
        )
        body, reason = pick_english(canonical, text)
        out.append(
            {
                "page": page,
                "path": path,
                "labels": labels,
                "sizes": [len(b) for _, b, _ in parsed],
                "body": body,
                "reason": reason,
                "canonical": canonical,
            }
        )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--pages", default="109,110,133,134,297")
    args = parser.parse_args(argv)

    pages = [int(x) for x in args.pages.split(",") if x.strip()]
    findings = scan(pages)
    for f in findings:
        print(
            f"  p{f['page']:03d} labels={f['labels']} sizes={f['sizes']} "
            f"-> keep {len(f['body'])}c ({f['reason']})"
        )
    print(f"\nmerged-batch EN files: {len(findings)}")

    if args.apply:
        for f in findings:
            f["path"].write_text(
                f"Arabic:\n{f['canonical']}\n\nEnglish:\n{f['body']}\n", encoding="utf-8"
            )
            print(f"  wrote p{f['page']:03d}")
    elif findings:
        print("\n(dry run - pass --apply to write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
