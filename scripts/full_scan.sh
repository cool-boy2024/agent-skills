#!/bin/bash
# full_scan.sh - Quarterly full scan of all SKILL.md-bearing repos.
# Two-tier output (decided 2026-06-06 in /grill-me session):
#   - >= 50,000 stars  -> tier=install  (suggested action: 装)
#   - >=  5,000 stars  -> tier=read     (suggested action: 🔖收藏 / 看)
#   - <   5,000 stars  -> dropped
#
# Differs from daily_learn.sh:
#   - No topic filter (broader sweep)
#   - No time filter (catches old-but-still-great projects the daily cron misses)
#   - Each appended row tagged "source=full_scan" + tier for traceability
#   - LOWER floor (5k instead of 50k) so the read-only tier populates
#
# Cron quarterly: 0 9 1 1,4,7,10 * (Jan/Apr/Jul/Oct 1st, 9am)

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CANDIDATES_FILE="$REPO_ROOT/catalog/candidates.md"
LOG="/tmp/auto-learner.log"

DRY_RUN=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN="--dry-run" ;;
    *) break ;;
  esac
  shift
done

DATE=$(date +%F)
log() { echo "[$(date '+%F %T')] [full_scan] $*" | tee -a "$LOG" >&2 ; }

log "=== full_scan run dry_run=${DRY_RUN:-no} ==="

# Ensure candidates file exists with header
if [ ! -f "$CANDIDATES_FILE" ] && [ -z "$DRY_RUN" ]; then
  mkdir -p "$(dirname "$CANDIDATES_FILE")"
  cat > "$CANDIDATES_FILE" <<'EOF'
# Candidate Skills

> Append-only raw queue. Each row passes the 50k+ stars gate + activity + non-archived check.
> Next session, Claude reads this and writes curated entries to `digest.md`.
> To install a skill from here: copy a `.source.json` template into `skills/<name>/`, fill it in, then `./scripts/install.sh <name>`.

| Date | Skill | Source | Installs | Last commit | Why it might fit | Source script |
|---|---|---|---|---|---|---|
EOF
fi

# 1. Broad code search — no topic, just SKILL.md files
#    GitHub code search returns by relevance; we filter by stars per-repo afterwards.
QUERY="filename:SKILL.md"
log "query: $QUERY (broad)"

RESP=$(gh api "search/code?q=$QUERY&per_page=30" 2>>"$LOG") || RESP=""

if [ -z "$RESP" ]; then
  log "no response (gh api call failed; see log)"
  exit 0
fi

if ! printf '%s' "$RESP" | python3 -c "import json,sys; json.loads(sys.stdin.read())" 2>/dev/null; then
  log "invalid JSON response (first 200 chars: ${RESP:0:200})"
  exit 0
fi

# 2. Parse hits (same parser as daily_learn.sh)
HITS=$(printf '%s' "$RESP" | python3 "$(dirname "$0")/../my-skills/auto-learner/scripts/parse_hits.py" 2>>"$LOG" || echo "")

if [ -z "$HITS" ]; then
  log "no hits"
  exit 0
fi

# 3. Per-repo metadata + gates
NEW_COUNT=0
EXISTING=$(grep -oE '\| [a-z0-9-]+ \|' "$CANDIDATES_FILE" 2>/dev/null | tr -d ' |' || true)

while IFS=$'\t' read -r name repo path _stars_unused; do
  if [ -f "$REPO_ROOT/skills/$name/.source.json" ]; then
    continue
  fi
  if echo "$EXISTING" | grep -qxF "$name"; then
    continue
  fi

  META=$(gh api "repos/$repo" --jq '{stars: .stargazers_count, pushed_at: .pushed_at, archived: .archived, disabled: .disabled}' 2>>"$LOG" || echo "")
  if [ -z "$META" ]; then
    log "  skip $repo: repo metadata fetch failed"
    continue
  fi

  STARS=$(echo "$META" | python3 -c "import json,sys; print(json.loads(sys.stdin.read()).get('stars', 0))" 2>/dev/null || echo 0)
  PUSHED=$(echo "$META" | python3 -c "import json,sys; print(json.loads(sys.stdin.read()).get('pushed_at', ''))" 2>/dev/null || echo "")
  ARCHIVED=$(echo "$META" | python3 -c "import json,sys; print(json.loads(sys.stdin.read()).get('archived', False))" 2>/dev/null || echo "False")

  if [ "$ARCHIVED" = "True" ]; then
    log "  skip $repo: archived"
    continue
  fi

  # Two-tier gate (user's curator design; see feedback_discovery_threshold.md):
  #   < 5k   -> drop (well below the floor, no curator value)
  #   5k-50k -> keep as tier=read (🔖收藏 / 看)
  #   >= 50k -> keep as tier=install (装)
  if [ "${STARS:-0}" -lt 5000 ]; then
    log "  skip $repo: below 5k star floor (★$STARS)"
    continue
  fi

  if [ "${STARS:-0}" -ge 50000 ]; then
    TIER="install"
  else
    TIER="read"
  fi

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

  ROW="| $DATE | $name | $repo | ? | ${AGE_DAYS}d (★${STARS}) | topic=broad | full_scan | $TIER |"
  log "  + $repo (★$STARS, last push ${AGE_DAYS}d ago, tier=$TIER)"

  if [ -z "$DRY_RUN" ]; then
    echo "$ROW" >> "$CANDIDATES_FILE"
  fi
  NEW_COUNT=$((NEW_COUNT + 1))
done <<< "$HITS"

log "=== done. $NEW_COUNT new candidate(s) added by full_scan. ==="
