"use client";

import { useMemo, useState, useRef, useCallback, useEffect } from "react";
import { getToc, getPageTitles } from "@/lib/manuscript";
import type { PageTitleEntry } from "@/lib/manuscript";
import { LANGS, Lang, LastRead } from "@/lib/types";
import { X, Search, Clock, Bookmark, BookOpen, FileText, Play, Loader } from "./icons";
import clsx from "clsx";

const PAGE_CHUNK = 100;

function timeAgo(at: number): string {
  const s = Math.floor((Date.now() - at) / 1000);
  if (s < 60) return "just now";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

export function Sidebar({
  open,
  onClose,
  lang,
  page,
  lastRead,
  bookmarks,
  onJump,
  onResume,
}: {
  open: boolean;
  onClose: () => void;
  lang: Lang;
  page: number;
  lastRead: LastRead | null;
  bookmarks: number[];
  onJump: (p: number) => void;
  onResume: () => void;
}) {
  const [tab, setTab] = useState<"toc" | "pages" | "bookmarks">("toc");
  const [q, setQ] = useState("");

  // Lazy loading: render PAGE_CHUNK items at a time
  const [visibleCount, setVisibleCount] = useState(PAGE_CHUNK);
  const sentinelRef = useRef<HTMLDivElement>(null);

  // Reset pagination when tab or query changes
  useEffect(() => { setVisibleCount(PAGE_CHUNK); }, [tab, q]);

  const TOC = getToc();

  // Lightweight: only page + title, no full text
  const pageTitles: PageTitleEntry[] = useMemo(() => {
    if (tab !== "pages") return [];
    return getPageTitles();
  }, [tab]);

  const filteredToc = useMemo(() => {
    const t = q.trim().toLowerCase();
    if (!t) return TOC;
    return TOC.filter((s) => s.title[lang].toLowerCase().includes(t));
  }, [q, lang, TOC]);

  const filteredPages = useMemo(() => {
    const t = q.trim().toLowerCase();
    if (!t) return pageTitles;
    return pageTitles.filter((p) => {
      const title = p.title[lang] ?? "";
      return title.toLowerCase().includes(t);
    });
  }, [q, lang, pageTitles]);

  const visiblePages = useMemo(
    () => filteredPages.slice(0, visibleCount),
    [filteredPages, visibleCount]
  );

  const hasMore = visibleCount < filteredPages.length;

  // IntersectionObserver: auto-load more when sentinel enters viewport
  useEffect(() => {
    const el = sentinelRef.current;
    if (!el || !hasMore) return;
    const io = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setVisibleCount((c) => c + PAGE_CHUNK); },
      { rootMargin: "200px" }
    );
    io.observe(el);
    return () => io.disconnect();
  }, [hasMore]);

  const bookmarkedEntries = useMemo(
    () =>
      bookmarks
        .slice()
        .sort((a, b) => a - b)
        .map((p) => {
          const sec = TOC.find((s) => p >= s.startPage && p <= s.endPage);
          return { page: p, section: sec?.title[lang] ?? "" };
        }),
    [bookmarks, lang]
  );

  // Stable jump callback for Sections (no useCallback needed — trivial)
  const jumpTo = useCallback((p: number) => { onJump(p); }, [onJump]);

  // Loader shown briefly while page data builds on first tab switch
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    if (tab !== "pages") return;
    setLoading(true);
    const id = requestAnimationFrame(() => setLoading(false));
    return () => cancelAnimationFrame(id);
  }, [tab]);

  const placeholder =
    tab === "toc"
      ? "Search sections…"
      : tab === "pages"
        ? "Search pages…"
        : "Search bookmarks…";

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/60 lg:hidden"
          onClick={onClose}
          aria-hidden
        />
      )}

      <aside
        className={clsx(
          "fixed z-50 flex h-full w-[300px] flex-col border-r border-[var(--color-border)] bg-[var(--color-bg-2)] transition-transform duration-300 lg:static lg:z-auto lg:w-[300px] lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--color-border)] px-4 py-3 shrink-0">
          <div className="flex items-center gap-2 text-[var(--color-gold-soft)]">
            <BookOpen width={18} height={18} />
            <span className="text-sm font-semibold tracking-wide">
              Contents
            </span>
          </div>
          <button
            onClick={onClose}
            className="grid h-8 w-8 place-items-center rounded-lg text-[var(--color-muted)] hover:text-[var(--color-fg)] lg:hidden"
            aria-label="Close"
          >
            <X />
          </button>
        </div>

        {/* Last read */}
        {lastRead && (
          <div className="m-3 rounded-[var(--radius-card)] border border-[var(--color-accent-dim)] bg-gradient-to-br from-[var(--color-accent-dim)]/40 to-[var(--color-panel)] p-3 shrink-0">
            <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-widest text-[var(--color-gold)]">
              <Clock width={13} height={13} /> Last Read
            </div>
            <div className="mt-1 flex items-end justify-between">
              <div>
                <div className="font-[var(--font-serif)] text-2xl text-[var(--color-fg)]">
                  Page {lastRead.page}
                </div>
                <div className="text-xs text-[var(--color-muted)]">
                  {LANGS[lastRead.lang].label} · {timeAgo(lastRead.at)}
                </div>
              </div>
              <button
                onClick={onResume}
                className="inline-flex items-center gap-1.5 rounded-full bg-[var(--color-accent)] px-3 py-1.5 text-xs font-medium text-[var(--color-gold-soft)] hover:bg-[var(--color-accent-soft)]"
              >
                <Play width={13} height={13} /> Resume
              </button>
            </div>
          </div>
        )}

        {/* Search */}
        <div className="px-3 pb-2 shrink-0">
          <div className="flex items-center gap-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] px-2.5 py-1.5">
            <Search width={15} height={15} className="text-[var(--color-muted)] shrink-0" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder={placeholder}
              className="w-full bg-transparent text-sm text-[var(--color-fg)] placeholder:text-[var(--color-muted)] focus:outline-none"
            />
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 px-3 pb-2 shrink-0">
          {(["toc", "pages", "bookmarks"] as const).map((t) => (
            <button
              key={t}
              onClick={() => { setTab(t); setQ(""); }}
              className={clsx(
                "inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg py-1.5 text-sm capitalize transition-colors",
                tab === t
                  ? "bg-[var(--color-panel)] text-[var(--color-fg)]"
                  : "text-[var(--color-muted)] hover:text-[var(--color-fg-soft)]"
              )}
            >
              {t === "bookmarks" && <Bookmark width={14} height={14} />}
              {t === "toc" && <BookOpen width={14} height={14} />}
              {t === "pages" && <FileText width={14} height={14} />}
              {t === "toc" ? "Sections" : t === "pages" ? "Pages" : `Saved (${bookmarks.length})`}
            </button>
          ))}
        </div>

        <div className="ornament mx-3 shrink-0" />

        {/* Scrollable list area */}
        <div className="flex-1 overflow-y-auto px-2 py-2 min-h-0">
          {/* SECTIONS TAB */}
          {tab === "toc" &&
            (filteredToc.length === 0 ? (
              <p className="px-3 py-6 text-center text-sm text-[var(--color-muted)]">
                No sections match &ldquo;{q}&rdquo;.
              </p>
            ) : (
              filteredToc.map((s) => {
                const active = page >= s.startPage && page <= s.endPage;
                return (
                  <button
                    key={s.id}
                    onClick={() => jumpTo(s.startPage)}
                    className={clsx(
                      "mb-0.5 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors",
                      active
                        ? "bg-[var(--color-panel-2)] text-[var(--color-gold-soft)]"
                        : "text-[var(--color-fg-soft)] hover:bg-[var(--color-panel)]"
                    )}
                  >
                    <span className="shrink-0 text-xs tabular-nums text-[var(--color-muted)]">
                      {String(s.startPage).padStart(3, "0")}
                    </span>
                    <span
                      className={clsx(
                        "truncate",
                        lang === "ar" && "font-[var(--font-amiri)] text-base"
                      )}
                    >
                      {s.title[lang]}
                    </span>
                  </button>
                );
              })
            ))}

          {/* PAGES TAB */}
          {tab === "pages" && loading && (
            <div className="flex items-center justify-center gap-2 py-10 text-[var(--color-muted)]">
              <Loader width={18} height={18} className="animate-spin" />
              <span className="text-sm">Loading pages…</span>
            </div>
          )}
          {tab === "pages" && !loading && visiblePages.length === 0 && (
            <p className="px-3 py-6 text-center text-sm text-[var(--color-muted)]">
              No pages match &ldquo;{q}&rdquo;.
            </p>
          )}
          {tab === "pages" && !loading && visiblePages.length > 0 && (
            <>
              {visiblePages.map((p) => {
                const active = p.page === page;
                return (
                  <button
                    key={p.page}
                    onClick={() => jumpTo(p.page)}
                    className={clsx(
                      "mb-0.5 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors",
                      active
                        ? "bg-[var(--color-panel-2)] text-[var(--color-gold-soft)]"
                        : "text-[var(--color-fg-soft)] hover:bg-[var(--color-panel)]"
                    )}
                  >
                    <span className="shrink-0 text-xs tabular-nums text-[var(--color-muted)] w-7">
                      {String(p.page).padStart(3, "0")}
                    </span>
                    <span
                      className={clsx(
                        "truncate",
                        lang === "ar" && "font-[var(--font-amiri)] text-base"
                      )}
                    >
                      {p.title[lang]}
                    </span>
                  </button>
                );
              })}
              {/* Sentinel for infinite scroll */}
              {hasMore && (
                <div ref={sentinelRef} className="flex items-center justify-center gap-2 py-4 text-[var(--color-muted)]">
                  <Loader width={14} height={14} className="animate-spin" />
                  <span className="text-xs">Loading more…</span>
                </div>
              )}
              {!hasMore && (
                <p className="py-3 text-center text-xs text-[var(--color-muted)]">
                  All {filteredPages.length} pages loaded
                </p>
              )}
            </>
          )}

          {/* BOOKMARKS TAB */}
          {tab === "bookmarks" &&
            (bookmarkedEntries.length === 0 ? (
              <p className="px-3 py-6 text-center text-sm text-[var(--color-muted)]">
                No bookmarks yet. Tap the ribbon on a page to save it.
              </p>
            ) : (
              bookmarkedEntries.map((b) => (
                <button
                  key={b.page}
                  onClick={() => jumpTo(b.page)}
                  className="mb-0.5 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-[var(--color-fg-soft)] hover:bg-[var(--color-panel)]"
                >
                  <Bookmark
                    width={14}
                    height={14}
                    className="shrink-0 text-[var(--color-gold)]"
                  />
                  <span className="shrink-0 text-xs tabular-nums text-[var(--color-muted)]">
                    {String(b.page).padStart(3, "0")}
                  </span>
                  <span className="truncate">{b.section}</span>
                </button>
              ))
            ))}
        </div>

        <div className="ornament mx-3 shrink-0" />
        <div className="px-4 py-2.5 text-[11px] text-[var(--color-muted)] shrink-0">
          {TOC.length} sections · 600 pages
        </div>
      </aside>
    </>
  );
}
