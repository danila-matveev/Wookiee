# Статусы из Google Sheet — источник правды

**Sheet ID:** `19Nbr0kD8JJlwd7OCIMbM9qxucYNjmXnWtwJUgXv0vlg`
**Service Account:** `services/sheets_sync/credentials/google_sa.json`

## Извлечённые наборы статусов

### Уровень `model` (лист «Все модели», колонка 7 «Статус»)

```
['Планирование', 'Делаем образец', 'Закуп', 'Запуск', 'В продаже', 'Выводим']
```

6 значений. Жизненный цикл: Планирование → Делаем образец → Закуп → Запуск → В продаже → (Выводим/Архив).

**Нужно добавить статус «Архив»** для уровня модели — он явно нужен (чтобы прятать модель из активных списков).

### Уровень `artikul` (лист «Все артикулы», колонка 5 «Статус товара»)

```
['Запуск', 'Продается', 'Выводим']
```

3 значения. Артикул жизненно-малочувствительный — обычно Продается, иногда Запуск или Выводим.

### Уровень `product` = SKU/WB+OZON (лист «Все товары»)

```
['Подготовка', 'План', 'Запуск', 'Продается', 'Выводим', 'Архив']
```

6 значений. **Уже есть в БД (с лишним «Новый», его удалить).**

### Уровень `sayt` (лист «Все товары», колонка «Статус Сайт»)

```
['Опубликован', 'Скрыт', 'Архив']
```

3 значения. Свой набор для собственного сайта (отличается от WB/OZON).

### Уровень `lamoda` (лист «Все товары», колонка «Статус Ламода»)

```
['Скрыт']
```

1 значение. Lamoda фактически не используется в данных.

### Уровень `color` (лист «Аналитики цветов», колонка 6 «Статус»)

```
['Продается', 'Выводим']
```

2 значения. **Нужно добавить «Архив»** для архивации старых цветов.

## Финальный набор статусов для миграции

### CHECK constraint
```sql
ALTER TABLE statusy DROP CONSTRAINT IF EXISTS statusy_tip_check;
ALTER TABLE statusy ADD CONSTRAINT statusy_tip_check
  CHECK (tip IN ('model', 'artikul', 'product', 'sayt', 'color'));
```

### Удалить
```sql
DELETE FROM statusy WHERE id = 13;  -- "Новый" — нет в источнике
```

### Существующие 6 product-статусов (id 8-12, 14) — оставить как есть

### Добавить новые (16 строк)

| id (auto) | nazvanie | tip | color (для UI) |
|-----------|----------|-----|----------------|
| — | Планирование | model | gray |
| — | Делаем образец | model | amber |
| — | Закуп | model | blue |
| — | Запуск | model | blue |
| — | В продаже | model | green |
| — | Выводим | model | red |
| — | Архив | model | gray |
| — | Запуск | artikul | blue |
| — | Продается | artikul | green |
| — | Выводим | artikul | red |
| — | Опубликован | sayt | green |
| — | Скрыт | sayt | gray |
| — | Архив | sayt | gray |
| — | Скрыт | lamoda | gray |
| — | Продается | color | green |
| — | Выводим | color | red |
| — | Архив | color | gray |

## Маппинг статусов модели из Sheet → Supabase

После добавления model-статусов нужно заполнить `modeli_osnova.status_id`:

```python
# scripts/sync-model-statuses-from-sheet.py
import gspread
from supabase import create_client

gc = gspread.service_account('services/sheets_sync/credentials/google_sa.json')
sh = gc.open_by_key('19Nbr0kD8JJlwd7OCIMbM9qxucYNjmXnWtwJUgXv0vlg')
ws = sh.worksheet('Все модели')

# Колонки: A=Модель, G=Статус (по факту проверить через row 1)
hdr = ws.row_values(1)
kod_col = hdr.index('Модель') + 1   # adjust if name differs
status_col = hdr.index('Статус') + 1

rows = ws.get_all_values()[1:]
mapping = {}
for r in rows:
    if not r or len(r) < status_col:
        continue
    kod = r[kod_col-1].strip()
    status = r[status_col-1].strip()
    if kod and status:
        mapping[kod] = status

# Подключиться к Supabase, получить id всех model-статусов:
sb = create_client(SUPABASE_URL, SUPABASE_KEY)
status_records = sb.table('statusy').select('id,nazvanie').eq('tip', 'model').execute()
status_id_by_name = {s['nazvanie']: s['id'] for s in status_records.data}

# Update modeli_osnova
for kod, status_name in mapping.items():
    status_id = status_id_by_name.get(status_name)
    if not status_id:
        print(f"WARN: статус '{status_name}' не найден для модели {kod}")
        continue
    sb.table('modeli_osnova').update({'status_id': status_id}).eq('kod', kod).execute()
    print(f"OK: {kod} → {status_name} (id={status_id})")
```

## Цвет: маппинг семейства по префиксу color_code

```python
def detect_family(color_code: str) -> str:
    cc = color_code.strip()
    if cc.startswith('AU'):
        return 'audrey'
    if cc.startswith('WE'):
        return 'jelly'
    if cc.startswith('w') and cc[1:].replace('.','').isdigit():
        return 'jelly'
    if cc.startswith('set_') or cc in ('111', '123', '124', '125'):
        return 'sets'
    if cc.replace('.','').isdigit():
        return 'tricot'
    return 'other'
```

## Цвет: словарь hex по русскому/английскому названию

См. `04_WAVE_0_SYNC.md` — там полный словарь из 60+ пар.
