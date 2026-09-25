#!/usr/bin/env python3
"""Deterministic validation gate for one Translation Alignment V2 page."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


LABELS = {"Arabic", "English", "Indonesia"}
RECOGNISED_NO_TEXT_SOURCE = re.compile(
    r"^---\s*\nthere is no text on this page\.\s*\n---$",
    re.IGNORECASE,
)
EN_NO_TEXT_MARKER = "[NO VISIBLE TEXT]"
ID_NO_TEXT_MARKER = "[TIDAK ADA TEKS TERLIHAT]"
EN_FALLBACKS = {
    "(no english text on this page)",
    "(no english text on this page.)",
    "there is no text on this page.",
}
ID_FALLBACKS = {
    "(tidak ada teks pada halaman ini)",
    "(tidak ada teks pada halaman ini.)",
    "tidak ada teks pada halaman ini.",
}


class PageValidationError(ValueError):
    pass


def _root(root: Path | str | None) -> Path:
    return (
        Path(root).expanduser().resolve()
        if root is not None
        else Path(__file__).resolve().parents[1]
    )


def _clean(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()


def _parse_blocks(text: str, path: Path) -> tuple[dict[str, str], dict[str, int], list[str]]:
    """Parse exact heading lines without allowing a heading regex to cross blocks."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    occurrences: dict[str, int] = {label: 0 for label in LABELS}
    positions: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.endswith(":") and stripped[:-1] in LABELS:
            label = stripped[:-1]
            occurrences[label] += 1
            positions.append((index, label))

    errors: list[str] = []
    if not positions:
        errors.append(f"{path.name}: no canonical block labels found")
        return {}, occurrences, errors

    blocks: dict[str, str] = {}
    for position, (start, label) in enumerate(positions):
        end = positions[position + 1][0] if position + 1 < len(positions) else len(lines)
        body = "\n".join(lines[start + 1 : end]).strip()
        if label in blocks:
            errors.append(f"{path.name}: duplicate {label} label")
        else:
            blocks[label] = body
    return blocks, occurrences, errors


def _read(path: Path, errors: list[str]) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        errors.append(f"missing file: {path.as_posix()}")
    except OSError as exc:
        errors.append(f"cannot read {path.as_posix()}: {exc}")
    return None


def _is_explicit_no_text(source: str) -> bool:
    return bool(RECOGNISED_NO_TEXT_SOURCE.fullmatch(_clean(source)))


def _validate_target(
    path: Path,
    text: str | None,
    required: set[str],
    source: str,
    language: str,
    errors: list[str],
) -> tuple[str | None, dict[str, str]]:
    if text is None:
        return None, {}
    blocks, counts, parse_errors = _parse_blocks(text, path)
    errors.extend(parse_errors)
    actual = set(blocks)
    missing = required - actual
    extra = actual - required
    if missing:
        errors.append(f"{path.name}: missing required labels: {', '.join(sorted(missing))}")
    if extra:
        errors.append(f"{path.name}: unexpected labels: {', '.join(sorted(extra))}")
    for label, count in counts.items():
        if count > 1:
            # _parse_blocks already reports this, but this message makes the
            # structured report useful even when duplicate blocks are empty.
            errors.append(f"{path.name}: duplicate {label} label ({count} occurrences)")

    embedded = blocks.get("Arabic")
    if embedded is not None and _clean(embedded) != _clean(source):
        errors.append(
            f"{path.name}: embedded Arabic differs from canonical ocr/enriched source"
        )

    target_label = "English" if language == "en" else "Indonesia"
    body = blocks.get(target_label)
    if body is None:
        return None, blocks
    body_clean = _clean(body)
    if not body_clean:
        errors.append(f"{path.name}: {target_label} block is empty")
    blank_source = _is_explicit_no_text(source)
    if blank_source:
        expected_marker = EN_NO_TEXT_MARKER if language == "en" else ID_NO_TEXT_MARKER
        if body_clean != expected_marker:
            errors.append(
                f"{path.name}: blank source requires exact marker {expected_marker!r}"
            )
    else:
        fallbacks = EN_FALLBACKS if language == "en" else ID_FALLBACKS
        if body_clean.casefold() in fallbacks:
            errors.append(
                f"{path.name}: fallback text is not allowed on a content page"
            )
    return body_clean, blocks


def validate_page(root: Path | str | None, page: int) -> dict[str, Any]:
    root_path = _root(root)
    errors: list[str] = []
    warnings: list[str] = []
    if page < 1:
        return {"ok": False, "page": page, "errors": ["page must be >= 1"], "warnings": []}

    page_name = f"page_{page:03d}.txt"
    source_path = root_path / "ocr" / "enriched" / page_name
    en_path = root_path / "ocr" / "enriched_en" / page_name
    id_path = root_path / "ocr" / "enriched_id" / page_name
    json_path = root_path / "web" / "public" / "manuscript.json"

    source = _read(source_path, errors)
    en_text = _read(en_path, errors)
    id_text = _read(id_path, errors)
    if source is None:
        source = ""

    en_body, en_blocks = _validate_target(
        en_path, en_text, {"Arabic", "English"}, source, "en", errors
    )
    id_body, id_blocks = _validate_target(
        id_path, id_text, {"Arabic", "Indonesia"}, source, "id", errors
    )

    record: dict[str, Any] | None = None
    json_text = _read(json_path, errors)
    if json_text is not None:
        try:
            records = json.loads(json_text)
            if not isinstance(records, list):
                raise PageValidationError("manuscript JSON root is not a list")
            matches = [item for item in records if isinstance(item, dict) and item.get("page") == page]
            if len(matches) != 1:
                errors.append(
                    f"manuscript JSON must contain exactly one record for page {page}; "
                    f"found {len(matches)}"
                )
            else:
                record = matches[0]
                text = record.get("text")
                if not isinstance(text, dict):
                    errors.append(f"manuscript JSON page {page} has no text object")
                else:
                    if _clean(str(text.get("ar", ""))) != _clean(source):
                        errors.append(
                            f"manuscript JSON page {page} Arabic text differs from source"
                        )
                    if en_body is not None and _clean(str(text.get("en", ""))) != en_body:
                        errors.append(
                            f"manuscript JSON page {page} English text differs from target file"
                        )
                    if id_body is not None and _clean(str(text.get("id", ""))) != id_body:
                        errors.append(
                            f"manuscript JSON page {page} Indonesian text differs from target file"
                        )
        except (json.JSONDecodeError, PageValidationError) as exc:
            errors.append(f"cannot validate manuscript JSON: {exc}")

    return {
        "ok": not errors,
        "page": page,
        "source_path": source_path.as_posix(),
        "english_path": en_path.as_posix(),
        "indonesian_path": id_path.as_posix(),
        "json_path": json_path.as_posix(),
        "blank_source": _is_explicit_no_text(source),
        "english_block": en_body,
        "indonesian_block": id_body,
        "record_found": record is not None,
        "errors": errors,
        "warnings": warnings,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("page", type=int)
    parser.add_argument("--root", default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = validate_page(args.root, args.page)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        state = "PASS" if report["ok"] else "FAIL"
        print(f"{state}: page {args.page}")
        for error in report["errors"]:
            print(f"- {error}")
        for warning in report["warnings"]:
            print(f"WARNING: {warning}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
