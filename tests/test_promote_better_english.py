"""Regression tests for promote_better_english.choose().

The tool's job is to pick the better of two competing English copies for a page.
Its original tie-break was "prefer the longer copy when both contain Arabic
script". That is wrong, and page 57 is the proof:

    worker-aligned copy : 0 Arabic letters, 4722 chars
    stale copy          : 56 Arabic letters, 4445 chars

The stale copy is SHORTER, so the length rule would have replaced a compliant
worker revision with a non-compliant one -- and both copies pass
verify_translation_v2_page.py, so the validator would not have caught it.

These tests pin the compliant-vs-noncompliant preference and pin the refusal
to guess when neither copy is compliant.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from promote_better_english import arabic_letters, choose  # noqa: E402

# A faithful English rendering of the ninety-nine names, as the V2 worker writes
# it: Latin transliteration, no Arabic script, longer because the name list is
# expanded.
COMPLIANT = (
    "— 51 —\n\n"
    "ʿAlīm al-Ṣabūr\n"
    "Jāmiʿ Muʿīd Bāʿith\n"
    "al-Ghafūr al-Ghaffār\n"
    "al-Qahhār\n"
)

# The stale copy: an untranslated Arabic-script run left inline in the English
# block, and SHORTER than COMPLIANT because transliteration compresses it.
STALE = (
    "— 51 —\n\n"
    "عليم الصبور\n"
    "جامع معيد باعث\n"
    "الغفور الغفار\n"
    "القهار\n"
)


def test_arabic_letters_counts_letters_not_digits() -> None:
    # A folio line uses Arabic-Indic digits, which are allowed in a target block.
    assert arabic_letters("— ٥١ —\nsome English text") == 0
    assert arabic_letters("عليم الصبور") > 0


def test_compliant_copy_wins_even_when_shorter() -> None:
    """The core failure: a compliant copy must not lose on length."""
    id_copy, en_copy = STALE, COMPLIANT
    assert len(id_copy) < len(en_copy), "fixture must keep the stale copy shorter"
    winner, reason = choose(id_copy, en_copy)
    assert winner == COMPLIANT
    assert "V2 rule 3" in reason


def test_compliant_id_copy_wins() -> None:
    winner, reason = choose(COMPLIANT, STALE)
    assert winner == COMPLIANT
    assert "V2 rule 3" in reason


def test_both_noncompliant_keeps_en_copy_for_review() -> None:
    """When neither copy is compliant, do not guess -- keep and report.

    Both fixtures need a real Arabic-script run, otherwise the compliant-vs-
    noncompliant branch fires first and the review branch is never reached.
    """
    a = "— 51 —\n\nعليه الصبور\nجامع\n"  # Arabic script
    b = "— 51 —\n\nBāʿith ʿAlīm\nالجامع\n"  # Latin but still carries an Arabic run
    assert arabic_letters(a) > 0 and arabic_letters(b) > 0
    winner, reason = choose(a, b)
    assert winner == b, "must keep the EN file's own copy when neither is clean"
    assert "for review" in reason


def test_both_compliant_keeps_en_copy() -> None:
    a = "— 51 —\n\nʿAlīm al-Ṣabūr\nshort\n"
    b = "— 51 —\n\nʿAlīm al-Ṣabūr\nand a much longer compliant body here\n"
    winner, reason = choose(a, b)
    assert winner == b
    assert "both compliant" in reason


def test_length_alone_never_decides() -> None:
    """No input pair may be decided by character count."""
    pairs = [
        (STALE, COMPLIANT),
        (COMPLIANT, STALE),
        ("— 51 —\n\nx", "— 51 —\n\n" + "y" * 500),
        ("— 51 —\n\n" + "z" * 500, "— 51 —\n\nx"),
    ]
    for id_copy, en_copy in pairs:
        _, reason = choose(id_copy, en_copy)
        assert "longer" not in reason, f"length-based decision leaked: {reason}"
