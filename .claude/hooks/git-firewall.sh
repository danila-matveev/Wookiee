#!/bin/bash
# Wookiee Workflow Guard — PreToolUse(Bash) firewall for git commands
set -uo pipefail
: "${CLAUDE_PROJECT_DIR:=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
source "${CLAUDE_PROJECT_DIR}/.claude/hooks/guard-lib.sh"

INPUT="$(cat)"
CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')
CWD="${CWD:-$CLAUDE_PROJECT_DIR}"

# Empty command — allow
[ -z "$CMD" ] && exit 0

BRANCH=$(guard_current_branch "$CWD")

deny() {
  guard_log "git-firewall-deny" "branch=$BRANCH cmd='$CMD' reason='$1'"
  guard_emit_deny "$1" "${2:-}"
  exit 0
}

# Block direct push to main
if echo "$CMD" | grep -qE 'git[[:space:]]+push[[:space:]]+.*[[:space:]](origin/?)?main([[:space:]]|$)'; then
  deny "прямой push в main запрещён" "оформи PR через /ship — GitHub смерджит сам когда CI зелёный"
fi
if echo "$CMD" | grep -qE 'git[[:space:]]+push[[:space:]]+.*HEAD:.*main'; then
  deny "push HEAD:main запрещён" "используй /ship для PR"
fi

# Block force push anywhere
if echo "$CMD" | grep -qE 'git[[:space:]]+push[[:space:]]+.*(--force([[:space:]]|=|$)|--force-with-lease|[[:space:]]-f([[:space:]]|$))'; then
  deny "force-push запрещён" "если действительно нужно — пользователь сделает руками из терминала"
fi

# Block dangerous ops on main
if [ "$BRANCH" = "main" ]; then
  if echo "$CMD" | grep -qE 'git[[:space:]]+(merge|rebase|reset[[:space:]]+--hard|cherry-pick)[[:space:]]'; then
    deny "git merge/rebase/reset --hard/cherry-pick на main запрещены" "переключись на feature-ветку"
  fi
  if echo "$CMD" | grep -qE 'git[[:space:]]+commit'; then
    deny "коммит прямо в main запрещён" "git checkout -b feature/... и работай там"
  fi
fi

# Block branch -D main / origin/main
if echo "$CMD" | grep -qE 'git[[:space:]]+branch[[:space:]]+-D[[:space:]]+(origin/)?main([[:space:]]|$)'; then
  deny "удаление ветки main запрещено"
fi

# Block edits to guard files via shell — only if path is DIRECT target of rm/mv/cp/sed -i or shell redirect
# (not just mentioned in heredoc body)
if echo "$CMD" | grep -qE '(\b(rm|mv|cp)[[:space:]]+(-[a-zA-Z]+[[:space:]]+)*|\bsed[[:space:]]+-i[[:space:]]+)[^|;&]*\.claude/(settings[^[:space:]/]*\.json|hooks/[^[:space:]/]+)'; then
  deny "изменение .claude/settings*.json или .claude/hooks/* через shell запрещено" "правки только через Edit-инструмент на feature-ветке"
fi
if echo "$CMD" | grep -qE '>[[:space:]]*\.claude/(settings[^[:space:]/]*\.json|hooks/[^[:space:]/]+)'; then
  deny "запись в .claude/settings*.json или .claude/hooks/* через shell-редирект запрещена"
fi
if echo "$CMD" | grep -qE '(\b(rm|mv|cp)[[:space:]]+(-[a-zA-Z]+[[:space:]]+)*|\bsed[[:space:]]+-i[[:space:]]+|>[[:space:]]*)git-hooks/[^[:space:]/]+'; then
  deny "изменение git-hooks/* через shell запрещено"
fi

# Block obfuscation attempts
if echo "$CMD" | grep -qE '(python3?[[:space:]]+-c|bash[[:space:]]+-c|eval[[:space:]]|base64[[:space:]]+-d|\$\(echo[[:space:]])'; then
  if echo "$CMD" | grep -qiE '(git[[:space:]]+push|git[[:space:]]+merge|git[[:space:]]+reset|\.claude/settings|hooks/)'; then
    deny "обход хуков через python/bash -c/eval/base64 запрещён"
  fi
fi

# rm -rf outside cwd
if echo "$CMD" | grep -qE 'rm[[:space:]]+(-rf?|-fr)[[:space:]]+/[^[:space:]]'; then
  # Allow rm -rf inside cwd, /tmp, or relative paths
  if ! echo "$CMD" | grep -qE 'rm[[:space:]]+-r?f?[[:space:]]+('"$CWD"'|/tmp|/private/tmp|/var/folders)'; then
    deny "rm -rf с абсолютным путём вне cwd/tmp запрещён"
  fi
fi

# All other git commands — allow
exit 0
