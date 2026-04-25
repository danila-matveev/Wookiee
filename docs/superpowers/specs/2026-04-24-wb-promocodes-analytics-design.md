# WB Promocodes Analytics — design

**Date:** 2026-04-24
**Status:** draft (pending user approval)
**Owner:** danila
**Tool slug (registry):** `wb-promocodes-analytics`

## 1. Цель

Еженедельный отчёт по эффективности промокодов (WB seller promocodes, фича Beta) для двух кабинетов (ООО + ИП). Источник — `reportDetailByPeriod` v5 (поля `uuid_promocode`, `sale_price_promocode_discount_prc`). Результат — Google Sheets с дашборд-шапкой и кнопкой ручного обновления.

## 2. Бизнес-требования

- **R1.** Видеть продажи, заказы, возвраты, среднюю скидку и топ-3 модели по каждому промокоду — за каждую неделю.
- **R2.** История за всё время существования фичи (последние ~2-3 месяца, расширим если данные раньше есть).
- **R3.** Оба кабинета (ООО + ИП) в одной таблице, с разделением по столбцу.
- **R4.** Связь UUID → человеко-читаемое имя (CHARLOTTE10 и т.д.). Имя WB через API не отдаёт — пользователь ведёт справочник вручную (UUID копируется из WB UI при создании промокода).
- **R5.** UUID, которых нет в справочнике, выводятся в аналитику с пометкой «неизвестный» (с полной статистикой) — пользователь дозаполняет справочник постфактум.
- **R6.** Кнопка «🔄 Обновить» в таблице — подтянуть данные за последнюю закрытую неделю по запросу, без ожидания крона.
- **R7.** Дашборд-шапка: timestamp последнего обновления, статус (все ли недели на месте), краткие метрики за последнюю неделю.
- **R8.** Регистрация в реестре `tools` (Supabase) для трекинга запусков, метрик, отображения в каталоге.

## 3. Архитектура

### 3.1 Прототип

Полностью копирует паттерн **`wb-logistics-optimizer`** ([services/wb_logistics_api/app.py](services/wb_logistics_api/app.py)):

```
services/wb_promocodes_api/        # HTTP-эндпоинт (FastAPI)
    app.py                          # POST /run, GET /status, GET /health
    requirements.txt
services/sheets_sync/sync/
    sync_promocodes.py              # расчётное ядро (читает API, агрегирует, пишет в Sheets)
scripts/
    run_wb_promocodes_sync.py       # CLI-обёртка (для крона и ручного запуска из shell)
```

Ядро (`sync_promocodes.py`) вызывается из обоих путей: и из `app.py` (фоновый поток после POST /run), и из CLI (cron / отладка).

### 3.2 Триггеры

| Триггер | Путь | Когда срабатывает |
|---|---|---|
| Cron в `wb-promocodes-api` контейнере | прямо вызывает CLI | вторник 09:00 МСК |
| GAS-кнопка «Обновить» | UrlFetchApp → POST /run | по нажатию пользователя |
| Ручной запуск | CLI на сервере | отладка, бэкфилл |

Все три пути попадают в одну функцию `sync_promocodes.run(week_start, week_end, cabinets)` → один источник истины.

### 3.3 Идемпотентность

Ключ строки в листе аналитики: `(week_start, cabinet, uuid)`. Перед записью скрипт ищет такую строку и **обновляет её**, если есть; иначе добавляет новую. Безопасно перезапускать — дубликатов не будет.

## 4. Google Sheets — структура

**Spreadsheet:** `1Y7uxZnrjHLBntoDLkKJBOt5-lmODRJ5QEkE19QBA8xk` (тот, что прислал пользователь).

### 4.1 Лист `Промокоды_справочник` (вручную)

| Колонка | Пример | Заполняет |
|---|---|---|
| UUID | `be6900f2-c9e9-4963-9ad1-27d10d9492d6` | Пользователь (копирует из WB UI) |
| Название | CHARLOTTE10 | Пользователь |
| Канал | Соцсети / Блогер / Корп / Лояльность | Пользователь |
| Скидка % | 10 | Пользователь |
| Старт | 02.03.2026 | Пользователь |
| Окончание | 12.03.2026 | Пользователь |
| Примечание | для @blogger_x, посевы на TG | Пользователь (опц.) |

Скрипт только **читает** этот лист. Автоматически ничего не меняет.

### 4.2 Лист `Промокоды_аналитика`

**Строки 1–8 (фиксированная шапка-дашборд):**

```
A1:E1   [🔄 ОБНОВИТЬ]  ← кнопка GAS
A2      Последнее обновление:    {value B2}: 2026-04-22 09:15:32 МСК ✅
A3      Статус полноты:           ✅ 8 недель (23.02→19.04), пропусков нет
A4      Неизвестных UUID:         2 (см. жёлтые строки ниже)
A6      ── За последнюю неделю (13–19 апр) ──
A7      Активных промокодов: 3 │ Продажи: 45 200 ₽ │ Заказов: 18 │ Чемпион: MYALICE5
```

**Строка 9 — заголовки таблицы.**

**Строки 10+ — данные:**

| Неделя | Кабинет | Название | UUID | Скидка % | Продажи (retail), ₽ | К перечислению, ₽ | Заказов, шт | Возвратов, шт | Ср. чек, ₽ | Топ-3 модели | Обновлено |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---|---|

**Подсветка строк (через conditional formatting):**
- Белый — UUID найден в справочнике
- Светло-жёлтый (`#FFF8DC`) — UUID не найден, поле «Название» = «неизвестный» (триггер для пользователя добавить в справочник)

### 4.3 GAS-кнопка

```javascript
// прикрепляется к Drawing «Обновить»
function refreshPromocodes() {
  const url = PropertiesService.getScriptProperties().getProperty('PROMOCODES_API_URL');
  const token = PropertiesService.getScriptProperties().getProperty('PROMOCODES_API_KEY');
  const resp = UrlFetchApp.fetch(url + '/run', {
    method: 'post',
    headers: { 'X-API-Key': token },
    muteHttpExceptions: true,
    payload: JSON.stringify({ mode: 'last_week' })
  });
  const json = JSON.parse(resp.getContentText());
  // GAS пишет результат в дашборд-ячейки
  const sheet = SpreadsheetApp.getActive().getSheetByName('Промокоды_аналитика');
  sheet.getRange('B2').setValue(new Date());
  if (json.status === 'ok') {
    sheet.getRange('B3').setValue(`✅ Обновлено: +${json.rows_added} строк`);
  } else {
    sheet.getRange('B3').setValue(`❌ Ошибка: ${json.error}`);
  }
}
```

При нажатии: GAS POST'ит на сервер, ждёт результат (до GAS-лимита 360 сек), пишет статус в шапку.

## 5. HTTP API

### `POST /run`

**Headers:** `X-API-Key: <token>`

**Body:**
```json
{ "mode": "last_week" }                                          // closed previous ISO week
{ "mode": "specific", "from": "2026-04-13", "to": "2026-04-19" } // explicit
{ "mode": "bootstrap", "weeks_back": 12 }                        // historical backfill
```

**Response (success):**
```json
{
  "status": "ok",
  "started_at": "2026-04-22T09:15:32+03:00",
  "finished_at": "2026-04-22T09:18:47+03:00",
  "weeks_processed": [["2026-04-13", "2026-04-19"]],
  "cabinets": ["ИП", "ООО"],
  "rows_added": 6,
  "rows_updated": 0,
  "unknown_uuids": ["aaaa-bbbb-...", "cccc-dddd-..."]
}
```

**Response (error):**
```json
{ "status": "error", "error": "WB API rate limit", "stage": "fetch_ip" }
```

Запросы за один ISO-week возвращаются за ~3-4 минуты (rate-limit WB 1 req/min × 2 кабинета × 2-3 страницы).

### `GET /status`

Текущее состояние сервиса: `idle | running | done | error`, с timestamps и последним результатом. Тот же паттерн, что в [services/wb_logistics_api/app.py](services/wb_logistics_api/app.py).

### `GET /health`

Healthcheck для Docker.

## 6. Деплой

**Новый docker-compose сервис:** `wb-promocodes-api` (рядом с `wb-logistics-api`, не в `wookiee_oleg`).

```yaml
wb-promocodes-api:
  build:
    context: .
    dockerfile: services/wb_promocodes_api/Dockerfile
  env_file: .env
  ports:
    - "8092:8000"            # любой свободный порт на сервере
  restart: unless-stopped
  command: ["uvicorn", "services.wb_promocodes_api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Cron** запускаем внутри того же контейнера через `cron` (как в `wookiee_oleg`):
- Расписание: `0 9 * * 2` (вторник 09:00 МСК)
- Команда: `python /app/scripts/run_wb_promocodes_sync.py --mode last_week`

Альтернатива (предпочительная при простоте): cron на хосте Timeweb вызывает curl `POST /run` — без cron внутри контейнера. Решим на этапе планирования.

## 7. Bootstrap

При первом запуске (флаг `--mode bootstrap --weeks-back 12`):

1. **ООО** — читает кеш [output/wb_promocodes_test/rows_2026-04-24.jsonl](output/wb_promocodes_test/rows_2026-04-24.jsonl) (260K строк за 60 дней), разбивает по ISO-неделям, апсёртит в лист. Бесплатно — без API.
2. **ИП** — дёргает `reportDetailByPeriod` за 60-90 дней (~5-7 минут).
3. Если данных за 12 недель не хватает (фича промокодов могла быть включена позже) — пишем меньше недель, не падаем.

## 8. Реестр инструментов (Supabase `tools`)

Новая запись:

```python
{
    "slug": "wb-promocodes-analytics",
    "display_name": "Аналитика промокодов WB",
    "type": "service",
    "category": "analytics",
    "description": (
        "Еженедельный сбор статистики по промокодам WB (продажи, заказы, скидка, "
        "топ-3 модели) для обоих кабинетов (ООО + ИП). Источник — reportDetailByPeriod v5. "
        "Результат — Google Sheets с дашборд-шапкой и кнопкой ручного обновления. "
        "Cron вторник 09:00 МСК + ручной триггер через GAS."
    ),
    "how_it_works": (
        "1) Читает Sheets-справочник (UUID → Название). "
        "2) Для каждого кабинета (ООО + ИП): reportDetailByPeriod v5 за прошлую ISO-неделю. "
        "3) Фильтрует строки с uuid_promocode != ''. "
        "4) Агрегирует по UUID. "
        "5) Джойнит с справочником. "
        "6) Апсёртит в лист 'Промокоды_аналитика' (ключ: week+cabinet+uuid). "
        "7) Обновляет дашборд-шапку с timestamp + метриками. "
        "Триггеры: cron + GAS-кнопка → POST /run"
    ),
    "status": "active",
    "version": "1.0.0",
    "run_command": "POST /run | python scripts/run_wb_promocodes_sync.py --mode last_week",
    "data_sources": ["WB Statistics API (reportDetailByPeriod v5)", "Google Sheets справочник"],
    "depends_on": ["WB Supplier API", "Google Sheets API"],
    "output_targets": ["Google Sheets (Промокоды_аналитика, dashboard header)"],
    "owner": "danila"
}
```

## 9. Конфигурация

В `.env`:
```
PROMOCODES_API_KEY=<random 32-char token>
PROMOCODES_SPREADSHEET_ID=1Y7uxZnrjHLBntoDLkKJBOt5-lmODRJ5QEkE19QBA8xk
PROMOCODES_DICT_SHEET=Промокоды_справочник
PROMOCODES_DATA_SHEET=Промокоды_аналитика
```

WB-ключи (`WB_API_KEY_OOO`, `WB_API_KEY_IP`) и Google SA — переиспользуем существующие.

## 10. Логирование и мониторинг

- Каждый запуск пишет строку в `tool_runs` (Supabase) — для дашборда статуса в реестре.
- Stdout/stderr контейнера — обычные docker-логи.
- Дашборд-шапка таблицы — пользовательский UI статуса.

## 11. Что НЕ входит (out of scope для v1)

- Авто-маппинг UUID → name через WB Promocodes API (не нашёл в публичной документации). Решаем ручным справочником.
- Каннибализация / ROI / маржа промокодов (вариант C из брейнсторма) — позже, отдельный план.
- Telegram / Notion уведомления — пользователь явно сказал «только Sheets».

## 12. Открытые вопросы

Все закрыты по итогам обсуждения:
- ✅ Сервер: новый `wb-promocodes-api` контейнер по образцу `wb-logistics-api`
- ✅ Дашборд: шапка в листе с timestamp + статусом + метриками
- ✅ Кнопка: GAS Drawing → POST /run
- ✅ Маппинг UUID: ручной справочник (UUID виден в WB UI)
- ✅ Bootstrap: 12 недель назад при первом запуске
- ✅ Уведомления: только Sheets, без Telegram/Notion

## 13. Критерии приёмки (UAT)

- [ ] После деплоя GAS-кнопка возвращает `{status: 'ok'}` в течение 5 минут.
- [ ] В листе `Промокоды_аналитика` появились строки за прошлую неделю по обоим кабинетам.
- [ ] CHARLOTTE10 в листе подтянуто из справочника по UUID `be6900f2-...`.
- [ ] Незаведённый UUID попадает в лист как «неизвестный», строка подсвечена жёлтым.
- [ ] Cron вторник 09:00 МСК отрабатывает без ручного вмешательства.
- [ ] Запись в `tools` Supabase создана; запуски видны в `tool_runs`.
- [ ] `docs/TOOLS_CATALOG.md` перегенерирован, новая запись присутствует.
