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

const NUMERAL_RE = /^\s*—\s*[٠-٩0-9]+\s*—\s*$/;
const TABLE_ROW_RE = /^\s*\|.*\|\s*$/;
const HALF_VERSE_RE = /\s*\*\s*/; // the " * " caesura between hemistichs
// a "grid art" line: packed box/ornament glyphs with little prose
const GRID_GLYPHS = /[𐍈▢◻◼▣▤▥▦▧▨▩⬛⬜⓪①②Ⅲ✶✵]/;

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
        let body = block;
        let numeral: string | null = null;

        // Page numeral header may be the first line of an otherwise-mixed block
        // (e.g. "— ٨٩ —\n<verse> …"). Strip it so the rest renders as verse/grid.
        const firstNewline = block.indexOf("\n");
        const firstLine = (firstNewline === -1 ? block : block.slice(0, firstNewline)).trim();
        const numMatch = firstLine.match(/^—\s*([٠-٩0-9]+)\s*—$/);
        if (numMatch) {
          numeral = numMatch[1];
          body = firstNewline === -1 ? "" : block.slice(firstNewline + 1).trim();
        } else if (NUMERAL_RE.test(block)) {
          numeral = block.match(/[٠-٩0-9]+/)?.[0] ?? null;
          body = "";
        }

        // Render the numeral rubric (if any) plus the rest of the block.
        const rest =
          body.length > 0 ? (
            <BlockBody key={`b${bi}`} body={body} isAr={isAr} />
          ) : null;

        if (numeral) {
          return (
            <Fragment key={bi}>
              <div className="ms-numeral" dir="rtl">
                <span className="ms-numeral-mark">—</span>
                <span className="ms-numeral-num">{numeral}</span>
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
