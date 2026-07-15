#!/usr/bin/env python3
"""Verify per-page alignment of enriched_id/*.txt vs enriched/*.txt (Arabic).

Language-independent signatures shared by a correctly-translated page:
  (1) header numeral  "— N —"  (Arabic-Indic digits, identical across langs)
  (2) count of ornate-bracket FRAMES  \uFD3E ... \uFD3F  (same count in every lang)
  (3) set of embedded untranslated Arabic lemma tokens (Allah, Muhammad, Musa, ...)

For each ID file we compare its Indonesia: section signature to the Arabic
source (same filename). On mismatch we find the Arabic page whose signature
best matches -> the true physical page.
"""
import os
import re
import sys
from collections import Counter

OCR = os.path.dirname(os.path.abspath(__file__))
AR = os.path.join(OCR, "enriched")
EN = os.path.join(OCR, "enriched_en")
ID = os.path.join(OCR, "enriched_id")

FRAME_RE = re.compile("\uFD3E")
HEADER_RE = re.compile(r"^\s*—\s*([0-9٠-٩]+)\s*—\s*$")
TRANS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
LEMMA_RE = re.compile(r"\b(Allah|Muhammad|Musa|Yahya|Ibrahim|Ismail|Adam|Yunus|Isa|Iblis|Jibril|Mika'il)\b")


def ascii_num(s):
    return s.translate(TRANS)


def sig(text):
    """(header_num|None, frame_count, lemma_counter)."""
    header = None
    if text:
        for line in text.splitlines():
            m = HEADER_RE.match(line.strip())
            if m:
                header = ascii_num(m.group(1))
                break
    frames = len(FRAME_RE.findall(text)) if text else 0
    lemmas = Counter(LEMMA_RE.findall(text)) if text else Counter()
    return header, frames, lemmas


def section(text, label):
    if text is None:
        return ""
    LABEL_RE = re.compile(r"(?m)^(?:Arabic|English|Indonesia)\s*[:：]?\s*$")
    ms = list(LABEL_RE.finditer(text))
    for i, m in enumerate(ms):
        if m.group(0).startswith(label):
            s = m.end()
            e = ms[i + 1].start() if i + 1 < len(ms) else len(text)
            return text[s:e]
    return ""


def load(d, name):
    p = os.path.join(d, name)
    if not os.path.exists(p):
        return None
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        return None


def score(a, b):
    """Similarity 0..1 of two signatures."""
    sa, fa, la = a
    sb, fb, lb = b
    pts = 0
    tot = 0
    if sa is not None and sb is not None:
        tot += 2
        if sa == sb:
            pts += 2
    tot += 1
    if fa == fb:
        pts += 1
    tot += 1
    if set(la) == set(lb) and (not la or sum(la.values()) == sum(lb.values())):
        pts += 1
    return pts / tot if tot else 1.0


def main():
    id_files = sorted(
        f for f in os.listdir(ID) if f.startswith("page_") and f.endswith(".txt")
    )
    print(f"ID files: {len(id_files)}")

    ar_sig = {f: sig(load(AR, f)) for f in id_files}

    mismatches = []
    for f in id_files:
        id_body = section(load(ID, f), "Indonesia")
        sid = sig(id_body)
        sar = ar_sig[f]
        # skip pages with no usable signal
        if sid[0] is None and sid[1] == 0 and not sid[2]:
            continue
        if score(sid, sar) >= 0.999:
            continue
        best_m, best_s = None, -1.0
        for g, gs in ar_sig.items():
            s = score(sid, gs)
            if s > best_s:
                best_s, best_m = s, g
        mismatches.append((f, sid, sar, best_m, round(best_s, 3)))

    if not mismatches:
        print("ALIGNMENT OK: every ID Indonesia section matches its same-numbered "
              "Arabic source (header numeral + bracket frames + lemmas).")
        return 0

    print(f"\nMISALIGNED ID FILES: {len(mismatches)}")
    print(f"{'file':<14} {'ID(hdr,fr)':<14} {'AR(hdr,fr)':<14} -> best slot (score)")
    for f, sid, sar, bm, sc in mismatches:
        fid = f"{sid[0]},{sid[1]}"
        far = f"{sar[0]},{sar[1]}"
        bm_s = bm[len('page_'):-len('.txt')] if bm else '?'
        print(f"{f:<14} {fid:<14} {far:<14} -> page_{bm_s} ({sc})")
    return 1


if __name__ == "__main__":
    sys.exit(main())
