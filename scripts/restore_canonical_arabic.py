"""Restore the embedded Arabic block to the canonical source, exactly.

52 of 604 target files carry an Arabic block that is not byte-equal to
ocr/enriched/page_NNN.txt. The tracker's own commit gate requires them to
match, and the builder trusts the embedded block, so a drifted one is a
latent correctness bug: the page's own canonical text is what readers and
validators should see.

Three classes, all measured rather than assumed:

  +/- 1 character  ~45 files. A trailing space, a stray newline, or one
                   flipped harakah (p127 differs at exactly one position:
                   fatha where the source has kasra). Mechanical to fix.
  SMALL vs LARGE  3 files. p095 embedded 1,661c against a 16,439c source;
                   p250 embedded 1,827c against 16,390c. These are the
                   wrong PAGE's text, or a collapsed block. Not mechanical
                   - reported, never auto-repaired.

THE TOOL IS DELIBERATELY REFUSING ON THE BIG CASES. Overwriting a 16,439c
canonical block with a 1,661c guess would be a silent data-loss event, and
the fact that a mismatch exists says nothing about which side is wrong.

Only the +/- 1 class is repaired, and only after checking the two blocks
differ ONLY by that margin - a large delta is escalated, not applied.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from recover_sibling_blocks import blocks_for, clean  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
TOTAL = 604
FOLDERS = {"enriched_en": "English", "enriched_id": "Indonesia"}
TOLERANCE = 1  # the +/- 1 class


def restore(page: int, folder: str, label: str, apply: bool) -> str:
    """Return a one-line verdict. Applies only within TOLERANCE."""
    src_path = REPO_ROOT / "ocr" / "enriched" / f"page_{page:03d}.txt"
    tgt_path = REPO_ROOT / "ocr" / folder / f"page_{page:03d}.txt"
    if not src_path.exists() or not tgt_path.exists():
        return "missing file"

    source = clean(src_path.read_text(encoding="utf-8"))
    text = clean(tgt_path.read_text(encoding="utf-8"))
    embedded = blocks_for(text, "Arabic")
    if not embedded:
        return "no Arabic block"
    if embedded[0] == source:
        return "ok"

    short = "en" if folder.endswith("_en") else "id"
    delta = len(embedded[0]) - len(source)
    if abs(delta) > TOLERANCE:
        return (
            f"ESCALATE {short}: embedded {len(embedded[0])}c vs canonical "
            f"{len(source)}c (delta {delta:+d}) - wrong page or collapsed "
            f"block, NOT auto-repaired"
        )

    # within tolerance: replace only the Arabic block, leave the translation
    if apply:
        body = blocks_for(text, label)
        if not body:
            return "no target block"
        tgt_path.write_text(
            f"Arabic:\n{source}\n\n{label}:\n{body[0]}\n", encoding="utf-8"
        )
    return f"fixed {short}: embedded {len(embedded[0])}c -> canonical {len(source)}c"


def scan() -> tuple[list[str], list[str]]:
    fixable, escalate = [], []
    for page in range(1, TOTAL + 1):
        for folder, label in FOLDERS.items():
            verdict = restore(page, folder, label, apply=False)
            if verdict.startswith("fixed"):
                fixable.append(f"p{page:03d} {verdict}")
            elif verdict.startswith("ESCALATE"):
                escalate.append(f"p{page:03d} {verdict}")
    return fixable, escalate


def scan_filler() -> list[str]:
    """Pages whose source is a scan FILL run rather than prose.

    Degenerate pages are not a defect class - they are a documented
    condition, and six of them already explain themselves in the target
    block. But one of them failed in a way this tool could not see: p095's
    source is 1,630 repetitions of U+10348 GOTHIC LETTER HWAIR, a scan
    fill-placeholder rather than a character. The two target files carried
    794 and 8,183 copies of it respectively - the SAME page, filler counted
    three different ways, all byte-compatible on the prose prefix, so
    nothing flagged them.

    What gives them away is a COUNT mismatch rather than a content
    mismatch, so it is checked separately here.
    """
    glyph = "\U00010348"
    canonical: dict[int, int] = {}
    for page in range(1, TOTAL + 1):
        src = REPO_ROOT / "ocr" / "enriched" / f"page_{page:03d}.txt"
        if src.exists():
            count = clean(src.read_text(encoding="utf-8")).count(glyph)
            if count:
                canonical[page] = count

    flags = []
    for page, want in sorted(canonical.items()):
        for folder, label in FOLDERS.items():
            path = REPO_ROOT / "ocr" / folder / f"page_{page:03d}.txt"
            if not path.exists():
                continue
            text = clean(path.read_text(encoding="utf-8"))
            # The count belongs on the EMBEDDED ARABIC BLOCK, not on the
            # translation. My first version checked the target body, where
            # 0 is the CORRECT answer - a translation must not reproduce
            # 1,630 filler glyphs, it should say `[UNCLEAR: ...]` about them
            # as p095 now does. Checking the translation would have flagged
            # a correct page as broken, which is the mirror image of the bug
            # that started this.
            arabic = blocks_for(text, "Arabic")
            if not arabic:
                continue
            got = arabic[0].count(glyph)
            if got != want:
                flags.append(
                    f"p{page:03d} {folder[-2:]}: Arabic block has {got} "
                    f"U+10348 fillers, canonical has {want}"
                )
    return flags



def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pages", nargs="*", type=int)
    ap.add_argument("--apply", action="store_true", help="write the repairs")
    args = ap.parse_args()

    if args.pages:
        for page in args.pages:
            for folder, label in FOLDERS.items():
                print(f"p{page:03d} {restore(page, folder, label, args.apply)}")
        return 0

    fixable, escalate = scan()
    print("=== within tolerance (mechanically repairable) ===")
    for line in fixable:
        print("  " + line)
    print(f"  {len(fixable)} file(s)")
    print()
    print("=== ESCALATE (not auto-repaired) ===")
    for line in escalate:
        print("  " + line)
    print(f"  {len(escalate)} file(s)")

    filler = scan_filler()
    print()
    print("=== SCAN-FILL COUNT MISMATCH ===")
    for line in filler:
        print("  " + line)
    print(f"  {len(filler)} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
