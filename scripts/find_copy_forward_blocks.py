"""Detect target blocks filed under the WRONG page.

The V2 page validator checks STRUCTURE: labels present, Arabic matches the
canonical source, no forbidden markers. It does not check that a translation
corresponds to its own page - so a block that is a neighbour's text, copied
forward, passes every gate.

Page 61 is the proof. Its English block is 91.9% similar to page 60's, has
the wrong folio (54 where the source says 55), and contains none of page 61's
content: no 'mim', no 'Thursday', no 'bees', no 'the north', no 'seasons'.
verify_translation_v2_page.py returned PASS.

WHY THE NAIVE VERSION OF THIS CHECK FAILED

My first attempt scored each block by how many of its page's rare Arabic
terms appeared literally in the target. It flagged 1,125 pages starting at
page 7 - because A TRANSLATION CONTAINS NO ARABIC. It scored the English
copy of a perfectly good page 0.0%. A faithful translation of a page full of
rare Arabic terms will contain none of them as Arabic.

The workable signal needs no transliteration dictionary, because a misfile
identifies itself: the text it wrongly contains belongs to a NEIGHBOUR.
So compare pages against each other instead of against their own source.

  - exact duplicate bodies across pages -> certain misfile
  - blocks sharing >60% of their 12-word shingles with a different page
    -> a copy of that neighbour
  - a folio line present in the target that disagrees with the source's
    -> decisive when both carry one

A page that is merely under-translated is a different, milder defect; it
does not appear here, and is caught by the completeness checker instead.
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from recover_sibling_blocks import blocks_for, clean, parse_blocks  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
TOTAL = 604
FOLDERS = {"enriched_en": "English", "enriched_id": "Indonesia"}
AR_DIGITS = str.maketrans("\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669", "0123456789")


def folio_of(text: str) -> str | None:
    """Return the folio when the block's FIRST non-blank line is a folio line.

    Only the leading line counts. Scanning further down produces nonsense: a
    target that opens mid-prose has its real folio in the page's ARABIC block,
    and picking up some number from body text produced 40 phantom
    'folio-mismatch' findings across pages that are fine.
    """
    for line in text.splitlines():
        if not line.strip():
            continue
        if "-" in line or "\u2014" in line or "(" in line:
            m = re.search(r"[\u0660-\u0669]+|\d{1,3}", line)
            if m:
                return str(int(m.group().translate(AR_DIGITS)))
        return None
    return None


def load(folder: str, label: str) -> dict[int, str]:
    out: dict[int, str] = {}
    for page in range(1, TOTAL + 1):
        path = REPO_ROOT / "ocr" / folder / f"page_{page:03d}.txt"
        if not path.exists():
            continue
        text = clean(path.read_text(encoding="utf-8"))
        if [l for l, _, _ in parse_blocks(text)] != ["Arabic", label]:
            continue
        bodies = blocks_for(text, label)
        if bodies and len(bodies[0]) >= 60:
            out[page] = bodies[0]
    return out


def shingles(body: str, k: int = 12) -> set[str]:
    words = re.findall(r"[A-Za-z\u0100-\u024F']+", body.lower())
    return {" ".join(words[i : i + k]) for i in range(max(0, len(words) - k + 1))}


def main() -> int:
    src_folio: dict[int, str | None] = {}
    for page in range(1, TOTAL + 1):
        path = REPO_ROOT / "ocr" / "enriched" / f"page_{page:03d}.txt"
        src_folio[page] = (
            folio_of(clean(path.read_text(encoding="utf-8"))) if path.exists() else None
        )

    findings: list[tuple[str, int, int, str, str]] = []
    for folder, label in FOLDERS.items():
        blocks = load(folder, label)
        pages = sorted(blocks)

        by_body: dict[str, list[int]] = defaultdict(list)
        for page, body in blocks.items():
            by_body[re.sub(r"\s+", " ", body).strip()].append(page)
        for group in by_body.values():
            if len(group) > 1:
                for other in group[1:]:
                    findings.append((label, other, group[0], "exact-duplicate", f"identical to p{group[0]}"))

        sh = {p: shingles(b) for p, b in blocks.items()}
        for i, a in enumerate(pages):
            if not sh[a]:
                continue
            for b in pages[i + 1 :]:
                if not sh[b]:
                    continue
                inter = len(sh[a] & sh[b])
                if not inter:
                    continue
                best = max(inter / len(sh[a]), inter / len(sh[b]))
                if best > 0.60:
                    findings.append((label, a, b, "near-duplicate", f"{best:.0%} shared with p{b}"))
                    findings.append((label, b, a, "near-duplicate", f"{best:.0%} shared with p{a}"))

        for page, body in blocks.items():
            want, got = src_folio.get(page), folio_of(body)
            if want and got and want != got:
                findings.append((label, page, -1, "folio-mismatch", f"source {want} vs target {got}"))

    print(f"findings: {len(findings)}\n")
    for label, page, other, kind, detail in findings:
        who = f"p{page:03d}" + (f" <-> p{other:03d}" if other > 0 else "")
        print(f"  {label:10s} {who:20s} {kind:17s} {detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
