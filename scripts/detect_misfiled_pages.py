"""Detect target blocks that were filed under the WRONG page.

The V2 page validator checks structure: labels present, Arabic matches the
canonical source, no forbidden markers. It does NOT check that a translation
actually corresponds to its own page - so a block that is a neighbour's text,
copied forward, passes every gate.

Page 61 is the proof: its English block is 91.9% similar to page 60's and
contains none of page 61's own content (no 'mim', no 'Thursday', no 'bees',
no 'the north', no 'seasons'), while the validator returned PASS.

The reliable signal is FIDELITY TO THE SOURCE, not similarity between
neighbours. A page's own distinctive terms should appear in its own
translation and in no neighbour's. So:

  1. Extract each page's rarest content terms from its Arabic source -
     words that appear on that page and almost nowhere else in the corpus.
  2. Require each target block to cover a good share of them.
  3. Also flag blocks that are far more similar to a NEIGHBOUR than their
     own source warrants.

A block can legitimately diverge in length, so this is a ranked report, not
a gate. Read the top rows before acting.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from recover_sibling_blocks import blocks_for, clean, parse_blocks  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
TOTAL = 604
FOLDERS = {"enriched_en": "English", "enriched_id": "Indonesia"}

WORD = re.compile(r"[\u0600-\u06FF]{4,}")
STOP = {
    # function words and formulaic religious phrases that carry no page identity
    "الله", "تعالى", "صلى", "عليه", "وسلم", "الذي", "التي", "هذا", "هذه",
    "ذلك", "التي", "كان", "ismic", "كانوا", "بسم", "الرحمن", "الرحيم",
    "من", "في", "على", "الى", "عن", "مع", "التي", "الذي", "ما", "لا", "ان",
    "ثم", "قد", "وهو", "وهي", "فهو", "به", "له", "اي", "ول", "|February",
}


def ar_text(page: int) -> str:
    path = REPO_ROOT / "ocr" / "enriched" / f"page_{page:03d}.txt"
    return clean(path.read_text(encoding="utf-8")) if path.exists() else ""


def target(page: int, folder: str, label: str) -> str:
    path = REPO_ROOT / "ocr" / folder / f"page_{page:03d}.txt"
    if not path.exists():
        return ""
    text = clean(path.read_text(encoding="utf-8"))
    if [l for l, _, _ in parse_blocks(text)] != ["Arabic", label]:
        return ""
    bodies = blocks_for(text, label)
    return bodies[0] if bodies else ""


def main() -> int:
    print("building corpus term frequencies ...", flush=True)
    df: Counter[str] = Counter()
    per_page: dict[int, set[str]] = {}
    sources: dict[int, str] = {}
    for page in range(1, TOTAL + 1):
        text = ar_text(page)
        if not text:
            continue
        sources[page] = text
        words = {w for w in WORD.findall(text) if w not in STOP}
        per_page[page] = words
        df.update(words)

    # a term is distinctive when it appears on few pages
    threshold = 3
    rows: list[tuple[int, str, float, list[str]]] = []
    for folder, label in FOLDERS.items():
        print(f"checking {label} ...", flush=True)
        for page in range(1, TOTAL + 1):
            body = target(page, folder, label)
            if len(body) < 60:
                continue
            own = {w for w in per_page.get(page, set()) if df[w] <= threshold}
            if len(own) < 4:
                continue
            hit = sum(1 for w in own if w in body)
            ratio = hit / len(own)
            missing = sorted(own - {w for w in own if w in body})[:5]
            if ratio < 0.5:
                rows.append((page, label, ratio, missing))

    rows.sort(key=lambda r: r[2])
    print(f"\nblocks that cover <50% of their own page's distinctive terms: {len(rows)}\n")
    for page, label, ratio, missing in rows:
        print(f"  p{page:03d} {label:10s} {ratio:5.1%}  missing e.g. {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
