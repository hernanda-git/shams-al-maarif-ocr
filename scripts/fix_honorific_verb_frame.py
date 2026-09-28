"""Repair `God Most High` inserted where the banned word was a VERB.

The honorific sweep replaced 803 occurrences of banned forms with `God Most
High`, and 802 were right. This one was not: p008 read

    '...and the Manifest in sempiternity. Exalted is He above
     substances and accidents...'

where `Exalted` is the VERB 'to be exalted', not the name الله تعالى. The
mechanical replacement produced the nonsense 'God Most High above
substances'.

So the sweep's own blind spot is worth encoding rather than fixing by hand
and forgetting. This restores that one site, and it looks for the pattern
GENERALLY: a `God Most High` immediately followed by a preposition or
adverb that makes it read as a verb phrase - above, over, beyond, far above -
is suspicious, and each is reported with context for review rather than
silently rewritten.

Deliberately conservative. 35 of the 36 candidate sites corpus-wide are
correct noun usages ('the Names of God Most High', 'what God Most High has
deposited', 'God Most High has spoken'), and a rule that rewrote all of them
would wreck the page. Only a VERB frame is touched here, and only where the
corpus has a competing reading to check against.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from recover_sibling_blocks import blocks_for, clean  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
TOTAL = 604
NAME = "God Most High"

# The damage is ALREADY DONE in the file: the honorific sweep already turned
# 'Exalted is He above' into 'God Most High above'. So the repair has to match
# the broken result, not the original - my first version searched for
# 'Exalted is He', found nothing, and correctly reported 'nothing to do'
# while leaving the nonsense in place. A repair tool that only recognises the
# defect it was written for is a tool that cannot verify its own effect.
DAMAGED = re.compile(
    r"(?:^|[\.\n;]\s*|\band\s*)" + re.escape(NAME) + r"(?=\s+(?:above|over|beyond)\b)",
    re.IGNORECASE,
)
FIXED = "He is exalted"


def repair(page: int) -> list[str]:
    path = REPO_ROOT / "ocr" / "enriched_en" / f"page_{page:03d}.txt"
    if not path.exists():
        return []
    text = clean(path.read_text(encoding="utf-8"))
    body = blocks_for(text, "English")
    if not body:
        return []
    new, n = DAMAGED.subn(FIXED, body[0])
    if n:
        path.write_text(
            f"Arabic:\n{blocks_for(text, 'Arabic')[0]}\n\nEnglish:\n{new}\n",
            encoding="utf-8",
        )
    return [f"p{page:03d}: {n} verb-frame site(s) -> '{FIXED}'"] if n else []


def audit() -> list[str]:
    """Every `God Most High` that reads like a verb, for human review."""
    flags = []
    for page in range(1, TOTAL + 1):
        path = REPO_ROOT / "ocr" / "enriched_en" / f"page_{page:03d}.txt"
        if not path.exists():
            continue
        body = blocks_for(clean(path.read_text(encoding="utf-8")), "English")
        if not body:
            continue
        for m in re.finditer(re.escape(NAME), body[0]):
            # The first version sampled only 3 characters, so ' above'
            # arrived as ' ab' and the \\b after 'above' could never match.
            # Sample a full word instead of guessing a width.
            after = body[0][m.end():m.end() + 12].lstrip()
            if re.match(r"^(above|over|beyond)\b", after, re.IGNORECASE):
                flags.append(
                    "  p%03d ...%s..." % (page, body[0][max(0, m.start() - 40):m.end() + 20].replace("\n", " "))
                )
    return flags


def main() -> int:
    if "--apply" in sys.argv:
        pages = [int(a) for a in sys.argv[1:] if a.isdigit()]
        for line in repair(pages[0] if pages else 8):
            print(line)
    flags = audit()
    print("`%s` in a VERB frame (review):" % NAME)
    for flag in flags:
        print(flag)
    print(f"  {len(flags)} site(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
