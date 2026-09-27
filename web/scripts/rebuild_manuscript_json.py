#!/usr/bin/env python3
"""Rebuild web/public/manuscript.json while preserving per-page titles.

`web/scripts/build_manuscript_json.py` rebuilds the reader payload from the three
translation layers.  It emits only `page`, `text`, and `scanSrc`, so running it
directly DROPS the 600 LLM-generated page titles that the reader sidebar and
search index depend on.  Titles are therefore restored here, deterministically,
as part of every rebuild.

Title resolution order (first hit wins):
  1. the current manuscript.json on disk (normal in-progress rebuild);
  2. the newest committed manuscript.json reachable from git (recovery when the
     working copy was clobbered or titles were never generated);
  3. no title (the reader tolerates a missing title; it is reported, not fatal).

Usage:
  uv run --no-project python web/scripts/rebuild_manuscript_json.py
  uv run --no-project python web/scripts/rebuild_manuscript_json.py --check
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
JSON_PATH = REPO_ROOT / "web" / "public" / "manuscript.json"
BUILDER = REPO_ROOT / "web" / "scripts" / "build_manuscript_json.py"


def titles_from_disk() -> dict[int, dict]:
    if not JSON_PATH.exists():
        return {}
    try:
        records = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {
        item["page"]: item["title"]
        for item in records
        if isinstance(item, dict)
        and isinstance(item.get("page"), int)
        and isinstance(item.get("title"), dict)
        and item["title"]
    }


def titles_from_git() -> dict[int, dict]:
    try:
        log = subprocess.run(
            ["git", "log", "-n", "60", "--format=%H", "--", "web/public/manuscript.json"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    for sha in log.stdout.split():
        try:
            blob = subprocess.run(
                ["git", "show", f"{sha}:web/public/manuscript.json"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
            records = json.loads(blob.stdout)
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
            continue
        found = {
            item["page"]: item["title"]
            for item in records
            if isinstance(item, dict)
            and isinstance(item.get("page"), int)
            and isinstance(item.get("title"), dict)
            and item["title"]
        }
        if found:
            return found
    return {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report the state of the generated JSON without rebuilding it",
    )
    args = parser.parse_args()

    if args.check:
        if not JSON_PATH.exists():
            print(f"MISSING: {JSON_PATH}")
            return 1
        records = json.loads(JSON_PATH.read_text(encoding="utf-8"))
        pages = [r.get("page") for r in records]
        contiguous = pages == list(range(1, len(pages) + 1))
        titled = sum(1 for r in records if r.get("title"))
        print(
            f"records={len(records)} contiguous={contiguous} titled={titled} "
            f"untitled={[p for p in pages if not records[p - 1].get('title')][:20]}"
        )
        return 0 if contiguous else 1

    before = titles_from_disk()
    if not before:
        before = titles_from_git()
        print(f"restoring titles from git history: {len(before)} titled pages")

    result = subprocess.run(
        [sys.executable, str(BUILDER)], cwd=REPO_ROOT, capture_output=True, text=True
    )
    print(result.stdout.strip())
    if result.returncode != 0:
        print(result.stderr.strip(), file=sys.stderr)
        return result.returncode

    records = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    restored = 0
    for item in records:
        title = before.get(item.get("page"))
        if title:
            item["title"] = title
            restored += 1
    with JSON_PATH.open("w", encoding="utf-8") as handle:
        json.dump(records, handle, ensure_ascii=False, indent=0)

    pages = [r["page"] for r in records]
    contiguous = pages == list(range(1, len(pages) + 1))
    untitled = [p for p in pages if not records[p - 1].get("title")]
    print(f"titles restored: {restored}/{len(records)}; untitled pages: {untitled}")
    return 0 if contiguous else 1


if __name__ == "__main__":
    raise SystemExit(main())
