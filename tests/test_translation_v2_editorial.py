"""Pure, literal-preservation tests for authorized English editorial overlays."""

import copy
import hashlib
import importlib
import importlib.util
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


def load_editorial():
    assert importlib.util.find_spec("translation_v2_editorial") is not None, (
        "The pure editorial policy module has not been implemented"
    )
    return importlib.import_module("translation_v2_editorial")


def test_canonical_bytes_change_only_crlf():
    editorial = load_editorial()
    raw = " \r\nبِسْمِ\r\n**Ā**\rkept\t \n".encode()
    assert editorial.canonical_file_bytes(raw) == " \nبِسْمِ\n**Ā**\rkept\t \n".encode()
    assert editorial.canonical_file_bytes(b"a\n\n ") == b"a\n\n "


SOURCE = "— ٣٤ —\nبِسْمِ اللهِ تَعَالَى\nسطرٌ ثانٍ".encode()
ENGLISH = (
    "— 34 —\n\n# Ādam’s **Names**\n"
    "God (exalted is He), not a silently mandated replacement.\n"
    "Example: بِسْمِ اللهِ\n| ḥāʾ | أ |\n| --- | --- |\n"
    "Its meaning in Arabic: I am He who gives everything.\n"
    "Keep CASE, e\u0301, and intentional folio 999."
)
PREFIX = b"Arabic:\n" + SOURCE + b"\n\n"
PREVIOUS = PREFIX + b"English:\nPrevious translation.\n"
CORRECTED = PREFIX + b"English:\n\n  " + ENGLISH.encode() + b"\n\n"
PROVENANCE = {"docs/english-corrections/page-040.md": b"**User evidence**\r\n"}
AUTHORIZED_AT = "2026-11-07T10:00:00+07:00"


def test_extract_english_preserves_literal_examples_case_marks_and_markdown():
    editorial = load_editorial()
    assert editorial.extract_english(CORRECTED) == ENGLISH
    assert editorial.extract_english(CORRECTED.replace(b"\n", b"\r\n")) == ENGLISH


@pytest.mark.parametrize("raw", [
    b"English:\nbody\nArabic:\nsource",
    b"Arabic:\nsource\nEnglish:\nbody\nEnglish:\nagain",
    b"Arabic:\nsource\nEnglish:\nbody\nIndonesia:\nextra",
    b"Arabic:\nsource\nenglish:\nbody",
    b"Arabic:\nsource\nEnglish:\n \t\n",
    b"preamble\nArabic:\nsource\nEnglish:\nbody",
    b"Arabic: source\nEnglish:\nbody",
    b"Arabic:\n\nEnglish:\nbody",
    b"Arabic:\nsource\nEnglish:\n\xff",
    b"",
    None,
])
def test_extract_rejects_malformed_or_empty_targets(raw):
    with pytest.raises(ValueError):
        load_editorial().extract_english(raw)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def make_entry(**changes):
    args = dict(page=40, source=SOURCE, previous=PREVIOUS, corrected=CORRECTED,
                provenance=PROVENANCE, boundary_page=95, authorized_at=AUTHORIZED_AT)
    args.update(changes)
    return load_editorial().make_override_entry(**args)


def test_entry_binds_raw_source_and_evidence_but_crlf_only_targets():
    raw_source = b" \r\n" + SOURCE.replace(b"\n", b"\r\n") + b"\r\n"
    raw_corrected = CORRECTED.replace(b"\n", b"\r\n")
    provenance_before = copy.deepcopy(PROVENANCE)
    entry = make_entry(source=raw_source, corrected=raw_corrected)
    evidence_path, evidence = next(iter(PROVENANCE.items()))
    assert entry == {
        "page": 40, "boundary_page": 95, "authorized_at": AUTHORIZED_AT,
        "kind": "user_editorial_override", "source_verified": False,
        "source_sha256": sha(raw_source),
        "previous_en_sha256": sha(PREVIOUS),
        "en_sha256": sha(CORRECTED),
        "observed_raw_en_sha256": sha(raw_corrected),
        "arabic_prefix_sha256": sha(PREFIX),
        "provenance": [{"path": evidence_path, "sha256": sha(evidence),
                        "normalized_sha256": sha(evidence.replace(b"\r\n", b"\n"))}],
    }
    assert PROVENANCE == provenance_before
    assert make_entry(previous=PREVIOUS.replace(b"\n", b"\r\n"))["previous_en_sha256"] == sha(PREVIOUS)


@pytest.mark.parametrize("changes", [
    {"corrected": CORRECTED.replace("بِسْمِ".encode(), "بسمِ".encode(), 1)},
    {"previous": PREVIOUS.replace("بِسْمِ".encode(), "بسمِ".encode(), 1)},
    {"source": SOURCE + "ز".encode()},
    {"source": b" \n\t"},
    {"source": b"\xff"},
    {"source": None},
    {"corrected": CORRECTED.replace(b"\n\nEnglish:", b"\n\n\nEnglish:", 1)},
    {"corrected": CORRECTED.replace(b"Arabic:\n", b"Arabic:\n ", 1)},
    {"corrected": PREFIX + b"English:\n  \n"},
    {"corrected": CORRECTED + b"\nEnglish:\nextra"},
    {"previous": b"not labelled"},
    {"page": 0}, {"page": 605}, {"page": True}, {"page": "40"},
    {"boundary_page": 0}, {"boundary_page": 605}, {"boundary_page": False},
    {"authorized_at": ""}, {"authorized_at": "  "}, {"authorized_at": None},
    {"provenance": {}}, {"provenance": []},
    {"provenance": {"docs/english-corrections/a.md": "not bytes"}},
])
def test_entry_rejects_arabic_prefix_drift_and_invalid_construction(changes):
    with pytest.raises(ValueError):
        make_entry(**changes)


@pytest.mark.parametrize("path", [
    "", "/docs/english-corrections/a.md", "C:/docs/english-corrections/a.md",
    "C:docs/english-corrections/a.md", "//server/share/a.md",
    "docs/english-corrections", "docs/english-corrections/",
    "docs/english-corrections/../a.md", "docs/english-corrections/sub/../../a.md",
    "docs/english-corrections/./a.md", "docs/english-corrections//a.md",
    "docs/english-corrections/.. /escape.md", "docs/english-corrections/.../a.md",
    "docs/english-corrections/a.md ", "docs/english-corrections/a\n.md",
    "docs/english-corrections/..\\a.md", "docs\\english-corrections\\a.md",
    "docs/english-corrections/a.md:stream", "docs/english-corrections/a\x00.md",
    "docs/other/a.md", "../docs/english-corrections/a.md", None,
])
def test_entry_rejects_unsafe_provenance_paths(path):
    with pytest.raises(ValueError):
        make_entry(provenance={path: b"evidence"})


@pytest.mark.parametrize("page", [1, 604])
def test_entry_accepts_inclusive_page_and_boundary_limits(page):
    assert make_entry(page=page, boundary_page=page)["page"] == page


def test_registered_match_accepts_only_bound_file_and_historical_evidence():
    editorial = load_editorial()
    entry = make_entry(provenance={"docs/english-corrections/historical-only.md": b"old bytes"})
    snapshot = copy.deepcopy(entry)
    assert editorial.registered_override_matches(SOURCE, CORRECTED, entry) is True
    assert editorial.registered_override_matches(SOURCE, CORRECTED.replace(b"\n", b"\r\n"), entry) is True
    assert entry == snapshot
    # The input evidence may subsequently be superseded; only registry hashes bind history.
    later_evidence = {"docs/english-corrections/historical-only.md": b"superseded bytes"}
    assert sha(next(iter(later_evidence.values()))) != entry["provenance"][0]["sha256"]
    assert editorial.registered_override_matches(SOURCE, CORRECTED, entry) is True


@pytest.mark.parametrize("target", [
    PREVIOUS, CORRECTED + b" ",
    CORRECTED.replace(b"CASE", b"Case"),
    CORRECTED.replace("e\u0301".encode(), "é".encode()),
    CORRECTED.replace("بِسْمِ".encode(), "بسمِ".encode(), 1),
    CORRECTED.replace(b"\n\nEnglish:", b"\n\n\nEnglish:", 1),
    b"", None, "not bytes",
])
def test_registered_match_rejects_any_non_crlf_target_drift(target):
    assert load_editorial().registered_override_matches(SOURCE, target, make_entry()) is False


@pytest.mark.parametrize("source", [
    SOURCE + b"\n", SOURCE.replace(b"\n", b"\r\n"),
    SOURCE.replace("بِسْمِ".encode(), "بسمِ".encode()),
    b"", b"\xff", None, "not bytes",
])
def test_registered_match_binds_raw_canonical_source_even_for_outer_whitespace(source):
    assert load_editorial().registered_override_matches(source, CORRECTED, make_entry()) is False


@pytest.mark.parametrize("field,value", [
    ("kind", "translation"), ("kind", None),
    ("source_verified", True), ("source_verified", 0), ("source_verified", None),
    ("page", 0), ("page", 605), ("page", "40"), ("page", True),
    ("boundary_page", 0), ("boundary_page", 605), ("boundary_page", 95.0),
    ("authorized_at", ""), ("authorized_at", "  "), ("authorized_at", None),
    ("source_sha256", "0" * 64), ("en_sha256", "0" * 64),
    ("arabic_prefix_sha256", "0" * 64),
    ("previous_en_sha256", "xyz"), ("observed_raw_en_sha256", False),
    ("provenance", []), ("provenance", {}), ("provenance", None),
    ("provenance", [{"path": "docs/english-corrections/a.md"}]),
    ("provenance", [{"path": "docs/english-corrections/../escape.md",
                     "sha256": "0" * 64, "normalized_sha256": "0" * 64}]),
    ("provenance", [None]),
])
def test_registered_match_fails_closed_for_malformed_metadata(field, value):
    entry = make_entry()
    entry[field] = value
    assert load_editorial().registered_override_matches(SOURCE, CORRECTED, entry) is False


@pytest.mark.parametrize("field", [
    "page", "boundary_page", "authorized_at", "kind", "source_verified",
    "source_sha256", "previous_en_sha256", "en_sha256", "observed_raw_en_sha256",
    "arabic_prefix_sha256", "provenance",
])
def test_registered_match_requires_all_entry_fields(field):
    entry = make_entry()
    del entry[field]
    assert load_editorial().registered_override_matches(SOURCE, CORRECTED, entry) is False


@pytest.mark.parametrize("entry", [None, [], "entry", 0, True, {}])
def test_registered_match_rejects_non_registry_objects(entry):
    assert load_editorial().registered_override_matches(SOURCE, CORRECTED, entry) is False


@pytest.mark.parametrize("target", [
    PREFIX + b"English:\n  \n",
    CORRECTED + b"English:\nextra",
    CORRECTED.replace("بِسْمِ".encode(), "بسمِ".encode(), 1),
])
def test_registry_hash_does_not_override_structural_or_arabic_validation(target):
    entry = make_entry()
    entry["en_sha256"] = sha(target)
    entry["observed_raw_en_sha256"] = sha(target)
    assert load_editorial().registered_override_matches(SOURCE, target, entry) is False


def test_registry_source_hash_alone_cannot_authorize_different_embedded_arabic():
    changed_source = SOURCE + "ز".encode()
    entry = make_entry()
    entry["source_sha256"] = sha(changed_source)
    assert load_editorial().registered_override_matches(changed_source, CORRECTED, entry) is False


STYLE_FINDINGS = [
    "en: UNTRANSLATED 4 Arabic characters in 1 run(s), longest 4 (e.g. 'الله')",
    "en: BANNED honorific 'exalted is He'",
    "en: honorific not the mandated 'God Most High'",
]
BLOCKING_FINDINGS = [
    "id: UNTRANSLATED 4 Arabic characters in 1 run(s), longest 4 (e.g. 'الله')",
    "id: honorific not the mandated 'Yang Mahatinggi'",
    "en: FOLIO WRONG PAGE source 34 target 999",
    "en: FOLIO off-by-one (normal realignment) source 34 target 35",
    "en: EMPTY (0c)", "en: MALFORMED labels=['English']",
    "en: file missing", "en: no English block", "no canonical source",
    "en: NO TEXT marker over nonblank canonical source", "other issue",
    "en: BANNED honorific 'something else'",
    "en: BANNED honorific 'exalted is He' FOLIO WRONG PAGE",
    "en: UNTRANSLATED malformed Arabic characters",
    STYLE_FINDINGS[0] + " FOLIO WRONG PAGE",
]


def test_triage_split_waives_only_exact_en_style_findings_after_registered_match():
    editorial = load_editorial()
    findings = [STYLE_FINDINGS[0], *BLOCKING_FINDINGS, *STYLE_FINDINGS[1:]]
    before = list(findings)
    matches = editorial.registered_override_matches(SOURCE, CORRECTED, make_entry())
    remaining, waived = editorial.split_triage_findings(findings, matches)
    assert remaining == BLOCKING_FINDINGS
    assert waived == STYLE_FINDINGS
    assert findings == before
    assert remaining is not findings and waived is not findings


@pytest.mark.parametrize("matches", [False, None, 1, "true"])
def test_triage_without_registered_match_waives_nothing(matches):
    findings = STYLE_FINDINGS + BLOCKING_FINDINGS
    remaining, waived = load_editorial().split_triage_findings(findings, matches)
    assert remaining == findings and remaining is not findings
    assert waived == []


def test_triage_split_preserves_duplicates_and_empty_list():
    editorial = load_editorial()
    assert editorial.split_triage_findings([], True) == ([], [])
    assert editorial.split_triage_findings([STYLE_FINDINGS[1]] * 2, True) == (
        [], [STYLE_FINDINGS[1]] * 2)


def records_fixture():
    return [
        {"page": page, "text": {"ar": SOURCE.decode(), "en": f"old {page}",
                                "id": "Indonesia: tetap", "extra": {"marks": ["ā"]}},
         "title": {"ar": "عنوان", "en": "Original Title", "id": "Judul"},
         "scanSrc": f"/keep-exact/scan-{page}.pdf?x=1",
         "other": {"nested": [{"folio": "٣٤"}], "verified": False}}
        for page in range(1, 4)
    ]


def test_overlay_updates_only_requested_text_en_and_deepcopies_every_record():
    records = records_fixture()
    before = copy.deepcopy(records)
    literal_replacement = " \n" + ENGLISH + "\n\n "
    replacement = {2: literal_replacement}
    result = load_editorial().overlay_english_records(records, replacement)
    expected = copy.deepcopy(before)
    expected[1]["text"]["en"] = literal_replacement
    assert result == expected
    assert records == before
    assert replacement == {2: literal_replacement}
    for original, overlaid in zip(records, result):
        assert overlaid is not original
        assert overlaid["text"] is not original["text"]
        assert overlaid["title"] is not original["title"]
        assert overlaid["text"]["extra"] is not original["text"]["extra"]
        assert overlaid["other"]["nested"] is not original["other"]["nested"]
    result[0]["other"]["nested"][0]["folio"] = "changed copy"
    assert records == before


def test_overlay_isolates_shared_text_objects_from_other_records_and_metadata():
    records = records_fixture()
    records[1]["text"] = records[0]["text"]
    records[0]["other"]["text_alias"] = records[0]["text"]
    before = copy.deepcopy(records)
    result = load_editorial().overlay_english_records(records, {1: ENGLISH})
    assert result[0]["text"]["en"] == ENGLISH
    assert result[0]["other"] == before[0]["other"]
    assert result[1:] == before[1:]
    assert records == before


def test_overlay_preserves_metadata_aliasing_the_selected_record():
    records = [
        {"page": 1, "text": {"en": "first"}, "meta": {}},
        {"page": 2, "text": {"en": "second"}, "meta": {}},
    ]
    records[1]["meta"]["record_alias"] = records[0]
    before = copy.deepcopy(records)
    result = load_editorial().overlay_english_records(records, {1: "changed"})
    assert result[0]["text"]["en"] == "changed"
    assert result[1]["meta"] == before[1]["meta"]
    assert records == before


def test_overlay_without_replacements_is_a_deep_copy_not_a_rebuild():
    records = records_fixture()
    result = load_editorial().overlay_english_records(records, {})
    assert result == records and result is not records
    result[2]["title"]["en"] = "copy only"
    assert records[2]["title"]["en"] == "Original Title"
    assert load_editorial().overlay_english_records([], {}) == []


@pytest.mark.parametrize("records", [
    [{"page": 1, "text": {"en": "a"}}, {"page": 1, "text": {"en": "b"}}],
    [{"page": 1, "text": {"en": "a"}}, {"page": 3, "text": {"en": "c"}}],
    [{"page": 2, "text": {"en": "b"}}, {"page": 1, "text": {"en": "a"}}],
    [{"page": 0, "text": {"en": "a"}}],
    [{"page": "1", "text": {"en": "a"}}],
    [{"page": True, "text": {"en": "a"}}],
    [{"page": 1.0, "text": {"en": "a"}}],
    [{"text": {"en": "a"}}], [{"page": 1}],
    [{"page": 1, "text": None}], [{"page": 1, "text": {}}],
    [{"page": 1, "text": {"ar": "source", "id": "kept"}}],
    [{"page": 1, "text": {"en": None}}],
    [None], {}, None,
])
def test_overlay_rejects_missing_duplicate_unordered_or_malformed_records(records):
    before = copy.deepcopy(records)
    with pytest.raises(ValueError):
        load_editorial().overlay_english_records(records, {})
    assert records == before


@pytest.mark.parametrize("replacement", [
    {0: "new"}, {4: "new"}, {"2": "new"}, {True: "new"}, {2.0: "new"},
    {1: ENGLISH, 4: "missing"}, {2: ""}, {2: " \n\t"}, {2: None}, {2: b"bytes"},
    [], None,
])
def test_overlay_rejects_nonexistent_pages_or_missing_replacement_bodies(replacement):
    records = records_fixture()
    before = copy.deepcopy(records)
    with pytest.raises(ValueError):
        load_editorial().overlay_english_records(records, replacement)
    assert records == before
