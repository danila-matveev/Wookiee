#!/usr/bin/env bash
#
# deploy_v2.sh — деплой Oleg v2 (единый контейнер)
#
# Использование:
#   bash deploy/deploy_v2.sh
#   make oleg2-deploy
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"
CONTAINER="wookiee_oleg_v2"
SERVICE="wookiee-oleg-v2"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()   { echo -e "${GREEN}[deploy-v2]${NC} $*"; }
warn()  { echo -e "${YELLOW}[deploy-v2]${NC} $*"; }
error() { echo -e "${RED}[deploy-v2]${NC} $*"; }

# ─── 1. Остановить старый контейнер ──────────────────────────
log "Останавливаю $CONTAINER..."
if docker ps -q -f name="$CONTAINER" | grep -q .; then
    docker compose -f "$COMPOSE_FILE" stop "$SERVICE"
    docker compose -f "$COMPOSE_FILE" rm -f "$SERVICE"
    log "Контейнер остановлен"
else
    log "Контейнер не запущен, пропускаю"
fi

# ─── 2. Проверить .env ───────────────────────────────────────
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    error "Файл .env не найден в $PROJECT_ROOT"
    exit 1
fi

for var in TELEGRAM_BOT_TOKEN OPENROUTER_API_KEY DB_HOST DB_PASSWORD; do
    if ! grep -q "^${var}=" "$PROJECT_ROOT/.env"; then
        error "Переменная $var не найдена в .env"
        exit 1
    fi
done
log "Конфигурация .env валидна"

# ─── 3. Собрать образ ────────────────────────────────────────
log "Собираю Docker-образ..."
docker compose -f "$COMPOSE_FILE" build "$SERVICE"
log "Образ собран"

# ─── 4. Запустить контейнер ──────────────────────────────────
log "Запускаю $SERVICE..."
docker compose -f "$COMPOSE_FILE" up -d "$SERVICE"
log "Контейнер запущен"

# ─── 5. Ожидание и проверка ──────────────────────────────────
log "Жду 10 секунд для инициализации..."
sleep 10

if ! docker ps -q -f name="$CONTAINER" | grep -q .; then
    error "Контейнер $CONTAINER не запустился!"
    echo ""
    error "Последние логи:"
    docker compose -f "$COMPOSE_FILE" logs --tail=30 "$SERVICE"
    exit 1
fi

# ─── 6. Показать логи ────────────────────────────────────────
echo ""
log "Последние логи:"
echo "─────────────────────────────────────────"
docker compose -f "$COMPOSE_FILE" logs --tail=20 --no-log-prefix "$SERVICE"
echo "─────────────────────────────────────────"

echo ""
log "Деплой завершён. Контейнер: $CONTAINER"
log "Логи: docker compose -f $COMPOSE_FILE logs -f $SERVICE"
