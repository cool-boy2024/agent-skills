#!/bin/bash
# pin.sh - Pin a skill so clean.sh won't remove it. (Reverse of unpin.sh.)
#
# Usage:
#   ./scripts/pin.sh <skill-name>
#
# Note: `install.sh` auto-pins on install. Use this only if you want to re-pin an unpinned skill.

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PINNED_FILE="$REPO_ROOT/pinned.txt"

if [ $# -lt 1 ]; then
  echo "Usage: $0 <skill-name>"
  exit 1
fi

NAME="$1"

if grep -qxF "$NAME" "$PINNED_FILE" 2>/dev/null; then
  echo "ℹ️  '$NAME' is already pinned"
  exit 0
fi

echo "$NAME" >> "$PINNED_FILE"
echo "📌 Pinned '$NAME' (clean.sh will now refuse to remove it without --force)"
