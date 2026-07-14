"use client";

import { useCallback, useRef, useState } from "react";
import {
  loadManuscript,
  clearImportedData,
  getImportStats,
  isUsingImportedData,
} from "@/lib/manuscript";
import { X, Upload } from "./icons";

const IMPORT_KEY = "shams-imported-manuscript-v1";

function persistImport(json: string) {
  try {
    localStorage.setItem(IMPORT_KEY, json);
  } catch {
    /* ignore quota */
  }
}

function restoreImport() {
  try {
    const raw = localStorage.getItem(IMPORT_KEY);
    if (raw) {
      loadManuscript(raw);
      return;
    }
  } catch {
    /* ignore */
  }
}

export function ImportPanel({
  open,
  onClose,
  onReload,
}: {
  open: boolean;
  onClose: () => void;
  onReload: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [drag, setDrag] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleJson = useCallback(
    (text: string) => {
      setError(null);
      setMsg(null);
      try {
        const parsed = JSON.parse(text);
        const stats = loadManuscript(parsed);
        persistImport(text);
        setMsg(
          `Imported ${stats.pages} pages across ${stats.sections} section(s). Reload to view.`
        );
        onReload();
      } catch (e) {
        setError(
          e instanceof Error
            ? e.message
            : "Could not parse file. Expected JSON: [{page, ar, en, id}] or {pages:[...]}."
        );
      }
    },
    [onReload]
  );

  const onFile = (file: File) => {
    const reader = new FileReader();
    reader.onload = () => handleJson(String(reader.result));
    reader.readAsText(file);
  };

  if (!open) return null;

  const stats = getImportStats();
  const imported = isUsingImportedData();

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 p-4">
      <div className="w-full max-w-lg overflow-hidden rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-bg-2)] shadow-2xl">
        <div className="flex items-center justify-between border-b border-[var(--color-border)] px-4 py-3">
          <h2 className="text-sm font-semibold text-[var(--color-gold-soft)]">
            Import Manuscript Data
          </h2>
          <button
            onClick={onClose}
            className="grid h-8 w-8 place-items-center rounded-lg text-[var(--color-muted)] hover:text-[var(--color-fg)]"
            aria-label="Close"
          >
            <X />
          </button>
        </div>

        <div className="space-y-4 p-4">
          <p className="text-sm text-[var(--color-fg-soft)]">
            Drop a JSON file with your OCR manuscript. Accepted shapes:
          </p>
          <pre className="overflow-x-auto rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-3 text-xs text-[var(--color-muted)]">
{`[ { "page": 1, "ar": "...", "en": "...", "id": "..." },
  { "page": 2, "text": { "ar": "...", "en": "...", "id": "..." } } ]
// or: { "pages": [...], "toc": [{ "id", "title", "start", "end" }] }`}
          </pre>

          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDrag(true);
            }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDrag(false);
              const f = e.dataTransfer.files?.[0];
              if (f) onFile(f);
            }}
            onClick={() => fileRef.current?.click()}
            className={
              "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-[var(--radius-card)] border-2 border-dashed py-8 text-center transition-colors " +
              (drag
                ? "border-[var(--color-accent)] bg-[var(--color-accent-dim)]/30"
                : "border-[var(--color-border)] hover:border-[var(--color-gold)]")
            }
          >
            <Upload className="text-[var(--color-gold)]" />
            <span className="text-sm text-[var(--color-fg-soft)]">
              Drop JSON here or click to browse
            </span>
            <input
              ref={fileRef}
              type="file"
              accept="application/json,.json"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) onFile(f);
              }}
            />
          </div>

          {error && (
            <p className="rounded-lg border border-[var(--color-accent-dim)] bg-[var(--color-accent-dim)]/30 p-2 text-xs text-[var(--color-gold-soft)]">
              {error}
            </p>
          )}
          {msg && (
            <p className="rounded-lg border border-[var(--color-gold)]/40 bg-[var(--color-gold)]/10 p-2 text-xs text-[var(--color-gold-soft)]">
              {msg}
            </p>
          )}

          <div className="flex items-center justify-between border-t border-[var(--color-border)] pt-3 text-xs text-[var(--color-muted)]">
            <span>
              Source: {imported ? "imported" : "generator"} · {stats.pages} pages
              loaded
            </span>
            <button
              onClick={() => {
                clearImportedData();
                localStorage.removeItem(IMPORT_KEY);
                setMsg("Reverted to built-in sample data.");
                onReload();
              }}
              className="rounded-lg border border-[var(--color-border)] px-2.5 py-1 text-[var(--color-fg-soft)] hover:text-[var(--color-fg)]"
            >
              Reset to sample
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export { restoreImport };
