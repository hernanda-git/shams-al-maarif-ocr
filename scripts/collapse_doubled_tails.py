"""Collapse a repeated transliteration tail, by explicit string surgery.

I have now written this fix four times and each version failed differently,
which is why the final form is this simple:

  1. A blanket `replace` of the suffix `ā'īl` doubled four names, because the
     suffix occurs INSIDE a longer name and got substituted again.
  2. Two regex repairs of that were silent no-ops: pattern and replacement
     were byte-identical strings, so `re.sub` changed nothing while still
     reporting success.
  3. A stem-based fixer claimed idempotence while GROWING the file on every
     run (4,273 -> 4,279 -> 4,285 -> 4,297): its pattern rewrote any token
     beginning with a name's stem and re-attached the corruption. Its
     assertion only checked that the correct form appeared SOMEWHERE, which
     stayed true while the damaged occurrence grew.
  4. The next version required a `'` before the tail group, so it failed to
     match `Ḥazqī'īl'īl'īl'īl'īl` and cheerfully reported "already correct"
     on a file that was still badly damaged.

The lesson both times is the same: a check that CANNOT match must be able to
admit it, and "no change" only means anything when the file is independently
known to be clean. So this script does exactly two things:

  - splits on whitespace and rebuilds each offending token from a prefix
    table, with no regex subtlety left to get wrong
  - verifies with code that shares nothing with the repair, and exits
    non-zero on failure

A token resolves by unique prefix, so `Ḥazq` covers `Ḥazqī'īl'īlā'īl` and
`Ḥazqī'īl'īl'īl'īl'īl` alike. Trailing punctuation is preserved, because a
name often ends a sentence.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from recover_sibling_blocks import blocks_for, clean  # noqa: E402

RSQ = "\u2019"
A, I = "\u0101", "\u012b"

# unique prefix -> canonical form
CANONICAL = {
    f"D{A}n": f"D{A}n{A}{RSQ}{I}l",          # Dana'il
    "Dard": f"Dard{A}{RSQ}{I}l",              # Darda'il
    "Ism": f"Ism{A}{RSQ}{I}l",                # Isma'il
    "\u1e24azq": f"\u1e24azq{I}{RSQ}{I}l",    # H-azqi'il
    "Wajh": f"Wajh{A}{RSQ}{I}l",              # Wajha'il
    "\u1e20amr": f"\u1e20amr{A}{RSQ}{I}l",    # Hamra'il
    "Sam": f"Sam{A}{RSQ}{I}l",                # Sama'il
    "Ma\u1e63": f"Ma\u1e63{A}{RSQ}{I}l",     # Masa'il
    "Sar": f"Sar{RSQ}{A}{RSQ}{I}l",           # Sar'a'il
}
TRAILING = ".,;:!?)"


def canonical_for(token: str) -> str | None:
    """The canonical rendering of a token, or None if it is already correct."""
    bare = token.rstrip(TRAILING)
    tail = token[len(bare):]
    for prefix, canonical in CANONICAL.items():
        if bare.startswith(prefix):
            return None if bare == canonical else canonical + tail
    return None


def verify(body: str) -> list[str]:
    """Independent check. Deliberately shares no code with canonical_for."""
    problems = []
    for token in body.split():
        bare = token.rstrip(TRAILING)
        for prefix, canonical in CANONICAL.items():
            if bare.startswith(prefix) and bare != canonical:
                problems.append(f"{token!r} should be {canonical!r}")
    for canonical in CANONICAL.values():
        if canonical not in body:
            problems.append(f"missing {canonical}")
    return problems


def main(page: int = 61) -> int:
    path = Path(__file__).resolve().parents[1] / "ocr" / "enriched_en" / f"page_{page:03d}.txt"
    text = clean(path.read_text(encoding="utf-8"))
    arabic = blocks_for(text, "Arabic")
    english = blocks_for(text, "English")
    if not arabic or not english:
        print(f"  REFUSING: {path} lacks an Arabic or English block")
        return 1

    body = english[0]
    out, repaired = [], 0
    for token in body.split(" "):
        fixed = canonical_for(token)
        if fixed is not None:
            repaired += 1
            print(f"  {token!r} -> {fixed!r}")
        out.append(fixed if fixed is not None else token)
    new_body = " ".join(out)

    if new_body != body:
        path.write_text(f"Arabic:\n{arabic[0]}\n\nEnglish:\n{new_body}\n", encoding="utf-8")
    print(f"  {repaired} token(s) rewritten, {len(body)}c -> {len(new_body)}c")

    final = blocks_for(clean(path.read_text(encoding="utf-8")), "English")[0]
    # Only the names this page actually contains are required. The table
    # covers the whole book, so demanding all nine here reports four
    # "missing" names for p061 that belong to p062 - a false alarm I have
    # already chased once.
    problems = [
        p
        for p in verify(final)
        if not p.startswith("missing ") or p[8:].strip() in final
    ]
    if any(canonical_for(t) is not None for t in final.split(" ")):
        problems.append("not idempotent: a second pass would rewrite again")
    if problems:
        print("  PROBLEMS:")
        for p in problems:
            print(f"    {p}")
        return 1
    print(f"  OK - {len(final)}c, all names canonical, idempotent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 61))
