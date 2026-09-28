"""Report, per page, whether each target block opens with its own folio line.

The V2 page validator does not check this, so a block can be filed under the
wrong page and still pass. Page 61's English opens '- 54 -' where its source
says 55, and its body is page 60's text (91.9% shared shingles) with none of
page 61's own content.

A target that does not open with a folio line is a different, milder defect -
it is a continuation, not a copy of a neighbour - so it is listed separately
from a folio that names the WRONG page.

  leading   the block's first line is its own page's folio  -> healthy
  wrong     it opens with a folio that belongs to another page -> misfiled
  no-folio  it opens mid-prose                                -> continuation
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from recover_sibling_blocks import blocks_for, clean, parse_blocks  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
TOTAL = 604
FOLDERS = {"enriched_en": "English", "enriched_id": "Indonesia"}
AR_DIGITS = str.maketrans("\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669", "0123456789")


def leading_folio(text: str) -> str | None:
    for line in text.splitlines():
        if not line.strip():
            continue
        if "-" in line or "\u2014" in line or "(" in line:
            m = re.search(r"[\u0660-\u0669]+|\d{1,3}", line)
            if m:
                return str(int(m.group().translate(AR_DIGITS)))
        return None
    return None


def main() -> int:
    print(f"{'page':>5} {'layer':10s} {'verdict':9s} detail")
    wrong = no_folio = 0
    for page in range(1, TOTAL + 1):
        spath = REPO_ROOT / "ocr" / "enriched" / f"page_{page:03d}.txt"
        if not spath.exists():
            continue
        want = leading_folio(clean(spath.read_text(encoding="utf-8")))
        for folder, label in FOLDERS.items():
            path = REPO_ROOT / "ocr" / folder / f"page_{page:03d}.txt"
            if not path.exists():
                continue
            text = clean(path.read_text(encoding="utf-8"))
            if [l for l, _, _ in parse_blocks(text)] != ["Arabic", label]:
                continue
            bodies = blocks_for(text, label)
            if not bodies or len(bodies[0]) < 40:
                continue
            got = leading_folio(bodies[0])
            if not want or not got:
                continue
            if got == want:
                continue
            if abs(int(got) - int(want)) == 1:
                continue  # normal print/scan realignment
            verdict = "wrong" if abs(int(got) - int(want)) > 1 else "no-folio"
            if verdict == "wrong":
                wrong += 1
            else:
                no_folio += 1
            print(f"{page:5d} {label:10s} {verdict:9s} source {want} vs target {got}")
    print(f"\nwrong page: {wrong}   continuation with no folio line: see copy-forward report")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
