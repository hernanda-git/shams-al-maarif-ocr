"use client";

import { Fragment, ReactNode } from "react";

/**
 * Block-aware, manuscript-faithful text renderer for the OCR transcriptions.
 *
 * The raw OCR text is a single block with meaningful internal structure:
 *   - a page numeral header:   — ٩٠ —            (Arabic-Indic digits)
 *   - verse stanzas:           line * line        (the * marks a half-verse caesura)
 *   - tables / magic squares:  | a | b | c |      (markdown pipe grids)
 *   - talisman/grid art:       rows of 𐍈 / ▢ / box chars (monospaced)
 *   - ordinary prose paragraphs separated by blank lines
 *
 * We split on blank lines into blocks, then render each block by its dominant
 * type so the page reads like the manuscript instead of one wrapped string.
 */

const TABLE_ROW_RE = /^\s*\|.*\|\s*$/;
const HALF_VERSE_RE = /\s*\*\s*/; // the " * " caesura between hemistichs
// a "grid art" line: packed box/ornament glyphs with little prose
const GRID_GLYPHS = /[𐍈▢◻◼▣▤▥▦▧▨▩⬛⬜⓪①②Ⅲ✶✵]/;

// --- Page-numeral header detection -----------------------------------------
// The manuscript uses several numeral glyph sets and wrapper marks that the
// strict `— N —` pattern misses:
//   • Arabic-Indic digits ٠-٩ (U+0660-0669)            — ٨٩ —
//   • Persian/Extended Arabic-Indic ۰-۹ (U+06F0-06F9)   — ۷۹ —
//   • ASCII digits                                       — 190 —
//   • wrappers: em/en/figure dash, bars, tatweel ـ, tilde, minus, parens
//       - ٨ -   ( ١١ )   ـ ٢١٧ ـ   -- ١٨ --
//   • bare top-of-page numerals (1-3 digits): ١١٠
// Anything that is NOT a genuine page numeral (years like 1927, "٤ مجلدات",
// prose) must be left alone.
const DIGIT_ONLY_RE = /^[٠-٩۰-۹0-9]+$/;
const SEP_RE = /[—‒―⎯─━~−֊ـ()-]/;

/**
 * Detects a page-number header at the start of `firstLine` and returns the
 * numeral string plus the character offset to slice from (so the numeral can
 * be stripped from the block). Handles:
 *   • isolated numerals:        — ٨٩ —   - ٨ -   ( ١١ )   ـ ٢١٧ ـ
 *   • bare top numerals:        ١١٠
 *   • numeral prepended to text on the same line:  — ۷۹ —  المعبر …   (common in OCR)
 * Returns null when the line is not a page numeral (years, prose, tables).
 */
function detectNumeral(firstLine: string): { numeral: string; sliceFrom: number } | null {
  const t = (firstLine || "").trim();
  if (!t) return null;

  const NUMERAL_WRAPPED = /^\s*[—‒―⎯─━~−֊ـ()-]*\s*[٠-٩۰-۹0-9]{1,5}\s*[—‒―⎯─━~−֊ـ()-]*\s*$/;
  const NUMERAL_BARE = /^\s*[٠-٩۰-۹0-9]{1,3}\s*$/;
  const NUMERAL_PREFIX = /^\s*[—‒―⎯─━~−֊ـ()-]*\s*([٠-٩۰-۹0-9]{1,5})\s*[—‒―⎯─━~−֊ـ()-]*\s+/;

  if (NUMERAL_WRAPPED.test(t)) {
    const m = t.match(/[٠-٩۰-۹0-9]{1,5}/);
    if (m) return { numeral: m[0], sliceFrom: firstLine.length };
  }
  if (NUMERAL_BARE.test(t)) {
    const m = t.match(/^\s*([٠-٩۰-۹0-9]{1,3})/);
    if (m) return { numeral: m[1], sliceFrom: firstLine.length };
  }
  const pm = firstLine.match(NUMERAL_PREFIX);
  if (pm) {
    const numeral = pm[1];
    // A bare (no separator) 4+ digit run at a line start is a year/number, not a page.
    const hasSep = SEP_RE.test(pm[0].replace(/[٠-٩۰-۹0-9]{1,5}/, ""));
    if (!hasSep && numeral.length > 3) return null;
    return { numeral, sliceFrom: pm[0].length };
  }
  return null;
}

function isGridArtLine(line: string): boolean {
  const t = line.trim();
  if (t.length === 0) return false;
  const glyphs = (t.match(/[𐍈▢◻◼▣▤▥▦▧▨▩⬛⬜⓪①②Ⅲ✶✵]/g) || []).length;
  // A genuine prose sentence never carries ≥20 ornament glyphs; a magic-square
  // or talisman line does. Use total glyph count (suffix runs included).
  return glyphs >= 20;
}

function parseTableRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((c) => c.trim());
}

function isTableSeparator(line: string): boolean {
  return /^\s*\|?[\s:|-]+\|?\s*$/.test(line) && line.includes("-");
}

/** Render one prose/verse block (may contain " * " caesuras). */
function renderVerseBlock(text: string, isAr: boolean): ReactNode {
  // Preserve the manuscript's own line breaks as soft breaks within the block,
  // but drop fully-empty lines so we don't emit phantom <p> gaps.
  const lines = text.split("\n").map((l) => l.trim());
  const kept = lines.filter((l) => l.length > 0);
  return (
    <div className={"verse-block" + (isAr ? " arabic" : "")}>
      {kept.map((line, i) => {
        const parts = line.split(HALF_VERSE_RE);
        return (
          <p key={i} className="verse-line">
            {parts.map((part, j) => (
              <Fragment key={j}>
                {j > 0 && <span className="verse-caesura" aria-hidden> ✦ </span>}
                <span>{part}</span>
              </Fragment>
            ))}
          </p>
        );
      })}
    </div>
  );
}

function renderTable(block: string[]): ReactNode {
  const rows: string[][] = [];
  for (const line of block) {
    if (isTableSeparator(line)) continue;
    rows.push(parseTableRow(line));
  }
  if (!rows.length) return null;
  const header = rows[0];
  const body = rows.slice(1);
  return (
    <div className="ms-table-wrap">
      <table className="ms-table">
        <thead>
          <tr>
            {header.map((c, i) => (
              <th key={i}>{c}</th>
            ))}
          </tr>
        </thead>
        {body.length > 0 && (
          <tbody>
            {body.map((r, i) => (
              <tr key={i}>
                {r.map((c, j) => (
                  <td key={j}>{c}</td>
                ))}
              </tr>
            ))}
          </tbody>
        )}
      </table>
    </div>
  );
}

function renderGridArt(block: string[]): ReactNode {
  return (
    <div className="ms-grid-art" dir="ltr">
      {block.map((line, i) => (
        <div key={i} className="ms-grid-row">
          {line.replace(/\s+/g, " ")}
        </div>
      ))}
    </div>
  );
}

export function ReaderText({
  text,
  isAr,
}: {
  text: string;
  isAr: boolean;
}) {
  // Split into blocks on blank lines.
  const rawBlocks = text.split(/\n\s*\n/).map((b) => b.trim()).filter(Boolean);

  return (
    <>
      {rawBlocks.map((block, bi) => {
        // Page numeral header may be the first line of an otherwise-mixed block
        // (e.g. "— ٨٩ —\n<verse> …") or prefixed to the text on the same line
        // (e.g. "— ۷۹ —  المعبر …"). Detect it across digit scripts and wrapper
        // marks, then strip it so the rest renders as verse/grid.
        const firstNewline = block.indexOf("\n");
        const firstLine = (firstNewline === -1 ? block : block.slice(0, firstNewline)).trim();
        const detected = detectNumeral(firstLine);
        let body = block;
        if (detected) {
          // If the numeral is on its own line, drop that line; if it shares the
          // first line with body text, slice it off the start of the line.
          body =
            firstNewline === -1
              ? block.slice(detected.sliceFrom).trim()
              : block.slice(firstNewline + 1).trim();
        }

        // Render the numeral rubric (if any) plus the rest of the block.
        const rest =
          body.length > 0 ? (
            <BlockBody key={`b${bi}`} body={body} isAr={isAr} />
          ) : null;

        if (detected) {
          return (
            <Fragment key={bi}>
              <div className="ms-numeral" dir="rtl">
                <span className="ms-numeral-mark">—</span>
                <span className="ms-numeral-num">{detected.numeral}</span>
                <span className="ms-numeral-mark">—</span>
              </div>
              {rest}
            </Fragment>
          );
        }

        if (rest) return rest;
        return null;
      })}
    </>
  );
}

/** Renders everything after a (possible) numeral line: table / grid / verse. */
function BlockBody({ body, isAr }: { body: string; isAr: boolean }): ReactNode {
  const lines = body.split("\n").map((l) => l.trim()).filter(Boolean);
  if (lines.length === 0) return null;

  // Table block: every (non-separator) line is a pipe row
  if (lines.length >= 2 && lines.every((l) => TABLE_ROW_RE.test(l))) {
    return renderTable(lines);
  }

  // Pull out grid-art lines (magic squares / talismans) even from a mixed
  // block, render them as monospace art; the rest as verse/prose.
  const gridIdx = new Set<number>();
  lines.forEach((l, i) => {
    if (isGridArtLine(l)) gridIdx.add(i);
  });
  if (gridIdx.size > 0) {
    const versePart = lines.filter((_, i) => !gridIdx.has(i));
    const gridPart = lines.filter((_, i) => gridIdx.has(i));
    return (
      <>
        {versePart.length > 0 && renderVerseBlock(versePart.join("\n"), isAr)}
        {renderGridArt(gridPart)}
      </>
    );
  }

  // Verse / prose block
  return renderVerseBlock(body, isAr);
}
