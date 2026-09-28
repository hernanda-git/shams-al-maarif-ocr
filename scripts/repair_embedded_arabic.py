#!/usr/bin/env python3
"""Restore a truncated canonical Arabic block in a target file.

A translation worker sometimes writes the Arabic block as a PREFIX of the source
instead of the whole thing, and the target block then sits in the file with a
body that no longer matches ``ocr/enriched/page_NNN.txt``. Observed twice:

    p105 EN : 2444c of a 16382c source (a `[في المربع]` grid repetition run cut off)
    p550 EN : 1296c of a 13893c source -- and that prefix is page 549's text,
              because the worker read the wrong file

The validator reports this as ``embedded Arabic differs from canonical source``.
The fix is mechanical and safe: the canonical source is authoritative and the
target-language block is preserved exactly as the worker wrote it.

Usage:
  uv run --no-project python scripts/repair_embedded_arabic.py --scan
  uv run --no-project python scripts/repair_embedded_arabic.py --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from recover_sibling_blocks import blocks_for, clean, parse_blocks  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
OCR = REPO_ROOT / "ocr"
TOTAL_PAGES = 604

FOLDERS = {
    "enriched_en": ("English", "en"),
    "enriched_id": ("Indonesia", "id"),
}


def scan() -> list[dict]:
    findings = []
    for folder, (label, lang) in FOLDERS.items():
        for page in range(1, TOTAL_PAGES + 1):
            src_path = OCR / "enriched" / f"page_{page:03d}.txt"
            tgt_path = OCR / folder / f"page_{page:03d}.txt"
            if not (src_path.exists() and tgt_path.exists()):
                continue
            canonical = clean(src_path.read_text(encoding="utf-8"))
            text = clean(tgt_path.read_text(encoding="utf-8"))
            embedded = blocks_for(text, "Arabic")
            if not embedded:
                continue
            block = embedded[0]
            if block == canonical:
                continue
            # A long, unrelated file is not the defect this tool fixes. Only a
            # TRUNCATION is: the embedded block is a leading slice of the source
            # and the remainder was dropped. Line-break flattening alone also
            # produces a mismatch, and the validator already tolerates that, so
            # measure the shortfall, not equality.
            shortfall = len(canonical) - len(block)
            if shortfall <= 0:
                continue
            # Collapse whitespace on both sides: a real truncation is thousands
            # of characters, a newline difference is a handful.
            flat_c = " ".join(canonical.split())
            flat_b = " ".join(block.split())
            if not flat_c.startswith(flat_b[:200]):
                continue
            if len(flat_c) - len(flat_b) < 200:
                continue
            findings.append(
                {
                    "folder": folder,
                    "page": page,
                    "label": label,
                    "lang": lang,
                    "path": tgt_path,
                    "got": len(block),
                    "want": len(canonical),
                    "shortfall": shortfall,
                    "prefix": flat_c.startswith(flat_b[:200]),
                    "keep": blocks_for(text, label),
                }
            )
    return findings


def apply(finding: dict) -> str:
    canonical = clean(
        (OCR / "enriched" / f"page_{finding['page']:03d}.txt").read_text(encoding="utf-8")
    )
    kept = finding["keep"][0] if finding["keep"] else ""
    finding["path"].write_text(
        f"Arabic:\n{canonical}\n\n{finding['label']}:\n{kept}\n", encoding="utf-8"
    )
    return f"restored {finding['want']}c of Arabic, kept {len(kept)}c of {finding['label']}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    findings = scan()
    for f in findings:
        print(
            f"  {f['folder']:12s} p{f['page']:03d} arabic {f['got']}c -> {f['want']}c "
            f"(prefix={f['prefix']})  {f['label']} block {len(f['keep'][0]) if f['keep'] else 0}c"
        )
    print(f"\nfiles with a non-canonical Arabic block: {len(findings)}")

    if args.apply:
        print("\napplying:")
        for f in findings:
            print(f"  {f['folder']} p{f['page']:03d}: {apply(f)}")
    elif findings:
        print("\n(dry run - pass --apply to write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
