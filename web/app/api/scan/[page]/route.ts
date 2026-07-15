import { NextRequest } from "next/server";

/**
 * Same-origin PDF proxy for per-page facsimiles.
 *
 * The scans live in Cloudflare R2 and are served from the public domain
 * https://shamsmaarif.warga-digital.com/page-NNN.pdf. Loading that cross-origin
 * inside an <iframe> on the Vercel app is blocked by Cloudflare's browser
 * integrity / hotlink protection in real browsers, even though the object is
 * public (we confirmed a server-side fetch succeeds).
 *
 * This route fetches the PDF *server-side* and streams it back from our own
 * origin, so the <iframe> is same-origin and always renders. No R2 credentials
 * are needed — we just hit the public domain that Cloudflare serves to
 * non-browser clients.
 */
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const PUBLIC_DOMAIN =
  process.env.R2_PUBLIC_DOMAIN || "shamsmaarif.warga-digital.com";

const RE = /^\d{1,3}$/;

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ page: string }> }
) {
  const { page } = await params;
  if (!RE.test(page)) {
    return new Response("Invalid page", { status: 400 });
  }
  const num = parseInt(page, 10);
  if (num < 1 || num > 600) {
    return new Response("Page out of range", { status: 400 });
  }
  const key = `page-${String(num).padStart(3, "0")}.pdf`;
  const url = `https://${PUBLIC_DOMAIN}/${key}`;

  try {
    const upstream = await fetch(url, { cache: "no-store" });
    if (!upstream.ok) {
      return new Response("Scan not found", { status: 404 });
    }
    const buf = Buffer.from(await upstream.arrayBuffer());
    return new Response(buf, {
      status: 200,
      headers: {
        "Content-Type": "application/pdf",
        "Content-Length": String(buf.length),
        "Cache-Control": "public, max-age=86400, immutable",
        // Explicitly allow embedding in same-origin iframes (and anywhere).
        "X-Frame-Options": "SAMEORIGIN",
      },
    });
  } catch {
    return new Response("Failed to load scan", { status: 502 });
  }
}
