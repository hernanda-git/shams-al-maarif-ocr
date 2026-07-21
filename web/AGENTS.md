<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

# Shams al-Ma'arif Reader — AGENT QUICKSTART (DEPLOY REPO · `web/` subdir)

This `web/` folder is the **deploy target** for the Shams reader.
Pushing `main` here triggers GitHub Actions → Vercel (auto-deploy to
`https://shams-al-maarif.vercel.app`).

## Source of truth
App code is edited in the SEPARATE source repo `C:/Workspace/shams-al-maarif`,
then synced here with `cp`. **Do NOT make feature edits here expecting them to
appear in the source repo** — sync flows ONE way (source → this repo).

## Environment gotchas (Windows host)
- `python`/`python3` broken → use `uv run --no-project python <script>`.
- `taskkill /F /PID <pid>` (single slash) to free a stuck :3000.
- Browser tool cannot reach the Vercel prod URL (egress blocked) — use curl.
- `git status` HANGS on this repo (7.7 MB untracked `ocr/source/`). Use
  `git diff --cached --name-only` for fast checks; **NEVER `git add -A`**
  (keeps the 7.7 MB `ocr/source/` out of commits). See skill
  `references/ocr-repo-commit-discipline.md`.

## Path map
- App code: `web/components`, `web/lib`, `web/app`.
- Served data: `web/public/manuscript.json` (regenerated from OCR, NOT hand-edited).
- Deploy config: repo-root `vercel.json` + `.github/workflows/deploy.yml`.

## Authoritative reference
Load skill **`nextjs-manuscript-reader`** for every build / verify / deploy procedure.
The skill also documents the source repo and the two-repo `cp` sync flow.
