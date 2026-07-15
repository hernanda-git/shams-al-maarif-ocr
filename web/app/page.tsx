import { seedManuscriptFromDisk } from "@/lib/manuscript";
import ReaderApp from "@/components/ReaderApp";
import path from "path";
import { readFileSync } from "fs";

// Read the manuscript fresh on every request — never statically prerender from a
// build-time snapshot (the JSON is large and updated out-of-band).
export const dynamic = "force-dynamic";
export const revalidate = 0;

// Resolve the bundled manuscript JSON at build/SSR time so the first paint
// already contains real text (no client fetch -> no content flash).
const JSON_PATH = path.join(process.cwd(), "public", "manuscript.json");
seedManuscriptFromDisk(JSON_PATH);

// Read once at module load (server) and pass the real array down to the
// client component so it never falls back to the placeholder generator.
function readManuscriptArray(): unknown[] {
  try {
    if (require("fs").existsSync(JSON_PATH)) {
      return JSON.parse(readFileSync(JSON_PATH, "utf8"));
    }
  } catch {
    /* ignore */
  }
  return [];
}

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const pages = readManuscriptArray();
  const sp = await searchParams;

  // Deep-link support: ?page=N&lang=ar|en|id&mode=text|page
  const q = (k: string): string | undefined => {
    const v = sp[k];
    return Array.isArray(v) ? v[0] : v;
  };
  const p = parseInt(q("page") || "", 10);
  const initialPage = Number.isFinite(p) && p >= 1 && p <= 600 ? p : 1;
  const l = q("lang");
  const initialLang =
    l === "ar" || l === "en" || l === "id" ? (l as "ar" | "en" | "id") : "en";
  const m = q("mode");
  const initialMode = m === "text" || m === "page" ? (m as "text" | "page") : "text";

  return (
    <ReaderApp
      serverPages={pages}
      initialPage={initialPage}
      initialLang={initialLang}
      initialMode={initialMode}
    />
  );
}
