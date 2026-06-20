# ╔═══════════════════════════════════════════════════════════════╗
# ║   شمس المعارف الكبرى                                         ║
# ║   Shams al-Ma'arif al-Kubra                                  ║
# ║   — The Great Sun of Gnoses —                                ║
# ║                                                              ║
# ║   OCR · Enrichment · English Translation Pipeline            ║
# ╚═══════════════════════════════════════════════════════════════╝

[![Pages](https://img.shields.io/badge/Pages-604-blue)](#)
[![OCR](https://img.shields.io/badge/OCR-100%25-success)](#)
[![Enriched](https://img.shields.io/badge/Enriched-100%25-success)](#)
[![Translated](https://img.shields.io/badge/Translation-24%25-yellow)](#)
[![Model](https://img.shields.io/badge/Model-Gemini%202.0%20Flash-purple)](#)
[![License](https://img.shields.io/badge/License-MIT-lightgrey)](#)

> *"A book of luminous secrets, divine names, and the hidden currents that move the spheres."*

A complete, production-grade pipeline to OCR, enrich, and translate Ahmad al-Buni's seminal 13th-century Arabic grimoire — **Shams al-Ma'arif al-Kubra** — from a 604-page scanned PDF into verbatim English, using multi-key Gemini OCR and GPT-5.4-mini translation.

---

## 📜 Philosophy

| Layer | What | Status |
|-------|------|--------|
| **Raw OCR** | Gemini Arabic extraction, page by page, untouched | ✅ 604/604 |
| **Enriched** | AI post-processing corrects OCR noise, preserves every word | ✅ 604/604 |
| **Translation** | Verbatim English — no summarisation, no interpretation | 🔄 59/245 pages with text |
| **HTML Codex** | Styled book manuscript from enriched output | ✅ Built |

**The highest rule:** Translate what the author wrote, not what you think the author meant.

---

## ⚡ Quick Start

```bash
# ── Setup ──
cd /mnt/c/Working\ Folder/Research/shams-al-maarif-ocr
python3 -m venv .venv && source .venv/bin/activate
pip install requests pillow

# ── Manual OCR batch (10 pages) ──
bash scripts/run_batch.sh

# ── Translation status ──
cd ocr && python3 translate_en.py --status

# ── Translate 6 pages ──
python3 translate_en.py --gentle

# ── Rebuild combined output ──
bash ~/.hermes/scripts/shams_combine_en.sh
```

---

## 🏛️ Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         shams-al-maarif-ocr                                │
│                                                                            │
│  📄 PDF (604 pages)                                                        │
│       │                                                                    │
│       ▼                                                                    │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────────┐                  │
│  │  STAGE 1 │    │   STAGE 2    │    │    STAGE 3       │                  │
│  │  OCR     │───▶│  Enrichment  │───▶│  Translation     │                  │
│  │  Gemini  │    │  Gemini      │    │  GPT-5.4-mini    │                  │
│  └──────────┘    └──────────────┘    └──────────────────┘                  │
│       │                 │                    │                             │
│       ▼                 ▼                    ▼                             │
│  ocr/raw/         ocr/enriched/        ocr/enriched_en/                    │
│  page_NNN.txt     page_NNN.txt         page_NNN.txt                       │
│                                            │                               │
│                                            ▼                               │
│                                     shams-al-maarif-en-complete.md         │
│                                     shams-al-maarif-en-complete.html       │
│                                            │                               │
│                                            ▼                               │
│                                     📖 manuscript/shams-al-maarif-verbatim.html
│                                                                            │
│  🕐 CRON:  */30 * * * *  (OCR enrichment)                                 │
│  🕐 CRON:  every 3h      (Translation)                                    │
│  🕐 CRON:  */15 * * * *  (Rebuild combined output)                        │
└────────────────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Multi-key rotation (8 keys)** | Free-tier Gemini caps at ~60 RPM / 50 RPD per key. Rotation unlocks continuous processing. |
| **3 pages per API call** | Respects rate limits while maximising throughput per key |
| **Verbatim + [UNCLEAR] markers** | When uncertain, the model marks ambiguity rather than guessing |
| **Git-tracked outputs** | Every translation page is committed — full audit trail |
| **Persistent state (JSON)** | Resumable across crashes, cron cycles, and terminal sessions |

---

## 📁 Repository Structure

```
shams-al-maarif-ocr/
├── 📄 README.md                          # This file — the map
├── 📄 PIPELINE_STATUS.md                 # Real-time pipeline health
├── 📄 manifest.json                      # Document metadata (BibTeX-style)
├── 📄 .gitignore                         # API keys, logs, runtime state
│
├── 📂 scripts/                           # Pipeline engines
│   ├── ocr_gemini.py                     # STAGE 1: Gemini Arabic OCR
│   ├── enrich_gemini.py                  # STAGE 2: AI post-correction
│   ├── progress_manager.py               # Shared state tracker (progress.json)
│   ├── run_batch.sh                      # CRON: OCR + enrich batch (10 pages)
│   ├── batch_process_all.sh              # Full backfill: pages 363→604
│   ├── git_auto_push.sh                  # Commit & push after batch
│   └── build_html_book.py                # Generate styled HTML codex
│
├── 📂 ocr/
│   ├── 📂 raw/                           # Raw Gemini output (verbatim, untouched)
│   │   └── page_{001..604}.txt
│   ├── 📂 enriched/                      # OCR noise corrected, text preserved
│   │   └── page_{001..604}.txt
│   ├── 📂 enriched_en/                   # English translations
│   │   └── page_{001..245}.txt           # (245 pages with actual content)
│   ├── translate_en.py                   # STAGE 3: English translation engine
│   ├── translate_keys.py                 # 8 API keys (gitignored)
│   ├── .translate_state.json             # Translation progress (gitignored)
│   ├── shams-al-maarif-en-complete.md    # Combined English (3.7 MB, 3766 lines)
│   ├── shams-al-maarif-en-complete.html  # Styled HTML version (4.1 MB)
│   └── 📂 logs/                          # Runtime debug logs (gitignored)
│
├── 📂 state/
│   ├── progress.json                     # Per-page OCR/enrich status
│   └── batch_log.json                    # Batch run history
│
└── 📂 manuscript/                        # Final deliverable artifacts
    └── shams-al-maarif-verbatim.html     # Styled book HTML (539-line generator)
```

---

## 🧠 Pipeline Stages

### Stage 1: OCR — Gemini Arabic Extraction

**Script:** `scripts/ocr_gemini.py`

Sends each page PDF to Google Gemini 2.0 Flash with a carefully crafted Arabic-extraction prompt. Uses **8-key rotation** (via `gemini_rotate.py`) to bypass free-tier rate limits.

```bash
# Single page
python3 scripts/ocr_gemini.py 42

# Batch (via run_batch.sh — processes next 10 pending pages)
bash scripts/run_batch.sh
```

**Key features:**
- Multi-key rotation with persistent state (survives crashes)
- Exponential backoff on 429 rate limits (max 5 retries per page)
- Blank page detection — pages with <100 chars get marked `blank` not `failed`
- Verbatim mode — never summarises, never invents
- Output: `ocr/raw/page_NNN.txt` (completely unmodified Gemini response)

### Stage 2: Enrichment — AI Post-Correction

**Script:** `scripts/enrich_gemini.py`

Takes raw OCR (which may contain broken letterforms, ink-smudge artefacts, merged/split words from antique Naskh typeface) and produces a clean version.

```bash
# Single page
python3 scripts/enrich_gemini.py 42

# What it does:
#   ❌ "سـاحر" → ✅ "ساحر"  (fixes broken letter joins)
#   ❌ "ألرحمن" → ✅ "الرحمن" (fixes article splitting)
#   ❌ [UNCLEAR] → ✅ marks uncertainty when unsure
```

**Rules:**
- **Never deletes** content — even uncertain passages are preserved with `[?]`
- **Never rephrases** — this is correction, not rewriting
- **Never summarises** — every word of the original stays
- If uncertain → keep the raw text + `[?]` suffix

### Stage 3: Translation — English Verbatim

**Script:** `ocr/translate_en.py`

Translates enriched Arabic pages into English using OpenAI **gpt-5.4-mini** (Responses API). Multi-key rotation across 8 API keys.

```bash
# Translation commands
python3 translate_en.py --status              # Show progress
python3 translate_en.py --gentle              # 6 pages (2 API calls, 15s apart)
python3 translate_en.py --range 60-80         # Specific range
python3 translate_en.py --retry-failed        # Retry failed pages
python3 translate_en.py --all                 # Translate everything remaining
```

**Translation rules (enforced in prompt):**
1. Preserve technical terms — Raml (رمل), Shakl (شكل), Watad (وتد), Ruhaniyyah (روحانية)
2. Preserve honourifics, invocations, repeated phrases
3. Preserve grid/diagram/number-square content as-is
4. No interpretation, commentary, or cultural adaptation
5. When forced to choose: **accurate English > smooth English**

**State persistence:** `.translate_state.json` tracks:
- `completed` — successfully translated pages
- `failed` — permanently failed (rate limit exhaustion)
- `key_index` — which API key was active (survives crashes)

### Stage 4: HTML Codex Assembly

**Script:** `scripts/build_html_book.py`

Assembles enriched English pages into a styled HTML book manuscript with:
- Intelligent paragraph rejoining (fragmented OCR lines → proper paragraphs)
- Section heading detection
- Arabic span wrapping for proper font rendering
- Uniform typographic spacing

```bash
python3 scripts/build_html_book.py
# Output: manuscript/shams-al-maarif-verbatim.html
```

### Combine Scripts (external, in `~/.hermes/scripts/`)

| Script | Function |
|--------|----------|
| `shams_combine_en.sh` | Merges all `enriched_en/page_NNN.txt` → complete `.md` + `.html` |
| `shams_translate_gentle.sh` | Cron wrapper: translation + combine |
| `shams_to_html.py` | Alternative HTML generator for combined markdown |

---

## 🕐 Cron Jobs

| Job Name | Schedule | What It Does | Max Pages/Run |
|----------|----------|-------------|:-------------:|
| `shams-al-maarif-ocr-enrichment` | `*/30 * * * *` | OCR + enrich next 10 pending pages | 10 |
| `shams-translate-gentle` | `every 3h` | Translate 6 pages + rebuild combined files | 6 |
| `shams-enrich-complete` | `*/15 * * * *` | Standalone rebuild of `.md` + `.html` from latest | — |

**Timing formula for cron intervals:**
```
max_batch = floor(interval / (t_ocr + t_enrich + t_push))
Example: 30 min cron / (90s per page × 2 stages + 30s push) ≈ 10 pages
```

---

## 📊 Progress Tracking

```bash
# Pipeline status
python3 scripts/progress_manager.py status

# Translation status
cd ocr && python3 translate_en.py --status
```

**Current metrics:**

| Metric | Value |
|--------|-------|
| Total pages | 604 |
| Pages with text | 245 |
| Raw OCR complete | 604 / 604 (✅ 100%) |
| Enriched | 604 / 604 (✅ 100%) |
| Translated | 59 / 245 (🔄 24.1%) |
| Failed | 0 |
| Translation model | gpt-5.4-mini |
| API keys | 8 (rotated on rate limit) |
| Combined .md | 3.7 MB, 3766 lines |
| Combined .html | 4.1 MB |

---

## 🔧 Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `429 rateLimitExceeded` | Free-tier key exhausted | Auto-rotates to next key. If all 8 exhausted, wait 60s |
| `RECITATION` finish reason | Gemini safety filter | Shorten prompt to 12 words: "Extract all visible text verbatim" |
| `Failed: exit code` | Network / API timeout | Increase `PER_PAGE_TIMEOUT` to 300s, retry with `--retry-failed` |
| Empty page output | Genuinely blank folio | That's correct — marked as `blank`, not `failed` |
| Enriched text missing words | Aggressive correction | Check raw vs enriched diff. Lower correction strength if needed |
| Git push fails | Network / auth | Run `bash scripts/git_auto_push.sh` manually |
| `.venv` permission denied | Hermes-owned venv | Use `pip install --user` or create venv outside Hermes home |

---

## 🔐 Git Security

The following are **never committed** (blocked by `.gitignore`):

| Pattern | Contents |
|---------|----------|
| `translate_keys.py` | 8 OpenAI API keys (base64-encoded) |
| `.translate_env` | Legacy single-key env file |
| `.translate_state.json` | Runtime state (includes key_index) |
| `ocr/logs/` | Debug logs (may contain request/response data) |

Translation output files (`enriched_en/`, `shams-al-maarif-en-complete.*`) **are tracked** — they're the pipeline's deliverable.

---

## 📖 Document Details

| Field | Value |
|-------|-------|
| **Title** | شمس المعارف الكبرى ولطائف العوارف |
| **English** | The Great Sun of Gnoses and the Subtleties of the Knowledges |
| **Author** | أحمد بن علي البوني (Ahmad ibn Ali al-Buni, d. 1225 CE / 622 AH) |
| **Subject** | Lettrism (*'ilm al-huruf*), esoteric sciences, divination, occult properties of Divine Names and Quranic verses |
| **Edition** | Cairo printing, collated against Egypt & India editions + al-Hajj Mirza Husayn manuscript |
| **Editor** | Shaykh 'Abd al-Rahman al-Jaziri (الشيخ عبد الرحمن الجزيرى) |
| **Language** | Classical Arabic |
| **Pages** | 604 (245 with text content, rest blank folios) |
| **Source** | Scanned PDF, 200 DPI, antique Naskh typeface |
| **OCR Engine** | Gemini 2.0 Flash (google/gemini-2.0-flash-001) |
| **Translation** | OpenAI gpt-5.4-mini (Responses API) |
| **Pipeline** | v1.0.0 |

---

## 🤝 Contributing

Since this is a **verbatim preservation project**, any correction must be traceable:

1. **Check the raw OCR** — was it a Gemini misread or an enrichment mistake?
2. **Check the enriched Arabic** — is the source correct before translation?
3. **If translation error** — note the page number + proposed correction
4. **Open an issue** — with the page number, current text, and suggested fix

---

## 📄 License

The original text is in the **public domain** (13th century CE).  
The OCR output, enrichment pipeline, translation tools, and generated artifacts are released under the **MIT License**.

---

<div align="center">

*"In the Name of Allah, the Most Gracious, the Most Merciful. This is a book of luminous secrets and hidden sciences..."*

— Ahmad al-Buni, *Shams al-Ma'arif al-Kubra*

</div>
