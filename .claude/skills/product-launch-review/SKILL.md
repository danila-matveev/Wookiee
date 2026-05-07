---
name: product-launch-review
description: Use when user asks to validate a new product launch on WB/OZON (стоит ли запускать, целесообразность запуска, проверь продукт, оценить идею, /product-launch-review). Mandatory economic clarification with pre-flight numerics before agent dispatch.
triggers:
  - /product-launch-review
  - стоит ли запускать
  - оценить запуск
  - проверь продукт
  - целесообразность запуска
  - анализ запуска продукта
  - launch review
---

# Product Launch Review

5-агентная панель валидации продуктового запуска: 3 аналитика + красная команда + бренд-директор. Архитектура из 3 волн с зависимостями.

**Iron Rule:** Цифры в Notion-карточке часто противоречат экономике. Stage 0 верифицирует ДО запуска агентов. Без подтверждённых входов агенты не запускаются.

## Architecture

```
Wave 1 (parallel, background)              Wave 2 (sequential)        Wave 3 (foreground)
┌─────────────────────────────┐            ┌─────────────────┐        ┌──────────────────┐
│ Marketplace Strategist (WB/OZON)│ ──┐    │                 │        │                  │
├─────────────────────────────┤   │    │ Red Team        │        │ Brand Director   │
│ Product & Marketing Strategist  │ ──┼──> │ (Devil's        │ ────>  │ (Synthesis,      │
├─────────────────────────────┤   │    │  Advocate)      │        │  Final Verdict)  │
│ Financial Modeler                │ ──┘    │                 │        │                  │
└─────────────────────────────┘            └─────────────────┘        └──────────────────┘
```

---

## Stage 0: Mandatory Economic Clarification

Собрать через AskUserQuestion **одним батчем** все 8 вопросов. Не пропускать ни один.

### Q1 — Источник продуктового контекста
- Notion URL / опишу текстом / уже в чате выше

### Q2 — MOQ
- Малый (50-300) / Средний (500-1000) / Большой (1000+ на цвет) / Other

### Q3 — Полная COGS на единицу (₽)
Если пользователь даёт только закупку — попросить уточнить: закупка + доставка + таможня + НДС + ФФ.

### Q4 — Целевая финальная цена (₽)
Уточнить: на старте (с нулём отзывов) и после 100-200 отзывов.

### Q5 — Целевая маржа (%)
- 10-15% / 20-25% / 28-35% / Other

### Q6 — Каналы
- Только WB / WB сейчас+OZON позже / WB+OZON параллельно

### Q7 — Аналоги в портфеле для бенчмарка
Названия моделей (Charlotte, Wendy и т.п.). Используются для DB-запросов.

### Q8 — Дедлайн / сезонная привязка

---

## Stage 0.5: Pre-flight Economic Check (ОБЯЗАТЕЛЬНО)

Перед запуском агентов выполнить inline-расчёт и показать пользователю:

```python
# Минимальная финальная цена для целевой маржи
# Формула: COGS + WB_commission + WB_logistics + marketing + VAT + target_margin
# где WB_commission = 0.35 × price, marketing = 0.10 × price, VAT = 0.05 × price
# price × (1 - 0.35 - 0.10 - 0.05) = COGS + 200 + (price × target_margin)
# price × (0.50 - target_margin) = COGS + 200
# min_price = (COGS + 200) / (0.50 - target_margin)

cogs = {{COGS}}
target_margin = {{TARGET_MARGIN}} / 100
min_price = (cogs + 200) / (0.50 - target_margin)
cash_commit = {{MOQ}} * cogs
batch_revenue = {{MOQ}} * {{TARGET_PRICE_START}}
batch_profit = batch_revenue * target_margin
```

Показать пользователю **в чате**:

```
📊 Pre-flight check

COGS на единицу: {{COGS}} ₽
Целевая маржа: {{TARGET_MARGIN}}%
→ Минимальная финальная цена для маржи: X ₽

Целевая цена пользователя: {{TARGET_PRICE_START}} ₽
{✅ Сходится / ⚠️ НЕ СХОДИТСЯ — пользователь хочет цену ниже минимально безубыточной}

Cash commitment: {{MOQ}} × {{COGS}} = Y ₽
Прогнозируемая прибыль с партии: Z ₽ ({{TARGET_MARGIN}}% × {{MOQ}} × цена)

Партия окупится за: ROI%, payback ~N месяцев

Подтвердить и запустить агентов?
```

**Если расхождение > 10%** между пользовательской ценой и расчётной min_price — **СТОП**, попросить пересмотреть цену или маржу.
**Если cash commitment > 2,000,000 ₽** — явный warning о размере коммита.

Не запускать Wave 1 без явного подтверждения пользователя.

---

## Stage 1: Context Pack Assembly

Собрать `/tmp/product-launch-context.md` со следующими блоками:

1. **Product spec** — Notion fetch (`mcp__claude_ai_Notion__notion-fetch`) или user text
2. **Confirmed economics** — все 8 ответов Stage 0 + расчёт min_price из Stage 0.5
3. **Comparator data** — реальные данные по моделям из Q7:
   ```bash
   cd /Users/danilamatveev/Projects/Wookiee
   PYTHONPATH=. python3 -c "
   from shared.data_layer import get_model_performance
   for model in {{COMPARATOR_PRODUCTS}}:
       data = get_model_performance(model, last_n_weeks=12)
       print(f'{model}: avg_price={data.avg_price}, margin={data.margin}, units/wk={data.units_per_week}, buyout={data.buyout_pct}, returns={data.return_rate}')
   "
   ```
   Если функция отсутствует — использовать существующие репорты из `docs/reports/` или `services/` для извлечения цифр.

4. **Competitor data** (если есть в Notion) — нормализовать в таблицу: артикул, цена, выручка/мес, отзывы, дата запуска.

---

## Stage 2 (Wave 1): Parallel Specialists — 3 агента

Запустить **одним сообщением, 3 Agent-вызова в параллель**, все `run_in_background: true`.

### Agent 1 — Marketplace Strategist
- Prompt: `.claude/skills/product-launch-review/prompts/marketplace-specialist.md`
- Фокус: рынок, конкуренты, SEO, OZON-стратегия, параметры запуска
- НЕ делает детальную финансовую модель — это Agent 3

### Agent 2 — Product & Marketing Strategist
- Prompt: `.claude/skills/product-launch-review/prompts/product-marketing.md`
- Фокус: концепция, УТП, аудитория, контент карточки, креативы

### Agent 3 — Financial Modeler
- Prompt: `.claude/skills/product-launch-review/prompts/financial-modeler.md`
- Фокус: маржа на каждой цене, sensitivity, ROI, прибыль партии, cashflow

Все 3 получают одинаковый Context Pack. Каждый получает только свой фокусный prompt.

Дождаться 3 completion notifications. **НЕ переходить к Wave 2 без всех 3.**

---

## Stage 2.5 (Wave 2): Red Team Critique

После получения 3 отчётов запустить 4-го агента **в background** (можно foreground если осталось мало контекста):

### Agent 4 — Red Team / Devil's Advocate
- Prompt: `.claude/skills/product-launch-review/prompts/red-team.md`
- Получает: outputs всех 3 предыдущих агентов + Context Pack
- Задача:
  - Pre-mortem: "Прошло 6 месяцев, запуск провалился катастрофически. Что его убило?"
  - Оспорить интерпретацию рынка (быстрый рост = накачка промо, не реальный спрос?)
  - Оспорить уникальность УТП (а покупателю это правда важно?)
  - Оспорить валидность аналогов (Charlotte успешен — это бренд или продукт?)
  - Найти скрытые риски, не упомянутые аналитиками
  - Контр-аргументы к рекомендации GO
  - Минимальный бар: что должно быть верно, чтобы запуск имел шанс

---

## Stage 3 (Wave 3): Brand Director Synthesis

После получения 4 отчётов — запустить **в foreground**:

### Agent 5 — Brand Development Director
- Prompt: `.claude/skills/product-launch-review/prompts/brand-director.md`
- Получает: все 4 отчёта (Marketplace + Product/Marketing + Financial + Red Team) + Context Pack
- Задача: финальный вердикт по 8-секционной структуре
- **ОБЯЗАТЕЛЬНО:** в каждом из своих "Рисков и ответов" явно упомянуть, какое возражение Red Team он принимает или отвергает (и почему).

---

## Stage 4: Delivery + Artifact

1. **Презентация пользователю** — финальный отчёт директора по структуре:
   1. Вердикт (GO / УСЛОВНЫЙ GO / NO-GO)
   2. Топ-3 довода
   3. Критические условия
   4. Риски + ответы (с явными ссылками на Red Team)
   5. Параметры запуска (таблица)
   6. Прогноз 6 месяцев (3 сценария + вероятности)
   7. Стратегический смысл для бренда
   8. Главное действие сейчас

2. **Сохранение артефакта:**
   ```
   docs/reports/YYYY-MM-DD-product-launch-{slug}.md
   ```
   Содержит: все входы Stage 0, Pre-flight check, 4 отчёта аналитиков + красной команды, синтез директора. Полная воспроизводимость.

3. **Логирование** — см. секцию "## Логирование" в самом конце файла. Выполняется через Supabase MCP.

---

## Stage 5: Iteration Loop (опционально)

После доставки спросить:

```
question: "Хочешь перезапустить с обновлёнными входами?"
options:
  - "MOQ изменился" / description: "Перезапустить Financial Modeler + Director"
  - "Цена/маржа изменилась" / description: "Перезапустить Financial Modeler + Director"
  - "Аналог изменился" / description: "Полный перезапуск Wave 1+2+3"
  - "Нет, всё устраивает" / description: "Закрыть"
```

При перезапуске — пересобрать Context Pack с новыми входами и запустить только нужные агенты.

---

## Critical Rules

- **Stage 0 + 0.5 не пропускать.** Pre-flight check показывается пользователю **в чате** до запуска агентов.
- **Wave 1 строго параллельно** (3 агента в одном сообщении).
- **Wave 2 НЕ запускать** до получения всех 3 отчётов Wave 1.
- **Wave 3 НЕ запускать** до Wave 2.
- **Director обязан адресовать Red Team возражения** явно — иначе вердикт неполный.
- **Все цифры в промптах — только из подтверждённых Stage 0**, никаких выдумок.
- **Сохранять артефакт в `docs/reports/`** для воспроизводимости.

## Common Mistakes

| Ошибка | Реальность |
|---|---|
| "Cтейдж 0.5 — лишнее, агенты сами посчитают" | В реальном кейсе Love Notion рекомендовал 1,499₽ при COGS 808₽ — убыточно. Pre-flight ловит это до запуска. |
| "Запустим всех 5 агентов в параллель" | Red Team нужны выходы Wave 1, Director — выходы Wave 2. Зависимость нарушена → бесполезный синтез. |
| "Маркетплейс-агент посчитает экономику" | Он считает рынок, не финансы. Пересечение доменов снижает качество обоих. |
| "Red Team — это негативизм, лишний шум" | Без него все 3 агента склоняются к GO (institutional bias). Решение принимается в эхо-камере. |
| "Аналоги опишу гипотетически" | У бренда есть факт-данные. Использовать `data_layer.py` или существующие отчёты. |
| "MOQ × COGS — это деталь" | 240 ед × 808₽ = 194K₽ vs 3000 ед × 808₽ = 2.4M₽. Разные риск-профили, разные решения. |
| "Не сохранять — пользователь и так увидит" | Через месяц при изменении сценария нужно вернуться к расчётам. Без артефакта — запуск с нуля. |

---

## Логирование (выполнить всегда в конце)

Определи переменные:
- `_log_status` = `success` или `error`
- `_log_url` = путь к артефакту (`docs/reports/...md`) или пустая строка
- `_log_items` = количество агентов отработавших успешно (обычно 5)
- `_log_notes` = краткое описание результата (например "Боди Love: УСЛОВНЫЙ GO, цена 2,900₽, партия 3000, прибыль ~2.5M₽")
- `_log_user` = `USER_EMAIL` из `.env` (или "unknown")
- `N` = длительность выполнения в секундах

Выполни через Supabase MCP (`execute_sql`, project `gjvwcdtfglupewcwzfhw`):

```sql
WITH ins AS (
  INSERT INTO tool_runs (
    id, tool_slug, status, trigger_type, triggered_by,
    result_url, items_processed, notes,
    started_at, finished_at, duration_sec
  ) VALUES (
    gen_random_uuid(),
    '/product-launch-review',
    '_log_status',
    'manual',
    'user:_log_user',
    '_log_url',
    _log_items,
    '_log_notes',
    now() - interval 'N seconds',
    now(),
    N
  )
  RETURNING tool_slug, status
)
UPDATE tools SET
  total_runs = total_runs + 1,
  last_run_at = now(),
  last_status = '_log_status',
  updated_at = now()
WHERE slug = '/product-launch-review';
```
