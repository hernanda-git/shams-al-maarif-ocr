"use client";

import { useEffect, useRef, useState } from "react";
import { Lang, ViewMode } from "@/lib/types";
import { LanguageSwitcher } from "./LanguageSwitcher";
import {
  Menu,
  TextMode,
  PageMode,
  Sun,
  Grid,
  Search,
  Upload,
  MoreVertical,
  AutoScroll,
} from "./icons";
import clsx from "clsx";

export function TopBar({
  lang,
  mode,
  onLang,
  onMode,
  onToggleSidebar,
  onOpenGrid,
  onOpenSearch,
  onOpenImport,
  onCycleTheme,
  themeLabel,
  fontSize,
  onFont,
  autoSpeed,
  onCycleAuto,
  bottomCountdown,
  page,
  total,
  sectionTitle,
}: {
  lang: Lang;
  mode: ViewMode;
  onLang: (l: Lang) => void;
  onMode: (m: ViewMode) => void;
  onToggleSidebar: () => void;
  onOpenGrid: () => void;
  onOpenSearch: () => void;
  onOpenImport: () => void;
  onCycleTheme: () => void;
  themeLabel: string;
  fontSize: number;
  onFont: (delta: number) => void;
  autoSpeed: number;
  onCycleAuto: () => void;
  bottomCountdown: number | null;
  page: number;
  total: number;
  sectionTitle: string;
}) {
  const [moreOpen, setMoreOpen] = useState(false);
  const moreRef = useRef<HTMLDivElement>(null);

  // Close the mobile "More" menu on outside click / Escape.
  useEffect(() => {
    if (!moreOpen) return;
    const onDown = (e: MouseEvent) => {
      if (moreRef.current && !moreRef.current.contains(e.target as Node)) {
        setMoreOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMoreOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [moreOpen]);

  // Shared action: run it then close the menu (mobile only).
  const run = (fn: () => void) => () => {
    fn();
    setMoreOpen(false);
  };

  return (
    <header className="sticky top-0 z-30 flex flex-wrap items-center gap-2 border-b border-[var(--color-border)] bg-[var(--color-bg-2)]/85 px-3 py-2 backdrop-blur-md">
      <button
        onClick={onToggleSidebar}
        className="grid h-9 w-9 shrink-0 place-items-center rounded-lg text-[var(--color-muted)] hover:bg-[var(--color-panel)] hover:text-[var(--color-fg)] lg:hidden"
        aria-label="Toggle navigation"
      >
        <Menu />
      </button>

      {/* Brand */}
      <div className="flex min-w-0 items-center gap-2.5">
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-[var(--color-accent-dim)] text-[var(--color-gold-soft)]">
          <Sun width={20} height={20} />
        </span>
        <div className="min-w-0 leading-tight">
          <div className="truncate font-[var(--font-amiri)] text-lg text-[var(--color-gold-soft)]">
            شمس المعارف
          </div>
          <div className="truncate text-[11px] uppercase tracking-widest text-[var(--color-muted)]">
            Shams al-Ma&apos;arif · Reader
          </div>
        </div>
      </div>

      {/* Section context (desktop) */}
      <div className="hidden md:flex min-w-0 flex-1 items-center gap-2 px-2">
        <span className="truncate text-sm text-[var(--color-fg-soft)]">
          {sectionTitle}
        </span>
        <span className="shrink-0 rounded-full border border-[var(--color-border)] px-2 py-0.5 text-xs text-[var(--color-muted)]">
          {page} / {total}
        </span>
      </div>

      {/* Controls */}
      <div className="ml-auto flex flex-wrap items-center gap-1.5 sm:gap-2 max-[460px]:ml-0 max-[460px]:mt-1 max-[460px]:w-full max-[460px]:justify-between">
        <button
          onClick={onOpenImport}
          className="hidden sm:grid h-9 w-9 place-items-center rounded-lg text-[var(--color-muted)] hover:bg-[var(--color-panel)] hover:text-[var(--color-fg)]"
          aria-label="Import manuscript data"
          title="Import data"
        >
          <Upload />
        </button>

        <button
          onClick={onOpenSearch}
          className="grid h-9 w-9 place-items-center rounded-lg text-[var(--color-muted)] hover:bg-[var(--color-panel)] hover:text-[var(--color-fg)]"
          aria-label="Search"
          title="Search ( / )"
        >
          <Search />
        </button>

        <button
          onClick={onCycleTheme}
          className="hidden sm:grid h-9 w-9 place-items-center rounded-lg text-[var(--color-muted)] hover:bg-[var(--color-panel)] hover:text-[var(--color-fg)]"
          aria-label="Cycle reading theme"
          title={`Theme: ${themeLabel}`}
        >
          <Sun />
        </button>

        <button
          onClick={onOpenGrid}
          className="hidden sm:grid h-9 w-9 place-items-center rounded-lg text-[var(--color-muted)] hover:bg-[var(--color-panel)] hover:text-[var(--color-fg)]"
          aria-label="Page grid"
          title="Page grid"
        >
          <Grid />
        </button>

        {/* Auto-scroll: cycle off -> 1 -> 2 -> 3 -> 4 -> off */}
        <button
          onClick={onCycleAuto}
          className={clsx(
            "hidden sm:inline-flex h-9 items-center gap-1.5 rounded-full border px-2.5 text-sm transition-colors",
            autoSpeed > 0
              ? "border-[var(--color-accent)] bg-[var(--color-accent)] text-[var(--color-gold-soft)]"
              : "border-[var(--color-border)] bg-[var(--color-bg-2)] text-[var(--color-muted)] hover:text-[var(--color-fg)]"
          )}
          aria-label="Auto-scroll speed"
          title={
            autoSpeed === 0
              ? "Auto-scroll: off"
              : `Auto-scroll: ${autoSpeed} (click to ${autoSpeed >= 4 ? "turn off" : "speed up"})`
          }
        >
          <AutoScroll width={16} height={16} />
          <span className="tabular-nums">{autoSpeed === 0 ? "Off" : autoSpeed}</span>
        </button>

        {/* Font size */}
        <div className="hidden sm:flex items-center gap-1 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-2)] px-1.5 py-0.5">
          <button
            onClick={() => onFont(-1)}
            className="grid h-7 w-7 place-items-center rounded-full text-[var(--color-muted)] hover:text-[var(--color-fg)]"
            aria-label="Decrease font"
          >
            A-
          </button>
          <span className="w-7 text-center text-xs text-[var(--color-muted)]">
            {fontSize}
          </span>
          <button
            onClick={() => onFont(1)}
            className="grid h-7 w-7 place-items-center rounded-full text-[var(--color-fg)] hover:text-[var(--color-gold-soft)]"
            aria-label="Increase font"
          >
            A+
          </button>
        </div>

        {/* View toggle */}
        <div className="inline-flex items-center rounded-full border border-[var(--color-border)] bg-[var(--color-bg-2)] p-0.5">
          <button
            onClick={() => onMode("text")}
            className={clsx(
              "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-sm transition-colors",
              mode === "text"
                ? "bg-[var(--color-accent)] text-[var(--color-gold-soft)]"
                : "text-[var(--color-muted)] hover:text-[var(--color-fg)]"
            )}
            title="OCR text view"
          >
            <TextMode width={16} height={16} /> <span className="hidden md:inline">Text</span>
          </button>
          <button
            onClick={() => onMode("page")}
            className={clsx(
              "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-sm transition-colors",
              mode === "page"
                ? "bg-[var(--color-accent)] text-[var(--color-gold-soft)]"
                : "text-[var(--color-muted)] hover:text-[var(--color-fg)]"
            )}
            title="Scanned page (PDF) view"
          >
            <PageMode width={16} height={16} /> <span className="hidden md:inline">Page</span>
          </button>
        </div>

        <LanguageSwitcher lang={lang} onChange={onLang} />

        {/* Mobile "More" overflow: exposes the desktop-only controls on < sm */}
        <div ref={moreRef} className="relative sm:hidden">
          <button
            onClick={() => setMoreOpen((v) => !v)}
            className={clsx(
              "grid h-9 w-9 place-items-center rounded-lg text-[var(--color-muted)] hover:bg-[var(--color-panel)] hover:text-[var(--color-fg)] sm:hidden",
              moreOpen && "bg-[var(--color-panel)] text-[var(--color-fg)]"
            )}
            aria-label="More controls"
            aria-expanded={moreOpen}
          >
            <MoreVertical />
          </button>

          {moreOpen && (
            <div className="absolute right-0 top-11 z-50 w-56 rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg-2)] p-2 shadow-2xl shadow-black/50">
              <button
                onClick={run(onOpenImport)}
                className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm text-[var(--color-fg-soft)] hover:bg-[var(--color-panel)]"
              >
                <Upload width={18} height={18} className="text-[var(--color-muted)]" />
                Import manuscript
              </button>

              <button
                onClick={run(onCycleTheme)}
                className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm text-[var(--color-fg-soft)] hover:bg-[var(--color-panel)]"
              >
                <Sun width={18} height={18} className="text-[var(--color-muted)]" />
                Theme: {themeLabel}
              </button>

              <button
                onClick={run(onOpenGrid)}
                className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm text-[var(--color-fg-soft)] hover:bg-[var(--color-panel)]"
              >
                <Grid width={18} height={18} className="text-[var(--color-muted)]" />
                Page grid
              </button>

              {/* Auto-scroll (mobile) */}
              <button
                onClick={run(onCycleAuto)}
                className="flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2.5 text-left text-sm text-[var(--color-fg-soft)] hover:bg-[var(--color-panel)]"
              >
                <span className="flex items-center gap-3">
                  <AutoScroll width={18} height={18} className="text-[var(--color-muted)]" />
                  Auto-scroll
                </span>
                <span
                  className={clsx(
                    "rounded-full px-2 py-0.5 text-xs",
                    autoSpeed > 0
                      ? "bg-[var(--color-accent)] text-[var(--color-gold-soft)]"
                      : "border border-[var(--color-border)] text-[var(--color-muted)]"
                  )}
                >
                  {autoSpeed === 0 ? "Off" : `Speed ${autoSpeed}`}
                </span>
              </button>

              {/* Font size slider */}
              <div className="flex items-center justify-between gap-3 rounded-xl px-3 py-2.5">
                <span className="text-sm text-[var(--color-fg-soft)]">Font size</span>
                <div className="flex items-center gap-1 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-2)] px-1.5 py-0.5">
                  <button
                    onClick={() => onFont(-1)}
                    className="grid h-7 w-7 place-items-center rounded-full text-[var(--color-muted)] hover:text-[var(--color-fg)]"
                    aria-label="Decrease font"
                  >
                    A-
                  </button>
                  <span className="w-7 text-center text-xs text-[var(--color-muted)]">
                    {fontSize}
                  </span>
                  <button
                    onClick={() => onFont(1)}
                    className="grid h-7 w-7 place-items-center rounded-full text-[var(--color-fg)] hover:text-[var(--color-gold-soft)]"
                    aria-label="Increase font"
                  >
                    A+
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
