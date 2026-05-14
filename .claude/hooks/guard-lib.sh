#!/bin/bash
# Wookiee Workflow Guard — shared library
export PATH=/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin:$PATH

GUARD_REGISTRY="${CLAUDE_PROJECT_DIR:-$PWD}/.claude/session-registry"
GUARD_LOGS="${CLAUDE_PROJECT_DIR:-$PWD}/.claude/logs"

mkdir -p "$GUARD_REGISTRY" "$GUARD_LOGS" 2>/dev/null

guard_log() {
  local event="$1"; shift
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $event: $*" >> "$GUARD_LOGS/guard.log"
}

guard_current_branch() {
  local cwd="${1:-$PWD}"
  git -C "$cwd" rev-parse --abbrev-ref HEAD 2>/dev/null
}

guard_emit_deny() {
  local reason="$1"
  local hint="${2:-}"
  jq -nc \
    --arg reason "$reason" \
    --arg hint "$hint" \
    '{
      hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny"},
      systemMessage: ("WOOKIEE-GUARD blocked: " + $reason + (if $hint != "" then "\nHint: " + $hint else "" end))
    }'
}

guard_emit_session_context() {
  local message="$1"
  jq -nc \
    --arg msg "$message" \
    '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $msg}}'
}

guard_prune_dead_sessions() {
  for f in "$GUARD_REGISTRY"/*.json; do
    [ -f "$f" ] || continue
    local pid
    pid=$(jq -r '.pid // empty' "$f" 2>/dev/null)
    [ -z "$pid" ] && continue
    if ! kill -0 "$pid" 2>/dev/null; then
      rm -f "$f"
    fi
  done
}
