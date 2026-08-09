#!/usr/bin/env bash
# Digest gate (v3.0 finding S-01): every GitHub Action pinned by commit
# digest, not tag. The Trivy tag-hijack of March 2026 (GHSA-69fq-xp46-6x23)
# is the reason this gate exists.
set -euo pipefail
fail=0
while IFS= read -r line; do
  if [[ "$line" =~ uses:\ *([A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+)@([^[:space:]]+) ]]; then
    ref="${BASH_REMATCH[2]}"
    if [[ ! "$ref" =~ ^[0-9a-f]{40}$ ]]; then
      echo "DIGEST-GATE FAIL: ${BASH_REMATCH[1]}@$ref is not a commit digest"
      fail=1
    fi
  fi
done < <(grep -h "uses:" .github/workflows/*.yml || true)
if [[ "$fail" -eq 1 ]]; then
  echo "Run tools/pin-actions.sh to resolve tags to digests, then commit."
  exit 1
fi
echo "digest gate: all actions pinned by commit digest"
