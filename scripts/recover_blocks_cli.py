#!/usr/bin/env python3
"""Repair sibling-file block defects in the tri-lingual translation layers.

Defect class: a translation that was written into the WRONG file, or written
without a usable label, so ``build_manuscript_json.py`` silently drops it and
the reader renders a fallback string.

This tool only ever *moves or relabels existing translation text*. It never
writes a new translation -- pages that genuinely need one are reported as
``translate`` and must be handled by a human/LLM under docs/translation-style-v2.md.

The target file is always rewritten in the canonical V2 shape:

    Arabic:
    <verbatim ocr/enriched/page_NNN.txt>

    <Target>:
    <body>

Usage:
  uv run --no-project python scripts/recover_sibling_blocks.py --scan
  uv run --no-project python scripts/recover_sibling_blocks.py --pages 59,95 --dry-run
  uv run --no-project python scripts/recover_sibling_blocks.py --apply-all
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from recover_sibling_blocks import (  # noqa: E402
    blocks_for,
    clean,
    is_translation_like,
    plan_page,
    strip_artifacts,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
OCR = REPO_ROOT / "ocr"
TOTAL_PAGES = 604

FOLDERS = {"en": OCR / "enriched_en", "id": OCR / "enriched_id"}
SIBLING = {"en": OCR / "enriched_id", "id": OCR / "enriched_en"}
LABEL_OF = {"en": "English", "id": "Indonesia"}


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return ""


def canonical_source(page: int) -> str:
    return clean(read(OCR / "enriched" / f"page_{page:03d}.txt"))


def _to_ascii_digits(text: str) -> str:
    """Map Arabic-Indic and Extended Arabic-Indic digits onto ASCII."""
    out = []
    for ch in text:
        if "٠" <= ch <= "۹":
            out.append(str(ord(ch) - ord("٠")))
        elif "۰" <= ch <= "۹":
            out.append(str(ord(ch) - ord("۰")))
        else:
            out.append(ch)
    return "".join(out)


def leading_folio(text: str) -> str:
    """Return the leading folio numeral as ASCII digits.

    The Arabic source writes folios in Arabic-Indic digits ('— ٥٣ —') while a
    Latin translation writes the same folio in ASCII ('— 53 —'), so a raw
    string comparison reports a mismatch on every recovered page. Normalise
    both sides before comparing.
    """
    for line in clean(text).split("\n")[:3]:
        digits = "".join(ch for ch in line if ch.isdigit() or "٠" <= ch <= "۹")
        if digits:
            return _to_ascii_digits(digits)
    return ""


def render(canonical: str, label: str, body: str) -> str:
    return f"Arabic:\n{canonical}\n\n{label}:\n{body}\n"


def analyse(page: int, lang: str) -> dict:
    label = LABEL_OF[lang]
    target_path = FOLDERS[lang] / f"page_{page:03d}.txt"
    sibling_path = SIBLING[lang] / f"page_{page:03d}.txt"

    own = [
        body
        for body in blocks_for(strip_artifacts(clean(read(target_path))), label)
        if is_translation_like(body, lang)
    ]
    if own:
        return {
            "page": page,
            "lang": lang,
            "action": "ok",
            "reason": f"target already has a valid {label} block ({len(own[0])} chars)",
            "body": own[0],
        }

    plan = plan_page(read(sibling_path), label, sibling_path.parent.name, lang)
    report = {
        "page": page,
        "lang": lang,
        "action": plan["action"],
        "reason": plan["reason"],
        "body": plan["body"],
    }
    if plan["body"]:
        src_folio = leading_folio(canonical_source(page))
        body_folio = leading_folio(plan["body"])
        report["source_folio"] = src_folio
        report["body_folio"] = body_folio
        report["folio_match"] = bool(src_folio) and src_folio == body_folio
    return report


def scan() -> list[dict]:
    findings = []
    for page in range(1, TOTAL_PAGES + 1):
        for lang in ("en", "id"):
            report = analyse(page, lang)
            if report["action"] != "ok":
                findings.append(report)
    return findings


def apply_one(report: dict) -> str:
    if report["action"] == "translate":
        return "skipped (needs translation)"
    body = strip_artifacts(report.get("body", ""))
    if not body:
        return "skipped (no body)"
    page, lang = report["page"], report["lang"]
    target_path = FOLDERS[lang] / f"page_{page:03d}.txt"
    target_path.write_text(
        render(canonical_source(page), LABEL_OF[lang], body), encoding="utf-8"
    )
    rel = target_path.relative_to(REPO_ROOT).as_posix()
    return f"{report['action']}: wrote {len(body)} chars -> {rel}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan", action="store_true", help="report every defect")
    parser.add_argument("--pages", default="", help="comma-separated page numbers")
    parser.add_argument("--lang", default="", choices=["", "en", "id"])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply-all", action="store_true")
    args = parser.parse_args(argv)

    if args.pages:
        pages = [int(x) for x in args.pages.split(",") if x.strip()]
        langs = [args.lang] if args.lang else ["en", "id"]
        reports = [analyse(page, lang) for page in pages for lang in langs]
    else:
        reports = scan()

    for report in reports:
        folio = ""
        if "folio_match" in report:
            folio = (
                f"  folio src={report['source_folio']!r} body={report['body_folio']!r}"
                f" match={report['folio_match']}"
            )
        print(f"  p{report['page']:03d} {report['lang']}  {report['action']:<9} {report['reason']}{folio}")

    actionable = [r for r in reports if r["action"] in ("recover", "relabel")]
    needs_work = [r for r in reports if r["action"] == "translate"]
    print(f"\nrecover/relabel: {len(actionable)}   needs translation: {len(needs_work)}")
    if needs_work:
        print("  translate-needed: " + ", ".join(f"p{r['page']:03d}/{r['lang']}" for r in needs_work))

    if args.apply_all and not args.dry_run:
        print("\napplying:")
        for report in actionable:
            print(f"  p{report['page']:03d} {report['lang']}: {apply_one(report)}")
    elif actionable:
        print("\n(dry run - pass --apply-all to write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
