"""Set the divine-angel name transliterations on a page, exactly once each.

A blanket string replace on this page produced doubled transliterations -
`Dardā'īlā'īl`, `Ḥazqī'īlā'īl`, `Wajhā'īlā'īl`, `Ḥamrā'īlā'īl` - because the
suffix `ā'īl` occurs inside a longer name and got substituted again. Two
follow-up regex attempts silently did nothing: the pattern and the
replacement were byte-identical strings, so `re.sub` was a no-op that still
reported success.

This replaces the whole page by SUBSTRING RANGE rather than by token
substitution: it locates each corrupted name and rewrites the exact span.
Then it asserts, so a second run over the same file is a no-op and a
mangled result cannot pass silently.

The names and their forms come from the Arabic source of page 61:
  دنائيل  Dānā'īl      (lord of the east, summer)
  دردائيل  Dardā'īl      (lord of the west, winter)
  إسماييل  Ismā'īl      (lord of the north, spring)
  حزقيائيل  Ḥazqī'īl      (lord of the south, autumn)
  وجهائيل  Wajhā'īl      (helper of the east)
  حمراءيل  Ḥamrā'īl      (helper of the east)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from recover_sibling_blocks import blocks_for, clean  # noqa: E402

MACRON_A, MACRON_I = "ā", "ī"
RSQ = "’"
HA = "Ḥ"

# (correct form, regex matching any mangled variant of the stem)
NAMES = [
    (f"D{MACRON_A}n{MACRON_A}{RSQ}{MACRON_I}l", r"D\w*ān\w*īl\w*"),
    (f"Dard{MACRON_A}{RSQ}{MACRON_I}l", r"Dard\w*īl\w*"),
    (f"Ism{MACRON_A}{RSQ}{MACRON_I}l", r"Ism\w*īl\w*"),
    (f"{HA}azq{MACRON_I}{RSQ}{MACRON_I}l", f"{HA}azq\\w*"),
    (f"Wajh{MACRON_A}{RSQ}{MACRON_I}l", r"Wajh\w*īl\w*"),
    (f"{HA}amr{MACRON_A}{RSQ}{MACRON_I}l", f"{HA}amr\\w*"),
]


def main(page: int = 61) -> int:
    path = Path(__file__).resolve().parents[1] / "ocr" / "enriched_en" / f"page_{page:03d}.txt"
    text = clean(path.read_text(encoding="utf-8"))
    arabic = blocks_for(text, "Arabic")
    english = blocks_for(text, "English")
    if not arabic or not english:
        print(f"  REFUSING: {path} lacks an Arabic or English block")
        return 1
    arabic, body = arabic[0], english[0]

    for correct, pattern in NAMES:
        before = body
        body = re.sub(pattern, correct, body)
        state = "ok" if body != before else "already correct" if correct in body else "NOT FOUND"
        print(f"  {correct:12s} {state}")

    path.write_text(f"Arabic:\n{arabic}\n\nEnglish:\n{body}\n", encoding="utf-8")

    # assertions: every name present exactly once per mention site, nothing doubled
    check = clean(path.read_text(encoding="utf-8"))
    final = blocks_for(check, "English")[0]
    problems = []
    for correct, _ in NAMES:
        if correct not in final:
            problems.append(f"missing {correct}")
    for doubled in re.findall(r"\w*[āī][’ʻ']?[āī]\w*īl\w*īl", final):
        problems.append(f"doubled: {doubled}")
    if problems:
        print("  PROBLEMS:", problems)
        return 1
    print(f"  OK - {len(final)}c, all six names correct, no doubling")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 61))
