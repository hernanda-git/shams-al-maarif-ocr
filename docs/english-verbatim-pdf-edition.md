# Verbatim Illustrated English PDF Edition — Session Record & Continuation Runbook

## 1. Current Baseline Snapshot (Pages 1–92)

- **Date:** 2026-11-07
- **Origin:** Completed the interrupted Hermes session `local-7a7cfb45a679ae4d847be315be834d12323b1a3cfe7e13f392acb54bea414fd8`, targeting all committed pages from Translation Alignment V2 campaign session `local-43c73d837d858a3379db8753710f3ed56392571ed569fbb2a7e2af5465797e7a` (checkpoint `31a4ad8`).
- **Completed Scope:** Physical Scan Pages **1–92** of 604 (**Printed Cairo Folios 1–86**).
- **Artifacts:**
  - `scripts/build_english_verbatim_pdf.py` — deterministic two-pass Chromium + PyMuPDF book compiler with 300-DPI manuscript diagram extraction and strict token-level verbatim verification.
  - `manuscript/Shams-al-Maarif-English-Verbatim-Pages-001-092.pdf` — `152` A4 pages (`27.53 MB`).

### Verification Metrics (Baseline `p001–p092`)

| Check | Result |
| --- | --- |
| Canonical English source parity (`ocr/enriched_en/page_001.txt`–`page_092.txt`) | **PASS** — `71,987 / 71,987` verbatim tokens (`0` diffs against `web/public/manuscript.json` and canonical block files) |
| Preserved 300-DPI manuscript figures & plates | **39 figures** across 34 scan pages (all visually audited against normalized coordinate grids) |
| Two-pass pagination convergence | **PASS** — `144 / 144` section, thematic-part, scan-page, and figure anchors resolved on Pass 2 |
| Navigation & PDF structure | `141` clickable internal TOC / Figure-Index links; `145` hierarchical PDF sidebar bookmarks; running headers & footers (`Page X of 152`) |
| Canonical corpus & tracker safety | Zero modifications to `ocr/enriched*`, `web/public/manuscript.json`, or `state/translation_v2/*` |

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
  - Inline editorial uncertainty notes (`[UNCLEAR: ...]`), kept verbatim inline at `8.7pt` italic muted sepia so continuous prose remains effortless to read.
  - Parenthetical Arabic-style rubrics (`(Chapter ...)`, `(Section)`, `(Benefit)`, `(Attention)`, `(And know)`), highlighted in dark crimson-sepia bold and split onto clean paragraph starts.
- **Pipe Tables (`awfāq` / `jadāwil`):**
  - `split_raw_blocks()` splits both on blank lines and on inline transitions between prose and pipe rows (needed e.g. on Scan Page 78 where the 4×4 numerical grid immediately follows prose without a blank line).
  - Markdown pipe syntax (`|` and `:---` separator rows) renders as bordered HTML `<table class="ms-table">` cells while `verify_html_verbatim()` verifies 100% token equality across all cell values and prose tokens.
  - `[Letter-string: ... | ...]` on Scan Page 56 is explicitly excluded from pipe-table parsing so its literal `|` separators remain intact.

### 2.3 Preserved Figures Inventory (`Scan Pages 1–92`)

Plain-text `.txt` files omit spatial geometry, circular rings, corner archangel labels, seals, and inline constellation dot-patterns. All 39 figures in `FIGURES` (`scripts/build_english_verbatim_pdf.py`) are cropped at 300 DPI with normalized `(x0, y0, x1, y1)` coordinates:

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

---

## 3. Continuation Playbook (Extending Beyond Page 92)

When ready to extend the English PDF to newly committed Translation Alignment V2 pages (`93..N`):

1. **Check Committed Boundary:**
   Inspect `state/translation_v2/progress.json` and identify the highest contiguous page with `"status": "committed"`. Never include pages currently `claimed`, `in_progress`, or `review`.

2. **Survey New Scan Pages (`93..N`) for Visuals:**
   - Search Arabic and English blocks of `93..N` for diagram cues (`صور`, `صفت`, `جدول`, `وفق`, `أوفاق`, `دائر`, `خاتم`, `شكل`, `هكذا`, `كما ترى`) AND visually inspect contact sheets of `web/public/scans/page-093.pdf`..`page-NNN.pdf` (some inline talismanic strips or secondary squares have no bracket tag in `.txt`).
   - Plot candidate pages with a `5%` normalized `(0.00..1.00)` coordinate grid, extract 300-DPI test crops, and visually verify that no outer borders, corner angel labels, or marginalia are clipped.

3. **Update `scripts/build_english_verbatim_pdf.py`:**
   - **Thematic `PARTS`:** Adjust `Part X` (`start_page=68`) or split at **Chapter Twelve** (which opens near the end of Scan Page 92: *Chapter Twelve on the Greatest Name of God and Its Hidden Operations*) and append `PartSpec` entries covering `93..N` up to the 40th chapter.
   - **`FIGURES`:** Append verified `FigureSpec` entries (`fig_num` continuing sequentially from `40`), setting `after_block` (`-1` for top-of-page before `B0`, or `0..K` after the specific block index returned by `split_raw_blocks()`).
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
