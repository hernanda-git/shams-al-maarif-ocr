"""Enumerate every degenerate SOURCE page, and what each target layer did with it.

A source page is DEGENERATE when the scan failed: the page is mostly one
repeated token, either a filler glyph or the `[?]` illegibility marker. These
are not a defect class to be repaired - the source is what it is, and the
correct treatment is for the target block to translate the real prose and
DESCRIBE the unrecoverable run with `[UNCLEAR: ...]`, as p095, p142, p250,
p253 and p402 now do.

The danger is not the page. It is the drift I found twice by accident:
  p095 - the same source counted three different ways across the canonical
         and two target files, so a length comparison showed a "swap" that
         did not exist
  p250 - the two layers failed DIFFERENTLY, a swap in one and a truncation
         in the other, so one framing could only describe half of it

So this reports, per degenerate page: the canonical length, the marker
count, the real-letter count, and for each layer whether it holds the
canonical block and whether its body documents the damage. A layer that is
neither equal to canonical nor explains itself is flagged.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from recover_sibling_blocks import blocks_for, clean  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
TOTAL = 604
FOLDERS = {"enriched_en": "English", "enriched_id": "Indonesia"}
FILLER = "[\u200e?\u200f]?"  # the [?] marker, tolerant of stray marks
UNCLEAR_MARK = "[?]"  # a literal '?' between brackets
ARABIC = re.compile(r"[\u0600-\u06FF]")
ANY_FILLER = re.compile(r"\[[^\]\n]{0,4}\]")


def classify(source: str) -> tuple[str, int, int] | None:
    """(kind, filler count, Arabic letters) if degenerate, else None."""
    lines = [l for l in source.splitlines() if l.strip()]
    if len(lines) < 4:
        return None
    counts = Counter(lines)
    top, n = counts.most_common(1)[0]
    if n <= 0.5 * len(lines):
        return None
    letters = len(ARABIC.findall(source))
    kind = "unclear-marker" if top.strip().startswith("[") else "repeated-glyph"
    # a repeated line that is real prose (e.g. a dhikr) is intentional
    if kind == "repeated-glyph" and letters > 40 * n:
        return None
    return kind, source.count(UNCLEAR_MARK), letters


def documents(body: str) -> bool:
    """Does the target block EXPLAIN the damage, in any of the corpus's ways?

    My first version looked for the literal token `[UNCLEAR` and reported
    p105, p142 and p253 as undocumented. They are not. p105 ends with an
    in-prose note, p142 says 'repeated 500 times - preserved as-is; the
    source OCR contains only this repeated name', p253's Indonesian writes
    'cap tak terbaca dalam OCR sumber'. A check that only recognises the
    phrasing I happened to write on p250 would have sent workers to 'fix'
    three correct pages - the same class of error as p061's citation
    markers, where 81 blocks were flagged for a perfectly normal usage.

    So: a block counts as documenting if it says so in ANY language, and the
    test is deliberately broad. A false negative here costs a manual look;
    a false positive costs a worker rewriting a correct page.
    """
    lowered = body.lower()
    markers = (
        "unclear",  # English
        "tidak terbaca", "tidak dapat dipulihkan", "dipertahankan apa",
        "hanya memuat",  # Indonesian
    )
    if any(m in lowered for m in markers):
        return True
    # a bracketed explanatory note, which is how the corpus marks a note
    return bool(re.search(r"\[[^\]\n]*(recovered|recoverable|OCR|grid|square|preserve)", body, re.I))


def main() -> int:
    rows = []
    for page in range(1, TOTAL + 1):
        src_path = REPO_ROOT / "ocr" / "enriched" / f"page_{page:03d}.txt"
        if not src_path.exists():
            continue
        source = clean(src_path.read_text(encoding="utf-8"))
        verdict = classify(source)
        if not verdict:
            continue
        kind, markers, letters = verdict
        layers = []
        for folder, label in FOLDERS.items():
            path = REPO_ROOT / "ocr" / folder / f"page_{page:03d}.txt"
            if not path.exists():
                layers.append(f"{folder[-2:]}:MISSING")
                continue
            text = clean(path.read_text(encoding="utf-8"))
            arabic = blocks_for(text, "Arabic")
            body = blocks_for(text, label)
            if not arabic or arabic[0] != source:
                state = "AR-WRONG"
            elif not body:
                state = "NO-TRANSLATION"
            elif documents(body[0]):
                state = "documented"
            else:
                state = "undocumented"
            layers.append(f"{folder[-2:]}:{state}")
        rows.append((page, kind, len(source), markers, letters, layers))

    print("DEGENERATE SOURCE PAGES: %d" % len(rows))
    print()
    print("page  kind             canon  markers  letters  layers")
    for page, kind, size, markers, letters, layers in rows:
        print(
            "p%03d  %-16s %6d  %7d  %7d  %s"
            % (page, kind, size, markers, letters, " ".join(layers))
        )

    flagged = [
        (p, l) for p, _k, _s, _m, _l, layers in rows for l in layers
        if "AR-WRONG" in l or "NO-TRANSLATION" in l or "undocumented" in l
    ]
    print()
    if flagged:
        print("NEEDS ATTENTION:")
        for page, layer in flagged:
            print("   p%03d  %s" % (page, layer))
    else:
        print("Every degenerate page holds its canonical block and documents itself.")
    return 1 if flagged else 0


if __name__ == "__main__":
    raise SystemExit(main())
