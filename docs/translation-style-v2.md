# Translation Style — V2 (`docs/translation-style-v2.md`)

Locked for the Translation Alignment V2 campaign. This file records the conventions that the
already-accepted pages 1–53 actually follow, so pages 54–604 stay consistent with them. When a
rule here conflicts with the Arabic source, the Arabic wins and the divergence is reported in
the review record.

## 1. File contract (validator-enforced)

`ocr/enriched_en/page_NNN.txt`

```text
Arabic:
<verbatim copy of ocr/enriched/page_NNN.txt>

English:
<revised English block>
```

`ocr/enriched_id/page_NNN.txt`

```text
Arabic:
<verbatim copy of ocr/enriched/page_NNN.txt>

Indonesia:
<revised Indonesian block>
```

Exactly one `Arabic` and one target label per file. **Never** put an `English:` block inside the
ID file, and never duplicate the Arabic block. The generated `web/public/manuscript.json` record
for page `N` must equal these blocks exactly.

## 2. The Arabic block is immutable

Copy `ocr/enriched/page_NNN.txt` into both target files byte-for-byte (newline normalization and
outer trim only). An OCR defect found during translation is reported, never silently fixed here.

The physical page number is the scan index in the filename. A printed folio number inside the
page (`— ٤٨ —`) is content: translate/keep it as content, never use it to renumber the file.

## 3. No Arabic script in a target block

Target blocks are Latin script. Retained Arabic terms are Latin transliteration only. An earlier
plan proposed the paired form `al-Akbar (الأكبر)`; the accepted pages do **not** use it, so the
campaign uses transliteration alone. Do not reintroduce parentheses with Arabic script.

If the source term itself is a Qur'anic or invocation fragment that must stay protected, keep it
only if it is already inside the canonical Arabic block — a target block still gets a full
translation, never the Arabic original appended.

## 4. Glossary — established renderings

Honorifics and fixed phrases (counts are occurrences across accepted pages 1–53):

| Arabic | English | Bahasa Indonesia |
| --- | --- | --- |
| الله تعالى | God Most High | Allah Yang Mahatinggi |
| صلى الله عليه وسلم | the Prophet, peace and blessings be upon him | Nabi, semoga selawat dan salam tercurah kepadanya |
| اسم الله الأعظم | the Greatest Name of God | Nama Allah Yang Paling Agung |
| اسم العزيز الرحمن | the Name of the Mighty, the Merciful | nama Yang Maha Mulia lagi Maha Pengasih |
| الصلاة | the prayer | shalat |
| القبلة | the qiblah | kiblat |
| التقوى | God-fearers / God-consciousness | bertakwa |
| رقابة / الحجاب | barāʾāt (written slips) | barāʾāt (lembaran bertulis) |
| الجن | jinn | jin |
| وفق | wafq | wafq |
| سورة | Sūrat X | Surah X |
| الفاتحة | al-Fātiḥah | al-Fātiḥah |
| كرامة | karamah | karamah |
| رحمة | raḥmah | raḥmat |

`peace and blessings be upon him` and its Indonesian counterpart are interchangeable in the EN
layer (`may God bless him and grant him peace` also appears); pick the one that reads best and
keep it stable for the rest of that page. Do not alternate mid-page.

Scientific/technical terms keep full diacritics: `Sūrat al-Dukhān`, `Tanzīl al-Sajdah`,
`Tabāraka al-Mulk`, `barāʾāt`, `ṭarṭūr`, `wafq`, `mīm`, `nūn`, `wāw`.

## 5. Meaning is the top priority

The order when requirements compete:

1. completeness and correct meaning against the Arabic;
2. structural fidelity (headings, lists, numbers, conditions, repetitions, diagrams);
3. terminology/transliteration consistency;
4. readable modern English/Indonesian.

"Readable" never means abridged. Do not drop a qualifier, a repetition, a named entity, a
number, or a condition. Operational, occult, medical, and devotional instructions are translated
as **source-attributed claims**, not as the agent's advice: keep the imperative mood, do not
endorse efficacy.

## 6. Antecedents: name the subject, never guess a pronoun

When Arabic introduces a new speaker or elides the subject, an English `he` or an Indonesian
`Beliau` silently binds to the previously named person — God speaking to His Prophet becomes
"the Prophet said to His Prophet". Name the subject explicitly in both targets whenever the
Arabic subject is elided or newly introduced. Auditors must check this on any page carrying two
quotations in a row.

## 7. Uncertainty markers

- `[UNCLEAR]` alone when the source text is simply unreadable.
- `[UNCLEAR: short description]` when you can describe the gap, in the target language.
- The ID marker's description is written in Indonesian.

Never guess a garbled condition, never normalize an OCR reading to a remembered canonical text,
and never add a familiar clause that the source lacks. 170 accepted markers use the
`[UNCLEAR: ...]` form; one legacy bare `[UNCLEAR]` exists — do not add more of those.

A page whose canonical source is the explicit no-text form gets the exact marker
`[NO VISIBLE TEXT]` (EN) / `[TIDAK ADA TEKS TERLIHAT]` (ID) and nothing else. Never invent prose
for a blank or folio page.

## 8. Structure and visuals

Preserve, in source order: headings and chapter titles in parentheses, paragraph boundaries,
numbered instructions, sequences, repetitions, exceptions, invocations, quotations, protected
formulas, and grid/diagram geometry.

For a magic square, table, concentric-ring diagram, or a page that only says
`[جدول يحتوي على أرقام وحروف عربية]`, translate the marker itself and keep the layout markers
(`*`, aligned rows, blank lines). Describe the geometry as structure, never as an interpretation,
and never replace a diagram with prose. A page whose table contents are genuinely absent from the
OCR gets a plain translation of the marker only — do not append a clause about the OCR state.

## 9. Opening folio line

The leading folio marker is content and is kept as its own line: `— 48 —` / `— 45 —` / `- 47 -`,
preserving the dash style the source uses. It is not a page header to be dropped.

## 10. Per-page procedure (the gate)

1. `claim-next` → `start` → `packet`.
2. Read the Arabic source, then draft EN and ID **independently from the Arabic**. Existing
   drafts are comparison material, never evidence that a sentence exists.
3. Write only the two target files. Rebuild the JSON with
   `uv run --no-project python web/scripts/rebuild_manuscript_json.py` (it preserves the 600
   page titles; running the raw builder drops them).
4. `heartbeat` → `validate` → sweep all accepted pages → focused unit tests.
5. Independent read-only review of that page only, with an explicit content-coverage checklist.
   The structural validator is not semantic: quotes, named-entity lists, causal claims, and
   scope-bearing words (pronouns, possessives, number, negation, actor) need a human/model audit.
6. On FAIL, apply the corrections, re-validate, and dispatch a **fresh** reviewer.
7. On PASS: `submit-review` → `approve` → accepted content commit → `record-commit` → tracker
   checkpoint commit → push → `git ls-remote` verification.
8. After any `patch` edit, scan the touched target block for foreign-script contamination
   (CJK, control characters, mojibake) before validating. The validator does not catch it.

One physical page at a time. Never claim page N+1 before page N is `committed`.
