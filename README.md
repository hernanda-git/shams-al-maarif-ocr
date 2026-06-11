# شمس المعارف الكبرى — OCR & Enrichment Pipeline

**Shams al-Ma'arif al-Kubra** (The Great Sun of Gnoses) by Ahmad al-Buni (d. 1225 CE) — a seminal 604-page Arabic manuscript on lettrism (*'ilm al-huruf*), esoteric sciences, divination, and the occult properties of Divine Names and Quranic verses.

This repository contains a **Gemini-powered OCR pipeline** that transcribes the printed Cairo edition page-by-page, preserves every word **verbatim**, then enriches the output through a second AI pass that corrects OCR artefacts without deleting or rewriting any content.

---

## 📁 Structure

```
shams-al-maarif-ocr/
├── README.md                  # This file
├── .gitignore
├── manifest.json              # Global document metadata
│
├── scripts/
│   ├── ocr_gemini.py          # Stage 1: Gemini OCR — sends each page PDF to Gemini
│   │                          #   for Arabic text extraction. Output is VERBATIM.
│   ├── enrich_gemini.py       # Stage 2: Enrichment — corrects OCR noise while
│   │                          #   preserving every character of the original.
│   ├── progress_manager.py    # Shared state: read/write progress.json
│   ├── run_batch.sh           # 🕐 CRON ENTRY POINT — processes next 10 pending pages
│   └── git_auto_push.sh       # Commits & pushes changes to GitHub
│
├── ocr/
│   ├── raw/                   # Raw Gemini OCR output — untouched, verbatim
│   │   └── page_{001..604}.txt
│   └── enriched/              # Enriched versions — OCR noise corrected, content intact
│       └── page_{001..604}.txt
│
├── state/
│   ├── progress.json          # Per-page status: pending → raw_ocr → enriched → committed
│   └── batch_log.json         # History of every batch run
│
├── src/                       # (future) Consolidated pipeline modules
└── notebooks/                 # (future) Analysis notebooks
```

---

## 🧠 Workflow

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐     ┌──────────────┐
│ New page PDF │────▶│ Gemini OCR       │────▶│ Enrichment Pass │────▶│ git commit & │
│ detected     │     │ (verbatim raw)   │     │ (correct noise) │     │ push to main │
└─────────────┘     └──────────────────┘     └─────────────────┘     └──────────────┘
       │                     │                        │                       │
       │              saved to ocr/raw/          saved to ocr/enriched/      GitHub
       │                                                                  (private repo)
       └─── progress.json updated at every step ──────────────────────────┘
```

### Stage 1 — Raw OCR (`ocr_gemini.py`)

- Reads a page PDF (`page_NNN.pdf`) from the source directory
- Sends it to `gemini-2.0-flash` via the Gemini API with a **no-invention, no-summarisation** prompt
- Saves the raw response to `ocr/raw/page_NNN.txt` **completely unmodified** — every character the model returned
- Records character count, confidence indicators, detected language

### Stage 2 — Enrichment (`enrich_gemini.py`)

- Reads the raw OCR output
- Sends it to Gemini with a **conservative correction** prompt:
  - Fix only obvious OCR artefacts (garbled letter forms, broken words)
  - NEVER delete, rephrase, or summarise
  - Preserve original line breaks and paragraph structure
  - If unsure about a passage, leave it **exactly as in the raw OCR**
- Output goes to `ocr/enriched/page_NNN.txt`

### Enrichment Philosophy

> **"First, do no harm."**  
> The raw OCR is the ground truth of what the model saw. The enriched version adds corrections but must never remove content. If the model cannot read a word, it should mark it `[?]` rather than guess or omit. The two files together give researchers confidence: raw = what came off the page, enriched = best-effort reconstruction.

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+**
- **Gemini API key** — obtain from [aistudio.google.com](https://aistudio.google.com)
- **poppler-utils** (for `pdftoppm` / `pdftotext` on page PDFs)
- **Git** with GitHub authentication configured

### Setup

```bash
# Clone (or enter) the repo
cd /mnt/c/Working\ Folder/Research/shams-al-maarif-ocr

# Create virtualenv & install deps
python3 -m venv .venv
source .venv/bin/activate
pip install requests pillow

# Configure API key
echo 'GEMINI_API_KEY="AI..."' > .env
```

### Manual Run (one 10-page batch)

```bash
bash scripts/run_batch.sh
```

### Cron Schedule

```bash
# Every 30 minutes, process the next 10 pages
crontab -e
# Add:
*/30 * * * * cd /mnt/c/Working\ Folder/Research/shams-al-maarif-ocr && bash scripts/run_batch.sh >> state/cron.log 2>&1
```

---

## 📊 Progress Tracking

```bash
# See current status
python3 scripts/progress_manager.py status

# Output:
#   Total pages: 604
#   OCR raw done: 47
#   Enriched: 40
#   Pending: 557
#   Last batch: 2026-06-11 22:30 UTC
```

---

## 🔐 GitHub Publishing

This repo is designed to be a **GitHub private repository** so every enrichment iteration is version-controlled and auditable. The auto-push script:

```bash
# On every run_batch, after processing pages:
bash scripts/git_auto_push.sh
```

To set up the remote:

```bash
git remote add origin https://github.com/YOUR_USER/shams-al-maarif-ocr.git
git push -u origin main
```

---

## 📜 Document Details

| Field | Value |
|-------|-------|
| **Title** | شمس المعارف الكبرى ولطائف العوارف |
| **Author** | أحمد بن علي البوني (Ahmad al-Buni, d. 1225 CE) |
| **Edition** | Cairo printing, collated against Egypt & India editions + al-Hajj Mirza Husayn manuscript |
| **Editor** | Shaykh 'Abd al-Rahman al-Jaziri |
| **Total Pages** | 604 |
| **Source** | Scanned PDF, 200 DPI, Naskh typeface |
| **Language** | Arabic (Classical) |
| **Processing** | Gemini 2.0 Flash → enrichment pass |

---

## 🤝 Contributing

Since this is a **verbatim preservation project**, any corrections must be traceable. If you spot an error in the enriched files:
1. Check the raw OCR — was it a Gemini error or an enrichment mistake?
2. If enrichment, propose a fix via pull request with the raw & corrected side-by-side.

---

## 📄 License

The text itself is in the public domain (original work from 13th century CE).  
The OCR output and enrichment pipeline code are released under the MIT License.
