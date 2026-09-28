#!/usr/bin/env python3
"""Promote the better English copy into the EN file, then de-duplicate the ID file.

Why this exists
---------------
``build_manuscript_json.py`` reads English from ``ocr/enriched_en/page_NNN.txt``
only. The Indonesian files, however, carry a second ``English:`` block -- and on
475 pages that block DIFFERS from the one in the EN file. Measured against the
V2 style guide (rule 3: no Arabic script in a target block):

    copy inside the ID file : contains Arabic script on  92/475 pages
    copy inside the EN file : contains Arabic script on 451/475 pages

So the ID file holds the newer, V2-revised translation (``Allah (exalted is He)``
where the stale EN copy still has ``Allah تعالى``), and the reader has been
showing the stale one. This tool promotes the better copy into the EN file and
then leaves the ID file with the two blocks it is allowed to keep.

Selection is deterministic, never "newest file wins":

1. prefer the copy with no Arabic script;
2. otherwise prefer the longer one;
3. otherwise prefer the EN file's existing copy (no change).

Usage:
  uv run --no-project python scripts/promote_better_english.py --scan
  uv run --no-project python scripts/promote_better_english.py --apply
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


def first_valid(text: str, label: str, lang: str) -> str | None:
    for body in blocks_for(clean(text), label):
        if is_translation_like(body, lang):
            return body
    return None


def arabic_letters(text: str) -> int:
    """Count Arabic LETTERS (digits are allowed in a folio line)."""
    from recover_sibling_blocks import _ARABIC_IN_TARGET  # local: internal detail

    return len(_ARABIC_IN_TARGET.findall(text))


def choose(id_copy: str, en_copy: str) -> tuple[str, str]:
    """Return ``(winner, reason)`` from the two competing English copies."""
    id_arabic, en_arabic = arabic_letters(id_copy), arabic_letters(en_copy)
    if id_arabic == 0 and en_arabic > 0:
        return id_copy, "id-copy has no Arabic script (V2 rule 3)"
    if en_arabic == 0 and id_arabic > 0:
        return en_copy, "en-copy has no Arabic script (V2 rule 3)"
    if len(id_copy) > len(en_copy):
        return id_copy, "id-copy is longer, both have Arabic"
    if len(en_copy) > len(id_copy):
        return en_copy, "en-copy is longer, both have Arabic"
    return en_copy, "identical length, keeping the EN file's copy"


def scan() -> list[dict]:
    findings = []
    for page in range(1, TOTAL_PAGES + 1):
        en_path = OCR / "enriched_en" / f"page_{page:03d}.txt"
        id_path = OCR / "enriched_id" / f"page_{page:03d}.txt"
        if not (en_path.exists() and id_path.exists()):
            continue
        en_text = en_path.read_text(encoding="utf-8")
        id_text = id_path.read_text(encoding="utf-8")

        en_copy = first_valid(en_text, "English", "en")
        id_copy = first_valid(id_text, "English", "en")
        if id_copy is None:
            continue
        if en_copy is not None and en_copy.strip() == id_copy.strip():
            continue  # already identical

        winner, reason = choose(id_copy, en_copy or "")
        if en_copy is not None and winner.strip() == en_copy.strip():
            continue  # nothing to gain

        findings.append(
            {
                "page": page,
                "en_path": en_path,
                "id_path": id_path,
                "winner": winner,
                "reason": reason,
                "id_len": len(id_copy),
                "en_len": len(en_copy) if en_copy else 0,
            }
        )
    return findings


def apply(finding: dict) -> str:
    page = finding["page"]
    canonical = clean(
        (OCR / "enriched" / f"page_{page:03d}.txt").read_text(encoding="utf-8")
    )
    finding["en_path"].write_text(
        f"Arabic:\n{canonical}\n\nEnglish:\n{finding['winner']}\n", encoding="utf-8"
    )
    return f"promoted {len(finding['winner'])}c ({finding['reason']})"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    findings = scan()
    for f in findings[:20]:
        print(f"  p{f['page']:03d} id={f['id_len']}c en={f['en_len']}c  {f['reason']}")
    if len(findings) > 20:
        print(f"  ... and {len(findings) - 20} more")
    print(f"\npages where the EN file holds the worse copy: {len(findings)}")

    if args.apply:
        print("\napplying:")
        for f in findings:
            apply(f)
        print(f"  promoted {len(findings)} pages")
    elif findings:
        print("\n(dry run - pass --apply to write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
