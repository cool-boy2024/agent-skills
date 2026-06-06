#!/bin/bash
# clean.sh - Remove an installed skill.
#
# Usage:
#   ./scripts/clean.sh <skill-name>           # remove only if NOT pinned (default safe)
#   ./scripts/clean.sh <skill-name> --force   # remove even if pinned
#   ./scripts/clean.sh <skill-name> --project # remove from ./.claude/skills/ instead of ~/.claude/skills/
#
# To remove a pinned skill safely: ./scripts/unpin.sh <name> first, then ./scripts/clean.sh <name>.
#
# Belt-and-suspenders: also scans for any other straggler dirs named <skill-name> in agent skill
# locations under the current project and $HOME, excluding our catalog metadata dir.

set -e

if [ $# -lt 1 ]; then
  echo "Usage: $0 <skill-name> [--force] [--project]"
  echo ""
  echo "Currently installed skills:"
  for d in "$HOME/.claude/skills"/*/ "$REPO_ROOT/.claude/skills"/*/; do
    [ -d "$d" ] && echo "  $(basename "$d")  ($d)"
  done 2>/dev/null
  exit 1
fi

NAME="$1"
shift
FORCE=""
PROJECT_FLAG=""
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PINNED_FILE="$REPO_ROOT/pinned.txt"

while [ $# -gt 0 ]; do
  case "$1" in
    --force)   FORCE="--force" ;;
    --project) PROJECT_FLAG="--project" ;;
    *) echo "Unknown flag: $1"; exit 1 ;;
  esac
  shift
done

# Pinned-skill guard
if [ -z "$FORCE" ] && grep -qxF "$NAME" "$PINNED_FILE" 2>/dev/null; then
  echo "🛑 '$NAME' is PINNED. Refusing to remove."
  echo "   To remove: ./scripts/unpin.sh $NAME  (then re-run this script)"
  echo "   Or force:  ./scripts/clean.sh $NAME --force"
  exit 1
fi

CATALOG_DIR="$REPO_ROOT/skills/$NAME"

echo "🗑  Removing [$NAME]..."

REMOVED=0

# Primary: claude-code dir
if [ "$PROJECT_FLAG" = "--project" ]; then
  PRIMARY="$REPO_ROOT/.claude/skills/$NAME"
else
  PRIMARY="$HOME/.claude/skills/$NAME"
fi
if [ -d "$PRIMARY" ]; then
  rm -rf "$PRIMARY"
  echo "   removed $PRIMARY"
  REMOVED=$((REMOVED + 1))
fi

# Belt-and-suspenders: any other *\*/skills/<name> under . or $HOME, excluding our catalog dir.
while read -r d; do
  [ -z "$d" ] && continue
  abs=$(cd "$d" 2>/dev/null && pwd)
  [ -z "$abs" ] && continue
  if [ "$abs" = "$CATALOG_DIR" ]; then continue; fi
  rm -rf "$d"
  echo "   removed $d"
  REMOVED=$((REMOVED + 1))
done < <(find . "$HOME" -type d -name "$NAME" -path "*/skills/$NAME" 2>/dev/null | sort -u)

echo ""
echo "✅ Removed $NAME from $REMOVED location(s)."
echo "   Catalog metadata at $CATALOG_DIR is preserved (intentional)."
