"use client";

import { useState } from "react";
import { ChevronLeft, ChevronRight } from "./icons";

export function ProgressDock({
  page,
  total,
  progress,
  onPrev,
  onNext,
  onJump,
}: {
  page: number;
  total: number;
  progress: number; // 0..1
  onPrev: () => void;
  onNext: () => void;
  onJump: (p: number) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState(String(page));

  const commit = () => {
    const n = parseInt(val, 10);
    if (!isNaN(n)) onJump(Math.min(total, Math.max(1, n)));
    setEditing(false);
  };

  return (
    <div className="sticky bottom-0 z-30 border-t border-[var(--color-border)] bg-[var(--color-bg-2)]/90 px-3 py-2.5 backdrop-blur-md">
      {/* progress bar */}
      <div className="mb-2 h-1 w-full overflow-hidden rounded-full bg-[var(--color-panel)]">
        <div
          className="h-full rounded-full bg-gradient-to-r from-[var(--color-accent)] to-[var(--color-gold)] transition-[width] duration-300"
          style={{ width: `${Math.round(progress * 100)}%` }}
        />
      </div>

      <div className="flex items-center justify-between gap-3">
        <button
          onClick={onPrev}
          disabled={page <= 1}
          className="grid h-9 w-9 place-items-center rounded-lg border border-[var(--color-border)] text-[var(--color-fg-soft)] transition-colors hover:bg-[var(--color-panel)] disabled:opacity-30"
          aria-label="Previous page"
        >
          <ChevronLeft />
        </button>

        <div className="flex flex-1 items-center justify-center gap-2 text-sm">
          {editing ? (
            <input
              autoFocus
              value={val}
              onChange={(e) => setVal(e.target.value.replace(/[^0-9]/g, ""))}
              onBlur={commit}
              onKeyDown={(e) => e.key === "Enter" && commit()}
              className="w-16 rounded-md border border-[var(--color-accent)] bg-[var(--color-bg)] px-2 py-1 text-center text-[var(--color-fg)] focus:outline-none"
            />
          ) : (
            <button
              onClick={() => {
                setVal(String(page));
                setEditing(true);
              }}
              className="tabular-nums text-[var(--color-fg)] hover:text-[var(--color-gold-soft)]"
            >
              <span className="text-[var(--color-gold-soft)] font-semibold">
                {page}
              </span>{" "}
              / {total}
            </button>
          )}
          <span className="hidden sm:inline text-xs text-[var(--color-muted)]">
            · {Math.round(progress * 100)}% read
          </span>
        </div>

        <button
          onClick={onNext}
          disabled={page >= total}
          className="grid h-9 w-9 place-items-center rounded-lg border border-[var(--color-border)] text-[var(--color-fg-soft)] transition-colors hover:bg-[var(--color-panel)] disabled:opacity-30"
          aria-label="Next page"
        >
          <ChevronRight />
        </button>
      </div>
    </div>
  );
}
