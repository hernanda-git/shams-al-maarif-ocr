import { TocEntry, ManuscriptPage, Lang } from "./types";
import { normalizeManuscriptInput, ManuscriptInput } from "./loadManuscript";

export const TOTAL_PAGES = 600;

/**
 * ~30 treatise sections of the Shams al-Ma'arif, each spanning a contiguous
 * range of pages. Start pages are deterministic; endPage = next start - 1.
 * (Used as fallback TOC when no imported data overrides it.)
 */
const RAW_SECTIONS: { id: string; title: Record<Lang, string>; start: number }[] = [
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

export const FALLBACK_TOC: TocEntry[] = RAW_SECTIONS.map((s, i) => ({
  id: s.id,
  title: s.title,
  startPage: s.start,
  endPage: i + 1 < RAW_SECTIONS.length ? RAW_SECTIONS[i + 1].start - 1 : TOTAL_PAGES,
}));

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
 * Synchronously seed the real manuscript from the bundled static JSON at
 * build/SSR time. Called once from the server component (page.tsx) so the
 * prerendered HTML already contains real text — no client-side fetch and no
 * "content flashes then swaps" on load. Falls back silently if the file is
 * absent (generator text is shown instead).
 */
export function seedManuscriptFromDisk(jsonPath: string): void {
  if (_override.source === "imported") return; // never clobber an explicit import
  try {
    // Read with Node fs (server only). Use require to avoid bundling in client.
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const fs = require("fs") as typeof import("fs");
    if (!fs.existsSync(jsonPath)) return;
    const raw = fs.readFileSync(jsonPath, "utf8");
    const json = JSON.parse(raw);
    if (Array.isArray(json) && json.length) {
      loadManuscript(json);
      _override.source = "generator"; // still "real" data, not "imported"
    }
  } catch {
    /* ignore — generator fallback stays */
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
    scanSrc: `/scans/page-${String(page).padStart(3, "0")}.png`,
    text: {
      ar: lorem("ar", page, sec.title.ar),
      en: lorem("en", page, sec.title.en),
      id: lorem("id", page, sec.title.id),
    },
  };
}

const _cache = new Map<number, ManuscriptPage>();

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
