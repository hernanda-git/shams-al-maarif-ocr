"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getPage, getSectionTitle, TOTAL_PAGES, hydrateManuscript } from "@/lib/manuscript";
import { Lang, ViewMode, LANGS } from "@/lib/types";
import { useReaderStore, THEMES, ThemeName } from "@/lib/useReaderStore";
import { TopBar } from "@/components/TopBar";
import { Sidebar } from "@/components/Sidebar";
import { Reader } from "@/components/Reader";
import { PageViewer } from "@/components/PageViewer";
import { ProgressDock } from "@/components/ProgressDock";
import { GridModal } from "@/components/GridModal";
import { SearchModal } from "@/components/SearchModal";
import { ImportPanel } from "@/components/ImportPanel";

const SCROLL_KEY = (p: number) => `shams-scroll-p${p}`;

export default function ReaderApp({
  serverPages,
  initialPage = 1,
  initialLang = "en",
  initialMode = "text",
}: {
  serverPages?: unknown;
  initialPage?: number;
  initialLang?: Lang;
  initialMode?: ViewMode;
}) {
  const store = useReaderStore();

  const [lang, setLang] = useState<Lang>(initialLang);
  const [mode, setMode] = useState<ViewMode>(initialMode);
  const [page, setPage] = useState<number>(initialPage);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [gridOpen, setGridOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);

  const scrollRef = useRef<HTMLDivElement>(null);
  const jumpCounter = useRef(0);

  // NOTE: manuscript data is already seeded at SSR time (see page.tsx). The
  // client runs in a separate module instance with an empty in-memory store,
  // so we hydrate it from the server-passed array on mount — this is what
  // makes the real OCR text + R2 scanSrc available to the client renderer
  // (otherwise it would fall back to placeholder /scans/... paths).
  useEffect(() => {
    if (Array.isArray(serverPages) && serverPages.length) {
      try {
        hydrateManuscript(serverPages);
      } catch {
        /* ignore — placeholder fallback stays */
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Restore last-read position on mount ONLY when there is no deep-link in
  // the URL (deep-link values are already applied via initial state above).
  useEffect(() => {
    if (window.location.search) return; // deep-link wins
    if (store.lastRead) {
      setLang(store.lastRead.lang);
      setMode(store.lastRead.mode);
      setPage(store.lastRead.page);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // mark read whenever page/lang/mode changes (stable callback, no loop)
  const { markRead } = store;
  useEffect(() => {
    markRead(page, lang, mode);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, lang, mode]);

  const data = useMemo(() => getPage(page), [page, lang, mode]);
  const sectionTitle = useMemo(() => getSectionTitle(page, lang), [page, lang]);
  const progress = useMemo(() => page / TOTAL_PAGES, [page]);
  const dir = LANGS[lang].dir;

  // ---- scroll memory (T1d) ----
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const saved = Number(localStorage.getItem(SCROLL_KEY(page)) || "0");
    const id = requestAnimationFrame(() => {
      el.scrollTop = saved;
    });
    return () => cancelAnimationFrame(id);
  }, [page, lang, mode]);

  const saveScroll = useCallback(() => {
    const el = scrollRef.current;
    if (el) localStorage.setItem(SCROLL_KEY(page), String(el.scrollTop));
  }, [page]);

  const jump = useCallback(
    (p: number, restoreScroll = false) => {
      saveScroll();
      const clamped = Math.min(TOTAL_PAGES, Math.max(1, p));
      setPage(clamped);
      setSidebarOpen(false);
      if (!restoreScroll) {
        const id = requestAnimationFrame(() => {
          if (scrollRef.current) scrollRef.current.scrollTop = 0;
        });
        void id;
      }
    },
    [saveScroll]
  );

  const onLang = (l: Lang) => setLang(l);
  const onMode = (m: ViewMode) => {
    saveScroll();
    setMode(m);
  };

  const resume = () => {
    if (store.lastRead) {
      setLang(store.lastRead.lang);
      setMode(store.lastRead.mode);
      jump(store.lastRead.page);
    }
  };

  const cycleTheme = useCallback(() => {
    const order: ThemeName[] = ["night", "sepia", "paper"];
    const cur = order.indexOf(store.theme);
    store.setTheme(order[(cur + 1) % order.length]);
  }, [store]);

  const themeLabel = THEMES.find((t) => t.id === store.theme)?.label ?? "Night";

  // ---- keyboard nav (T1c) ----
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      const typing =
        tag === "INPUT" || tag === "TEXTAREA" || (e.target as HTMLElement)?.isContentEditable;
      if (typing) return;

      if (e.key === "/" && !searchOpen) {
        e.preventDefault();
        setSearchOpen(true);
        return;
      }
      if (e.key === "g" && !searchOpen) {
        setGridOpen(true);
        return;
      }
      if (e.key === "ArrowLeft") {
        e.preventDefault();
        jump(page - 1);
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        jump(page + 1);
      } else if (e.key === " " || e.key === "PageDown") {
        const el = scrollRef.current;
        if (el && el.scrollHeight - el.scrollTop - el.clientHeight > 4) {
          e.preventDefault();
          el.scrollBy({ top: el.clientHeight * 0.9, behavior: "smooth" });
        } else {
          e.preventDefault();
          jump(page + 1);
        }
      } else if (e.key === "PageUp") {
        const el = scrollRef.current;
        if (el && el.scrollTop > 4) {
          e.preventDefault();
          el.scrollBy({ top: -el.clientHeight * 0.9, behavior: "smooth" });
        } else {
          e.preventDefault();
          jump(page - 1);
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [page, jump, searchOpen]);

  // edge-tap flip zones (T1c)
  const onEdgeTap = (side: "left" | "right") => {
    const isRtl = dir === "rtl";
    if (side === "right") jump(isRtl ? page - 1 : page + 1);
    else jump(isRtl ? page + 1 : page - 1);
  };

  return (
    <div dir={dir} className="flex h-screen flex-col overflow-hidden">
      <TopBar
        lang={lang}
        mode={mode}
        onLang={onLang}
        onMode={onMode}
        onToggleSidebar={() => setSidebarOpen((v) => !v)}
        onOpenGrid={() => setGridOpen(true)}
        onOpenSearch={() => setSearchOpen(true)}
        onOpenImport={() => setImportOpen(true)}
        onCycleTheme={cycleTheme}
        themeLabel={themeLabel}
        fontSize={store.fontSize}
        onFont={(d) =>
          store.setFontSize(Math.min(72, Math.max(4, store.fontSize + d * 2)))
        }
        page={page}
        total={TOTAL_PAGES}
        sectionTitle={sectionTitle}
      />

      <div className="flex min-h-0 flex-1">
        <Sidebar
          open={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          lang={lang}
          page={page}
          lastRead={store.lastRead}
          bookmarks={store.bookmarks}
          onJump={jump}
          onResume={resume}
        />

        <main className="relative flex min-h-0 flex-1 flex-col">
          {/* edge-tap flip zones */}
          <button
            aria-label="Previous page"
            onClick={() => onEdgeTap("left")}
            className="absolute left-0 top-0 z-20 hidden h-full w-12 cursor-w-resize bg-gradient-to-r from-black/20 to-transparent md:block"
          />
          <button
            aria-label="Next page"
            onClick={() => onEdgeTap("right")}
            className="absolute right-0 top-0 z-20 hidden h-full w-12 cursor-e-resize bg-gradient-to-l from-black/20 to-transparent md:block"
          />

          <div
            ref={scrollRef}
            onScroll={saveScroll}
            className="min-h-0 flex-1 overflow-y-auto px-4 py-8 sm:px-8"
          >
            {mode === "text" ? (
              <Reader
                page={page}
                lang={lang}
                data={data}
                fontSize={store.fontSize}
                onBookmark={() => store.toggleBookmark(page)}
                bookmarked={store.isBookmarked(page)}
              />
            ) : (
              <PageViewer
                page={page}
                lang={lang}
                sectionTitle={sectionTitle}
                scanSrc={data.scanSrc}
                fallbackText={data.text[lang]}
                onBookmark={() => store.toggleBookmark(page)}
                bookmarked={store.isBookmarked(page)}
              />
            )}
          </div>

          <ProgressDock
            page={page}
            total={TOTAL_PAGES}
            progress={progress}
            onPrev={() => jump(page - 1)}
            onNext={() => jump(page + 1)}
            onJump={jump}
          />
        </main>
      </div>

      <GridModal
        open={gridOpen}
        onClose={() => setGridOpen(false)}
        lang={lang}
        page={page}
        bookmarks={store.bookmarks}
        onJump={jump}
      />
      <SearchModal
        open={searchOpen}
        onClose={() => setSearchOpen(false)}
        lang={lang}
        onJump={jump}
      />
      <ImportPanel
        open={importOpen}
        onClose={() => setImportOpen(false)}
        onReload={() => {
          /* data is seeded at SSR; import reload is a no-op refresh */
        }}
      />
    </div>
  );
}
