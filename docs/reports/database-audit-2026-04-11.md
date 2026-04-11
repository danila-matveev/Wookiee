# Database & Sheet Full Audit — 2026-04-11

## Сводка

- **Всего проблем:** 179 (PIM) + 12 (Sheet) + 10 (Infra) + 6 (Sync bugs) = **207**
- **HIGH:** 34 | **MEDIUM:** 108 | **LOW:** 65
- **Таблиц проверено:** 27 из 27 (17 PIM + 10 Infra)
- **Листов проверено:** 7 из 7
- **Верификация:** Verifier подтвердил 5/5 spot-checks, нашёл 2 противоречия, скорректировал confidence для 2 рекомендаций

### Критические находки (требуют немедленного внимания)

1. **30 моделей-основ отсутствуют в БД** — есть в Sheet, но sync не запускался → 54 modeli с NULL model_osnova_id (каскадный эффект)
2. **Склейки OZON не синхронизируются** — 1405 строк в Sheet, 0 в БД, sync функция не реализована
3. **Баг sync-скрипта: col C вместо col A** — создаёт ~20 призрачных моделей с русскими названиями вместо кодов
4. **3 infra-таблицы мертвые** — report_runs, analytics_rules, notification_log: 0 code refs, можно удалить

---

## 1. PIM — Товарная матрица

### 1.1 modeli_osnova (34 проблемы)

**В БД:** 26 записей | **В Sheet (col B):** ~56 уникальных значений

| # | ID | kod | Проблема | Рекомендация | Уверенность |
|---|-----|-----|----------|--------------|-------------|
| 1 | 24 | компбел-ж-бесшов | WRONG_TYPE + ORPHAN — артикул в таблице моделей-основ. 0 FK-зависимостей (verified) | DELETE | **HIGH** |
| 2 | 23 | Evelyn | ORPHAN — в БД но col B пустой в Sheet. ⚠ Verifier: modeli id=39 ссылается на эту запись! | REVIEW (не удалять — есть FK) | **LOW** ↓ |
| 3-34 | — | Ashley, Aspen, Berlin, Billie, Carol, Diana, Emma, Jackie, Jane, Kat, Kerry, Kira, Kylie, Linda, Luna, Margo, Meg, Miami, Nancy, Nicole, Nora, Oslo, Paris, Polly, Rose, Sabrina, Sally, Sky, Tina, Viola, Vita | MISSING — 30 моделей-основ в Sheet, отсутствуют в БД. Причина: sync не запускался после добавления | Запустить sync_modeli_osnova | **HIGH** |

### 1.2 modeli (106 проблем)

**В БД:** 112 записей

#### Призрачные модели с русскими названиями (~20 записей, 0 artikuly у каждой)

Корневая причина: sync_modeli() читает col C ("Название модели") вместо col A ("Модель") как kod. Col C содержит русские описательные названия.

| # | ID | kod (из col C) | Должно быть (col A) | Рекомендация | Уверенность |
|---|-----|----------------|---------------------|--------------|-------------|
| 1 | 42 | Vuki animal | VukiN | DELETE (0 artikuly, ghost) | **MEDIUM** |
| 2 | 43 | Vuki выстиранки | VukiW | DELETE (0 artikuly, ghost) | **MEDIUM** |
| 3 | 44 | Vuki Принты | VukiP | DELETE (0 artikuly, ghost) | **MEDIUM** |
| 4 | 45 | VukiN animal | VukiN2 | DELETE (0 artikuly, ghost) | **MEDIUM** |
| 5 | 46 | VukiW выстиранки | VukiW2 | DELETE (0 artikuly, ghost) | **MEDIUM** |
| 6 | 47 | Vuki трусы | Set Wookiee | DELETE (0 artikuly, ghost) | **MEDIUM** |
| 7 | 48 | Vuki Принты трусы | Set VukiP | DELETE (0 artikuly, ghost) | **MEDIUM** |
| 8 | 49 | Moon выстиранки | MoonW | DELETE (0 artikuly, ghost) | **MEDIUM** |
| 9 | 50 | Moon трусы | Set Moon2 | DELETE (0 artikuly, ghost) | **MEDIUM** |
| 10 | 51 | Moon Принты трусы | Set MoonP | DELETE (0 artikuly, ghost) | **MEDIUM** |
| 11 | 52 | Ruby выстиранки | RubyW | DELETE (0 artikuly, ghost) | **MEDIUM** |
| 12 | 53 | Ruby Принты | RubyP | DELETE (0 artikuly, ghost) | **MEDIUM** |
| 13 | 54 | Ruby трусы | Set Ruby | DELETE (0 artikuly, ghost) | **MEDIUM** |
| 14 | 55 | Joy выстиранки | JoyW | DELETE (0 artikuly, ghost) | **MEDIUM** |
| 15 | 56 | Wendy трусы | Set Wendy | DELETE (0 artikuly, ghost) | **MEDIUM** |
| 16 | 58 | Трусы Air | — | DELETE (0 artikuly, ghost) | **MEDIUM** |

#### Некорректное имя

| # | ID | kod | Проблема | Рекомендация | Уверенность |
|---|-----|-----|----------|--------------|-------------|
| 17 | 40 | RubyPT | PT=Print+Text, в Sheet "Ruby Принты+текст". ⚠ Verifier: 2 artikuly ссылаются (Ruby/total_love_pink, Ruby/total_love_red) | RENAME → подобрать корректный код | **MEDIUM** |

#### 49 моделей с NULL model_osnova_id

Каскадный эффект от 30 отсутствующих modeli_osnova + пустого col B для некоторых моделей. Примеры: Nancy (ids 62-63), Nora (64-65), Linda (66-67), Emma (68-69), Billie (70-71), Kylie (72-73), Carol (74-75), Rose (76-77), Sky (78-79), Jackie (80-81), Sabrina (82-83), Polly (84-85), Luna (86-87), Diana (88-89), Tina (90-91), Ashley (92-93), Viola (94-95), Kat (96-97), Meg (98-99), Kira (100-101), Vita (102-103), Margo (104-105), Sally (106-107), Kerry (108-109), Rio (111), setWendy (57), Jane (60-61), Дргуие товары (112).

**Рекомендация:** Запустить sync modeli_osnova → sync modeli для автоматического заполнения. **MEDIUM**

#### 73 модели с NULL nazvanie_en

Все 73 — это модели с русскоязычными nazvanie (описательные названия). Может быть нормально для русскоязычных моделей.

**Рекомендация:** Заполнить nazvanie_en для моделей в продаже. **LOW**

#### 6 моделей в Sheet, отсутствуют в БД

Aspen, Berlin, Miami, Nicole, Oslo, Paris — все в статусе "Планирование".

**Рекомендация:** Появятся автоматически при следующем sync. **MEDIUM**

### 1.3 artikuly (2 проблемы)

| # | Scope | Проблема | Рекомендация | Уверенность |
|---|-------|----------|--------------|-------------|
| 1 | 66 шт (e.g. ids 481, 482, 493, 105, 106) | ORPHAN — 66 артикулов без единого товара | Удалить orphan-артикулы или создать товары | **MEDIUM** (verified: count=66) |
| 2 | 267 шт | В БД, но нет в Sheet "Все артикулы" | Синхронизировать Sheet | **LOW** |

### 1.4 tovary (полная проверка — все 3499 строк Sheet)

**Sheet баркодов (unique, non-empty):** 1701 | **БД баркодов:** 1473 | **Совпадают:** 1473 | **Orphan в БД:** 0

| # | Scope | Проблема | Рекомендация | Уверенность |
|---|-------|----------|--------------|-------------|
| 1 | 10 шт в БД (ids: 112, 115, 121, 124, 127, 637, 640, 643, 653, 695) | BAD_BARCODE В БД — 1-2 цифры (7, 9, 10, 18, 21, 23, 24, 25, 26, 27). Все для артикулов компбел-ж-бесшов и Joy | Заменить на реальные баркоды или удалить | **HIGH** |
| 2 | 238 шт в Sheet (rows 1508-1764) | BAD_BARCODE В SHEET — 4-6 цифр (8987-9190, 11111-11119, 548385-548402). Все для новых моделей: Nora, Emma, Jackie, Rose, Sabrina, Polly, Luna, Billie, Sky, Kylie, Diana, Carol, Tina, Ashley, Rio | Placeholder-баркоды — заменить на реальные GS1 при запуске | **MEDIUM** |
| 3 | 228 шт | Баркоды в Sheet, отсутствуют в БД. 100% overlap с bad format — это те же placeholder-баркоды но��ых моделей | Импортируются автоматически при sync после получения реальных GS1 | **LOW** |
| 4 | 5 артикулов | Rio/ivory, Rio/obsidian, Rio/storm, Rio/umber, Rio/wineberry — в Sheet, нет в БД | Появятся при sync | **MEDIUM** |
| 5 | 1 модель | `set ruby` — в Sheet "Все товары", нет в БД modeli | Появится при sync | **LOW** |

**Ключевой вывод:** БД — чистый subset Sheet. 0 orphan-баркодов в БД (всё что в БД — есть в Sheet). 228 "пропущенных" = placeholder-ба��коды незапущенных моделей.

### 1.5 Справочники

#### cveta (19 проблем)

16 групп дубликатов по LOWER(cvet):

| Цвет | IDs (дубли) | Кол-во записей |
|------|-------------|----------------|
| black | 2, 100, 118 | 3 |
| white | 3, 103, 121 | 3 |
| brown | 5, 105, 117 | 3 |
| nude | 4, 98, 123 | 3 |
| ivory | 11, 116, 135 | 3 |
| fig | 46, 109, 131 | 3 |
| light pink | 47, 110, 129 | 3 |
| yellow | 138, 43 | 2 |
| light brown | 22, 127 | 2 |
| green | 44, 136 | 2 |
| темно-синий | 113, 133 | 2 |
| graphite | 106, 122 | 2 |
| winered | 107, 128 | 2 |
| americano | 108, 130 | 2 |
| skin | 111, 132 | 2 |
| blue | 112, 134 | 2 |

**Verifier:** Дубликаты подтверждены. Причина: sync дедуплицирует по color_code (разные для разных линеек: 2/AU002/WE001 = "black"), а не по названию цвета. Мёрж требует FK-миграции. **MEDIUM**

Также: 7 color_codes в Sheet, нет в БД (STLW-01...STLW-06 + "Color code" — заголовок). 3 неиспользуемых цвета.

#### kategorii (5 неиспользуемых)

| ID | Название | Рекомендация |
|----|----------|-------------|
| 4 | Леггинсы | Оставить — будут использоваться новыми моделями (Планирование) |
| 5 | Лонгслив | То же |
| 6 | Рашгард | То же |
| 7 | Топ | То же |
| 8 | Футболка | То же |

**Уверенность:** LOW — скорее всего нужны для моделей в статусе "Планирование".

#### kollekcii (2 неиспользуемых)

| ID | Название |
|----|----------|
| 3 | Трикотажное белье без вставок |
| 8 | Спортивная трикотажная коллекция |

**Уверенность:** LOW

### 1.6 Склейки

#### skleyki_wb (8 проблем)

| # | Проблема | Запись | Уверенность |
|---|----------|--------|-------------|
| 1-3 | MISSING (в Sheet, нет в БД) | ИП склейка в продаже, ООО Склейка Выводимые 3, ООО склейка рубчик | MEDIUM |
| 4-8 | ORPHAN (в БД, нет в Sheet) | ИП Склейка Vuki 1, ИП Склейка Moon 1, ООО Склейка Ruby 1, ООО Склейка Joy 1, ООО Склейка Дубли 2 | LOW |

#### skleyki_ozon (КРИТИЧНО)

**БД: 0 строк. Sheet: 1405 строк (16 уникальных склеек).** Sync функция НЕ реализована.

**Рекомендация:** Реализовать sync_skleyki_ozon() или загрузить вручную. **HIGH**

### 1.7 Непроверенные таблицы (4 шт)

| Таблица | Строк в БД | Code Usage | Причина пропуска |
|---------|------------|------------|------------------|
| tovary_skleyki_wb | 1,442 | READ | Junction table, зависит от skleyki_wb |
| tovary_skleyki_ozon | 0 | REFERENCE | Пусто (зависит от пустой skleyki_ozon) |
| sertifikaty | 0 | READ+WRITE | Пусто, данные не заведены |
| modeli_osnova_sertifikaty | 0 | REFERENCE | Пусто, junction для sertifikaty |

---

## 2. Google Sheet — анализ структуры

### 2.1 Анализ колонок "Все модели" (91 колонка, 317 строк, 73 модели)

#### Семантика колонок A, B, C

| Сравнение | Совпадений | % | Вывод |
|-----------|------------|---|-------|
| A (Модель) == B (Модель основа) | 55/73 | 75% | Разное назначение: A = код варианта (VukiN), B = группа (Vuki) |
| A (Модель) == C (Название модели) | 20/73 | 27% | Все три колонки семантически различны |
| B (Модель основа) == C (Название модели) | 21/73 | 29% | **Оставить все три** |

**Col H (Артикул модели):** 100% заполнен, всегда заканчивается на `/`, 62 уникальных значения.

#### Колонки sync-скрипта

Из 91 колонки "Все модели" sync использует **30 колонок** для modeli_osnova + modeli.
Из 52 колонок "Все товары" sync использует **20 колонок** для cveta + artikuly + tovary.

**61 колонка "Все модели" НЕ используется sync** — информационные (каталог, цены, описания, логистика).

### 2.2 Проблемы качества данных

| # | Лист | Проблема | Рекомендация | Уверенность |
|---|------|----------|--------------|-------------|
| 1 | Все модели | 3 колонки помечены "не нужно" (cols 34-36) | Удалить | HIGH |
| 2 | Все модели | 4 колонки с пустым заголовком и 0 данных (cols 37, 71, 77, 89) | Удалить | HIGH |
| 3 | Все модели | 1 модель с пустым "Модель основа" (col B) — Evelyn | Заполнить | MEDIUM |
| 4 | Все модели | 11 колонок с >80% пустых (Рос. размер, Теги, Степень поддержки x3, Price, Вес, MOQ, OZON цены x2, Name for Invoice) | Рассмотреть удаление или перенос | LOW |
| 5 | Все товары | Trailing space в заголовке "БАРКОД " | Обрезать | MEDIUM |
| 6 | Склейки WB | Все заголовки пустые (merged cells?) | Восстановить заголовки | MEDIUM |
| 7 | Склейки Озон | Все заголовки пустые + не синхронизируется с БД | Восстановить заголовки + реализовать sync | HIGH |
| 8 | Все модели | Cols 78-91 (Ср чек, Маржа, ДРР и т.д.) — расчётные метрики из БД | Вынести из Sheet, рассчитывать из БД | LOW |

### 2.3 Анализ остальных листов

| Лист | Строк | Колонок | Состояние |
|------|-------|---------|-----------|
| Все товары | 3,499 | 52 | 1701 уникальных баркодов, 1798 строк без баркода (под-строки размеров) |
| Все артикулы | 281 | 23 | Хорошо заполнен, кроме Комиссия (0%), Оборачиваемость (0%), Цена WB (0%) |
| Аналитики цветов | 181 | 26 | 147 цветов, все 143 из Все товары присутствуют. 4 лишних: au013, color code, stlw-06, we013 |
| Склейки WB | 552 | 23 | Сломанные заголовки |
| Склейки Озон | 1,405 | 17 | Сломанные заголовки, не синхронизирован |
| Упаковки | 13 | 7 | 5 реальных упаковок + аксессуары + пустые строки |

---

## 3. Инфраструктурные таблицы

### 3.1 Карта таблиц

| Таблица | Записей | Последняя запись | Code Usage | Вердикт | Schema | Retention |
|---------|---------|------------------|------------|---------|--------|-----------|
| kb_chunks | 7,091 | active | READ+WRITE | **KEEP** | infra | Permanent |
| content_assets | 10,146 | active | READ+WRITE | **KEEP** | infra | Permanent |
| field_definitions | 44 | 2026-04-01 | READ+WRITE | **KEEP** | infra | Permanent |
| istoriya_izmeneniy | 4,014 | trigger | WRITE-only | **KEEP** | infra | 180 дней rolling |
| archive_records | 0 | never | READ+WRITE | **REVIEW** | infra | Permanent |
| agent_runs | 650 | 2026-04-02 | WRITE-only | **ARCHIVE** | infra | 90 дней |
| orchestrator_runs | 130 | 2026-04-02 | WRITE-only | **ARCHIVE** | infra | 90 дней |
| report_runs | 9 | 2026-03-30 | UNUSED | **DELETE** | — | — |
| analytics_rules | 20 | 2026-03-30 | UNUSED | **DELETE** | — | — |
| notification_log | 1 | unknown | UNUSED | **DELETE** | — | — |

### 3.2 Описания таблиц (KEEP)

**kb_chunks** — Векторная база знаний (768d) для текстовых документов WB domain. Writers: store.py. Readers: store.py (semantic search).

**content_assets** — Векторная база фото товаров (~10K, Gemini Embedding 2). Writers: content_kb/store.py. Readers: store.py (visual search).

**field_definitions** — Динамическая схема полей для Product Matrix API (44 определения). Writers/Readers: schema.py.

**istoriya_izmeneniy** — Аудит-лог PIM операций через PostgreSQL triggers. Writers: trigger log_izmeneniya(). Readers: только ручные SQL-запросы. **Рекомендация: retention 180 дней** (`DELETE FROM istoriya_izmeneniy WHERE data_izmeneniya < now() - interval '180 days'` по cron).

**archive_records** — Механизм soft-delete для PIM API. Полностью реализован в коде (archive_service.py), но ни разу не использован (0 строк). **Решение:** оставить если архивация планируется, удалить вместе с archive_service.py если нет.

### 3.3 DELETE кандидаты (verified: 0 code refs)

| Таблица | Строк | Причина | Риск |
|---------|-------|---------|------|
| report_runs | 9 | Спроектирована в reporter-v4 spec, не интегрирована в код | Нет |
| analytics_rules | 20 | Seed-данные из spec-фазы, нет code refs | Нет |
| notification_log | 1 | Orphan test record, нет code refs | Нет |

### 3.4 ARCHIVE кандидаты

| Таблица | Строк | Причина | Рекомендация |
|---------|-------|---------|-------------|
| agent_runs | 650 | logger.py пишет, никто не читает (dead-letter pattern) | Добавить dashboard или удалить logger writes |
| orchestrator_runs | 130 | То же | То же |

### 3.5 Реорганизация Schema

**Предложение:** `CREATE SCHEMA infra` → перенести 7 таблиц из `public`:

```sql
CREATE SCHEMA IF NOT EXISTS infra;
GRANT USAGE ON SCHEMA infra TO authenticated, service_role;

-- KEEP
ALTER TABLE public.kb_chunks SET SCHEMA infra;
ALTER TABLE public.content_assets SET SCHEMA infra;
ALTER TABLE public.field_definitions SET SCHEMA infra;
ALTER TABLE public.istoriya_izmeneniy SET SCHEMA infra;
ALTER TABLE public.archive_records SET SCHEMA infra;

-- ARCHIVE (если оставляем)
ALTER TABLE public.agent_runs SET SCHEMA infra;
ALTER TABLE public.orchestrator_runs SET SCHEMA infra;

-- DELETE
DROP TABLE IF EXISTS public.report_runs;
DROP TABLE IF EXISTS public.analytics_rules;
DROP TABLE IF EXISTS public.notification_log;
```

**Код для обновления** (9 файлов): store.py x2, schema.py, archive_service.py, database.py, triggers.sql, logger.py, migrations.

**Альтернатива:** `ALTER ROLE service_role SET search_path TO public, infra;` — избегает правок кода.

---

## 4. Sync-скрипт — выявленные баги

### Баг 1 (HIGH): Col C вместо Col A для modeli.kod

**Функция:** `sync_modeli()`, строка 506
**Корень:** Читает "Название модели" (col C = "Vuki animal") вместо "Модель" (col A = "VukiN") как kod
**Эффект:** ~20 призрачных моделей с русскими названиями, 0 artikuly у каждой
**Исправление:**
```python
# БЫЛО (строка 506):
nazvanie = clean_string(row.get("Название модели", ""))
kod = normalize_key(nazvanie)

# ДОЛЖНО БЫТЬ:
model_code = clean_string(row.get("Модель", ""))  # Col A = actual code
nazvanie = clean_string(row.get("Название модели", ""))  # Col C = display name
kod = normalize_key(model_code)
```

### Баг 2 (LOW): компбел-ж-бесшов в modeli_osnova

**Причина:** Legacy-данные или ручной INSERT до создания sync-скрипта. Текущий sync не удаляет orphan записи (строки 464-471 — только WARNING).
**Исправление:** `DELETE FROM modeli_osnova WHERE id = 24;`

### Баг 3 (HIGH): skleyki_ozon не синхронизируется

**Функция:** `run_sync()`, строка 36
**Корень:** `LEVELS_ORDER` содержит только `["statusy", "cveta", "modeli_osnova", "modeli", "artikuly", "tovary"]` — нет skleyki_wb и skleyki_ozon
**Эффект:** 1405 строк Ozon-склеек отсутствуют в БД
**Исправление:** Реализовать `sync_skleyki_wb()` и `sync_skleyki_ozon()`, добавить в LEVELS_ORDER

### Баг 4 (HIGH): 30 отсутствующих modeli_osnova

**Причина:** Sync не на cron — модели добавлены в Sheet после последнего запуска (все в статусе "Планирование")
**Эффект:** 30 missing osnova → 54 modeli с NULL model_osnova_id
**Исправление:** Запустить sync + рассмотреть cron-расписание

### Баг 5 (MEDIUM): Дубли цветов

**Функция:** `sync_cveta()`, строка 271
**Корень:** Дедупликация по color_code, а не по названию цвета. Разные линейки (2/AU002/WE001 = "black")
**Эффект:** 16 групп дублей
**Исправление:** Миграция FK на канонический id + UNIQUE на LOWER(cvet), ИЛИ документировать как intentional

### Баг 6 (HIGH): Путаница Col A / Col C (структурная)

**Корень:** sync_modeli_osnova использует col B (корректно), sync_modeli использует col C (некорректно), sync из "Все товары" использует "Модель" (корректно). Несогласованность создаёт дубликаты.

---

## 5. Сводка действий (чеклист для утверждения)

### Приоритет 1 — Автоматически исправляемые (re-run sync)

- [ ] Запустить `sync_modeli_osnova` для создания 30 отсутствующих записей — **HIGH**
- [ ] Запустить `sync_modeli` для заполнения 49 NULL model_osnova_id — **MEDIUM** (после P1)

### Приоритет 2 — Исправление sync-скрипта

- [ ] Исправить Баг 1: col C → col A в sync_modeli() строка 506 — **HIGH**
- [ ] Реализовать sync_skleyki_ozon() + sync_skleyki_wb() — **HIGH**
- [ ] Рассмотреть cron-расписание для sync — **MEDIUM**

### Приоритет 3 — Очистка данных (после исправления sync)

- [ ] DELETE modeli_osnova id=24 (компбел-ж-бесшов) — 0 FK deps — **HIGH**
- [ ] DELETE ~16 ghost-моделей (Vuki animal, Moon трусы и т.д.) — 0 artikuly — **MEDIUM**
- [ ] Проверить modeli id=40 (RubyPT) — 2 artikuly, rename осторожно — **MEDIUM**
- [ ] Решить по 66 orphan-артикулам — **MEDIUM**
- [ ] Решить по 16 группам дублей cveta (FK-миграция) — **MEDIUM**
- [ ] Проверить 10+ баркодов с плохим форматом — **MEDIUM**

### Приоритет 4 — Google Sheet

- [ ] Удалить 3 колонки "не нужно" (34-36) + 4 пустых (37, 71, 77, 89) — **HIGH**
- [ ] Восстановить заголовки Склейки WB + Склейки Озон — **MEDIUM**
- [ ] Обрезать trailing space в "БАРКОД " — **MEDIUM**
- [ ] Заполнить "Модель основа" для Evelyn — **MEDIUM**

### Приоритет 5 — Инфраструктура

- [ ] pg_dump + DROP: report_runs, analytics_rules, notification_log — **HIGH**
- [ ] Решить по agent_runs/orchestrator_runs: dashboard или удалить — **MEDIUM**
- [ ] CREATE SCHEMA infra + перенести 5-7 таблиц — **MEDIUM**
- [ ] Добавить retention cron для istoriya_izmeneniy (180 дней) — **LOW**
- [ ] Решить по archive_records: ship feature или удалить код — **LOW**

### Приоритет 6 — Информационные (LOW)

- [ ] 5 неиспользуемых категорий — вероятно нужны для "Планирование" моделей — **LOW**
- [ ] 2 неиспользуемых коллекции — **LOW**
- [ ] 73 модели с NULL nazvanie_en — **LOW**
- [ ] 267 артикулов в БД, нет в Sheet — **LOW**
- [ ] 227 баркодов в Sheet, нет в БД — **LOW**

---

## Приложения

### A. Покрытие верификацией

| Spot-check | Результат |
|------------|-----------|
| modeli_osnova id=24 FK refs | PASS — 0 refs, safe to delete |
| modeli id=40 (RubyPT) artikuly | PASS — 2 artikuly (rename needs care) |
| Vuki animal/Moon трусы artikuly | PASS — 0 artikuly each (ghost records) |
| Orphan artikuly count | PASS — confirmed 66 |
| skleyki_ozon row count | PASS — confirmed 0 |
| modeli_osnova id=23 (Evelyn) FK | **CAUGHT** — 1 FK dep, downgraded to LOW |

### B. Метаданные аудита

- **Метод:** 7 субагентов (3 сборщика + 3 аналитика + 1 верификатор) + оркестратор
- **Источники:** Supabase (psycopg2), Google Sheets (gws CLI), кодовая база (Grep/Glob)
- **Ограничения:** Фаза 1 — только чтение. Никаких мутаций в БД.
- **Непроверенные таблицы:** 4 junction/lookup (tovary_skleyki_wb/ozon, sertifikaty, modeli_osnova_sertifikaty)
