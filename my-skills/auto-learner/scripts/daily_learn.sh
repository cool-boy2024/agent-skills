#!/bin/bash
# daily_learn.sh - Discover candidate skills for a topic and append them to catalog/candidates.md.
#
# Usage:
#   ./daily_learn.sh                 # use default topic "any"
#   ./daily_learn.sh "<topic>"       # e.g. "rust async", "kubernetes operator"
#   ./daily_learn.sh --dry-run       # show what would be added, don't write
#
# What it does:
#   1. Search GitHub code for SKILL.md files matching the topic
#   2. For each hit, check freshness (last commit age) via gh api
#   3. Append surviving candidates to ../../catalog/candidates.md
#   4. Does NOT install anything; human reviews candidates.md and runs install.sh manually.
#
# Cron-safe: writes its own log to /tmp/auto-learner.log, exits 0 on no-hits.

set -e

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
CANDIDATES_FILE="$REPO_ROOT/catalog/candidates.md"
LOG="/tmp/auto-learner.log"

# Parse flags
DRY_RUN=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN="--dry-run" ;;
    *) break ;;
  esac
  shift
done

TOPIC="${1:-any}"
DATE=$(date +%F)
log() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG" >&2 ; }

log "=== daily_learn run: topic='$TOPIC' dry_run=${DRY_RUN:-no} ==="

# Ensure candidates file exists with header
if [ ! -f "$CANDIDATES_FILE" ] && [ -z "$DRY_RUN" ]; then
  mkdir -p "$(dirname "$CANDIDATES_FILE")"
  cat > "$CANDIDATES_FILE" <<'EOF'
# Candidate Skills

> Append-only queue. Each row is a skill that survived the gates in `my-skills/auto-learner/SKILL.md`.
> To add to the catalog: review, then copy a `.source.json` template, fill it in, commit.

| Date | Skill | Source | Installs | Last commit | Why it might fit |
|---|---|---|---|---|---|
EOF
fi

# 1. Search GitHub for SKILL.md files
#    The code search API requires a user-agent but gh api provides auth + rate-limit headroom.
#    We constrain to markdown SKILL.md files containing the topic word.
QUERY=$(printf 'filename:SKILL.md+%s' "$TOPIC")
log "query: $QUERY"

RESP=$(gh api "search/code?q=$QUERY&per_page=20" 2>>"$LOG") || RESP=""

if [ -z "$RESP" ]; then
  log "no response for topic '$TOPIC' (gh api call failed; see log)"
  exit 0
fi

# Validate it's JSON before processing
if ! printf '%s' "$RESP" | python3 -c "import json,sys; json.loads(sys.stdin.read())" 2>/dev/null; then
  log "invalid JSON response for topic '$TOPIC' (first 200 chars: ${RESP:0:200})"
  exit 0
fi

# 2. Parse hits
HITS=$(printf '%s' "$RESP" | python3 "$(dirname "$0")/parse_hits.py" 2>>"$LOG" || echo "")

if [ -z "$HITS" ]; then
  log "no hits for topic '$TOPIC'"
  exit 0
fi

# 3. For each hit, check last commit on the repo and decide whether to append
NEW_COUNT=0
EXISTING=$(grep -oE '\| [a-z0-9-]+ \|' "$CANDIDATES_FILE" 2>/dev/null | tr -d ' |' || true)

while IFS=$'\t' read -r name repo path _stars_unused; do
  # Skip if already in catalog metadata
  if [ -f "$REPO_ROOT/skills/$name/.source.json" ]; then
    continue
  fi
  # Skip if already in candidates (avoid duplicates)
  if echo "$EXISTING" | grep -qxF "$name"; then
    continue
  fi

  # One API call per repo to get: stars, last commit date, default branch.
  # We need stars (gate) + freshness; combined into one repo lookup.
  META=$(gh api "repos/$repo" --jq '{stars: .stargazers_count, pushed_at: .pushed_at, archived: .archived, disabled: .disabled}' 2>>"$LOG" || echo "")
  if [ -z "$META" ]; then
    log "  skip $repo: repo metadata fetch failed (probably deleted/private)"
    continue
  fi

  STARS=$(echo "$META" | python3 -c "import json,sys; print(json.loads(sys.stdin.read()).get('stars', 0))" 2>/dev/null || echo 0)
  PUSHED=$(echo "$META" | python3 -c "import json,sys; print(json.loads(sys.stdin.read()).get('pushed_at', ''))" 2>/dev/null || echo "")
  ARCHIVED=$(echo "$META" | python3 -c "import json,sys; print(json.loads(sys.stdin.read()).get('archived', False))" 2>/dev/null || echo "False")

  # Gate 1: not archived/disabled
  if [ "$ARCHIVED" = "True" ]; then
    log "  skip $repo: archived"
    continue
  fi

  # Gate 2: must have ≥ 10 stars
  if [ "${STARS:-0}" -lt 10 ]; then
    log "  skip $repo: low stars (★$STARS)"
    continue
  fi

  # Gate 3: must be pushed within 12 months
  AGE_DAYS="?"
  if [ -n "$PUSHED" ]; then
    PUSHED_EPOCH=$(date -j -f '%Y-%m-%dT%H:%M:%S' "$PUSHED" +%s 2>/dev/null || echo 0)
    if [ "$PUSHED_EPOCH" -gt 0 ]; then
      AGE_DAYS=$(( ( $(date +%s) - PUSHED_EPOCH ) / 86400 ))
    fi
  fi
  if [ "$AGE_DAYS" != "?" ] && [ "$AGE_DAYS" -gt 365 ]; then
    log "  skip $repo: stale (last push ${AGE_DAYS}d ago)"
    continue
  fi

  ROW="| $DATE | $name | $repo | ? | ${AGE_DAYS}d (★${STARS}) | topic=$TOPIC |"
  log "  + $repo (★$STARS, last push ${AGE_DAYS}d ago)"

  if [ -z "$DRY_RUN" ]; then
    echo "$ROW" >> "$CANDIDATES_FILE"
  fi
  NEW_COUNT=$((NEW_COUNT + 1))
done <<< "$HITS"

log "=== done. $NEW_COUNT new candidate(s) added. ==="
