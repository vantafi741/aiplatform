#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# Create and push annotated release tag.
# Usage:
#   bash scripts/pin_release.sh v0.1.0

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

if [ "${1:-}" = "" ]; then
  echo "Usage: bash scripts/pin_release.sh <tag>"
  echo "Example: bash scripts/pin_release.sh v0.1.0"
  exit 1
fi

TAG_NAME="$1"

if ! echo "$TAG_NAME" | grep -Eq '^v[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z]+)?$'; then
  echo "[WARN] Tag format is unusual. Recommended: vX.Y.Z"
fi

echo "[STEP] fetch tags"
git fetch --tags --prune

if git rev-parse -q --verify "refs/tags/$TAG_NAME" >/dev/null; then
  echo "[FAIL] Tag already exists locally: $TAG_NAME"
  exit 1
fi

if git ls-remote --tags origin "refs/tags/$TAG_NAME" | grep -q .; then
  echo "[FAIL] Tag already exists on origin: $TAG_NAME"
  exit 1
fi

echo "[STEP] create annotated tag: $TAG_NAME"
git tag -a "$TAG_NAME" -m "Release $TAG_NAME"

echo "[STEP] push tag to origin"
git push origin "$TAG_NAME"

echo "[DONE] Tag pushed: $TAG_NAME"
echo "[NEXT] VPS deploy command:"
echo "  bash scripts/deploy_vps.sh $TAG_NAME"
