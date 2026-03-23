#!/usr/bin/env bash
#
# deploy-v3-migration.sh — полный деплой V2→V3 миграции
#
# Выполняет:
#   1. Добавляет swap 4 ГБ (если ещё нет)
#   2. Останавливает oleg-mcp (V2)
#   3. Пересобирает и перезапускает wookiee-oleg (V3)
#   4. Перезапускает eggent с новыми лимитами
#   5. Запускает пропущенные weekly отчёты
#
# Использование:
#   ssh timeweb
#   cd /opt/wookiee
#   git pull
#   bash deploy/deploy-v3-migration.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()   { echo -e "${GREEN}[v3-migration]${NC} $*"; }
warn()  { echo -e "${YELLOW}[v3-migration]${NC} $*"; }
error() { echo -e "${RED}[v3-migration]${NC} $*"; }

# ─── 0. Проверка что мы на сервере ─────────────────────────
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    error "Файл .env не найден. Запускайте из /opt/wookiee"
    exit 1
fi

# ─── 1. Swap 4 ГБ ──────────────────────────────────────────
log "Проверяю swap..."
SWAP_SIZE=$(free -g | awk '/Swap/{print $2}')
if [ "$SWAP_SIZE" -lt 2 ]; then
    log "Swap недостаточен ($SWAP_SIZE ГБ). Создаю 4 ГБ..."
    sudo fallocate -l 4G /swapfile 2>/dev/null || sudo dd if=/dev/zero of=/swapfile bs=1G count=4
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    if ! grep -q '/swapfile' /etc/fstab; then
        echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    fi
    log "Swap создан и активирован"
else
    log "Swap уже достаточен ($SWAP_SIZE ГБ), пропускаю"
fi
free -h | head -3

# ─── 2. Остановить oleg-mcp (V2) ──────────────────────────
log "Останавливаю oleg-mcp (V2)..."
if docker ps -q -f name=oleg_mcp | grep -q .; then
    docker stop oleg_mcp
    docker rm -f oleg_mcp
    log "oleg-mcp остановлен и удалён"
else
    log "oleg-mcp уже не запущен"
fi

# ─── 3. Пересобрать и перезапустить wookiee-oleg (V3) ─────
log "Пересобираю wookiee-oleg..."
docker compose -f "$COMPOSE_FILE" build wookiee-oleg
docker compose -f "$COMPOSE_FILE" stop wookiee-oleg || true
docker compose -f "$COMPOSE_FILE" rm -f wookiee-oleg || true
docker compose -f "$COMPOSE_FILE" up -d wookiee-oleg
log "wookiee-oleg запущен"

# ─── 4. Перезапустить eggent с новыми лимитами ────────────
log "Перезапускаю eggent с лимитом 512 МБ..."
docker compose -f "$COMPOSE_FILE" up -d eggent
log "eggent перезапущен"

# ─── 5. Ожидание и проверка ────────────────────────────────
log "Жду 15 секунд для инициализации..."
sleep 15

echo ""
log "Статус контейнеров:"
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.CPUPerc}}" \
    wookiee_oleg eggent 2>/dev/null || docker ps --format "table {{.Names}}\t{{.Status}}" | head -10

echo ""
log "Последние логи wookiee-oleg:"
echo "─────────────────────────────────────────"
docker compose -f "$COMPOSE_FILE" logs --tail=20 --no-log-prefix wookiee-oleg
echo "─────────────────────────────────────────"

# ─── 6. Запуск пропущенных weekly отчётов ──────────────────
echo ""
read -p "Запустить пропущенные weekly отчёты за 16-22 марта? [y/N] " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    log "Запускаю пропущенные отчёты..."
    docker compose -f "$COMPOSE_FILE" exec wookiee-oleg python -c "
import asyncio
from agents.v3 import orchestrator

async def main():
    # Weekly financial
    print('Запуск weekly report...')
    r = await orchestrator.run_weekly_report(
        '2026-03-16', '2026-03-22', '2026-03-09', '2026-03-15',
        trigger='manual_catchup')
    print(f'weekly: {r.get(\"status\")}')

    # Weekly marketing
    print('Запуск marketing weekly...')
    r = await orchestrator.run_marketing_report(
        '2026-03-16', '2026-03-22', '2026-03-09', '2026-03-15',
        report_period='weekly', trigger='manual_catchup')
    print(f'marketing_weekly: {r.get(\"status\")}')

    # Funnel weekly
    print('Запуск funnel weekly...')
    r = await orchestrator.run_funnel_report(
        '2026-03-16', '2026-03-22', '2026-03-09', '2026-03-15',
        trigger='manual_catchup')
    print(f'funnel_weekly: {r.get(\"status\")}')

asyncio.run(main())
"
    log "Пропущенные отчёты запущены"
else
    log "Пропущенные отчёты пропущены. Можете запустить позже через /report_weekly в Telegram"
fi

echo ""
log "V3 миграция завершена!"
log ""
log "Следующие шаги:"
log "  1. Проверьте отчёты в Notion"
log "  2. Отправьте /health в Telegram-бот"
log "  3. Мониторьте логи: docker compose -f $COMPOSE_FILE logs -f wookiee-oleg"
