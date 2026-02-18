# Олег — Технологический контекст

## Стек технологий

### Backend
- **Python 3.10+**
- **aiogram 3.15.0** — Telegram bot framework
- **psycopg2-binary 2.9.9** — PostgreSQL driver
- **httpx 0.27.0** — HTTP client (API-запросы)
- **APScheduler 3.10.4** — планировщик задач
- **bcrypt 4.2.0** — хеширование паролей
- **python-dotenv 1.0.0** — управление .env
- **pytz 2024.1** — управление часовыми поясами (Europe/Moscow)

### AI/ML
- **OpenRouter API** — primary LLM провайдер
  - `moonshotai/kimi-k2.5` — основная аналитика ($0.00045/$0.00044 за 1K токенов)
  - `z-ai/glm-4.5-flash` — классификация запросов ($0.0001/$0.0002)
  - `google/gemini-3-flash-preview` — fallback ($0.0005/$0.003)
- **z.ai API** — standby провайдер
  - `glm-4-plus` — fallback аналитика ($0.007)

### Аналитика
- **numpy >= 1.24.0**
- **pandas >= 2.0.0**
- **scipy >= 1.12.0**
- **statsmodels >= 0.14.1** — мультифакторный регрессионный анализ, «чистая» эластичность с контролем маркетинговых инвестиций. Используется `HAC` (Newey-West) ковариация для устойчивости к автокорреляции.

### Quality Gates (Контроль качества)
Для предотвращения неверных рекомендаций внедрена 3-уровневая система фильтрации:
1. **Data Sufficiency**: Проверка количества дней (n >= 30) и покрытия периода данными (date_coverage >= 70% от календарного окна).
2. **Variation Checks**: Проверка наличия сигнала (unique prices >= 3, range >= 5%, price changes >= 2) на основе округлённых цен.
3. **Model Validity**: Проверка адекватности (elasticity < 0, p-value < 0.1, R² > 0.05).

### Базы данных
- **PostgreSQL** (WB/OZON) — read-only доступ к продажам, финансам, трафику
- **Supabase** — товарная матрица (REST API)
- **SQLite** — локальное хранилище отчётов, кэш, learning store

### Внешние API
- **Telegram Bot API** — интерфейс с пользователями
- **Notion API** — синхронизация отчётов
- **OpenRouter API** — LLM inference
- **z.ai API** — fallback LLM

### Инфраструктура
- **Docker** — контейнеризация
- **docker-compose** — оркестрация
- **Healthcheck** — мониторинг состояния бота
- **Moscow Timezone (MSK)** — глобальная синхронизация времени во всех компонентах через `time_utils.py`.

## Архитектура кода

### Разделение процессов
Система разделена на два независимых процесса для повышения надёжности:
1. **Oleg Agent Runner (`agent_runner.py`)**:
   - Генерирует отчёты по расписанию (daily, weekly, monthly).
   - Мониторит свежесть данных (`DataFreshnessService`): проверка на наличие 50% выручки (vs 7d avg), положительной маржи и логистики (`logist`/`logist_end`), а также кросс-чек `abc_date` vs `orders`.
   - Кладёт результаты (HTML + клавиатуры) в таблицу `delivery_queue` в SQLite.
   - Выполняет процедуру восстановления пропущенных отчётов (3-day lookback).
2. **Oleg Bot (`main.py`)**:
   - Обрабатывает входящие команды в Telegram.
   - Выполняет интерактивные аналитические запросы.
   - Каждые несколько секунд проверяет `delivery_queue` и отправляет сообщения пользователям.

### Структура папок
```
agents/oleg/
├── main.py                    # Бот: UI + доставка из очереди
├── agent_runner.py            # Агент: планировщик + генерация отчётов
├── __main__.py                # Выбор режима запуска (bot/agent)
├── config.py                  # Конфигурация (общая для обоих процессов)
├── playbook.md                # Живая инструкция для LLM
├── AGENT_SPEC.md              # Спецификация агента
├── data/                      # SQLite БД (reports.db с очередью доставки)
├── logs/                      # Логи и PID-файлы (oleg_agent.pid)
├── services/                  # Бизнес-логика (используется обоими процессами)
│   ├── time_utils.py          # Централизованная работа с московским временем
│   └── data_freshness_service.py # Проверка готовности данных к анализу
└── ...

### Зависимости от shared/
Олег использует общую библиотеку проекта:
- `shared/data_layer.py` — все SQL-запросы (WB, OZON, Supabase). Внедрена гибридная модель: orders (qty, prices) + abc_date (expenses).
- `shared/config.py` — конфигурация (shim для обратной совместимости)
- `shared/clients/openrouter_client.py` — OpenRouter API wrapper
- `shared/clients/zai_client.py` — z.ai API wrapper
- `shared/clients/supabase_client.py` — Supabase REST API
- `shared/clients/notion_client.py` — Notion API
- `shared/utils/json_utils.py` — JSON parsing (extract_json)

## ReAct цикл
```python
max_iterations: 10          # Максимум 10 шагов думания
max_tool_calls: 20          # Максимум 20 вызовов инструментов
timeout: 120 секунд         # Таймаут на весь анализ
required_tools_deep: {      # Минимум для глубокого анализа
    "get_brand_finance",
    "get_channel_finance",
    "get_model_breakdown",
    "get_margin_levers"
}
```

**Логика:**
1. Classify запроса (glm-4.5-flash)
2. Генерация плана (Reasoning)
3. Вызов инструментов (Acting)
4. Анализ результатов (Reasoning)
5. Повторение 3-4 до ответа или лимита
6. Финальный отчёт (краткая сводка + подробный)

## Инструменты (Tools)

### Финансовые (12 tools)
- `get_brand_finance` — финансовая сводка бренда (WB+OZON)
- `get_channel_finance` — детальные финансы канала
- `get_model_breakdown` — топ моделей по марже
- `get_daily_trend` — дневная динамика метрик
- `get_advertising_stats` — статистика рекламы
- `get_model_advertising` — реклама по модели
- `get_orders_by_model` — заказы по модели
- `get_margin_levers` — 5 рычагов маржи
- `get_weekly_breakdown` — понедельная декомпозиция
- `validate_data_quality` — проверка расхождений с PowerBI
- `get_product_statuses` — статусы товаров (OOS, новинки)
- `calculate_metric` — вычисление кастомных метрик

### Ценовые (9 tools)
- `get_price_elasticity` — ценовая эластичность спроса (мультифакторная модель ln(orders) ~ ln(price) + ln(adv), log-log OLS)
- `get_price_margin_correlation` — корреляции цена ↔ маржа/объём
- `get_price_recommendation` — рекомендация по цене
- `simulate_price_change` — "что если цену изменить на X%?"
- `get_price_counterfactual` — "что было бы если..."
- `analyze_promotion` — анализ акций WB/OZON
- `get_price_trend` — тренд цены/маржи/СПП
- `get_recommendation_history` — история рекомендаций
- `get_price_changes_detected` — значимые изменения цены

## Конфигурация

### Переменные окружения (.env)
```bash
# Telegram
TELEGRAM_BOT_TOKEN=...
BOT_PASSWORD_HASH=...
ADMIN_CHAT_ID=...

# AI Providers
OPENROUTER_API_KEY=...
OLEG_ANALYTICS_MODEL=moonshotai/kimi-k2.5
OLEG_CLASSIFY_MODEL=z-ai/glm-4.5-flash
OLEG_FALLBACK_MODEL=google/gemini-3-flash-preview

# Database
DB_HOST=...
DB_PORT=6433
DB_USER=...
DB_PASSWORD=...
DB_NAME_WB=pbi_wb_wookiee
DB_NAME_OZON=pbi_ozon_wookiee

# Notion
NOTION_TOKEN=...
NOTION_DATABASE_ID=...

# Scheduler
TIMEZONE=Europe/Moscow
DAILY_REPORT_TIME=10:05
WEEKLY_REPORT_TIME=10:15
MONTHLY_REPORT_TIME=10:30

# Logging
LOG_LEVEL=INFO
```

## Развёртывание

### Docker
```yaml
# deploy/docker-compose.yml
services:
  wookiee-agent:
    image: wookiee-analytics
    command: ["python", "-m", "agents.oleg", "agent"]
    healthcheck:
      test: ["CMD", "python", "/app/deploy/healthcheck_agent.py"]

  wookiee-bot:
    image: wookiee-analytics
    command: ["python", "-m", "agents.oleg", "bot"]
    depends_on:
      - wookiee-agent
    healthcheck:
      test: ["CMD", "python", "/app/deploy/healthcheck.py"]
```

### Запуск
```bash
# Запуск агента (планировщик)
python -m agents.oleg agent

# Запуск бота (интерфейс)
python -m agents.oleg bot
```

## Метрики производительности

### Стоимость
- Стандартный отчёт: ~$0.03
- Глубокий анализ: ~$0.06
- analyze_deep с post-check: ~$0.08
- Месячный бюджет (5 запросов/день): **$7.50/месяц**

### Время выполнения
- Classify запроса: 0.5 сек (p95: 1.2 сек)
- Простой запрос (1-2 tools): 8-12 сек (p95: 18 сек)
- Стандартный отчёт (4-6 tools): 30-50 сек (p95: 75 сек)
- Глубокий анализ (8-10 tools): 60-90 сек (p95: 115 сек)

### Надёжность (февраль 2026)
- Uptime: 98.7%
- Error rate: 1.3%
- Success rate (tool calls): 99.4%
