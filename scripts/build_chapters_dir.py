#!/usr/bin/env python3
"""
Build a top-level `chapters/` tree of the OCR pipeline's deliverable content.

For every page in ocr/enriched_en/page_NNN.txt, copy it into:
    chapters/<chapter_slug>/page_NNN.txt

The chapter-to-page mapping is the SAME curated map used by
group_by_chapters.py / build_db.py / build_static_html.py so the tree
stays consistent with the DB and HTML reader.

Pages before the first chapter's start page (1..10) are grouped under
`00_front_matter`.

Pure file copy — never modifies source content. Re-runnable (overwrites).
"""

import shutil
from pathlib import Path

ROOT         = Path(__file__).resolve().parent.parent
SRC_DIR      = ROOT / "ocr" / "enriched_en"
DEST_ROOT    = ROOT / "chapters"

# ── Curated chapter-to-start-page mapping (from group_by_chapters.py) ──
# (start_page, slug)
CHAPTER_MAP = {
    1:  (11,  "chapter_01_letters"),
    2:  (16,  "chapter_02_breaking_expansion_times"),
    3:  (26,  "chapter_03_lunar_mansions"),
    4:  (32,  "chapter_04_zodiac_signs"),
    5:  (38,  "chapter_05_basmala_secrets"),
    6:  (54,  "chapter_06_seclusion_retreat"),
    7:  (56,  "chapter_07_jesus_names"),
    8:  (62,  "chapter_08_four_tawqifat"),
    9:  (67,  "chapter_09_quran_beginnings"),
    10: (75,  "chapter_10_fatiha_secrets"),
    11: (84,  "chapter_11_inventions_lights"),
    12: (92,  "chapter_12_greatest_name"),
    13: (108, "chapter_13_fatiha_omissions"),
    14: (113, "chapter_14_spiritual_exercises"),
    15: (148, "chapter_15_conditions_beginnings_endings"),
    16: (165, "chapter_16_beautiful_names"),
    17: (207, "chapter_17_kaf_ha_ya_ayn_sad"),
    18: (224, "chapter_18_verse_of_throne"),
    19: (241, "chapter_19_wafqs_talismans"),
    20: (260, "chapter_20_yaseen"),
    21: (268, "chapter_21_names_pattern_one"),
    22: (281, "chapter_22_names_pattern_two"),
    23: (285, "chapter_23_names_pattern_three"),
    24: (288, "chapter_24_names_pattern_four"),
    25: (294, "chapter_25_names_pattern_five"),
    26: (297, "chapter_26_names_pattern_six"),
    27: (299, "chapter_27_names_pattern_seven"),
    28: (303, "chapter_28_names_pattern_eight"),
    29: (305, "chapter_29_names_pattern_nine"),
    30: (308, "chapter_30_names_pattern_ten"),
    31: (310, "chapter_31_arabic_letters"),
    32: (320, "chapter_32_arod_secrets"),
    33: (340, "chapter_33_circle_encompassment"),
    34: (351, "chapter_34_zayirja_science"),
    35: (365, "chapter_35_jafr_rules"),
    36: (379, "chapter_36_talismanic_letters"),
    37: (398, "chapter_37_simia_works"),
    38: (401, "chapter_38_letter_uses_retreats"),
    39: (423, "chapter_39_beautiful_names_explanation"),
    40: (516, "chapter_40_answered_supplications"),
}

FRONT_MATTER_SLUG = "00_front_matter"


def chapter_for_page(page_num: int) -> str:
    """Return the slug of the chapter a given page belongs to."""
    assigned = FRONT_MATTER_SLUG
    for ch_num in sorted(CHAPTER_MAP.keys()):
        start_page, slug = CHAPTER_MAP[ch_num]
        if page_num >= start_page:
            assigned = slug
    return assigned


def main():
    src_files = sorted(SRC_DIR.glob("page_*.txt"))
    if not src_files:
        raise SystemExit(f"No page files found in {SRC_DIR}")

    # Count per chapter for a summary
    counts: dict[str, int] = {}

    for src in src_files:
        page_num = int(src.stem.split("_")[1])
        slug = chapter_for_page(page_num)
        dest_dir = DEST_ROOT / slug
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest_dir / src.name)
        counts[slug] = counts.get(slug, 0) + 1

    total = sum(counts.values())
    print(f"Copied {total} page files into {len(counts)} chapter directories.")
    print(f"Destination: {DEST_ROOT}\n")
    for slug in sorted(counts.keys()):
        print(f"  {slug:42s} {counts[slug]:3d} pages")


if __name__ == "__main__":
    main()
