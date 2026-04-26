# Wookiee Tool Registry — спецификация

## Цель

Единая система учёта всех инструментов проекта Wookiee: скиллов, скриптов, сервисов. Позволяет:
- Видеть что есть, как работает, кто отвечает
- Отслеживать запуски, ошибки, результаты
- Делиться с командой через один репозиторий

## Архитектура

```
Supabase (PostgreSQL)
├── tools          — реестр инструментов (что есть)
└── tool_runs      — журнал запусков (что произошло)

Claude Code
├── /tool-status   — скилл просмотра статуса
├── /tool-register — скилл регистрации нового инструмента
└── shared/tool_logger.py — Python-модуль логирования
```

## Таблица `tools` — реестр инструментов

Мастер-реестр. Заполняется через `/tool-register`. Обновляется вручную или через `/tool-register --update`.

```sql
CREATE TABLE tools (
  id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  slug            text UNIQUE NOT NULL,
  display_name    text NOT NULL,
  type            text NOT NULL,  -- skill | script | service
  category        text,           -- analytics | planning | content | team | infra
  description     text,
  how_it_works    text,
  status          text DEFAULT 'active',  -- active | testing | deprecated
  version         text,
  run_command     text,
  data_sources    text[],
  depends_on      text[],
  output_targets  text[],
  owner           text,
  -- Автоматические (обновляются tool_logger):
  total_runs      int DEFAULT 0,
  success_rate    float DEFAULT 0,
  avg_duration    float DEFAULT 0,
  last_run_at     timestamptz,
  last_status     text,
  created_at      timestamptz DEFAULT now(),
  updated_at      timestamptz DEFAULT now()
);
```

## Таблица `tool_runs` — журнал запусков

Каждый запуск = одна строка. Записывается автоматически через `shared/tool_logger.py`.

```sql
CREATE TABLE tool_runs (
  id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  tool_slug       text NOT NULL REFERENCES tools(slug),
  tool_version    text,
  started_at      timestamptz DEFAULT now(),
  finished_at     timestamptz,
  duration_sec    float,
  status          text NOT NULL,   -- success | error | timeout | data_not_ready
  trigger_type    text,            -- manual | cron | api | skill_chain
  triggered_by    text,            -- "user:danila" | "cron:daily"
  environment     text,            -- "local:macbook" | "server:timeweb"
  period_start    date,
  period_end      date,
  depth           text,            -- day | week | month
  result_url      text,
  error_message   text,
  error_stage     text,
  items_processed int,
  output_sections int,
  details         jsonb,
  model_used      text,
  tokens_input    int,
  tokens_output   int,
  notes           text
);
```

## Компоненты

### 1. shared/tool_logger.py

Fire-and-forget логирование. Если Supabase недоступен — не блокирует основной процесс.

```python
from shared.tool_logger import ToolLogger

logger = ToolLogger("finance-report")
run_id = logger.start(trigger="manual", user="danila", version="v4")

# ... работа скилла ...

logger.finish(run_id,
    status="success",
    result_url="https://notion.so/...",
    items_processed=16,
    details={"margin": 319453, "revenue": 1406265}
)

# или при ошибке:
logger.error(run_id, stage="data_collection", message="DB timeout")
```

### 2. Скилл /tool-register

Регистрирует новый инструмент или обновляет существующий.

```
/tool-register finance-report
→ Парсит .claude/skills/finance-report/SKILL.md
→ Заполняет tools таблицу (slug, display_name, description, version, ...)

/tool-register calc_irp --type script --category infra
→ Создаёт запись вручную для скрипта
```

### 3. Скилл /tool-status

Читает из Supabase и показывает сводку.

```
> статус инструментов

📊 Wookiee Tools — последние 7 дней

✅ /finance-report v4 — 5 запусков, все успешны
   Последний: 12.04 (5 мин), маржа 319К
✅ /marketing-report v1 — 2 запуска
❌ /abc-audit — 1 ошибка (data_collection: timeout)
⚪ /reviews-audit — не запускался

Итого: 8 запусков, 7 успешных (87%)
```

## Инструменты для регистрации (начальный набор)

### Скиллы (проектные)
| slug | display_name | type | category | status |
|---|---|---|---|---|
| /finance-report | Финансовый анализ | skill | analytics | active |
| /marketing-report | Маркетинговый анализ | skill | analytics | active |
| /funnel-report | Анализ воронки WB | skill | analytics | active |
| /analytics-report | Мета-оркестратор аналитики | skill | analytics | testing |
| /abc-audit | ABC-аудит товарной матрицы | skill | analytics | testing |
| /reviews-audit | Аудит отзывов и возвратов | skill | analytics | testing |
| /market-review | Обзор рынка и конкурентов | skill | analytics | testing |
| /monthly-plan | Месячный бизнес-план | skill | planning | testing |
| /content-search | Поиск фото бренда | skill | content | testing |
| /bitrix-task | Задачи в Битрикс24 | skill | team | active |
| /finolog | ДДС операции Финолог | skill | infra | active |

### Сервисы
| slug | display_name | type | category | status |
|---|---|---|---|---|
| sheets-sync | Синхронизация Google Sheets | service | infra | active |
| content-kb | Индексатор фото (Content KB) | service | content | active |
| logistics-audit | Аудит логистики WB | service | analytics | active |
| wb-localization | Оптимизация ИЛ/ИРП | service | infra | active |
| dashboard-api | API WookieeHub | service | infra | active |

### Скрипты
| slug | display_name | type | category | status |
|---|---|---|---|---|
| collect-all | Сборщик данных для аналитики | script | analytics | active |
| sync-sheets-to-supabase | Google Sheets → Supabase | script | infra | active |
| abc-analysis | ABC-анализ по финансам | script | analytics | active |
| calc-irp | Калькулятор ИЛ/ИРП | script | infra | active |

## Как работает с новыми скиллами

1. Создаёшь новый скилл (`.claude/skills/new-skill/SKILL.md`)
2. Запускаешь `/tool-register new-skill` — он парсит SKILL.md и создаёт запись в tools
3. В SKILL.md добавляешь вызов `tool_logger.start()` / `tool_logger.finish()` в Stage 1 и Stage 5
4. Каждый запуск автоматически логируется в tool_runs
5. `/tool-status` показывает полную картину

## Как работает с действующими скиллами

1. Один раз: запускаем `/tool-register` для всех существующих инструментов (начальный набор выше)
2. Постепенно добавляем `tool_logger` в каждый скилл (начиная с finance-report)
3. Скиллы без логгера работают как раньше, просто не появляются в tool_runs

## Реализация — план

### Фаза 1: Инфраструктура (1 сессия)
- Создать таблицы в Supabase (tools, tool_runs)
- Написать shared/tool_logger.py
- Зарегистрировать все инструменты из начального набора

### Фаза 2: Скиллы (1 сессия)
- Создать /tool-status скилл
- Создать /tool-register скилл
- Интегрировать tool_logger в /finance-report (как пример)

### Фаза 3: Масштабирование (по мере готовности)
- Интегрировать tool_logger в остальные скиллы
- Скопировать bitrix-task, finolog в репо Wookiee
- Обновить TOOLS_CATALOG.md генерацией из tools таблицы
