# Справочник метрик и БД Wookiee

> **Последнее обновление:** 20 февраля 2026
> **Назначение:** Единый справочник по бизнес-доменам для ИИ-агентов и аналитиков.
> **Источники:** PostgreSQL (pbi_wb_wookiee, pbi_ozon_wookiee), Excel-документация метрик, PowerBI-верификация.

---

## 0. ПОДКЛЮЧЕНИЕ И ОБЩИЕ ПРАВИЛА

### 0.1 Подключение

```
Host: ${DB_HOST}     (см. корневой .env)
Port: ${DB_PORT}     (по умолчанию 6433)
User: ${DB_USER}
Password: <см. корневой .env>
```

| База данных | Маркетплейс | Основная таблица | Период данных |
|-------------|-------------|------------------|---------------|
| `pbi_wb_wookiee` | Wildberries (53 таблицы) | `abc_date` (853K строк) | 01.01.2024 — сегодня |
| `pbi_ozon_wookiee` | OZON (33 таблицы) | `abc_date` (156K строк) | 20.01.2024 — сегодня |

### 0.2 Юридические лица (поле `lk`)

| МП | Значения |
|----|----------|
| WB | `WB ИП Медведева П.В.`, `WB ООО ВУКИ` |
| OZON | `Ozon ИП Медведева П.В.`, `Ozon ООО ВУКИ` |

### 0.3 Критические ловушки

**WB: Парадокс суффикса `_spp`** — суффикс `_spp` означает "ДО СПП" (контринтуитивно!):

| Поле | Ожидание | РЕАЛЬНОСТЬ |
|------|----------|------------|
| `revenue_spp` | После СПП | **ДО СПП** (цена продавца, полная) |
| `revenue` | До СПП | **ПОСЛЕ СПП** (цена покупателя) |
| `comis_spp` | После СПП | **ДО СПП** |
| `comis` | До СПП | **ПОСЛЕ СПП** |

**OZON: Суффикс `_end`** — означает итоговое значение (за вычетом возвратов):

| Поле | Значение |
|------|----------|
| `price_end` | Выручка ДО СПП (итоговая) |
| `price_end_spp` | Выручка ПОСЛЕ СПП |
| `comission_end` | Комиссия ДО СПП |
| `comission_end_spp` | Комиссия ПОСЛЕ СПП |

**Маржа — всегда вычитать НДС** на обоих МП. Предрассчитанное поле `marga` НЕ включает НДС.

### 0.4 Чек-лист SQL

- [ ] WB: `revenue_spp` для выручки "до СПП" (НЕ `revenue`)
- [ ] WB: маржа по формуле из 11 полей или `marga - nds`
- [ ] OZON: маржа = `marga - nds`
- [ ] GROUP BY по модели: всегда через `LOWER(SPLIT_PART(article, '/', 1))`
- [ ] Процентные метрики: только средневзвешенные
- [ ] Фильтр по `lk` при работе с конкретным кабинетом

### 0.5 Быстрый маппинг WB ↔ OZON

| Метрика | WB (abc_date) | OZON (abc_date) |
|---------|---------------|-----------------|
| Выручка (до СПП) | `revenue_spp` | `price_end` |
| Выручка (после СПП) | `revenue` | `price_end_spp` |
| Маржа | формула из 11 полей | `marga - nds` |
| Комиссия (до СПП) | `comis_spp` | `comission_end` |
| Логистика | `logist` | `logist_end` |
| Себестоимость | `sebes` | `sebes_end` |
| Реклама (внутр.) | `reclama` | `reclama_end` |
| Реклама (внеш.) | `reclama_vn` | `adv_vn` |
| Хранение | `storage` | `storage_end` |
| НДС | `nds` | `nds` |
| СПП (руб) | `spp` | `spp` |
| Продажи, шт | `full_counts` | `count_end` |
| Возвраты, шт | `count_return` | `count_return` |
| Заказы, шт | `count_orders` | из таблицы `orders` |
| Штрафы | `penalty` | — (в `service_end`) |

---

## 1. ФИНАНСОВЫЕ ПОКАЗАТЕЛИ

Основной источник: таблица `abc_date` (WB) / `abc_date` (OZON) — агрегированные метрики по дням, артикулам, баркодам.

### 1.1 Выручка и продажи

#### revenue / revenue_spp (WB)

| Параметр | Значение |
|----------|----------|
| **Русское название** | Выручка |
| **Таблица** | `abc_date` (WB) |
| **Поле до СПП** | `revenue_spp` |
| **Поле после СПП** | `revenue` |
| **Формула расчёта** | С 01.03.25: SUM(`retail_amount`) WHERE `doc_type_name` = 'Продажа'. До 01.03.25: SUM(`retail_amount`) WHERE `supplier_oper_name` IN ('Продажа', 'Корректная продажа') − SUM(`retail_amount`) WHERE `supplier_oper_name` = 'Сторно продаж' |
| **Дата группировки** | `rr_dt` (из `reportdetailbyperiod`) |
| **Источник** | `reportdetailbyperiod` |

#### price_end / price_end_spp (OZON)

| Параметр | Значение |
|----------|----------|
| **Русское название** | Продажи руб |
| **Таблица** | `abc_date` (OZON) |
| **Поле до СПП** | `price_end` |
| **Поле после СПП** | `price_end_spp` |
| **Формула расчёта** | SUM(`price` × `quantity`) из `orders` по `operation_date` из `transactions`. Связь: `orders` ↔ `transactions` по `posting_number`, `orders` ↔ `ozon_services` по `posting_number` + `product_id` |
| **Дата группировки** | `operation_date` (из `transactions`) |
| **Источник** | `orders`, `transactions`, `ozon_services` |

#### full_counts (WB) / count_end (OZON) — количество продаж

| МП | Поле | Формула |
|----|------|---------|
| WB | `full_counts` | SUM(`quantity`) WHERE `supplier_oper_name` IN ('Продажа', 'Корректная продажа', 'Коррекция продаж' при `doc_type_name`='Продажа') − SUM(`quantity`) WHERE `supplier_oper_name` IN ('Сторно продаж', 'Коррекция продаж' при `doc_type_name`='Возврат'). Текущая неделя: COUNT(*) WHERE `priceWithDisc` > 0 (из `sales`) |
| OZON | `count_end` | MAX(`quantity`) из `ozon_services` по `operation_date` из `transactions`, WHERE `accruals_for_sales` ≠ 0, `type` = 'orders' |

#### count_orders (WB) — количество заказов

| Параметр | Значение |
|----------|----------|
| **Формула** | COUNT(*) из таблицы `orders` |
| **Источник** | `orders` |

#### conversion — конверсия

| Параметр | Значение |
|----------|----------|
| **Формула WB** | (`full_counts` − `counts_sam` − `count_return`) × 100 / (`count_orders` − `counts_sam`) |

#### average_check — средний чек

| Параметр | Значение |
|----------|----------|
| **Формула** | `revenue` / `full_counts` (WB) |

#### revenue_spp / revenue_return_spp (WB) — продажи/возвраты без СПП

| Поле | Формула |
|------|---------|
| `revenue_spp` | SUM(`retail_price_withdisc_rub`) WHERE `doc_type_name` = 'Продажа'. Текущая неделя: SUM(`priceWithDisc`) WHERE > 0 (из `sales`) |
| `revenue_return_spp` | SUM(`retail_price_withdisc_rub`) WHERE `doc_type_name` = 'Возврат'. Текущая неделя: SUM(`priceWithDisc`) WHERE < 0 |

### 1.2 Возвраты

#### revenue_return / returns (WB)

| Поле | Русское | Формула |
|------|---------|---------|
| `revenue_return` | Возвраты, руб | С 01.03.25: SUM(`retail_amount`) WHERE `doc_type_name` = 'Возврат'. До 01.03.25: SUM(`retail_amount`) WHERE `supplier_oper_name` IN ('Возврат', 'Корректный возврат') − SUM WHERE 'Сторно возвратов' |
| `returns` | Возвраты, шт | Аналогичная формула по `quantity` |
| `count_return` | Кол-во возвратов | Аналогично |

#### return_end (OZON)

| Параметр | Значение |
|----------|----------|
| **Формула** | SUM(`price` из `orders` × `quantity` из `ozon_services`) по `operation_date` из `returns`. Связь: `orders` ↔ `returns` по `posting_number` |
| **count_return** | MAX(`quantity`) из `ozon_services` WHERE `accruals_for_sales` ≠ 0, `operation_type` IN ('OperationAgentStornoDeliveredToCustomer', 'ClientReturnAgentOperation'), `type` = 'returns' |

### 1.3 Маржа и прибыль

#### Маржа WB (верифицировано, расхождение <1% с PowerBI)

**11-полевая формула:**
```sql
Маржа_WB = SUM(revenue_spp) - SUM(comis_spp) - SUM(logist) - SUM(sebes)
         - SUM(reclama) - SUM(reclama_vn) - SUM(storage) - SUM(nds)
         - SUM(penalty) - SUM(retention) - SUM(deduction)
```

**Полная формула из Excel (все компоненты):**
```
marga = revenue - revenue_return - buyouts - logist - comis - sebes
      + sebes_return + sebes_sam - reclama - rashod_dop_defect - rashod_dop_loss
      + revenue_dop_defect + revenue_dop_loss - surcharges - nalog - penalty
      - over_logist - storage - inspection - retention
      - no_vozvratny_fulfil - prod_fulfil - fulfilment_returns
      - no_vozvratny_vhesh_logist - prod_vnehs_logist
      - vozvratny_upakov - prod_upakov - vozvratny_zerkalo - prod_zercalo
      + upakovka_sam + zercalo_sam + upakovka_returns + zercalo_returns
      - marketing - sebes_kompens
```

#### Маржа OZON (верифицировано, точное совпадение с PowerBI)

```sql
Маржа_OZON = SUM(marga) - SUM(nds)
```

**Полная формула из Excel:**
```
marga = price_end + return_end + service_compens + transfer_delivery
      - (comission_end + logist_end + storage_end + reclama_end + cross_end
         + bank_end + sebes_end - buyouts_ss + service_end + nalog_end
         - service_kor + buyouts_end + service_new + sebes_kompens + sebes_util)
```

#### Производные метрики

| Метрика | Формула |
|---------|---------|
| Маржинальность (%) | Маржа / Выручка_до_СПП × 100 |
| Маржа на 1 ед. (WB) | `marga` / `full_counts` |
| ДРР WB (%) | (`reclama` + `reclama_vn`) / `revenue_spp` × 100 |
| ДРР OZON (%) | (`reclama_end` + `adv_vn`) / `price_end` × 100 |
| ROMI (%) | Маржа / Реклама × 100 |
| Ср. чек заказов | Заказы_руб / Заказы_шт |
| Ср. чек продаж | Выручка_до_СПП / Продажи_шт |

#### Метрики P&L (ОПИУ)

| Метрика | Формула |
|---------|---------|
| Выручка за вычетом возвратов | Продажи_после_СПП − Самовыкупы |
| Маржинальная прибыль | Выручка_после_СПП − Себестоимость − Расходы_площадки |
| Операционная прибыль (EBITDA) | Маржинальная_прибыль − Косвенные_расходы |
| Чистая прибыль | EBITDA + Доходы_после − Расходы_после − Налоги |

### 1.4 Расходы площадки

#### comis / comis_spp (WB) — Комиссия

| Параметр | Значение |
|----------|----------|
| **Формула (с 2024-01-29)** | SUM(`retail_amount` − `ppvz_for_pay`) WHERE `doc_type_name` = 'Продажа' − SUM(...) WHERE 'Возврат' |
| **Формула (2023-05-29 — 2024-01-28)** | SUM(`ppvz_vw_nds` + `rebill_logistic_cost` + `ppvz_reward` + `acquiring_fee` + `ppvz_vw`) WHERE 'Продажа' − SUM(`ppvz_vw_nds` + `ppvz_sales_commission`) WHERE 'Возврат' |
| **Формула (до 2023-05-29)** | SUM(`ppvz_vw_nds` + `ppvz_sales_commission`) WHERE 'Продажа' − аналогично WHERE 'Возврат' |
| **Источник** | `reportdetailbyperiod` |
| **comis_spp** (без СПП) | SUM(`retail_price_withdisc_rub` − `ppvz_for_pay`) WHERE 'Продажа' − аналогично WHERE 'Возврат' |
| **comis_union** | `comis` / (`full_counts` + `returns`) |

#### comission_end (OZON)

| Параметр | Значение |
|----------|----------|
| **Формула** | SUM(`commission_amount`) из `orders` по `operation_date` из `transactions` |
| **Источник** | `orders`, `transactions`, `ozon_services` |

#### logist (WB) / logist_end (OZON) — Логистика

| МП | Формула | Источник |
|----|---------|----------|
| WB | SUM(`delivery_rub`) из `reportdetailbyperiod` | `reportdetailbyperiod` |
| OZON | SUM(`price`) из `ozon_services`, делится на кол-во артикулов в заказе | `ozon_services`, `transactions`, `returns` |

**Производные:**
- `logist_union` (WB) = `logist` / (`full_counts` − `returns`)
- `logist_union_prod` = SUM(`delivery_rub`) WHERE `delivery_amount` ≠ 0, `supplier_oper_name` IN ('Логистика', 'Логистика сторно') / COUNT(*)
- `logis_return_rub` = SUM(`delivery_rub`) WHERE `delivery_amount` = 0 (логистика по возвратам)
- `logist_union_return` = `logis_return_rub` / COUNT(возвратных записей)

#### storage (WB) / storage_end (OZON) — Хранение

| МП | Формула | Источник |
|----|---------|----------|
| WB | SUM("Стоимость хранения") за неделю × доля выручки | `accrual_report_wb` |
| OZON | Статья "Услуга размещения товаров на складе". С 01.05.2024: за день по артикулам пропорционально остаткам. До 01.05.2024: за месяц пропорционально выручке | `categore`, `stocks` |

#### penalty (WB) — Штрафы

| Параметр | Значение |
|----------|----------|
| **Формула** | SUM(`penalty`) WHERE `supplier_oper_name` = 'Штрафы' |
| **dop_penalty** | SUM("Другие виды штрафов") за неделю × доля выручки (из `accrual_report_wb`) |
| **over_logist** | SUM("Повышенная логистика согласно коэффициенту по обмерам") за неделю × доля выручки (из `accrual_report_wb`) |
| **penalty_union** | `penalty` / `full_counts` |

#### retention (WB) — Удержания

| Параметр | Значение |
|----------|----------|
| **Формула** | SUM(`deduction`) WHERE `bonus_type_name` НЕ начинается с 'Перевод на баланс заёмщика', 'Платеж по договору займа', 'Погашение задолженности', 'ПОГАШЕНИЕ ЗАДОЛЖЕННОСТИ ПО ЗАЙМУ', 'Оказание услуг «Продвижение»' и НЕ содержит 'кредит' + `cashback_amount` + `cashback_c_c` |
| **Источник** | `reportdetailbyperiod`, `reportdetailbyperiod_daily` |

#### surcharges (WB) — Доплаты

| Параметр | Значение |
|----------|----------|
| **Формула** | Если `supplier_oper_name` IN ('Доплаты', 'Корректировка'): SUM(`additional_payment`). Иначе: SUM(`additional_payment` WHERE 'Продажа') − SUM(... WHERE 'Возврат') |
| **Источник** | `reportdetailbyperiod` |

#### inspection (WB) — Приёмка

| Параметр | Значение |
|----------|----------|
| **Формула (до 28.10.24)** | SUM("Стоимость платной приемки") за неделю × доля выручки (из `accrual_report_wb`) |
| **Формула (с 28.10.24)** | SUM(`total`) из `paid_acceptance` за день × доля выручки по nmid. Если выручки по nmid нет — равномерно по баркодам |
| **Источник** | `accrual_report_wb`, `paid_acceptance` |

#### cross_end (OZON) — Кросс-докинг

| Параметр | Значение |
|----------|----------|
| **Статьи** | "Доставка товаров на склад Ozon (кросс-докинг)", "Доставка возвратов до склада продавца силами Ozon", "Кросс-докинг" |
| **Формула** | −SUM(`amount`) WHERE `operation_type_name` в указанных статьях. За месяц пропорционально доле выручки |
| **Источник** | `category` (OZON) |

#### bank_end (OZON) — Эквайринг

| Параметр | Значение |
|----------|----------|
| **Формула** | −SUM(`amount`) WHERE `operation_type_name` = 'Оплата эквайринга'. Распределяется по кол-ву артикулов в заказе. Связь: `order_number` = `posting_number` |
| **Источник** | `orders`, `category` |

#### service_end (OZON) — Услуги OZON (агрегат)

Включает ~30 статей операций (Бонусы продавца, Утилизация, Обработка излишков, Premium, и т.д.). Подробные формулы — в Excel-документации. Распределяется за месяц пропорционально доле выручки.

**Детализация по подкатегориям:**
| Поле | Статья |
|------|--------|
| `service_bonus` | Услуга продвижения Бонусы продавца |
| `service_util` | Утилизация |
| `service_izlish` | Опознанные излишки |
| `service_defect` | Обработка брака с приемки |
| `service_otziv` | Отзывы (приобретение, закрепление, баллы) |
| `service_izlish_opozn` | Неопознанные излишки |
| `service_rassilka` | Бонусы продавца — рассылка |
| `service_premium` | Premium-подписка |
| `service_viplat` | Досрочная выплата |
| `service_brand` | Продвижение бренда |
| `service_new` | Нераспределённые услуги |

### 1.5 Себестоимость

#### sebes (WB) / sebes_end (OZON)

| МП | Формула |
|----|---------|
| WB | Себестоимость по артикулу и кабинету × `full_counts`. Из [Журнала операций (Google Sheet)](https://docs.google.com/spreadsheets/d/1Dsz7s_mZ0wUhviGFho89lyhtjce1V0Cmv_RPL1aLxnk/edit?gid=1763584085#gid=1763584085) по статьям: "Оплата поставщику (товара или услуги)", "Закупка товара" |
| OZON | Себестоимость по артикулу и кабинету × (`count_end` − `count_return`). Из ЖО аналогично |

**Производные:**
| Поле | Формула |
|------|---------|
| `sebes_return` (WB) | Себестоимость единицы × кол-во возвратов |
| `sebes_sam` (WB) | Себестоимость единицы × `counts_sam` |
| `sebes_kompens` (WB) | Себестоимость единицы × SUM(`quantity`) при неосновных `supplier_oper_name` и `doc_type_name` = 'Продажа' |
| `sebes_kompens` (OZON) | Себестоимость единицы × количество из таблицы `kompens` (связь: `sku` = `ozon_product_id`) |
| `sebes_util` (OZON) | Себестоимость единицы × количество из `utilization` / `categore` WHERE 'Утилизация' |
| `buyouts_ss` (OZON) | Себестоимость × `count_sam` |

**View sebest_view** (85K строк): актуальная себестоимость по артикулам с датами изменения.

| Поле | Тип | Описание |
|------|-----|----------|
| `lk` | text | Юр. лицо |
| `article` | text | Артикул |
| `nmid/sku` | text | Номенклатурный ID / SKU |
| `barcod/product_id` | text | Баркод / Product ID |
| `ss` | double | Себестоимость (руб) |
| `date_ss` | date | Дата начала действия |
| `next_date_ss` | date | Дата следующего изменения |
| `mp` | text | Маркетплейс (WB/Ozon) |

**View sebest_all_view**: расширенная версия для всех расчётов.

### 1.6 Самовыкупы

| Поле WB | Формула |
|---------|---------|
| `counts_sam` | Кол-во WHERE "Статья операции" = Самовыкупы, МП = WB. Из ЖО + reportdetailbyperiod |
| `buyouts` | SUM("Расход") WHERE "Статья операции" = Самовыкупы, МП = WB |
| `comis_sam` | `comis` × `counts_sam` / (`full_counts` + `returns`) |
| `logist_sam` | `logist` × `counts_sam` / (`full_counts` − `returns`) |

| Поле OZON | Формула |
|-----------|---------|
| `count_sam` | Кол-во по `posting_number` из таблицы Самовыкупы Ozon + ЖО WHERE mp='Ozon' |
| `buyouts_end` | Сумма заказа, `posting_number` из таблицы Самовыкупы Ozon + ЖО |

### 1.7 Дополнительные доходы/расходы (WB)

| Поле | Русское | Формула |
|------|---------|---------|
| `revenue_dop_defect` | Доход от оплаты брака | SUM(`retail_amount`) WHERE `doc_type_name`='Продажа', `supplier_oper_name` IN ('Оплата брака', 'Частичная компенсация брака', 'Компенсация брака') |
| `rashod_dop_defect` | Расход на оплату брака | Аналогично WHERE `doc_type_name`='Возврат' |
| `revenue_dop_loss` | Доход от потерянного товара | SUM WHERE 'Оплата потерянного товара', 'Авансовая оплата за товар без движения', 'Компенсация подмененного товара' |
| `rashod_dop_loss` | Расход потерянного товара | Аналогично WHERE 'Возврат' |
| `compens_comis` | Компенсация комиссии | (`retail_amount` − `ppvz_for_pay`) WHERE 'Добровольная компенсация при возврате' или 'Компенсация ущерба' |

### 1.8 НДС и налоги

| Поле | МП | Формула |
|------|----|---------|
| `nds` | WB | (`revenue` + `revenue_dop_defect` + `revenue_dop_loss` − `revenue_return` − `rashod_dop_defect` − `rashod_dop_loss`) × ставка_НДС / (ставка_НДС + 100). По умолчанию 0% |
| `nds` | OZON | (`price_end_spp` + `return_end_spp` + `service_compens` + `transfer_delivery`) × ставка_НДС / (ставка_НДС + 100). По умолчанию 0% |
| `nalog` | WB | (выручка нетто − НДС) × 7% (УСН по умолчанию) |
| `nalog_end` | OZON | (`price_end_spp` + `return_end_spp` + `service_compens` + `transfer_delivery` − `nds`) × 7% |
| `loan` | WB | SUM(`deduction`) WHERE `bonus_type_name` начинается с 'Перевод на баланс заёмщика', 'Платеж по договору займа', 'Погашение задолженности' или содержит 'кредит' |
| `advert` | WB | SUM(`deduction`) WHERE `bonus_type_name` = 'Оказание услуг «ВБ.Продвижение»' |
| `deduction` | WB | SUM(`deduction`) WHERE `bonus_type_name` ≠ 'Оказание услуг «ВБ.Продвижение»' |

### 1.9 Фулфилмент, упаковка, зеркала (WB)

Все эти расходы распределяются пропорционально выручке за месяц. Источник — [Журнал операций (Google Sheet)](https://docs.google.com/spreadsheets/d/1Dsz7s_mZ0wUhviGFho89lyhtjce1V0Cmv_RPL1aLxnk/edit?gid=1763584085#gid=1763584085).

| Поле | Статья | Логика |
|------|--------|--------|
| `no_vozvratny_fulfil` | Фулфилмент (без артикула) | SUM("Расход") × доля выручки артикула за месяц |
| `prod_fulfil` | Фулфилмент (с артикулом) | SUM(`quantity`) × SUM("Расход") / SUM("Кол-во") для продаж |
| `fulfilment_returns` | Фулфилмент возвраты | Аналогично для возвратов |
| `fulfilment_sam` | Фулфилмент самовыкупы | Аналогично для самовыкупов |
| `no_vozvratny_vhesh_logist` | Внешняя логистика (без артикула) | SUM("Расход") × доля выручки |
| `prod_vnehs_logist` | Внешняя логистика (с артикулом) | SUM × доля количества |
| `vnesh_logist_sam` | Внеш. логистика самовыкупы | Для самовыкупов |
| `vnesh_logist_returns` | Внеш. логистика возвраты | Для возвратов |
| `vozvratny_upakov` | Упаковка (без артикула) | SUM("Расход") × доля выручки |
| `prod_upakov` | Упаковка (с артикулом) | SUM × доля количества |
| `upakovka_sam` | Упаковка самовыкупы (возврат расхода) | + к марже |
| `upakovka_returns` | Упаковка возвраты (возврат расхода) | + к марже |
| `vozvratny_zerkalo` | Зеркала (без артикула) | SUM("Расход") × доля выручки |
| `prod_zercalo` | Зеркала (с артикулом) | SUM × доля количества |
| `zercalo_sam` | Зеркала самовыкупы (возврат расхода) | + к марже |
| `zercalo_returns` | Зеркала возвраты (возврат расхода) | + к марже |
| `marketing` | Маркетинг | SUM по статье "Маркетинг" WHERE артикул/размер заполнен, МП = WB |

### 1.10 СПП (скидка маркетплейса)

| Параметр | Значение |
|----------|----------|
| **Поле WB** | `spp` |
| **Формула** | SUM(`retail_price_withdisc_rub` − `retail_amount`) WHERE `supplier_oper_name` IN ('Продажа', 'Корректная продажа', 'Сторно возвратов') − аналогично WHERE ('Возврат', 'Корректный возврат', 'Сторно продаж') |
| **СПП %** | SUM(`spp`) / SUM(`revenue_spp`) × 100 |

---

## 2. СКЛАДСКИЕ ПОКАЗАТЕЛИ

### 2.1 Остатки на складах

**Таблица stocks** (WB: 1.3M строк, OZON: аналогичная)

Обновляется ежедневно через API. Содержит:
- Текущие остатки по складам WB/OZON
- Разбивка по баркодам/артикулам
- Названия складов

**Ключевые поля:** `supplierarticle`, `warehousename`, `barcode`, `quantity`, `quantityfull`, `date`

### 2.2 Поставки и логистика

| Таблица WB | Строк | Назначение |
|------------|-------|------------|
| `postavki` | 23K | Поставки на склады WB |
| `on_way` | 9K | Товары в пути |
| `paid_storage` | 6.3M | Платное хранение (детализация по дням/баркодам) |
| `paid_acceptance` | 6K | Платная приёмка |

### 2.3 Таблицы МойСклад

| Таблица | Строк | Назначение |
|---------|-------|------------|
| `ms_product` | 556K | Товары в МойСклад |
| `ms_sklad` | 53K | Склады МойСклад |
| `ms_stocks` | 177K | Остатки на складах МойСклад |
| `ms_ss_pribylnost` | 21K | Прибыльность/себестоимость по МойСклад |

**ms_ss_pribylnost** — себестоимость операций из МойСклад:
| Поле | Тип | Описание |
|------|-----|----------|
| `operation_date` | date | Дата операции |
| `name` | text | Название товара (напр. "Angelina/black_M") |
| `article` | text | Артикул модели |
| `code` | text | Код варианта |
| `sell_cost` | numeric | Себестоимость продажи |
| `return_cost` | numeric | Себестоимость возврата |

### 2.4 Артикулы и номенклатура

| Таблица | Строк | Назначение |
|---------|-------|------------|
| `nomenclature` | 3K | Справочник товаров (WB API) |
| `nomenclature_history` | 10K | История изменений номенклатуры |
| `products` | 21K | Товары (WB) |
| `sklad_article` | 25K (WB), 33K (OZON) | Связка артикул → склад |

**sklad_article**: простая таблица из 2 полей (`supplierarticle`, `warehousename`). Содержит все уникальные комбинации артикул-склад.

### 2.5 Планирование

**plan_article** (256 строк) — планы по артикулам. Обновляется **вручную** через [таблицу управленческого учёта (Google Sheet)](https://docs.google.com/spreadsheets/d/1Dsz7s_mZ0wUhviGFho89lyhtjce1V0Cmv_RPL1aLxnk/edit?gid=1763584085#gid=1763584085). Планируется автоматизация через агента-планировщика.

| Поле | Тип | Описание |
|------|-----|----------|
| `МП` | text | Маркетплейс (WB/Ozon) |
| `ЛК` | text | Юр. лицо |
| `Артикул` | text | Модель |
| `Показатель` | text | "Кол-во заказов, шт" / "Сумма заказов, руб" / "Кол-во продаж, шт" и т.д. |
| `Дата начала` / `Дата окончания` | text | Период плана |
| `Значение` | text | Плановое значение |

---

## 3. МАРКЕТИНГОВЫЕ ПОКАЗАТЕЛИ (РЕКЛАМА)

### 3.1 Внутренняя реклама WB

#### reclama (abc_date) — агрегат рекламы

| Параметр | Значение |
|----------|----------|
| **Формула** | По умолчанию: SUM(`sum`) / (кол-во уникальных баркодов артикула). Опционально: SUM("ВБ продвижение") за неделю × доля выручки |
| **Распределение** | Равномерно по размерам (баркодам). Если у одного размера несколько баркодов — к более "новому" |
| **Источник** | `wb_adv` |

#### Таблицы рекламы WB

| Таблица | Строк | Описание |
|---------|-------|----------|
| `wb_adv` | 308K | Основная статистика: показы, клики, расход, CTR, CPC, CR |
| `wb_adv_history` | 32K | История рекламных кампаний |
| `adv_budget` | 7K | Бюджет рекламы |
| `adv_campaigns_info` | 1.7K | Информация о кампаниях |
| `sp_adv` | 1.7K | Рекламные кампании (id, тип, статус) |
| `adv_comp` | 201 | Связка advertid → name_rk (название кампании) |
| `adv_budget_everyhour` | 71K | Почасовой бюджет РК (cash, netting, total по id_rk) |
| `details_adv` | 5K | Детали рекламы |

#### Метрики рекламы

| Метрика | Формула |
|---------|---------|
| CTR (%) | `clicks` / `views` × 100 |
| CPC (руб) | `sum` / `clicks` |
| CPO (руб) | Реклама / Заказы_рекл |
| CR в корзину (%) | Корзина / Показы × 100 |
| CR в заказ (%) | Заказы / Показы × 100 |

### 3.2 Реклама OZON

#### reclama_end (abc_date OZON) — агрегат

| Параметр | Значение |
|----------|----------|
| **Формула** | SUM(`sum_rev`) WHERE `rk_category` ≠ 'Промо предложение' |
| **Источник** | `ozon_adv` |

#### Таблицы рекламы OZON

| Таблица | Строк | Описание |
|---------|-------|----------|
| `adv_stats_daily` | — | Агрегат по РК за день (views, clicks, расход, orders) |
| `ozon_adv` | 118K (OZON БД) | Расход рекламы по артикулам/дням |
| `ozon_adv_history` | — | История рекламных кампаний |
| `details_adv` | — | Детали рекламных кампаний |
| `ozon_adv_all_pvp` | 142 (OZON) | Все PVP-кампании (product_promotion) |
| `ozon_adv_sp` | 155 (OZON) | Рекламные кампании SP (id, category, name, status) |

### 3.3 Внешняя реклама

| Поле (abc_date) | Описание |
|-----------------|----------|
| `reclama_vn` (WB) | Внешняя реклама (ВК, блогеры и т.д.) |
| `adv_vn` (OZON) | Внешняя реклама OZON |

### 3.4 Реклама из финансовой отчётности

| Поле | Формула |
|------|---------|
| `reclama_fin` / `advert` (WB) | SUM(`deduction`) WHERE `bonus_type_name` = 'Оказание услуг «ВБ.Продвижение»' |

---

## 4. SEO И КОНТЕНТ-ПОКАЗАТЕЛИ

### 4.1 Воронка контента WB

**content_analysis** (61K строк) — полная воронка по nmid:

| Поле | Описание |
|------|----------|
| `opencardcount` | Открытия карточки |
| `addtocartcount` | Добавления в корзину |
| `orderscount` | Заказы |
| `orderssumrub` | Сумма заказов (руб) |
| `buyoutscount` | Выкупы |
| `buyoutssumrub` | Сумма выкупов |
| `cancelcount` | Отмены |
| `addtocartconversion` | Конверсия в корзину (%) |
| `carttoorderconversion` | Конверсия корзина→заказ (%) |
| `buyoutpercent` | Процент выкупа (%) |

### 4.2 Детальная история контента WB

**detail_history_report** (72K строк) — аналогичная воронка по nmid с историей:

| Поле | Описание |
|------|----------|
| `nmid` | Номенклатурный ID |
| `operation_date` | Дата |
| `opencardcount` | Открытия карточки |
| `addtocartcount` | Добавления в корзину |
| `orderscount` / `orderssumrub` | Заказы шт/руб |
| `buyoutscount` / `buyoutssumrub` | Выкупы шт/руб |
| `cancelcount` / `cancelsumrub` | Отмены шт/руб |
| `addtocartconversion` | Конверсия в корзину |
| `carttoorderconversion` | Корзина → заказ |
| `buyoutpercent` | % выкупа |
| `addtowishlist` | Добавления в вишлист |

### 4.3 Позиции в поиске WB

**kz_off** (719K строк) — SEO-аналитика по ключевым запросам WB:

| Поле | Описание |
|------|----------|
| `text` | ID поискового запроса |
| `nmid` | Номенклатурный ID товара |
| `subjectname` | Категория |
| `vendorcode` | Артикул поставщика |
| `weekfrequency` | Частота запроса за неделю |
| `frequency_current` | Текущая частота |
| `medianposition_current` | Медианная позиция |
| `avgposition_current` | Средняя позиция |
| `opencard_current` / `opencard_percentile` | Открытия карточки / перцентиль |
| `addtocart_current` / `addtocart_percentile` | Корзина / перцентиль |
| `orders_current` / `orders_percentile` | Заказы / перцентиль |
| `carttoorder_current` / `carttoorder_percentile` | Конверсия корзина→заказ / перцентиль |
| `opentocart_current` / `opentocart_percentile` | Конверсия открытие→корзина |
| `visibility_current` | Видимость (%) |
| `data` | Дата |

### 4.4 Аналитика поиска OZON

**search_stat** (OZON) — статистика поиска.
> **ВНИМАНИЕ:** Органические данные = 0! Таблица не заполняется корректно.

### 4.5 Ключевые слова

| Таблица | Строк | Описание |
|---------|-------|----------|
| `stat_words` | 11.6M | Статистика поисковых запросов (WB) |
| `excluded_words` | 161K | Исключённые/минус-слова (WB) |

### 4.6 Отзывы

**feedbacks_off** (WB: 34K строк) — текущие отзывы:
| Поле | Описание |
|------|----------|
| `nmid` | Номенклатурный ID |
| `text` | Текст отзыва |
| `productvaluation` | Оценка (1-5) |
| `createddate` | Дата создания |
| `answer` | Ответ продавца |

**feedbacks_old** (WB: 27.5K строк) — архив отзывов:
Аналогичная структура + `color`, `size`.

---

## 5. ЗАКАЗЫ И ВОРОНКА ПРОДАЖ

### 5.1 Заказы

**orders** (WB: 285K строк, OZON: аналогичная) — сырые заказы:

| Ключевые поля WB | Описание |
|-------------------|----------|
| `date` | Дата заказа |
| `supplierarticle` | Артикул |
| `nmid` | Номенклатурный ID |
| `barcode` | Штрихкод |
| `totalprice` | Полная цена |
| `pricewithdisc` | Цена со скидкой |
| `warehousename` | Склад |
| `oblast` / `regionname` | Регион |
| `iscancel` | Отменён ли |
| `srid` | ID сделки |

**orders_voronka** (WB: 100K строк) — воронка заказов по регионам.

### 5.2 Продажи

**sales** (WB: 250K строк) — выкупы/продажи:
Основные поля: `date`, `supplierarticle`, `nmid`, `barcode`, `totalprice`, `pricewithdisc`, `warehousename`.

### 5.3 Возвраты

**returns** (WB: 14K строк, OZON: аналогичная):
Основные поля: `date`, `supplierarticle`, `nmid`, `barcode`, `totalprice`, `warehousename`.

---

## 6. ФИНАНСОВАЯ ОТЧЁТНОСТЬ

### 6.1 Детальные отчёты

**reportdetailbyperiod** (WB: 4.8M строк) — основной источник всех финансовых расчётов:
- Содержит все операции: продажи, возвраты, логистика, штрафы
- Ключевые поля: `supplier_oper_name`, `doc_type_name`, `retail_amount`, `ppvz_for_pay`, `delivery_rub`, `penalty`, `additional_payment`, `deduction`
- Группировка: по `rr_dt` (дата), `sa_name` (артикул), `nm_id`, `barcode`

**reportdetailbyperiod_daily** (WB: 759K строк) — ежедневная версия.

**accrual_report_wb** (WB: 412 строк) — еженедельные начисления WB:

| Поле | Описание |
|------|----------|
| `lk` | Юр. лицо |
| `date_start` / `date_end` | Период недели |
| `sale` | Продажи |
| `cost_logistics` | Логистика |
| `over_logist` | Повышенная логистика |
| `penalty` / `all_penalty` | Штрафы |
| `storage` | Хранение |
| `inspection` | Приёмка |
| `retention` | Удержания |
| `total` | Итого к выплате |
| `сommission` | Комиссия |
| `advert` | Реклама |
| `subscription` | Подписка |

### 6.2 Реализация и транзакции

| Таблица | МП | Строк | Назначение |
|---------|-----|-------|------------|
| `realization` | WB | 43K | Отчёты о реализации |
| `realization` | OZON | — | Отчёты о реализации OZON |
| `transactions` | WB | 134K | Финансовые транзакции |
| `transactions` | OZON | — | Транзакции OZON (ключевая таблица для дат `operation_date`) |

### 6.3 Сервисы OZON

| Таблица | Назначение |
|---------|------------|
| `ozon_services` | Связь заказов: `posting_number`, `product_id`, `quantity`, `type` (orders/returns) |
| `category` / `categore` | Операции по статьям: `operation_type_name`, `amount`, `operation_date` |

### 6.4 Сверка

**sverka** (WB: 224 строк, OZON: аналогичная) — сверка данных БД с PowerBI:

| Поле | Описание |
|------|----------|
| `lk` | Юр. лицо |
| `date` | Период (формат "2026-4" = неделя 4 2026) |
| `rev_all` / `rev_all_a` | Выручка: БД / Агрегат |
| `delta_r` | Дельта выручки (1.00 = совпадение) |
| `com_all` / `com_all_a` / `delta_c` | Комиссия: БД / Агрегат / Дельта |
| `log_all` / `log_all_a` / `delta_l` | Логистика |
| `cat_all` / `cat_all_a` / `delta_ca` | Категории (часто расходятся!) |
| `stor_all` / `stor_all_a` / `delta_st` | Хранение |
| `marga` | Маржа |
| `pen_all` / `pen_all_a` / `delta_pen` | Штрафы |
| `sur_all` / `sur_all_a` / `delta_sur` | Доплаты |

> **Ловушка:** `delta_ca` часто ≪ 1.0 (0.18-0.19), что указывает на систематическое расхождение в категориях.

### 6.5 Финансовые продукты OZON

**finance_products_buyout** (OZON: 228 строк) — выкупы по финансовым продуктам:
| Поле | Описание |
|------|----------|
| `sku_ozon` | SKU OZON |
| `posting_number` | Номер отправления |
| `accrual` | Начисление |
| `sale_commission` | Комиссия продажи |
| `price` | Цена |
| `quantity` | Количество |
| `product_id` | ID продукта |

---

## 7. ЦЕНООБРАЗОВАНИЕ

### 7.1 Цены

| Таблица | МП | Строк | Описание |
|---------|-----|-------|----------|
| `price` | WB | 48K | Текущие/исторические цены |
| `price_wb_off` | WB | 568K | Детальная история цен WB |
| `price` | OZON | — | Цены OZON |

#### retail_price / price_rozn (abc_date WB)

| Поле | Формула |
|------|---------|
| `retail_price` | SUM(`retail_price_withdisc_rub`) / COUNT(*) WHERE `supplier_oper_name` IN ('Продажа', 'Корректная продажа', 'Сторно возвратов', 'Возврат', 'Корректный возврат', 'Сторно продаж') |
| `price_rozn` | SUM(`retail_price_withdisc_rub`) WHERE 'Продажа' − SUM WHERE 'Возврат' |

---

## 8. СПРАВОЧНИКИ И VIEWS

### 8.1 Views

| View | Строк | Назначение |
|------|-------|------------|
| `sebest_view` | 85K | Себестоимость по артикулам с датами (WB + OZON) |
| `sebest_all_view` | — | Расширенная себестоимость для всех расчётов |
| `wb_basket` | — | Корзина WB |
| `wb_claster` | — | Кластеры WB (для регионов) |
| `wb_claster_to` | — | Кластеры назначения |
| `mv_orders_calendar` | — | Материализованное представление заказов |

### 8.2 Уценка OZON

**ucenka_ozon** (OZON: 15K строк) — уценённые товары:
| Поле | Описание |
|------|----------|
| `offer_id` | Артикул |
| `is_enabled` | Активен ли |
| `discount_price` | Цена уценки |
| `original_price` | Исходная цена |
| `quantity_ozon` | Кол-во на OZON |
| `condition` | Состояние товара |

### 8.3 Служебные таблицы

**manager_dashboard_app_sourceupdatemodelbd** (WB: 16K, OZON: аналогичная) — лог обновлений таблиц:

| Поле | Описание |
|------|----------|
| `lk` | Юр. лицо |
| `bd` | База данных |
| `table_name` | Название таблицы (рус.) |
| `mp` | Маркетплейс |
| `date_update` | Начало обновления |
| `end_time` | Конец обновления |

Полезно для мониторинга актуальности данных и диагностики задержек.

---

## 9. ПОЛНЫЙ РЕЕСТР ТАБЛИЦ

### 9.1 pbi_wb_wookiee (53 таблицы)

| Таблица | Строк | Домен | Описание |
|---------|-------|-------|----------|
| `abc_date` | 853K | Финансы | Основная финансовая таблица (94 поля) |
| `abc_week` | 41K | Финансы | Финансы по неделям |
| `abc_month` | 9K | Финансы | Финансы по месяцам |
| `accrual_report_wb` | 412 | Финансы | Еженедельные начисления |
| `adv_budget` | 7K | Маркетинг | Бюджет рекламы |
| `adv_budget_everyhour` | 71K | Маркетинг | Почасовой бюджет РК |
| `adv_campaigns_info` | 1.7K | Маркетинг | Информация о РК |
| `adv_comp` | 201 | Маркетинг | Связка advertid → название РК |
| `content_analysis` | 61K | SEO/Контент | Воронка контента |
| `detail_history_report` | 72K | SEO/Контент | Детальная история контента |
| `details_adv` | 5K | Маркетинг | Детали рекламы |
| `excluded_words` | 161K | SEO | Минус-слова |
| `feedbacks_off` | 34K | SEO/Контент | Текущие отзывы |
| `feedbacks_old` | 27.5K | SEO/Контент | Архив отзывов |
| `kz_off` | 719K | SEO | SEO-аналитика по запросам |
| `manager_dashboard_app_sourceupdatemodelbd` | 16K | Служебная | Лог обновлений таблиц |
| `ms_product` | 556K | Склад | МойСклад товары |
| `ms_sklad` | 53K | Склад | МойСклад склады |
| `ms_ss_pribylnost` | 21K | Финансы/Склад | Прибыльность из МойСклад |
| `ms_stocks` | 177K | Склад | МойСклад остатки |
| `nomenclature` | 3K | Справочник | Справочник товаров |
| `nomenclature_history` | 10K | Справочник | История номенклатуры |
| `on_way` | 9K | Склад | Товары в пути |
| `orders` | 285K | Заказы | Сырые заказы |
| `orders_voronka` | 100K | Заказы | Воронка заказов по регионам |
| `paid_acceptance` | 6K | Склад | Платная приёмка |
| `paid_storage` | 6.3M | Склад | Платное хранение |
| `plan_article` | 256 | Планирование | Планы по артикулам |
| `postavki` | 23K | Склад | Поставки |
| `price` | 48K | Цены | Цены |
| `price_wb_off` | 568K | Цены | История цен |
| `products` | 21K | Справочник | Товары |
| `realization` | 43K | Финансы | Отчёты о реализации |
| `reportdetailbyperiod` | 4.8M | Финансы | Детальный отчёт (основной) |
| `reportdetailbyperiod_daily` | 759K | Финансы | Ежедневный детальный отчёт |
| `returns` | 14K | Заказы | Возвраты |
| `sales` | 250K | Заказы | Продажи |
| `sebest_all_view` | — | Финансы (view) | Расширенная себестоимость |
| `sebest_view` | 85K | Финансы (view) | Себестоимость по артикулам |
| `sklad_article` | 25K | Склад | Связка артикул-склад |
| `sp_adv` | 1.7K | Маркетинг | Рекламные кампании |
| `stat_words` | 11.6M | SEO | Статистика поисковых запросов |
| `stocks` | 1.3M | Склад | Остатки на складах |
| `sverka` | 224 | Служебная | Сверка с PowerBI |
| `transactions` | 134K | Финансы | Транзакции |
| `wb_adv` | 308K | Маркетинг | Рекламная статистика |
| `wb_adv_history` | 32K | Маркетинг | История рекламы |
| `wb_basket` | — | Справочник (view) | Корзина WB |
| `wb_claster` | — | Справочник (view) | Кластеры WB |
| `wb_claster_to` | — | Справочник (view) | Кластеры назначения |
| `mv_orders_calendar` | — | Справочник (view) | Мат. представление заказов |

### 9.2 pbi_ozon_wookiee (33 таблицы)

| Таблица | Строк | Домен | Описание |
|---------|-------|-------|----------|
| `abc_date` | 156K | Финансы | Основная финансовая таблица |
| `abc_week` | — | Финансы | Финансы по неделям |
| `abc_month` | — | Финансы | Финансы по месяцам |
| `adv_stats_daily` | — | Маркетинг | Рекламная статистика по дням |
| `category` / `categore` | — | Финансы | Операции по статьям |
| `details_adv` | — | Маркетинг | Детали рекламы |
| `feedbacks_off` | — | SEO/Контент | Отзывы |
| `finance_products_buyout` | 228 | Финансы | Выкупы фин. продуктов |
| `kompens` | — | Финансы | Компенсации |
| `manager_dashboard_app_sourceupdatemodelbd` | — | Служебная | Лог обновлений |
| `nomenclature` | — | Справочник | Номенклатура |
| `nomenclature_history` | — | Справочник | История номенклатуры |
| `on_way` | — | Склад | В пути |
| `orders` | — | Заказы | Заказы |
| `ozon_adv` | 118K | Маркетинг | Реклама по артикулам |
| `ozon_adv_all_pvp` | 142 | Маркетинг | PVP-кампании |
| `ozon_adv_history` | — | Маркетинг | История рекламы |
| `ozon_adv_sp` | 155 | Маркетинг | SP-кампании |
| `ozon_services` | — | Финансы | Сервисы (связь заказов) |
| `postings_backup` | 1K | Служебная | Бэкап отправлений |
| `price` | — | Цены | Цены |
| `products` | — | Справочник | Товары |
| `realization` | — | Финансы | Реализация |
| `returns` | — | Заказы | Возвраты |
| `search_stat` | — | SEO | Поисковая статистика (данные=0!) |
| `sebest_view` | — | Финансы (view) | Себестоимость |
| `sklad_article` | 33K | Склад | Связка артикул-склад |
| `stocks` | — | Склад | Остатки |
| `sverka` | — | Служебная | Сверка с PowerBI |
| `transactions` | — | Финансы | Транзакции |
| `ucenka_ozon` | 15K | Цены | Уценённые товары |
| `utilization` | — | Склад | Утилизация |

---

## 10. СВЯЗИ МЕЖДУ ТАБЛИЦАМИ

### 10.1 WB — ключевые связи

```
abc_date ←────── reportdetailbyperiod (по rr_dt, sa_name/article, barcode)
    │
    ├── orders (по date, supplierarticle, nmid)
    ├── sales (по date, supplierarticle, nmid)
    ├── returns (по date, supplierarticle, nmid)
    │
    ├── wb_adv (по nmid, date → reclama)
    ├── content_analysis (по nmid, date)
    ├── detail_history_report (по nmid, operation_date)
    │
    ├── accrual_report_wb (по date_start/date_end → storage, inspection, over_logist)
    ├── paid_acceptance (по shkсreatedate, nmid → inspection с 28.10.24)
    │
    ├── sebest_view (по article, lk, date_ss → sebes)
    ├── stocks (по supplierarticle, warehousename)
    └── nomenclature (по nmid → описание товара)
```

### 10.2 OZON — ключевые связи

```
abc_date ←────── transactions (по operation_date)
    │                └── orders (по posting_number)
    │                └── ozon_services (по posting_number, product_id)
    │
    ├── returns (по posting_number, operation_date)
    ├── category/categore (по operation_date → storage, cross, services)
    │
    ├── ozon_adv (по sku, date → reclama_end)
    │
    ├── sebest_view (по article, lk, date_ss → sebes_end)
    ├── stocks (по product_id)
    └── nomenclature (по sku → описание товара)
```

### 10.3 Модель из артикула

Для GROUP BY по моделям **всегда** использовать:
```sql
LOWER(SPLIT_PART(article, '/', 1)) AS model
```

---

## 11. ЭТАЛОННЫЕ SQL-ЗАПРОСЫ

### Финансовая сводка WB за период

```sql
SELECT
    LOWER(SPLIT_PART(article, '/', 1)) AS model,
    SUM(revenue_spp) AS revenue,
    SUM(revenue_spp) - SUM(comis_spp) - SUM(logist) - SUM(sebes)
      - SUM(reclama) - SUM(reclama_vn) - SUM(storage) - SUM(nds)
      - SUM(penalty) - SUM(retention) - SUM(deduction) AS margin,
    SUM(full_counts) AS sales_qty,
    CASE WHEN SUM(revenue_spp) > 0
         THEN ROUND((SUM(revenue_spp) - SUM(comis_spp) - SUM(logist) - SUM(sebes)
           - SUM(reclama) - SUM(reclama_vn) - SUM(storage) - SUM(nds)
           - SUM(penalty) - SUM(retention) - SUM(deduction))
           / SUM(revenue_spp) * 100, 1)
         ELSE 0 END AS margin_pct
FROM abc_date
WHERE date BETWEEN '2026-02-01' AND '2026-02-20'
GROUP BY LOWER(SPLIT_PART(article, '/', 1))
ORDER BY revenue DESC;
```

### Финансовая сводка OZON за период

```sql
SELECT
    LOWER(SPLIT_PART(article, '/', 1)) AS model,
    SUM(price_end) AS revenue,
    SUM(marga) - SUM(nds) AS margin,
    SUM(count_end) AS sales_qty,
    CASE WHEN SUM(price_end) > 0
         THEN ROUND((SUM(marga) - SUM(nds)) / SUM(price_end) * 100, 1)
         ELSE 0 END AS margin_pct
FROM abc_date
WHERE date BETWEEN '2026-02-01' AND '2026-02-20'
GROUP BY LOWER(SPLIT_PART(article, '/', 1))
ORDER BY revenue DESC;
```

### ДРР (доля рекламных расходов) WB

```sql
SELECT
    LOWER(SPLIT_PART(article, '/', 1)) AS model,
    SUM(reclama) + SUM(reclama_vn) AS ad_spend,
    SUM(revenue_spp) AS revenue,
    CASE WHEN SUM(revenue_spp) > 0
         THEN ROUND((SUM(reclama) + SUM(reclama_vn)) / SUM(revenue_spp) * 100, 1)
         ELSE 0 END AS drr_pct
FROM abc_date
WHERE date BETWEEN '2026-02-01' AND '2026-02-20'
GROUP BY LOWER(SPLIT_PART(article, '/', 1))
HAVING SUM(revenue_spp) > 0
ORDER BY drr_pct DESC;
```

### Воронка контента WB

```sql
SELECT
    n.vendorcode AS article,
    SUM(c.opencardcount) AS views,
    SUM(c.addtocartcount) AS to_cart,
    SUM(c.orderscount) AS orders,
    SUM(c.buyoutscount) AS buyouts,
    CASE WHEN SUM(c.opencardcount) > 0
         THEN ROUND(SUM(c.addtocartcount)::numeric / SUM(c.opencardcount) * 100, 1)
         ELSE 0 END AS cr_cart_pct,
    CASE WHEN SUM(c.orderscount) > 0
         THEN ROUND(SUM(c.buyoutscount)::numeric / SUM(c.orderscount) * 100, 1)
         ELSE 0 END AS buyout_pct
FROM content_analysis c
JOIN nomenclature n ON c.nmid = n.nmid
WHERE c.date BETWEEN '2026-02-01' AND '2026-02-20'
GROUP BY n.vendorcode
ORDER BY views DESC;
```

---

## 12. ПЛАН УЛУЧШЕНИЯ РАБОТЫ AI-АГЕНТОВ

По результатам исследования БД выявлены неиспользуемые данные и возможности для улучшения работы агентов.

### 12.1 Новые инструменты для агента Олег

Олег сейчас имеет 21 инструмент (12 финансовых + 9 ценовых). Предлагаемые дополнения:

| # | Новый инструмент | Источник данных | Ценность |
|---|------------------|-----------------|----------|
| 1 | **get_seo_positions** | `kz_off` (719K строк) | SEO-аналитика: позиции по запросам, частоты, конверсии, перцентили видимости. Позволит отслеживать влияние рекламы на органическую выдачу |
| 2 | **get_content_funnel** | `detail_history_report` (72K строк) | Расширенная воронка контента (дополняет content_analysis): opencardcount → addtocart → orders → buyouts + wishlist + cancel. Возможность анализа по дням |
| 3 | **get_plan_fact** | `plan_article` (256 строк, ручное обновление через Google Sheet) | План-факт анализ: сравнение плановых показателей с фактом. Данные обновляются вручную. Планируется агент-планировщик |
| 4 | **get_reviews_analysis** | `feedbacks_old` (27.5K), `feedbacks_off` (34K) | Аналитика отзывов: средняя оценка, динамика, ключевые слова из текстов |
| 5 | **get_data_freshness** | `manager_dashboard_app_sourceupdatemodelbd` (16K) | Проверка актуальности данных: какие таблицы когда обновлялись |
| 6 | **get_sverka_check** | `sverka` (224 строк) | Автоматическая сверка с PowerBI: дельты по выручке, комиссии, логистике, хранению |
| 7 | **get_ucenka_analysis** | `ucenka_ozon` (15K строк) | Анализ уценённых товаров OZON: количество, скидки, потенциальная выручка |

### 12.2 Валидация формул data_layer.py

Рекомендуется сверить формулы в `shared/data_layer.py` с каноническими формулами из Excel:

| Формула | Риск расхождения |
|---------|------------------|
| WB Маржа | Высокий — Excel содержит 30+ компонентов, data_layer использует 11-полевую формулу |
| WB Комиссия | Средний — формула менялась 3 раза (до 2023-05-29, до 2024-01-29, после) |
| WB Удержания | Средний — сложная логика исключений по bonus_type_name |
| OZON service_end | Высокий — 30+ статей операций, некоторые распределяются по выручке, другие по артикулам |
| Все _sam / _return метрики | Низкий — простые формулы (себестоимость × кол-во) |

### 12.3 metric_registry.json — runtime-доступ к формулам

Предлагается создать JSON-реестр метрик для runtime-использования агентами:

```json
{
  "wb_margin": {
    "name_ru": "Маржа WB",
    "formula": "revenue_spp - comis_spp - logist - sebes - reclama - reclama_vn - storage - nds - penalty - retention - deduction",
    "verified": true,
    "verified_date": "2026-02-07",
    "divergence_pbi": "<1%"
  },
  "ozon_margin": {
    "name_ru": "Маржа OZON",
    "formula": "marga - nds",
    "verified": true,
    "verified_date": "2026-02-07",
    "divergence_pbi": "0%"
  }
}
```

Агент сможет вызывать `lookup_metric("wb_margin")` для проверки формулы перед анализом.

### 12.4 Приоритеты реализации

| Приоритет | Задача | Трудоёмкость | Эффект |
|-----------|--------|-------------|--------|
| P0 | Валидация формул data_layer.py vs Excel | Средняя | Устранение потенциальных ошибок |
| P1 | get_seo_positions (kz_off) | Низкая | Новый домен аналитики для Олега |
| P1 | get_plan_fact (plan_article) | Низкая | Стратегическая аналитика |
| P2 | get_content_funnel (detail_history_report) | Низкая | Дополнение к content_analysis |
| P2 | get_data_freshness | Низкая | Диагностика качества данных |
| P2 | get_reviews_analysis | Средняя | NLP-анализ отзывов |
| P3 | metric_registry.json + lookup_metric | Средняя | Самопроверка формул агентом |
| P3 | get_ucenka_analysis | Низкая | OZON-специфичная аналитика |

---

## 13. ПОЛНЫЙ СПРАВОЧНИК ИСТОЧНИКОВ ДАННЫХ

Единый реестр всех доступных источников данных — от API маркетплейсов до внутренних БД и внешних сервисов.

### 13.0 Архитектура данных

```
Внешние API                    Хранилища                   Интерфейсы
─────────────                  ─────────                   ──────────
WB API (5 доменов)     ──►  PostgreSQL PBI (read-only)  ──►  Telegram Bot (Олег)
OZON API               ──►  PostgreSQL ETL (managed)    ──►  Telegram Bot (Людмила)
МойСклад API           ──►  Supabase (товарная матрица) ──►  Notion (отчёты)
Google Sheets (ЖО)     ──►  Google Sheets (sync)        ──►  Bitrix24 (задачи)
Bitrix24 CRM           ──►  SQLite (кэш/память)
OpenRouter (LLM)
```

### 13.1 Wildberries API

**Аутентификация:** Bearer Token в заголовке `Authorization`

| Кабинет | Env-переменная |
|---------|----------------|
| ИП Медведева П.В. | `WB_API_KEY_IP` |
| ООО ВУКИ | `WB_API_KEY_OOO` |

**Base URLs:**

| Домен | Назначение |
|-------|------------|
| `https://seller-analytics-api.wildberries.ru` | Аналитика, склад |
| `https://statistics-api.wildberries.ru` | Продажи, заказы, остатки, поставки, отчёт реализации |
| `https://discounts-prices-api.wildberries.ru` | Цены и скидки |
| `https://feedbacks-api.wildberries.ru` | Отзывы |
| `https://dp-calendar-api.wildberries.ru` | Промоакции |
| `https://content-api.wildberries.ru` | Карточки товаров |
| `https://advert-api.wildberries.ru` | Реклама |

**Эндпоинты:**

| Эндпоинт | Метод | Назначение | → Таблица БД | Пагинация |
|----------|-------|------------|--------------|-----------|
| `/api/v1/supplier/reportDetailByPeriod` | GET | Основной финансовый отчёт | `reportdetailbyperiod` → `abc_date` | rrdid (100K/стр) |
| `/api/v1/supplier/sales` | GET | Продажи | `sales` | flag (0=все, 1=обновлённые) |
| `/api/v1/supplier/orders` | GET | Заказы | `orders` | flag |
| `/api/v1/supplier/stocks` | GET | Остатки на складах | `stocks` | по дате |
| `/api/v1/supplier/incomes` | GET | Поставки | `postavki` | по дате |
| `/api/v1/warehouse_remains` | GET | Остатки на складах (расширенный) | `stocks` | async: task_id polling |
| `/api/v2/list/goods/filter` | GET | Цены товаров | `price` | offset/limit (1000/стр) |
| `/content/v2/get/cards/list` | POST | Карточки товаров | `nomenclature` | cursor |
| `/api/v2/nm-report/detail` | POST | Аналитика карточек (воронка) | `content_analysis` | page |
| `/api/v2/fullstats` | POST | Статистика рекламы | `wb_adv` | batch (100 РК макс) |
| `/api/v1/feedbacks` | GET | Отзывы | `feedbacks_off` | skip (5000/стр) |
| `/api/v1/calendar/promotions` | GET | Промоакции | — | — |
| `/api/v1/calendar/promotions/details` | GET | Детали промоакции | — | promotion_id |
| `/api/v1/calendar/promotions/nomenclatures` | POST | Товары в промоакции | — | promotion_id |

**Rate Limits:**
- По умолчанию: 60 req/min (1 req/sec)
- Sales/Orders: 5 req/min (12 sec между запросами)
- При 429: пауза 60 сек + retry

**Клиенты в коде:**
- Legacy: `shared/clients/wb_client.py`
- ETL: `services/marketplace_etl/api_clients/wb_client.py`

### 13.2 OZON Seller API

**Base URL:** `https://api-seller.ozon.ru`

**Аутентификация:** два заголовка `Client-Id` + `Api-Key`

| Кабинет | Client-Id | Api-Key |
|---------|-----------|---------|
| ИП Медведева П.В. | `OZON_CLIENT_ID_IP` | `OZON_API_KEY_IP` |
| ООО ВУКИ | `OZON_CLIENT_ID_OOO` | `OZON_API_KEY_OOO` |

**Эндпоинты:**

| Эндпоинт | Метод | Назначение | → Таблица БД | Пагинация |
|----------|-------|------------|--------------|-----------|
| `/v3/finance/transaction/list` | POST | Финансовые транзакции | `transactions` → `abc_date` | page (1000/стр) |
| `/v2/posting/fbo/list` | POST | FBO-заказы | `orders` | offset |
| `/v2/posting/fbs/list` | POST | FBS-заказы | `orders` | offset |
| `/v1/analytics/data` | POST | Аналитика (выручка, заказы, возвраты) | `abc_date` | offset |
| `/v2/product/info/list` | POST | Информация о товарах | `nomenclature` | по ID |
| `/v2/product/list` | POST | Каталог товаров | `nomenclature` | last_id cursor |
| `/v1/product/info/stocks` | POST | Остатки на складах | `stocks` | offset |
| `/v1/actions` | POST | Промоакции | — | — |
| `/v1/actions/candidates` | POST | Товары для промо | — | offset/limit |
| `/v1/actions/products` | POST | Товары в промоакции | — | offset/limit |
| `/v1/performance/campaigns` | POST | Рекламные кампании | `ozon_adv` | — |
| `/v1/performance/statistics/campaign/daily` | POST | Статистика РК по дням | `ozon_adv` | campaign_id |
| `/v1/client/statistics` | POST | Поисковая статистика | `search_stat` (=0!) | — |
| `/v1/report/products/create` | POST | Создание отчёта остатки/цены | — | async: report_code polling |
| `/v1/report/info` | POST | Статус отчёта + URL скачивания | — | report_code |
| `/v1/warehouse/list` | POST | Тест подключения | — | — |

**Rate Limits:**
- По умолчанию: 20 req/sec
- Finance API: 1-2 req/sec
- При 429: retry с backoff

**Особенности:**
- Async report pattern: POST create → poll status → download CSV
- CSV: разделитель `;`, UTF-8 BOM, апостроф-префикс ('100 → 100)

**Клиенты в коде:**
- Legacy: `shared/clients/ozon_client.py`
- ETL: `services/marketplace_etl/api_clients/ozon_client.py`

### 13.3 МойСклад API

**Base URL:** `https://api.moysklad.ru/api/remap/1.2`

**Аутентификация:** Bearer Token (`MOYSKLAD_TOKEN`)

**Эндпоинты:**

| Эндпоинт | Назначение | Пагинация |
|----------|------------|-----------|
| `/entity/assortment` | Каталог товаров (32 атрибута на товар) | limit=500 |
| `/report/stock/bystore` | Остатки по складам | limit=1000 |
| `/report/stock/all` | Остатки для себестоимости | limit=1000 |
| `/entity/purchaseorder` | Заказы поставщикам | limit=100 |
| `/entity/purchaseorder/{id}/positions` | Позиции заказа | limit=1000 |

**32 атрибута товара:** Артикул Ozon, Баркод, Модель, Цвет, SKU, Цена, Статусы WB/OZON, EAN13, GTIN и др.

**Hardcoded склады:**
- Основной: `4c51ead2-2731-11ef-0a80-07b100450c6a`
- Приёмка: `6281f079-8ae2-11ef-0a80-148c00124916`

**Rate Limits:** 0.3-0.5 сек между запросами, макс 20 страниц пагинации

**→ Выгрузка:** Google Sheet "МойСклад_АПИ"

**Клиент:** `shared/clients/moysklad_client.py`

### 13.4 Supabase — товарная матрица (SKU Database)

**Подключение:**
```
Host: aws-0-xx-xxx-x.pooler.supabase.com
Port: 5432
Database: postgres
User: postgres.xxxxx (service role)
Password: <из sku_database/.env>
```

**Иерархия таблиц:**
```
modeli_osnova (22 модели: Vuki, Moon, Ruby...)
  └─ modeli (40 вариаций)
       └─ artikuly (478 артикулов)
            └─ tovary (1450 SKU)
  └─ cveta (137 цветов со статусами)
statusy (7 статусов)
```

**Безопасность (RLS):**
- `anon` → заблокирован (0 прав)
- `authenticated` → только SELECT
- `postgres` → полный доступ (service_role для Python)

**Кто использует:**
- Олег — статусы артикулов (`get_product_statuses`)
- Людмила — долгосрочная память пользователей
- ABC-анализ, отчёты

**REST API:** `https://<project>.supabase.co/rest/v1/`

**Документация:** `sku_database/README.md`

### 13.5 Google Sheets

**Аутентификация:** Service Account (файл: `services/sheets_sync/credentials/google_sa.json`)

**Основной SPREADSHEET_ID — синхронизируемые листы:**

| Лист | Источник данных | Назначение |
|------|-----------------|------------|
| `WB_Stocks` | WB API (warehouse_remains, prices) | Остатки и цены WB |
| `WB_Prices` | WB API (prices) | Цены WB |
| `WB_Bundles` | WB API | Комплекты WB |
| `WB_Feedbacks` | WB API (feedbacks) | Отзывы WB |
| `OZON_Stocks_Prices` | OZON API (report) | Остатки и цены OZON |
| `OZON_Bundles` | OZON API | Комплекты OZON |
| `Финансовые_Данные` | PostgreSQL | Финансовая сводка |
| `Поиск_Аналитика` | — | Поисковая аналитика |
| `МойСклад_АПИ` | МойСклад API | Каталог из МойСклад |

**Отдельные листы:**
- `VASILY_SPREADSHEET_ID` — Василий: логистика, локализация (11 листов)
- [Журнал операций (ЖО)](https://docs.google.com/spreadsheets/d/1Dsz7s_mZ0wUhviGFho89lyhtjce1V0Cmv_RPL1aLxnk/edit?gid=1763584085#gid=1763584085) — себестоимость, фулфилмент, упаковка, зеркала. Доступ через серверный email

**Клиент:** `shared/clients/sheets_client.py` (gspread)

### 13.6 Bitrix24 CRM

**Аутентификация:** OAuth 2.0 + Webhook

| Параметр | Env-переменная |
|----------|----------------|
| Портал | `BITRIX_PORTAL_DOMAIN` (wookiee.bitrix24.ru) |
| Client ID | `BITRIX_CLIENT_ID` |
| Client Secret | `BITRIX_CLIENT_SECRET` |
| Webhook | `Bitrix_rest_api` |

**Кто использует:**
- **Людмила** — задачи, встречи, контакты, дайджесты
- **Василий** — уведомления в чат "Wookiee Склад МСК"

**Операции:** создание/обновление задач, встречи, контакты, дайджесты

**Rate Limits:** 2 req/sec

**Клиент:** `shared/clients/bitrix_oauth.py`

### 13.7 Notion API

**Base URL:** `https://api.notion.com/v1` (версия `2022-06-28`)

| Параметр | Env-переменная |
|----------|----------------|
| Token | `NOTION_TOKEN` |
| Database ID | `NOTION_DATABASE_ID` |

**Кто использует:** Олег — синхронизация отчётов

**Операции:** создание страниц, обновление, запрос БД, удаление/добавление блоков

**Клиент:** `agents/oleg/services/notion_service.py`

### 13.8 OpenRouter (LLM-провайдер)

**Base URL:** `https://openrouter.ai/api/v1` (OpenAI-совместимый SDK)

| Тир | Модель | Стоимость (in/out за 1M) | Назначение |
|-----|--------|--------------------------|------------|
| LIGHT | `z-ai/glm-4.7-flash` | $0.07 / $0.30 | Классификация, определение намерений |
| MAIN | `z-ai/glm-4.7` | $0.06 / $0.40 | Аналитика, tool-use, отчёты |
| HEAVY | `google/gemini-3-flash-preview` | $0.50 / $3.00 | Сложные рассуждения, fallback |
| FREE | `openrouter/free` | $0 / $0 | Последний fallback |

**Env:** `OPENROUTER_API_KEY`

**Клиент:** `shared/clients/openrouter_client.py`

### 13.9 PostgreSQL — финансовые БД (PBI)

Основные базы данных с финансовыми метриками. Заполняются внешним подрядчиком, **read-only**.

| Параметр | Значение |
|----------|----------|
| Host | `DB_HOST` (из .env) |
| Port | `6433` (нестандартный!) |
| User | `DB_USER` |
| Password | `DB_PASSWORD` |

| БД | МП | Таблиц | Основная таблица |
|----|-----|--------|------------------|
| `pbi_wb_wookiee` | Wildberries | 43 (после очистки) | `abc_date` (853K строк) |
| `pbi_ozon_wookiee` | OZON | 33 | `abc_date` (156K строк) |

Подробное описание таблиц и метрик — секции 1-11 данного документа.

**Клиент:** `shared/data_layer.py` (~78KB, ~30 SQL-функций)

### 13.10 PostgreSQL — Marketplace ETL (Ibrahim)

Managed-БД, заполняемая ETL-пайплайном Ибрагима (WB/OZON API → обработка → БД).

| Параметр | Env-переменная |
|----------|----------------|
| Host | `MARKETPLACE_DB_HOST` |
| Port | `5432` |
| Database | `MARKETPLACE_DB_NAME` (wookiee_marketplace) |
| User | `MARKETPLACE_DB_USER` |
| Password | `MARKETPLACE_DB_PASSWORD` |

**Переключение источника:** `DATA_SOURCE=legacy|managed`
- `legacy` → PBI-базы (read-only, подрядчик)
- `managed` → Marketplace ETL (собственный пайплайн)

**Расписание ETL:** ежедневно 05:00 МСК, еженедельный анализ воскресенье 03:00

**Клиент:** `services/marketplace_etl/`

### 13.11 Двойные кабинеты (ИП + ООО)

Все API маркетплейсов работают с двумя юридическими лицами:

| МП | ИП Медведева П.В. | ООО ВУКИ |
|----|-------------------|----------|
| WB | `WB_API_KEY_IP` | `WB_API_KEY_OOO` |
| OZON | `OZON_CLIENT_ID_IP` + `OZON_API_KEY_IP` | `OZON_CLIENT_ID_OOO` + `OZON_API_KEY_OOO` |

В БД различаются через поле `lk`:
- WB: `WB ИП Медведева П.В.`, `WB ООО ВУКИ`
- OZON: `Ozon ИП Медведева П.В.`, `Ozon ООО ВУКИ`

### 13.12 Какой агент что использует

| Агент | PostgreSQL PBI | Supabase | WB/OZON API | МойСклад | Google Sheets | Bitrix24 | Notion | OpenRouter |
|-------|---------------|----------|-------------|----------|---------------|----------|--------|------------|
| **Олег** (финансовый) | да (основной) | да (статусы) | — | — | — | — | да (отчёты) | да |
| **Людмила** (CRM) | — | да (память) | — | — | — | да (задачи) | — | да |
| **Ибрагим** (ETL) | да (сверка) | — | да (ETL) | да | — | — | — | да (анализ) |
| **Василий** (логистика) | — | — | да (остатки) | — | да (отчёты) | да (уведомления) | — | — |
