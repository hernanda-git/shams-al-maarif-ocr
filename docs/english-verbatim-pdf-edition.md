# Verbatim Illustrated English PDF Edition — Session Record & Continuation Runbook

## 1. Current Edition Snapshot (Pages 1–121)

- **Date:** 2026-11-10
- **Included Sessions:**
  - Initial V2 alignment baseline (`local-43c73d83…`, Pages **1–92**).
  - User parallel English editorial overrides (`local-40c6d39d…`, integrated on Scan Pages **40–41, 43–46, 50–51**).
  - Continuation alignment campaigns (`local-43c73d83…` Pages **93–95**, `local-242dac73…` Pages **96–102**, `hermes-v2-p103…`–`p121…` Pages **103–121**, checkpoint `a0c1de7`).
- **Completed Scope:** Physical Scan Pages **1–121** of 604 (**Printed Cairo Folios 1–115**).
- **Artifacts:**
  - `scripts/build_english_verbatim_pdf.py` — deterministic two-pass Chromium + PyMuPDF book compiler with 300-DPI manuscript diagram extraction and strict token-level verbatim verification.
  - `manuscript/Shams-al-Maarif-English-Verbatim-Pages-001-121.pdf` — `216` A4 pages (`37.71 MB`), superseding the `001-102` milestone (`179` pages) and the `001-092` milestone (`152` pages).

### Verification Metrics (`p001–p121`)

| Check | Result |
| --- | --- |
| Canonical English source parity (`ocr/enriched_en/page_001.txt`–`page_121.txt`) | **PASS** — `102,142 / 102,142` verbatim tokens (`0` diffs against `web/public/manuscript.json` and canonical block files) |
| Preserved 300-DPI manuscript figures & plates | **53 figures** across 43 scan pages (all visually audited against normalized coordinate grids) |
| Two-pass pagination convergence | **PASS** — `190 / 190` section, thematic-part (`I–XIII`), scan-page (`1–121`), and figure (`1–53`) anchors resolved on Pass 2 |
| Navigation & PDF structure | `187` clickable internal TOC / Figure-Index links; `191` hierarchical PDF sidebar bookmarks; running headers & footers (`Page X of 216`) |
| Canonical corpus & tracker safety | Zero modifications to `ocr/enriched*`, `web/public/manuscript.json`, or `state/translation_v2/*` (Page 122 was in rework and deliberately excluded) |
---

## 2. Pipeline Architecture & Non-Obvious Invariants

### 2.1 300-DPI MRC Foreground Ink Mask in `web/public/scans/page-NNN.pdf`
Each single-page scan PDF in `web/public/scans/` is a Mixed Raster Content (MRC) document:
- Background/color layers (`Im001`, `Im002`) are `710 × 1105` (`~100 DPI` DCTDecode).
- Foreground calligraphy and diagram line-art live in an `ImageMask` (`CCITTFaxDecode`) at **`2129 × 3313` (`300 DPI`)**.
- **Invariant:** Always rasterize via `doc[0].get_pixmap(dpi=300)` in PyMuPDF so the lossless `300 DPI` CCITT mask composites onto the archival paper layer. Never extract raw `get_images()` XObjects directly.

### 2.2 Strict Verbatim Fidelity + Readable Book Typography
- **Canonical Parser:** `scripts/build_english_verbatim_pdf.py` imports `parse_blocks` from `scripts/recover_sibling_blocks.py` (the same parser used by `web/scripts/build_manuscript_json.py`).
- **Zero-Omission Rule:** Every token of the `English:` block is preserved in exact reading order, including:
  - Printed folio headers (`— 2 —`, `- 8 -`, `5`, `15`, `-- 18 --`), styled as centered folio rubrics.
  - Blank-leaf notices (`[NO VISIBLE TEXT]` on Scan Pages 1, 3, 5).
  - Inline editorial uncertainty notes (`[UNCLEAR: ...]`, `[Translator's note: ...]`, `[U+XXXX]`), kept verbatim inline in muted italic/micro philological spans so continuous prose remains effortless to read (including the 1,630 `[U+10348]` OCR placeholder tokens on Scan Page 95).
  - Poetic hemistich lines (` * ` caesura, e.g. *al-Qaṣīdah al-Jaljalūtiyyah* on Scan Pages 96–97), rendered line-by-line with hanging poetic indentation while retaining every token verbatim.
  - Inline Arabic-script letter demonstrations in user editorial overrides (Scan Pages 40, 44, 45), isolated in RTL Arabic calligraphy spans.
  - Parenthetical Arabic-style rubrics (`(Chapter ...)`, `(Section)`, `(Benefit)`, `(Attention)`, `(And know)`), highlighted in dark crimson-sepia bold and split onto clean paragraph starts.
- **Pipe Tables (`awfāq` / `jadāwil`):**
  - `split_raw_blocks(en_text, page_num)` separates leading folio lines even when not followed by a blank line, splits blank-line paragraphs, and splits inline transitions between prose and pipe rows.
  - Markdown pipe syntax (`|` and `:---` separator rows) renders as bordered HTML `<table class="ms-table">` cells while `verify_html_verbatim()` verifies 100% token equality across all cell values and prose tokens.
  - `[Letter-string: ... | ...]` on Scan Page 56 is explicitly excluded from pipe-table parsing so its literal `|` separators remain intact.

### 2.3 Preserved Figures Inventory (`Scan Pages 1–102`, 47 Figures)

Plain-text `.txt` files omit spatial geometry, circular rings, corner archangel labels, seals, and inline constellation dot-patterns. All 47 figures in `FIGURES` (`scripts/build_english_verbatim_pdf.py`) are cropped at 300 DPI with normalized `(x0, y0, x1, y1)` coordinates:

| Fig # | Scan Page (Folio) | `fig_id` | Visual Element Preserved |
| --- | --- | --- | --- |
| 1–5 | pp. 2, 4, 6, 7, 8 | `fig_p002`–`fig_p008` | McGill RBSC bookplate/stamps, Samuelian label, ruled poetic leaf, Part One calligraphic title page, Basmalah headpiece |
| 6 | p. 12 (Fol. 6) | `fig_p012` | Inline Leo talismanic symbol strip (lines 8–10) |
| 7 | p. 14 (Fol. 8) | `fig_p014` | Concentric cosmic & Divine-Name circle (*dāʾirah*) with central square & cardinal corners |
| 8–9 | pp. 15–16 (Fol. 9–10) | `fig_p015`, `fig_p016` | Twin 4×4 numerical/letter *awfāq* and framed invocation square |
| 10 | p. 17 (Fol. 11) | `fig_p017` | Inline talismanic symbols of *Alif* omitted in plain text |
| 11–12 | pp. 18–19 (Fol. 12–13) | `fig_p018`, `fig_p019` | Three-chambered *Alif* talismanic panel; Abū Jaʿfar al-Barmakī's circular *wafq* |
| 13–14 | pp. 21, 23 (Fol. 15, 17) | `fig_p021`, `fig_p023b` | 8×8 mansion/zodiac letter grid; 4×4 zodiac elemental triplicities table |
| 15–16 | pp. 24–25 (Fol. 18–19) | `fig_p024`, `fig_p025a` | Concentric wheel of concealed letter-angels; grand 28-mansion astronomical wheel |
| 17–23 | pp. 25–31 (Fol. 19–25) | `fig_p025b`–`fig_p031` | Manuscript plates preserving inline star-dot asterisms for all 28 Lunar Mansions, constellations & p. 31 glyph strip |
| 24 | p. 33 (Fol. 27) | `fig_p033` | 12-column solar month, zodiac & lunar mansion concordance table |
| 25 | p. 41 (Fol. 35) | `fig_p041` | Four archangelic *awfāq*: ʿIzrāʾīl (3×3), Isrāfīl (4×4), Jibrīl (7×7), Mīkāʾīl (8×8) |
| 26–27 | pp. 45, 47 (Fol. 39, 41) | `fig_p045`, `fig_p047` | 5×5 *Basmalah* square; Concentric Circle of *Bismillāh al-Raḥmān al-Raḥīm* |
| 28–31 | pp. 53, 56, 57, 60 | `fig_p053`–`fig_p060` | 11×11 octagon-inscribed retreat table; four-crescent circle; circular *khātam* seal; Circle of Jesus' prayer |
| 32–35 | pp. 61, 64, 67 | `fig_p061a`–`fig_p067` | 8×8 *Mīm* square; 10×10 numerical table; three lower Divine-Name *awfāq* (omitted in OCR); *Mālik al-Mulk* 4×4 *wafq* |
| 36–39 | pp. 78, 80, 82, 84 | `fig_p078`–`fig_p084` | Love *wafq*, *al-Laṭīf* *wafq*, Jibrīl/Mīkāʾīl *wafq*, and full-width 8×8 Grid of the Most Beautiful Names of Allah |
| 40 | p. 95 (Fol. 89) | `fig_p095` | Full archival plate of Folio 89: Seven Seals glyph formulas (`[U+10348]` in OCR) & opening 18 verses of *al-Qaṣīdah al-Jaljalūtiyyah* |
| 41–42 | p. 97 (Fol. 91) | `fig_p097a`, `fig_p097b` | Inline Torah, Gospel & Qurʾān seal glyphs (`[U+06DE] |||`, `‡ mīm`, `[U+06E9] |||`) and three-rod healing seal |
| 43–44 | p. 99 (Fol. 93) | `fig_p099a`, `fig_p099b` | Inline Seven-Seals Greatest-Name formula & 7×7 Seven-Seals talismanic *wafq* |
| 45–46 | p. 100 (Fol. 94) | `fig_p100a`, `fig_p100b` | 6-column table of the Two Tablets (1–30), numerical Tablet of Life/Death, 5×4 prisoner lunatic-glyph *wafq*, and 3×3 numerical *wafq* |
| 47 | p. 102 (Fol. 96) | `fig_p102` | 10×10 diagonally calligraphed *Muʿashshar* magic square of the opening verses of Sūrat al-Ḥadīd |
| 48 | p. 104 (Fol. 61) | `fig_p104` | Concentric talismanic circle around an inscribed square, with marginal name-labels |
| 49–50 | p. 105 (Fol. 99) | `fig_p105a`, `fig_p105b` | Eight-pointed letter lattice (*wafq*) with corner names above the “truth against falsehood” verse; square cord diagram with four named corners |
| 51 | p. 112 (Fol. 106) | `fig_p112` | Six 7×7 letter grids for the planetary days (fāʾ/Sun, shīn/Mars, ẓāʾ/Jupiter, jīm/Moon, thāʾ/Mercury, ḥāʾ/Venus) |
| 52 | p. 113 (Fol. 107) | `fig_p113` | Seven-column *zāy* letter grid for Saturn and Saturday with its printed caption |
| 53 | p. 121 (Fol. 115) | `fig_p121` | Six-column “sufficient figure” (*al-shakl al-kāfī*) letter grid closing the *wafq* described at the end of Scan Page 120 |

---

## 3. Continuation Playbook (Extending Beyond Page 121)

When ready to extend the English PDF to newly committed Translation Alignment V2 pages (`122..N`). Note Scan Page 122 was in *rework* at this snapshot and is therefore excluded until its r2 approval lands:

1. **Check Committed Boundary:**
   Inspect `state/translation_v2/progress.json` and identify the highest contiguous page with `"status": "committed"`. Never include pages currently `claimed`, `in_progress`, or `review`.

2. **Survey New Scan Pages (`122..N`) for Visuals (plus any Parallel Editorial Overrides):**
   - Check `git diff --name-only <last_pdf_commit>..HEAD -- ocr/enriched_en/` to see if any earlier pages with `FigureSpec` entries had their paragraph/block counts altered by parallel editorial overrides, and update `after_block` if needed.
   - Search Arabic and English blocks of `122..N` for diagram cues (`صور`, `صفت`, `جدول`, `وفق`, `أوفاق`, `دائر`, `خاتم`, `شكل`, `هكذا`, `كما ترى`) AND visually inspect contact sheets of `web/public/scans/page-122.pdf`..`page-NNN.pdf`.
   - Plot candidate pages with a `5%` normalized `(0.00..1.00)` coordinate grid, extract 300-DPI test crops, and visually verify that no outer borders, corner angel labels, or marginalia are clipped. Pages whose diagrams are tall composites often need two separate crops rather than one merged box.

3. **Update `scripts/build_english_verbatim_pdf.py`:**
   - **Thematic `PARTS`:** Split the trailing `PartSpec` at the next major chapter boundary (current tail: `Part XIII`, `113..604`) and append new entries; keep the final `PartSpec.end_page = 604` so `min(pt.end_page, end_page)` dynamically covers the exact committed frontier.
   - **`FIGURES`:** Append verified `FigureSpec` entries (`fig_num` continuing sequentially from `54`), setting `after_block` (`-1` for top-of-page before `B0`, or `0..K` after the specific block index returned by `split_raw_blocks(en, page_num)`).
   - Keep `.part-kicker` `letter-spacing <= 0.08em` so Chromium's PDF text layer preserves `Part <Roman>` for two-pass page probing.

4. **Build & Verify:**
   ```bash
   "C:/Users/it26/AppData/Local/hermes/tools/uv-0.13.5-win32-x64/uv.exe" run \
     --with pymupdf --with pillow \
     python scripts/build_english_verbatim_pdf.py --end-page <N>
   ```
   Confirm:
   - `[OK] Strict HTML Verbatim Audit PASSED` (`0` token diffs across all `1..N` pages).
   - `Pagination converged cleanly on pass 2!` with all `3 + len(PARTS) + N + len(FIGURES)` probes resolved.
   - `[OK] PDF Text Layer Audit PASSED` and visual spot-check of rendered TOC, new diagram crops, and final page.
