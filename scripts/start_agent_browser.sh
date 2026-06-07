#!/bin/bash
# start_agent_browser.sh - Start the agent's isolated Chrome profile and fix up
# the DevToolsActivePort so web-access (and any other CDP client expecting the
# standard path) can find it.
#
# Why this script exists:
# web-access's check-deps reads DevToolsActivePort from the standard Chrome path
# (~/Library/Application Support/Google/Chrome/) — not the agent profile path
# (~/Library/Application Support/Google/Chrome-Agent/). When Chrome starts with
# --remote-debugging-port=9222 via command line, it opens the port but does NOT
# write DevToolsActivePort (that's only written when the chrome://inspect
# toggle is used). And even when it does write the file, it goes to the
# profile's own data dir, not the standard path.
#
# Result: web-access can't find the agent profile automatically. This script
# bridges the gap by:
#   1. Killing any existing Chrome on 9222
#   2. Launching agent Chrome with --user-data-dir=.../Chrome-Agent + --remote-debugging-port=9222
#   3. Querying /json/version on 9222 to get the actual browser wsPath
#   4. Writing a fresh DevToolsActivePort at the standard path with the real wsPath
#
# Usage:
#   ./scripts/start_agent_browser.sh [--no-launch]  # --no-launch = just fix the file
#
# Idempotent. Safe to re-run.

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AGENT_PROFILE_DIR="$HOME/Library/Application Support/Google/Chrome-Agent"
STANDARD_CHROME_DIR="$HOME/Library/Application Support/Google/Chrome"
DEBUG_PORT=9222
LOG="/tmp/agent_browser.log"

log() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG" >&2 ; }

LAUNCH=1
while [ $# -gt 0 ]; do
  case "$1" in
    --no-launch) LAUNCH=0 ;;
    *) log "unknown arg: $1"; exit 1 ;;
  esac
  shift
done

# Make sure profile dir exists
if [ ! -d "$AGENT_PROFILE_DIR" ]; then
  log "creating agent profile dir: $AGENT_PROFILE_DIR"
  mkdir -p "$AGENT_PROFILE_DIR"
fi

if [ "$LAUNCH" = "1" ]; then
  # Kill any Chrome holding the debug port
  EXISTING_PID=$(lsof -nP -iTCP:$DEBUG_PORT -sTCP:LISTEN -t 2>/dev/null || echo "")
  if [ -n "$EXISTING_PID" ]; then
    log "killing existing Chrome on port $DEBUG_PORT (PID $EXISTING_PID)"
    kill $EXISTING_PID 2>/dev/null || true
    sleep 2
    pkill -9 -f "Google Chrome" 2>/dev/null || true
    sleep 1
  fi

  # Also clear stale DevToolsActivePort from a prior (now-dead) Chrome at the standard path
  rm -f "$STANDARD_CHROME_DIR/DevToolsActivePort"

  # Launch agent Chrome
  log "launching agent Chrome (user-data-dir=$AGENT_PROFILE_DIR, port=$DEBUG_PORT)"
  open -na "/Applications/Google Chrome.app" --args \
    --user-data-dir="$AGENT_PROFILE_DIR" \
    --remote-debugging-port=$DEBUG_PORT \
    --no-first-run \
    --no-default-browser-check \
    --disable-background-mode

  # Wait for Chrome to bind the port
  log "waiting for Chrome to come up on $DEBUG_PORT..."
  for i in $(seq 1 20); do
    if lsof -nP -iTCP:$DEBUG_PORT -sTCP:LISTEN >/dev/null 2>&1; then
      log "Chrome is listening on $DEBUG_PORT (after ${i}s)"
      break
    fi
    sleep 1
  done

  if ! lsof -nP -iTCP:$DEBUG_PORT -sTCP:LISTEN >/dev/null 2>&1; then
    log "ERROR: Chrome did not bind $DEBUG_PORT within 20s"
    exit 1
  fi
fi

# Query the actual wsPath from the running Chrome
WS_PATH=$(curl -s "http://localhost:$DEBUG_PORT/json/version" \
  | python3 -c "import json,sys; print(json.loads(sys.stdin.read())['webSocketDebuggerUrl'].replace('ws://localhost:$DEBUG_PORT',''))" 2>/dev/null || echo "")

if [ -z "$WS_PATH" ]; then
  log "ERROR: could not query /json/version on port $DEBUG_PORT"
  exit 1
fi

log "actual wsPath: $WS_PATH"

# Write a fresh DevToolsActivePort at the standard Chrome path so check-deps
# (which only looks there) can find this agent profile.
printf "%s\n%s\n" "$DEBUG_PORT" "$WS_PATH" > "$STANDARD_CHROME_DIR/DevToolsActivePort"
log "wrote $STANDARD_CHROME_DIR/DevToolsActivePort"

# Restart cdp-proxy so it picks up the new state
pkill -f "cdp-proxy.mjs" 2>/dev/null || true
sleep 1

log "=== done. agent Chrome is ready for web-access. ==="
