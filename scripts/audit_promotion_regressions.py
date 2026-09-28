"""Regression check across every EN page my repair rewrote vs origin/main.

The V2 worker had already aligned pages 1-56 in origin/main. My repair commit
2ee94a9 rewrote 458 EN files. promote_better_english.py falls back to "prefer
the longer copy" when BOTH copies contain Arabic script -- and a V2-revised copy
can be SHORTER than the stale one, because transliterating an Arabic-script run
compresses it. So the longer-copy rule can downgrade an already-aligned page.

For every EN page my repair touched, compare the Arabic-script count in the
English block before and after. More Arabic in mine = a regression.
"""
import re, subprocess
from pathlib import Path

MY = Path(r"C:/Workspace/gw-shams-repair")
AR = re.compile(r"[\u0600-\u06FF]")


def show(ref, path):
    return subprocess.run(["git", "-C", str(MY), "show", f"{ref}:{path}"],
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout


def en_of(text):
    t = text.replace("\r\n", "\n")
    i = t.find("\nEnglish:")
    return t[i + len("\nEnglish:"):].strip() if i >= 0 else ""


touched = subprocess.run(
    ["git", "-C", str(MY), "diff", "--name-only", "origin/main", "2ee94a9",
     "--", "ocr/enriched_en/"],
    capture_output=True, text=True).stdout.split()
pages = sorted(int(p.split("_")[-1].split(".")[0]) for p in touched if "_" in p)
print(f"EN pages my repair rewrote vs origin/main: {len(pages)}\n")

regressions, same, improved, skipped = [], 0, 0, 0
for page in pages:
    before = en_of(show("origin/main", f"ocr/enriched_en/page_{page:03d}.txt"))
    after = en_of(show("2ee94a9", f"ocr/enriched_en/page_{page:03d}.txt"))
    if not before or not after:
        skipped += 1
        continue
    b, a = len(AR.findall(before)), len(AR.findall(after))
    if a > b:
        regressions.append((page, b, a, len(before), len(after)))
    elif a < b:
        improved += 1
    else:
        same += 1

print(f"improved (less Arabic)  : {improved}")
print(f"unchanged               : {same}")
print(f"skipped (no en block)   : {skipped}")
print(f"REGRESSED (more Arabic) : {len(regressions)}")
for p, b, a, bl, al in regressions:
    print(f"  p{p:03d}  arabic {b} -> {a}   len {bl} -> {al}")
