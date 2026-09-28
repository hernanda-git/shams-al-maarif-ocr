# Independent review evidence

Store one Markdown record for each independent review of a physical page.

## Required record

- The first line is exactly `APPROVED PAGE N/604` or `REWORK PAGE N/604`.
- Record reviewer ID/context, SHA-256 hashes for the source and both target files, and the exact reviewed paths.
- State the source inventory covered: geometry, terms/formulae, agents/speakers, source ambiguities, EN↔ID parity, generated-record contract, and target-script hygiene.
- A rework record must cite each defect, source location, current target wording, and the minimal repair. An approval record must confirm the resulting snapshot, not a prior draft.
- Reviewers are read-only: they do not change translation files, tracker state, or commits.

The parent copies verified reports here and commits them only with the tracker checkpoint, never in the page-content commit. A rework requires validation and a fresh independent reviewer after the repair; an old approval never applies to a changed target snapshot.
