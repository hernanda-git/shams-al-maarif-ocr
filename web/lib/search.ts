import { getPage, TOTAL_PAGES, sectionOfPage } from "./manuscript";
import { Lang } from "./types";

export interface SearchHit {
  page: number;
  section: string;
  snippet: string;
  /** character offset of the match inside the plain text (for highlight) */
  at: number;
}

/**
 * Full-text search across the (OCR) manuscript for one language.
 * Scans all pages lazily; deterministic, no external index needed for 600 pages.
 */
export function searchAll(
  query: string,
  lang: Lang,
  limit = 60
): SearchHit[] {
  const q = query.trim().toLowerCase();
  if (q.length < 2) return [];

  const hits: SearchHit[] = [];
  for (let p = 1; p <= TOTAL_PAGES; p++) {
    const text = getPage(p).text[lang];
    const idx = text.toLowerCase().indexOf(q);
    if (idx === -1) continue;

    // build a snippet around the match
    const start = Math.max(0, idx - 60);
    const end = Math.min(text.length, idx + q.length + 80);
    let snippet = text.slice(start, end);
    if (start > 0) snippet = "…" + snippet;
    if (end < text.length) snippet = snippet + "…";

    hits.push({
      page: p,
      section: sectionOfPage(p).title[lang],
      snippet,
      at: idx - start, // offset within snippet
    });
    if (hits.length >= limit) break;
  }
  return hits;
}
