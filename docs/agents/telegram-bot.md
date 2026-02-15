# Telegram Bot Agent

## Бизнес-описание

**Назначение:** AI-ассистент финансового менеджера бренда Wookiee. Единый интерфейс для доступа к аналитике через Telegram.

**Статус:** Активен (production)

**Какие задачи решает:**
- Ежедневные финансовые отчёты — автоматическая рассылка в 10:05 МСК
- Отчёты за произвольный период — интерактивный выбор дат
- ABC-анализ товарной матрицы
- Произвольные вопросы на естественном языке через AI
- Мониторинг свежести данных — уведомления когда WB/OZON данные готовы
- Синхронизация всех отчётов с Notion

**Кто использует:** Финансовый менеджер, руководство бренда

---

## Технические детали

### Стек

| Компонент | Технология |
|-----------|-----------|
| Framework | aiogram 3.15 (Telegram Bot API) |
| Scheduling | APScheduler 3.10.4 |
| AI (primary) | z.ai API (GLM-4.5-flash, ~$0.002/запрос) |
| AI (fallback) | Claude API (Sonnet 4.5, ~$0.02/запрос) |
| Хранилище | SQLite FTS5 (полнотекстовый поиск по отчётам) |
| Аутентификация | bcrypt (хэширование паролей) |
| Контейнеризация | Docker + docker-compose |

### Архитектура

```
Telegram User
    ↓
bot/main.py (инициализация, роутинг)
    ↓
bot/handlers/
    ├── auth.py              → авторизация по паролю
    ├── menu.py              → главное меню и навигация
    ├── scheduled_reports.py → шаблонные отчёты (daily, period, ABC)
    └── custom_queries.py    → произвольные AI-запросы
    ↓
bot/services/
    ├── ai_agent.py          → маршрутизация: z.ai (95%) → Claude (5%)
    ├── zai_client.py        → клиент z.ai API
    ├── claude_client.py     → клиент Claude API
    ├── report_generator.py  → запуск scripts/ через subprocess
    ├── simple_query_router.py → паттерн-матчинг без AI
    ├── scheduler_service.py → расписание (APScheduler)
    ├── data_freshness_service.py → мониторинг свежести данных
    ├── report_storage.py    → SQLite + FTS5
    ├── abc_analyzer.py      → ABC-классификация
    └── auth_service.py      → управление сессиями
    ↓
scripts/ (subprocess)
    ├── daily_analytics.py
    ├── period_analytics.py
    └── monthly_analytics.py
```

### AI-маршрутизация

Бот использует двухуровневую стратегию для минимизации затрат:

1. **Простые запросы** → `simple_query_router.py` — паттерн-матчинг по ключевым словам ("вчера", "за неделю", "за месяц"). AI не вызывается.
2. **z.ai (primary)** — 95% запросов. Дешёвый и быстрый (GLM-4.5-flash).
3. **Claude (fallback)** — 5% запросов. Когда confidence z.ai < 0.7 или нужен сложный анализ.

### Расписание

| Задача | Время | Описание |
|--------|-------|----------|
| Проверка свежести данных | Каждые 5 мин, 06:00-12:00 МСК | Ждёт обновления WB (~06:18) и OZON (~07:03) |
| Ежедневный отчёт | 10:05 МСК | Автоматическая рассылка всем авторизованным |
| Очистка старых отчётов | По настройке | Retention: 90 дней |

### Ключевые файлы

| Файл | Назначение |
|------|-----------|
| `bot/main.py` | Точка входа, инициализация, роутинг |
| `bot/config.py` | Конфигурация (читает из .env) |
| `bot/handlers/` | Обработчики команд и callback |
| `bot/services/ai_agent.py` | Умная маршрутизация между AI-провайдерами |
| `bot/services/report_generator.py` | Запуск аналитических скриптов |
| `bot/services/data_freshness_service.py` | Мониторинг обновления данных |
| `bot/services/report_storage.py` | SQLite хранилище с FTS5 |
| `bot/requirements.txt` | Зависимости (14 пакетов) |

### Конфигурация (.env)

```env
# Telegram
TELEGRAM_BOT_TOKEN=...
BOT_PASSWORD=...

# AI
ZAI_API_KEY=...
ANTHROPIC_API_KEY=...

# PostgreSQL (WB)
DB_HOST=...
DB_PORT=...
DB_NAME=pbi_wb_wookiee
DB_USER=...
DB_PASSWORD=...

# PostgreSQL (OZON)
DB_HOST_OZON=...
DB_NAME_OZON=pbi_ozon_wookiee

# Notion
NOTION_TOKEN=...
NOTION_DATABASE_ID=...

# Supabase
SUPABASE_ENV_PATH=...
```

---

## Запуск и использование

### Локальный запуск

```bash
cd bot
pip install -r requirements.txt
cp .env.example .env
nano .env  # заполнить все токены и ключи

python -m bot.main
```

### Docker (рекомендуется)

```bash
docker-compose up -d
```

### Команды бота

| Команда | Действие |
|---------|---------|
| `/start` | Авторизация (ввод пароля) |
| `/menu` | Главное меню |
| `/logout` | Выход из системы |

### Меню

1. **Шаблонные отчёты** → daily / period / ABC
2. **Кастомный запрос** → вопрос на естественном языке
3. **История отчётов** → поиск по истории (FTS5)
4. **Настройки**
5. **Помощь**

---

## Зависимости

- **Внутренние:** `scripts/` (вызывается через subprocess)
- **Внешние:** PostgreSQL (WB/OZON), Supabase, z.ai API, Claude API, Notion API, Telegram Bot API

---

## Ссылки

- Исходный код: [`bot/`](../bot/)
- Получение токена бота: [`bot/GET_BOT_TOKEN.md`](../bot/GET_BOT_TOKEN.md)
- Аналитический движок: [`agents/analytics-engine.md`](analytics-engine.md)
- Правила проекта: [`AGENTS.md`](../AGENTS.md)
