#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/home/danila/projects/wookiee"
LOG_DIR="$PROJECT_DIR/logs/wb_tariffs"

mkdir -p "$LOG_DIR"

cd "$PROJECT_DIR"

if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
elif [[ -f "venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "venv/bin/activate"
fi

LOG_FILE="$LOG_DIR/$(date +%F).log"

export WOOKIEE_ENV="${WOOKIEE_ENV:-prod}"

{
  echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] Starting wb_tariffs daily collection"
  python -m services.logistics_audit.etl.tariff_collector --cabinet OOO --trigger cron
  echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] Finished wb_tariffs daily collection"
} >>"$LOG_FILE" 2>&1
