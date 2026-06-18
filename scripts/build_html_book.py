#!/usr/bin/env python3
"""Build a complete HTML book manuscript from enriched English pages.

   v2 — intelligently rejoins fragmented OCR lines into proper paragraphs,
   detects section headings, and applies uniform typographic spacing.
"""

import os
import re
import glob

PAGES_DIR = r"C:\Working Folder\Research\shams-al-maarif-ocr\ocr\enriched_en"
OUTPUT_DIR = r"C:\Working Folder\Research\shams-al-maarif-ocr\manuscript"
HTML_FILE = os.path.join(OUTPUT_DIR, "shams-al-maarif-verbatim.html")


# ── helpers ──────────────────────────────────────────────────────────

def html_escape(text):
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return text


def html_escape_with_arabic(text):
    """Escape HTML, then wrap Arabic spans for proper font rendering."""
    escaped = html_escape(text)
    arabic_re = re.compile(
        r'([\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF'
        r'\uFB50-\uFDFF\uFE70-\uFEFF]+'
        r'(?:\s+[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF'
        r'\uFB50-\uFDFF\uFE70-\uFEFF]+)*)'
    )
    return arabic_re.sub(r'<span class="ar">\1</span>', escaped)


def parse_page(text):
    """Extract (arabic, english) from a page file."""
    parts = text.split("English:\n", 1)
    if len(parts) < 2:
        return "", ""
    arabic_part = ""
    if "Arabic:\n" in parts[0]:
        arabic_part = parts[0].split("Arabic:\n", 1)[1].strip()
    english = parts[1]
    for suffix in ("\nNotes:", "\n\nNotes\n"):
        if suffix in english:
            english = english.split(suffix, 1)[0]
    return arabic_part.strip(), english.strip()


# ── line classification ─────────────────────────────────────────────

def classify_line(s):
    """Return a (kind, payload) tuple for a stripped line."""
    if not s:
        return ("blank", "")

    # standalone page number  "— 24 —"  or  "- 44 -"
    if re.match(r'^[—\-–]\s*\d+\s*[—\-–]$', s):
        return ("page_number", s)

    # ornamental heading  "❖ Notice ❖",  "❖ And following it ❖"
    if s.startswith("❖") or s.startswith("※") or s.startswith("⁂"):
        return ("ornament_heading", s)

    # bracketed section  "(Section)",  "(The first chapter…)",  "( الفصل … )"
    if re.match(r'^[\(（]\s*(?:Section|Chapter|الفصل|الباب|The\s)', s):
        return ("section_heading", s)

    # standalone Arabic-bracket chapter  "﴿ Chapter Two ﴾" embedded — not a whole line
    # We'll handle inline  ﴿…﴾  later.

    # short isolated number (often an artifact line)
    if re.match(r'^\d{1,3}$', s):
        return ("short_num", s)

    # grid / numerical content
    grid_chars = set("☩۞۩○●□■▢∆▲▽▼")
    if any(c in grid_chars for c in s) and len(s) > 5:
        return ("grid", s)
    if re.match(r'^[\d\s]{8,}$', s) and len(s) > 10:
        return ("grid", s)

    # line with only a few words (OCR line-break artifact)
    word_count = len(s.split())
    if word_count <= 3:
        return ("short_line", s)

    # regular prose
    return ("prose", s)


def is_continuation(prev_kind, prev_text, curr_text):
    """Should curr_text be joined to prev_text as the same paragraph?"""
    # If previous was a short line or short number, join
    if prev_kind in ("short_line", "short_num", "prose"):
        # If previous ends with sentence-ending punctuation, likely a break
        if prev_text.rstrip().endswith(('.', '!', '?', ':', '،', '؛')):
            # But not if it's just a very short line (OCR break)
            if len(prev_text.split()) > 4:
                return False
        # If current starts with uppercase after a period-ender → new sentence
        if curr_text[0].isupper() and prev_text.rstrip().endswith('.'):
            return True  # still join, but could add a space
        return True
    return False


# ── paragraph building ──────────────────────────────────────────────

def build_paragraphs(lines):
    """Join OCR-fragmented lines into semantic paragraphs / headings.

    Returns a list of (type, text) tuples where type is one of:
      'prose', 'section_heading', 'ornament_heading', 'grid', 'poetry'
    """
    blocks = []  # list of (kind, [lines])

    current_kind = None
    current_lines = []

    def flush():
        nonlocal current_kind, current_lines
        if current_lines:
            blocks.append((current_kind, list(current_lines)))
        current_kind = None
        current_lines = []

    for raw_line in lines:
        s = raw_line.strip()
        kind, _ = classify_line(s)

        if kind in ("blank", "page_number"):
            flush()
            continue
        if kind == "short_num":
            # skip isolated numbers (often OCR artifacts)
            continue

        if kind == "section_heading":
            flush()
            blocks.append(("section_heading", s))
            continue

        if kind == "ornament_heading":
            flush()
            blocks.append(("ornament_heading", s))
            continue

        if kind == "grid":
            if current_kind != "grid":
                flush()
                current_kind = "grid"
            current_lines.append(s)
            continue

        # prose / short_line
        if current_kind is None:
            current_kind = "prose"
            current_lines = [s]
        elif current_kind == "prose":
            if is_continuation(current_kind, current_lines[-1], s):
                current_lines.append(s)
            else:
                flush()
                current_kind = "prose"
                current_lines = [s]
        elif current_kind == "grid":
            flush()
            current_kind = "prose"
            current_lines = [s]
        else:
            flush()
            current_kind = "prose"
            current_lines = [s]

    flush()
    return blocks


def detect_inline_formatting(text):
    """Apply inline HTML formatting within a paragraph of prose text."""
    # Escape
    t = html_escape_with_arabic(text)

    # Style inline ﴿ … ﴾ chapter references as highlights
    t = re.sub(r'﴿\s*(Chapter\s+\w+)\s*﴾',
               r'<span class="ch-ref">﴿ \1 ﴾</span>', t)

    # Style inline Arabic ﴿ … ﴾ brackets as subtle
    t = re.sub(r'﴿\s*([^﴿]+\s*[﴾])',
               r'<span class="ar-bracket">﴿ \1</span>', t)

    return t


def format_block(kind, text):
    """Turn a (kind, text) block into an HTML string."""
    if kind == "section_heading":
        # Remove outer parentheses
        clean = re.sub(r'^[\(（]\s*', '', text)
        clean = re.sub(r'\s*[\)）]$', '', clean)
        return f'    <p class="s-head">{html_escape_with_arabic(clean)}</p>'

    if kind == "ornament_heading":
        return f'    <p class="o-head">{html_escape_with_arabic(text)}</p>'

    if kind == "grid":
        return f'    <div class="grid">{html_escape(text)}</div>'

    if kind == "prose":
        para = detect_inline_formatting(text)
        return f'    <p>{para}</p>'

    return ""


# ── main assembler ──────────────────────────────────────────────────

def build_html(pages_data):
    """Build complete HTML document from page data."""

    known_chapters = [
        (6,  "Aperture", "",
         ""),
        (7,  "Preface — The First Part",
         "الجزء الأول من كتاب شمس المعارف الكبرى ولطائف العوارف",
         "The first part of the book Shams al-Maʿārif al-Kubrā wa-Laṭāʾif al-ʿAwārif"),
        (11, "Chapter One — On the Dotted Letters",
         "الفصل الأول في الحروف المعجمة وما فيها من الأسرار والإضمارات",
         "On the dotted letters and what is in them of secrets and hidden meanings"),
        (16, "Chapter Two — On Fraction and Expansion",
         "الفصل الثاني في الكسر والبسط وترتيب الأعمال في الأوقات والساعات",
         "On fraction and expansion, and the arrangement of works in the times and hours"),
        (24, "Chapter Three — On the Twenty-Eight Lunar Mansions",
         "الفصل الثالث في أحكام منازل القمر الثمانية والعشرين الفلكيات",
         "On the rulings of the twenty-eight lunar mansions"),
        (32, "Chapter Four — On the Twelve Zodiacal Signs",
         "الفصل الرابع في أحكام البروج الاثني عشر وما لها من الإشارات والارتباطات",
         "On the rulings of the twelve zodiacal signs"),
        (39, "Chapter Five — Secrets of the Basmalah",
         "الفصل الخامس في أسرار البسملة وما لها من الخواص والبركات الخفيات",
         "On the secrets of the basmalah and its hidden properties"),
        (54, "Chapter Six — On Seclusion",
         "الفصل السادس في الخلوة وما يختص به أرباب الاعتكافات الموصلات للعلويات",
         "On seclusion and what pertains to the masters of iʿtikāf"),
        (62, "Chapter Eight — The Four Tawqīfāt",
         "الفصل الثامن في التواقيف الأربعة وما لها من الفصول والدائرات",
         "On the four tawqīfāt and their chapters and circles"),
        (67, "Chapter Nine — Properties of the Beginnings of Sūras",
         "الفصل التاسع في خواص أوائل سور القرآن والآيات المحكمات",
         "On the properties of the beginnings of the sūras and the clear verses"),
        (75, "Chapter Ten — Secrets of al-Fātiḥah",
         "الفصل العاشر في أسرار الفاتحة وخواصها ودعواتها المشهورة",
         "On the secrets of al-Fātiḥah, its properties and supplications"),
        (84, "Chapter Eleven — The Raḥmutiyyāt Inventions",
         "الفصل الحادي عشر في الاختراعات الرحموتيات والأنوار المشرقة من الأسرار الملكوتيات",
         "On the raḥmutiyyāt inventions and the shining lights"),
        (92, "Chapter Twelve — The Supreme Name",
         "الفصل الثاني عشر في الاسم الأعظم وما له من التصريفات الخفيات",
         "On the supreme name and its hidden dispositions"),
    ]

    # ── CSS ──────────────────────────────────────────────────────────
    css = r"""
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html { font-size: 18px; scroll-behavior: smooth; }

body {
  font-family: 'Merriweather', 'Georgia', 'Palatino', 'Book Antiqua', 'Times New Roman', serif;
  background: #f2ebe1;
  color: #2c2416;
  line-height: 1.85;
  -webkit-font-smoothing: antialiased;
}

/* ── book container ── */
.book {
  max-width: 740px;
  margin: 0 auto;
  background: #faf6ef;
  min-height: 100vh;
  box-shadow: 0 0 60px rgba(0,0,0,0.06);
}

/* ── title page ── */
.title-page {
  text-align: center;
  padding: 18vh 2rem 2rem;
}
.title-page .ar-title {
  font-family: 'Amiri', 'Traditional Arabic', serif;
  font-size: 2rem; direction: rtl; color: #5a4a34;
  margin-bottom: 1.2rem;
}
.title-page h1 {
  font-size: 2.8rem; font-weight: 700; line-height: 1.15;
  color: #1a150e; margin-bottom: 0.6rem;
}
.title-page .subtitle {
  font-size: 1.05rem; font-weight: 300; font-style: italic;
  color: #7a6b54; margin-bottom: 1.5rem;
}
.title-page .author {
  font-size: 1.05rem; margin-top: 2rem; color: #4a3d2e;
}
.title-page .edition {
  font-size: 0.8rem; color: #8a7b64; margin-top: 3rem;
  letter-spacing: 0.12em; text-transform: uppercase;
}
.title-divider { width: 50px; height: 1px; background: #c4b8a8; margin: 1.2rem auto; }

/* ── copyright ── */
.copyright {
  padding: 3rem 2rem; font-size: 0.8rem; color: #7a6b54; line-height: 1.7;
}
.copyright p { margin-bottom: 0.7rem; }

/* ── chapter heading ── */
.chapter {
  padding: 3.5rem 2rem 0.5rem;
}
.chapter .ch-label {
  font-size: 0.78rem; letter-spacing: 0.2em; text-transform: uppercase;
  color: #8a7b64; margin-bottom: 0.2rem;
}
.chapter .ch-title {
  font-size: 1.5rem; font-weight: 700; line-height: 1.3;
  color: #2c2416; margin-bottom: 0.2rem;
}
.chapter .ch-ar {
  font-family: 'Amiri', 'Traditional Arabic', serif;
  font-size: 1.1rem; direction: rtl; color: #6a5b44; margin-bottom: 0.2rem;
}
.chapter .ch-desc {
  font-size: 0.9rem; font-style: italic; color: #7a6b54; margin-bottom: 1.2rem;
}
.ch-divider { width: 36px; height: 2px; background: #c4b8a8; }

/* ── page marker ── */
.p-marker {
  text-align: center; font-size: 0.72rem; color: #b8ae9e;
  letter-spacing: 0.12em; margin: 1.5rem 0 1rem;
  padding-top: 1rem; border-top: 1px solid #e8e0d4;
}
.p-marker:first-of-type { border: none; padding-top: 0; margin-top: 0; }
.p-marker .p-num { font-weight: 700; color: #9a8e7e; }

/* ── body text ── */
.body-text { padding: 0 2rem 0.5rem; }

.body-text p {
  margin-bottom: 1rem;
  text-align: justify;
  text-indent: 0;
  orphans: 3; widows: 3;
  hanging-punctuation: first;
}

/* ── section heading (parenthesised) ── */
.s-head {
  font-weight: 700; font-size: 0.95rem;
  color: #3a3024; margin: 1.8rem 0 0.8rem !important;
  letter-spacing: 0.03em;
}

/* ── ornamental heading (❖) ── */
.o-head {
  font-weight: 600; font-size: 0.95rem;
  color: #5a4a34; margin: 1.5rem 0 0.8rem !important;
  text-align: center;
}

/* ── inline chapter references ── */
.ch-ref { color: #7a6b54; font-style: italic; font-size: 0.9rem; }
.ar-bracket { color: #8a7b64; font-size: 0.9rem; }

/* ── arabic inline ── */
.ar {
  font-family: 'Amiri', 'Traditional Arabic', serif;
  direction: rtl; font-size: 1.05em; color: #5a4a34;
}

/* ── grid / numerical content ── */
.grid {
  margin: 1.2rem 0; padding: 0.8rem 1rem;
  background: #f3ede4; border: 1px solid #e0d6c8; border-radius: 3px;
  font-family: 'Courier New', monospace;
  font-size: 0.82rem; line-height: 1.35;
  white-space: pre-wrap; overflow-x: auto;
  color: #3a3024;
}

/* ── print ── */
@media print {
  body { background: white; font-size: 11pt; }
  .book { max-width: 100%; box-shadow: none; background: white; }
}
@media (max-width: 600px) {
  html { font-size: 16px; }
  .title-page h1 { font-size: 2rem; }
  .chapter .ch-title { font-size: 1.3rem; }
  .body-text { padding: 0 1.2rem; }
}
"""

    # ── build HTML ──────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Shams al-Maʿārif al-Kubrā — Verbatim English Edition</title>
<style>{css}</style>
</head>
<body>
<div class="book">

<!-- TITLE -->
<div class="title-page">
  <div class="ar-title">شمس المعارف الكبرى</div>
  <h1>Shams al-Maʿārif<br>al-Kubrā</h1>
  <div class="subtitle">The Great Sun of Gnoses<br>Verbatim English Edition</div>
  <div class="title-divider"></div>
  <div class="author">Aḥmad ibn ʿAlī al-Būnī<br><span style="font-size:0.85rem;color:#7a6b54;">d. 622 AH / 1225 CE</span></div>
  <div class="edition">Literal &amp; Unabridged · Pages 1–119 of 604</div>
</div>

<!-- COPYRIGHT -->
<div class="copyright">
<p><strong>Shams al-Maʿārif al-Kubrā</strong> — Verbatim English Edition</p>
<div style="height:1.5rem;"></div>
<p>This translation is a <strong>verbatim, literal rendering</strong> of the original Arabic. No interpretation, commentary, or cultural adaptation has been added. Technical terms, honorifics, invocations, and ambiguous constructions are preserved as-is. When forced to choose between smooth English and accurate English, accuracy is chosen.</p>
<p>Source text: Cairo edition, collated against Egypt &amp; India editions plus the al-Ḥajj Mirzā Ḥusayn manuscript. OCR &amp; enrichment via Gemini 2.0 Flash.</p>
<p style="margin-top:1rem;">This is a work-in-progress partial edition (pages 1–119 of 604).</p>
</div>

<!-- CONTENTS (inline list) -->
<div class="body-text" style="padding:2rem 2rem 3rem;border-top:1px solid #e8e0d4;">
<p style="font-weight:700;font-size:1.1rem;text-align:center;margin-bottom:1.5rem;letter-spacing:0.1em;text-transform:uppercase;color:#2c2416;">Contents</p>
"""
    # TOC
    for pg, label, ar, desc in known_chapters:
        if ar:
            ar_display = f'<span style="font-family:Amiri,\'Traditional Arabic\',serif;direction:rtl;font-size:0.9rem;color:#6a5b44;"> — {ar}</span>' if ar else ""
        else:
            ar_display = ""
        html += f'<p style="margin-bottom:0.3rem;font-size:0.9rem;"><span style="color:#8a7b64;font-weight:600;">{pg}</span> {label}{ar_display}</p>\n'

    html += """</div>

<!-- BOOK BODY -->
<div class="book-body">
"""

    # ── process pages ───────────────────────────────────────────────
    ch_map = {pg: (label, ar, desc) for pg, label, ar, desc in known_chapters}

    for page_num, arabic, english in pages_data:
        # skip blank pages
        if page_num in (1, 3, 5):
            continue

        # chapter break before this page?
        if page_num in ch_map:
            label, ar, desc = ch_map[page_num]
            html += '<div class="chapter">\n'
            html += f'  <div class="ch-label">— {label.split(" —")[0] if "—" in label else label} —</div>\n'
            html += f'  <div class="ch-title">{label}</div>\n'
            if ar:
                html += f'  <div class="ch-ar">{ar}</div>\n'
            if desc:
                html += f'  <div class="ch-desc">{desc}</div>\n'
            html += '  <div class="ch-divider"></div>\n'
            html += '</div>\n'

        # page marker
        if page_num == 2:
            html += f"""<div class="body-text">
<p class="p-marker"><span class="p-num">[p. {page_num}]</span> — Library Stamp</p>
<pre style="font-size:0.82rem;color:#6a5b44;margin:0.5rem 0 1rem;">{html_escape(english)}</pre>
</div>
"""
            continue

        html += f'<div class="body-text">\n'
        html += f'  <p class="p-marker"><span class="p-num">[p. {page_num}]</span></p>\n'

        # Build paragraphs from the English text
        raw_lines = english.split("\n")
        blocks = build_paragraphs(raw_lines)
        for kind, payload in blocks:
            if isinstance(payload, list):
                payload = " ".join(payload)
            html += format_block(kind, payload) + "\n"

        html += '</div>\n'

    # colophon
    html += """
<div class="copyright" style="margin-top:3rem;border-top:1px solid #e8e0d4;padding-top:2.5rem;">
<p><strong>Colophon</strong></p>
<p>Verbatim English Edition of <em>Shams al-Maʿārif al-Kubrā</em>. Every technical term (raml, shakl, watad, rūḥāniyyah), honorific (ʿalayhi al-salām, ṣallā Allāhu ʿalayhi wa-sallam), and invocation is preserved. Grids and numerical squares are reproduced as-is. Ambiguities in the original are retained.</p>
<p>Typeface: Merriweather (body), Amiri (Arabic). Soft light edition.</p>
<p>Pages 1–119 of 604 · Work in progress.</p>
</div>

</div><!-- /book-body -->
</div><!-- /book -->
</body>
</html>"""

    return html


# ── entry point ─────────────────────────────────────────────────────

def main():
    files = sorted(glob.glob(os.path.join(PAGES_DIR, "page_*.txt")),
                   key=lambda x: int(re.search(r'page_(\d+)', x).group(1)))
    pages_data = []
    for fpath in files:
        pn = int(re.search(r'page_(\d+)', fpath).group(1))
        with open(fpath, 'r', encoding='utf-8') as f:
            text = f.read()
        ar, en = parse_page(text)
        pages_data.append((pn, ar, en))

    print(f"Read {len(pages_data)} pages")
    html = build_html(pages_data)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(HTML_FILE, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Written: {HTML_FILE}  ({len(html)//1024} KB)")


if __name__ == "__main__":
    main()
