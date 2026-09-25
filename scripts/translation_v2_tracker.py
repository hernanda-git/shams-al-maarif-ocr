#!/usr/bin/env python3
"""Durable, single-page tracker for the Translation Alignment V2 campaign.

This module intentionally contains no translation-provider code.  The worker/LLM
edits one page, then uses this tracker to pass deterministic gates before the
next page can be claimed.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterator


SCHEMA_VERSION = 1
DEFAULT_TOTAL_PAGES = 604
LOCK_STALE_SECONDS = 30 * 60
STATE_LOCK_STALE_SECONDS = 5 * 60
COMMIT_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")

TERMINAL_STATUS = "committed"
ACTIVE_STATUSES = {"claimed", "in_progress", "review", "rework"}
CLAIMABLE_STATUSES = {"pending", "rework"}


class TrackerError(RuntimeError):
    """Base error for invalid or unsafe tracker operations."""


class WorkerBusy(TrackerError):
    """Another worker (or the same worker) owns the single active page."""


class SequenceBlocked(TrackerError):
    """The next physical page is blocked and must be explicitly resolved."""


class StateCorrupt(TrackerError):
    """Durable tracker state is missing or malformed."""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _normalise_root(root: Path | str | None) -> Path:
    if root is None:
        return Path(__file__).resolve().parents[1]
    return Path(root).expanduser().resolve()


def _pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        return False
    return True


def _age_seconds(timestamp: str | None) -> float:
    if not timestamp:
        return float("inf")
    try:
        parsed = dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return float("inf")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return max(0.0, (dt.datetime.now(dt.timezone.utc) - parsed).total_seconds())


class Tracker:
    """State machine and atomic persistence for one-page translation work."""

    def __init__(self, root: Path | str | None = None, total_pages: int | None = None):
        self.root = _normalise_root(root)
        self.state_dir = self.root / "state" / "translation_v2"
        self.state_path = self.state_dir / "progress.json"
        self.events_path = self.state_dir / "events.jsonl"
        self.worker_lock_path = self.state_dir / "worker.lock"
        self.state_lock_path = self.state_dir / "state.lock"
        self.total_pages = total_pages or self._read_manifest_total() or DEFAULT_TOTAL_PAGES
        if self.total_pages < 1:
            raise TrackerError("total_pages must be positive")

    def _read_manifest_total(self) -> int | None:
        manifest = self.root / "manifest.json"
        if not manifest.exists():
            return None
        try:
            value = json.loads(manifest.read_text(encoding="utf-8")).get("total_pages")
            return int(value) if value is not None else None
        except (OSError, ValueError, TypeError):
            return None

    def _ensure_dirs(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _read_json(self, path: Path) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise StateCorrupt(f"missing tracker file: {path}") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise StateCorrupt(f"cannot read tracker file {path}: {exc}") from exc

    def load_state(self) -> dict[str, Any]:
        state = self._read_json(self.state_path)
        self._validate_state_shape(state)
        return state

    def _validate_state_shape(self, state: dict[str, Any]) -> None:
        if not isinstance(state, dict):
            raise StateCorrupt("tracker state root must be a JSON object")
        if state.get("schema_version") != SCHEMA_VERSION:
            raise StateCorrupt(
                f"unsupported tracker schema: {state.get('schema_version')!r}"
            )
        total = state.get("total_pages")
        pages = state.get("pages")
        if not isinstance(total, int) or total < 1 or not isinstance(pages, dict):
            raise StateCorrupt("tracker state has invalid total_pages/pages")
        expected = {str(page) for page in range(1, total + 1)}
        if set(pages) != expected:
            raise StateCorrupt("tracker page map is not exactly 1..total_pages")
        for page, record in pages.items():
            if not isinstance(record, dict) or record.get("status") not in {
                "pending",
                "claimed",
                "in_progress",
                "review",
                "rework",
                "approved",
                "blocked",
                "committed",
            }:
                raise StateCorrupt(f"invalid record for page {page}")

    @contextlib.contextmanager
    def _state_lock(self, owner: str = "tracker") -> Iterator[None]:
        """Acquire a short-lived atomic lock for state-file updates."""
        self._ensure_dirs()
        for _ in range(2):
            try:
                fd = os.open(
                    self.state_lock_path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o600,
                )
                holder = {
                    "owner": owner,
                    "pid": os.getpid(),
                    "created_at": utc_now(),
                }
                os.write(fd, json.dumps(holder).encode("utf-8"))
                os.close(fd)
                break
            except FileExistsError:
                try:
                    existing = self._read_json(self.state_lock_path)
                    if not isinstance(existing, dict):
                        existing = {}
                except StateCorrupt:
                    existing = {}
                stale = _age_seconds(existing.get("created_at")) > STATE_LOCK_STALE_SECONDS
                if stale and not _pid_alive(existing.get("pid")):
                    self.state_lock_path.unlink(missing_ok=True)
                    continue
                raise WorkerBusy(
                    "tracker state lock is held by "
                    f"{existing.get('owner', 'unknown')} (pid {existing.get('pid', '?')})"
                )
        else:  # pragma: no cover - defensive, the loop either breaks or raises
            raise WorkerBusy("could not acquire tracker state lock")

        try:
            yield
        finally:
            self.state_lock_path.unlink(missing_ok=True)

    def _atomic_write(self, path: Path, value: Any) -> None:
        self._ensure_dirs()
        temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        temp.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        os.replace(temp, path)

    def _write_state(self, state: dict[str, Any]) -> None:
        state["updated_at"] = utc_now()
        self._validate_state_shape(state)
        self._atomic_write(self.state_path, state)

    def _append_event(self, action: str, **payload: Any) -> None:
        self._ensure_dirs()
        event = {"timestamp": utc_now(), "action": action, **payload}
        with self.events_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def events(self) -> list[dict[str, Any]]:
        if not self.events_path.exists():
            return []
        result: list[dict[str, Any]] = []
        for line in self.events_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                result.append(json.loads(line))
        return result

    def _read_worker_lock(self) -> dict[str, Any] | None:
        if not self.worker_lock_path.exists():
            return None
        try:
            lock = self._read_json(self.worker_lock_path)
        except StateCorrupt as exc:
            raise WorkerBusy(f"worker lock is unreadable: {exc}") from exc
        if not isinstance(lock, dict) or not isinstance(lock.get("page"), int) or not lock.get("worker_id"):
            raise WorkerBusy("worker lock is malformed; use reclaim-lock --force")
        return lock

    def _write_worker_lock(self, worker_id: str, page: int) -> dict[str, Any]:
        lock = {
            "worker_id": worker_id,
            "pid": os.getpid(),
            "page": page,
            "started_at": utc_now(),
            "heartbeat_at": utc_now(),
        }
        try:
            fd = os.open(
                self.worker_lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
        except FileExistsError as exc:
            raise WorkerBusy("another page is already locked") from exc
        try:
            os.write(fd, json.dumps(lock).encode("utf-8"))
        finally:
            os.close(fd)
        return lock

    def _require_lock(self, worker_id: str, page: int) -> dict[str, Any]:
        lock = self._read_worker_lock()
        if lock is None:
            raise TrackerError(f"page {page} has no active worker lock")
        if lock["page"] != page or lock["worker_id"] != worker_id:
            raise WorkerBusy(
                f"page {lock['page']} is locked by worker {lock['worker_id']!r}"
            )
        return lock

    def _remove_worker_lock(self, page: int | None = None) -> None:
        lock = self._read_worker_lock()
        if lock is not None and (page is None or lock.get("page") == page):
            self.worker_lock_path.unlink(missing_ok=True)

    def _assert_page(self, state: dict[str, Any], page: int) -> dict[str, Any]:
        if not isinstance(page, int) or not 1 <= page <= state["total_pages"]:
            raise TrackerError(f"page must be between 1 and {state['total_pages']}")
        return state["pages"][str(page)]

    def _expected(self, state: dict[str, Any]) -> tuple[int | None, dict[str, Any] | None]:
        for number in range(1, state["total_pages"] + 1):
            record = state["pages"][str(number)]
            if record["status"] != TERMINAL_STATUS:
                return number, record
        return None, None

    def initialize(self, reset: bool = False) -> dict[str, Any]:
        self._ensure_dirs()
        if self.state_path.exists() and not reset:
            return self.load_state()
        if self.worker_lock_path.exists():
            raise WorkerBusy("cannot initialize while a worker lock exists")
        now = utc_now()
        state = {
            "schema_version": SCHEMA_VERSION,
            "total_pages": self.total_pages,
            "sequence_policy": "strict-lowest-uncommitted",
            "created_at": now,
            "updated_at": now,
            "active_page": None,
            "pages": {
                str(page): {
                    "page": page,
                    "status": "pending",
                    "attempts": 0,
                    "owner": None,
                    "claimed_at": None,
                    "heartbeat_at": None,
                    "review_submitted_at": None,
                    "reviewer": None,
                    "validator": None,
                    "last_error": None,
                    "commit_sha": None,
                    "committed_at": None,
                }
                for page in range(1, self.total_pages + 1)
            },
        }
        with self._state_lock("initialize"):
            self._write_state(state)
            self._append_event(
                "initialize",
                total_pages=self.total_pages,
                reset=reset,
            )
        return state

    def status(self) -> dict[str, Any]:
        state = self.load_state()
        counts: dict[str, int] = {}
        for record in state["pages"].values():
            counts[record["status"]] = counts.get(record["status"], 0) + 1
        next_page, next_record = self._expected(state)
        lock = self._read_worker_lock()
        return {
            "schema_version": state["schema_version"],
            "total_pages": state["total_pages"],
            "counts": counts,
            "completed": counts.get("committed", 0),
            "next_page": next_page,
            "next_status": next_record["status"] if next_record else None,
            "active_page": state.get("active_page"),
            "worker_lock": lock,
            "updated_at": state.get("updated_at"),
        }

    def next_page(self) -> dict[str, Any]:
        state = self.load_state()
        page, record = self._expected(state)
        if page is None:
            return {"done": True, "page": None, "status": "committed"}
        return {
            "done": False,
            "page": page,
            "status": record["status"],
            "attempts": record["attempts"],
            "owner": record["owner"],
            "last_error": record["last_error"],
        }

    def page_record(self, page: int) -> dict[str, Any]:
        """Return a validated page record for read-only worker packet generation."""
        state = self.load_state()
        return self._assert_page(state, page)

    def active_lock(self) -> dict[str, Any] | None:
        """Return the current single-worker lock without changing state."""
        return self._read_worker_lock()

    def claim_next(self, worker_id: str) -> dict[str, Any]:
        if not worker_id or not worker_id.strip():
            raise TrackerError("worker_id is required")
        with self._state_lock(worker_id):
            state = self.load_state()
            existing = self._read_worker_lock()
            if existing is not None:
                raise WorkerBusy(
                    f"page {existing['page']} is already locked by "
                    f"worker {existing['worker_id']!r}"
                )
            page, record = self._expected(state)
            if page is None:
                return {"done": True, "page": None, "status": "committed"}
            status = record["status"]
            if status == "blocked":
                raise SequenceBlocked(
                    f"page {page} is blocked: {record.get('last_error') or 'no reason'}"
                )
            if status == "approved":
                raise TrackerError(
                    f"page {page} is approved but not committed; record its commit first"
                )
            if status not in CLAIMABLE_STATUSES:
                raise TrackerError(
                    f"page {page} is {status!r} without a usable worker claim; "
                    "inspect state before recovery"
                )
            lock = self._write_worker_lock(worker_id, page)
            record["status"] = "claimed"
            record["owner"] = worker_id
            record["attempts"] += 1
            record["claimed_at"] = lock["started_at"]
            record["heartbeat_at"] = lock["heartbeat_at"]
            record["last_error"] = None
            state["active_page"] = page
            self._write_state(state)
            self._append_event(
                "claim",
                page=page,
                worker_id=worker_id,
                attempt=record["attempts"],
            )
            return {
                "done": False,
                "page": page,
                "status": record["status"],
                "worker_id": worker_id,
                "attempt": record["attempts"],
                "source_path": f"ocr/enriched/page_{page:03d}.txt",
                "english_path": f"ocr/enriched_en/page_{page:03d}.txt",
                "indonesian_path": f"ocr/enriched_id/page_{page:03d}.txt",
            }

    def start(self, page: int, worker_id: str) -> dict[str, Any]:
        with self._state_lock(worker_id):
            state = self.load_state()
            record = self._assert_page(state, page)
            self._require_lock(worker_id, page)
            if record["status"] not in {"claimed", "rework"}:
                raise TrackerError(f"page {page} cannot start from {record['status']!r}")
            record["status"] = "in_progress"
            record["heartbeat_at"] = utc_now()
            state["active_page"] = page
            self._write_state(state)
            self._append_event("start", page=page, worker_id=worker_id)
            return {"page": page, "status": record["status"]}

    def heartbeat(self, worker_id: str) -> dict[str, Any]:
        with self._state_lock(worker_id):
            state = self.load_state()
            lock = self._read_worker_lock()
            if lock is None or lock["worker_id"] != worker_id:
                raise WorkerBusy("worker does not own the active page lock")
            page = lock["page"]
            record = self._assert_page(state, page)
            now = utc_now()
            lock["heartbeat_at"] = now
            self._atomic_write(self.worker_lock_path, lock)
            record["heartbeat_at"] = now
            state["active_page"] = page
            self._write_state(state)
            self._append_event("heartbeat", page=page, worker_id=worker_id)
            return {"page": page, "heartbeat_at": now}

    def submit_review(
        self, page: int, worker_id: str, validator_report: dict[str, Any]
    ) -> dict[str, Any]:
        if not validator_report.get("ok"):
            raise TrackerError("cannot submit review with a failed page validator")
        with self._state_lock(worker_id):
            state = self.load_state()
            record = self._assert_page(state, page)
            self._require_lock(worker_id, page)
            if record["status"] != "in_progress":
                raise TrackerError(
                    f"page {page} cannot submit review from {record['status']!r}"
                )
            record["status"] = "review"
            record["validator"] = validator_report
            record["review_submitted_at"] = utc_now()
            record["heartbeat_at"] = utc_now()
            state["active_page"] = page
            self._write_state(state)
            self._append_event(
                "submit_review",
                page=page,
                worker_id=worker_id,
                validator=validator_report,
            )
            return {"page": page, "status": record["status"]}

    def approve(
        self, page: int, reviewer_id: str, allow_self_review: bool = False
    ) -> dict[str, Any]:
        if not reviewer_id or not reviewer_id.strip():
            raise TrackerError("reviewer_id is required")
        with self._state_lock(reviewer_id):
            state = self.load_state()
            record = self._assert_page(state, page)
            lock = self._read_worker_lock()
            if lock is None or lock.get("page") != page:
                raise TrackerError("cannot approve a page without its worker lock")
            if record["status"] != "review":
                raise TrackerError(f"page {page} is not awaiting review")
            if reviewer_id == record.get("owner") and not allow_self_review:
                raise TrackerError(
                    "independent review required; use an explicit self-review override"
                )
            record["status"] = "approved"
            record["reviewer"] = reviewer_id
            state["active_page"] = page
            self._write_state(state)
            self._append_event(
                "approve",
                page=page,
                reviewer_id=reviewer_id,
                self_review=reviewer_id == record.get("owner"),
            )
            return {"page": page, "status": record["status"], "reviewer": reviewer_id}

    def rework(self, page: int, reviewer_id: str, reason: str) -> dict[str, Any]:
        if not reason.strip():
            raise TrackerError("rework reason is required")
        with self._state_lock(reviewer_id):
            state = self.load_state()
            record = self._assert_page(state, page)
            lock = self._read_worker_lock()
            if lock is None or lock.get("page") != page:
                raise TrackerError("cannot rework a page without its worker lock")
            if record["status"] != "review":
                raise TrackerError(f"page {page} is not awaiting review")
            record["status"] = "rework"
            record["reviewer"] = reviewer_id
            record["last_error"] = reason
            state["active_page"] = page
            self._write_state(state)
            self._append_event(
                "rework", page=page, reviewer_id=reviewer_id, reason=reason
            )
            return {"page": page, "status": record["status"], "reason": reason}

    def block(self, page: int, worker_id: str, reason: str) -> dict[str, Any]:
        if not reason.strip():
            raise TrackerError("block reason is required")
        with self._state_lock(worker_id):
            state = self.load_state()
            record = self._assert_page(state, page)
            self._require_lock(worker_id, page)
            if record["status"] not in ACTIVE_STATUSES:
                raise TrackerError(f"page {page} cannot be blocked from {record['status']!r}")
            record["status"] = "blocked"
            record["last_error"] = reason
            state["active_page"] = None
            self._write_state(state)
            self._remove_worker_lock(page)
            self._append_event("block", page=page, worker_id=worker_id, reason=reason)
            return {"page": page, "status": record["status"], "reason": reason}

    def unblock(self, page: int, operator_id: str, note: str = "") -> dict[str, Any]:
        with self._state_lock(operator_id):
            state = self.load_state()
            record = self._assert_page(state, page)
            if self._read_worker_lock() is not None:
                raise WorkerBusy("cannot unblock while a worker lock exists")
            expected, _ = self._expected(state)
            if expected != page:
                raise TrackerError(
                    f"page {page} is not the sequence gate; expected page {expected}"
                )
            if record["status"] != "blocked":
                raise TrackerError(f"page {page} is not blocked")
            record["status"] = "pending"
            record["last_error"] = note or None
            state["active_page"] = None
            self._write_state(state)
            self._append_event("unblock", page=page, operator_id=operator_id, note=note)
            return {"page": page, "status": record["status"]}

    def record_commit(
        self,
        page: int,
        sha: str,
        worker_id: str,
        verify_git: bool = True,
    ) -> dict[str, Any]:
        if not COMMIT_SHA_RE.fullmatch(sha):
            raise TrackerError("commit SHA must be 7-64 hexadecimal characters")
        with self._state_lock(worker_id):
            state = self.load_state()
            record = self._assert_page(state, page)
            self._require_lock(worker_id, page)
            if record["status"] != "approved":
                raise TrackerError(
                    f"page {page} must be approved before recording a commit"
                )
            if verify_git:
                self._verify_page_commit(page, sha)
            record["status"] = "committed"
            record["commit_sha"] = sha
            record["committed_at"] = utc_now()
            state["active_page"] = None
            self._write_state(state)
            self._remove_worker_lock(page)
            self._append_event("record_commit", page=page, worker_id=worker_id, sha=sha)
            return {"page": page, "status": record["status"], "commit_sha": sha}

    def _verify_page_commit(self, page: int, sha: str) -> None:
        check = subprocess.run(
            ["git", "-C", str(self.root), "cat-file", "-e", f"{sha}^{{commit}}"],
            text=True,
            capture_output=True,
        )
        if check.returncode != 0:
            raise TrackerError(f"commit {sha} is not a reachable Git commit")
        show = subprocess.run(
            ["git", "-C", str(self.root), "show", "--format=", "--name-only", sha],
            text=True,
            capture_output=True,
        )
        if show.returncode != 0:
            raise TrackerError(f"cannot inspect commit {sha}: {show.stderr.strip()}")
        changed = {line.strip().replace("\\", "/") for line in show.stdout.splitlines() if line.strip()}
        expected = {
            f"ocr/enriched_en/page_{page:03d}.txt",
            f"ocr/enriched_id/page_{page:03d}.txt",
            "web/public/manuscript.json",
        }
        if not expected.issubset(changed):
            missing = ", ".join(sorted(expected - changed))
            raise TrackerError(f"commit {sha} is missing page evidence: {missing}")
        unexpected = changed - expected
        if unexpected:
            raise TrackerError(
                f"commit {sha} changes files outside the page scope: "
                + ", ".join(sorted(unexpected))
            )

    def reclaim_lock(
        self,
        operator_id: str,
        reason: str,
        force: bool = False,
        stale_after: int = LOCK_STALE_SECONDS,
    ) -> dict[str, Any]:
        if not reason.strip():
            raise TrackerError("reclaim reason is required")
        with self._state_lock(operator_id):
            lock = self._read_worker_lock()
            if lock is None:
                raise TrackerError("no worker lock exists")
            stale = _age_seconds(lock.get("heartbeat_at")) >= stale_after
            if not force and (not stale or _pid_alive(lock.get("pid"))):
                raise TrackerError(
                    "lock is not demonstrably stale; use --force only for an explicit recovery"
                )
            state = self.load_state()
            page = lock["page"]
            record = self._assert_page(state, page)
            record["status"] = "blocked"
            record["last_error"] = f"lock reclaimed by {operator_id}: {reason}"
            state["active_page"] = None
            self._write_state(state)
            self._remove_worker_lock(page)
            self._append_event(
                "reclaim_lock",
                page=page,
                previous_worker=lock["worker_id"],
                operator_id=operator_id,
                reason=reason,
                force=force,
            )
            return {"page": page, "status": record["status"], "reason": reason}


def _json_or_text(value: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, ensure_ascii=False, indent=2))
    elif isinstance(value, (dict, list)):
        print(json.dumps(value, ensure_ascii=False, indent=2))
    else:
        print(value)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="repository root (default: detected root)")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(command: str, **kwargs: Any) -> argparse.ArgumentParser:
        child = sub.add_parser(command, **kwargs)
        child.add_argument("--root", default=argparse.SUPPRESS)
        child.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
        return child

    init = common("init")
    init.add_argument("--reset", action="store_true")
    common("status")
    common("next")
    claim = common("claim", aliases=["claim-next"])
    claim.add_argument("--worker-id", required=True)
    start = common("start")
    start.add_argument("--page", type=int, required=True)
    start.add_argument("--worker-id", required=True)
    heartbeat = common("heartbeat")
    heartbeat.add_argument("--worker-id", required=True)
    submit = common("submit-review")
    submit.add_argument("--page", type=int, required=True)
    submit.add_argument("--worker-id", required=True)
    submit.add_argument("--validator", required=True, help="JSON validator report")
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
    commit.add_argument("--sha", required=True)
    commit.add_argument("--worker-id", required=True)
    commit.add_argument("--skip-git-verify", action="store_true")
    events = common("events")
    events.add_argument("--limit", type=int, default=0)
    reclaim = common("reclaim-lock")
    reclaim.add_argument("--operator-id", required=True)
    reclaim.add_argument("--reason", required=True)
    reclaim.add_argument("--force", action="store_true")
    reclaim.add_argument("--stale-after", type=int, default=LOCK_STALE_SECONDS)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    tracker = Tracker(args.root)
    as_json = bool(getattr(args, "json", False))
    try:
        command = args.command
        if command == "init":
            result = tracker.initialize(reset=args.reset)
        elif command == "status":
            result = tracker.status()
        elif command == "next":
            result = tracker.next_page()
        elif command in {"claim", "claim-next"}:
            result = tracker.claim_next(args.worker_id)
        elif command == "start":
            result = tracker.start(args.page, args.worker_id)
        elif command == "heartbeat":
            result = tracker.heartbeat(args.worker_id)
        elif command == "submit-review":
            try:
                report = json.loads(args.validator)
            except json.JSONDecodeError as exc:
                raise TrackerError(f"--validator must be JSON: {exc}") from exc
            result = tracker.submit_review(args.page, args.worker_id, report)
        elif command == "approve":
            result = tracker.approve(args.page, args.reviewer_id, args.allow_self_review)
        elif command == "rework":
            result = tracker.rework(args.page, args.reviewer_id, args.reason)
        elif command == "block":
            result = tracker.block(args.page, args.worker_id, args.reason)
        elif command == "unblock":
            result = tracker.unblock(args.page, args.operator_id, args.note)
        elif command == "record-commit":
            result = tracker.record_commit(
                args.page,
                args.sha,
                args.worker_id,
                verify_git=not args.skip_git_verify,
            )
        elif command == "events":
            result = tracker.events()
            if args.limit:
                result = result[-args.limit :]
        elif command == "reclaim-lock":
            result = tracker.reclaim_lock(
                args.operator_id,
                args.reason,
                force=args.force,
                stale_after=args.stale_after,
            )
        else:  # pragma: no cover - argparse prevents this
            raise TrackerError(f"unknown command {command}")
        _json_or_text(result, as_json)
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
