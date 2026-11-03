"""One triage command for the whole V2 queue, so each page is judged the same way.

The V2 tracker's own page validator checks STRUCTURE only. Three defect
classes pass it:

  untranslated  a target block contains any Arabic-script characters, including
                citation markers, short grid cells, and presentation forms.
                Style V2 requires Latin transliteration even inside grids.
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
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from recover_sibling_blocks import blocks_for, clean, parse_blocks  # noqa: E402
from verify_translation_v2_page import _is_explicit_no_text  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
TOTAL = 604
FOLDERS = {"enriched_en": "English", "enriched_id": "Indonesia"}
# Arabic blocks include marks, digits, punctuation, and presentation forms.
# Latin punctuation and ordinary mathematical symbols are not contamination.
AR_RUN = re.compile(
    r"[\u0600-\u06FF\u0750-\u077F\u0870-\u089F\u08A0-\u08FF"
    r"\uFB50-\uFDFF\uFE70-\uFEFC\U00010E60-\U00010E7F"
    r"\U00010EC0-\U00010EFF\U0001EE00-\U0001EEFF]+"
)
AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
# Exact canonical descriptions on p003 and p005, not a substring/keyword guess.
DESCRIPTIVE_NO_TEXT_SOURCES = {
    "هذا المستند عبارة عن صفحة فارغة (غلاف داخلي أو صفحة بيضاء) ولا يحتوي على أي نصوص عربية.",
    "هذه الصفحة فارغة ولا تحتوي على أي نص.",
}
NO_TEXT_MARKERS = {"English": "[NO VISIBLE TEXT]", "Indonesia": "[TIDAK ADA TEKS TERLIHAT]"}


def arabic_prose_runs(body: str) -> list[str]:
    """Return every contiguous Arabic-block run, including single characters.

    The public name is retained for compatibility; these are contamination
    runs, not a prose classifier. No words, grid cells, or honorifics are exempt.
    Counts are diagnostic character counts, never evidence of semantic coverage.
    """
    return AR_RUN.findall(body)


def needs_honorific(source: str) -> bool:
    """Match the actual adjacent الله تعالى phrase, ignoring vocalization.

    Whitespace may include line breaks; disconnected occurrences of the two
    words do not establish this honorific. Normalize presentation forms too.
    Allow common attached conjunction/preposition clitics (بالله، والله، لله),
    but not arbitrary word prefixes or intervening words.
    """
    normalized = "".join(
        char for char in unicodedata.normalize("NFKD", source)
        if not unicodedata.category(char).startswith("M") and char != "ـ"
    )
    return bool(re.search(r"(?<!\w)[وف]?(?:[بك]?الله|لله)\s+تعالى(?!\w)", normalized))


def leading_folio(text: str) -> str | None:
    """The page number on the first non-blank line, or None.

    Deliberately tolerant about the SURROUNDINGS, because the corpus is not
    consistent about them. p022's English opens with a bare '16' - no
    dashes at all - and an earlier version required '-' or an em-dash, so it
    reported 39 pages as having NO folio when they plainly have one. The
    question being asked is 'what number is this page', not 'is this
    formatted the way I would format it', so a bare numeral counts.

    Returns None only when the first line carries no number at all, which
    is the genuine missing-folio case (p130's English before its repair).
    """
    for line in text.splitlines():
        if not line.strip():
            continue
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
        blank_source = _is_explicit_no_text(source) or source in DESCRIPTIVE_NO_TEXT_SOURCES
        if body.strip() in NO_TEXT_MARKERS.values():
            if not blank_source:
                problems.append(f"{short}: NO TEXT marker over nonblank canonical source")
            elif body.strip() != NO_TEXT_MARKERS[label]:
                problems.append(f"{short}: incorrect no-text marker for {label}")
        elif len(body) < 40:
            problems.append(f"{short}: EMPTY ({len(body)}c)")
        # Even a short/empty-looking block must be checked for contamination.

        runs = arabic_prose_runs(body)
        if runs:
            total = sum(len(r) for r in runs)
            longest = max(len(r) for r in runs)
            problems.append(
                f"{short}: UNTRANSLATED {total} Arabic characters in {len(runs)} "
                f"run(s), longest {longest} (e.g. {runs[0]!r})"
            )

        got = leading_folio(body)
        if want and got and got != want:
            delta = abs(int(got) - int(want))
            kind = "WRONG PAGE" if delta > 1 else "off-by-one (normal realignment)"
            problems.append(f"{short}: FOLIO {kind} source {want} target {got}")

        if short == "en":
            if "exalted is He" in body:
                problems.append("en: BANNED honorific 'exalted is He'")
            elif needs_honorific(source) and "Most High" not in body:
                # Only flag a MISSING honorific when the source actually
                # carries الله تعالى. My first version flagged any page
                # mentioning 'God' at all, which caught 68 pages - almost all
                # of them correct: 'God says', 'God knows best', 'no god but
                # God', 'the Names of God'. Those are plain God, and الله
                # appears in ordinary sentences as readily as it does in the
                # honorific phrase. Requiring the honorific is the only way
                # to tell them apart, and p402 proved the point from the
                # other side: its body reads 'name of God can be read' while
                # its source contains no الله at all.
                problems.append("en: honorific not the mandated 'God Most High'")
        else:
            if re.search(r"\bTa['‘’]ala\b", body, re.IGNORECASE):
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
