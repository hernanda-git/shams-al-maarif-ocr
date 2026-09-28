"""Align a grid page's target block with the corpus convention for illegible cells.

Page 244 is a magic-square page: a 5-row abjad grid of single Arabic letters
(which ARE the divine name, so they stay raw), a `[Diagram text]` marker, and
then a row of 2,710 OCR-illegible cells. The grid cells must be preserved raw;
the illegible cells must be reproduced cell-for-cell, because that is what the
rest of the corpus does.

A worker surveying the six grid pages concluded that "none reproduce the full
run, so the compact representation is the house convention". That reading was
wrong. p253's English keeps 2,605 of 2,606 cells and p244's own English keeps
all 2,710 - the convention is to REPRODUCE, and p244's Indonesian layer was the
outlier at 546.

This rewrites the target's tail: keeps everything up to the `[Diagram text]`
marker, then the note, then the source's cells verbatim. It never invents
content, and it never touches the Arabic block.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from recover_sibling_blocks import blocks_for, clean, parse_blocks  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
LABEL = {"en": ("enriched_en", "English"), "id": ("enriched_id", "Indonesia")}

NOTE = {
    "en": (
        "[UNCLEAR: the source's diagram is an unbroken row of illegible cells; each "
        "cell is recorded in the source by its own illegible-cell placeholder, and "
        "that whole row is reproduced below cell for cell, unchanged, with no content "
        "supplied for it]"
    ),
    "id": (
        "[UNCLEAR: diagram pada sumber adalah barisan sel yang tidak terbaca tanpa "
        "henti; setiap sel tercatat pada sumber dengan penanda selnya masing-masing, "
        "dan seluruh barisan itu reproduced di bawah sel demi sel, tanpa perubahan, "
        "tanpa isi yang dikarang untuknya]"
    ),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page", type=int, required=True)
    parser.add_argument("--lang", choices=["en", "id"], required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    folder, label = LABEL[args.lang]
    path = REPO_ROOT / "ocr" / folder / f"page_{args.page:03d}.txt"
    source = clean(
        (REPO_ROOT / "ocr" / "enriched" / f"page_{args.page:03d}.txt").read_text(encoding="utf-8")
    )

    text = clean(path.read_text(encoding="utf-8"))
    blocks = dict((l, b) for l, b, _ in parse_blocks(text))
    arabic = blocks.get("Arabic", "")
    body = blocks.get(label, "")
    if not arabic or not body:
        print(f"  REFUSING: {path} has no {label} block to align")
        return 1

    # everything up to and including the diagram marker is the fixed head
    marker = "[Diagram text]"
    if marker in body:
        head = body[: body.index(marker) + len(marker)]
    else:
        head = body[: body.index("[?]")] if "[?]" in body else body

    src_cells = source.count("[?]")
    have_cells = body.count("[?]")

    print(f"  head            : {len(head)}c (through {marker!r})")
    print(f"  illegible cells : target {have_cells}  source {src_cells}")
    if have_cells == src_cells:
        print("  already aligned")
        return 0
    if not args.apply:
        print("  (dry run; pass --apply to rewrite)")
        return 0

    new_body = f"{head}\n{NOTE[args.lang]}\n" + " | ".join(["[?]"] * src_cells)
    path.write_text(f"Arabic:\n{arabic}\n\n{label}:\n{new_body}\n", encoding="utf-8")
    print(f"  wrote {path}: {label} block now carries all {src_cells} cells")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
