#!/usr/bin/env bash
#
# server_predeploy_check.sh — pre-deploy guard для app-сервера.
#
# Проверяет, что репозиторий пригоден для `docker compose up -d`. Запускается:
#   - server_autopull.sh перед `git reset --hard` + rebuild
#   - вручную из CI или GH Actions deploy.yml
#   - руками перед `bash deploy/deploy.sh`
#
# Возвращает exit code 0 если всё ок, иначе — non-zero и пишет ошибки в stderr.
#
set -euo pipefail

REPO="${REPO:-/home/danila/projects/wookiee}"
ENV_FILE="$REPO/.env"
ENV_EXAMPLE="$REPO/.env.example"
COMPOSE_FILE="$REPO/deploy/docker-compose.yml"

ERRORS=0

err() { echo "[predeploy] ERROR: $*" >&2; ERRORS=$((ERRORS+1)); }
ok()  { echo "[predeploy] OK: $*"; }

# 1) .env существует и не пустой
if [ ! -f "$ENV_FILE" ]; then
    err ".env not found at $ENV_FILE"
elif [ ! -s "$ENV_FILE" ]; then
    err ".env is empty"
else
    ok ".env exists ($(wc -c < "$ENV_FILE") bytes)"
fi

# 2) Required vars в .env (минимальный набор для compose-сервисов)
REQUIRED_VARS=(
    TELEGRAM_BOT_TOKEN
    OPENROUTER_API_KEY
    DB_HOST
    DB_PASSWORD
    WB_API_TOKEN_IP
    WB_API_TOKEN_OOO
    BITRIX24_WEBHOOK_URL
)
if [ -f "$ENV_FILE" ]; then
    for var in "${REQUIRED_VARS[@]}"; do
        if ! grep -qE "^${var}=" "$ENV_FILE"; then
            err ".env missing required var: $var"
        fi
    done
    [ "$ERRORS" = "0" ] && ok "all required .env vars present"
fi

# 3) Compose syntax валиден
if [ -f "$COMPOSE_FILE" ]; then
    if (cd "$REPO/deploy" && docker compose config -q 2>&1); then
        ok "docker-compose.yml syntax valid"
    else
        err "docker-compose.yml syntax check failed"
    fi
else
    err "compose file not found at $COMPOSE_FILE"
fi

# 4) Скрипты, на которые ссылаются compose Cmd / cron — существуют
SCRIPTS_REFERENCED=(
    scripts/sync_sheets_to_supabase.py
    scripts/run_search_queries_sync.py
    services/logistics_audit/etl/cron_tariff_collector.sh
)
for s in "${SCRIPTS_REFERENCED[@]}"; do
    if [ ! -f "$REPO/$s" ]; then
        err "missing referenced script: $s"
    fi
done
[ "$ERRORS" = "0" ] && ok "all referenced scripts present"

# 5) Python compileall — синтаксис исходников валиден
if command -v python3 >/dev/null; then
    if (cd "$REPO" && python3 -m compileall -q services scripts shared agents 2>&1 >/dev/null); then
        ok "python compileall passed"
    else
        err "python compileall failed — syntax error in source"
    fi
fi

# 6) Working tree clean (если запускаем из autopull, working tree уже clean,
#    но при ручном запуске может быть грязным — это сигнал)
if [ -d "$REPO/.git" ]; then
    DIRTY=$(cd "$REPO" && git status --porcelain | head -5)
    if [ -n "$DIRTY" ]; then
        echo "[predeploy] WARN: dirty working tree:" >&2
        echo "$DIRTY" | sed 's/^/  /' >&2
        # Не считаем ошибкой — pre-deploy guard может вызываться и до commit-а в CI
    fi
fi

if [ "$ERRORS" = "0" ]; then
    echo "[predeploy] PASSED ($(date -u +%Y-%m-%dT%H:%M:%SZ))"
    exit 0
else
    echo "[predeploy] FAILED with $ERRORS error(s)" >&2
    exit 1
fi
