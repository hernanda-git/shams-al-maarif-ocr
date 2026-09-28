"""Restore a degenerate page's cell run to the source's own count.

A degenerate page's source is thousands of identical markers - `[?]` or
`[في المربع]` - standing in for a magic square whose cells the scan could not
read. p244 taught the rule here: a compact 'house convention' representation
loses the grid, so the target block must keep ONE token per source cell.

Three states, and only the first two are defects:

  p105 both layers  1,359 of 1,359 cells kept. Correct - the trailing lone
                    '[' is cosmetic, not a lost cell.
  p253 English      5,211 of 2,606 source cells. DOUBLED. The grid geometry
                    is now wrong, so the page misrepresents the source.
  p253 Indonesian   2,607 of 2,606. Correct, plus a closing note.

So this counts and REPORTS by default, and rewrites only with --apply, and
even then only for a layer whose count does not match. It never invents a
count: the target is whatever the canonical source says, because the source
is the only authority for how many cells the page has.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from recover_sibling_blocks import blocks_for, clean  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
FOLDERS = {"enriched_en": "English", "enriched_id": "Indonesia"}
CELLS = {
    105: ("[في المربع]", {"en": "[in the square]", "id": "[Di dalam persegi]"}),
    253: ("[?]", {"en": "[?]", "id": "[?]", }),
}
NOTE = re.compile(r"\s*\[[^\]\n]*(wafq|tak terbaca|OCR)[^\]\n]*\]\s*$")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pages", nargs="*", type=int, default=sorted(CELLS))
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    problems = 0
    for page in args.pages:
        if page not in CELLS:
            print(f"p{page:03d}  no cell pattern configured")
            continue
        source_marker, per_layer = CELLS[page]
        source = clean(
            (REPO_ROOT / "ocr" / "enriched" / f"page_{page:03d}.txt").read_text(encoding="utf-8")
        )
        want = source.count(source_marker)
        for folder, label in FOLDERS.items():
            short = "en" if folder.endswith("_en") else "id"
            path = REPO_ROOT / "ocr" / folder / f"page_{page:03d}.txt"
            if not path.exists():
                continue
            text = clean(path.read_text(encoding="utf-8"))
            arabic = blocks_for(text, "Arabic")
            body = blocks_for(text, label)
            if not body:
                print(f"p{page:03d} {short}  NO TRANSLATION")
                problems += 1
                continue
            body = body[0]
            if arabic and arabic[0] != source:
                print(f"p{page:03d} {short}  AR block != canonical (fix that first)")
                problems += 1
                continue

            token = per_layer[short]
            got = body.count(token)
            if got == want:
                print(f"p{page:03d} {short}  ok - {got} of {want} cells")
                continue

            problems += 1
            kind = "DOUBLED" if got > want else "TRUNCATED"
            print(f"p{page:03d} {short}  {kind}: {got} cells, source has {want}")
            if not args.apply:
                continue

            # rebuild the run: strip every existing cell token, then append
            # exactly `want` of them, keeping any trailing note the page
            # already had so the change stays surgical.
            note = NOTE.search(body)
            tail = note.group().strip() if note else ""
            stripped = body.replace(token, "\x00").replace("\x00", "")
            stripped = re.sub(r"\n{3,}", "\n\n", stripped).rstrip()
            run = "\n".join([token] * want)
            new = f"{stripped}\n{run}"
            if tail:
                new = f"{new}\n{tail}"
            path.write_text(
                f"Arabic:\n{arabic[0]}\n\n{label}:\n{new}\n", encoding="utf-8"
            )
            check = blocks_for(clean(path.read_text(encoding="utf-8")), label)[0]
            print(f"         -> rewrote to {check.count(token)} cells")

    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
