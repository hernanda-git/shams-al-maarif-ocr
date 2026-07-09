#!/usr/bin/env python3
"""
Update CHecKLIST.md checkbox state for given page numbers.

Usage:
    uv run python scripts/update_checklist.py 17 18 19 20

Idempotent: marks the listed pages as [x] and rewrites the progress line.
Only touches the checkbox markers; never edits page text.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKLIST = ROOT / "CHECKLIST.md"

def main():
    pages = set()
    for arg in sys.argv[1:]:
        if "-" in arg:
            a, b = arg.split("-", 1)
            for n in range(int(a), int(b) + 1):
                pages.add(n)
        else:
            pages.add(int(arg))
    if not pages:
        print("no pages given")
        return
    text = CHECKKLIST.read_text(encoding="utf-8")
    lines = text.split("\n")

    # progress line
    total = 0
    done = 0
    for i, ln in enumerate(lines):
        m = re.match(r"- \[([ xX])\] page_(\d{3})$", ln)
        if m:
            total += 1
            if m.group(1).lower() == "x":
                done += 1

    # mark requested pages done
    pat = re.compile(r"- \[([ xX])\] page_(\d{3})$")
    for i, ln in enumerate(lines):
        m = pat.match(ln)
        if m and int(m.group(2)) in pages:
            lines[i] = f"- [x] page_{m.group(2)}"
            done += 1

    # rewrite progress line
    for i, ln in enumerate(lines):
        if ln.startswith("Progress:"):
            lines[i] = (
                f"Progress: {done}/{total} pages translated "
                "(Hermes-authored, verbatim aligned to Arabic + English)"
            )
            break

    CHECKKLIST.write_text("\n".join(lines), encoding="utf-8")
    print(f"updated: marked {len(pages)} page(s) done -> progress {done}/{total}")

if __name__ == "__main__":
    main()
