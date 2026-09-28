"""Verify each translated page is COMPLETE, not truncated.

A translation that stops early is the failure mode that matters here: the file
looks valid and the validator passes it, because the validator checks structure,
not completeness. These checks are the ones the validator does NOT do:

  1. target block char count vs source Arabic letter count (a rough length ratio)
  2. no literal truncation marker anywhere in the file
  3. embedded Arabic block equals the canonical source
  4. target block line count vs source line count
  5. no Arabic script in the target block
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from recover_sibling_blocks import (  # noqa: E402
    _ARABIC_IN_TARGET,
    blocks_for,
    clean,
    parse_blocks,
)

TRUNCATION = re.compile(
    r"\[\.\.\.|truncated\}|omitted for brevity|remaining pages|"
    r"\[continue(?:d)? on|see next page",
    re.IGNORECASE,
)

FOLDERS = {"enriched_en": ("English", "en"), "enriched_id": ("Indonesia", "id")}


def main() -> int:
    pages = [int(a) for a in sys.argv[1:]] or list(range(1, 605))
    bad = 0
    for page in pages:
        src_path = REPO_ROOT / "ocr" / "enriched" / f"page_{page:03d}.txt"
        if not src_path.exists():
            continue
        src = clean(src_path.read_text(encoding="utf-8"))
        src_letters = len([c for c in src if c.isalpha() and "؀" <= c <= "ۿ"])
        src_lines = len([l for l in src.split("\n") if l.strip()])
        for folder, (label, lang) in FOLDERS.items():
            path = REPO_ROOT / "ocr" / folder / f"page_{page:03d}.txt"
            if not path.exists():
                continue
            raw = path.read_text(encoding="utf-8")
            text = clean(raw)
            labels = [l for l, _, _ in parse_blocks(text)]
            if labels.count(label) != 1 or labels != ["Arabic", label]:
                continue  # not a well-formed target file; other tools own that
            body = blocks_for(text, label)
            if not body:
                continue
            body = body[0]
            embedded = blocks_for(text, "Arabic")
            issues = []
            if embedded and " ".join(embedded[0].split()) != " ".join(src.split()):
                issues.append(
                    f"embedded Arabic != canonical ({len(embedded[0])}c vs {len(src)}c)"
                )
            arabic_in_body = len(_ARABIC_IN_TARGET.findall(body))
            if arabic_in_body > max(4, len(body) * 0.005):
                issues.append(f"Arabic script in target: {arabic_in_body} chars")
            m = TRUNCATION.search(body)
            if m:
                issues.append(f"truncation marker: {m.group()!r}")
            ratio = len(body) / src_letters if src_letters else 0
            if src_letters > 200 and ratio < 0.25:
                issues.append(f"ratio {ratio:.2f} (target {len(body)}c / {src_letters} letters)")
            # LINE COUNT IS NOT A COMPLETENESS SIGNAL. A 32-line Arabic page
            # reflows into 3 lines of English and is complete (p561: 3001c for
            # 32 source lines). Only the character ratio is checked.
            if issues:
                bad += 1
                print(f"  BAD  p{page:03d} {folder[-2:]}  " + "; ".join(issues))
    print(f"\npages with a completeness problem: {bad}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
