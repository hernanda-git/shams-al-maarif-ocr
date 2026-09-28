#!/usr/bin/env bash
# Validate a set of pages against the V2 deterministic validator.
# Usage: bash check_pages.sh 59 60 69 112 131
set -u
cd "C:/Workspace/gw-shams-repair" || exit 1
pass=0; fail=0; failed=""
for p in "$@"; do
  out=$(uv run --no-project python scripts/verify_translation_v2_page.py "$p" 2>&1)
  if echo "$out" | head -1 | grep -q '^PASS'; then
    pass=$((pass+1))
  else
    fail=$((fail+1)); failed="$failed $p"
    echo "--- FAIL page $p"
    echo "$out" | head -6
  fi
done
echo ""
echo "PASS=$pass FAIL=$fail"
[ -n "$failed" ] && echo "failed:$failed"
exit 0
