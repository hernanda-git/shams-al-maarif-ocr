# Shams al-Ma'arif Translation V2 Worker + Progress Tracker Plan

> For Hermes: execute one physical page at a time. Never parallelize page edits, never claim the next page before the current page is committed, and never treat a generated status file as proof that translation QA passed.

Goal: build a repository-local, crash-resumable worker and tracker that force the Translation Alignment V2 campaign through one page at a time with an auditable state machine, an atomic single-worker lock, page-local validation, independent review, and commit evidence.

Architecture: `scripts/translation_v2_tracker.py` owns the durable 604-page state machine and append-only event log. `scripts/translation_v2_worker.py` is the page-scoped worker interface: it claims one page, emits a self-contained LLM task packet, records heartbeat/review/block/commit transitions, and refuses to advance while the current page is unresolved. `scripts/verify_translation_v2_page.py` is a deterministic page gate that checks the immutable Arabic source, canonical EN/ID block format, fallback/blank handling, and generated JSON parity.

The worker does not call an LLM in the first implementation. It provides the safe claim/prompt/validate/review/commit boundary so Hermes or another approved LLM can do the language work without batching pages or silently skipping state. Any future provider adapter must call this worker for exactly one claimed page and must not own the tracker state directly.

## Current baseline

- Canonical physical scope: 604 pages from `manifest.json`.
- Existing web bundle: 600 pages; Phase 0 must reconcile this before final V2 publication.
- Arabic source: `ocr/enriched/page_NNN.txt`; immutable during translation work.
- Target layers: `ocr/enriched_en/page_NNN.txt` and `ocr/enriched_id/page_NNN.txt`.
- Generated output: `web/public/manuscript.json`.
- Existing OCR `state/progress.json` is not a translation QA tracker and must remain separate.
- Existing `ocr/translate_en.py` and `ocr/translate_id.py` batch three pages and are not the V2 worker; do not route V2 through their batch path.

## State machine

Each page begins as `pending` and may move only through these transitions:

`pending -> claimed -> in_progress -> review -> approved -> committed`

`review -> rework -> in_progress`

`claimed|in_progress|review|rework -> blocked`

`blocked -> pending` only through an explicit unblock command. `committed` is terminal. The tracker must refuse a page N+1 claim while page N is not `committed`, including when N is blocked or merely approved but not recorded with a commit SHA.

Only one page may be active across the repository. A worker lock contains worker ID, PID, page, start time, and heartbeat time. Lock creation is atomic. A fresh lock blocks all other workers; stale-lock recovery requires an explicit command and recorded reason.

## Implementation tasks

### Task 1: Add failing tracker tests

Create `tests/test_translation_v2_tracker.py` using only Python standard library `unittest` and temporary directories. Cover:

- initialization creates exactly pages 1..604 (use a small injected total in tests);
- first claim is the lowest pending page;
- a second worker cannot claim while the first lock is fresh;
- the same worker cannot claim a second page;
- page N+1 cannot be claimed while page N is review, approved, or blocked;
- reviewer approval requires a reviewer ID different from the worker unless an explicit self-review override is supplied;
- only an approved page can record a commit;
- unblock returns a blocked page to the sequence;
- JSON state and append-only events survive reload.

Run the focused test before implementation and confirm it fails for the expected missing-module reason.

### Task 2: Implement the durable tracker

Create `scripts/translation_v2_tracker.py`.

Requirements:

- standard library only;
- repository-root discovery from `__file__`, with optional `--root` for tests;
- state under `state/translation_v2/progress.json`;
- append-only events under `state/translation_v2/events.jsonl`;
- transient worker lock under `state/translation_v2/worker.lock`;
- separate atomic state-write lock under `state/translation_v2/state.lock`;
- atomic JSON writes via temporary file + `os.replace`;
- UTC ISO-8601 timestamps;
- worker identity from CLI, never guessed from a mutable display name;
- strict transition validation and explicit error messages;
- `init`, `status`, `next`, `claim`, `start`, `heartbeat`, `submit-review`, `approve`, `rework`, `block`, `unblock`, `record-commit`, `events`, and `reclaim-lock` commands;
- machine-readable `--json` output for LLM callers;
- no batch-size argument for claim: one claim is exactly one page;
- tracker must never edit OCR or translation content.

The state must include schema version, total pages, sequence policy, current active page, per-page attempts, owner, timestamps, last error, reviewer, validator result, and commit SHA.

### Task 3: Add failing page-gate tests

Create `tests/test_verify_translation_v2_page.py` with fixtures for:

- a valid page whose Arabic block is copied exactly and whose EN/ID blocks match generated JSON;
- missing `Indonesia:` block;
- duplicate labels;
- altered embedded Arabic;
- a generic fallback marker on a content page;
- JSON drift;
- explicit no-visible-text page using the agreed V2 markers.

Run the focused test and confirm it fails before implementation.

### Task 4: Implement the deterministic page validator

Create `scripts/verify_translation_v2_page.py`.

The validator must:

- accept one physical page only;
- parse labels line-by-line (never a regex whose `\\s*` can consume across lines);
- require exactly one `Arabic` and one `English` block in the EN file;
- require exactly one `Arabic` and one `Indonesia` block in the ID file;
- reject duplicated EN inside ID;
- compare embedded Arabic with the canonical `ocr/enriched/page_NNN.txt` after only newline normalization and outer whitespace trimming;
- reject the exact generator fallback strings on content pages;
- recognize only explicit canonical blank markers as valid for an allowlisted no-visible-text source;
- compare EN/ID block bodies with the generated `web/public/manuscript.json` record;
- report every failed check as structured JSON and exit non-zero on failure;
- never modify files.

Canonical V2 blank markers:

- English: `[NO VISIBLE TEXT]`
- Indonesian: `[TIDAK ADA TEKS TERLIHAT]`

The validator must report a missing generated record for pages 601–604 until the 604-page web contract is separately fixed; it must not silently downgrade that failure.

### Task 5: Add the page-scoped worker interface

Create `scripts/translation_v2_worker.py`.

The worker must:

- call the tracker for every state transition;
- claim only the next sequence page;
- emit a page packet containing page number, exact source/target paths, Arabic source, current EN/ID drafts, acceptance rules, and forbidden actions;
- write no translation itself;
- provide heartbeat and explicit block/rework paths;
- run the page validator before `submit-review`;
- require a distinct reviewer for `approve` by default;
- require a real reachable Git commit SHA when recording `committed`;
- verify that the commit contains only the page EN/ID files plus generated JSON for a page commit;
- rerun the page validator before recording the commit;
- refuse to advance after a failed validator, a missing reviewer, a missing commit SHA, or an active lock owned by another worker.

Example workflow:

```text
uv run --no-project python scripts/translation_v2_worker.py init
uv run --no-project python scripts/translation_v2_worker.py claim-next --worker-id hermes-page-worker
uv run --no-project python scripts/translation_v2_worker.py packet --page 1 --worker-id hermes-page-worker
# LLM edits only page_001 EN/ID files, then rebuilds JSON.
uv run --no-project python scripts/translation_v2_worker.py submit-review --page 1 --worker-id hermes-page-worker
# Independent reviewer checks page 1 and calls approve or rework.
uv run --no-project python scripts/translation_v2_worker.py record-commit --page 1 --sha <exact-sha> --worker-id hermes-page-worker
```

### Task 6: Add operator documentation and initial tracker

Create `state/translation_v2/README.md` with the state machine, lock policy, command examples, recovery procedure, and explicit warning that existing translation files are drafts.

Initialize and commit `state/translation_v2/progress.json` with 604 pending pages and no active worker. Do not commit the transient lock or state-lock files. Update `.gitignore` for `state/translation_v2/worker.lock`, `state/translation_v2/state.lock`, and temporary state files while keeping the durable progress and events policy explicit.

### Task 7: Verify the vertical slice

Run:

```text
uv run --no-project python -m unittest discover -s tests -p 'test_translation_v2*.py' -v
uv run --no-project python scripts/translation_v2_tracker.py status --json
uv run --no-project python scripts/translation_v2_worker.py next --json
uv run --no-project python scripts/verify_translation_v2_page.py 1 --json
```

The tracker test must pass and return page 1 as the next page. The page validator is expected to fail on the current uncorrected page 1 until V2 translation content and generated JSON satisfy the new contract; this is an honest baseline failure, not a reason to weaken the gate.

Then run the existing web production build to ensure the new Python tooling does not affect the reader:

```text
cd web
npm run build
```

Finally inspect `git diff --check`, the explicit file list, secret-scan additions, and the tracker state. Do not run a translation API call, deploy, or create a recurring cron job in this implementation slice.

## Definition of done

- A durable plan exists.
- A 604-page tracker exists and is initialized.
- One and only one worker can claim one page at a time.
- The next page cannot be skipped.
- A page cannot become committed without page validation, independent approval, and a reachable commit SHA.
- The worker emits an LLM-ready page-scoped packet and refuses batch operation.
- State transitions and recovery actions are auditable in JSONL events.
- Tests prove the lock, sequence, transition, and validator behavior.
- Current translation defects remain visible as failures; no data is silently marked complete.
