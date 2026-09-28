#!/usr/bin/env python3
"""Restore a page where this branch's promotion overwrote a CLEANER upstream copy.

Commit 2ee94a9 promoted the "better" of two English/Indonesian copies across 424
pages using: prefer the copy with no Arabic script, else prefer the longer copy.
That rule is wrong in a specific way this tool repairs.

The corpus contains pages the V2 worker had already aligned on origin/main: the
target block is clean (0 Arabic script) and carries the project's
``[UNCLEAR: ...]`` markers. The sibling file's copy of the same page is often
LONGER and still raw Arabic -- because it was never revised. So on those pages
the length rule preferred the dirty copy and replaced the worker's clean one.

Page 58 is the proof:

    origin/main enriched_en : 5975c, 0 Arabic  (worker-aligned, has [UNCLEAR:])
    this branch            : 5100c, 42 Arabic (stale sibling copy)

So: for every target file this branch rewrote, compare the target block against
the same block on origin/main. If upstream was CLEANER (fewer Arabic letters),
restore the upstream block and keep this branch's Arabic block, which is
byte-identical to the canonical source anyway.

Usage:
  uv run --no-project python scripts/restore_upstream_clean_blocks.py --scan
  uv run --no-project python scripts/restore_upstream_clean_blocks.py --apply
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from recover_sibling_blocks import (  # noqa: E402
    _ARABIC_IN_TARGET,
    blocks_for,
    clean,
    parse_blocks,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
LABEL = {"enriched_en": "English", "enriched_id": "Indonesia"}
MIN_MARGIN = 3  # ignore a 1-2 char wobble; only a real regression counts


def upstream(ref: str, path: str) -> str:
    r = subprocess.run(["git", "-C", str(REPO_ROOT), "show", f"{ref}:{path}"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return r.stdout if r.returncode == 0 else ""


def arabic_in(text: str, label: str) -> int:
    bodies = blocks_for(clean(text), label)
    if not bodies:
        return -1
    return len(_ARABIC_IN_TARGET.findall(bodies[0]))


def scan() -> list[dict]:
    names = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "diff", "--name-only", "origin/main", "HEAD", "--", "ocr/"],
        capture_output=True, text=True).stdout.split()
    found = []
    for n in names:
        m = re.search(r"(enriched_en|enriched_id)/page_(\d+)\.txt", n)
        if not m:
            continue
        folder, page = m.group(1), int(m.group(2))
        label = LABEL[folder]
        path = REPO_ROOT / n
        if not path.exists():
            continue
        before = arabic_in(upstream("origin/main", n), label)
        after = arabic_in(path.read_text(encoding="utf-8"), label)
        if before >= 0 and after > 0 and before < after - MIN_MARGIN:
            found.append(
                {
                    "folder": folder,
                    "page": page,
                    "label": label,
                    "path": path,
                    "rel": n,
                    "before": before,
                    "after": after,
                    "keep": blocks_for(path.read_text(encoding="utf-8"), label),
                }
            )
    return found


def apply(finding: dict) -> str:
    """Keep this branch's canonical Arabic block, restore the upstream target."""
    src_path = REPO_ROOT / "ocr" / "enriched" / f"page_{finding['page']:03d}.txt"
    canonical = clean(src_path.read_text(encoding="utf-8"))
    body = upstream("origin/main", finding["rel"])
    kept = blocks_for(clean(body), finding["label"])
    text = kept[0] if kept else ""
    finding["path"].write_text(
        f"Arabic:\n{canonical}\n\n{finding['label']}:\n{text}\n", encoding="utf-8"
    )
    return f"restored {len(text)}c of {finding['label']} ({finding['before']} -> 0 arabic)"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    found = scan()
    for f in found:
        print(
            f"  {f['folder']:12s} p{f['page']:03d} {f['label']:10s} "
            f"arabic {f['before']} -> {f['after']}  (upstream was cleaner)"
        )
    print(f"\npages where this branch made a target block WORSE: {len(found)}")

    if args.apply:
        print("\napplying:")
        for f in found:
            print(f"  {f['folder']} p{f['page']:03d}: {apply(f)}")
    elif found:
        print("\n(dry run - pass --apply to write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
