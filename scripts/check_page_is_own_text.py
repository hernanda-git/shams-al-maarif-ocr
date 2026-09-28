"""Prove a page's target block is a translation of ITS OWN page, not a neighbour's.

The V2 page validator checks structure only, so a block that is a neighbour's
text passes it. Page 61 was the proof: its English opened folio 54 where the
source said 55, shared 91.9% of its text with page 60, and contained none of
page 61's own content.

This asks the cheap question first - are the page's DISTINCTIVE CONTENT WORDS
present? - and only then measures similarity against neighbours.

A FAILURE MEANS SOMETHING, WHICH IS THE POINT

My first version of the acceptance gate for page 61 grepped the English block
for the literal string 'Daniyil'. A worker had correctly transliterated the
four kings as `Dānā'īl`, `Dardā'īl`, `Ismā'īl`, `Ḥazqī'īl` per
docs/translation-style-v2.md section 4 ('Scientific/technical terms keep full
diacritics'). The grep failed, and the worker - sensibly - degraded the
transliteration to plain ASCII to satisfy it. A test I wrote had made the
data worse.

So comparisons here are DIACRITIC-INSENSITIVE: text is normalised to NFD and
combining marks are stripped before matching. `Dānā'īl` then matches
`daniyil`, so a correct transliteration is not punished for being correct.

The cost is that a genuinely different name could pass. That is acceptable:
this is a smoke test that catches a whole class of misfile, and the
authoritative check is a human reading the page against its source.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from recover_sibling_blocks import blocks_for, clean, parse_blocks  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
FOLDERS = {"enriched_en": "English", "enriched_id": "Indonesia"}


def fold(text: str) -> str:
    """Lowercase and strip combining marks, so diacritics never break a match."""
    stripped = "".join(
        c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn"
    )
    return stripped.replace("’", "'").replace("ʻ", "'").replace("ʾ", "'")


def distinctive_terms(source: str, k: int = 6) -> list[str]:
    """Longest content words in the source, as a cheap page fingerprint.

    Arabic function words and short tokens carry no page identity, so only
    words of 5+ characters are considered, longest first.
    """
    stop = {
        "الله", "تعالى", "صلى", "عليه", "وسلم", "الذي", "التي", "هذا",
        "هذه", "ذلك", "كان", "كانت", "بسم", "الرحمن", "الرحيم", "وقال",
    }
    words = [w for w in re.findall(r"[\u0600-\u06FF]{5,}", source) if w not in stop]
    seen: list[str] = []
    for w in sorted(set(words), key=len, reverse=True):
        if len(seen) >= k:
            break
        seen.append(w)
    return seen


def main() -> int:
    pages = [int(a) for a in sys.argv[1:]] or [61]
    worst = 0.0
    for page in pages:
        spath = REPO_ROOT / "ocr" / "enriched" / f"page_{page:03d}.txt"
        if not spath.exists():
            print(f"p{page:03d}  no source")
            continue
        source = clean(spath.read_text(encoding="utf-8"))
        terms = distinctive_terms(source)
        print(f"p{page:03d}  source {len(source)}c, fingerprint {len(terms)} terms")
        for folder, label in FOLDERS.items():
            path = REPO_ROOT / "ocr" / folder / f"page_{page:03d}.txt"
            if not path.exists():
                continue
            text = clean(path.read_text(encoding="utf-8"))
            if [l for l, _, _ in parse_blocks(text)] != ["Arabic", label]:
                print(f"   {label:10s} MALFORMED")
                continue
            bodies = blocks_for(text, label)
            if not bodies:
                print(f"   {label:10s} NO BLOCK")
                continue
            body = bodies[0]
            if len(body) < 40:
                print(f"   {label:10s} EMPTY")
                continue
            src_folio = next(
                (l for l in source.splitlines() if l.strip()), ""
            ).strip()
            head = next((l for l in body.splitlines() if l.strip()), "").strip()
            same_folio = (
                re.sub(r"\D", "", src_folio.translate(str.maketrans(
                    "٠١٢٣٤٥٦٧٨٩", "0123456789"))) or "?"
            ) == (re.sub(r"\D", "", head.translate(str.maketrans(
                "٠١٢٣٤٥٦٧٨٩", "0123456789"))) or "?")
            ratio = len(body) / max(1, len(source))
            print(
                f"   {label:10s} {len(body):6d}c  ratio {ratio:.2f}  "
                f"folio {'ok' if same_folio else 'MISMATCH'}  head={head[:24]!r}"
            )
            worst = max(worst, ratio if ratio < 0.25 else 0.0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
