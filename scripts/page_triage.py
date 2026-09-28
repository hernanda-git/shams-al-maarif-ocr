"""One triage command for the whole V2 queue, so each page is judged the same way.

The V2 tracker's own page validator checks STRUCTURE only. Three defect
classes pass it:

  untranslated  a target block still contains a run of Arabic prose. A magic
                square's grid CELLS are legitimately Arabic, so the test is
                the length of the longest run, not the presence of any Arabic.
  wrong-page    the block opens with a folio that is not its page's - it is a
                neighbour's text copied forward. Page 61 was 91.9% identical
                to page 60 and the validator said PASS.
  honorific     the block uses 'God (exalted is He)' where the style guide
                mandates 'God Most High', or omits the mandated form entirely.

Read the three findings together. A page can carry more than one, and the fix
differs by class, so reporting them together avoids dispatching a worker for
one and discovering the other afterwards.

Usage:
  uv run --no-project python scripts/page_triage.py 62
  uv run --no-project python scripts/page_triage.py 61 62 63
  uv run --no-project python scripts/page_triage.py --queue 20   # next N pending
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from recover_sibling_blocks import blocks_for, clean, parse_blocks  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
TOTAL = 604
FOLDERS = {"enriched_en": "English", "enriched_id": "Indonesia"}
AR_RUN = re.compile(r"[\u0600-\u06FF]+")
AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
# a run this long is prose, not a one-letter grid cell
PROSE_RUN = 4


def leading_folio(text: str) -> str | None:
    for line in text.splitlines():
        if not line.strip():
            continue
        if "-" in line or "\u2014" in line or "(" in line:
            m = re.search(r"[\u0660-\u0669]+|\d{1,3}", line)
            if m:
                return str(int(m.group().translate(AR_DIGITS)))
        return None
    return None


def triage(page: int) -> list[str]:
    problems: list[str] = []
    spath = REPO_ROOT / "ocr" / "enriched" / f"page_{page:03d}.txt"
    if not spath.exists():
        return ["no canonical source"]
    source = clean(spath.read_text(encoding="utf-8"))
    want = leading_folio(source)

    for folder, label in FOLDERS.items():
        path = REPO_ROOT / "ocr" / folder / f"page_{page:03d}.txt"
        short = "en" if "enriched_en" in folder else "id"
        if not path.exists():
            problems.append(f"{short}: file missing")
            continue
        text = clean(path.read_text(encoding="utf-8"))
        labels = [l for l, _, _ in parse_blocks(text)]
        if labels != ["Arabic", label]:
            problems.append(f"{short}: MALFORMED labels={labels}")
            continue
        body = blocks_for(text, label)
        if not body:
            problems.append(f"{short}: no {label} block")
            continue
        body = body[0]
        if len(body) < 40:
            problems.append(f"{short}: EMPTY ({len(body)}c)")
            continue

        runs = AR_RUN.findall(body)
        longest = max((len(r) for r in runs), default=0)
        if longest >= PROSE_RUN:
            total = sum(len(r) for r in runs)
            problems.append(f"{short}: UNTRANSLATED {total} Arabic letters (longest {longest})")

        got = leading_folio(body)
        if want and got and got != want:
            delta = abs(int(got) - int(want))
            kind = "WRONG PAGE" if delta > 1 else "off-by-one (normal realignment)"
            problems.append(f"{short}: FOLIO {kind} source {want} target {got}")

        if short == "en":
            if "exalted is He" in body:
                problems.append("en: BANNED honorific 'exalted is He'")
            elif "God Most High" not in body and "Most High" not in body:
                if re.search(r"\bGod\b", body):
                    problems.append("en: honorific not the mandated 'God Most High'")
        else:
            if "Ta\u2018ala" in body or "Ta\u2019ala" in body:
                problems.append("id: honorific not the mandated 'Yang Mahatinggi'")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pages", nargs="*", type=int)
    ap.add_argument("--queue", type=int, help="triage the next N pending pages")
    args = ap.parse_args()

    pages = list(args.pages)
    if args.queue:
        progress = REPO_ROOT / "state" / "translation_v2" / "progress.json"
        if progress.exists():
            import json

            state = json.loads(progress.read_text(encoding="utf-8"))
            records = state.get("pages") or {}
            done = {
                int(k)
                for k, v in records.items()
                if (v.get("status") if isinstance(v, dict) else v) == "committed"
            }
            pages += [p for p in range(1, TOTAL + 1) if p not in done][: args.queue]
        else:
            pages += list(range(1, args.queue + 1))

    if not pages:
        ap.error("give page numbers or --queue N")
    clean_count = 0
    for page in pages:
        problems = triage(page)
        if problems:
            print(f"p{page:03d}  {len(problems)} issue(s)")
            for p in problems:
                print(f"        {p}")
        else:
            clean_count += 1
            print(f"p{page:03d}  clean")
    print(f"\n{len(pages) - clean_count}/{len(pages)} pages need work")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
