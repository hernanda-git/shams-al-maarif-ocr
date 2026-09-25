import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from verify_translation_v2_page import validate_page  # noqa: E402


class TranslationV2PageValidatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "ocr" / "enriched").mkdir(parents=True)
        (self.root / "ocr" / "enriched_en").mkdir(parents=True)
        (self.root / "ocr" / "enriched_id").mkdir(parents=True)
        (self.root / "web" / "public").mkdir(parents=True)
        self.source = "Arabic source line one.\nArabic source line two."
        self.en = "English translation line one.\nEnglish translation line two."
        self.id = "Baris terjemahan Indonesia satu.\nBaris terjemahan Indonesia dua."
        self._write_valid()

    def tearDown(self):
        self.tmp.cleanup()

    def _write_valid(self):
        (self.root / "ocr" / "enriched" / "page_001.txt").write_text(
            self.source, encoding="utf-8"
        )
        (self.root / "ocr" / "enriched_en" / "page_001.txt").write_text(
            f"Arabic:\n{self.source}\n\nEnglish:\n{self.en}", encoding="utf-8"
        )
        (self.root / "ocr" / "enriched_id" / "page_001.txt").write_text(
            f"Arabic:\n{self.source}\n\nIndonesia:\n{self.id}", encoding="utf-8"
        )
        (self.root / "web" / "public" / "manuscript.json").write_text(
            json.dumps(
                [
                    {
                        "page": 1,
                        "text": {"ar": self.source, "en": self.en, "id": self.id},
                    }
                ]
            ),
            encoding="utf-8",
        )

    def test_valid_page_passes(self):
        report = validate_page(self.root, 1)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["errors"], [])

    def test_missing_indonesia_block_fails(self):
        (self.root / "ocr" / "enriched_id" / "page_001.txt").write_text(
            f"Arabic:\n{self.source}\n\nEnglish:\n{self.en}", encoding="utf-8"
        )
        report = validate_page(self.root, 1)
        self.assertFalse(report["ok"])
        self.assertTrue(any("Indonesia" in error for error in report["errors"]))

    def test_duplicate_label_fails(self):
        (self.root / "ocr" / "enriched_id" / "page_001.txt").write_text(
            f"Arabic:\n{self.source}\n\nIndonesia:\n{self.id}\n\nIndonesia:\ncopy",
            encoding="utf-8",
        )
        report = validate_page(self.root, 1)
        self.assertFalse(report["ok"])
        self.assertTrue(any("duplicate" in error.lower() for error in report["errors"]))

    def test_embedded_arabic_mismatch_fails(self):
        (self.root / "ocr" / "enriched_en" / "page_001.txt").write_text(
            "Arabic:\nchanged source\n\nEnglish:\n" + self.en, encoding="utf-8"
        )
        report = validate_page(self.root, 1)
        self.assertFalse(report["ok"])
        self.assertTrue(any("Arabic" in error for error in report["errors"]))

    def test_fallback_on_content_page_fails(self):
        (self.root / "ocr" / "enriched_id" / "page_001.txt").write_text(
            f"Arabic:\n{self.source}\n\nIndonesia:\n(tidak ada teks pada halaman ini)",
            encoding="utf-8",
        )
        report = validate_page(self.root, 1)
        self.assertFalse(report["ok"])
        self.assertTrue(any("fallback" in error.lower() for error in report["errors"]))

    def test_generated_json_drift_fails(self):
        data = json.loads((self.root / "web" / "public" / "manuscript.json").read_text())
        data[0]["text"]["id"] = "stale generated text"
        (self.root / "web" / "public" / "manuscript.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        report = validate_page(self.root, 1)
        self.assertFalse(report["ok"])
        self.assertTrue(any("JSON" in error for error in report["errors"]))

    def test_explicit_no_visible_text_marker_is_valid(self):
        source = "---\nThere is no text on this page.\n---"
        (self.root / "ocr" / "enriched" / "page_001.txt").write_text(
            source, encoding="utf-8"
        )
        (self.root / "ocr" / "enriched_en" / "page_001.txt").write_text(
            f"Arabic:\n{source}\n\nEnglish:\n[NO VISIBLE TEXT]", encoding="utf-8"
        )
        (self.root / "ocr" / "enriched_id" / "page_001.txt").write_text(
            f"Arabic:\n{source}\n\nIndonesia:\n[TIDAK ADA TEKS TERLIHAT]",
            encoding="utf-8",
        )
        (self.root / "web" / "public" / "manuscript.json").write_text(
            json.dumps(
                [
                    {
                        "page": 1,
                        "text": {
                            "ar": source,
                            "en": "[NO VISIBLE TEXT]",
                            "id": "[TIDAK ADA TEKS TERLIHAT]",
                        },
                    }
                ]
            ),
            encoding="utf-8",
        )
        report = validate_page(self.root, 1)
        self.assertTrue(report["ok"], report)


if __name__ == "__main__":
    unittest.main()
