#!/usr/bin/env node
/**
 * Upload all per-page scanned PDFs from public/scans/ to the Cloudflare R2
 * bucket "shams-al-maarif" so the production app can serve facsimiles
 * (instead of falling back to OCR text).
 *
 * Credentials are read from .env.local (never hardcoded / never committed).
 * R2 is S3-compatible; we point the SDK at the jurisdiction endpoint.
 *
 * Object layout in R2:  page-001.pdf ... page-604.pdf  (same keys the app
 * already references via scanSrc, but served from the R2 public domain).
 */
const fs = require("fs");
const path = require("path");
const { S3Client, PutObjectCommand, HeadBucketCommand } = require("@aws-sdk/client-s3");

// Load .env.local manually (avoid dotenvx/dotenv quirks)
(function loadEnv() {
  const fp = path.join(__dirname, "..", ".env.local");
  if (!fs.existsSync(fp)) return;
  for (const line of fs.readFileSync(fp, "utf8").split("\n")) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (m) process.env[m[1]] = m[2].replace(/\r$/, "");
  }
})();

const ACCOUNT_ID = process.env.R2_ACCOUNT_ID;
const ACCESS_KEY = process.env.R2_ACCESS_KEY_ID;
const SECRET = process.env.R2_SECRET_ACCESS_KEY;
const BUCKET = process.env.R2_BUCKET;
const PUBLIC_DOMAIN = process.env.R2_PUBLIC_DOMAIN;
const SCANS_DIR = path.join(__dirname, "..", "public", "scans");

if (!ACCOUNT_ID || !ACCESS_KEY || !SECRET || !BUCKET) {
  console.error("Missing R2 credentials in .env.local");
  process.exit(1);
}

const client = new S3Client({
  region: "auto",
  endpoint: `https://${ACCOUNT_ID}.r2.cloudflarestorage.com`,
  credentials: { accessKeyId: ACCESS_KEY, secretAccessKey: SECRET },
});

async function main() {
  // sanity check bucket reachable
  try {
    await client.send(new HeadBucketCommand({ Bucket: BUCKET }));
    console.log(`Bucket "${BUCKET}" reachable.`);
  } catch (e) {
    console.error("Cannot reach bucket:", e.message);
    process.exit(1);
  }

  const files = fs
    .readdirSync(SCANS_DIR)
    .filter((f) => /^page-\d+\.pdf$/.test(f))
    .sort();
  console.log(`Found ${files.length} scan PDFs.`);

  let ok = 0;
  let fail = 0;
  for (let i = 0; i < files.length; i++) {
    const f = files[i];
    const body = fs.readFileSync(path.join(SCANS_DIR, f));
    const key = f; // page-NNN.pdf
    try {
      await client.send(
        new PutObjectCommand({
          Bucket: BUCKET,
          Key: key,
          Body: body,
          ContentType: "application/pdf",
          // public-read so the app can fetch via the R2 public domain
          ACL: "public-read",
        })
      );
      ok++;
      if (i % 50 === 0 || i === files.length - 1) {
        console.log(`[${i + 1}/${files.length}] uploaded ${key} (${body.length} bytes)`);
      }
    } catch (e) {
      fail++;
      console.error(`[${i + 1}/${files.length}] FAILED ${key}: ${e.message}`);
    }
  }

  console.log(`\nDone. uploaded=${ok} failed=${fail}`);
  console.log(`Public base: https://${PUBLIC_DOMAIN}/`);
}
main();
