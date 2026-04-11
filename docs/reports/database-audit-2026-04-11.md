# Database & Sheet Full Audit — 2026-04-11

## Сводка

- **Всего проблем:** 179 (PIM) + 12 (Sheet) + 10 (Infra) = **201**
- **HIGH:** 33 | **MEDIUM:** 92 | **LOW:** 54 | **Infra actions:** 10 | **Sheet fixes:** 12
- **Таблиц проверено:** 27 из 27 (17 PIM + 10 Infra)
- **Листов проверено:** 7 из 7
- **Verifier корректировки:** 4 (2 отклонено, 1 повышен, 1 уточнён)

### Критические корректировки Verifier

| Рекомендация агента | Вердикт Verifier | Причина |
|---|---|---|
| Удалить Evelyn (id=23) из modeli_osnova | **ОТКЛОНЕНО** | Валидная модель, нужно заполнить Col B в Sheet |
| Переименовать RubyPT → Ruby P | **ОТКЛОНЕНО** | RubyPT — корректный код из "Все товары", имеет 2 артикула |
| Удалить 6 русских дублей (Vuki animal и т.д.) | **ПОВЫШЕНО до HIGH** | 0 артикулов, 0 товаров, безопасно |
| 66 orphan artikuly — удалить | **ПОНИЖЕНО до LOW** | Это ПЛАНИРУЕМЫЕ продукты, не мусор |

---

## 1. PIM — Товарная матрица

### 1.1 modeli_osnova (3 верифицированные проблемы)

| # | ID | kod | Проблема | Рекомендация | Уверенность |
|---|-----|-----|----------|--------------|-------------|
| 1 | 24 | компбел-ж-бесшов | Артикул в таблице моделей-основ. 0 FK ссылок. Legacy artifact старого маппинга | DELETE | **HIGH** |
| 2 | 23 | Evelyn | Col B в Sheet пуст → sync не обновляет. Модель валидная | Заполнить Col B = "Evelyn" в Sheet | **MEDIUM** |
| 3 | — | 30 моделей | MISSING — есть в Sheet Col B, нет в БД (Nancy, Sally, Diana, Carol, Ashley, Aspen, Berlin, Billie, Emma, Jackie, Jane, Kat, Kerry, Kira, Kylie, Linda, Luna, Margo, Meg, Miami, Nicole, Nora, Oslo, Paris, Polly, Rose, Sabrina, Sky, Tina, Viola, Vita) | Запустить sync (модели добавятся автоматически) | **HIGH** |

**Root cause:** 30 моделей добавлены в Sheet после последнего синка (07.04). Достаточно запустить `python scripts/sync_sheets_to_supabase.py --level modeli_osnova` — они создадутся автоматически. Но предварительно нужно заполнить Col B для Evelyn.

### 1.2 modeli (верифицированные проблемы)

#### Безопасные DELETE (0 FK зависимостей)

| # | ID | kod | Проблема | Уверенность |
|---|-----|-----|----------|-------------|
| 1 | 42 | Vuki animal | Пустая модель-вариант, 0 artikuly, 0 tovary | **HIGH** |
| 2 | 43 | Vuki выстиранки | Пустая модель-вариант, 0 artikuly, 0 tovary | **HIGH** |
| 3 | 45 | VukiN animal | Пустая модель-вариант, 0 artikuly, 0 tovary | **HIGH** |
| 4 | 46 | VukiW выстиранки | Пустая модель-вариант, 0 artikuly, 0 tovary | **HIGH** |
| 5 | 49 | Moon выстиранки | Пустая модель-вариант, 0 artikuly, 0 tovary | **HIGH** |
| 6 | 50 | Moon трусы | Пустая модель-вариант, 0 artikuly, 0 tovary | **HIGH** |

#### NULL model_osnova_id (54 записи)

54 модели (ids 57-112) не привязаны к modeli_osnova. Это новые модели (Nancy, Nora, Linda, Emma, Billie, Kylie, Carol, Rose, Sky, Jackie, Sabrina, Polly, Luna, Diana, Tina, Ashley, Viola, Kat, Meg, Kira, Vita, Margo, Sally, Kerry, Rio, Jane и др.).

**Root cause:** Их modeli_osnova ещё не существует в БД (см. п.1.1 — 30 MISSING). После создания modeli_osnova через sync, нужно повторить sync на уровне modeli — FK заполнятся автоматически.

| Рекомендация | Уверенность |
|---|---|
| Запустить полный sync `--level all` после исправления Sheet | **MEDIUM** |

#### NULL nazvanie_en (73 записи)

Модели ids 62-112 не имеют английского названия. Это **by design** — в Sheet нет колонки "English name", модели с кириллическими названиями (типа "Nancy кружевные слипы") — это описательные имена для российского рынка.

| Рекомендация | Уверенность |
|---|---|
| Информационно. Если нужны EN-имена для экспорта — добавить колонку в Sheet | **LOW** |

#### RubyPT — НЕ ошибка

RubyPT — это валидный код модели "Ruby Принты+текст" из листа "Все товары". Имеет 2 artikuly. НЕ переименовывать.

### 1.3 artikuly (66 orphans)

66 артикулов без товаров. Модели: Nora, Emma, Jackie, Rose, Sabrina, Polly, Luna, Billie, Sky, Kylie, Diana, Carol, Tina, Ashley.

| Рекомендация | Уверенность |
|---|---|
| **НЕ УДАЛЯТЬ.** Это планируемые продукты — товары будут созданы при запуске (после генерации баркодов) | **LOW** |

### 1.4 tovary (10 bad barcodes)

| # | ID | barkod | Проблема | Рекомендация | Уверенность |
|---|-----|--------|----------|--------------|-------------|
| 1 | 115 | 7 | Placeholder (1-2 цифры, похоже на номер строки) | Заменить на реальный баркод из Sheet | **HIGH** |
| 2 | 121 | 9 | То же | То же | **HIGH** |
| 3 | 124 | 10 | То же | То же | **HIGH** |
| 4 | 127 | 21 | То же | То же | **HIGH** |
| 5 | 640 | 25 | То же | То же | **HIGH** |
| 6 | 641 | 18 | То же | То же | **HIGH** |
| 7 | 642 | 23 | То же | То же | **HIGH** |
| 8 | 643 | 24 | То же | То же | **HIGH** |
| 9 | 644 | 26 | То же | То же | **HIGH** |
| 10 | 645 | 27 | То же | То же | **HIGH** |

**Root cause:** Вероятно, ручной импорт с ошибкой — вместо баркодов попали номера строк Excel.

### 1.5 Справочники

#### cveta — 16 групп дубликатов

| # | Цвет | IDs дубликатов | Кол-во | Рекомендация | Уверенность |
|---|------|----------------|--------|--------------|-------------|
| 1 | black | 2, 100, 118 | 3 | MERGE → оставить id=2, перенести FK | **MEDIUM** |
| 2 | white | 3, 103, 121 | 3 | MERGE → оставить id=3, перенести FK | **MEDIUM** |
| 3 | nude | 4, 98, 123 | 3 | MERGE → оставить id=4, перенести FK | **MEDIUM** |
| 4 | brown | 5, 105, 117 | 3 | MERGE → оставить id=5, перенести FK | **MEDIUM** |
| 5 | ivory | 11, 116, 135 | 3 | MERGE → оставить id=11, перенести FK | **MEDIUM** |
| 6 | fig | 46, 109, 131 | 3 | MERGE → оставить id=46, перенести FK | **MEDIUM** |
| 7 | light pink | 47, 110, 129 | 3 | MERGE → оставить id=47, перенести FK | **MEDIUM** |
| 8 | yellow | 138, 43 | 2 | MERGE | **MEDIUM** |
| 9 | light brown | 22, 127 | 2 | MERGE | **MEDIUM** |
| 10 | green | 44, 136 | 2 | MERGE | **MEDIUM** |
| 11 | темно-синий | 113, 133 | 2 | MERGE | **MEDIUM** |
| 12 | graphite | 106, 122 | 2 | MERGE | **MEDIUM** |
| 13 | winered | 107, 128 | 2 | MERGE | **MEDIUM** |
| 14 | americano | 108, 130 | 2 | MERGE | **MEDIUM** |
| 15 | skin | 111, 132 | 2 | MERGE | **MEDIUM** |
| 16 | blue | 112, 134 | 2 | MERGE | **MEDIUM** |

**Внимание:** Перед MERGE необходимо проверить color_code у дубликатов. Если color_code разный — это РАЗНЫЕ цвета с одинаковым названием (допустимо). MERGE только при идентичных color_code.

#### kategorii — 5 неиспользуемых

| ID | Название | Рекомендация | Уверенность |
|-----|----------|--------------|-------------|
| 4 | Леггинсы | Не удалять — новые модели (Diana) будут их использовать | **LOW** |
| 5 | Лонгслив | То же (Jackie, Tina) | **LOW** |
| 6 | Рашгард | То же (Rose) | **LOW** |
| 7 | Топ | То же (Sky, Kylie, Viola, Luna) | **LOW** |
| 8 | Футболка | То же (Carol, Sabrina, Polly) | **LOW** |

**Вердикт:** НЕ удалять — это категории для планируемых моделей.

#### kollekcii — 2 неиспользуемых

| ID | Название | Рекомендация | Уверенность |
|-----|----------|--------------|-------------|
| 3 | Трикотажное белье без вставок | Проверить — нужна ли для новых моделей | **LOW** |
| 8 | Спортивная трикотажная коллекция | То же | **LOW** |

---

## 2. Google Sheet — анализ структуры

### 2.1 Дублирующиеся колонки

| Сравнение | Совпадение | Вердикт |
|---|---|---|
| Col A (Модель) vs Col B (Модель основа) | 75.3% | **Разные цели:** A = короткий код (VukiN), B = группа (Vuki). Оставить оба |
| Col A vs Col C (Название модели) | 27.4% | Разные: A = код, C = полное имя (Vuki animal) |
| Col B vs Col C | 28.8% | Разные: B = группа, C = вариант |

**Вывод:** Все 3 колонки несут разную семантику. Col A (Модель) НЕ используется sync-скриптом — она информационная.

### 2.2 Проблемы качества данных

| # | Лист | Проблема | Рекомендация | Уверенность |
|---|------|----------|--------------|-------------|
| 1 | Все модели | Col B пуст для Evelyn (row 165) | Заполнить "Evelyn" | **HIGH** |
| 2 | Все модели | Статусы "Запуск" (2) и "Выводим" (5) не в маппинге sync | Добавить в statusy таблицу | **MEDIUM** |
| 3 | Все модели | 3 колонки "не нужно" (cols 34-36) с данными | Удалить колонки | **MEDIUM** |
| 4 | Все модели | 4 колонки с пустыми заголовками (37, 71, 77, 89) | Удалить | **HIGH** |
| 5 | Все товары | Header "БАРКОД " с trailing space | Убрать пробел | **LOW** |
| 6 | Склейки WB | Пустые заголовки (merged cells?) | Исправить headers | **MEDIUM** |
| 7 | Склейки Озон | 1405 строк в Sheet, 0 в БД — sync не реализован | Реализовать sync | **HIGH** |

### 2.3 Использование колонок sync-скриптом

**"Все модели":** 32 из 91 колонки (35%) используются sync. 59 колонок — информационные.

**"Все товары":** 19 из 52 колонок (37%) используются sync.

**5 листов НЕ используются sync:**
- Все артикулы (аналитический лист)
- Аналитики цветов (аналитический)
- Склейки WB (данные есть в БД из другого источника)
- Склейки Озон (**КРИТИЧНО — данные нигде не синкаются!**)
- Упаковки (справочник)

### 2.4 Предложения по улучшению

| # | Предложение | Приоритет | Уверенность |
|---|---|---|---|
| 1 | Удалить 3 колонки "не нужно" + 4 пустых | HIGH | **HIGH** |
| 2 | Реализовать sync Склейки Озон → skleyki_ozon | HIGH | **HIGH** |
| 3 | Добавить data validation на Статус (dropdown) | MEDIUM | **MEDIUM** |
| 4 | Заполнить Col B для Evelyn | HIGH | **HIGH** |
| 5 | Добавить маппинг статусов "Запуск" и "Выводим" в sync | MEDIUM | **MEDIUM** |
| 6 | Вынести расчётные метрики (cols 78-91) — они из БД, не из Sheet | LOW | **LOW** |
| 7 | Стандартизировать язык заголовков (микс RU/EN) | LOW | **LOW** |

---

## 3. Инфраструктурные таблицы

### 3.1 Карта таблиц

| Таблица | Записей | Последняя запись | Используется | Вердикт | Schema |
|---------|---------|------------------|--------------|---------|--------|
| agent_runs | 650 | 2026-04-02 | WRITE-only (logger.py) | **ARCHIVE** | infra |
| orchestrator_runs | 130 | 2026-04-02 | WRITE-only (logger.py) | **ARCHIVE** | infra |
| report_runs | 9 | 2026-03-30 | UNUSED | **DELETE** | — |
| kb_chunks | 7,091 | active | READ+WRITE | **KEEP** | infra |
| content_assets | 10,146 | active | READ+WRITE | **KEEP** | infra |
| analytics_rules | 20 | 2026-03-30 | UNUSED | **DELETE** | — |
| notification_log | 1 | unknown | UNUSED | **DELETE** | — |
| archive_records | 0 | never | READ+WRITE (dormant) | **REVIEW** | infra |
| field_definitions | 44 | 2026-04-01 | READ+WRITE | **KEEP** | infra |
| istoriya_izmeneniy | 4,014 | trigger | WRITE (triggers) | **KEEP** | infra |

### 3.2 Описания (KEEP)

| Таблица | Назначение | Writers | Readers | Retention |
|---------|------------|---------|---------|-----------|
| kb_chunks | Текстовая vector KB (768d) для WB domain knowledge | knowledge_base/store.py | knowledge_base/store.py | Permanent |
| content_assets | Фото vector KB (~10K, Gemini Embed 2) | content_kb/store.py | content_kb/store.py | Permanent |
| field_definitions | Динамическая схема Product Matrix API | product_matrix_api/schema.py | product_matrix_api/schema.py | Permanent |
| istoriya_izmeneniy | Аудит-лог PIM (PostgreSQL triggers) | DB triggers | Manual SQL | 180 дней rolling |

### 3.3 Schema reorganization

**Предложение:** Создать schema `infra` и перенести все инфраструктурные таблицы.

```sql
-- Step 1: Create schema
CREATE SCHEMA IF NOT EXISTS infra;
GRANT USAGE ON SCHEMA infra TO authenticated, service_role;

-- Step 2: Migrate KEEP tables
ALTER TABLE public.kb_chunks SET SCHEMA infra;
ALTER TABLE public.content_assets SET SCHEMA infra;
ALTER TABLE public.field_definitions SET SCHEMA infra;
ALTER TABLE public.istoriya_izmeneniy SET SCHEMA infra;
ALTER TABLE public.archive_records SET SCHEMA infra;

-- Step 3: Delete unused
DROP TABLE IF EXISTS public.report_runs;
DROP TABLE IF EXISTS public.analytics_rules;
DROP TABLE IF EXISTS public.notification_log;

-- Alternative: set search_path (avoids code changes)
ALTER ROLE service_role SET search_path TO public, infra;
```

**Затрагиваемые файлы (при прямом schema-qualify):** 7 файлов, ~50 ссылок.

---

## 4. Sync-скрипт — выявленные баги

### 4.1 компбел-ж-бесшов → modeli_osnova

**Причина:** Legacy artifact из старой версии скрипта, где Col H ("Артикул модели") ошибочно маппился в modeli_osnova. Текущая версия (line 337) корректно использует Col B. Запись — zombie, safe to delete.

### 4.2 Русские модели-варианты (Vuki animal и т.д.)

**Причина:** By design. Sync uses Col C ("Название модели") = "Vuki animal" as model kod. Каждый вариант — отдельная модель. 6 пустых (без artikuly) — это deprecated варианты, safe to delete.

### 4.3 RubyPT

**Причина:** Создан из "Все товары" Col F fallback path (line 527-542). "RubyPT" — корректный shorthand для "Ruby Принты+текст". НЕ баг.

### 4.4 Статусы "Запуск" / "Выводим"

**Причина:** Sheet использует эти статусы, но sync script не имеет их в маппинге. Результат: NULL status_id в БД для этих моделей.

**Fix:** Добавить в таблицу `statusy` и в маппинг sync-скрипта.

### 4.5 Evelyn не синкается

**Причина:** Col B пуст → sync skip (line 343: `if not kod: continue`). Fix: заполнить Col B = "Evelyn".

---

## 5. Сводка действий (чеклист для утверждения)

### Немедленные действия (HIGH confidence)

- [ ] **DELETE** modeli_osnova id=24 (компбел-ж-бесшов) — 0 FK ссылок, zombie
- [ ] **DELETE** 6 пустых моделей (ids: 42, 43, 45, 46, 49, 50) — Vuki animal, Vuki выстиранки, VukiN animal, VukiW выстиранки, Moon выстиранки, Moon трусы — 0 FK
- [ ] **FIX** 10 bad barcodes (ids: 115, 121, 124, 127, 640-645) — заменить на реальные из Sheet
- [ ] **FILL** Sheet Col B = "Evelyn" (row 165)
- [ ] **RUN SYNC** `python scripts/sync_sheets_to_supabase.py --level all` — создаст 30 missing modeli_osnova + привяжет 54 modeli через FK
- [ ] **DELETE** Sheet cols 34-36 ("не нужно") + cols 37, 71, 77, 89 (пустые)
- [ ] **DROP** 3 infra tables: report_runs, analytics_rules, notification_log

### Требуют подтверждения (MEDIUM confidence)

- [ ] **MERGE** 16 групп дубликатов в cveta (проверить color_code у каждой группы перед merge)
- [ ] **ADD** статусы "Запуск" и "Выводим" в таблицу statusy + маппинг sync
- [ ] **IMPLEMENT** sync для "Склейки Озон" (1405 строк в Sheet, 0 в БД)
- [ ] **ARCHIVE** agent_runs (650 rows) + orchestrator_runs (130 rows) — export CSV, затем решить: добавить dashboard или удалить writes из logger.py
- [ ] **ADD** data validation dropdown на col G (Статус) в Sheet

### Требуют обсуждения (LOW confidence)

- [ ] 66 orphan artikuly — оставить (планируемые продукты) или пометить статусом
- [ ] 73 модели с NULL nazvanie_en — оставить или добавить колонку EN name в Sheet
- [ ] 5 kategorii + 2 kollekcii без использования — оставить для будущих моделей
- [ ] Schema reorganization (CREATE SCHEMA infra) — оценить effort vs benefit
- [ ] archive_records (0 rows) — оставить dormant или удалить с archive_service.py
- [ ] Вынести расчётные метрики из Sheet (cols 78-91) — стоит ли?

---

## Методология

**Архитектура аудита:** 7 субагентов в 3 волнах + оркестратор

```
Wave 1 (parallel):  DB Reader | Sheet Reader | Code Scanner
                         ↓            ↓             ↓
Wave 2 (parallel):  PIM Auditor | Sheet Analyst | Infra Auditor
                         ↓            ↓             ↓
Wave 3 (single):         └──── Verifier ────────────┘
                                   ↓
Final:                    Orchestrator (этот отчёт)
```

**Все операции — READ ONLY.** Никаких изменений в БД или Sheet не производилось.
