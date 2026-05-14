#!/bin/bash
# Wookiee Workflow Guard — PreToolUse(Edit|Write|MultiEdit) firewall
set -uo pipefail
: "${CLAUDE_PROJECT_DIR:=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
source "${CLAUDE_PROJECT_DIR}/.claude/hooks/guard-lib.sh"

INPUT="$(cat)"
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty')
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')
CWD="${CWD:-$CLAUDE_PROJECT_DIR}"

[ -z "$FILE_PATH" ] && exit 0

BRANCH=$(guard_current_branch "$CWD")

deny() {
  guard_log "fs-firewall-deny" "branch=$BRANCH file='$FILE_PATH' reason='$1'"
  guard_emit_deny "$1" "${2:-}"
  exit 0
}

# Block edits to settings/hooks themselves
case "$FILE_PATH" in
  */.claude/settings.json|*/.claude/settings.local.json|*/.claude/settings*.json)
    deny "правка .claude/settings.json через Claude запрещена" "только вручную в обычном редакторе (emergency rollback)"
    ;;
  */.claude/hooks/*|*/git-hooks/*)
    if [ "$BRANCH" = "main" ]; then
      deny "правка хук-файлов на main запрещена" "создай feature-ветку и PR"
    fi
    ;;
esac

# Block ALL writes when on main (read-only mode)
if [ "$BRANCH" = "main" ]; then
  # Allow writes outside project (e.g. /tmp scratch files)
  case "$FILE_PATH" in
    "$CWD"/*|"$CLAUDE_PROJECT_DIR"/*)
      deny "правка файлов на ветке main запрещена" "создай feature-ветку: git checkout -b feature/название"
      ;;
  esac
fi

exit 0
