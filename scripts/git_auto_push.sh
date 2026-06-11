#!/bin/bash
# git_auto_push.sh — Stage, commit, and push enrichment results to GitHub.
# Called by run_batch.sh after each 10-page batch completes.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

BRANCH="main"

# Collect what changed
CHANGED_RAW=$(git diff --name-only HEAD 2>/dev/null | grep 'ocr/raw/' || true)
CHANGED_ENR=$(git diff --name-only HEAD 2>/dev/null | grep 'ocr/enriched/' || true)
CHANGED_STATE=$(git diff --name-only HEAD 2>/dev/null | grep 'state/' || true)
UNTRACKED=$(git ls-files --others --exclude-standard | grep -E 'ocr/(raw|enriched)/' || true)

ALL_CHANGES=$(echo -e "${CHANGED_RAW}\n${CHANGED_ENR}\n${CHANGED_STATE}\n${UNTRACKED}" | grep -v '^$' | sort -u)

if [ -z "$ALL_CHANGES" ]; then
    echo "[PUSH] No changes to commit."
    exit 0
fi

# Extract page range from changed files
PAGE_NUMS=$(echo "$ALL_CHANGES" | sed -n 's/.*page_0*\([0-9]\+\).*/\1/p' | sort -n | uniq)
if [ -n "$PAGE_NUMS" ]; then
    FIRST=$(echo "$PAGE_NUMS" | head -1)
    LAST=$(echo "$PAGE_NUMS" | tail -1)
    if [ "$FIRST" = "$LAST" ]; then
        RANGE="page ${FIRST}"
    else
        RANGE="pages ${FIRST}-${LAST}"
    fi
else
    RANGE="state update"
fi

# Count changes
RAW_COUNT=$(echo "$ALL_CHANGES" | grep 'ocr/raw/' | wc -l)
ENR_COUNT=$(echo "$ALL_CHANGES" | grep 'ocr/enriched/' | wc -l)

# Build commit message
COMMIT_MSG="feat(ocr): enrich ${RANGE}

• OCR raw: ${RAW_COUNT} page(s) added/updated
• Enriched: ${ENR_COUNT} page(s)
• Pipeline: shams-al-maarif-ocr v1.0.0

Auto-committed by enrichment cron job on $(date +'%Y-%m-%d %H:%M UTC')"

echo "[PUSH] Changes detected for ${RANGE}"
echo "[PUSH] Committing: raw=${RAW_COUNT} enriched=${ENR_COUNT}"

git add ocr/raw/ ocr/enriched/ state/
git commit -m "$COMMIT_MSG"

# Push to GitHub
echo "[PUSH] Pushing to origin ${BRANCH}..."
if git remote -v | grep -q origin; then
    git push origin "${BRANCH}" 2>&1 || echo "[PUSH] WARNING: Push failed — is remote configured?"
else
    echo "[PUSH] No remote 'origin' configured — commit saved locally."
fi

echo "[PUSH] Done."
