"""Assemble a target file from a canonical Arabic source plus a body-only draft.

A translation worker drafted the English body for page 333 correctly but every
attempt to write the target FILE failed: the scratch drafts contain only the
body, with no `Arabic:` / `English:` labels, so the parser saw one 4,256c
`Arabic:` block and a 7-character `English:` block holding only the folio line.

The body itself is sound, so this assembles the file mechanically: canonical
Arabic block, then the label, then the body, exactly as the V2 contract
requires. It never edits the body.

Usage:
  uv run --no-project python scripts/assemble_target_file.py --scan
  uv run --no-project python scripts/assemble_target_file.py --apply \
      --page 333 --lang en --body <path-to-body-only-draft>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from recover_sibling_blocks import (  # noqa: E402
    _ARABIC_IN_TARGET,
    blocks_for,
    clean,
    is_translation_like,
    parse_blocks,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
LABEL = {"en": ("enriched_en", "English"), "id": ("enriched_id", "Indonesia")}
LANG_OF = {"English": "en", "Indonesia": "id"}


def scan() -> list[dict]:
    """Find target files whose body is stranded outside its own label block."""
    found = []
    for lang, (folder, label) in LABEL.items():
        for page in range(1, 605):
            path = REPO_ROOT / "ocr" / folder / f"page_{page:03d}.txt"
            if not path.exists():
                continue
            text = clean(path.read_text(encoding="utf-8"))
            labels = [l for l, _, _ in parse_blocks(text)]
            if labels == ["Arabic", label]:
                continue  # already canonical
            own = blocks_for(text, label)
            own_body = own[0] if own else ""
            stray = [
                (l, len(b))
                for l, b, _ in parse_blocks(text)
                if l not in ("Arabic", label) and is_translation_like(b, lang)
            ]
            if own_body or stray:
                found.append(
                    {
                        "page": page,
                        "lang": lang,
                        "folder": folder,
                        "label": label,
                        "path": path,
                        "own_chars": len(own_body),
                        "stray": stray,
                    }
                )
    return found


def assemble(page: int, lang: str, body: str) -> tuple[Path, int]:
    folder, label = LABEL[lang]
    canonical = clean(
        (REPO_ROOT / "ocr" / "enriched" / f"page_{page:03d}.txt").read_text(encoding="utf-8")
    )
    path = REPO_ROOT / "ocr" / folder / f"page_{page:03d}.txt"
    path.write_text(f"Arabic:\n{canonical}\n\n{label}:\n{body}\n", encoding="utf-8")
    return path, len(body)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--page", type=int)
    parser.add_argument("--lang", choices=["en", "id"])
    parser.add_argument("--body", help="path to a body-only draft (no labels)")
    args = parser.parse_args(argv)

    if args.apply:
        if not (args.page and args.lang and args.body):
            parser.error("--apply needs --page, --lang and --body")
        body = clean(Path(args.body).read_text(encoding="utf-8"))
        if not is_translation_like(body, args.lang):
            print(f"  REFUSING: the draft does not look like {args.lang} text")
            return 1
        arabic = len(_ARABIC_IN_TARGET.findall(body))
        path, n = assemble(args.page, args.lang, body)
        print(f"  wrote {path}  ({n}c of {LABEL[args.lang][1]}, {arabic} Arabic letters)")
        return 0

    found = scan()
    for f in found:
        print(
            f"  p{f['page']:03d} {f['lang']}  own block={f['own_chars']}c "
            f"stray translation-like blocks={f['stray']}"
        )
    print(f"\ntarget files needing assembly: {len(found)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
