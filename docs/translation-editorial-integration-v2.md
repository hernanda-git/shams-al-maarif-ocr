# Parallel editorial corrections in the V2 translation line

## User authority and scope

The user authorized a single integrated line: parallel English fixes are merged and included whenever the coordinator completes a new physical page. This supplements the original translation contract; it does not permit changing canonical Arabic or rewriting prior review history.

- Translators own the currently claimed page's normal Arabic-to-English/Indonesian work.
- Under the active integrated workflow, parallel correction workers edit only supplied English replacements and their provenance under `docs/english-corrections/`. They must defer rebuilding the live shared `web/public/manuscript.json` to the coordinator, not merely defer staging or committing it, to avoid a reader-file write race.
- The coordinator alone snapshots, rebuilds the frozen candidate, validates, commits and publishes each completed-page batch. Correction workers should not stage or commit the shared reader JSON or campaign tracker.
- English replacements remain **user editorial overrides**, not independently authenticated translations or religious quotations. Preserve their supplied wording, Arabic examples, diacritics, headings, overlap and intentional differences literally.

## Completion boundary

At each page boundary, the coordinator freezes the current page plus ready parallel English/provenance changes. Files are read into an immutable candidate; a second read detects changes during capture. A changing file is deferred to the next boundary, never overwritten or guessed complete. Later edits stay in the live working tree for the next page.

Use a candidate built from the current Git HEAD, not the live mixed generated JSON. Materialize canonical sources from their verified immutable raw-byte inventory: archive/checkout line-ending conversion is not proof of byte identity, and historical working sources contain mixed LF/CRLF conventions. Check Git-source content separately with CRLF-only normalization, without rewriting the live canonical files. Overlay only frozen English fixes, preserving Arabic, Indonesian, titles, scan references, record order and every other field. Produce a separate editorial integration commit in the same completed-page batch, followed by the ordinary page-scoped content commit and tracker/review commit. This preserves the tracker's narrow page-commit verifier without omitting the user's fixes.

The final candidate reader payload is also checked against the original title-preserving rebuild on that frozen corpus. Do not add flags to the existing rebuild wrapper, replace canonical sources, or stage a live reader file that contains newer, unreviewed work.

## Hash-bound exceptions and provenance

`state/translation_v2/editorial_overrides.json` records each accepted editorial English version: page, boundary, canonical raw hash, previous and replacement English content hashes, preserved Arabic-prefix identity, authorization and provenance hashes. Working-byte and Git-normalized hashes are separate; only CRLF-to-LF normalization is permitted for historical English files. No source word or Unicode content is normalized away.

The exception applies only while the current English version and canonical source match that registered snapshot. Callers MUST check `entry['page'] == registry_key == current_page` before using `registered_override_matches` to waive triage findings: the helper validates the entry's page range, not its association with the currently processed page. Retained Arabic examples and explicitly supplied English terminology may be recorded as authorized style exceptions. Indonesian, missing or malformed blocks, source-prefix mutations, missing text and wrong-page defects are never exempt. Raw triage diagnostics are retained alongside the classified exceptions, not silently deleted or reported as absent.

A prior independent model review remains evidence for its original bytes. The registry supersedes that English version editorially without pretending the old reviewer approved the user's replacement. New model-generated page translations still require complete independent source-to-target review, exact Arabic-byte embedding and the usual structural, script, quantity and fidelity gates.

## Publication and live work

Use an isolated Git index and frozen candidate bytes. Verify exact staged paths and blob hashes, whitespace, secrets, persistent documentation links and the content of every commit. Include only the snapshot accepted for this page; preserve newer live edits and every unrelated staged entry. Refresh index entries only for published paths, never reset or stash the user's working files.

After the page's content commit, use the supported approval/record-commit transitions to release its worker lock. Publish the complete batch and read back the exact remote ref. Before claiming the next page, verify its predecessor's terminal record and all immutable source hashes. A snapshot or correction commit alone is not completion of the new page.

If a file changes after capture, retain the frozen published version in Git and leave the newer live bytes dirty for the next boundary. If a source, current-page target or tracker changes unexpectedly, stop that conflicting operation and preserve both observations rather than overwriting either side.
