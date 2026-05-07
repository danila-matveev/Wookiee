# WB API keys cleanup — план

**Дата:** 2026-05-07
**Контекст:** в `.env` лежали 4 WB-токена (`WB_API_KEY_IP/OOO`, `WB_API_TOKEN_IP/OOO`). Реальная картина:
- `WB_API_KEY_IP == WB_API_KEY_OOO` — побайтная копия одного и того же ООО-токена (`s=1073823486`, ИНН 9729327530, бренд Wookiee, кабинет с wendy/ruby/audrey).
- `WB_API_TOKEN_IP` и `WB_API_TOKEN_OOO` (`s=1073757950`) — мертвы (401 на 10 разных scope), хотя exp 2026-08-12.

**Получен новый ИП-токен:** `s=1073823486, oid=105757`, `seller-info → ИП Медведева П.В., ИНН 771889257880`, в продажах vuki/moon, wendy=0. Проверки на live WB API пройдены.

---

## Что меняется

### `.env` (локально + позднее на сервере вручную)
- `WB_API_KEY_IP` ← **новый ИП-токен** (вместо старого ООО-дубля)
- `WB_API_KEY_OOO` ← без изменений
- `WB_API_TOKEN_IP` ← **удалить** (мёртвый, и compose теперь читает KEY_IP)
- `WB_API_TOKEN_OOO` ← **удалить** (мёртвый, и compose теперь читает KEY_OOO)

### `deploy/docker-compose.yml`
- `wb-mcp-ip.environment`: `WB_API_TOKEN=${WB_API_TOKEN_IP}` → `WB_API_TOKEN=${WB_API_KEY_IP}`
- `wb-mcp-ooo.environment`: `WB_API_TOKEN=${WB_API_TOKEN_OOO}` → `WB_API_TOKEN=${WB_API_KEY_OOO}`

### `scripts/server_predeploy_check.sh`
- Удалить `WB_API_TOKEN_IP` и `WB_API_TOKEN_OOO` из `REQUIRED_VARS` (строки 39-40).

### `.claude/commands/update-env.md`
- Таблица сервисов: `wb-mcp-ip` → только `WB_API_KEY_IP`; `wb-mcp-ooo` → только `WB_API_KEY_OOO`.

### Что **не трогаем**
- Python-код (`shared/data_layer/funnel_seo.py`, `services/sheets_sync/config.py`, `scripts/reviews_audit/collect_data.py`, `services/sheets_sync/sync/sync_promocodes.py`) — он уже читает `WB_API_KEY_*` корректно. После замены значения `WB_API_KEY_IP` начнёт впервые видеть реальный ИП-кабинет.
- `.env.example` — там уже только `WB_API_KEY_*`, без `_TOKEN_*`.
- Архивные документы в `docs/archive/`.

---

## Команда агентов

### Wave 1 (параллельно)

**Agent A — code-cleanup** (`general-purpose`):
Правит 3 файла: `deploy/docker-compose.yml`, `scripts/server_predeploy_check.sh`, `.claude/commands/update-env.md`. Без контакта с токеном.
После правок:
- `python3 -m compileall services scripts shared agents`
- `docker compose -f deploy/docker-compose.yml config -q` (синтаксис)
Возвращает: список изменённых файлов + статусы команд.

**Implementer (это Я, не агент):**
Правлю `.env` напрямую через `Edit`:
1. Заменить значение `WB_API_KEY_IP` на новый ИП-токен.
2. Удалить блок `WB_API_TOKEN_IP=...` (с комментарием).
3. Удалить блок `WB_API_TOKEN_OOO=...` (с комментарием).
Токен не передаётся в prompt субагента — он остаётся в текущем conversation context.

### Wave 2 (последовательно после Wave 1)

**Agent B — verifier** (`general-purpose`):
Проверки:
1. `grep -rn "WB_API_TOKEN_\(IP\|OOO\)"` — должно остаться **только** в `docs/archive/`.
2. `.env` содержит ровно `WB_API_KEY_IP` и `WB_API_KEY_OOO`, нет `WB_API_TOKEN_*`.
3. `deploy/docker-compose.yml` — `wb-mcp-ip` использует `${WB_API_KEY_IP}`, `wb-mcp-ooo` — `${WB_API_KEY_OOO}`.
4. `scripts/server_predeploy_check.sh` — `REQUIRED_VARS` без `WB_API_TOKEN_*`.
5. `python3 -m compileall services scripts shared agents` — без ошибок.
6. Smoke-import: `from services.sheets_sync.config import CABINET_IP, CABINET_OOO; assert CABINET_IP.wb_api_key != CABINET_OOO.wb_api_key`.
7. Live WB API: `seller-info` под `WB_API_KEY_IP` → `ИП Медведева П.В.` (ИНН `771889257880`), `seller-info` под `WB_API_KEY_OOO` → `ООО "ВУКИ"` (ИНН `9729327530`). Без логирования значений токенов.
Возвращает: PASS/FAIL по каждому пункту.

### Wave 3 — Я

- `git status` + `git diff` (без `.env` — он в `.gitignore`).
- Показать пользователю diff и попросить апрув.
- После апрува: `git add` (compose, predeploy, update-env.md) → `git commit` → **попросить апрув на push** (push в shared remote — risky action).

### Wave 4 — Деплой

**Порядок критичен** (иначе при autopull MCP-контейнеры стартанут с ООО-токеном вместо ИП):

1. **Сначала на сервере** (делает пользователь, не я):
   ```
   ssh timeweb
   nano /opt/wookiee/.env  # путь уточнить, обычно репо в /opt/<project>
   # — в WB_API_KEY_IP=... подменить значение на новый ИП-токен
   # — удалить строки WB_API_TOKEN_IP=... и WB_API_TOKEN_OOO=...
   ```
2. **Затем локально**: `git push origin main`.
3. autopull на сервере подтянет новый compose + predeploy_check.
4. Compose перезапустит `wb-mcp-ip` (теперь с настоящим ИП-токеном) и `wb-mcp-ooo` (с ООО-токеном).

---

## Rollback

Если что-то пошло не так:
1. На сервере: вернуть прежний `.env` (бэкап нужно сделать перед правкой: `cp .env .env.bak.20260507`).
2. Локально: `git revert <commit>` + push.

---

## Поведенческие следствия (важно для следующего запуска кронов)

После замены `WB_API_KEY_IP` следующие скрипты впервые увидят настоящий ИП-кабинет (раньше получали ООО-данные):
- `services/sheets_sync` (`CABINET_IP`)
- `shared/data_layer/funnel_seo.py` (limit=30 для IP)
- `scripts/reviews_audit/collect_data.py`
- `services/sheets_sync/sync/sync_promocodes.py`

→ В Sheets/funnel/reviews может скакнуть исторический ряд по ИП. Это разовая корректировка корректности данных, не баг.
