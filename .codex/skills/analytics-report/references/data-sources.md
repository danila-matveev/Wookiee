# Data Sources Reference — Analytics Report

## DB Tables (read-only)

### WB (PostgreSQL: `pbi_wb_wookiee`)

| Table | Rows | Fields | Description |
|---|---|---|---|
| `abc_date` | ~853K | 94 | Основная финансовая таблица: продажи, выручка, маржа, логистика, хранение, комиссия, НДС, реклама, СПП, себестоимость. Гранулярность: день × баркод |
| `orders` | ~285K | — | Заказы: дата, артикул, баркод, количество, сумма |
| `sales` | ~250K | — | Продажи (выкупы): дата, артикул, баркод, количество, сумма |
| `stocks` | ~1.3M | — | Остатки на складах WB: дата, баркод, склад, количество |
| `content_analysis` | ~61K | — | Воронка трафика: показы, клики, корзина, заказы. **NB: расхождение ~20% с PowerBI** |
| `wb_adv` | ~308K | — | Рекламные кампании WB: показы, клики, CTR, CPC, расход, заказы от рекламы |
| `adv_budget` | ~7K | — | Пополнения рекламного бюджета WB |
| `ms_stocks` | ~177K | — | Остатки МойСклад: артикул, склад, количество, себестоимость |
| `paid_storage` | ~6.3M | — | Платное хранение WB: баркод, склад, дни, стоимость |
| `stat_words` | ~11.6M | — | Поисковые запросы WB: ключевые слова, позиции, частотность |

### OZON (PostgreSQL: `pbi_ozon_wookiee`)

| Table | Rows | Fields | Description |
|---|---|---|---|
| `abc_date` | ~156K | 72 | Основная финансовая таблица OZON: аналог WB abc_date |
| `adv_stats_daily` | ~1.3K | — | Статистика рекламы OZON по дням |
| `ozon_adv_api` | ~3.8K | — | Рекламные кампании OZON через API |
| `ozon_services` | ~375K | — | Услуги OZON: логистика, хранение, комиссия, штрафы |

### Supabase (PostgreSQL: RLS enabled)

| Table | Description |
|---|---|
| `sku_matrix` | Товарная матрица: артикул → модель → подмодель → статус → себестоимость |
| `model_statuses` | Статусы моделей: ACTIVE, HOLDOUT, ARCHIVE |

## Google Sheets (read-only)

| Sheet | ID | Content |
|---|---|---|
| План WB+OZON | `1Dsz7s_mZ0wUhviGFho89lyhtjce1V0Cmv_RPL1aLxnk` | Месячный план: выручка, маржа, заказы по каналам |
| Блогеры + посевы | `1Y7uxZnrjHLBntoDLkKJBOt5-lmODRJ5QEkE19QBA8xk` | Рекламные размещения: блогер, дата, бюджет, охват, переходы |
| Внешний трафик VK/Yandex | `1h0NeYw_5Cn7mkI03QxUk_zkvJ7NGV1zFmAtXNW9euSU` | Performance-маркетинг: расход, клики, CPC, конверсии |
| SMM | `19NXHQGWSFjeWiPE12R3YAy5u2IsLpTISrECpysPSdPU` | Контент и SMM: посты, охват, вовлеченность, расход |

## Data Layer Functions

All DB access goes through `shared/data_layer/`. Direct SQL is forbidden.

### finance.py (7 functions)

| Function | Description |
|---|---|
| `get_wb_finance(current_start, prev_start, current_end)` | WB P&L: выручка, маржа, логистика, хранение, комиссия, НДС, реклама |
| `get_wb_by_model(current_start, prev_start, current_end)` | WB финансы по моделям: выручка, маржа, маржинальность |
| `get_wb_orders_by_model(current_start, prev_start, current_end)` | WB заказы по моделям: шт, руб |
| `get_wb_buyouts_returns_by_model(...)` | WB выкупы и возвраты по моделям |
| `get_ozon_finance(current_start, prev_start, current_end)` | OZON P&L: аналог WB |
| `get_ozon_by_model(current_start, prev_start, current_end)` | OZON финансы по моделям |
| `get_ozon_orders_by_model(current_start, prev_start, current_end)` | OZON заказы по моделям |

### advertising.py (14 functions)

| Function | Description |
|---|---|
| `get_wb_external_ad_breakdown(current_start, prev_start, current_end, lk)` | WB разбивка внешней рекламы: блогеры, VK, Yandex |
| `get_ozon_external_ad_breakdown(current_start, prev_start, current_end, lk)` | OZON разбивка внешней рекламы |
| `get_wb_organic_vs_paid_funnel(current_start, prev_start, current_end, lk)` | WB воронка: органика vs реклама |
| `get_wb_ad_daily_series(start_date, end_date, lk)` | WB рекламный расход по дням |
| `get_ozon_ad_daily_series(start_date, end_date)` | OZON рекламный расход по дням |
| `get_wb_model_ad_roi(current_start, prev_start, current_end, lk)` | WB ROI рекламы по моделям |
| `get_ozon_model_ad_roi(current_start, prev_start, current_end, lk)` | OZON ROI рекламы по моделям |
| `get_ozon_ad_by_sku(current_start, prev_start, current_end)` | OZON реклама по SKU |
| `get_wb_campaign_stats(current_start, prev_start, current_end, lk)` | WB статистика рекламных кампаний |
| `get_wb_ad_budget_utilization(start_date, end_date)` | WB утилизация рекламного бюджета |
| `get_wb_ad_totals_check(start_date, end_date)` | WB контрольная сумма рекламных расходов |
| `get_wb_organic_by_status(current_start, prev_start, current_end, lk)` | WB органика по статусам моделей |
| `get_ozon_organic_estimated(current_start, prev_start, current_end, lk)` | OZON оценочная органика (прямые данные недоступны) |
| `get_wb_model_metrics_comparison(current_start, prev_start, current_end, lk)` | WB сравнение метрик моделей |

### inventory.py (13 functions)

| Function | Description |
|---|---|
| `get_wb_avg_stock(start_date, end_date)` | WB средний остаток за период |
| `get_ozon_avg_stock(start_date, end_date)` | OZON средний остаток за период |
| `get_moysklad_stock_by_article(max_staleness_days)` | Остатки МойСклад по артикулам |
| `get_total_avg_stock(channel, start_date, end_date)` | Общий средний остаток по каналу |
| `get_wb_sales_trend_by_model(start_date, end_date)` | WB тренд продаж по моделям |
| `get_ozon_sales_trend_by_model(start_date, end_date)` | OZON тренд продаж по моделям |
| `get_wb_turnover_by_model(start_date, end_date)` | WB оборачиваемость по моделям |
| `get_ozon_turnover_by_model(start_date, end_date)` | OZON оборачиваемость по моделям |
| `get_wb_turnover_by_submodel(start_date, end_date)` | WB оборачиваемость по подмоделям |
| `get_wb_stock_daily_by_model(start_date, end_date, model)` | WB остатки по дням по моделям |
| `get_ozon_stock_daily_by_model(start_date, end_date, model)` | OZON остатки по дням по моделям |
| `get_moysklad_stock_by_model()` | Остатки МойСклад по моделям |
| `_get_days_in_stock_by_model(channel, start_date, end_date)` | Дни в наличии по моделям (internal) |

### pricing.py (8 functions)

| Function | Description |
|---|---|
| `get_wb_price_margin_daily(start_date, end_date, model)` | WB цена и маржа по дням |
| `get_ozon_price_margin_daily(start_date, end_date, model)` | OZON цена и маржа по дням |
| `get_wb_price_changes(start_date, end_date, model)` | WB изменения цен |
| `get_ozon_price_changes(start_date, end_date, model)` | OZON изменения цен |
| `get_wb_spp_history_by_model(start_date, end_date, model)` | WB история СПП по моделям |
| `get_wb_price_margin_by_model_period(start_date, end_date)` | WB цена и маржа по моделям за период |
| `get_wb_price_margin_by_submodel_period(start_date, end_date)` | WB цена и маржа по подмоделям |
| `get_ozon_price_margin_by_model_period(start_date, end_date)` | OZON цена и маржа по моделям |

### pricing_article.py (2 functions)

| Function | Description |
|---|---|
| `get_wb_price_margin_daily_by_article(start_date, end_date, article, model)` | WB цена и маржа по артикулам |
| `get_ozon_price_margin_daily_by_article(start_date, end_date, article, model)` | OZON цена и маржа по артикулам |

### traffic.py (3 functions)

| Function | Description |
|---|---|
| `get_wb_traffic(current_start, prev_start, current_end)` | WB трафик: показы, клики, CTR, конверсии |
| `get_wb_traffic_by_model(current_start, prev_start, current_end)` | WB трафик по моделям |
| `get_ozon_traffic(current_start, prev_start, current_end)` | OZON трафик |

### time_series.py (6 functions)

| Function | Description |
|---|---|
| `get_wb_daily_series(target_date, lookback_days)` | WB дневной ряд (7 дней назад от target) |
| `get_ozon_daily_series(target_date, lookback_days)` | OZON дневной ряд |
| `get_wb_daily_series_range(start_date, end_date)` | WB дневной ряд за произвольный период |
| `get_ozon_daily_series_range(start_date, end_date)` | OZON дневной ряд за произвольный период |
| `get_wb_weekly_breakdown(month_start, month_end)` | WB понедельная разбивка |
| `get_ozon_weekly_breakdown(month_start, month_end)` | OZON понедельная разбивка |

### article.py (8 functions)

| Function | Description |
|---|---|
| `get_wb_by_article(start_date, end_date)` | WB данные по артикулам |
| `get_ozon_by_article(start_date, end_date)` | OZON данные по артикулам |
| `get_wb_orders_by_article(start_date, end_date)` | WB заказы по артикулам |
| `get_wb_barcode_to_marketplace_mapping()` | WB маппинг баркод → артикул |
| `get_wb_fin_data_by_barcode(start_date, end_date)` | WB финансы по баркодам |
| `get_wb_orders_by_barcode(start_date, end_date)` | WB заказы по баркодам |
| `get_ozon_fin_data_by_barcode(start_date, end_date)` | OZON финансы по баркодам |
| `get_ozon_orders_by_barcode(start_date, end_date)` | OZON заказы по баркодам |

### funnel_seo.py (7 functions)

| Function | Description |
|---|---|
| `get_wb_article_funnel(start_date, end_date, model_filter, top_n)` | WB воронка по артикулам |
| `get_wb_article_funnel_wow(current_start, prev_start, current_end, artikul_filter)` | WB воронка WoW сравнение |
| `get_wb_article_ad_attribution(start_date, end_date, artikul_filter)` | WB атрибуция рекламы по артикулам |
| `get_wb_article_economics(start_date, end_date, artikul_filter)` | WB unit-economics по артикулам |
| `get_wb_article_contribution_margin(start_date, end_date, artikul_filter)` | WB маржинальный вклад по артикулам |
| `get_wb_seo_keyword_positions(current_start, prev_start, current_end, artikul_filter)` | WB позиции по ключевым словам |
| `get_wb_search_keywords_api(start_date, end_date, nmids)` | WB поисковые запросы через API |

### planning.py (2 functions)

| Function | Description |
|---|---|
| `get_active_models_with_abc(start_date, end_date)` | Активные модели с ABC-классификацией |
| `get_plan_by_period(month_start, month_end)` | План на период |

### sku_mapping.py (6 functions)

| Function | Description |
|---|---|
| `get_artikuly_statuses()` | Статусы артикулов |
| `get_artikul_to_submodel_mapping()` | Маппинг артикул → подмодель |
| `get_nm_to_article_mapping()` | Маппинг nm_id → артикул |
| `get_model_statuses()` | Статусы моделей |
| `get_model_statuses_mapped()` | Статусы моделей с маппингом |
| `get_artikuly_full_info()` | Полная информация по артикулам |

### quality.py (1 function)

| Function | Description |
|---|---|
| `validate_wb_data_quality(target_date)` | Проверка качества данных WB на дату |

### Utility functions (_connection.py)

| Function | Description |
|---|---|
| `to_float(val)` | Безопасная конвертация в float |
| `format_num(num, decimals)` | Форматирование чисел: `1 234 567` |
| `format_pct(num)` | Форматирование процентов: `24.1%` |
| `get_arrow(change)` | Стрелка направления: `+12.3% ↑` |
| `calc_change(current, previous)` | Расчет изменения в % |
| `calc_change_pp(current, previous)` | Расчет изменения в п.п. |
