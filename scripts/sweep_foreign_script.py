"""Sweep a target block for foreign-script contamination the validators miss.

Every existing gate on this corpus checks the ARABIC range (U+0600-U+06FF).
That is a real gap, and it was found by accident: while patching page 62 a
malformed `\\uXXXX` escape in a hand-built patch string wrote a mixture of
Arabic, Cyrillic and Arabic-script letters into the middle of an
Indonesian sentence. The page passed `page_triage.py` and
`verify_worker_output.py`, because neither looks outside the Arabic block.

The same mechanism produces CJK, Greek, Hebrew, a stray U+FFFD replacement
character from a bad decode, or a control character from a truncated
escape - all of them invisible to an Arabic-only check and all of them
shippable.

WHAT IS ALLOWED, so this does not fire on legitimate content:
  ASCII, Latin-1/Latin Extended letters and the combining marks that give
  scholarly diacritics (ā ī ū Ḥ ḥ Ṣ ṣ Ṭ ṭ), Arabic, Hebrew (the target
  languages use it for the Q 7:55 quotation), and the punctuation the
  style guide requires (quote marks, dashes, the Arabic comma and
  question mark).

Usage:
  uv run --no-project python scripts/sweep_foreign_script.py 62
  uv run --no-project python scripts/sweep_foreign_script.py 61 62 63
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

# Scripts that are never legitimate in any target block, with a label.
FORBIDDEN = [
    ("Cyrillic", 0x0400, 0x04FF),
    ("Greek", 0x0370, 0x03FF),
    ("CJK", 0x4E00, 0x9FFF),
    ("Devanagari", 0x0900, 0x097F),
    ("Thai", 0x0E00, 0x0E7F),
    ("Armenian", 0x0530, 0x058F),
    ("Georgian", 0x10A0, 0x10FF),
    ("Katakana", 0x30A0, 0x30FF),
    ("Hangul", 0xAC00, 0xD7AF),
]


def offenders(body: str) -> list[tuple[str, str, int]]:
    """Every character that has no business being in a target block."""
    found: list[tuple[str, str, int]] = []
    for index, ch in enumerate(body):
        code = ord(ch)
        for name, lo, hi in FORBIDDEN:
            if lo <= code <= hi:
                found.append((name, ch, index))
                break
        else:
            if code == 0xFFFD:
                found.append(("U+FFFD replacement", ch, index))
            elif unicodedata.category(ch) == "Cc" and ch not in "\n\r\t":
                found.append((f"control U+{code:04X}", ch, index))
    return found


def main() -> int:
    pages = [int(a) for a in sys.argv[1:]] or [62]
    problems = 0
    for page in pages:
        for folder, label in FOLDERS.items():
            path = REPO_ROOT / "ocr" / folder / f"page_{page:03d}.txt"
            if not path.exists():
                continue
            short = "en" if "enriched_en" in folder else "id"
            text = clean(path.read_text(encoding="utf-8"))
            bodies = blocks_for(text, label)
            if not bodies:
                print(f"p{page:03d} {short}  MALFORMED - no {label} block")
                problems += 1
                continue
            body = bodies[0]
            bad = offenders(body)
            if bad:
                problems += 1
                counts: dict[str, int] = {}
                for name, _ch, _i in bad:
                    counts[name] = counts.get(name, 0) + 1
                print(f"p{page:03d} {short}  {len(bad)} CONTAMINATED: {counts}")
                for name, ch, i in bad[:5]:
                    lo = max(0, i - 24)
                    print(f"        {name} at {i}: ...{body[lo:i + 24]!r}")
            else:
                print(f"p{page:03d} {short}  clean ({len(body)}c)")
    print(f"\n{problems} problem block(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
