# Предложения по улучшению БД: Wookiee Product Catalog

> **Дата:** 2026-02-25
> **Основание:** Аудит БД (`docs/plans/2026-02-25-db-audit-results.md`)
> **Scope:** Каталожная БД Supabase (`sku_database/`)

---

## Сводка предложений

| # | Предложение | Приоритет | Блокирует дашборд? | Миграция SQL |
|---|-------------|-----------|---------------------|-------------|
| P-001 | Импорт Ozon-склеек | CRITICAL | Да — модуль склеек Ozon | Нет (данные) |
| P-002 | Таблица `upakovki` (справочник упаковок) | HIGH | Да — визуал каталога | Да |
| P-003 | Поля сертификации в `modeli_osnova` | HIGH | Да — юридический блок | Да |
| P-004 | Поля компонентных SKU в `modeli_osnova` | HIGH | Да — состав комплекта | Да |
| P-005 | Многоканальные статусы товаров | MEDIUM | Да — управление каналами | Да |
| P-006 | Поле закупочной цены (Price CNY) | MEDIUM | Да — ценообразование | Да |
| P-007 | Поле `tovarnyy_znak` в `modeli_osnova` | MEDIUM | Да — юридический блок | Да |
| P-008 | Динамический pivot вместо хардкодного view | LOW | Да — матрица цветов | Да (VIEW) |
| P-009 | Поле `agreed` в таблице `cveta` | LOW | Нет | Да |
| P-010 | Compound UNIQUE на `artikuly(model_id, cvet_id)` | LOW | Нет | Да (INDEX) |

---

## P-001: Импорт Ozon-склеек [CRITICAL]

**Проблема:** Таблица `skleyki_ozon` существует в schema.sql, но пуста. Нет маппинга (`MAPPING_SKLEYKI_OZON`), нет метода импорта в `migrate_data.py`. Лист "Склейки Озон" содержит 1 406 строк данных.

**Текущее состояние:**
- Таблица `skleyki_ozon`: 0 записей
- Таблица `tovary_skleyki_ozon`: 0 записей
- Лист "Склейки Озон": ~20 уникальных склеек, 1 406 строк товаров

**Решение:**
1. Добавить `MAPPING_SKLEYKI_OZON` в `config/mapping.py`:
   ```python
   MAPPING_SKLEYKI_OZON = {
       'Склейкообразующий признак': 'nazvanie',
       '(col 0: юрлицо)': '_importer',
   }
   ```
2. Добавить метод `_migrate_skleyki_ozon()` в `migrate_data.py`
3. Заполнить `tovary_skleyki_ozon` через связь Артикул Ozon → artikuly → tovary

**Затронутые файлы:**
- `sku_database/config/mapping.py` — добавить маппинг
- `sku_database/scripts/migrate_data.py` — добавить метод импорта

---

## P-002: Таблица `upakovki` (справочник упаковок) [HIGH]

**Проблема:** Упаковки хранятся как строка в `modeli_osnova.upakovka` (напр. "Basic ZIP Pack Small"). Данные из листа "Упаковки" (цена, размеры, ссылка на дизайн) теряются.

**Текущее состояние:**
- `modeli_osnova.upakovka` = `VARCHAR(100)` (строка)
- Лист "Упаковки": 13 упаковок с ценой, размерами, ссылками

**Решение:** Создать справочную таблицу `upakovki` и заменить строковое поле на FK.

**Миграция:**
```sql
-- Новая таблица
CREATE TABLE upakovki (
    id SERIAL PRIMARY KEY,
    nazvanie VARCHAR(100) NOT NULL UNIQUE,
    cena_cny DECIMAL(8,2),
    dlina_cm DECIMAL(5,1),
    shirina_cm DECIMAL(5,1),
    vysota_cm DECIMAL(5,1),
    obem_l DECIMAL(6,3),
    ssylka_fayl VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE upakovki IS 'Справочник упаковок';

-- Миграция данных
INSERT INTO upakovki (nazvanie)
SELECT DISTINCT upakovka FROM modeli_osnova WHERE upakovka IS NOT NULL;

-- Добавить FK
ALTER TABLE modeli_osnova ADD COLUMN upakovka_id INT REFERENCES upakovki(id);
UPDATE modeli_osnova SET upakovka_id = u.id
FROM upakovki u WHERE modeli_osnova.upakovka = u.nazvanie;

-- (Позднее) Удалить старое строковое поле
-- ALTER TABLE modeli_osnova DROP COLUMN upakovka;
```

**Затронутые файлы:**
- `sku_database/database/schema.sql` — добавить таблицу
- `sku_database/database/models.py` — добавить ORM-модель
- `sku_database/config/mapping.py` — добавить маппинг для листа "Упаковки"
- `sku_database/scripts/migrate_data.py` — добавить метод импорта

---

## P-003: Поля сертификации в `modeli_osnova` [HIGH]

**Проблема:** В листе "Все модели" есть колонки "Сертификат" и "Срок действия", которые не импортируются. Для дашборда нужна информация о сертификатах.

**Текущее состояние:** Поля отсутствуют в БД.

**Решение:** Добавить 2 поля в `modeli_osnova`.

**Миграция:**
```sql
ALTER TABLE modeli_osnova ADD COLUMN sertifikat VARCHAR(200);
ALTER TABLE modeli_osnova ADD COLUMN sertifikat_srok_deystviya VARCHAR(100);
COMMENT ON COLUMN modeli_osnova.sertifikat IS 'Название сертификата';
COMMENT ON COLUMN modeli_osnova.sertifikat_srok_deystviya IS 'Срок действия сертификата';
```

**Затронутые файлы:**
- `sku_database/database/schema.sql`
- `sku_database/database/models.py`
- `sku_database/config/mapping.py` — добавить маппинг
- `sku_database/scripts/migrate_data.py` — добавить в `_migrate_modeli_osnova()`

---

## P-004: Поля компонентных SKU в `modeli_osnova` [HIGH]

**Проблема:** В листе "Все модели" есть колонки "Майк" (SKU майки) и "Трусы" (SKU трусов), которые описывают состав комплекта. Для дашборда это важно — показать из чего состоит комплект.

**Текущее состояние:** Поля отсутствуют в БД. Данные: "040" (трусы), "66161" (майка), "wen01" (топ Wendy), "dy01" (трусы Wendy).

**Решение:** Добавить 2 поля в `modeli_osnova`.

**Миграция:**
```sql
ALTER TABLE modeli_osnova ADD COLUMN sku_top VARCHAR(50);
ALTER TABLE modeli_osnova ADD COLUMN sku_trusy VARCHAR(50);
COMMENT ON COLUMN modeli_osnova.sku_top IS 'SKU топа/майки в комплекте';
COMMENT ON COLUMN modeli_osnova.sku_trusy IS 'SKU трусов в комплекте';
```

**Затронутые файлы:**
- `sku_database/database/schema.sql`
- `sku_database/database/models.py`
- `sku_database/config/mapping.py` — добавить: `'Майк': 'sku_top'`, `'Трусы': 'sku_trusy'`
- `sku_database/scripts/migrate_data.py` — добавить в `_migrate_modeli_osnova()`

---

## P-005: Многоканальные статусы товаров [MEDIUM]

**Проблема:** В Sheets товары имеют 4 статуса: "Статус товара" (WB), "Статус товара OZON", "Статус товара Сайт", "Статус товара Ламода". В БД импортируются только первые два.

**Текущее состояние:**
- `tovary.status_id` — статус WB ✅
- `tovary.status_ozon_id` — статус OZON ✅
- Статус Сайт — ❌ отсутствует
- Статус Ламода — ❌ отсутствует

**Решение:** Добавить 2 FK-поля в `tovary`.

**Миграция:**
```sql
ALTER TABLE tovary ADD COLUMN status_sayt_id INT REFERENCES statusy(id);
ALTER TABLE tovary ADD COLUMN status_lamoda_id INT REFERENCES statusy(id);
COMMENT ON COLUMN tovary.status_sayt_id IS 'Статус товара на сайте';
COMMENT ON COLUMN tovary.status_lamoda_id IS 'Статус товара на Lamoda';
```

**Затронутые файлы:**
- `sku_database/database/schema.sql`
- `sku_database/database/models.py`
- `sku_database/config/mapping.py` — добавить маппинг
- `sku_database/scripts/migrate_data.py` — добавить в `_migrate_tovary()`

---

## P-006: Поле закупочной цены (Price CNY) [MEDIUM]

**Проблема:** В листах "Все модели" и "Все товары" есть колонка "Price" (закупочная цена в CNY). Для дашборда важно видеть закупочную цену.

**Текущее состояние:** Поле отсутствует в БД. Данные в формате "¥10,95", "¥31,20".

**Решение:** Добавить поле на уровне `modeli_osnova` (цена на уровне модели) с возможностью переопределения на уровне `tovary` (цена зависит от размера).

**Миграция:**
```sql
ALTER TABLE modeli_osnova ADD COLUMN cena_zakupki_cny DECIMAL(8,2);
COMMENT ON COLUMN modeli_osnova.cena_zakupki_cny IS 'Закупочная цена (CNY) — базовая для модели';

ALTER TABLE tovary ADD COLUMN cena_zakupki_cny DECIMAL(8,2);
COMMENT ON COLUMN tovary.cena_zakupki_cny IS 'Закупочная цена (CNY) — для конкретного размера, если отличается от модели';
```

**Затронутые файлы:**
- `sku_database/database/schema.sql`
- `sku_database/database/models.py`
- `sku_database/config/mapping.py`
- `sku_database/scripts/migrate_data.py`

---

## P-007: Поле `tovarnyy_znak` в `modeli_osnova` [MEDIUM]

**Проблема:** В листе "Все модели" колонка "Товарный знак" (значение "Wookiee") не импортируется.

**Текущее состояние:** Поле отсутствует в БД.

**Решение:**
```sql
ALTER TABLE modeli_osnova ADD COLUMN tovarnyy_znak VARCHAR(100);
COMMENT ON COLUMN modeli_osnova.tovarnyy_znak IS 'Товарный знак (Wookiee)';
```

**Затронутые файлы:**
- `sku_database/database/schema.sql`
- `sku_database/database/models.py`
- `sku_database/config/mapping.py` — добавить: `'Товарный знак': 'tovarnyy_znak'`
- `sku_database/scripts/migrate_data.py`

---

## P-008: Динамический pivot вместо хардкодного view [LOW]

**Проблема:** View `v_matrica_cveta_modeli` содержит хардкод 11 из 22 моделей основы. При добавлении новых моделей view нужно пересоздавать вручную.

**Текущее состояние:**
```sql
-- Хардкод:
MAX(CASE WHEN mo.kod = 'Vuki' THEN '✓' ELSE '' END) AS "Vuki",
-- ... 11 моделей, отсутствуют: Valery, Miafull, Bella, Lana, Eva, Charlotte, Jess, Duo, Mia, Angelina, Set Wendy
```

**Решение:** Два варианта:

**Вариант A (рекомендуется для дашборда):** Использовать `v_cveta_modeli_osnova` (уже есть), который возвращает STRING_AGG моделей. Фронтенд парсит и строит pivot динамически.

**Вариант B (для SQL-клиентов):** Создать функцию `refresh_matrica()`, которая пересоздаёт view с актуальным списком моделей.

```sql
CREATE OR REPLACE FUNCTION refresh_matrica_cveta_modeli() RETURNS void AS $$
DECLARE
    v_sql TEXT;
    v_columns TEXT;
BEGIN
    SELECT string_agg(
        format('MAX(CASE WHEN mo.kod = %L THEN ''✓'' ELSE '''' END) AS %I', kod, kod),
        ', ' ORDER BY kod
    ) INTO v_columns
    FROM modeli_osnova;

    v_sql := format('CREATE OR REPLACE VIEW v_matrica_cveta_modeli AS
        SELECT c.color_code, c.cvet, %s
        FROM cveta c
        LEFT JOIN artikuly a ON a.cvet_id = c.id
        LEFT JOIN modeli m ON a.model_id = m.id
        LEFT JOIN modeli_osnova mo ON m.model_osnova_id = mo.id
        GROUP BY c.color_code, c.cvet
        ORDER BY c.color_code', v_columns);

    EXECUTE v_sql;
END;
$$ LANGUAGE plpgsql;
```

**Затронутые файлы:**
- `sku_database/database/schema.sql` — обновить view или добавить функцию

---

## P-009: Поле `agreed` в таблице `cveta` [LOW]

**Проблема:** В листе "Аналитики цветов" есть колонка "Agreed" (TRUE/FALSE) — согласован ли цвет. В БД этого поля нет.

**Решение:**
```sql
ALTER TABLE cveta ADD COLUMN agreed BOOLEAN DEFAULT FALSE;
COMMENT ON COLUMN cveta.agreed IS 'Цвет согласован (Agreed)';
```

**Затронутые файлы:**
- `sku_database/database/schema.sql`
- `sku_database/database/models.py`
- `sku_database/config/mapping.py`

---

## P-010: Compound UNIQUE на `artikuly(model_id, cvet_id)` [LOW]

**Проблема:** Бизнес-правило: один артикул = одна модель + один цвет. Но в БД нет constraint, предотвращающего дубли.

**Текущее состояние:** `artikuly.artikul` имеет UNIQUE, но нет compound unique на `(model_id, cvet_id)`.

**Решение:**
```sql
CREATE UNIQUE INDEX idx_artikuly_model_cvet
ON artikuly(model_id, cvet_id)
WHERE model_id IS NOT NULL AND cvet_id IS NOT NULL;
```

**Примечание:** Partial index, т.к. NULL-значения допустимы (при неполных данных).

---

## Порядок реализации

```
1. P-001 (Ozon склейки)     — данные, без миграции схемы
2. P-002 (Упаковки)         — новая таблица + FK
3. P-003 (Сертификаты)      — ALTER TABLE
4. P-004 (Компонентные SKU)  — ALTER TABLE
5. P-005 (Статусы каналов)   — ALTER TABLE
6. P-006 (Price CNY)         — ALTER TABLE
7. P-007 (Товарный знак)     — ALTER TABLE
8. P-008 (Динамический view) — VIEW/FUNCTION
9. P-009 (Agreed)            — ALTER TABLE
10. P-010 (Compound UNIQUE)  — INDEX
```

P-003 через P-007 и P-009 можно объединить в одну миграцию (`007_add_missing_catalog_fields.py`), т.к. все они — ALTER TABLE ADD COLUMN на существующие таблицы.
