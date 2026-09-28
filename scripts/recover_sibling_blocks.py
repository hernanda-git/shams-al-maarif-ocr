"""Deterministic repair helpers for the Shams al-Ma'arif tri-lingual dataset.

The batch writer occasionally put a translation in the *wrong sibling file*:

  * an ``English:`` block lands in ``ocr/enriched_id/page_NNN.txt`` while
    ``ocr/enriched_en/page_NNN.txt`` keeps only its ``Arabic:`` block;
  * an ``Indonesia:`` block is present but unlabelled, or its label sits inline
    on the same line as other text rather than on its own line;
  * a ``--- PAGE NNN TRANSLATION ---`` batch header or a
    ``[combined output - see batch]`` stub is left inside a block.

Every function here is pure: it reads text and returns a plan. Nothing writes
files. ``scripts/recover_sibling_blocks.py`` is the only writer, and it is
deliberately separate so the decision logic stays testable.
"""

from __future__ import annotations

import re
import unicodedata

LABELS = ("Arabic", "English", "Indonesia")

# A label heading: either on its own line or trailing other text on the line.
_LABEL_LINE = re.compile(r"^[ \t]*(Arabic|English|Indonesia)[ \t]*:[ \t]*$")
_LABEL_INLINE = re.compile(r"(Arabic|English|Indonesia)[ \t]*:")
_ANY_LABEL = re.compile(r"(?m)^[ \t]*(Arabic|English|Indonesia)[ \t]*:")

# Batch artifacts that must never survive into a target block.
_BATCH_HEADER = re.compile(
    r"^[ \t]*---[ \t]*PAGE[ \t]+\d+[ \t]*TRANSLATION[ \t]*---[ \t]*$", re.MULTILINE
)
_COMBINED_STUB = re.compile(
    r"^\[combined output[^\\\]]*\]$", re.IGNORECASE | re.MULTILINE
)
_COMBINED_INLINE = re.compile(r"\[combined output[^\]]*\]", re.IGNORECASE)

_ARABIC_RANGE = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")

# Arabic *letters* only. A target block may legitimately contain an Arabic-Indic
# folio numeral ('— ٥٣ —' survives in accepted ID pages), so digits must not count
# as Arabic script or every valid block is rejected.
_ARABIC_IN_TARGET = re.compile(r"[ؠ-يٮ-ۓݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿]")

# Non-Latin symbols that are NOT translation text: magic-square glyphs (U+10348
# OLD ITALIC), box drawing, geometric shapes, dingbats. A block made of these is
# layout art, never a translation -- p095's ID file is 16 KB of U+10348.
# Punctuation that legitimately appears in a translation and must not count as
# an exotic symbol.
_ALLOWED_PUNCT = set("—–-'\"()[]{}|/,.:;!?")


def _is_symbol(ch: str) -> bool:
    """True for a glyph that carries no Latin linguistic content.

    ``\\w`` is Unicode-aware, so U+10348 (OLD ITALIC, the magic-square glyph)
    counts as a word character and a naive ``[^\\w\\s]`` test misses it. Judge
    each character explicitly instead: anything non-ASCII that is not an Arabic
    letter, an Arabic-Indic digit, or approved punctuation is layout art.
    """
    if ch.isspace() or ch.isascii() and ch.isalnum():
        return False
    if ch in _ALLOWED_PUNCT:
        return False
    if ch.isascii():
        return False
    if _ARABIC_IN_TARGET.match(ch):
        return False
    if "٠" <= ch <= "۹" or ch.isdigit():
        return False
    return True


_LATIN_WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")

# Function-word probes used only to confirm a body is in the expected language.
# Calibrated against the known-good corpus (see the note on the thresholds).
_INDO_MARKERS = frozenset({
    "yang", "dan", "tidak", "ada", "ini", "dengan", "untuk", "adalah", "pada",
    "akan", "dalam", "halaman", "dari", "ke", "di", "itu", "atau", "juga",
    "sudah", "bagi", "kepada", "kepadanya", "maka", "pun", "punlah", "adalah",
})
_ENG_MARKERS = frozenset({
    "the", "and", "not", "this", "with", "for", "is", "that", "was", "were",
    "of", "to", "in", "it", "he", "she", "they", "which", "as", "be", "has",
    "have", "said", "his", "her", "their", "upon", "from", "there",
})


def marker_density(text: str, markers: frozenset[str]) -> float:
    """Fraction of lowercase word tokens present in ``markers``."""
    tokens = _LATIN_WORD.findall(text.lower())
    if not tokens:
        return 0.0
    return sum(1 for t in tokens if t in markers) / len(tokens)

# The canonical no-text source form and the exact markers the V2 contract
# requires for it. Aligned to scripts/verify_translation_v2_page.py, which is
# authoritative: for a blank source the target body must equal EN_NO_TEXT_MARKER
# / ID_NO_TEXT_MARKER exactly. Nothing else is a valid blank-page translation,
# and the "tidak ada teks pada halaman ini" family is a BUILDER FALLBACK
# (ID_FALLBACKS) that the validator rejects -- so the two sets must not overlap.
_BLANK_SOURCE = re.compile(r"^---\s*\nthere is no text on this page\.\s*\n---$", re.IGNORECASE)
BLANK_MARKERS = {
    "en": {"[NO VISIBLE TEXT]"},
    "id": {"[TIDAK ADA TEKS TERLIHAT]"},
}

# Strings that build_manuscript_json.py synthesises when a block is missing.
# They look like prose and would pass every shape check, so they must be refused
# explicitly -- verify_translation_v2_page.py rejects them as "fallback text is
# not allowed on a content page", and propagating one would launder a missing
# translation into the dataset.
FALLBACK_STRINGS = {
    "en": {"(no english text on this page)", "(no english text on this page.)",
           "(no arabic text on this page)", "there is no text on this page.",
           "there is no visible arabic text on this page."},
    "id": {"(tidak ada teks pada halaman ini)", "(tidak ada teks pada halaman ini.)",
           "tidak ada teks pada halaman ini.",
           "tidak ada teks arab yang terlihat pada halaman ini."},
}


def is_fallback(body: str, lang: str | None) -> bool:
    """True when a body is a builder-synthesised fallback, not a translation."""
    if lang is None:
        return False
    return clean(body).casefold() in FALLBACK_STRINGS[lang]


def clean(text: str | None) -> str:
    """Normalise newlines and strip outer whitespace."""
    if not text:
        return ""
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def strip_artifacts(text: str) -> str:
    """Remove batch-artifact lines and combined-output stubs from a block."""
    out = _BATCH_HEADER.sub("", text)
    out = _COMBINED_STUB.sub("", out)
    out = _COMBINED_INLINE.sub("", out)
    # collapse the blank-line debris the removals leave behind
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def parse_blocks(text: str) -> list[tuple[str, str, int]]:
    """Return ``(label, body, start_line)`` for every labelled block, in order.

    A label is recognised either on its own line (the canonical shape) or
    trailing other text on the same line. The latter is p543's real shape:
    ``<arabic text> Indonesia: <indonesian>``, where the block begins at the
    label's column rather than on the following line.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")

    # (label_line, body_line, body_col, label)
    positions: list[tuple[int, int, int, str]] = []
    for index, line in enumerate(lines):
        own_line = _LABEL_LINE.match(line)
        if own_line:
            # canonical shape: body begins on the following line
            positions.append((index, index + 1, 0, own_line.group(1)))
            continue
        inline = _LABEL_INLINE.search(line)
        if inline:
            # p543 shape: body begins right after the label's colon, same line
            positions.append((index, index, inline.end(), inline.group(1)))

    blocks: list[tuple[str, str, int]] = []
    for order, (label_line, body_line, body_col, label) in enumerate(positions):
        end_line = positions[order + 1][0] if order + 1 < len(positions) else len(lines)

        collected: list[str] = []
        if body_line < end_line:
            tail = lines[body_line][body_col:].strip()
            if tail:
                collected.append(tail)
            collected.extend(lines[body_line + 1 : end_line])
        body = "\n".join(collected).strip()
        blocks.append((label, body, label_line))
    return blocks


def extract_inline(text: str, label: str) -> str | None:
    """Return the body of ``label``, or ``None`` when the label is absent.

    Unlike a strict line-anchored parser this also matches a label that trails
    other text on its line.
    """
    for found, body, _ in parse_blocks(text):
        if found == label:
            return body
    return None


def blocks_for(text: str, label: str) -> list[str]:
    """Return every body labelled ``label``, in file order."""
    return [body for found, body, _ in parse_blocks(text) if found == label]


def arabic_ratio(text: str) -> float:
    """Fraction of characters that are Arabic script."""
    if not text:
        return 0.0
    return len(_ARABIC_IN_TARGET.findall(text)) / len(text)


def is_blank_source(canonical: str) -> bool:
    """True when the canonical Arabic source is the explicit no-text form."""
    return bool(_BLANK_SOURCE.match(clean(canonical)))


def is_blank_marker(body: str, lang: str) -> bool:
    """True when a body is one of the accepted no-text markers for ``lang``."""
    return clean(body).casefold() in {m.casefold() for m in BLANK_MARKERS[lang]}


def symbol_load(body: str) -> float:
    """Fraction of non-space characters that are non-Latin symbols."""
    compact = [ch for ch in body if not ch.isspace()]
    if not compact:
        return 0.0
    return sum(1 for ch in compact if _is_symbol(ch)) / len(compact)


def prose_score(body: str) -> int:
    """Count of real Latin words. Distinguishes prose from layout art."""
    return len(_LATIN_WORD.findall(body))


def is_translation_like(body: str, lang: str | None = None) -> bool:
    """True when a body looks like a real Latin-script translation.

    Rejects: empty bodies, verbatim Arabic, batch stubs, and -- importantly --
    blocks that are mostly magic-square/box-drawing art with no real words.
    ``p095``'s ID file is 16 KB of U+10348 glyphs; a naive script check calls
    that "non-Arabic" and would treat it as an unlabelled translation.
    """
    body = strip_artifacts(clean(body))
    if lang is not None and is_fallback(body, lang):
        return False  # a synthesised "missing translation" placeholder
    if lang is not None and is_blank_marker(body, lang):
        return True  # a legitimate no-text marker for a blank page
    if len(body) < 25:
        return False
    if arabic_ratio(body) > 0.15:
        return False
    if prose_score(body) < 4:
        return False
    if symbol_load(body) > 0.25:
        return False
    # Confirm the body is in the EXPECTED language. Calibrated on the
    # known-good corpus: 566/566 accepted English bodies contain zero
    # Indonesian function words, and 518/592 Indonesian bodies contain zero
    # English ones, so a strong density on the WRONG language is decisive
    # evidence that a block was filed under the wrong label. The 2% floor
    # keeps tables, grids, and proper-noun pages from tripping the check.
    if lang == "en" and marker_density(body, _INDO_MARKERS) > 0.02:
        return False
    if lang == "id" and marker_density(body, _ENG_MARKERS) > 0.02:
        return False
    return True


def plan_page(
    sibling_text: str,
    label: str,
    kind: str = "enriched_en",
    lang: str | None = None,
) -> dict:
    """Decide how to repair one page's target block.

    ``kind`` is the folder the file lives in; ``lang`` is the ``en``/``id`` key
    used for blank-marker recognition. Returns one of three actions:

    ``recover``
        The block exists in the sibling file and is translation-like. Copy it.
    ``relabel``
        The sibling file already *is* the target language but carries no usable
        ``label``; wrap the whole body instead of extracting one.
    ``translate``
        No usable text exists; a human/LLM must translate from the Arabic.
    """
    cleaned_sibling = strip_artifacts(clean(sibling_text))

    candidates = [
        b for b in blocks_for(cleaned_sibling, label) if is_translation_like(b, lang)
    ]
    if candidates:
        return {
            "action": "recover",
            "body": strip_artifacts(candidates[0]),
            "reason": f"{label} block found in sibling file ({len(candidates[0])} chars)",
        }

    # No labelled block. If the file is entirely a non-Arabic Latin body, it is
    # an unlabelled translation and only needs the label restored.
    without_label = _ANY_LABEL.sub("", cleaned_sibling).strip()
    if is_translation_like(without_label, lang):
        return {
            "action": "relabel",
            "body": strip_artifacts(without_label),
            "reason": f"{kind} file body is already {label}-language but unlabelled",
        }

    return {
        "action": "translate",
        "body": "",
        "reason": f"no {label} block and no unlabelled {label} body in sibling file",
    }


def fold_ratio(text: str) -> float:
    """Normalise Arabic (drop diacritics/tatweel) for tolerant comparison."""
    stripped = "".join(
        ch
        for ch in unicodedata.normalize("NFKD", text or "")
        if not unicodedata.combining(ch) and ch != "ـ"
    )
    return 0.0 if not stripped else len(stripped) / max(1, len(text))
