# Wookiee Tool Registry — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Создать единый реестр инструментов Wookiee в Supabase с журналом запусков и скиллами для просмотра/регистрации.

**Architecture:** 2 таблицы в Supabase (tools + tool_runs), Python-модуль tool_logger.py для fire-and-forget логирования, 2 скилла (/tool-status, /tool-register). Интеграция с существующим finance-report как пример.

**Tech Stack:** PostgreSQL/Supabase, Python (psycopg2), Claude Code skills (Markdown)

**Spec:** `docs/superpowers/specs/2026-04-13-tool-registry-design.md`

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `shared/tool_logger.py` | Fire-and-forget логирование в Supabase |
| Create | `.claude/skills/tool-status/SKILL.md` | Скилл просмотра статуса инструментов |
| Create | `.claude/skills/tool-register/SKILL.md` | Скилл регистрации инструмента |
| Create | `scripts/init_tool_registry.py` | Создание таблиц + начальное заполнение |
| Modify | `.claude/skills/finance-report/SKILL.md` | Добавить вызов tool_logger (пример интеграции) |

---

### Task 1: Создание таблиц в Supabase

**Files:**
- Create: `scripts/init_tool_registry.py`

- [ ] **Step 1: Написать скрипт создания таблиц**

```python
#!/usr/bin/env python3
"""Create tool registry tables in Supabase."""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv("sku_database/.env")

DDL = """
CREATE TABLE IF NOT EXISTS tools (
  id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  slug            text UNIQUE NOT NULL,
  display_name    text NOT NULL,
  type            text NOT NULL CHECK (type IN ('skill', 'script', 'service')),
  category        text CHECK (category IN ('analytics', 'planning', 'content', 'team', 'infra')),
  description     text,
  how_it_works    text,
  status          text DEFAULT 'active' CHECK (status IN ('active', 'testing', 'deprecated')),
  version         text,
  run_command     text,
  data_sources    text[],
  depends_on      text[],
  output_targets  text[],
  owner           text,
  total_runs      int DEFAULT 0,
  success_rate    float DEFAULT 0,
  avg_duration    float DEFAULT 0,
  last_run_at     timestamptz,
  last_status     text,
  created_at      timestamptz DEFAULT now(),
  updated_at      timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tool_runs (
  id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  tool_slug       text NOT NULL REFERENCES tools(slug),
  tool_version    text,
  started_at      timestamptz DEFAULT now(),
  finished_at     timestamptz,
  duration_sec    float,
  status          text NOT NULL CHECK (status IN ('running', 'success', 'error', 'timeout', 'data_not_ready')),
  trigger_type    text,
  triggered_by    text,
  environment     text,
  period_start    date,
  period_end      date,
  depth           text,
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

CREATE INDEX IF NOT EXISTS idx_tool_runs_slug ON tool_runs(tool_slug);
CREATE INDEX IF NOT EXISTS idx_tool_runs_started ON tool_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_tool_runs_status ON tool_runs(status);
"""

def main():
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "postgres"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(DDL)
    cur.close()
    conn.close()
    print("✅ Tables created: tools, tool_runs")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Запустить скрипт**

Run: `PYTHONPATH=. python3 scripts/init_tool_registry.py`
Expected: `✅ Tables created: tools, tool_runs`

- [ ] **Step 3: Коммит**

```bash
git add scripts/init_tool_registry.py
git commit -m "feat: create tool registry tables in Supabase"
```

---

### Task 2: shared/tool_logger.py

**Files:**
- Create: `shared/tool_logger.py`

- [ ] **Step 1: Написать модуль логирования**

```python
"""Fire-and-forget tool run logger for Supabase.

Usage:
    from shared.tool_logger import ToolLogger
    logger = ToolLogger("finance-report")
    run_id = logger.start(trigger="manual", user="danila", version="v4")
    # ... work ...
    logger.finish(run_id, status="success", result_url="...", details={...})
    # or:
    logger.error(run_id, stage="data_collection", message="timeout")
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

import psycopg2

logger = logging.getLogger(__name__)


def _get_connection():
    """Connect to Supabase PostgreSQL."""
    from dotenv import load_dotenv
    load_dotenv("sku_database/.env")
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "postgres"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


class ToolLogger:
    """Fire-and-forget logger. Never raises, never blocks."""

    def __init__(self, tool_slug: str):
        self.tool_slug = tool_slug

    def start(
        self,
        trigger: str = "manual",
        user: str = "unknown",
        version: str = "",
        environment: str = "local",
        period_start: str = "",
        period_end: str = "",
        depth: str = "",
    ) -> Optional[str]:
        """Record run start. Returns run_id or None on failure."""
        run_id = str(uuid.uuid4())
        try:
            conn = _get_connection()
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO tool_runs
                (id, tool_slug, tool_version, status, trigger_type, triggered_by,
                 environment, period_start, period_end, depth)
                VALUES (%s, %s, %s, 'running', %s, %s, %s, %s, %s, %s)""",
                (
                    run_id, self.tool_slug, version or None,
                    trigger, f"user:{user}", environment,
                    period_start or None, period_end or None, depth or None,
                ),
            )
            cur.close()
            conn.close()
            return run_id
        except Exception as e:
            logger.warning(f"tool_logger.start failed: {e}")
            return None

    def finish(
        self,
        run_id: Optional[str],
        status: str = "success",
        result_url: str = "",
        items_processed: int = 0,
        output_sections: int = 0,
        details: dict = None,
        model_used: str = "",
        tokens_input: int = 0,
        tokens_output: int = 0,
        notes: str = "",
    ) -> None:
        """Record run completion."""
        if not run_id:
            return
        try:
            import json
            now = datetime.now(timezone.utc)
            conn = _get_connection()
            conn.autocommit = True
            cur = conn.cursor()

            # Get started_at to compute duration
            cur.execute("SELECT started_at FROM tool_runs WHERE id = %s", (run_id,))
            row = cur.fetchone()
            started_at = row[0] if row else now
            duration = (now - started_at).total_seconds() if started_at else 0

            cur.execute(
                """UPDATE tool_runs SET
                    finished_at = %s, duration_sec = %s, status = %s,
                    result_url = %s, items_processed = %s, output_sections = %s,
                    details = %s, model_used = %s, tokens_input = %s,
                    tokens_output = %s, notes = %s
                WHERE id = %s""",
                (
                    now, duration, status,
                    result_url or None, items_processed or None, output_sections or None,
                    json.dumps(details) if details else None,
                    model_used or None, tokens_input or None, tokens_output or None,
                    notes or None, run_id,
                ),
            )

            # Update tools aggregate stats
            cur.execute(
                """UPDATE tools SET
                    total_runs = total_runs + 1,
                    last_run_at = %s,
                    last_status = %s,
                    updated_at = %s
                WHERE slug = %s""",
                (now, status, now, self.tool_slug),
            )

            cur.close()
            conn.close()
        except Exception as e:
            logger.warning(f"tool_logger.finish failed: {e}")

    def error(
        self,
        run_id: Optional[str],
        stage: str = "",
        message: str = "",
    ) -> None:
        """Record run error."""
        if not run_id:
            return
        try:
            now = datetime.now(timezone.utc)
            conn = _get_connection()
            conn.autocommit = True
            cur = conn.cursor()

            cur.execute("SELECT started_at FROM tool_runs WHERE id = %s", (run_id,))
            row = cur.fetchone()
            started_at = row[0] if row else now
            duration = (now - started_at).total_seconds() if started_at else 0

            cur.execute(
                """UPDATE tool_runs SET
                    finished_at = %s, duration_sec = %s, status = 'error',
                    error_stage = %s, error_message = %s
                WHERE id = %s""",
                (now, duration, stage or None, message or None, run_id),
            )

            cur.execute(
                """UPDATE tools SET
                    total_runs = total_runs + 1,
                    last_run_at = %s,
                    last_status = 'error',
                    updated_at = %s
                WHERE slug = %s""",
                (now, now, self.tool_slug),
            )

            cur.close()
            conn.close()
        except Exception as e:
            logger.warning(f"tool_logger.error failed: {e}")
```

- [ ] **Step 2: Коммит**

```bash
git add shared/tool_logger.py
git commit -m "feat: add fire-and-forget tool_logger for Supabase"
```

---

### Task 3: Начальное заполнение реестра

**Files:**
- Modify: `scripts/init_tool_registry.py` (добавить seed data)

- [ ] **Step 1: Добавить функцию seed_tools в init_tool_registry.py**

Добавить после функции `main()`:

```python
SEED_TOOLS = [
    # Skills - analytics
    ("/finance-report", "Финансовый анализ", "skill", "analytics", "active", "v4",
     "P&L бренда WB+OZON, 12 секций, модельная декомпозиция, воронка, план-факт, callout-блоки. 3-волновой движок + 2 канальных аналитика + верификатор.",
     "/finance-report 2026-04-10", "danila"),
    ("/marketing-report", "Маркетинговый анализ", "skill", "analytics", "active", "v1",
     "Воронка трафика, ДРР по каналам, блогеры/ВК/SMM из Google Sheets, матрица эффективности моделей.",
     "/marketing-report 2026-04-10", "danila"),
    ("/funnel-report", "Анализ воронки WB", "skill", "analytics", "active", "v1",
     "Помодельная воронка WB: переходы→корзина→заказы→выкупы. CRO как главная метрика.",
     "/funnel-report 2026-04-10", "danila"),
    ("/analytics-report", "Мета-оркестратор аналитики", "skill", "analytics", "testing", "",
     "Вызывает finance + marketing + funnel последовательно.", "/analytics-report 2026-04-10", "danila"),
    ("/abc-audit", "ABC-аудит товарной матрицы", "skill", "analytics", "testing", "v1",
     "ABC x ROI классификация, color_code анализ, рекомендации по артикулам.", "/abc-audit", "danila"),
    ("/reviews-audit", "Аудит отзывов и возвратов", "skill", "analytics", "testing", "",
     "LLM-кластеризация отзывов/вопросов WB, модельные карточки, gap-анализ.", "/reviews-audit", "danila"),
    ("/market-review", "Обзор рынка и конкурентов", "skill", "analytics", "testing", "",
     "Ежемесячный анализ через MPStats: динамика категории, конкуренты.", "/market-review", "danila"),
    # Skills - planning
    ("/monthly-plan", "Месячный бизнес-план", "skill", "planning", "testing", "",
     "Multi-wave генерация бизнес-плана: таргеты, действия по моделям.", "/monthly-plan 2026-05", "danila"),
    # Skills - content
    ("/content-search", "Поиск фото бренда", "skill", "content", "testing", "",
     "Vector search по Content KB (~10K фото). Подбор контента под воронку.", "/content-search модель на пляже", "danila"),
    # Skills - team
    ("/bitrix-task", "Задачи в Битрикс24", "skill", "team", "active", "",
     "Создание задач через Битрикс24 REST API.", "поставь задачу ...", "danila"),
    ("/bitrix-analytics", "Пульс команды Битрикс", "skill", "team", "active", "",
     "Еженедельный отчёт по активности в Битрикс24: чаты, задачи, блокеры.", "/bitrix-analytics", "danila"),
    ("/finolog", "ДДС операции Финолог", "skill", "infra", "active", "",
     "Расходы, переводы, сводка по счетам, прогноз кассового разрыва.", "запиши расход ...", "danila"),
    # Services
    ("sheets-sync", "Синхронизация Google Sheets", "service", "infra", "active", "",
     "WB/OZON/МойСклад → Google Sheets. Остатки, цены, отзывы, финансы.",
     "python -m services.sheets_sync.runner all", "danila"),
    ("content-kb", "Индексатор фото (Content KB)", "service", "content", "active", "",
     "YaDisk → Gemini Embedding → pgvector. ~10K изображений.",
     "python -m services.content_kb.scripts.index_all", "danila"),
    ("logistics-audit", "Аудит логистики WB", "service", "analytics", "active", "",
     "Расчёт переплаты за логистику по формуле Оферты. Excel 11 листов.",
     "python -m services.logistics_audit.runner OOO 2026-01-01 2026-03-23", "danila"),
    ("wb-localization", "Оптимизация ИЛ/ИРП", "service", "infra", "active", "",
     "Калькулятор индекса локализации WB. Оптимальные склады для перемещения.",
     "python services/wb_localization/run_localization.py --cabinet ooo", "danila"),
    ("dashboard-api", "API WookieeHub", "service", "infra", "active", "",
     "FastAPI: ABC, Finance, Promo, Series, Stocks, Traffic, Comms.",
     "uvicorn services.dashboard_api.app:app --reload", "danila"),
    # Scripts
    ("collect-all", "Сборщик данных для аналитики", "script", "analytics", "active", "",
     "Параллельная загрузка: WB, OZON, Sheets → JSON (8 блоков).",
     "python scripts/analytics_report/collect_all.py --start DATE --end DATE", "danila"),
    ("sync-sheets-to-supabase", "Google Sheets → Supabase", "script", "infra", "active", "",
     "Синхронизация товарной матрицы: statusy, modeli, artikuly, tovary.",
     "python scripts/sync_sheets_to_supabase.py --level all", "danila"),
    ("abc-analysis", "ABC-анализ по финансам", "script", "analytics", "active", "",
     "Классификация артикулов: Лучшие/Хорошие/Неликвид/Новый.",
     "python scripts/abc_analysis.py --channel wb --save", "danila"),
    ("calc-irp", "Калькулятор ИЛ/ИРП", "script", "infra", "active", "",
     "ИЛ и ИРП для WB за 13 недель. Коэффициенты КТР/КРП.",
     "python scripts/calc_irp.py --top 20", "danila"),
    ("search-queries-sync", "Синхронизация поисковых запросов WB", "script", "analytics", "active", "",
     "Еженедельная загрузка аналитики поисковых запросов WB в Google Sheets. Замена GAS. Cron: пн 10:00 МСК.",
     "python scripts/run_search_queries_sync.py", "danila"),
    ("sync-product-db", "Синхронизация товарной БД", "script", "infra", "active", "",
     "Google Sheets → Supabase: statusy, modeli, artikuly, tovary. Cron ежедневно 06:00 МСК. Idempotent, retention 180 дней.",
     "python scripts/sync_sheets_to_supabase.py --level all", "danila"),
]


def seed_tools():
    """Insert initial tool registry data."""
    conn = _get_connection()
    conn.autocommit = True
    cur = conn.cursor()

    for slug, name, typ, cat, status, ver, desc, cmd, owner in SEED_TOOLS:
        cur.execute(
            """INSERT INTO tools (slug, display_name, type, category, status, version,
                description, run_command, owner)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (slug) DO UPDATE SET
                display_name = EXCLUDED.display_name,
                description = EXCLUDED.description,
                status = EXCLUDED.status,
                version = EXCLUDED.version,
                run_command = EXCLUDED.run_command,
                updated_at = now()""",
            (slug, name, typ, cat, status, ver or None, desc, cmd, owner),
        )

    cur.close()
    conn.close()
    print(f"✅ Seeded {len(SEED_TOOLS)} tools")


def _get_connection():
    from dotenv import load_dotenv
    load_dotenv("sku_database/.env")
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "postgres"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--seed":
        seed_tools()
    else:
        main()
        seed_tools()
```

- [ ] **Step 2: Запустить**

Run: `PYTHONPATH=. python3 scripts/init_tool_registry.py`
Expected: `✅ Tables created: tools, tool_runs` + `✅ Seeded 21 tools`

- [ ] **Step 3: Проверить данные**

Run: `PYTHONPATH=. python3 -c "from shared.tool_logger import _get_connection; c=_get_connection(); cur=c.cursor(); cur.execute('SELECT slug, display_name, status FROM tools ORDER BY slug'); [print(r) for r in cur.fetchall()]"`
Expected: 21 строк с правильными slug/display_name/status

- [ ] **Step 4: Коммит**

```bash
git add scripts/init_tool_registry.py
git commit -m "feat: seed tool registry with 21 instruments"
```

---

### Task 4: Скилл /tool-status

**Files:**
- Create: `.claude/skills/tool-status/SKILL.md`

- [ ] **Step 1: Написать SKILL.md**

```markdown
---
name: tool-status
description: Статус инструментов Wookiee — последние запуски, ошибки, метрики
triggers:
  - /tool-status
  - статус инструментов
  - какие инструменты есть
  - покажи запуски
---

# Tool Status — статус инструментов Wookiee

Показывает реестр инструментов и журнал запусков из Supabase.

## Использование

- `/tool-status` — сводка за последние 7 дней
- `/tool-status finance-report` — детали по конкретному инструменту
- `какие инструменты есть` — полный реестр
- `какие ошибки были` — только ошибки

## Реализация

1. Подключиться к Supabase (sku_database/.env)
2. Запросить данные из таблиц tools и tool_runs
3. Сформировать читаемый отчёт

### Сводка (по умолчанию)

```bash
PYTHONPATH=. python3 -c "
import psycopg2, os, json
from dotenv import load_dotenv
load_dotenv('sku_database/.env')

conn = psycopg2.connect(
    host=os.getenv('POSTGRES_HOST'), port=os.getenv('POSTGRES_PORT', '5432'),
    dbname=os.getenv('POSTGRES_DB', 'postgres'), user=os.getenv('POSTGRES_USER'),
    password=os.getenv('POSTGRES_PASSWORD'))
cur = conn.cursor()

# Tools summary
cur.execute('SELECT slug, display_name, status, version, total_runs, last_run_at, last_status FROM tools ORDER BY category, slug')
tools = cur.fetchall()

# Recent runs (7 days)
cur.execute('''SELECT tool_slug, started_at, duration_sec, status, result_url, error_message, details
    FROM tool_runs WHERE started_at > now() - interval \'7 days\' ORDER BY started_at DESC LIMIT 20''')
runs = cur.fetchall()

cur.close(); conn.close()
print(json.dumps({'tools': [dict(zip(['slug','name','status','version','total_runs','last_run','last_status'], t)) for t in tools], 'recent_runs': [dict(zip(['slug','started','duration','status','url','error','details'], r)) for r in runs]}, default=str, ensure_ascii=False, indent=2))
"
```

### Формат вывода

Показать в виде читаемой таблицы:

**Реестр:**
| Инструмент | Тип | Статус | Версия | Запусков | Последний |
|---|---|---|---|---|---|

**Запуски за 7 дней:**
| Дата | Инструмент | Результат | Длительность | Ссылка |
|---|---|---|---|---|

**Ошибки:**
| Дата | Инструмент | Этап | Сообщение |
|---|---|---|---|
```

- [ ] **Step 2: Коммит**

```bash
git add .claude/skills/tool-status/SKILL.md
git commit -m "feat: add /tool-status skill for tool registry"
```

---

### Task 5: Скилл /tool-register

**Files:**
- Create: `.claude/skills/tool-register/SKILL.md`

- [ ] **Step 1: Написать SKILL.md**

```markdown
---
name: tool-register
description: Регистрация нового инструмента в реестре Wookiee
triggers:
  - /tool-register
  - зарегистрируй инструмент
---

# Tool Register — регистрация инструмента

Добавляет новый инструмент в таблицу tools в Supabase или обновляет существующий.

## Использование

```
/tool-register finance-report
/tool-register calc-irp --type script --category infra
/tool-register finance-report --update
```

## Алгоритм

### Для скиллов (type=skill):

1. Прочитать `.claude/skills/{slug}/SKILL.md`
2. Извлечь из frontmatter: name, description
3. Извлечь из changelog: version
4. Записать в Supabase таблицу tools

### Для скриптов/сервисов:

1. Запросить у пользователя: display_name, description, category, run_command
2. Записать в Supabase

### SQL

```sql
INSERT INTO tools (slug, display_name, type, category, status, version, description, run_command, owner)
VALUES ($1, $2, $3, $4, 'active', $5, $6, $7, $8)
ON CONFLICT (slug) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    version = EXCLUDED.version,
    run_command = EXCLUDED.run_command,
    updated_at = now();
```
```

- [ ] **Step 2: Коммит**

```bash
git add .claude/skills/tool-register/SKILL.md
git commit -m "feat: add /tool-register skill"
```

---

### Task 6: Интеграция tool_logger в finance-report

**Files:**
- Modify: `.claude/skills/finance-report/SKILL.md`

- [ ] **Step 1: Добавить логирование в SKILL.md**

В Stage 1 (после сбора данных) добавить:

```
### 1.3 Start Tool Logging

```bash
PYTHONPATH=. python3 -c "
from shared.tool_logger import ToolLogger
logger = ToolLogger('/finance-report')
run_id = logger.start(trigger='manual', user='danila', version='v4',
    period_start='{START}', period_end='{END}', depth='{DEPTH}')
print(f'RUN_ID={run_id}')
"
```

Save the `RUN_ID` for use in Stage 5.
```

В Stage 5 (после публикации в Notion) добавить:

```
### 5.5 Finish Tool Logging

```bash
PYTHONPATH=. python3 -c "
from shared.tool_logger import ToolLogger
logger = ToolLogger('/finance-report')
logger.finish('{RUN_ID}',
    status='success',
    result_url='{NOTION_URL}',
    items_processed={MODEL_COUNT},
    output_sections=12,
    details={
        'margin': {BRAND_MARGIN},
        'revenue': {BRAND_REVENUE},
        'orders': {BRAND_ORDERS}
    })
"
```
```

- [ ] **Step 2: Коммит**

```bash
git add .claude/skills/finance-report/SKILL.md
git commit -m "feat: integrate tool_logger into finance-report skill"
```

---

### Task 7: Тестирование E2E

- [ ] **Step 1: Проверить что таблицы существуют**

```bash
PYTHONPATH=. python3 -c "
from shared.tool_logger import _get_connection
c = _get_connection()
cur = c.cursor()
cur.execute(\"SELECT COUNT(*) FROM tools\")
print(f'Tools: {cur.fetchone()[0]}')
cur.execute(\"SELECT COUNT(*) FROM tool_runs\")
print(f'Runs: {cur.fetchone()[0]}')
cur.close(); c.close()
"
```

Expected: `Tools: 21`, `Runs: 0`

- [ ] **Step 2: Тестовый запуск tool_logger**

```bash
PYTHONPATH=. python3 -c "
from shared.tool_logger import ToolLogger
logger = ToolLogger('/finance-report')
run_id = logger.start(trigger='test', user='danila', version='v4')
print(f'Started: {run_id}')
logger.finish(run_id, status='success', result_url='https://test.notion.so', items_processed=16, details={'margin': 319453})
print('Finished successfully')
"
```

Expected: `Started: <uuid>`, `Finished successfully`

- [ ] **Step 3: Проверить запись в БД**

```bash
PYTHONPATH=. python3 -c "
from shared.tool_logger import _get_connection
c = _get_connection()
cur = c.cursor()
cur.execute(\"SELECT tool_slug, status, duration_sec, details FROM tool_runs ORDER BY started_at DESC LIMIT 1\")
print(cur.fetchone())
cur.execute(\"SELECT slug, total_runs, last_status FROM tools WHERE slug = '/finance-report'\")
print(cur.fetchone())
cur.close(); c.close()
"
```

Expected: Запись в tool_runs со status=success, tools.total_runs=1

- [ ] **Step 4: Проверить /tool-status**

Run: `/tool-status`
Expected: Таблица с 21 инструментом, 1 запуск /finance-report

- [ ] **Step 5: Финальный коммит**

```bash
git add -A
git commit -m "feat: tool registry E2E tested and working"
```
