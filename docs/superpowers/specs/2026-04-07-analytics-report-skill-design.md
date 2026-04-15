# Analytics Report Skill — Design Spec (Subproject 1: Core + Finance)

**Date:** 2026-04-07
**Status:** Draft
**Scope:** Subproject 1 of 3 (Core + Financial Analysis)

## Overview

Claude Code skill `/analytics-report` — единая точка входа для оперативного финансового анализа WB и OZON за любой период. Заменяет нерабочие скрипты Oleg v2. Работает параллельно с Oleg v2 до стабилизации, затем полная замена.

**Roadmap подпроектов:**
1. **Ядро + Финансовый анализ** ← этот спек
2. Маркетинг + Трафик (следующий спек)
3. Операционка + Рекомендации (следующий спек)

## 1. Интерфейс скилла

**Имя:** `analytics-report`
**Вызов:** `/analytics-report <start_date> [end_date]`
- 1 дата → дневной отчёт (этот день vs предыдущий)
- 2 даты → период (vs предыдущий период такой же длины)

**Примеры:**
```
/analytics-report 2026-04-05                    → день 05.04 vs 04.04
/analytics-report 2026-03-30 2026-04-05          → неделя vs 23-29.03
/analytics-report 2026-03-01 2026-03-31          → месяц vs февраль
```

**Автоматические параметры:**
- `prev_start`, `prev_end` — предыдущий период такой же длины
- `depth` — адаптивная глубина:
  - `day` (1 день): краткий отчёт
  - `week` (2-13 дней): средний
  - `month` (14+ дней): глубокий

## 2. Архитектура (Hybrid)

```
┌─────────────────────────────────────────────────┐
│ SKILL.md (оркестратор)                          │
│                                                 │
│ Stage 1: Сбор данных                            │
│   └─ collect_all.py --start X --end Y           │
│      → /tmp/analytics-report-data.json          │
│                                                 │
│ Stage 2: Анализ + Верификация                   │
│   └─ Субагент-аналитик (analyst.md)             │
│      → draft.md                                 │
│   └─ Субагент-верификатор (verifier.md)         │
│      → corrections[]                            │
│   └─ Если corrections > 0 → retry аналитика    │
│      → final.md                                 │
│                                                 │
│ Stage 3: Публикация                             │
│   └─ Сохранить MD → docs/reports/               │
│   └─ Notion (shared.notion_client)              │
│   └─ Summary в чат                              │
└─────────────────────────────────────────────────┘
```

**Почему Hybrid (а не Multi-wave или Full Parallel):**
- Коллекторы делают всю тяжёлую работу: предрассчёт долей, аномалий, изменений
- 1 аналитик с полным контекстом лучше 5 узких без общей картины
- 2 LLM-вызова вместо 5+ → быстрее (~1-2 мин), дешевле
- Проще отлаживать: данные видны в JSON

## 3. Коллекторы данных

**Файл:** `scripts/analytics_report/collect_all.py`
**CLI:** `python scripts/analytics_report/collect_all.py --start 2026-03-30 --end 2026-04-05`
**Выход:** `/tmp/analytics-report-data.json`

### 6 коллекторов (параллельно через ThreadPoolExecutor)

| # | Файл | Источник | Что собирает |
|---|------|----------|-------------|
| 1 | `collectors/finance_wb.py` | `shared.data_layer` | Выручка, маржа, комиссия, логистика, хранение, штрафы, СПП — бренд + по моделям. Предрассчёт: доли от выручки, изменения vs prev period |
| 2 | `collectors/finance_ozon.py` | `shared.data_layer` | Аналогично для OZON (72 поля abc_date) |
| 3 | `collectors/funnel.py` | `shared.data_layer` | Воронка WB: показы (opencardcount) → корзина (addtocartcount) → заказы (orderscount) → выкупы (buyoutscount). CR на каждом этапе |
| 4 | `collectors/inventory.py` | `shared.data_layer` | Остатки WB + OZON + МойСклад, оборачиваемость по моделям, ABC-классификация |
| 5 | `collectors/pricing.py` | `shared.data_layer` | Цены, изменения цен за период, история СПП, маржинальность по моделям |
| 6 | `collectors/anomalies.py` | Рассчитывается из 1-5 | Детектор аномалий: доля метрики изменилась > 3 п.п. vs prev period |

### Правила коллекторов (ОБЯЗАТЕЛЬНО)

- **GROUP BY модели:** `LOWER(SPLIT_PART(article, '/', 1))` — всегда
- **Процентные метрики:** средневзвешенные: `sum(X) / sum(Y) * 100`
- **Оба периода:** каждая метрика рассчитывается для current И previous
- **Доли:** каждая статья расходов / выручка_до_СПП * 100
- **SKU-статусы:** из Supabase через `get_artikuly_statuses()` / `get_model_statuses()`
- **Data quality:** `validate_wb_data_quality()` — автоматическая проверка retention/deduction дубликатов
- **WB маржа:** `SUM(marga) - SUM(nds) - SUM(reclama_vn) - COALESCE(SUM(reclama_vn_vk), 0) - COALESCE(SUM(reclama_vn_creators), 0)`
- **OZON маржа:** `SUM(marga) - SUM(nds)`
- **Органик vs Paid:** НЕ суммировать (несравнимые метрики)

### Адаптивность по depth

| Depth | Коллекторы | Разрезы |
|-------|-----------|---------|
| `day` | finance_wb, finance_ozon, anomalies | Бренд + модели |
| `week` | + funnel, inventory, pricing | + воронка, оборачиваемость |
| `month` | Все 6 полностью | + артикулы, ABC, ценовые изменения |

### Формат JSON

```json
{
  "meta": {
    "start": "2026-03-30",
    "end": "2026-04-05",
    "prev_start": "2026-03-23",
    "prev_end": "2026-03-29",
    "depth": "week",
    "generated_at": "2026-04-07T10:00:00",
    "errors": []
  },
  "brand": {
    "wb": {
      "current": {
        "revenue_before_spp": 5000000,
        "revenue_after_spp": 4200000,
        "spp_pct": 16.0,
        "commission": 800000, "commission_share": 16.0,
        "logistics": 400000, "logistics_share": 8.0,
        "storage": 150000, "storage_share": 3.0,
        "cogs": 1000000, "cogs_share": 20.0,
        "ads_internal": 200000, "ads_internal_share": 4.0,
        "ads_external": 50000, "ads_external_share": 1.0,
        "penalties": 10000, "penalties_share": 0.2,
        "margin": 1200000, "margin_pct": 24.0,
        "orders_count": 1500, "orders_value": 5200000,
        "sales_count": 1300, "buyout_pct": 86.7
      },
      "previous": { "...same structure..." },
      "changes": {
        "revenue_before_spp": { "abs": 300000, "pct": 6.4 },
        "margin_pct": { "abs": 1.2, "pp": 1.2 },
        "logistics_share": { "abs": -0.5, "pp": -0.5 }
      }
    },
    "ozon": { "...same structure..." },
    "total": { "...weighted aggregation..." }
  },
  "models": {
    "wendy": {
      "status": "Продается",
      "wb": { "current": {...}, "previous": {...}, "changes": {...} },
      "ozon": { "current": {...}, "previous": {...}, "changes": {...} }
    }
  },
  "funnel": {
    "wb": {
      "current": {
        "impressions": 500000,
        "card_opens": 50000, "cr_open": 10.0,
        "add_to_cart": 10000, "cr_cart": 20.0,
        "orders": 1500, "cr_order": 15.0,
        "buyouts": 1300, "cr_buyout": 86.7
      },
      "previous": {...},
      "changes": {...}
    }
  },
  "inventory": {
    "by_model": {
      "wendy": {
        "wb_stock": 500, "ozon_stock": 200, "moysklad_stock": 300,
        "total_stock": 1000, "daily_sales": 25, "turnover_days": 40,
        "recommendation": "ok"
      }
    },
    "abc": {
      "A": ["wendy", "bella"],
      "B": ["ivy", "diana"],
      "C": ["evelyn"]
    }
  },
  "pricing": {
    "changes": [
      { "model": "wendy", "channel": "wb", "old_price": 3500, "new_price": 3200, "date": "2026-04-01" }
    ],
    "spp_history": [
      { "model": "wendy", "date": "2026-04-01", "spp_pct": 15.0 }
    ]
  },
  "anomalies": [
    {
      "metric": "logistics_share",
      "channel": "wb",
      "model": null,
      "prev_share": 7.5,
      "curr_share": 11.2,
      "delta_pp": 3.7,
      "severity": "high",
      "severity_rules": "high: delta > 5 п.п. или > 100К₽; medium: delta 3-5 п.п.; low: < 3 п.п. (не включается)",
      "hypothesis": "Рост тарифов или снижение индекса локализации"
    }
  ],
  "quality": {
    "warnings": ["retention==deduction on 2026-04-02, adjustment applied: +15000₽"],
    "adjustments": { "margin_wb": 15000 }
  }
}
```

## 4. Субагенты

### 4.1 Аналитик (`prompts/analyst.md`)

**Вход:** JSON-бандл + промпт с правилами
**Выход:** MD-отчёт по шаблону
**Модель:** MAIN (gemini-3-flash) → fallback HEAVY (claude-sonnet)

**Правила в промпте аналитика (ОБЯЗАТЕЛЬНО):**
1. Выкуп % — ЛАГОВЫЙ показатель (задержка 3-21 дней). Нельзя использовать как причину изменения маржинальности. Показывать только как информационный.
2. ДРР — ВСЕГДА с разбивкой: внутренняя (МП) и внешняя (блогеры, ВК) отдельно.
3. СПП — НЕ управляемый показатель. Рост СПП → рост спроса → рост заказов. Влияет на конечную цену для покупателя.
4. Комиссия — НЕ управляемый показатель. Фиксировать, но не рекомендовать действия.
5. Инструменты управления = ЦЕНА + МАРКЕТИНГ. Все рекомендации должны быть через эти рычаги.
6. Товары "Выводим" — задача распродать быстрее, можно жертвовать маржой ради оборачиваемости.
7. Товары "Продается" — целевая маржа ≥20%, целевая оборачиваемость в диапазоне.
8. Аномалии в долях > 3 п.п. — ОБЯЗАТЕЛЬНО упомянуть с гипотезой причины.
9. Рекомендации — "что если" сценарии с расчётом эффекта в ₽.
10. Реклама → Заказы: если реклама выросла — проверить выросли ли заказы. Реклама + рост заказов = эффективно. Реклама растёт, заказы нет = неэффективно.

### 4.2 Верификатор (`prompts/verifier.md`)

**Вход:** JSON-бандл + draft.md от аналитика
**Выход:** `{ "passed": bool, "corrections": [...] }`
**Модель:** MAIN

**Проверки:**
1. Цифры в тексте соответствуют JSON (±1% допуск на округление)
2. Нет артефактов: "0%", "—", "н/д" вместо реальных данных
3. Доли расходов складываются в ~100% (±2%)
4. Все аномалии из JSON упомянуты в отчёте
5. Выводы не противоречат данным (например, "маржа выросла" при падении)
6. Формат: toggle-заголовки, таблицы, цвета — соответствует Notion-гайду

**Retry-логика:**
- Если `passed=false` → аналитик получает `corrections[]` и перегенерирует
- Максимум 1 retry. Если после retry всё ещё не passed → публикуется с пометкой "⚠️ Требует ручной проверки"

## 5. Структура отчёта (шаблон)

### Для depth=day (краткий)

```markdown
# Аналитический отчёт: {date}

## Сводка
Ключевые цифры бренда (WB+OZON): выручка, маржа, маржа%, заказы шт.
Топ-3 изменения vs вчера (по ₽ эффекту).

## Финансовая воронка (бренд)
Таблица: метрика | WB | OZON | Итого | Δ vs вчера
Выручка, Комиссия, Логистика, Хранение, Себестоимость, Реклама, Маржа
Каждая: ₽ + доля% + изменение

## По моделям
Таблица: модель | статус | выручка | маржа% | заказы | Δ
Топ-5 по выручке + все с аномалиями.

## Аномалии
Список аномалий с гипотезами.
```

### Для depth=week (средний)

Добавляются:
```markdown
## По каналам (WB / OZON отдельно)
Полная финансовая воронка для каждого канала.

## Воронка трафика
Показы → Корзина → Заказы → Выкупы, CR, изменения.
⚠️ Выкупы — лаговый показатель (3-21 дн)

## Оборачиваемость и остатки
По моделям: остатки WB+OZON+МСк, дней запаса, рекомендация.
```

### Для depth=month (глубокий)

Добавляются:
```markdown
## Детализация по артикулам
Топ-10 и анти-топ-10 по маржинальности.
ABC-классификация.

## Ценовые изменения
Все изменения цен за период, эффект на маржу.
История СПП по моделям.
```

## 6. Notion-форматирование

- Toggle-заголовки на ВСЕХ уровнях (H1-H4)
- Таблицы: `<table fit-page-width header-row header-column>`
- Цвета:
  - `green_bg` — положительные изменения (рост маржи, снижение расходов)
  - `red_bg` — отрицательные изменения
  - `yellow_bg` — предупреждения, лаговые показатели
  - `gray_bg` — итоговые строки
  - `blue_bg` — заголовки разделов
- Callout-блоки для предупреждений (⚠️ выкупы лаговые, ⚠️ data quality issues)
- Числа: `1 234 567 ₽` (пробелы-разделители), проценты: `24.1%`

## 7. Публикация

- **MD-файл:** `docs/reports/{start}_{end}_analytics.md`
- **Notion:** через `shared.notion_client.sync_report()`:
  - Database: `30158a2b-d587-8091-bfc3-000b83c6b747`
  - Тип анализа: зависит от depth (Ежедневный / Еженедельный / Ежемесячный фин анализ)
  - Источник: "Analytics Skill v1"
- **Summary в чат:** краткое резюме (3-5 строк) + ссылка на Notion

## 8. Файловая структура

```
.claude/skills/analytics-report/
├── SKILL.md                         # Оркестратор (Stage 1-3)
├── prompts/
│   ├── analyst.md                   # Промпт аналитика
│   └── verifier.md                  # Промпт верификатора
└── config.py                        # Константы (thresholds, depth rules)

scripts/analytics_report/
├── collect_all.py                   # Параллельный запуск коллекторов
├── collectors/
│   ├── finance_wb.py                # WB финансы
│   ├── finance_ozon.py              # OZON финансы
│   ├── funnel.py                    # Воронка трафика
│   ├── inventory.py                 # Остатки + оборачиваемость
│   ├── pricing.py                   # Цены + СПП
│   └── anomalies.py                 # Детектор аномалий
└── utils.py                         # Общие утилиты (date math, formatting)
```

## 9. Зависимости

- `shared/data_layer/` — 75 функций (все уже есть)
- `shared/config.py` — DB credentials из `.env`
- `shared/notion_client.py` — Notion публикация (уже есть)
- `shared/notion_blocks.py` — MD → Notion конвертер (уже есть)
- НЕТ новых pip-зависимостей

## 10. Тестирование

- **Тестовый период:** неделя 30.03-05.04.2026
- **Smoke test:** `python scripts/analytics_report/collect_all.py --start 2026-03-30 --end 2026-04-05` → проверить JSON
- **Integration test:** полный прогон скилла → проверить Notion-страницу
- **Проверка правил:** GROUP BY с LOWER(), средневзвешенные %, data quality validation

## 11. Будущие подпроекты (не в этом спеке)

**Подпроект 2: Маркетинг + Трафик**
- Внутренняя реклама (ДРР, ROI по моделям) из `shared.data_layer.advertising`
- Внешний маркетинг (блогеры, посевы, ВК) из Google Sheets
- SMM метрики из Google Sheets
- Расширение JSON-бандла новыми секциями

**Подпроект 3: Операционка + Рекомендации**
- План-факт анализ (данные из Google Sheets plan)
- Агент-рекомендатор (ценовые гипотезы, маркетинговые действия)
- Расширенный ABC с ценовыми сценариями

## 12. Внешние источники данных (справочник)

| Источник | URL | Что содержит |
|----------|-----|-------------|
| План поартикульно WB+OZON | Google Sheets `1Dsz7...` | Месячные планы по артикулам |
| Правила аналитики | Notion `wookieeshop/Wookiee-2f458...` | Бизнес-правила анализа |
| Старые отчёты | Notion `wookieeshop/30158...` | Референс формата |
| Блогеры | Google Sheets `1Y7ux...` | Данные по блогерам (лист "блогеры") |
| Посевы от Светы | Google Sheets `1Y7ux...` (лист) | Посевы |
| Внешний трафик | Google Sheets `1h0Ne...` | ВК посевы, таргет, Яндекс промо |
| SMM бренда | Google Sheets `19NXH...` | Отчёт месяц + Понедельный отчёт |

*Эти источники будут интегрированы в Подпроектах 2-3.*
