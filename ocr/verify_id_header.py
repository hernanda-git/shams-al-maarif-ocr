#!/usr/bin/env python3
"""Find the TRUE physical page for each enriched_id file by matching its
Indonesia-section header numeral (— N —) to the Arabic source scanned for that
physical page. The Arabic file page_NNN.txt IS physical page NNN (OCR from scan
NNN, header numeral on the scan). So an ID file whose header reads M belongs at
enriched_id/page_MMM.txt.

Also emit a proposed rename map and a count of displaced files.
"""
import os
import re
from collections import defaultdict

OCR = "."
AR = "enriched"
ID = "enriched_id"
FRAME = re.compile("\uFD3E")
HEADER = re.compile(r"^\s*—\s*([0-9٠-٩]+)\s*—\s*$")
TR = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def an(s):
    return s.translate(TR)


def header_of(text):
    if not text:
        return None
    for ln in text.splitlines():
        m = HEADER.match(ln.strip())
        if m:
            return an(m.group(1))
    return None


def frames_of(text):
    return len(FRAME.findall(text)) if text else 0


def sec(t, lab):
    if not t:
        return ""
    LR = re.compile(r"(?m)^(?:Arabic|English|Indonesia)\s*[:：]?\s*$")
    ms = list(LR.finditer(t))
    for i, m in enumerate(ms):
        if m.group(0).startswith(lab):
            s = m.end()
            e = ms[i + 1].start() if i + 1 < len(ms) else len(t)
            return t[s:e]
    return ""


def load(d, n):
    p = os.path.join(d, n)
    return open(p, encoding="utf-8", errors="replace").read() if os.path.exists(p) else None


def main():
    # arabic physical-page -> header numeral (sanity)
    ar_files = sorted(f for f in os.listdir(AR) if f.startswith("page_") and f.endswith(".txt"))
    ar_hdr = {}
    for f in ar_files:
        n = f[len("page_"):-len(".txt")]
        h = header_of(load(AR, f))
        ar_hdr[n] = h

    id_files = sorted(f for f in os.listdir(ID) if f.startswith("page_") and f.endswith(".txt"))
    displaced = []
    consistent = 0
    for f in id_files:
        n = f[len("page_"):-len(".txt")]
        idb = sec(load(ID, f), "Indonesia")
        h = header_of(idb)
        fr = frames_of(idb)
        ar_h = ar_hdr.get(n)
        # determine true physical page from ID header
        true_page = h
        # aligned if ID header == arabic source's OWN header (which == n)
        if h is not None and h == ar_h:
            consistent += 1
        else:
            displaced.append((f, n, h, ar_h, fr))

    print(f"ID files: {len(id_files)}  aligned: {consistent}  displaced: {len(displaced)}")
    print(f"\n{'file':<14} {'IDhdr':<7} {'ARhdr(sameFile)':<16} frames")
    for f, n, h, ar_h, fr in displaced:
        print(f"{f:<14} {str(h):<7} {str(ar_h):<16} {fr}")

    # Build proposed rename map: current file -> target page_MMM.txt (by ID header)
    print("\nPROPOSED RENAMES (by Indonesia header numeral):")
    renames = []
    for f, n, h, ar_h, fr in displaced:
        if h is not None:
            target = f"page_{int(h):03d}.txt"
            if target != f:
                renames.append((f, target))
    for f, t in renames:
        print(f"  {f}  ->  {t}")
    print(f"\ntotal rename actions proposed: {len(renames)}")


if __name__ == "__main__":
    main()
