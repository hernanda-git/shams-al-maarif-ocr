import { seedManuscriptFromDisk } from "@/lib/manuscript";
import ReaderApp from "@/components/ReaderApp";
import path from "path";
import { readFileSync } from "fs";

export const dynamic = "force-dynamic";
export const revalidate = 0;

const JSON_PATH = path.join(process.cwd(), "public", "manuscript.json");
seedManuscriptFromDisk(JSON_PATH);

function readSinglePage(n: number): unknown | null {
  try {
    if (!require("fs").existsSync(JSON_PATH)) return null;
    const all = JSON.parse(readFileSync(JSON_PATH, "utf8"));
    if (!Array.isArray(all)) return null;
    return all.find((p: Record<string, unknown>) => p.page === n) ?? null;
  } catch {
    return null;
  }
}

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;

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

  // Only embed the single page the user opens (~15KB) instead of all 600 (~8MB).
  const serverPage = readSinglePage(initialPage);

  return (
    <ReaderApp
      serverPage={serverPage}
      initialPage={initialPage}
      initialLang={initialLang}
      initialMode={initialMode}
    />
  );
}
