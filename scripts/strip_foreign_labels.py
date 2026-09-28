#!/usr/bin/env python3
"""Remove a foreign label block from a target file, but only when it is safe.

The V2 contract is one ``Arabic:`` block plus exactly one target block per file.
The batch writer left two defects that violate it:

  * a 3-layer ``enriched_id`` file (Arabic + English + Indonesia);
  * a duplicated block inside one file (merged batch output).

Stripping a block is only safe when the same text still exists in the sibling
file. In 475 cases the ID file's ``English:`` block DIFFERS from the EN file's:
the ID copy is the V2-revised one (no Arabic script, per style guide 3) while the
EN copy is stale. Deleting the ID copy there would destroy the better text, so
this tool refuses those and reports them for review instead.

Usage:
  uv run --no-project python scripts/strip_foreign_labels.py --scan
  uv run --no-project python scripts/strip_foreign_labels.py --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from recover_sibling_blocks import (  # noqa: E402
    blocks_for,
    clean,
    is_translation_like,
    parse_blocks,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
OCR = REPO_ROOT / "ocr"
TOTAL_PAGES = 604

FOLDERS = {
    "enriched_en": ("English", {"Arabic", "English"}, "enriched_id", "en"),
    "enriched_id": ("Indonesia", {"Arabic", "Indonesia"}, "enriched_en", "id"),
}


def first_valid(text: str, label: str, lang: str) -> str | None:
    for body in blocks_for(clean(text), label):
        if is_translation_like(body, lang):
            return body
    return None


def scan() -> list[dict]:
    findings = []
    for folder, (own_label, allowed, sibling_folder, own_lang) in FOLDERS.items():
        for page in range(1, TOTAL_PAGES + 1):
            path = OCR / folder / f"page_{page:03d}.txt"
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            parsed = parse_blocks(clean(text))
            labels = [label for label, _, _ in parsed]
            foreign = sorted({l for l in labels if l not in allowed})
            duplicated = sorted({l for l in labels if labels.count(l) > 1})
            if not foreign and not duplicated:
                continue

            sibling_path = OCR / sibling_folder / f"page_{page:03d}.txt"
            sibling_text = (
                sibling_path.read_text(encoding="utf-8")
                if sibling_path.exists()
                else ""
            )

            unsafe = []
            for label in sorted(set(foreign) | set(duplicated)):
                lang = "en" if label == "English" else "id"
                here = [body for l, body, _ in parsed if l == label]
                there = first_valid(sibling_text, label, lang)
                for body in here:
                    if there is not None and body.strip() == there.strip():
                        continue  # an identical copy exists in the sibling
                    if not is_translation_like(body, lang):
                        continue  # a batch stub: safe to drop
                    unsafe.append(label)

            findings.append(
                {
                    "folder": folder,
                    "page": page,
                    "path": path,
                    "own_label": own_label,
                    "own_lang": own_lang,
                    "foreign": foreign,
                    "duplicated": duplicated,
                    "unsafe": sorted(set(unsafe)),
                }
            )
    return findings


def apply(finding: dict) -> str:
    """Rewrite the file as canonical Arabic + its own single target block."""
    text = clean(finding["path"].read_text(encoding="utf-8"))
    canonical = clean(
        (OCR / "enriched" / f"page_{finding['page']:03d}.txt").read_text(encoding="utf-8")
    )
    own, kept, seen = finding["own_label"], "", False
    for label, body, _ in parse_blocks(text):
        if label == "Arabic":
            continue
        if label == own and not seen and is_translation_like(body, finding["own_lang"]):
            kept, seen = body, True
    finding["path"].write_text(
        f"Arabic:\n{canonical}\n\n{own}:\n{kept}\n", encoding="utf-8"
    )
    return f"kept {len(kept)} chars of {own}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    findings = scan()
    safe = [f for f in findings if not f["unsafe"]]
    unsafe = [f for f in findings if f["unsafe"]]

    for f in findings:
        flag = "REVIEW" if f["unsafe"] else "safe"
        print(
            f"  {flag:6s} {f['folder']:12s} p{f['page']:03d} foreign={f['foreign']} "
            f"dup={f['duplicated']} unsafe={f['unsafe']}"
        )
    print(f"\nsafe to strip: {len(safe)}   needs review: {len(unsafe)}")
    if unsafe:
        pages = sorted({f["page"] for f in unsafe})
        print(f"  review pages ({len(pages)}): {pages}")

    if args.apply:
        print("\napplying safe only:")
        for f in safe:
            print(f"  {f['folder']} p{f['page']:03d}: {apply(f)}")
    elif findings:
        print("\n(dry run - pass --apply to write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
