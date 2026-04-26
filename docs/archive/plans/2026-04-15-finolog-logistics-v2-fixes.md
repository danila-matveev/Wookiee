# Finolog DDS + Logistics Report v2 Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two critical issues: (1) DDS analyst must project cash gaps against PLANNED operations, not absolute balances; (2) Logistics analyst must use velocity-adjusted thresholds for inventory classification.

**Architecture:** Prompt-only changes — no Python code changes needed. Both fixes are in `.claude/skills/*/prompts/analyst.md` and `synthesizer.md`.

**Tech Stack:** Markdown prompts (Claude Code skills)

---

## File Map

### Modified files
| File | Change |
|------|--------|
| `.claude/skills/finolog-dds-report/prompts/analyst.md:49-65` | Rewrite `cash_gap_scenarios` section: use forecast expense groups as planned operations, compute `free_after_planned = balance - cumulative(planned_expenses)` |
| `.claude/skills/finolog-dds-report/prompts/analyst.md:77-84` | Update `recommendations` to reference operational runway vs planned spend |
| `.claude/skills/finolog-dds-report/prompts/synthesizer.md:76-89` | Rewrite Section IV to show "Баланс после плановых операций" instead of raw balance |
| `.claude/skills/logistics-report/prompts/analyst.md:66-71` | Replace fixed thresholds with velocity-adjusted classification |
| `.claude/skills/logistics-report/prompts/synthesizer.md` | Add Δ пп for logistics % of revenue between periods |

---

## Task 1: DDS Analyst — cash gap against planned operations

**Files:**
- Modify: `.claude/skills/finolog-dds-report/prompts/analyst.md`

- [ ] **Step 1: Rewrite `cash_gap_scenarios` section (lines 49-65)**

Replace the current `cash_gap_scenarios` section with:

```markdown
### 4. planned_operations_gap

The key question: **хватит ли свободных денег на все запланированные расходы?**

Use `forecast` data — it contains planned expenses by group for each of the next 12 months.

**Step 1:** Calculate `free_balance` = total balance minus funds (funds are reserved, not free).
Only "operating" purpose accounts are free.

**Step 2:** For each month in `forecast`, extract planned expenses by group:
- Закупки (largest — typically 5-7М/мес)
- ФОТ (~2М/мес)
- Маркетинг (~1М/мес)
- Логистика (variable)
- Налоги (quarterly spikes)
- Склад, Услуги, Кредиты

**Step 3:** Compute cumulative planned spend and project balance:
```
Month 1: free_balance + forecast[0].income + forecast[0].expense → end_balance_1
Month 2: end_balance_1 + forecast[1].income + forecast[1].expense → end_balance_2
...
```

**Step 4:** Three scenarios:
- **Optimistic**: income = forecast income × 1.1
- **Base**: income = forecast income as-is
- **Pessimistic**: income = forecast income × 0.8

For each scenario, flag months where projected balance < 2,000,000 ₽ (operational minimum — 2 weeks of expenses).

**Step 5:** For each scenario, compute:
- `months_of_runway` = free_balance / avg_monthly_expense (from forecast)
- `gap_month` = first month where balance < 2M₽, or null
- `min_balance` = lowest balance across all months
- `largest_expense_month` = month with highest planned expenses (usually quarterly tax month)

Output:
```json
{
  "free_balance": 18393200,
  "funds_reserved": 8627797,
  "total_balance": 27111171,
  "avg_monthly_planned_expense": 15000000,
  "months_of_runway_from_free": 1.2,
  "scenarios": {
    "optimistic": {
      "months": [{"month": "апр 2026", "income": ..., "planned_expenses": ..., "end_balance": ..., "below_2m": false}],
      "gap_month": null,
      "min_balance": ...
    },
    "base": {...},
    "pessimistic": {...}
  },
  "largest_expense_month": {"month": "май 2026", "total_planned": 17636901, "breakdown": {"Закупки": 5862322, "Логистика": 5352439, ...}}
}
```

CRITICAL: Do NOT say "ликвидность высокая" if free_balance covers less than 3 months of planned expenses. 18М free with 15М/мес planned expenses = 1.2 months runway. That is TIGHT, not comfortable.
```

- [ ] **Step 2: Update `recommendations` section (lines 77-84)**

Replace the current `recommendations` content with:

```markdown
### 6. recommendations

Generate 3–5 specific, actionable recommendations:
- **Runway alert**: "Свободные средства {X}М покрывают {N} месяцев плановых расходов ({Y}М/мес). При N < 3 — это зона риска."
- **Largest upcoming expense**: "В {месяц} запланированы расходы {X}М (из них закупки {Y}М) — убедиться в достаточности средств за 2 недели до"
- **Fund adequacy**: "Налоговый фонд {X}М покрывает {N} квартальных платежей. ФОТ-фонд {X}М покрывает {N} месяцев."
- Cost concerns (for groups with significant growth)
- Cash gap action if any scenario shows gap

NEVER say "ликвидность высокая" based on absolute balance. Always express as months of runway vs planned operations.
```

- [ ] **Step 3: Verify the prompt is valid**

Read the full updated file to verify no broken markdown or JSON.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/finolog-dds-report/prompts/analyst.md
git commit -m "fix(finolog-dds): analyst must project cash gap vs planned operations, not absolute balance"
```

---

## Task 2: DDS Synthesizer — "Баланс после плановых операций"

**Files:**
- Modify: `.claude/skills/finolog-dds-report/prompts/synthesizer.md`

- [ ] **Step 1: Rewrite Section IV (lines 76-89)**

Replace the current Section IV with:

```markdown
### Section IV: Прогноз кассового разрыва

**IMPORTANT: Show balance AFTER planned operations, not raw balance.**

First, summary callout:
> 📊 Свободные средства: X₽. Плановые расходы: ~X₽/мес. Запас: **X месяцев**.

If runway < 3 months:
> ⚠️ Запас покрывает только **X месяцев** плановых расходов. Зона риска — необходим контроль закупок и поступлений.

Table with 3 scenarios × 6 months showing balance AFTER all planned operations:

| Месяц | Плановые расходы | Оптимистичный | Базовый | Пессимистичный |
|---|---|---|---|---|
| апр 2026 | X₽ | X₽ | X₽ | X₽ |
| май 2026 | X₽ | X₽ | X₽ | ⚠️ X₽ |

Mark months with balance < 2М₽ with ⚠️.

Show breakdown of the heaviest month:
> 📊 Самый тяжёлый месяц — {месяц}: закупки X₽, логистика X₽, ФОТ X₽, налоги X₽ = итого X₽

If any scenario shows gap:
> ⚠️ Кассовый разрыв в **{месяц}** в {scenario}: остаток X₽ после плановых расходов X₽. Дефицит X₽.
> 💡 Действие: сдвинуть закупку на X₽ на следующий месяц / ускорить получение выручки с МП.

If no gap:
> ✅ Кассовый разрыв не прогнозируется. Запас {X} месяцев при текущем плане расходов.
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/finolog-dds-report/prompts/synthesizer.md
git commit -m "fix(finolog-dds): synthesizer shows balance after planned operations"
```

---

## Task 3: Logistics Analyst — velocity-adjusted inventory thresholds

**Files:**
- Modify: `.claude/skills/logistics-report/prompts/analyst.md`

- [ ] **Step 1: Replace fixed thresholds (lines 66-71)**

Replace the current `Status classification` block with:

```markdown
Status classification — **velocity-adjusted thresholds:**

First, compute `daily_sales` for each model from turnover data.

**Thresholds depend on velocity:**

For high-velocity models (daily_sales >= 10):
- `DEFICIT` — turnover < 14 days OR marketplace stock < daily_sales × 3
- `WARNING` — turnover 14–21 days
- `OK` — turnover 21–60 days
- `OVERSTOCK` — turnover 60–120 days
- `DEAD_STOCK` — turnover > 120 days

For medium-velocity models (daily_sales 2–9):
- `DEFICIT` — turnover < 7 days OR marketplace stock < 3 units
- `WARNING` — turnover 7–14 days
- `OK` — turnover 14–45 days
- `OVERSTOCK` — turnover 45–90 days
- `DEAD_STOCK` — turnover > 90 days

For low-velocity models (daily_sales < 2):
- `DEFICIT` — marketplace stock = 0
- `WARNING` — turnover < 7 days AND stock < 3
- `OK` — turnover 7–45 days
- `OVERSTOCK` — turnover 45–60 days
- `DEAD_STOCK` — turnover > 60 days OR no sales in period

**CRITICAL:** A bestseller (top-10 by revenue or daily_sales >= 20) with 45-60 days turnover is NOT overstock — it needs this buffer because resupply takes 5-14 days and stockout = lost revenue. Only flag bestsellers as OVERSTOCK if turnover > 90 days.

Include `velocity_tier` ("high" / "medium" / "low") and `daily_sales` in output for each model.
```

- [ ] **Step 2: Update output format to include velocity**

In the output JSON section, update `inventory_assessment` to include `daily_sales` and `velocity_tier`:

Replace:
```json
"deficit": [{"model": "...", "wb_stock": 0, "ozon_stock": 0, "turnover_days": 0, "lost_sales_est": 0}],
```

With:
```json
"deficit": [{"model": "...", "wb_stock": 0, "ozon_stock": 0, "turnover_days": 0, "daily_sales": 0, "velocity_tier": "high|medium|low", "lost_sales_est": 0}],
```

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/logistics-report/prompts/analyst.md
git commit -m "fix(logistics): use velocity-adjusted thresholds for inventory classification"
```

---

## Task 4: Logistics Synthesizer — add Δ пп for logistics share

**Files:**
- Modify: `.claude/skills/logistics-report/prompts/synthesizer.md`

- [ ] **Step 1: Update Section II table to include Δ пп**

In the Section II description, update the WB table to add a `Δ пп` column:

Replace:
```markdown
| Метрика | Текущая неделя | Предыдущая неделя | Динамика |
```

With:
```markdown
### WB

| Канал | Стоимость | % выручки | На единицу | Δ ₽ | Δ % | Δ доли (пп) |
|---|---|---|---|---|---|---|
| WB | X₽ | X% | X₽ | Δ₽ | **±X%** | **+X,X пп** |
| OZON | X₽ | X% | X₽ | Δ₽ | **±X%** | — |
| **Итого** | **X₽** | **X%** | — | — | — | — |

Bold if Δ доли > 1 пп.
```

- [ ] **Step 2: Update Section V to show velocity tier**

Add a `Скорость` column to the inventory table:

```markdown
| Модель | WB | OZON | МС | Обор. | Прод./день | Статус | Эффект |
|---|---|---|---|---|---|---|---|
| model | X | X | X | X дн. | X шт/д | ⚠️ Дефицит | −X₽ |
```

This makes it clear WHY a model with 56 days turnover is OK (28 sales/day = high velocity).

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/logistics-report/prompts/synthesizer.md
git commit -m "fix(logistics): add delta pp for logistics share + velocity tier in inventory"
```

---

## Task 5: Smoke test — re-run both skills

- [ ] **Step 1: Re-run finolog-dds-report**

Invoke `/finolog-dds-report 2026-04-07 2026-04-13` and verify:
- Section IV shows "Свободные средства: 18,4М. Плановые расходы: ~15М/мес. Запас: ~1,2 месяца."
- NOT "ликвидность очень высокая"
- Scenarios show balance AFTER planned operations

- [ ] **Step 2: Re-run logistics-report**

Invoke `/logistics-report 2026-04-07 2026-04-13` and verify:
- Charlotte NOT marked as OVERSTOCK (28 sales/day, high velocity)
- Ruby may still be OVERSTOCK but with velocity context
- Table shows daily_sales column
- Logistics % has Δ пп column
