"""Focused regressions for source-grounded V2 triage, not semantic validation."""

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import page_triage as triage


class ArabicContaminationTests(unittest.TestCase):
    def test_terms_have_no_whitelist_or_minimum_length(self):
        terms = "ذكره ذكرها ذكرهم ذكر الله تعالى صلى عليه وسلم قسم صدق ب في من".split()
        self.assertEqual(triage.arabic_prose_runs(" ".join(terms)), terms)

    def test_grid_cells_and_digits(self):
        self.assertEqual(triage.arabic_prose_runs("| ا | ب |\n| ١ | ۲ |"), ["ا", "ب", "١", "۲"])

    def test_presentation_forms_and_extended_arabic(self):
        for char in ("ﷲ", "ﻻ", "ﷺ", "ݐ", "ࢠ", "ࡰ", "\U00010E60", "\U00010EC2", "\U0001EE00", "َ", "،"):
            with self.subTest(char=char):
                self.assertEqual(triage.arabic_prose_runs(char), [char])

    def test_latin_transliteration_punctuation_and_math_allowed(self):
        self.assertEqual(triage.arabic_prose_runs("mīm, nūn; Ta'ala — ‘word’ × ÷ + = ∑ 123 | [x]"), [])


class HonorificPhraseTests(unittest.TestCase):
    def test_actual_phrase_with_whitespace_diacritics_and_presentation_forms(self):
        for source in ("الله تعالى", "اللَّهُ\n	تَعَالَى", "(ﷲ تعالى)", "الله تعالى", "اللـه تعالى"):
            with self.subTest(source=source):
                self.assertTrue(triage.needs_honorific(source))

    def test_common_attached_clitics_preserve_adjacent_phrase(self):
        for source in ("بالله تعالى", "والله تعالى", "فالله تعالى", "لله تعالى",
                       "ولله تعالى", "فلله تعالى", "وبالله تعالى", "فبالله تعالى",
                       "كالله تعالى", "وَبِاللَّهِ\nتَعَالَى"):
            with self.subTest(source=source):
                self.assertTrue(triage.needs_honorific(source))

    def test_clitics_do_not_allow_disconnected_or_arbitrary_prefixes(self):
        for source in ("بالله ثم تعالى", "والله قال ثم تعالى", "لله الحمد ثم تعالى",
                       "عبدالله تعالى", "شيءالله تعالى", "xالله تعالى", "بالله تعالىشيء"):
            with self.subTest(source=source):
                self.assertFalse(triage.needs_honorific(source))

    def test_disconnected_words_do_not_trigger(self):
        for source in ("الله يعلم ثم تعالى", "تعالى ثم الله", "الله، تعالى", "الله", "تعالى", "الله تعالي", "الله تعالىشيء"):
            with self.subTest(source=source):
                self.assertFalse(triage.needs_honorific(source))


class PageTriageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.root_patch = patch.object(triage, "REPO_ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.en = "This is a sufficiently long English translation of the canonical source."
        self.id = "Ini terjemahan Indonesia yang cukup panjang untuk sumber kanonis."

    def write_page(self, source="نص المصدر الحقيقي", en=None, id_body=None):
        bodies = {"enriched": source,
                  "enriched_en": f"Arabic:\n{source}\n\nEnglish:\n{self.en if en is None else en}",
                  "enriched_id": f"Arabic:\n{source}\n\nIndonesia:\n{self.id if id_body is None else id_body}"}
        for folder, text in bodies.items():
            path = self.root / "ocr" / folder / "page_001.txt"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def test_source_arabic_does_not_contaminate_target(self):
        self.write_page()
        self.assertEqual(triage.triage(1), [])

    def test_short_target_still_detects_contamination(self):
        self.write_page(en="ب", id_body="ﷲ")
        problems = triage.triage(1)
        self.assertTrue(any(p.startswith("en: UNTRANSLATED") for p in problems))
        self.assertTrue(any(p.startswith("id: UNTRANSLATED") for p in problems))
        self.assertTrue(any("EMPTY" in p for p in problems))

    def test_grid_targets_detected_in_both_languages(self):
        self.write_page(en=self.en + "\n| ا | ب |", id_body=self.id + "\n| ج | د |")
        self.assertEqual(sum("UNTRANSLATED" in p for p in triage.triage(1)), 2)

    def test_disconnected_honorific_not_required(self):
        self.write_page(source="قال الله في موضع آخر ثم تعالى")
        self.assertEqual(triage.triage(1), [])

    def test_actual_honorific_required_and_mandated_rendering_passes(self):
        self.write_page(source="قال اللَّهُ\nتَعَالَى")
        self.assertIn("en: honorific not the mandated 'God Most High'", triage.triage(1))
        self.write_page(source="قال الله تعالى", en=self.en + " God Most High")
        self.assertEqual(triage.triage(1), [])

    def test_indonesian_ascii_and_curly_apostrophes(self):
        for word in ("Ta'ala", "Ta‘ala", "Ta’ala", "ta'ala"):
            with self.subTest(word=word):
                self.write_page(id_body=self.id + " Allah " + word)
                self.assertIn("id: honorific not the mandated 'Yang Mahatinggi'", triage.triage(1))

    def test_blank_marker_cannot_hide_real_source(self):
        for source in ("نص حقيقي", "هذه الصفحة فارغة ولا تحتوي على أي نص.\nولكن هنا نص حقيقي"):
            with self.subTest(source=source):
                self.write_page(source=source, en="[NO VISIBLE TEXT]", id_body="[TIDAK ADA TEKS TERLIHAT]")
                self.assertEqual(sum("nonblank canonical source" in p for p in triage.triage(1)), 2)

    def test_precisely_supported_blank_sources(self):
        sources = ["---\nThere is no text on this page.\n---", *triage.DESCRIPTIVE_NO_TEXT_SOURCES]
        self.assertEqual(len(sources), 3)
        for source in sources:
            with self.subTest(source=source):
                self.write_page(source=source, en="[NO VISIBLE TEXT]", id_body="[TIDAK ADA TEKS TERLIHAT]")
                self.assertEqual(triage.triage(1), [])

    def test_wrong_language_blank_marker_rejected(self):
        self.write_page(source="---\nThere is no text on this page.\n---", en="[TIDAK ADA TEKS TERLIHAT]", id_body="[NO VISIBLE TEXT]")
        self.assertEqual(sum("incorrect no-text marker" in p for p in triage.triage(1)), 2)

    def test_folio_findings_preserved(self):
        self.write_page(source="— ٤٨ —\nنص", en="— 45 —\n" + self.en, id_body="— 47 —\n" + self.id)
        problems = triage.triage(1)
        self.assertTrue(any("WRONG PAGE source 48 target 45" in p for p in problems))
        self.assertTrue(any("off-by-one (normal realignment)" in p for p in problems))

    def test_cli_explicit_pages_preserves_zero_exit_and_summary(self):
        self.write_page(en=self.en + " ذكره")
        output = io.StringIO()
        with patch.object(sys, "argv", ["page_triage.py", "1"]), contextlib.redirect_stdout(output):
            self.assertEqual(triage.main(), 0)
        self.assertIn("p001  1 issue(s)", output.getvalue())
        self.assertIn("1/1 pages need work", output.getvalue())

    def test_cli_queue_without_tracker(self):
        self.write_page()
        output = io.StringIO()
        with patch.object(sys, "argv", ["page_triage.py", "--queue", "1"]), contextlib.redirect_stdout(output):
            self.assertEqual(triage.main(), 0)
        self.assertIn("p001  clean", output.getvalue())
        self.assertIn("0/1 pages need work", output.getvalue())


if __name__ == "__main__":
    unittest.main()
