import { TocEntry, ManuscriptPage, Lang } from "./types";
import { normalizeManuscriptInput, buildFallbackToc, ManuscriptInput } from "./loadManuscript";

export const TOTAL_PAGES = 600;

/**
 * Canonical ~30 treatise sections of the Shams al-Ma'arif, each spanning a
 * contiguous range of pages. Start pages are deterministic; endPage = next
 * start - 1. Used as the fallback TOC whenever no imported data overrides it.
 * (Definition lives in loadManuscript.ts as buildFallbackToc — single source.)
 */
export const FALLBACK_TOC: TocEntry[] = buildFallbackToc(TOTAL_PAGES);

/** Live TOC getter — reflects imported overrides (Sidebar/GridModal call this). */
export function getToc(): TocEntry[] {
  return _override.toc;
}

// ============ In-memory override store (filled by imported data) ============
interface Override {
  pages: Map<number, ManuscriptPage>;
  toc: TocEntry[];
  source: "generator" | "imported";
}

const _override: Override = {
  pages: new Map(),
  toc: FALLBACK_TOC,
  source: "generator",
};

export function isUsingImportedData(): boolean {
  return _override.source === "imported";
}

export function getImportStats(): { pages: number; source: string } {
  return { pages: _override.pages.size, source: _override.source };
}

export function loadManuscript(input: ManuscriptInput): { pages: number; sections: number } {
  const { pages, toc } = normalizeManuscriptInput(input, TOTAL_PAGES);
  _override.pages = pages;
  _override.toc = toc;
  _override.source = "imported";
  return { pages: pages.size, sections: toc.length };
}

export function clearImportedData(): void {
  _override.pages = new Map();
  _override.toc = FALLBACK_TOC;
  _override.source = "generator";
}

/**
 * Hydrate the (client-side) in-memory store from data passed down from the
 * server component. Unlike loadManuscript(), this marks the source as
 * "generator" so an explicit user import can still override it, and it never
 * emits a relative /scans/... path — any missing scanSrc falls back to the
 * absolute R2 URL.
 */
export function hydrateManuscript(input: ManuscriptInput): void {
  const { pages, toc } = normalizeManuscriptInput(input, TOTAL_PAGES);
  _override.pages = pages;
  _override.toc = toc;
  _override.source = "generator";
}

/**
 * Seed a single page into the override store for SSR (avoids parsing the
 * full 7.8 MB manuscript on every request).
 */
export function seedSinglePage(pageData: Record<string, unknown>): void {
  if (_override.source === "imported") return;
  try {
    const { pages } = normalizeManuscriptInput([pageData], TOTAL_PAGES);
    for (const [k, v] of pages) {
      _override.pages.set(k, v);
    }
  } catch {
    /* ignore */
  }
}

export function sectionOfPage(page: number): TocEntry {
  const toc = _override.toc;
  for (const s of toc) {
    if (page >= s.startPage && page <= s.endPage) return s;
  }
  return toc[toc.length - 1];
}

/** Deterministic placeholder so the reader always has *something* to show. */
function generatePage(page: number): ManuscriptPage {
  const sec = sectionOfPage(page);
  return {
    page,
    sectionId: sec.id,
    scanSrc: `https://shamsmaarif.warga-digital.com/page-${String(page).padStart(3, "0")}.pdf`,
    text: {
      ar: lorem("ar", page, sec.title.ar),
      en: lorem("en", page, sec.title.en),
      id: lorem("id", page, sec.title.id),
    },
  };
}

const _cache = new Map<number, ManuscriptPage>();

/** Page title entry — lightweight, no full text. */
export interface PageTitleEntry {
  page: number;
  title: Record<Lang, string>;
}

/** Return all 600 page titles. Only reads the `title` field — no full text. */
export function getPageTitles(): PageTitleEntry[] {
  const arr: PageTitleEntry[] = [];
  for (let p = 1; p <= TOTAL_PAGES; p++) {
    const imp = _override.pages.get(p);
    if (imp && imp.title) {
      arr.push({ page: p, title: imp.title });
    } else {
      // fallback: use section title
      const sec = sectionOfPage(p);
      arr.push({ page: p, title: sec.title });
    }
  }
  return arr;
}

export function getPage(page: number): ManuscriptPage {
  const p = Math.min(TOTAL_PAGES, Math.max(1, page));
  // 1) imported data wins
  const imp = _override.pages.get(p);
  if (imp) return imp;
  // 2) memoized generator fallback
  if (_cache.has(p)) return _cache.get(p)!;
  const mp = generatePage(p);
  _cache.set(p, mp);
  return mp;
}

export function getSectionTitle(page: number, lang: Lang): string {
  return sectionOfPage(page).title[lang];
}

function lorem(lang: Lang, page: number, sectionTitle: string): string {
  const seeds: Record<Lang, [string, string, string]> = {
    ar: [
      "بسم الله الرحمن الرحيم. وفي هذا الموضع يُذكر ما أُودع في طيّ الكلمات من الأسرار والأنوار، فاعتبر يا ذا البصيرة بما تضمّنته هذه الصحيفة من الحِكَم والخواصّ.",
      "واعلم أن للحروف جواهرَ وأرواحًا تدبّرُ بها الملكوتُ، ومن عرفَ مقامَها فُتحت عليه مغاليقُ الغيب، وانشرحَ صدرُه لنورِ المعرفة.",
      `وهذا هو الفصل المعنون: «${sectionTitle}». وفيه بيانُ ما يُستخرج من الأسماء والأعمال على سننِ الحكماء المتقدمين.`,
    ],
    en: [
      "In the name of the Merciful. Herein is related what has been lodged within the folds of words — secrets and lights — so that the discerning may ponder the wisdom and properties contained in this leaf.",
      "Know that the letters possess essences and spirits by which the celestial dominion is governed; and he who knows their station shall have the locks of the unseen opened unto him, and his breast dilated with the light of knowledge.",
      `This is the chapter entitled: "${sectionTitle}". In it is the exposition of what is drawn forth from the Names and the works, after the manner of the ancients.`,
    ],
    id: [
      "Dengan nama Yang Maha Pengasih. Di sini diceritakan apa yang tersimpan dalam lipatan kata — rahasia dan cahaya — agar orang yang berpandangan tajam merenungkan hikmah dan sifat yang terkandung dalam lembaran ini.",
      "Ketahuilah bahwa huruf memiliki inti dan ruh yang mengatur kerajaan langit; dan siapa yang mengetahui kedudukannya, maka akan dibukakan baginya gembok alam gaib, serta dadanya diluaskan dengan cahaya ma'rifat.",
      `Inilah bab yang berjudul: "${sectionTitle}". Di dalamnya dijelaskan apa yang diambil dari nama-nama dan amalan, menurut jalan para hukama terdahulu.`,
    ],
  };
  const base = seeds[lang];
  const a = base[page % 3];
  const b = base[(page + 1) % 3];
  const c = base[(page + 2) % 3];
  return `${a}\n\n${b}\n\n${c}`;
}
