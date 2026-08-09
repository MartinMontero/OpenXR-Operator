#!/usr/bin/env bash
# Resolves every tag-pinned `uses:` in the workflows to a commit digest via
# the GitHub API, and rewrites the workflow files in place, keeping the
# original tag as a comment. Run once after bootstrap, then commit.
set -euo pipefail
for wf in .github/workflows/*.yml; do
  tmp="$wf.pinned"
  while IFS= read -r line; do
    if [[ "$line" =~ ^([[:space:]]*-?\ *uses:\ *)([A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+)@([^[:space:]#]+)(.*)$ ]]; then
      prefix="${BASH_REMATCH[1]}"; repo="${BASH_REMATCH[2]}"; ref="${BASH_REMATCH[3]}"
      if [[ "$ref" =~ ^[0-9a-f]{40}$ ]]; then echo "$line"; continue; fi
      # Subpath actions (owner/repo/path@ref): API root is first two segments
      api_repo="$(cut -d/ -f1,2 <<<"$repo")"
      sha="$(curl -fsSL "https://api.github.com/repos/$api_repo/git/refs/tags/$ref" \
             | python3 -c "import sys,json; o=json.load(sys.stdin); print(o['object']['sha'])" \
             || true)"
      if [[ -z "$sha" ]]; then
        echo "WARNING: could not resolve $repo@$ref — left as tag (resolve manually)" >&2
        echo "$line"
      else
        echo "${prefix}${repo}@${sha} # ${ref}"
      fi
    else
      echo "$line"
    fi
  done < "$wf" > "$tmp"
  mv "$tmp" "$wf"
done
echo "Pinned. Verify with: bash tools/check-action-pins.sh"
