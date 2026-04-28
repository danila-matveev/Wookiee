#!/usr/bin/env bash
#
# sync_env_to_server.sh — синхронизация локального .env с продакшен-сервером.
#
# Workflow:
#   1. Редактируешь локально:    nano /Users/.../Wookiee/.env
#   2. Запускаешь:                bash scripts/sync_env_to_server.sh
#   3. Скрипт показывает diff (только имена переменных — значения не печатаются),
#      просит подтверждение, делает бэкап на сервере и заливает.
#
# По умолчанию направление одностороннее: локальный → сервер. Серверный .env
# считается «зеркалом» локального; всё, что осталось только на сервере, будет
# удалено. Для двусторонней синхронизации используй ../scripts/migrate-setup.
#
# Опции:
#   --dry-run      показать diff и выйти, без записи
#   --force        пропустить интерактивное подтверждение (для CI)
#   --no-validate  не запускать predeploy guard на сервере после синка
#
set -euo pipefail

# ── Пути ────────────────────────────────────────────────────────────────────
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOCAL_ENV="$PROJECT_ROOT/.env"
SERVER_HOST="${WOOKIEE_SSH_HOST:-timeweb}"
SERVER_PATH="/home/danila/projects/wookiee/.env"
TMP_SERVER=$(mktemp /tmp/sync_env.XXXXXX)
trap 'rm -f "$TMP_SERVER"' EXIT

# ── Флаги ──────────────────────────────────────────────────────────────────
DRY_RUN=0
FORCE=0
NO_VALIDATE=0
for arg in "$@"; do
    case "$arg" in
        --dry-run)     DRY_RUN=1 ;;
        --force)       FORCE=1 ;;
        --no-validate) NO_VALIDATE=1 ;;
        -h|--help)
            sed -n '3,25p' "$0"
            exit 0
            ;;
        *) echo "Unknown arg: $arg" >&2; exit 1 ;;
    esac
done

# ── Цвета ──────────────────────────────────────────────────────────────────
if [ -t 1 ]; then
    GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
else
    GREEN=''; YELLOW=''; RED=''; NC=''
fi

# ── 1. Sanity ──────────────────────────────────────────────────────────────
if [ ! -f "$LOCAL_ENV" ]; then
    echo -e "${RED}ERROR: локальный .env не найден: $LOCAL_ENV${NC}" >&2
    exit 1
fi
if [ ! -s "$LOCAL_ENV" ]; then
    echo -e "${RED}ERROR: локальный .env пустой${NC}" >&2
    exit 1
fi

# ── 2. Стянуть серверный .env во временный файл ─────────────────────────────
echo -e "${GREEN}[1/5]${NC} Читаю серверный .env с $SERVER_HOST..."
if ! ssh -o ConnectTimeout=10 "$SERVER_HOST" "cat $SERVER_PATH" > "$TMP_SERVER" 2>/dev/null; then
    echo -e "${RED}ERROR: не удалось прочитать $SERVER_PATH через ssh $SERVER_HOST${NC}" >&2
    exit 2
fi

# ── 3. Diff на уровне имён ─────────────────────────────────────────────────
echo -e "${GREEN}[2/5]${NC} Сравниваю переменные..."
DIFF_RC=0
python3 - "$LOCAL_ENV" "$TMP_SERVER" <<'PYEOF' || DIFF_RC=$?
import sys
def parse(path):
    out = {}
    with open(path) as f:
        for line in f:
            s = line.strip()
            if s and not s.startswith('#') and '=' in s:
                k, v = s.split('=', 1)
                out[k] = v
    return out
local = parse(sys.argv[1])
server = parse(sys.argv[2])
added = sorted(set(local) - set(server))
removed = sorted(set(server) - set(local))
val_diffs = sorted(k for k in (set(local) & set(server)) if local[k] != server[k])
total = len(added) + len(removed) + len(val_diffs)
if total == 0:
    print('  ✓ Локальный и серверный .env уже идентичны. Делать нечего.')
    sys.exit(2)
print(f'  Добавятся на сервер ({len(added)}):')
for k in added: print(f'    + {k}')
print(f'  Удалятся с сервера ({len(removed)}):')
for k in removed: print(f'    - {k}')
print(f'  Перезапишутся значения ({len(val_diffs)}):')
for k in val_diffs: print(f'    ~ {k}')
sys.exit(0)
PYEOF
if [ "$DIFF_RC" = "2" ]; then
    exit 0
fi
if [ "$DIFF_RC" != "0" ]; then
    echo -e "${RED}ERROR: ошибка при diff (rc=$DIFF_RC)${NC}" >&2
    exit 3
fi

# ── 4. Dry-run или подтверждение ───────────────────────────────────────────
if [ "$DRY_RUN" = "1" ]; then
    echo -e "${YELLOW}--dry-run: завершено без записи.${NC}"
    exit 0
fi

if [ "$FORCE" = "0" ]; then
    echo ""
    echo -ne "${YELLOW}Залить локальный .env на сервер? [y/N] ${NC}"
    read -r ANSWER
    case "${ANSWER:-N}" in
        y|Y|yes|Yes|YES) ;;
        *)
            echo "Отменено."
            exit 0
            ;;
    esac
fi

# ── 5. Бэкап на сервере + scp ──────────────────────────────────────────────
TS=$(date -u +%Y%m%d-%H%M%S)
echo -e "${GREEN}[3/5]${NC} Бэкап серверного .env: ${SERVER_PATH}.bak.$TS"
ssh "$SERVER_HOST" "cp $SERVER_PATH ${SERVER_PATH}.bak.$TS"

echo -e "${GREEN}[4/5]${NC} Заливаю локальный .env на сервер..."
scp -q "$LOCAL_ENV" "$SERVER_HOST:$SERVER_PATH"

# Сверить byte-identity
ssh "$SERVER_HOST" "cat $SERVER_PATH" > "$TMP_SERVER"
if cmp -s "$LOCAL_ENV" "$TMP_SERVER"; then
    echo "  ✓ Файлы byte-identical."
else
    echo -e "${RED}WARNING: после синка файлы различаются!${NC}" >&2
    diff "$LOCAL_ENV" "$TMP_SERVER" | head -20 >&2
    exit 4
fi

# ── 6. Validate ────────────────────────────────────────────────────────────
if [ "$NO_VALIDATE" = "0" ]; then
    echo -e "${GREEN}[5/5]${NC} Запускаю predeploy guard и compose validation на сервере..."
    if ssh "$SERVER_HOST" 'cd /home/danila/projects/wookiee/deploy && docker compose config -q 2>&1 | grep -E "warning|error" | head -3; /home/danila/projects/wookiee/scripts/server_predeploy_check.sh 2>&1 | tail -3'; then
        echo "  ✓ Validation passed."
    else
        echo -e "${YELLOW}WARN: validation вернула non-zero — посмотри вывод выше.${NC}"
    fi
fi

# ── Финал ──────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}✓ Синхронизация завершена.${NC}"
echo "  Бэкап на сервере: ${SERVER_PATH}.bak.$TS"
echo ""
echo -e "${YELLOW}Если ты менял значения, которые читают running контейнеры —${NC}"
echo "  пересоздай их (контейнер читает .env только при старте):"
echo ""
echo "    ssh $SERVER_HOST 'cd /home/danila/projects/wookiee/deploy && \\"
echo "      docker compose up -d --force-recreate <имя-сервиса>'"
echo ""
echo "  Сервисы: wookiee-cron, sheets-sync, wb-mcp-ip, wb-mcp-ooo, bitrix24-mcp, wb-logistics-api"
