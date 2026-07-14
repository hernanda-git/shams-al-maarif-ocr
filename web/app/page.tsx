import { seedManuscriptFromDisk } from "@/lib/manuscript";
import ReaderApp from "@/components/ReaderApp";
import path from "path";

// Resolve the bundled manuscript JSON at build/SSR time so the first paint
// already contains real text (no client fetch -> no content flash).
const JSON_PATH = path.join(process.cwd(), "public", "manuscript.json");
seedManuscriptFromDisk(JSON_PATH);

export default function Page() {
  return <ReaderApp />;
}
