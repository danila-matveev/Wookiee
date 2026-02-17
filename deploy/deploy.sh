#!/usr/bin/env bash
#
# deploy.sh — единая точка входа для деплоя Oleg (Agent + Bot)
#
# Использование:
#   cd deploy && bash deploy.sh          # стандартный деплой
#   cd deploy && bash deploy.sh --build  # принудительный rebuild образа
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"
CONTAINER_AGENT="wookiee_analytics_agent"
CONTAINER_BOT="wookiee_analytics_bot"
PID_FILE_BOT="$PROJECT_ROOT/agents/oleg/logs/oleg_bot.pid"
PID_FILE_AGENT="$PROJECT_ROOT/agents/oleg/logs/oleg_agent.pid"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log()   { echo -e "${GREEN}[deploy]${NC} $*"; }
warn()  { echo -e "${YELLOW}[deploy]${NC} $*"; }
error() { echo -e "${RED}[deploy]${NC} $*"; }

# ─── 1. Остановить старые контейнеры ─────────────────────────
log "Останавливаю старые контейнеры..."
if docker ps -q -f name="$CONTAINER_AGENT" -f name="$CONTAINER_BOT" | grep -q .; then
    docker-compose -f "$COMPOSE_FILE" down --timeout 30
    log "Контейнеры остановлены"
else
    log "Контейнеры не запущены, пропускаю"
fi

# ─── 2. Убить локальные процессы бота/агента ──────────────────
log "Проверяю локальные процессы..."
# Убиваем ОБА паттерна: agents.oleg И oleg_bot (старый процесс-призрак)
for pattern in "agents.oleg" "oleg_bot"; do
    if pgrep -f "$pattern" > /dev/null 2>&1; then
        warn "Найдены процессы '$pattern', завершаю..."
        pkill -f "$pattern" || true
        sleep 2
        if pgrep -f "$pattern" > /dev/null 2>&1; then
            warn "Процессы '$pattern' не завершились, принудительно убиваю..."
            pkill -9 -f "$pattern" || true
        fi
        log "Процессы '$pattern' завершены"
    fi
done

# ─── 3. Удалить stale PID-locks ──────────────────────────────
for pid_file in "$PID_FILE_BOT" "$PID_FILE_AGENT"; do
    if [ -f "$pid_file" ]; then
        warn "Удаляю stale PID-lock: $pid_file"
        rm -f "$pid_file"
    fi
done

# ─── 4. Проверить .env ───────────────────────────────────────
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    error "Файл .env не найден в $PROJECT_ROOT"
    exit 1
fi

# Проверяем обязательные переменные
for var in TELEGRAM_BOT_TOKEN OPENROUTER_API_KEY DB_HOST DB_PASSWORD; do
    if ! grep -q "^${var}=" "$PROJECT_ROOT/.env"; then
        error "Переменная $var не найдена в .env"
        exit 1
    fi
done
log "Конфигурация .env валидна"

# ─── 5. Собрать образ ────────────────────────────────────────
log "Собираю Docker-образ..."
docker-compose -f "$COMPOSE_FILE" build --no-cache
log "Образ собран"

# ─── 6. Запустить контейнеры ─────────────────────────────────
log "Запускаю контейнеры (agent + bot)..."
docker-compose -f "$COMPOSE_FILE" up -d
log "Контейнеры запущены"

# ─── 7. Ожидание и проверка ──────────────────────────────────
log "Жду 15 секунд для инициализации..."
sleep 15

# Проверяем что оба контейнера живы
for container in "$CONTAINER_AGENT" "$CONTAINER_BOT"; do
    if ! docker ps -q -f name="$container" | grep -q .; then
        error "Контейнер $container не запустился!"
        echo ""
        error "Последние логи:"
        docker-compose -f "$COMPOSE_FILE" logs --tail=30
        exit 1
    fi

    HEALTH=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "no-healthcheck")
    if [ "$HEALTH" = "healthy" ]; then
        log "$container — Healthcheck: HEALTHY"
    elif [ "$HEALTH" = "starting" ]; then
        warn "$container — Healthcheck: ещё стартует (start_period=60s)"
    elif [ "$HEALTH" = "unhealthy" ]; then
        error "$container — Healthcheck: UNHEALTHY!"
        docker inspect --format='{{range .State.Health.Log}}{{.Output}}{{end}}' "$container" 2>/dev/null
    fi
done

# ─── 8. Показать логи ────────────────────────────────────────
echo ""
log "Последние логи:"
echo "─────────────────────────────────────────"
docker-compose -f "$COMPOSE_FILE" logs --tail=20 --no-log-prefix
echo "─────────────────────────────────────────"

echo ""
log "Деплой завершён. Контейнеры: $CONTAINER_AGENT + $CONTAINER_BOT"
log "Логи: docker-compose -f $COMPOSE_FILE logs -f"
