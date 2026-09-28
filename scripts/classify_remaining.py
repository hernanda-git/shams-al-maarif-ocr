"""Classify the pages the recovery scan still reports as needing translation.

Not all 20 need a human translator. They split into three deterministic cases:

  MARKER   the canonical Arabic is itself a no-text marker, so the target must
           be the exact V2 marker ([NO VISIBLE TEXT] / [TIDAK ADA TEKS
           TERLIHAT]). This is a mechanical fix, not translation.
  GRID     the Arabic is a magic-square / table page: the only honest target
           preserves the grid and says so. No prose translation exists.
  OCR-FAIL the Arabic is overwhelmingly [?]: untranslatable by anyone.
  TRANSLATE a real body of Arabic with no target text. Genuine work.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from recover_sibling_blocks import (  # noqa: E402
    clean,
    is_translation_like,
    is_fallback,
    parse_blocks,
    _is_symbol,
    blocks_for,
)

OCR = REPO_ROOT / "ocr"
EN_MARKER = "[NO VISIBLE TEXT]"
ID_MARKER = "[TIDAK ADA TEKS TERLIHAT]"

CANDIDATES = [
    ("en", 84), ("id", 84), ("en", 95), ("id", 95), ("en", 105), ("id", 105),
    ("id", 117), ("id", 134), ("id", 250), ("en", 331), ("en", 332), ("en", 402),
    ("id", 402), ("id", 550), ("id", 587), ("id", 600), ("id", 601), ("en", 603),
    ("id", 603), ("en", 604),
]

NO_TEXT_AR = re.compile(
    r"no (visible )?(arabic )?text|does not contain any|tidak ada teks|"
    r"tidak mengandung teks|لا يحتوي على أي",
    re.IGNORECASE,
)


def source_of(page: int) -> str:
    return clean((OCR / "enriched" / f"page_{page:03d}.txt").read_text(encoding="utf-8"))


def target_of(page: int, lang: str) -> str:
    folder = "enriched_en" if lang == "en" else "enriched_id"
    label = "English" if lang == "en" else "Indonesia"
    path = OCR / folder / f"page_{page:03d}.txt"
    if not path.exists():
        return ""
    for body in blocks_for(clean(path.read_text(encoding="utf-8")), label):
        return body
    return ""


def classify(page: int, lang: str) -> tuple[str, str]:
    src = source_of(page)
    tgt = target_of(page, lang)
    letters = [c for c in src if c.isalpha() and "؀" <= c <= "ۿ"]
    symbols = sum(1 for c in src if _is_symbol(c))
    bracket = src.count("[?]")

    if tgt.strip() in (EN_MARKER, ID_MARKER):
        return "DONE", "already carries the exact V2 marker"

    if NO_TEXT_AR.search(src) and len(src) < 200:
        return "MARKER", f"blank Arabic source -> write the exact marker"

    if bracket > 200:
        return "OCR-FAIL", f"{bracket} [?] chars = OCR destroyed this page"

    grid = "grid content preserved" in tgt.lower() or "[grid content" in tgt.lower()
    if symbols > len(letters) and len(letters) < 60:
        return "GRID", f"{symbols} symbols vs {len(letters)} letters = magic-square page"
    if grid:
        return "GRID", "target already preserves a grid"

    if tgt and is_fallback(tgt, lang):
        return "TRANSLATE", f"builder fallback present ({len(tgt)}c)"
    return "TRANSLATE", f"{len(src)}c Arabic, {len(letters)} letters, no usable target"


def main() -> int:
    buckets: dict[str, list] = {}
    for lang, page in CANDIDATES:
        kind, why = classify(page, lang)
        buckets.setdefault(kind, []).append((page, lang, why))

    for kind in ("DONE", "MARKER", "GRID", "OCR-FAIL", "TRANSLATE"):
        rows = buckets.get(kind, [])
        print(f"{kind:10s} {len(rows):2d}  " + ", ".join(f"p{p}/{l}" for p, l, _ in rows))
        for p, l, why in rows:
            print(f"             p{p}/{l}: {why}")
    print()
    print(f"genuine translation work remaining: {len(buckets.get('TRANSLATE', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
