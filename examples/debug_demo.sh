#!/usr/bin/env bash
set -euo pipefail

BASE_URL="http://localhost:8000/mcp"
DIR="$(cd "$(dirname "$0")" && pwd)"
LOG="$DIR/debug.log"
REQUESTS="$DIR/requests"

> "$LOG"

log() { echo "$@" | tee -a "$LOG"; }

post() {
  curl -s -D- -X POST "$BASE_URL" \
    -H 'Content-Type: application/json' \
    -H 'Accept: application/json, text/event-stream' \
    "$@"
}

parse_sse() { grep '^data:' | sed 's/^data: //' | python3 -m json.tool; }

log "============================================"
log "MCP Debugging Demo — $(date)"
log "============================================"
log ""

# --- Step 1: Initialize ---
log ">>> Step 1: Initialize session"
log "--- REQUEST ---"
cat "$REQUESTS/1_initialize.json" | tee -a "$LOG"
log ""
log "--- RESPONSE ---"

INIT=$(post -d @"$REQUESTS/1_initialize.json")
echo "$INIT" | tee -a "$LOG"
log ""

SESSION=$(echo "$INIT" | grep -i mcp-session-id | awk '{print $2}' | tr -d '\r')
log "    Session ID: $SESSION"
log ""

# --- Step 2: Confirm handshake ---
log ">>> Step 2: Confirm handshake (initialized notification)"
log "--- REQUEST ---"
cat "$REQUESTS/2_initialized.json" | tee -a "$LOG"
log ""
log "--- RESPONSE ---"

post -H "Mcp-Session-Id: $SESSION" \
  -d @"$REQUESTS/2_initialized.json" | tee -a "$LOG"
log ""
log ""

# --- Step 3: List tools ---
log ">>> Step 3: List available tools"
log "--- REQUEST ---"
cat "$REQUESTS/3_list_tools.json" | tee -a "$LOG"
log ""
log "--- RESPONSE ---"

TOOLS=$(post -H "Mcp-Session-Id: $SESSION" \
  -d @"$REQUESTS/3_list_tools.json")
echo "$TOOLS" | tee -a "$LOG"
log ""
log "--- PARSED ---"
echo "$TOOLS" | parse_sse | tee -a "$LOG"
log ""

# --- Step 4: Call tool ---
log ">>> Step 4: Call curl tool (fetch http://127.0.0.1:9000)"
log "--- REQUEST ---"
cat "$REQUESTS/4_call_tool.json" | tee -a "$LOG"
log ""
log "--- RESPONSE ---"

CALL=$(post -H "Mcp-Session-Id: $SESSION" \
  -d @"$REQUESTS/4_call_tool.json")
echo "$CALL" | tee -a "$LOG"
log ""
log "--- PARSED ---"
echo "$CALL" | parse_sse | tee -a "$LOG"
log ""

log "============================================"
log "Done. Full log: $LOG"
log "============================================"
