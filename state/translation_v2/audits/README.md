# Supplemental translation audits

These retrospective audits repair translations already in the terminal V2 workflow state `committed`. They do not reset that state, rewrite old reviewer fields, or claim a new sequential worker completion. Page-scoped source/target snapshots and independent-model review evidence establish the current acceptance status.

## Source precedence

1. `ocr/enriched/page_NNN.txt` is the canonical, immutable Arabic OCR.
2. Draft English and Indonesian are checked independently against that Arabic, then against each other for conflicting actors, conditions, negations, lists, numbers, and technical meanings. Agreement between translations cannot justify adding words absent from Arabic.
3. Readable unusual claims remain literal and source-attributed. Corrupt/incomplete wording retains readable fragments and gets a descriptive `[UNCLEAR: ...]` marker in the target language. No remembered canonical quotation replaces a damaged source.
4. Latin transliteration preserves target-table geometry and cell identity without copying Arabic script. Source and embedded Arabic remain unchanged.

## Evidence

Final structured review reports contain a real independently delegated reviewer ID, `reviewer_kind: independent_model`, every covered page, an explicit `approved`/`rework` verdict, exact raw-byte source/EN/ID SHA-256 hashes, a concrete coverage inventory, findings, and source uncertainties. Approval is specific to those hashes. A subsequent edit invalidates it and needs a fresh reviewer. Failed reports are retained.

A supplemental manifest links each page to the final report hash and canonical generated-record hash. `scripts/verify_translation_audit.py --manifest <manifest> --json` checks completeness, current files, report verdicts, reviewer/editor separation, and generated-record consistency. It is not a semantic translation engine and cannot authenticate people or agent identities from caller-written strings. The parent session must establish task/result lineage through actual delegation tools. Independent model review is never labelled human review.

Raw file hashes bind the reviewed working-tree bytes, not newline-normalized Git blobs. The audited OCR files in this Windows checkout use CRLF (`core.autocrlf=true`); a checkout with different newline settings can correctly fail the raw-byte gate even if the words are unchanged. Do not regenerate approval hashes blindly to bypass that failure. Audit JSON/Markdown evidence is pinned to LF by `.gitattributes` so its report hashes survive checkout.

The 2026-11-03 campaign manifest records complete, hash-bound acceptance for pages 1–67 after repair and fresh independent review of every final snapshot.

Historical V2 `committed` counts describe workflow history, not blanket approval of later revisions. Review provenance corrections append to `events.jsonl`; original event lines are not removed or rewritten. See the dated campaign manifest and provenance note for effective snapshot acceptance.
