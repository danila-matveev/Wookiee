---
name: tool-register
description: Регистрация нового инструмента в реестре Wookiee или обновление существующего
triggers:
  - /tool-register
  - зарегистрируй инструмент
  - добавь инструмент в реестр
---

# Tool Register — регистрация инструмента в реестре

Добавляет новый инструмент в таблицу `tools` в Supabase или обновляет существующий.

## Использование

```
/tool-register finance-report
/tool-register calc-irp --type script --category infra
/tool-register my-new-skill --update
```

## Алгоритм

### Для скиллов (type=skill)

1. Прочитать `.claude/skills/{slug}/SKILL.md`
2. Извлечь из frontmatter: `name` (→ display_name), `description`
3. Определить version из changelog в файле (если есть)
4. Записать в Supabase через upsert

### Для скриптов и сервисов (type=script / type=service)

1. Если данные не указаны явно — запросить у пользователя:
   - `display_name` — читаемое название
   - `description` — что делает
   - `category` — analytics | planning | content | team | infra
   - `run_command` — как запустить
2. Записать в Supabase

### SQL для записи

```bash
PYTHONPATH=. python3 -c "
import psycopg2, os
from dotenv import load_dotenv
load_dotenv('sku_database/.env')

conn = psycopg2.connect(
    host=os.getenv('POSTGRES_HOST'), port=os.getenv('POSTGRES_PORT', '5432'),
    dbname=os.getenv('POSTGRES_DB', 'postgres'), user=os.getenv('POSTGRES_USER'),
    password=os.getenv('POSTGRES_PASSWORD'))
conn.autocommit = True
cur = conn.cursor()

cur.execute('''
    INSERT INTO tools (slug, display_name, type, category, status, version, description, run_command, owner)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (slug) DO UPDATE SET
        display_name = EXCLUDED.display_name,
        description = EXCLUDED.description,
        version = EXCLUDED.version,
        run_command = EXCLUDED.run_command,
        updated_at = now()
''', ('SLUG', 'DISPLAY_NAME', 'TYPE', 'CATEGORY', 'active', 'VERSION', 'DESCRIPTION', 'RUN_CMD', 'danila'))

cur.close(); conn.close()
print('✅ Tool registered: SLUG')
"
```

### Проверка после регистрации

```bash
PYTHONPATH=. python3 -c "
import psycopg2, os
from dotenv import load_dotenv
load_dotenv('sku_database/.env')

conn = psycopg2.connect(
    host=os.getenv('POSTGRES_HOST'), port=os.getenv('POSTGRES_PORT', '5432'),
    dbname=os.getenv('POSTGRES_DB', 'postgres'), user=os.getenv('POSTGRES_USER'),
    password=os.getenv('POSTGRES_PASSWORD'))
cur = conn.cursor()
cur.execute('SELECT slug, display_name, type, status, version FROM tools WHERE slug = %s', ('SLUG',))
print(cur.fetchone())
cur.close(); conn.close()
"
```

## Важно

- `slug` для скиллов включает `/` префикс: `/finance-report`
- `slug` для скриптов/сервисов без `/`: `calc-irp`, `sheets-sync`
- Если инструмент уже есть в реестре — используется upsert (обновление)
- Новые скиллы должны добавлять `tool_logger.start()` / `tool_logger.finish()` в свой SKILL.md
