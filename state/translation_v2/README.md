# Translation V2 worker state

This directory belongs to the page-by-page Translation Alignment V2 campaign. It is separate from the historical OCR/translation state files under `state/progress.json` and `ocr/.translate_state*.json`.

Durable files:

- `progress.json` — one record for each physical page 1–604.
- `events.jsonl` — append-only state-transition audit log.
- `reviews/` — page-scoped independent-review evidence, committed with the tracker checkpoint.
- `audits/` — supplemental snapshot-bound retrospective audits and transparent provenance corrections. Terminal workflow records are historical; a changed translation requires fresh review evidence.

Transient files (ignored by Git):

- `worker.lock` — one active page/worker lock for the whole repository.
- `state.lock` — short-lived atomic write lock.

## Non-negotiable sequence

A worker may claim only the lowest page that is not `committed`. It may never claim a later page while the current page is `blocked`, `review`, `approved`, or otherwise unresolved.

```text
pending -> claimed -> in_progress -> review -> approved -> committed
                                      \-> rework -> in_progress
claimed|in_progress|review|rework -> blocked -> pending
```

`blocked -> pending` requires an explicit operator unblock. `committed` is terminal. A page is not complete because a file exists or because an old translation state file says `completed`; it is complete only after the deterministic validator, an independent review, and a recorded Git commit SHA.

## Commands

From the repository root:

```text
uv run --no-project python scripts/translation_v2_worker.py init
uv run --no-project python scripts/translation_v2_worker.py status --json
uv run --no-project python scripts/translation_v2_worker.py next --json

# Claim exactly one page. The command refuses a second claim.
uv run --no-project python scripts/translation_v2_worker.py claim-next --worker-id hermes-page-worker --json
uv run --no-project python scripts/translation_v2_worker.py start --page 1 --worker-id hermes-page-worker
uv run --no-project python scripts/translation_v2_worker.py packet --page 1 --worker-id hermes-page-worker --json
uv run --no-project python scripts/translation_v2_worker.py heartbeat --worker-id hermes-page-worker

# After editing only the claimed EN/ID files and rebuilding manuscript.json:
uv run --no-project python scripts/translation_v2_worker.py validate --page 1 --json
uv run --no-project python scripts/translation_v2_worker.py submit-review --page 1 --worker-id hermes-page-worker --json

# A different reviewer ID is required by default.
uv run --no-project python scripts/translation_v2_worker.py approve --page 1 --reviewer-id human-reviewer --json

# Persist the reviewer report under reviews/page_NNN-rN-<verdict>.md.
# The report starts with APPROVED PAGE N/TOTAL or REWORK PAGE N/TOTAL,
# carries source/target hashes, and is staged only with the tracker checkpoint.
# After REWORK, repair, validate, and send a fresh reviewer; an old verdict
# does not apply to changed files.

# Record the exact page-scoped commit only after approval.
uv run --no-project python scripts/translation_v2_worker.py record-commit --page 1 --worker-id hermes-page-worker --sha <exact-commit-sha> --json
```

If a page already passes the V2 validator and needs no content edit, do not change wording merely to create a diff. After independent approval, create and commit a verification receipt instead:

```text
uv run --no-project python scripts/translation_v2_worker.py prepare-verification --page 5 --worker-id hermes-page-worker --json
git add state/translation_v2/receipts/page_005.json
git commit -m "verify: translation v2 page 005"
uv run --no-project python scripts/translation_v2_worker.py record-commit --page 5 --worker-id hermes-page-worker --sha <receipt-commit-sha> --verification-only --json
```

The verification receipt hashes the canonical source, both target files, and generated JSON. It is accepted only when the receipt commit contains exactly that page receipt and the validator/reviewer evidence is positive.


The worker packet is the LLM boundary. It contains the page number, exact source and target paths, current drafts, acceptance rules, and forbidden actions. The worker must not use the legacy three-page batch translators for this campaign.

## Recovery

If a worker exits cleanly, it should block the page with a reason or finish the review/commit sequence. If a process dies while holding the lock, inspect the PID and heartbeat first. Only an operator may reclaim the lock, and reclamation blocks the page so that it cannot be silently skipped:

```text
uv run --no-project python scripts/translation_v2_worker.py reclaim-lock \
  --operator-id operator --reason "worker process confirmed dead" --json
uv run --no-project python scripts/translation_v2_worker.py unblock \
  --page 1 --operator-id operator --note "recovery reviewed" --json
```

Use `--force` only when the process/lock cannot be proven stale and the reason is recorded. Do not delete `progress.json`, `events.jsonl`, or a lock by hand during a live run.

## Current baseline

The tracker initializes 604 pending pages. The generated reader dataset now contains physical pages 1–604; the old 600-page limitation no longer applies. Existing translations remain drafts until deterministic validation and genuine independent review of the exact snapshot.

The 2026-11-03 retrospective audit covers pages 1–67. See `audits/2026-11-03-p001-p067-provenance.md`: earlier `human-reviewer` approvals for pages 64–67 did not come from a human or an independent reviewer and are invalid as acceptance evidence. The original events and terminal workflow records are preserved, with append-only corrections. Fresh supplemental review evidence, not a historical reviewer label or `committed` count, establishes acceptance of repaired files. Page 68 is outside this audit and must not be advanced as part of it.
