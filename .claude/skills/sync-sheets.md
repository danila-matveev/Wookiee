---
name: sync-sheets
description: Синхронизация Google Sheets → Supabase товарной матрицы. Используй этот скилл когда пользователь просит обновить данные из Google таблицы в Supabase, синхронизировать товарную матрицу, или загрузить изменения из Sheets в базу данных. Триггеры: 'обнови данные из Google таблицы', 'синхронизируй Sheets', 'sync sheets', 'загрузи матрицу в Supabase', 'обнови Supabase из Sheets'.
---

# Sync Google Sheets → Supabase

Односторонняя синхронизация товарной матрицы из Google Sheets (source of truth) в Supabase.

## Что делает

Smart sync: сопоставляет записи по ключам, вставляет новые, обновляет изменённые, архивирует пропавшие из Sheets (soft-delete → статус "Архив").

Иерархия синхронизации:
1. Справочники (statusy, kategorii, kollekcii, importery, fabriki)
2. Цвета (cveta)
3. Модели основа (modeli_osnova)
4. Модели (modeli)
5. Артикулы (artikuly)
6. Товары/SKU (tovary)

## Как использовать

### Полная синхронизация (по умолчанию)

```bash
python3 scripts/sync_sheets_to_supabase.py
```

### Синхронизация до определённого уровня

```bash
python3 scripts/sync_sheets_to_supabase.py --level modeli    # только до уровня modeli
python3 scripts/sync_sheets_to_supabase.py --level artikuly   # до уровня artikuly
python3 scripts/sync_sheets_to_supabase.py --level tovary     # все уровни (= all)
```

### Dry-run (посмотреть что изменится)

```bash
python3 scripts/sync_sheets_to_supabase.py --dry-run
```

## После запуска

1. Запусти скрипт с нужными параметрами
2. Покажи пользователю summary-таблицу из stdout
3. Если есть warnings — покажи их
4. Укажи путь к JSON-логу: `docs/reports/sync-log-YYYY-MM-DD.json`

## Аргументы от пользователя

Если пользователь просит:
- "обнови всё" → без аргументов (--level all)
- "обнови только модели" → --level modeli
- "покажи что изменится" → --dry-run
- "обнови артикулы" → --level artikuly
