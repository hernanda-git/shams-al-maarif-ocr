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

# Genuine independent review of the final bytes is required.
# A different ID alone does not establish independence or human approval.
uv run --no-project python scripts/translation_v2_worker.py approve --page 1 --reviewer-id hermes-independent-reviewer --json

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

### Bounded campaign checkpoint — 2026-11-07 (WIB)

Physical pages **68–77** were subsequently translated/aligned, independently model-reviewed and committed in strict sequence. See [the batch checkpoint](audits/2026-11-07-p068-p077-campaign.md) and [hash-bound verification receipt](audits/2026-11-07-p068-p077-campaign.json). Page 76 includes a preserved rework finding and a fresh r2 approval after correcting a divine antecedent.

At that snapshot, the tracker contains **77 committed / 527 pending pages**; the next gate is **page 78, pending and unclaimed**, with no active page or worker lock. All 604 canonical-source hashes and existing titles were preserved, the accepted-page structural/triage sweep passed through page 77, and the full Python suite passed 168 tests plus 49 subtests. This is model-review evidence, not human approval or a claim that the remaining corpus or deployed reader has been verified.

### Rolling continuation checkpoint — 2026-11-07 (WIB)

The user subsequently authorized continued sequential execution. Physical pages **78–87** were aligned, independently model-reviewed and committed one at a time. See [the continuation checkpoint](audits/2026-11-07-p078-p087-campaign.md) and [hash-bound verification receipt](audits/2026-11-07-p078-p087-campaign.json). Page 82 preserves its earlier findings and fresh r3 approval after speaker/recited-voice repairs; page 85 preserves independent r1 rework and fresh r2 approval after lexical and quotation/speaker-uncertainty repairs. Failed reviews were not overwritten or relabeled as approvals.

At this snapshot, **87 pages are committed / 517 pending**; **page 88 is pending and unclaimed**, with no active page or worker lock. All 604 canonical-source hashes, 604 existing titles, out-of-batch generated/tracker records, protected WIP fingerprints and historical event prefixes passed preservation checks. The accepted-page structural/triage sweep passed through page 87; the fresh full Python suite passed **168 tests and 49 subtests in 68.66 seconds**. Content and tracker commit scopes, all final review hashes and the preserved rework artifacts were verified against Git.

This is a periodic recovery/publication checkpoint, not completion of the corpus or a resource stop. Sequential continuation remains authorized while quota supports a complete page and independent review. Read the live tracker before the next claim; the snapshot above is historical once later pages advance. No human approval, deployment or live-reader verification is claimed.

### Recovery and quota-observation checkpoint — 2026-11-07 (WIB)

Pages **88–91** subsequently passed source-to-EN/ID independent model review and the page-scoped content/tracker commit sequence. The [cumulative continuation checkpoint](audits/2026-11-07-p078-p091-campaign.md) and [machine receipt](audits/2026-11-07-p078-p091-campaign.json) verify **14 continuation pages, 78–91**, with **91 committed / 513 pending**. At this snapshot **page 92 is pending and unclaimed**, with no active page or worker lock.

Page 88 was recovered through supported tracker transitions only after confirming that the interrupted worker was no longer live and had not changed its targets. Page 89 required restoring LF wrappers to achieve exact raw-source embedding, followed by fresh full-page independent review; its original structured decision is preserved beside the rendered report. Pages 90–91 retain source contradictions and damaged clauses rather than harmonizing their cosmology or importing familiar quotations.

All 604 canonical hashes and titles, out-of-batch records, historical event prefixes and protected WIP passed preservation checks; final review hashes and both content/tracker commit scopes were checked against Git. The accepted-page sweep passed through page 91. The fresh full suite passed **168 tests and 49 subtests in 86.52 seconds**.

The quota endpoint temporarily returned `fetch-error`, so no zero or invented percentage was inferred. A subsequent cache observation recovered **24% session / 47% weekly**; these are dated snapshot values, not permission to assume future capacity. Approved work was checkpointed before another long item. Continuation requires a current usable quota observation and enough reserve for a complete page, independent review and publication. No model switch, human approval, deployment or live-reader verification is claimed.
