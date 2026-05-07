# Wave 0 — Синхронизация данных из Google Sheet и БД-чистка

**Цель:** Привести БД в согласованное состояние ДО любого фронт-кода.
**Длительность:** 1 фаза, 1 агент (последовательно — каждый шаг от предыдущего зависит).
**Параллелизация:** НЕТ (это data-migration фаза, конфликты в БД недопустимы).

## Что делает Wave 0

1. Расширяет CHECK constraint на `statusy.tip` до 5 значений
2. Удаляет лишний статус «Новый» (id=13)
3. Добавляет 17 новых статусов (model/artikul/sayt/lamoda/color)
4. Сливает дубликаты в kategorii (id=9 → 4) и kollekcii (id=9 → 8)
5. Добавляет недостающие колонки в kategorii, kollekcii, fabriki, importery, razmery, modeli_osnova, cveta
6. Создаёт 4 новые таблицы: semeystva_cvetov, upakovki, kanaly_prodazh, ui_preferences
7. Заполняет cveta.semeystvo по правилу префиксов
8. Заполняет cveta.hex по словарю русских/английских названий
9. Тянет статусы моделей из Google Sheet «Все модели» и заполняет modeli_osnova.status_id
10. Заполняет seed-данные для semeystva_cvetov, upakovki, kanaly_prodazh

## Self-contained промпт для агента Wave 0

```
Ты выполняешь Wave 0 каталога Wookiee Hub — миграция БД и заливка данных из Google Sheet.

Контекст:
- Проект Supabase: gjvwcdtfglupewcwzfhw
- Source of truth для статусов: Google Sheet 19Nbr0kD8JJlwd7OCIMbM9qxucYNjmXnWtwJUgXv0vlg
- Service Account: services/sheets_sync/credentials/google_sa.json
- DQ-проблемы зафиксированы в `.planning/catalog-rework/01_DATA_AUDIT.md`
- Список статусов зафиксирован в `.planning/catalog-rework/02_STATUSES_FROM_SHEET.md`

Перед началом обязательно прочитай эти 2 файла + 03_GAP_LIST.md (раздел J).

Шаги (выполнять по порядку, после каждого — verify):

### Шаг 1: Backup
mkdir -p .planning/catalog-rework/backups/wave_0
Снять SQL-дамп через pg_dump или mcp supabase execute_sql + сохранить:
- statusy → backups/wave_0/statusy_before.json
- kategorii → backups/wave_0/kategorii_before.json
- kollekcii → backups/wave_0/kollekcii_before.json
- modeli_osnova (id, kod, status_id) → backups/wave_0/modeli_status_before.json
- cveta (id, color_code, color_ru, semeystvo, status_id) → backups/wave_0/cveta_before.json

### Шаг 2: Миграция statusy
Применить через mcp__plugin_supabase_supabase__apply_migration:
название миграции: catalog_statusy_extend_2026_05_07

```sql
-- 1. Расширить CHECK
ALTER TABLE statusy DROP CONSTRAINT IF EXISTS statusy_tip_check;
ALTER TABLE statusy ADD CONSTRAINT statusy_tip_check
  CHECK (tip IN ('model', 'artikul', 'product', 'sayt', 'color', 'lamoda'));

-- 2. Удалить лишний
DELETE FROM statusy WHERE id = 13;  -- Новый, нет в Sheet

-- 3. Добавить новые. Используй INSERT … ON CONFLICT DO NOTHING для идемпотентности
INSERT INTO statusy (nazvanie, tip, color) VALUES
  ('Планирование', 'model', 'gray'),
  ('Делаем образец', 'model', 'amber'),
  ('Закуп', 'model', 'blue'),
  ('Запуск', 'model', 'blue'),
  ('В продаже', 'model', 'green'),
  ('Выводим', 'model', 'red'),
  ('Архив', 'model', 'gray'),
  ('Запуск', 'artikul', 'blue'),
  ('Продается', 'artikul', 'green'),
  ('Выводим', 'artikul', 'red'),
  ('Опубликован', 'sayt', 'green'),
  ('Скрыт', 'sayt', 'gray'),
  ('Архив', 'sayt', 'gray'),
  ('Скрыт', 'lamoda', 'gray'),
  ('Продается', 'color', 'green'),
  ('Выводим', 'color', 'red'),
  ('Архив', 'color', 'gray')
ON CONFLICT DO NOTHING;
```

⚠ Обязательно проверь существование колонки `color` в `statusy`. Если её нет — добавь:
```sql
ALTER TABLE statusy ADD COLUMN IF NOT EXISTS color VARCHAR(20);
```

Verify: `SELECT tip, count(*) FROM statusy GROUP BY tip` — должно быть 6 типов.

### Шаг 3: Слияние дубликатов
Миграция: catalog_dedupe_kategorii_kollekcii_2026_05_07

```sql
-- Перевязать FK kategorii
UPDATE modeli_osnova SET kategoriya_id = 4 WHERE kategoriya_id = 9;
DELETE FROM kategorii WHERE id = 9;

-- Перевязать FK kollekcii
UPDATE modeli_osnova SET kollekciya_id = 8 WHERE kollekciya_id = 9;
DELETE FROM kollekcii WHERE id = 9;
```

⚠ Перед DELETE убедиться что нет других FK ссылающихся на 9 (через information_schema).

### Шаг 4: Расширение колонок справочников
Миграция: catalog_enrich_reference_columns_2026_05_07

```sql
ALTER TABLE kategorii
  ADD COLUMN IF NOT EXISTS opisanie TEXT;

ALTER TABLE kollekcii
  ADD COLUMN IF NOT EXISTS opisanie TEXT,
  ADD COLUMN IF NOT EXISTS god_zapuska INT;

ALTER TABLE fabriki
  ADD COLUMN IF NOT EXISTS gorod VARCHAR(100),
  ADD COLUMN IF NOT EXISTS kontakt VARCHAR(200),
  ADD COLUMN IF NOT EXISTS email VARCHAR(200),
  ADD COLUMN IF NOT EXISTS wechat VARCHAR(100),
  ADD COLUMN IF NOT EXISTS specializaciya TEXT,
  ADD COLUMN IF NOT EXISTS leadtime_dni INT,
  ADD COLUMN IF NOT EXISTS notes TEXT;

ALTER TABLE importery
  ADD COLUMN IF NOT EXISTS short_name VARCHAR(50),
  ADD COLUMN IF NOT EXISTS kpp VARCHAR(20),
  ADD COLUMN IF NOT EXISTS ogrn VARCHAR(20),
  ADD COLUMN IF NOT EXISTS bank VARCHAR(200),
  ADD COLUMN IF NOT EXISTS rs VARCHAR(30),
  ADD COLUMN IF NOT EXISTS ks VARCHAR(30),
  ADD COLUMN IF NOT EXISTS bik VARCHAR(20),
  ADD COLUMN IF NOT EXISTS kontakt VARCHAR(200),
  ADD COLUMN IF NOT EXISTS telefon VARCHAR(50);

ALTER TABLE razmery
  ADD COLUMN IF NOT EXISTS ru VARCHAR(20),
  ADD COLUMN IF NOT EXISTS eu VARCHAR(20),
  ADD COLUMN IF NOT EXISTS china VARCHAR(20);

ALTER TABLE modeli_osnova
  ADD COLUMN IF NOT EXISTS notion_strategy_link VARCHAR(500),
  ADD COLUMN IF NOT EXISTS yandex_disk_link VARCHAR(500);

ALTER TABLE cveta
  ADD COLUMN IF NOT EXISTS hex VARCHAR(7),
  ADD COLUMN IF NOT EXISTS color_en VARCHAR(50),
  ADD COLUMN IF NOT EXISTS lastovica BOOLEAN DEFAULT FALSE;
```

### Шаг 5: Создание новых таблиц
Миграция: catalog_new_tables_2026_05_07

```sql
-- Семейства цветов
CREATE TABLE IF NOT EXISTS semeystva_cvetov (
  id SERIAL PRIMARY KEY,
  kod VARCHAR(20) UNIQUE NOT NULL,
  nazvanie VARCHAR(100) NOT NULL,
  opisanie TEXT,
  poryadok INT DEFAULT 0
);

-- Упаковки
CREATE TABLE IF NOT EXISTS upakovki (
  id SERIAL PRIMARY KEY,
  nazvanie VARCHAR(100) NOT NULL,
  tip VARCHAR(50),
  price_yuan NUMERIC(10,2),
  dlina_cm NUMERIC(6,2),
  shirina_cm NUMERIC(6,2),
  vysota_cm NUMERIC(6,2),
  obem_l NUMERIC(8,2),
  srok_izgotovleniya_dni INT,
  file_link VARCHAR(500),
  notes TEXT,
  poryadok INT DEFAULT 0
);

-- Каналы продаж
CREATE TABLE IF NOT EXISTS kanaly_prodazh (
  id SERIAL PRIMARY KEY,
  kod VARCHAR(20) UNIQUE NOT NULL,
  nazvanie VARCHAR(100) NOT NULL,
  short VARCHAR(20),
  color VARCHAR(20),
  active BOOLEAN DEFAULT TRUE,
  poryadok INT DEFAULT 0
);

-- UI preferences
CREATE TABLE IF NOT EXISTS ui_preferences (
  id SERIAL PRIMARY KEY,
  scope VARCHAR(50) NOT NULL,
  key VARCHAR(100) NOT NULL,
  value JSONB,
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(scope, key)
);

-- FK: modeli_osnova → upakovki
ALTER TABLE modeli_osnova ADD COLUMN IF NOT EXISTS upakovka_id INT REFERENCES upakovki(id);

-- FK: cveta → semeystva_cvetov (заменить enum на FK для гибкости)
-- Пока оставляем существующий varchar `semeystvo` (CHECK на 5 значений) — это семейство-код.
-- Дополнительно колонка semeystvo_id для будущих расширений.
ALTER TABLE cveta ADD COLUMN IF NOT EXISTS semeystvo_id INT REFERENCES semeystva_cvetov(id);
```

### Шаг 6: RLS на новые таблицы
```sql
ALTER TABLE semeystva_cvetov ENABLE ROW LEVEL SECURITY;
ALTER TABLE upakovki ENABLE ROW LEVEL SECURITY;
ALTER TABLE kanaly_prodazh ENABLE ROW LEVEL SECURITY;
ALTER TABLE ui_preferences ENABLE ROW LEVEL SECURITY;

-- SELECT для authenticated
CREATE POLICY "auth read semeystva" ON semeystva_cvetov FOR SELECT TO authenticated USING (true);
CREATE POLICY "auth read upakovki" ON upakovki FOR SELECT TO authenticated USING (true);
CREATE POLICY "auth read kanaly" ON kanaly_prodazh FOR SELECT TO authenticated USING (true);
CREATE POLICY "auth read ui_prefs" ON ui_preferences FOR SELECT TO authenticated USING (true);

-- INSERT/UPDATE/DELETE для authenticated
CREATE POLICY "auth write semeystva" ON semeystva_cvetov FOR ALL TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "auth write upakovki" ON upakovki FOR ALL TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "auth write kanaly" ON kanaly_prodazh FOR ALL TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "auth write ui_prefs" ON ui_preferences FOR ALL TO authenticated USING (true) WITH CHECK (true);
```

⚠ Также проверить, что у kategorii, kollekcii, fabriki, importery, razmery, modeli_osnova, cveta, statusy, sertifikaty есть RLS-политики INSERT/UPDATE/DELETE (не только SELECT).

### Шаг 7: Seed-данные
Миграция: catalog_seed_2026_05_07

```sql
-- Семейства цветов
INSERT INTO semeystva_cvetov (kod, nazvanie, opisanie, poryadok) VALUES
  ('tricot', 'Трикотаж (цифровые коды)', 'Стандартный набор цветов для трикотажных коллекций', 1),
  ('jelly', 'Jelly (бесшовный)', 'Цвета бесшовной коллекции Jelly (w*, WE*)', 2),
  ('audrey', 'Audrey', 'Цвета коллекции Audrey (AU*)', 3),
  ('sets', 'Наборы трусов', 'Цвета только для наборов', 4),
  ('other', 'Прочие', 'Нетипичные цвета', 5)
ON CONFLICT (kod) DO NOTHING;

-- Каналы продаж
INSERT INTO kanaly_prodazh (kod, nazvanie, short, color, active, poryadok) VALUES
  ('wb', 'Wildberries', 'WB', 'pink', TRUE, 1),
  ('ozon', 'OZON', 'OZ', 'blue', TRUE, 2),
  ('sayt', 'Сайт', 'Сайт', 'gray', TRUE, 3),
  ('lamoda', 'Lamoda', 'LAM', 'amber', FALSE, 4)
ON CONFLICT (kod) DO NOTHING;

-- Упаковки (10 штук из MVP)
INSERT INTO upakovki (nazvanie, tip, price_yuan, dlina_cm, shirina_cm, vysota_cm, srok_izgotovleniya_dni) VALUES
  ('Малый пакет 20×30', 'pakey', 0.30, 20, 30, 1, 7),
  ('Средний пакет 25×35', 'pakey', 0.45, 25, 35, 1, 7),
  ('Большой пакет 30×40', 'pakey', 0.60, 30, 40, 1, 7),
  ('Малый пакет с зипом', 'pakey_zip', 0.55, 20, 30, 1, 10),
  ('Большой пакет с зипом', 'pakey_zip', 0.85, 30, 40, 1, 10),
  ('Коробка S', 'korobka', 1.20, 25, 18, 6, 14),
  ('Коробка M', 'korobka', 1.65, 30, 22, 7, 14),
  ('Коробка L', 'korobka', 2.10, 35, 25, 8, 14),
  ('Цветная коробка S', 'korobka_print', 2.40, 25, 18, 6, 21),
  ('Цветная коробка L', 'korobka_print', 3.30, 35, 25, 8, 21)
ON CONFLICT DO NOTHING;
```

### Шаг 8: Заполнить cveta.semeystvo
Скрипт scripts/migrate-cveta-semeystvo.py:

```python
import os, sys
sys.path.insert(0, '/Users/danilamatveev/Projects/Wookiee')
from shared.config import config
from supabase import create_client

sb = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

def detect_family(color_code: str) -> str:
    cc = (color_code or '').strip()
    if not cc:
        return 'other'
    if cc.startswith('AU'):
        return 'audrey'
    if cc.startswith('WE'):
        return 'jelly'
    # w1, w2, w3.5 — Jelly
    if cc.startswith('w') and len(cc) > 1 and (cc[1:].replace('.','').isdigit()):
        return 'jelly'
    if cc.startswith('set_') or cc in ('111', '123', '124', '125'):
        return 'sets'
    if cc.replace('.','').isdigit():
        return 'tricot'
    return 'other'

# Загрузить все цвета
res = sb.table('cveta').select('id,color_code,semeystvo').execute()

updates = []
for c in res.data:
    family = detect_family(c['color_code'])
    if c['semeystvo'] != family:
        updates.append({'id': c['id'], 'kod': c['color_code'], 'old': c['semeystvo'], 'new': family})

print(f'К обновлению: {len(updates)} цветов')
for u in updates[:20]:
    print(f"  {u['kod']:15} {u['old']} → {u['new']}")

# Подтверждение
if input('\nПрименить? (y/N): ').strip().lower() != 'y':
    print('Отменено')
    sys.exit(0)

# Применить
fam_to_id = {f['kod']: f['id'] for f in sb.table('semeystva_cvetov').select('id,kod').execute().data}

for u in updates:
    sb.table('cveta').update({
        'semeystvo': u['new'],
        'semeystvo_id': fam_to_id[u['new']]
    }).eq('id', u['id']).execute()

print(f'Обновлено: {len(updates)}')
```

Verify:
```sql
SELECT semeystvo, count(*) FROM cveta GROUP BY semeystvo;
-- Должно быть распределение по 5 семействам, 0 NULL
```

### Шаг 9: Заполнить cveta.hex
Скрипт scripts/migrate-cveta-hex.py:

```python
import sys, re
sys.path.insert(0, '/Users/danilamatveev/Projects/Wookiee')
from shared.config import config
from supabase import create_client

sb = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

# Словарь русских названий → hex (расширенный из MVP)
COLOR_DICT = {
    'белый': '#FFFFFF', 'кремовый': '#FFF8DC', 'молочный': '#FFFDD0',
    'бежевый': '#F5DEB3', 'светло-бежевый': '#F5F0E1', 'тёмно-бежевый': '#C4A57B',
    'песочный': '#E0C9A6', 'кофейный': '#6F4E37', 'шоколадный': '#5C4033',
    'коричневый': '#8B4513', 'тёмно-коричневый': '#3E2723', 'мокко': '#967259',
    'хаки': '#8B864E', 'оливковый': '#808000', 'болотный': '#556B2F',
    'зелёный': '#228B22', 'мятный': '#98FF98', 'изумрудный': '#50C878',
    'тёмно-зелёный': '#013220', 'фисташковый': '#93C572', 'салатовый': '#A8E04F',
    'голубой': '#87CEEB', 'небесный': '#87CEEB', 'тёмно-голубой': '#4A6E8A',
    'бирюзовый': '#40E0D0', 'циан': '#00FFFF', 'аква': '#00FFFF',
    'синий': '#0000FF', 'тёмно-синий': '#000080', 'тёмно синий': '#000080',
    'индиго': '#4B0082', 'кобальтовый': '#0047AB', 'васильковый': '#6495ED',
    'фиолетовый': '#8B00FF', 'сиреневый': '#C8A2C8', 'лавандовый': '#E6E6FA',
    'пурпурный': '#800080', 'фуксия': '#FF00FF', 'малиновый': '#DC143C',
    'розовый': '#FFC0CB', 'светло-розовый': '#FFB6C1', 'пыльно-розовый': '#D8A6A6',
    'пудровый': '#F5C2C7', 'персиковый': '#FFCBA4', 'коралловый': '#FF7F50',
    'красный': '#FF0000', 'бордовый': '#800020', 'винный': '#722F37',
    'тёмно-красный': '#8B0000', 'кирпичный': '#B22222', 'терракотовый': '#E2725B',
    'оранжевый': '#FFA500', 'тёмно-оранжевый': '#FF8C00', 'абрикосовый': '#FBCEB1',
    'жёлтый': '#FFFF00', 'лимонный': '#FFFACD', 'горчичный': '#FFDB58',
    'золотой': '#FFD700', 'охра': '#CC7722',
    'серый': '#808080', 'светло-серый': '#D3D3D3', 'тёмно-серый': '#404040',
    'тёмно серый': '#404040', 'графитовый': '#383838', 'антрацитовый': '#293133',
    'серебристый': '#C0C0C0', 'жемчужный': '#EAE0C8',
    'чёрный': '#000000', 'черный': '#000000',
}

def normalize(s):
    return (s or '').strip().lower()

def find_hex(color_ru, color_en):
    n = normalize(color_ru)
    if not n:
        return None
    # Точное совпадение
    if n in COLOR_DICT:
        return COLOR_DICT[n]
    # Вхождение основного слова
    for key, hex_val in COLOR_DICT.items():
        if key in n or n in key:
            return hex_val
    return None

res = sb.table('cveta').select('id,color_ru,color_en,hex').execute()

found = 0
missed = []
updates = []

for c in res.data:
    if c.get('hex'):
        continue
    hx = find_hex(c.get('color_ru', ''), c.get('color_en', ''))
    if hx:
        updates.append({'id': c['id'], 'color_ru': c['color_ru'], 'hex': hx})
        found += 1
    else:
        missed.append(c)

print(f'Найдено: {found}, не найдено: {len(missed)}')
for m in missed:
    print(f'  MISS: {m["color_ru"]}')

if input(f'\nПрименить {found} обновлений? (y/N): ').strip().lower() != 'y':
    print('Отменено')
    sys.exit(0)

for u in updates:
    sb.table('cveta').update({'hex': u['hex']}).eq('id', u['id']).execute()

print(f'Готово. {len(missed)} цветов остались без hex — заполнить вручную в UI.')
```

Verify:
```sql
SELECT count(*) FROM cveta WHERE hex IS NULL;
-- Должно быть < 30 (остальные через color picker в UI)
```

### Шаг 10: Заполнить modeli_osnova.status_id из Sheet
Скрипт scripts/sync-model-statuses-from-sheet.py:

```python
import sys, gspread
sys.path.insert(0, '/Users/danilamatveev/Projects/Wookiee')
from shared.config import config
from supabase import create_client

# Google Sheets через service account
gc = gspread.service_account('services/sheets_sync/credentials/google_sa.json')
sh = gc.open_by_key('19Nbr0kD8JJlwd7OCIMbM9qxucYNjmXnWtwJUgXv0vlg')

# Лист «Все модели»: column A = «Модель» (kod), column G = «Статус»
ws = sh.worksheet('Все модели')
hdr = ws.row_values(1)
print(f'Заголовки: {hdr}')

kod_idx = hdr.index('Модель')
status_idx = hdr.index('Статус')

rows = ws.get_all_values()[1:]
mapping = {}
for r in rows:
    if len(r) <= max(kod_idx, status_idx):
        continue
    kod = r[kod_idx].strip()
    status = r[status_idx].strip()
    if kod and status:
        mapping[kod] = status

print(f'Маппинг из Sheet: {len(mapping)} моделей')

# Supabase
sb = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
status_recs = sb.table('statusy').select('id,nazvanie').eq('tip', 'model').execute()
status_id_by_name = {s['nazvanie']: s['id'] for s in status_recs.data}

print(f'Model-статусы в Supabase: {status_id_by_name}')

# Применить
updated = 0
warned = []
for kod, status_name in mapping.items():
    sid = status_id_by_name.get(status_name)
    if not sid:
        warned.append((kod, status_name))
        continue
    res = sb.table('modeli_osnova').update({'status_id': sid}).eq('kod', kod).execute()
    if res.data:
        updated += 1

print(f'Обновлено: {updated}')
print(f'Не нашли статус: {len(warned)}')
for w in warned:
    print(f'  {w[0]} → "{w[1]}"')

# Verify
nul = sb.table('modeli_osnova').select('id', count='exact').is_('status_id', 'null').execute()
print(f'Моделей без status_id осталось: {nul.count}')
```

Verify:
```sql
SELECT count(*) FROM modeli_osnova WHERE status_id IS NULL;
-- Должно быть 0
```

### Шаг 11: Последний sanity-check
Создать .planning/catalog-rework/wave_0_report.md с:
- Сколько строк в каждой каталоговой таблице
- Сколько записей было обновлено в каждом скрипте
- Распределение по семействам
- Список цветов без hex (для ручной заливки в UI)
- Список моделей без статуса (если есть)

### Критерии готовности Wave 0
- [ ] backups/wave_0/ — все JSON-снимки сделаны
- [ ] statusy: 6 типов (model, artikul, product, sayt, color, lamoda)
- [ ] kategorii: 10 строк (без дубля «Легинсы»)
- [ ] kollekcii: 10 строк (без дубля «Спортивная трикотажкая»)
- [ ] cveta.semeystvo: 0 NULL
- [ ] cveta.hex: ≤ 30 NULL
- [ ] modeli_osnova.status_id: 0 NULL
- [ ] semeystva_cvetov: 5 строк
- [ ] upakovki: 10 строк
- [ ] kanaly_prodazh: 4 строки
- [ ] RLS на 4 новые таблицы + INSERT/UPDATE/DELETE политики на старых
- [ ] wave_0_report.md создан

После Wave 0 → переход на Wave 1.
```
