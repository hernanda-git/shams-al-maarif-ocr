import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from translation_v2_tracker import Tracker, TrackerError, WorkerBusy  # noqa: E402
from translation_v2_worker import build_packet  # noqa: E402


class TranslationV2WorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "manifest.json").write_text(
            json.dumps({"total_pages": 2}), encoding="utf-8"
        )
        for directory in ("enriched", "enriched_en", "enriched_id"):
            (self.root / "ocr" / directory).mkdir(parents=True)
        (self.root / "web" / "public").mkdir(parents=True)
        source = "---\nThere is no text on this page.\n---"
        for number in (1, 2):
            name = f"page_{number:03d}.txt"
            (self.root / "ocr" / "enriched" / name).write_text(source, encoding="utf-8")
            (self.root / "ocr" / "enriched_en" / name).write_text(
                f"Arabic:\n{source}\n\nEnglish:\n[NO VISIBLE TEXT]", encoding="utf-8"
            )
            (self.root / "ocr" / "enriched_id" / name).write_text(
                f"Arabic:\n{source}\n\nIndonesia:\n[TIDAK ADA TEKS TERLIHAT]",
                encoding="utf-8",
            )
        (self.root / "web" / "public" / "manuscript.json").write_text(
            json.dumps(
                [
                    {
                        "page": number,
                        "text": {
                            "ar": source,
                            "en": "[NO VISIBLE TEXT]",
                            "id": "[TIDAK ADA TEKS TERLIHAT]",
                        },
                    }
                    for number in (1, 2)
                ]
            ),
            encoding="utf-8",
        )
        self.tracker = Tracker(self.root)
        self.tracker.initialize()

    def tearDown(self):
        self.tmp.cleanup()

    def test_packet_is_scoped_to_one_claimed_page(self):
        self.tracker.claim_next("worker-a")
        packet = build_packet(self.tracker, 1, "worker-a")
        self.assertEqual(packet["page"], 1)
        self.assertIn("page_001.txt", packet["paths"]["source"])
        self.assertNotIn("page_002.txt", packet["paths"]["source"])
        self.assertTrue(packet["forbidden_actions"])

    def test_packet_rejects_non_owner_and_worker_cannot_skip(self):
        self.tracker.claim_next("worker-a")
        with self.assertRaises(TrackerError):
            build_packet(self.tracker, 1, "worker-b")
        with self.assertRaises(WorkerBusy):
            self.tracker.claim_next("worker-b")


if __name__ == "__main__":
    unittest.main()
