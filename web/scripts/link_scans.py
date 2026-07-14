#!/usr/bin/env python3
"""
Link the per-page scanned PDFs from the OCR pipeline into the Next.js
public/scans folder, renaming page_NNN.pdf -> page-NNN.pdf to match the
scanSrc field emitted by build_manuscript_json.py.

Source: <pdf>/131812-pages/page_NNN.pdf
Dest:   public/scans/page-NNN.pdf
"""
import os
import shutil
import sys

SRC = os.environ.get(
    "SHAMS_PAGES_DIR",
    r"C:/Working Folder/Research/pdf/131812-pages",
)
DEST = os.environ.get(
    "SHAMS_SCANS_OUT",
    r"C:/Workspace/shams-al-maarif/public/scans",
)
TOTAL = 604


def main():
    os.makedirs(DEST, exist_ok=True)
    copied = 0
    missing = 0
    for n in range(1, TOTAL + 1):
        src = os.path.join(SRC, f"page_{n:03d}.pdf")
        dst = os.path.join(DEST, f"page-{n:03d}.pdf")
        if not os.path.exists(src):
            missing += 1
            continue
        # skip if already present and same size
        if os.path.exists(dst) and os.path.getsize(dst) == os.path.getsize(src):
            copied += 1
            continue
        shutil.copy2(src, dst)
        copied += 1
    print(f"Scans ready in {DEST}")
    print(f"  copied/present: {copied}/{TOTAL}")
    if missing:
        print(f"  missing source: {missing}")


if __name__ == "__main__":
    main()
