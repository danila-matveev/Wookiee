#!/usr/bin/env bash
# Companion frontend: services/influencer_crm_ui/scripts/run_dev.sh (port 5173)
# Local dev runner. Reads .env, picks port 8082 (collisionless with marketplace ETL on 8081).
set -euo pipefail
cd "$(dirname "$0")/../../.."  # repo root
exec .venv/bin/uvicorn services.influencer_crm.app:app \
    --reload --host 127.0.0.1 --port 8082 \
    --log-level info
