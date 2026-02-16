# Sheets Sync — Документация проекта

> Система синхронизации данных из API маркетплейсов (WB, OZON, МойСклад) в Google Sheets.
> Заменяет 11 оригинальных Google Apps Script скриптов на Python.

---

## Оглавление

1. [Архитектура](#архитектура)
2. [Структура файлов](#структура-файлов)
3. [Конфигурация (config.py)](#конфигурация)
4. [Клиенты API](#клиенты-api)
   - [sheets_client.py — Google Sheets](#sheets_clientpy)
   - [wb_client.py — Wildberries](#wb_clientpy)
   - [ozon_client.py — OZON](#ozon_clientpy)
   - [moysklad_client.py — МойСклад](#moysklad_clientpy)
5. [Sync-скрипты](#sync-скрипты)
   - [sync_moysklad.py — МойСклад_АПИ](#sync_moyskaldpy)
   - [sync_wb_stocks.py — WB остатки](#sync_wb_stockspy)
   - [sync_wb_prices.py — WB Цены](#sync_wb_pricespy)
   - [sync_wb_feedbacks.py — Отзывы](#sync_wb_feedbackspy)
   - [sync_wb_bundles.py — Склейки WB](#sync_wb_bundlespy)
   - [sync_ozon_stocks_prices.py — Ozon остатки и цены](#sync_ozon_stocks_pricespy)
   - [sync_ozon_bundles.py — Склейки Озон](#sync_ozon_bundlespy)
   - [sync_search_analytics.py — Аналитика по запросам](#sync_search_analyticspy)
6. [Инфраструктура](#инфраструктура)
   - [runner.py — CLI-запуск](#runnerpy)
   - [status.py — Статус синхронизации](#statuspy)
   - [control_panel.py — Панель управления](#control_panelpy)
7. [Google Sheets: листы и форматы](#google-sheets-листы)
8. [Внешние API: эндпоинты](#внешние-api-эндпоинты)
9. [Запуск и использование](#запуск-и-использование)
10. [Переменные окружения (.env)](#переменные-окружения)
11. [Механизм кнопок обновления](#механизм-кнопок-обновления)

---

## Архитектура

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  WB API          │     │  OZON API        │     │  МойСклад API    │
│  (2 кабинета:    │     │  (2 кабинета:    │     │  (1 токен)       │
│   ИП + ООО)      │     │   ИП + ООО)      │     │                  │
└────────┬─────────┘     └────────┬─────────┘     └────────┬─────────┘
         │                        │                        │
    ┌────▼────┐             ┌─────▼─────┐           ┌──────▼──────┐
    │WBClient │             │OzonClient │           │MoySkladClient│
    └────┬────┘             └─────┬─────┘           └──────┬──────┘
         │                        │                        │
    ┌────▼────────────────────────▼────────────────────────▼────┐
    │                    Sync-скрипты (8 шт.)                   │
    │  sync_wb_stocks, sync_wb_prices, sync_wb_feedbacks,       │
    │  sync_wb_bundles, sync_ozon_stocks_prices,                │
    │  sync_ozon_bundles, sync_moysklad, sync_search_analytics  │
    └─────────────────────────┬────────────────────────────────┘
                              │
                     ┌────────▼────────┐
                     │  sheets_client  │
                     │  (gspread)      │
                     └────────┬────────┘
                              │
                     ┌────────▼────────┐
                     │  Google Sheets  │
                     │  (1 spreadsheet)│
                     └─────────────────┘
```

**Поток данных:**
1. `runner.py` или `control_panel.py` вызывает `sync()` из нужного скрипта
2. Sync-скрипт создает API-клиент, запрашивает данные
3. Данные обрабатываются, нормализуются
4. Через `sheets_client.py` записываются в Google Sheets
5. Результат (SyncResult) записывается в лист "Статус синхронизации"

---

## Структура файлов

```
services/sheets_sync/
├── __init__.py                          # Пустой
├── __main__.py                          # Точка входа: вызывает runner.main()
├── config.py                            # Конфигурация, кабинеты, env
├── runner.py                            # CLI-запуск, реестр скриптов
├── status.py                            # Лист "Статус синхронизации"
├── control_panel.py                     # Polling + расписание + checkbox
├── DOCUMENTATION.md                     # ← Этот файл
│
├── clients/                             # (Локальные копии, НЕ используются)
│   ├── __init__.py
│   ├── sheets_client.py
│   ├── wb_client.py
│   ├── ozon_client.py
│   └── moysklad_client.py
│
└── sync/                                # 8 sync-скриптов
    ├── __init__.py
    ├── sync_moysklad.py                 # МойСклад_АПИ
    ├── sync_wb_stocks.py                # WB остатки
    ├── sync_wb_prices.py                # WB Цены
    ├── sync_wb_feedbacks.py             # Отзывы ООО / Отзывы ИП
    ├── sync_wb_bundles.py               # Склейки WB
    ├── sync_ozon_stocks_prices.py       # Ozon остатки и цены
    ├── sync_ozon_bundles.py             # Склейки Озон
    └── sync_search_analytics.py         # Аналитика по запросам (2 листа)

shared/clients/                          # ← Фактически используемые клиенты
├── sheets_client.py
├── wb_client.py
├── ozon_client.py
└── moysklad_client.py
```

> **Важно:** Импорты идут из `shared.clients.*`, а не из `services.sheets_sync.clients.*`.

---

## Конфигурация

### `config.py`

**Путь:** `services/sheets_sync/config.py`

| Элемент | Тип | Описание |
|---------|-----|----------|
| `Cabinet` | `@dataclass` | Кабинет маркетплейса: `name`, `wb_api_key`, `ozon_client_id`, `ozon_api_key` |
| `CABINET_IP` | `Cabinet` | Кабинет ИП (ключи из `.env`: `WB_API_KEY_IP`, `OZON_CLIENT_ID_IP`, `OZON_API_KEY_IP`) |
| `CABINET_OOO` | `Cabinet` | Кабинет ООО (ключи из `.env`: `WB_API_KEY_OOO`, `OZON_CLIENT_ID_OOO`, `OZON_API_KEY_OOO`) |
| `ALL_CABINETS` | `list[Cabinet]` | `[CABINET_IP, CABINET_OOO]` |
| `MOYSKLAD_TOKEN` | `str` | Bearer-токен МойСклад (из `MOYSKLAD_TOKEN`) |
| `GOOGLE_SA_FILE` | `str` | Путь к JSON ключу Google Service Account |
| `SPREADSHEET_ID` | `str` | ID Google Spreadsheet |
| `TEST_MODE` | `bool` | `SYNC_TEST_MODE=true` → суффикс `_TEST` к именам листов |
| `LOG_LEVEL` | `str` | Уровень логирования (default: `INFO`) |

#### Функции

```python
def get_sheet_name(base_name: str) -> str
```
Возвращает имя листа с суффиксом `_TEST`, если `TEST_MODE=True`.

---

## Клиенты API

### `sheets_client.py`

**Путь:** `shared/clients/sheets_client.py`
**Назначение:** Обертка над gspread для работы с Google Sheets.

#### Функции

```python
def get_client(sa_file: str) -> gspread.Client
```
Создает аутентифицированный gspread-клиент из JSON-файла Service Account.

---

```python
def get_moscow_now() -> datetime
```
Текущее время в часовом поясе `Europe/Moscow`.

---

```python
def get_moscow_datetime() -> tuple[str, str]
```
Возвращает `(дата "DD.MM.YYYY", время "HH:MM")` по Москве.

---

```python
def to_number(value) -> int | float | str
```
Конвертирует строку в число (`int` или `float`).

**Критично для Google Sheets:**
- Python `float` → Sheets хранит как число → отображает с запятой (правильно)
- Python `str "4.90"` → Sheets хранит как текст → отображает с точкой (неправильно)

Обрабатывает: пробелы, неразрывные пробелы (`\xa0`), запятые вместо точек, апострофы.

---

```python
def set_checkbox(ws: gspread.Worksheet, cell: str = "C1") -> None
```
Создает checkbox (Data Validation Boolean) в ячейке. Используется как кнопка обновления на листах. Значение устанавливается в `"FALSE"`.

---

```python
def get_or_create_worksheet(spreadsheet, name: str, rows: int = 1000, cols: int = 50) -> Worksheet
```
Получает лист по имени. Если не существует — создает.

---

```python
def clear_and_write(
    worksheet, headers: list[str], data: list[list],
    meta_cells: list[tuple[int, int, str]] | None = None,
    header_row: int = 3, data_start_row: int = 4
) -> int
```
Очищает лист от `header_row` вниз, записывает мета-ячейки, заголовки, данные.

**Параметры:**
- `meta_cells` — список `(row, col, value)` для метаданных (дата/время)
- `header_row` — строка для заголовков (по умолчанию 3)
- `data_start_row` — строка начала данных (по умолчанию 4)

**Возвращает:** количество записанных строк данных.

---

```python
def write_range(worksheet, start_row: int, start_col: int, data: list[list]) -> None
```
Записывает блок данных начиная с `(start_row, start_col)`.

---

```python
def _cell_ref(row: int, col: int) -> str
```
Приватная. Конвертирует `(row, col)` в A1-нотацию. Пример: `(3, 27)` → `"AA3"`.

---

### `wb_client.py`

**Путь:** `shared/clients/wb_client.py`
**Назначение:** Клиент Wildberries API.

#### Класс `WBClient`

**Конструктор:**
```python
def __init__(self, api_key: str, cabinet_name: str)
```

**API Endpoints:**
| Константа | URL |
|-----------|-----|
| `ANALYTICS_BASE` | `https://seller-analytics-api.wildberries.ru` |
| `STATISTICS_BASE` | `https://statistics-api.wildberries.ru` |
| `PRICES_BASE` | `https://discounts-prices-api.wildberries.ru` |
| `FEEDBACKS_BASE` | `https://feedbacks-api.wildberries.ru` |

#### Методы

```python
def get_warehouse_remains(self) -> list[dict]
```
**Асинхронный отчет:** создать задачу → ожидать готовности (poll каждые 15с, до 100 попыток) → ожидание 60с → скачать.
Возвращает список товаров, каждый с массивом `warehouses`.

**Используется в:** `sync_wb_stocks.py`

---

```python
def get_prices(self) -> list[dict]
```
Пагинированный запрос цен (limit=1000). Каждый элемент: `nmID`, `vendorCode`, `discount`, `sizes`.

**Используется в:** `sync_wb_prices.py`, `sync_wb_bundles.py`

---

```python
def get_all_feedbacks(self) -> list[dict]
```
Все отзывы (answered + unanswered) с пагинацией (take=5000).

**Используется в:** `sync_wb_feedbacks.py`

---

```python
def get_supplier_orders(self, date_from: str, flag: int = 0) -> list[dict]
```
Заказы из Statistics API с пагинацией (до 60000 строк за запрос). Включает `warehouseName`, `oblast`, `supplierArticle`, `techSize`, `nmId`, `isCancel`.

**Используется в:** `sync_search_analytics.py` (опционально)

---

```python
def _request(self, method: str, url: str, retries: int = 3, **kwargs) -> dict | list | None
```
Приватная. HTTP-запрос с retry на 429 (rate limit, ожидание 60с).

---

### `ozon_client.py`

**Путь:** `shared/clients/ozon_client.py`
**Назначение:** Клиент OZON Seller API (через отчеты).

#### Класс `OzonClient`

**Конструктор:**
```python
def __init__(self, client_id: str, api_key: str, cabinet_name: str)
```

**Base URL:** `https://api-seller.ozon.ru`

#### Методы

```python
def get_stocks_and_prices_report(self, skus: list[int]) -> list[list[str]]
```
**Полный цикл:** создать отчет → poll (каждые 5с, до 12 попыток) → скачать CSV → парсинг.
Поддерживает батчи по 1000 SKU. Возвращает список строк (первая строка — заголовки).

**Используется в:** `sync_ozon_stocks_prices.py`, `sync_ozon_bundles.py`

---

```python
def _create_report(self, skus: list[int]) -> str | None
```
Приватная. `POST /v1/report/products/create` → код отчета.

---

```python
def _check_report(self, code: str) -> str | None
```
Приватная. `POST /v1/report/info` → URL файла если готов.

---

```python
def _download_and_parse_csv(self, url: str) -> list[list[str]]
```
Приватная. Скачивает CSV, парсит с разделителем `;`, обрабатывает BOM и апострофы.

---

### `moysklad_client.py`

**Путь:** `shared/clients/moysklad_client.py`
**Назначение:** Клиент МойСклад JSON API 1.2.

#### Класс `MoySkladClient`

**Конструктор:**
```python
def __init__(self, token: str)
```

**Base URL:** `https://api.moysklad.ru/api/remap/1.2`

**Константы:**
| Константа | Значение | Описание |
|-----------|----------|----------|
| `STORE_MAIN` | `4c51ead2-...` | UUID основного склада |
| `STORE_ACCEPTANCE` | `6281f079-...` | UUID склада приемки |
| `ATTRIBUTES_ORDER` | список 32 шт. | Порядок атрибутов для колонок |
| `ADDITIONAL_COLUMNS_START` | `39` | Начальная колонка доп. данных (AM) |
| `ADDITIONAL_COLUMNS` | список 4 шт. | Остатки офис/приемка/транзит/себестоимость |
| `STATE_COMPLETED_HREF` | URL | Href статуса "Выполнен" для фильтрации заказов |

#### Методы

```python
def fetch_assortment(self, moment: str = "", store_url: str = "") -> list[dict]
```
Пагинированный `/entity/assortment` (limit=500, до 20 страниц). Фильтры: `stockMoment`, `stockStore`.

**Используется в:** `sync_moysklad.py` (основные данные + остатки офиса)

---

```python
def fetch_stock_by_store(self, store_id: str) -> list[dict]
```
Пагинированный `/report/stock/bystore` для конкретного склада (limit=1000).

**Используется в:** `sync_moysklad.py` (остатки приемки)

---

```python
def fetch_stock_all(self) -> list[dict]
```
Пагинированный `/report/stock/all` (limit=1000). Содержит поле `price` (себестоимость в копейках).

**Используется в:** `sync_moysklad.py` (себестоимость)

---

```python
def fetch_purchase_orders(self) -> list[dict]
```
Пагинированные заказы поставщику (limit=100, до 20 страниц).
Фильтрует: только заказы с `state` (существует) и НЕ в статусе "Выполнен".

**Используется в:** `sync_moysklad.py` (товары в пути)

---

```python
def fetch_order_positions(self, order_id: str) -> list[dict]
```
Пагинированные позиции заказа (limit=1000, до 10 страниц).

**Используется в:** `sync_moysklad.py` (товары в пути — количества)

---

```python
def extract_attributes(self, product: dict) -> list[str]
```
Извлекает 32 атрибута из товара в порядке `ATTRIBUTES_ORDER`. Обрабатывает кастомные типы (dict с `name`).

---

```python
def extract_barcodes(self, product: dict) -> tuple[str, str]
```
Извлекает `(EAN13, GTIN)` из массива `barcodes` товара.

---

## Sync-скрипты

Каждый sync-скрипт экспортирует единственную функцию:

```python
def sync(**kwargs) -> int  # Количество записанных строк
```

---

### `sync_moysklad.py`

**Путь:** `services/sheets_sync/sync/sync_moysklad.py`
**Лист:** `МойСклад_АПИ`
**Оригинальный GAS:** `Обновление МойСклад.js`

#### Формат листа

| Строка | Содержимое |
|--------|-----------|
| Row 1 | A1 = datetime (`YYYY-MM-DD HH:MM:SS`), B1 = кнопка (вставленная картинка), C1 = checkbox |
| Row 2 | 42 заголовка (A-AP) |
| Row 3+ | Данные |

#### Колонки (42 шт.)

A-AL (38 основных): Артикул Ozon, Product ID, Баркод, EAN13, GTIN, Нуменклатура, Артикул, Модель, Название для Этикетки, Ozon >>, Артикул Ozon (2), Ozon Product ID, FBO OZON SKU ID, Размер, Цвет, О товаре >>>, Продавец, Фабрика, Состав, ТНВЭД, SKU, Сolor, Color code, Price, Вес, Длина, Ширина, Высота, Объем, Кратность короба, Импортер, Адрес Импортера, Статус WB, Статус OZON, Склейка на WB, Категория, Модель основа, Коллекция

AM-AP (4 дополнительных): Остатки в офисе, Товары с приемкой, Товары в пути, Себестоимость

#### Функция `sync() -> int`

1. Получает datetime по Москве
2. `fetch_assortment(moment=...)` — все товары (пагинация)
3. Фильтрует: `"attributes" in row` AND `len(barcodes) > 1`
4. Обрабатывает каждую строку в 38 колонок через `_process_row()`
5. Очищает лист от row 3 вниз (сохраняет row 1-2!)
6. Записывает: A1=datetime, row 2=заголовки, row 3+=данные
7. Устанавливает checkbox C1
8. Записывает 4 доп. колонки через `_write_additional_data()`

#### Приватные функции

```python
def _process_row(row: dict, ms: MoySkladClient) -> list | None
```
Обрабатывает один товар МойСклад в 38-колоночный формат. Извлекает атрибуты, баркоды, нормализует цену.

---

```python
def _write_additional_data(ms, ws, product_ids, formatted_date) -> None
```
Записывает 4 доп. колонки (AM-AP):
1. **Остатки в офисе** — `fetch_assortment(store=STORE_MAIN)`
2. **Товары с приемкой** — `fetch_stock_by_store(STORE_ACCEPTANCE + STORE_MAIN)`
3. **Товары в пути** — `fetch_purchase_orders()` + `fetch_order_positions()` для каждого заказа
4. **Себестоимость** — `fetch_stock_all()`, цена в копейках → рубли (`/ 100`)

---

```python
def _build_id_value_map(data, field, is_cost=False) -> dict
```
Строит `{product_id: value}`. Если `is_cost=True`, конвертирует копейки в рубли.

---

```python
def _build_stock_map(data) -> dict
```
Строит `{product_id: stock}` из данных `/report/stock/bystore`. Суммирует по одинаковым ID.

---

```python
def _normalize_price(value) -> float
```
Нормализует цену: убирает символы валют (¥€$₽), заменяет запятую на точку, `round(x, 2)`.

---

```python
def _col_letter(col: int) -> str
```
Номер колонки → буква. `1→A`, `27→AA`.

---

### `sync_wb_stocks.py`

**Путь:** `services/sheets_sync/sync/sync_wb_stocks.py`
**Лист:** `WB остатки`
**Оригинальный GAS:** `Обновление WB остатки.js`

#### Формат листа

| Строка | Содержимое |
|--------|-----------|
| Row 1 | A1="Дата составления", B1=дата |
| Row 2 | A2="Время отчёт", B2=время, I2-K2=суммы по спецскладам |
| Row 3 | Заголовки: Баркод, Артикул, Размер, NMID, Категория, Бренд, Объем, Кабинет, [склады...] |
| Row 4+ | Данные |

#### Функция `sync() -> int`

1. Запрашивает `get_warehouse_remains()` из обоих кабинетов (ИП + ООО)
2. Собирает уникальные склады. Порядок: спецсклады первые ("В пути до получателей", "В пути возвраты на склад WB", "Всего находится на складах"), затем остальные по алфавиту
3. Строит pivot-таблицу: уникальные баркоды × склады
4. Записывает через `clear_and_write(header_row=3, data_start_row=4)`
5. Записывает суммы спецскладов в row 2 (cols I-K)
6. Устанавливает checkbox C1

**Особенности:**
- `nmId` конвертируется в `int`, `volume` в `float`
- Данные агрегируются по баркоду через все кабинеты

---

### `sync_wb_prices.py`

**Путь:** `services/sheets_sync/sync/sync_wb_prices.py`
**Лист:** `WB Цены`
**Оригинальный GAS:** `Обновление WB цены.js`

#### Формат листа

| Строка | Содержимое |
|--------|-----------|
| Row 1 | A1 = `"{дата} {время} \| Два кабинета"` |
| Row 2-3 | Пустые (зарезервированы) |
| Row 4 | Заголовки: nmID, Артикул, Кабинет, Цена, Скидка % |
| Row 5+ | Данные |

#### Функция `sync() -> int`

1. `get_prices()` из обоих кабинетов (пагинация, limit=1000)
2. Для каждого товара: `[nmID, vendorCode, cabinet.name, price, discount]`
3. `discount` — целое число (15, не 0.15)
4. `clear_and_write(header_row=4, data_start_row=5)`
5. Checkbox C1

---

### `sync_wb_feedbacks.py`

**Путь:** `services/sheets_sync/sync/sync_wb_feedbacks.py`
**Листы:** `Отзывы ООО`, `Отзывы ИП`
**Оригинальный GAS:** `Скрипт для получения отзывов.js`

#### Формат листа (для каждого кабинета отдельный)

| Строка | Содержимое |
|--------|-----------|
| Row 1 | A1="Дата составления отчёта", B1=дата |
| Row 2 | A2="Время отчёта", B2=время |
| Row 4 | A4="С" |
| Row 5 | A5="01.01.2020", B5=текущая_дата |
| Row 11 | D11="Отзывы, в штуках" |
| Row 12 | C12="Рейтинг", D12="5★", E12="4★", F12="3★", G12="2★", H12="1★" |
| Row 13+ | A=Кабинет, B=nmID, C=avg_rating, D-H=количество по звездам (5→1) |

#### Функция `sync() -> int`

1. Для каждого кабинета:
   - `get_all_feedbacks()` (answered + unanswered, пагинация)
   - `_aggregate_feedbacks()` — группировка по nmId
   - Сортировка по количеству отзывов (desc)
   - `ws.clear()` — полная очистка (формат не сохраняется)
   - Запись мета-строк, заголовков, данных
   - Checkbox C1

**Важно:** nmID формируются из ответа API, а не из листа.

#### Приватные функции

```python
def _aggregate_feedbacks(feedbacks: list[dict]) -> dict
```
Группирует отзывы по `nmId`. Возвращает `{nmId: {1: count, 2: count, ..., 5: count, avg: float, total: int}}`.

---

### `sync_wb_bundles.py`

**Путь:** `services/sheets_sync/sync/sync_wb_bundles.py`
**Лист:** `Склейки WB`
**Оригинальный GAS:** `Обновление Склейки WB.js`

#### Функция `sync() -> int`

1. `get_prices()` из обоих кабинетов
2. Строит `price_map: {nmID: {price, discount, discountedPrice, clubDiscount}}`
3. Читает nmID из колонки D (D3+) листа
4. Если колонка пуста → `return 0` с info-логом (не warning)
5. Записывает в колонки S-V (19-22): price, discount, discountedPrice, clubDiscount
6. S1 = `"{время} {дата}"`

**Особенность:** НЕ очищает весь лист, только колонки S-V от row 3.

---

### `sync_ozon_stocks_prices.py`

**Путь:** `services/sheets_sync/sync/sync_ozon_stocks_prices.py`
**Лист:** `Ozon остатки и цены`
**Оригинальный GAS:** `Обновление Ozon остатки и цены.js`

#### Формат листа

| Строка | Содержимое |
|--------|-----------|
| Row 1 | A1="Дата составления отчёта", B1=дата |
| Row 2 | A2="Время отчёта", B2=время |
| Row 3 | 30 заголовков |
| Row 4+ | Данные |

#### Заголовки (30 колонок)

Артикул, Ozon Product ID, SKU, Barcode, Название товара, Контент-рейтинг, Бренд, Статус товара, Метки, Отзывы, Рейтинг, Видимость на Ozon, Причины скрытия, Дата создания, Категория, Тип, Объем товара (л), Объемный вес (кг), FBO (шт.), Зарезервировано (шт), FBS (шт.), realFBS (шт.), Зарезервировано на моих складах (шт), Текущая цена со скидкой (₽), Цена до скидки (₽), Цена Premium (₽), Размер НДС (%), Ошибки, Предупреждения, Кабинет

#### Функция `sync() -> int`

1. Читает SKU из листа "Все товары" (`_get_skus_from_all_products()`)
2. Для каждого кабинета: `get_stocks_and_prices_report(skus)` — через CSV-отчет
3. Нормализация до 30 колонок
4. Конвертация числовых колонок через `to_number()` (индексы: 1,2,5,9,10,16-26)
5. `clear_and_write(header_row=3, data_start_row=4)`
6. Checkbox C1

#### Приватные функции

```python
def _get_skus_from_all_products(spreadsheet) -> dict[str, list[int]]
```
Читает лист "Все товары", находит колонки "FBO OZON SKU ID" и "Импортер", разбивает SKU по кабинетам (ИП/ООО). Определение кабинета: "ИП"/"Медведева" → ИП, "ООО"/"Вуки" → ООО.

---

### `sync_ozon_bundles.py`

**Путь:** `services/sheets_sync/sync/sync_ozon_bundles.py`
**Лист:** `Склейки Озон`
**Оригинальный GAS:** `Обновление Склейки Озон.js`

#### Функция `sync() -> int`

1. Читает кабинет из колонки A, артикул (SKU) из колонки E (row 3+)
2. Группирует артикулы по кабинетам
3. Очищает колонки R, S, V от row 3
4. Для каждого кабинета: `get_stocks_and_prices_report(skus)` → парсит CSV
5. Записывает: R(18)=цена до скидки, S(19)=цена со скидкой, V(22)=FBO остаток

**Особенность:** НЕ очищает весь лист, только целевые колонки.

#### Приватные функции

```python
def _find_col(headers, exact, fallback) -> int | None
```
Поиск колонки: сначала точное совпадение, затем partial match.

```python
def _parse_number(value) -> float
def _parse_int(value) -> int
```
Парсинг чисел из CSV с обработкой апострофов и запятых.

---

### `sync_search_analytics.py`

**Путь:** `services/sheets_sync/sync/sync_search_analytics.py`
**Листы:** `Аналитика по запросам`, `Аналитика по запросам (поартикульно)`
**Оригинальный GAS:** `Аналитика по запросам.js`

#### Функция `sync(start_date=None, end_date=None) -> int`

Запускает два подотчета:
1. `_sync_search_words()` — агрегация по ключевым словам
2. `_sync_artikul()` — поартикульная разбивка

**Принимает даты в формате DD.MM.YYYY.** Если не заданы — берет из листа или авто (прошлая неделя).

#### Подотчет 1: Аналитика по запросам

**Лист:** `Аналитика по запросам`

- Читает поисковые слова из колонки A (A3+)
- Загружает маппинг подмены из A:B (для фильтрации переходов)
- Запрашивает WB Search API для обоих кабинетов
- Агрегирует: частота, переходы, добавления в корзину, заказы
- Записывает в первые свободные колонки (не очищает старые данные — накопительный формат)

#### Подотчет 2: Поартикульно

**Лист:** `Аналитика по запросам (поартикульно)`

- Очищает от row 4
- Для каждого кабинета: WB Search API → 10 колонок на строку
- Колонки: текст, nmId, openCard, addToCart, openToCart%, orders, cartToOrder%, startDate, endDate, cabinet

#### Приватные функции

```python
def _analyze_cabinet_search_words(cabinet_name, api_start, api_end, search_words, mapping) -> dict
```
Анализирует ключевые слова для одного кабинета. Фильтрует переходы через маппинг подмен.

```python
def _fetch_search_data(api_key, cabinet_name, api_start, api_end, limit) -> list[dict]
```
`POST` к WB Search API. Лимиты: ООО=100, ИП=30.

```python
def _extract_metric(item, key) -> int
```
Извлекает метрику (обрабатывает как скаляры, так и объекты с `current`).

```python
def _load_podmen_mapping(all_values) -> dict
```
Загружает маппинг подмен `{слово: [артикул1, артикул2]}` из колонок A:B.

```python
def _should_count_transitions(word, nm_id, mapping) -> bool
```
Проверяет, нужно ли считать переходы для пары слово+nmId.

```python
def _resolve_dates(ws, start_date, end_date) -> tuple
```
Определяет даты: из аргументов → из листа (A1/B1) → авто (прошлая неделя).

```python
def _dd_mm_to_api(date_str) -> str | None
```
Конвертирует `DD.MM.YYYY` → `YYYY-MM-DD`.

```python
def _auto_last_week() -> tuple[str, str]
```
Прошлая полная неделя (пн-вс) в формате `DD.MM.YYYY`.

---

## Инфраструктура

### `runner.py`

**Путь:** `services/sheets_sync/runner.py`
**Назначение:** CLI-запуск sync-скриптов.

#### Dataclass `SyncResult`

```python
@dataclass
class SyncResult:
    name: str        # Имя скрипта (e.g. "wb_stocks")
    sheet_name: str  # Целевой лист (e.g. "WB остатки")
    status: str      # "ok", "error", "skipped"
    rows: int        # Количество строк
    duration_sec: float  # Длительность в секундах
    error: str       # Текст ошибки (пусто если ok)
```

#### Реестр `SYNC_REGISTRY`

| Имя | Модуль | Лист |
|-----|--------|------|
| `wb_stocks` | `sync.sync_wb_stocks` | WB остатки |
| `wb_prices` | `sync.sync_wb_prices` | WB Цены |
| `moysklad` | `sync.sync_moysklad` | МойСклад_АПИ |
| `ozon` | `sync.sync_ozon_stocks_prices` | Ozon остатки и цены |
| `wb_feedbacks` | `sync.sync_wb_feedbacks` | Отзывы ООО / Отзывы ИП |
| `wb_bundles` | `sync.sync_wb_bundles` | Склейки WB |
| `ozon_bundles` | `sync.sync_ozon_bundles` | Склейки Озон |
| `search_analytics` | `sync.sync_search_analytics` | Аналитика по запросам |

#### Функции

```python
def run_sync(name: str, start_date=None, end_date=None) -> SyncResult
```
Запускает один sync-скрипт по имени. Динамический импорт модуля.

```python
def run_all(start_date=None, end_date=None) -> list[SyncResult]
```
Запускает все скрипты последовательно.

```python
def main()
```
CLI entry point. Аргументы:
- `<name>` — имя скрипта или `all`
- `--list` — список доступных скриптов
- `--test` — принудительный тестовый режим
- `--start DD.MM.YYYY` — начальная дата (для search_analytics)
- `--end DD.MM.YYYY` — конечная дата

#### Примеры запуска

```bash
python -m services.sheets_sync.runner --list
python -m services.sheets_sync.runner wb_stocks
python -m services.sheets_sync.runner all
python -m services.sheets_sync.runner search_analytics --start 01.01.2026 --end 07.01.2026
```

---

### `status.py`

**Путь:** `services/sheets_sync/status.py`
**Лист:** `Статус синхронизации`

#### Функция `update_status(results: list) -> None`

Записывает результаты синхронизации в лист. Мерджит с существующими данными (по имени скрипта).

**Колонки:** Скрипт, Лист, Последний запуск, Статус, Строк, Длительность, Ошибка

#### Приватная функция

```python
def _read_existing_status(ws) -> dict[str, list]
```
Читает существующие записи статуса. Возвращает `{script_name: [row_values]}`.

---

### `control_panel.py`

**Путь:** `services/sheets_sync/control_panel.py`
**Лист:** `Панель управления`
**Назначение:** Непрерывный polling Google Sheets для запуска скриптов.

#### Три механизма запуска

1. **Панель управления** — лист с checkbox'ами (колонка B), poll каждые 15 секунд
2. **Checkbox на листах данных** — C1 на каждом листе, проверка каждые ~60 секунд
3. **Ежедневный автозапуск** — 6:00 МСК, `run_all()`

#### Маппинг листов

```python
SHEET_TO_SYNC = {
    "МойСклад_АПИ": "moysklad",
    "WB остатки": "wb_stocks",
    "WB Цены": "wb_prices",
    "Ozon остатки и цены": "ozon",
    "Отзывы ООО": "wb_feedbacks",
    "Отзывы ИП": "wb_feedbacks",
    "Склейки WB": "wb_bundles",
    "Склейки Озон": "ozon_bundles",
}

LABEL_TO_SYNC = {
    "МойСклад остатки": "moysklad",
    "WB остатки": "wb_stocks",
    "WB цены": "wb_prices",
    "Ozon остатки и цены": "ozon",
    "WB отзывы": "wb_feedbacks",
    "Склейки WB": "wb_bundles",
    "Склейки Озон": "ozon_bundles",
    "Аналитика запросов": "search_analytics",
}
```

#### Функции

```python
def setup_panel(spreadsheet) -> None
```
Создает лист "Панель управления" с заголовками и строками для каждого скрипта. Колонки: Скрипт, Запустить, Дата от, Дата до, Статус, Последний запуск, Строк.

---

```python
def poll_once() -> list[SyncResult]
```
Один цикл проверки. Читает лист, находит TRUE в колонке B, сбрасывает, запускает sync, обновляет статус. Поддерживает "Запустить все".

---

```python
def check_data_sheet_checkboxes() -> list[SyncResult]
```
Проверяет C1 на каждом листе данных (через `SHEET_TO_SYNC`). Если TRUE — сбрасывает и запускает sync. Дедупликация: `wb_feedbacks` запускается один раз (несмотря на 2 листа).

---

```python
def poll_loop(interval: int = 15) -> None
```
Бесконечный цикл:
- Ежедневный автозапуск в 6:00 МСК
- `poll_once()` каждые 15 секунд
- `check_data_sheet_checkboxes()` каждые ~60 секунд (каждые 4 цикла)

---

```python
def main()
```
CLI entry point. Аргументы:
- `--once` — один цикл
- `--interval N` — интервал polling в секундах

```bash
python -m services.sheets_sync.control_panel
python -m services.sheets_sync.control_panel --once
python -m services.sheets_sync.control_panel --interval 30
```

---

## Google Sheets: листы

**Spreadsheet ID:** из переменной окружения `SPREADSHEET_ID`

| Лист | Скрипт | Тип |
|------|--------|-----|
| МойСклад_АПИ | `sync_moysklad` | Полная перезапись (row 3+) |
| WB остатки | `sync_wb_stocks` | Полная перезапись (row 4+) |
| WB Цены | `sync_wb_prices` | Полная перезапись (row 5+) |
| Отзывы ООО | `sync_wb_feedbacks` | Полная перезапись (всё) |
| Отзывы ИП | `sync_wb_feedbacks` | Полная перезапись (всё) |
| Ozon остатки и цены | `sync_ozon_stocks_prices` | Полная перезапись (row 4+) |
| Склейки WB | `sync_wb_bundles` | Частичная (только S-V) |
| Склейки Озон | `sync_ozon_bundles` | Частичная (только R,S,V) |
| Аналитика по запросам | `sync_search_analytics` | Накопительная (новые колонки) |
| Аналитика по запросам (поартикульно) | `sync_search_analytics` | Полная перезапись (row 4+) |
| Все товары | `sync_ozon_stocks_prices` | Только чтение (источник SKU) |
| Панель управления | `control_panel` | Polling UI |
| Статус синхронизации | `status` | Журнал результатов |

---

## Внешние API: эндпоинты

### Wildberries

| Эндпоинт | Метод | Используется в |
|----------|-------|----------------|
| `/api/v1/warehouse_remains` | GET (создать задачу) | `sync_wb_stocks` |
| `/api/v1/warehouse_remains/tasks/{id}/status` | GET | `sync_wb_stocks` |
| `/api/v1/warehouse_remains/tasks/{id}/download` | GET | `sync_wb_stocks` |
| `/api/v2/list/goods/filter` | GET (пагинация) | `sync_wb_prices`, `sync_wb_bundles` |
| `/api/v1/feedbacks` | GET (пагинация) | `sync_wb_feedbacks` |
| `/api/v1/supplier/orders` | GET (пагинация) | `sync_search_analytics` |
| `/api/v2/search-report/product/search-texts` | POST | `sync_search_analytics` |

### OZON

| Эндпоинт | Метод | Используется в |
|----------|-------|----------------|
| `/v1/report/products/create` | POST | `sync_ozon_stocks_prices`, `sync_ozon_bundles` |
| `/v1/report/info` | POST | `sync_ozon_stocks_prices`, `sync_ozon_bundles` |
| CSV URL (из report info) | GET | `sync_ozon_stocks_prices`, `sync_ozon_bundles` |

### МойСклад

| Эндпоинт | Метод | Используется в |
|----------|-------|----------------|
| `/entity/assortment` | GET (пагинация) | `sync_moysklad` |
| `/report/stock/bystore` | GET (пагинация) | `sync_moysklad` |
| `/report/stock/all` | GET (пагинация) | `sync_moysklad` |
| `/entity/purchaseorder` | GET (пагинация) | `sync_moysklad` |
| `/entity/purchaseorder/{id}/positions` | GET (пагинация) | `sync_moysklad` |

---

## Запуск и использование

### Разовый запуск одного скрипта

```bash
# Тестовый режим (пишет в листы с суффиксом _TEST)
SYNC_TEST_MODE=true python -m services.sheets_sync.runner wb_stocks

# Продакшн (пишет в основные листы)
SYNC_TEST_MODE=false python -m services.sheets_sync.runner wb_stocks
```

### Запуск всех скриптов

```bash
python -m services.sheets_sync.runner all
```

### Непрерывный polling (control panel)

```bash
python -m services.sheets_sync.control_panel
```

### Список доступных скриптов

```bash
python -m services.sheets_sync.runner --list
```

---

## Переменные окружения

Файл: `.env` в корне `services/`

| Переменная | Описание |
|------------|----------|
| `WB_API_KEY_IP` | API ключ WB кабинет ИП |
| `WB_API_KEY_OOO` | API ключ WB кабинет ООО |
| `OZON_CLIENT_ID_IP` | OZON Client-Id кабинет ИП |
| `OZON_API_KEY_IP` | OZON Api-Key кабинет ИП |
| `OZON_CLIENT_ID_OOO` | OZON Client-Id кабинет ООО |
| `OZON_API_KEY_OOO` | OZON Api-Key кабинет ООО |
| `MOYSKLAD_TOKEN` | Bearer-токен МойСклад |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Путь к JSON ключу Google SA |
| `SPREADSHEET_ID` | ID Google Spreadsheet |
| `SYNC_TEST_MODE` | `true` = тестовый режим (`_TEST` суффикс) |
| `LOG_LEVEL` | Уровень логирования (default: `INFO`) |

---

## Механизм кнопок обновления

### Как работает

На каждом листе данных в ячейке C1 создается checkbox (Data Validation Boolean). Пользователь может вставить изображение-кнопку в B1 и привязать к ней GAS-триггер, который устанавливает C1=TRUE.

**Цепочка:**
1. Пользователь нажимает кнопку (изображение в B1)
2. GAS-триггер устанавливает C1 = TRUE
3. `control_panel.py` → `check_data_sheet_checkboxes()` обнаруживает TRUE
4. Сбрасывает C1 = FALSE
5. Запускает соответствующий sync-скрипт
6. Обновляет статус

### GAS-триггер (пример для МойСклад_АПИ)

```javascript
function triggerMoySklad() {
  SpreadsheetApp.getActive()
    .getSheetByName("МойСклад_АПИ")
    .getRange("C1")
    .setValue(true);
}
```

Этот GAS-скрипт привязывается к изображению-кнопке через контекстное меню → "Назначить скрипт" → `triggerMoySklad`.

### Задержка

Polling `check_data_sheet_checkboxes()` выполняется каждые ~60 секунд (каждые 4 цикла по 15с). Максимальная задержка срабатывания: ~75 секунд.

---

## Важные технические детали

### Числа в Google Sheets (русская локаль)

Python `float` → Sheets хранит как число → отображает с запятой: `4,90` (правильно)
Python `str "4.90"` → Sheets хранит как текст → отображает с точкой: `4.90` (неправильно)

**Решение:** Функция `to_number()` конвертирует строки в `int`/`float` перед записью.

### Двухкабинетная структура

Все скрипты WB и OZON работают с двумя кабинетами (ИП + ООО). Данные объединяются в один лист с колонкой "Кабинет", кроме отзывов (отдельные листы).

### Тестовый режим

`SYNC_TEST_MODE=true` → все листы получают суффикс `_TEST` (e.g. `WB остатки_TEST`). Продакшн-данные не затрагиваются.

### JS vs Python truthiness

В JavaScript `[]` (пустой массив) — truthy. В Python `[]` — falsy. Это влияет на фильтрацию в `sync_moysklad.py`: используется `"attributes" in row` вместо `if row.get("attributes")`.

### Пагинация

Все API-клиенты реализуют пагинацию с защитой от бесконечных циклов (максимум 10-20 страниц).
