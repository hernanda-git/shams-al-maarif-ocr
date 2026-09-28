"""Verify a subagent's translation actually landed, in the file on disk.

A delegation summary is a SELF-REPORT. This reads the real bytes and checks the
claims that matter:

  1. the target label exists exactly once
  2. the target block is non-empty and is genuinely target-language
  3. the embedded Arabic block equals the canonical source
  4. NO degenerate repetition: the most common 12-char window must not
     dominate the block
  5. no model-scratchpad tokens leaked into the file ('ELEMENT_MESSAGE',
     'the result of', a bare 'what what', a run of 'PuPu')
  6. completeness: target chars / Arabic letters ratio, and no truncation marker
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from recover_sibling_blocks import (  # noqa: E402
    _ARABIC_IN_TARGET,
    blocks_for,
    clean,
    parse_blocks,
)

SCRATCH = re.compile(
    r"ELEMENT_MESSAGE|The result of the|four lingual|\bPuPu|what what|/what\b|"
    r"assistant<|analysis<|<tool_call>|Here's a thinking",
)
TRUNC = re.compile(r"\[\.\.\.|truncated\}|omitted for brevity", re.IGNORECASE)

FOLDERS = {"enriched_en": ("English", "en"), "enriched_id": ("Indonesia", "id")}


def main() -> int:
    pairs = [(int(a), b) for a in sys.argv[1:] for b in ("en", "id")]
    bad = 0
    for page, lang in pairs:
        if not sys.argv[1:]:
            continue
        folder = "enriched_en" if lang == "en" else "enriched_id"
        tgt_label = "English" if lang == "en" else "Indonesia"
        path = REPO_ROOT / "ocr" / folder / f"page_{page:03d}.txt"
        src_path = REPO_ROOT / "ocr" / "enriched" / f"page_{page:03d}.txt"
        if not path.exists():
            print(f"  MISSING p{page:03d} {lang}: {path.name} does not exist")
            bad += 1
            continue
        raw = path.read_text(encoding="utf-8")
        text = clean(raw)
        labels = [l for l, _, _ in parse_blocks(text)]
        src = clean(src_path.read_text(encoding="utf-8"))
        src_letters = len([c for c in src if c.isalpha() and "؀" <= c <= "ۿ"])

        issues = []
        if labels.count(tgt_label) != 1:
            issues.append(f"label {tgt_label!r} x{labels.count(tgt_label)} (labels={labels})")
        bodies = blocks_for(text, tgt_label)
        body = bodies[0] if bodies else ""
        if not body:
            issues.append("target block EMPTY")
        embedded = blocks_for(text, "Arabic")
        if embedded and " ".join(embedded[0].split()) != " ".join(src.split()):
            issues.append(f"embedded Arabic != canonical ({len(embedded[0])}c vs {len(src)}c)")
        m = SCRATCH.search(raw)
        if m:
            issues.append(f"SCRATCHPAD LEAK {m.group()!r} x{len(SCRATCH.findall(raw))}")
        if len(body) > 200:
            # Degenerate output is a model stuck in a loop. Its signature is a
            # NON-LINGUISTIC filler token repeating, or the same window
            # occupying most of the block. A legitimate repetitive page
            # (p105 is 1,359 grid markers; p134 is a 641-occurrence dhikr) has a
            # high dominant-window ratio too, so the window must be checked for
            # being real text: if it contains a space-separated word it is
            # prose/grid text and repetition is expected, not degenerate.
            c = Counter(body[i:i + 12] for i in range(len(body) - 12))
            top, n = c.most_common(1)[0]
            alpha_ratio = sum(ch.isalpha() or ch == " " for ch in top) / len(top)
            looks_like_words = " " in top and alpha_ratio > 0.5
            if not looks_like_words and n > len(body) / 3 and len(body) > 500:
                issues.append(f"DEGENERATE REPETITION: {top!r} x{n} of {len(body)}c")
        # A magic-square page legitimately carries Arabic LETTERS: the grid
        # cells ARE the letters of the divine name, and transliterating them
        # would destroy the geometry the style guide requires preserving. Page
        # 244 has 40 single-letter Arabic cells in a 7,545c block -- correct as
        # written. What must not survive is a RUN of Arabic prose, i.e. an
        # untranslated passage. So flag only a long contiguous run.
        longest = max((len(m.group()) for m in re.finditer(r"[\u0600-\u06FF]+", body)), default=0)
        total_ar = len(_ARABIC_IN_TARGET.findall(body))
        if longest >= 12 or (total_ar > max(4, len(body) * 0.005) and longest < 3 and total_ar > 60):
            issues.append(f"untranslated Arabic: longest run {longest}, {total_ar} letters")
        # `[?]` is the pipeline's own OCR placeholder for an illegible cell; it
        # is data, not a truncation marker written by a translator.
        body_no_placeholder = re.sub(r"\[\?\]", "", body)
        if TRUNC.search(body_no_placeholder):
            issues.append("truncation marker")
        if src_letters > 200 and len(body) / src_letters < 0.25:
            issues.append(f"ratio {len(body)/src_letters:.2f} ({len(body)}c/{src_letters} letters)")

        if issues:
            bad += 1
            print(f"  BAD  p{page:03d} {lang}  " + "; ".join(issues))
        else:
            print(f"  ok   p{page:03d} {lang}  {len(body)}c target, {len(labels)} labels")
    print(f"\nproblem files: {bad}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
