# شمس المعارف الكبرى — OCR, Enrichment & English Translation Pipeline

**Shams al-Ma'arif al-Kubra** (The Great Sun of Gnoses) by Ahmad al-Buni (d. 1225 CE) — a seminal 604-page Arabic manuscript on lettrism (*'ilm al-huruf*), esoteric sciences, divination, and the occult properties of Divine Names and Quranic verses.

This repository contains a complete pipeline:

1. **OCR** — Gemini-powered Arabic text extraction, page by page, verbatim
2. **Enrichment** — AI post-processing that corrects OCR artefacts without deleting content
3. **English Translation** — GPT-5.4-mini translation of enriched pages into English, with multi-key rotation for free-tier rate limits

---

## 📁 Structure

```
shams-al-maarif-ocr/
├── README.md                    # This file
├── .gitignore
├── manifest.json                # Global document metadata

├── scripts/
│   ├── ocr_gemini.py            # Stage 1: Gemini OCR (Arabic extraction)
│   ├── enrich_gemini.py         # Stage 2: Enrichment (correct OCR noise)
│   ├── progress_manager.py      # Shared state for progress.json
│   ├── run_batch.sh             # 🕐 CRON — OCR enrichment batch
│   └── git_auto_push.sh         # Commit & push to GitHub

├── ocr/
│   ├── raw/                     # Raw Gemini OCR output (untouched, verbatim)
│   │   └── page_{001..604}.txt
│   ├── enriched/                # Enriched versions (OCR noise corrected)
│   │   └── page_{001..604}.txt
│   ├── enriched_en/             # 🆕 English translations of enriched pages
│   │   └── page_{001..245}.txt  # (245 pages containing actual text)
│   ├── translate_en.py          # 🆕 Translation script (OpenAI Responses API)
│   ├── .translate_state.json    # 🆕 Translation progress tracker (gitignored)
│   ├── shams-al-maarif-en-complete.md       # 🆕 Combined English markdown
│   ├── shams-al-maarif-en-complete.html     # 🆕 Combined English HTML
│   └── logs/                    # 🆕 Translation runtime logs (gitignored)

├── state/
│   ├── progress.json            # OCR/enrichment per-page status
│   └── batch_log.json           # OCR batch run history

├── src/                         # (future) Consolidated pipeline modules
└── notebooks/                   # (future) Analysis notebooks
```

**Key:** 🆕 = New in this update

---

## 🧠 Workflow Overview

```
┌─────────────┐    ┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Page PDF    │───▶│ Gemini OCR      │───▶│ Enrichment Pass  │───▶│ English         │
│ (604 pages) │    │ (Arabic raw)    │    │ (noise correct)   │    │ Translation     │
└─────────────┘    └─────────────────┘    └──────────────────┘    └─────────────────┘
                         │                       │                        │
                   ocr/raw/page_NNN.txt    ocr/enriched/page_NNN.txt  ocr/enriched_en/page_NNN.txt
                                                                            │
                                                                    shams-al-maarif-en-complete.md
                                                                    shams-al-maarif-en-complete.html
```

---

## 🇬🇧 English Translation Pipeline

### Overview

Translates enriched Arabic pages into English using OpenAI **gpt-5.4-mini** via the Responses API.

**Key features:**
- **Verbatin translation** — no summarisation, no paraphrasing, no modernisation
- **Multi-key rotation** — 8 API keys distribute 50 RPD / 100K TPM limits across accounts
- **Batch mode** — 3 pages per API call to respect rate limits
- **Persistent state** — `.translate_state.json` tracks completed/failed pages across runs
- **Auto-combine** — `shams_combine_en.sh` merges all translations into master .md and .html files

### Translation Rules (Verbatim)

The highest rule: **translate what the author wrote, not what you think the author meant.**

- Preserve technical terms: Raml (رمل), Shakl (شكل), Watad (وتد), Ruhaniyyah (روحانية)
- Preserve honourifics, invocations, repeated phrases, ambiguities
- Preserve grid/diagram/number-square content as-is
- No interpretation, commentary, or cultural adaptation
- When forced to choose between smooth English vs accurate English → ALWAYS choose accurate

### Scripts

| Script | Purpose |
|--------|---------|
| `ocr/translate_en.py` | Main translation engine (OpenAI Responses API) |
| `~/.hermes/scripts/shams_combine_en.sh` | Merges all individual translations into complete files |
| `~/.hermes/scripts/shams_to_html.py` | Converts combined markdown to styled HTML |
| `~/.hermes/scripts/shams_translate_gentle.sh` | Cron wrapper (translation + combine) |

**Files NOT tracked in git** (for security):
- `ocr/translate_keys.py` — 8 API keys (base64-encoded)
- `ocr/.translate_state.json` — Runtime state (completed/failed/key_index)
- `ocr/logs/` — Runtime debug logs

### Progress

| Metric | Value |
|--------|-------|
| **Pages with text** | 245 |
| **Translated** | 59 / 245 (24.1%) |
| **Failed** | 0 |
| **Model** | gpt-5.4-mini |
| **API keys** | 8 (rotated on rate limit) |
| **Combined output** | `shams-al-maarif-en-complete.md` (499 KB) |
| | `shams-al-maarif-en-complete.html` (408 KB) |

---

## 🕐 Cron Jobs

| Job Name | Schedule | What It Does |
|----------|----------|-------------|
| `shams-al-maarif-ocr-enrichment` | `*/30 * * * *` | OCR enrichment: processes next 10 pending pages |
| `shams-translate-gentle` | `every 3h` | Translation: 6 pages per run, then rebuilds complete files |
| `shams-enrich-complete` | `*/15 * * * *` | Standalone rebuild of combined .md/.html from latest translations |

### Manual Translation

```bash
cd ocr

# Show status
python3 translate_en.py --status

# Gentle run (6 pages)
python3 translate_en.py --gentle

# Specific range
python3 translate_en.py --range 60-80

# Retry failed
python3 translate_en.py --retry-failed

# Translate all remaining
python3 translate_en.py --all

# Rebuild combined files only (if translation already done)
bash ~/.hermes/scripts/shams_combine_en.sh
```

---

## 🚀 Getting Started (OCR Pipeline)

### Prerequisites

- **Python 3.10+**
- **Gemini API key** — obtain from [aistudio.google.com](https://aistudio.google.com)
- **poppler-utils** (for `pdftoppm` / `pdftotext` on page PDFs)
- **Git** with GitHub authentication configured
- **OpenAI API key(s)** for translation (see translate_keys.py)

### Setup

```bash
# Clone (or enter) the repo
cd /mnt/c/Working\ Folder/Research/shams-al-maarif-ocr

# Create virtualenv & install deps
python3 -m venv .venv
source .venv/bin/activate
pip install requests pillow

# Configure Gemini API key
echo 'GEMINI_API_KEY="AI..."' > .env
```

### Manual OCR Run (one 10-page batch)

```bash
bash scripts/run_batch.sh
```

---

## 📊 Progress Tracking

```bash
# OCR / enrichment status
python3 scripts/progress_manager.py status

# Translation status
cd ocr && python3 translate_en.py --status

# Output (OCR):
#   Total pages: 604
#   OCR raw done: 604
#   Enriched: 604
#   Last batch: 2026-06-11 22:30 UTC

# Output (Translation):
#   Model:        gpt-5.4-mini
#   Total pages:  245
#   Completed:    59 (24.1%)
#   Remaining:    186
#   Failed:       0
#   Active key:   key[2]
#   Total keys:   8
```

---

## 🔐 Git Security

**Never commit API keys or tokens.** The `.gitignore` blocks:

| Pattern | Why |
|---------|-----|
| `translate_keys.py` | 8 OpenAI API keys (sensitive) |
| `.translate_env` | Legacy single-key env file |
| `.translate_state.json` | Runtime state (contains key_index) |
| `ocr/logs/` | Debug logs (may contain request/response data) |

Translation output files (`enriched_en/`, `shams-al-maarif-en-complete.*`) are **tracked** in git — they're the deliverable.

---

## 📜 Document Details

| Field | Value |
|-------|-------|
| **Title** | شمس المعارف الكبرى ولطائف العوارف |
| **Author** | أحمد بن علي البوني (Ahmad al-Buni, d. 1225 CE) |
| **Edition** | Cairo printing, collated against Egypt & India editions + al-Hajj Mirza Husayn manuscript |
| **Editor** | Shaykh 'Abd al-Rahman al-Jaziri |
| **Total Pages** | 604 (245 with text, rest blank/folio) |
| **Source** | Scanned PDF, 200 DPI, Naskh typeface |
| **OCR** | Gemini 2.0 Flash |
| **Translation** | OpenAI gpt-5.4-mini (Responses API) |

---

## 🤝 Contributing

Since this is a **verbatim preservation project**, any corrections must be traceable. If you spot an error:

1. Check the raw OCR — was it a Gemini error or an enrichment mistake?
2. Check the enriched Arabic — is it correct before translation?
3. If translation error, note the page number and proposed correction

---

## 📄 License

The text itself is in the public domain (original work from 13th century CE).  
The OCR output, enrichment pipeline, and translation tools are released under the MIT License.
