# Hub → Google Sheets Sync — QA Plan

> **Назначение:** этот документ — инструкция оркестратора для финальной проверки зеркала Hub → Sheets, поставленного PR #137 (squash commit `8ae265fb`). Документ самодостаточен — orchestrator-агент в новом контекстном окне читает только этот файл и стартует.
>
> **Автор:** Claude (Opus 4.7), 2026-05-15, после консультации трёх параллельных subagent'ов.
>
> **Версия:** 1.0 (2026-05-15)

---

## 0. Контекст для нового окна

### Что было сделано в PR #137
- 6 Postgres views в `database/migrations/030_catalog_export_views.sql` (vw_export_modeli/_artikuly/_tovary/_cveta/_skleyki_wb/_skleyki_ozon)
- Python-пакет `services/sheets_sync/hub_to_sheets/` (config, anchor, diff, batch, runner, exporter)
- API-эндпоинт `services/analytics_api/catalog_sync.py` (POST/GET `/api/catalog/sync-mirror`)
- Hub-кнопка `wookiee-hub/src/components/catalog/sync-mirror-button.tsx` на 9 каталог-страницах
- Зеркальная Google-таблица `1qqcCmg-Xagike1G3F3TdBihEDFF6mMLiDiZPXXWR7ls` (далее — "PROD MIRROR")
- Запись в реестре: `tools.slug='catalog-sheets-mirror'`

### Известные проблемы перед QA
1. **Огромные строки в листе «Все модели»:** 30 ячеек колонки «Описание для сайта» содержат `\n`, Sheets рендерит каждый перенос как soft line break → высота строки ~600 px. Источник — `modeli_osnova.opisanie_sayt` (правится вручную в Hub, имеет абзацы). Лечится в `exporter.py:_to_cell`. Это **Фаза 1** этого плана.
2. **Визуальное несоответствие зеркала и основной таблицы** (88 vs 47 колонок по моделям, нет цветной шапки). Это by design — главная содержит аналитику/решения/недельные снимки, зеркало = только источник правды Hub. Косметика (цветные шапки в стиле main) **вынесена за рамки этой QA**, делается отдельным PR после.

### Жёсткие ограничения
- ❌ **Не трогать prod-БД** (никаких UPDATE/DELETE/INSERT в `public.modeli`, `public.artikuly`, `public.tovary`, `public.modeli_color_codes`, `public.skleyki_wb`, `public.skleyki_ozon`). Все мутации — только в schema `test_catalog_sync.*`, созданной в Фазе 2.
- ❌ **Не трогать прод-зеркало** через мутации. На PROD MIRROR — только read-only проверки (Фаза 3). Все жёсткие тесты с записью — на TEST MIRROR (Фаза 2).
- ❌ **Не пушить в main**. Все коммиты идут в feature-ветки, мерджатся через PR.
- ❌ **Не делать косметику** (цветные шапки, ренеймы Lamoda→Ламода, расширение views) — это отдельная задача после QA.

### Целевой результат
- Файл `wookiee-hub/.planning/hub-to-sheets-sync/QA-LOG.md` с журналом каждого теста + результатом (PASS/FAIL/SKIP), evidence (SQL-выводы, кол-ва, скриншоты).
- Если все 20 тестов PASS → выходной критерий: 7 дней без багов в работе (соответствует исходному заданию).
- Если есть FAIL → багами заводятся отдельные коммиты-фиксы в той же ветке `qa/hub-to-sheets-sync`, перепроверка, потом PR.

---

## 1. Архитектура оркестрации

Orchestrator-агент (Claude в новом окне) исполняет **5 фаз последовательно**. Внутри фазы можно дёргать subagent'ы параллельно. Перед началом каждой фазы — TodoWrite. После каждой фазы — verification gate (если провален → STOP и спросить пользователя).

```
ФАЗА 1 (sequential, ~30 мин)
  ↓ commit + PR + merge
ФАЗА 2 (sequential, ~20 мин)
  ↓ test mirror sheet + test schema + .env override
ФАЗА 3 (parallel 4 agents, ~15 мин)
  Agent 3A: Hub UI tests (Playwright × 9 страниц)
  Agent 3B: Auth + endpoint tests (curl × 5)
  Agent 3C: Data integrity (gspread + psycopg2 для 6 листов)
  Agent 3D: Idempotency + status endpoint
  ↓ aggregate → QA-LOG.md секция Phase 3
ФАЗА 4 (sequential, ~60 мин, 12 тестов)
  Setup → T9..T20 → Teardown
  ↓ aggregate → QA-LOG.md секция Phase 4
ФАЗА 5 (sequential, ~10 мин)
  Final report + summary + decide PR or fixes
```

Если subagent возвращает FAIL → orchestrator останавливает фазу и записывает в QA-LOG.md. Не идёт дальше без явного разрешения пользователя.

---

## 2. Подготовка окружения (Phase 0, ~5 мин)

**Перед стартом orchestrator:**

```bash
# Убедиться что мы на чистой ветке qa/hub-to-sheets-sync на свежем main
cd /Users/danilamatveev/Projects/Wookiee
git fetch origin main
git checkout qa/hub-to-sheets-sync
git pull origin main --rebase  # если main ушёл вперёд

# Проверить что код PR #137 в наличии
ls services/sheets_sync/hub_to_sheets/exporter.py
ls services/analytics_api/catalog_sync.py
ls database/migrations/030_catalog_export_views.sql
ls wookiee-hub/src/components/catalog/sync-mirror-button.tsx

# Креды
test -f services/sheets_sync/credentials/google_sa.json && echo "SA OK" || echo "SA MISSING"
grep -q "CATALOG_MIRROR_SHEET_ID=" .env && echo "PROD MIRROR ID set" || echo "MISSING ENV"
grep -q "HUB_QA_USER_PASSWORD" .env && echo "Hub QA user creds OK" || echo "MISSING"

# Создать QA-LOG.md skeleton
cat > wookiee-hub/.planning/hub-to-sheets-sync/QA-LOG.md << 'EOF'
# Hub → Sheets Sync — QA Log

**Запущено:** YYYY-MM-DD HH:MM
**Orchestrator:** Claude Opus 4.7 (new context)
**План:** QA-PLAN.md v1.0

## Phase 1: \n bug fix
## Phase 2: Test environment setup
## Phase 3: Read-only verification on PROD MIRROR
## Phase 4: Mutation tests on TEST MIRROR
## Phase 5: Final summary
EOF
```

**Gate Phase 0 → 1:** все файлы на месте, креды есть, лог создан.

---

## 3. Фаза 1 — Фикс `\n` в `exporter._to_cell` (~30 мин)

### Цель
Многострочные значения из БД (поле «Описание для сайта» в моделях) синкаются в Sheets как одна строка с пробелами вместо `\n`. Высота строк нормализуется.

### Корневая причина (из subagent-исследования)
- Файл: `services/sheets_sync/hub_to_sheets/exporter.py:45-55`
- Функция `_to_cell()` делает `str(value)` без нормализации переносов.
- Источник `\n`: `modeli_osnova.opisanie_sayt` (30 из 76 моделей).
- Other views (artikuly/tovary/cveta/skleyki_*) — чистые сегодня, но фикс должен быть глобальный.

### Шаги (sequential, выполняет orchestrator inline, без subagent)

**1.1.** Прочитать текущий `services/sheets_sync/hub_to_sheets/exporter.py`.

**1.2.** Заменить функцию `_to_cell` на:
```python
def _to_cell(value: object) -> str:
    """Convert a DB value to its Sheets representation (string).

    Multi-line text (\\n, \\r\\n, \\r) is collapsed to a single space — Sheets
    renders \\n as a soft line break, which blows up row height for long-form
    fields like "Описание для сайта".
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Да" if value else "Нет"
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return str(value)
    s = str(value)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = " ".join(part.strip() for part in s.split("\n") if part.strip())
    return s
```

**1.3.** Добавить unit-тест в `tests/services/sheets_sync/test_exporter.py` (создать файл, если нет):
```python
def test_to_cell_collapses_newlines():
    from services.sheets_sync.hub_to_sheets.exporter import _to_cell
    assert _to_cell("a\nb") == "a b"
    assert _to_cell("a\r\nb\r\nc") == "a b c"
    assert _to_cell("a\n\n\nb") == "a b"  # multiple newlines -> single space
    assert _to_cell("  leading and trailing \n  middle  \n end  ") == "leading and trailing middle end"

def test_to_cell_preserves_existing_behavior():
    from services.sheets_sync.hub_to_sheets.exporter import _to_cell
    assert _to_cell(None) == ""
    assert _to_cell(True) == "Да"
    assert _to_cell(False) == "Нет"
    assert _to_cell(26.0) == "26"
    assert _to_cell(26.7) == "26.7"
    assert _to_cell("plain text") == "plain text"
```

**1.4.** Запустить тесты:
```bash
cd /Users/danilamatveev/Projects/Wookiee
python -m pytest tests/services/sheets_sync/ -v
```
**Ожидание:** все тесты pass (старые 17 + новые 2 = 19).

**1.5.** Commit:
```bash
git add services/sheets_sync/hub_to_sheets/exporter.py tests/services/sheets_sync/test_exporter.py
git commit -m "fix(sheets-sync): collapse newlines in _to_cell to prevent row-height blowup

Cells containing \\n (e.g. modeli.opisanie_sayt with paragraph breaks)
were rendered by Sheets as soft line breaks, causing row heights of
~600px in 'Все модели'. Now collapse all newlines
to single space at export time.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

**1.6.** Запустить `/pullrequest` через Skill tool:
```
Skill: pullrequest
args: (none — auto-merge default)
```

Ожидание: PR создан, Codex review проходит (или 1-2 раунда правок), squash-мердж в main, ветка удалена с remote.

**1.7.** Дождаться автопулла на сервере timeweb (~5-10 мин). Verify:
```bash
ssh timeweb 'cd /home/danila/projects/wookiee && git log -1 --oneline'
# Должен показать новый коммит с "collapse newlines"
ssh timeweb 'docker compose -f /home/danila/projects/wookiee/docker-compose.yml ps analytics-api | grep -o "Up [0-9]* minutes"'
# Контейнер запущен недавно
```

**1.8.** Триггернуть синк только для моделей:
```bash
curl -s -X POST https://analytics-api.os.wookiee.shop/api/catalog/sync-mirror \
  -H "X-API-Key: $ANALYTICS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"sheet":"Все модели"}' | jq
```
**Ожидание:** `cells_updated >= 30, rows_appended=0, rows_deleted=0, status="ok"`.

**1.9.** Прочитать `\n` в PROD MIRROR заново (gspread, см. Phase 3C методику) → подтвердить что **0 ячеек** содержат `\n`.

### Phase 1 verification gate
- ✅ Unit-тесты pass
- ✅ PR смерджен
- ✅ Контейнер пересобран
- ✅ Sync run обновил ≥30 ячеек
- ✅ В PROD MIRROR `\n` больше нет

→ Записать в QA-LOG.md `Phase 1: PASS`. Перейти к Phase 2.

### Откат, если Phase 1 проваливается
- Если тесты упали → починить тесты, не двигаться дальше
- Если PR review нашёл проблему → исправить
- Если ячейки не обновились после sync → проверить логи analytics-api на сервере: `ssh timeweb 'docker logs analytics-api --tail 100'`

---

## 4. Фаза 2 — Тестовое окружение (~20 мин)

### Цель
Создать изолированные ресурсы для жёстких мутационных тестов. Ничего не должно касаться prod-таблиц или prod-зеркала.

### Артефакты, которые создаются
1. **TEST MIRROR sheet** (отдельный Google-документ, 6 листов с теми же заголовками что у prod-зеркала)
2. **`test_catalog_sync` schema** в Supabase с 6 fixture-таблицами и 6 views поверх них
3. **CLI-флаги** в `runner.py`: `--spreadsheet-id` и `--views-schema` для переопределения env
4. **`.env`-переменная** `CATALOG_MIRROR_SHEET_ID_TEST` (только локально, не на сервере)

### Шаги (sequential)

**2.1. Создать TEST MIRROR через `/gws-sheets`:**

Orchestrator вызывает Skill `gws-sheets`:
```
Создай Google-таблицу «Спецификация Wookiee — Test Mirror (QA)» с 6 листами:
- Все модели
- Все артикулы
- Все товары
- Аналитики цветов
- Склейки WB
- Склейки Озон

Заголовки скопировать с prod-зеркала (sheet ID 1qqcCmg-Xagike1G3F3TdBihEDFF6mMLiDiZPXXWR7ls,
строка 1 каждой вкладки). Дать доступ matveev.liceist@gmail.com (editor) и
сервис-аккаунту из services/sheets_sync/credentials/google_sa.json (editor).
Вернуть spreadsheet ID.
```

Сохранить ID в переменную `TEST_MIRROR_ID` (используется ниже).

**2.2. Прописать в локальный `.env`:**
```bash
echo "CATALOG_MIRROR_SHEET_ID_TEST=$TEST_MIRROR_ID" >> /Users/danilamatveev/Projects/Wookiee/.env
```
(только локально, на сервере не нужно — все Phase 4 тесты гоняются локально через CLI).

**2.3. Создать `test_catalog_sync` schema в Supabase:**

Подключение через `services/analytics_api/db.py` (или прямой psycopg2 с `SUPABASE_DB_URL` из .env).

```sql
-- Schema
CREATE SCHEMA IF NOT EXISTS test_catalog_sync;

-- Fixture-таблицы (минимальные, для каждой ситуации тестов)
CREATE TABLE test_catalog_sync.fx_modeli (
  kod text PRIMARY KEY,
  status text,
  nazvanie text,
  opisanie_sayt text,
  bool_flag boolean,
  num_value numeric(10,2)
);

CREATE TABLE test_catalog_sync.fx_skleyki_wb (
  nazvanie text,
  barcode text,
  artikul text,
  model text,
  color_code int,
  cvet text,
  razmer text,
  kanal text,
  sozdano timestamp,
  PRIMARY KEY (nazvanie, barcode)
);

-- views, эмулирующие vw_export_*
CREATE OR REPLACE VIEW test_catalog_sync.vw_export_modeli AS
SELECT
  kod AS "Модель",
  '' AS "Модель основа",
  nazvanie AS "Название модели",
  '' AS "Название EN",
  '' AS "Артикул модели",
  '' AS "Бренд",
  '' AS "Категория",
  '' AS "Коллекция",
  '' AS "Тип коллекции",
  '' AS "Фабрика",
  status AS "Статус",
  '' AS "Российский размер",
  '' AS "Размеры модели",
  bool_flag AS "Набор",
  '' AS "Теги",
  '' AS "Посадка трусов",
  '' AS "Вид трусов",
  '' AS "Для какой груди",
  '' AS "Степень поддержки",
  '' AS "Форма чашки",
  '' AS "Регулировка",
  '' AS "Застежка",
  '' AS "Назначение",
  '' AS "Стиль",
  '' AS "По настроению",
  '' AS "Материал",
  '' AS "Состав сырья",
  '' AS "Composition",
  '' AS "ТНВЭД",
  '' AS "Группа сертификата",
  '' AS "Название для этикетки",
  '' AS "Название для сайта",
  opisanie_sayt AS "Описание для сайта",
  '' AS "Details",
  '' AS "Description",
  '' AS "SKU CHINA",
  '' AS "Упаковка",
  num_value AS "Вес (кг)",
  '' AS "Длина",
  '' AS "Ширина",
  '' AS "Высота",
  '' AS "Кратность короба",
  '' AS "Срок производства",
  '' AS "Комплектация",
  '' AS "Notion link",
  '' AS "Notion strategy link",
  '' AS "Yandex disk link",
  '' AS "Header image URL"
FROM test_catalog_sync.fx_modeli;

CREATE OR REPLACE VIEW test_catalog_sync.vw_export_skleyki_wb AS
SELECT
  nazvanie AS "Название склейки",
  barcode AS "БАРКОД",
  artikul AS "Артикул",
  model AS "Модель",
  color_code AS "Color code",
  cvet AS "Цвет",
  razmer AS "Размер",
  kanal AS "Канал",
  to_char(sozdano, 'YYYY-MM-DD HH24:MI:SS') AS "Создано"
FROM test_catalog_sync.fx_skleyki_wb;

-- (остальные 4 view создавать НЕ обязательно — Phase 4 тесты используют только Модели и Склейки WB)

GRANT USAGE ON SCHEMA test_catalog_sync TO service_role, authenticated;
GRANT SELECT ON ALL TABLES IN SCHEMA test_catalog_sync TO service_role, authenticated;
```

**2.4. Добавить CLI-флаги в `runner.py`** (это требует код-правки):

В `services/sheets_sync/hub_to_sheets/runner.py` найти `argparse.ArgumentParser` и добавить:
```python
parser.add_argument("--spreadsheet-id", help="Override CATALOG_MIRROR_SHEET_ID env var")
parser.add_argument("--views-schema", default="public", help="Schema for vw_export_* views (default: public)")
```

В `SheetSpec` или в местах, где view используется — пробрасывать `--views-schema` так, чтобы view-name стало `f"{schema}.vw_export_modeli"` вместо `"public.vw_export_modeli"`.

В `SheetsBatchWriter.__init__` — принимать `spreadsheet_id` параметром, если передан — использовать, иначе `os.environ["CATALOG_MIRROR_SHEET_ID"]`.

**Это атомарный коммит, тесты пишутся параллельно:**
```python
def test_runner_respects_spreadsheet_id_override(monkeypatch):
    ...

def test_runner_respects_views_schema_override(monkeypatch):
    ...
```

Коммит:
```
chore(sheets-sync): CLI flags --spreadsheet-id and --views-schema for testing
```

**2.5. Smoke-тест test mirror:**
```bash
python -m services.sheets_sync.hub_to_sheets.runner \
  --spreadsheet-id "$TEST_MIRROR_ID" \
  --views-schema test_catalog_sync \
  --smoke
```
**Ожидание:** JSON с `anchor_ok: true, status_col_ok: true` для листов «Все модели» и «Склейки WB» (остальные — пустые).

### Phase 2 verification gate
- ✅ TEST_MIRROR_ID сохранён, документ открывается
- ✅ Schema `test_catalog_sync` создана с 2 view (modeli, skleyki_wb)
- ✅ CLI-флаги работают (smoke не падает)
- ✅ Коммит CLI-флагов отдельным PR (можно отложить мердж до конца Phase 4)

→ Записать в QA-LOG.md `Phase 2: PASS`. Перейти к Phase 3.

---

## 5. Фаза 3 — Read-only проверки на PROD MIRROR (~15 мин)

### Цель
Убедиться, что зеркало в текущем состоянии полностью соответствует БД. **Никаких записей ни в БД, ни в Sheets, ни в tool_runs (кроме нормального run при тесте идемпотентности).** Все 4 subagent'а — параллельно.

### Subagent 3A — Hub UI

Promt:
```
Use Playwright (mcp__plugin_playwright_playwright__*) to verify that the
'Обновить зеркало' button works on all 9 Hub catalog pages.

Login: HUB_QA_USER (claude-agent@wookiee.shop), пароль в .env (HUB_QA_USER_PASSWORD).
Login flow: https://hub.os.wookiee.shop/login → fill email/password → submit.

Pages to test:
- https://hub.os.wookiee.shop/catalog/artikuly
- https://hub.os.wookiee.shop/catalog/tovary
- https://hub.os.wookiee.shop/catalog/colors
- https://hub.os.wookiee.shop/catalog/skleyki
- https://hub.os.wookiee.shop/catalog/reference/brendy
- https://hub.os.wookiee.shop/catalog/reference/kollekcii
- https://hub.os.wookiee.shop/catalog/reference/kategorii
- https://hub.os.wookiee.shop/catalog/reference/tipy-kollekciy
- https://hub.os.wookiee.shop/catalog/reference/fabriki

For each page:
1. Navigate to URL
2. Find button labelled 'Обновить зеркало' (header area, top-right)
3. Take screenshot before click
4. Click the button — confirm dropdown opens with 7 options
5. Close dropdown (esc)
6. Take screenshot

Do NOT actually click 'Всё' or any sheet option — just verify button exists,
is enabled, opens dropdown.

Return: per-page PASS/FAIL + screenshot paths.
```

### Subagent 3B — Auth и эндпоинты

Promt:
```
Test authentication and validation on /api/catalog/sync-mirror endpoint.

Use curl (Bash tool). Tests:

1. POST without Authorization header → expect 401
   curl -i -X POST https://analytics-api.os.wookiee.shop/api/catalog/sync-mirror -H "Content-Type: application/json" -d '{}'

2. POST with garbage Bearer → expect 401
   curl -i -X POST https://analytics-api.os.wookiee.shop/api/catalog/sync-mirror -H "Authorization: Bearer xxx" -H "Content-Type: application/json" -d '{}'

3. POST with valid X-API-Key (from .env ANALYTICS_API_KEY), invalid sheet → expect 400 with message listing valid sheet names
   curl -i -X POST ... -H "X-API-Key: $ANALYTICS_API_KEY" -d '{"sheet":"NonExistent"}'

4. GET /status without auth → expect 401
   curl -i https://analytics-api.os.wookiee.shop/api/catalog/sync-mirror/status

5. GET /status with valid key → expect 200 with last run info
   curl -i ... -H "X-API-Key: $ANALYTICS_API_KEY"

Return: per-test expected vs actual status, response body excerpt.
```

### Subagent 3C — Data integrity

Promt:
```
Verify that PROD MIRROR (spreadsheet 1qqcCmg-Xagike1G3F3TdBihEDFF6mMLiDiZPXXWR7ls)
matches the underlying DB views byte-for-byte.

Steps:
1. Connect to Supabase via psycopg2 (creds in .env: SUPABASE_DB_URL or pieces).
2. Connect to mirror via gspread (auth: services/sheets_sync/credentials/google_sa.json).

For each of 6 sheets/views:
- Все модели        ↔ public.vw_export_modeli
- Все артикулы      ↔ public.vw_export_artikuly
- Все товары        ↔ public.vw_export_tovary
- Аналитики цветов  ↔ public.vw_export_cveta
- Склейки WB        ↔ public.vw_export_skleyki_wb
- Склейки Озон      ↔ public.vw_export_skleyki_ozon

Do:
3. count_db  = SELECT count(*) FROM the view
4. count_sh  = number of non-empty data rows in the sheet (rows where anchor col is filled)
5. Assert count_db == count_sh

6. Pick 10 random anchors from the DB (use random.sample on full result set).
7. For each anchor: read the full DB row + the full sheet row, normalize via the
   same _to_cell() logic (from services/sheets_sync/hub_to_sheets/exporter.py),
   and assert ALL shared columns match.

Important: use the JUST-DEPLOYED _to_cell (after Phase 1 fix) — newlines collapsed.
Run AFTER Phase 1's sync (which should have written all 30 fixed rows already).

Return: per-sheet table:
| Sheet | DB count | Sheet count | Match? | Mismatches (anchor → column → db_val vs sh_val) |
```

### Subagent 3D — Идемпотентность и /status

Promt:
```
Verify idempotency and status endpoint.

1. Read current tool_runs row (most recent for slug 'catalog-sheets-mirror'):
   SQL: SELECT * FROM public.tool_runs WHERE tool_slug='catalog-sheets-mirror' ORDER BY started_at DESC LIMIT 1
   Save the run_id as PREV_RUN_ID.

2. Trigger a full sync via API:
   curl -X POST https://analytics-api.os.wookiee.shop/api/catalog/sync-mirror \
     -H "X-API-Key: $ANALYTICS_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"sheet":"all"}'
   Save response as RUN_1.

3. Wait 2s, trigger again identically. Save as RUN_2.

4. For RUN_2, assert:
   - status == "ok"
   - cells_updated == 0
   - rows_appended == 0
   - rows_deleted == 0
   This is the idempotency check.

5. GET /api/catalog/sync-mirror/status with valid auth.
   Assert response includes: run_id (== RUN_2.run_id), status="success",
   started_at, finished_at, duration_ms (positive int), output_summary.

6. Verify in DB:
   SELECT * FROM public.tool_runs WHERE tool_slug='catalog-sheets-mirror'
     ORDER BY started_at DESC LIMIT 3;
   Top row should match RUN_2; status='success'.

Return: PASS/FAIL with the relevant counters.
```

### Phase 3 verification gate
- ✅ Все 4 subagent'а вернули PASS
- ✅ Никаких записей в БД не делалось
- ✅ PROD MIRROR не был структурно изменён

→ Записать в QA-LOG.md `Phase 3: PASS` (или FAIL с деталями). Перейти к Phase 4.

---

## 6. Фаза 4 — Мутационные тесты на TEST MIRROR (~60 мин)

### Цель
Прогнать каждую правило/edge case системы на изолированных fixture-данных. Никаких prod-таблиц, никаких prod-листов.

### Шаги (strictly sequential — большинство тестов зависит от состояния предыдущего)

**Setup:**
```sql
-- Очистить fixtures на старте
TRUNCATE test_catalog_sync.fx_modeli, test_catalog_sync.fx_skleyki_wb;
```

Все sync-команды Phase 4 запускаются как:
```bash
python -m services.sheets_sync.hub_to_sheets.runner \
  --spreadsheet-id "$TEST_MIRROR_ID" \
  --views-schema test_catalog_sync \
  --sheet "<sheet name>" 2>&1 | tee /tmp/qa-phase4-T<N>.log
```

---

**T9 — Append новой строки**
```sql
INSERT INTO test_catalog_sync.fx_modeli (kod, status, nazvanie, opisanie_sayt, bool_flag, num_value)
VALUES ('TEST_M_001', 'Продается', 'Test Model 1', 'short desc', true, 100.00);
```
Sync `--sheet "Все модели"`.

**Verify:** response: `rows_appended=1, cells_updated=0, rows_deleted=0`. В TEST MIRROR появилась строка с `Модель=TEST_M_001, Статус=Продается`.

---

**T10 — Update одной ячейки**
```sql
UPDATE test_catalog_sync.fx_modeli SET status='Выводим' WHERE kod='TEST_M_001';
```
Sync.

**Verify:** `cells_updated=1, rows_appended=0`. В строке TEST_M_001 столбец «Статус» = `Выводим`.

---

**T11 — Hub-empty не затирает**
```
В TEST MIRROR вручную (через gspread в тесте) записать значение "MANUAL NOTE"
в ячейку TEST_M_001 / "Название EN" (этот столбец в fx_modeli пустой).
```
Sync.

**Verify:** `cells_updated=0`. Ячейка TEST_M_001/«Название EN» = `MANUAL NOTE` (не стёрта).

---

**T12 — Архив для non-skleyki**
```sql
DELETE FROM test_catalog_sync.fx_modeli WHERE kod='TEST_M_001';
```
Sync.

**Verify:** `cells_updated=1` (status set), `rows_deleted=0`. В TEST MIRROR строка TEST_M_001 на месте, «Статус» = `Архив`. «Название EN» = `MANUAL NOTE` (всё ещё не стёрта).

---

**T13 — Уже-Архив = no-op**
Sync ещё раз (без изменений в fx_modeli).

**Verify:** `cells_updated=0, rows_appended=0, rows_deleted=0` (полный no-op).

---

**T14 — Физическое удаление склейки**
```sql
INSERT INTO test_catalog_sync.fx_skleyki_wb VALUES
  ('TEST_SKLEYKA_1', 'BARCODE_001', 'art1', 'M1', 1, 'Black', 'M', 'WB', NOW()),
  ('TEST_SKLEYKA_1', 'BARCODE_002', 'art1', 'M1', 1, 'Black', 'L', 'WB', NOW());
```
Sync `--sheet "Склейки WB"`. Verify: `rows_appended=2`.

Затем:
```sql
DELETE FROM test_catalog_sync.fx_skleyki_wb WHERE barcode='BARCODE_001';
```
Sync.

**Verify:** `rows_deleted=1, cells_updated=0`. В TEST MIRROR Склейки WB содержит только `BARCODE_002`, строка с `BARCODE_001` физически удалена.

---

**T15 — Массовое удаление склеек (order check)**
```sql
INSERT INTO test_catalog_sync.fx_skleyki_wb
SELECT 'BULK', 'B'||generate_series(1,110), 'a', 'm', 1, 'c', 'r', 'WB', NOW();
```
Sync. Verify `rows_appended=110`.

```sql
DELETE FROM test_catalog_sync.fx_skleyki_wb WHERE artikul='a';
```
Sync.

**Verify:** `rows_deleted=110`, в TEST MIRROR Склейки WB содержит только `BARCODE_002` (одна строка от T14). Никаких остатков от bulk.

---

**T16 — Formula injection (USER_ENTERED)**
```sql
INSERT INTO test_catalog_sync.fx_modeli (kod, status, nazvanie)
VALUES ('TEST_FORMULA', 'Продается', '=1+1');
```
Sync `--sheet "Все модели"`.

**Verify:** В TEST MIRROR в ячейке TEST_FORMULA/«Название модели»:
- Если ячейка показывает `2` → **FAIL**: USER_ENTERED опасен, нужно переключить на RAW в `batch.py:152,177` для текстовых колонок (или вообще). Записать как баг, не блокировать остальные тесты.
- Если ячейка показывает `=1+1` буквально → PASS.

**Если FAIL — багу записать, но фиксить отдельным коммитом после Phase 4 (не блокировать остальные тесты).**

---

**T17 — Decimal с trailing zeros**
```sql
INSERT INTO test_catalog_sync.fx_modeli (kod, status, num_value)
VALUES ('TEST_DEC', 'Продается', 26.70);
```
Sync. Verify: `rows_appended=1`. Ячейка TEST_DEC/«Вес (кг)» = `26.7` или `26.70`.

Sync ещё раз без изменений.

**Verify:** `cells_updated=0`. Если 1 — баг: трейлинг-нули в Decimal вызывают флип. Записать.

---

**T18 — Многострочные значения (валидация Phase 1)**
```sql
INSERT INTO test_catalog_sync.fx_modeli (kod, status, opisanie_sayt)
VALUES ('TEST_NL', 'Продается', E'first line\nsecond line\n\nthird');
```
Sync `--sheet "Все модели"`.

**Verify:** Ячейка TEST_NL/«Описание для сайта» = `first line second line third` (без `\n`, одной строкой). gspread → read raw cell value → not contains `\n`.

---

**T19 — Параллельные запуски (race condition)**
Запустить два sync параллельно в фоне:
```bash
(python -m services.sheets_sync.hub_to_sheets.runner \
  --spreadsheet-id "$TEST_MIRROR_ID" --views-schema test_catalog_sync --sheet "Все модели" > /tmp/qa-t19-a.json) &
(python -m services.sheets_sync.hub_to_sheets.runner \
  --spreadsheet-id "$TEST_MIRROR_ID" --views-schema test_catalog_sync --sheet "Все модели" > /tmp/qa-t19-b.json) &
wait
```

**Verify:** оба завершились без ошибок. Сложить `rows_appended` от обоих. В TEST MIRROR в `Все модели` посчитать строки. Если их больше чем уникальных `kod` в fx_modeli → race-condition (дубли). Записать как баг.

(Это известный риск без advisory lock — может быть FAIL, и это OK для текущей фазы, если задокументировано.)

---

**T20 — Smoke endpoint**
```bash
python -m services.sheets_sync.hub_to_sheets.runner \
  --spreadsheet-id "$TEST_MIRROR_ID" \
  --views-schema test_catalog_sync \
  --smoke
```
**Verify:** Для каждого листа в JSON:
- `header_cols > 0`
- `anchor_ok: true`
- Для не-склейки: `status_col_ok: true`
- Для склейки: `status_col_ok: true` (т.к. status_col=None ожидаемо)

---

**Teardown:**
```sql
DROP SCHEMA test_catalog_sync CASCADE;
```
Локально из `.env` убрать `CATALOG_MIRROR_SHEET_ID_TEST`. TEST MIRROR оставить (доступен для повторных тестов).

### Phase 4 verification gate
- ✅ T9-T15, T18, T20 — PASS
- ⚠️ T16, T17, T19 могут быть FAIL — это known risks, документируются, не блокируют merge
- ✅ Schema удалена, prod-данные нетронуты

→ Записать в QA-LOG.md `Phase 4: PASS` или `Phase 4: PASS WITH NOTED ISSUES`.

---

## 7. Фаза 5 — Финальный отчёт (~10 мин)

### Цель
Собрать всё в QA-LOG.md, решить судьбу qa-ветки.

**Шаги:**

**5.1.** Записать summary в QA-LOG.md:
```markdown
## Phase 5: Summary

**Всего тестов:** 20
**PASS:** N
**FAIL:** M
**SKIP:** K

**Critical fixes shipped:** `\n` collapsing (Phase 1 PR #XXX).

**Noted issues (не блокирующие):**
- T16 USER_ENTERED — formula injection возможна, рекомендуется переключить на RAW для текстовых колонок.
- T19 race condition — без advisory lock параллельные запуски могут создавать дубли.

**Рекомендация:**
- ✅ Готово к prod-использованию для одиночных операторских запусков.
- ⚠️ Не запускать параллельно из cron + Hub одновременно.
- 🔧 Следующая итерация: advisory lock + RAW mode + cosmetic phase.
```

**5.2.** Закоммитить QA-LOG.md в ветку `qa/hub-to-sheets-sync`:
```bash
git add wookiee-hub/.planning/hub-to-sheets-sync/QA-LOG.md
git commit -m "docs(qa): full Hub→Sheets sync QA report

20 tests across Phase 1-4. Phase 1 (\\n fix) shipped in PR #XXX.
Phase 3 read-only checks: all PASS.
Phase 4 mutation tests: T9-T15 PASS, T16/T17/T19 noted.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

**5.3.** Если есть noted issues с фиксами → создать отдельные PR'ы для каждого. Если только документация → PR ветки `qa/hub-to-sheets-sync` в main.

**5.4.** Сообщить пользователю итог одной фразой:
```
QA выполнен: N/20 PASS, M/20 FAIL (noted), Phase 1 fix в PR #XXX.
Полный лог: wookiee-hub/.planning/hub-to-sheets-sync/QA-LOG.md
```

---

## 8. Справочник для orchestrator'а

### Sheet IDs
- **PROD MIRROR:** `1qqcCmg-Xagike1G3F3TdBihEDFF6mMLiDiZPXXWR7ls`
- **Основная (main spec):** `19Nbr0kD8JJlwd7OCIMbM9qxucYNjmXnWtwJUgXv0vlg`
- **TEST MIRROR:** создаётся в Phase 2.1, ID сохраняется в .env

### Ключевые файлы
- `services/sheets_sync/hub_to_sheets/exporter.py` — `_to_cell` (Phase 1)
- `services/sheets_sync/hub_to_sheets/runner.py` — CLI (Phase 2.4)
- `services/sheets_sync/hub_to_sheets/batch.py` — gspread retry/auth (RAW vs USER_ENTERED — на случай T16 фикса)
- `services/analytics_api/catalog_sync.py` — API endpoint
- `database/migrations/030_catalog_export_views.sql` — views
- `services/sheets_sync/credentials/google_sa.json` — SA key
- `.env` — `CATALOG_MIRROR_SHEET_ID`, `ANALYTICS_API_KEY`, `SUPABASE_DB_URL`, `HUB_QA_USER_PASSWORD`

### Hub credentials
- QA user: `claude-agent@wookiee.shop`, пароль в `.env` (`HUB_QA_USER_PASSWORD`)

### Slash-commands
- `/gws-sheets` — для создания TEST MIRROR (Phase 2.1)
- `/pullrequest` — для PR с auto-merge (Phase 1.6)
- `/update-env` — НЕ нужен в этой QA (TEST_MIRROR_ID только локально)

### Полезные SQL
```sql
-- Состояние tool_runs для catalog-sheets-mirror
SELECT run_id, status, started_at, finished_at, duration_ms,
       output_summary, error_message, triggered_by
FROM public.tool_runs
WHERE tool_slug = 'catalog-sheets-mirror'
ORDER BY started_at DESC LIMIT 5;

-- Кол-ва в prod views
SELECT 'modeli' AS view, count(*) FROM public.vw_export_modeli UNION ALL
SELECT 'artikuly', count(*) FROM public.vw_export_artikuly UNION ALL
SELECT 'tovary',   count(*) FROM public.vw_export_tovary UNION ALL
SELECT 'cveta',    count(*) FROM public.vw_export_cveta UNION ALL
SELECT 'skleyki_wb', count(*) FROM public.vw_export_skleyki_wb UNION ALL
SELECT 'skleyki_ozon', count(*) FROM public.vw_export_skleyki_ozon;
-- Эталон на 2026-05-14: 76 / 554 / 1473 / 146 / 1442 / 1345
```

### Подключение к Sheets (Python)
```python
import gspread
from google.oauth2.service_account import Credentials

creds = Credentials.from_service_account_file(
    "services/sheets_sync/credentials/google_sa.json",
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ],
)
gc = gspread.authorize(creds)
sh = gc.open_by_key("1qqcCmg-Xagike1G3F3TdBihEDFF6mMLiDiZPXXWR7ls")
ws = sh.worksheet("Все модели")
all_values = ws.get_all_values()
```

### Подключение к Supabase (Python)
```python
import os
import psycopg2
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()
db_url = os.environ["SUPABASE_DB_URL"]  # или соберите из частей SUPABASE_DB_HOST/PORT/...
conn = psycopg2.connect(db_url)
cur = conn.cursor()
cur.execute("SELECT count(*) FROM public.vw_export_modeli")
print(cur.fetchone())
```

---

## 9. Известные риски и обходы

| Риск | Митигация |
|---|---|
| TEST MIRROR креды утекут в логи | Не печатать TEST_MIRROR_ID в публичных каналах. В .env он только локально |
| Phase 1 PR review нашёл проблему | Orchestrator чинит, не обходит, не пушит без review |
| Phase 4 race condition (T19) FAIL | Это known limitation, документируется в QA-LOG, не блокирует Phase 5 |
| autopull не подхватил Phase 1 | Phase 1.7 явно ждёт + проверяет ssh — нет проверки → STOP |
| Supabase DB url не в .env | Orchestrator должен сам подобрать (SUPABASE_DB_HOST/PORT/USER/PASSWORD склеить) |
| Service account потерял доступ к TEST MIRROR | Phase 2.1 явно делит права с SA — проверить через gspread connect |
| Запуск в context'е, где нет нужных Skills | Orchestrator должен sanity-check'нуть наличие /gws-sheets, /pullrequest до старта |

---

## 10. Список ожидаемых артефактов после QA

После завершения orchestrator должен оставить в репо:

- ✅ Коммит фикса `\n` в main (через PR из Phase 1)
- ✅ Коммит CLI-флагов в `runner.py` (отдельный PR из Phase 2.4, может быть слит позже)
- ✅ Файл `wookiee-hub/.planning/hub-to-sheets-sync/QA-LOG.md` с полным отчётом
- ✅ Schema `test_catalog_sync` в Supabase — **удалена** в teardown
- ✅ Ветка `qa/hub-to-sheets-sync` — содержит QA-LOG.md, готова к мерджу или удалению
- ✅ TEST MIRROR sheet — остаётся (для будущих regression-проверок)

---

## 11. Чего этот план НЕ покрывает (out of scope)

- ❌ Косметика: цветные шапки, переименования (Lamoda→Ламода), расширение views
- ❌ Полная замена USER_ENTERED → RAW в gspread писателе (если T16 FAIL — заводится отдельная задача)
- ❌ Внедрение advisory lock на `tool_slug` (если T19 FAIL — заводится отдельная задача)
- ❌ Регрессионные snapshot-тесты (отдельный шаг после стабилизации)
- ❌ Performance/scale тесты (большие view'ы)

Эти пункты — следующая итерация после успешного QA.

---

*Конец плана. Orchestrator: читай раздел 0 → выполняй фазы строго по порядку → останавливайся на каждом verification gate.*
