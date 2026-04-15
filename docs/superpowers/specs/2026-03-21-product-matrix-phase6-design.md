# PIM Phase 6: External Data Integration & Detail Page

**Дата:** 2026-03-21
**Статус:** Review
**Scope:** Остатки + unit-экономика с маркетплейсов, полная страница записи с табами

---

## 1. Что делаем

Две фичи:

1. **External Data Integration** — бэкенд-сервис, который подтягивает остатки (МойСклад + МП) и unit-экономику (БД подрядчика) для сущностей товарной матрицы
2. **Full Record Page** — переработка `entity-detail-page.tsx` из простого грида полей в табовый layout с интеграцией внешних данных

### Что НЕ делаем

- Telegram auth (Hub используется локально)
- Экспорт CSV/Excel (будет Google Sheets sync позже)
- Рейтинг / отзывы (заглушка, будущая фаза)
- Задачи (заглушка)

---

## 2. Источники данных

| Данные | Источник | Функции |
|---|---|---|
| Остатки WB FBO | БД подрядчика (таблица `stocks`) | `shared/data_layer/inventory.get_wb_avg_stock()` |
| Остатки Ozon FBO | БД подрядчика (таблица `stocks`) | `shared/data_layer/inventory.get_ozon_avg_stock()` |
| Остатки МойСклад | БД подрядчика (таблица `ms_stocks`) | `shared/data_layer/inventory.get_moysklad_stock_by_article()` |
| Оборачиваемость WB | Расчёт: остатки ÷ daily_sales | `shared/data_layer/inventory.get_wb_turnover_by_model()` |
| Оборачиваемость Ozon | Расчёт: остатки ÷ daily_sales | `shared/data_layer/inventory.get_ozon_turnover_by_model()` |
| Unit-экономика WB (агрегат) | БД подрядчика (`abc_date`) | `shared/data_layer/finance.get_wb_finance()` — все поля |
| Unit-экономика WB (по моделям) | БД подрядчика (`abc_date`) | `shared/data_layer/finance.get_wb_by_model()` — sparse (sales, revenue, margin, adv, cost) |
| Unit-экономика Ozon (агрегат) | БД подрядчика (`abc_date`) | `shared/data_layer/finance.get_ozon_finance()` — все поля |
| Unit-экономика Ozon (по моделям) | БД подрядчика (`abc_date`) | `shared/data_layer/finance.get_ozon_by_model()` — sparse |
| Заказы WB по моделям | БД подрядчика (`orders`) | `shared/data_layer/finance.get_wb_orders_by_model()` |
| Заказы Ozon по моделям | БД подрядчика (`orders`) | `shared/data_layer/finance.get_ozon_orders_by_model()` |
| Артикулы WB | БД подрядчика | `shared/data_layer/article.get_wb_by_article()` |
| Артикулы Ozon | БД подрядчика | `shared/data_layer/article.get_ozon_by_article()` |
| Реклама WB по моделям | БД подрядчика | `shared/data_layer/advertising.get_wb_model_ad_roi()` |
| Реклама Ozon по моделям | БД подрядчика | `shared/data_layer/advertising.get_ozon_model_ad_roi()` |

### 2.1 Ограничение существующих функций

Функция `get_wb_by_model()` возвращает **sparse** набор полей: `sales_count`, `revenue_before_spp`, `adv_internal`, `adv_external`, `margin`, `cost_of_goods`. Не содержит: `revenue_after_spp`, `commission`, `logistics`, `storage`, `nds`, `spp`, `returns`, `buyout`.

Для полной unit-экономики по конкретной модели нужно **написать новую функцию** `get_wb_finance_by_model()` в `ExternalDataService`, которая выполняет SQL-запрос к `abc_date` с GROUP BY model, но с полным набором полей (как в `get_wb_finance()`). Аналогично для Ozon.

Это НЕ модификация `shared/data_layer/` — новая функция живёт в `services/product_matrix_api/services/external_data.py` и использует `shared/data_layer/_connection` для подключения к БД подрядчика.

### 2.2 Сигнатуры функций data_layer

Все финансовые функции принимают 3 даты: `(current_start, prev_start, current_end)`:
- `current_start` — начало текущего периода
- `prev_start` — начало предыдущего периода (для дельты)
- `current_end` — конец текущего периода (exclusive)

Пример для `period=7, compare=week`:
```python
today = date.today()  # 2026-03-21
current_end = today.isoformat()       # "2026-03-21"
current_start = (today - timedelta(days=7)).isoformat()  # "2026-03-14"
prev_start = (today - timedelta(days=14)).isoformat()    # "2026-03-07"
```

`compare=month` означает предыдущие 30 дней относительно current_start.

---

## 3. Матчинг: сущности матрицы → данные МП

Иерархия матрицы: Модель основа → Модель → Артикул → Товар → Склейка WB/Ozon

| Уровень матрицы | Поле-ключ в Supabase | Ключ для data_layer | Функции |
|---|---|---|---|
| Модель основа | `ModelOsnova.kod` | `LOWER(kod)` = model name | `*_by_model()` → filter by key |
| Модель | `Model.kod` | `LOWER(kod)` = model name (e.g. "vukin") | `*_by_model()` → filter by key |
| Артикул | `Artikul.artikul` | `LOWER(artikul)` | `*_by_article()` → filter by key |
| Товар | `Tovar.barkod` | `barkod` | Прямой lookup в `stocks` по barcode |
| Цвет | `Cvet.color_code` | — | Нет прямой привязки к МП, табы скрыты |
| Склейка WB | `SleykaWB.tovary` (M2M) | Агрегация по баркодам связанных товаров | Traverse: SleykaWB → tovary → barkod list |
| Склейка Ozon | `SleykaOzon.tovary` (M2M) | Агрегация по баркодам связанных товаров | Traverse: SleykaOzon → tovary → barkod list |
| Фабрика / Импортёр / Сертификат | — | — | Нет привязки к МП, табы скрыты |

### Модели БД (фактические поля)

- `ModelOsnova`: поле `kod` (String(50), unique) — "Vuki", "Moon", "Ruby"
- `Model`: поле `kod` (String(50), unique) — "VukiN", "VukiW". Поле `nazvanie` — display name, НЕ используется для матчинга
- `Artikul`: поле `artikul` (String(100)) — "компбел-ж-бесшов/чер"
- `Tovar`: поле `barkod` (String(50)) — "2000989949060"
- `Cvet`: поле `color_code` (String(20)) — "2", "w1"
- `SleykaWB`: поле `nazvanie` (String(100)), связь `tovary` (M2M через `tovary_skleyki_wb`)
- `SleykaOzon`: поле `nazvanie` (String(100)), связь `tovary` (M2M через `tovary_skleyki_ozon`)

### Алгоритм resolve

```python
@dataclass
class MarketplaceKey:
    level: str          # "model" | "article" | "barcode" | "barcode_list"
    key: str | None     # single key
    keys: list[str] | None = None  # for barcode_list (cards)
    channel: str | None = None     # "wb" | "ozon" | None (both)

def resolve_marketplace_key(entity_type: str, entity_id: int, db: Session) -> MarketplaceKey:
    """Определяет ключ для поиска в данных МП по типу и ID сущности."""

    if entity_type == "models_osnova":
        record = db.get(ModelOsnova, entity_id)
        return MarketplaceKey(level="model", key=record.kod.lower())

    elif entity_type == "models":
        record = db.get(Model, entity_id)
        return MarketplaceKey(level="model", key=record.kod.lower())

    elif entity_type == "articles":
        record = db.get(Artikul, entity_id)
        return MarketplaceKey(level="article", key=record.artikul.lower())

    elif entity_type == "products":
        record = db.get(Tovar, entity_id)
        return MarketplaceKey(level="barcode", key=record.barkod)

    elif entity_type == "cards_wb":
        record = db.get(SleykaWB, entity_id)
        # SleykaWB не имеет nm_id — traverse M2M к товарам
        barcodes = [t.barkod for t in record.tovary if t.barkod]
        return MarketplaceKey(level="barcode_list", keys=barcodes, channel="wb")

    elif entity_type == "cards_ozon":
        record = db.get(SleykaOzon, entity_id)
        barcodes = [t.barkod for t in record.tovary if t.barkod]
        return MarketplaceKey(level="barcode_list", keys=barcodes, channel="ozon")

    else:
        # colors, factories, importers, certs — нет привязки к МП
        raise ValueError(f"Entity type {entity_type} has no marketplace mapping")
```

### Обработка barcode_list (склейки)

Для уровня `barcode_list` сервис:
1. Получает все данные по баркодам (stock, finance)
2. Агрегирует: суммирует stock_mp, sales_count, revenue; пересчитывает средние (avg_check, margin_pct)
3. Возвращает единый агрегированный ответ

---

## 4. Backend: API Endpoints

### 4.1 Stock endpoint

```
GET /api/matrix/{entity}/{id}/stock?period=30
```

**Параметры:**
- `entity` — тип сущности (models_osnova, models, articles, products, cards_wb, cards_ozon)
- `id` — ID записи
- `period` — дни для расчёта daily_sales (default: 30)

**Response schema:**

```python
class StockChannel(BaseModel):
    stock_mp: float          # остатки на складах МП (FBO)
    daily_sales: float       # средние продажи в день
    turnover_days: float     # оборачиваемость в днях
    sales_count: int         # продажи за период (шт)
    days_in_stock: int       # дни наличия на складе

class MoySkladStock(BaseModel):
    stock_main: float        # основной склад
    stock_transit: float     # товары в пути
    total: float
    snapshot_date: str | None
    is_stale: bool           # данные устарели (> 3 дней)

class StockResponse(BaseModel):
    entity_type: str
    entity_id: int
    entity_name: str
    period_days: int
    wb: StockChannel | None
    ozon: StockChannel | None
    moysklad: MoySkladStock | None
    total_stock: float       # wb + ozon + moysklad
    total_turnover_days: float | None
```

### 4.2 Finance endpoint

```
GET /api/matrix/{entity}/{id}/finance?period=7&compare=week
```

**Параметры:**
- `period` — дни основного периода (default: 7)
- `compare` — период сравнения: `week` (предыдущие 7 дней), `month` (предыдущие 30 дней), `none` (без сравнения). Default: `week`.

**Расчёт дат из параметров:**
```python
today = date.today()
current_end = today.isoformat()
current_start = (today - timedelta(days=period)).isoformat()

if compare == "week":
    prev_start = (today - timedelta(days=period + 7)).isoformat()
elif compare == "month":
    prev_start = (today - timedelta(days=period + 30)).isoformat()
else:
    prev_start = current_start  # нет сравнения

# compare_period_end всегда = current_start (предыдущий период заканчивается там, где начинается текущий)
compare_period_end = current_start if compare != "none" else None
```

**Response schema:**

```python
class ExpenseItem(BaseModel):
    value: float             # сумма в рублях
    pct: float               # % от выручки до СПП
    delta_value: float | None  # Δ к предыдущему периоду (₽)
    delta_pct: float | None    # Δ к предыдущему периоду (п.п.)

class DRR(BaseModel):
    total: float             # общий DRR %
    internal: float          # внутренняя реклама %
    external: float          # внешняя реклама %

class FinanceChannel(BaseModel):
    # Верхнеуровневые KPI
    revenue_before_spp: float        # выручка до СПП
    revenue_after_spp: float         # выручка после СПП
    margin: float                    # маржинальная прибыль ₽
    margin_pct: float                # маржинальность % от выручки до СПП
    orders_count: int                # заказы шт
    orders_sum: float                # заказы ₽ до СПП
    sales_count: int                 # продажи шт
    sales_sum: float                 # продажи ₽ до СПП
    avg_check_before_spp: float      # ср. чек до СПП
    avg_check_after_spp: float       # ср. чек после СПП
    spp_pct: float                   # СПП %
    buyout_pct: float                # выкупаемость %
    returns_count: int               # возвраты шт
    returns_pct: float               # возвраты %

    # Расходы (с дельтой встроенной в каждый item)
    expenses: dict[str, ExpenseItem]
    # Ключи: commission (комиссия до СПП), logistics, cost_price,
    #         advertising, storage, nds, other (penalty + retention + deduction)

    # DRR
    drr: DRR

class FinanceDelta(BaseModel):
    """Дельта к предыдущему периоду — ключевые метрики."""
    revenue_before_spp: float
    revenue_after_spp: float
    margin: float
    margin_pct: float               # изменение в п.п.
    orders_count: int
    orders_sum: float
    sales_count: int
    avg_check_before_spp: float
    avg_check_after_spp: float
    spp_pct: float                  # изменение в п.п.
    buyout_pct: float               # изменение в п.п.
    returns_count: int
    returns_pct: float              # изменение в п.п.
    drr_total: float                # изменение в п.п.
    drr_internal: float
    drr_external: float

class FinanceResponse(BaseModel):
    entity_type: str
    entity_id: int
    entity_name: str
    period_start: str               # ISO date
    period_end: str
    compare_period_start: str | None
    compare_period_end: str | None
    wb: FinanceChannel | None
    ozon: FinanceChannel | None
    delta_wb: FinanceDelta | None   # дельта к прошлому периоду
    delta_ozon: FinanceDelta | None
```

### 4.3 Error responses

```python
# Entity type без привязки к МП
HTTP 404: {"detail": "Entity type 'colors' has no marketplace data"}

# БД подрядчика недоступна
HTTP 503: {"detail": "Marketplace database temporarily unavailable"}

# Запись не найдена
HTTP 404: {"detail": "Model #42 not found"}
```

### 4.4 Кэширование

**Стратегия: bulk-and-filter.** Функции data_layer возвращают данные по ВСЕМ моделям/артикулам. Кэшируем весь результат, фильтруем по ключу.

```python
from cachetools import TTLCache

# Кэш для bulk-данных (все модели, все артикулы)
_bulk_cache = TTLCache(maxsize=32, ttl=3600)  # 1 час

# Реестр callable функций
_BULK_FUNCS = {
    "wb_turnover": get_wb_turnover_by_model,       # (start_date, end_date) → dict
    "ozon_turnover": get_ozon_turnover_by_model,    # (start_date, end_date) → dict
    "moysklad": get_moysklad_stock_by_model,        # () → dict
}

def _get_cached_bulk(func_name: str, *args):
    """Кэширует результат bulk-функции (все модели/артикулы)."""
    cache_key = f"{func_name}:{args}"
    if cache_key not in _bulk_cache:
        _bulk_cache[cache_key] = _BULK_FUNCS[func_name](*args)
    return _bulk_cache[cache_key]
```

**Сигнатуры:**
- Inventory/turnover функции: `(start_date, end_date)` — 2 аргумента, возвращают `dict[model_name, {...}]`
- MoySklad: `()` — без аргументов, возвращает `dict[model_name, {...}]`
- Finance функции: `(current_start, prev_start, current_end)` — 3 аргумента

Первый запрос к модели загружает ВСЕ модели → кэш. Последующие запросы к другим моделям за тот же период берут из кэша.

---

## 5. Backend: Service Layer

### 5.1 Новый файл: `services/product_matrix_api/services/external_data.py`

Содержит:

1. `resolve_marketplace_key()` — определение ключа для сущности
2. `ExternalDataService` — основной сервис
3. Новые SQL-функции для полной unit-экономики по модели

```python
class ExternalDataService:
    """Сервис для получения внешних данных МП для сущностей матрицы."""

    @staticmethod
    def get_stock(entity_type: str, entity_id: int, period_days: int, db: Session) -> StockResponse:
        key = resolve_marketplace_key(entity_type, entity_id, db)

        if key.level == "model":
            # Вычисляем даты для inventory (2 аргумента)
            end_date = date.today().isoformat()
            start_date = (date.today() - timedelta(days=period_days)).isoformat()

            # Используем существующие функции (возвращают dict[model_name, {...}])
            wb_data = _get_cached_bulk("wb_turnover", start_date, end_date)
            ozon_data = _get_cached_bulk("ozon_turnover", start_date, end_date)
            ms_data = _get_cached_bulk("moysklad")

            # Фильтруем по key.key
            wb = wb_data.get(key.key)
            ozon = ozon_data.get(key.key)
            ms = ms_data.get(key.key)

        elif key.level == "article":
            # Используем get_wb_by_article() / get_ozon_by_article() из shared/data_layer/article.py
            # Эти функции возвращают список dict-ов с полями: article, model, sales_count, revenue, margin
            # Фильтруем по key.key, считаем turnover = stock / (sales_count / period_days)
            # days_in_stock: используем calendar_days (period_days) как fallback
            ...

        elif key.level in ("barcode", "barcode_list"):
            # Прямой SQL-lookup в stocks по barcode(s) через _get_wb_connection()
            # Для barcode_list (склейки): агрегация по всем баркодам
            # days_in_stock: COUNT(DISTINCT date WHERE stock > 0) из stocks таблицы
            ...

        return StockResponse(...)

    @staticmethod
    def get_finance(entity_type: str, entity_id: int, period_days: int,
                    compare: str, db: Session) -> FinanceResponse:
        key = resolve_marketplace_key(entity_type, entity_id, db)

        # Рассчитываем даты
        current_start, prev_start, current_end = _calculate_dates(period_days, compare)

        if key.level == "model":
            # Новая функция: полная unit-экономика по модели
            wb = _get_full_wb_finance_by_model(current_start, prev_start, current_end, key.key)
            ozon = _get_full_ozon_finance_by_model(current_start, prev_start, current_end, key.key)
        ...

        return FinanceResponse(...)
```

### 5.2 Новые SQL-функции для полной unit-экономики

Существующая `get_wb_by_model()` возвращает только 6 полей. Для полного набора (commission, logistics, storage, nds, spp, returns, buyout) пишем новые функции прямо в ExternalDataService:

```python
def _get_full_wb_finance_by_model(current_start, prev_start, current_end, model_key):
    """Полная unit-экономика WB для одной модели.

    Два SQL-запроса (как в get_wb_finance()):
    1. abc_date — продажи, выручка, расходы, маржа
    2. orders — заказы (кол-во, сумма в ₽)

    Использует shared/data_layer/_connection для подключения.
    """
    conn = _get_wb_connection()
    cur = conn.cursor()

    # Query 1: abc_date — продажи и расходы
    query = f"""
    SELECT
        CASE WHEN date >= %s THEN 'current' ELSE 'previous' END as period,
        SUM(full_counts) as sales_count,
        SUM(revenue_spp) - COALESCE(SUM(revenue_return_spp), 0) as revenue_before_spp,
        SUM(revenue) - COALESCE(SUM(revenue_return), 0) as revenue_after_spp,
        SUM(reclama) as adv_internal,
        SUM(reclama_vn + COALESCE(reclama_vn_vk, 0)) as adv_external,
        SUM(sebes) as cost_of_goods,
        SUM(logist) as logistics,
        SUM(storage) as storage,
        SUM(comis_spp) as commission,
        SUM(spp) as spp_amount,
        SUM(nds) as nds,
        SUM(penalty) as penalty,
        SUM(retention) as retention,
        SUM(deduction) as deduction,
        {WB_MARGIN_SQL} as margin,
        COALESCE(SUM(revenue_return_spp), 0) as returns_revenue
    FROM abc_date
    WHERE date >= %s AND date < %s
      AND {get_osnova_sql("SPLIT_PART(article, '/', 1)")} = %s
    GROUP BY 1
    ORDER BY period DESC;
    """
    cur.execute(query, (current_start, prev_start, current_end, model_key))
    sales_data = cur.fetchall()

    # Query 2: orders — заказы (кол-во и сумма)
    orders_query = f"""
    SELECT
        CASE WHEN date >= %s THEN 'current' ELSE 'previous' END as period,
        COUNT(*) as orders_count,
        SUM(pricewithdisc) as orders_rub
    FROM orders
    WHERE date >= %s AND date < %s
      AND {get_osnova_sql("SPLIT_PART(supplierarticle, '/', 1)")} = %s
    GROUP BY 1
    ORDER BY period DESC;
    """
    cur.execute(orders_query, (current_start, prev_start, current_end, model_key))
    orders_data = cur.fetchall()

    cur.close()
    conn.close()
    return sales_data, orders_data
```

Аналогичная `_get_full_ozon_finance_by_model()` (Ozon использует `in_process_at::date` для orders, `count_end` для sales, `marga - nds` для margin).

**Примечание по returns_count для WB:** таблица WB `abc_date` не содержит колонку `returns_count`. Вычисляем приблизительно: `returns_count = orders_count - sales_count` (разница между заказами и выкупленными). `returns_pct = returns_count / orders_count * 100`. Для Ozon — если доступна `count_return`, используем её напрямую.

Эти функции используют `shared/data_layer/_connection._get_wb_connection()` и `shared/data_layer._sql_fragments.WB_MARGIN_SQL` — переиспользование инфраструктуры без модификации `shared/data_layer/`.

### 5.3 Расчёт производных метрик

```python
def _calc_derived_metrics(raw: dict) -> FinanceChannel:
    """Вычисляет производные метрики из сырых данных SQL."""
    revenue = raw['revenue_before_spp']
    sales = raw['sales_count']
    orders = raw['orders_count']

    avg_check_before = revenue / sales if sales > 0 else 0
    avg_check_after = raw['revenue_after_spp'] / sales if sales > 0 else 0
    spp_pct = (1 - raw['revenue_after_spp'] / revenue) * 100 if revenue > 0 else 0
    buyout_pct = (sales / orders * 100) if orders > 0 else 0
    margin_pct = (raw['margin'] / revenue * 100) if revenue > 0 else 0

    returns_count = orders - sales  # приблизительно (WB не имеет отдельного поля)
    returns_pct = (returns_count / orders * 100) if orders > 0 else 0

    # DRR = реклама / заказы_₽ * 100
    total_adv = raw['adv_internal'] + raw['adv_external']
    orders_sum = raw.get('orders_rub', 0)  # из второго SQL-запроса (orders table)
    drr_total = (total_adv / orders_sum * 100) if orders_sum > 0 else 0
    drr_internal = (raw['adv_internal'] / orders_sum * 100) if orders_sum > 0 else 0
    drr_external = (raw['adv_external'] / orders_sum * 100) if orders_sum > 0 else 0

    # Расходы в ₽ и % от выручки до СПП
    expenses = {}
    for exp_key, val in [
        ('commission', raw['commission']),
        ('logistics', raw['logistics']),
        ('cost_price', raw['cost_of_goods']),
        ('advertising', total_adv),
        ('storage', raw['storage']),
        ('nds', raw['nds']),
        ('other', raw.get('penalty', 0) + raw.get('retention', 0) + raw.get('deduction', 0)),
    ]:
        expenses[exp_key] = ExpenseItem(
            value=val,
            pct=(val / revenue * 100) if revenue > 0 else 0,
            delta_value=None,  # заполняется при compare
            delta_pct=None,
        )
    ...
```

### 5.4 Агрегация "Все каналы" на frontend

Backend возвращает `wb` и `ozon` отдельно. Frontend в режиме "Все" агрегирует:
- Суммы (revenue, margin, orders_count, sales_count, expenses.value) — сложение
- Проценты (margin_pct, spp_pct, buyout_pct, expenses.pct, DRR) — **средневзвешенные по выручке до СПП** (согласно AGENTS.md)

```typescript
// Пример: margin_pct для "Все"
const totalRevenue = (wb?.revenue_before_spp ?? 0) + (ozon?.revenue_before_spp ?? 0);
const totalMargin = (wb?.margin ?? 0) + (ozon?.margin ?? 0);
const combinedMarginPct = totalRevenue > 0 ? (totalMargin / totalRevenue) * 100 : 0;
```

### 5.5 Новый файл: `services/product_matrix_api/routes/external_data.py`

```python
router = APIRouter(prefix="/api/matrix", tags=["external-data"])

@router.get("/{entity}/{entity_id}/stock", response_model=StockResponse)
def get_entity_stock(entity: str, entity_id: int, period: int = 30,
                     db: Session = Depends(get_db)):
    validate_entity_has_mp(entity)  # 404 для colors, factories, etc.
    return ExternalDataService.get_stock(entity, entity_id, period, db)

@router.get("/{entity}/{entity_id}/finance", response_model=FinanceResponse)
def get_entity_finance(entity: str, entity_id: int, period: int = 7,
                       compare: str = "week", db: Session = Depends(get_db)):
    validate_entity_has_mp(entity)
    return ExternalDataService.get_finance(entity, entity_id, period, compare, db)
```

**Эндпоинты синхронные** (не async) — функции data_layer используют блокирующие psycopg2-курсоры. FastAPI запускает их в threadpool автоматически.

---

## 6. Frontend: Full Record Page

### 6.1 Перепроектирование entity-detail-page.tsx

Текущий `entity-detail-page.tsx` — простой грид всех полей. Заменяем на табовый layout.

```
/product/matrix/:entity/:id

┌─────────────────────────────────────────────────┐
│ ← Назад к матрице          Charlotte (Модель)   │
├─────────────────────────────────────────────────┤
│ [Информация] [Остатки] [Финансы] [Рейтинг] [⋯] │
├─────────────────────────────────────────────────┤
│                                                 │
│  Содержимое активного таба                      │
│                                                 │
└─────────────────────────────────────────────────┘
```

### 6.2 Табы и их содержимое

**Какие табы показывать:**

| Entity type | Информация | Остатки | Финансы | Рейтинг | Задачи |
|---|---|---|---|---|---|
| models_osnova | + | + | + | + | + |
| models | + | + | + | + | + |
| articles | + | + | + | + | + |
| products | + | + | + | + | + |
| cards_wb | + | + | + | + | + |
| cards_ozon | + | + | + | + | + |
| colors | + | — | — | — | + |
| factories | + | — | — | — | + |
| importers | + | — | — | — | + |
| certs | + | — | — | — | + |

#### Tab: Информация (`info-tab.tsx`)

- Все поля записи, сгруппированные по секциям из `field_definitions`
- Inline editing (как сейчас в DataTable)
- Связанные сущности как кликабельные списки:
  - Модель основа → список Моделей, Артикулов, Цветов
  - Модель → Артикулы, Товары
  - Артикул → Товары, Склейки

#### Tab: Остатки (`stock-tab.tsx`)

```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  WB FBO     │  │  Ozon FBO   │  │  МойСклад   │
│  142 шт     │  │  38 шт      │  │  Склад: 230 │
│  4.2 дня    │  │  7.5 дней   │  │  В пути: 85 │
│  34.2 шт/д  │  │  5.1 шт/д   │  │  Итого: 315 │
└─────────────┘  └─────────────┘  └─────────────┘

Итого: 495 шт | Общая оборачиваемость: 12.6 дней
```

Три карточки + итоговая строка. Индикаторы:
- Красный: оборачиваемость < 3 дней (риск OOS)
- Жёлтый: 3-7 дней
- Зелёный: 7-30 дней
- Серый: > 30 дней (затоваривание)

#### Tab: Финансы (`finance-tab.tsx`)

**Верхний блок — 3 KPI-карточки:**

```
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ Заказы до СПП    │  │ Продажи до СПП   │  │ Маржа            │
│ 2.0 млн ₽       │  │ 1.4 млн ₽        │  │ 332 тыс ₽        │
│ 1 045 шт        │  │ 745 шт           │  │ 24.5%    ▲ 5.4%  │
│ ▼ -339 тыс      │  │ ▲ +7.6 тыс       │  │                  │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

**Нижний блок — таблица расходов:**

| Расходы | Сумма | % | Δ | Δ% |
|---------|-------|---|---|-----|
| Комиссия | 511.9 тыс | 37.8% | ▲ 452 | ▼ -0.2% |
| Логистика | 126.3 тыс | 9.3% | ▼ -2.8 тыс | ▼ -0.3% |
| Себестоимость | 262.4 тыс | 19.4% | ▲ 104 | ▼ -0.1% |
| Реклама | 32.9 тыс | 2.4% | ▼ -7.4 тыс | ▼ -0.6% |
| Хранение | 31.7 тыс | 2.3% | ▼ -542 | ▼ -0.1% |
| Ост. расходы | 10.7 тыс | 0.8% | ▼ -5.1 тыс | ▼ -0.4% |
| НДС | 42.8 тыс | 3.2% | ▲ 1.2 тыс | ▲ 0.1% |

**Дополнительные метрики (ниже таблицы):**
- Ср. чек до/после СПП с дельтой
- СПП %
- Выкупаемость %
- Возвраты шт и %
- DRR: общий / внутренний / внешний

**Переключатель каналов:** WB | Ozon | Все (по умолчанию — Все, с разбивкой)

Режим "Все": суммы складываются, проценты — **средневзвешенные по выручке до СПП**.

#### Tab: Рейтинг (`rating-tab.tsx`)

Заглушка:
```
Средний рейтинг: — | Отзывы: —
Функционал будет доступен в следующей версии.
```

#### Tab: Задачи (`tasks-tab.tsx`)

Заглушка:
```
Задачи будут доступны в следующей версии.
```

### 6.3 TypeScript типы (`matrix-api.ts`)

```typescript
// ── Stock ──
interface StockChannel {
  stock_mp: number;
  daily_sales: number;
  turnover_days: number;
  sales_count: number;
  days_in_stock: number;
}

interface MoySkladStock {
  stock_main: number;
  stock_transit: number;
  total: number;
  snapshot_date: string | null;
  is_stale: boolean;
}

interface StockResponse {
  entity_type: string;
  entity_id: number;
  entity_name: string;
  period_days: number;
  wb: StockChannel | null;
  ozon: StockChannel | null;
  moysklad: MoySkladStock | null;
  total_stock: number;
  total_turnover_days: number | null;
}

// ── Finance ──
interface ExpenseItem {
  value: number;
  pct: number;
  delta_value: number | null;
  delta_pct: number | null;
}

interface DRR {
  total: number;
  internal: number;
  external: number;
}

interface FinanceChannel {
  revenue_before_spp: number;
  revenue_after_spp: number;
  margin: number;
  margin_pct: number;
  orders_count: number;
  orders_sum: number;
  sales_count: number;
  sales_sum: number;
  avg_check_before_spp: number;
  avg_check_after_spp: number;
  spp_pct: number;
  buyout_pct: number;
  returns_count: number;
  returns_pct: number;
  expenses: Record<string, ExpenseItem>;
  drr: DRR;
}

interface FinanceDelta {
  revenue_before_spp: number;
  revenue_after_spp: number;
  margin: number;
  margin_pct: number;
  orders_count: number;
  orders_sum: number;
  sales_count: number;
  avg_check_before_spp: number;
  avg_check_after_spp: number;
  spp_pct: number;
  buyout_pct: number;
  returns_count: number;
  returns_pct: number;
  drr_total: number;
  drr_internal: number;
  drr_external: number;
}

interface FinanceResponse {
  entity_type: string;
  entity_id: number;
  entity_name: string;
  period_start: string;
  period_end: string;
  compare_period_start: string | null;
  compare_period_end: string | null;
  wb: FinanceChannel | null;
  ozon: FinanceChannel | null;
  delta_wb: FinanceDelta | null;
  delta_ozon: FinanceDelta | null;
}
```

### 6.4 API client functions

```typescript
export async function fetchEntityStock(
  entity: string, id: number, period = 30
): Promise<StockResponse> {
  return get(`/api/matrix/${entity}/${id}/stock?period=${period}`);
}

export async function fetchEntityFinance(
  entity: string, id: number, period = 7, compare = "week"
): Promise<FinanceResponse> {
  return get(`/api/matrix/${entity}/${id}/finance?period=${period}&compare=${compare}`);
}
```

---

## 7. Файлы: создание и изменение

### Backend (основной репо)

| Файл | Действие | Описание |
|---|---|---|
| `services/product_matrix_api/services/external_data.py` | NEW | ExternalDataService + resolve_marketplace_key + SQL-функции |
| `services/product_matrix_api/routes/external_data.py` | NEW | 2 GET эндпоинта |
| `services/product_matrix_api/models/schemas.py` | MODIFY | Pydantic-схемы Stock/Finance response |
| `services/product_matrix_api/app.py` | MODIFY | Подключить external_data router |
| `requirements.txt` / `pyproject.toml` | MODIFY | Добавить `cachetools` если отсутствует |

### Frontend (wookiee-hub/ репо)

| Файл | Действие | Описание |
|---|---|---|
| `src/components/matrix/tabs/info-tab.tsx` | NEW | Поля + связанные сущности |
| `src/components/matrix/tabs/stock-tab.tsx` | NEW | 3 карточки остатков + оборачиваемость |
| `src/components/matrix/tabs/finance-tab.tsx` | NEW | KPI-карточки + таблица расходов |
| `src/components/matrix/tabs/rating-tab.tsx` | NEW | Заглушка |
| `src/components/matrix/tabs/tasks-tab.tsx` | NEW | Заглушка |
| `src/pages/product-matrix/entity-detail-page.tsx` | REWRITE | Табовый layout |
| `src/lib/matrix-api.ts` | MODIFY | Типы + fetchEntityStock, fetchEntityFinance |

### Не трогаем

- `shared/data_layer/` — используем as-is (импортируем `_connection` и `_sql_fragments`)
- `shared/clients/` — не нужны напрямую
- Существующие роуты Product Matrix API
- `dashboard_api/` — параллельный сервис

---

## 8. Edge Cases

| Ситуация | Решение |
|---|---|
| Модель есть в матрице, но нет данных в БД подрядчика | `StockResponse.wb = null`, UI: "Нет данных" |
| БД подрядчика недоступна | HTTP 503, UI: "Данные временно недоступны" |
| МойСклад данные устарели (> 3 дней) | Показываем с warning badge: "Данные от 18.03" |
| Entity type без привязки к МП (фабрика, цвет) | HTTP 404, frontend скрывает табы |
| Первый запрос медленный (загрузка всех моделей) | Loading skeleton в UI, далее из кэша |
| Склейка без товаров (пустая M2M) | `StockResponse.wb = null`, `FinanceResponse.wb = null` |
| Товар без баркода | `StockResponse.wb = null`, финансы по другим ключам |

---

## 9. Тестирование

### Backend тесты

- `tests/product_matrix_api/test_external_data.py`:
  - `resolve_marketplace_key()` для каждого entity type (models_osnova → kod, models → nazvanie, articles → artikul, products → barkod, cards_wb → barcode_list через M2M)
  - Stock endpoint: мок `shared/data_layer/inventory` → проверка StockResponse
  - Finance endpoint: мок SQL-соединения → проверка FinanceResponse
  - 404 для entity types без привязки к МП (colors, factories, importers, certs)
  - Кэширование: второй запрос не вызывает data_layer повторно
  - Расчёт дат: period=7 + compare=week → правильные current_start/prev_start/current_end

### Frontend

- TypeScript компиляция (`npx tsc --noEmit`)
- Визуальная проверка: открыть модель → табы → данные отображаются

---

## 10. Зависимости

| Пакет | Назначение | Версия |
|---|---|---|
| `cachetools` | TTLCache для in-memory кэширования | `>=5.0` |

Проверить наличие в `requirements.txt` / `pyproject.toml` перед реализацией.
