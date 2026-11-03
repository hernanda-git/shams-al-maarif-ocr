#!/usr/bin/env python3
"""Read-only supplemental Translation V2 audit verifier; never resets the tracker.

Manifest example (pages must contain each integer 1..67 exactly once)::

    {"schema_version": 1, "type": "translation_v2_supplemental_audit",
     "scope": {"first_page": 1, "last_page": 67}, "pages": [
       {"page": 1, "repairer_id": "actual-editor-session-id",
        "reviewer_id": "actual-reviewer-session-id",
        "reviewer_kind": "independent_model", "verdict": "approved",
        "files": {
          "source": {"path": "ocr/enriched/page_001.txt", "sha256": "<sha256>"},
          "english": {"path": "ocr/enriched_en/page_001.txt", "sha256": "<sha256>"},
          "indonesian": {"path": "ocr/enriched_id/page_001.txt", "sha256": "<sha256>"}},
        "evidence": {"path": "state/translation_v2/reviews/final-page-001.json",
                     "sha256": "<sha256>"},
        "generated_record_sha256": "<sha256>"}]}

All file hashes cover raw bytes and are 64 lowercase hex characters. Generated
hashes cover the ENTIRE matching manuscript record, canonicalized using UTF-8
json.dumps(sort_keys=True, ensure_ascii=False, separators=(',', ':'),
allow_nan=False), with no trailing newline. Unknown metadata is retained/allowed.
All JSON inputs reject duplicate object keys at every nesting level; a raw-file
checksum never legitimizes ambiguous JSON. Nonstandard NaN/Infinity are rejected.
Artifact paths must be root-relative, resolve inside root, and use no '..'.
Evidence must be JSON, possibly a batch report, with this structure::

    {"reviewer_id": "actual-reviewer-session-id", "reviewer_kind": "independent_model",
     "pages": [{"page": 1, "verdict": "approved", "files": {"source": {"path":
       "ocr/enriched/page_001.txt", "sha256": "<sha256>"}, "english": {"path":
       "ocr/enriched_en/page_001.txt", "sha256": "<sha256>"}, "indonesian": {"path":
       "ocr/enriched_id/page_001.txt", "sha256": "<sha256>"}},
       "coverage": "Detailed actual review coverage", "findings": [], "uncertainties": []}]}

The evidence identity/kind and corresponding page files/verdict must match the
manifest exactly. Coverage must be nonblank, approved findings must be empty,
and uncertainties must be a list; disclosed uncertainties may remain nonempty.

TRUST BOUNDARY: reviewer IDs and verdicts are declarations, NOT authentication.
The parent must verify actual independent subagent task/result lineage, coverage,
and that the report attests this snapshot. This tool detects missing/stale bytes
and inconsistent declarations; it cannot authenticate a session or judge a
translation. A passing result is not human approval or a tracker transition.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path, PureWindowsPath
from typing import Any

SCOPE = {"first_page": 1, "last_page": 67}
TRUST_BOUNDARY = (
    "IDs/verdicts are declarations, not authenticated identity or semantic review; "
    "verify independent subagent lineage and snapshot coverage externally. "
    "No human approval or tracker transition is implied."
)
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"nonstandard JSON constant: {value}")


def strict_json_loads(text: str) -> Any:
    """Reject duplicate keys recursively, including escape-equivalent key names."""
    return json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)


def canonical_record_hash(record: dict[str, Any]) -> str:
    encoded = json.dumps(
        record, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _inside(root: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("path must be a nonblank root-relative string")
    # Windows paths must remain unsafe even when tests run on POSIX.
    normalized = value.replace("\\", "/")
    path = Path(normalized)
    if path.is_absolute() or PureWindowsPath(value).drive or ".." in path.parts:
        raise ValueError("path must be root-relative without traversal")
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("path resolves outside root")
    if not resolved.is_file():
        raise ValueError("path is not an existing regular file")
    return resolved


def _hash_artifact(root: Path, spec: Any, label: str, errors: list[str], expected: str | None = None) -> Path | None:
    try:
        if not isinstance(spec, dict):
            raise ValueError("artifact must be an object with path and sha256")
        digest = spec.get("sha256")
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            raise ValueError("sha256 must be 64 lowercase hexadecimal characters")
        if expected is not None and spec.get("path") != expected:
            raise ValueError(f"path must equal {expected}")
        path = _inside(root, spec.get("path"))
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("SHA-256 mismatch (stale or changed artifact)")
        return path
    except (ValueError, OSError, RuntimeError) as exc:
        errors.append(f"{label}: {exc}")


def _verify_evidence(root: Path, entry: dict[str, Any], errors: list[str]) -> None:
    label = f"page {entry['page']} evidence"
    path = _hash_artifact(root, entry.get("evidence"), label, errors)
    if path is None:
        return
    try:
        evidence = strict_json_loads(path.read_text(encoding="utf-8"))
        if not isinstance(evidence, dict):
            raise ValueError("JSON evidence must be an object")
        for field in ("reviewer_id", "reviewer_kind"):
            if evidence.get(field) != entry.get(field):
                raise ValueError(f"{field} does not match manifest")
        pages = evidence.get("pages")
        if not isinstance(pages, list):
            raise ValueError("pages must be a list")
        seen: set[int] = set()
        match = None
        for page in pages:
            if not isinstance(page, dict) or type(page.get("page")) is not int:
                raise ValueError("every evidence page requires integer page")
            number = page["page"]
            if number in seen:
                raise ValueError(f"duplicate evidence page {number}")
            seen.add(number)
            if number == entry["page"]:
                match = page
        if match is None:
            raise ValueError("matching page absent from report")
        if match.get("verdict") != "approved":
            raise ValueError("review report does not approve this page")
        if match.get("files") != entry.get("files"):
            raise ValueError("review report files do not match manifest snapshot")
        if not isinstance(match.get("coverage"), str) or not match["coverage"].strip():
            raise ValueError("coverage must be a nonblank detailed string")
        if match.get("findings") != []:
            raise ValueError("approved report findings must be an empty list")
        if not isinstance(match.get("uncertainties"), list):
            raise ValueError("uncertainties must be a list")
    except (OSError, ValueError, RuntimeError) as exc:
        errors.append(f"{label}: {exc}")


def validate_audit(root: Path | str, manifest_path: Path | str) -> dict[str, Any]:
    """Return a deterministic report without writing files or tracker state."""
    root = Path(root).resolve()
    errors: list[str] = []
    report: dict[str, Any] = {
        "ok": False, "scope": dict(SCOPE), "pages_checked": 0,
        "errors": errors, "trust_boundary": TRUST_BOUNDARY,
    }
    try:
        manifest_file = Path(manifest_path)
        if manifest_file.is_absolute():
            manifest_file = manifest_file.resolve().relative_to(root)
        manifest = strict_json_loads(_inside(root, str(manifest_file)).read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise ValueError("manifest must be an object")
    except (OSError, ValueError, RuntimeError) as exc:
        errors.append(f"manifest: {exc}")
        return report
    if type(manifest.get("schema_version")) is not int or manifest.get("schema_version") != 1:
        errors.append("manifest: schema_version must be integer 1")
    if manifest.get("type") != "translation_v2_supplemental_audit":
        errors.append("manifest: invalid type")
    scope = manifest.get("scope")
    if (not isinstance(scope, dict) or scope != SCOPE
            or any(type(scope.get(key)) is not int for key in SCOPE)):
        errors.append("manifest: scope must be exactly first_page=1, last_page=67")
    pages = manifest.get("pages")
    if not isinstance(pages, list):
        errors.append("manifest: pages must be a list")
        return report

    generated: dict[int, dict[str, Any]] = {}
    try:
        records = strict_json_loads(_inside(root, "web/public/manuscript.json").read_text(encoding="utf-8"))
        if not isinstance(records, list):
            raise ValueError("manuscript must be a list")
        for record in records:
            if not isinstance(record, dict) or type(record.get("page")) is not int:
                raise ValueError("manuscript records require integer page")
            number = record["page"]
            if number in generated:
                raise ValueError(f"duplicate generated page {number}")
            generated[number] = record
    except (OSError, ValueError, RuntimeError) as exc:
        errors.append(f"generated manuscript: {exc}")

    seen: set[int] = set()
    for index, entry in enumerate(pages):
        if not isinstance(entry, dict) or type(entry.get("page")) is not int:
            errors.append(f"pages[{index}]: record requires integer page")
            continue
        page = entry["page"]
        label = f"page {page}"
        if page not in range(1, 68):
            errors.append(f"{label}: outside authorized scope 1..67")
            continue
        if page in seen:
            errors.append(f"{label}: duplicate audit page")
            continue
        seen.add(page)
        report["pages_checked"] += 1
        for field in ("repairer_id", "reviewer_id"):
            if not isinstance(entry.get(field), str) or not entry[field].strip():
                errors.append(f"{label}: {field} must be nonblank")
        if (isinstance(entry.get("reviewer_id"), str)
                and isinstance(entry.get("repairer_id"), str)
                and entry["reviewer_id"].strip() == entry["repairer_id"].strip()):
            errors.append(f"{label}: reviewer_id must differ from repairer_id")
        if entry.get("reviewer_kind") != "independent_model":
            errors.append(f"{label}: reviewer_kind must be independent_model")
        if entry.get("verdict") != "approved":
            errors.append(f"{label}: unresolved/rework or missing approved verdict")
        files = entry.get("files")
        if not isinstance(files, dict):
            files = {}
        for key, directory in (("source", "enriched"), ("english", "enriched_en"), ("indonesian", "enriched_id")):
            _hash_artifact(root, files.get(key), f"{label} {key}", errors,
                           f"ocr/{directory}/page_{page:03d}.txt")
        _verify_evidence(root, entry, errors)
        expected_hash = entry.get("generated_record_sha256")
        if not isinstance(expected_hash, str) or not SHA256.fullmatch(expected_hash):
            errors.append(f"{label}: generated_record_sha256 must be 64 lowercase hex characters")
        elif page not in generated:
            errors.append(f"{label}: generated record missing")
        else:
            try:
                if canonical_record_hash(generated[page]) != expected_hash:
                    errors.append(f"{label}: generated record SHA-256 mismatch")
            except (ValueError, TypeError) as exc:
                errors.append(f"{label}: invalid generated record: {exc}")
    missing = sorted(set(range(1, 68)) - seen)
    if missing:
        errors.append(f"manifest: missing scope pages {missing}")
    report["ok"] = not errors
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = validate_audit(args.root, args.manifest)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Supplemental audit: {'PASS' if report['ok'] else 'FAIL'} ({report['pages_checked']}/67 pages)")
        for error in report["errors"]:
            print(f"- {error}")
        print(TRUST_BOUNDARY)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
