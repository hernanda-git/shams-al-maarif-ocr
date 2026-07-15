#!/usr/bin/env python3
"""
Group enriched_en pages by the 40 main chapters of Shams al-Ma'arif.
VERBATIM — no content modification.

Uses a curated chapter-to-page mapping built from:
  1. Confirmed Arabic chapter markers in the enriched_en content
  2. Table of contents cross-reference from the master markdown
  3. Content analysis for chapters without explicit markers

The key challenge: Chapter 16 (Beautiful Names) spans pages 165-223 and contains
sub-chapters numbered 1-99 for each of Allah's 99 Names. These are NOT the main
40 chapters — they stay within Chapter 16.
"""

import os
import re
from pathlib import Path

ROOT         = Path(__file__).resolve().parent.parent
ENRICHED_DIR = ROOT / "ocr" / "enriched_en"
OUTPUT_DIR   = ROOT / "ocr" / "chapters_en"

# ── Curated chapter-to-start-page mapping ──
# Page numbers = enriched_en file numbers (page_001.txt .. page_604.txt)
# Start page = first page belonging to that chapter
# Last chapter extends to page 604

CHAPTER_MAP = {
    1:  (11,  "chapter_01_letters",
          "The Dotted Letters — secrets, hidden meanings, and the foundations of speech"),
    2:  (16,  "chapter_02_breaking_expansion_times",
          "Breaking and Expansion — arrangement of works in times and hours"),
    3:  (26,  "chapter_03_lunar_mansions",
          "The Twenty-Eight Lunar Mansions — rulings and celestial influences"),
    4:  (32,  "chapter_04_zodiac_signs",
          "The Twelve Zodiac Signs — indications and connections"),
    5:  (38,  "chapter_05_basmala_secrets",
          "Secrets of the Basmala — hidden properties and blessings"),
    6:  (54,  "chapter_06_seclusion_retreat",
          "Seclusion and Retreat — masters of retreat leading to the upper realms"),
    7:  (56,  "chapter_07_jesus_names",
          "The Names by Which Jesus (upon him peace) Brought the Dead to Life"),
    8:  (62,  "chapter_08_four_tawqifat",
          "The Four Tawqīfāt — chapters and circles"),
    9:  (67,  "chapter_09_quran_beginnings",
          "Properties of the Beginnings of the Qur'an and the Firm Verses"),
    10: (75,  "chapter_10_fatiha_secrets",
          "Secrets of al-Fātiḥa — supplications and famous properties"),
    11: (84,  "chapter_11_inventions_lights",
          "Inventions and Merciful Lights — radiant secrets of the celestial realm"),
    12: (92,  "chapter_12_greatest_name",
          "The Greatest Name of Allah — hidden dispositions"),
    13: (108, "chapter_13_fatiha_omissions",
          "Fallen Parts of al-Fātiḥa — wafqs and answered supplications"),
    14: (113, "chapter_14_spiritual_exercises",
          "Spiritual Exercises, Remembrances and Answered Supplications"),
    15: (148, "chapter_15_conditions_beginnings_endings",
          "Conditions — from beginnings to the suns of endings"),
    16: (165, "chapter_16_beautiful_names",
          "The Beautiful Names of Allah — times, properties, and sub-chapters for each Name"),
    17: (207, "chapter_17_kaf_ha_ya_ayn_sad",
          "Properties of Kāfiyāʿaynṣ (Kهيعص) — divine letters, lordly and most holy"),
    18: (224, "chapter_18_verse_of_throne",
          "Properties of the Verse of the Throne — hidden blessings"),
    19: (241, "chapter_19_wafqs_talismans",
          "Properties of Wafqs and Talismans — beneficial and tried"),
    20: (260, "chapter_20_yaseen",
          "Sūrat Yā Sīn — answered supplications"),
    21: (268, "chapter_21_names_pattern_one",
          "The Beautiful Names — First Pattern of supplications and dispositions"),
    22: (281, "chapter_22_names_pattern_two",
          "The Second Pattern — the Bestowed Names"),
    23: (285, "chapter_23_names_pattern_three",
          "The Third Pattern — attributes and supports"),
    24: (288, "chapter_24_names_pattern_four",
          "The Fourth Pattern — secrets of the Lord of the creatures"),
    25: (294, "chapter_25_names_pattern_five",
          "The Fifth Pattern — selected secrets"),
    26: (297, "chapter_26_names_pattern_six",
          "The Sixth Pattern — secrets of the necessitating matters"),
    27: (299, "chapter_27_names_pattern_seven",
          "The Seventh Pattern — blessings of the Names"),
    28: (303, "chapter_28_names_pattern_eight",
          "The Eighth Pattern — beneficial secrets"),
    29: (305, "chapter_29_names_pattern_nine",
          "The Ninth Pattern — hidden transformations"),
    30: (308, "chapter_30_names_pattern_ten",
          "The Tenth Pattern — beneficial secrets"),
    31: (310, "chapter_31_arabic_letters",
          "Arabic Letters — planets, servants, minerals, and seclusions"),
    32: (320, "chapter_32_arod_secrets",
          "Secrets of Uncovering the ʿArūḍ — the immaterial thrones"),
    33: (340, "chapter_33_circle_encompassment",
          "The Circle of Encompassment — foundations and definitions"),
    34: (351, "chapter_34_zayirja_science",
          "The Science of the Zāyirja — proportions, zodiac, and balances"),
    35: (365, "chapter_35_jafr_rules",
          "The Lettered Hidden Thing — by the Jafr rules"),
    36: (379, "chapter_36_talismanic_letters",
          "The Divine Overflow and Sacred Stone — properties of plants"),
    37: (398, "chapter_37_simia_works",
          "Works of Sīmiyāʾ — all the articles and sayings"),
    38: (401, "chapter_38_letter_uses_retreats",
          "Uses of the Letters and Their Retreats"),
    39: (423, "chapter_39_beautiful_names_explanation",
          "Explanation of the Beautiful Names — elucidation and details"),
    40: (516, "chapter_40_answered_supplications",
          "Answered Supplications — for all times and occasions"),
}


def get_sorted_files():
    """Get all enriched_en files sorted by page number."""
    files = sorted(
        ENRICHED_DIR.glob("page_*.txt"),
        key=lambda p: int(re.search(r'(\d+)', p.stem).group(1))
    )
    return files


def build_page_chapters(files):
    """Build a mapping of page_number → chapter_number."""
    total_pages = max(int(re.search(r'(\d+)', fp.stem).group(1)) for fp in files)
    
    # Sort chapters by start page
    sorted_chapters = sorted(CHAPTER_MAP.items(), key=lambda x: x[1][0])
    
    page_to_chapter = {}
    for fp in files:
        page_num = int(re.search(r'(\d+)', fp.stem).group(1))
        
        # Find which chapter this page belongs to
        assigned_ch = 0  # default: front matter
        for ch_num, (start_page, _, _) in reversed(sorted_chapters):
            if page_num >= start_page:
                assigned_ch = ch_num
                break
        
        page_to_chapter[page_num] = assigned_ch
    
    return page_to_chapter, total_pages


def main():
    files = get_sorted_files()
    print(f"Found {len(files)} enriched_en files")
    
    page_to_chapter, total_pages = build_page_chapters(files)
    
    # Group pages by chapter
    chapter_pages = {}
    for page_num, ch_num in page_to_chapter.items():
        chapter_pages.setdefault(ch_num, []).append(page_num)
    
    # Print summary
    print(f"\n{'='*70}")
    print(f"  CHAPTER MAPPING — Shams al-Ma'arif wa Lata'if al-'Awarif")
    print(f"{'='*70}")
    for ch_num in sorted(chapter_pages.keys()):
        pages = chapter_pages[ch_num]
        start_page, slug, title = CHAPTER_MAP.get(ch_num, (0, f"ch{ch_num:03d}", ""))
        print(f"  Ch {ch_num:2d}: pages {pages[0]:03d}–{pages[-1]:03d} ({len(pages):3d} pages) | {title[:50]}")
    
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Write chapter files — VERBATIM concatenation
    print(f"\n{'='*70}")
    print(f"  WRITING CHAPTER FILES")
    print(f"{'='*70}")
    
    for ch_num in sorted(chapter_pages.keys()):
        pages = chapter_pages[ch_num]
        start_page, slug, title = CHAPTER_MAP.get(ch_num, (0, f"ch{ch_num:03d}", ""))
        
        filename = f"{ch_num:02d}_{slug}.txt"
        outpath = OUTPUT_DIR / filename
        
        parts = []
        for page_num in pages:
            page_file = ENRICHED_DIR / f"page_{page_num:03d}.txt"
            if not page_file.exists():
                continue
            try:
                with open(page_file, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
            except Exception:
                continue
            
            # Skip blank/empty pages
            stripped = content.strip()
            if ('There is no text on this page' in stripped or 
                'This page is empty' in stripped or
                len(stripped) < 30):
                continue
            
            # Add page separator for navigation
            parts.append(f"\n{'━'*60}")
            parts.append(f"  ┃  PAGE {page_num:03d}")
            parts.append(f"{'━'*60}\n")
            parts.append(content)
        
        if parts:
            with open(outpath, 'w', encoding='utf-8') as f:
                f.write(''.join(parts))
            size = outpath.stat().st_size
            size_str = f"{size/1024:.1f} KB" if size < 1024*1024 else f"{size/1024/1024:.1f} MB"
            print(f"  ✅ {filename}: {len(pages)} pages, {size_str}")
        else:
            print(f"  ⚠️  {filename}: no content (all blank pages)")
    
    # Summary
    total_files = len(list(OUTPUT_DIR.glob('*.txt')))
    total_size = sum(f.stat().st_size for f in OUTPUT_DIR.glob('*.txt'))
    print(f"\n{'='*70}")
    print(f"  DONE — {total_files} chapter files, {total_size/1024/1024:.1f} MB total")
    print(f"  Output: {OUTPUT_DIR}")
    print(f"{'='*70}")


if __name__ == '__main__':
    main()
