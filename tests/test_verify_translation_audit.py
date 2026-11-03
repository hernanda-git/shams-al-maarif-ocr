"""Isolated manifest-schema examples; fixture IDs/verdicts are not real approvals."""
import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from verify_translation_audit import canonical_record_hash, main, strict_json_loads, validate_audit


@pytest.fixture
def audit(tmp_path):
    records = []
    pages = []

    def artifact(relative, text):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
        return {"path": relative, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    for page in range(1, 68):
        record = {"page": page, "text": {"ar": "عربي", "en": "English", "id": "Indonesia"}}
        records.append(record)
        pages.append({
            "page": page, "repairer_id": "fixture-editor", "reviewer_id": "fixture-reviewer",
            "reviewer_kind": "independent_model", "verdict": "approved",
            "files": {
                key: artifact(f"ocr/{directory}/page_{page:03d}.txt", f"{page} {key} عربي\r\n")
                for key, directory in (("source", "enriched"), ("english", "enriched_en"), ("indonesian", "enriched_id"))
            },
            "evidence": artifact(f"state/translation_v2/reviews/audit-{page:03d}.md", "Synthetic final report\n"),
            "generated_record_sha256": canonical_record_hash(record),
        })
    for entry in pages:
        evidence = {"reviewer_id": entry["reviewer_id"], "reviewer_kind": "independent_model",
                    "pages": [{"page": entry["page"], "verdict": "approved",
                               "files": copy.deepcopy(entry["files"]),
                               "coverage": "Synthetic source fidelity and EN/ID parity review",
                               "findings": [], "uncertainties": []}]}
        entry["evidence"] = artifact(f"state/translation_v2/reviews/audit-{entry['page']:03d}.json",
                                     json.dumps(evidence, ensure_ascii=False))
    manuscript = tmp_path / "web/public/manuscript.json"
    manuscript.parent.mkdir(parents=True)
    manuscript.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
    manifest = {"schema_version": 1, "type": "translation_v2_supplemental_audit",
                "scope": {"first_page": 1, "last_page": 67}, "pages": pages}
    return tmp_path, manifest, records


def check(audit):
    root, manifest, _ = audit
    path = root / "supplemental.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return validate_audit(root, path)


def test_complete_manifest_passes_without_tracker_or_file_writes(audit):
    root, manifest, _ = audit
    manifest["reconciliation"] = {"note": "optional metadata"}
    manifest["pages"][0]["original_commit_sha"] = "historical metadata"
    assert check(audit)["ok"]
    before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    report = validate_audit(root, "supplemental.json")
    after = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    assert before == after
    assert report["pages_checked"] == 67
    assert "not authenticated" in report["trust_boundary"]
    assert not (root / "state/translation_v2/progress.json").exists()


@pytest.mark.parametrize("verdict", ["rework", "unresolved", None, "APPROVED", True])
def test_rejects_nonfinal_verdict(audit, verdict):
    audit[1]["pages"][0]["verdict"] = verdict
    assert not check(audit)["ok"]


@pytest.mark.parametrize("field,value", [
    ("reviewer_id", "fixture-editor"), ("reviewer_id", " fixture-editor "),
    ("reviewer_id", " "), ("reviewer_id", None), ("repairer_id", ""),
    ("reviewer_kind", "human"), ("reviewer_kind", None),
])
def test_rejects_inconsistent_review_declarations(audit, field, value):
    audit[1]["pages"][0][field] = value
    assert not check(audit)["ok"]


def test_id_swap_does_not_repair_stale_evidence(audit):
    root, manifest, _ = audit
    manifest["pages"][0]["reviewer_id"] = "another-declared-id"
    (root / manifest["pages"][0]["evidence"]["path"]).write_text("changed", encoding="utf-8")
    assert any("evidence" in e and "mismatch" in e for e in check(audit)["errors"])


@pytest.mark.parametrize("kind", ["source", "english", "indonesian", "evidence"])
def test_detects_stale_raw_artifact_bytes(audit, kind):
    root, manifest, _ = audit
    entry = manifest["pages"][0]
    artifact = entry["evidence"] if kind == "evidence" else entry["files"][kind]
    path = root / artifact["path"]
    path.write_bytes(path.read_bytes() + b"changed")
    assert any(kind in e and "mismatch" in e for e in check(audit)["errors"])


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "outside", "boolean", "not_object"])
def test_exact_scope_pages_required(audit, mutation):
    pages = audit[1]["pages"]
    if mutation == "missing":
        pages.pop()
    elif mutation == "duplicate":
        pages.append(copy.deepcopy(pages[0]))
    elif mutation == "outside":
        pages[-1]["page"] = 68
    elif mutation == "boolean":
        pages[0]["page"] = True
    else:
        pages[0] = None
    assert not check(audit)["ok"]


@pytest.mark.parametrize("field,value", [
    ("schema_version", True), ("schema_version", 2), ("type", "other"),
    ("scope", {"first_page": True, "last_page": 67}),
    ("scope", {"first_page": 1, "last_page": 68}), ("pages", {}),
])
def test_bad_manifest_shape_fails(audit, field, value):
    audit[1][field] = value
    assert not check(audit)["ok"]


@pytest.mark.parametrize("path", ["../outside.md", "state/../../outside.md", "C:/outside.md", "C:outside.md", "/outside.md", "\\\\server\\share\\report.md"])
def test_evidence_paths_cannot_escape_root(audit, path):
    audit[1]["pages"][0]["evidence"]["path"] = path
    assert not check(audit)["ok"]


def test_source_path_must_match_physical_page(audit):
    manifest = audit[1]
    manifest["pages"][0]["files"]["source"] = manifest["pages"][1]["files"]["source"]
    assert any("path must equal" in e for e in check(audit)["errors"])


def test_missing_evidence_fails(audit):
    audit[1]["pages"][0].pop("evidence")
    assert not check(audit)["ok"]


def test_missing_target_file_fails(audit):
    root, manifest, _ = audit
    # Remove a fixture only, never a repository artifact.
    path = root / manifest["pages"][0]["files"]["english"]["path"]
    assert path.resolve().is_relative_to(root.resolve())
    path.unlink()
    assert not check(audit)["ok"]


@pytest.mark.parametrize("digest", ["not-a-hash", "a" * 63, "A" * 64, None])
def test_invalid_hash_declarations_fail(audit, digest):
    audit[1]["pages"][0]["evidence"]["sha256"] = digest
    audit[1]["pages"][0]["generated_record_sha256"] = digest
    assert not check(audit)["ok"]


@pytest.mark.parametrize("mutation", ["stale", "missing", "duplicate", "non_list", "nan"])
def test_generated_record_problems_fail(audit, mutation):
    root, _, records = audit
    if mutation == "stale":
        records[0]["text"]["en"] = "changed"
    elif mutation == "missing":
        records.pop(0)
    elif mutation == "duplicate":
        records.append(records[0])
    elif mutation == "non_list":
        records = {"pages": records}
    else:
        records[0]["extra"] = float("nan")
    (root / "web/public/manuscript.json").write_text(json.dumps(records), encoding="utf-8")
    assert not check(audit)["ok"]


def test_canonical_hash_is_utf8_sorted_compact_and_no_newline():
    record = {"text": {"id": "é", "ar": "ع"}, "page": 1}
    expected = '{"page":1,"text":{"ar":"ع","id":"é"}}'.encode("utf-8")
    assert canonical_record_hash(record) == hashlib.sha256(expected).hexdigest()
    assert canonical_record_hash(record) == canonical_record_hash({"page": 1, "text": {"ar": "ع", "id": "é"}})


def test_unrelated_generated_page_does_not_stale_audited_records(audit):
    root, _, records = audit
    records.append({"page": 68, "text": {"en": "outside audited scope"}})
    (root / "web/public/manuscript.json").write_text(json.dumps(records, indent=4), encoding="utf-8")
    assert check(audit)["ok"]


def test_cli_json_and_exit_status(audit, capsys):
    root = audit[0]
    assert check(audit)["ok"]
    assert main(["--root", str(root), "--manifest", "supplemental.json", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"]
    assert main(["--root", str(root), "--manifest", "missing.json", "--json"]) == 1
    assert not json.loads(capsys.readouterr().out)["ok"]


def rewrite_evidence(audit, mutate):
    root, manifest, _ = audit
    entry = manifest["pages"][0]
    path = root / entry["evidence"]["path"]
    evidence = json.loads(path.read_text(encoding="utf-8"))
    mutate(evidence)
    path.write_text(json.dumps(evidence), encoding="utf-8")
    # Keep raw-file checksum current: these tests target structured contradictions.
    entry["evidence"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("mutation", ["rework", "wrong_reviewer", "wrong_kind", "wrong_page",
    "wrong_hash", "wrong_path", "empty_coverage", "findings", "missing_uncertainties",
    "duplicate_page", "boolean_page"])
def test_evidence_must_attest_the_same_approved_snapshot(audit, mutation):
    def mutate(evidence):
        page = evidence["pages"][0]
        if mutation == "rework":
            page["verdict"] = "rework"
        elif mutation == "wrong_reviewer":
            evidence["reviewer_id"] = "different-reviewer"
        elif mutation == "wrong_kind":
            evidence["reviewer_kind"] = "human"
        elif mutation == "wrong_page":
            page["page"] = 2
        elif mutation == "wrong_hash":
            page["files"]["english"]["sha256"] = "0" * 64
        elif mutation == "wrong_path":
            page["files"]["source"]["path"] = "ocr/enriched/page_002.txt"
        elif mutation == "empty_coverage":
            page["coverage"] = " "
        elif mutation == "findings":
            page["findings"] = ["unresolved defect"]
        elif mutation == "missing_uncertainties":
            page.pop("uncertainties")
        elif mutation == "duplicate_page":
            evidence["pages"].append(copy.deepcopy(page))
        else:
            page["page"] = True
    rewrite_evidence(audit, mutate)
    assert any("evidence" in e for e in check(audit)["errors"])


def test_evidence_not_json_rejected_even_with_matching_checksum(audit):
    root, manifest, _ = audit
    entry = manifest["pages"][0]
    path = root / entry["evidence"]["path"]
    path.write_bytes(b"REWORK PAGE 1/604")
    entry["evidence"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    assert not check(audit)["ok"]


def test_manifest_reviewer_swap_without_report_change_fails(audit):
    audit[1]["pages"][0]["reviewer_id"] = "new-label-does-not-change-report"
    assert not check(audit)["ok"]


def test_batch_evidence_with_explicit_uncertainty_passes(audit):
    root, manifest, _ = audit
    evidence = {"reviewer_id": "fixture-reviewer", "reviewer_kind": "independent_model", "pages": [
        {"page": entry["page"], "verdict": "approved", "files": copy.deepcopy(entry["files"]),
         "coverage": "Synthetic detailed source and parity coverage",
         "findings": [], "uncertainties": ["Source ambiguity transparently retained"]}
        for entry in manifest["pages"]]}
    path = root / "batch.json"
    path.write_text(json.dumps(evidence), encoding="utf-8")
    spec = {"path": "batch.json", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    for entry in manifest["pages"]:
        entry["evidence"] = copy.deepcopy(spec)
    assert check(audit)["ok"]


@pytest.mark.parametrize("artifact", ["manifest", "evidence", "generated"])
@pytest.mark.parametrize("field,first_value", [
    ("verdict", "rework"), ("reviewer_id", "contradictory-reviewer"),
    ("sha256", "0" * 64), ("page", 999),
])
def test_duplicate_object_keys_fail_even_with_current_checksum(audit, artifact, field, first_value):
    root, manifest, records = audit
    if artifact == "manifest":
        # Inject contradictory values before the original: permissive last-key-wins
        # parsing would retain exactly the original, otherwise-valid manifest.
        raw = json.dumps(manifest)
        path = root / "supplemental.json"
    elif artifact == "evidence":
        path = root / manifest["pages"][0]["evidence"]["path"]
        raw = path.read_text(encoding="utf-8")
    else:
        # Unknown metadata remains allowed, so give it review/hash declarations
        # too: duplicate detection must recurse everywhere, not just known fields.
        records[0]["audit_metadata"] = {"verdict": "approved", "reviewer_id": "fixture-reviewer",
                                        "sha256": "a" * 64}
        raw = json.dumps(records)
        path = root / "web/public/manuscript.json"
    key = json.dumps(field) + ":"
    assert key in raw
    raw = raw.replace(key, key + " " + json.dumps(first_value) + ", " + key, 1)
    path.write_text(raw, encoding="utf-8")
    if artifact == "manifest":
        report = validate_audit(root, path)
    else:
        if artifact == "evidence":
            manifest["pages"][0]["evidence"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            manifest["pages"][0]["generated_record_sha256"] = canonical_record_hash(records[0])
        report = check(audit)
    assert not report["ok"]
    assert any("duplicate JSON object key" in error for error in report["errors"])


@pytest.mark.parametrize("raw", [
    '{"outer":[{"verdict":"rework","verdict":"approved"}]}',
    '{"files":{"source":{"sha256":"old","sha256":"new"}}}',
    '{"page":1,"page":1}',
    '{"reviewer_id":"first","reviewer_\\u0069d":"second"}',
])
def test_strict_loader_rejects_nested_and_escape_equivalent_duplicate_keys(raw):
    with pytest.raises(ValueError, match="duplicate JSON object key"):
        strict_json_loads(raw)


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_strict_loader_rejects_nonstandard_constants(constant):
    with pytest.raises(ValueError, match="nonstandard JSON constant"):
        strict_json_loads('{"nested":[' + constant + ']}')


def test_invalid_json_and_outside_manifest_fail(tmp_path):
    (tmp_path / "broken.json").write_text("{", encoding="utf-8")
    assert not validate_audit(tmp_path, "broken.json")["ok"]
    assert not validate_audit(tmp_path, "../outside.json")["ok"]
    assert not validate_audit(tmp_path, tmp_path.parent / "outside.json")["ok"]
