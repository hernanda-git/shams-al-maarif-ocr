"use client";

import { useState } from "react";
import { getToc, TOTAL_PAGES } from "@/lib/manuscript";
import { Lang } from "@/lib/types";
import { X } from "./icons";
import clsx from "clsx";

export function GridModal({
  open,
  onClose,
  lang,
  page,
  bookmarks,
  onJump,
}: {
  open: boolean;
  onClose: () => void;
  lang: Lang;
  page: number;
  bookmarks: number[];
  onJump: (p: number) => void;
}) {
  const [q, setQ] = useState("");
  if (!open) return null;

  const TOC = getToc();
  const bset = new Set(bookmarks);
  const term = q.trim().toLowerCase();

  const cells = Array.from({ length: TOTAL_PAGES }, (_, i) => i + 1);
  // if searching, only show pages in matching sections
  const filtered = term
    ? cells.filter((p) => {
        const sec = TOC.find((s) => p >= s.startPage && p <= s.endPage);
        return sec?.title[lang].toLowerCase().includes(term);
      })
    : cells;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 p-4">
      <div className="flex h-[85vh] w-full max-w-4xl flex-col overflow-hidden rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-bg-2)] shadow-2xl">
        <div className="flex items-center gap-3 border-b border-[var(--color-border)] px-4 py-3">
          <h2 className="text-sm font-semibold text-[var(--color-gold-soft)]">
            Go to page
          </h2>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Filter by section…"
            className="ml-2 flex-1 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-1.5 text-sm text-[var(--color-fg)] placeholder:text-[var(--color-muted)] focus:outline-none"
          />
          <button
            onClick={onClose}
            className="grid h-8 w-8 place-items-center rounded-lg text-[var(--color-muted)] hover:text-[var(--color-fg)]"
            aria-label="Close"
          >
            <X />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          <div className="grid grid-cols-4 gap-2 sm:grid-cols-6 md:grid-cols-8">
            {filtered.map((p) => {
              const active = p === page;
              const book = bset.has(p);
              const sec = TOC.find((s) => p >= s.startPage && p <= s.endPage);
              return (
                <button
                  key={p}
                  onClick={() => {
                    onJump(p);
                    onClose();
                  }}
                  title={`${sec?.title[lang]} — p.${p}`}
                  className={clsx(
                    "relative aspect-[3/4] rounded-md border text-[10px] transition-all",
                    active
                      ? "border-[var(--color-accent)] bg-[var(--color-accent-dim)] text-[var(--color-gold-soft)]"
                      : "border-[var(--color-border)] bg-[var(--color-panel)] text-[var(--color-muted)] hover:border-[var(--color-gold)] hover:text-[var(--color-fg)]"
                  )}
                >
                  <span className="absolute inset-0 grid place-items-center font-semibold tabular-nums">
                    {p}
                  </span>
                  {book && (
                    <span className="absolute right-1 top-1 text-[var(--color-gold)]">
                      ★
                    </span>
                  )}
                </button>
              );
            })}
          </div>
          {filtered.length === 0 && (
            <p className="py-10 text-center text-sm text-[var(--color-muted)]">
              No pages match “{q}”.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
