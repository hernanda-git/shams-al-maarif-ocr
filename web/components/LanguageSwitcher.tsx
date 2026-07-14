"use client";

import { LANGS, LANG_ORDER, Lang } from "@/lib/types";
import clsx from "clsx";

export function LanguageSwitcher({
  lang,
  onChange,
}: {
  lang: Lang;
  onChange: (l: Lang) => void;
}) {
  return (
    <div
      role="tablist"
      aria-label="Language"
      className="inline-flex items-center rounded-full border border-[var(--color-border)] bg-[var(--color-bg-2)] p-0.5"
    >
      {LANG_ORDER.map((code) => {
        const m = LANGS[code];
        const active = code === lang;
        return (
          <button
            key={code}
            role="tab"
            aria-selected={active}
            onClick={() => onChange(code)}
            className={clsx(
              "rounded-full px-2.5 py-1 text-sm font-medium transition-colors max-[460px]:px-2 max-[460px]:text-[13px]",
              m.dir === "rtl" ? "font-[var(--font-amiri)] text-base" : "",
              active
                ? "bg-[var(--color-accent)] text-[var(--color-gold-soft)] shadow"
                : "text-[var(--color-muted)] hover:text-[var(--color-fg)]"
            )}
            title={m.english}
          >
            {m.label}
          </button>
        );
      })}
    </div>
  );
}
