"use client";

import { Lang } from "@/lib/types";

/**
 * Renders the "scanned" (non-OCR) page.
 *
 * The real per-page facsimile PDFs live in the Cloudflare R2 bucket
 * `shams-al-maarif` and are served from the public domain
 * https://shamsmaarif.warga-digital.com/page-NNN.pdf (uploaded by
 * scripts/upload_scans_r2.js). We render them with a plain <iframe> so the
 * browser's native PDF viewer handles zoom/pan and no CORS-restricted
 * fetch is needed.
 *
 * FALLBACK: if the scan is missing or the iframe fails, we render the OCR
 * transcription for the active language instead of a blank screen, so the
 * reader always has readable content.
 */
export function PageViewer({
  page,
  lang,
  sectionTitle,
  scanSrc,
  fallbackText,
  onBookmark,
  bookmarked,
}: {
  page: number;
  lang: Lang;
  sectionTitle: string;
  scanSrc?: string;
  /** OCR text shown if the scan is unavailable */
  fallbackText?: string;
  onBookmark: () => void;
  bookmarked: boolean;
}) {
  const src =
    scanSrc || `https://shamsmaarif.warga-digital.com/page-${String(page).padStart(3, "0")}.pdf`;
  const isRtl = lang === "ar";

  // --- Fallback: no scan source -> show OCR transcription ---
  if (!src) {
    return (
      <div className="mx-auto flex max-w-3xl flex-col items-center">
        <div className="mb-3 flex w-full items-center justify-between rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-2)] px-3 py-2 text-xs text-[var(--color-muted)]">
          <span>Scanned facsimile unavailable · showing OCR text</span>
          <button
            onClick={onBookmark}
            className={bookmarked ? "text-[var(--color-gold)]" : "hover:text-[var(--color-fg)]"}
            title="Toggle bookmark"
          >
            {bookmarked ? "★ Bookmarked" : "☆ Bookmark"}
          </button>
        </div>
        <div className="w-full rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-bg-2)] p-6 shadow-2xl">
          <div className="ornament mb-6" />
          <div className={"reading-column " + (isRtl ? "arabic" : "")} style={{ fontSize: "20px" }}>
            {(fallbackText || "(no text for this page)").split("\n\n").map((para, i) => (
              <p key={i}>{para}</p>
            ))}
          </div>
          <div className="ornament my-8" />
          <p className="text-center text-xs text-[var(--color-muted)]">
            Facsimile of page {page} could not be loaded — showing OCR transcription instead.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col items-center">
      {/* viewer chrome */}
      <div className="mb-3 flex w-full items-center justify-between rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-2)] px-3 py-2 text-xs text-[var(--color-muted)]">
        <span>Scanned facsimile · non-OCR</span>
        <div className="flex items-center gap-2">
          <a
            href={src}
            target="_blank"
            rel="noreferrer"
            className="rounded px-2 py-0.5 hover:bg-[var(--color-bg)]"
            title="Open in new tab"
          >
            ↗ Open
          </a>
          <button
            onClick={onBookmark}
            className={bookmarked ? "text-[var(--color-gold)]" : "hover:text-[var(--color-fg)]"}
            title="Toggle bookmark"
          >
            {bookmarked ? "★ Bookmarked" : "☆ Bookmark"}
          </button>
        </div>
      </div>

      <div className="w-full overflow-hidden rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-bg)] shadow-2xl">
        <iframe
          src={src}
          title={`Facsimile of page ${page}`}
          className="h-[80vh] w-full"
        />
      </div>

      <p className="mt-3 text-center text-xs text-[var(--color-muted)]">
        Facsimile of page {page}
        {isRtl && sectionTitle ? ` · ${sectionTitle}` : ""} — authentic scan,
        served from R2.{fallbackText ? " Switch to Text mode for the OCR transcription." : ""}
      </p>
    </div>
  );
}
