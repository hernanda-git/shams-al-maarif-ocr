import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from translation_v2_tracker import (  # noqa: E402
    SequenceBlocked,
    Tracker,
    TrackerError,
    WorkerBusy,
)


class TranslationV2TrackerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "manifest.json").write_text(
            json.dumps({"total_pages": 3}), encoding="utf-8"
        )
        self.tracker = Tracker(self.root)
        self.tracker.initialize()

    def tearDown(self):
        self.tmp.cleanup()

    def test_initializes_exact_page_sequence_and_status(self):
        state = self.tracker.load_state()
        self.assertEqual(state["total_pages"], 3)
        self.assertEqual(list(state["pages"]), ["1", "2", "3"])
        self.assertEqual(self.tracker.status()["counts"], {"pending": 3})

    def test_single_worker_lock_and_no_second_page_claim(self):
        claim = self.tracker.claim_next("worker-a")
        self.assertEqual(claim["page"], 1)
        self.tracker.start(1, "worker-a")

        with self.assertRaises(WorkerBusy):
            self.tracker.claim_next("worker-b")
        with self.assertRaises(WorkerBusy):
            self.tracker.claim_next("worker-a")

        self.tracker.heartbeat("worker-a")
        self.assertEqual(self.tracker.load_state()["pages"]["1"]["status"], "in_progress")

    def test_sequence_requires_review_approval_and_commit_before_next_page(self):
        self.tracker.claim_next("worker-a")
        self.tracker.start(1, "worker-a")
        self.tracker.submit_review(1, "worker-a", validator_report={"ok": True})

        with self.assertRaises(WorkerBusy):
            self.tracker.claim_next("worker-b")

        with self.assertRaises(TrackerError):
            self.tracker.approve(1, "worker-a")
        self.tracker.approve(1, "reviewer-b")

        with self.assertRaises(WorkerBusy):
            self.tracker.claim_next("worker-b")

        self.tracker.record_commit(1, "a" * 40, "worker-a", verify_git=False)
        claim = self.tracker.claim_next("worker-b")
        self.assertEqual(claim["page"], 2)

    def test_blocked_page_is_a_sequence_gate_until_explicitly_unblocked(self):
        self.tracker.claim_next("worker-a")
        self.tracker.start(1, "worker-a")
        self.tracker.block(1, "worker-a", "source needs human classification")

        with self.assertRaises(SequenceBlocked):
            self.tracker.claim_next("worker-b")

        self.tracker.unblock(1, "operator")
        claim = self.tracker.claim_next("worker-b")
        self.assertEqual(claim["page"], 1)

    def test_self_review_requires_explicit_override_and_events_survive_reload(self):
        self.tracker.claim_next("worker-a")
        self.tracker.start(1, "worker-a")
        self.tracker.submit_review(1, "worker-a", validator_report={"ok": True})
        with self.assertRaises(TrackerError):
            self.tracker.approve(1, "worker-a")
        self.tracker.approve(1, "worker-a", allow_self_review=True)
        self.tracker.record_commit(1, "b" * 40, "worker-a", verify_git=False)

        reloaded = Tracker(self.root)
        self.assertEqual(reloaded.load_state()["pages"]["1"]["status"], "committed")
        events = reloaded.events()
        self.assertGreaterEqual(len(events), 6)
        self.assertEqual(events[-1]["action"], "record_commit")

    def test_only_approved_page_can_record_commit(self):
        self.tracker.claim_next("worker-a")
        with self.assertRaises(TrackerError):
            self.tracker.record_commit(1, "c" * 40, "worker-a", verify_git=False)

    def test_reachable_git_commit_must_contain_exact_page_evidence(self):
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Translation Test"], cwd=self.root, check=True)
        expected = [
            self.root / "ocr" / "enriched_id" / "page_001.txt",
            self.root / "web" / "public" / "manuscript.json",
        ]
        for path in expected:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("page evidence", encoding="utf-8")
        subprocess.run(["git", "add", *(str(path.relative_to(self.root)) for path in expected)], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "page-1"], cwd=self.root, check=True)
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.root, check=True, text=True, capture_output=True
        ).stdout.strip()

        self.tracker.claim_next("worker-a")
        self.tracker.start(1, "worker-a")
        self.tracker.submit_review(1, "worker-a", {"ok": True})
        self.tracker.approve(1, "reviewer-b")
        result = self.tracker.record_commit(1, sha, "worker-a")
        self.assertEqual(result["status"], "committed")


if __name__ == "__main__":
    unittest.main()
