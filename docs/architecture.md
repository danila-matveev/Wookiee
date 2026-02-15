# Wookiee Analytics — Архитектура системы

## Обзор

Аналитическая система для бренда Wookiee, работающая с маркетплейсами Wildberries и OZON. Генерирует ежедневные, периодные и месячные отчёты с confidence scoring и AI-powered запросами.

## Компоненты

### 1. Analytics Scripts (`scripts/`)
- **Назначение:** Аналитический движок — генерация отчётов
- **Стек:** Python, psycopg2, python-dotenv
- **Ключевые файлы:** config.py, data_layer.py, daily_analytics.py, period_analytics.py, monthly_analytics.py, notion_sync.py
- **Data flow:** PostgreSQL -> data_layer.py -> analytics scripts -> Markdown -> Notion

### 2. Telegram Bot (`bot/`)
- **Назначение:** Пользовательский интерфейс для аналитики + AI-запросы
- **Стек:** Python, aiogram 3.15, APScheduler, SQLite (FTS5), bcrypt
- **Подкомпоненты:** handlers/ (auth, menu, reports), services/ (AI agents, report generators, storage)
- **AI routing:** z.ai (95% запросов) + Claude API (5% fallback)

### 3. SKU Database (`sku_database/`)
- **Назначение:** Товарная матрица (модели, цвета, размеры, статусы)
- **Стек:** Python, Supabase (PostgreSQL), Bitrix24 интеграция
- **Иерархия:** modeli_osnova -> modeli -> artikuly -> tovary

### 4. Marketplace Data Pipeline (`marketplace-data-pipeline/`)
- **Назначение:** Загрузка данных из API WB/OZON
- **Стек:** Python, WB API, OZON API, PostgreSQL
- **Подкомпоненты:** api_clients/, etl/, database/, tests/

### 5. MP Scripts (`MP scripts/`)
- **Назначение:** Скрипты локализации для Wildberries

## Источники данных

| Источник | БД | Содержимое |
|----------|-------|------------|
| Wildberries | `pbi_wb_wookiee` (PostgreSQL) | Финансы, трафик, заказы, реклама |
| OZON | `pbi_ozon_wookiee` (PostgreSQL) | Финансы, трафик, заказы, реклама |
| Supabase | товарная матрица | Статусы артикулов, модели, цвета |
| Notion | Фин аналитика | Хранение отчётов |

## Инфраструктура

- **Docker:** бот контейнеризирован (Dockerfile + docker-compose.yml)
- **Отчёты:** Markdown в reports/ + синхронизация с Notion
- **Расписание:** APScheduler (ежедневные отчёты в 10:05 МСК)
- **Мониторинг данных:** проверка каждые 5 мин с 06:00 до 12:00 МСК

## Технологии

- Python 3.11+
- PostgreSQL (финансовые данные)
- Supabase (товарная матрица)
- aiogram 3.15 (Telegram bot)
- Docker / docker-compose
- APScheduler
- Notion API
- z.ai API + Claude API
