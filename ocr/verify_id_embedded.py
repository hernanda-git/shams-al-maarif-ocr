#!/usr/bin/env python3
"""Authoritative ID alignment via token-fingerprint matching.

Compare the EMBEDDED Arabic section of each enriched_id/page_NNN.txt against the
STANDALONE Arabic source enriched/page_NNN.txt (OCR of scan NNN = physical page
NNN). If embedded AR is the same text as AR(NNN) -> aligned. Else find the AR
page whose token set best overlaps -> true physical page. Fast: fingerprint = set
of whitespace-token hashes.
"""
import os
import re

OCR = "."
AR = "enriched"
ID = "enriched_id"


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


def fingerprint(t):
    if not t:
        return set()
    return set(t.split())


def load(d, n):
    p = os.path.join(d, n)
    return open(p, encoding="utf-8", errors="replace").read() if os.path.exists(p) else None


def main():
    id_files = sorted(f for f in os.listdir(ID) if f.startswith("page_") and f.endswith(".txt"))
    ar_fp = {}
    for f in id_files:
        t = load(AR, f)
        ar_fp[f] = fingerprint(t)

    aligned = 0
    displaced = []
    for f in id_files:
        idf = load(ID, f)
        emb = fingerprint(sec(idf, "Arabic"))
        if not emb:
            displaced.append((f, None, 0.0, "no-embedded-arabic"))
            continue
        # exact token-set match vs same file
        if ar_fp[f] and emb == ar_fp[f]:
            aligned += 1
            continue
        best_g, best_j = None, -1.0
        for g, gf in ar_fp.items():
            if not gf:
                continue
            inter = len(emb & gf)
            union = len(emb | gf)
            j = inter / union if union else 0
            if j > best_j:
                best_j, best_g = j, g
        displaced.append((f, best_g, round(best_j, 3), "fuzzy") if best_g else (f, None, 0.0, "no-match"))

    print(f"ID files: {len(id_files)}  ALIGNED: {aligned}  DISPLACED: {len(displaced)}")
    # how many displaced have a strong (>=0.9) match -> real misplacement
    strong = [(f, g, j) for (f, g, j, *_ ) in displaced if g and j >= 0.9]
    print(f"  with strong match (J>=0.9): {len(strong)}")
    print(f"\n{'file':<14} {'true slot':<12} {'J'}")
    for f, g, j, *_ in displaced:
        if g:
            gs = g[len('page_'):-len('.txt')]
            print(f"{f:<14} {gs:<12} {j}")


if __name__ == "__main__":
    main()
