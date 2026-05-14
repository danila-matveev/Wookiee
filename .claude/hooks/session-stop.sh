#!/bin/bash
# Wookiee Workflow Guard — Stop hook
set -uo pipefail
: "${CLAUDE_PROJECT_DIR:=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
source "${CLAUDE_PROJECT_DIR}/.claude/hooks/guard-lib.sh"

INPUT="$(cat)"
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty')

if [ -n "$SESSION_ID" ]; then
  rm -f "$GUARD_REGISTRY/${SESSION_ID}.json" 2>/dev/null
  guard_log "session_stop" "sid=$SESSION_ID"
fi

exit 0
