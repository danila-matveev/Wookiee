# Product Data Audit — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Провести полный аудит товарной матрицы: сверить Google Sheets vs Supabase vs МойСклад, выявить расхождения, дубли, сломанные иерархии и несогласованные статусы.

**Architecture:** 5 параллельных субагентов (Schema Matcher, Hierarchy Checker, MoySklad Validator, Status Auditor, Duplicate Finder), каждый выполняет SQL-запросы через Supabase MCP и/или читает Google Sheets. Результаты собираются в единый Markdown-отчёт.

**Tech Stack:** Supabase MCP (execute_sql), Google Sheets (gws CLI), МойСклад API (shared/clients/moysklad_client.py)

**Spec:** `docs/superpowers/specs/2026-04-07-product-data-audit-design.md`

---

## Task 1: Загрузка данных из Google Sheets

**Цель:** Получить snapshot данных из ключевых табов для использования агентами.

- [ ] **Step 1: Прочитать "Все модели" (headers + all rows)**

```bash
gws sheets get --spreadsheet-id 19Nbr0kD8JJlwd7OCIMbM9qxucYNjmXnWtwJUgXv0vlg --range "'Все модели'!A1:AZ200" --output json > /tmp/audit_vse_modeli.json
```

Ключевые колонки: B (Название модели), F (Статус), G (Артикул модели), H (Модель основа), I (Категория), K (Коллекция).

- [ ] **Step 2: Прочитать "Все товары" (headers + all rows)**

```bash
gws sheets get --spreadsheet-id 19Nbr0kD8JJlwd7OCIMbM9qxucYNjmXnWtwJUgXv0vlg --range "'Все товары'!A1:AZ2000" --output json > /tmp/audit_vse_tovary.json
```

Ключевые колонки: A (БАРКОД), E (Артикул), F (Модель), G (Color code), Q (Размер), R (Статус товара), S (Статус OZON), T (Статус Сайт), U (Статус Ламода), W (Склейка на WB), Y (Модель основа).

- [ ] **Step 3: Прочитать "Все артикулы" (headers + all rows)**

```bash
gws sheets get --spreadsheet-id 19Nbr0kD8JJlwd7OCIMbM9qxucYNjmXnWtwJUgXv0vlg --range "'Все артикулы'!A1:W600" --output json > /tmp/audit_vse_artikuly.json
```

Ключевые колонки: A (Артикул), B (Модель), E (Статус товара).

- [ ] **Step 4: Получить snapshot Supabase — counts по уровням**

```sql
-- execute_sql на Supabase MCP
SELECT 'modeli_osnova' as level, count(*) as cnt FROM modeli_osnova
UNION ALL SELECT 'modeli', count(*) FROM modeli
UNION ALL SELECT 'artikuly', count(*) FROM artikuly
UNION ALL SELECT 'tovary', count(*) FROM tovary
UNION ALL SELECT 'cveta', count(*) FROM cveta
UNION ALL SELECT 'statusy', count(*) FROM statusy
UNION ALL SELECT 'razmery', count(*) FROM razmery
UNION ALL SELECT 'importery', count(*) FROM importery
UNION ALL SELECT 'fabriki', count(*) FROM fabriki;
```

Записать результаты — это baseline для сверки.

---

## Task 2: Agent 1 — Schema Matcher (Sheets ↔ Supabase)

**Цель:** Сверить каждую запись между Google Sheets и Supabase по всем уровням иерархии.

Запустить как субагент с промптом ниже.

- [ ] **Step 1: Запустить агент Schema Matcher**

Промпт для субагента:

```
Ты — Schema Matcher. Твоя задача: сверить записи между Google Sheets и Supabase.

ИСТОЧНИКИ:
- Google Sheets: файлы /tmp/audit_vse_modeli.json и /tmp/audit_vse_tovary.json
- Supabase: через execute_sql (project gjvwcdtfglupewcwzfhw)

ПРОВЕРКИ (выполни все):

1. MODELI_OSNOVA: Прочитай из Sheets "Все модели" колонку G (Артикул модели). 
   Из Supabase: SELECT kod, nazvanie FROM modeli_osnova.
   Сверь: каждый Артикул модели (LOWER, trim, убери trailing /) должен совпадать с LOWER(kod).
   Запиши: missing_in_supabase, missing_in_sheets.

2. MODELI: Прочитай уникальные значения колонки F (Модель) из "Все товары".
   Из Supabase: SELECT kod, model_osnova_id FROM modeli.
   Сверь по LOWER(kod).

3. ARTIKULY: Прочитай уникальные значения колонки E (Артикул) из "Все товары".
   Из Supabase: SELECT artikul, model_id, cvet_id FROM artikuly.
   Сверь по LOWER(TRIM(artikul)).

4. TOVARY: Прочитай колонку A (БАРКОД) из "Все товары" — только непустые числовые значения.
   Из Supabase: SELECT barkod, artikul_id, razmer_id FROM tovary.
   Сверь точным совпадением (баркоды числовые).

5. COUNTS: Сравни количество записей:
   - Sheets "Все модели" rows vs modeli_osnova count
   - Sheets "Все товары" rows vs tovary count
   - Sheets уникальные артикулы vs artikuly count

ФОРМАТ РЕЗУЛЬТАТА — JSON:
{
  "agent": "schema_matcher",
  "severity_counts": {"critical": N, "warning": N, "info": N},
  "findings": [
    {"severity": "critical|warning|info", "type": "missing_in_supabase|missing_in_sheets|count_mismatch", "level": "modeli_osnova|modeli|artikuly|tovary", "detail": "описание", "sheet_key": "...", "supabase_key": "..."}
  ]
}

SEVERITY:
- critical: запись есть в одной системе но отсутствует в другой
- warning: count расхождение > 5%
- info: count расхождение <= 5%, статистика
```

- [ ] **Step 2: Сохранить результат**

Сохранить JSON-результат агента в `/tmp/audit_agent1_schema_matcher.json`.

---

## Task 3: Agent 2 — Hierarchy Checker (FK integrity в Supabase)

**Цель:** Проверить целостность FK-цепочек внутри Supabase.

- [ ] **Step 1: Запустить агент Hierarchy Checker**

Промпт для субагента:

```
Ты — Hierarchy Checker. Твоя задача: проверить целостность FK-цепочек в Supabase.

ИНСТРУМЕНТ: execute_sql на Supabase (project gjvwcdtfglupewcwzfhw)

ПРОВЕРКИ (выполни ВСЕ SQL-запросы):

1. Сломанные FK — modeli без modeli_osnova:
SELECT m.id, m.kod FROM modeli m
LEFT JOIN modeli_osnova mo ON m.model_osnova_id = mo.id
WHERE mo.id IS NULL;

2. Сломанные FK — artikuly без modeli:
SELECT a.id, a.artikul FROM artikuly a
LEFT JOIN modeli m ON a.model_id = m.id
WHERE m.id IS NULL;

3. Сломанные FK — artikuly без cveta:
SELECT a.id, a.artikul FROM artikuly a
LEFT JOIN cveta c ON a.cvet_id = c.id
WHERE c.id IS NULL;

4. Сломанные FK — tovary без artikuly:
SELECT t.id, t.barkod FROM tovary t
LEFT JOIN artikuly a ON t.artikul_id = a.id
WHERE a.id IS NULL;

5. Сломанные FK — tovary без razmery:
SELECT t.id, t.barkod FROM tovary t
LEFT JOIN razmery r ON t.razmer_id = r.id
WHERE r.id IS NULL;

6. Осиротевшие modeli_osnova (без modeli):
SELECT mo.id, mo.kod, mo.nazvanie FROM modeli_osnova mo
LEFT JOIN modeli m ON m.model_osnova_id = mo.id
WHERE m.id IS NULL;

7. Осиротевшие modeli (без artikuly):
SELECT m.id, m.kod FROM modeli m
LEFT JOIN artikuly a ON a.model_id = m.id
WHERE a.id IS NULL;

8. Осиротевшие artikuly (без tovary):
SELECT a.id, a.artikul FROM artikuly a
LEFT JOIN tovary t ON t.artikul_id = a.id
WHERE t.id IS NULL;

9. Дерево иерархии — полная карта:
SELECT mo.nazvanie as model_osnova, 
  count(DISTINCT m.id) as modeli_count,
  count(DISTINCT a.id) as artikuly_count,
  count(DISTINCT t.id) as tovary_count
FROM modeli_osnova mo
LEFT JOIN modeli m ON m.model_osnova_id = mo.id
LEFT JOIN artikuly a ON a.model_id = m.id
LEFT JOIN tovary t ON t.artikul_id = a.id
GROUP BY mo.id, mo.nazvanie
ORDER BY mo.nazvanie;

ФОРМАТ РЕЗУЛЬТАТА — JSON:
{
  "agent": "hierarchy_checker",
  "severity_counts": {"critical": N, "warning": N, "info": N},
  "findings": [
    {"severity": "critical", "type": "broken_fk|orphan", "level": "modeli|artikuly|tovary", "detail": "описание", "ids": [1,2,3]}
  ],
  "hierarchy_tree": [результат запроса 9]
}

SEVERITY:
- critical: сломанный FK (ссылка на несуществующую запись)
- warning: осиротевшая запись (существует но ни к чему не привязана)
- info: статистика дерева
```

- [ ] **Step 2: Сохранить результат**

Сохранить в `/tmp/audit_agent2_hierarchy_checker.json`.

---

## Task 4: Agent 3 — MoySklad Validator (МойСклад ↔ Supabase)

**Цель:** Сверить баркоды и артикулы между МойСклад API и Supabase.

- [ ] **Step 1: Получить данные МойСклад**

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee
python3 -c "
import json
from shared.clients.moysklad_client import MoySkladClient
client = MoySkladClient()
items = client.fetch_assortment()
# Извлечь баркоды и атрибуты
result = []
for item in items:
    barcodes = [b.get('ean13','') or b.get('ean8','') for b in item.get('barcodes', [])]
    attrs = {a.get('name',''): a.get('value','') for a in item.get('attributes', []) if isinstance(a.get('value'), str)}
    result.append({
        'name': item.get('name',''),
        'barcodes': barcodes,
        'article': attrs.get('Артикул', ''),
        'model': attrs.get('Модель', ''),
        'color': attrs.get('Цвет', ''),
        'size': attrs.get('Размер', ''),
    })
with open('/tmp/audit_moysklad_data.json', 'w') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(f'Exported {len(result)} items')
"
```

- [ ] **Step 2: Запустить агент MoySklad Validator**

Промпт для субагента:

```
Ты — MoySklad Validator. Сверь баркоды из МойСклад с Supabase.

ДАННЫЕ:
- МойСклад: /tmp/audit_moysklad_data.json (массив объектов с полями: name, barcodes[], article, model, color, size)
- Supabase: execute_sql (project gjvwcdtfglupewcwzfhw)

ПРОВЕРКИ:

1. Получи все баркоды из Supabase:
SELECT barkod, barkod_gs1, barkod_gs2 FROM tovary WHERE barkod IS NOT NULL;

2. Для каждого item из МойСклад: проверь что хотя бы один barcode есть в Supabase.

3. Для каждого barkod из Supabase: проверь что есть в МойСклад.

4. Где баркоды совпали — проверь артикулы: 
   МойСклад.article vs Supabase artikuly.artikul (через tovary.artikul_id).

ФОРМАТ РЕЗУЛЬТАТА — JSON:
{
  "agent": "moysklad_validator",
  "severity_counts": {"critical": N, "warning": N, "info": N},
  "findings": [
    {"severity": "...", "type": "missing_in_supabase|missing_in_moysklad|article_mismatch", "detail": "...", "barcode": "...", "moysklad_value": "...", "supabase_value": "..."}
  ],
  "stats": {"moysklad_items": N, "supabase_tovary": N, "matched": N, "unmatched_moysklad": N, "unmatched_supabase": N}
}
```

- [ ] **Step 3: Сохранить результат**

Сохранить в `/tmp/audit_agent3_moysklad_validator.json`.

---

## Task 5: Agent 4 — Status Auditor (статусы по иерархии)

**Цель:** Проверить согласованность статусов по уровням иерархии и каналам.

- [ ] **Step 1: Запустить агент Status Auditor**

Промпт для субагента:

```
Ты — Status Auditor. Проверь согласованность статусов в товарной матрице.

ИНСТРУМЕНТ: execute_sql на Supabase (project gjvwcdtfglupewcwzfhw)
ДАННЫЕ SHEETS: /tmp/audit_vse_tovary.json

ПРОВЕРКИ:

1. Модели в "Архив" с активными товарами:
SELECT m.kod as model, s.nazvanie as model_status, 
  count(t.id) as active_tovary
FROM modeli m
JOIN statusy s ON m.status_id = s.id
JOIN artikuly a ON a.model_id = m.id
JOIN tovary t ON t.artikul_id = a.id
JOIN statusy ts ON t.status_id = ts.id
WHERE LOWER(s.nazvanie) LIKE '%архив%'
  AND LOWER(ts.nazvanie) NOT LIKE '%архив%'
GROUP BY m.kod, s.nazvanie;
→ CRITICAL для каждой найденной строки

2. Все товары модели в архиве, но модель не в архиве:
SELECT m.kod, ms.nazvanie as model_status,
  count(t.id) as total_tovary,
  count(t.id) FILTER (WHERE LOWER(ts.nazvanie) LIKE '%архив%') as archived_tovary
FROM modeli m
JOIN statusy ms ON m.status_id = ms.id
JOIN artikuly a ON a.model_id = m.id
JOIN tovary t ON t.artikul_id = a.id
JOIN statusy ts ON t.status_id = ts.id
WHERE LOWER(ms.nazvanie) NOT LIKE '%архив%'
GROUP BY m.kod, ms.nazvanie
HAVING count(t.id) = count(t.id) FILTER (WHERE LOWER(ts.nazvanie) LIKE '%архив%')
  AND count(t.id) > 0;
→ WARNING для каждой найденной строки

3. Vuki/Vuki2 согласованность — модели с одной modeli_osnova:
SELECT mo.nazvanie as osnova, m.kod as model, s.nazvanie as status
FROM modeli m
JOIN modeli_osnova mo ON m.model_osnova_id = mo.id
JOIN statusy s ON m.status_id = s.id
ORDER BY mo.nazvanie, m.kod;
→ WARNING если модели с одной osnova имеют разные статусы

4. Товары без статуса:
SELECT t.id, t.barkod FROM tovary t WHERE t.status_id IS NULL;
→ CRITICAL

5. Статусы по каналам (информация):
SELECT 
  count(*) as total,
  count(status_ozon_id) as has_ozon_status,
  count(status_sayt_id) as has_sayt_status,
  count(status_lamoda_id) as has_lamoda_status
FROM tovary;
→ INFO

6. Сверка статусов Sheets vs Supabase:
Прочитай /tmp/audit_vse_tovary.json, колонка R (Статус товара).
Сравни с Supabase: SELECT t.barkod, s.nazvanie FROM tovary t JOIN statusy s ON t.status_id = s.id.
Матчинг по barkod, сравнение статусов.
→ WARNING для расхождений

ФОРМАТ РЕЗУЛЬТАТА — JSON:
{
  "agent": "status_auditor",
  "severity_counts": {"critical": N, "warning": N, "info": N},
  "findings": [...],
  "vuki_vuki2_status_map": [результат запроса 3]
}
```

- [ ] **Step 2: Сохранить результат**

Сохранить в `/tmp/audit_agent4_status_auditor.json`.

---

## Task 6: Agent 5 — Duplicate Finder (дубли и неправильные связи)

**Цель:** Найти дубли баркодов, артикулов и проверить связи Vuki/Vuki2.

- [ ] **Step 1: Запустить агент Duplicate Finder**

Промпт для субагента:

```
Ты — Duplicate Finder. Найди дубли и неправильные связи.

ИНСТРУМЕНТ: execute_sql на Supabase (project gjvwcdtfglupewcwzfhw)

ПРОВЕРКИ:

1. Дублирующие баркоды в tovary:
SELECT barkod, count(*) as cnt, array_agg(id) as ids
FROM tovary
WHERE barkod IS NOT NULL AND barkod != ''
GROUP BY barkod
HAVING count(*) > 1;
→ CRITICAL

2. Дублирующие артикулы (с LOWER):
SELECT LOWER(artikul) as art, count(*) as cnt, array_agg(id) as ids
FROM artikuly
GROUP BY LOWER(artikul)
HAVING count(*) > 1;
→ CRITICAL

3. Дублирующие kod в modeli_osnova:
SELECT LOWER(kod) as k, count(*) as cnt, array_agg(id) as ids
FROM modeli_osnova
GROUP BY LOWER(kod)
HAVING count(*) > 1;
→ CRITICAL

4. Дублирующие kod в modeli:
SELECT LOWER(kod) as k, count(*) as cnt, array_agg(id) as ids
FROM modeli
GROUP BY LOWER(kod)
HAVING count(*) > 1;
→ CRITICAL

5. Товары с одинаковым artikul_id + razmer_id:
SELECT artikul_id, razmer_id, count(*) as cnt, array_agg(id) as ids
FROM tovary
WHERE artikul_id IS NOT NULL AND razmer_id IS NOT NULL
GROUP BY artikul_id, razmer_id
HAVING count(*) > 1;
→ CRITICAL

6. Проверка Vuki/Vuki2 связей:
SELECT mo.id as osnova_id, mo.nazvanie as osnova_name, mo.kod as osnova_kod,
  m.id as model_id, m.kod as model_kod, i.nazvanie as importer
FROM modeli m
JOIN modeli_osnova mo ON m.model_osnova_id = mo.id
LEFT JOIN importery i ON m.importer_id = i.id
WHERE LOWER(m.kod) LIKE '%vuki%' OR LOWER(mo.nazvanie) LIKE '%vuki%'
ORDER BY mo.nazvanie, m.kod;
→ INFO (показать структуру) + WARNING если Vuki и Vuki2 ссылаются на разные modeli_osnova

7. Баркоды в Sheets с дублями:
Прочитай /tmp/audit_vse_tovary.json, колонка A (БАРКОД).
Найди дубли (один баркод в нескольких строках).
→ CRITICAL

ФОРМАТ РЕЗУЛЬТАТА — JSON:
{
  "agent": "duplicate_finder",
  "severity_counts": {"critical": N, "warning": N, "info": N},
  "findings": [...],
  "vuki_structure": [результат запроса 6]
}
```

- [ ] **Step 2: Сохранить результат**

Сохранить в `/tmp/audit_agent5_duplicate_finder.json`.

---

## Task 7: Merger — Собрать единый отчёт

**Цель:** Объединить результаты всех 5 агентов в Markdown-отчёт.

- [ ] **Step 1: Прочитать все JSON-результаты**

Файлы:
- `/tmp/audit_agent1_schema_matcher.json`
- `/tmp/audit_agent2_hierarchy_checker.json`
- `/tmp/audit_agent3_moysklad_validator.json`
- `/tmp/audit_agent4_status_auditor.json`
- `/tmp/audit_agent5_duplicate_finder.json`

- [ ] **Step 2: Сформировать Markdown-отчёт**

Создать файл `docs/reports/2026-04-07-product-data-audit-report.md`:

```markdown
# Product Data Audit Report — 2026-04-07

## Summary

| Agent | Critical | Warning | Info |
|-------|----------|---------|------|
| Schema Matcher | ? | ? | ? |
| Hierarchy Checker | ? | ? | ? |
| MoySklad Validator | ? | ? | ? |
| Status Auditor | ? | ? | ? |
| Duplicate Finder | ? | ? | ? |
| **Total** | **?** | **?** | **?** |

## Critical Findings
[Все findings с severity=critical, сгруппированные по агенту]

## Warnings
[Все findings с severity=warning, сгруппированные по агенту]

## Hierarchy Tree
[Дерево из Agent 2: modeli_osnova → count modeli → count artikuly → count tovary]

## Vuki/Vuki2 Structure
[Результат из Agent 5: связи, импортеры, статусы]

## Matching Statistics
[Stats из Agent 3: сколько сматчилось между МойСклад и Supabase]

## Recommendations
[На основе findings — что нужно исправить, приоритеты]
```

- [ ] **Step 3: Коммит отчёта**

```bash
git add docs/reports/2026-04-07-product-data-audit-report.md
git add docs/superpowers/specs/2026-04-07-product-data-audit-design.md
git commit -m "docs(audit): product data audit report — Sheets vs Supabase vs MoySklad"
```

---

## Порядок выполнения

```
Task 1  → Загрузка данных (Sheets + Supabase baseline)
          │
          ├── Task 2 (Agent 1: Schema Matcher)     ─┐
          ├── Task 3 (Agent 2: Hierarchy Checker)   ─┤ параллельно
          ├── Task 4 (Agent 3: MoySklad Validator)  ─┤
          ├── Task 5 (Agent 4: Status Auditor)      ─┤
          └── Task 6 (Agent 5: Duplicate Finder)    ─┘
                                                     │
Task 7  → Merger (собрать отчёт)                    ─┘
```

**Tasks 2-6 запускаются параллельно** через subagent-driven-development.
Task 1 — prerequisite, Task 7 — после завершения всех агентов.
