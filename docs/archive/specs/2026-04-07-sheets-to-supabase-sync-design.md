# Sheets → Supabase Smart Sync — Design Spec

**Дата:** 2026-04-07
**Статус:** Approved
**Scope:** Односторонняя синхронизация Google Sheets → Supabase товарной матрицы
**Предшественник:** Product Data Audit (2026-04-07) — выявил 15 моделей, 70 артикулов, 232 товара отсутствующих в Supabase, 579 расхождений статусов

---

## Контекст

### Проблема

Google Sheets — source of truth для товарной матрицы Wookiee. Supabase отстаёт: новые модели, артикулы и товары добавляются в Sheets, но не попадают в БД. Статусы расходятся. Единственный существующий инструмент — `sku_database/scripts/migrate_data.py` — это одноразовый full-reload из Excel, без инкрементальных обновлений.

### Существующая инфраструктура

| Компонент | Путь | Что делает |
|-----------|------|------------|
| Маппинг полей | `sku_database/config/mapping.py` | 44+ полей, clean-функции |
| Supabase схема | `sku_database/database/schema.sql` | 16+ таблиц, FK constraints |
| Sheets клиент | `shared/clients/sheets_client.py` | gspread обёртка (OAuth SA) |
| Data layer | `shared/data_layer/sku_mapping.py` | psycopg2 подключение к Supabase |
| Миграция (legacy) | `sku_database/scripts/migrate_data.py` | Excel → Supabase full reload |
| Sync framework | `services/sheets_sync/` | 11 скриптов, все пишут В Sheets |

### Иерархия товарной матрицы

```
Справочники (statusy, razmery, cveta, importery, fabriki, kategorii, kollekcii)
  └── modeli_osnova (Vuki, Moon, Ruby...)          — базовая модель
      └── modeli (Vuki-ИП, Vuki2-ООО)             — вариация по юрлицу
          └── artikuly (компбел-ж-бесшов/чер)      — модель + цвет
              └── tovary (баркод 2000000123456)     — артикул + размер (SKU)
```

---

## Решения

1. **Направление:** Sheets → Supabase (одностороннее). Sheets = source of truth.
2. **Режим:** Smart Sync — upsert + soft-delete записей, пропавших из Sheets.
3. **Гранулярность:** `--level all` по умолчанию. Можно `--level modeli`, `--level tovary` и т.д.
4. **Отчётность:** Apply сразу + JSON-лог каждого изменения. Без dry-run по умолчанию.
5. **Интерфейс:** Python-скрипт + Claude Code скилл `/sync-sheets`.

---

## Архитектура

### Пайплайн

```
Google Sheets (gspread)
    │
    ├── "Все модели" → modeli_osnova, modeli (частично)
    ├── "Все товары" → modeli, artikuly, tovary, cveta
    └── "Все артикулы" → artikuly (дополнительные поля)
    │
    ▼
┌─────────────────────────────┐
│  sync_sheets_to_supabase.py │
│                             │
│  1. Load Sheets data        │
│  2. Load Supabase state     │
│  3. Diff engine (by keys)   │
│  4. Apply: INSERT/UPDATE/   │
│     SOFT-DELETE              │
│  5. Write JSON log          │
└─────────────────────────────┘
    │
    ▼
Supabase (psycopg2)
```

### Порядок синхронизации (FK-зависимости)

Строго сверху вниз:

1. **Справочники** — statusy, razmery, kategorii, kollekcii, importery, fabriki
2. **cveta** — цвета (справочник, но зависит от данных товаров)
3. **modeli_osnova** — базовые модели
4. **modeli** — вариации (FK → modeli_osnova, importery)
5. **artikuly** — артикулы (FK → modeli, cveta)
6. **tovary** — товары/SKU (FK → artikuly, razmery, statusy)

При `--level modeli` синхронизируются уровни 1-4 (все зависимости включительно).

### Ключи матчинга

| Уровень | Sheets источник | Sheets колонка | Supabase поле | Нормализация |
|---------|----------------|----------------|---------------|-------------|
| modeli_osnova | "Все модели" | G (Артикул модели) | kod | LOWER, trim, strip trailing "/" |
| modeli | "Все товары" | F (Модель) | kod | LOWER |
| artikuly | "Все товары" | E (Артикул) | artikul | LOWER, TRIM |
| tovary | "Все товары" | A (БАРКОД) | barkod | exact (числовой) |
| cveta | "Все товары" | G (Color code) | kod | LOWER |
| statusy | "Все товары" | R (Статус товара) | nazvanie | exact |
| importery | "Все модели" | p (Импортер) | nazvanie | exact |

### Маппинг полей

Переиспользуем `sku_database/config/mapping.py` — там уже определены все 44+ полей с clean-функциями.

Дополнительные маппинги для Sheets (col index → field name):

**"Все модели" → modeli_osnova:**
- B(1) → nazvanie
- G(6) → kod
- H(7) → model_osnova (для определения связи)
- I(8) → kategoriya
- K(10) → kollekciya
- F(5) → status

**"Все товары" → tovary:**
- A(0) → barkod
- B(1) → barkod_gs1
- C(2) → barkod_gs2
- E(4) → artikul (для FK lookup)
- F(5) → model (для FK lookup)
- G(6) → color_code (для FK lookup)
- Q(16) → razmer (для FK lookup)
- R(17) → status
- S(18) → status_ozon
- T(19) → status_sayt
- U(20) → status_lamoda
- W(22) → skleyka_wb
- Y(24) → model_osnova

---

## Diff Engine

### Алгоритм для каждого уровня

```python
def sync_level(sheets_records, supabase_records, key_fn, normalize_fn):
    sheets_by_key = {normalize_fn(key_fn(r)): r for r in sheets_records}
    supa_by_key = {normalize_fn(key_fn(r)): r for r in supabase_records}

    to_insert = [r for k, r in sheets_by_key.items() if k not in supa_by_key]
    to_update = [r for k, r in sheets_by_key.items()
                 if k in supa_by_key and has_changes(r, supa_by_key[k])]
    to_soft_delete = [r for k, r in supa_by_key.items() if k not in sheets_by_key]

    return to_insert, to_update, to_soft_delete
```

### Сравнение полей (has_changes)

Сравниваются только маппированные поля. Игнорируются:
- `id`, `created_at`, `updated_at` (системные)
- FK id's (сравниваем по значению, не по id)

### Soft-delete логика

| Уровень | Действие при отсутствии в Sheets |
|---------|-------------------------------|
| tovary | status_id → "Архив" |
| artikuly | status_id → "Архив" |
| modeli | status_id → "Архив" |
| modeli_osnova | Не трогаем, WARNING в лог |
| Справочники | Не трогаем (могут использоваться в других местах) |

---

## Скрипт

### Файл: `scripts/sync_sheets_to_supabase.py`

```
Usage:
  python scripts/sync_sheets_to_supabase.py [--level LEVEL] [--dry-run] [--spreadsheet-id ID]

Options:
  --level        all (default) | statusy | modeli_osnova | modeli | artikuly | tovary
  --dry-run      Показать что изменится, без применения
  --spreadsheet-id  ID таблицы (по умолчанию из .env: PRODUCT_MATRIX_SPREADSHEET_ID)
```

### Зависимости

- `psycopg2` — Supabase
- `gspread` + `google-auth` — Google Sheets
- `sku_database/config/mapping.py` — маппинг полей
- `shared/config.py` — конфигурация

### Выход

**stdout:**
```
Sync Sheets → Supabase (level: all)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
statusy:        0 new, 0 updated, 0 archived
cveta:          2 new, 0 updated, 0 archived
modeli_osnova:  1 new, 0 updated, 0 archived  [+set bella]
modeli:        15 new, 2 updated, 1 archived
artikuly:      70 new, 5 updated, 0 archived
tovary:       232 new, 42 updated, 3 archived
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total: 320 new, 49 updated, 4 archived (12.5s)
Log: docs/reports/sync-log-2026-04-07.json
```

---

## JSON-лог

### Файл: `docs/reports/sync-log-YYYY-MM-DD.json`

```json
{
  "timestamp": "2026-04-07T15:30:00",
  "level": "all",
  "spreadsheet_id": "19Nbr0kD8JJlwd7OCIMbM9qxucYNjmXnWtwJUgXv0vlg",
  "duration_ms": 12500,
  "summary": {
    "modeli_osnova": {"inserted": 1, "updated": 0, "soft_deleted": 0, "unchanged": 22},
    "modeli": {"inserted": 15, "updated": 2, "soft_deleted": 1, "unchanged": 38},
    "artikuly": {"inserted": 70, "updated": 5, "soft_deleted": 0, "unchanged": 473},
    "tovary": {"inserted": 232, "updated": 42, "soft_deleted": 3, "unchanged": 1405}
  },
  "details": [
    {
      "action": "insert",
      "level": "modeli",
      "key": "ashley",
      "fields": {"kod": "ashley", "model_osnova": "Ashley", "status": "Подготовка"}
    },
    {
      "action": "update",
      "level": "tovary",
      "key": "2000989123456",
      "changed_fields": {"status": {"old": "Продается", "new": "Выводим"}}
    },
    {
      "action": "soft_delete",
      "level": "modeli",
      "key": "evelyn",
      "reason": "not_in_sheets"
    }
  ],
  "warnings": [
    "modeli_osnova 'evelyn' exists in Supabase but not in Sheets — not deleted (manual review required)"
  ]
}
```

---

## Claude Code Скилл

### Файл: `.claude/skills/sync-sheets.md`

**Триггеры:** "обнови данные из Google таблицы", "синхронизируй Sheets", "sync sheets", "/sync-sheets"

**Поведение:**
1. Запускает `python scripts/sync_sheets_to_supabase.py` с параметрами
2. Парсит JSON-лог
3. Выводит summary-таблицу
4. При ошибках — показывает warnings

**Аргументы скилла:**
- Без аргументов → `--level all`
- `--level modeli` → только до уровня modeli
- `--dry-run` → показать что изменится

---

## Обработка ошибок

| Ситуация | Поведение |
|----------|----------|
| Sheets недоступен | Exit с ошибкой, ничего не меняем |
| Supabase недоступен | Exit с ошибкой |
| FK не найден (напр. цвет не в справочнике) | Создать запись в справочнике автоматически, WARNING в лог |
| Дубль ключа при INSERT | Переключиться на UPDATE |
| Невалидный баркод (< 10 символов) | Пропустить, WARNING в лог |
| Пустая строка в Sheets | Пропустить |

---

## Вне scope

- Синхронизация Supabase → Sheets (обратное направление)
- МойСклад интеграция (отдельная подсистема)
- Автоматический запуск по расписанию (cron) — добавим позже
- Уведомления в Telegram о результатах sync
