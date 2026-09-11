#!/usr/bin/env bash
# Fail if product sources contain org lab hostnames or known lab password fingerprints.
# SECURITY.md / this script may mention the fingerprint for documentation / detection.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# Domain / host fingerprints + lab password pattern historically present in this / sibling repos.
PATTERN='mxhash\.com|gitea\.mxhash|harbor\.mxhash|nexus\.mxhash|upload\.mxhash|/var/lib/mxhash|[Ww]elcomeback'

hits="$(
  grep -rEIn "$PATTERN" "$ROOT" \
    --include='*.yaml' --include='*.yml' --include='*.j2' --include='*.json' --include='*.tf' \
    --include='*.md' --include='*.sh' --include='*.py' --include='*.toml' \
    --exclude-dir=.git \
    --exclude-dir=workspace \
    --exclude-dir=.ansible \
    --exclude-dir=scripts \
    --exclude-dir=tests \
    --exclude-dir=.github \
    --exclude='SECURITY.md' \
    || true
)"

# Drop comment-only YAML/Jinja/TF noise lines (leading # after optional spaces)
hits="$(printf '%s\n' "$hits" | grep -vE ':[0-9]+:[[:space:]]*#' || true)"

# examples/internal is not product path (site-coupled samples); ignore for this guard.
hits="$(printf '%s\n' "$hits" | grep -vE '/examples/internal/' || true)"

if [[ -n "${hits}" ]]; then
  echo "$hits" >&2
  echo "ERROR: org fingerprint found in atlas-compute-provision product sources" >&2
  exit 1
fi

echo "OK: no org hostname hardcodes in atlas-compute-provision product sources"
