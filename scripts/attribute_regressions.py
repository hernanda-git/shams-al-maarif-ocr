"""Is an Arabic-in-target finding on a page this branch rewrote a REGRESSION?

A page I rewrote is only a regression if the target block was CLEAN on
origin/main and my change made it dirty. Most were already dirty: the corpus
carries a standing backlog the V2 worker sweeps page by page, and my mechanical
repairs (promote / strip / recover) rewrote the LAYER around the target block
without changing the target text.

So compare the Arabic-letter count of the target block before vs after, per page.
Only a count that went UP is a regression.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from recover_sibling_blocks import _ARABIC_IN_TARGET, clean, parse_blocks  # noqa: E402

LABEL = {"enriched_en": "English", "enriched_id": "Indonesia"}


def blob(ref: str, path: str) -> str:
    r = subprocess.run(["git", "-C", str(REPO_ROOT), "show", f"{ref}:{path}"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return r.stdout if r.returncode == 0 else ""


def ar_count(text: str, label: str) -> int:
    blocks = [b for l, b, _ in parse_blocks(clean(text)) if l == label]
    if not blocks:
        return -1
    return len(_ARABIC_IN_TARGET.findall(blocks[0]))


def main() -> int:
    names = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "diff", "--name-only", "origin/main", "HEAD", "--", "ocr/"],
        capture_output=True, text=True).stdout.split()
    worse, better, unchanged, now_clean = [], [], 0, 0
    for n in names:
        m = re.search(r"(enriched_en|enriched_id)/page_(\d+)\.txt", n)
        if not m:
            continue
        folder, page = m.group(1), int(m.group(2))
        label = LABEL[folder]
        before = ar_count(blob("origin/main", n), label)
        after = ar_count(blob("HEAD", n), label)
        if after <= 0:
            now_clean += 1
            continue
        if after > before:
            worse.append((folder, page, before, after))
        elif after < before:
            better.append((folder, page, before, after))
        else:
            unchanged += 1

    print(f"target files this branch rewrote: {len(names)}")
    print(f"  got CLEANER          : {len(better)}")
    print(f"  unchanged (still dirty, pre-existing) : {unchanged}")
    print(f"  now CLEAN            : {now_clean}")
    print(f"  REGRESSIONS (worse)  : {len(worse)}")
    for folder, page, b, a in worse:
        print(f"     {folder} p{page:03d}  arabic {b} -> {a}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
