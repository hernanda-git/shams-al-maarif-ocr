#!/usr/bin/env python3
"""Sweep every accepted Translation V2 page through the deterministic validator.

Usage:
  uv run --no-project python scripts/sweep_translation_v2.py            # all committed pages
  uv run --no-project python scripts/sweep_translation_v2.py 54         # through page 54
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from verify_translation_v2_page import validate_page  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROGRESS = ROOT / "state" / "translation_v2" / "progress.json"


def committed_pages() -> list[int]:
    data = json.loads(PROGRESS.read_text(encoding="utf-8"))
    pages = data.get("pages", {})
    out = []
    for key, record in pages.items():
        status = record.get("status") if isinstance(record, dict) else None
        if status == "committed":
            out.append(int(key))
    return sorted(out)


def main() -> int:
    pages = committed_pages()
    if len(sys.argv) > 1:
        limit = int(sys.argv[1])
        pages = [p for p in pages if p <= limit]
    failures = []
    for page in pages:
        report = validate_page(ROOT, page)
        if not report["ok"]:
            failures.append((page, report["errors"]))
    print(f"swept {len(pages)} pages: {len(pages) - len(failures)} pass, {len(failures)} fail")
    for page, errors in failures:
        print(f"FAIL page {page}:")
        for error in errors:
            print(f"  - {error}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
