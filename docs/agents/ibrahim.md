# Ибрагим — дата-инженер

## Бизнес-описание

- **Назначение:** Автономный AI дата-инженер. Управляет собственной PostgreSQL БД (`wookiee_marketplace`), наполняет данными через API маркетплейсов, анализирует API-документацию, следит за качеством данных.
- **Статус:** Активен
- **Задачи:**
  - Ежедневная синхронизация данных через ETL-пайплайн (05:00 МСК)
  - Сверка (reconciliation) с read-only БД — расхождение < 1%
  - Контроль качества данных: полнота, свежесть, консистентность
  - Анализ API-документации WB/Ozon — поиск новых источников данных
  - Эволюция схемы БД — предложения по улучшению
- **Кто использует:** Команда разработки, другие AI-агенты (через `DATA_SOURCE=managed`)

## Технические детали

- **Стек:** Python, psycopg2, WB API, OZON API, z.ai (для analyze-api/schema)
- **Путь:** `agents/ibrahim/`
- **Ключевые файлы:**
  - `ibrahim_service.py` — основной ETL-оркестратор
  - `tasks/etl_operator.py` — выполнение ETL
  - `tasks/reconciliation.py` — сверка данных
  - `tasks/api_docs_analyzer.py` — LLM-анализ API документации
  - `tasks/schema_manager.py` — управление схемой БД
  - `scheduler.py` — планировщик задач
  - `playbook.md` — живая инструкция агента
- **БД:** `wookiee_marketplace` (PostgreSQL) — WB (6 таблиц) + OZON (7 таблиц)
- **Зависимости:** `shared/config.py`, `shared/clients/wb_client.py`, `shared/clients/ozon_client.py`

## Запуск и использование

```bash
# Синхронизация за вчера
python -m agents.ibrahim sync

# Синхронизация за диапазон дат
python -m agents.ibrahim sync --from 2026-02-01 --to 2026-02-07

# Сверка с read-only БД
python -m agents.ibrahim reconcile

# Статус данных
python -m agents.ibrahim status

# Полный healthcheck
python -m agents.ibrahim health

# Анализ API-документации (LLM)
python -m agents.ibrahim analyze-api

# Предложения по схеме (LLM)
python -m agents.ibrahim analyze-schema

# Запуск постоянного планировщика
python -m agents.ibrahim run-scheduler
```

## Ссылки

- Исходный код: [`agents/ibrahim/`](../../agents/ibrahim/)
- Playbook: [`agents/ibrahim/playbook.md`](../../agents/ibrahim/playbook.md)
