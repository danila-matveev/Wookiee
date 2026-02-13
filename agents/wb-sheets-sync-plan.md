# План: WB API → Google Sheets синхронизация

## Контекст

Сейчас в Google Sheets настроены скрипты (Google Apps Script), которые тянут данные из Wildberries API. Эти скрипты создал другой человек, и команда не может ими управлять. Задача — создать Python-скрипты в проекте Wookiee, которые заменят Google Apps Script и дадут полный контроль над обновлением данных.

**Данные для синхронизации:**
- Остатки на складах WB
- Статистика по конверсиям
- Поисковые запросы
- Другие отчёты из аналитики продавца

**Результат:** данные записываются в Google Sheets (команда работает в таблицах).

---

## Архитектура решения

```
wb_sheets_sync/
├── config.py                    — конфигурация (WB API ключ, Google credentials)
├── wb_client.py                 — универсальный клиент WB API
├── sheets_client.py             — клиент Google Sheets (обёртка над gspread)
│
├── sync_stocks.py               — синхронизация остатков на складах
├── sync_statistics.py           — статистика: заказы, продажи, возвраты
├── sync_analytics.py            — аналитика: конверсии, просмотры карточек
├── sync_search_queries.py       — поисковые запросы
│
├── scheduler.py                 — расписание запуска (APScheduler или cron)
├── monitor.py                   — мониторинг: логи, алерты в Telegram при сбоях
│
├── requirements.txt             — зависимости
└── README.md                    — документация
```

---

## Шаг 1: Настройка Google Sheets API

### Что нужно сделать (одноразово):

1. **Google Cloud Console** (console.cloud.google.com):
   - Создать проект (или использовать существующий)
   - Включить **Google Sheets API**
   - Включить **Google Drive API**

2. **Service Account:**
   - Создать Service Account
   - Скачать JSON-ключ (credentials)
   - Сохранить в `.env` или отдельный файл (git-ignored!)

3. **Расшарить таблицы:**
   - Открыть каждую Google-таблицу, которую нужно обновлять
   - Нажать "Поделиться" → вставить email сервисного аккаунта (из JSON)
   - Дать права "Редактор"

### .env переменные:

```env
# Google Sheets
GOOGLE_SERVICE_ACCOUNT_FILE=credentials/google_service_account.json
# Или inline JSON:
# GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"..."}

# ID таблиц (из URL: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit)
SHEETS_STOCKS_ID=1abc...xyz
SHEETS_STATISTICS_ID=2abc...xyz
SHEETS_ANALYTICS_ID=3abc...xyz
SHEETS_SEARCH_QUERIES_ID=4abc...xyz
```

### Библиотеки:

```
gspread>=6.0.0
google-auth>=2.20.0
```

### Код sheets_client.py (основа):

```python
import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

def get_client(credentials_file: str) -> gspread.Client:
    creds = Credentials.from_service_account_file(credentials_file, scopes=SCOPES)
    return gspread.authorize(creds)

def write_dataframe(client, spreadsheet_id, sheet_name, df):
    """Записать pandas DataFrame в лист Google Sheets."""
    sh = client.open_by_key(spreadsheet_id)
    try:
        ws = sh.worksheet(sheet_name)
        ws.clear()
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=sheet_name, rows=len(df)+1, cols=len(df.columns))

    data = [df.columns.values.tolist()] + df.values.tolist()
    ws.update(data, 'A1')
```

---

## Шаг 2: Настройка WB API

### Получение API-ключа:

1. Войти в ЛК Wildberries → Настройки → Доступ к API
2. Создать ключ с нужными правами:
   - **Статистика** — для остатков, заказов, продаж
   - **Аналитика** — для конверсий, поисковых запросов
   - **Контент** — если нужны данные карточек

### .env переменные:

```env
# Wildberries API
WB_API_KEY=your_api_key_here
# Или отдельные ключи если разные права:
# WB_STATISTICS_API_KEY=...
# WB_ANALYTICS_API_KEY=...
```

### WB API эндпоинты:

#### Statistics API (statistics-api.wildberries.ru)

| Метод | Эндпоинт | Данные |
|-------|----------|--------|
| GET | `/api/v1/supplier/incomes` | Поставки |
| GET | `/api/v1/supplier/stocks` | Остатки на складах |
| GET | `/api/v1/supplier/orders` | Заказы |
| GET | `/api/v1/supplier/sales` | Продажи |
| GET | `/api/v5/supplier/reportDetailByPeriod` | Детальный отчёт по реализации |

#### Analytics API (seller-analytics-api.wildberries.ru)

| Метод | Эндпоинт | Данные |
|-------|----------|--------|
| POST | `/api/v2/stocks-report/products/products` | Отчёт по остаткам товаров |
| POST | `/api/v2/stocks-report/products/sizes` | Остатки по размерам |
| GET | `/api/v2/nm-report/detail` | Аналитика карточек (просмотры, корзина, заказы) |
| POST | `/api/v2/search-report/text/request` | Создать отчёт по поисковым запросам |
| GET | `/api/v2/search-report/text/result` | Получить результат отчёта |
| GET | `/api/analytics/v1/warehouse-measurements` | Замеры складов |

### Код wb_client.py (основа):

```python
import httpx
import time
from typing import Optional

class WBClient:
    STATISTICS_BASE = "https://statistics-api.wildberries.ru"
    ANALYTICS_BASE = "https://seller-analytics-api.wildberries.ru"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = httpx.Client(
            headers={"Authorization": api_key},
            timeout=30.0
        )

    def _request(self, method, url, **kwargs):
        """Запрос с retry при 429 (rate limit)."""
        for attempt in range(3):
            resp = self.session.request(method, url, **kwargs)
            if resp.status_code == 429:
                time.sleep(60)  # WB rate limit = 1 мин
                continue
            resp.raise_for_status()
            return resp.json()
        raise Exception(f"WB API rate limited after 3 attempts: {url}")

    def get_stocks(self, date_from: str):
        """Остатки на складах."""
        return self._request("GET", f"{self.STATISTICS_BASE}/api/v1/supplier/stocks",
                           params={"dateFrom": date_from})

    def get_orders(self, date_from: str, flag: int = 0):
        """Заказы."""
        return self._request("GET", f"{self.STATISTICS_BASE}/api/v1/supplier/orders",
                           params={"dateFrom": date_from, "flag": flag})

    def get_sales(self, date_from: str, flag: int = 0):
        """Продажи."""
        return self._request("GET", f"{self.STATISTICS_BASE}/api/v1/supplier/sales",
                           params={"dateFrom": date_from, "flag": flag})

    def get_nm_report(self, nm_ids: list, period: dict, page: int = 1):
        """Аналитика карточек (конверсии, просмотры)."""
        return self._request("POST", f"{self.ANALYTICS_BASE}/api/v2/nm-report/detail",
                           json={"nmIDs": nm_ids, "period": period, "page": page})
```

### Важно — Rate Limits WB API:

| API | Лимит |
|-----|-------|
| Statistics | 1 запрос / минуту на эндпоинт |
| Analytics | Зависит от эндпоинта (обычно 10/мин) |
| Content | 100 запросов / минуту |

**WB API строго лимитирует запросы.** При превышении — 429 ошибка с блокировкой на 1 минуту. Нужен retry с задержкой.

---

## Шаг 3: Скрипты синхронизации

### sync_stocks.py — Остатки

```python
# Псевдокод
def sync():
    wb = WBClient(api_key)
    sheets = get_sheets_client(credentials)

    stocks = wb.get_stocks(date_from="2024-01-01")
    df = pd.DataFrame(stocks)

    # Фильтрация, группировка по артикулу/складу
    df_grouped = df.groupby(['supplierArticle', 'warehouseName']).agg(...)

    write_dataframe(sheets, SPREADSHEET_ID, "Остатки", df_grouped)
    log.info(f"Stocks synced: {len(df_grouped)} rows")
```

### sync_statistics.py — Заказы и продажи

```python
def sync():
    orders = wb.get_orders(date_from=yesterday)
    sales = wb.get_sales(date_from=yesterday)

    write_dataframe(sheets, SPREADSHEET_ID, "Заказы", pd.DataFrame(orders))
    write_dataframe(sheets, SPREADSHEET_ID, "Продажи", pd.DataFrame(sales))
```

### sync_analytics.py — Конверсии

```python
def sync():
    # Получить nm_ids из Supabase (товарная матрица)
    nm_ids = get_nm_ids_from_supabase()

    report = wb.get_nm_report(nm_ids, period={"begin": start, "end": end})
    df = pd.DataFrame(report["data"]["cards"])

    write_dataframe(sheets, SPREADSHEET_ID, "Конверсии", df)
```

### sync_search_queries.py — Поисковые запросы

```python
def sync():
    # 1. Создать запрос на отчёт
    task = wb.create_search_report(text="...", ...)

    # 2. Подождать готовности (async)
    while not task.ready:
        time.sleep(30)

    # 3. Скачать результат
    result = wb.get_search_report_result(task.id)

    write_dataframe(sheets, SPREADSHEET_ID, "Поисковые запросы", pd.DataFrame(result))
```

---

## Шаг 4: Расписание и мониторинг

### Варианты запуска:

| Вариант | Когда использовать |
|---------|-------------------|
| **APScheduler** (в процессе бота) | Если бот уже запущен 24/7 — добавить задачи в scheduler |
| **cron** (системный) | Если скрипты запускаются отдельно от бота |
| **GitHub Actions** | Если проект на GitHub — бесплатный cron в облаке |

### Рекомендуемое расписание:

| Скрипт | Частота | Время |
|--------|---------|-------|
| sync_stocks | Каждые 4 часа | 06:00, 10:00, 14:00, 18:00, 22:00 |
| sync_statistics | 2 раза в день | 08:00, 20:00 |
| sync_analytics | 1 раз в день | 09:00 |
| sync_search_queries | 1 раз в день | 10:00 |

### Мониторинг:

1. **Логирование** — каждый запуск записывается:
   - Время старта/финиша
   - Количество записанных строк
   - Ошибки с traceback

2. **Алерты в Telegram** — при сбое отправляется сообщение в бот:
   ```
   ⚠️ WB Sync Error
   Скрипт: sync_stocks
   Ошибка: 429 Rate Limited
   Время: 2026-02-10 14:00:03
   ```

3. **Status Sheet** — отдельный лист в Google Sheets "Статус синхронизации":
   | Скрипт | Последний запуск | Статус | Строк | Ошибка |
   |--------|-----------------|--------|-------|--------|
   | sync_stocks | 2026-02-10 14:00 | OK | 1450 | — |
   | sync_statistics | 2026-02-10 08:00 | OK | 328 | — |

---

## Шаг 5: Зависимости

### requirements.txt

```
gspread>=6.0.0
google-auth>=2.20.0
httpx>=0.27.0
pandas>=2.0.0
python-dotenv>=1.0.0
APScheduler>=3.10.0    # если расписание через Python
```

---

## Порядок реализации

### Фаза 1: Инфраструктура (1 день)
1. Создать папку `wb_sheets_sync/`
2. Настроить Google Cloud + Service Account
3. Создать `config.py`, `sheets_client.py`, `wb_client.py`
4. Протестировать: записать тестовые данные в Google Sheet

### Фаза 2: Первый скрипт — остатки (1 день)
1. Реализовать `sync_stocks.py`
2. Протестировать: запустить, проверить данные в таблице
3. Сравнить с данными из текущего Google Apps Script

### Фаза 3: Остальные скрипты (2-3 дня)
1. `sync_statistics.py` — заказы и продажи
2. `sync_analytics.py` — конверсии карточек
3. `sync_search_queries.py` — поисковые запросы

### Фаза 4: Расписание и мониторинг (1 день)
1. Настроить расписание (APScheduler или cron)
2. Добавить логирование
3. Добавить алерты в Telegram при сбоях
4. Создать Status Sheet

### Фаза 5: Переключение (1 день)
1. Запустить параллельно с текущими Google Apps Script
2. Сравнить данные — убедиться что совпадают
3. Отключить старые Google Apps Script
4. Документация и передача команде

---

## Что нужно от вас для старта

1. **WB API ключ** — создать в ЛК Wildberries с правами на Статистику + Аналитику
2. **Google Cloud** — создать Service Account и JSON-ключ (инструкция выше)
3. **ID таблиц** — URL-ы Google Sheets, которые нужно обновлять
4. **Текущие скрипты** — если есть доступ к Google Apps Script, покажите код — перенесу логику 1:1

---

## Ссылки

- [WB API Documentation](https://dev.wildberries.ru/en)
- [WB API Swagger — Analytics](https://dev.wildberries.ru/en/swagger/analytics)
- [WB API SDK (Python)](https://github.com/artemdorozhkin/wb-api)
- [gspread Documentation](https://docs.gspread.org/)
- [Google Cloud Console](https://console.cloud.google.com)
