"use client";

import { ManuscriptPage, Lang } from "@/lib/types";

export function Reader({
  page,
  lang,
  data,
  fontSize,
  onBookmark,
  bookmarked,
}: {
  page: number;
  lang: Lang;
  data: ManuscriptPage;
  fontSize: number;
  onBookmark: () => void;
  bookmarked: boolean;
}) {
  const isAr = lang === "ar";

  return (
    <article className="mx-auto max-w-3xl">
      {/* page header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <div className="text-[11px] uppercase tracking-widest text-[var(--color-gold)]">
            {data.sectionId.replace("s", "Section ")}
          </div>
          <h1
            className={
              "mt-1 font-[var(--font-serif)] text-2xl text-[var(--color-fg)] " +
              (isAr ? "font-[var(--font-amiri)] text-right" : "")
            }
          >
            {data.text[lang].slice(0, 0) /* title rendered by parent */}
          </h1>
        </div>
        <button
          onClick={onBookmark}
          className={
            "shrink-0 rounded-full border px-3 py-1.5 text-xs transition-colors " +
            (bookmarked
              ? "border-[var(--color-gold)] text-[var(--color-gold)]"
              : "border-[var(--color-border)] text-[var(--color-muted)] hover:text-[var(--color-fg)]")
          }
          title="Toggle bookmark"
        >
          {bookmarked ? "★ Bookmarked" : "☆ Bookmark"}
        </button>
      </div>

      <div className="ornament mb-6" />

      {/* OCR text */}
      <div
        className={"reading-column " + (isAr ? "arabic" : "")}
        style={{ fontSize: `${fontSize}px` }}
      >
        {data.text[lang].split("\n\n").map((para, i) => (
          <p key={i}>{para}</p>
        ))}
      </div>

      <div className="ornament my-8" />
      <p className="text-center text-xs text-[var(--color-muted)]">
        OCR transcription · page {page} · machine-readable text
      </p>
    </article>
  );
}
