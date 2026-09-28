"""Sweep the whole corpus for UNTRANSLATED ARABIC PROSE in a target block.

A target block may legitimately contain single Arabic letters - a magic
square's grid cells ARE the letters of the divine name, and transliterating
them destroys the geometry the style guide requires. So "any Arabic" is the
wrong test. What must not survive is a RUN of Arabic prose: an untranslated
sentence someone forgot to render.

This finds every such run across all 604 pages in both layers, and separates
it from the legitimate grid-cell case by the length of the longest run:

  run >= 4  -> an untranslated word or phrase, needs fixing
  run <= 2  -> grid cells, correct as written

Prints the pages grouped by severity so the sweep can be prioritised.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from recover_sibling_blocks import blocks_for, clean, parse_blocks  # noqa: E402

RUN = re.compile(r"[\u0600-\u06FF]+")
FOLDERS = {"enriched_en": "English", "enriched_id": "Indonesia"}


def main() -> int:
    prose, cells = [], []
    for folder, label in FOLDERS.items():
        for page in range(1, 605):
            path = REPO_ROOT / "ocr" / folder / f"page_{page:03d}.txt"
            if not path.exists():
                continue
            text = clean(path.read_text(encoding="utf-8"))
            if [l for l, _, _ in parse_blocks(text)] != ["Arabic", label]:
                continue  # malformed: another tool's concern
            bodies = blocks_for(text, label)
            if not bodies:
                continue
            body = bodies[0]
            runs = RUN.findall(body)
            if not runs:
                continue
            longest = max(len(r) for r in runs)
            total = sum(len(r) for r in runs)
            row = (page, total, longest, max(runs, key=len))
            (prose if longest >= 4 else cells).append(row)

    prose.sort(key=lambda r: (-r[2], -r[1]))
    print(f"UNTRANSLATED ARABIC PROSE in a target block: {len(prose)} pages")
    for page, total, longest, sample in prose:
        print(f"  p{page:03d}  {total:4d} letters, longest run {longest:3d}  {sample[:34]!r}")

    print(f"\ngrid-cell pages (single letters, correct as written): {len(cells)}")
    print("  " + ", ".join(f"p{p}" for p, _, _, _ in sorted(cells)[:40]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
