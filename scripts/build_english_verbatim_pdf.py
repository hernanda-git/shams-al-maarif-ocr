#!/usr/bin/env python3
"""Build a publication-grade, 100% verbatim English PDF of Shams al-Ma'arif al-Kubra
with high-resolution (300-DPI) cropped manuscript diagrams, magic squares (awfaq),
celestial circles (dawa'ir), star-dot asterisms, pagination, TOC, and PDF bookmarks.

Default scope: Physical Scan Pages 1 through the last `committed` page in
`state/translation_v2/progress.json` (currently Page 92).
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pymupdf
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from recover_sibling_blocks import parse_blocks as _parse_blocks  # noqa: E402


# ── Thematic Structure (Inserted only BETWEEN manuscript pages) ──────────────

@dataclass(frozen=True)
class PartSpec:
    part_num: str
    start_page: int
    end_page: int
    title: str
    subtitle: str


PARTS: List[PartSpec] = [
    PartSpec("I", 1, 9, "Codex Preliminaries, Title Leaf & Opening Doxology",
             "McGill Library Witness (RBSC Islamic BF 1410 B8 1927), Cairo Imprint & Author's Invocation"),
    PartSpec("II", 10, 10, "Synopsis of the Forty Chapters of the Great Book",
             "Author's Programmatic Table of Contents Across the Complete Compendium"),
    PartSpec("III", 11, 16, "Chapter One: Secrets of the Dotted Letters & Cosmic Spheres",
             "Planetary Correspondences, Letter Operations, Concentric Circles & Fourfold Awfāq"),
    PartSpec("IV", 17, 23, "Chapter Two: Timing of Operations, Letter Invocations & Celestial Hours",
             "Servants of Alif, Lunar-Mansion Concordances, Planetary Hours & Elemental Triplicities"),
    PartSpec("V", 24, 31, "Chapter Three: Concealed Letter-Angels & The Twenty-Eight Lunar Mansions",
             "Celestial Wheels, Mansion Rulings, Incenses & Star-Cluster Asterisms"),
    PartSpec("VI", 32, 39, "Chapter Four: The Twelve Zodiac Signs, Constellations & Planetary Natures",
             "Solar-Month Concordance, Constellation Forms, Celestial Bodies & Planetary Dignities"),
    PartSpec("VII", 40, 52, "Chapters Five & Six: Secrets of the Basmalah, Seclusion & Spiritual Retreat",
             "Archangelic Awfāq, Virtues of Bismillāh, Circle of the Basmalah & Conditions of Khalwah"),
    PartSpec("VIII", 53, 60, "Sacred Geometric Circles & Chapter Seven: The Reviving Names of Jesus",
             "The 11×11 Retreat Table, Four-Crescent Circle, Talismanic Seal & Prayer of ʿĪsā"),
    PartSpec("IX", 61, 67, "Chapter Eight: Secrets of Mīm, the Four Harmonies & Properties of Divine Names",
             "Seasonal Angels, Four Winds, Magic Squares of the Beautiful Names & Mālik al-Mulk"),
    PartSpec("X", 68, 92, "Chapters Nine–Eleven: Luminous Surah Openings, Supplications & the 99 Names Grid",
             "Secrets of the Fourteen Luminous Letters, Protective Invocations, 8×8 Names Table & Subtle Realities"),
]


# ── Verified 300-DPI Manuscript Figures (Scan Pages 1–92) ────────────────────

@dataclass(frozen=True)
class FigureSpec:
    fig_id: str
    fig_num: int
    page: int
    crop: Tuple[float, float, float, float]  # (x0, y0, x1, y1) normalized [0..1]
    after_block: int  # -1 = before B0 (top of page); N = after block N (clamped to last block)
    size_class: str   # "sm" | "md" | "lg" | "plate" | "tall"
    caption: str


FIGURES: List[FigureSpec] = [
    FigureSpec("fig_p002", 1, 2, (0.25, 0.05, 0.78, 0.96), 99, "md",
               "McGill University Islamic Studies Library bookplate, call number (RBSC Islamic BF 1410 B8 1927), and accession stamp."),
    FigureSpec("fig_p004", 2, 4, (0.23, 0.04, 0.86, 0.56), 99, "md",
               "Bookseller label (Librairie Orientale H. Samuelian, Paris) and Institute of Islamic Studies library plate."),
    FigureSpec("fig_p006", 3, 6, (0.11, 0.10, 0.91, 0.90), 99, "plate",
               "Ornamental ruled poetic opening leaf preceding the Part One title page."),
    FigureSpec("fig_p007", 4, 7, (0.11, 0.09, 0.89, 0.90), -1, "plate",
               "Calligraphic Part One title page of Shams al-Maʿārif al-Kubrā (Muṣṭafā al-Bābī al-Ḥalabī and Sons, Cairo)."),
    FigureSpec("fig_p008", 5, 8, (0.11, 0.10, 0.89, 0.41), -1, "lg",
               "Illuminated opening headpiece (Wa-qul Rabbi zidnī ʿilman and Basmalah cartouche, Printed Folio 2)."),
    FigureSpec("fig_p012", 6, 12, (0.12, 0.25, 0.89, 0.35), 99, "lg",
               "Inline talismanic symbol arrangement for the figure of Leo (Folio 6, lines 8–10)."),
    FigureSpec("fig_p014", 7, 14, (0.13, 0.28, 0.56, 0.80), 2, "md",
               "Concentric cosmic and Divine-Name circle (dāʾirah) with central magic square and four cardinal inscriptions (Folio 8)."),
    FigureSpec("fig_p015", 8, 15, (0.21, 0.11, 0.53, 0.22), 1, "md",
               "Twin 4×4 numerical and letter awfāq squares for protection and intellect (Folio 9)."),
    FigureSpec("fig_p016", 9, 16, (0.50, 0.30, 0.82, 0.41), 2, "md",
               "Fourfold letter wafq square alongside its framed invocation (Folio 10)."),
    FigureSpec("fig_p017", 10, 17, (0.12, 0.15, 0.88, 0.26), 2, "lg",
               "Inline talismanic symbols and letter-forms of Alif omitted by plain-text OCR (Folio 11, lines 3–5)."),
    FigureSpec("fig_p018", 11, 18, (0.11, 0.20, 0.89, 0.47), 1, "lg",
               "Three-chambered talismanic diagram for invoking the servants of Alif, centered on a concentric circle and square (Folio 12)."),
    FigureSpec("fig_p019", 12, 19, (0.52, 0.19, 0.90, 0.44), 1, "md",
               "The Great Circular Wafq (al-Wafq al-ʿAẓīm) associated with Abū Jaʿfar al-Barmakī (Folio 13)."),
    FigureSpec("fig_p021", 13, 21, (0.21, 0.57, 0.56, 0.75), 6, "md",
               "8×8 Arabic letter concordance grid (jadwal) for the lunar mansions and zodiac signs (Folio 15)."),
    FigureSpec("fig_p023b", 14, 23, (0.14, 0.71, 0.45, 0.84), 6, "sm",
               "4×4 Concordance table of the twelve zodiac signs and four elemental natures (Folio 17)."),
    FigureSpec("fig_p024", 15, 24, (0.12, 0.51, 0.89, 0.90), 7, "lg",
               "Concentric wheel of the twenty-eight lunar mansions and concealed letter-angels (Folio 18)."),
    FigureSpec("fig_p025a", 16, 25, (0.12, 0.11, 0.91, 0.55), 1, "lg",
               "Grand concentric astronomical wheel of the 28 Lunar Mansions, 12 Zodiac Signs, and 28 Arabic Letters (Folio 19)."),
    FigureSpec("fig_p025b", 17, 25, (0.13, 0.57, 0.89, 0.90), 99, "plate",
               "Manuscript facsimile preserving inline star-dot asterisms for Mansions 1–3: al-Sharaṭān, al-Buṭayn, and al-Thurayyā (Folio 19)."),
    FigureSpec("fig_p026", 18, 26, (0.12, 0.11, 0.89, 0.90), 99, "plate",
               "Manuscript facsimile preserving inline star-dot asterisms for Mansions 4–9: al-Dabarān through al-Ṭarfah (Folio 20)."),
    FigureSpec("fig_p027", 19, 27, (0.11, 0.11, 0.89, 0.90), 99, "plate",
               "Manuscript facsimile preserving inline star-dot asterisms for Mansions 10–17: al-Ḥarthān through al-Shawlah (Folio 21)."),
    FigureSpec("fig_p028", 20, 28, (0.11, 0.11, 0.89, 0.90), 99, "plate",
               "Manuscript facsimile preserving inline star-dot asterisms for Mansions 18–26: al-Naʿāʾim through al-Fargh al-Muqaddam (Folio 22)."),
    FigureSpec("fig_p029", 21, 29, (0.11, 0.11, 0.89, 0.90), 99, "plate",
               "Manuscript facsimile preserving inline star-dot asterisms for Mansions 27–28 (al-Fargh al-Muʾakhkhar, al-Rashā) and polar stars (Folio 23)."),
    FigureSpec("fig_p030", 22, 30, (0.11, 0.11, 0.89, 0.90), 99, "plate",
               "Manuscript facsimile preserving inline constellation star-cluster asterisms from al-Thurayyā to al-Iklīl (Folio 24)."),
    FigureSpec("fig_p031", 23, 31, (0.11, 0.11, 0.89, 0.66), 9, "plate",
               "Manuscript facsimile preserving inline star-cluster asterisms and line-11 cryptic talismanic glyph strip (Folio 25)."),
    FigureSpec("fig_p033", 24, 33, (0.11, 0.35, 0.89, 0.50), 1, "lg",
               "Twelve-column concordance table of solar months, twelve zodiac signs, and twenty-eight lunar mansions (Folio 27)."),
    FigureSpec("fig_p041", 25, 41, (0.12, 0.38, 0.89, 0.82), 6, "lg",
               "The four archangelic magic squares (awfāq): ʿIzrāʾīl (3×3), Isrāfīl (4×4), Jibrīl (7×7), and Mīkāʾīl (8×8) (Folio 35)."),
    FigureSpec("fig_p045", 26, 45, (0.10, 0.14, 0.43, 0.34), 3, "sm",
               "Fivefold Basmalah magic square (wafq Bismillāh al-Raḥmān al-Raḥīm, Folio 39)."),
    FigureSpec("fig_p047", 27, 47, (0.13, 0.13, 0.69, 0.49), 0, "md",
               "Concentric Circle of Bismillāh al-Raḥmān al-Raḥīm (Folio 41; introduced at the conclusion of Scan Page 46)."),
    FigureSpec("fig_p053", 28, 53, (0.14, 0.13, 0.87, 0.50), 1, "lg",
               "11×11 Table of Numbers and Letters with inscribed geometric figure and marginal invocations (Folio 47)."),
    FigureSpec("fig_p056", 29, 56, (0.12, 0.13, 0.59, 0.46), 4, "md",
               "Geometric Circle (dāʾirah) with four corner crescents and radial Divine-Name inscriptions (Folio 50)."),
    FigureSpec("fig_p057", 30, 57, (0.19, 0.69, 0.47, 0.88), 8, "sm",
               "Circular talismanic seal (khātam) of the Divine Names in rectangular frame (Folio 51)."),
    FigureSpec("fig_p060", 31, 60, (0.12, 0.13, 0.53, 0.45), 1, "md",
               "Concentric Circle (ṣifat al-dāʾirah) associated with the reviving prayer of Jesus (Folio 54)."),
    FigureSpec("fig_p061a", 32, 61, (0.22, 0.34, 0.60, 0.60), 7, "md",
               "8×8 Numerical magic square (wafq) of the secrets of the letter Mīm (Folio 55)."),
    FigureSpec("fig_p064a", 33, 64, (0.12, 0.10, 0.89, 0.39), 0, "lg",
               "10×10 Numerical magic square table (Folio 58; introduced at the conclusion of Scan Page 63)."),
    FigureSpec("fig_p064b", 34, 64, (0.11, 0.53, 0.35, 0.90), 2, "tall",
               "Three stacked magic squares for the Divine Names al-Raḥmān, al-Raḥīm, and al-Salām (Folio 58; omitted in plain-text OCR)."),
    FigureSpec("fig_p067", 35, 67, (0.18, 0.45, 0.43, 0.61), 3, "sm",
               "4×4 Magic square (wafq) of Mālik al-Mulk and Dhū al-Jalāl wa-l-Ikrām (Folio 61)."),
    FigureSpec("fig_p078", 36, 78, (0.08, 0.30, 0.38, 0.39), 1, "md",
               "Fourfold numerical magic square (wafq) for attracting love and harmony (Folio 72)."),
    FigureSpec("fig_p080", 37, 80, (0.09, 0.34, 0.29, 0.45), 1, "sm",
               "4×4 Letter-and-numeral wafq of al-Laṭīf for safety and blessing (Folio 74)."),
    FigureSpec("fig_p082", 38, 82, (0.10, 0.56, 0.45, 0.70), 2, "md",
               "4×4 Archangelic numerical wafq headed by Jibrīl and Mīkāʾīl (Folio 76)."),
    FigureSpec("fig_p084", 39, 84, (0.11, 0.13, 0.89, 0.69), 1, "lg",
               "8×8 Grid of the Most Beautiful Names of Allah (al-Mālik, al-Quddūs, al-Salām..., Folio 78; introduced on Scan Page 83)."),
]


# ── Helpers: Parsing, Folio Detection & Verbatim Block Formatting ────────────

FOLIO_LINE_RE = re.compile(r"^\s*(?:[—‒―⎯─━~−֊ـ()-]+\s*\d{1,3}\s*[—‒―⎯─━~−֊ـ()-]+|\d{1,3})\s*$")
PIPE_TABLE_ROW_RE = re.compile(r"^\s*(?:\|.*\|.*|\d+\s*\|(?:\s*\d+\s*\|?)+)\s*$")
TABLE_SEP_RE = re.compile(r"^\s*\|?[\s:\-]+\|[\s:\-|]*$")
NEW_PARA_START_RE = re.compile(
    r"^(?:\(\s*(?:Chapter|The\s+[a-z\-]+\s+chapter|A\s+chapter|Section|Another\s+section|"
    r"Benefit|Attention|Notice|And\s+know|Know|Discourse|Some\s+of\s+them|As\s+for\s+the\s+literal|"
    r"Since\s+it\s+has|The\s+(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|"
    r"eleventh|twelfth|thirteenth|fourteenth|fifteenth|sixteenth|seventeenth|eighteenth)\s+mansion|"
    r"Among\s+its\s+properties|Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|"
    r"\d+\s*[—\-])"
    r"|\[(?:Chapter|The\s+[a-z\-]+\s+chapter)[^\]]*\]"
    r"|❖|☆|☼|\*$)",
    re.IGNORECASE,
)
STANDALONE_HEADING_RE = re.compile(
    r"^(?:\(\s*(?:Chapter|The\s+[^\)]{1,90}?chapter|A\s+chapter|Section|Another\s+section|"
    r"Discourse)[^\)]*\)|\[\s*(?:Chapter|The\s+[^\]]{1,90}?chapter)[^\]]*\])\s*$",
    re.IGNORECASE,
)


def parse_en_file(path: Path) -> str:
    raw = path.read_text(encoding="utf-8")
    for label, body, _ in _parse_blocks(raw):
        if label.lower() == "english" and body.strip():
            return body.strip()
    return ""


def detect_folio_number(page_num: int, first_line: str) -> Optional[str]:
    if page_num <= 7:
        return None
    s = first_line.strip()
    if FOLIO_LINE_RE.match(s):
        m = re.search(r"\d+", s)
        if m:
            return m.group(0)
    return None


def is_pipe_row(line: str) -> bool:
    s = line.strip()
    if not s or s.startswith("[Letter-string:"):
        return False
    return bool(PIPE_TABLE_ROW_RE.match(s))


def split_raw_blocks(en_text: str) -> List[str]:
    """Split on blank lines AND also split whenever prose transitions to/from a pipe-table."""
    coarse = [b.strip() for b in re.split(r"\n\s*\n", en_text.strip()) if b.strip()]
    refined: List[str] = []
    for block in coarse:
        lines = block.splitlines()
        cur: List[str] = []
        cur_is_pipe: Optional[bool] = None
        for ln in lines:
            p = is_pipe_row(ln)
            if cur_is_pipe is None:
                cur_is_pipe = p
                cur.append(ln)
            elif p == cur_is_pipe:
                cur.append(ln)
            else:
                refined.append("\n".join(cur).strip())
                cur = [ln]
                cur_is_pipe = p
        if cur:
            refined.append("\n".join(cur).strip())
    return refined


def style_inline_verbatim(raw_text: str) -> str:
    """Escape HTML and apply non-destructive inline visual styling while keeping 100% verbatim characters."""
    escaped = html.escape(raw_text, quote=False)

    # Style [UNCLEAR: ...] inline annotations in muted italic philological spans
    escaped = re.sub(
        r"(\[UNCLEAR:[^\]]*\])",
        r'<span class="ms-unclear">\1</span>',
        escaped,
        flags=re.DOTALL,
    )

    # Style [ Chapter ... ] inline synopsis markers (e.g., Page 10)
    escaped = re.sub(
        r"(\[\s*Chapter\s+[^\]]+\])",
        r'<strong class="ms-inline-chap">\1</strong>',
        escaped,
    )

    # Style leading parenthetical rubric at the very beginning of a paragraph: "(Section)", "(And know)", etc.
    escaped = re.sub(
        r"^(\([^\)\n]{1,115}\))",
        r'<strong class="ms-rubric">\1</strong>',
        escaped,
    )
    return escaped


def render_pipe_table_html(lines: List[str]) -> str:
    rows: List[List[str]] = []
    for ln in lines:
        if TABLE_SEP_RE.match(ln):
            continue
        s = ln.strip()
        if s.startswith("|") and s.endswith("|"):
            cells = [c.strip() for c in s[1:-1].split("|")]
        else:
            cells = [c.strip() for c in s.split("|")]
        rows.append(cells)

    if not rows:
        return ""
    max_cols = max(len(r) for r in rows)
    dense_class = " ms-table-dense" if max_cols >= 9 else ""
    out = [f'<div class="ms-table-wrap"><table class="ms-table{dense_class}"><tbody>']
    for r_idx, r in enumerate(rows):
        row_cls = ' class="ms-table-first"' if r_idx == 0 and len(rows) > 1 else ""
        out.append(f"<tr{row_cls}>")
        for c in r:
            cell_html = style_inline_verbatim(c) if c else ""
            out.append(f"<td>{cell_html}</td>")
        for _ in range(max_cols - len(r)):
            out.append('<td class="ms-empty-cell"></td>')
        out.append("</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def render_block_html(page_num: int, block_idx: int, block: str) -> str:
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    if not lines:
        return ""

    # 1. Folio line on block 0
    if block_idx == 0 and len(lines) == 1 and page_num >= 8 and FOLIO_LINE_RE.match(lines[0]):
        return f'<div class="ms-folio-line">{html.escape(lines[0], quote=False)}</div>'

    # 2. Blank page marker
    if len(lines) == 1 and lines[0] == "[NO VISIBLE TEXT]":
        return f'<div class="ms-blank-notice">{html.escape(lines[0], quote=False)}</div>'

    # 3. Pipe table block
    if all(is_pipe_row(ln) for ln in lines):
        return render_pipe_table_html(lines)

    # 4. Page 84 Divine Names row block: [Row N] followed by names
    if re.match(r"^\[Row\s+\d+\]$", lines[0]) and len(lines) > 1:
        hdr = html.escape(lines[0], quote=False)
        items = "".join(
            f'<div class="ms-name-cell">{style_inline_verbatim(ln)}</div>'
            for ln in lines[1:]
        )
        return f'<div class="ms-names-row-block"><div class="ms-row-badge">{hdr}</div><div class="ms-names-grid">{items}</div></div>'

    # 5. Diagram transcription / positional callout blocks
    if (
        re.match(r"^\[(?:Inside|Around|Outside|Top|Bottom|Grid\s+contents|Table\s+containing|Geometric\s+figure|Letter-string)", lines[0])
        or lines[0].startswith("Text transcribed ")
        or lines[0].startswith("Picture of ")
    ):
        inner = "<br>\n".join(style_inline_verbatim(ln) for ln in lines)
        return f'<div class="ms-diagram-callout">{inner}</div>'

    # 6. Front-matter stamp / poetic fragment / title pages (Pages 2, 4, 6, 7)
    if page_num in (2, 4, 6, 7):
        out_lines = []
        for ln in lines:
            if ln.startswith("❖"):
                out_lines.append(f'<div class="ms-ornament-heading">{style_inline_verbatim(ln)}</div>')
            else:
                out_lines.append(f'<div class="ms-imprint-line">{style_inline_verbatim(ln)}</div>')
        cls = "ms-title-leaf-box" if page_num == 7 else "ms-prelim-box"
        return f'<div class="{cls}">' + "\n".join(out_lines) + "</div>"

    # 7. Standalone single-line dividers / headings
    if len(lines) == 1:
        s = lines[0]
        if s == "*":
            return '<div class="ms-asterisk">*</div>'
        if s.startswith("❖"):
            return f'<div class="ms-ornament-heading">{style_inline_verbatim(s)}</div>'
        if STANDALONE_HEADING_RE.match(s):
            return f'<h3 class="ms-subheading">{html.escape(s, quote=False)}</h3>'

    # 8. Reflowed prose paragraphs (preserving 100% of words/characters verbatim, splitting on structural openers)
    paras: List[Tuple[str, List[str]]] = []
    cur_lines: List[str] = []

    def flush_cur() -> None:
        nonlocal cur_lines
        if cur_lines:
            paras.append(("p", cur_lines))
            cur_lines = []

    for ln in lines:
        if ln == "*":
            flush_cur()
            paras.append(("ast", [ln]))
        elif ln.startswith("❖"):
            flush_cur()
            paras.append(("orn", [ln]))
        elif STANDALONE_HEADING_RE.match(ln):
            flush_cur()
            paras.append(("h3", [ln]))
        elif cur_lines and NEW_PARA_START_RE.match(ln):
            flush_cur()
            cur_lines.append(ln)
        else:
            cur_lines.append(ln)
    flush_cur()

    rendered: List[str] = []
    for kind, plines in paras:
        joined = " ".join(plines)
        if kind == "ast":
            rendered.append('<div class="ms-asterisk">*</div>')
        elif kind == "orn":
            rendered.append(f'<div class="ms-ornament-heading">{style_inline_verbatim(joined)}</div>')
        elif kind == "h3":
            rendered.append(f'<h3 class="ms-subheading">{html.escape(joined, quote=False)}</h3>')
        else:
            rendered.append(f'<p class="ms-para">{style_inline_verbatim(joined)}</p>')
    return "\n".join(rendered)


def render_figure_html(fig: FigureSpec, fig_dir: Path, folio_str: Optional[str]) -> str:
    img_uri = (fig_dir / f"{fig.fig_id}.jpg").resolve().as_uri()
    folio_part = f" · Folio {folio_str}" if folio_str else ""
    return (
        f'<figure class="ms-figure ms-fig-{fig.size_class}" id="{fig.fig_id}">'
        f'<div class="ms-fig-frame"><img src="{img_uri}" alt="Figure {fig.fig_num}"></div>'
        f'<figcaption class="ms-figcaption">'
        f'<strong>Figure {fig.fig_num}</strong> (Scan Page {fig.page}{folio_part}): '
        f'{html.escape(fig.caption, quote=False)}'
        f'</figcaption>'
        f'</figure>'
    )


# ── Crop Extraction ──────────────────────────────────────────────────────────

def extract_all_figures(scans_dir: Path, fig_dir: Path) -> None:
    fig_dir.mkdir(parents=True, exist_ok=True)
    by_page: Dict[int, List[FigureSpec]] = {}
    for f in FIGURES:
        by_page.setdefault(f.page, []).append(f)

    for page_no, specs in sorted(by_page.items()):
        pdf_path = scans_dir / f"page-{page_no:03d}.pdf"
        doc = pymupdf.open(pdf_path)
        pix = doc[0].get_pixmap(dpi=300)
        im = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        doc.close()
        w, h = im.size
        for spec in specs:
            x0, y0, x1, y1 = spec.crop
            crop = im.crop((int(w * x0), int(h * y0), int(w * x1), int(h * y1)))
            crop = ImageOps.autocontrast(crop, cutoff=0.5)
            crop = ImageEnhance.Contrast(crop).enhance(1.12)
            crop = crop.filter(ImageFilter.UnsharpMask(radius=1.0, percent=110, threshold=3))
            crop.save(fig_dir / f"{spec.fig_id}.jpg", "JPEG", quality=92, optimize=True)


# ── CSS & Full Book HTML Builder ─────────────────────────────────────────────

BOOK_CSS = r"""
@page {
  size: A4 portrait;
  margin: 22mm 20mm 21mm 20mm;
}
@page :first {
  margin: 0mm;
}

* {
  box-sizing: border-box;
}

html, body {
  margin: 0;
  padding: 0;
  font-family: 'Cambria', 'Times New Roman', 'Segoe UI Symbol', 'Segoe UI Historic', serif;
  font-size: 10.5pt;
  line-height: 1.56;
  color: #1f1a15;
  background: #ffffff;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}

a {
  color: inherit;
  text-decoration: none;
}

/* ── Cover Page ── */
.cover-page {
  width: 210mm;
  height: 296.5mm;
  padding: 18mm;
  background: #fbf8f1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  page-break-after: always;
  break-after: page;
}
.cover-outer-frame {
  width: 100%;
  height: 100%;
  border: 2.2pt solid #7a5829;
  padding: 4.5mm;
  display: flex;
}
.cover-inner-frame {
  width: 100%;
  height: 100%;
  border: 0.8pt solid #b49363;
  padding: 16mm 14mm;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: center;
  text-align: center;
  background: radial-gradient(circle at center, #fffdf8 0%, #f7f0e2 100%);
}
.cover-kicker {
  font-size: 9pt;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: #7a5829;
  font-weight: 700;
}
.cover-arabic {
  font-family: 'Traditional Arabic', 'Aldhabi', 'Segoe UI', serif;
  font-size: 32pt;
  line-height: 1.25;
  color: #5c3d16;
  margin: 4mm 0 2mm 0;
  direction: rtl;
}
.cover-title {
  font-size: 25pt;
  line-height: 1.18;
  font-weight: 700;
  color: #21180f;
  margin: 2mm 0;
  letter-spacing: 0.02em;
}
.cover-subtitle {
  font-size: 13pt;
  font-style: italic;
  color: #5a4630;
  margin: 1mm 0 6mm 0;
}
.cover-rule {
  width: 68mm;
  height: 1pt;
  background: linear-gradient(90deg, transparent, #8c6632, transparent);
  margin: 4mm auto;
}
.cover-author {
  font-size: 12pt;
  color: #2b2117;
  font-weight: 700;
}
.cover-author-dates {
  font-size: 10pt;
  color: #6b5740;
  margin-top: 1mm;
}
.cover-edition-box {
  margin-top: 6mm;
  padding: 6mm 9mm;
  border-top: 0.75pt solid #cdb58e;
  border-bottom: 0.75pt solid #cdb58e;
  background: rgba(255, 255, 255, 0.65);
  max-width: 132mm;
}
.cover-edition-title {
  font-size: 10.5pt;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: #6a481c;
  margin-bottom: 2mm;
}
.cover-edition-desc {
  font-size: 9.6pt;
  line-height: 1.48;
  color: #3d3124;
}
.cover-footer {
  font-size: 8.8pt;
  color: #6b5842;
  line-height: 1.45;
}

/* ── Front Matter Sections ── */
.front-section {
  page-break-after: always;
  break-after: page;
}
.fm-title {
  font-size: 16pt;
  font-weight: 700;
  color: #5c3d16;
  border-bottom: 1.2pt solid #b49363;
  padding-bottom: 2.5mm;
  margin: 0 0 5mm 0;
  letter-spacing: 0.03em;
}
.fm-subtitle {
  font-size: 9.8pt;
  font-style: italic;
  color: #6b5842;
  margin: -3mm 0 5mm 0;
}
.editorial-card {
  background: #fbf8f2;
  border: 0.75pt solid #ded1bc;
  border-left: 3pt solid #8c6632;
  padding: 4mm 5mm;
  margin-bottom: 4.5mm;
  border-radius: 2px;
}
.editorial-card h3 {
  margin: 0 0 1.5mm 0;
  font-size: 10.5pt;
  color: #5c3d16;
}
.editorial-card p {
  margin: 0;
  font-size: 9.6pt;
  line-height: 1.48;
  color: #2c241c;
}
.meta-grid {
  width: 100%;
  border-collapse: collapse;
  margin-top: 3mm;
  font-size: 9.3pt;
}
.meta-grid td {
  padding: 2mm 3mm;
  border-bottom: 0.5pt solid #e3d9c8;
  vertical-align: top;
}
.meta-grid td:first-child {
  width: 44mm;
  font-weight: 700;
  color: #5c3d16;
}

/* ── Table of Contents & Index of Figures ── */
.toc-part-block {
  margin-bottom: 4mm;
}
.toc-part-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  background: #f5efe3;
  border-left: 2.5pt solid #7a5829;
  padding: 1.6mm 3mm;
  margin: 2.5mm 0 1.5mm 0;
  font-weight: 700;
  font-size: 9.8pt;
  color: #3a2813;
  break-after: avoid;
}
.toc-part-sub {
  font-size: 8.5pt;
  font-style: italic;
  color: #6a5842;
  margin: 0 0 1.5mm 3.5mm;
  break-after: avoid;
}
.toc-row {
  display: flex;
  align-items: baseline;
  font-size: 8.9pt;
  line-height: 1.42;
  padding: 0.35mm 1mm 0.35mm 3.5mm;
  color: #261e16;
  break-inside: avoid;
  page-break-inside: avoid;
}
.toc-row:nth-child(even) {
  background: #fcfaf6;
}
.toc-badge {
  flex: 0 0 28mm;
  white-space: nowrap;
  font-size: 8.1pt;
  font-weight: 700;
  color: #7a5829;
}
.toc-label {
  flex: 1 1 auto;
  padding-right: 2mm;
}
.toc-fig-tag {
  font-size: 7.6pt;
  color: #845920;
  background: #f3ead8;
  padding: 0 1.5mm;
  border-radius: 2px;
  margin-left: 1.5mm;
  font-style: normal;
}
.toc-dots {
  flex: 0 1 12mm;
  border-bottom: 0.5pt dotted #c5b69e;
  margin: 0 1.5mm;
}
.toc-pnum {
  flex: 0 0 9mm;
  text-align: right;
  font-weight: 700;
  color: #4a351b;
  font-variant-numeric: tabular-nums;
}

/* ── Thematic Part Dividers in Body ── */
.part-banner {
  margin: 2mm 0 5mm 0;
  padding: 4.5mm 6mm;
  background: linear-gradient(180deg, #faf5ea 0%, #f2e8d5 100%);
  border-top: 1.8pt solid #7a5829;
  border-bottom: 1pt solid #b49363;
  text-align: center;
  break-inside: avoid;
  break-after: avoid;
}
.part-banner-break {
  page-break-before: always;
  break-before: page;
}
.part-kicker {
  font-size: 8.3pt;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #7a5829;
}
.part-title {
  font-size: 13.5pt;
  font-weight: 700;
  color: #281c0f;
  margin: 1mm 0;
}
.part-subtitle {
  font-size: 9.2pt;
  font-style: italic;
  color: #5e4b35;
}

/* ── Manuscript Page Section ── */
.ms-page {
  margin-bottom: 6.5mm;
}
.ms-page-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 4mm;
  padding: 1.8mm 3mm;
  margin: 4.5mm 0 2.8mm 0;
  background: #f7f2e7;
  border-top: 1pt solid #bfa274;
  border-bottom: 0.5pt solid #d8c6a8;
  border-left: 3pt solid #7a5829;
  break-inside: avoid;
  break-after: avoid;
}
.ms-page-num {
  font-size: 8.6pt;
  font-weight: 700;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: #6a481c;
  white-space: nowrap;
}
.ms-page-title {
  font-size: 9.5pt;
  font-weight: 700;
  font-style: italic;
  color: #3b2c1c;
  text-align: right;
}

/* ── Verbatim Text Typography ── */
.ms-folio-line {
  text-align: center;
  font-size: 9.2pt;
  font-weight: 700;
  color: #7a5c38;
  margin: 0.5mm 0 2.5mm 0;
  letter-spacing: 0.06em;
  break-after: avoid;
}
.ms-blank-notice {
  text-align: center;
  font-size: 9pt;
  font-style: italic;
  color: #7d7061;
  background: #faf8f4;
  border: 0.5pt dashed #d4c7b2;
  padding: 2.5mm;
  margin: 1.5mm 0;
}
.ms-para {
  margin: 0 0 2.6mm 0;
  text-align: justify;
  hyphens: auto;
  orphans: 2;
  widows: 2;
}
.ms-rubric {
  color: #6e3518;
  font-weight: 700;
}
.ms-inline-chap {
  color: #5c3414;
  font-weight: 700;
  background: #f5ede0;
  padding: 0 1.2mm;
  border-radius: 1.5px;
}
.ms-unclear {
  font-size: 8.7pt;
  font-style: italic;
  color: #695c4e;
  background: #f5f1e8;
  padding: 0.1mm 1.2mm;
  border-radius: 2px;
}
.ms-subheading {
  font-size: 10.6pt;
  font-weight: 700;
  color: #5c3414;
  margin: 3.5mm 0 1.8mm 0;
  padding-left: 2.5mm;
  border-left: 2pt solid #b49363;
  break-after: avoid;
}
.ms-ornament-heading {
  text-align: center;
  font-size: 10.3pt;
  font-weight: 700;
  color: #6a481c;
  margin: 2.5mm 0 2mm 0;
  break-after: avoid;
}
.ms-asterisk {
  text-align: center;
  font-size: 11pt;
  font-weight: 700;
  color: #8c6632;
  margin: 1.8mm 0;
  break-after: avoid;
}
.ms-prelim-box {
  background: #fcfaf5;
  border: 0.6pt solid #dfd3be;
  padding: 3mm 4.5mm;
  margin: 2mm 0;
  font-size: 9.8pt;
}
.ms-title-leaf-box {
  background: #fbf7ee;
  border: 1pt solid #c9b089;
  padding: 4.5mm 6mm;
  margin: 2.5mm 0;
  text-align: center;
}
.ms-imprint-line {
  margin: 0.8mm 0;
}
.ms-diagram-callout {
  background: #faf6ed;
  border: 0.6pt solid #dfd1b8;
  border-left: 2.2pt solid #9d7a46;
  padding: 2.5mm 4mm;
  margin: 2.2mm 0;
  font-size: 9.2pt;
  line-height: 1.42;
}

/* ── Pipe Grids / Magic Squares (Awfāq) ── */
.ms-table-wrap {
  margin: 3mm 0;
  display: flex;
  justify-content: center;
  break-inside: avoid;
}
.ms-table {
  border-collapse: collapse;
  background: #fffdf9;
  border: 1.1pt solid #6b4e29;
  font-size: 9.2pt;
  line-height: 1.3;
}
.ms-table td {
  border: 0.6pt solid #9c825d;
  padding: 1.4mm 2.6mm;
  text-align: center;
  vertical-align: middle;
  font-variant-numeric: tabular-nums;
}
.ms-table-dense {
  font-size: 7.7pt;
  width: 100%;
}
.ms-table-dense td {
  padding: 1mm 1.1mm;
}
.ms-empty-cell {
  background: #f7f2e8;
}

/* ── Page 84 99-Names Grid Concordance ── */
.ms-names-row-block {
  margin: 2mm 0;
  border: 0.6pt solid #dcd0ba;
  background: #fcfaf5;
  padding: 2mm 3mm;
  break-inside: avoid;
}
.ms-row-badge {
  font-size: 8.6pt;
  font-weight: 700;
  color: #6a481c;
  margin-bottom: 1.2mm;
  border-bottom: 0.5pt solid #e5dac7;
  padding-bottom: 0.6mm;
}
.ms-names-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1.2mm 2.5mm;
  font-size: 8.8pt;
  line-height: 1.32;
}
.ms-name-cell {
  padding: 0.6mm 1mm;
  background: #ffffff;
  border: 0.4pt solid #e8dfd0;
  border-radius: 1.5px;
}

/* ── Preserved 300-DPI Manuscript Figures ── */
.ms-figure {
  margin: 3.5mm auto;
  text-align: center;
  break-inside: avoid;
  page-break-inside: avoid;
}
.ms-fig-frame {
  display: inline-block;
  padding: 1.6mm;
  background: #fbf7ef;
  border: 0.8pt solid #baa077;
  box-shadow: 0 0.5mm 1.5mm rgba(0, 0, 0, 0.06);
}
.ms-fig-frame img {
  display: block;
  width: auto;
  height: auto;
}
.ms-fig-sm .ms-fig-frame img {
  max-width: 68mm;
  max-height: 62mm;
}
.ms-fig-md .ms-fig-frame img {
  max-width: 112mm;
  max-height: 98mm;
}
.ms-fig-lg .ms-fig-frame img {
  max-width: 156mm;
  max-height: 118mm;
}
.ms-fig-tall .ms-fig-frame img {
  max-width: 78mm;
  max-height: 132mm;
}
.ms-fig-plate .ms-fig-frame img {
  max-width: 136mm;
  max-height: 112mm;
}
.ms-figcaption {
  margin: 1.6mm auto 0 auto;
  max-width: 152mm;
  font-size: 8.5pt;
  line-height: 1.38;
  color: #544432;
  font-style: italic;
}
.ms-figcaption strong {
  font-style: normal;
  color: #5c3d16;
}
"""


def build_html_document(
    pages_data: List[dict],
    fig_dir: Path,
    page_map: Optional[Dict[str, int]] = None,
) -> Tuple[str, Dict[int, List[str]]]:
    """Build complete HTML book and return (html_string, per_page_verbatim_blocks)."""
    figs_by_page: Dict[int, List[FigureSpec]] = {}
    for f in FIGURES:
        figs_by_page.setdefault(f.page, []).append(f)

    part_by_start: Dict[int, PartSpec] = {pt.start_page: pt for pt in PARTS}
    page_map = page_map or {}

    def fmt_pg(key: str) -> str:
        val = page_map.get(key)
        return str(val) if val is not None else "—"

    end_page = pages_data[-1]["page"]

    # Precompute folios & titles
    folios: Dict[int, Optional[str]] = {}
    for item in pages_data:
        pno = item["page"]
        en = item["en"]
        first_ln = en.splitlines()[0] if en else ""
        folios[pno] = detect_folio_number(pno, first_ln)

    # 1. Cover Page
    cover_html = f"""
    <div class="cover-page">
      <div class="cover-outer-frame">
        <div class="cover-inner-frame">
          <div class="cover-kicker">Classical Arabic Esoteric &amp; Cosmological Compendium · Part One</div>
          <div>
            <div class="cover-arabic">شَمْسُ الْمَعَارِفِ الْكُبْرَى وَلَطَائِفُ الْعَوَارِفِ</div>
            <div class="cover-title">Shams al-Maʿārif al-Kubrā</div>
            <div class="cover-subtitle">The Great Sun of Gnoses and the Subtleties of Elevated Things</div>
            <div class="cover-rule"></div>
            <div class="cover-author">Shaykh Aḥmad ibn ʿAlī al-Būnī</div>
            <div class="cover-author-dates">d. 622 AH / 1225 CE</div>
          </div>
          <div class="cover-edition-box">
            <div class="cover-edition-title">Verbatim English Edition · Physical Pages 1–{end_page}</div>
            <div class="cover-edition-desc">
              Unabridged, word-for-word English translation aligned to the canonical Arabic witness
              (Printed Folios 1–86), preserving all <strong>{len([f for f in FIGURES if f.page <= end_page])} original manuscript diagrams</strong>,
              concentric circles (<em>dawāʾir</em>), magic squares (<em>awfāq</em>), talismanic seals (<em>khawātim</em>),
              and lunar-mansion star-cluster asterisms at 300 DPI.
            </div>
          </div>
          <div class="cover-footer">
            Source Witness: McGill University Islamic Studies Library · RBSC Islamic BF 1410 B8 1927<br>
            Imprint of Muṣṭafā al-Bābī al-Ḥalabī and His Sons, Cairo · Translation Alignment V2 Corpus
          </div>
        </div>
      </div>
    </div>
    """

    # 2. Editorial & Provenance Page
    editorial_html = f"""
    <section class="front-section" id="editorial-note">
      <h1 class="fm-title">Editorial &amp; Reader's Guide</h1>
      <div class="fm-subtitle">Provenance, Verbatim Fidelity, Preserved Diagrams, and Dual Pagination</div>

      <div class="editorial-card">
        <h3>1. Complete Verbatim Preservation</h3>
        <p>
          Every English page in this volume reproduces <strong>100% verbatim</strong> the independently reviewed
          and committed English translation layer of the <em>Translation Alignment V2</em> campaign
          (<code>ocr/enriched_en/page_001.txt</code> through <code>page_{end_page:03d}.txt</code>).
          No sentences, qualifiers, invocations, divine names, numerical table entries, printed folio markers,
          blank-leaf notices (<code>[NO VISIBLE TEXT]</code>), or philological annotations (<code>[UNCLEAR: ...]</code>)
          have been omitted, abridged, or paraphrased.
        </p>
      </div>

      <div class="editorial-card">
        <h3>2. Preservation of Manuscript Diagrams, Magic Squares &amp; Star Asterisms</h3>
        <p>
          Plain-text OCR files cannot convey the spatial geometry of al-Būnī's concentric celestial wheels
          (<em>dawāʾir</em>), radial archangelic inscriptions, multi-chambered talismanic panels, magic squares
          (<em>awfāq</em>), circular seals (<em>khawātim</em>), or the inline star-dot constellation asterisms of the
          twenty-eight lunar mansions. All <strong>{len([f for f in FIGURES if f.page <= end_page])} visual figures and plates</strong>
          across Physical Pages 1–{end_page} have been extracted directly from the 300-DPI archival scans
          and anchored beside their corresponding passages.
        </p>
      </div>

      <div class="editorial-card">
        <h3>3. Typography &amp; Dual Pagination</h3>
        <p>
          Soft-wrapped OCR prose lines are joined into justified book paragraphs while preserving structural
          headings, liturgical lines, and tables intact. Inline editorial notes (<code>[UNCLEAR: ...]</code>)
          appear verbatim in smaller italic type so continuous reading remains effortless. Every manuscript page
          carries a milestone banner citing both its <strong>Physical Scan Page (1–{end_page})</strong> and its
          <strong>Printed Cairo Folio</strong>, while sequential <strong>PDF Page Numbers</strong> appear in the
          running footer and Table of Contents.
        </p>
      </div>

      <table class="meta-grid">
        <tr><td>Source Manuscript</td><td><em>Shams al-Maʿārif al-Kubrā wa Laṭāʾif al-ʿAwārif</em> (4 parts in 1 vol., Cairo: Muṣṭafā al-Bābī al-Ḥalabī, 1927; McGill Library RBSC Islamic BF 1410 B8 1927)</td></tr>
        <tr><td>Completed Scope</td><td>Physical Scan Pages 1–{end_page} of 604 (Printed Folios 1–86; all committed V2 pages in job <code>local-43c73d83…</code>)</td></tr>
        <tr><td>Terminology Standard</td><td>IJMES Latin transliteration in target prose; Divine and Prophetic honorifics preserved per <code>docs/translation-style-v2.md</code></td></tr>
        <tr><td>Visual Plates &amp; Figures</td><td>{len([f for f in FIGURES if f.page <= end_page])} high-resolution 300-DPI archival crops embedded in situ</td></tr>
      </table>
    </section>
    """

    # 3. Table of Contents (Grouped by Thematic Part, listing all 92 Scan Pages)
    toc_parts_html: List[str] = [
        '<section class="front-section" id="table-of-contents">',
        '<h1 class="fm-title">Table of Contents</h1>',
        f'<div class="fm-subtitle">Thematic Parts &amp; Complete Page-by-Page Concordance (Scan Pages 1–{end_page})</div>',
    ]
    p_lookup = {d["page"]: d for d in pages_data}
    for pt in PARTS:
        if pt.start_page > end_page:
            continue
        actual_end = min(pt.end_page, end_page)
        toc_parts_html.append('<div class="toc-part-block">')
        toc_parts_html.append(
            f'<a href="#part-{pt.part_num}" class="toc-part-header">'
            f'<span>Part {pt.part_num} — {html.escape(pt.title, quote=False)} (Scan pp. {pt.start_page}–{actual_end})</span>'
            f'<span class="toc-pnum">{fmt_pg(f"PART:{pt.part_num}")}</span>'
            f'</a>'
            f'<div class="toc-part-sub">{html.escape(pt.subtitle, quote=False)}</div>'
        )
        for pno in range(pt.start_page, actual_end + 1):
            if pno not in p_lookup:
                continue
            d = p_lookup[pno]
            fol = folios.get(pno)
            fol_lbl = f" · Fol. {fol}" if fol else ""
            p_figs = figs_by_page.get(pno, [])
            fig_badge = ""
            if p_figs:
                nums = ", ".join(str(f.fig_num) for f in p_figs)
                fig_badge = f'<span class="toc-fig-tag">Fig. {nums}</span>'
            toc_parts_html.append(
                f'<a href="#ms-page-{pno:03d}" class="toc-row">'
                f'<span class="toc-badge">Scan p. {pno:03d}{fol_lbl}</span>'
                f'<span class="toc-label">{html.escape(d["title"], quote=False)}{fig_badge}</span>'
                f'<span class="toc-dots"></span>'
                f'<span class="toc-pnum">{fmt_pg(f"MS:{pno:03d}")}</span>'
                f'</a>'
            )
        toc_parts_html.append("</div>")
    toc_parts_html.append("</section>")

    # 4. List of Figures
    lof_html: List[str] = [
        '<section class="front-section" id="list-of-figures">',
        '<h1 class="fm-title">Index of Preserved Manuscript Diagrams &amp; Plates</h1>',
        '<div class="fm-subtitle">Original Circles (Dawāʾir), Magic Squares (Awfāq), Seals (Khawātim), Star Asterisms &amp; Imprints</div>',
    ]
    for fig in FIGURES:
        if fig.page > end_page:
            continue
        fol = folios.get(fig.page)
        fol_lbl = f" (Fol. {fol})" if fol else ""
        lof_html.append(
            f'<a href="#{fig.fig_id}" class="toc-row">'
            f'<span class="toc-badge">Figure {fig.fig_num:02d} · p. {fig.page:03d}</span>'
            f'<span class="toc-label">{html.escape(fig.caption, quote=False)}{fol_lbl}</span>'
            f'<span class="toc-dots"></span>'
            f'<span class="toc-pnum">{fmt_pg(f"FIG:{fig.fig_num:03d}")}</span>'
            f'</a>'
        )
    lof_html.append("</section>")

    # 5. Body Pages (1..end_page)
    body_parts: List[str] = []
    emitted_blocks: Dict[int, List[str]] = {}

    for d in pages_data:
        pno = d["page"]
        en_text = d["en"]
        title_en = d["title"]
        fol = folios.get(pno)

        if pno in part_by_start:
            pt = part_by_start[pno]
            actual_end = min(pt.end_page, end_page)
            brk_cls = " part-banner-break" if pno > 1 else ""
            body_parts.append(
                f'<div class="part-banner{brk_cls}" id="part-{pt.part_num}">'
                f'<div class="part-kicker">Part {pt.part_num} · Scan Pages {pt.start_page}–{actual_end}</div>'
                f'<div class="part-title">{html.escape(pt.title, quote=False)}</div>'
                f'<div class="part-subtitle">{html.escape(pt.subtitle, quote=False)}</div>'
                f'</div>'
            )

        fol_header = f" · Printed Folio {fol}" if fol else " · Unnumbered Preliminary Leaf"
        body_parts.append(f'<section class="ms-page" id="ms-page-{pno:03d}">')
        body_parts.append(
            f'<div class="ms-page-header">'
            f'<span class="ms-page-num">Scan Page {pno:03d}{fol_header}</span>'
            f'<span class="ms-page-title">{html.escape(title_en, quote=False)}</span>'
            f'</div>'
        )

        blocks = split_raw_blocks(en_text)
        emitted_blocks[pno] = blocks
        p_figs = figs_by_page.get(pno, [])

        # Figures anchored before block 0 (after_block == -1)
        for fg in p_figs:
            if fg.after_block < 0:
                body_parts.append(render_figure_html(fg, fig_dir, fol))

        last_idx = max(0, len(blocks) - 1)
        for b_idx, blk in enumerate(blocks):
            blk_html = render_block_html(pno, b_idx, blk)
            body_parts.append(f'<div class="ms-verbatim-chunk" data-ms-page="{pno}">{blk_html}</div>')
            for fg in p_figs:
                if fg.after_block >= 0 and min(fg.after_block, last_idx) == b_idx:
                    body_parts.append(render_figure_html(fg, fig_dir, fol))

        body_parts.append("</section>")

    full_html = (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n"
        "<meta charset=\"UTF-8\">\n"
        f"<title>Shams al-Ma'arif al-Kubra — Verbatim English Edition (Pages 1–{end_page})</title>\n"
        f"<style>{BOOK_CSS}</style>\n"
        "</head>\n<body>\n"
        + cover_html
        + editorial_html
        + "\n".join(toc_parts_html)
        + "\n".join(lof_html)
        + "\n".join(body_parts)
        + "\n</body>\n</html>\n"
    )
    return full_html, emitted_blocks


# ── Browser PDF Rendering, Probe Discovery & Post-Processing ─────────────────

def find_browser_exe() -> str:
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        str(Path.home() / "AppData/Local/hermes/tools/chromium-1208/chrome-win64/chrome.exe"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    raise FileNotFoundError("No Chromium/Chrome/Edge browser executable found for PDF rendering.")


def render_html_to_pdf(browser_exe: str, html_path: Path, pdf_path: Path) -> None:
    cmd = [
        browser_exe,
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--no-pdf-header-footer",
        "--print-to-pdf-no-header",
        f"--print-to-pdf={pdf_path.resolve()}",
        html_path.resolve().as_uri(),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if not pdf_path.exists() or pdf_path.stat().st_size < 1024:
        raise RuntimeError(f"Browser PDF render failed (rc={res.returncode}): {res.stderr}")


PART_BANNER_RE = re.compile(r"P\s*a\s*r\s*t\s+([IVX]+)\s*·\s*S\s*c\s*a\s*n", re.IGNORECASE)
MS_BANNER_RE = re.compile(r"Scan\s+Page\s+(\d{3})\s*·\s*(?:Printed\s+Folio|Unnumbered)", re.IGNORECASE)
FIG_CAPTION_RE = re.compile(r"Figure\s+(\d{1,3})\s*\(Scan\s+Page\s+\d+", re.IGNORECASE)


def extract_probe_map(pdf_path: Path) -> Tuple[Dict[str, int], Dict[int, List[int]], int]:
    """Return (key -> 1-based PDF page, pdf_page -> list of MS scan pages on/active on that PDF page, total_pages)."""
    doc = pymupdf.open(pdf_path)
    probe_map: Dict[str, int] = {}
    ms_on_pdf_page: Dict[int, List[int]] = {}
    current_ms: Optional[int] = None

    for idx in range(len(doc)):
        pno_1 = idx + 1
        norm = re.sub(r"\s+", " ", doc[idx].get_text("text"))
        if "Provenance, Verbatim Fidelity, Preserved Diagrams" in norm and "SEC:EDITORIAL" not in probe_map:
            probe_map["SEC:EDITORIAL"] = pno_1
        if "Thematic Parts & Complete Page-by-Page Concordance" in norm and "SEC:TOC" not in probe_map:
            probe_map["SEC:TOC"] = pno_1
        if "Original Circles (Daw" in norm and "SEC:LOF" not in probe_map:
            probe_map["SEC:LOF"] = pno_1

        for pm in PART_BANNER_RE.finditer(norm):
            pkey = f"PART:{pm.group(1).upper()}"
            probe_map.setdefault(pkey, pno_1)

        found_ms_here: List[int] = []
        for mm in MS_BANNER_RE.finditer(norm):
            m_str = mm.group(1)
            mkey = f"MS:{m_str}"
            probe_map.setdefault(mkey, pno_1)
            ms_num = int(m_str)
            found_ms_here.append(ms_num)
            current_ms = ms_num

        for fm in FIG_CAPTION_RE.finditer(norm):
            fkey = f"FIG:{int(fm.group(1)):03d}"
            probe_map.setdefault(fkey, pno_1)

        if found_ms_here:
            ms_on_pdf_page[pno_1] = found_ms_here
        elif current_ms is not None:
            ms_on_pdf_page[pno_1] = [current_ms]

    total = len(doc)
    doc.close()
    return probe_map, ms_on_pdf_page, total


def stamp_headers_footers_and_bookmarks(
    pdf_in: Path,
    pdf_out: Path,
    probe_map: Dict[str, int],
    ms_on_pdf_page: Dict[int, List[int]],
    pages_data: List[dict],
) -> None:
    doc = pymupdf.open(pdf_in)
    total_pages = len(doc)
    end_ms = pages_data[-1]["page"]
    p_lookup = {d["page"]: d for d in pages_data}

    folios: Dict[int, Optional[str]] = {}
    for d in pages_data:
        first_ln = d["en"].splitlines()[0] if d["en"] else ""
        folios[d["page"]] = detect_folio_number(d["page"], first_ln)

    body_start_pdf = probe_map.get("MS:001", 9999)
    toc_pdf = probe_map.get("SEC:TOC", 3)
    lof_pdf = probe_map.get("SEC:LOF", 4)

    header_color = (0.42, 0.31, 0.18)
    rule_color = (0.76, 0.65, 0.48)

    for idx in range(total_pages):
        pno_1 = idx + 1
        if pno_1 == 1:
            continue  # Cover page stays clean

        page = doc[idx]
        rect = page.rect  # A4: ~595.28 x 841.89 pt
        left_x = 56.7     # 20mm
        right_x = rect.width - 56.7

        # Determine right running header label
        if pno_1 < toc_pdf:
            right_label = "Editorial & Reader's Guide"
        elif pno_1 < lof_pdf:
            right_label = "Table of Contents"
        elif pno_1 < body_start_pdf:
            right_label = "Index of Manuscript Diagrams & Plates"
        else:
            ms_list = ms_on_pdf_page.get(pno_1, [])
            if len(ms_list) == 1:
                m = ms_list[0]
                fol = folios.get(m)
                fol_s = f" · Folio {fol}" if fol else ""
                t_short = p_lookup[m]["title"]
                if len(t_short) > 46:
                    t_short = t_short[:44].rstrip() + "…"
                right_label = f"Scan p. {m:03d}{fol_s} — {t_short}"
            elif len(ms_list) > 1:
                m0, m1 = ms_list[0], ms_list[-1]
                right_label = f"Scan Pages {m0:03d}–{m1:03d}"
            else:
                right_label = ""

        # Draw top header text & hairline rule
        header_y = 34.0
        rule_top_y = 39.5
        page.insert_text(
            (left_x, header_y),
            "Shams al-Ma'arif al-Kubra — Verbatim English Edition",
            fontsize=8.0,
            fontname="tiit",
            color=header_color,
        )
        if right_label:
            # ASCII-safe fallback check for Base14 Times-Roman; use insert_htmlbox for full Unicode diacritics!
            hdr_box = pymupdf.Rect(left_x + 215, 23.0, right_x, 38.5)
            page.insert_htmlbox(
                hdr_box,
                f'<div style="font-family: Cambria, Times New Roman, serif; font-size: 8pt; '
                f'color: #6b4f2e; text-align: right;">{html.escape(right_label, quote=False)}</div>',
            )
        page.draw_line((left_x, rule_top_y), (right_x, rule_top_y), color=rule_color, width=0.45)

        # Draw bottom footer hairline rule & page number
        rule_bot_y = rect.height - 39.0
        page.draw_line((left_x, rule_bot_y), (right_x, rule_bot_y), color=rule_color, width=0.45)
        ftr_box = pymupdf.Rect(left_x, rect.height - 36.5, right_x, rect.height - 20.0)
        page.insert_htmlbox(
            ftr_box,
            f'<div style="font-family: Cambria, Times New Roman, serif; font-size: 8.5pt; '
            f'color: #5c4528; text-align: center;">Page {pno_1} of {total_pages}</div>',
        )

    # Build Hierarchical PDF Bookmarks (Outline)
    toc: List[List] = [
        [1, "Cover — Shams al-Maʿārif al-Kubrā (Pages 1–92)", 1],
        [1, "Editorial & Reader's Guide", probe_map.get("SEC:EDITORIAL", 2)],
        [1, "Table of Contents", probe_map.get("SEC:TOC", 3)],
        [1, "Index of Manuscript Diagrams & Plates", probe_map.get("SEC:LOF", 4)],
    ]
    figs_by_page: Dict[int, List[FigureSpec]] = {}
    for f in FIGURES:
        figs_by_page.setdefault(f.page, []).append(f)

    for pt in PARTS:
        if pt.start_page > end_ms:
            continue
        actual_end = min(pt.end_page, end_ms)
        pt_pg = probe_map.get(f"PART:{pt.part_num}", probe_map.get(f"MS:{pt.start_page:03d}", 1))
        toc.append([1, f"Part {pt.part_num}: {pt.title} (pp. {pt.start_page}–{actual_end})", pt_pg])
        for pno in range(pt.start_page, actual_end + 1):
            if pno not in p_lookup:
                continue
            d = p_lookup[pno]
            fol = folios.get(pno)
            fol_s = f" [Fol. {fol}]" if fol else ""
            ms_pg = probe_map.get(f"MS:{pno:03d}", pt_pg)
            toc.append([2, f"Scan Page {pno:03d}{fol_s}: {d['title']}", ms_pg])
            for fg in figs_by_page.get(pno, []):
                fg_pg = probe_map.get(f"FIG:{fg.fig_num:03d}", ms_pg)
                toc.append([3, f"Figure {fg.fig_num}: {fg.caption[:72]}", fg_pg])

    doc.set_toc(toc)
    doc.set_metadata({
        "title": f"Shams al-Ma'arif al-Kubra — Verbatim English Edition (Pages 1–{end_ms})",
        "author": "Ahmad ibn Ali al-Buni (Translation Alignment V2 Corpus)",
        "subject": f"Unabridged verbatim English translation of physical pages 1–{end_ms} with 300-DPI manuscript diagrams",
        "creator": "build_english_verbatim_pdf.py",
    })
    doc.save(pdf_out, garbage=4, deflate=True)
    doc.close()


# ── Strict Verbatim Verification ─────────────────────────────────────────────

def canonical_tokens(en_text: str) -> List[str]:
    """Tokenize canonical English text, stripping ONLY markdown pipe-table syntax (`|` and `|---|---|` rows)."""
    out_lines: List[str] = []
    for ln in en_text.splitlines():
        if is_pipe_row(ln):
            if TABLE_SEP_RE.match(ln):
                continue
            s = ln.strip()
            if s.startswith("|") and s.endswith("|"):
                s = s[1:-1]
            out_lines.append(s.replace("|", " "))
        else:
            out_lines.append(ln)
    return "\n".join(out_lines).split()


def verify_html_verbatim(pages_data: List[dict], final_html: str) -> None:
    """Prove 100.000% exact token-by-token verbatim match for every single page 1..N in rendered HTML."""
    # Extract all <div class="ms-verbatim-chunk" data-ms-page="N">...</div>
    chunk_re = re.compile(
        r'<div class="ms-verbatim-chunk" data-ms-page="(\d+)">(.*?)</div>(?=\s*(?:<div class="ms-verbatim-chunk"|<figure|</section>))',
        re.DOTALL,
    )
    by_page_html: Dict[int, List[str]] = {}
    for m in chunk_re.finditer(final_html):
        pno = int(m.group(1))
        inner = m.group(2)
        # Strip inline styling tags without adding whitespace, then block tags with space
        no_inline = re.sub(r"</?(?:span|strong)\b[^>]*>", "", inner)
        plain = html.unescape(re.sub(r"<[^>]+>", " ", no_inline))
        by_page_html.setdefault(pno, []).append(plain)

    mismatches = []
    total_tokens = 0
    for d in pages_data:
        pno = d["page"]
        expected = canonical_tokens(d["en"])
        actual = " ".join(by_page_html.get(pno, [])).split()
        total_tokens += len(expected)
        if expected != actual:
            # Find first differing index
            diff_at = next((i for i, (a, b) in enumerate(zip(expected, actual)) if a != b), min(len(expected), len(actual)))
            mismatches.append(
                f"Page {pno:03d}: expected {len(expected)} tokens vs actual {len(actual)} at idx {diff_at}: "
                f"exp={expected[max(0,diff_at-2):diff_at+3]} vs act={actual[max(0,diff_at-2):diff_at+3]}"
            )
    if mismatches:
        raise AssertionError("VERBATIM AUDIT FAILED:\n" + "\n".join(mismatches[:10]))
    print(f"[OK] Strict HTML Verbatim Audit PASSED: 100.000% exact match across {len(pages_data)} pages ({total_tokens:,} tokens, 0 diffs).")


def verify_pdf_text_presence(pdf_path: Path, pages_data: List[dict], probe_map: Dict[str, int]) -> None:
    """Verify every manuscript page's opening & closing verbatim phrases and figure captions exist in final PDF."""
    doc = pymupdf.open(pdf_path)
    body_start = probe_map["MS:001"] - 1
    full_body_text = "\n".join(doc[i].get_text("text") for i in range(body_start, len(doc)))
    norm_pdf = re.sub(r"\s+", " ", full_body_text)

    for d in pages_data:
        pno = d["page"]
        toks = canonical_tokens(d["en"])
        # Check sample phrases (first 4 tokens and last 4 tokens) allowing soft hyphenation across line breaks
        for sample in (toks[:4], toks[-4:]):
            if not sample:
                continue
            # Check each token without soft-hyphen splits
            for tok in sample:
                if len(tok) >= 4 and tok.isalpha() and tok not in norm_pdf:
                    # Could be hyphenated at line end in justified PDF text layer (e.g. "knowl- edge")
                    hy_pat = r"[\-\s]*".join(re.escape(ch) for ch in tok)
                    if not re.search(hy_pat, norm_pdf):
                        raise AssertionError(f"PDF text audit: token {tok!r} from Scan Page {pno} missing in PDF!")
    print(f"[OK] PDF Text Layer Audit PASSED: all {len(pages_data)} manuscript pages & {len(doc)} PDF pages verified.")
    doc.close()


# ── Main Entrypoint ──────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--end-page", type=int, default=None, help="Last scan page (default: highest committed page in progress.json)")
    ap.add_argument("--output", type=str, default=None, help="Output PDF path")
    args = ap.parse_args()

    prog = json.loads((REPO_ROOT / "state/translation_v2/progress.json").read_text(encoding="utf-8"))
    committed = sorted(int(k) for k, v in prog["pages"].items() if v.get("status") == "committed")
    end_page = args.end_page or committed[-1]

    ms_json = json.loads((REPO_ROOT / "web/public/manuscript.json").read_text(encoding="utf-8"))
    titles_by_page = {r["page"]: r.get("title", {}).get("en", f"Manuscript Page {r['page']}") for r in ms_json}

    pages_data: List[dict] = []
    for pno in range(1, end_page + 1):
        en_path = REPO_ROOT / f"ocr/enriched_en/page_{pno:03d}.txt"
        en_text = parse_en_file(en_path)
        if not en_text:
            raise RuntimeError(f"Empty English block on page {pno}: {en_path}")
        pages_data.append({
            "page": pno,
            "en": en_text,
            "title": titles_by_page.get(pno, f"Page {pno}"),
        })

    out_pdf = Path(args.output) if args.output else (
        REPO_ROOT / "manuscript" / f"Shams-al-Maarif-English-Verbatim-Pages-001-{end_page:03d}.pdf"
    )
    out_pdf.parent.mkdir(parents=True, exist_ok=True)

    work_dir = Path(os.environ.get("TEMP", "/tmp")) / "shams_pdf_build"
    fig_dir = work_dir / "figures"
    work_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/5] Extracting {len([f for f in FIGURES if f.page <= end_page])} manuscript figures at 300 DPI...")
    extract_all_figures(REPO_ROOT / "web/public/scans", fig_dir)

    browser_exe = find_browser_exe()
    print(f"[2/5] Using Chromium engine: {browser_exe}")

    probe_map: Dict[str, int] = {}
    ms_on_pdf_page: Dict[int, List[int]] = {}
    raw_pdf = work_dir / "pass_raw.pdf"
    html_path = work_dir / "book.html"

    for pass_no in range(1, 4):
        print(f"[3/5] Rendering layout pass {pass_no}...")
        html_str, _ = build_html_document(pages_data, fig_dir, probe_map if probe_map else None)
        if pass_no == 1:
            verify_html_verbatim(pages_data, html_str)
        html_path.write_text(html_str, encoding="utf-8")
        render_html_to_pdf(browser_exe, html_path, raw_pdf)
        new_map, ms_on_pdf_page, total_pgs = extract_probe_map(raw_pdf)
        print(f"      Pass {pass_no} total PDF pages: {total_pgs} (probes resolved: {len(new_map)})")
        if pass_no >= 2 and new_map == probe_map:
            print(f"      Pagination converged cleanly on pass {pass_no}!")
            break
        probe_map = new_map

    print("[4/5] Stamping running headers, footers, metadata, and hierarchical PDF bookmarks...")
    stamp_headers_footers_and_bookmarks(raw_pdf, out_pdf, probe_map, ms_on_pdf_page, pages_data)

    print("[5/5] Running post-build PDF verification...")
    verify_pdf_text_presence(out_pdf, pages_data, probe_map)
    size_mb = out_pdf.stat().st_size / (1024 * 1024)
    print(f"\nSUCCESS: {out_pdf} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    main()
