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

### Resource-boundary checkpoint through page 92 — 2026-11-07 (WIB)

One additional complete page was translated and independently reviewed after quota recovery. See [the cumulative pages 78–92 checkpoint](audits/2026-11-07-p078-p092-campaign.md) and [machine receipt](audits/2026-11-07-p078-p092-campaign.json): **15 continuation pages**, **92 committed / 512 pending**, and **page 93 pending and unclaimed**, with no active page or worker lock at the snapshot.

Page 92 preserves the printed compound number-word groups and divisor chain without calculating or correcting them. The first compound group has four thousand-multiplier tokens in the source and each target, verified programmatically. Both short prophetic honorifics, the full closing blessing, and Chapter Twelve's unfinished opening are retained. All source, title, collateral-record, review-history and protected-WIP checks pass; the fresh full suite passed **168 tests and 49 subtests in 92.89 seconds**.

Fresh quota is **13% session / 45% weekly**. The current page is complete and checkpointed without reducing fidelity; further long execution requires a renewed quota observation or an explicit bounded-scope/model decision. No model switch or banked reset was performed. The remaining corpus and deployed reader are not claimed complete or verified.

### Approved pages 93–94; external editorial conflict at 95 — 2026-11-07 (WIB)

Pages **93–94** are independently reviewed and committed. See the [current blocked-state checkpoint](audits/2026-11-07-p093-p094-campaign.md) and [machine receipt](audits/2026-11-07-p093-p094-campaign.json). Page 93 preserves r1 rejection and fresh r2 approval; page 94's unapproved builder feature was removed before acceptance.

The current tracker has **{'blocked': 1, 'committed': 94, 'pending': 509}**; **page 95 is blocked**, with no active page/worker lock and no page-96 claim. Page 95's local text, exact Arabic wrappers and 1,630-glyph round trips pass, but it is not approved or content-committed. Concurrent user-supplied English corrections on pages 40–41 intentionally conflict with the Latin-only convention and lie outside the page-owned gate; further concurrent English changes are recorded in the receipt. They were not modified, committed or normalized by this campaign. The shared generated JSON has mixed uncommitted records **[40, 41, 43, 44, 45, 95]** at observation time and is not staged by this checkpoint.

All canonical hashes and titles remain unchanged. The frozen pre-conflict sweep through 94 is historical; current global acceptance is **BLOCKED**, even though the code suite passes **168 tests / 49 subtests**. Reconcile the documented editorial override and review provenance before unblocking 95; do not bypass the gate or rewrite old approvals. No human-model review substitution, deployment or live-reader verification is claimed.

### Integrated page 95 with parallel editorial fixes — 2026-11-08T00:29:15.291756+07:00

The user authorized same-line per-page integration. Page **95** is independently reviewed and content-committed as `ee399cb1702e8a8cd93abff18c3b45c47f6f30d3`. Parallel user English corrections on physical pages **[40, 41, 43, 44, 45, 46, 50, 51]** were frozen and integrated in `f0a194b18f565bbc62f5ec002a05c12816055444` with their supplied provenance. See the [boundary receipt](integrations/page_095.json), [editorial policy](../../docs/translation-editorial-integration-v2.md), and [page review](reviews/page_095-r1-approved.md). Old reviews remain historical; the hash-bound registry attributes editorial versions without claiming Arabic-source authentication.

Tracker counts: **{'committed': 95, 'pending': 509, 'blocked': 0}**; no active page or worker lock. The frozen accepted view through 95 passes with explicitly recorded English editorial style exceptions. All canonical raw hashes and titles are preserved; the frozen-candidate suite passes **332 tests / 49 subtests**. Newer live corrections are left untouched for the next page. Publication is verified after the checkpoint commit; no deployment or live-reader verification is claimed.

### Integrated page 96 — 2026-11-08T01:25:39.975059+07:00

Physical page **96** has complete independent model review of its exact Arabic/English/Indonesian hashes and is content-committed as `833e1de20db062919e231d26166084ba086d8ebe`. Its opaque invocation poem retains all 30 verses, 31 star markers, ordered letters and repeated tokens, source quantities and negatives, and the unfinished ending. Local source uncertainties are retained rather than reconstructed from a familiar formula. See the [complete review](reviews/page_096-r1-approved.md) and its lossless JSON decision.

The same-line [editorial boundary](integrations/page_096.json) is committed separately as `c87498b3e3719091e3f670552143110384add04f`. Ready new English corrections: **[]**; no new replacement was ready at this snapshot. Previously registered editorial versions and their historical review provenance remain unchanged. Later live changes are reserved for the next boundary.

Tracker: **{'committed': 96, 'pending': 508}**. Next: **page 97, pending and unclaimed**; no active page or worker lock at this checkpoint. All 604 canonical raw hashes and titles, scan references, unselected records, historical event prefixes and protected WIP pass preservation checks. Frozen candidate: **332 tests / 49 subtests passed in 117.52 seconds**. Publication uses guarded ref promotion, isolated candidate commits and explicit index-only refresh. All batch commits contain `[skip ci]` to suppress the push-triggered deployment workflow; deployment, historical PDF generation and live-reader verification are not part of this work. Exact remote readback follows the checkpoint commit.

### Integrated page 97 — 2026-11-08T01:42:22.109105+07:00

Physical page **97** has complete independent model review bound to the actual Arabic/English/Indonesian hashes and is content-committed as `00a5bdef8258c151064b0005f6361f01f23fa79e`. The complete opening verse and four sections retain all clauses, sign sequences, quantities, negatives, conditions and repeated scopes. Opaque forms and source damage remain local uncertainties; medical/occult effects remain source-attributed claims. See the [complete review](reviews/page_097-r1-approved.md) and its original structured JSON decision.

The separate [editorial boundary](integrations/page_097.json) is committed as `4d4a3dc28b61fc07ed6fe0f290b7d4e05a328f16`. Ready new English corrections: **[]**. Previously registered editorial versions and original review provenance remain unchanged. Later live edits remain for the next boundary.

Tracker: **{'committed': 97, 'pending': 507}**. Next: **page 98, pending and unclaimed**, no active page or worker lock at this checkpoint. All 604 canonical raw hashes, titles, scan references, unselected records, historical event prefixes and protected WIP pass preservation checks. Frozen candidate: **332 tests / 49 subtests passed in 138.3 seconds**. Publication uses isolated candidate commits, guarded ref promotion and explicit index-only refresh. Every batch commit carries `[skip ci]` to suppress the push-triggered deployment workflow. No deployment, historical PDF rebuild, or live-reader verification is claimed. Exact remote readback follows this checkpoint commit.
