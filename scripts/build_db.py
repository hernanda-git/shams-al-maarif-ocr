#!/usr/bin/env python3
"""
Build a SQLite database from the chapter-grouped enriched_en files.
Provides structured access for static site generation and full-text search.

Output: ocr/shams_chapters.db
Tables:
  - chapters: metadata for each of the 40 chapters
  - pages: individual page content with chapter FK
  - fts_content: FTS5 virtual table for full-text search
"""

import os
import re
import sqlite3
from pathlib import Path

CHAPTERS_DIR = Path("/mnt/c/Working Folder/Research/shams-al-maarif-ocr/ocr/chapters_en")
ENRICHED_DIR = Path("/mnt/c/Working Folder/Research/shams-al-maarif-ocr/ocr/enriched_en")
DB_PATH      = Path("/mnt/c/Working Folder/Research/shams-al-maarif-ocr/ocr/shams_chapters.db")

# Chapter metadata (same as group_by_chapters.py)
CHAPTERS = {
    1:  {"slug": "chapter_01_letters",                "title": "The Dotted Letters",                        "subtitle": "Secrets, hidden meanings, and the foundations of speech"},
    2:  {"slug": "chapter_02_breaking_expansion_times","title": "Breaking and Expansion",                     "subtitle": "Arrangement of works in times and hours"},
    3:  {"slug": "chapter_03_lunar_mansions",          "title": "The Twenty-Eight Lunar Mansions",            "subtitle": "Rulings and celestial influences"},
    4:  {"slug": "chapter_04_zodiac_signs",            "title": "The Twelve Zodiac Signs",                    "subtitle": "Indications and connections"},
    5:  {"slug": "chapter_05_basmala_secrets",         "title": "Secrets of the Basmala",                     "subtitle": "Hidden properties and blessings"},
    6:  {"slug": "chapter_06_seclusion_retreat",       "title": "Seclusion and Retreat",                      "subtitle": "Masters of retreat leading to the upper realms"},
    7:  {"slug": "chapter_07_jesus_names",             "title": "The Names of Jesus",                         "subtitle": "By which Jesus (upon him peace) brought the dead to life"},
    8:  {"slug": "chapter_08_four_tawqifat",           "title": "The Four Tawqīfāt",                          "subtitle": "Chapters and circles"},
    9:  {"slug": "chapter_09_quran_beginnings",        "title": "Properties of Quran Beginnings",             "subtitle": "The beginnings of the Suras and the firm verses"},
    10: {"slug": "chapter_10_fatiha_secrets",          "title": "Secrets of al-Fātiḥa",                       "subtitle": "Supplications and famous properties"},
    11: {"slug": "chapter_11_inventions_lights",       "title": "Inventions and Merciful Lights",             "subtitle": "Radiant secrets of the celestial realm"},
    12: {"slug": "chapter_12_greatest_name",           "title": "The Greatest Name of Allah",                 "subtitle": "Hidden dispositions and spiritual attainments"},
    13: {"slug": "chapter_13_fatiha_omissions",        "title": "Fallen Parts of al-Fātiḥa",                 "subtitle": "Wafqs and answered supplications"},
    14: {"slug": "chapter_14_spiritual_exercises",     "title": "Spiritual Exercises",                        "subtitle": "Remembrances and answered supplications"},
    15: {"slug": "chapter_15_conditions_beginnings_endings", "title": "Conditions",                            "subtitle": "From beginnings to the suns of endings"},
    16: {"slug": "chapter_16_beautiful_names",         "title": "The Beautiful Names of Allah",               "subtitle": "Times, properties, and sub-sections for each Name"},
    17: {"slug": "chapter_17_kaf_ha_ya_ayn_sad",      "title": "Properties of Kāfiyāʿaynṣ",                  "subtitle": "Divine letters — lordly and most holy"},
    18: {"slug": "chapter_18_verse_of_throne",         "title": "Properties of the Verse of the Throne",      "subtitle": "Āyat al-Kursī and its hidden blessings"},
    19: {"slug": "chapter_19_wafqs_talismans",         "title": "Wafqs and Talismans",                        "subtitle": "Beneficial and tried"},
    20: {"slug": "chapter_20_yaseen",                  "title": "Sūrat Yā Sīn",                              "subtitle": "Answered supplications"},
    21: {"slug": "chapter_21_names_pattern_one",       "title": "The Names — First Pattern",                  "subtitle": "Supplications and dispositions"},
    22: {"slug": "chapter_22_names_pattern_two",       "title": "The Names — Second Pattern",                 "subtitle": "The Bestowed Names"},
    23: {"slug": "chapter_23_names_pattern_three",     "title": "The Names — Third Pattern",                  "subtitle": "Attributes and supports"},
    24: {"slug": "chapter_24_names_pattern_four",      "title": "The Names — Fourth Pattern",                 "subtitle": "Secrets of the Lord of the creatures"},
    25: {"slug": "chapter_25_names_pattern_five",      "title": "The Names — Fifth Pattern",                  "subtitle": "Selected secrets"},
    26: {"slug": "chapter_26_names_pattern_six",       "title": "The Names — Sixth Pattern",                  "subtitle": "Secrets of the necessitating matters"},
    27: {"slug": "chapter_27_names_pattern_seven",     "title": "The Names — Seventh Pattern",                "subtitle": "Blessings of the Names"},
    28: {"slug": "chapter_28_names_pattern_eight",     "title": "The Names — Eighth Pattern",                 "subtitle": "Beneficial secrets"},
    29: {"slug": "chapter_29_names_pattern_nine",      "title": "The Names — Ninth Pattern",                  "subtitle": "Hidden transformations"},
    30: {"slug": "chapter_30_names_pattern_ten",       "title": "The Names — Tenth Pattern",                  "subtitle": "Beneficial secrets"},
    31: {"slug": "chapter_31_arabic_letters",          "title": "Arabic Letters",                             "subtitle": "Planets, servants, minerals, and seclusions"},
    32: {"slug": "chapter_32_arod_secrets",            "title": "Secrets of the ʿArūḍ",                       "subtitle": "The immaterial thrones"},
    33: {"slug": "chapter_33_circle_encompassment",    "title": "The Circle of Encompassment",                "subtitle": "Foundations and definitions"},
    34: {"slug": "chapter_34_zayirja_science",         "title": "The Science of the Zāyirja",                "subtitle": "Proportions, zodiac, and balances"},
    35: {"slug": "chapter_35_jafr_rules",             "title": "The Lettered Hidden Thing",                  "subtitle": "By the Jafr rules"},
    36: {"slug": "chapter_36_talismanic_letters",      "title": "The Divine Overflow",                        "subtitle": "Sacred stone and properties of plants"},
    37: {"slug": "chapter_37_simia_works",             "title": "Works of Sīmiyāʾ",                           "subtitle": "All the articles and sayings"},
    38: {"slug": "chapter_38_letter_uses_retreats",    "title": "Uses of the Letters",                        "subtitle": "And their retreats upon the sentences"},
    39: {"slug": "chapter_39_beautiful_names_explanation", "title": "Explanation of the Beautiful Names",      "subtitle": "Elucidation and details"},
    40: {"slug": "chapter_40_answered_supplications",  "title": "Answered Supplications",                     "subtitle": "For all times and occasions"},
}


def extract_pages_from_file(filepath: Path) -> list[dict]:
    """Parse a chapter file back into individual pages."""
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    pages = []
    # Split on PAGE markers
    parts = re.split(r'━+\s*┃\s*PAGE\s+(\d+)\s*━+\s*', content)

    # parts[0] = before first marker (usually empty)
    # parts[1] = page number, parts[2] = content, parts[3] = page number, ...
    i = 1
    while i < len(parts) - 1:
        page_num = int(parts[i])
        page_content = parts[i + 1].strip()
        if page_content:
            pages.append({
                'page_num': page_num,
                'content': page_content,
                'content_length': len(page_content),
            })
        i += 2

    return pages


def build_database():
    """Create the SQLite database."""
    # Remove old DB
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    # Create tables
    cur.executescript('''
        CREATE TABLE chapters (
            chapter_num INTEGER PRIMARY KEY,
            slug TEXT NOT NULL,
            title TEXT NOT NULL,
            subtitle TEXT,
            page_count INTEGER DEFAULT 0,
            total_chars INTEGER DEFAULT 0,
            file_size_kb REAL DEFAULT 0
        );

        CREATE TABLE pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chapter_num INTEGER NOT NULL,
            page_num INTEGER NOT NULL,
            content TEXT NOT NULL,
            content_length INTEGER,
            has_arabic INTEGER DEFAULT 0,
            has_english INTEGER DEFAULT 0,
            FOREIGN KEY (chapter_num) REFERENCES chapters(chapter_num)
        );

        CREATE INDEX idx_pages_chapter ON pages(chapter_num);
        CREATE INDEX idx_pages_num ON pages(page_num);

        CREATE VIRTUAL TABLE fts_content USING fts5(
            page_num,
            chapter_num,
            content,
            content=pages,
            content_rowid=id
        );

        -- Triggers to keep FTS in sync
        CREATE TRIGGER pages_ai AFTER INSERT ON pages BEGIN
            INSERT INTO fts_content(rowid, page_num, chapter_num, content)
            VALUES (new.id, new.page_num, new.chapter_num, new.content);
        END;

        CREATE TRIGGER pages_ad AFTER DELETE ON pages BEGIN
            INSERT INTO fts_content(fts_content, rowid, page_num, chapter_num, content)
            VALUES('delete', old.id, old.page_num, old.chapter_num, old.content);
        END;

        CREATE TRIGGER pages_au AFTER UPDATE ON pages BEGIN
            INSERT INTO fts_content(fts_content, rowid, page_num, chapter_num, content)
            VALUES('delete', old.id, old.page_num, old.chapter_num, old.content);
            INSERT INTO fts_content(rowid, page_num, chapter_num, content)
            VALUES (new.id, new.page_num, new.chapter_num, new.content);
        END;
    ''')

    # Populate chapters and pages
    total_pages = 0
    total_chars = 0

    for ch_num in sorted(CHAPTERS.keys()):
        meta = CHAPTERS[ch_num]
        filename = f"{ch_num:02d}_{meta['slug']}.txt"
        filepath = CHAPTERS_DIR / filename

        if not filepath.exists():
            print(f"  ⚠️  Missing: {filename}")
            continue

        file_size = filepath.stat().st_size
        pages = extract_pages_from_file(filepath)

        ch_chars = sum(p['content_length'] for p in pages)

        cur.execute('''
            INSERT INTO chapters (chapter_num, slug, title, subtitle, page_count, total_chars, file_size_kb)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (ch_num, meta['slug'], meta['title'], meta['subtitle'],
              len(pages), ch_chars, file_size / 1024))

        for page in pages:
            has_arabic = 1 if re.search(r'[\u0600-\u06FF]', page['content']) else 0
            has_english = 1 if re.search(r'[A-Za-z]{3,}', page['content']) else 0

            cur.execute('''
                INSERT INTO pages (chapter_num, page_num, content, content_length, has_arabic, has_english)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (ch_num, page['page_num'], page['content'], page['content_length'],
                  has_arabic, has_english))

        total_pages += len(pages)
        total_chars += ch_chars
        print(f"  ✅ Ch {ch_num:2d}: {len(pages):3d} pages, {ch_chars:>7,} chars | {meta['title']}")

    conn.commit()

    # Verify FTS
    fts_count = cur.execute("SELECT COUNT(*) FROM fts_content").fetchone()[0]
    print(f"\n  FTS entries: {fts_count}")

    # Test search
    test_results = cur.execute(
        "SELECT page_num, chapter_num FROM fts_content WHERE fts_content MATCH 'بسم الله' LIMIT 3"
    ).fetchall()
    print(f"  FTS test ('بسم الله'): {len(test_results)} results → pages {[r[0] for r in test_results]}")

    conn.close()

    size_kb = DB_PATH.stat().st_size / 1024
    print(f"\n{'='*60}")
    print(f"  Database: {DB_PATH}")
    print(f"  Size: {size_kb:.0f} KB")
    print(f"  Chapters: 40")
    print(f"  Pages: {total_pages}")
    print(f"  Total chars: {total_chars:,}")
    print(f"{'='*60}")


if __name__ == '__main__':
    build_database()
