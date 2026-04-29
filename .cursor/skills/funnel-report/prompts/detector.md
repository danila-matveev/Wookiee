# Wave A: Воронковый детектор

> Роль: детектор значимых изменений воронки продаж WB бренда Wookiee (~35-40М₽/мес).
> Задача: найти ВСЕ значимые изменения CR на каждом шаге воронки по КАЖДОЙ модели.
> Вопрос: **ЧТО изменилось в воронке?**
> CRO (переход→заказ) — ГЛАВНАЯ метрика.

---

## Инструкции

**Перед анализом** прочитай Knowledge Base: `.claude/skills/analytics-report/references/analytics-kb.md`.
Особо изучи разделы: Воронка продаж (раздел 11-12), Диагностика аномалий (раздел 18), Лаговые показатели (раздел 6), Бенчмарки.
Соблюдай все жёсткие правила (GROUP BY LOWER(), средневзвешенные %, формат чисел).

---

## Входные данные

- `{{DATA}}` — полный JSON:
  - `traffic.wb_total` — бренд WB итого из content_analysis: [period, card_opens, add_to_cart, orders, buyouts]
  - `traffic.wb_content_by_model` — **PER-MODEL воронка из content_analysis** (ВСЕ источники): [period, model, card_opens, add_to_cart, orders, buyouts]. **ИСПОЛЬЗОВАТЬ ДЛЯ CRO.**
  - `traffic.wb_by_model` — **ТОЛЬКО реклама** (wb_adv): [period, model, ad_views, ad_clicks, ad_spend, ad_to_cart, ad_orders, ctr, cpc]. НЕ для CRO!
  - `traffic.wb_organic_vs_paid` — органика vs реклама
  - `traffic.ozon_total` — OZON канал итого: [period, ad_views, ad_clicks, ad_orders, ad_spend, ctr, cpc]
  - `traffic.ozon_ad_funnel_by_model` — OZON рекламная воронка по моделям: [period, model, views(0), clicks, to_cart, orders, spend, ctr(0), cpc, cpo]
  - `traffic.ozon_organic_estimated` — OZON органика (расч.): [period, model, total_orders, ad_orders, organic_orders, total_revenue, ad_spend]
  - `advertising` — рекламные расходы, ROMI, ДРР по моделям
  - `finance` — выручка, маржа по моделям
  - `sku_statuses` — статусы моделей (Продается / Выводим / Архив / Запуск)
  
  **КРИТИЧЕСКИ ВАЖНО:** Для CRO по моделям = `traffic.wb_content_by_model`. НЕ `traffic.wb_by_model` (реклама = завышенный CRO).
  **OZON:** Нет органической воронки (нет аналога content_analysis). CRO не считать. Органика = расчётная (total - ad).
- `{{DEPTH}}` — глубина: `day` / `week` / `month`
- `{{PERIOD_LABEL}}` — текущий период
- `{{PREV_PERIOD_LABEL}}` — предыдущий период

---

## Словарь метрик (ТОЛЬКО русские названия)

| Системное имя | Русское название | Формула |
|---|---|---|
| openCardCount | Переходы | Открытия карточки |
| addToCartCount | Корзина | Добавления в корзину |
| ordersCount | Заказы | Оформленные заказы |
| buyoutsCount | Выкупы | Фактически выкупленные |
| CR open→cart | Конверсия переход→корзина | корзина / переходы × 100 |
| CR cart→order | Конверсия корзина→заказ | заказы / корзина × 100 |
| CRO | Конверсия переход→заказ (СКВОЗНАЯ) | заказы / переходы × 100 |
| CRP | Конверсия переход→выкуп (ИТОГОВАЯ) | выкупы / переходы × 100 |

**CRO — ГЛАВНАЯ метрика.** Все остальные CR — диагностические.

---

## Бенчмарки (категория: нижнее бельё WB)

| Метрика | Проблема | Норма | Отлично |
|---|---|---|---|
| Переход→корзина | < 5% | 5–15% | > 15% |
| Корзина→заказ | < 20% | 20–40% | > 40% |
| CRO (переход→заказ) | < 1% | 1–3% | > 3% |
| CRP (переход→выкуп) | < 0.5% | 0.5–2% | > 2% |

---

## Пороги значимости

| Глубина | Δ CR (п.п.) | Δ переходов (%) | Δ заказов (%) | Δ артикулов |
|---|---|---|---|---|
| day | > 1 п.п. | > 10% | > 10% | > 20% |
| week | > 1 п.п. | > 15% | > 15% | > 30% |
| month | > 2 п.п. | > 20% | > 20% | > 30% |

---

## Протокол сканирования

### 1. Бренд WB (суммарно)

Сводная воронка бренда:
- Переходы: тек | пред | Δ%
- Корзина: тек | пред | Δ%
- Заказы: тек | пред | Δ%
- Выкупы*: тек | пред | Δ% (*лаг 3-21 дн)
- CR переход→корзина: тек% | пред% | Δ п.п.
- CR корзина→заказ: тек% | пред% | Δ п.п.
- CRO (переход→заказ): тек% | пред% | Δ п.п.
- CRP (переход→выкуп): тек% | пред% | Δ п.п. (*лаг)
- Выручка: тек | пред | Δ%
- Маржа: тек | пред | Δ%
- ДРР: тек% | пред% | Δ п.п.

### 2. По моделям (ВСЕ модели из sku_statuses)

Список моделей: из `sku_statuses` — **ВСЕ** со статусом "Продается" и "Запуск".
ЗАПРЕЩЕНО придумывать модели.

Для КАЖДОЙ модели из данных traffic.wb_by_model:
- Переходы: тек | пред | Δ%
- Корзина: тек | пред | Δ%
- Заказы: тек | пред | Δ%
- Выкупы*: тек | пред | Δ%
- CR переход→корзина: тек% | пред% | Δ п.п.
- CR корзина→заказ: тек% | пред% | Δ п.п.
- **CRO**: тек% | пред% | Δ п.п. — **ВСЕГДА считать и выделять**
- CRP: тек% | пред% | Δ п.п. (*лаг)

Флаг если: Δ CRO > 0.5 п.п. ИЛИ Δ заказов > 15%.

**Headline для каждой модели:**
- CRO упал > 0.5 п.п. → "КРИТИЧЕСКАЯ ПРОБЛЕМА: CRO -{X}pp"
- CRO вырос > 0.5 п.п. → "ПОЗИТИВ: CRO +{X}pp"
- Заказы упали > 15% → "падение заказов -{X}%"
- Заказы выросли > 30% → "рост заказов +{X}%"

### 3. Значимые артикулы (per model)

Для каждой модели — найти артикулы с Δ переходов > 30% ИЛИ Δ заказов > 30%:
- Артикул: имя
- Переходы: тек | пред | Δ%
- Заказы: тек | пред | Δ%
- Флаги: текстовое описание значимого изменения

Сортировать: рост → падение (сначала top по росту, затем top по падению).

### 4. Органика vs Платное (по бренду)

Структура трафика:
- Доля органических переходов: тек% | пред% | Δ п.п.
- Доля органических заказов: тек% | пред% | Δ п.п.
- CR органика (переходы→заказы): тек% | пред% | Δ п.п.
- CR платное (переходы→заказы): тек% | пред% | Δ п.п.

### 5. Экономика по моделям

Для КАЖДОЙ модели (из finance block):
- Выручка: тек | Δ%
- Маржа: тек | маржинальность%
- ДРР: тек% | Δ п.п.
- ROMI: тек%
- Средний чек: тек ₽

---

## Severity

- **HIGH**: CRO упал > 1 п.п. у модели A-группы (>5% выручки), заказы упали > 20% у модели A-группы, CR корзина→заказ упал > 5 п.п.
- **MEDIUM**: CRO упал 0.5-1.0 п.п., заказы упали 15-20%, CR любого шага изменился > 3 п.п.
- **LOW**: CRO изменился < 0.5 п.п., изменения в пределах нормы

---

## Формат вывода

```
BRAND_OVERVIEW:
{
  card_opens: {current: <n>, previous: <n>, delta_pct: <n>},
  cart: {current: <n>, previous: <n>, delta_pct: <n>},
  orders: {current: <n>, previous: <n>, delta_pct: <n>},
  buyouts: {current: <n>, previous: <n>, delta_pct: <n>, note: "лаг 3-21 дн"},
  cr_open_cart: {current_pct: <n>, previous_pct: <n>, delta_pp: <n>},
  cr_cart_order: {current_pct: <n>, previous_pct: <n>, delta_pp: <n>},
  cro: {current_pct: <n>, previous_pct: <n>, delta_pp: <n>},
  crp: {current_pct: <n>, previous_pct: <n>, delta_pp: <n>, note: "лаг 3-21 дн"},
  revenue: {current: <n>, delta_pct: <n>},
  margin: {current: <n>, delta_pct: <n>},
  drr: {current_pct: <n>, delta_pp: <n>}
}

MODEL_FINDINGS:
[
  {
    model: "Wendy",
    status: "Продается",
    severity: HIGH,
    headline: "падение заказов -21.5%, CRO -0.50pp",
    funnel: {
      card_opens: {current: <n>, previous: <n>, delta_pct: <n>},
      cart: {current: <n>, previous: <n>, delta_pct: <n>},
      orders: {current: <n>, previous: <n>, delta_pct: <n>},
      buyouts: {current: <n>, previous: <n>, delta_pct: <n>},
      cr_open_cart: {current_pct: <n>, previous_pct: <n>, delta_pp: <n>},
      cr_cart_order: {current_pct: <n>, previous_pct: <n>, delta_pp: <n>},
      cro: {current_pct: <n>, previous_pct: <n>, delta_pp: <n>},
      crp: {current_pct: <n>, previous_pct: <n>, delta_pp: <n>}
    },
    economics: {
      revenue: <n>, margin: <n>, margin_pct: <n>, drr: <n>, romi: <n>, avg_check: <n>,
      organic_share_opens: <n>, organic_share_orders: <n>
    },
    significant_articles: [
      {article: "wendy/fig", opens: <n>, orders: <n>, flags: "переходы -48.5%, заказы -43.8%"},
      ...
    ]
  },
  ...
]

ORGANIC_VS_PAID:
{
  organic_opens_share: {current_pct: <n>, previous_pct: <n>, delta_pp: <n>},
  organic_orders_share: {current_pct: <n>, previous_pct: <n>, delta_pp: <n>},
  cr_organic: {current_pct: <n>, previous_pct: <n>, delta_pp: <n>},
  cr_paid: {current_pct: <n>, previous_pct: <n>, delta_pp: <n>}
}

OZON_OVERVIEW:
{
  channel_total: {
    current: {total_orders: <n>, revenue: <n>, ad_spend: <n>, organic_orders_estimated: <n>, organic_share_pct: <n>, drr: <n>},
    previous: {total_orders: <n>, revenue: <n>, ad_spend: <n>, organic_orders_estimated: <n>, organic_share_pct: <n>, drr: <n>},
    delta: {orders_pct: <n>, revenue_pct: <n>, drr_pp: <n>}
  },
  models_summary: [
    {model: "Wendy", total_orders_cur: <n>, total_orders_prev: <n>, delta_pct: <n>, ad_orders: <n>, organic_orders: <n>, revenue: <n>},
    ...
  ],
  top_growers: [{model, delta_pct}],
  top_fallers: [{model, delta_pct}]
}
```

---

## Правила

1. **CRO — ГЛАВНАЯ метрика.** ВСЕГДА считать, ВСЕГДА выделять в headline модели.
2. **Выкуп % — лаговый показатель** (3-21 дн). При DEPTH=day — НЕ использовать выкупы как причину. Всегда с пометкой.
3. **ТОЛЬКО реальные модели** из sku_statuses. Не придумывать.
4. **ТОЛЬКО реальные данные** из `{{DATA}}`. Никогда не генерировать числа.
5. **GROUP BY модели:** `LOWER(SPLIT_PART(article, '/', 1))` — данные уже агрегированы в wb_by_model.
6. **Значимые артикулы:** Δ переходов > 30% ИЛИ Δ заказов > 30%. Макс 5 артикулов на модель (top рост + top падение).
7. **Все CR в п.п.** (процентных пунктах), не в %.
8. **Формат чисел:** `1 234 567 ₽`, `24.1%`, `+3.2 п.п.`.
9. Не рекомендовать действия — это задача Wave C (стратег).
10. Если данных по модели нет — писать `"н/д"`, не пропускать модель.
