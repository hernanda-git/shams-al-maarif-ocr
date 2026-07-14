"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { searchAll } from "@/lib/search";
import { Lang } from "@/lib/types";
import { X } from "./icons";

export function SearchModal({
  open,
  onClose,
  lang,
  onJump,
}: {
  open: boolean;
  onClose: () => void;
  lang: Lang;
  onJump: (p: number) => void;
}) {
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setQ("");
      setActive(0);
      setTimeout(() => inputRef.current?.focus(), 30);
    }
  }, [open]);

  const hits = useMemo(() => searchAll(q, lang), [q, lang]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!open) return;
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActive((a) => Math.min(hits.length - 1, a + 1));
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setActive((a) => Math.max(0, a - 1));
      }
      if (e.key === "Enter" && hits[active]) {
        onJump(hits[active].page);
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, hits, active, onClose, onJump]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center bg-black/70 p-4 pt-[8vh]">
      <div className="flex max-h-[80vh] w-full max-w-2xl flex-col overflow-hidden rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-bg-2)] shadow-2xl">
        <div className="flex items-center gap-3 border-b border-[var(--color-border)] px-4 py-3">
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setActive(0);
            }}
            placeholder="Search the manuscript…"
            className="flex-1 bg-transparent text-base text-[var(--color-fg)] placeholder:text-[var(--color-muted)] focus:outline-none"
          />
          <span className="text-xs text-[var(--color-muted)]">
            {hits.length} hits
          </span>
          <button
            onClick={onClose}
            className="grid h-8 w-8 place-items-center rounded-lg text-[var(--color-muted)] hover:text-[var(--color-fg)]"
            aria-label="Close"
          >
            <X />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-2">
          {q.trim().length < 2 && (
            <p className="px-3 py-8 text-center text-sm text-[var(--color-muted)]">
              Type at least 2 characters to search all 600 pages.
            </p>
          )}
          {q.trim().length >= 2 && hits.length === 0 && (
            <p className="px-3 py-8 text-center text-sm text-[var(--color-muted)]">
              No matches for “{q}”.
            </p>
          )}
          {hits.map((h, i) => {
            const before = h.snippet.slice(0, h.at);
            const match = h.snippet.slice(h.at, h.at + q.length);
            const after = h.snippet.slice(h.at + q.length);
            return (
              <button
                key={h.page + "-" + i}
                onMouseEnter={() => setActive(i)}
                onClick={() => {
                  onJump(h.page);
                  onClose();
                }}
                className={
                  "mb-1 flex w-full gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition-colors " +
                  (i === active
                    ? "bg-[var(--color-panel-2)]"
                    : "hover:bg-[var(--color-panel)]")
                }
              >
                <span className="shrink-0 text-xs tabular-nums text-[var(--color-gold)]">
                  {String(h.page).padStart(3, "0")}
                </span>
                <span className="min-w-0">
                  <span className="block truncate text-xs text-[var(--color-muted)]">
                    {h.section}
                  </span>
                  <span className="block text-[var(--color-fg-soft)]">
                    {before}
                    <mark className="rounded bg-[var(--color-accent)]/70 px-0.5 text-[var(--color-gold-soft)]">
                      {match}
                    </mark>
                    {after}
                  </span>
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
