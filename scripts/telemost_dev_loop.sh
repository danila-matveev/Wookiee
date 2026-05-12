#!/usr/bin/env bash
# Dev-loop rig: restart the recorder against the same meeting every N seconds.
# Use when iterating on DM rendering / handlers without burning real meetings.
#
# Required env:
#   TELEMOST_API=http://localhost:8006         # or ssh tunnel
#   TELEMOST_API_TOKEN=...                     # X-API-Key if API enforces it
#   MEETING_URL=https://telemost.360.yandex.ru/j/...
#   TRIGGERED_BY=111111111                     # telegram_id of the test user
# Optional:
#   INTERVAL_SECONDS=300                       # default 5 min
#   MAX_ITER=100                               # default unlimited (0)
set -euo pipefail

: "${TELEMOST_API:?TELEMOST_API is required}"
: "${MEETING_URL:?MEETING_URL is required}"
: "${TRIGGERED_BY:?TRIGGERED_BY is required}"
INTERVAL="${INTERVAL_SECONDS:-300}"
MAX="${MAX_ITER:-0}"
HEADERS=()
if [[ -n "${TELEMOST_API_TOKEN:-}" ]]; then
  HEADERS=(-H "X-API-Key: ${TELEMOST_API_TOKEN}")
fi

i=0
while :; do
  i=$((i+1))
  echo "[$(date -Iseconds)] iter $i — enqueueing $MEETING_URL"
  curl -sS -X POST "$TELEMOST_API/internal/spawn_recorder" \
    "${HEADERS[@]}" \
    -H 'Content-Type: application/json' \
    -d "{\"meeting_url\":\"$MEETING_URL\",\"triggered_by\":$TRIGGERED_BY}" \
    || echo "  spawn failed"
  if [[ "$MAX" != "0" && "$i" -ge "$MAX" ]]; then
    echo "[$(date -Iseconds)] reached MAX_ITER=$MAX, stop"
    exit 0
  fi
  echo "[$(date -Iseconds)] sleeping ${INTERVAL}s..."
  sleep "$INTERVAL"
done
