#!/usr/bin/env bash
#
# deploy.sh — единая точка входа для деплоя Oleg Bot
#
# Использование:
#   cd deploy && bash deploy.sh          # стандартный деплой
#   cd deploy && bash deploy.sh --build  # принудительный rebuild образа
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"
CONTAINER_NAME="wookiee_analytics_bot"
PID_FILE="$PROJECT_ROOT/agents/oleg/logs/oleg_bot.pid"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log()   { echo -e "${GREEN}[deploy]${NC} $*"; }
warn()  { echo -e "${YELLOW}[deploy]${NC} $*"; }
error() { echo -e "${RED}[deploy]${NC} $*"; }

# ─── 1. Остановить старый контейнер ──────────────────────────
log "Останавливаю старый контейнер..."
if docker ps -q -f name="$CONTAINER_NAME" | grep -q .; then
    docker-compose -f "$COMPOSE_FILE" down --timeout 30
    log "Контейнер остановлен"
else
    log "Контейнер не запущен, пропускаю"
fi

# ─── 2. Убить локальные процессы бота ────────────────────────
log "Проверяю локальные процессы бота..."
if pgrep -f "agents.oleg" > /dev/null 2>&1; then
    warn "Найдены локальные процессы бота, завершаю..."
    pkill -f "agents.oleg" || true
    sleep 2
    # Если не завершились — SIGKILL
    if pgrep -f "agents.oleg" > /dev/null 2>&1; then
        warn "Процессы не завершились, принудительно убиваю..."
        pkill -9 -f "agents.oleg" || true
    fi
    log "Локальные процессы завершены"
else
    log "Локальных процессов нет"
fi

# ─── 3. Удалить stale PID-lock ──────────────────────────────
if [ -f "$PID_FILE" ]; then
    warn "Удаляю stale PID-lock: $PID_FILE"
    rm -f "$PID_FILE"
fi

# ─── 4. Проверить .env ──────────────────────────────────────
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    error "Файл .env не найден в $PROJECT_ROOT"
    exit 1
fi

# Проверяем обязательные переменные
for var in TELEGRAM_BOT_TOKEN ZAI_API_KEY DB_HOST DB_PASSWORD; do
    if ! grep -q "^${var}=" "$PROJECT_ROOT/.env"; then
        error "Переменная $var не найдена в .env"
        exit 1
    fi
done
log "Конфигурация .env валидна"

# ─── 5. Собрать образ ───────────────────────────────────────
log "Собираю Docker-образ..."
docker-compose -f "$COMPOSE_FILE" build --no-cache
log "Образ собран"

# ─── 6. Запустить контейнер ──────────────────────────────────
log "Запускаю контейнер..."
docker-compose -f "$COMPOSE_FILE" up -d
log "Контейнер запущен"

# ─── 7. Ожидание и проверка ──────────────────────────────────
log "Жду 15 секунд для инициализации..."
sleep 15

# Проверяем что контейнер жив
if ! docker ps -q -f name="$CONTAINER_NAME" | grep -q .; then
    error "Контейнер не запустился!"
    echo ""
    error "Последние логи:"
    docker-compose -f "$COMPOSE_FILE" logs --tail=30
    exit 1
fi

# Проверяем healthcheck (если доступен)
HEALTH=$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER_NAME" 2>/dev/null || echo "no-healthcheck")
if [ "$HEALTH" = "healthy" ]; then
    log "Healthcheck: HEALTHY"
elif [ "$HEALTH" = "starting" ]; then
    warn "Healthcheck: ещё стартует (start_period=40s). Проверьте через 30 сек"
elif [ "$HEALTH" = "unhealthy" ]; then
    error "Healthcheck: UNHEALTHY!"
    docker inspect --format='{{range .State.Health.Log}}{{.Output}}{{end}}' "$CONTAINER_NAME" 2>/dev/null
fi

# ─── 8. Показать логи ───────────────────────────────────────
echo ""
log "Последние логи:"
echo "─────────────────────────────────────────"
docker-compose -f "$COMPOSE_FILE" logs --tail=20 --no-log-prefix
echo "─────────────────────────────────────────"

echo ""
log "Деплой завершён. Контейнер: $CONTAINER_NAME"
log "Логи: docker-compose -f $COMPOSE_FILE logs -f"
