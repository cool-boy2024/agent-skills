#!/bin/bash
# install.sh - Download a skill by name from this catalog into ~/.claude/skills/<name>/.
#
# Usage:
#   ./scripts/install.sh                        # list available skills
#   ./scripts/install.sh <skill-name>           # install to claude-code (default)
#   ./scripts/install.sh <skill-name> --project # install to ./.claude/skills/<name>/ instead
#
# Implementation: `curl` codeload.github.com tarball + `tar -xz` + `cp` the subpath.
# This avoids `gh repo clone` (which uses git+https://github.com and is blocked on this network)
# AND avoids `npx skills add` (which scans 70+ candidate "agent dirs" and may wipe our catalog).

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

PROJECT_FLAG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --project) PROJECT_FLAG="--project" ;;
    *) echo "Unknown flag: $1"; exit 1 ;;
  esac
  shift
done

OWNER=$(jq -r '.source.owner' "$SOURCE_FILE")
REPO=$(jq -r '.source.repo' "$SOURCE_FILE")
REF=$(jq -r '.source.ref' "$SOURCE_FILE")
SUBPATH=$(jq -r '.source.path' "$SOURCE_FILE")
LICENSE=$(jq -r '.source.license' "$SOURCE_FILE")
INSTALLS=$(jq -r '.metrics.installs' "$SOURCE_FILE")

if [ "$PROJECT_FLAG" = "--project" ]; then
  DEST="$REPO_ROOT/.claude/skills/$NAME"
else
  DEST="$HOME/.claude/skills/$NAME"
fi

echo "📦 Installing [$NAME] from $OWNER/$REPO (ref: $REF, subpath: $SUBPATH)"
echo "   license: $LICENSE | installs: $INSTALLS"
echo "   → $DEST"
echo ""

# Download tarball from codeload.github.com (works on networks that block github.com:443)
TMP=$(mktemp -d)
trap "rm -rf '$TMP'" EXIT

URL="https://codeload.github.com/$OWNER/$REPO/tar.gz/$REF"
echo "   fetching $URL ..."
curl -sL --max-time 60 "$URL" | tar -xz -C "$TMP" 2>&1 | tail -3 || {
  echo "❌ Failed to download $URL"
  exit 1
}

# Find the extracted top-level dir (it's <repo>-<ref>)
EXTRACTED=$(find "$TMP" -mindepth 1 -maxdepth 1 -type d | head -1)
if [ -z "$EXTRACTED" ]; then
  echo "❌ Tarball extraction failed"
  exit 1
fi

SRC="$EXTRACTED/$SUBPATH"
if [ ! -d "$SRC" ]; then
  echo "❌ Subpath '$SUBPATH' not found in $OWNER/$REPO at $REF"
  exit 1
fi

mkdir -p "$DEST"
rm -rf "$DEST"/*
cp -R "$SRC/." "$DEST/"

echo ""
echo "✅ Installed to $DEST"
echo "   Verify: ls $DEST"
echo "   Remove: ./scripts/clean.sh $NAME$([ "$PROJECT_FLAG" = "--project" ] && echo " --project" || true)"
