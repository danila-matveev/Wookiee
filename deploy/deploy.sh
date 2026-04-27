#!/usr/bin/env bash
#
# deploy.sh — деплой Wookiee cron (единый контейнер)
#
# Использование:
#   bash deploy/deploy.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"
CONTAINER="wookiee_cron"
SERVICE="wookiee-cron"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()   { echo -e "${GREEN}[deploy]${NC} $*"; }
warn()  { echo -e "${YELLOW}[deploy]${NC} $*"; }
error() { echo -e "${RED}[deploy]${NC} $*"; }

# ─── 1. Остановить старый контейнер ───────────────────────
# Legacy cleanup: до refactor v3 PR #5 контейнер назывался wookiee_oleg.
# На уже задеплоенных хостах он может быть запущен — без явного удаления
# первый деплой оставит его рядом с новым wookiee_cron, и cron-задачи
# выполнятся дважды.
LEGACY_CONTAINER="wookiee_oleg"
if docker ps -aq -f name="^${LEGACY_CONTAINER}$" | grep -q .; then
    warn "Удаляю legacy-контейнер $LEGACY_CONTAINER (rename → $CONTAINER)..."
    docker stop "$LEGACY_CONTAINER" 2>/dev/null || true
    docker rm -f "$LEGACY_CONTAINER" 2>/dev/null || true
fi

log "Останавливаю $CONTAINER..."
if docker ps -q -f name="$CONTAINER" | grep -q .; then
    docker compose -f "$COMPOSE_FILE" stop "$SERVICE"
    docker compose -f "$COMPOSE_FILE" rm -f "$SERVICE"
    log "Контейнер остановлен"
else
    log "Контейнер не запущен, пропускаю"
fi

# ─── 2. Pre-deploy guard ───────────────────────────────────
PREDEPLOY="$PROJECT_ROOT/scripts/server_predeploy_check.sh"
if [ -x "$PREDEPLOY" ]; then
    log "Запускаю pre-deploy guard..."
    if ! REPO="$PROJECT_ROOT" "$PREDEPLOY"; then
        error "Pre-deploy guard упал. Деплой остановлен."
        exit 1
    fi
else
    warn "$PREDEPLOY не найден или не executable — пропускаю pre-deploy check"
fi

# ─── 3. Собрать образ ────────────────────────────────────
# Idempotent symlink на .env — wb-mcp-* и bitrix24-mcp в compose используют
# ${VAR} подстановку, которая требует .env в директории compose-файла.
[ -e "$SCRIPT_DIR/.env" ] || ln -sf ../.env "$SCRIPT_DIR/.env"

log "Собираю Docker-образ..."
docker compose -f "$COMPOSE_FILE" build "$SERVICE"
log "Образ собран"

# ─── 4. Запустить контейнер ──────────────────────────────
log "Запускаю $SERVICE..."
docker compose -f "$COMPOSE_FILE" up -d "$SERVICE"
log "Контейнер запущен"

# ─── 5. Ожидание и проверка ──────────────────────────────
log "Жду 10 секунд для инициализации..."
sleep 10

if ! docker ps -q -f name="$CONTAINER" | grep -q .; then
    error "Контейнер $CONTAINER не запустился!"
    echo ""
    error "Последние логи:"
    docker compose -f "$COMPOSE_FILE" logs --tail=30 "$SERVICE"
    exit 1
fi

# ─── 6. Показать логи ────────────────────────────────────
echo ""
log "Последние логи:"
echo "─────────────────────────────────────────"
docker compose -f "$COMPOSE_FILE" logs --tail=20 --no-log-prefix "$SERVICE"
echo "─────────────────────────────────────────"

echo ""
log "Деплой завершён. Контейнер: $CONTAINER"
log "Логи: docker compose -f $COMPOSE_FILE logs -f $SERVICE"
