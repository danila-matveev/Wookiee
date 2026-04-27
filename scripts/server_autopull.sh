#!/usr/bin/env bash
#
# server_autopull.sh — safety-net автосинхронизация app-сервера с origin/main.
#
# Запускается раз в 5 минут из crontab пользователя deploy. Если на сервере
# main отстал от origin/main, делает hard-reset и (при изменении deploy/-файлов)
# rebuild Docker-сервисов. При грязном working tree не делает ничего —
# только пишет в лог и шлёт Telegram alert.
#
# Это резервный механизм: основной авто-деплой делает GitHub Actions
# (.github/workflows/deploy.yml), но эта cron-job ловит случаи, когда GH Actions
# не сработал (отключён, force-push без CI, ручные правки на сервере).
#
# Установка:
#   crontab -e   # под пользователем deploy
#   */5 * * * * /home/danila/projects/wookiee/scripts/server_autopull.sh
#
set -euo pipefail

REPO=/home/danila/projects/wookiee
LOCK=/tmp/wookiee-autopull.lock
LOG_DIR="$REPO/logs/autopull"
LOG="$LOG_DIR/$(date -u +%Y-%m).log"
PREDEPLOY="$REPO/scripts/server_predeploy_check.sh"

mkdir -p "$LOG_DIR"

ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
log() { echo "$(ts) [autopull] $*" >> "$LOG"; }

# Telegram alert (опционально — если есть бот в .env)
alert() {
    local msg="$1"
    log "ALERT: $msg"
    if [ -f "$REPO/.env" ]; then
        # shellcheck disable=SC1091
        set +u
        TELEGRAM_BOT_TOKEN=$(grep -E "^TELEGRAM_BOT_TOKEN=" "$REPO/.env" | head -1 | cut -d= -f2- | tr -d '"' || true)
        TELEGRAM_ALERT_CHAT_ID=$(grep -E "^TELEGRAM_ALERT_CHAT_ID=" "$REPO/.env" | head -1 | cut -d= -f2- | tr -d '"' || true)
        set -u
        if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_ALERT_CHAT_ID:-}" ]; then
            curl -fsS --max-time 10 \
                -d "chat_id=${TELEGRAM_ALERT_CHAT_ID}" \
                -d "text=[wookiee autopull] ${msg}" \
                "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
                >> "$LOG" 2>&1 || log "telegram send failed"
        fi
    fi
}

# Не запускать параллельно (если предыдущий запуск ещё идёт)
exec 9>"$LOCK"
if ! flock -n 9; then
    log "another instance is running, skip"
    exit 0
fi

cd "$REPO"

# 1) Свежий fetch
if ! git fetch origin --quiet 2>>"$LOG"; then
    alert "git fetch failed (host=$(hostname))"
    exit 1
fi

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

# 2) Уже синхронизировано — выход
if [ "$LOCAL" = "$REMOTE" ]; then
    exit 0
fi

# 3) Грязный working tree — НЕ ресетим, шлём alert
if [ -n "$(git status --porcelain)" ]; then
    DIRTY_FILES=$(git status --porcelain | head -10 | sed 's/^/  /')
    alert "DIRTY working tree on host=$(hostname), drift detected (local=$LOCAL remote=$REMOTE). Manual investigation required. Files:
${DIRTY_FILES}"
    exit 2
fi

# 4) Чисто и есть drift — определяем, нужен ли rebuild docker-сервисов
CHANGED_FILES=$(git diff --name-only "$LOCAL" "$REMOTE")
NEED_REBUILD=0
if echo "$CHANGED_FILES" | grep -qE '^(deploy/|services/.*requirements|requirements)'; then
    NEED_REBUILD=1
fi

# 5) Pre-deploy check (валидация .env, скриптов, compose, python)
if [ -x "$PREDEPLOY" ]; then
    if ! "$PREDEPLOY" >> "$LOG" 2>&1; then
        alert "pre-deploy check FAILED before reset $LOCAL -> $REMOTE on host=$(hostname). Aborting autopull."
        exit 3
    fi
fi

# 6) Hard-reset на origin/main
if ! git reset --hard "$REMOTE" >> "$LOG" 2>&1; then
    alert "git reset --hard failed (local=$LOCAL remote=$REMOTE)"
    exit 4
fi
log "synced $LOCAL -> $REMOTE (rebuild=$NEED_REBUILD)"

# 7) Docker rebuild + restart, если затронут код контейнеров
if [ "$NEED_REBUILD" = "1" ]; then
    # Idempotent symlink — wb-mcp-* и bitrix24-mcp в compose используют ${VAR}
    # подстановку, которая требует .env в той же директории, что docker-compose.yml.
    [ -e "$REPO/deploy/.env" ] || ln -sf ../.env "$REPO/deploy/.env"
    if (cd "$REPO/deploy" && docker compose up -d --build --remove-orphans >> "$LOG" 2>&1); then
        log "docker compose up -d --build --remove-orphans done"
    else
        alert "docker compose up failed after sync $LOCAL -> $REMOTE on host=$(hostname). Containers may be in inconsistent state."
        exit 5
    fi
fi

exit 0
