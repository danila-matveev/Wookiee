# План: WB/OZON/МойСклад → Google Sheets синхронизация

## Контекст

В Google Sheets (`19Nbr0kD8JJlwd7OCIMbM9qxucYNjmXnWtwJUgXv0vlg`) настроены скрипты (Google Apps Script), которые тянут данные из WB/OZON/МойСклад API. Скрипты создал другой человек, команда не может ими управлять. Задача — создать Python-скрипты в проекте Wookiee, которые заменят Google Apps Script и дадут полный контроль.

**Целевая таблица:** `19Nbr0kD8JJlwd7OCIMbM9qxucYNjmXnWtwJUgXv0vlg`

---

## Что сейчас в Google Sheets (изучено из таблицы)

| # | Лист | Источник API | Данные |
|---|------|-------------|--------|
| 1 | **МойСклад_АПИ** | **МойСклад JSON API 1.2** | Товары и остатки на собственном складе в Москве (товароучёт) |
| 2 | **WB остатки** | **WB Statistics API** | Остатки товаров на складах Wildberries |
| 3 | **WB цены** | **WB Content/Prices API** | Цены и скидки ~370 позиций (ООО + ИП) |
| 4 | **Ozon остатки и цены** | **OZON Seller API** | Остатки и цены товаров на OZON |
| 5 | **Отзывы ООО** | **WB Feedbacks API** | Рейтинг, кол-во отзывов по звёздам (кабинет ООО) |
| 6 | **Отзывы ИП** | **WB Feedbacks API** | То же для кабинета ИП Медведева |

**Важно:**
- Два кабинета WB — **ООО** и **ИП Медведева** (отдельные API-ключи)
- **МойСклад** — единая система товароучёта: товар → Excel → МойСклад → собственный склад в Москве

---

## Часть 1: Пошаговая настройка API

### 1.1. МойСклад API

**Что это:** Система товароучёта, хранит информацию о товарах и остатках на собственном складе.

**Шаг 1 — Получить токен:**
1. Войти в МойСклад → Настройки → Пользователи
2. Выбрать пользователя с правами на API
3. Токены доступа → Создать новый токен
4. Скопировать токен (он бессрочный)

**Альтернатива (через API):**
```
POST https://api.moysklad.ru/api/remap/1.2/security/token
Authorization: Basic <base64(login:password)>
```

**Шаг 2 — Проверить подключение:**
```bash
curl -X GET "https://api.moysklad.ru/api/remap/1.2/entity/organization" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Accept-Encoding: gzip"
```
Если вернулось JSON с организацией — токен работает.

**Шаг 3 — Сохранить в .env:**
```env
MOYSKLAD_TOKEN=your_bearer_token_here
```

**API справка:**
- Base URL: `https://api.moysklad.ru/api/remap/1.2`
- Auth: заголовок `Authorization: Bearer <token>`
- Обязательно: `Accept-Encoding: gzip`
- Пагинация: `limit` (max 1000), `offset`
- Остатки: `GET /report/stock/bystore` (по складам), `GET /report/stock/all` (по товарам)
- Товары: `GET /entity/product`
- Фильтры: `filter=store=<URL_склада>`, `stockMode=all`

---

### 1.2. WB API (Wildberries)

**Шаг 1 — Создать ключи (для КАЖДОГО кабинета: ООО и ИП):**
1. Войти в ЛК Wildberries → Настройки → Доступ к API
2. Создать ключ с правами:
   - **Статистика** → для остатков (`/api/v1/supplier/stocks`)
   - **Контент** → для цен
   - **Отзывы и вопросы** → для отзывов
3. Повторить для второго кабинета

**Шаг 2 — Проверить подключение:**
```bash
curl -X GET "https://statistics-api.wildberries.ru/api/v1/supplier/stocks?dateFrom=2026-01-01" \
  -H "Authorization: <API_KEY>"
```

**Шаг 3 — Сохранить в .env:**
```env
WB_API_KEY_OOO=key_for_ooo_cabinet
WB_API_KEY_IP=key_for_ip_cabinet
```

**API справка:**
- Statistics: `https://statistics-api.wildberries.ru` — остатки, заказы, продажи
- Content: `https://content-api.wildberries.ru` — цены, карточки
- Feedbacks: `https://feedbacks-api.wildberries.ru` — отзывы
- Auth: заголовок `Authorization: <api_key>` (без Bearer!)
- Rate limits: Statistics = 1 запрос/мин на эндпоинт, при 429 → ждать 60 сек

---

### 1.3. OZON API

**Шаг 1 — Получить ключи:**
1. Войти в ЛК OZON Seller → Настройки → API ключи
2. Создать ключ с правами на товары и остатки
3. Скопировать Client-Id и Api-Key

**Шаг 2 — Проверить подключение:**
```bash
curl -X POST "https://api-seller.ozon.ru/v2/product/list" \
  -H "Client-Id: <CLIENT_ID>" \
  -H "Api-Key: <API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"limit": 1}'
```

**Шаг 3 — Сохранить в .env:**
```env
OZON_CLIENT_ID=your_client_id
OZON_API_KEY=your_api_key
```

**API справка:**
- Base URL: `https://api-seller.ozon.ru`
- Auth: заголовки `Client-Id` + `Api-Key`
- Остатки: `POST /v2/product/info/stocks`
- Цены: `POST /v4/product/info/prices`

---

### 1.4. Google Sheets API

**Шаг 1 — Создать Service Account:**
1. Открыть [Google Cloud Console](https://console.cloud.google.com)
2. Создать проект (или использовать существующий)
3. APIs & Services → Enable API:
   - **Google Sheets API** — включить
   - **Google Drive API** — включить
4. Credentials → Create credentials → Service Account
5. Скачать JSON-ключ → сохранить как `credentials/google_sa.json`

**Шаг 2 — Расшарить таблицу:**
1. Открыть JSON-файл, найти поле `client_email` (вида `xxx@project.iam.gserviceaccount.com`)
2. Открыть Google Sheets таблицу → Поделиться → вставить email SA → дать права "Редактор"

**Шаг 3 — Сохранить в .env:**
```env
GOOGLE_SERVICE_ACCOUNT_FILE=credentials/google_sa.json
SPREADSHEET_ID=19Nbr0kD8JJlwd7OCIMbM9qxucYNjmXnWtwJUgXv0vlg
```

---

## Часть 2: Структура модуля

**Папка:** `wb_sheets_sync/` (в корне проекта)

```
wb_sheets_sync/
├── __init__.py
├── config.py                    — все ключи и настройки из .env
├── wb_client.py                 — клиент WB API
├── ozon_client.py               — клиент OZON Seller API
├── moysklad_client.py           — клиент МойСклад JSON API 1.2
├── sheets_client.py             — клиент Google Sheets (gspread)
│
├── sync_moysklad_stocks.py      — → лист "МойСклад_АПИ"
├── sync_wb_stocks.py            — → лист "WB остатки"
├── sync_wb_prices.py            — → лист "WB цены"
├── sync_ozon.py                 — → лист "Ozon остатки и цены"
├── sync_wb_feedbacks.py         — → листы "Отзывы ООО" и "Отзывы ИП"
│
├── runner.py                    — единый запуск: run_sync("moysklad_stocks") / run_all()
├── status.py                    — обновление листа "Статус синхронизации"
│
├── requirements.txt
├── .env.example
├── PLAN.md                      — этот файл
└── README.md
```

**Интеграция с ботом (новые файлы в `bot/`):**
```
bot/handlers/sync.py             — команды /sync, /sync_status
bot/services/sync_service.py     — сервис запуска sync-скриптов из бота
```

---

## Часть 3: API-клиенты

### 3.1. moysklad_client.py

```python
class MoySkladClient:
    BASE_URL = "https://api.moysklad.ru/api/remap/1.2"

    def __init__(self, token: str):
        self.session = httpx.Client(
            headers={
                "Authorization": f"Bearer {token}",
                "Accept-Encoding": "gzip",
            },
            timeout=30.0,
        )

    def get_stock_by_store(self) -> list[dict]:
        """GET /report/stock/bystore — остатки по складам.
        Пагинация: limit=1000, offset."""

    def get_products(self) -> list[dict]:
        """GET /entity/product — товары (артикул, штрихкод, доп. поля)."""
```

### 3.2. wb_client.py

```python
class WBClient:
    STATISTICS_BASE = "https://statistics-api.wildberries.ru"
    CONTENT_BASE = "https://content-api.wildberries.ru"
    FEEDBACKS_BASE = "https://feedbacks-api.wildberries.ru"

    def __init__(self, api_key: str):
        # Auth: Authorization: <api_key>
        # Retry при 429 через 60 сек

    def get_stocks(self, date_from) -> list[dict]:      # /api/v1/supplier/stocks
    def get_prices(self) -> list[dict]:                  # Content API
    def get_feedbacks_summary(self, nm_ids) -> list[dict]:  # Feedbacks API
```

### 3.3. ozon_client.py

```python
class OzonClient:
    BASE_URL = "https://api-seller.ozon.ru"

    def __init__(self, client_id: str, api_key: str):
        # Auth: Client-Id + Api-Key headers

    def get_stocks(self) -> list[dict]:    # POST /v2/product/info/stocks
    def get_prices(self) -> list[dict]:    # POST /v4/product/info/prices
```

### 3.4. sheets_client.py

```python
def get_client(credentials_file) -> gspread.Client
def write_dataframe(client, spreadsheet_id, sheet_name, df) -> None
    # Очистить лист → записать DataFrame (заголовки + данные)
def write_with_header(client, spreadsheet_id, sheet_name, header_rows, df) -> None
    # Записать строки метаданных (дата, время) + DataFrame
```

---

## Часть 4: Скрипты синхронизации

### 4.1. sync_moysklad_stocks.py → "МойСклад_АПИ"

**Источник:** МойСклад API `/report/stock/bystore`
**Логика:**
1. Получить остатки по складам из МойСклад (с пагинацией)
2. Получить товары (`/entity/product`) для артикулов, штрихкодов, доп. полей
3. Объединить данные: товар + остаток на складе
4. Записать в лист с метаданными (дата, время, итого)

### 4.2. sync_wb_stocks.py → "WB остатки"

**Источник:** WB Statistics API `/api/v1/supplier/stocks`
**Логика:**
1. Два вызова: ключ ООО + ключ ИП (с паузой из-за rate limit)
2. Pivot: строки = товары, колонки = склады WB
3. Добавить колонку "Кабинет"
4. Записать в лист с метаданными

### 4.3. sync_wb_prices.py → "WB цены"

**Источник:** WB Content/Prices API
**Логика:**
1. Два вызова: ООО + ИП
2. Объединить, добавить "Кабинет"
3. Записать в лист

### 4.4. sync_ozon.py → "Ozon остатки и цены"

**Источник:** OZON Seller API
**Логика:**
1. Получить остатки (`/v2/product/info/stocks`)
2. Получить цены (`/v4/product/info/prices`)
3. Объединить по offer_id
4. Записать в лист

### 4.5. sync_wb_feedbacks.py → "Отзывы ООО" + "Отзывы ИП"

**Источник:** WB Feedbacks API
**Логика:**
1. Для каждого кабинета: получить отзывы, агрегировать по nmID
2. Записать в соответствующий лист

### 4.6. runner.py — единый запуск

```python
SYNC_REGISTRY = {
    "moysklad_stocks": {"func": sync_moysklad_stocks.sync, "sheet": "МойСклад_АПИ"},
    "wb_stocks":       {"func": sync_wb_stocks.sync,       "sheet": "WB остатки"},
    "wb_prices":       {"func": sync_wb_prices.sync,       "sheet": "WB цены"},
    "ozon":            {"func": sync_ozon.sync,            "sheet": "Ozon остатки и цены"},
    "wb_feedbacks":    {"func": sync_wb_feedbacks.sync,    "sheet": "Отзывы ООО/ИП"},
}

async def run_sync(name: str) -> SyncResult:
    """Запуск одного скрипта по имени. Возвращает результат (status, rows, error, duration)."""

async def run_all() -> list[SyncResult]:
    """Запуск всех скриптов последовательно."""

# CLI-интерфейс:
# python -m wb_sheets_sync.runner moysklad_stocks
# python -m wb_sheets_sync.runner all
```

---

## Часть 5: Мониторинг и управление

### 5.1. Лист "Статус синхронизации" в Google Sheets

Автоматически обновляемый dashboard прямо в той же таблице:

| Скрипт | Лист | Последний запуск | Статус | Строк | Длительность | Ошибка |
|--------|------|-----------------|--------|-------|-------------|--------|
| moysklad_stocks | МойСклад_АПИ | 10.02.2026 13:00 | OK | 245 | 4.2 сек | — |
| wb_stocks | WB остатки | 10.02.2026 13:05 | OK | 1450 | 8.1 сек | — |
| wb_prices | WB цены | 10.02.2026 08:00 | OK | 370 | 3.5 сек | — |
| ozon | Ozon остатки и цены | 10.02.2026 08:00 | OK | 180 | 5.0 сек | — |
| wb_feedbacks | Отзывы ООО/ИП | 10.02.2026 09:00 | ОШИБКА | 0 | — | 429 Rate Limited |

**Файл:** `wb_sheets_sync/status.py`
- После каждого запуска sync-скрипта → обновить строку в листе "Статус синхронизации"
- Цветовая кодировка: зелёный = OK, красный = ошибка (через gspread format API)

### 5.2. Telegram-бот: команды управления

**Новый хендлер:** `bot/handlers/sync.py`

| Команда | Описание |
|---------|----------|
| `/sync` | Показать меню с кнопками для каждого скрипта |
| `/sync_status` | Показать статус всех скриптов (последний запуск, ошибки) |

**Inline-кнопки в `/sync`:**

```
Синхронизация данных

МойСклад остатки      [Запустить]
WB остатки             [Запустить]
WB цены                [Запустить]
OZON остатки и цены    [Запустить]
WB отзывы              [Запустить]
━━━━━━━━━━━━━━━━━━━━━━━
Запустить все           [Запустить все]
```

При нажатии кнопки:
1. Бот отвечает "Запускаю sync_wb_stocks..."
2. Запускает `runner.run_sync("wb_stocks")` асинхронно
3. По завершении обновляет сообщение: "WB остатки обновлены (1450 строк, 8.1 сек)" или "Ошибка: 429 Rate Limited"
4. Обновляет лист "Статус синхронизации"

**Команда `/sync_status`:**
```
Статус синхронизации

МойСклад остатки   — 10.02 13:00 — 245 строк — OK
WB остатки          — 10.02 13:05 — 1450 строк — OK
WB цены             — 10.02 08:00 — 370 строк — OK
OZON                — 10.02 08:00 — 180 строк — OK
WB отзывы           — 10.02 09:00 — ОШИБКА: 429 Rate Limited
```

**Сервис:** `bot/services/sync_service.py`
```python
class SyncService:
    """Обёртка для запуска sync-скриптов из бота."""

    async def run(self, sync_name: str) -> SyncResult
    async def run_all(self) -> list[SyncResult]
    async def get_status() -> list[SyncStatus]
```

### 5.3. Автоматические алерты при сбоях

При ошибке sync-скрипта → автоматическое сообщение в Telegram всем авторизованным пользователям:

```
Ошибка синхронизации

Скрипт: wb_stocks (WB остатки)
Время: 10.02.2026 13:05
Ошибка: 429 Rate Limited — WB API превышен лимит запросов

Повторный запуск через 5 минут...

[Перезапустить сейчас]
```

Кнопка "Перезапустить сейчас" — inline callback, который повторно вызывает `runner.run_sync()`.

### 5.4. Логирование

Каждый запуск записывается в Python logger:
```
2026-02-10 13:00:03 INFO  [sync_moysklad_stocks] Starting sync...
2026-02-10 13:00:05 INFO  [sync_moysklad_stocks] Fetched 245 products from MoySklad
2026-02-10 13:00:06 INFO  [sync_moysklad_stocks] Written 245 rows to sheet "МойСклад_АПИ"
2026-02-10 13:00:07 INFO  [sync_moysklad_stocks] Completed in 4.2 sec
```

---

## Часть 6: Автоматическое расписание

### Через APScheduler (в боте)

Sync-скрипты добавляются в существующий `scheduler_service.py` бота:

| Скрипт | Частота | Время (МСК) |
|--------|---------|-------------|
| sync_moysklad_stocks | 2-3 раза/день | 07:00, 13:00, 19:00 |
| sync_wb_stocks | 2-3 раза/день | 07:05, 13:05, 19:05 |
| sync_wb_prices | 1 раз/день | 08:00 |
| sync_ozon | 2 раза/день | 08:00, 18:00 |
| sync_wb_feedbacks | 1 раз/неделю | Пн 09:00 |

**Почему через бот:** APScheduler уже настроен и работает 24/7. Не нужен отдельный cron или сервис. Плюс сразу доступны алерты через Telegram.

**Регистрация в `bot/main.py`:**
```python
# Добавить в метод setup_scheduler():
from wb_sheets_sync.runner import run_sync

self.scheduler.scheduler.add_job(
    lambda: run_sync("moysklad_stocks"),
    trigger=CronTrigger(hour="7,13,19", timezone="Europe/Moscow"),
    id="sync_moysklad_stocks",
    replace_existing=True,
)
# ... аналогично для остальных
```

### Возможность ручного перезапуска

Помимо автоматического расписания:
1. **Telegram**: `/sync` → кнопка → мгновенный запуск
2. **CLI**: `python -m wb_sheets_sync.runner moysklad_stocks`
3. **Google Sheets**: лист "Статус синхронизации" показывает когда последний раз запускался каждый скрипт

---

## Часть 7: Зависимости

### requirements.txt (в wb_sheets_sync/)
```
gspread>=6.0.0
google-auth>=2.20.0
httpx>=0.27.0
pandas>=2.0.0
python-dotenv>=1.0.0
```

### .env.example
```env
# МойСклад API
MOYSKLAD_TOKEN=your_bearer_token_here

# Wildberries API (два кабинета)
WB_API_KEY_OOO=your_key_here
WB_API_KEY_IP=your_key_here

# OZON API
OZON_CLIENT_ID=your_client_id
OZON_API_KEY=your_key_here

# Google Sheets
GOOGLE_SERVICE_ACCOUNT_FILE=credentials/google_sa.json
SPREADSHEET_ID=19Nbr0kD8JJlwd7OCIMbM9qxucYNjmXnWtwJUgXv0vlg
```

---

## Что нужно от пользователя для старта

| # | Что | Где получить | Инструкция |
|---|-----|-------------|-----------|
| 1 | МойСклад токен | Настройки → Пользователи → Токены | Часть 1.1 |
| 2 | WB API ключ (ООО) | ЛК WB → API → Статистика + Контент + Отзывы | Часть 1.2 |
| 3 | WB API ключ (ИП) | ЛК WB (кабинет ИП) → API | Часть 1.2 |
| 4 | OZON Client-Id + Api-Key | ЛК OZON → API ключи | Часть 1.3 |
| 5 | Google Service Account JSON | Google Cloud Console | Часть 1.4 |
| 6 | (Опц.) Код текущих GAS-скриптов | Google Apps Script editor | Для воспроизведения точной логики |

---

## Порядок реализации

| Фаза | Что делаем | Файлы | Результат |
|------|-----------|-------|-----------|
| 1 | Инфраструктура: config, clients, sheets | config.py, sheets_client.py, wb_client.py, moysklad_client.py, ozon_client.py | Подключение ко всем API работает |
| 2 | Первый sync: МойСклад остатки | sync_moysklad_stocks.py, runner.py, status.py | Лист "МойСклад_АПИ" обновляется |
| 3 | WB остатки | sync_wb_stocks.py | Лист "WB остатки" обновляется |
| 4 | WB цены + OZON | sync_wb_prices.py, sync_ozon.py | Листы "WB цены" и "Ozon" обновляются |
| 5 | Отзывы | sync_wb_feedbacks.py | Листы "Отзывы ООО/ИП" обновляются |
| 6 | Telegram управление | bot/handlers/sync.py, bot/services/sync_service.py | Команды /sync, /sync_status работают |
| 7 | Автоматическое расписание + алерты | Обновить bot/main.py (scheduler) | Данные обновляются по расписанию, ошибки приходят в Telegram |
| 8 | Сверка → отключение GAS | — | Параллельный запуск, сравнение данных, отключение старых скриптов |

---

## Критические файлы

| Файл | Действие |
|------|----------|
| wb_sheets_sync/__init__.py | Создать |
| wb_sheets_sync/config.py | Создать |
| wb_sheets_sync/wb_client.py | Создать |
| wb_sheets_sync/ozon_client.py | Создать |
| wb_sheets_sync/moysklad_client.py | Создать |
| wb_sheets_sync/sheets_client.py | Создать |
| wb_sheets_sync/sync_moysklad_stocks.py | Создать |
| wb_sheets_sync/sync_wb_stocks.py | Создать |
| wb_sheets_sync/sync_wb_prices.py | Создать |
| wb_sheets_sync/sync_ozon.py | Создать |
| wb_sheets_sync/sync_wb_feedbacks.py | Создать |
| wb_sheets_sync/runner.py | Создать |
| wb_sheets_sync/status.py | Создать |
| wb_sheets_sync/requirements.txt | Создать |
| wb_sheets_sync/.env.example | Создать |
| wb_sheets_sync/README.md | Создать |
| bot/handlers/sync.py | Создать |
| bot/services/sync_service.py | Создать |
| bot/main.py | Обновить (добавить sync router + scheduler jobs) |
| agents/wb-sheets-sync.md | Создать (описание агента) |
| agents/README.md | Обновить |
| README.md | Обновить |

---

## Верификация

1. **API подключения:** Проверить curl-запросами к каждому API (МойСклад, WB, OZON, Google Sheets)
2. **Первый sync:** `python -m wb_sheets_sync.runner moysklad_stocks` → данные в листе "МойСклад_АПИ"
3. **Все sync:** `python -m wb_sheets_sync.runner all` → все 6 листов обновлены
4. **Статус лист:** Лист "Статус синхронизации" показывает результаты всех запусков
5. **Telegram /sync:** Отправить `/sync` → нажать кнопку → скрипт запускается → статус обновляется
6. **Telegram /sync_status:** Показывает актуальный статус всех скриптов
7. **Алерты:** Имитировать сбой (невалидный ключ) → сообщение об ошибке приходит в Telegram
8. **Расписание:** Запустить бот → через время проверить что sync отрабатывает по расписанию
9. **Сравнение с GAS:** Сравнить данные от Python-скриптов с текущими данными от Google Apps Script
