"""Regression tests for the three near-miss defect classes found in the wild.

Each of these pages was a near-miss that a naive script check would get WRONG in
the dangerous direction -- silently overwriting a correct file with art or with
an unrelated sibling's text. They are pinned here so the repair tool can never
regress to that behaviour.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from recover_sibling_blocks import (  # noqa: E402
    is_blank_marker,
    is_blank_source,
    is_translation_like,
    plan_page,
    prose_score,
    symbol_load,
)

# p095's ID file: 16 KB of the Old Italic magic-square glyph. Zero Arabic, so a
# script-only check would call it "Indonesian" and overwrite the file with it.
P095_ID_ART = "\n".join(["— ٨٩ —", "قليلا بكفك وادهن به وجهك " + "\U00010348 " * 200])

# p001's ID file holds the exact V2 no-text marker for a blank page.
P001_ID_BLANK = "[TIDAK ADA TEKS TERLIHAT]"
P001_EN_BLANK = "[NO VISIBLE TEXT]"

# p604's EN body. The V2 contract accepts only the bracketed marker form for a
# blank source, so this legacy prose form is a defect, not a valid body.
P604_EN_LEGACY = "(No text visible)"


def test_pure_glyph_art_is_not_a_translation():
    assert not is_translation_like(P095_ID_ART, "id")
    assert prose_score(P095_ID_ART) == 0
    assert symbol_load(P095_ID_ART) > 0.5


def test_p095_id_sibling_is_never_relabelled():
    plan = plan_page(P095_ID_ART, "Indonesia", "enriched_id", "id")
    assert plan["action"] == "translate"
    assert plan["body"] == ""


def test_p001_blank_marker_counts_as_a_valid_body():
    assert is_translation_like(P001_EN_BLANK, "en")
    assert is_translation_like(P001_ID_BLANK, "id")


def test_p001_blank_source_is_detected():
    assert is_blank_source("---\nThere is no text on this page.\n---")
    assert not is_blank_source(REAL := "— 53 —\n\nactual arabic content here")


def test_blank_marker_recognition_is_language_scoped():
    assert is_blank_marker(P001_EN_BLANK, "en")
    assert not is_blank_marker(P001_EN_BLANK, "id")


def test_p604_legacy_marker_is_a_defect_not_a_valid_body():
    """Only the bracketed marker satisfies the V2 blank-source contract."""
    assert not is_translation_like(P604_EN_LEGACY, "en")
    assert is_translation_like(P001_EN_BLANK, "en")


def test_grid_table_translation_still_passes():
    """p198/p393 are real translations that contain markdown tables."""
    body = (
        "— 192 —\n\n| 15 | 8 | 21 | 8 |\n| 20 | 9 | 14 | 19 |\n"
        "| 10 | 6 | 13 | 13 |\n\nThe letters are arranged in the square as follows."
    )
    assert is_translation_like(body, "en")


def test_short_marker_for_a_blank_page_is_not_prose():
    assert not is_translation_like("(no English text on this page)", "en")


# --------------------------------------------------------------- wrong-language
# p603's EN file contains the Indonesian no-text text. A shape-only check calls
# it a valid body; the language probe is what catches the misfiling.
P603_WRONG_LANG = "---\nTidak ada teks pada halaman ini.\n---\nTidak ada teks pada halaman ini."


def test_indonesian_body_is_refused_as_english():
    assert not is_translation_like(P603_WRONG_LANG, "en")
    assert plan_page(P603_WRONG_LANG, "English", "enriched_id", "en")["action"] == "translate"


def test_english_body_is_refused_as_indonesian():
    body = "This document is a blank page and does not contain any Arabic text."
    assert not is_translation_like(body, "id")
    assert plan_page(body, "Indonesia", "enriched_en", "id")["action"] == "translate"


def test_correct_language_still_accepted():
    assert is_translation_like(
        "This document is a blank page and does not contain any Arabic text.", "en"
    )
    assert is_translation_like(
        "Dokumen ini merupakan halaman kosong dan tidak berisi teks Arab.", "id"
    )


def test_language_probe_tolerates_proper_noun_pages():
    """p2 is an accepted page that is mostly a library stamp with no function words."""
    body = "RBSC Islamic\nBF 1410\nB8\n1927\n\nMcGill\nUniversity\nLibraries\nIslamic Studies Library\n\n3537621"
    assert is_translation_like(body, "en")
    assert is_translation_like(body.replace("University", "Universitas"), "id")
