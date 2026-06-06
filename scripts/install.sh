#!/bin/bash
# install.sh - Download a skill by name from this catalog into ~/.claude/skills/<name>/.
#
# Usage:
#   ./scripts/install.sh                        # list available skills (with pinned/installed status)
#   ./scripts/install.sh <skill-name>           # install to claude-code, then auto-pin
#   ./scripts/install.sh <skill-name> --project # install to ./.claude/skills/<name>/ instead
#   ./scripts/install.sh <skill-name> --no-pin  # install but do NOT pin
#
# Auto-pin behavior: when a skill is installed, it's added to pinned.txt. clean.sh will then
# refuse to remove it without --force. Use ./scripts/unpin.sh <name> to remove from pinned.
#
# Implementation: `curl` codeload.github.com tarball + `tar -xz` + `cp` the subpath.

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
PINNED_FILE="$REPO_ROOT/pinned.txt"

if [ $# -eq 0 ]; then
  echo "Available skills in this catalog:"
  echo ""
  printf "  %-22s  %-12s  %-7s  %-7s  %s\n" "NAME" "CATEGORY" "PINNED" "INSTALLED" "DESCRIPTION"
  printf "  %-22s  %-12s  %-7s  %-7s  %s\n" "----" "--------" "------" "--------- " "-----------"
  for d in skills/*/; do
    if [ -f "$d/.source.json" ]; then
      name=$(basename "$d")
      cat=$(jq -r .category "$d/.source.json")
      desc=$(jq -r .description "$d/.source.json" | head -c 50)
      # pin status
      if grep -qxF "$name" "$PINNED_FILE" 2>/dev/null; then pin="yes"; else pin="no"; fi
      # installed status
      if [ -d "$HOME/.claude/skills/$name" ] || [ -d "$REPO_ROOT/.claude/skills/$name" ]; then inst="yes"; else inst="no"; fi
      printf "  %-22s  %-12s  %-7s  %-7s  %s\n" "$name" "$cat" "$pin" "$inst" "$desc..."
    fi
  done
  echo ""
  echo "My own skills (always on disk, never need install):"
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
NO_PIN=""
while [ $# -gt 0 ]; do
  case "$1" in
    --project) PROJECT_FLAG="--project" ;;
    --no-pin)  NO_PIN="--no-pin" ;;
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

# Auto-pin (unless --no-pin)
if [ -z "$NO_PIN" ]; then
  if ! grep -qxF "$NAME" "$PINNED_FILE" 2>/dev/null; then
    echo "$NAME" >> "$PINNED_FILE"
    echo "📌 pinned (use ./scripts/unpin.sh $NAME to allow removal)"
  else
    echo "📌 already pinned"
  fi
fi

echo ""
echo "✅ Installed to $DEST"
echo "   Remove with: ./scripts/unpin.sh $NAME && ./scripts/clean.sh $NAME"
echo "   Force-remove without unpinning: ./scripts/clean.sh $NAME --force"
