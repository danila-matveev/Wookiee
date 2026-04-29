---
name: tool-status
description: Статус инструментов Wookiee — последние запуски, ошибки, метрики из Supabase
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

### Шаг 1: Получить данные из Supabase

Запустить Python-скрипт для получения данных:

```bash
PYTHONPATH=. python3 -c "
import psycopg2, os, json
from dotenv import load_dotenv
load_dotenv('database/sku/.env')

conn = psycopg2.connect(
    host=os.getenv('POSTGRES_HOST'), port=os.getenv('POSTGRES_PORT', '5432'),
    dbname=os.getenv('POSTGRES_DB', 'postgres'), user=os.getenv('POSTGRES_USER'),
    password=os.getenv('POSTGRES_PASSWORD'))
cur = conn.cursor()

cur.execute('SELECT slug, display_name, type, category, status, version, total_runs, last_run_at, last_status FROM tools ORDER BY category, slug')
tools = cur.fetchall()

cur.execute('''SELECT tool_slug, started_at, duration_sec, status, result_url, error_message
    FROM tool_runs WHERE started_at > now() - interval \\'7 days\\'
    ORDER BY started_at DESC LIMIT 20''')
runs = cur.fetchall()

cur.close(); conn.close()
print(json.dumps({
    'tools': [dict(zip(['slug','name','type','category','status','version','total_runs','last_run','last_status'], t)) for t in tools],
    'recent_runs': [dict(zip(['slug','started','duration','status','url','error'], r)) for r in runs]
}, default=str, ensure_ascii=False, indent=2))
"
```

### Шаг 2: Сформировать отчёт

Показать данные в виде таблиц:

**Реестр инструментов:**
| Инструмент | Тип | Категория | Статус | Версия | Запусков | Последний запуск |
|---|---|---|---|---|---|---|

**Запуски за 7 дней:**
| Дата | Инструмент | Результат | Длительность | Ссылка |
|---|---|---|---|---|

**Ошибки:**
| Дата | Инструмент | Этап | Сообщение |
|---|---|---|---|

### Если запрос по конкретному инструменту (/tool-status SLUG)

Запустить запрос только для него:

```bash
PYTHONPATH=. python3 -c "
import psycopg2, os, json
from dotenv import load_dotenv
load_dotenv('database/sku/.env')

slug = 'REPLACE_WITH_SLUG'
conn = psycopg2.connect(
    host=os.getenv('POSTGRES_HOST'), port=os.getenv('POSTGRES_PORT', '5432'),
    dbname=os.getenv('POSTGRES_DB', 'postgres'), user=os.getenv('POSTGRES_USER'),
    password=os.getenv('POSTGRES_PASSWORD'))
cur = conn.cursor()

cur.execute('SELECT * FROM tools WHERE slug = %s', (slug,))
cols = [d[0] for d in cur.description]
row = cur.fetchone()
tool = dict(zip(cols, row)) if row else None

cur.execute('SELECT started_at, status, duration_sec, result_url, error_message, error_stage, details FROM tool_runs WHERE tool_slug = %s ORDER BY started_at DESC LIMIT 10', (slug,))
runs = cur.fetchall()

cur.close(); conn.close()
print(json.dumps({'tool': tool, 'runs': [dict(zip(['started','status','duration','url','error','stage','details'], r)) for r in runs]}, default=str, ensure_ascii=False, indent=2))
"
```

Показать карточку инструмента + все запуски.
