"""Compare digit runs between a source and a target block, across BOTH ranges.

This exists because of a mistake worth not repeating. Page 400's Arabic
source contains a 7,517-character run of digits: U+0661 (Arabic-Indic one)
repeated 7,514 times after a short ٩٩٢ prefix. I checked the target for a
run of `[0-9]` - ASCII digits only - found none, and concluded the target
had FABRICATED a huge digit run that the source did not contain. The
source has it. A faithful rendering of this page is supposed to contain a
comparable run.

So any check that asks "does the source have a long digit run?" or "did the
target invent one?" must span BOTH ASCII 0-9 and Arabic-Indic ٠-٩, plus the
Extended Arabic-Indic forms. A check that searches one range will either
invent a defect or hide a real one.

Usage:
  uv run --no-project python scripts/digit_run_audit.py 400
  uv run --no-project python scripts/digit_run_audit.py          # whole corpus
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from recover_sibling_blocks import blocks_for, clean, parse_blocks  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]

# Every digit a scan of this manuscript can produce. Missing any of these
# ranges is how the page-400 false positive happened.
DIGIT = r"[0-9\u0660-\u0669\u06F0-\u06F9]"
FOLDERS = {"enriched_en": "English", "enriched_id": "Indonesia"}


def runs(text: str) -> list[str]:
    import re

    return [m.group() for m in re.finditer(f"{DIGIT}+", text)]


def report(page: int) -> int:
    source = clean(
        (REPO_ROOT / "ocr" / "enriched" / f"page_{page:03d}.txt").read_text(encoding="utf-8")
    )
    src_runs = runs(source)
    src_longest = max((len(r) for r in src_runs), default=0)
    print(f"p{page:03d} SOURCE: {len(source)} chars, {len(src_runs)} digit runs, longest {src_longest}")

    for folder, label in FOLDERS.items():
        path = REPO_ROOT / "ocr" / folder / f"page_{page:03d}.txt"
        if not path.exists():
            continue
        text = clean(path.read_text(encoding="utf-8"))
        if [l for l, _, _ in parse_blocks(text)] != ["Arabic", label]:
            continue
        body = blocks_for(text, label)
        if not body:
            continue
        tgt_runs = runs(body[0])
        tgt_longest = max((len(r) for r in tgt_runs), default=0)
        verdict = (
            "mirrors source"
            if tgt_longest >= src_longest // 2
            else ("declared unclear" if "[UNCLEAR" in body[0] else "SUSPECT: unexplained shrink")
        )
        print(
            f"  {label:10s} {len(body[0]):6d}c  runs={len(tgt_runs):3d} longest={tgt_longest:5d}  {verdict}"
        )
    return 0


def main(argv: list[str]) -> int:
    if argv:
        return report(int(argv[0]))
    print("pages whose SOURCE has a digit run over 20 characters:")
    for page in range(1, 605):
        path = REPO_ROOT / "ocr" / "enriched" / f"page_{page:03d}.txt"
        if not path.exists():
            continue
        longest = max((len(r) for r in runs(clean(path.read_text(encoding="utf-8")))), default=0)
        if longest > 20:
            print(f"  p{page:03d}  longest {longest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
