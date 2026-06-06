#!/bin/bash
# unpin.sh - Remove a skill from the pinned list, allowing clean.sh to delete it.
#
# Usage:
#   ./scripts/unpin.sh <skill-name>     # unpin
#   ./scripts/pin.sh <skill-name>       # re-pin (alias)
#
# This does NOT remove the skill from ~/.claude/skills/. To actually remove it:
#   ./scripts/unpin.sh <name> && ./scripts/clean.sh <name>

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PINNED_FILE="$REPO_ROOT/pinned.txt"

if [ $# -lt 1 ]; then
  echo "Currently pinned skills:"
  grep -v '^#' "$PINNED_FILE" 2>/dev/null | grep -v '^$' | sed 's/^/  /'
  exit 0
fi

NAME="$1"

if ! grep -qxF "$NAME" "$PINNED_FILE" 2>/dev/null; then
  echo "ℹ️  '$NAME' is not pinned (nothing to do)"
  exit 0
fi

# Remove the line in-place (preserves comments and other entries)
grep -vxF "$NAME" "$PINNED_FILE" > "$PINNED_FILE.tmp"
mv "$PINNED_FILE.tmp" "$PINNED_FILE"

echo "📍 Unpinned '$NAME'. It can now be removed with:"
echo "   ./scripts/clean.sh $NAME"
