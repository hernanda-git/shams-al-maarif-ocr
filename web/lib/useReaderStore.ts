"use client";

import { useCallback, useEffect, useState } from "react";
import { Lang, ViewMode, LastRead } from "./types";

export type ThemeName = "night" | "sepia" | "paper";
export const THEMES: { id: ThemeName; label: string }[] = [
  { id: "night", label: "Night" },
  { id: "sepia", label: "Sepia" },
  { id: "paper", label: "Paper" },
];

export type LineHeight = "cozy" | "normal" | "airy";
export const LINE_HEIGHTS: { id: LineHeight; label: string; value: number }[] = [
  { id: "cozy", label: "Cozy", value: 1.7 },
  { id: "normal", label: "Normal", value: 2.0 },
  { id: "airy", label: "Airy", value: 2.4 },
];

const KEY = "shams-reader-state-v1";

interface PersistShape {
  lastRead: LastRead | null;
  bookmarks: number[];
  fontSize: number;
  theme: ThemeName;
  lineHeight: LineHeight;
}

function load(): PersistShape {
  if (typeof window === "undefined") {
    return {
      lastRead: null,
      bookmarks: [],
      fontSize: 20,
      theme: "night",
      lineHeight: "normal",
    };
  }
  try {
    const raw = window.localStorage.getItem(KEY);
    if (raw) {
      const p = JSON.parse(raw) as PersistShape;
      return {
        lastRead: p.lastRead ?? null,
        bookmarks: Array.isArray(p.bookmarks) ? p.bookmarks : [],
        fontSize: p.fontSize ?? 20,
        theme: p.theme ?? "night",
        lineHeight: p.lineHeight ?? "normal",
      };
    }
  } catch {
    /* ignore */
  }
  return {
    lastRead: null,
    bookmarks: [],
    fontSize: 20,
    theme: "night",
    lineHeight: "normal",
  };
}

export function useReaderStore() {
  const [lastRead, setLastReadState] = useState<LastRead | null>(null);
  const [bookmarks, setBookmarks] = useState<number[]>([]);
  const [fontSize, setFontSizeState] = useState<number>(20);
  const [theme, setThemeState] = useState<ThemeName>("night");
  const [lineHeight, setLineHeightState] = useState<LineHeight>("normal");

  // hydrate after mount (avoids SSR/hydration mismatch)
  useEffect(() => {
    const p = load();
    setLastReadState(p.lastRead);
    setBookmarks(p.bookmarks);
    setFontSizeState(p.fontSize);
    setThemeState(p.theme);
    setLineHeightState(p.lineHeight);
  }, []);

  // apply theme + line-height to <html>
  useEffect(() => {
    if (typeof document !== "undefined") {
      document.documentElement.dataset.theme = theme;
      document.documentElement.dataset.line = lineHeight;
    }
  }, [theme, lineHeight]);

  const persist = useCallback(
    (next: Partial<PersistShape>) => {
      if (typeof window === "undefined") return;
      const cur = load();
      const merged: PersistShape = { ...cur, ...next };
      try {
        window.localStorage.setItem(KEY, JSON.stringify(merged));
      } catch {
        /* ignore quota */
      }
    },
    []
  );

  const markRead = useCallback(
    (page: number, lang: Lang, mode: ViewMode) => {
      const lr: LastRead = { page, at: Date.now(), lang, mode };
      setLastReadState(lr);
      persist({ lastRead: lr });
    },
    [persist]
  );

  const toggleBookmark = useCallback(
    (page: number) => {
      setBookmarks((prev) => {
        const has = prev.includes(page);
        const next = has ? prev.filter((p) => p !== page) : [...prev, page].sort((a, b) => a - b);
        persist({ bookmarks: next });
        return next;
      });
    },
    [persist]
  );

  const isBookmarked = useCallback(
    (page: number) => bookmarks.includes(page),
    [bookmarks]
  );

  const setFontSize = useCallback(
    (size: number) => {
      setFontSizeState(size);
      persist({ fontSize: size });
    },
    [persist]
  );

  const setTheme = useCallback(
    (t: ThemeName) => {
      setThemeState(t);
      persist({ theme: t });
    },
    [persist]
  );

  const setLineHeight = useCallback(
    (l: LineHeight) => {
      setLineHeightState(l);
      persist({ lineHeight: l });
    },
    [persist]
  );

  return {
    lastRead,
    bookmarks,
    fontSize,
    theme,
    lineHeight,
    markRead,
    toggleBookmark,
    isBookmarked,
    setFontSize,
    setTheme,
    setLineHeight,
  };
}
