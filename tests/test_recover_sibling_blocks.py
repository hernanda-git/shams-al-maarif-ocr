from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from recover_sibling_blocks import (  # noqa: E402
    arabic_ratio,
    blocks_for,
    clean,
    extract_inline,
    fold_ratio,
    is_blank_marker,
    is_blank_source,
    is_translation_like,
    parse_blocks,
    plan_page,
    prose_score,
    strip_artifacts,
    symbol_load,
)

REAL_EN = "— 53 —\n\nMay Allah bless our master Muhammad, his family, and his companions."
REAL_ID = "— ٥٣ —\n\nGroup of four epistles written by the noble scholar."
ARABIC_BODY = "— ٨٩ —\nقليلا بكفك وادهن به وجهك فكل من رآك أحبك وهذه صفة الخاتم"


# --------------------------------------------------------------------------- clean


def test_clean_normalises_newlines_and_strips():
    assert clean("  a\r\nb\r  ") == "a\nb"


def test_clean_handles_none_and_empty():
    assert clean(None) == ""
    assert clean("") == ""


# ------------------------------------------------------------------- strip_artifacts


def test_strip_artifacts_removes_batch_header_line():
    text = "--- PAGE 108 TRANSLATION ---\n\nreal english body here"
    assert strip_artifacts(text) == "real english body here"


def test_strip_artifacts_removes_combined_output_stub():
    text = "[combined output — see batch]\n\nreal english body here"
    assert "combined output" not in strip_artifacts(text)


def test_strip_artifacts_leaves_clean_text_untouched():
    assert strip_artifacts(REAL_EN) == REAL_EN


# --------------------------------------------------------------------- parse_blocks


def test_parse_blocks_reads_own_line_labels():
    text = f"Arabic:\n{ARABIC_BODY}\n\nEnglish:\n{REAL_EN}\n\nIndonesia:\n{REAL_ID}"
    found = [(label, body) for label, body, _ in parse_blocks(text)]
    assert [label for label, _ in found] == ["Arabic", "English", "Indonesia"]
    assert found[1][1] == REAL_EN


def test_parse_blocks_handles_crlf():
    text = f"Arabic:\r\n{ARABIC_BODY}\r\nEnglish:\r\n{REAL_EN}"
    assert extract_inline(text, "English") == REAL_EN


def test_parse_blocks_finds_label_inline_on_a_content_line():
    """p543's real shape: the label trails other text on the same line."""
    text = f"Arabic: {ARABIC_BODY} Indonesia: {REAL_ID}"
    assert extract_inline(text, "Indonesia") == REAL_ID


def test_extract_inline_returns_none_when_label_absent():
    assert extract_inline(f"Arabic:\n{ARABIC_BODY}", "English") is None


def test_blocks_for_returns_every_occurrence():
    text = f"English:\n{REAL_EN}\n\nArabic:\n{ARABIC_BODY}\n\nEnglish:\n{REAL_ID}"
    assert len(blocks_for(text, "English")) == 2


# ------------------------------------------------------------------ arabic_ratio


def test_arabic_ratio_zero_for_latin():
    assert arabic_ratio(REAL_EN) == 0.0


def test_arabic_ratio_high_for_arabic():
    assert arabic_ratio(ARABIC_BODY) > 0.5


# -------------------------------------------------------------- is_translation_like


def test_translation_like_accepts_latin_body():
    assert is_translation_like(REAL_EN)


def test_translation_like_rejects_arabic_body():
    assert not is_translation_like(ARABIC_BODY + " " + ARABIC_BODY)


def test_translation_like_rejects_short_body():
    assert not is_translation_like("(No text visible)")


def test_translation_like_rejects_artifact_only():
    assert not is_translation_like("--- PAGE 96 TRANSLATION ---")


# -------------------------------------------------------------------- plan_page


def test_plan_page_recovers_english_from_id_sibling():
    sibling = f"Arabic:\n{ARABIC_BODY}\n\nEnglish:\n{REAL_EN}\n\nIndonesia:\n{REAL_ID}"
    plan = plan_page(sibling, "English", "enriched_id")
    assert plan["action"] == "recover"
    assert plan["body"] == REAL_EN


def test_plan_page_recovers_while_stripping_the_batch_header():
    sibling = f"Arabic:\n{ARABIC_BODY}\n\nEnglish:\n--- PAGE 108 TRANSLATION ---\n{REAL_EN}"
    plan = plan_page(sibling, "English", "enriched_id")
    assert plan["action"] == "recover"
    assert "TRANSLATION ---" not in plan["body"]
    assert plan["body"] == REAL_EN


def test_plan_page_relabels_unlabelled_indonesian_body():
    """p244/p250/p587/p600 shape: whole file is already the target language."""
    sibling = REAL_ID
    plan = plan_page(sibling, "Indonesia", "enriched_id")
    assert plan["action"] == "relabel"
    assert plan["body"] == REAL_ID


def test_plan_page_recovers_inline_indonesia_label():
    """p543 shape: Indonesian present but the label is not on its own line."""
    sibling = f"Arabic: {ARABIC_BODY} Indonesia: {REAL_ID}"
    plan = plan_page(sibling, "Indonesia", "enriched_id")
    assert plan["action"] == "recover"
    assert plan["body"] == REAL_ID


def test_plan_page_requires_translation_when_sibling_is_arabic():
    sibling = f"Arabic:\n{ARABIC_BODY}\n\nArabic:\n{ARABIC_BODY}"
    plan = plan_page(sibling, "English", "enriched_id")
    assert plan["action"] == "translate"
    assert plan["body"] == ""


def test_plan_page_requires_translation_for_artifact_only_sibling():
    sibling = "Arabic:\n" + ARABIC_BODY + "\n\nEnglish:\n--- PAGE 108 TRANSLATION ---"
    plan = plan_page(sibling, "English", "enriched_id")
    assert plan["action"] == "translate"


def test_plan_page_translate_when_sibling_is_empty():
    assert plan_page("", "English", "enriched_id")["action"] == "translate"


# --------------------------------------------------------------------- fold_ratio


def test_fold_ratio_one_for_plain_ascii():
    assert fold_ratio("plain ascii text") == 1.0


def test_fold_ratio_drops_diacritics():
    assert fold_ratio("قَلِيلًا") < 1.0
