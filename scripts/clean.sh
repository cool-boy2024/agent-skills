#!/bin/bash
# clean.sh - Remove an installed skill.
# Usage:
#   ./scripts/clean.sh <skill-name>         # remove globally
#   ./scripts/clean.sh <skill-name> --project
set -e

if [ $# -lt 1 ]; then
  echo "Usage: $0 <skill-name> [--project]"
  echo ""
  echo "Currently installed (per agent):"
  npx -y skills list 2>/dev/null || echo "  (could not list)"
  exit 1
fi

NAME="$1"
shift

echo "🗑  Removing [$NAME]..."
npx -y skills remove "$NAME" -a '*' -y "$@"

# Belt-and-suspenders: also nuke any leftover copies in standard agent skill dirs.
for dir in "$HOME/.claude/skills/$NAME" "$HOME/.codex/skills/$NAME" "$HOME/.cursor/skills/$NAME"; do
  if [ -d "$dir" ]; then
    rm -rf "$dir"
    echo "   also removed $dir"
  fi
done

echo "✅ Removed $NAME"
