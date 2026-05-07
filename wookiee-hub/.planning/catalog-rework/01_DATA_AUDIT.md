# Data Quality Audit — Supabase каталога

**Проект Supabase:** `gjvwcdtfglupewcwzfhw`
**Дата аудита:** 2026-05-07

## Сводка проблем

| Проблема | Серьёзность | Где |
|---------|-------------|-----|
| 56/56 моделей без `status_id` | КРИТИЧНО | `modeli_osnova` |
| 146/146 цветов без `semeystvo` | КРИТИЧНО | `cveta` |
| Нет колонки `hex` | КРИТИЧНО | `cveta` |
| Все 7 статусов имеют `tip='product'`, нет model/color | КРИТИЧНО | `statusy` |
| Дубль `Леггинсы` (id=4) и `Легинсы` (id=9) | ВЫСОКО | `kategorii` |
| Дубль `Спортивная трикотажная` (id=8) и `Спортивная трикотажкая` (id=9) | ВЫСОКО | `kollekcii` |
| 9/56 моделей без `kollekciya_id` | СРЕДНЕ | `modeli_osnova` |
| 35/56 моделей без `tip_kollekcii` | СРЕДНЕ | `modeli_osnova` |
| 12/146 цветов без `status_id` | НИЗКО | `cveta` |
| 4 артикула без `cvet_id` | НИЗКО | `artikuly` |
| 77 артикулов без `nomenklatura_wb` | НИЗКО | `artikuly` (норма для новых) |
| 911/1473 SKU без `status_sayt_id` | СРЕДНЕ | `tovary` |
| 1473/1473 SKU без `status_lamoda_id` | НИЗКО | `tovary` (Lamoda не используется) |
| CHECK на `tip_kollekcii` (3 значения) рассинхрон с kollekcii | СРЕДНЕ | `modeli_osnova` |

## Фактическая схема (важное)

### Таблица `statusy` (7 строк, ВСЕ tip='product')
| id | nazvanie | tip |
|----|----------|-----|
| 8 | Продается | product |
| 9 | Выводим | product |
| 10 | Архив | product |
| 11 | Подготовка | product |
| 12 | План | product |
| 13 | Новый | product (НЕТ в источнике, удалить) |
| 14 | Запуск | product |

CHECK constraint: `tip IN ('model', 'product', 'color')` — нужно расширить до `('model', 'artikul', 'product', 'sayt', 'color')`.

### `kategorii` (11 строк, есть дубль)
| id | nazvanie |
|----|----------|
| 1 | Комплект белья |
| 2 | Трусы |
| 3 | Боди женское |
| **4** | **Леггинсы** ← основной |
| 5 | Лонгслив |
| 6 | Рашгард |
| 7 | Топ |
| 8 | Футболка |
| **9** | **Легинсы** ← УДАЛИТЬ, перевязать FK на 4 |
| 10 | Велосипедки |
| 11 | Бюстгалтер |

Нет колонок `opisanie`. Нужно добавить.

### `kollekcii` (11 строк, есть дубль)
| id | nazvanie |
|----|----------|
| 1 | Трикотажное белье без вкладышей |
| 2 | Трикотажное белье |
| 3 | Трикотажное белье без вставок |
| 4 | Наборы трусов |
| 5 | Трикотажное белье с вкладышами |
| 6 | Хлопковая коллекция |
| 7 | Бесшовное белье Jelly |
| **8** | **Спортивная трикотажная коллекция** ← основной |
| **9** | **Спортивная трикотажкая коллекция** ← УДАЛИТЬ (опечатка), перевязать FK на 8 |
| 10 | Спортивная бешовная коллекция |
| 11 | Бесшовный боди |

Нет колонок `opisanie`, `god_zapuska`. Нужно добавить.

### `razmery` (6 строк, всё ок)
- XS(6), S(1), M(2), L(3), XL(4), XXL(5)
- `poryadok` НЕпоследовательный — XS=1, остальные сдвинуты

Нет колонок `ru, eu, china`. Нужно добавить.

### `importery` (2 строки)
| id | nazvanie | nazvanie_en | inn | adres |
|----|----------|-------------|-----|-------|
| 1 | ИП Медведева П.В. | ... | ... | ... |
| 2 | ООО Вуки | ... | ... | ... |

Нет: `short, kpp, ogrn, bank, rs, kontakt, telefon`. Нужно добавить.

### `fabriki` (6 строк)
| id | nazvanie | strana |
|----|----------|--------|
| 1 | Singwear | CN |
| 2 | Angelina | CN |
| 3 | B&G | NULL |
| 4 | Shantou Xinzhaofeng Clothing Co., Ltd. | NULL |
| 5 | Lanhai | NULL |
| 6 | Shantou Zhina Clothing Co., Ltd. | NULL |

Нет: `gorod, kontakt, email, wechat, specializaciya, leadtime, notes`. Нужно добавить.

### `cveta` (146 строк, ВСЕ без semeystvo, нет hex)
- 12/146 без `status_id`
- 146/146 без `semeystvo`
- Нет колонки `hex`
- CHECK на semeystvo: `IN ('tricot', 'jelly', 'audrey', 'sets', 'other')`

### `modeli_osnova` (56 строк, БОГАТАЯ)
**Уже есть** колонки динамических атрибутов (отлично для UI):
- `dlya_kakoy_grudi, stepen_podderzhki, forma_chashki, regulirovka, zastezhka, posadka_trusov, vid_trusov, naznachenie, stil, po_nastroeniyu`
- `tnved, gruppa_sertifikata, nazvanie_etiketka, nazvanie_sayt, opisanie_sayt, details, description, tegi`
- `notion_link, komplektaciya, upakovka` (text), `material, sostav_syrya, composition`
- `ves_kg, dlina_cm, shirina_cm, vysota_cm, kratnost_koroba, srok_proizvodstva, sku_china, razmery_modeli`
- `kategoriya_id, kollekciya_id, fabrika_id, status_id, tip_kollekcii`

**Нет** (нужно добавить):
- `notion_strategy_link, yandex_disk_link` (varchar)
- `upakovka_id` (FK на новую таблицу upakovki)

### `tovary` (1473 строки)
- 4 баркода: `barkod` (100%), `barkod_gs1` (100%), `barkod_gs2` (58%), `barkod_perehod` (0%)
- 4 статуса каналов: `status_id` (WB общий), `status_ozon_id`, `status_sayt_id` (62% NULL), `status_lamoda_id` (100% NULL)

### `sertifikaty` (УЖЕ ЕСТЬ, 0 строк!)
Существующие колонки: `nazvanie, tip, nomer, data_vydachi, data_okonchaniya, organ_sertifikacii, file_url, gruppa_sertifikata`. **Использовать как есть.**

### `modeli_osnova_sertifikaty` (junction, 0 строк) — использовать

### Junction tables (заполнены)
- `tovary_skleyki_wb` — 1442 строки ✅
- `tovary_skleyki_ozon` — 1345 строк ✅

## Отсутствующие таблицы (нужно создать)

1. **`semeystva_cvetov`** (id, kod UNIQUE, nazvanie, opisanie) — 5 сидов из MVP
2. **`upakovki`** (id, nazvanie, tip, price_yuan, dlina_cm, shirina_cm, vysota_cm, obem_l, srok_izgotovleniya, file_link, notes) — 10 сидов
3. **`kanaly_prodazh`** (id, kod UNIQUE, nazvanie, short, color, active) — 4 канала (wb/ozon/sayt/lamoda)
4. **`ui_preferences`** (id, scope, key, value JSONB) — общие настройки ColumnsManager

## План очистки

1. Удалить status «Новый» (id=13) — нет в источнике
2. Расширить `statusy.tip` до 5 значений
3. Добавить недостающие статусы (см. `02_STATUSES_FROM_SHEET.md`)
4. Перевязать `modeli_osnova.kategoriya_id = 9 → 4`, удалить `kategorii.id=9`
5. Перевязать `modeli_osnova.kollekciya_id = 9 → 8`, удалить `kollekcii.id=9`
6. Заполнить `cveta.semeystvo` миграцией по правилу префиксов:
   - `1, 2, 3, 4, 5, 6, 7, 8, 9, 10, ...` (цифровые) → `tricot`
   - `w1, w2, w3, ...` → `jelly`
   - `WE001, WE002, ...` → `jelly`
   - `AU001, AU002, ...` → `audrey`
   - `set_*, 111, 123` → `sets`
   - остальные → `other`
7. Добавить `cveta.hex`, заполнить по словарю name → hex (см. `04_WAVE_0_SYNC.md`)
8. Заполнить `modeli_osnova.status_id` из Sheet «Все модели»
9. Расширить колонки kategorii, kollekcii, fabriki, importery, razmery, modeli_osnova
10. Добавить RLS-политики INSERT/UPDATE/DELETE для authenticated на все каталоговые таблицы
