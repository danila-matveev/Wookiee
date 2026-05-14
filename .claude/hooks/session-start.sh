#!/bin/bash
# Wookiee Workflow Guard — SessionStart hook
set -uo pipefail
: "${CLAUDE_PROJECT_DIR:=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
source "${CLAUDE_PROJECT_DIR}/.claude/hooks/guard-lib.sh"

INPUT="$(cat)"
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty')
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')
CWD="${CWD:-$CLAUDE_PROJECT_DIR}"

BRANCH=$(guard_current_branch "$CWD")
PID=$$

guard_prune_dead_sessions

# Write session registry entry
if [ -n "$SESSION_ID" ]; then
  jq -nc \
    --arg sid "$SESSION_ID" \
    --arg pid "$PPID" \
    --arg cwd "$CWD" \
    --arg branch "$BRANCH" \
    --arg started "$(date -Iseconds)" \
    '{session_id: $sid, pid: ($pid | tonumber), cwd: $cwd, branch: $branch, started_at: $started}' \
    > "$GUARD_REGISTRY/${SESSION_ID}.json" 2>/dev/null
fi

guard_log "session_start" "sid=$SESSION_ID pid=$PPID branch=$BRANCH cwd=$CWD"

# Inject context based on branch
if [ "$BRANCH" = "main" ]; then
  MSG="WOOKIEE-GUARD active: ты на ветке main. Это read-only режим. Все правки файлов и пуши в main блокируются хуками. Чтобы внести изменения — создай feature-ветку через git checkout -b или используй worktree. Команда /ship оформит PR с auto-merge."
elif [ -z "$BRANCH" ] || [ "$BRANCH" = "HEAD" ]; then
  MSG="WOOKIEE-GUARD active: ты в detached HEAD. Перед работой переключись на нормальную ветку."
else
  MSG="WOOKIEE-GUARD active: ты на ветке $BRANCH. Прямые пуши в main и правки .claude/settings* блокируются. Для слива в main — /ship (создаст PR с auto-merge)."
fi

guard_emit_session_context "$MSG"
