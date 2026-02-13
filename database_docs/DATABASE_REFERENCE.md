# Полный справочник базы данных PostgreSQL

> **Последнее обновление:** 8 февраля 2026
> **Назначение:** Единый источник истины для ИИ и аналитики. Каждое поле описано, формулы верифицированы.
> **Рабочий документ с вопросами:** [DATABASE_WORKPLAN.md](DATABASE_WORKPLAN.md)

---

## 1. ПОДКЛЮЧЕНИЕ

```
Host: ${DB_HOST}     (см. корневой .env)
Port: ${DB_PORT}
User: ${DB_USER}
Password: <см. корневой .env файл>
```

| База данных | Маркетплейс | Основная таблица | Период данных |
|-------------|-------------|------------------|---------------|
| `pbi_wb_wookiee` | Wildberries | `abc_date` (853K строк) | 01.01.2024 — сегодня |
| `pbi_ozon_wookiee` | OZON | `abc_date` (156K строк) | 20.01.2024 — сегодня |

### Юридические лица (поле `lk`)

| МП | Значения |
|----|----------|
| WB | `WB ИП Медведева П.В.`, `WB ООО ВУКИ` |
| OZON | `Ozon ИП Медведева П.В.`, `Ozon ООО ВУКИ` |

### Кросс-запросы между БД

```sql
pbi_wb_wookiee.public.abc_date    -- WB
pbi_ozon_wookiee.public.abc_date  -- OZON
```

---

## 2. КРИТИЧЕСКИЕ ЛОВУШКИ НАИМЕНОВАНИЙ

### 2.1 WB: Парадокс суффикса `_spp`

**Суффикс `_spp` означает "ДО СПП" (контринтуитивно!)**

| Поле | Ожидание | РЕАЛЬНОСТЬ |
|------|----------|------------|
| `revenue_spp` | После СПП | **ДО СПП (цена продавца, полная цена)** |
| `revenue` | До СПП | **ПОСЛЕ СПП (цена покупателя, со скидкой)** |
| `comis_spp` | После СПП | **ДО СПП** |
| `comis` | До СПП | **ПОСЛЕ СПП** |

### 2.2 WB и OZON: Маржа — всегда вычитать НДС

Паттерн одинаковый на обоих МП: предрассчитанное поле маржи **НЕ включает НДС**.

| МП | Поле в БД | Финальная маржа | Статус |
|----|-----------|-----------------|--------|
| **OZON** | `marga` | `marga - nds` | Верифицировано (точное совпадение с PowerBI) |
| **WB** | `marga_union` | `marga_union - nds` (гипотеза) | Требуется проверка. Альтернатива: формула из 11 полей |

**Что мы знаем:**
- `marga_union` напрямую даёт ~10% расхождение с PowerBI — это ровно доля НДС
- `marga_union - nds` по аналогии с OZON должна дать корректный результат
- Формула из 11 полей (раздел 3.1) уже включает `- nds` и даёт <1% расхождение
- Поле `marga` (без `_union`) — назначение неизвестно, не использовать

### 2.3 OZON: Суффикс `_end`

Суффикс `_end` означает **итоговое значение** (за вычетом возвратов).

| Поле | Значение |
|------|----------|
| `price_end` | Выручка ДО СПП (итоговая) |
| `price_end_spp` | Выручка ПОСЛЕ СПП |
| `comission_end` | Комиссия ДО СПП |
| `comission_end_spp` | Комиссия ПОСЛЕ СПП |

### 2.4 OZON: Ловушка маржи

Поле `marga` — это **промежуточная** маржа. Финальная маржа = `marga - nds`.

---

## 3. ВЕРИФИЦИРОВАННЫЕ ФОРМУЛЫ

### 3.1 WB Маржа (верифицировано 07.02.2026, расхождение <1%)

```sql
-- PowerBI: 1,047,104 руб | БД: 1,041,577 руб (за 01-05.02.2026)
Маржа_WB = SUM(revenue_spp) - SUM(comis_spp) - SUM(logist) - SUM(sebes)
         - SUM(reclama) - SUM(reclama_vn) - SUM(storage) - SUM(nds)
         - SUM(penalty) - SUM(retention) - SUM(deduction)
```

**Компоненты:** Продажи до СПП − Комиссия до СПП − Логистика − Себестоимость − Реклама внутр. − Реклама внеш. − Хранение − НДС − Штрафы − Удержания − Вычеты

### 3.2 OZON Маржа (верифицировано 07.02.2026, точное совпадение)

```sql
-- PowerBI: 57,014 руб | БД: 57,014 руб (за 01-05.02.2026)
Маржа_OZON = SUM(marga) - SUM(nds)
```

### 3.3 Производные метрики

```sql
-- Маржинальность (%)
Маржинальность = Маржа / Выручка_до_СПП * 100

-- ДРР (%)
ДРР_WB = (SUM(reclama) + SUM(reclama_vn)) / SUM(revenue_spp) * 100
ДРР_OZON = (SUM(reclama_end) + SUM(adv_vn)) / SUM(price_end) * 100

-- ROMI (%)
ROMI = Маржа / Реклама * 100

-- СПП (%)
СПП_WB = SUM(spp) / SUM(revenue_spp) * 100
СПП_OZON = SUM(spp) / SUM(price_end) * 100

-- Ср.чек заказов (руб) — ПРОГНОЗ
Ср_чек_заказов = Заказы_руб / Заказы_шт

-- Ср.чек продаж (руб) — ФАКТ
Ср_чек_продаж = Выручка_до_СПП / Продажи_шт

-- CTR (%)
CTR = clicks / views * 100

-- CPC (руб)
CPC_WB = sum / clicks          -- из wb_adv
CPC_OZON = rk_expense / clicks -- из adv_stats_daily

-- CPO (руб)
CPO = Реклама / Заказы_рекл

-- CR в корзину (%)
CR_корзина = Корзина / Показы * 100

-- CR в заказ (%)
CR_заказ = Заказы / Показы * 100

-- Выкуп (%)
Выкуп = Выкупы / Заказы * 100

-- Модель из артикула
model = SPLIT_PART(article, '/', 1)
```

### 3.4 Метрики P&L (ОПИУ)

| Метрика | Формула |
|---------|---------|
| Выручка за вычетом возвратов | Продажи_после_СПП − Самовыкупы |
| Маржинальная прибыль | Выручка_после_СПП − Себестоимость − Расходы_площадки |
| Операционная прибыль (EBITDA) | Маржинальная_прибыль − Косвенные_расходы |
| Чистая прибыль | EBITDA + Доходы_после − Расходы_после − Налоги |

---

## 4. БЫСТРАЯ СПРАВКА

### Какое поле использовать для...

| Метрика | WB | OZON |
|---------|-----|------|
| Выручка (до СПП) | `revenue_spp` | `price_end` |
| Выручка (после СПП) | `revenue` | `price_end_spp` |
| Маржа | **формула из 11 полей** или `marga_union - nds` | `marga - nds` |
| Комиссия (до СПП) | `comis_spp` | `comission_end` |
| Комиссия (после СПП) | `comis` | `comission_end_spp` |
| Логистика | `logist` | `logist_end` |
| Себестоимость | `sebes` | `sebes_end` |
| Реклама (внутр.) | `reclama` | `reclama_end` |
| Реклама (внеш.) | `reclama_vn` | `adv_vn` |
| Хранение | `storage` | `storage_end` |
| НДС | `nds` | `nds` |
| Скидка МП (СПП) | `spp` | `spp` |
| Продажи, шт | `full_counts` | `count_end` |
| Заказы, руб | `orders.pricewithdisc` | `orders.price` |
| Заказы, шт | `count_orders` | из таблицы `orders` |
| Возвраты, шт | `count_return` | `count_return` |
| Показы (органика) | `content_analysis.opencardcount` | `search_stat.hits_view` (данные = 0) |
| Показы (реклама) | `wb_adv.views` | `adv_stats_daily.views` |
| Клики (реклама) | `wb_adv.clicks` | `adv_stats_daily.clicks` |
| Модель из артикула | `SPLIT_PART(article, '/', 1)` | `SPLIT_PART(article, '/', 1)` |

### Чек-лист при написании SQL-запросов

- [ ] WB: использую `revenue_spp` (НЕ `revenue`) для "до СПП"
- [ ] WB: рассчитываю маржу по формуле из 11 полей (НЕ `marga_union`)
- [ ] WB: использую `comis_spp` (НЕ `comis`) для комиссии
- [ ] OZON: маржа = `marga - nds` (НЕ просто `marga`)
- [ ] OZON: использую поля с суффиксом `_end` для "до СПП"
- [ ] Фильтрую по правильному периоду
- [ ] Проверяю результат на порядок величины
- [ ] Сверяю с PowerBI (расхождение должно быть <1%)

---

## 5. WILDBERRIES — ВСЕ ТАБЛИЦЫ

### 5.1 Список таблиц pbi_wb_wookiee

| Таблица | Строк | Назначение |
|---------|-------|------------|
| **abc_date** | 853K | Финансы по дням/артикулам (основная) |
| **abc_week** | 41K | Финансы по неделям |
| **abc_month** | 9K | Финансы по месяцам |
| **orders** | 285K | Сырые заказы |
| **sales** | 250K | Продажи |
| **stocks** | 1.3M | Остатки на складах |
| **nomenclature** | 3K | Справочник товаров |
| **content_analysis** | 61K | Воронка (показы → корзина → заказы) |
| **wb_adv** | 308K | Рекламная статистика |
| **wb_adv_history** | 32K | История рекламных кампаний |
| **adv_budget** | 7K | Бюджет рекламы |
| **adv_campaigns_info** | 1.7K | Информация о кампаниях |
| **sp_adv** | 1.7K | Рекламные кампании |
| **orders_voronka** | 100K | Воронка заказов по регионам |
| **reportdetailbyperiod** | 4.8M | Детальный отчёт по периодам |
| **reportdetailbyperiod_daily** | 759K | Ежедневный детальный отчёт |
| **products** | 21K | Товары |
| **price** | 48K | Цены |
| **price_wb_off** | 568K | История цен |
| **paid_storage** | 6.3M | Платное хранение |
| **paid_acceptance** | 6K | Платная приёмка |
| **realization** | 43K | Отчёты о реализации |
| **returns** | 14K | Возвраты |
| **transactions** | 134K | Финансовые транзакции |
| **feedbacks_off** | 34K | Отзывы |
| **stat_words** | 11.6M | Статистика поисковых запросов |
| **excluded_words** | 161K | Исключённые слова |
| **ms_product** | 556K | МойСклад товары |
| **ms_sklad** | 53K | МойСклад склад |
| **ms_stocks** | 177K | МойСклад остатки |
| **postavki** | 23K | Поставки |
| **on_way** | 9K | В пути |
| **details_adv** | 5K | Детали рекламы |
| **nomenclature_history** | 10K | История изменений номенклатуры |

---

### 5.2 WB abc_date — 94 поля (основная финансовая таблица)

#### Идентификаторы

| # | Поле | Тип | Описание |
|---|------|-----|----------|
| 1 | `date` | date | Дата |
| 2 | `period` | varchar | Период (формат "01.2024") |
| 3 | `dateto` | text | Дата окончания периода |
| 4 | `lk` | text | Юридическое лицо |
| 5 | `article` | text | Артикул поставщика |
| 6 | `ts_name` | text | Размер (S, M, L, XL и т.д.) |
| 7 | `barcode` | text | Штрихкод |
| 8 | `nm_id` | bigint | Номенклатурный ID в WB |
| 9 | `mp` | text | Маркетплейс ("wb") |
| 10 | `dateupdate` | timestamp | Дата обновления записи |

#### Выручка и продажи

| # | Поле | Тип | Описание | PowerBI |
|---|------|-----|----------|---------|
| 11 | `revenue_spp` | numeric | **Выручка ДО СПП (цена продавца)** | Продажи до скидки МП, руб |
| 12 | `revenue` | numeric | Выручка ПОСЛЕ СПП (цена покупателя) | Продажи после скидки МП, руб |
| 13 | `buyouts_spp` | numeric | Выкупы ДО СПП (руб) | Выкупы до СПП |
| 14 | `buyouts` | numeric | Выкупы ПОСЛЕ СПП (руб) | Выкупы после СПП |
| 15 | `revenue_return_spp` | numeric | Возвраты ДО СПП (руб) | Возвраты до скидки МП |
| 16 | `revenue_return` | numeric | Возвраты ПОСЛЕ СПП (руб) | Возвраты после скидки МП |
| 17 | `full_counts` | integer | **Количество продаж (выкупов)** | Продажи, шт |
| 18 | `count_orders` | integer | Количество заказов | Заказы, шт |
| 19 | `count_return` | numeric | Количество возвратов | Возвраты, шт |
| 20 | `count_cancell` | integer | Количество отмен | Отмены, шт |
| 21 | `counts_sam` | numeric | Количество самовыкупов | Самовыкупы, шт |
| 22 | `returns` | numeric | Возвраты (руб) | Возвраты, руб |
| 23 | `spp` | numeric | **Скидка маркетплейса (руб)** | СПП, руб |
| 24 | `conversion` | numeric | Конверсия (%) | Конверсия |
| 25 | `average_check` | numeric | Средний чек (руб) | Средний чек |
| 26 | `retail_price` | numeric | Розничная цена | Цена розничная |
| 27 | `price_rozn` | numeric | Розничная цена (дубль) | Цена розничная |
| 28 | `sale_sum` | numeric | Сумма реализации | Реализация, руб |

#### Расходы (основные)

| # | Поле | Тип | Описание | PowerBI | Входит в формулу маржи |
|---|------|-----|----------|---------|------------------------|
| 29 | `comis_spp` | numeric | **Комиссия ДО СПП** | Комиссия до скидки МП | ДА |
| 30 | `comis` | numeric | Комиссия ПОСЛЕ СПП | Комиссия после скидки МП | нет |
| 31 | `logist` | numeric | **Логистика** | Логистика, руб | ДА |
| 32 | `sebes` | numeric | **Себестоимость** | Себестоимость, руб | ДА |
| 33 | `reclama` | numeric | **Реклама внутренняя** | Реклама внутри, руб | ДА |
| 34 | `reclama_vn` | numeric | **Реклама внешняя (всего)** | Реклама внешняя, руб | ДА |
| 35 | `storage` | numeric | **Хранение** | Хранение, руб | ДА |
| 36 | `nds` | numeric | **НДС** | НДС, руб | ДА |
| 37 | `penalty` | numeric | **Штрафы** | Штрафы, руб | ДА |
| 38 | `retention` | numeric | **Удержания** | Удержания, руб | ДА |
| 39 | `deduction` | numeric | **Вычеты** | Вычеты, руб | ДА |
| 40 | `nalog` | numeric | Налог (УСН) | УСН, руб | нет |

#### Реклама (детализация)

| # | Поле | Тип | Описание |
|---|------|-----|----------|
| 41 | `reclama_vn_vk` | numeric | Реклама ВКонтакте |
| 42 | `reclama_vn_creators` | numeric | Реклама у блогеров |
| 43 | `advert` | numeric | Реклама (альтернативное поле). *Требуется уточнение* |
| 44 | `marketing` | numeric | Маркетинг. *Требуется уточнение* |

#### Расходы по самовыкупам

| # | Поле | Тип | Описание |
|---|------|-----|----------|
| 45 | `comis_sam` | numeric | Комиссия по самовыкупам |
| 46 | `logist_sam` | numeric | Логистика самовыкупов |
| 47 | `sebes_sam` | numeric | Себестоимость самовыкупов |
| 48 | `sebes_return` | numeric | Себестоимость возвратов |

#### Маржа

| # | Поле | Тип | Описание |
|---|------|-----|----------|
| 49 | `marga` | numeric | Маржа (базовая). Назначение неясно. *Требуется уточнение* |
| 50 | `marga_union` | numeric | Маржа (объединённая) **БЕЗ НДС**. Финальная маржа = `marga_union - nds` (по аналогии с OZON) |
| 51 | `proverka` | numeric | Проверочное поле. *Требуется уточнение* |
| 52 | `proverka2` | numeric | Второе проверочное поле. *Требуется уточнение* |

#### Объединённые поля (`_union`) — *все требуют уточнения*

| # | Поле | Тип | Описание |
|---|------|-----|----------|
| 53 | `comis_union` | numeric | Комиссия (объединённая). *Требуется уточнение* |
| 54 | `logist_union` | numeric | Логистика (объединённая). *Требуется уточнение* |
| 55 | `logist_union_prod` | numeric | Логистика продукции (объединённая). *Требуется уточнение* |
| 56 | `logist_union_return` | numeric | Логистика возвратов (объединённая). *Требуется уточнение* |
| 57 | `storage_union` | numeric | Хранение (объединённое). *Требуется уточнение* |
| 58 | `over_logist` | numeric | Сверхлогистика. *Требуется уточнение* |
| 59 | `over_logist_union` | numeric | Сверхлогистика (объединённая). *Требуется уточнение* |
| 60 | `penalty_union` | numeric | Штрафы (объединённые). *Требуется уточнение* |
| 61 | `dop_penalty` | numeric | Дополнительные штрафы. *Требуется уточнение* |
| 62 | `retention_union` | numeric | Удержания (объединённые). *Требуется уточнение* |
| 63 | `inspection` | numeric | Инспекция. *Требуется уточнение* |
| 64 | `inspection_union` | numeric | Инспекция (объединённая). *Требуется уточнение* |

#### Логистика (детализация)

| # | Поле | Тип | Описание |
|---|------|-----|----------|
| 65 | `logis_return_rub` | numeric | Логистика возвратов (руб) |
| 66 | `logis_cancell_rub` | numeric | Логистика отмен (руб) |
| 67 | `rebill_logistic_cost` | numeric | Перевыставление логистики. *Требуется уточнение* |

#### Фулфилмент

| # | Поле | Тип | Описание |
|---|------|-----|----------|
| 68 | `no_vozvratny_fulfil` | numeric | Невозвратный фулфилмент. *Требуется уточнение* |
| 69 | `prod_fulfil` | numeric | Продуктовый фулфилмент. *Требуется уточнение* |
| 70 | `fulfilment_sam` | numeric | Фулфилмент самовыкупов |
| 71 | `fulfilment_returns` | numeric | Фулфилмент возвратов |

#### Внешняя логистика

| # | Поле | Тип | Описание |
|---|------|-----|----------|
| 72 | `no_vozvratny_vhesh_logist` | numeric | Невозвратная внеш. логистика. *Требуется уточнение* |
| 73 | `prod_vnehs_logist` | numeric | Продуктовая внеш. логистика. *Требуется уточнение* |
| 74 | `vnesh_logist_sam` | numeric | Внеш. логистика самовыкупов |
| 75 | `vnesh_logist_returns` | numeric | Внеш. логистика возвратов |

#### Упаковка

| # | Поле | Тип | Описание |
|---|------|-----|----------|
| 76 | `vozvratny_upakov` | numeric | Возвратная упаковка. *Требуется уточнение* |
| 77 | `prod_upakov` | numeric | Продуктовая упаковка. *Требуется уточнение* |
| 78 | `upakovka_sam` | numeric | Упаковка самовыкупов |
| 79 | `upakovka_returns` | numeric | Упаковка возвратов |

#### Зеркало

| # | Поле | Тип | Описание |
|---|------|-----|----------|
| 80 | `vozvratny_zerkalo` | numeric | Возвратное зеркало. *Требуется уточнение* |
| 81 | `prod_zercalo` | numeric | Продуктовое зеркало. *Требуется уточнение* |
| 82 | `zercalo_sam` | numeric | Зеркало самовыкупов |
| 83 | `zercalo_returns` | numeric | Зеркало возвратов |

#### Прочие финансовые поля

| # | Поле | Тип | Описание |
|---|------|-----|----------|
| 84 | `surcharges` | numeric | Доплаты. *Требуется уточнение* |
| 85 | `compens_comis` | numeric | Компенсация комиссии. *Требуется уточнение* |
| 86 | `sebes_kompens` | numeric | Компенсация себестоимости |
| 87 | `acquiring` | numeric | Эквайринг. *Требуется уточнение* |
| 88 | `acquiring_fee` | numeric | Эквайринг (комиссия). *Требуется уточнение* |
| 89 | `cross` | numeric | Кросс-докинг |
| 90 | `bank` | numeric | Банковские расходы |
| 91 | `service` | numeric | Сервисные расходы |
| 92 | `count_self` | numeric | *Требуется уточнение* |
| 93 | `inkasator_count` | numeric | *Требуется уточнение* |
| 94 | `kompens_counts` | numeric | Количество компенсаций. *Требуется уточнение* |
| 95 | `count_otkl` | numeric | Количество отклонений. *Требуется уточнение* |
| 96 | `kiz` | numeric | Маркировка (КИЗ). *Требуется уточнение* |
| 97 | `other_deductions` | numeric | Прочие вычеты. *Требуется уточнение* |
| 98 | `subsribe` | numeric | Подписка. *Требуется уточнение* |
| 99 | `bonus_pay` | numeric | Бонусная оплата. *Требуется уточнение* |

#### Дополнительные доходы/расходы

| # | Поле | Тип | Описание |
|---|------|-----|----------|
| 100 | `revenue_dop_defect` | numeric | Доход от дефектов. *Требуется уточнение* |
| 101 | `rashod_dop_defect` | numeric | Расход на дефекты. *Требуется уточнение* |
| 102 | `revenue_dop_loss` | numeric | Доход от потерь (компенсация). *Требуется уточнение* |
| 103 | `rashod_dop_loss` | numeric | Расход на потери. *Требуется уточнение* |
| 104 | `additional_payment` | integer | Дополнительные платежи. *Требуется уточнение* |
| 105 | `rashod_additional_payment` | numeric | Расход по доп. платежам. *Требуется уточнение* |
| 106 | `postup_wb_all` | numeric | Поступления от WB. *Требуется уточнение* |
| 107 | `loan` | numeric | Кредит. *Требуется уточнение* |
| 108 | `cashback_amount` | numeric | Кэшбэк. *Требуется уточнение* |
| 109 | `cashback_c_c` | numeric | Кэшбэк (комиссия). *Требуется уточнение* |

---

### 5.3 WB orders — 31 поле (заказы)

| Поле | Тип | Описание |
|------|-----|----------|
| `date` | timestamp | Дата заказа |
| `lastchangedate` | timestamp | Дата последнего изменения |
| `supplierarticle` | text | Артикул поставщика |
| `techsize` | text | Размер |
| `barcode` | text | Штрихкод |
| `totalprice` | numeric | Общая цена |
| `discountpercent` | numeric | Процент скидки |
| `spp` | numeric | СПП |
| `finishedprice` | numeric | Итоговая цена |
| `pricewithdisc` | numeric | **Цена со скидкой (используется как "Заказы, руб")** |
| `warehousename` | text | Название склада |
| `oblast` | text | Область |
| `region` | text | Регион |
| `regionname` | text | Регион (название) |
| `country` | text | Страна |
| `nmid` | bigint | Номенклатурный ID |
| `subject` | text | Предмет |
| `category` | text | Категория |
| `brand` | text | Бренд |
| `iscancel` | text | Отменён (0/1) |
| `cancel_dt` | timestamp | Дата отмены |
| `gnumber` | text | Номер заказа |
| `gnumberid` | text | Артикул поставщика (альт.) |
| `sticker` | text | Стикер (штрих-код) |
| `srid` | text | ID |
| `ordertype` | text | Тип заказа (Клиентский) |
| `lk` | text | Юр.лицо |
| `wb_claster` | text | Кластер WB |
| `wb_claster_to` | text | Кластер назначения |
| `warehousetype` | text | Тип склада |
| `dateupdate` | timestamp | Дата обновления |

---

### 5.4 WB sales — 32 поля (продажи)

| Поле | Тип | Описание |
|------|-----|----------|
| `date` | timestamp | Дата продажи |
| `lastchangedate` | timestamp | Дата последнего изменения |
| `supplierarticle` | text | Артикул поставщика |
| `techsize` | text | Размер |
| `barcode` | text | Штрихкод |
| `totalprice` | numeric | Общая цена |
| `discountpercent` | integer | Процент скидки |
| `spp` | numeric | СПП |
| `forpay` | numeric | К выплате |
| `finishedprice` | numeric | Итоговая цена |
| `pricewithdisc` | numeric | Цена со скидкой |
| `warehousename` | text | Название склада |
| `countryname` | text | Страна |
| `oblastokrugname` | text | Область/округ |
| `regionname` | text | Регион |
| `nmid` | bigint | Номенклатурный ID |
| `subject` | text | Предмет |
| `category` | text | Категория |
| `brand` | text | Бренд |
| `isstorno` | integer | Сторно (0/1) |
| `gnumber` | text | Номер |
| `saleid` | text | ID продажи |
| `srid` | text | ID |
| `lk` | text | Юр.лицо |
| `paymentsaleamount` | numeric | Сумма выплаты |
| `dateupdate` | timestamp | Дата обновления |

---

### 5.5 WB nomenclature — 19 полей (справочник товаров)

| Поле | Тип | Описание |
|------|-----|----------|
| `vendorcode` | text | **Артикул поставщика (ключ связи с abc_date.article)** |
| `nmid` | bigint | **Номенклатурный ID (ключ связи с wb_adv.nmid)** |
| `brand` | text | Бренд |
| `object` | text | Категория товара |
| `title` | text | Название товара |
| `barcod` | text | Штрихкод |
| `colors` | text | Цвет |
| `techsize` | text | Размер |
| `chrtid` | text | ID характеристики |
| `imtid` | text | IMT ID |
| `video` | text | Видео |
| `tags` | text | Теги |
| `description` | text | Описание |
| `link_card` | text | Ссылка на карточку |
| `mediafiles` | text | Медиафайлы |
| `lk` | text | Юр.лицо |
| `createdat` | date | Дата создания |
| `updateat` | date | Дата обновления |
| `dateupdate` | timestamp | Дата обновления (timestamp) |

---

### 5.6 WB content_analysis — воронка контента

| Поле | Тип | Описание | PowerBI |
|------|-----|----------|---------|
| `date` | date | Дата | Дата |
| `vendorcode` | text | **Артикул поставщика** | Артикул |
| `nmid` | bigint | Номенклатурный ID | — |
| `opencardcount` | integer | **Открытия карточки** | Показы карточки, шт |
| `addtocartcount` | integer | **Добавления в корзину** | Корзина, шт |
| `orderscount` | integer | **Заказы из воронки** | Заказы (воронка), шт |
| `buyoutscount` | integer | **Выкупы** | Выкупы, шт |
| `addtocartpercent` | numeric | CR открытие → корзина (%) | CR в корзину |
| `carttoorderpercent` | numeric | CR корзина → заказ (%) | CR в заказ |
| `buyoutspercent` | numeric | Процент выкупа | % выкупа |
| `addtowishlist` | integer | Добавления в избранное | Избранное |
| `lk` | text | Юр.лицо | — |

---

### 5.7 WB wb_adv — рекламная статистика (308K строк)

| Поле | Тип | Описание | PowerBI |
|------|-----|----------|---------|
| `date` | date | Дата | Дата |
| `nmid` | bigint | **Номенклатурный ID (связь через nomenclature)** | nmId |
| `views` | integer | **Рекламные показы** | Показы реклама, шт |
| `clicks` | integer | **Рекламные клики** | Клики реклама, шт |
| `sum` | numeric | **Расход на рекламу (руб)** | Расход реклама, руб |
| `atbs` | integer | **Добавления в корзину с рекламы** | Корзина (рекл.), шт |
| `orders` | integer | **Заказы с рекламы** | Заказы (рекл.), шт |
| `ctr` | numeric | CTR (%) | CTR |
| `cpc` | numeric | CPC (руб) | CPC |
| `cr` | numeric | CR (%) | CR |
| `frq` | numeric | Частота показов | Частота |
| `shks` | integer | *Требуется уточнение* | — |
| `unique_users` | integer | Уникальные пользователи | — |
| `canceled` | integer | Отменённые. *Требуется уточнение* | — |
| `advertid` | integer | ID рекламной кампании | — |
| `name_rk` | text | Название рекламной кампании | — |
| `lk` | text | Юр.лицо | — |

---

### 5.8 WB orders_voronka — воронка заказов по регионам (100K строк)

| Поле | Тип | Описание |
|------|-----|----------|
| `vendorcode` | text | Артикул |
| `nmid` | bigint | Номенклатурный ID |
| `regionname` | text | Регион |
| `officename` | text | Склад/ПВЗ |
| `orderscount` | integer | Количество заказов |
| `orderssum` | numeric | Сумма заказов |
| `buyoutcount` | integer | Количество выкупов |
| `buyoutsum` | numeric | Сумма выкупов |
| `operation_date` | date | Дата |

---

## 6. OZON — ВСЕ ТАБЛИЦЫ

### 6.1 Список таблиц pbi_ozon_wookiee

| Таблица | Строк | Назначение |
|---------|-------|------------|
| **abc_date** | 156K | Финансы по дням/артикулам (основная) |
| **abc_week** | 37K | Финансы по неделям |
| **abc_month** | 9K | Финансы по месяцам |
| **orders** | 131K | Заказы |
| **postings** | 131K | Отправления |
| **returns** | 67K | Возвраты |
| **stocks** | 659K | Остатки на складах |
| **transactions** | 96K | Финансовые транзакции |
| **nomenclature** | 1.5K | Справочник товаров |
| **nomenclature_history** | 1.2K | История изменений товаров |
| **search_stat** | 130K | Аналитика поиска и карточек |
| **adv_stats_daily** | 1.3K | Рекламная статистика (агрегат по РК) |
| **ozon_adv** | 3.7K | Детальная реклама по товарам |
| **ozon_adv_api** | 3.8K | Реклама через API (по SKU) |
| **ozon_adv_history** | 1.1K | История рекламных кампаний |
| **details_adv** | 4.8K | Детали рекламы |
| **price** | 306K | История цен |
| **realization** | 28K | Отчёты о реализации |
| **accrual_report** | 425K | Отчёт о начислениях |
| **ozon_services** | 375K | Услуги OZON |
| **warehousing_cost_bas** | 14K | Стоимость хранения |
| **category** | 237K | Категории |
| **sverka** | 1.4K | Таблица сверки. *Требуется уточнение* |
| **is_foreign** | 1 | *Требуется уточнение* |
| **kompens** | 0 | Компенсации (пустая) |
| **utilization** | 0 | Утилизация (пустая) |

---

### 6.2 OZON abc_date — 72 поля (основная финансовая таблица)

#### Идентификаторы

| # | Поле | Тип | Описание |
|---|------|-----|----------|
| 1 | `date` | date | Дата |
| 2 | `period` | varchar | Период (формат "01.2024") |
| 3 | `lk` | text | Юридическое лицо |
| 4 | `article` | text | Артикул товара (offer_id) |
| 5 | `sku` | text | SKU товара |
| 6 | `product_id` | text | ID товара в OZON |
| 7 | `mp` | text | Маркетплейс ("ozon") |
| 8 | `date_update` | timestamp | Дата обновления записи |

#### Выручка и продажи

| # | Поле | Тип | Описание | PowerBI |
|---|------|-----|----------|---------|
| 9 | `price_end` | numeric | **Выручка ДО СПП (итоговая)** | Продажи до скидки МП, руб |
| 10 | `price_end_spp` | numeric | Выручка ПОСЛЕ СПП | Продажи после скидки МП, руб |
| 11 | `buyouts_end` | numeric | Выкупы (руб) | Выкупы, руб |
| 12 | `buyouts_spp` | numeric | Выкупы после СПП (руб) | — |
| 13 | `return_end` | numeric | Возвраты (руб, до СПП) | Возвраты до СПП |
| 14 | `return_end_spp` | numeric | Возвраты (руб, после СПП) | Возвраты после СПП |
| 15 | `count_end` | numeric | **Количество продаж (за вычетом возвратов)** | Продажи, шт |
| 16 | `count_return` | numeric | Количество возвратов | Возвраты, шт |
| 17 | `cancell_end` | numeric | Отмены | Отмены |
| 18 | `count_sam` | numeric | Количество самовыкупов | Самовыкупы, шт |
| 19 | `spp` | numeric | **Скидка маркетплейса (руб)** | СПП, руб |

#### Расходы (основные)

| # | Поле | Тип | Описание | PowerBI | Входит в формулу маржи |
|---|------|-----|----------|---------|------------------------|
| 20 | `comission_end` | numeric | **Комиссия ДО СПП** | Комиссия до скидки МП | через marga |
| 21 | `comission_end_spp` | numeric | Комиссия ПОСЛЕ СПП | Комиссия после скидки МП | нет |
| 22 | `logist_end` | numeric | **Логистика** | Логистика, руб | через marga |
| 23 | `storage_end` | numeric | **Хранение** | Хранение, руб | через marga |
| 24 | `sebes_end` | numeric | **Себестоимость** | Себестоимость, руб | через marga |
| 25 | `reclama_end` | numeric | **Реклама внутренняя** | Реклама внутри, руб | через marga |
| 26 | `bank_end` | numeric | Эквайринг | Эквайринг, руб | *Требуется уточнение* |
| 27 | `nalog_end` | numeric | Налог (УСН) | УСН, руб | нет |
| 28 | `nds` | numeric | **НДС** | НДС, руб | ДА (вычитается из marga) |
| 29 | `cross_end` | numeric | Кросс-докинг | Кросс-докинг, руб | *Требуется уточнение* |

#### Внешняя реклама

| # | Поле | Тип | Описание | PowerBI |
|---|------|-----|----------|---------|
| 30 | `adv_vn` | numeric | **Внешняя реклама (общая)** | Реклама внешняя, руб |
| 31 | `adv_vn_vk` | numeric | Реклама ВКонтакте | Реклама ВК, руб |
| 32 | `adv_vn_creators` | numeric | Реклама у блогеров | Реклама блогеры, руб |

#### Маржа

| # | Поле | Тип | Описание |
|---|------|-----|----------|
| 33 | `marga` | numeric | **Маржа (промежуточная).** Финальная маржа = `marga - nds` |

#### Сервисы OZON

| # | Поле | Тип | Описание |
|---|------|-----|----------|
| 34 | `service_end` | numeric | Сервисные услуги (общее) |
| 35 | `service_bonus` | numeric | Бонусы |
| 36 | `service_kor` | numeric | Корректировки |
| 37 | `service_util` | numeric | Утилизация |
| 38 | `service_izlish` | numeric | Излишки |
| 39 | `service_defect` | numeric | Дефекты товара |
| 40 | `service_otziv` | numeric | Отзывы (платные) |
| 41 | `service_izlish_opozn` | numeric | Излишки опознанные. *Требуется уточнение* |
| 42 | `service_rassilka` | numeric | Рассылка писем |
| 43 | `service_premium` | numeric | Премиум |
| 44 | `service_viplat` | numeric | Выплаты. *Требуется уточнение* |
| 45 | `service_grafic` | numeric | График. *Требуется уточнение* |
| 46 | `service_bron` | numeric | Бронирование. *Требуется уточнение* |
| 47 | `service_defect_sklad` | numeric | Дефекты на складе |
| 48 | `service_loss` | numeric | Потери OZON |
| 49 | `service_uslov_otgruz` | numeric | Условия отгрузки. *Требуется уточнение* |
| 50 | `service_new` | numeric | Новые сервисы. *Требуется уточнение* |
| 51 | `service_fbo` | numeric | FBO сервисы |
| 52 | `service_compens` | numeric | Компенсации |
| 53 | `service_brand` | numeric | Брендовые сервисы |

#### Компоненты выкупа

| # | Поле | Тип | Описание |
|---|------|-----|----------|
| 54 | `buyouts_ss` | numeric | Себестоимость выкупов. *Требуется уточнение* |
| 55 | `buyouts_logist` | numeric | Логистика выкупов. *Требуется уточнение* |
| 56 | `buyouts_comission` | numeric | Комиссия с выкупов. *Требуется уточнение* |
| 57 | `buyouts_bank` | numeric | Банк. комиссия с выкупов. *Требуется уточнение* |

#### Компенсации и прочее

| # | Поле | Тип | Описание |
|---|------|-----|----------|
| 58 | `sebes_kompens` | numeric | Компенсация себестоимости |
| 59 | `sebes_util` | numeric | Утилизация себестоимости |
| 60 | `pretenzia` | numeric | Претензии. *Требуется уточнение* |
| 61 | `other_compensation` | numeric | Прочие компенсации |
| 62 | `other_services` | numeric | Прочие услуги. *Требуется уточнение* |
| 63 | `error` | numeric | Ошибки. *Требуется уточнение* |

#### Доставка

| # | Поле | Тип | Описание |
|---|------|-----|----------|
| 64 | `drop_off` | numeric | Drop-off. *Требуется уточнение* |
| 65 | `transfer_delivery` | numeric | Трансферная доставка. *Требуется уточнение* |
| 66 | `realfbs` | numeric | FBS реализация |

#### ЕАЭС

| # | Поле | Тип | Описание |
|---|------|-----|----------|
| 67 | `eaes_count` | numeric | Количество продаж ЕАЭС |
| 68 | `eaes` | numeric | ЕАЭС выручка |
| 69 | `eaes_spp` | numeric | ЕАЭС после СПП. *Требуется уточнение* |
| 70 | `sebes_eaes` | numeric | Себестоимость ЕАЭС |
| 71 | `eaes_nds` | numeric | НДС ЕАЭС. *Требуется уточнение* |

#### Прочее

| # | Поле | Тип | Описание |
|---|------|-----|----------|
| 72 | `zvezdny_tovar` | numeric | Программа "Звёздный товар". *Требуется уточнение* |

---

### 6.3 OZON orders — 23 поля (заказы)

| Поле | Тип | Описание |
|------|-----|----------|
| `order_id` | bigint | ID заказа |
| `posting_number` | text | Номер отправления |
| `order_number` | text | Номер заказа |
| `product_id` | text | ID товара |
| `sku` | text | SKU |
| `offer_id` | text | **Артикул продавца (ключ связи с abc_date.article)** |
| `delivery_schema` | text | Схема доставки (FBO/FBS) |
| `status` | text | Статус (delivered, cancelled, etc.) |
| `price` | numeric | **Цена (используется как "Заказы, руб")** |
| `quantity` | integer | Количество (обычно 1) |
| `commission_amount` | numeric | Сумма комиссии |
| `in_process_at` | timestamp | **Дата обработки (дата заказа)** |
| `dateupdate` | timestamp | Дата обновления |
| `warehouse_id` | text | ID склада |
| `warehouse_name` | text | Название склада |
| `cluster_to` | text | Кластер назначения |
| `cluster_from` | text | Кластер отправки |
| `lk` | text | Юр.лицо |
| `is_express` | text | Экспресс доставка |
| `ozon_claster` | text | Кластер OZON |
| `ozon_claster_to` | text | Кластер OZON (назначение) |
| `city` | text | Город |
| `region` | text | Регион |

---

### 6.4 OZON nomenclature — 19 полей (справочник товаров)

| Поле | Тип | Описание |
|------|-----|----------|
| `article` | text | Артикул |
| `ozon_product_id` | text | ID товара в OZON |
| `fbo_ozon_sku_id` | text | FBO SKU |
| `fbs_ozon_sku_id` | text | FBS SKU |
| `barcode` | text | Штрихкод |
| `category` | text | Категория |
| `status` | text | Статус ("Готов к продаже") |
| `current_price_including_discount` | numeric | Текущая цена со скидкой |
| `price_before_discount` | numeric | Цена до скидки |
| `premium_price` | numeric | Премиум цена |
| `market_price` | numeric | Рыночная цена |
| `product_volume_l` | numeric | Объём (л) |
| `volumetric_weight_kg` | numeric | Объёмный вес (кг) |
| `primary_image` | text | URL главного изображения |
| `lk` | text | Юр.лицо |
| `brand` | text | Бренд |
| `name_tovar` | text | Название товара |
| `dateupdate` | timestamp | Дата обновления |
| `createdat` | date | Дата создания |

---

### 6.5 OZON returns — 27 полей (возвраты)

| Поле | Тип | Описание |
|------|-----|----------|
| `operation_id` | text | ID операции |
| `operation_type` | text | Тип операции |
| `operation_date` | date | Дата операции |
| `operation_type_name` | text | Название типа операции |
| `posting_number` | text | Номер отправления |
| `order_date` | timestamp | Дата заказа |
| `sku` | text | SKU |
| `product_id` | text | ID товара |
| `name` | text | Название товара |
| `lk` | text | Юр.лицо |
| `delivery_schema` | text | Схема доставки |
| `type` | text | Тип (returns) |
| `amount` | numeric | Сумма |
| `delivery_charge` | numeric | Стоимость доставки |
| `return_delivery_charge` | numeric | Стоимость возврата |
| `accruals_for_sale` | numeric | Начисления за продажу |
| `sale_commission` | numeric | Комиссия с продажи |
| `marketplaceserviceitemdirectflowlogistic` | numeric | Логистика (прямой поток) |
| `marketplaceserviceitemreturnflowlogistic` | numeric | Логистика (возврат) |
| `marketplaceserviceitemdelivtocustomer` | numeric | Доставка клиенту |
| `marketplaceserviceitemdirectflowtrans` | numeric | Транспорт (прямой) |
| `marketplaceserviceitemfulfillment` | numeric | Фулфилмент |
| `marketplaceserviceitemreturnafterdelivtocustomer` | numeric | Возврат после доставки |
| `marketplaceserviceitemreturnnotdelivtocustomer` | numeric | Возврат без доставки |
| `marketplaceserviceitemreturnpartgoodscustomer` | numeric | Частичный возврат |

---

### 6.6 OZON search_stat — аналитика поиска (130K строк)

**ВНИМАНИЕ: Органические данные = 0 для всех записей. Работают только рекламные данные.**

| Поле | Тип | Описание | PowerBI |
|------|-----|----------|---------|
| `date` | date | Дата | Дата |
| `sku` | text | SKU | SKU |
| `hits_view` | integer | Показы (органика) — **= 0** | Показы, шт |
| `hits_view_search` | integer | Показы в поиске — **= 0** | — |
| `hits_view_pdp` | integer | Показы на карточке — **= 0** | — |
| `hits_tocart` | integer | Корзина — **= 0** | Корзина, шт |
| `hits_tocart_search` | integer | Корзина из поиска — **= 0** | — |
| `hits_tocart_pdp` | integer | Корзина с карточки — **= 0** | — |
| `session_view` | integer | Сессии (показы) | — |
| `conv_tocart` | real | CR в корзину (%) | CR в корзину |
| `ordered_units` | integer | Заказы — **= 0** | Заказы, шт |
| `delivered_units` | integer | Доставленные | — |
| `revenue` | numeric | Выручка | — |
| `returns` | integer | Возвраты | — |
| `cancellations` | integer | Отмены | — |
| `position_category` | real | Позиция в категории | Позиция |

---

### 6.7 OZON adv_stats_daily — рекламная статистика (1.3K строк)

| Поле | Тип | Описание | PowerBI |
|------|-----|----------|---------|
| `id_rk` | bigint | ID рекламной кампании | ID РК |
| `title` | text | Название РК | Название РК |
| `operation_date` | date | Дата | Дата |
| `views` | integer | **Рекламные показы** | Показы реклама, шт |
| `clicks` | integer | **Рекламные клики** | Клики реклама, шт |
| `orders_count` | integer | **Заказы с рекламы** | Заказы (рекл.), шт |
| `orders_amount` | numeric | Сумма заказов с рекламы | Заказы (рекл.), руб |
| `rk_expense` | numeric | **Расход на рекламу (руб)** | Расход реклама, руб |
| `avg_bid` | numeric | Средняя ставка. *Требуется уточнение: за клик или за показ?* | Ставка |

---

### 6.8 OZON ozon_adv_api — реклама по SKU (3.8K строк)

| Поле | Тип | Описание |
|------|-----|----------|
| `sku` | text | SKU товара |
| `operation_date` | date | Дата |
| `clicks` | integer | Клики |
| `to_cart` | integer | Добавления в корзину |
| `orders` | integer | Заказы |
| `cpc` | integer | CPC |
| `ctr` | numeric | CTR (%) |
| `sum_rev` | numeric | Расход на рекламу (руб) |
| `id_rk` | text | ID рекламной кампании |
| `orders_model` | integer | *Требуется уточнение* |
| `revenu_model` | numeric | *Требуется уточнение* |

---

## 7. СВЯЗИ МЕЖДУ ТАБЛИЦАМИ

### 7.1 WB

```
abc_date.article = orders.gnumberid         -- артикул поставщика
abc_date.article = orders.supplierarticle   -- артикул поставщика (альт.)
abc_date.article = content_analysis.vendorcode
abc_date.article = nomenclature.vendorcode
wb_adv.nmid = nomenclature.nmid            -- через JOIN для получения артикула
abc_date.nm_id = nomenclature.nmid          -- прямая связь по nmid
```

**Получение рекламы по артикулу (WB):**
```sql
SELECT n.vendorcode, SUM(a.sum) as ad_spend
FROM wb_adv a
JOIN nomenclature n ON a.nmid = n.nmid
WHERE a.date >= '2026-02-01'
GROUP BY n.vendorcode;
```

### 7.2 OZON

```
abc_date.article = orders.offer_id     -- артикул
abc_date.sku = orders.sku              -- SKU
abc_date.article = nomenclature.article
adv_stats_daily.id_rk                  -- агрегат по РК (не по артикулу)
ozon_adv_api.sku = abc_date.sku        -- детальная реклама по товарам
```

### 7.3 Supabase (товарная матрица)

```sql
-- Связь со статусами товаров
artikuly.artikul = abc_date.article
artikuly.status_id → statusy.id → statusy.nazvanie
artikuly.model_id → modeli.id → modeli.model_osnova_id → modeli_osnova.kod

-- Группировка статусов:
-- "В продаже": Продается, Запуск, Новый
-- "Выводим": Выводим
-- "Не учитывать": План, Подготовка, Архив
```

### 7.4 Supabase — безопасность и подключение

**Подключение:** через Supabase Connection Pooler (роль `postgres` / service_role).
Python-скрипты обходят RLS (service_role = суперпользователь).

**RLS (Row Level Security):** включён на всех 16 таблицах (миграция 005, 11.02.2026).

| Роль | Права | Назначение |
|------|-------|------------|
| `postgres` (service_role) | Полный доступ | Python-скрипты, миграции |
| `authenticated` | SELECT only | Если когда-либо будет фронтенд |
| `anon` | Нет доступа | Публичный REST API заблокирован |

**При создании новых таблиц** — обязательно включить RLS и создать политики.
Подробная инструкция: `wookiee_sku_database/README.md` → раздел "Безопасность Supabase".

---

## 8. АКТУАЛЬНОСТЬ ДАННЫХ

### WB (pbi_wb_wookiee)

| Таблица | Период | Обновление | Строк |
|---------|--------|-----------|-------|
| `abc_date` | 01.01.2024 — сегодня | Ежедневно | 853K |
| `abc_week` | 01.01.2024 — сегодня | Еженедельно | 41K |
| `abc_month` | 01.01.2024 — сегодня | Ежемесячно | 9K |
| `orders` | 01.01.2024 — сегодня | Ежедневно | 285K |
| `sales` | 01.01.2024 — сегодня | Ежедневно | 250K |
| `stocks` | 01.01.2024 — сегодня | Ежедневно | 1.3M |

### OZON (pbi_ozon_wookiee)

| Таблица | Период | Обновление | Строк |
|---------|--------|-----------|-------|
| `abc_date` | 20.01.2024 — сегодня | Ежедневно | 156K |
| `abc_week` | 20.01.2024 — сегодня | Еженедельно | 37K |
| `abc_month` | 20.01.2024 — сегодня | Ежемесячно | 9K |
| `orders` | 20.01.2024 — сегодня | Ежедневно | 131K |
| `returns` | 20.01.2024 — сегодня | Ежедневно | 67K |
| `stocks` | 20.01.2024 — сегодня | Ежедневно | 659K |

### SQL для проверки актуальности

```sql
SELECT 'WB' as mp, MIN(date) as start, MAX(date) as end, MAX(dateupdate) as last_update
FROM pbi_wb_wookiee.public.abc_date
UNION ALL
SELECT 'OZON', MIN(date), MAX(date), MAX(date_update)
FROM pbi_ozon_wookiee.public.abc_date;
```

---

## 9. ТИПИЧНЫЕ ОШИБКИ

### Ошибка 1: Неправильные поля WB

| Неправильно | Правильно | Расхождение |
|-------------|-----------|-------------|
| `SUM(revenue)` | `SUM(revenue_spp)` | ~2x |
| `SUM(marga_union)` | Формула из 11 полей | ~10% |
| `SUM(comis)` | `SUM(comis_spp)` | ~15% |

### Ошибка 2: Сравнение выкупов между периодами

Заказы конца периода ещё не выкупились (лаг 3-21 день). Выкупы корректно сравнивать только с лагом 3+ недели.

### Ошибка 3: OZON маржа без вычета НДС

| Неправильно | Правильно |
|-------------|-----------|
| `SUM(marga)` | `SUM(marga) - SUM(nds)` |

### Ошибка 4: Забыт фильтр по периоду

Всегда указывать `WHERE date >= '...' AND date < '...'`.

### Ошибка 5: Путаница между БД

При кросс-запросах использовать полные имена: `pbi_wb_wookiee.public.abc_date`.

---

## 10. ЭТАЛОННЫЕ SQL-ЗАПРОСЫ

### WB маржа за период

```sql
SELECT
    SUM(revenue_spp) as sales_before_spp,
    SUM(revenue_spp) - SUM(comis_spp) - SUM(logist) - SUM(sebes)
    - SUM(reclama) - SUM(reclama_vn) - SUM(storage) - SUM(nds)
    - SUM(penalty) - SUM(retention) - SUM(deduction) as margin,
    ROUND((SUM(revenue_spp) - SUM(comis_spp) - SUM(logist) - SUM(sebes)
    - SUM(reclama) - SUM(reclama_vn) - SUM(storage) - SUM(nds)
    - SUM(penalty) - SUM(retention) - SUM(deduction))
    / NULLIF(SUM(revenue_spp), 0) * 100, 2) as margin_pct
FROM pbi_wb_wookiee.public.abc_date
WHERE date >= '2026-02-01' AND date < '2026-03-01';
```

### OZON маржа за период

```sql
SELECT
    SUM(price_end) as sales_before_spp,
    SUM(marga) - SUM(nds) as margin,
    ROUND((SUM(marga) - SUM(nds)) / NULLIF(SUM(price_end), 0) * 100, 2) as margin_pct
FROM pbi_ozon_wookiee.public.abc_date
WHERE date >= '2026-02-01' AND date < '2026-03-01';
```

### Сводный WB + OZON

```sql
SELECT 'WB' as mp,
    SUM(revenue_spp) as sales,
    SUM(revenue_spp) - SUM(comis_spp) - SUM(logist) - SUM(sebes)
    - SUM(reclama) - SUM(reclama_vn) - SUM(storage) - SUM(nds)
    - SUM(penalty) - SUM(retention) - SUM(deduction) as margin
FROM pbi_wb_wookiee.public.abc_date
WHERE date >= '2026-02-01' AND date < '2026-02-06'
UNION ALL
SELECT 'OZON',
    SUM(price_end),
    SUM(marga) - SUM(nds)
FROM pbi_ozon_wookiee.public.abc_date
WHERE date >= '2026-02-01' AND date < '2026-02-06';
```

### Маржинальность по моделям (WB)

```sql
SELECT
    SPLIT_PART(article, '/', 1) as model,
    SUM(revenue_spp) as revenue,
    SUM(revenue_spp) - SUM(comis_spp) - SUM(logist) - SUM(sebes)
    - SUM(reclama) - SUM(reclama_vn) - SUM(storage) - SUM(nds)
    - SUM(penalty) - SUM(retention) - SUM(deduction) as margin,
    ROUND((SUM(revenue_spp) - SUM(comis_spp) - SUM(logist) - SUM(sebes)
    - SUM(reclama) - SUM(reclama_vn) - SUM(storage) - SUM(nds)
    - SUM(penalty) - SUM(retention) - SUM(deduction))
    / NULLIF(SUM(revenue_spp), 0) * 100, 2) as margin_pct
FROM pbi_wb_wookiee.public.abc_date
WHERE date >= '2026-02-01' AND date < '2026-02-06'
GROUP BY SPLIT_PART(article, '/', 1)
ORDER BY revenue DESC;
```

### Рекламный трафик по артикулу (WB)

```sql
SELECT
    n.vendorcode as article,
    SUM(a.views) as ad_views,
    SUM(a.clicks) as ad_clicks,
    SUM(a.atbs) as ad_to_cart,
    SUM(a.orders) as ad_orders,
    SUM(a.sum) as ad_spend,
    ROUND(AVG(a.ctr), 2) as avg_ctr,
    ROUND(AVG(a.cpc), 2) as avg_cpc
FROM pbi_wb_wookiee.public.wb_adv a
JOIN pbi_wb_wookiee.public.nomenclature n ON a.nmid = n.nmid
WHERE a.date >= '2026-02-01' AND a.date < '2026-02-06'
GROUP BY n.vendorcode
ORDER BY ad_spend DESC;
```

### Воронка контента (WB)

```sql
SELECT
    vendorcode as article,
    SUM(opencardcount) as card_opens,
    SUM(addtocartcount) as add_to_cart,
    SUM(orderscount) as orders,
    SUM(buyoutscount) as buyouts,
    ROUND(AVG(addtocartpercent), 2) as avg_cr_to_cart,
    ROUND(AVG(carttoorderpercent), 2) as avg_cr_to_order
FROM pbi_wb_wookiee.public.content_analysis
WHERE date >= '2026-02-01' AND date < '2026-02-06'
GROUP BY vendorcode
ORDER BY card_opens DESC;
```

---

## 11. ДАННЫЕ О ТРАФИКЕ — ДОСТУПНОСТЬ

| Маркетплейс | Рекламный трафик | Органический трафик | Внешний трафик |
|-------------|------------------|---------------------|----------------|
| **WB** | Полные данные (`wb_adv`) | Частично (`content_analysis.opencardcount`) | Нет данных |
| **OZON** | Полные данные (`adv_stats_daily`, `ozon_adv_api`) | Данные = 0 (`search_stat`) | Нет данных |

### Сопоставление метрик трафика с БД

#### WB

| Метрика PowerBI | Таблица | Поле | Статус |
|-----------------|---------|------|--------|
| Клики, шт (всего) | — | вычисляемое: реклама + органика + внешний | Составное поле PowerBI |
| Клики реклама, шт | `wb_adv` | `clicks` | Есть |
| Клики внешний трафик, шт | — | — | **Нет данных в БД** (в PowerBI присутствует, источник неизвестен) |
| Клики органика, шт | `content_analysis` | `opencardcount` (приближённо — это "открытия карточки", не клики) | Частично |
| Показы (реклама) | `wb_adv` | `views` | Есть |
| Корзина, шт | `content_analysis` | `addtocartcount` | Есть |
| CR клик - корзина, % | `content_analysis` | `addtocartpercent` (внимание: CR от открытий карточки, не от кликов) | Частично |
| Заказы воронка, шт | `content_analysis` | `orderscount` | Есть |
| CR корзина - заказ, % | `content_analysis` | `carttoorderpercent` | Есть |
| Выкупы | `content_analysis` | `buyoutscount` | Есть |
| Показы (органика) | — | — | Нет данных |

#### OZON

| Метрика PowerBI | Таблица | Поле | Статус |
|-----------------|---------|------|--------|
| Показы, шт (всего) | — | вычисляемое: реклама + органика + внешний | Составное поле PowerBI |
| Показы реклама, шт | `adv_stats_daily` | `views` | **Только на уровне РК** (нет привязки к артикулу; в `ozon_adv_api` поле `views` отсутствует) |
| Показы внешний трафик, шт | — | — | **Нет данных в БД** (в PowerBI присутствует, источник неизвестен) |
| Показы органика, шт | `search_stat` | `hits_view` | **Данные = 0** (API не настроен) |
| Клики, шт (всего) | — | вычисляемое: реклама + органика + внешний | Составное поле PowerBI |
| Клики реклама, шт | `ozon_adv_api` | `clicks` | Есть |
| Клики внешний трафик, шт | — | — | **Нет данных в БД** |
| Клики органика, шт | `search_stat` | — | **Нет поля** (в `search_stat` есть показы `hits_view`, но поле кликов отсутствует) |
| Корзина, шт | `ozon_adv_api` | `to_cart` | Частично (только рекламная корзина; органика в `search_stat.hits_tocart` = 0) |
| CR клик - корзина, % | — | вычисляемое | Составное поле PowerBI |
| Заказы воронка, шт | `ozon_adv_api` | `orders` | Частично (только рекламные) |
| CR корзина - заказ, % | — | вычисляемое | Составное поле PowerBI |
| Заказы (реклама, агрегат) | `adv_stats_daily` | `orders_count` | Есть (на уровне РК) |

---

## 12. САМОВЫКУПЫ И ВОЗВРАТЫ

### Самовыкупы

При анализе маржи и ROI самовыкупы часто нужно исключать (искажают реальную картину).

| МП | Поле | Описание |
|----|------|----------|
| WB | `counts_sam` | Количество самовыкупов |
| WB | `comis_sam` | Комиссия по самовыкупам |
| WB | `logist_sam` | Логистика самовыкупов |
| WB | `sebes_sam` | Себестоимость самовыкупов |
| WB | `fulfilment_sam` | Фулфилмент самовыкупов |
| WB | `vnesh_logist_sam` | Внешняя логистика самовыкупов |
| WB | `upakovka_sam` | Упаковка самовыкупов |
| WB | `zercalo_sam` | Зеркало самовыкупов |
| OZON | `count_sam` | Количество самовыкупов |

### Возвраты

| МП | Поле | Описание |
|----|------|----------|
| WB | `count_return` | Количество возвратов |
| WB | `returns` | Возвраты (руб) |
| WB | `revenue_return_spp` | Выручка по возвратам (до СПП) |
| WB | `revenue_return` | Выручка по возвратам (после СПП) |
| WB | `sebes_return` | Себестоимость возвратов |
| WB | `logis_return_rub` | Логистика возвратов (руб) |
| WB | `fulfilment_returns` | Фулфилмент возвратов |
| WB | `vnesh_logist_returns` | Внешняя логистика возвратов |
| WB | `upakovka_returns` | Упаковка возвратов |
| WB | `zercalo_returns` | Зеркало возвратов |
| OZON | `count_return` | Количество возвратов |
| OZON | `return_end` | Возвраты (руб, до СПП) |
| OZON | `return_end_spp` | Возвраты (руб, после СПП) |

---

## 13. РЕКЛАМА — ВНУТРЕННЯЯ И ВНЕШНЯЯ

### Внутренняя реклама (контекстная реклама внутри маркетплейса)

| МП | Агрегат в abc_date | Детализация | Таблица |
|----|--------------------|-----------  |---------|
| WB | `reclama` | По nmid/дате/РК | `wb_adv` |
| OZON | `reclama_end` | По SKU/дате/РК | `ozon_adv_api`, `adv_stats_daily` |

### Внешняя реклама (ВК, блогеры, другие каналы)

| МП | Общая сумма | ВКонтакте | Блогеры |
|----|-------------|-----------|---------|
| WB | `reclama_vn` | `reclama_vn_vk` | `reclama_vn_creators` |
| OZON | `adv_vn` | `adv_vn_vk` | `adv_vn_creators` |

---

**Конец справочника**
