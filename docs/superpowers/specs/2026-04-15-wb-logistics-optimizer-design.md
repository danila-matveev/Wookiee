# WB Logistics Optimizer — Design Spec

**Дата**: 2026-04-15
**Статус**: Draft
**Автор**: Claude Code + Данила

## Цель

Расширить скрипт оптимизации логистики WB (бывший "Vasily") тремя блоками:

1. **Баг-фикс**: исправить смешение артикулов ИП/ООО через cabinet-фильтрацию в Supabase-запросах
2. **Module 2 — ИЛ/ИРП калькулятор**: поартикульный анализ индекса локализации с разбивкой по 6 ФО, расчёт влияния на цены, экспорт в Sheets
3. **Переименование**: Vasily → WB Logistics Optimizer (код, конфиги, БД)

Перестановки (Module 1) не трогаем — только получают cabinet-фильтрованные данные.

---

## 1. Баг-фикс: разделение кабинетов

### Корневая причина

3 функции в `shared/data_layer/sku_mapping.py` загружают данные **без фильтра по кабинету**:
- `get_artikuly_statuses()` — нет WHERE по importer_id
- `get_nm_to_article_mapping()` — нет WHERE по importer_id
- `get_artikul_to_submodel_mapping()` — нет WHERE по importer_id

В `run_localization.py:720-724` statuses и barcodes загружаются **один раз** для обоих кабинетов.

### Решение

#### 1.1 Добавить параметр `cabinet_name` в SQL-запросы

Цепочка в Supabase: `importery → modeli (importer_id) → artikuly (model_id) → tovary`

Маппинг:
- `cabinet_name="ИП"` → `importery.nazvanie LIKE '%ИП%'`
- `cabinet_name="ООО"` → `importery.nazvanie LIKE '%ООО%'`

Изменить функции:

```python
# shared/data_layer/sku_mapping.py

def get_artikuly_statuses(cabinet_name: str | None = None) -> dict[str, str]:
    """Статусы артикулов, опционально фильтрованные по кабинету."""
    query = """
        SELECT a.artikul, s.nazvanie as status, mo.kod as model_osnova
        FROM artikuly a
        LEFT JOIN statusy s ON a.status_id = s.id
        LEFT JOIN modeli m ON a.model_id = m.id
        LEFT JOIN modeli_osnova mo ON m.model_osnova_id = mo.id
    """
    if cabinet_name:
        query += """
            JOIN importery i ON m.importer_id = i.id
            WHERE i.nazvanie LIKE %s
        """
        # params: f'%{cabinet_name}%'
    ...
```

Аналогично для `get_nm_to_article_mapping()` и `get_artikul_to_submodel_mapping()`.

#### 1.2 Загружать per-cabinet в run_localization.py

```python
# Было (строки 720-724):
barcode_dict = load_barcodes(args.sku_db)
statuses = load_statuses(skip=args.no_statuses)
own_stock = fetch_own_stock()

for cabinet in cabinets:
    result = run_for_cabinet(cabinet, args, own_stock, barcode_dict, statuses)

# Стало:
own_stock = fetch_own_stock()  # общий МойСклад (один физический склад)

for cabinet in cabinets:
    barcode_dict = load_barcodes(args.sku_db, cabinet_name=cabinet.name)
    statuses = load_statuses(skip=args.no_statuses, cabinet_name=cabinet.name)
    result = run_for_cabinet(cabinet, args, own_stock, barcode_dict, statuses)
```

#### 1.3 Backward compatibility

Параметр `cabinet_name` опционален (`None` = загрузить все). Существующие вызовы без параметра продолжают работать.

---

## 2. Module 2 — ИЛ/ИРП калькулятор

### 2.1 Новый файл

`services/wb_localization/calculators/il_irp_analyzer.py`

### 2.2 Входные данные

Использует **те же данные**, что уже загружаются в `run_localization.py`:
- `orders: list[dict]` — заказы из WB supplier/orders API (cabinet-specific)
- `prices_dict: dict[str, float]` — цены из WB prices API
- `cabinet_name: str` — имя кабинета

НЕ использует данные из WB-экспорта "Поставки по регионам" — вместо этого рассчитывает local/non-local из тех же orders, что и перестановки.

### 2.3 Маппинг данных WB API → формат таблицы

WB supplier/orders API возвращает для каждого заказа:
- `supplierArticle` → Артикул продавца
- `warehouseName` → определяем ФО склада через `get_warehouse_fd()`
- `regionName` / `oblast` → определяем ФО доставки через `get_delivery_fd()`
- `orderType` → фильтр (только клиентские заказы)

Классификация local/non-local:
- **LOCAL** = `warehouse_fd == delivery_fd`
- **NON-LOCAL** = `warehouse_fd != delivery_fd`
- **CIS** = регион доставки в списке СНГ стран

Маппинги уже реализованы в `wb_localization_mappings.py`.

### 2.4 Группировка по 6 ФО

```python
REGION_GROUPS = {
    'Центральный': ['Центральный'],
    'Южный и Северо-Кавказский': ['Южный', 'Северо-Кавказский'],
    'Приволжский': ['Приволжский'],
    'Уральский': ['Уральский'],
    'Дальневосточный и Сибирский': ['Дальневосточный', 'Сибирский'],
    'Северо-Западный': ['Северо-Западный'],
}

CIS_REGIONS = {'Беларусь', 'Казахстан', 'Армения', 'Кыргызстан', 'Узбекистан'}
```

### 2.5 Таблицы КТР и КРП

Используем существующие таблицы из `irp_coefficients.py`, но верифицируем соответствие с таблицей-справочником (от 23.03.2026):

**КТР** (18 ступеней, 0.50–2.00):

| Доля лок., % | КТР |
|---|---|
| 95–100 | 0.50 |
| 90–94.99 | 0.60 |
| 85–89.99 | 0.70 |
| 80–84.99 | 0.80 |
| 75–79.99 | 0.90 |
| 60–74.99 | 1.00 |
| 55–59.99 | 1.05 |
| 50–54.99 | 1.10 |
| 45–49.99 | 1.20 |
| 40–44.99 | 1.30 |
| 35–39.99 | 1.40 |
| 30–34.99 | 1.50 |
| 25–29.99 | 1.55 |
| 20–24.99 | 1.60 |
| 15–19.99 | 1.70 |
| 10–14.99 | 1.75 |
| 5–9.99 | 1.80 |
| 0–4.99 | 2.00 |

**КРП** (13 ступеней, 0–2.50%):

| Доля лок., % | КРП, % |
|---|---|
| >= 60 | 0.00 |
| 55–59.99 | 2.00 |
| 50–54.99 | 2.05 |
| 45–49.99 | 2.05 |
| 40–44.99 | 2.10 |
| 35–39.99 | 2.10 |
| 30–34.99 | 2.15 |
| 25–29.99 | 2.20 |
| 20–24.99 | 2.25 |
| 15–19.99 | 2.30 |
| 10–14.99 | 2.35 |
| 5–9.99 | 2.45 |
| 0–4.99 | 2.50 |

### 2.6 Алгоритм расчёта

```python
def analyze_il_irp(
    orders: list[dict],
    prices_dict: dict[str, float],
    period_days: int = 30,
) -> dict:
    """Полный поартикульный анализ ИЛ/ИРП."""

    # 1. Классифицировать каждый заказ: local / non-local / CIS
    #    Используем get_warehouse_fd() и get_delivery_fd()

    # 2. Агрегировать по артикулу (только РФ):
    #    - wb_local_total, wb_nonlocal_total по каждому артикулу
    #    - Разбивка по 6 макро-регионам: {region: {local, nonlocal}}

    # 3. Для каждого артикула:
    #    pct_local = wb_local / (wb_local + wb_nonlocal) * 100
    #    ktr = lookup_ktr(pct_local)
    #    krp = lookup_krp(pct_local)
    #    contribution = (ktr - 1) * total_orders  # вклад в ИЛ (штраф)
    #    weighted = total_orders * ktr             # вклад шт*КТР
    #    status = classify_status(ktr)

    # 4. ИРП-влияние на цены (для артикулов с КРП > 0):
    #    price = prices_dict.get(article_lower, 0)
    #    irp_per_order = price * krp_pct / 100
    #    irp_per_month = irp_per_order * orders * 30 / period_days

    # 5. Общие метрики:
    #    ИЛ = sum(orders_i * ktr_i) / sum(orders_i)
    #    ИРП = sum(orders_i * krp_i) / (sum_rf_orders + sum_cis_orders)

    # 6. Ранжирование: sort by contribution desc
    #    Топ-10 проблем с рекомендацией по слабому региону
```

### 2.7 Статусы артикулов

| Условие | Статус | Цвет |
|---------|--------|------|
| КТР <= 0.90 | Отличная | Зелёный |
| КТР 0.91–1.05 | Нейтральная | Серый |
| КТР 1.06–1.30 | Слабая | Оранжевый |
| КТР >= 1.31 | Критическая | Красный |

### 2.8 Выходная структура

```python
{
    "cabinet": "ООО",
    "summary": {
        "overall_il": 1.02,           # средневзвешенный КТР
        "overall_irp_pct": 0.41,      # ИРП в %
        "total_rf_orders": 57380,
        "total_cis_orders": 1200,
        "local_orders": 45230,
        "nonlocal_orders": 12150,
        "loc_pct": 78.8,              # % локализации
        "total_articles": 1547,
        "irp_zone_articles": 58,       # артикулов с КРП > 0
        "irp_monthly_cost_rub": 267000,
    },
    "articles": [
        {
            "article": "wendy/black",
            "name": "Футболка Wendy Black",
            "category": "Футболки",
            "wb_local": 640,
            "wb_nonlocal": 460,
            "wb_total": 1100,
            "loc_pct": 58.2,
            "ktr": 1.05,
            "krp_pct": 2.00,
            "contribution": 55.0,       # (1.05-1)*1100
            "weighted": 1155.0,          # 1100*1.05
            "status": "Нейтральная",
            "price": 3000,
            "irp_per_order": 60.0,       # 3000 * 2% = 60₽
            "irp_per_month": 12420,
            "regions": {
                "Центральный": {"local": 500, "nonlocal": 30, "total": 530, "pct": 94.3},
                "Южный и Северо-Кавказский": {"local": 20, "nonlocal": 100, "total": 120, "pct": 16.7},
                "Приволжский": {"local": 80, "nonlocal": 50, "total": 130, "pct": 61.5},
                "Уральский": {"local": 10, "nonlocal": 80, "total": 90, "pct": 11.1},
                "Дальневосточный и Сибирский": {"local": 5, "nonlocal": 150, "total": 155, "pct": 3.2},
                "Северо-Западный": {"local": 25, "nonlocal": 50, "total": 75, "pct": 33.3},
            },
            "weakest_region": "Дальневосточный и Сибирский",
        },
        ...
    ],
    "top_problems": [  # top-10 by contribution desc
        {
            "rank": 1,
            "article": "wendy/black",
            "category": "Футболки",
            "orders": 1100,
            "loc_pct": 58.2,
            "ktr": 1.05,
            "krp_pct": 2.00,
            "contribution": 55.0,
            "weakest_region": "Дальневосточный и Сибирский",
            "recommendation": "Добавить остатки на склады Дальневосточного+Сибирского ФО",
        },
        ...
    ],
}
```

### 2.9 Граничные случаи

1. **СНГ-заказы**: исключаются из поартикульного ИЛ/КТР, но включаются в знаменатель ИРП с КРП=0
2. **Артикулы с 0 заказов**: пропускаются
3. **Цена отсутствует**: ИРП-влияние = 0, но КТР/КРП считается нормально
4. **Артикул в обоих кабинетах**: после фикса бага — невозможно (API ключ возвращает только свои)

---

## 3. Sheets-экспорт: новые листы

### 3.1 Лист `ИЛ Анализ {кабинет}` (37 колонок)

**Шапка (строки 1–10)** — сводные метрики:

| Ячейка | Метрика |
|--------|---------|
| B2 | ИЛ (Индекс Локализации) |
| C2 | значение (e.g. 1.02) |
| B3 | ИРП |
| C3 | значение % (e.g. 0.41%) |
| B4 | Локальных заказов WB (РФ) |
| C4 | число |
| B5 | Нелокальных заказов WB (РФ) |
| C5 | число |
| B6 | % локализации (всего) |
| C6 | % |
| B7 | Всего FBW заказов (РФ) |
| C7 | число |
| B8 | Артикулов в расчёте |
| C8 | число |
| B9 | Артикулов в ИРП-зоне |
| C9 | число |
| B10 | ИРП-нагрузка ₽/мес |
| C10 | сумма в ₽ |

**Таблица данных (строка 12 = заголовок, строка 13+ = данные):**

| Кол | Заголовок | Ширина |
|-----|-----------|--------|
| A | Артикул | 180 |
| B | Название | 250 |
| C | Предмет | 120 |
| D | ВБ Лок. (РФ) | 90 |
| E | ВБ Нелок. (РФ) | 90 |
| F | Всего WB (РФ) | 90 |
| G | % лок. | 70 |
| H | КТР | 60 |
| I | КРП,% | 60 |
| J | Вклад шт×КТР | 100 |
| K | Статус | 100 |
| L-O | Центральный: Лок, Нелок, Всего, % лок | 70 each |
| P-S | Южный+СК: same 4 cols | 70 each |
| T-W | Приволжский: same 4 cols | 70 each |
| X-AA | Уральский: same 4 cols | 70 each |
| AB-AE | Дальн.+Сиб.: same 4 cols | 70 each |
| AF-AI | С-Западный: same 4 cols | 70 each |
| AJ | Вклад в ИЛ | 90 |
| AK | ИРП ₽/мес | 90 |

Сортировка по **Вклад в ИЛ** desc (самые проблемные наверху).

Условное форматирование:
- Статус: цвет фона по таблице статусов
- % лок. по регионам: красный < 40%, оранжевый 40–59%, жёлтый 60–74%, зелёный >= 75%

### 3.2 Лист `Справочник`

Статический лист с таблицами КТР и КРП + пояснения формул. Записывается один раз при первом запуске.

| Раздел | Содержание |
|--------|-----------|
| A1:C20 | Таблица КТР (Доля лок. / КТР / Описание) |
| E1:G15 | Таблица КРП (Доля лок. / КРП% / Описание) |
| A23 | Формула ИЛ: Σ(заказы × КТР) / Σ(заказы) |
| A24 | Формула ИРП: Σ(заказы × КРП%) / (РФ + СНГ заказы) |
| A26 | Статусы: Отличная / Нейтральная / Слабая / Критическая |

---

## 4. Переименование Vasily → WB Logistics

| Компонент | Было | Станет |
|-----------|------|--------|
| API сервис (папка) | `services/vasily_api/` | `services/wb_logistics_api/` |
| Config env var | `VASILY_SPREADSHEET_ID` | `WB_LOGISTICS_SPREADSHEET_ID` (fallback на старый) |
| Config env var | `VASILY_CABINETS` | `WB_LOGISTICS_CABINETS` (fallback на старый) |
| Config env var | `VASILY_REPORT_PERIOD_DAYS` | `WB_LOGISTICS_PERIOD_DAYS` (fallback на старый) |
| SQLite БД | `data/vasily.db` | `data/wb_logistics.db` (миграция: если старый существует и нового нет, переименовать) |
| Логи/принты | "Vasily" | "WB Logistics" |
| Сервисная папка | `services/wb_localization/` | **без изменений** (слишком много внешних зависимостей) |
| Лист Sheets | "Обновление" | **без изменений** (пользовательские данные) |

Backward compatibility через fallback:
```python
SPREADSHEET_ID = os.getenv("WB_LOGISTICS_SPREADSHEET_ID") or os.getenv("VASILY_SPREADSHEET_ID", "")
```

---

## 5. Интеграция в пайплайн

### 5.1 Обновлённый поток в `run_localization.py`

```python
def run_for_cabinet(cabinet, args, own_stock, barcode_dict, statuses):
    # 1. Загрузка данных (без изменений)
    remains, orders, prices_dict = fetch_wb_data(cabinet, args.days)

    # 2. Module 1: Перестановки (без изменений)
    analysis = run_analysis(df_stocks, df_regions, barcode_dict, ...)

    # 3. Module 2: ИЛ/ИРП анализ (НОВОЕ)
    il_irp = analyze_il_irp(orders, prices_dict, period_days=args.days)

    # 4. Объединить результаты
    result = _build_result_payload(cabinet.name, analysis)
    result['il_irp'] = il_irp  # добавить ИЛ/ИРП данные
    return result
```

### 5.2 Обновлённый Sheets-экспорт

```python
def export_to_sheets(result):
    # Существующие 5 листов (без изменений)
    _write_movements(result, ...)
    _write_supplies(result, ...)
    _write_summary(result, ...)
    _write_regions(result, ...)
    _write_problems(result, ...)

    # Новые листы
    if result.get('il_irp'):
        _write_il_analysis(result['il_irp'], cabinet, ...)
        _write_reference(...)  # справочник — один раз
```

### 5.3 CLI

Новый флаг `--skip-il-analysis` для обратной совместимости:
```bash
python services/wb_localization/run_localization.py --cabinet ooo
python services/wb_localization/run_localization.py --cabinet both --skip-il-analysis
```

---

## 6. Файлы для изменения

| Файл | Изменение |
|------|-----------|
| `shared/data_layer/sku_mapping.py` | Добавить `cabinet_name` параметр в 3 функции |
| `services/wb_localization/generate_localization_report_v3.py` | `load_statuses(cabinet_name)`, `load_barcodes(cabinet_name)` |
| `services/wb_localization/run_localization.py` | Per-cabinet loading, интеграция Module 2, переименование |
| `services/wb_localization/config.py` | Новые env vars с fallback |
| `services/wb_localization/sheets_export.py` | Новые функции для листов ИЛ/Справочник |
| `services/wb_localization/calculators/il_irp_analyzer.py` | **НОВЫЙ** — Module 2 |
| `services/vasily_api/` → `services/wb_logistics_api/` | Переименование папки |
| `services/wb_logistics_api/app.py` | Обновить import paths, логи |

## 7. Верификация

### 7.1 Сравнение с эталоном

После реализации — запустить для кабинета ООО и сравнить:
- `ИЛ` должен быть ~1.00 (±0.03 от значения в WB-дашборде)
- `ИРП` должен быть ~0.41% (±0.10%)
- Артикулов в ИРП-зоне: ~58

### 7.2 Тесты

- Unit-тесты для `il_irp_analyzer.py`: lookup tables, агрегация, edge cases
- Integration-тест: сравнение с данными из `calc_irp.py` (существующий калькулятор)
- Тест cabinet-фильтрации: артикулы ИП не попадают в ООО и наоборот

### 7.3 Проверка в Sheets

- Листы `ИЛ Анализ ИП` и `ИЛ Анализ ООО` — без пересечений артикулов
- Справочник — корректные таблицы КТР/КРП
- Существующие листы перестановок — без регрессий
