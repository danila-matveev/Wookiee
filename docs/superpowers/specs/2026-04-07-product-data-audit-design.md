# Product Data Audit — Design Spec (Subsystem 1 of 3)

**Дата:** 2026-04-07
**Статус:** Approved
**Scope:** Аудит данных товарной матрицы (Google Sheets vs Supabase vs МойСклад)
**Следующие подсистемы:** 2) Sync Google Sheets → Supabase, 3) МойСклад cross-validation

## Контекст

### Источники данных

| Система | Роль | Объём |
|---------|------|-------|
| **Google Sheets** (source of truth) | 46 табов, ключевые: "Все модели" (52 кол.), "Все товары" (52 кол.), "Все артикулы" | ~1500 SKU, ~480 артикулов, ~40 моделей |
| **Supabase** (target DB) | 22 таблицы, иерархия: modeli_osnova → modeli → artikuly → tovary + справочники | Та же структура, но нормализованная |
| **МойСклад API** | ERP: ассортимент, остатки, себестоимость | 32 атрибута + баркоды на каждый товар |

### Иерархия товарной матрицы

```
modeli_osnova (Vuki, Moon, Ruby, Joy...)           — базовая модель
  └── modeli (Vuki-ИП, Vuki2-ООО)                 — вариация по юрлицу
      └── artikuly (компбел-ж-бесшов/чер)          — модель + цвет
          └── tovary (баркод 2000000123456)         — артикул + размер (SKU)
```

### Связь Vuki/Vuki2

Vuki и Vuki2 — одна и та же модель-основа, но разные юрлица:
- Vuki → ИП Медведева Полина (importer)
- Vuki2 → ООО Анна Авуки (importer)
- Обе ссылаются на одну modeli_osnova

### Статусы — независимые по уровням и каналам

- Модель может быть "В продаже", но конкретный товар — "Архив"
- Товар на WB = "В продаже", на OZON = "Не продаётся" — это нормально
- Канальные статусы: status_wb, status_ozon, status_sayt, status_lamoda — все независимы

### Существующая инфраструктура

- `shared/clients/sheets_client.py` — gspread клиент (Google SA auth)
- `shared/clients/moysklad_client.py` — МойСклад API клиент
- `sku_database/config/mapping.py` — маппинг Excel → DB (66+ полей)
- `shared/data_layer/sku_mapping.py` — SQL-запросы к Supabase
- Supabase MCP — прямые SQL-запросы

---

## Решения

1. **Подход:** Multi-Agent Audit — 5 параллельных агентов, каждый со своей зоной ответственности
2. **Источник правды:** Google Sheets
3. **Синхронизация:** по расписанию + по команде (scope подсистемы 2, не этого спека)
4. **Выход:** Markdown-отчёт + structured JSON findings

---

## Архитектура

### 5 агентов + Orchestrator + Merger

```
                    ┌─────────────────┐
                    │   Orchestrator   │
                    │  (main process)  │
                    └────────┬────────┘
                             │ запускает параллельно
              ┌──────────────┼──────────────┐
              │              │              │
    ┌─────────┴──┐  ┌───────┴───┐  ┌──────┴────────┐
    │ Agent 1    │  │ Agent 2   │  │ Agent 3       │
    │ Schema     │  │ Hierarchy │  │ MoySklad      │
    │ Matcher    │  │ Checker   │  │ Validator     │
    └────────────┘  └───────────┘  └───────────────┘
              │              │              │
    ┌─────────┴──┐  ┌───────┴───┐
    │ Agent 4    │  │ Agent 5   │
    │ Status     │  │ Duplicate │
    │ Auditor    │  │ Finder    │
    └────────────┘  └───────────┘
              │              │
              └──────┬───────┘
                     ↓
              ┌──────────────┐
              │ Merger Agent │
              │  (collect +  │
              │   report)    │
              └──────┬───────┘
                     ↓
            audit-report.md
            audit-findings.json
```

### Agent 1: Schema Matcher

**Задача:** Сверка записей между Google Sheets и Supabase.

**Входные данные:**
- Google Sheets: "Все модели" (col B: Название модели, col G: Артикул модели, col H: Модель основа)
- Google Sheets: "Все товары" (col A: БАРКОД, col E: Артикул, col F: Модель, col Q: Размер)
- Supabase: modeli_osnova, modeli, artikuly, tovary

**Проверки:**
- Каждая модель из Sheets есть в Supabase (match по `Артикул модели` ↔ `kod`)
- Каждый товар из Sheets есть в Supabase (match по `БАРКОД` ↔ `barkod`)
- Каждый артикул из Sheets есть в Supabase (match по `Артикул` ↔ `artikul`, с LOWER+trim)
- Обратная проверка: записи в Supabase без пары в Sheets
- Количественная сверка: count по уровням

### Agent 2: Hierarchy Checker

**Задача:** Проверка целостности FK-цепочек в Supabase.

**Входные данные:** Supabase (все таблицы иерархии)

**Проверки:**
- Все `modeli.model_osnova_id` ссылаются на существующие modeli_osnova
- Все `artikuly.model_id` ссылаются на существующие modeli
- Все `artikuly.cvet_id` ссылаются на существующие cveta
- Все `tovary.artikul_id` ссылаются на существующие artikuly
- Все `tovary.razmer_id` ссылаются на существующие razmery
- Осиротевшие записи: modeli_osnova без modeli, modeli без artikuly, artikuly без tovary
- Цепочка вниз: modeli_osnova → сколько modeli → сколько artikuly → сколько tovary (дерево)

### Agent 3: MoySklad Validator

**Задача:** Сверка данных МойСклад API с Supabase.

**Входные данные:**
- МойСклад API: `fetch_assortment()` — баркоды, артикулы, названия, размеры
- Supabase: tovary (barkod), artikuly (artikul)

**Проверки:**
- Каждый баркод из МойСклад есть в tovary.barkod
- Баркоды в Supabase без пары в МойСклад
- Расхождения в названиях модели/артикула
- Расхождения в размерах

### Agent 4: Status Auditor

**Задача:** Проверка согласованности статусов по иерархии и каналам.

**Входные данные:** Supabase + Google Sheets "Все товары"

**Правила валидации:**
1. Модель "Архив" → все её товары должны быть "Архив" (CRITICAL если нарушено)
2. Все товары модели "Архив" → модель should be "Архив" (WARNING)
3. Vuki/Vuki2 с одной modeli_osnova — статусы модели согласованы (WARNING если нет)
4. Канальные статусы (WB/OZON/Сайт/Lamoda) — независимы, не ошибка
5. Товар без общего статуса (CRITICAL)
6. Сверка статусов Sheets vs Supabase — совпадают ли

### Agent 5: Duplicate Finder

**Задача:** Поиск дублей и неправильных связей.

**Входные данные:** Supabase + Google Sheets

**Проверки:**
- Дублирующие баркоды (один баркод на нескольких товарах)
- Дублирующие артикулы (с учётом регистра — LOWER)
- Дублирующие kod в modeli_osnova
- Vuki/Vuki2: корректно связаны через одну modeli_osnova? Или два разных modeli_osnova?
- Товары с одинаковым artikul_id + razmer_id (должен быть уникальным)

---

## Ключи матчинга между системами

### Primary keys (по приоритету надёжности)

| Уровень | Sheets → Supabase | Sheets → МойСклад | Supabase → МойСклад |
|---------|-------------------|-------------------|---------------------|
| tovary (SKU) | `БАРКОД` ↔ `barkod` | `БАРКОД` ↔ barcode | `barkod` ↔ barcode |
| artikuly | `Артикул` ↔ `artikul` (LOWER+trim) | `Артикул` ↔ attr "Артикул" | `artikul` ↔ attr "Артикул" |
| modeli | `Модель` ↔ `kod` | `Модель` ↔ attr "Модель" | `kod` ↔ attr "Модель" |
| modeli_osnova | `Артикул модели` ↔ `kod` | — | — |

### Нюансы матчинга

- **LOWER()** обязателен для текстовых ключей (в Sheets "Wendy", в Supabase "wendy")
- **Trailing slash**: `Артикул модели` в Sheets может заканчиваться на "/" (e.g. "компбел-ж-бесшов/"), в Supabase может быть без
- **Баркод** — числовой, самый надёжный ключ, всегда точное совпадение

---

## Severity Levels

| Level | Описание | Примеры |
|-------|----------|---------|
| **CRITICAL** | Потеря данных, сломанная целостность | Отсутствующие записи, дубли баркодов, сломанные FK |
| **WARNING** | Несогласованность, требует внимания | Статусы расходятся, данные устарели |
| **INFO** | Наблюдение | Новые записи только в одном источнике, статистика |

---

## Выходной формат

### Каждый агент → JSON

```json
{
  "agent": "schema_matcher",
  "timestamp": "2026-04-07T12:00:00Z",
  "duration_ms": 15000,
  "severity_counts": {"critical": 3, "warning": 12, "info": 45},
  "findings": [
    {
      "severity": "critical",
      "type": "missing_in_supabase",
      "level": "modeli_osnova",
      "detail": "Модель 'NewModel' есть в Sheets (row 42) но отсутствует в Supabase",
      "sheet_key": "newmodel/",
      "supabase_key": null
    }
  ]
}
```

### Merger → Markdown Report

```markdown
# Product Data Audit Report — 2026-04-07

## Summary
| Agent | Critical | Warning | Info |
|-------|----------|---------|------|
| Schema Matcher | 3 | 12 | 45 |
| ... | ... | ... | ... |
| **Total** | **X** | **Y** | **Z** |

## Critical Findings
...

## Warnings
...

## Recommendations
...
```

---

## Вне scope (подсистемы 2 и 3)

| Подсистема | Описание | Зависит от |
|------------|----------|------------|
| **2. Sync Script** | Google Sheets → Supabase регулярная синхронизация | Результаты этого аудита (маппинги, расхождения) |
| **3. МойСклад Sync** | МойСклад → Supabase периодическая сверка + обновление | Результаты этого аудита |
