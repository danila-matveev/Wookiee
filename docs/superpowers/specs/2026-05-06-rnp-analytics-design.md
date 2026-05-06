# РНП — Рука на Пульсе: дизайн аналитического дашборда

**Дата:** 2026-05-06  
**Статус:** pending approval

---

## 1. Контекст и цель

Аналитик Артём построил в Google Sheets / GAS скрипт «RNP_Daily» — еженедельный дашборд для отслеживания полной воронки по модели: заказы → продажи → реклама (внутренняя + 4 канала внешней) → маржа → прогноз. Дашборд считает 76 метрик на основе данных из WB PostgreSQL и двух листов Google Sheets.

Цель — реализовать то же самое в Wookiee Hub: живой дашборд с выбором модели, периода и маркетплейса, недельная разбивка, интерактивные графики Recharts.

---

## 2. Архитектура

```
Hub UI (React/Recharts)
    ↕ REST
services/analytics_api/  (FastAPI, новый сервис)
    ├── shared/data_layer/rnp.py      — SQL к WB PostgreSQL
    └── shared/clients/sheets_client.py  — уже существует
        ├── Google Sheets "Блогеры"
        └── Google Sheets "Внешняя реклама"
```

**Стек:**
- Backend: Python 3.11, FastAPI, psycopg2 (через `shared/data_layer._connection`), gspread
- Frontend: React + Recharts ^2.0.0 (уже установлен), shadcn/ui, TailwindCSS
- Деплой: по паттерну `services/wb_logistics_api/` (threading.Lock, X-Api-Key, /health)
- Новый раздел навигации: «Аналитика» → «РНП» в `src/config/navigation.ts`

**MVP:** только WB. OZON — Phase 2 (скелет предусмотреть в API).

---

## 3. Источники данных

### 3.1 WB PostgreSQL — таблица `abc_date`

Одна строка = один артикул × один день. Поля, нужные для РНП:

| Поле в БД | Агрегация | Назначение |
|---|---|---|
| `count_orders` | SUM | Заказы (шт.) |
| `revenue_spp - revenue_return_spp` | SUM | Продажи до СПП, ₽ (нетто) |
| `full_counts - returns` | SUM | Продажи (шт., нетто) |
| `reclama` | SUM | Реклама внутренняя, ₽ |
| `marga - nds - reclama_vn - reclama_vn_vk - reclama_vn_creators` | SUM | Маржинальная прибыль, ₽ |

Фильтр по модели: `LOWER(SPLIT_PART(article, '/', 1)) = :model_lower`  
Фильтр по кабинету: `lk = ANY(:lks)`

### 3.2 WB PostgreSQL — таблица `orders`

| Поле в БД | Агрегация | Назначение |
|---|---|---|
| `pricewithdisc` | SUM | Заказы до СПП, ₽ (из orders) |
| `finishedprice` | SUM | Заказы после СПП, ₽ |

Фильтр: `LOWER(SPLIT_PART(supplierarticle, '/', 1)) = :model_lower`

> GAS использует `abc_date.count_orders` для Заказы (шт.) и `orders.pricewithdisc` / `orders.finishedprice` только для рублёвых значений (до/после СПП). `COUNT(*) FROM orders` вычисляется в GAS, но не используется в финальных метриках. Наш API следует той же логике.
>
> **D3 — Независимые запросы.** `abc_date` и `orders` — два отдельных SQL-запроса, суммируются по дате на стороне Python. Если за неделю данные есть в одной таблице, но не в другой — соответствующие поля будут null. Нет жёсткого JOIN между таблицами.

### 3.3 WB PostgreSQL — таблица `content_analysis`

| Поле в БД | Агрегация | Назначение |
|---|---|---|
| `opencardcount` | SUM | Клики общие всего (переходы в карточку) |
| `addtocartcount` | SUM | Корзина, шт. |

JOIN через `nmid`: `content_analysis.vendorcode` → `LOWER(SPLIT_PART(..., '/', 1)) = :model`

> **D2 — Известное расхождение.** Данные `content_analysis` расходятся ~20% с PowerBI (причина неизвестна, зафиксировано в `docs/database/DATA_QUALITY_NOTES.md`). Клики/корзина в РНП могут не совпасть с другими отчётами — это норма, предупреждение добавлено в RnpHelpBlock (§10).

### 3.4 WB PostgreSQL — таблица `wb_adv`

| Поле в БД | Агрегация | Назначение |
|---|---|---|
| `views` | SUM | Показы внутренней рекламы |
| `clicks` | SUM | Клики внутренней рекламы |
| `orders` | SUM | Заказы от внутренней рекламы |

Фильтр: `wb_adv.nmid IN (SELECT nmid FROM content_analysis WHERE LOWER(SPLIT_PART(vendorcode,'/',1)) = :model)`. Расход внутр. рекламы берём из `abc_date.reclama` (согласованно с GAS).

> **D5 — Уточнить при реализации:** проверить, есть ли прямая связь `wb_adv.nmid = content_analysis.nmid` или нужен промежуточный маппинг. Если связь прямая — subquery выше корректен; если нет — добавить таблицу-маппинг.

### 3.5 Google Sheets — три отдельных листа каналов внешней рекламы

Одна таблица (env var `RNP_EXT_ADS_SHEET_ID` = `1h0NeYw_5Cn7mkI03QxUk_zkvJ7NGV1zFmAtXNW9euSU`) содержит три листа — по одному на канал. Каждый лист фильтруется по модели (Товар, col C).

**Подтверждённый маппинг листов → бизнес-каналов:**

| Лист Google Sheets | Канал | API-префикс |
|---|---|---|
| Отчет ADS ежедневный | ВК SIDS (ВК рекламный кабинет) | `vk_sids` |
| Отчет ADB ежедневный | SIDS Contractor (Посевы через подрядчика) | `sids_contractor` |
| Отчет EPS ежедневный | Yandex Contractor | `yandex_contractor` |

Все три листа имеют одинаковую структуру колонок (подтверждена для ADS, предполагается для ADB/EPS):

#### Структура колонок (подтверждена для ADS, предполагается для ADB/EPS)

| Индекс | Название колонки | Назначение |
|---|---|---|
| 0 (A) | Дата | дата строки |
| 1 (B) | Артикул | — |
| 2 (C) | Товар | **фильтр по модели** |
| 3 (D) | Цвет | — |
| 4 (E) | Потраченные деньги с НДС | расход (`*_rub`) |
| 5 (F) | Охват | показы (`*_views`) |
| 6 (G) | Клики | клики (`*_clicks`) |
| 7–9 | CPC / CTR | — (выводим derived) |
| 10 (K) | Переходы по UTM | — |
| 11 (L) | Заказы (UTM) | заказы (`*_orders`) |
| 12–13 | Стоимость заказа / CPO | — |

> Структура колонок ADB и EPS **предполагается идентичной** ADS. Если это не так — обнаружится при первом прогоне; нужно сравнить заголовки листов в начале реализации.

> Блогеры (influencer-кампании с полной статистикой views/clicks/carts/orders) хранятся **отдельно** в листе «Блогеры» другой таблицы (env `RNP_BLOGGERS_SHEET_ID`). Три листа выше — только цифровые каналы (ВК/Посевы/Яндекс).

### 3.6 Google Sheets — лист «Блогеры» (influencer-кампании)

Отдельная таблица (env var `RNP_BLOGGERS_SHEET_ID` или может быть частью `RNP_EXT_ADS_SHEET_ID` — уточнить).

Колонки (0-indexed, из исходного GAS-скрипта):

| Индекс | Содержание |
|---|---|
| 5 (F) | Дата кампании |
| 6 (G) | Модель (lowercase match) |
| 13 (N) | Бюджет, ₽ |
| 23 (X) | Просмотры (может быть пустым) |
| 25 (Z) | Клики (может быть пустым) |
| 28 (AC) | Корзины (может быть пустым) |
| 30 (AE) | Заказы (может быть пустым) |

Если за период есть бюджет, но все строки stats пустые → флаг `no_stats=true`.

---

## 4. API-контракт

### `GET /api/rnp/weeks`

**Query параметры:**

| Параметр | Тип | Обязателен | Описание |
|---|---|---|---|
| `model` | string | да | Название модели, lowercase (например: `audrey`) |
| `date_from` | date (YYYY-MM-DD) | да | Начало диапазона (автовыравнивается до ближайшего пн) |
| `date_to` | date (YYYY-MM-DD) | да | Конец диапазона (автовыравнивается до ближайшего вс) |
| `marketplace` | `wb` \| `ozon` \| `all` | нет | По умолчанию `wb` |
| `buyout_forecast` | float (0–1) | нет | Прогнозный выкуп %. По умолчанию = фактический выкуп за период. |

**Автовыравнивание дат:** сервер всегда выравнивает `date_from` до Monday и `date_to` до Sunday, независимо от переданных значений.

**T6 — Лимит периода:** максимум 13 недель (91 день). Если `date_to - date_from > 91` после выравнивания → 400 Bad Request `{"detail": "Period exceeds 13 weeks maximum"}`.

**D1 — Null-safe division:** все вычисляемые поля (CR, CTR, CPC, CPO, avg_order, avg_sale, drr, romi) возвращают `null` (не 0, не Infinity), если знаменатель равен 0. Frontend рендерит `null` как `—`.

**Ответ:**

```json
{
  "model": "audrey",
  "marketplace": "wb",
  "date_from": "2025-02-24",
  "date_to": "2025-05-04",
  "buyout_forecast_used": 0.87,
  "weeks": [
    {
      "week_start": "2025-02-24",
      "week_end": "2025-03-02",
      "week_label": "24.02–02.03",
      "orders_qty": 312,
      "orders_rub": 1840000,
      "orders_spp_rub": 1650000,
      "avg_order_rub": 5897,
      "avg_order_spp_rub": 5288,
      "spp_pct": 10.3,
      "sales_qty": 271,
      "buyout_pct": 86.9,
      "sales_rub": 1598000,
      "avg_sale_rub": 5896,
      "clicks_total": 45200,
      "cart_total": 2140,
      "cr_card_to_cart": 4.73,
      "cr_cart_to_order": 14.58,
      "cr_total": 0.69,
      "adv_total_rub": 184500,
      "drr_total_from_sales": 11.5,
      "drr_total_from_orders": 10.0,
      "adv_internal_rub": 94500,
      "drr_internal_from_sales": 5.9,
      "drr_internal_from_orders": 5.1,
      "orders_organic_qty": 267,
      "orders_internal_qty": 45,
      "adv_views": 12400,
      "adv_clicks": 890,
      "ctr_internal": 7.18,
      "cpc_internal": 106.2,
      "cpo_internal": 2100,
      "cpm_internal": 76.2,
      "adv_internal_profit_forecast": 42000,
      "romi_internal": 44.4,
      "adv_external_rub": 90000,
      "drr_external_from_sales": 5.6,
      "drr_external_from_orders": 4.9,
      "ext_views": 38400,
      "ext_clicks": 1820,
      "ctr_external": 4.74,
      "blogger_rub": 60000,
      "drr_blogger_from_sales": 3.8,
      "drr_blogger_from_orders": 3.3,
      "blogger_views": 28000,
      "blogger_clicks": 1200,
      "ctr_blogger": 4.29,
      "blogger_carts": 86,
      "blogger_orders": 12,
      "blogger_profit_forecast": 18000,
      "romi_blogger": 30.0,
      "blogger_no_stats": false,
      "vk_sids_rub": 12000,
      "drr_vk_sids_from_sales": 0.75,
      "drr_vk_sids_from_orders": 0.65,
      "vk_sids_views": 4800,
      "vk_sids_clicks": 280,
      "ctr_vk_sids": 5.83,
      "sids_contractor_rub": 8000,
      "drr_sids_contractor_from_sales": 0.50,
      "drr_sids_contractor_from_orders": 0.43,
      "sids_contractor_views": 3200,
      "sids_contractor_clicks": 180,
      "ctr_sids_contractor": 5.63,
      "yandex_contractor_rub": 5000,
      "drr_yandex_contractor_from_sales": 0.31,
      "drr_yandex_contractor_from_orders": 0.27,
      "yandex_contractor_views": 800,
      "yandex_contractor_clicks": 60,
      "ctr_yandex_contractor": 7.50,
      "margin_before_ads_rub": 422500,
      "margin_before_ads_pct": 26.4,
      "margin_rub": 238000,
      "margin_pct": 14.9,
      "sales_forecast_rub": 1601000,
      "margin_forecast_rub": 232000,
      "margin_forecast_pct": 14.5
    }
  ]
}
```

### `GET /api/rnp/models`

**T5 — Endpoint для списка моделей (Select в фильтрах).**

Query параметры: `marketplace` (wb | ozon | all, default: wb)

Ответ:
```json
{
  "marketplace": "wb",
  "models": ["audrey", "charlotte", "wendy"]
}
```

Источник: `DISTINCT LOWER(SPLIT_PART(article, '/', 1)) FROM abc_date WHERE lk = ANY(:lks) ORDER BY 1`.

---

## 5. Полное покрытие 76 метрик GAS → Hub

### Блок 1. Заказы (метрики 0–4)

| # | Название | Поле API | Источник | Формула |
|---|---|---|---|---|
| 0 | Заказы (шт.) | `orders_qty` | abc_date.count_orders | SUM |
| 1 | Заказы до СПП, ₽ | `orders_rub` | orders.pricewithdisc | SUM |
| 2 | Ср. чек заказа до СПП, ₽ | `avg_order_rub` | computed | orders_rub / orders_qty |
| 3 | Ср. чек заказа после СПП, ₽ | `avg_order_spp_rub` | orders.finishedprice | orders_spp_rub / orders_qty |
| 4 | СПП заказы, % | `spp_pct` | computed | (orders_rub - orders_spp_rub) / orders_rub × 100 |

### Блок 2. Продажи (5–8)

| # | Название | Поле API | Источник | Формула |
|---|---|---|---|---|
| 5 | Продажи (шт.) | `sales_qty` | abc_date.(full_counts - returns) | SUM |
| 6 | Выкупы, % ⚠️ | `buyout_pct` | computed | sales_qty / orders_qty × 100 (лаг 3–21 дн) |
| 7 | Продажи до СПП, ₽ | `sales_rub` | abc_date.(revenue_spp - revenue_return_spp) | SUM |
| 8 | Ср. чек продажи до СПП, ₽ | `avg_sale_rub` | computed | sales_rub / sales_qty |

⚠️ **Выкуп** — лаговый показатель (3–21 дней). В UI отображается с пометкой «лаг 3–21 дн.».

### Блок 3. Воронка (9–13)

| # | Название | Поле API | Источник | Формула |
|---|---|---|---|---|
| 9 | Клики общие всего, шт | `clicks_total` | content_analysis.opencardcount | SUM |
| 10 | Корзина, шт | `cart_total` | content_analysis.addtocartcount | SUM |
| 11 | CR карточка → корзина, % | `cr_card_to_cart` | computed | cart_total / clicks_total × 100 |
| 12 | CR корзина → заказ, % | `cr_cart_to_order` | computed | orders_qty / cart_total × 100 |
| 13 | CR общий клик → заказ, % | `cr_total` | computed | orders_qty / clicks_total × 100 |

### Блок 4. Реклама итого (14–16)

| # | Название | Поле API | Источник | Формула |
|---|---|---|---|---|
| 14 | Реклама ИТОГО, ₽ | `adv_total_rub` | DB + Sheets | adv_internal + ext_total |
| 15 | ДРР общий от продаж, % | `drr_total_from_sales` | computed | adv_total / sales_rub × 100 |
| 16 | ДРР общий от заказов, % | `drr_total_from_orders` | computed | adv_total / orders_rub × 100 |

### Блок 5. Внутренняя реклама (17–29)

| # | Название | Поле API | Источник | Формула |
|---|---|---|---|---|
| 17 | Реклама внутр., ₽ | `adv_internal_rub` | abc_date.reclama | SUM |
| 18 | ДРР внутр. от продаж, % | `drr_internal_from_sales` | computed | adv_internal / sales_rub × 100 |
| 19 | ДРР внутр. от заказов, % | `drr_internal_from_orders` | computed | adv_internal / orders_rub × 100 |
| 20 | Заказы органика, шт | `orders_organic_qty` | computed | orders_qty - orders_internal_qty |
| 21 | Заказы внутр., шт | `orders_internal_qty` | wb_adv.orders | SUM |
| 22 | Показы внутр., шт | `adv_views` | wb_adv.views | SUM |
| 23 | Клики внутр., шт | `adv_clicks` | wb_adv.clicks | SUM |
| 24 | CTR внутр., % | `ctr_internal` | computed | adv_clicks / adv_views × 100 |
| 25 | CPC внутр., ₽ | `cpc_internal` | computed | adv_internal / adv_clicks |
| 26 | CPO внутр., ₽ | `cpo_internal` | computed | adv_internal / orders_internal_qty |
| 27 | CPM внутр., ₽ | `cpm_internal` | computed | adv_internal / adv_views × 1000 |
| 28 | Прибыль внутр. (прогноз), ₽ | `adv_internal_profit_forecast` | computed | см. §6.1 |
| 29 | ROMI внутр. (прогноз), % | `romi_internal` | computed | profit_forecast / adv_internal × 100 |

### Блок 6. Реклама внешняя итого (30–35)

| # | Название | Поле API | Формула |
|---|---|---|---|
| 30 | Реклама внеш., ₽ | `adv_external_rub` | blogger + vk_contractor + vk_seeds + seeds_contractor + yandex_contractor |
| 31 | ДРР внеш. от продаж, % | `drr_external_from_sales` | adv_external / sales_rub × 100 |
| 32 | ДРР внеш. от заказов, % | `drr_external_from_orders` | adv_external / orders_rub × 100 |
| 33 | Просмотры внеш., шт | `ext_views` | Sheets: сумма всех каналов |
| 34 | Клики внеш., шт | `ext_clicks` | Sheets: сумма всех каналов |
| 35 | CTR внеш., % | `ctr_external` | ext_clicks / ext_views × 100 |

### Блок 7. Блогеры (36–45)

| # | Название | Поле API | Источник |
|---|---|---|---|
| 36 | Реклама блогеры, ₽ | `blogger_rub` | Sheets "Блогеры" col N |
| 37 | ДРР блогеры от продаж, % | `drr_blogger_from_sales` | computed |
| 38 | ДРР блогеры от заказов, % | `drr_blogger_from_orders` | computed |
| 39 | Просмотры Блогеры, шт | `blogger_views` | Sheets col X |
| 40 | Клики Блогеры, шт | `blogger_clicks` | Sheets col Z |
| 41 | CTR Блогеры, % | `ctr_blogger` | computed |
| 42 | Корзины Блогеры, шт | `blogger_carts` | Sheets col AC |
| 43 | Заказы Блогеры, шт | `blogger_orders` | Sheets col AE |
| 44 | Прибыль от Блогеров (прогноз), ₽ | `blogger_profit_forecast` | computed, см. §6.2 |
| 45 | ROMI Блогеров (прогноз), % | `romi_blogger` | computed |

Флаг `blogger_no_stats: bool` — true, если за период есть бюджет, но нет ни одной строки со stats.

### Блок 8. ВК SIDS — лист ADS (46–53)

| # | Название | Поле API | Источник |
|---|---|---|---|
| 46 | Реклама ВК SIDS, ₽ | `vk_sids_rub` | Sheets лист ADS col E (4) |
| 47 | ДРР ВК SIDS от продаж, % | `drr_vk_sids_from_sales` | computed |
| 48 | ДРР ВК SIDS от заказов, % | `drr_vk_sids_from_orders` | computed |
| 49 | Показы ВК SIDS, шт | `vk_sids_views` | Sheets col F (5) |
| 50 | Клики ВК SIDS, шт | `vk_sids_clicks` | Sheets col G (6) |
| 51 | CTR ВК SIDS, % | `ctr_vk_sids` | computed |
| 52 | Заказы ВК SIDS (UTM), шт | `vk_sids_orders` | Sheets col L (11) |
| 53 | CPO ВК SIDS, ₽ | `cpo_vk_sids` | vk_sids_rub / vk_sids_orders |

### Блок 9. SIDS Contractor — лист ADB (54–61)

| # | Поле API | Источник |
|---|---|---|
| 54 | `sids_contractor_rub` | Sheets лист ADB col E (4) |
| 55 | `drr_sids_contractor_from_sales` | computed |
| 56 | `drr_sids_contractor_from_orders` | computed |
| 57 | `sids_contractor_views` | Sheets col F (5) |
| 58 | `sids_contractor_clicks` | Sheets col G (6) |
| 59 | `ctr_sids_contractor` | computed |
| 60 | `sids_contractor_orders` | Sheets col L (11) |
| 61 | `cpo_sids_contractor` | sids_contractor_rub / sids_contractor_orders |

### Блок 10. Yandex Contractor — лист EPS (62–69)

| # | Поле API | Источник |
|---|---|---|
| 62 | `yandex_contractor_rub` | Sheets лист EPS col E (4) |
| 63 | `drr_yandex_contractor_from_sales` | computed |
| 64 | `drr_yandex_contractor_from_orders` | computed |
| 65 | `yandex_contractor_views` | Sheets col F (5) |
| 66 | `yandex_contractor_clicks` | Sheets col G (6) |
| 67 | `ctr_yandex_contractor` | computed |
| 68 | `yandex_contractor_orders` | Sheets col L (11) |
| 69 | `cpo_yandex_contractor` | yandex_contractor_rub / yandex_contractor_orders |

### Блок 11. (удалён — каналы перераспределены по блокам 8–10)

*Блок 11 исключён — блоки 8–10 теперь покрывают все три цифровых канала. Нумерация метрик 64–69 сдвигается → часть блока 12.*

### Блок 12. Маржа (70–73)

| # | Название | Поле API | Источник | Формула |
|---|---|---|---|---|
| 70 | Маржа до рекламы, ₽ | `margin_before_ads_rub` | computed | margin_rub + adv_total_rub |
| 71 | Маржа до рекламы, % | `margin_before_ads_pct` | computed | margin_before_ads_rub / sales_rub × 100 |
| 72 | Маржинальная прибыль (после рекламы), ₽ | `margin_rub` | abc_date | SUM(marga - nds - reclama_vn - reclama_vn_vk - reclama_vn_creators) |
| 73 | Маржа (после рекламы), % | `margin_pct` | computed | margin_rub / sales_rub × 100 |

> **Архитектурная особенность:** оба значения — до и после рекламы — являются первоклассными метриками, отображаются в summary-карточках и в основном чарте "Маржа". Маржа до рекламы показывает «потенциал» модели; маржа после рекламы — реальный результат.

### Блок 13. Прогноз (73–75)

| # | Название | Поле API | Формула |
|---|---|---|---|
| 73 | Продажи (прогноз), ₽ | `sales_forecast_rub` | orders_rub × buyout_forecast |
| 74 | Маржинальная прибыль (прогноз), ₽ | `margin_forecast_rub` | см. §6.3 |
| 75 | Маржинальность, % (прогноз) | `margin_forecast_pct` | margin_forecast_rub / sales_forecast_rub × 100 |

**Итого: 77/76 метрик покрыты** (76 исходных GAS-метрик + `margin_before_ads_rub` как отдельное поле для UI). Источники:
- WB PostgreSQL (abc_date + orders + content_analysis + wb_adv): метрики 0–29, 70–75
- Google Sheets (Блогеры + 3 листа каналов): метрики 30–69

---

## 6. Производные формулы

### 6.1 Прибыль внутренней рекламы (прогноз)

> **D7 — Верификация с Артёмом.** `margin_rub = SUM(marga - nds - reclama_vn - reclama_vn_vk - reclama_vn_creators)`. Поля `reclama_vn*` — это внешняя реклама, учитываемая в WB-кабинете. Внешняя реклама из Sheets (блогеры, ВК SIDS, Яндекс) — **отдельно**, в abc_date не попадает. Значит, `adv_total_rub = adv_internal_rub + adv_external_sheets_rub` и `margin_rub` уже не содержит Sheets-расходы. Формула ниже корректна при условии, что `reclama_vn*` ≠ Sheets-расходам. **Уточнить у Артёма, что именно содержат `reclama_vn`, `reclama_vn_vk`, `reclama_vn_creators` — WB-кабинет или дублируют Sheets.**

```python
margin_before_ads_rub = margin_rub + adv_total_rub              # маржа до вычета рекламы
margin_before_ads_pct = margin_before_ads_rub / sales_rub        # доля маржи до рекламы
adv_orders_rub = orders_internal_qty * (orders_rub / orders_qty)   # выручка с рекл. заказов
adv_sales_rub = adv_orders_rub * buyout_forecast
adv_internal_profit_forecast = adv_sales_rub * margin_before_ads_pct - adv_internal_rub
romi_internal = adv_internal_profit_forecast / adv_internal_rub * 100
```

### 6.2 Прибыль блогеров (прогноз)

```python
blogger_orders_rub = blogger_orders * (orders_rub / orders_qty)
blogger_sales_rub  = blogger_orders_rub * buyout_forecast
blogger_profit_forecast = blogger_sales_rub * margin_before_ads_pct - blogger_rub
romi_blogger = blogger_profit_forecast / blogger_rub * 100
# При blogger_no_stats: profit/romi = null
```

### 6.3 Прогноз продаж и маржи

```python
sales_forecast_rub = orders_rub * buyout_forecast
margin_forecast_rub = sales_forecast_rub * margin_before_ads_pct - adv_total_rub
margin_forecast_pct = margin_forecast_rub / sales_forecast_rub * 100
```

### 6.4 Параметр buyout_forecast

По умолчанию = фактический выкуп за запрошенный период:
```python
buyout_forecast = sales_qty / orders_qty  # агрегат по всему периоду
```
Может быть переопределён через query parameter `buyout_forecast` (0–1).

> **D4 — Ограничение MVP.** Один buyout% на весь период усредняет недели с разной сезонностью. Для точного прогноза Phase 2: использовать медиану недельных buyout_pct (исключает выбросы от акций и новинок).

---

## 7. Детектирование фазы (Phase Coloring)

Фазы определяются **только по марже после рекламы** — по каждой неделе:

```python
def detect_phase(margin_pct: float) -> str:
    if margin_pct >= 15:
        return "norm"       # синий #185FA5
    elif margin_pct < 10:
        return "decline"    # красный #E24B4A
    else:
        return "recovery"   # зелёный #1D9E75
```

ДРР не участвует в фазировании — он показывается отдельно через линию на чарте. Это устраняет неоднозначность: «маржа 20%, ДРР 35%» — это хорошая модель с переинвестицией, а не Decline.

Поле `phase` добавляется в каждый объект `weeks[]`.  
Цвета применяются через `<Cell>` в Recharts BarChart.

---

## 8. Новый элемент навигации Hub

В `src/config/navigation.ts` добавляется группа:

```typescript
{
  id: "analytics",
  icon: TrendingUp,  // из lucide-react
  label: "Аналитика",
  items: [
    { id: "rnp", label: "Рука на пульсе", icon: Activity, path: "/analytics/rnp" },
  ],
}
```

Маршрут в `src/router.tsx`:
```typescript
{ path: "/analytics",      element: <Navigate to="/analytics/rnp" replace /> },
{ path: "/analytics/rnp",  element: <RnpPage /> },
```

---

## 9. Frontend — структура страницы

```
RnpPage (src/pages/analytics/rnp.tsx)
├── RnpHelpBlock          — общая инструкция (collapsible, один раз сверху)
├── RnpFilters            — модель, период, маркетплейс, кнопка «Обновить»
├── RnpSummaryCards       — 6 карточек (см. ниже)
└── RnpTabs               — 6 вкладок
    ├── Tab "Заказы & Продажи"
    ├── Tab "Воронка"
    ├── Tab "Реклама итого"
    ├── Tab "Внутренняя реклама"
    ├── Tab "Внешняя реклама"
    └── Tab "Маржа & Прогноз"
```

### 9.1 RnpSummaryCards

Шесть карточек, итог за весь выбранный период (сумма всех недель):

| Карточка | Поле | Акцент |
|---|---|---|
| Заказы | `orders_qty` + `orders_rub` | нейтральный |
| Продажи | `sales_qty` + `sales_rub` | нейтральный |
| Маржа **до** рекламы | `margin_before_ads_pct` + `margin_before_ads_rub` | **синий** — «потенциал» |
| Маржа **после** рекламы | `margin_pct` + `margin_rub` | **зелёный/красный** по фазе |
| ДРР итого | `drr_total_from_orders` | красный если > порога |
| Прогноз маржи | `margin_forecast_pct` + `margin_forecast_rub` | нейтральный |

Обе маржи стоят рядом — пользователь видит «эффект рекламы» = разницу между ними одним взглядом.

### 9.2 RnpFilters

- **Модель**: `<Select>` — список моделей из отдельного endpoint `GET /api/rnp/models`
- **Период**: date picker с auto-snap Mon→Sun; пресеты «4 нед.», «8 нед.», «12 нед.», «Свой»
- **Маркетплейс**: `<SegmentedControl>` «WB» | «WB + OZON» | «OZON» (OZON disabled, badge «скоро»)
- State в URL через `useSearchParams` — дашборд bookmarkable/shareable

### 9.3 Система графиков (Recharts)

**Базовый паттерн для каждого таба:**
```tsx
const [hidden, setHidden] = useState<Set<string>>(new Set())

<ComposedChart data={weeks}>
  <Bar dataKey="orders_qty" yAxisId="left" hide={hidden.has("orders_qty")}>
    {weeks.map(w => <Cell key={w.week_start} fill={PHASE_COLORS[w.phase]} />)}
  </Bar>
  <Line dataKey="margin_pct" yAxisId="right" hide={hidden.has("margin_pct")} />
  <YAxis yAxisId="left" />
  <YAxis yAxisId="right" orientation="right" />
  <Legend onClick={(e) => toggleHidden(e.dataKey)} />
</ComposedChart>
```

**Состав вкладок:**

| Таб | Графики | Таблица внизу |
|---|---|---|
| Заказы & Продажи | Bar: orders_qty (phase color); Line: sales_qty; Line: buyout_pct (правая ось) | Заказы/Продажи/Чек/СПП/Выкуп по неделям |
| Воронка | Bar: clicks_total; Line: cr_total (правая ось); Line: cr_card_to_cart (правая ось) | Клики/Корзина/3 CR-метрики |
| Реклама итого | Bar: adv_internal + adv_external (stacked); Line: drr_total_from_orders (правая ось) | Расход/ДРР по каналам |
| Внутренняя реклама | Bar: adv_views; Line: adv_clicks; Line: ctr_internal (правая ось); Bar: orders_internal_qty | CPC/CPO/CPM/ROMI |
| Внешняя реклама | Grouped Bar: blogger + vk_c + vk_s + s_c + ya_c по неделям; Line: ctr_external | Расход/Просмотры/Клики/CTR по каналам + Прибыль/ROMI блогеров |
| Маржа & Прогноз | Bar: margin_rub (phase color) + Bar: margin_before_ads_rub (серый, stacked-like overlay); Line: margin_pct (правая ось); Line: margin_before_ads_pct (правая ось, пунктир) | Маржа до/после рекламы / Прогноз / Разница (эффект рекламы) |

**Toggle:** клик по легенде скрывает/показывает серию. Активное состояние отображается opacity.

**M4 — Inline-маркер лага выкупа.** Недели, у которых `week_end` находится менее чем за 21 день до сегодня, маркируются пунктирной границей столбца и tooltip-пометкой «⚠ Выкуп занижен — лаг до 21 дня». Вычисляется на фронте по `week_end` и `Date.now()`.

---

## 10. Общая инструкция (RnpHelpBlock)

Располагается в collapsible в верхней части страницы. Текст:

> **РНП — Рука на пульсе**
>
> Дашборд показывает недельную динамику по выбранной модели. Данные обновляются ежедневно (T−1, вчера).
>
> **Как читать фазы:**
> - 🔵 Норма — маржа ≥ 15% и ДРР ≤ 20%
> - 🟢 Восстановление — показатели улучшаются, но пороги ещё не достигнуты
> - 🔴 Спад — маржа < 10% или ДРР > 30%
>
> **Выкуп %** — лаговый показатель (3–21 дней). Недельные значения для недавних недель занижены.
>
> **Прогноз** рассчитывается на основе прогнозного выкупа. По умолчанию используется фактический выкуп за выбранный период.
>
> **Графики**: кликните по названию серии в легенде, чтобы скрыть/показать её.
>
> **Клики и корзина** (воронка) — данные из WB `content_analysis`. Цифры могут расходиться ~20% с другими отчётами WB — это известная особенность источника, не ошибка дашборда.

---

## 11. Структура сервиса

```
services/analytics_api/
├── app.py                 — FastAPI app, /health, /api/rnp/weeks, /api/rnp/models
├── requirements.txt       — fastapi, uvicorn, psycopg2-binary, gspread
└── README.md

shared/data_layer/
└── rnp.py                 — fetch_rnp_wb_daily(model, date_from, date_to, lks)
                             fetch_rnp_models_wb(lks)

wookiee-hub/src/
├── pages/analytics/
│   └── rnp.tsx
├── components/analytics/
│   ├── rnp-filters.tsx
│   ├── rnp-help-block.tsx
│   ├── rnp-summary-cards.tsx
│   └── rnp-tabs/
│       ├── tab-orders.tsx
│       ├── tab-funnel.tsx
│       ├── tab-ads-total.tsx
│       ├── tab-ads-internal.tsx
│       ├── tab-ads-external.tsx
│       └── tab-margin.tsx
└── config/navigation.ts   — добавить группу "analytics"
```

**.env переменные (новые):**
```
ANALYTICS_API_KEY=       # X-Api-Key для защиты endpoint (T3)
RNP_EXT_ADS_SHEET_ID=1h0NeYw_5Cn7mkI03QxUk_zkvJ7NGV1zFmAtXNW9euSU
RNP_BLOGGERS_SHEET_ID=   # ID Google Sheets с листом «Блогеры»
```

Google Sheets credentials: используется существующий `shared/clients/sheets_client.py`, авторизация через Service Account (env var `GOOGLE_SERVICE_ACCOUNT_JSON` или путь к JSON — уточнить по текущей конфигурации sheets_client).

**T3 — Аутентификация:** все endpoints `/api/rnp/*` требуют заголовок `X-Api-Key: $ANALYTICS_API_KEY`. Без заголовка → 403.

**T4 — Sheets fallback:** если Google Sheets API недоступен (timeout > 10s) → возвращаем данные с `"ext_ads_available": false`, все Sheets-поля (блогеры, цифровые каналы) = null. Не 503 — пользователь видит хотя бы WB-данные.

**D6 — Кэш Sheets:** in-memory LRU кэш (TTL 15 минут) на пару (sheet_id, sheet_name, date_range). Предотвращает повторные запросы к Google API при параллельных пользователях.

**T1 — Порт:** `8005`. Caddy блок:
```
analytics-api.os.wookiee.shop {
    reverse_proxy localhost:8005
}
```

**Caddy / деплой:** новый блок в Caddyfile по паттерну `wb_logistics_api` (threading.Lock, /health endpoint).

---

## 12. Документация сервиса (README)

`services/analytics_api/README.md` включает:
- Описание: что считает, источники данных
- Запуск локально: `uvicorn app:app --reload --port 8006`
- Переменные окружения
- Таблица всех 76 метрик с источниками
- Описание формул прогноза
- Как добавить новый канал внешней рекламы
- OZON — план Phase 2

---

## 13. Out of scope (Phase 2)

- **OZON marketplace support.** MVP: `marketplace=ozon` → 501 Not Implemented `{"detail": "OZON support coming in Phase 2"}` (не 500).
- **Дельта неделя-к-неделе (M1):** колонки Δ в таблицах и стрелки «+12% к прошлой неделе».
- **buyout_forecast по неделям (D4):** медиана недельных buyout_pct вместо агрегата периода.
- Гипотезы (лист "Гипотезы" из GAS)
- Фильтр по статусу артикулов (Продается / Выводим / Архив)
- Кастомный `buyout_forecast` через UI (сейчас только через API param)
- Итого по всем моделям кабинета
