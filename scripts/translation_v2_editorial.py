"""Pure, hash-bound user editorial policy; never authenticates source content."""

from __future__ import annotations

import copy
import hashlib
import re

from recover_sibling_blocks import parse_blocks


def canonical_file_bytes(raw: bytes) -> bytes:
    """Normalize CRLF only, preserving all other bytes and outer whitespace."""
    if not isinstance(raw, bytes):
        raise ValueError("file content must be bytes")
    return raw.replace(b"\r\n", b"\n")


def _target_parts(raw: bytes) -> tuple[bytes, str, str]:
    text = canonical_file_bytes(raw).decode("utf-8")
    blocks = parse_blocks(text)
    if [label for label, _, _ in blocks] != ["Arabic", "English"]:
        raise ValueError("expected exactly Arabic and English blocks in order")
    headings = list(re.finditer(r"(?m)^English:[ \t]*(?:\n|$)", text))
    if not text.startswith("Arabic:\n") or len(headings) != 1:
        raise ValueError("expected canonical standalone Arabic and English headings")
    arabic, english = blocks[0][1], blocks[1][1]
    if not arabic or not english:
        raise ValueError("Arabic and English bodies must not be empty")
    # Include every separator byte before the English heading in the prefix.
    prefix = text[:headings[0].start()].encode("utf-8")
    return prefix, arabic, english


def extract_english(raw: bytes) -> str:
    """Validate the wrapper and return the shared reader parser's trimmed body."""
    return _target_parts(raw)[2]


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _valid_page(page: object) -> bool:
    return type(page) is int and 1 <= page <= 604


def _valid_provenance_path(path: object) -> bool:
    if (not isinstance(path, str)
            or any(c in "\\:" or ord(c) < 32 for c in path)):
        return False
    parts = path.split("/")
    return (len(parts) >= 3 and parts[:2] == ["docs", "english-corrections"]
            and all(part not in ("", ".", "..")
                    and not part.endswith((".", " ")) for part in parts))


def _source_text(source: bytes) -> str:
    body = canonical_file_bytes(source).decode("utf-8").strip()
    if not body:
        raise ValueError("canonical source must not be empty")
    return body


def make_override_entry(
    page: int, source: bytes, previous: bytes, corrected: bytes,
    provenance: dict[str, bytes], boundary_page: int, authorized_at: str,
) -> dict:
    """Bind this exact editorial file to source and historical evidence hashes.

    CRLF-only wrapper changes are permitted; no Arabic prefix content changes
    are permitted. ``source_verified=False`` is attribution, not authentication.
    """
    if not _valid_page(page) or not _valid_page(boundary_page):
        raise ValueError("page and boundary_page must be integers in 1..604")
    if not isinstance(authorized_at, str) or not authorized_at.strip():
        raise ValueError("authorized_at must be supplied by the caller")
    if not isinstance(provenance, dict) or not provenance:
        raise ValueError("nonempty provenance is required")
    evidence = []
    for path, raw in provenance.items():
        if not _valid_provenance_path(path):
            raise ValueError("provenance must be relative under docs/english-corrections")
        normalized = canonical_file_bytes(raw)
        evidence.append({"path": path, "sha256": _sha(raw),
                         "normalized_sha256": _sha(normalized)})
    source_body = _source_text(source)
    previous_prefix, previous_arabic, _ = _target_parts(previous)
    prefix, arabic, _ = _target_parts(corrected)
    if prefix != previous_prefix:
        raise ValueError("Arabic prefix changed beyond CRLF normalization")
    if arabic != source_body or previous_arabic != source_body:
        raise ValueError("embedded Arabic differs from canonical source")
    return {
        "page": page, "boundary_page": boundary_page, "authorized_at": authorized_at,
        "kind": "user_editorial_override", "source_verified": False,
        "source_sha256": _sha(source),
        "previous_en_sha256": _sha(canonical_file_bytes(previous)),
        "en_sha256": _sha(canonical_file_bytes(corrected)),
        "observed_raw_en_sha256": _sha(corrected),
        "arabic_prefix_sha256": _sha(prefix), "provenance": evidence,
    }


def _valid_sha(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def registered_override_matches(source: bytes, target: bytes, entry: dict) -> bool:
    """Fail closed unless the source, whole target and wrapper match the registry.

    Historical provenance hashes are validated as metadata, never looked up in
    current live files, which may contain a later authorized correction.
    """
    if not isinstance(entry, dict):
        return False
    if (entry.get("kind") != "user_editorial_override"
            or entry.get("source_verified") is not False
            or not _valid_page(entry.get("page"))
            or not _valid_page(entry.get("boundary_page"))):
        return False
    authorized_at = entry.get("authorized_at")
    if not isinstance(authorized_at, str) or not authorized_at.strip():
        return False
    hashes = ("source_sha256", "previous_en_sha256", "en_sha256",
              "observed_raw_en_sha256", "arabic_prefix_sha256")
    if not all(_valid_sha(entry.get(key)) for key in hashes):
        return False
    provenance = entry.get("provenance")
    if not isinstance(provenance, list) or not provenance:
        return False
    for item in provenance:
        if (not isinstance(item, dict)
                or not _valid_provenance_path(item.get("path"))
                or not _valid_sha(item.get("sha256"))
                or not _valid_sha(item.get("normalized_sha256"))):
            return False
    try:
        source_body = _source_text(source)
        prefix, arabic, _ = _target_parts(target)
        return (entry["source_sha256"] == _sha(source)
                and entry["en_sha256"] == _sha(canonical_file_bytes(target))
                and entry["arabic_prefix_sha256"] == _sha(prefix)
                and arabic == source_body)
    except (ValueError, TypeError):
        return False


_EN_ARABIC_FINDING = re.compile(
    r"en: UNTRANSLATED [1-9][0-9]* Arabic characters in [1-9][0-9]* "
    r"run\(s\), longest [1-9][0-9]* \(e\.g\. .+\)"
)
_EN_HONORIFIC_FINDINGS = frozenset({
    "en: BANNED honorific 'exalted is He'",
    "en: honorific not the mandated 'God Most High'",
})


def split_triage_findings(
    problems: list[str], override_matches: bool,
) -> tuple[list[str], list[str]]:
    """Attribute only known EN style exceptions; retain all blocking findings."""
    remaining, waived = [], []
    for problem in problems:
        allowed = (override_matches is True
                   and (problem in _EN_HONORIFIC_FINDINGS
                        or _EN_ARABIC_FINDING.fullmatch(problem) is not None))
        (waived if allowed else remaining).append(problem)
    return remaining, waived


def overlay_english_records(
    records: list[dict], replacements: dict[int, str],
) -> list[dict]:
    """Deep-copy an existing ordered dataset, changing only requested text.en."""
    if not isinstance(records, list) or not isinstance(replacements, dict):
        raise ValueError("records must be a list and replacements must be a dict")
    for page, record in enumerate(records, 1):
        if (not isinstance(record, dict) or type(record.get("page")) is not int
                or record["page"] != page):
            raise ValueError("records must contain ordered contiguous pages 1..len(records)")
        text = record.get("text")
        if not isinstance(text, dict) or not isinstance(text.get("en"), str):
            raise ValueError("every existing record must have a text.en string")
    for page, body in replacements.items():
        if type(page) is not int or not 1 <= page <= len(records):
            raise ValueError("replacement page must already exist")
        if not isinstance(body, str) or not body.strip():
            raise ValueError("replacement English body must not be empty")
    result = copy.deepcopy(records)
    for page, body in replacements.items():
        # Detach the record and text mappings so the EN change cannot leak
        # through copied aliases in metadata or another page.
        result[page - 1] = {
            **result[page - 1],
            "text": {**result[page - 1]["text"], "en": body},
        }
    return result
