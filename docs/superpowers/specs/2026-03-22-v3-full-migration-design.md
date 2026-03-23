# Дизайн: Полная миграция V2 → V3 с переносом качества отчётов

**Дата:** 2026-03-22
**Статус:** Draft
**Приоритет:** Высокий
**Цель:** V3 — единственная система. V2 удаляется. Качество отчётов V3 >= V2.

---

## Контекст

V3 (`agents/v3/`) уже работает в продакшене (контейнер `wookiee-oleg` запускает `python -m agents.v3`). Но:
- Отчёты V3 значительно беднее V2 по глубине и детализации
- Telegram-бот V3 — заглушка (только `/start`, `/ping`)
- Watchdog содержит баги, спамит ошибками в ТГ
- Notion dedup сломан — появляются дубли отчётов
- V2 Oleg живёт как MCP-сервер (`oleg-mcp`) и через CLI-скиллы, создавая параллельные отчёты

## Ключевое открытие аудита

**Инструменты НЕ потеряны.** V3 имеет ВСЕ 58 tools из V2 + 16 новых (KB + prompt-tuner). Проблема НЕ в данных, а в:
1. Промпты micro-agents менее требовательны к глубине output
2. Report-compiler не получает полных данных от agents
3. Баги в инфраструктуре (watchdog, dedup, bot handlers)

---

## Архитектура решения

### Подход: усилить V3 промпты до уровня V2

Сохраняем архитектуру V3 (параллельные micro-agents → compiler, Trust Envelope, KB), но каждый agent получает **точные требования к output** из V2 Reporter.

### Что НЕ меняется
- Orchestrator pipeline (`_run_report_pipeline`)
- Delivery router (Notion + Telegram)
- Trust Envelope и `_meta` блок
- Tool registry (все tools уже на месте)
- Scheduler / cron jobs

### Что меняется
- Промпты 5 micro-agents (margin-analyst, revenue-decomposer, ad-efficiency, funnel-digitizer, campaign-optimizer)
- Report-compiler промпт (уточнение требований к секциям) — расширение условной логики вместо отдельных файлов
- Watchdog bugs (2 fix — DB check никогда не работал в продакшене)
- Telegram bot handlers (port из V2)
- Notion dedup logic
- Orchestrator: graceful degradation при timeout агентов + compiler routing по task_type
- AGENT_TIMEOUT: увеличить с 120s до 180s для financial agents

---

## Фаза 1: Починка инфраструктуры

Цель: остановить спам ошибок, починить dedup, добавить Telegram-команды.

### 1.1 Fix watchdog DB check

**Файл:** `agents/v3/monitor.py` (строки 60-74)

**Баг (двойной):**
1. `_db_cursor(_get_wb_connection())` передаёт connection object вместо callable. `_db_cursor` ожидает `conn_factory: Callable`.
2. `as cur:` не распаковывает tuple — `_db_cursor` yields `(conn, cur)`, а код пытается вызвать `.execute()` на tuple.

**Результат:** DB health check **никогда не работал** в продакшене. Исключение ловится в `except`, возвращается `False`, watchdog спамит false-positive "DB down" алерты.

**Fix:**
```python
# Было:
with _db_cursor(_get_wb_connection()) as cur:
    cur.execute("SELECT 1")

# Стало:
with _db_cursor(_get_wb_connection) as (conn, cur):
    cur.execute("SELECT 1")
```

### 1.2 Fix watchdog last_run check

**Файл:** `agents/v3/monitor.py` (строки 77-104)

**Баг:** Queries `orchestrator_runs` таблицу в Supabase. Таблица может не существовать (нет CREATE TABLE, только fire-and-forget inserts).

**Fix:**
- Обернуть в `try/except` с fallback на `True` если таблица не найдена
- Добавить `CREATE TABLE IF NOT EXISTS` в `services/observability/logger.py`
- Или: переключить check на StateStore (`delivered:*` keys) вместо Supabase

### 1.3 Port Telegram bot handlers

**Файл:** `agents/v3/app.py` (строки 148-166)

**Из V2 (`agents/oleg/bot/telegram_bot.py`)** портировать:

| Команда | Что делает | V3 метод |
|---------|-----------|----------|
| `/report_daily` | Запуск daily report on demand | `orchestrator.run_daily_report()` |
| `/report_weekly` | Запуск weekly report | `orchestrator.run_weekly_report()` |
| `/report_monthly` | Запуск monthly report | `orchestrator.run_monthly_report()` |
| `/marketing_daily` | Marketing daily | `orchestrator.run_marketing_report("daily")` |
| `/marketing_weekly` | Marketing weekly | `orchestrator.run_marketing_report("weekly")` |
| `/marketing_monthly` | Marketing monthly | `orchestrator.run_marketing_report("monthly")` |
| `/health` | Health check | `monitor.get_watchdog().heartbeat()` |
| `/feedback <text>` | Сохранить feedback → PromptTuner | `prompt_tuner.save_instruction()` |
| Free text | Generic query → data-navigator agent | Новый handler через runner |

**Примечание:** `/marketing_daily` — только on-demand (нет scheduled job). V2 тоже не имел cron для daily marketing.

**Реализация:** каждый handler вызывает orchestrator метод → `_deliver()` → Telegram + Notion. Аналогичная логика V2 `_handle_report_daily()`.

### 1.4 Fix Notion deduplication

**Файл:** `agents/v3/delivery/notion.py`

**Два уровня dedup:**
1. **Scheduler-level** (`scheduler.py`): `state.is_delivered("daily_report", date)` — SQLite, TTL 48h. Предотвращает повторный запуск pipeline. Не связан с Notion.
2. **Notion-level** (`notion.py`): `_find_existing_page(start_date, end_date, report_type)` — API query по дате + типу. Upsert.

**Корневая причина дублей:** V2 CLI и V3 auto создают отчёты параллельно. Это разные pipelines с разными `source` ("CLI (manual)" vs "Oleg v3 (auto)"), Notion-level dedup не учитывает source — ищет по дате + тип. Но если `report_type` label не совпадает — создаётся новая страница.

**Дополнительные проблемы:**
- `price_analysis` отсутствует в `_REPORT_TYPE_MAP` — fallback на raw string
- Scheduler TTL 48h: после истечения pipeline запустится повторно при catchup
- Race condition при concurrent reports

**Fix:**
- **Главное:** Остановить V2 CLI пути (задача 1.5) — убирает основной источник дублей
- Добавить `price_analysis` и другие недостающие ключи в `_REPORT_TYPE_MAP`
- Увеличить TTL в StateStore до 30 дней (или убрать)
- Добавить `asyncio.Lock()` per report_type в delivery router
- Сохранять Notion page_id в StateStore после создания

### 1.5 Остановить V2 CLI дубликаты

**Действие:** Удалить/отключить CLI-скиллы и команды, которые запускают V2 pipeline:
- `.claude/skills/` или `.claude/commands/` с daily-report, weekly-report через V2
- `scripts/` которые вызывают `agents.oleg` напрямую

---

## Фаза 2: Усиление промптов micro-agents

Цель: V3 agents возвращают данные с той же глубиной, что V2 Reporter.

### Принцип переноса

V2 Reporter — один монолитный agent с промптом на 10 обязательных секций.
V3 — 3+ параллельных agents. Каждый agent отвечает за СВОИ секции.

**Матрица ответственности:**

| V2 секция | V3 agent | Что нужно в output JSON |
|-----------|----------|------------------------|
| 0. Паспорт | report-compiler | Собирает из `_meta` всех agents |
| 1. Топ-выводы | report-compiler | Собирает из `_meta.conclusions` |
| 2. План-факт | revenue-decomposer | `plan_fact[]` — ОБЯЗАТЕЛЕН если план есть |
| 3. Ключевые изменения (19 строк) | revenue-decomposer (поля 1-15) + ad-efficiency (поля 16-19) | `brand_metrics{}` — compiler мержит; при конфликте приоритет ad-efficiency для воронковых метрик |
| 4. Ценовая стратегия / СПП | margin-analyst | `spp_dynamics[]` + `price_forecast[]` |
| 5. Каскад маржи (10 строк) | margin-analyst | `margin_waterfall[]` — 10 статей с ₽ влиянием |
| 6.1 WB объём + модели | revenue-decomposer | `models[]` — ВСЕ модели с FBO, оборачиваемость, ROI |
| 6.1.3 Воронка WB | ad-efficiency | `funnel[]` — impressions→clicks→cart→orders + conversion % |
| 6.1.4 Структура затрат | margin-analyst | `cost_structure[]` — доли от выручки |
| 6.1.5 Реклама WB | ad-efficiency | `ad_stats{}` — Показы, Клики, CTR, CPC, CPM, CPO, Расход |
| 6.2 OZON | те же agents | Аналогично WB |
| 7. Драйверы/антидрайверы | all 3 agents | `top_drivers[]`, `top_anti_drivers[]` с ₽ impact |
| 8. Гипотезы → Действия | report-compiler | Собирает из `_meta.conclusions` |
| 9. Рекомендации Advisor | report-compiler | Из `_meta.conclusions` type=recommendation |
| 10. Сводка | report-compiler | Синтез |

### 2.1 Усиление margin-analyst.md

**Текущее состояние:** возвращает `levers[]` (5 рычагов), `nevyazka`, summary.
**Нужно добавить:**

```markdown
## ОБЯЗАТЕЛЬНЫЕ ПОЛЯ OUTPUT

### margin_waterfall (Каскад маржи — 10 строк)
Вызови `get_margin_levers` для КАЖДОГО канала (WB, OZON).
Верни массив из 10 объектов:
| Поле | Описание |
|------|----------|
| factor | Название: Выручка, Себестоимость/ед, Комиссия до СПП, Логистика/ед, Хранение/ед, Внутр. реклама, Внешн. реклама, Прочие расходы, НДС, Невязка |
| current_rub | Значение текущий период |
| previous_rub | Значение прошлый период |
| delta_rub | Изменение в ₽ |
| margin_impact_rub | Влияние на маржу в ₽ |

Невязка = Фактическая ΔМаржи - Σ(влияний всех факторов).
Если невязка > 5% от ΔМаржи — укажи в limitations.

### cost_structure (Структура затрат — доли от выручки)
Для каждого канала:
| Поле | Описание |
|------|----------|
| item | Комиссия до СПП, Логистика, Хранение, ДРР внутр, ДРР внешн, Себестоимость, Прочие, Маржинальность |
| current_pct | % от выручки текущий |
| previous_pct | % от выручки прошлый |
| delta_pp | Изменение в п.п. |

### spp_dynamics (Динамика СПП)
| Поле |
|------|
| channel, spp_current, spp_previous, delta, interpretation |

### price_forecast (Прогноз цен)
| Поле |
|------|
| channel, order_price_rub, sale_price_rub, gap_rub, forecast_text |
Если цена заказов > цены продаж → "выручка вырастет через 3-7 дней".
```

### 2.2 Усиление revenue-decomposer.md

**Текущее состояние:** возвращает `models[]`, `plan_fact[]`, `brand_totals{}`.
**Нужно добавить/изменить:**

```markdown
## ОБЯЗАТЕЛЬНЫЕ ПОЛЯ OUTPUT

### brand_metrics (15 финансовых метрик для секции "Ключевые изменения")
Вызови `get_brand_finance` + `get_channel_finance`.
Верни объект с 15 полями (воронковые метрики 16-19 — ответственность ad-efficiency):
1. margin_rub, 2. margin_pct, 3. sales_count, 4. sales_rub,
5. orders_rub, 6. orders_count, 7. adv_internal_rub, 8. adv_external_rub,
9. drr_orders_pct, 10. drr_sales_pct, 11. avg_check_orders, 12. avg_check_sales,
13. turnover_days, 14. roi_annual_pct, 15. spp_weighted_pct

Каждое поле: { current, previous, delta_abs, delta_pct }

### models (ВСЕ модели — НЕ фильтровать)
Вызови `get_model_breakdown` и выведи **ВСЕ** модели включая убыточные.
Каждая модель:
| Поле |
|------|
| model, channel, margin_rub, margin_delta_pct, margin_pct, stock_fbo, stock_own, stock_in_transit, stock_total, turnover_days, roi_annual_pct, drr_sales_pct, orders_count, revenue_rub |

stock_own = данные МойСклад (если недоступны — null, НЕ пропускать модель).
turnover_days = (avg_stock × num_days) / sales_count.
roi_annual = (margin / cogs) × (365 / turnover_days) × 100.

НЕ ФИЛЬТРУЙ модели. Если get_model_breakdown вернул 16 моделей — все 16 в output.

### plan_fact (План-факт MTD)
ОБЯЗАТЕЛЬНО вызови `get_plan_vs_fact`. Если план существует, верни:
| Поле |
|------|
| metric, plan_month, fact_mtd, plan_mtd, completion_pct, forecast, forecast_vs_plan_pct, status |

status: ✅ если >105%, ⚠️ если 95-105%, ❌ если <95%.
Метрики: orders_count, orders_rub, revenue, margin, adv_internal, adv_external.
Включи forecast (линейная экстраполяция) и forecast_vs_plan_pct.
```

### 2.3 Усиление ad-efficiency.md

**Текущее состояние:** возвращает `brand_drr{}`, `channels[]`, `model_matrix[]`.
**Нужно добавить:**

```markdown
## ОБЯЗАТЕЛЬНЫЕ ПОЛЯ OUTPUT

### funnel (Воронка продаж — по каждому каналу)
Вызови `get_advertising_stats` для WB и OZON.
Для каждого канала верни массив:
| Поле |
|------|
| stage (impressions, card_opens, add_to_cart, orders, buyouts), count, conversion_to_next_pct, benchmark_pct, gap_pp, status (ok/watch/critical) |

WB бенчмарки: CTR 1-3%, open→cart 5-15%, cart→order 25-40%, order→buyout 85-92%.
OZON бенчмарки: CTR 1-4%, card→order 3-8%, order→buyout 88-95%.

### ad_stats (Рекламная статистика — полная таблица)
| Поле |
|------|
| channel, impressions, clicks, ctr_pct, cpc_rub, cpm_rub, cpo_rub, spend_rub, cart_adds (WB), orders_from_ads |

НЕ сокращай до одной строки CPO. Вся таблица обязательна.

### brand_drr (ДРР — двойной расчёт)
| Поле |
|------|
| drr_orders_pct, drr_sales_pct, adv_internal_rub, adv_external_rub |

Всегда разделяй внутреннюю и внешнюю рекламу.
ДРР от заказов = (adv_internal + adv_external) / orders_rub × 100.
ДРР от продаж = (adv_internal + adv_external) / revenue_before_spp × 100.

### brand_metrics_funnel (4 воронковые метрики для секции 3)
| Поле |
|------|
| card_opens: {current, previous, delta_abs, delta_pct} |
| add_to_cart: {current, previous, delta_abs, delta_pct} |
| cr_open_to_cart_pct: {current, previous, delta_abs, delta_pct} |
| cr_cart_to_order_pct: {current, previous, delta_abs, delta_pct} |
```

### 2.4 Обновление report-compiler.md

Report-compiler уже имеет 11-секционную структуру. Нужно:

1. **Добавить точные таблицы** из V2 в каждую секцию (вместо generic описаний)
2. **Секция 3:** ровно 19 строк — перечислить каждую с формулой источника
3. **Секция 5:** ровно 10 строк waterfall — перечислить каждую
4. **Секция 6:** обязательные подсекции 6.1.1-6.1.5 для WB, 6.2.1-6.2.5 для OZON
5. **Добавить правило:** "НЕ СОКРАЩАЙ отчёт. Каждая таблица ОБЯЗАТЕЛЬНА."
6. **Graceful degradation:** если agent timed out — compiler строит секцию из доступных данных других agents, а не пропускает целиком

### 2.5 Усиление funnel-digitizer.md и campaign-optimizer.md

**funnel-digitizer:** промпт уже хороший, но добавить:
- Обязать `get_funnel_by_model` для ВСЕХ моделей (не только top)
- Добавить WoW trend обязательно (`get_funnel_trend`)

**campaign-optimizer:** промпт уже хороший, но добавить:
- Обязать `get_external_ad_breakdown` для разбивки внешняя реклама по каналам
- Добавить model-level ROMI matrix (`get_model_ad_efficiency`)

### 2.6 Расширить report-compiler.md условной логикой по типу отчёта

**Важно:** В orchestrator.py НЕТ COMPILER_MAP. Все типы отчётов используют один `report-compiler` agent (hard-coded на строке 263). Вместо создания отдельных файлов — расширяем `report-compiler.md` условными секциями (аналогично тому, как уже реализован pricing report через "if artifacts contain price-strategist").

**Добавить в report-compiler.md:**

**Условие: если task_type = marketing_weekly / marketing_monthly:**
Секции:
1. Исполнительная сводка
2. Анализ по каналам (WB + OZON)
3. Анализ воронки
4. Органика vs Платное
5. Внешняя реклама (по каналам: блогеры, VK, creators)
6. Эффективность по моделям (ROMI matrix)
7. Дневная динамика рекламы
8. Средний чек и связь с ДРР
9. Рекомендации и план действий
10. Прогноз на следующую неделю

**Условие: если task_type = funnel_weekly:**
Секции:
1. Общий обзор бренда (таблица: переходы, заказы, выкупы, выручка, маржа, ДРР, ROMI)
2. Модельная декомпозиция (по каждой модели: full funnel + WoW)
3. Bottleneck analysis
4. Keyword portfolio
5. Рекомендации

**Определение типа:** compiler получает `task_type` в artifact_context. Добавить в orchestrator `_run_report_pipeline` передачу `task_type` в compiler input (если не передаётся).

**Альтернатива (если промпт станет слишком длинным):** создать отдельные файлы И добавить `compiler_agent` параметр в `_run_report_pipeline()`, wire через `run_marketing_report()` / `run_funnel_report()`.

---

## Фаза 3: Верификация паритета

### 3.1 Side-by-side тест

1. Запустить V3 daily report для конкретной даты
2. Запустить V2 CLI report для той же даты
3. Сравнить в Notion: все секции, таблицы, количество данных

### 3.2 Критерии готовности

| Секция | Критерий паритета |
|--------|-------------------|
| Секция 3 (Ключевые изменения) | Ровно 19 строк с теми же колонками |
| Секция 5 (Каскад маржи) | 10 строк waterfall с невязкой |
| Секция 6 (Модели) | ВСЕ модели с FBO/МойСклад/оборачиваемость/ROI |
| Секция 6.1.3 (Воронка) | 2 таблицы: объём + эффективность с бенчмарками |
| Секция 6.1.5 (Реклама) | Полная таблица: Показы, Клики, CTR, CPC, CPM, CPO |
| Секция 2 (План-факт) | Все метрики + forecast + status icons |
| Секция 9 (Advisor) | Рекомендации с ₽ эффектом, confidence, приоритетом |
| Trust Envelope | 🟢🟡🔴 per agent, confidence, limitations |

### 3.3 Регрессионное покрытие

Прогнать все типы отчётов:
- daily_report
- weekly_report
- monthly_report
- marketing_weekly
- funnel_weekly
- finolog_weekly

Убедиться что каждый генерится без ошибок и содержит все обязательные секции.

---

## Фаза 4: Вывод V2 из эксплуатации

### 4.1 Отключение V2

1. **Удалить `oleg-mcp` контейнер** из `deploy/docker-compose.yml`
   - Если Eggent использует Oleg tools через MCP — перенаправить на V3 tools
2. **Удалить V2 CLI скиллы** — `.claude/commands/` и `.claude/skills/` которые вызывают V2 pipeline
3. **Оставить `agents/oleg/services/`** — V3 импортирует tools оттуда (agent_tools.py, marketing_tools.py, etc.)

### 4.2 Рефакторинг tools

После стабилизации V3 (3-5 дней без ошибок):
1. Переместить `agents/oleg/services/agent_tools.py` → `shared/tools/agent_tools.py`
2. Переместить `agents/oleg/services/marketing_tools.py` → `shared/tools/marketing_tools.py`
3. Переместить `agents/oleg/services/funnel_tools.py` → `shared/tools/funnel_tools.py`
4. Переместить `agents/oleg/services/price_tools.py` → `shared/tools/price_tools.py`
5. Обновить импорты в `agents/v3/runner.py`
6. Удалить `agents/oleg/` (кроме перенесённых tools)

### 4.3 Что оставить в V3

- `agents/oleg/services/` tools (перенести в shared/)
- `agents/oleg/playbook.md`, `marketing_playbook.md`, `funnel_playbook.md` — как reference (KB)
- Ничего из agents/oleg/bot/, orchestrator/, executor/, pipeline/

---

## Порядок выполнения задач

### Wave 1 (параллельно, нет зависимостей)
- [ ] 1.1 Fix watchdog DB check (никогда не работал — false-positive алерты)
- [ ] 1.2 Fix watchdog last_run check
- [ ] 1.4 Fix Notion dedup (_REPORT_TYPE_MAP + TTL + Lock)
- [ ] 1.5 Остановить V2 CLI дубликаты (главный источник дублей — приоритетно)
- [ ] 1.6 Увеличить AGENT_TIMEOUT 120s → 180s в config.py

### Wave 2 (параллельно, нет зависимостей)
- [ ] 1.3 Port Telegram bot handlers (9 команд + free text)
- [ ] 2.1 Усиление margin-analyst.md
- [ ] 2.2 Усиление revenue-decomposer.md
- [ ] 2.3 Усиление ad-efficiency.md

### Wave 3 (зависит от Wave 2)
- [ ] 2.4 Обновление report-compiler.md (точные таблицы + условная логика по task_type)
- [ ] 2.5 Усиление funnel-digitizer.md + campaign-optimizer.md
- [ ] 2.6 Расширить report-compiler условной логикой marketing/funnel

### Wave 4 (зависит от Wave 3)
- [ ] 2.7 Graceful degradation: prompt-level (compiler) + code-level (orchestrator timeout handling)
- [ ] 2.8 Очистка: удалить orphan `report-conductor.md` если не используется

### Wave 5 (зависит от Wave 4)
- [ ] 3.1 Side-by-side верификация
- [ ] 3.2 Проверка критериев паритета
- [ ] 3.3 Регрессия всех типов отчётов

### Wave 6 (зависит от Wave 5 + 3-5 дней стабильности)
- [ ] 4.1 Удаление oleg-mcp контейнера
- [ ] 4.2 Перенос tools в shared/
- [ ] 4.3 Удаление agents/oleg/

---

## Файлы для изменения

### Фаза 1 (инфраструктура)
| Файл | Изменение |
|------|-----------|
| `agents/v3/monitor.py` | Fix `_db_cursor` call + `_check_last_run` fallback |
| `agents/v3/app.py` | Добавить 9 Telegram handlers |
| `agents/v3/delivery/notion.py` | Fix dedup: remove TTL, add Lock, store page_id |
| `agents/v3/state.py` | Extend delivered keys: no TTL expiry, add page_id field |
| `deploy/docker-compose.yml` | (Фаза 4) удалить oleg-mcp |

### Фаза 2 (промпты)
| Файл | Изменение |
|------|-----------|
| `agents/v3/agents/margin-analyst.md` | Добавить margin_waterfall, cost_structure, spp_dynamics |
| `agents/v3/agents/revenue-decomposer.md` | Добавить brand_metrics (19 полей), усилить models output |
| `agents/v3/agents/ad-efficiency.md` | Добавить funnel[], ad_stats{}, brand_metrics_funnel |
| `agents/v3/agents/report-compiler.md` | Точные таблицы, 19 строк секция 3, graceful degradation |
| `agents/v3/agents/funnel-digitizer.md` | Обязать все модели + WoW trend |
| `agents/v3/agents/campaign-optimizer.md` | Обязать external breakdown + model ROMI |
| `agents/v3/orchestrator.py` | Graceful degradation при timeout + передача task_type в compiler |
| `agents/v3/config.py` | AGENT_TIMEOUT: 120 → 180 |
| `agents/v3/agents/report-conductor.md` | Удалить если orphan (не используется orchestrator'ом) |

### Фаза 4 (очистка)
| Файл | Изменение |
|------|-----------|
| `agents/oleg/services/*.py` | Переместить в `shared/tools/` |
| `agents/v3/runner.py` | Обновить import paths |
| `agents/oleg/` | Удалить (кроме перенесённых) |

---

## Фаза 0 (КРИТИЧНО): Стабилизация инфраструктуры — OOM

**Обнаружено 2026-03-23:** Сервер (2 ГБ RAM, 0 swap) каждую ночь убивает контейнер через OOM Killer.

### Хронология OOM

```
2026-03-22 03:04 UTC — OOM killed python (wookiee_oleg), RSS 413 МБ
2026-03-23 03:04 UTC — OOM killed python (wookiee_oleg), RSS 284 МБ
2026-03-23 10:43 UTC — контейнер рестартовал (7.5 часов даунтайм)
```

**Результат 2026-03-23 (понедельник):**
- 09:00 daily report → пропущен (контейнер мёртв)
- 10:15 weekly report → пропущен
- 11:15 weekly marketing bundle → пропущен
- ВСЕ weekly отчёты за 16-22 марта НЕ сгенерированы

### Диагностика памяти

**Сервер:** Timeweb Cloud, Amsterdam, 2 vCPU, **2 ГБ RAM**, 0 swap.

**Текущее потребление (при живом контейнере):**

| Контейнер | Использовано | Лимит | % |
|-----------|-------------|-------|---|
| eggent | 328 МБ | 1 ГБ | 32% |
| n8n | 265 МБ | 1.9 ГБ | 13% |
| wookiee_oleg (v3) | 189 МБ | 1 ГБ | 18% |
| vasily-api | 176 МБ | 512 МБ | 34% |
| oleg_mcp (V2) | 130 МБ | 512 МБ | 25% |
| 3× WB/Bitrix MCP | 124 МБ | 768 МБ | — |
| sheets_sync | 36 МБ | 512 МБ | 7% |
| **Итого** | **~1.25 ГБ** | **~6.2 ГБ** | — |

Available: 219 МБ. При ночном ETL sync (03:00-05:00) spike памяти убивает контейнер.

### Fix (Wave 0 — немедленно, до всех остальных задач)

| # | Действие | Эффект |
|---|----------|--------|
| 0.1 | **Добавить swap 4 ГБ** на сервер (`fallocate -l 4G /swapfile && mkswap && swapon`) | Предотвращает OOM при спайках |
| 0.2 | **Остановить `oleg_mcp`** контейнер | Освобождает 130 МБ RAM (V2 MCP не нужен) |
| 0.3 | **Снизить memory limit** eggent: 1 ГБ → 512 МБ, n8n: 1.9 ГБ → 1 ГБ | Предотвращает overcommit |
| 0.4 | **Добавить persistent logging** для wookiee_oleg (docker volume для логов) | Логи не теряются при рестарте |
| 0.5 | **Запустить пропущенные weekly отчёты** вручную через Telegram или CLI | Восстановить данные за 16-22 марта |

### Обновлённый порядок выполнения

**Wave 0** вставляется ПЕРЕД Wave 1. Без стабильного сервера все остальные waves бесполезны.

---

## Риски и митигация

| Риск | Митигация |
|------|-----------|
| **OOM Killer убивает контейнер ночью** | **Wave 0: swap 4 ГБ + остановить oleg_mcp + снизить лимиты** |
| LLM не следует длинному промпту — пропускает секции | "НЕ СОКРАЩАЙ" + проверка sections_included в compiler output |
| Agent timeout из-за более длинного output | Увеличить AGENT_TIMEOUT с 120s до 180s (задача 1.6 в Wave 1) |
| Дубли в Notion во время миграции | Lock + dedup fix до усиления промптов |
| МойСклад данные недоступны | null в stock_own, НЕ пропускать модель |
| Eggent зависит от oleg-mcp | Перенаправить на V3 tools или создать V3 MCP server |
| Контейнер рестарт → пропущенные отчёты | misfire_grace_time=3600 покрывает 1h; для >1h нужен catchup в conductor |

---

## Связанные документы

- [V3 Report Depth Gap](2026-03-22-v3-report-depth-gap.md) — исходная документация проблемы
- [Trust Envelope Plan](2026-03-21-trust-envelope-and-cost-tracking.md) — уже реализовано
- [Smart Conductor Design](2026-03-21-smart-conductor-design.md) — gate-based triggering
- [Advisor Agent Design](2026-03-21-advisor-agent-design.md) — advisor recommendations
- [Multi-Agent Redesign v3](../../agents/v3/README.md) — архитектура V3
