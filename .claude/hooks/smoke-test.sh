#!/bin/bash
# Wookiee Workflow Guard — smoke test
# Verifies git-firewall.sh and fs-firewall.sh respond with deny to known bad input
set -uo pipefail
export PATH=/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin:$PATH

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
export CLAUDE_PROJECT_DIR="$PROJECT_DIR"

FAILED=0

check_deny() {
  local label="$1" hook="$2" input="$3"
  local out
  out=$(echo "$input" | bash "$PROJECT_DIR/.claude/hooks/$hook" 2>/dev/null)
  if echo "$out" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null 2>&1; then
    echo "PASS: $label"
  else
    echo "FAIL: $label — expected deny, got: $out"
    FAILED=$((FAILED+1))
  fi
}

check_allow() {
  local label="$1" hook="$2" input="$3"
  local out
  out=$(echo "$input" | bash "$PROJECT_DIR/.claude/hooks/$hook" 2>/dev/null)
  if echo "$out" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null 2>&1; then
    echo "FAIL: $label — expected allow, got deny: $out"
    FAILED=$((FAILED+1))
  else
    echo "PASS: $label"
  fi
}

# Force tests to think we're on main
TEST_CWD="$PROJECT_DIR"

check_deny "push to main blocked" "git-firewall.sh" \
  "$(jq -nc --arg cwd "$TEST_CWD" '{tool_input:{command:"git push origin main"}, cwd:$cwd}')"

check_deny "force push blocked" "git-firewall.sh" \
  "$(jq -nc --arg cwd "$TEST_CWD" '{tool_input:{command:"git push --force origin feature/foo"}, cwd:$cwd}')"

check_deny "settings edit blocked" "fs-firewall.sh" \
  "$(jq -nc --arg cwd "$TEST_CWD" --arg fp "$TEST_CWD/.claude/settings.json" '{tool_input:{file_path:$fp}, cwd:$cwd}')"

check_allow "git status allowed" "git-firewall.sh" \
  "$(jq -nc --arg cwd "$TEST_CWD" '{tool_input:{command:"git status"}, cwd:$cwd}')"

if [ "$FAILED" -gt 0 ]; then
  echo ""
  echo "SMOKE-TEST FAILED: $FAILED check(s) broke"
  mkdir -p "$PROJECT_DIR/.claude/logs"
  echo "[$(date -Iseconds)] smoke-test failed: $FAILED" >> "$PROJECT_DIR/.claude/logs/guard-smoke-FAILED.log"
  exit 1
fi

echo ""
echo "All smoke-tests passed."
exit 0
