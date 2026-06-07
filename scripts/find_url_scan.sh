#!/bin/bash
# find_url_scan.sh - Discover repos from the user's local browser history/bookmarks
# via web-access's find-url, then run them through the same gates as full_scan.
#
# Complements the cron discovery (popularity-based) with user-specific signal
# (what the user has been browsing on GitHub). One user runs Claude = one scan.
#
# Why this exists: cron tells us "what's hot on GitHub". find-url tells us
# "what have you been looking at". Both matter — popular = quality, your-browsing
# = relevance. The intersection is gold; the union is the full curator's view.
#
# Privacy: this reads ~/Library/Application Support/... browser data. Output stays local.

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CANDIDATES_FILE="$REPO_ROOT/catalog/candidates.md"
LOG="/tmp/auto-learner.log"
FIND_URL="$HOME/.claude/skills/web-access/scripts/find-url.mjs"

# Sanity check: is web-access installed?
if [ ! -f "$FIND_URL" ]; then
  log_skip() { echo "[$(date '+%F %T')] [find_url_scan] $*" | tee -a "$LOG" >&2 ; }
  log_skip "web-access not installed at $FIND_URL — skipping"
  exit 0
fi

DRY_RUN=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN="--dry-run" ;;
    *) break ;;
  esac
  shift
done

DATE=$(date +%F)
log() { echo "[$(date '+%F %T')] [find_url_scan] $*" | tee -a "$LOG" >&2 ; }

log "=== find_url_scan run dry_run=${DRY_RUN:-no} ==="

# Ensure candidates file exists
if [ ! -f "$CANDIDATES_FILE" ] && [ -z "$DRY_RUN" ]; then
  mkdir -p "$(dirname "$CANDIDATES_FILE")"
  cat > "$CANDIDATES_FILE" <<'EOF'
# Candidate Skills

> Append-only raw queue. Each row passes the ≥ 5,000 stars floor + activity + non-archived check.
> Tier column tells Claude what action to recommend in `digest.md`:
> - `install` (≥ 50k stars) → suggested action: 🟢装
> - `read` (5k–50k stars) → suggested action: 🔖收藏 / 看
>
> Next session, Claude reads this and writes curated entries to `digest.md`.

| Date | Skill | Source | Installs | Last commit | Why it might fit | Source script | Tier |
|---|---|---|---|---|---|---|---|
EOF
fi

# 1. Run find-url on a set of relevant keywords. History-only, last 14 days.
#    Keywords chosen to surface: Claude-related stuff, web3, agent frameworks, popular dev tools.
EXISTING=$(grep -oE '\| [a-z0-9-]+ \|' "$CANDIDATES_FILE" 2>/dev/null | tr -d ' |' || true)
ALREADY_INSTALLED=$(ls "$REPO_ROOT/skills/" 2>/dev/null | grep -v '^\.' || true)

NEW_COUNT=0

# Track seen repos in a tmpfile (bash 3.2 compat — no associative arrays)
SEEN_FILE=$(mktemp)
trap "rm -f '$SEEN_FILE'" EXIT

# Extract github.com/<owner>/<repo> URLs from find-url output, dedupe, dedupe-against-existing
extract_and_process() {
  local keyword="$1"
  local out
  out=$(node "$FIND_URL" "$keyword" --since 14d --only history --limit 20 2>/dev/null || echo "")

  if [ -z "$out" ]; then
    return
  fi

  # Pull github.com/owner/repo URLs (ignore search URLs and other noise)
  echo "$out" | grep -oE 'https?://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+' \
    | sed -E 's|https?://github\.com/||; s|/$||; s|\.git$||' \
    | grep -v -E '/(issues|pull|discussions|actions|projects|wiki|settings|notifications|search|sponsors|orgs|users|topics|tags|blob|tree|raw|releases|commit|pulse|community|security|insights|forks|stargazers|watchers|activity|network)/' \
    | awk -F/ 'NF==2' \
    | sort -u | while IFS=/ read -r owner repo; do
      [ -z "$owner" ] || [ -z "$repo" ] && continue
      repo_name="$repo"
      key="$owner/$repo"

      # Skip if already seen in this run
      if grep -qxF "$key" "$SEEN_FILE" 2>/dev/null; then
        continue
      fi
      echo "$key" >> "$SEEN_FILE"

      # Skip if already in candidates
      if echo "$EXISTING" | grep -qxF "$repo_name"; then
        log "  skip $key: already in candidates"
        continue
      fi

      # Skip if already installed
      if echo "$ALREADY_INSTALLED" | grep -qxF "$repo_name"; then
        log "  skip $key: already installed"
        continue
      fi

      # Fetch metadata
      META=$(gh api "repos/$key" --jq '{stars: .stargazers_count, pushed_at: .pushed_at, archived: .archived, disabled: .disabled, has_skill: (.size > 0)}' 2>>"$LOG" || echo "")
      if [ -z "$META" ]; then
        log "  skip $key: metadata fetch failed"
        continue
      fi

      STARS=$(echo "$META" | python3 -c "import json,sys; print(json.loads(sys.stdin.read()).get('stars', 0))" 2>/dev/null || echo 0)
      PUSHED=$(echo "$META" | python3 -c "import json,sys; print(json.loads(sys.stdin.read()).get('pushed_at', ''))" 2>/dev/null || echo "")
      ARCHIVED=$(echo "$META" | python3 -c "import json,sys; print(json.loads(sys.stdin.read()).get('archived', False))" 2>/dev/null || echo "False")

      # Gate: not archived
      if [ "$ARCHIVED" = "True" ]; then
        log "  skip $key: archived"
        continue
      fi

      # Gate: 5k floor (same as full_scan)
      if [ "${STARS:-0}" -lt 5000 ]; then
        log "  skip $key: below 5k star floor (★$STARS)"
        continue
      fi

      # Gate: pushed within 12 months
      AGE_DAYS="?"
      if [ -n "$PUSHED" ]; then
        PUSHED_EPOCH=$(date -j -f '%Y-%m-%dT%H:%M:%S' "$PUSHED" +%s 2>/dev/null || echo 0)
        if [ "$PUSHED_EPOCH" -gt 0 ]; then
          AGE_DAYS=$(( ( $(date +%s) - PUSHED_EPOCH ) / 86400 ))
        fi
      fi
      if [ "$AGE_DAYS" != "?" ] && [ "$AGE_DAYS" -gt 365 ]; then
        log "  skip $key: stale (last push ${AGE_DAYS}d ago)"
        continue
      fi

      # Gate: must have a SKILL.md (or a clear skills/ subdir)
      # Use `// empty` so jq returns nothing on error responses (where .name is absent),
      # not the literal "null" — the previous `|| echo ""` pattern didn't work because
      # gh api prints the 404 JSON to stdout BEFORE the || triggers, and that output
      # gets captured by $().
      HAS_SKILL=$(gh api "repos/$key/contents/SKILL.md" --jq '.name // empty' 2>/dev/null)
      if [ -z "$HAS_SKILL" ]; then
        # Try skills/ subdir
        HAS_SKILL=$(gh api "repos/$key/contents/skills" --jq 'if type == "array" then .[0].name else empty end' 2>/dev/null)
      fi
      if [ -z "$HAS_SKILL" ]; then
        log "  skip $key: no SKILL.md or skills/ subdir"
        continue
      fi

      # Tier
      if [ "${STARS:-0}" -ge 50000 ]; then
        TIER="install"
      else
        TIER="read"
      fi

      ROW="| $DATE | $repo_name | $key | ? | ${AGE_DAYS}d (★${STARS}) | topic=$keyword | find-url | $TIER |"
      log "  + $key (★$STARS, last push ${AGE_DAYS}d ago, tier=$TIER)"

      if [ -z "$DRY_RUN" ]; then
        echo "$ROW" >> "$CANDIDATES_FILE"
      fi
      NEW_COUNT=$((NEW_COUNT + 1))
    done
}

# Run a set of relevant searches against user's browser history
for kw in "github" "claude" "agent" "web3" "defi" "trading" "skill" "typescript" "rust" "python"; do
  extract_and_process "$kw"
done

# Count rows actually added in this run (find_url_scan rows with today's date)
# Works around the subshell issue with $NEW_COUNT — just count the result.
ADDED_TODAY=$(grep -c "| $DATE | .* | find-url |" "$CANDIDATES_FILE" 2>/dev/null || echo 0)
log "=== done. $ADDED_TODAY new candidate(s) added by find_url_scan. ==="
