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

/**
 * Canonical ~30 treatise sections of the Shams al-Ma'arif. Used as the TOC
 * whenever an input doesn't supply its own section list — the real bundled
 * manuscript is a flat page array with no `toc`, so without this it would
 * collapse into a single "Imported Manuscript" section (the bug we fix here).
 */
const CANONICAL_SECTIONS: { id: string; title: Record<Lang, string>; start: number }[] = [
  { id: "s01", title: { ar: "في ذكر الشمس والمعارف", en: "On the Sun and the Knowledges", id: "Tentang Matahari dan Pengetahuan" }, start: 1 },
  { id: "s02", title: { ar: "باب الأسماء الإلهية", en: "The Chapter of the Divine Names", id: "Bab Nama-nama Ilahi" }, start: 22 },
  { id: "s03", title: { ar: "خواص الحروف", en: "The Properties of the Letters", id: "Sifat-sifat Huruf" }, start: 43 },
  { id: "s04", title: { ar: "علم الحروف والجفر", en: "The Science of Letters and Jafr", id: "Ilmu Huruf dan Jafr" }, start: 64 },
  { id: "s05", title: { ar: "أسماء ملك الموت", en: "The Names of the Angel of Death", id: "Nama-nama Malaikat Maut" }, start: 85 },
  { id: "s06", title: { ar: "الأسماء العظام", en: "The Greatest Names", id: "Nama-nama Agung" }, start: 106 },
  { id: "s07", title: { ar: "الطلاسم والسيمياء", en: "Talismans and Simia", id: "Jimat dan Simia" }, start: 127 },
  { id: "s08", title: { ar: "صنعة الخاتم", en: "The Making of the Seal-Ring", id: "Pembuatan Cincin Meterai" }, start: 148 },
  { id: "s09", title: { ar: "خاتم سليمان", en: "The Seal of Solomon", id: "Meterai Sulaiman" }, start: 169 },
  { id: "s10", title: { ar: "عزائم الرياح", en: "The Constraining of the Winds", id: "Pengendalian Angin" }, start: 190 },
  { id: "s11", title: { ar: "خواص السيارات", en: "The Properties of the Planets", id: "Sifat-sifat Planet" }, start: 211 },
  { id: "s12", title: { ar: "أعمال الكواكب", en: "The Works of the Stars", id: "Amalan Bintang" }, start: 232 },
  { id: "s13", title: { ar: "باب الزنج والتتار", en: "The Chapter of the Zanj and the Tatars", id: "Bab Zanj dan Tartar" }, start: 253 },
  { id: "s14", title: { ar: "أسماء العزائم", en: "The Names of Constraining", id: "Nama-nama Pengikat" }, start: 274 },
  { id: "s15", title: { ar: "خاتم الأخيار", en: "The Seal of the Pious", id: "Meterai Orang Saleh" }, start: 295 },
  { id: "s16", title: { ar: "عمل اللوح المحفوظ", en: "The Work of the Preserved Tablet", id: "Amalan Lauh Mahfuz" }, start: 316 },
  { id: "s17", title: { ar: "خواص الملائكة", en: "The Properties of the Angels", id: "Sifat-sifat Malaikat" }, start: 337 },
  { id: "s18", title: { ar: "أسماء الحفظة", en: "The Names of the Guardians", id: "Nama-nama Penjaga" }, start: 358 },
  { id: "s19", title: { ar: "باب الجن والشياطين", en: "The Chapter of the Jinn and Devils", id: "Bab Jin dan Setan" }, start: 379 },
  { id: "s20", title: { ar: "عزيمة الجن", en: "The Conjuration of the Jinn", id: "Kuasa Jin" }, start: 400 },
  { id: "s21", title: { ar: "خاتم القطب", en: "The Seal of the Pole", id: "Meterai Kutub" }, start: 421 },
  { id: "s22", title: { ar: "الأوراد والحِزب", en: "The Litancies and Hizb", id: "Wirid dan Hizib" }, start: 442 },
  { id: "s23", title: { ar: "خواص الآيات", en: "The Properties of the Verses", id: "Sifat-sifat Ayat" }, start: 463 },
  { id: "s24", title: { ar: "أسماء الأنبياء", en: "The Names of the Prophets", id: "Nama-nama Nabi" }, start: 484 },
  { id: "s25", title: { ar: "عمل السبعين اسما", en: "The Work of the Seventy Names", id: "Amalan Tujuh Puluh Nama" }, start: 505 },
  { id: "s26", title: { ar: "خاتم الفلاح", en: "The Seal of Prosperity", id: "Meterai Kesejahteraan" }, start: 526 },
  { id: "s27", title: { ar: "باب الرُّقى", en: "The Chapter of Incantations", id: "Bab Ruqyah" }, start: 547 },
  { id: "s28", title: { ar: "خواص الأيام", en: "The Properties of the Days", id: "Sifat-sifat Hari" }, start: 568 },
  { id: "s29", title: { ar: "خاتم الختم", en: "The Seal of Seals", id: "Meterai Segala Meterai" }, start: 589 },
  { id: "s30", title: { ar: "الخاتمة والدعاء", en: "The Conclusion and the Prayer", id: "Penutup dan Doa" }, start: 598 },
];

/** Build the canonical 30-section TOC for a manuscript of `totalPages` pages. */
export function buildFallbackToc(totalPages: number): TocEntry[] {
  return CANONICAL_SECTIONS.map((s, i) => ({
    id: s.id,
    title: s.title,
    startPage: s.start,
    endPage: i + 1 < CANONICAL_SECTIONS.length ? CANONICAL_SECTIONS[i + 1].start - 1 : totalPages,
  }));
}

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
      title: (r.title as Record<Lang, string>) ?? undefined,
      scanSrc:
        (r.scanSrc as string) ??
        (r.scan as string) ??
        `https://shamsmaarif.warga-digital.com/page-${String(ip).padStart(3, "0")}.pdf`,
      text: pickText(r),
    });
  }

  if (!pages.size) {
    throw new Error("No valid pages after parsing (check page numbers / fields).");
  }

  // TOC: explicit if provided, else fall back to the canonical 30-section
  // treatise structure of the Shams al-Ma'arif (a flat page array has no
  // `toc` of its own). We never collapse the whole manuscript into a single
  // "Imported Manuscript" section — that loses all navigation.
  let toc: TocEntry[];
  if (rawToc && rawToc.length) {
    toc = rawToc.map((t, i) => {
      const te = parseTocEntry(t, i + 1, totalPages);
      return te;
    });
  } else {
    toc = buildFallbackToc(totalPages);
  }

  return { pages, toc };
}
