# Система синхронизации данных с Google Sheets

## Что это

Сервис синхронизации данных из маркетплейсов (WB, Ozon) и МойСклад в Google Sheets. Позволяет по нажатию кнопки в таблице или по расписанию обновлять данные об остатках, ценах, отзывах, финансовых показателях и аналитике.

---

## Архитектура

Система состоит из двух слоёв:

### 1. Google Apps Script (`apps_script/`)

Скрипты, встроенные в Google Sheets. Привязаны к кнопкам на листах. При нажатии кнопки скрипт выставляет значение чекбокса в ячейке-триггере в `TRUE`.

### 2. Python-модули синхронизации (`sync/`)

Модули на Python, которые опрашивают чекбоксы в таблицах и выполняют синхронизацию данных.

---

## Механизм работы

```
Пользователь нажимает кнопку
        ↓
GAS выставляет checkbox = TRUE
        ↓
control_panel.py опрашивает чекбоксы каждые 60 секунд
        ↓
Обнаруживает TRUE → запускает нужный sync-модуль
        ↓
Модуль запрашивает данные из API (WB / Ozon / МойСклад / PostgreSQL)
        ↓
Данные записываются в соответствующий лист
        ↓
Checkbox сбрасывается в FALSE
        ↓
status.py фиксирует результат в листе "Статус синхронизации"
```

---

## Расписание

- **Ежедневный автозапуск**: 06:00 МСК — все синхронизации запускаются автоматически
- **По требованию**: через кнопки в Google Sheets в любое время

---

## Кабинеты

Система работает с двумя юридическими лицами, каждое со своими API-ключами WB и Ozon:

| Кабинет | Описание |
|---------|----------|
| ИП | Индивидуальный предприниматель — отдельные WB и Ozon аккаунты |
| ООО | Общество с ограниченной ответственностью — отдельные WB и Ozon аккаунты |

---

## Тестовый режим

При запуске с флагом `--test` данные записываются не в основные листы, а в листы с суффиксом `_TEST` (например, `WB остатки_TEST`). Это позволяет проверять корректность данных без перезаписи рабочих таблиц.

---

## Все синхронизации

| Sync | Модуль | Лист в Google Sheets | Источник данных |
|------|--------|----------------------|-----------------|
| `wb_stocks` | `sync_wb_stocks.py` | WB остатки | WB Analytics API |
| `wb_prices` | `sync_wb_prices.py` | WB Цены | WB Prices API |
| `moysklad` | `sync_moysklad.py` | МойСклад_АПИ | МойСклад JSON API |
| `ozon` | `sync_ozon_stocks_prices.py` | Ozon остатки и цены | Ozon Seller API |
| `wb_feedbacks` | `sync_wb_feedbacks.py` | Отзывы ООО / Отзывы ИП | WB Feedbacks API |
| `fin_data` | `sync_fin_data.py` | Фин данные | PostgreSQL |
| `fin_data_new` | `sync_fin_data_new.py` | Фин данные NEW | PostgreSQL |
| `wb_bundles` | `sync_wb_bundles.py` | Склейки WB | WB Prices API |
| `ozon_bundles` | `sync_ozon_bundles.py` | Склейки Озон | Ozon Seller API |
| `search_analytics` | `sync_search_analytics.py` | Аналитика по запросам | WB Search API |

---

## Структура файлов

```
services/sheets_sync/
├── apps_script/                   # Google Apps Script файлы
│   ├── wb_stocks.gs
│   ├── wb_prices.gs
│   ├── moysklad.gs
│   ├── ozon.gs
│   ├── wb_feedbacks.gs
│   ├── fin_data.gs
│   ├── wb_bundles.gs
│   ├── ozon_bundles.gs
│   └── search_analytics.gs
│
├── sync/                          # Python-модули синхронизации
│   ├── sync_wb_stocks.py
│   ├── sync_wb_prices.py
│   ├── sync_moysklad.py
│   ├── sync_ozon_stocks_prices.py
│   ├── sync_wb_feedbacks.py
│   ├── sync_fin_data.py
│   ├── sync_fin_data_new.py
│   ├── sync_wb_bundles.py
│   ├── sync_ozon_bundles.py
│   └── sync_search_analytics.py
│
├── control_panel.py               # Основной демон: опрашивает чекбоксы каждые 60с
├── runner.py                      # CLI-интерфейс для ручного запуска
├── status.py                      # Фиксирует результат каждой синхронизации
│
├── docs/
│   ├── README.md                  # Этот файл
│   ├── api-reference.md           # Справочник внешних API
│   └── sheets-map.md              # Карта листов и колонок
│
└── __init__.py
```

---

## CLI-использование

### Запуск одной синхронизации

```bash
python -m services.sheets_sync.runner wb_stocks
```

### Список всех доступных синхронизаций

```bash
python -m services.sheets_sync.runner --list
```

### Запуск всех синхронизаций

```bash
python -m services.sheets_sync.runner all
```

### Тестовый режим (запись в листы *_TEST)

```bash
python -m services.sheets_sync.runner wb_stocks --test
python -m services.sheets_sync.runner all --test
```

---

## Зависимости

- `gspread` — работа с Google Sheets API
- `requests` / `httpx` — HTTP-запросы к внешним API
- `psycopg2` — подключение к PostgreSQL для финансовых данных
- `shared/config.py` — все API-ключи и настройки берутся отсюда
- `shared/data_layer.py` — все DB-запросы только через этот модуль
