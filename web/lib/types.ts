export type Lang = "ar" | "en" | "id";
export type ViewMode = "text" | "page";

export interface LangMeta {
  code: Lang;
  label: string; // native label
  english: string;
  dir: "rtl" | "ltr";
}

export const LANGS: Record<Lang, LangMeta> = {
  ar: { code: "ar", label: "العربية", english: "Arabic", dir: "rtl" },
  en: { code: "en", label: "English", english: "English", dir: "ltr" },
  id: { code: "id", label: "Indonesia", english: "Indonesian", dir: "ltr" },
};

export const LANG_ORDER: Lang[] = ["ar", "en", "id"];

export interface TocEntry {
  id: string;
  title: Record<Lang, string>;
  startPage: number;
  endPage: number;
}

export interface ManuscriptPage {
  page: number; // 1..600
  sectionId: string;
  text: Record<Lang, string>;
  /** Per-page generated title in all 3 languages */
  title?: Record<Lang, string>;
  /** path to the scanned (non-OCR) PDF page image or pdf; generated sample used in dev */
  scanSrc?: string;
}

export interface LastRead {
  page: number;
  at: number; // epoch ms
  lang: Lang;
  mode: ViewMode;
}

export interface ReaderState {
  lang: Lang;
  mode: ViewMode;
  page: number;
  fontSize: number; // reading px scale factor base
  lastRead: LastRead | null;
  bookmarks: number[]; // page numbers
}
