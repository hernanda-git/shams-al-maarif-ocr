import { TocEntry, ManuscriptPage, Lang, LANG_ORDER } from "./types";

/**
 * Format-tolerant input. Accepts any of:
 *  - Array of { page, ar, en, id }                 (flat keys)
 *  - Array of { page, text: { ar, en, id } }       (nested text)
 *  - Array of { page, title?, body?, content? }    (lang guessed from keys)
 *  - { pages: [...], toc?: [...] }                 (wrapped)
 * Section/TOC may be supplied as { id, title:{ar,en,id}|string, start, end }.
 */
export type ManuscriptInput =
  | unknown[]
  | { pages?: unknown[]; toc?: unknown[] }
  | string;

function asObject(v: unknown): Record<string, unknown> {
  return typeof v === "object" && v !== null ? (v as Record<string, unknown>) : {};
}

function pickText(o: Record<string, unknown>): Record<Lang, string> {
  const out: Record<Lang, string> = { ar: "", en: "", id: "" };
  // direct lang keys
  for (const l of LANG_ORDER) {
    if (typeof o[l] === "string" && (o[l] as string).length) out[l] = o[l] as string;
  }
  // nested text.{lang}
  const t = asObject(o.text);
  for (const l of LANG_ORDER) {
    if (typeof t[l] === "string" && (t[l] as string).length) out[l] = t[l] as string;
  }
  // fallback: body/content/translation-ish keys
  const fb = (o.body ?? o.content ?? o.text_ ?? o.translation) as string | undefined;
  if (fb && !out.en) out.en = fb;
  return out;
}

function parseTocEntry(o: unknown, fallbackStart: number, fallbackEnd: number): TocEntry {
  const r = asObject(o);
  const titleRaw = r.title;
  let title: Record<Lang, string>;
  if (typeof titleRaw === "string") {
    title = { ar: titleRaw, en: titleRaw, id: titleRaw };
  } else if (titleRaw && typeof titleRaw === "object") {
    const tr = titleRaw as Record<string, unknown>;
    const strOr = (v: unknown) => (typeof v === "string" ? v : "");
    title = {
      ar: strOr(tr.ar) || (typeof titleRaw === "string" ? titleRaw : ""),
      en: strOr(tr.en) || (typeof titleRaw === "string" ? titleRaw : ""),
      id: strOr(tr.id) || (typeof titleRaw === "string" ? titleRaw : ""),
    };
  } else {
    title = { ar: `Section ${fallbackStart}`, en: `Section ${fallbackStart}`, id: `Bagian ${fallbackStart}` };
  }
  return {
    id: (r.id as string) ?? `s${fallbackStart}`,
    title,
    startPage: Number(r.start ?? r.startPage ?? fallbackStart),
    endPage: Number(r.end ?? r.endPage ?? fallbackEnd),
  };
}

export function normalizeManuscriptInput(
  input: ManuscriptInput,
  totalPages: number
): { pages: Map<number, ManuscriptPage>; toc: TocEntry[] } {
  // string -> try JSON
  let data: unknown = input;
  if (typeof input === "string") {
    try {
      data = JSON.parse(input);
    } catch {
      throw new Error("Invalid JSON string provided to loader.");
    }
  }

  let rawPages: unknown[] = [];
  let rawToc: unknown[] | undefined;

  if (Array.isArray(data)) {
    rawPages = data;
  } else if (data && typeof data === "object") {
    const d = data as Record<string, unknown>;
    rawPages = Array.isArray(d.pages) ? d.pages : [];
    rawToc = Array.isArray(d.toc) ? d.toc : undefined;
  }

  if (!rawPages.length) {
    throw new Error("No page entries found in input.");
  }

  const pages = new Map<number, ManuscriptPage>();
  for (const entry of rawPages) {
    const r = asObject(entry);
    const page = Number(r.page ?? r.p ?? r.number ?? r.n);
    if (!Number.isFinite(page) || page < 1 || page > totalPages) continue;
    const ip = page as number;
    pages.set(ip, {
      page: ip,
      sectionId: (r.sectionId as string) ?? (r.section as string) ?? "",
      scanSrc:
        (r.scanSrc as string) ??
        (r.scan as string) ??
        `/scans/page-${String(ip).padStart(3, "0")}.png`,
      text: pickText(r),
    });
  }

  if (!pages.size) {
    throw new Error("No valid pages after parsing (check page numbers / fields).");
  }

  // TOC: explicit if provided, else derive contiguous ranges from present pages
  let toc: TocEntry[];
  if (rawToc && rawToc.length) {
    toc = rawToc.map((t, i) => {
      const te = parseTocEntry(t, i + 1, totalPages);
      return te;
    });
  } else {
    const sorted = Array.from(pages.keys()).sort((a, b) => a - b);
    const start = sorted[0];
    const end = sorted[sorted.length - 1];
    toc = [
      {
        id: "imported",
        title: { ar: "المخطوط المستورد", en: "Imported Manuscript", id: "Naskah Terimpor" },
        startPage: start,
        endPage: end,
      },
    ];
  }

  return { pages, toc };
}
