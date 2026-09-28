"""Add titles for pages 601-604 to web/public/manuscript.json.

Pages 601-604 are the tail of the scan: a blank page, a library due-date card,
another blank page, and a final blank page. They have real (if thin) source
content, so each gets a title that DESCRIBES the page rather than inventing a
subject. The two Arabic bodies of pages 601 and 603 are the pipeline's own
English no-text markers, so the titles stay neutral.

This is a data-only edit: it touches the generated JSON, so
rebuild_manuscript_json.py must be re-run afterwards to prove the titles
survive a rebuild (they are restored from disk, then from git history).
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = REPO_ROOT / "web" / "public" / "manuscript.json"

TITLES = {
    601: {
        "ar": "صفحة فارغة",
        "en": "Blank Page",
        "id": "Halaman Kosong",
    },
    602: {
        "ar": "بطاقة إعارة المكتبة",
        "en": "Library Due-Date Card",
        "id": "Kartu Tempo Peminjaman Pustaka",
    },
    603: {
        "ar": "صفحة فارغة",
        "en": "Blank Page",
        "id": "Halaman Kosong",
    },
    604: {
        "ar": "صفحة فارغة",
        "en": "Blank Page",
        "id": "Halaman Kosong",
    },
}


def main() -> int:
    records = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    by_page = {r["page"]: r for r in records}

    for page, title in TITLES.items():
        record = by_page.get(page)
        if record is None:
            print(f"  page {page} missing from JSON - skipped")
            continue
        record["title"] = title
        print(f"  page {page}: {title['en']}")

    JSON_PATH.write_text(
        json.dumps(records, ensure_ascii=False, indent=0), encoding="utf-8"
    )

    titled = sum(1 for r in records if r.get("title"))
    untitled = [r["page"] for r in records if not r.get("title")]
    print(f"\nrecords={len(records)} titled={titled} untitled={untitled}")
    return 0 if not untitled else 1


if __name__ == "__main__":
    raise SystemExit(main())
