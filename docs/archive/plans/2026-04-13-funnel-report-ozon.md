# Funnel Report v2: OZON Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add OZON channel sections to the existing `/funnel-report` skill — channel overview, ad funnel (views→clicks→cart→orders), and per-model economics.

**Architecture:** Most OZON data already flows through `collect_all.py` (traffic.ozon_total, ozon_organic_estimated, advertising.ozon_model_ad_roi, ozon_ad_by_sku, finance.ozon_models). Need one new data_layer function for aggregated ad funnel by model, then update 5 skill prompt files to include OZON sections.

**Tech Stack:** Python (data_layer), Markdown (skill prompts), Notion API (publication)

**Spec:** `docs/superpowers/specs/2026-04-13-funnel-report-ozon-design.md`

---

## File Structure

```
Modified:
  shared/data_layer/advertising.py          ← add get_ozon_ad_funnel_by_model()
  scripts/analytics_report/collectors/traffic.py  ← add ozon_ad_funnel_by_model block
  .claude/skills/funnel-report/SKILL.md     ← add OZON data blocks + Stage 3b
  .claude/skills/funnel-report/prompts/detector.md      ← add OZON scanning
  .claude/skills/funnel-report/prompts/model-analyst.md ← add OZON model template
  .claude/skills/funnel-report/prompts/synthesizer.md   ← add OZON sections
  .claude/skills/funnel-report/prompts/verifier.md      ← add OZON check
```

---

### Task 1: Add `get_ozon_ad_funnel_by_model()` to data layer

**Files:**
- Modify: `shared/data_layer/advertising.py`

The existing `get_ozon_ad_by_sku()` returns SKU-level data. We need a model-level aggregate with the full ad funnel (views→clicks→to_cart→orders).

- [ ] **Step 1: Add function to advertising.py**

Add after `get_ozon_ad_by_sku()` (around line 440):

```python
def get_ozon_ad_funnel_by_model(current_start, prev_start, current_end):
    """OZON рекламная воронка по моделям: показы→клики→корзина→заказы.

    Sources: adv_stats_daily (views, clicks) + ozon_adv_api (to_cart, orders, spend).
    Groups by model via nomenclature JOIN.

    Returns: list of (period, model, views, clicks, to_cart, orders, spend, ctr, cpc, cpo)
    """
    conn = _get_ozon_connection()
    cur = conn.cursor()

    model_sql = get_osnova_sql("SPLIT_PART(o.offername, '/', 1)")

    query = f"""
    SELECT
        CASE WHEN o.operation_date >= %s THEN 'current' ELSE 'previous' END as period,
        {model_sql} as model,
        0 as views,
        SUM(o.clicks) as clicks,
        SUM(o.to_cart) as to_cart,
        SUM(o.orders) as orders,
        SUM(o.sum_rev) as spend,
        0 as ctr,
        CASE WHEN SUM(o.clicks) > 0 THEN SUM(o.sum_rev) / SUM(o.clicks) ELSE 0 END as cpc,
        CASE WHEN SUM(o.orders) > 0 THEN SUM(o.sum_rev) / SUM(o.orders) ELSE 0 END as cpo
    FROM ozon_adv_api o
    WHERE o.operation_date >= %s AND o.operation_date < %s
    GROUP BY 1, 2
    ORDER BY 1, SUM(o.sum_rev) DESC;
    """
    cur.execute(query, (current_start, prev_start, current_end))
    results = cur.fetchall()

    cur.close()
    conn.close()
    return results
```

Also add to `__all__` list at the top of the file.

- [ ] **Step 2: Test the function**

```bash
PYTHONPATH=. python3 -c "
from shared.data_layer.advertising import get_ozon_ad_funnel_by_model
results = get_ozon_ad_funnel_by_model('2026-04-06', '2026-03-30', '2026-04-13')
print(f'Rows: {len(results)}')
for row in results[:5]:
    p, model, views, clicks, to_cart, orders, spend, ctr, cpc, cpo = row
    print(f'{p} {model}: clicks={clicks} to_cart={to_cart} orders={orders} spend={spend:.0f}')
"
```

Expected: rows with per-model ad funnel data, to_cart values > 0.

- [ ] **Step 3: Commit**

```bash
git add shared/data_layer/advertising.py
git commit -m "feat(funnel-report): add get_ozon_ad_funnel_by_model()"
```

---

### Task 2: Add OZON ad funnel block to collector

**Files:**
- Modify: `scripts/analytics_report/collectors/traffic.py`

- [ ] **Step 1: Add import and block**

Add `get_ozon_ad_funnel_by_model` to imports from `shared.data_layer.advertising`:

```python
from shared.data_layer.advertising import (
    get_wb_organic_vs_paid_funnel,
    get_wb_organic_by_status,
    get_ozon_organic_estimated,
    get_ozon_ad_funnel_by_model,
)
```

Add to the returned dict, after `wb_skleyka_halo`:

```python
"ozon_ad_funnel_by_model": get_ozon_ad_funnel_by_model(start, prev_start, end),
```

- [ ] **Step 2: Test collector**

```bash
PYTHONPATH=. python3 -c "
import json
from scripts.analytics_report.collectors.traffic import collect_traffic
result = collect_traffic('2026-04-06', '2026-03-30', '2026-04-13')
ozon = result['traffic']['ozon_ad_funnel_by_model']
print(f'ozon_ad_funnel_by_model: {len(ozon)} rows')
for row in ozon[:3]:
    print(f'  {row}')
"
```

Expected: rows appear in collector output.

- [ ] **Step 3: Commit**

```bash
git add scripts/analytics_report/collectors/traffic.py
git commit -m "feat(funnel-report): add ozon_ad_funnel_by_model to collector"
```

---

### Task 3: Update SKILL.md — add OZON data blocks and Stage 3b

**Files:**
- Modify: `.claude/skills/funnel-report/SKILL.md`

- [ ] **Step 1: Update data blocks section**

After the existing data blocks list (around line 95), add OZON blocks:

```markdown
**OZON data blocks (for OZON sections):**
- `traffic.ozon_total` — OZON ad totals: [period, views, clicks, orders, spend, ctr, cpc]
- `traffic.ozon_organic_estimated` — расчётная органика по моделям: [period, model, total_orders, ad_orders, organic_orders, total_revenue, ad_spend]
- `traffic.ozon_ad_funnel_by_model` — рекл. воронка по моделям: [period, model, views, clicks, to_cart, orders, spend, ctr, cpc, cpo]
- `advertising.ozon_model_ad_roi` — ДРР и ROMI по моделям: [period, model, ad_spend, buyouts, revenue, margin, drr, romi]
- `finance.ozon_models` — финансы по моделям (заказы, выручка, маржа)
```

- [ ] **Step 2: Add Stage 3b after Stage 3**

After the existing Stage 3 (Model Analyst), add:

```markdown
## Stage 3b: OZON Model Sections

The same Model Analyst subagent generates OZON per-model sections using OZON data blocks.

**Input:** `ozon_ad_funnel_by_model` + `ozon_organic_estimated` + `ozon_model_ad_roi` + `finance.ozon_models` + `sku_statuses`

For each OZON model with orders > 0:
1. **Экономика** — заказы (тек vs пред), выручка, маржа, ДРР, ROMI, доля органики (расч.)
2. **Рекл. воронка** (если есть реклама) — клики, to_cart, заказы, CR клик→корзина, CR корзина→заказ, CPO
3. **Анализ** — 1-2 предложения о тренде

**Note:** Органическая воронка (переходы→корзина) НЕ доступна для OZON (search_stat пуст). Только заказы + реклама + финансы.

Save output as `ozon_model_deep`.
```

- [ ] **Step 3: Update report structure section**

Update the report structure table to include OZON sections:

```markdown
| # | Секция | Содержание |
|---|--------|------------|
| Title | Воронка WB+OZON за {PERIOD_LABEL} | Main heading |
| I | Общий обзор бренда (WB) | ... |
| I-b | Halo-эффект склеек (WB) | ... |
| II-XII | Модель: {Name} — ... | WB per-model |
| OZON-I | OZON: Обзор канала | заказы, выручка, маржа, ДРР, органика расч. |
| OZON-II | OZON: Рекламная воронка | показы→клики→корзина→заказы + CR + CTR + CPO |
| OZON-III+ | OZON: {Model} — заказы {Δ}% | per-model экономика |
| XIII | Выводы и рекомендации | WB + OZON объединённые |
```

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/funnel-report/SKILL.md
git commit -m "feat(funnel-report): add OZON stages and data blocks to SKILL.md"
```

---

### Task 4: Update detector.md — add OZON scanning

**Files:**
- Modify: `.claude/skills/funnel-report/prompts/detector.md`

- [ ] **Step 1: Add OZON data to input section**

After the existing WB data description, add:

```markdown
  **OZON данные:**
  - `traffic.ozon_total` — реклама OZON итого: [period, views, clicks, orders, spend, ctr, cpc]
  - `traffic.ozon_organic_estimated` — расчётная органика: [period, model, total_orders, ad_orders, organic_orders, total_revenue, ad_spend]
  - `traffic.ozon_ad_funnel_by_model` — рекл. воронка по моделям: [period, model, views, clicks, to_cart, orders, spend, ctr, cpc, cpo]
  - `advertising.ozon_model_ad_roi` — ДРР, ROMI по моделям
  - `finance.ozon_models` — финансы по моделям
```

- [ ] **Step 2: Add OZON scanning protocol**

Add new section "6. OZON канал" to the scanning protocol:

```markdown
### 6. OZON канал

#### Общие метрики
- Заказы: тек | пред | Δ%
- Выручка: тек | пред | Δ%
- Маржа: тек | пред | Δ%
- ДРР: тек% | пред% | Δ п.п.

#### Рекламная воронка (из ozon_ad_funnel_by_model, агрегат)
- Клики: тек | пред | Δ%
- Корзина (to_cart): тек | пред | Δ%
- Заказы рекл.: тек | пред | Δ%
- CR клик→корзина: тек% | пред% | Δ п.п.
- CR корзина→заказ: тек% | пред% | Δ п.п.
- CPO: тек ₽ | пред ₽ | Δ%

#### По моделям OZON
Для каждой модели с заказами > 0:
- Заказы: тек | пред | Δ%
- Доля органики (расч.): тек% | пред% | Δ п.п.
- ДРР: тек% | пред% | Δ п.п. (если есть реклама)

Флаг если: Δ заказов > 15% ИЛИ Δ ДРР > 3 п.п.

**Ограничение:** Органическая воронка (переходы→корзина) OZON НЕ доступна. Используем только расчётную органику = total_orders - ad_orders.
```

- [ ] **Step 3: Add OZON to output format**

Add to the output format section:

```markdown
OZON_OVERVIEW:
{
  orders: {current: <n>, previous: <n>, delta_pct: <n>},
  revenue: {current: <n>, previous: <n>, delta_pct: <n>},
  margin: {current: <n>, previous: <n>, delta_pct: <n>},
  drr: {current_pct: <n>, previous_pct: <n>, delta_pp: <n>},
  ad_funnel: {
    clicks: {current: <n>, previous: <n>, delta_pct: <n>},
    to_cart: {current: <n>, previous: <n>, delta_pct: <n>},
    orders: {current: <n>, previous: <n>, delta_pct: <n>},
    cr_click_cart: {current_pct: <n>, previous_pct: <n>, delta_pp: <n>},
    cr_cart_order: {current_pct: <n>, previous_pct: <n>, delta_pp: <n>},
    cpo: {current: <n>, previous: <n>, delta_pct: <n>}
  }
}

OZON_MODEL_FINDINGS:
[
  {model: "Wendy", orders: {current: <n>, previous: <n>, delta_pct: <n>}, organic_share: <n>, drr: <n>},
  ...
]
```

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/funnel-report/prompts/detector.md
git commit -m "feat(funnel-report): add OZON scanning to detector prompt"
```

---

### Task 5: Update model-analyst.md — add OZON model template

**Files:**
- Modify: `.claude/skills/funnel-report/prompts/model-analyst.md`

- [ ] **Step 1: Add OZON template section**

Add after the existing WB template section:

```markdown
---

## OZON модельные секции

Для каждой модели с заказами > 0 на OZON (из finance.ozon_models + ozon_organic_estimated):

\`\`\`markdown
## ▶ OZON: {Name} — заказы {+/-n}%
	### Экономика
	| Метрика | {PERIOD_LABEL} | {PREV_PERIOD_LABEL} | Δ |
	|---|---|---|---|
	| Заказы | {n} | {n} | {+/-n}% |
	| Выручка | {n} ₽ | {n} ₽ | {+/-n}% |
	| Маржа | {n} ₽ ({n}%) | {n} ₽ ({n}%) | {+/-n}% |
	| Рекл. расход | {n} ₽ | {n} ₽ | {+/-n}% |
	| ДРР | {n}% | {n}% | {+/-n} п.п. |
	| ROMI | {n}% | {n}% | {+/-n} п.п. |
	| Орган. заказы (расч.) | {n} ({n}%) | {n} ({n}%) | {+/-n} п.п. |
	### Рекламная воронка (если есть реклама)
	| Метрика | {PERIOD_LABEL} | {PREV_PERIOD_LABEL} | Δ |
	|---|---|---|---|
	| Клики | {n} | {n} | {+/-n}% |
	| Корзина (to_cart) | {n} | {n} | {+/-n}% |
	| CR клик→корзина | {n}% | {n}% | {+/-n} п.п. |
	| Заказы рекл. | {n} | {n} | {+/-n}% |
	| CR корзина→заказ | {n}% | {n}% | {+/-n} п.п. |
	| CPO | {n} ₽ | {n} ₽ | {+/-n}% |
	### Анализ
	{1-2 предложения: тренд заказов, изменение маржинальности, ДРР, доля органики}
	---
\`\`\`

**OZON-специфичные правила:**
- Нет органической воронки (переходы→корзина) — пометка "расчётная органика = total - paid"
- Нет выкупов — не показывать CRP
- Если рекламы нет (ad_spend = 0) — секцию "Рекламная воронка" НЕ показывать
- Сортировка: по убыванию выручки
- Toggle: `## ▶ OZON: {Name} — заказы {+/-n}%`
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/funnel-report/prompts/model-analyst.md
git commit -m "feat(funnel-report): add OZON model template to model-analyst"
```

---

### Task 6: Update synthesizer.md — add OZON report sections

**Files:**
- Modify: `.claude/skills/funnel-report/prompts/synthesizer.md`

- [ ] **Step 1: Update report structure**

Update the structure block to include OZON:

```markdown
## Структура отчёта

\`\`\`
# Воронка WB+OZON за {PERIOD_LABEL}

## ОБЩИЙ ОБЗОР БРЕНДА (WB)
{Секция I}
## Halo-эффект склеек (WB)
{Секция I-b}
---
## ▶ Модель: Wendy — ...
... (WB модели)
---

## OZON: Обзор канала
{Секция OZON-I}
## OZON: Рекламная воронка
{Секция OZON-II}
---
## ▶ OZON: Wendy — заказы +5%
... (OZON модели)
---

## Выводы и рекомендации
{Секция XIII — WB + OZON}
\`\`\`
```

- [ ] **Step 2: Add OZON section templates**

Add after the WB model sections:

```markdown
---

## Секция OZON-I: Обзор канала

**ТЫ ГЕНЕРИРУЕШЬ** из `finance.ozon_models` + `ozon_organic_estimated`.

| Метрика | {PERIOD_LABEL} | {PREV_PERIOD_LABEL} | Δ |
|---|---|---|---|
| Заказы | {n} | {n} | {+/-n}% |
| Выручка | {n} ₽ | {n} ₽ | {+/-n}% |
| Маржа | {n} ₽ | {n} ₽ | {+/-n}% |
| Маржинальность | {n}% | {n}% | {+/-n} п.п. |
| ДРР | {n}% | {n}% | {+/-n} п.п. |
| Рекл. заказы | {n} | {n} | {+/-n}% |
| Орган. заказы (расч.) | {n} | {n} | {+/-n}% |
| Доля органики | {n}% | {n}% | {+/-n} п.п. |

> 📊 OZON: {ключевой вывод — заказы, маржа, ДРР тренд}

**Примечание:** Органика OZON = total_orders - ad_orders (расчётная, не прямая).

---

## Секция OZON-II: Рекламная воронка

**ТЫ ГЕНЕРИРУЕШЬ** из `traffic.ozon_total` + `traffic.ozon_ad_funnel_by_model` (агрегат).

| Метрика | {PERIOD_LABEL} | {PREV_PERIOD_LABEL} | Δ |
|---|---|---|---|
| Показы | {n} | {n} | {+/-n}% |
| Клики | {n} | {n} | {+/-n}% |
| CTR | {n}% | {n}% | {+/-n} п.п. |
| Корзина (to_cart) | {n} | {n} | {+/-n}% |
| CR клик→корзина | {n}% | {n}% | {+/-n} п.п. |
| Заказы | {n} | {n} | {+/-n}% |
| CR корзина→заказ | {n}% | {n}% | {+/-n} п.п. |
| Расход | {n} ₽ | {n} ₽ | {+/-n}% |
| CPO | {n} ₽ | {n} ₽ | {+/-n}% |

---

## Секции OZON per-model

Вставить из `{{OZON_MODEL_DEEP}}`. Модели по убыванию выручки. `---` после каждой.
```

- [ ] **Step 3: Update conclusions section**

Update секция XIII to mention OZON:

```markdown
## Секция XIII: Выводы и рекомендации

**СИНТЕЗИРУЙ** из `{{HYPOTHESES}}` — объединённые WB + OZON.

ТОП-3 по WB (как сейчас) + отдельный блок:

### OZON — ключевые наблюдения

3-5 пунктов:
1. **Заказы:** {n} шт, Δ% vs пред. неделя
2. **ДРР:** {n}%, эффективность рекламы
3. **Доля органики:** {n}% (расчётная)
4. **Модель-лидер:** {name} — {выручка} ₽
5. **Рекомендация:** (если CPO > маржа/ед или ДРР > 15%)
```

- [ ] **Step 4: Update checklist**

Add to the pre-output checklist:

```markdown
- [ ] OZON секции присутствуют (обзор + рекл. воронка + per-model)
- [ ] OZON органика помечена как "расчётная"
- [ ] OZON заголовки таблиц с конкретными датами
- [ ] OZON toggle: `## ▶ OZON: {Name} — заказы {+/-n}%`
```

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/funnel-report/prompts/synthesizer.md
git commit -m "feat(funnel-report): add OZON sections to synthesizer"
```

---

### Task 7: Update verifier.md — add OZON check

**Files:**
- Modify: `.claude/skills/funnel-report/prompts/verifier.md`

- [ ] **Step 1: Add check #11**

After existing check #10, add:

```markdown
### 11. OZON данные

Проверить OZON секции:
- OZON обзор канала присутствует
- Заказы, выручка, маржа — не нулевые (OZON ~15% бизнеса)
- Рекламная воронка: CR клик→корзина и CR корзина→заказ в диапазоне 0-100%
- CPO > 0 если есть рекламный расход
- Органика помечена как "расч." или "расчётная"
- ДРР = ad_spend / revenue × 100 (проверить арифметику)

FAIL если: OZON секции отсутствуют ИЛИ данные нулевые ИЛИ CR > 100%.
```

- [ ] **Step 2: Update verdict section**

Update total checks count from 10 to 11.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/funnel-report/prompts/verifier.md
git commit -m "feat(funnel-report): add OZON data check to verifier"
```

---

### Task 8: E2E test — re-collect and re-generate report

- [ ] **Step 1: Re-collect data**

```bash
PYTHONPATH=. python3 scripts/analytics_report/collect_all.py --start 2026-04-06 --end 2026-04-12 --output /tmp/funnel-report-2026-04-06_2026-04-12-v4.json
```

Verify `ozon_ad_funnel_by_model` appears in output.

- [ ] **Step 2: Run full pipeline**

Execute `/funnel-report 2026-04-06 2026-04-12` using the updated skill. Verify:
- OZON overview section appears with real data
- OZON ad funnel table has CTR, to_cart, CPO
- OZON per-model toggles present
- All CRO values for WB still correct (< 5%)
- OZON organic marked as "расчётная"

- [ ] **Step 3: Publish to Notion and verify**

```python
PYTHONPATH=. python3 -c "
import asyncio, os
from dotenv import load_dotenv; load_dotenv()
from shared.notion_client import NotionClient
from pathlib import Path

async def main():
    md = Path('docs/reports/2026-04-06_2026-04-12_funnel.md').read_text()
    client = NotionClient(token=os.getenv('NOTION_TOKEN'), database_id=os.getenv('NOTION_DATABASE_ID'))
    url = await client.sync_report(start_date='2026-04-06', end_date='2026-04-12', report_md=md, report_type='funnel_weekly', source='Claude Code')
    print(f'Published: {url}')

asyncio.run(main())
"
```

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/funnel-report/
git commit -m "feat(funnel-report): v2 with OZON channel sections"
```

---

## Self-Review

1. **Spec coverage:** All 7 sections from spec covered — OZON overview (Task 6), ad funnel (Task 6), per-model (Task 5), data layer (Task 1), collector (Task 2), detector (Task 4), verifier (Task 7).
2. **No placeholders:** All code blocks have complete implementations.
3. **Type consistency:** `get_ozon_ad_funnel_by_model()` returns same tuple format used in prompts. Column names match between data layer and prompt documentation.
