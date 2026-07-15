#!/usr/bin/env python3
"""Authoritative re-map for enriched_id files by their Indonesia-section header
numeral. The Arabic source file page_NNN.txt is physical page NNN (OCR of scan
NNN, header numeral == NNN). So an ID file whose Indonesia header reads M truly
belongs at page_MMM.txt.

Outputs:
  - proposed renames (current -> target) and any collisions
  - a corrected build preview (does NOT write; build_manuscript_json.py already
    maps filename->page, so renaming fixes alignment end-to-end)
"""
import os
import re
from collections import defaultdict

OCR = "."
AR = "enriched"
ID = "enriched_id"
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
    id_files = sorted(f for f in os.listdir(ID) if f.startswith("page_") and f.endswith(".txt"))
    target_of = {}
    nohdr = []
    collisions = defaultdict(list)
    for f in id_files:
        n = f[len("page_"):-len(".txt")]
        h = header_of(sec(load(ID, f), "Indonesia"))
        if h is None:
            nohdr.append(f)
            continue
        target = f"page_{int(h):03d}.txt"
        target_of[f] = target
        collisions[target].append(f)

    # report
    renames = [(f, t) for f, t in target_of.items() if f != t]
    print(f"ID files: {len(id_files)}")
    print(f"  with header numeral: {len(target_of)}  (renames needed: {len(renames)})")
    print(f"  NO header numeral: {len(nohdr)} -> {nohdr}")

    # collisions: multiple current files map to same target
    coll = {t: fs for t, fs in collisions.items() if len(fs) > 1}
    print(f"\nCOLLISIONS (multiple ID files -> same true page): {len(coll)}")
    for t, fs in coll.items():
        print(f"  {t}: {fs}")

    # targets that already exist as a correctly-named file (would overwrite):
    # a target collides with an existing file name if there is BOTH a current
    # file named == target AND another file mapping to it.
    existing = {f for f in id_files}
    overwrite_risk = [t for t in coll if t in existing]
    print(f"\nTargets equal to an existing filename among colliders: {overwrite_risk}")

    # sanity: how many renames are pure "shift" (target != file)
    print(f"\nSample renames (first 30):")
    for f, t in renames[:30]:
        print(f"  {f} -> {t}")

    # verify every target is within 1..600
    bad = [t for t in target_of.values() if not (1 <= int(t[len('page_'):-len('.txt')]) <= 600)]
    print(f"\nTargets out of range 1..600: {bad}")


if __name__ == "__main__":
    main()
