#!/bin/bash
# install.sh - Download a skill by name from this catalog into the local agent's skills dir.
# Usage:
#   ./scripts/install.sh                    # list available skills
#   ./scripts/install.sh <skill-name>       # install globally
#   ./scripts/install.sh <skill-name> --project   # install to current project only
#
# After install, the skill content lives at ~/.claude/skills/<name>/ (or ./.claude/skills/<name>/ for --project).
# Use ./scripts/clean.sh <skill-name> to remove.

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

if [ $# -eq 0 ]; then
  echo "Available skills in this catalog:"
  echo ""
  printf "  %-22s  %-12s  %s\n" "NAME" "CATEGORY" "DESCRIPTION"
  printf "  %-22s  %-12s  %s\n" "----" "--------" "-----------"
  for d in skills/*/; do
    if [ -f "$d/.source.json" ]; then
      name=$(basename "$d")
      cat=$(jq -r .category "$d/.source.json")
      desc=$(jq -r .description "$d/.source.json" | head -c 60)
      printf "  %-22s  %-12s  %s\n" "$name" "$cat" "$desc..."
    fi
  done
  echo ""
  echo "My own skills (already on disk under my-skills/):"
  for d in my-skills/*/; do
    [ -f "$d/SKILL.md" ] && echo "  $(basename "$d")"
  done
  exit 0
fi

NAME="$1"
shift
SOURCE_FILE="skills/$NAME/.source.json"

if [ ! -f "$SOURCE_FILE" ]; then
  echo "❌ Unknown skill: $NAME"
  echo "Run '$0' (no args) to see available skills."
  exit 1
fi

OWNER=$(jq -r '.source.owner' "$SOURCE_FILE")
REPO=$(jq -r '.source.repo' "$SOURCE_FILE")
SKILL_NAME=$(jq -r '.name' "$SOURCE_FILE")
METHOD=$(jq -r '.install.method' "$SOURCE_FILE")
CUSTOM_CMD=$(jq -r '.install.command' "$SOURCE_FILE")
LICENSE=$(jq -r '.source.license' "$SOURCE_FILE")
INSTALLS=$(jq -r '.metrics.installs' "$SOURCE_FILE")

echo "📦 Installing [$SKILL_NAME] from $OWNER/$REPO (license: $LICENSE, installs: $INSTALLS)"
echo ""

# npx skills add defaults to interactive + symlink; we want non-interactive + copy so the user can rm -rf cleanly.
if [ "$METHOD" = "npx" ]; then
  npx -y skills add "$OWNER/$REPO" --skill "$SKILL_NAME" -a '*' --copy -y "$@"
else
  echo "→ Custom install: $CUSTOM_CMD"
  eval "$CUSTOM_CMD"
fi

echo ""
echo "✅ Done. Verify with: npx skills list"
echo "   Remove with:    ./scripts/clean.sh $NAME"
