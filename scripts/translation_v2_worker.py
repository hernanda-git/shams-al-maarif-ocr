#!/usr/bin/env python3
"""Page-scoped worker boundary for Translation Alignment V2.

This command is deliberately provider-neutral.  It gives an LLM a single page
packet, records the state transitions, and makes it impossible to advance to a
later page without validation, review, and a page-scoped commit.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from translation_v2_tracker import Tracker, TrackerError
from verify_translation_v2_page import validate_page


FORBIDDEN_ACTIONS = [
    "Do not read, edit, translate, or regenerate a neighboring page.",
    "Do not call the legacy batch translation commands for this task.",
    "Do not alter the Arabic source file.",
    "Do not mark a page complete without rebuilding manuscript.json and running the page validator.",
    "Do not claim the next page while this page is unresolved.",
]


def _read_optional(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def build_packet(tracker: Tracker, page: int, worker_id: str) -> dict[str, Any]:
    record = tracker.page_record(page)
    lock = tracker.active_lock()
    if lock is None or lock.get("page") != page or lock.get("worker_id") != worker_id:
        raise TrackerError(f"worker {worker_id!r} does not own page {page}")
    if record["status"] not in {"claimed", "in_progress", "rework"}:
        raise TrackerError(
            f"page {page} cannot produce a work packet from {record['status']!r}"
        )

    page_name = f"page_{page:03d}.txt"
    paths = {
        "source": tracker.root / "ocr" / "enriched" / page_name,
        "english": tracker.root / "ocr" / "enriched_en" / page_name,
        "indonesian": tracker.root / "ocr" / "enriched_id" / page_name,
        "generated_json": tracker.root / "web" / "public" / "manuscript.json",
    }
    return {
        "worker_id": worker_id,
        "page": page,
        "attempt": record["attempts"],
        "status": record["status"],
        "lock": lock,
        "paths": {key: path.as_posix() for key, path in paths.items()},
        "source_arabic": _read_optional(paths["source"]),
        "current_english_draft": _read_optional(paths["english"]),
        "current_indonesian_draft": _read_optional(paths["indonesian"]),
        "acceptance_rules": [
            "Copy the canonical Arabic source exactly into the Arabic block of both target files.",
            "Use exactly one English block in the English file and exactly one Indonesia block in the Indonesian file.",
            "Preserve uncertainty with an explicit marker; never invent missing text.",
            "Use [NO VISIBLE TEXT] and [TIDAK ADA TEKS TERLIHAT] only when the canonical source is an explicit no-visible-text page.",
            "Rebuild manuscript.json and make its page record equal the target blocks.",
            "Run verify_translation_v2_page.py for this page before review.",
        ],
        "forbidden_actions": FORBIDDEN_ACTIONS,
        "next_transition": "submit-review after the deterministic page validator passes",
    }


def _emit(value: Any, as_json: bool) -> None:
    if as_json or isinstance(value, (dict, list)):
        print(json.dumps(value, ensure_ascii=False, indent=2))
    else:
        print(value)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None)
    parser.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(name: str, **kwargs: Any) -> argparse.ArgumentParser:
        child = sub.add_parser(name, **kwargs)
        child.add_argument("--root", default=argparse.SUPPRESS)
        child.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
        return child

    init = common("init")
    init.add_argument("--reset", action="store_true")
    common("status")
    common("next")
    claim = common("claim-next")
    claim.add_argument("--worker-id", required=True)
    start = common("start")
    start.add_argument("--page", type=int, required=True)
    start.add_argument("--worker-id", required=True)
    heartbeat = common("heartbeat")
    heartbeat.add_argument("--worker-id", required=True)
    packet = common("packet")
    packet.add_argument("--page", type=int, required=True)
    packet.add_argument("--worker-id", required=True)
    validate = common("validate")
    validate.add_argument("--page", type=int, required=True)
    submit = common("submit-review")
    submit.add_argument("--page", type=int, required=True)
    submit.add_argument("--worker-id", required=True)
    approve = common("approve")
    approve.add_argument("--page", type=int, required=True)
    approve.add_argument("--reviewer-id", required=True)
    approve.add_argument("--allow-self-review", action="store_true")
    rework = common("rework")
    rework.add_argument("--page", type=int, required=True)
    rework.add_argument("--reviewer-id", required=True)
    rework.add_argument("--reason", required=True)
    block = common("block")
    block.add_argument("--page", type=int, required=True)
    block.add_argument("--worker-id", required=True)
    block.add_argument("--reason", required=True)
    unblock = common("unblock")
    unblock.add_argument("--page", type=int, required=True)
    unblock.add_argument("--operator-id", required=True)
    unblock.add_argument("--note", default="")
    commit = common("record-commit")
    commit.add_argument("--page", type=int, required=True)
    commit.add_argument("--worker-id", required=True)
    commit.add_argument("--sha", required=True)
    reclaim = common("reclaim-lock")
    reclaim.add_argument("--operator-id", required=True)
    reclaim.add_argument("--reason", required=True)
    reclaim.add_argument("--force", action="store_true")
    events = common("events")
    events.add_argument("--limit", type=int, default=0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    tracker = Tracker(args.root)
    as_json = bool(getattr(args, "json", False))
    try:
        command = args.command
        if command == "init":
            tracker.initialize(reset=args.reset)
            result = tracker.status()
        elif command == "status":
            result = tracker.status()
        elif command == "next":
            result = tracker.next_page()
        elif command == "claim-next":
            result = tracker.claim_next(args.worker_id)
        elif command == "start":
            result = tracker.start(args.page, args.worker_id)
        elif command == "heartbeat":
            result = tracker.heartbeat(args.worker_id)
        elif command == "packet":
            result = build_packet(tracker, args.page, args.worker_id)
        elif command == "validate":
            result = validate_page(tracker.root, args.page)
        elif command == "submit-review":
            report = validate_page(tracker.root, args.page)
            result = tracker.submit_review(args.page, args.worker_id, report)
            result["validator"] = report
        elif command == "approve":
            result = tracker.approve(args.page, args.reviewer_id, args.allow_self_review)
        elif command == "rework":
            result = tracker.rework(args.page, args.reviewer_id, args.reason)
        elif command == "block":
            result = tracker.block(args.page, args.worker_id, args.reason)
        elif command == "unblock":
            result = tracker.unblock(args.page, args.operator_id, args.note)
        elif command == "record-commit":
            report = validate_page(tracker.root, args.page)
            if not report["ok"]:
                raise TrackerError(
                    "page validator failed; refusing to record commit: "
                    + "; ".join(report["errors"])
                )
            result = tracker.record_commit(args.page, args.sha, args.worker_id)
            result["validator"] = report
        elif command == "reclaim-lock":
            result = tracker.reclaim_lock(
                args.operator_id, args.reason, force=args.force
            )
        elif command == "events":
            result = tracker.events()
            if args.limit:
                result = result[-args.limit :]
        else:  # pragma: no cover - argparse prevents this
            raise TrackerError(f"unknown command {command}")
        _emit(result, as_json)
        if command == "validate" and isinstance(result, dict) and not result.get("ok"):
            return 1
        return 0
    except (TrackerError, OSError, ValueError) as exc:
        error = {"ok": False, "error": str(exc)}
        if as_json:
            print(json.dumps(error, ensure_ascii=False, indent=2))
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
