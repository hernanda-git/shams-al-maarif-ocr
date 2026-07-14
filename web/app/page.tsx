import { seedManuscriptFromDisk } from "@/lib/manuscript";
import ReaderApp from "@/components/ReaderApp";
import path from "path";
import { readFileSync } from "fs";

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

export default function Page() {
  const pages = readManuscriptArray();
  return <ReaderApp serverPages={pages} />;
}
