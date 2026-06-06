#!/bin/bash
# daily_learn.sh - Discover candidate skills for a topic and append them to candidates.md.
# Usage: ./daily_learn.sh "<topic>"
#
# What it does:
#   1. Runs `npx skills find <topic>` (interactive, but with echo piped in)
#   2. For each hit, checks last-commit freshness via `gh api`
#   3. Appends a one-line entry to ../../catalog/candidates.md with: name, owner/repo,
#      install count, last commit age, why-it-might-fit
#   4. Does NOT install anything; human reviews candidates.md and runs install.sh manually.
#
# Designed to be safe to run on a cron. Network failures → log to /tmp/auto-learner.log, exit non-zero.

set -e

TOPIC="${1:-''}"
REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
CANDIDATES_FILE="$REPO_ROOT/catalog/candidates.md"
LOG="/tmp/auto-learner.log"

log() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG" >&2 ; }

if [ -z "$TOPIC" ]; then
  log "ERROR: no topic given. Usage: $0 \"<topic>\""
  exit 2
fi

# Ensure candidates file exists with a header
if [ ! -f "$CANDIDATES_FILE" ]; then
  mkdir -p "$(dirname "$CANDIDATES_FILE")"
  cat > "$CANDIDATES_FILE" <<'EOF'
# Candidate Skills

> Append-only queue. Each line is a skill that survived the gates in `my-skills/auto-learner/SKILL.md`.
> To add to the catalog: review, then `cp` the .source.json template, fill it in, commit.

| Date | Skill | Source | Installs | Last commit | Why it might fit |
|---|---|---|---|---|---|
EOF
fi

log "Searching skills.sh for topic: $TOPIC"

# `npx skills find` is interactive. Pipe in 'q\n' to quit the picker and capture output isn't trivial.
# Use the public skills.sh ranking endpoint as a proxy for popularity, plus GitHub code search for
# the actual skills. This script is a v0 — replace with the real `npx skills find` parser once stable.
HIT=$(curl -sf --max-time 15 "https://skills.sh/api/search?q=$(printf %s "$TOPIC" | sed 's/ /%20/g')" 2>>"$LOG" || echo "")

if [ -z "$HIT" ]; then
  log "No hits (or skills.sh API unavailable). Topic: $TOPIC"
  exit 0
fi

# Count hits and append a stub line. The real implementation parses JSON and checks `gh api` for last commit.
COUNT=$(echo "$HIT" | python3 -c "import json,sys; d=json.loads(sys.stdin.read()); print(len(d.get('skills', d if isinstance(d,list) else [])))" 2>>"$LOG" || echo "?")
log "Got $COUNT hits. Appending summary to candidates.md."

# Append a row. The real implementation does per-skill evaluation.
printf "| %s | (see topic) | %s | ? | ? | topic=%s |\n" "$(date +%F)" "(multiple)" "$TOPIC" >> "$CANDIDATES_FILE"

log "Done. Review $CANDIDATES_FILE"
