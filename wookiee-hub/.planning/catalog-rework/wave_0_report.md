# Wave 0 — Final Report

**Дата:** 2026-05-07
**Ветка:** `catalog-rework-2026-05-07`
**Проект Supabase:** `gjvwcdtfglupewcwzfhw`

## Резюме

Wave 0 (data-migration) выполнен полностью и атомарно. Все 11 шагов прошли. БД готова к Wave 1 (фронт-каталог).

**Все verification W0.1–W0.3 чеки pass.**

---

## Применённые миграции

| Версия              | Имя                                              |
|---------------------|--------------------------------------------------|
| 20260507203526      | catalog_statusy_extend_2026_05_07                |
| 20260507203555      | catalog_dedupe_kategorii_kollekcii_2026_05_07    |
| 20260507203622      | catalog_enrich_reference_columns_2026_05_07      |
| 20260507203649      | catalog_new_tables_2026_05_07                    |
| 20260507203809      | catalog_rls_2026_05_07                           |
| 20260507203850      | catalog_seed_2026_05_07                          |

---

## Размеры таблиц (DO / POSLE)

| Таблица            | DO   | POSLE | Δ            |
|--------------------|------|-------|--------------|
| statusy            | 7    | 23    | +16 (−1+17)  |
| kategorii          | 11   | 10    | −1 (dedup)   |
| kollekcii          | 11   | 10    | −1 (dedup)   |
| fabriki            | 6    | 6     | 0            |
| importery          | 2    | 2     | 0            |
| razmery            | 6    | 6     | 0            |
| modeli_osnova      | 56   | 56    | 0            |
| modeli             | 75   | 75    | 0            |
| artikuly           | 553  | 553   | 0            |
| tovary             | 1473 | 1473  | 0            |
| cveta              | 146  | 146   | 0            |
| sertifikaty        | 0    | 0     | 0            |
| semeystva_cvetov   | —    | 5     | NEW          |
| upakovki           | —    | 10    | NEW          |
| kanaly_prodazh     | —    | 4     | NEW          |
| ui_preferences     | —    | 0     | NEW          |

---

## Скрипты — что обновлено

| Скрипт                                | Затронуто | Лог                              |
|---------------------------------------|-----------|----------------------------------|
| migrate-cveta-semeystvo.py            | 146/146   | wave_0_cveta_semeystvo.log       |
| migrate-cveta-hex.py                  | 144/146   | wave_0_cveta_hex.log             |
| sync-model-statuses-from-sheet.py     | 56/56     | wave_0_model_statuses.log        |

---

## Verification W0.1 — БД-проверки

| Чек                                       | Ожидание | Факт          | Статус |
|-------------------------------------------|----------|---------------|--------|
| `statusy.tip` распределение               | model=7, artikul=3, product=6, sayt=3, color=3, lamoda=1 | model=7, artikul=3, product=6, sayt=3, color=3, lamoda=1 | PASS |
| `modeli_osnova WHERE status_id IS NULL`   | 0        | 0             | PASS   |
| `cveta WHERE semeystvo IS NULL`           | 0        | 0             | PASS   |
| `cveta WHERE hex IS NULL`                 | ≤30      | 2             | PASS   |
| `kategorii WHERE nazvanie LIKE Лег*инсы`  | 1        | 1             | PASS   |
| `kollekcii WHERE nazvanie LIKE Спортивная трикотаж%` | 1 | 1 | PASS |
| `to_regclass` 4 новые таблицы             | not null | все 4 not null | PASS  |
| `semeystva_cvetov`                        | 5        | 5             | PASS   |
| `kanaly_prodazh`                          | 4        | 4             | PASS   |
| `upakovki`                                | 10       | 10            | PASS   |

## Verification W0.2 — RLS

Каждая каталоговая таблица ≥4 политик:

| Таблица           | Политик |
|-------------------|---------|
| statusy           | 5       |
| kategorii         | 5       |
| kollekcii         | 5       |
| fabriki           | 5       |
| importery         | 5       |
| razmery           | 5       |
| modeli_osnova     | 5       |
| modeli            | 5       |
| artikuly          | 5       |
| tovary            | 5       |
| cveta             | 5       |
| sertifikaty       | 5       |
| semeystva_cvetov  | 5       |
| upakovki          | 5       |
| kanaly_prodazh    | 5       |
| ui_preferences    | 5       |

Структура политик на каждой таблице:
- `service_role_full_access_<tbl>` — postgres role, ALL (USING true / WITH CHECK true)
- `authenticated_select_<tbl>` — authenticated, SELECT (USING true)
- `authenticated_insert_<tbl>` — authenticated, INSERT (WITH CHECK true)
- `authenticated_update_<tbl>` — authenticated, UPDATE (USING true / WITH CHECK true)
- `authenticated_delete_<tbl>` — authenticated, DELETE (USING true)

## Verification W0.3 — Backups

```
backups/wave_0/
├── statusy_before.json       (7 строк)
├── kategorii_before.json     (11 строк, с дублём)
├── kollekcii_before.json     (11 строк, с дублём)
├── modeli_status_before.json (56 строк, все status_id=null)
└── cveta_before.json         (146 строк, все semeystvo=null, нет hex)
```
Все 5 файлов на диске, закоммичены.

---

## Распределение цветов по семействам

| Семейство | Кол-во | Доля   |
|-----------|--------|--------|
| tricot    | 40     | 27.4 % |
| jelly     | 34     | 23.3 % |
| audrey    | 19     | 13.0 % |
| sets      | 8      | 5.5 %  |
| **other** | 45     | 30.8 % |

`other` непропорционально велик — это DQ-сюрприз (см. ниже).

---

## DQ-сюрпризы (выявлено в ходе Wave 0)

### 1. Префиксное правило `semeystvo` слабое для washed/pattern/multi-цветов
45 цветов попали в `other` (≈31 % всех). Из них:
- `wa1`–`wa11` (washed-серия) — 11 шт. Это варианты тех же jelly-цветов (wa1=Black washed, wa10=Brown washed). Логически — `jelly`.
- `P1`–`P9` (pattern-серия) — 9 шт. Цветочные/heart-принты. Можно ввести 6-е семейство `pattern` или оставить в `other`.
- `STLW-01..05`, `TLW-01..05` — 10 шт. Это коды LW (Lana Wear?), нужна декомпозиция.
- Мульти-цветовые коды (`93w7`, `15w7`, `36w311`, `36w3w11`, `36w83`) — 6 шт. Реально это композиты для наборов. Возможно их семейство = `sets`.
- Точно `other`: `БАЗА СИНГВЕР` (id=1) — служебная запись.

**Предложение для Wave 1+:** ввести 6-е семейство `pattern` для P-серии и расширить правило префикса для `wa*` → `jelly`. ИЛИ дать пользователю UI для ручного присвоения семейства из 5 кандидатов.

### 2. Лишний статус «Новый» (id=13) был ссылочно используем
Перед DELETE пришлось перепривязать FK:
- `cveta.status_id`: 8 строк → переведены на id=11 «Подготовка»
- `artikuly.status_id`: 1 строка
- `tovary.status_id`: 3 строки
- `tovary.status_ozon_id`: 3 строки

15 объектов имели «Новый» как статус. Решение «Подготовка» = разумный аналог (раз товар «новый» = значит «в подготовке к продаже»). Если кто-то знал какие именно — ревью в backup'е.

### 3. Sheet «Все модели» содержит вариации
Sheet хранит 73 строки, но 17 из них — вариации основных моделей (VukiN/W/P/2, Vuki2, MoonW/2, RubyW/P/PT, JoyW, Set Wookiee, etc.), которые в БД-схеме относятся к таблице `modeli` (вариации), а не `modeli_osnova` (базовые). Они НЕ попали в `modeli_osnova.status_id` — это нормально, т.к. в `modeli_osnova` всего 56 базовых, и все 56 получили статусы.

**Предложение для Wave 1+:** также синхронизировать статусы вариаций (модель→`modeli.status_id`) — отдельным скриптом если нужно.

### 4. `cveta` не имеет `color_ru`/`color_en` — есть `color` и `cvet`
Изначальный план говорил «добавить `color_en`». В реальности уже есть колонка `color` (английское название) и `cvet` (русское или дублирующее). НЕ дублировал — использовал существующие. То же по `lastovica` — уже varchar (план хотел boolean, отказался от пересоздания, чтобы сохранить пользовательские данные).

### 5. Цвет id=71 «Camomile» (P3) и id=1 «БАЗА СИНГВЕР»
Эти 2 цвета остались без `hex` — Camomile не в словаре (это цветочный принт), БАЗА СИНГВЕР — служебная запись без цвета. Оба ниже порога `≤30`.

---

## Цвета без hex (для UI-доработки)

| id | color_code     | color   | cvet            | semeystvo |
|----|----------------|---------|-----------------|-----------|
| 1  | 31             | NULL    | БАЗА СИНГВЕР    | tricot    |
| 71 | P3             | Camomile| Camomile        | other     |

Эти 2 записи требуют ручной заливки в UI через color-picker (или удаления, если служебные).

## Модели без status_id

**0 моделей.** Все 56 модели получили статус из Sheet.

---

## Cписок Sheet-моделей не найденных в `modeli_osnova` (FYI, не блокер)

Это вариации, относящиеся к `modeli`, не к `modeli_osnova`:
VukiN, VukiW, VukiP, Vuki2, VukiN2, VukiW2, Set Wookiee, Set VukiP, MoonW, Moon2, MoonW2, Set Moon2, Set MoonP, RubyW, RubyP, JoyW, RubyPT.

---

## Готовность к Wave 1

Всё готово:
- БД нормализована (нет дублей kategorii/kollekcii)
- 4 новые reference-таблицы созданы и заполнены seed-данными
- Все каталоговые таблицы имеют ≥4 RLS-политик для `authenticated`
- 6 типов статусов с UI-цветами проставлены
- 144 цвета с hex (фронт может рисовать swatch'и сразу)
- 56 моделей со статусами
- 5 backup-снэпшотов на случай отката

Можно стартовать Wave 1 (Foundation).
