# Monthly Plan UX Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the monthly-plan skill output from an analytics report into a management tool — action-first format, single margin, toggle headings everywhere, simplified sections.

**Architecture:** Modify 10 prompt/template files in `.claude/skills/monthly-plan/`. No Python code changes. After all prompts updated, regenerate the April 2026 plan to verify.

**Tech Stack:** Markdown prompt templates, Notion-enhanced formatting, Claude Code skill system.

**Spec:** `docs/superpowers/specs/2026-04-03-monthly-plan-ux-refactor-design.md`

---

### Task 1: Rewrite plan-structure.md (new document template)

**Files:**
- Modify: `.claude/skills/monthly-plan/templates/plan-structure.md`

This is the skeleton template that the Synthesizer uses to assemble the final document. Replace the entire 12-section A-M structure with the new 7-section (0-6 + Reference) structure.

- [ ] **Step 1: Read current file to confirm state**

```bash
cat .claude/skills/monthly-plan/templates/plan-structure.md | head -5
```

Expected: starts with `# Бизнес-план Wookiee`

- [ ] **Step 2: Replace entire file with new template**

Replace the full content of `.claude/skills/monthly-plan/templates/plan-structure.md` with:

```markdown
# Бизнес-план Wookiee — {{PLAN_MONTH_NAME}} {{PLAN_YEAR}}

> Дата создания: {{CREATED_DATE}}
> Статус: **VERIFIED** — {{N_ANALYSTS}} аналитиков, {{N_CHECKS}} проверок, вердикт CFO: {{CFO_VERDICT}}
> Базовый период: {{BASE_MONTH_NAME}} {{BASE_YEAR}}

---

## 0. Резюме плана

### Целевые показатели

| Показатель | Цель {{PLAN_MONTH_NAME}} | Факт {{BASE_MONTH_NAME}} | Δ% |
|---|---|---|---|
| Заказы (₽) | {{TARGET_ORDERS}} | {{BASE_ORDERS}} | |
| Продажи (Revenue) | {{TARGET_REVENUE}} | {{BASE_REVENUE}} | |
| Маржа | {{TARGET_MARGIN}} | {{BASE_MARGIN}} | |
| Маржа % | {{TARGET_MARGIN_PCT}} | {{BASE_MARGIN_PCT}} | |

### Действия

{{TOP_ACTIONS_LIST}}

> 5-7 пунктов. Только действия, без пояснений. Формат:
> - Пополнить [модель] на [площадке]
> - Остановить рекламу [модель]
> - Увеличить рекламу [модель]
> - Снизить цену [модель] (overstock Xд)
> - Ликвидация [модель]

### Бюджет рекламы

| Статья | {{PLAN_MONTH_NAME}} | {{BASE_MONTH_NAME}} | Δ |
|---|---|---|---|
| Реклама внутренняя | {{PLAN_AD_INTERNAL}} | {{BASE_AD_INTERNAL}} | |
| Реклама внешняя | {{PLAN_AD_EXTERNAL}} | {{BASE_AD_EXTERNAL}} | |
| Итого | {{PLAN_AD_TOTAL}} | {{BASE_AD_TOTAL}} | |

---

## 1. Остатки и оборачиваемость

| Модель | Остаток, шт | Оборачиваемость, дн | Проблема | Действие |
|---|---|---|---|---|
| {{INVENTORY_ACTION_ROWS}} |

> Проблемы: ДЕФИЦИТ (<14д) / OK (14-60д) / ВНИМАНИЕ (60-90д) / OVERSTOCK (90-250д) / МЁРТВЫЙ СТОК (>250д)
> Действие: пополнить / держать / FREEZE / снизить цену / ликвидация

---

## 2. P&L Бренд — План {{PLAN_MONTH_NAME}}

### P&L воронка

| Статья P&L | План {{PLAN_MONTH_NAME}}, тыс.₽ | Факт {{BASE_MONTH_NAME}}, тыс.₽ | Δ% | Комментарий |
|---|---|---|---|---|
| Заказы (₽) | | | | |
| Выручка до СПП | | | | |
| СПП | | | | |
| Выручка после СПП | | | | |
| Себестоимость | | | | |
| Логистика | | | | |
| Хранение | | | | |
| Комиссия МП | | | | |
| НДС | | | | |
| Реклама внутренняя | | | | |
| Реклама внешняя | | | | |
| **Σ Реклама** | | | | |
| **Маржа** | | | | |
| **Маржа %** | | | | |

> Маржа = итоговая, включает ВСЮ рекламу (внутреннюю + внешнюю).

### Разбивка по каналам

> Toggle: детальная P&L по WB и OZON отдельно

| Показатель | WB План | WB Факт {{BASE}} | OZON План | OZON Факт {{BASE}} |
|---|---|---|---|---|
| {{CHANNEL_BREAKDOWN_ROWS}} |

---

## 3. P&L по моделям

| Модель | Выручка план, тыс.₽ | Выручка {{BASE}}, тыс.₽ | Δ% | Реклама, тыс.₽ | Маржа, тыс.₽ | Маржа, % | Ключевое решение |
|---|---|---|---|---|---|---|---|
| {{MODEL_PLAN_ROWS}} |
| **ИТОГО** | | | | | | | |

> Сортировка по выручке ↓. Маржа = итоговая (вкл. всю рекламу).

### Выводимые модели

| Модель | Статус | Выручка, тыс.₽ | Маржа, тыс.₽ | Остаток, шт | Оборачиваемость, дн | Действие |
|---|---|---|---|---|---|---|
| {{EXITING_ROWS}} |

---

## 4. Рекомендации по моделям

| Модель | Действие по цене | Действие по рекламе | Действие по остаткам | Эффект, тыс.₽ |
|---|---|---|---|---|
| {{RECOMMENDATIONS_ROWS}} |

> Каждое действие — 1 строка. Примеры:
> - Цена: "снизить на 5%", "поднять на 3%", "держать"
> - Реклама: "стоп", "увеличить бюджет +20%", "без изменений"
> - Остатки: "пополнить WB FBO", "FREEZE", "ликвидация"

### Обоснование

> Toggle по каждой модели: почему именно это действие.
> Содержит: оборачиваемость, маржа, тренд продаж, данные трафика.
> Бывшие гипотезы (D) и эластичность (I) — здесь в сжатом виде.

{{RATIONALE_PER_MODEL}}

---

## 5. Реклама

| Модель | Выручка, тыс.₽ | Реклама внутр., тыс.₽ | Реклама внешн., тыс.₽ | ДРР внутр., % | ДРР внешн., % | Маржа, % | Действие |
|---|---|---|---|---|---|---|---|
| {{AD_EFFICIENCY_ROWS}} |

### Рекомендованный бюджет

| Модель | Бюджет МП, тыс.₽ | Бюджет внешн., тыс.₽ | Итого, тыс.₽ | ДРР цель, % | Обоснование |
|---|---|---|---|---|---|
| {{RECOMMENDED_BUDGET_ROWS}} |
| **ИТОГО** | | | | | |

### Агрессивный сценарий

> Toggle: альтернативный бюджет с масштабированием top-performers

| Модель | Бюджет МП, тыс.₽ | Бюджет внешн., тыс.₽ | Итого, тыс.₽ | ДРР цель, % | Обоснование |
|---|---|---|---|---|---|
| {{AGGRESSIVE_BUDGET_ROWS}} |

---

## 6. План действий

> Приоритизированный список. Без дедлайнов, без недельной разбивки.

**[КРИТИЧНО]**
{{CRITICAL_ACTIONS}}

**[ВАЖНО]**
{{IMPORTANT_ACTIONS}}

**[ЖЕЛАТЕЛЬНО]**
{{NICE_TO_HAVE_ACTIONS}}

---

## Справочно

### Факт {{BASE_MONTH_NAME}} {{BASE_YEAR}}

> Toggle: полная P&L Brand (WB + OZON + итого), M-1 и M-2 факт

#### P&L Brand Total

| Показатель | WB {{BASE}}, тыс.₽ | OZON {{BASE}}, тыс.₽ | ИТОГО {{BASE}}, тыс.₽ |
|---|---|---|---|
| {{FACT_PNL_ROWS}} |

#### Разбивка внешней рекламы

| Канал | Сумма, тыс.₽ |
|---|---|
| Блогеры | |
| ВК | |
| Creators | |
| **Итого** | |

#### ДРР с разбивкой

| Канал | Внутренняя МП | Внешняя | Итого |
|---|---|---|---|
| WB | | | |
| OZON | | | |
| **ИТОГО** | | | |

#### P&L по моделям — Факт

| Модель | Выручка WB | Выручка OZON | Выручка Итого | Реклама внутр. | Реклама внешн. | Маржа | Маржа % | ДРР % |
|---|---|---|---|---|---|---|---|---|
| {{FACT_MODEL_ROWS}} |

### ABC-анализ + сверка с финансистом

> Toggle: ABC-классификация и план финансиста vs факт

#### ABC

| Модель | A-арт | B-арт | C-арт | Итого | Флаги |
|---|---|---|---|---|---|
| {{ABC_ROWS}} |

#### План финансиста vs факт

| Модель | План WB, тыс.₽ | Факт WB, тыс.₽ | Δ% | План OZON, тыс.₽ | Факт OZON, тыс.₽ | Δ% | Статус |
|---|---|---|---|---|---|---|---|
| {{PLAN_VS_FACT_ROWS}} |

### Верификация

> Toggle: результаты проверок критиками, корректор, вердикт CFO

#### Кросс-проверки

| Проверка | Результат | Статус |
|---|---|---|
| Сумма моделей = Total (<1%) | | |
| DRR с разбивкой внутр/внешн | | |
| СПП = средневзвешенный | | |
| Эластичность на уровне артикула | | |
| Маржа = итоговая (вкл. всю рекламу) | | |
| Все модели покрыты рекомендациями | | |
| Стратегические противоречия устранены | | |

**DQ Critic:** {{DQ_FINDINGS}}
**Strategy Critic:** {{STRATEGY_FINDINGS}}
**Корректор:** {{CORRECTOR_FIXES}}
**CFO Вердикт:** {{CFO_VERDICT}} (Проход {{CFO_PASS}})

### Контекст и ограничения

> Toggle: флаги качества данных, модели с мало данных

| Флаг | Описание | Влияние |
|---|---|---|
| fan_out_bug | get_wb_model_ad_roi() завышает ad_spend | ROAS через get_wb_by_model() |
| db_vs_sheets_external_ads_gap | Расхождение DB/Sheets по внешней рекламе | Внешн. реклама из Sheets |
| ozon_no_external_ads | OZON внешняя реклама = 0 в БД | ДРР OZON = только внутренняя |
| traffic_powerbi_gap_20pct | content_analysis ≠ PowerBI (~20%) | Трафик = тренд, не абсолют |

**Пользовательский контекст:** {{USER_CONTEXT}}
**Модели с ограниченными данными:** {{LOW_DATA_MODELS}}

### Методология

> Toggle: как считались метрики

- **Маржа** = выручка − себестоимость − логистика − хранение − комиссия − НДС − реклама (внутр. + внешн.). Единая маржа, включает все расходы на рекламу.
- **ДРР** = реклама / выручка × 100%. Всегда с разбивкой: внутр. (МП) и внешн. (блогеры, ВК, creators) отдельно.
- **СПП** при объединении каналов = средневзвешенный: sum(spp_amount) / sum(revenue_before_spp) × 100%.
- **Эластичность** считается на уровне артикула (не модели). Агрегация — volume-weighted.
- **Оборачиваемость** = остаток / средние продажи в день за последние 30 дней.
- **Риски остатков**: ДЕФИЦИТ (<14д), OK (14-60д), ВНИМАНИЕ (60-90д), OVERSTOCK (90-250д), МЁРТВЫЙ СТОК (>250д).
```

- [ ] **Step 3: Verify file was written correctly**

```bash
head -3 .claude/skills/monthly-plan/templates/plan-structure.md
```

Expected: `# Бизнес-план Wookiee — {{PLAN_MONTH_NAME}} {{PLAN_YEAR}}`

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/monthly-plan/templates/plan-structure.md
git commit -m "refactor(monthly-plan): new plan-structure template — 7 sections + reference"
```

---

### Task 2: Update P&L Analyst — single margin, 1 scenario

**Files:**
- Modify: `.claude/skills/monthly-plan/prompts/analysts/pnl-analyst.md`

Key changes:
- Remove M-2 (margin after external ads) from output — single margin includes all ads
- Remove two-scenario requirement (A/B) — produce 1 recommended plan
- Update output table columns

- [ ] **Step 1: Replace Section A instructions**

In `.claude/skills/monthly-plan/prompts/analysts/pnl-analyst.md`, replace lines 28-40 (Section A instructions) with:

```markdown
### Section A: P&L Brand Total

Build a full P&L funnel table for WB, OZON, and combined:
- M-1 (base month) fact column
- 1 recommended plan column for the target month
- Absolute values and Δ% change
- All metrics: revenue, SPP, cost_of_goods, logistics, storage, commission, NDS, adv_internal, adv_external, **margin** (single, includes ALL ads)
- DRR table with internal/external split

**Critical rules:**
- SPP % when combining channels = weighted average: sum(spp_amount) / sum(revenue_before_spp) * 100
- DRR always with internal/external split
- **Single margin** = revenue − all costs − all ads (internal + external). Do NOT split into M-1/M-2.
- Buyout % is a lagged metric (3-21 day lag) — do NOT use as a reason for daily margin changes
- Produce 1 recommended plan scenario (not A/B). Base it on realistic projections.
```

- [ ] **Step 2: Replace Section B output format**

Replace lines 43-50 (Section B instructions) with:

```markdown
### Section B: Active Models

Build model-level plan table with:
- Plan Revenue, M-1 Fact Revenue, Δ%
- Total ads (internal + external)
- **Margin** (single, ₽ and %)
- DRR %
- "Key Change" column: CFO decision summary per model (1 line)

**Critical rule:** GROUP BY model always uses LOWER().

**Output columns:** Модель | Выручка план,К | Выручка {{BASE}},К | Δ% | Реклама,К | Маржа,К | Маржа% | Ключевое изменение
```

- [ ] **Step 3: Update output format section at bottom**

Replace the Output Format section (last paragraph) with:

```markdown
## Output Format

Produce structured markdown for sections A, B, C with all required tables.
- Table headers: human-readable Russian, no abbreviations
- Single margin throughout (no M-1/M-2 distinction)
- 1 plan scenario (not A/B)

End with a summary of key anomalies found for other agents to note.
```

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/monthly-plan/prompts/analysts/pnl-analyst.md
git commit -m "refactor(monthly-plan): pnl-analyst — single margin, 1 scenario"
```

---

### Task 3: Update Pricing Analyst — action-first, hide raw stats

**Files:**
- Modify: `.claude/skills/monthly-plan/prompts/analysts/pricing-analyst.md`

Key changes:
- Elasticity computation stays internal (unchanged)
- Output format changes: action + 1-line reason (through turnover + margin logic)
- Raw E, r, confidence → hidden, only used as internal guards
- Section I removed from visible output → data goes into rationale toggle

- [ ] **Step 1: Replace Section I task description**

In `.claude/skills/monthly-plan/prompts/analysts/pricing-analyst.md`, replace the Section I task (lines 16-38) with:

```markdown
### Internal: Price Elasticity Computation

Compute E and r at the **article level** (same methodology as before — NEVER model-level). This data is used internally for recommendation quality, but NOT shown directly in the final document.

1. Compute E (price elasticity) and r (Pearson correlation) per article
2. Aggregate to model via volume-weighted averaging
3. Classify confidence: HIGH (|r|>0.5, >30d), MED, LOW
4. Use confidence as decision guard (see Critical Rules below)

**This data is NOT a separate section.** It feeds into recommendations.
```

- [ ] **Step 2: Replace Section D task description**

Replace Section D pricing part (lines 40-52) with:

```markdown
### Output: Price Recommendations (for Section 4 — Recommendations Table)

For each model, produce a single-row recommendation:

**Format:** `Модель | Действие по цене | Причина (1 строка) | Эффект, тыс.₽`

- **Действие:** "поднять на X%", "снизить на X%", "держать", "тест 1 SKU на 2 нед."
- **Причина:** frame through turnover + margin, NOT through E/r. Examples:
  - "Overstock 95д, маржа 28% → снизить для ускорения продаж"
  - "Дефицит 8д, маржа 22% → поднять, спрос превышает предложение"
  - "Маржа 12%, продажи стабильны → держать, снижение убьёт маржу"
  - "Мало данных (<15д) → держать, наблюдать"
- **Эффект:** calculate using elasticity internally, show as "+120К" or "−85К"

Also produce a **rationale block** per model for the toggle section:
```
Модель: [name]
Оборачиваемость: [X] дней ([RISK_LEVEL])
Маржа: [X]% (тренд: ↑/↓/→)
Тренд продаж: [краткое описание]
Ценовое решение: [действие] — [развёрнутое обоснование через бизнес-логику]
```
```

- [ ] **Step 3: Update Critical Rules — add turnover-based decision logic**

After the existing Critical Rules section, add:

```markdown
## Price Decision Logic (for output framing)

Recommendations are computed using elasticity internally but PRESENTED through business logic:

1. **Overstock + нормальная маржа (>15%)** → снижать цену (ускорить продажи)
2. **Дефицит + нормальная маржа** → повышать цену (спрос > предложение)
3. **Низкая маржа (<15%)** → НЕ снижать (даже при слабых продажах)
4. **Мёртвый сток (>250д)** → уценка / ликвидация
5. **Мало данных** → держать, наблюдать

The elasticity computation validates these heuristics. If elasticity contradicts the business logic (e.g., inelastic model with overstock), note it in the rationale.
```

- [ ] **Step 4: Update Output Format section**

Replace the Output Format section at the bottom:

```markdown
## Output Format

1. **Recommendations table** — one row per model: Модель | Действие | Причина | Эффект,К
2. **Rationale blocks** — one per model (for toggle section): turnover, margin, trend, full reasoning
3. **Internal data** — E, r, confidence per model (for critics to validate, NOT for final document)

Do NOT produce a standalone "Section I" table. The elasticity data is internal.
```

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/monthly-plan/prompts/analysts/pricing-analyst.md
git commit -m "refactor(monthly-plan): pricing-analyst — action-first, hide raw E/r"
```

---

### Task 4: Update Ad Analyst — 1 visible scenario, action column

**Files:**
- Modify: `.claude/skills/monthly-plan/prompts/analysts/ad-analyst.md`

Key changes:
- Section H: add "Действие" column, use single margin for break-even
- Section E: 1 recommended scenario visible, aggressive → separate block for toggle
- Single margin terminology

- [ ] **Step 1: Update Section H columns**

In `.claude/skills/monthly-plan/prompts/analysts/ad-analyst.md`, replace Section H task (lines 13-22) with:

```markdown
### Section H: Ad Efficiency (for Section 5 — Реклама)

For each model, build the ad efficiency table:
- Revenue, adv_internal, adv_external, DRR_internal%, DRR_external%
- Margin % (single margin, includes all ads)
- Verdict → converted to **Действие**: "увеличить +X%", "сохранить", "снизить −X%", "стоп"
- If DRR > break-even → "⚠️ УБЫТОК" in verdict

**DRR critical rule:** ALWAYS with internal/external split.
**Break-even DRR** = margin % (single margin — the point where ad spend = remaining profit)

**Output columns:** Модель | Выручка,К | Рекл внутр,К | Рекл внешн,К | ДРР внутр% | ДРР внешн% | Маржа% | Действие
```

- [ ] **Step 2: Update Section E — split into recommended + aggressive**

Replace Section E task (lines 24-37) with:

```markdown
### Section E: Budget Scenarios

**Recommended scenario (visible in main document):**
- Keep budget proportional to current ROAS where effective
- Models with DRR > break-even: reduce to break-even or stop
- Models with ROAS > 40x: +10-20% budget
- Show: per-model allocation, DRR target, rationale

**Aggressive scenario (for toggle, separate block):**
- Top performers (ROAS > 30x): +20-30% budget
- Growth models: +15-20%
- Loss-making: zero

Produce TWO separate tables — the synthesizer will place recommended in main view, aggressive in toggle.
```

- [ ] **Step 3: Update output format**

Replace the Output Format section:

```markdown
## Output Format

1. **Ad efficiency table** — per model with Действие column
2. **Recommended budget table** — 1 scenario, per-model allocation
3. **Aggressive budget table** — separate, for toggle
4. **Ad hypotheses per model** — for rationale toggle (1-2 sentences each)

Use single margin terminology throughout. No M-1/M-2.
```

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/monthly-plan/prompts/analysts/ad-analyst.md
git commit -m "refactor(monthly-plan): ad-analyst — 1 scenario visible, action column"
```

---

### Task 5: Update Inventory Analyst — action column, position #1

**Files:**
- Modify: `.claude/skills/monthly-plan/prompts/analysts/inventory-analyst.md`

Key changes:
- Add "Действие" column to main output
- Simplified output table (combined stock, single turnover)
- Note that this section is now #1 in the document (after summary)

- [ ] **Step 1: Update Section F output format**

In `.claude/skills/monthly-plan/prompts/analysts/inventory-analyst.md`, replace Section F task (lines 13-30) with:

```markdown
### Section F: Inventory & Turnover (Document Section 1 — first after summary)

This is now the FIRST operational section in the document (right after the executive summary). Build a simplified action-oriented table:

**Main table columns:** Модель | Остаток, шт | Оборачиваемость, дн | Проблема | Действие

Where:
- **Остаток** = total across all locations (WB FBO + OZON FBO + МойСклад + in-transit)
- **Оборачиваемость** = WB turnover days (primary channel)
- **Проблема**: ДЕФИЦИТ / OK / ВНИМАНИЕ / OVERSTOCK / МЁРТВЫЙ СТОК
- **Действие**: specific action — "пополнить WB FBO (МойСклад: X шт)", "FREEZE отгрузки", "снизить цену −X%", "ликвидация", "без действий"

Risk thresholds (unchanged):
- **ДЕФИЦИТ**: < 14 days
- **OK**: 14–60 days
- **ВНИМАНИЕ**: 60–90 days
- **OVERSTOCK**: 90–250 days
- **МЁРТВЫЙ СТОК**: > 250 days

**Also produce detailed breakdown** (for Reference toggle):
- Per-location stock: WB FBO, OZON FBO, МойСклад, in-transit
- WB and OZON turnover separately
- WB and OZON risk separately
```

- [ ] **Step 2: Update output format section**

Replace Output Format:

```markdown
## Output Format

1. **Simplified action table** — Модель | Остаток | Оборачиваемость | Проблема | Действие (for main document Section 1)
2. **Detailed breakdown** — per-location stock with dual-channel risks (for Reference toggle)
3. **Section G** — ABC + financier reconciliation (for Reference toggle)
4. **Replenishment/liquidation recommendations** — feed into Section 4 (Recommendations) and Section 6 (Action Plan)
```

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/monthly-plan/prompts/analysts/inventory-analyst.md
git commit -m "refactor(monthly-plan): inventory-analyst — action column, simplified table"
```

---

### Task 6: Update Traffic Analyst — output as rationale content

**Files:**
- Modify: `.claude/skills/monthly-plan/prompts/analysts/traffic-analyst.md`

Key change: traffic no longer gets its own section. Output feeds into the "Обоснование" toggle of Section 4 (Recommendations).

- [ ] **Step 1: Update role description and output format**

In `.claude/skills/monthly-plan/prompts/analysts/traffic-analyst.md`, replace lines 1-8 (role section) with:

```markdown
# Traffic & Funnel Analyst

You are the traffic and funnel analyst for the Wookiee brand.

## Your Role

Produce traffic and conversion analysis that feeds into the **rationale toggle** of Section 4 (Recommendations per model). You do NOT produce a standalone section — your output is supplementary context for other analysts' recommendations.
```

- [ ] **Step 2: Update output format at bottom**

Replace the Output Format section:

```markdown
## Output Format

**Per-model traffic rationale blocks** (for Section 4 toggle):

```
Модель: [name]
Органика: Shows [X] → Cart [Y] → Orders [Z] (CR: [X]%)
Рекламный трафик: [X]% от заказов
Тренд: [organic ↑/↓/→, ad dependency high/low]
Гипотеза: [1 sentence — e.g., "CR cart→order 11% — проверить ценовую конкурентоспособность"]
```

Do NOT produce standalone tables or a separate "Traffic" section. This data is context for recommendations.
```

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/monthly-plan/prompts/analysts/traffic-analyst.md
git commit -m "refactor(monthly-plan): traffic-analyst — output as rationale content"
```

---

### Task 7: Update DQ Critic — single margin checks

**Files:**
- Modify: `.claude/skills/monthly-plan/prompts/critics/data-quality-critic.md`

Key change: replace M-1/M-2 checks with single margin validation.

- [ ] **Step 1: Replace check #7 (Both Margin Levels)**

In `.claude/skills/monthly-plan/prompts/critics/data-quality-critic.md`, replace the "### 7. Both Margin Levels Present" section (lines 52-57) with:

```markdown
### 7. Single Margin Consistency
- Margin must be calculated as single value including ALL ads (internal + external)
- If any analyst reports separate M-1 and M-2 margins: WARNING — should be single margin
- Verify: margin = revenue − all_costs − adv_internal − adv_external
- If margin calculation excludes external ads: CRITICAL error
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/monthly-plan/prompts/critics/data-quality-critic.md
git commit -m "refactor(monthly-plan): dq-critic — single margin check"
```

---

### Task 8: Update CFO — action-list summary, no weekly plan

**Files:**
- Modify: `.claude/skills/monthly-plan/prompts/cfo.md`

Key changes:
- Section 0: 5-7 actions without explanations
- Replace weekly plan (Section J) with prioritized action list
- Single margin terminology
- Price decisions framed via turnover + margin

- [ ] **Step 1: Replace Section 0 instructions**

In `.claude/skills/monthly-plan/prompts/cfo.md`, replace "### 0. Generate Section 0" (lines 27-35) with:

```markdown
### 0. Generate Section 0 — Plan Summary

Produce the executive summary:
- **Target KPIs:** orders, revenue, margin, margin% (single margin, includes all ads)
- **5-7 actions** — NO explanations, NO rationale. Just actions:
  - "Пополнить [модель] на [площадке]"
  - "Остановить рекламу [модель]"
  - "Увеличить рекламу [модель] (+X%)"
  - "Снизить цену [модель] (overstock Xд)"
  - "Ликвидация [модель]"
- **Ad budget:** internal, external, total vs base month
```

- [ ] **Step 2: Replace weekly plan with prioritized action list**

Replace "### 3. Weekly Priorities (Section J)" (lines 56-66) with:

```markdown
### 3. Prioritized Action List (Section 6)

Instead of weekly plan, produce a prioritized flat list:

**[КРИТИЧНО]** — must do, immediate impact on margin/stockouts
**[ВАЖНО]** — significant impact, do within the month
**[ЖЕЛАТЕЛЬНО]** — nice-to-have, optimize if time allows

Format per item: `[PRIORITY] Action — model — expected effect in ₽`

No deadlines. No week numbers. No KPI alarms. Just prioritized actions.
```

- [ ] **Step 3: Update Price CUT guard terminology**

In the "### 1. Validate Key Recommendations" section, replace "M-1% > 20%" with "margin% > 20%" and add a note:

Replace line 42 (`- **Price CUT guard:** REJECT any CUT recommendation where confidence < HIGH (|r| < 0.5) AND model M-1% > 20%. Such models are healthy — do not cut price without strong statistical evidence. Downgrade to HOLD or single-SKU test.`) with:

```markdown
- **Price CUT guard:** REJECT any CUT where confidence < HIGH (|r| < 0.5) AND model margin% > 20%. Healthy models — do not cut without strong evidence. Downgrade to HOLD or single-SKU test.
- **Price decisions framing:** validate that recommendations use turnover + margin logic, not raw elasticity numbers. The reader should see "Overstock 95д, маржа 28% → снизить" not "E=-2.3, r=0.7 → снизить".
```

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/monthly-plan/prompts/cfo.md
git commit -m "refactor(monthly-plan): cfo — action-list summary, no weekly plan"
```

---

### Task 9: Update Synthesizer — new assembly rules

**Files:**
- Modify: `.claude/skills/monthly-plan/prompts/synthesizer.md`

Key changes:
- Reference new 7-section template (not 12-section A-M)
- Toggle headings at all levels
- Single margin
- New quality checks

- [ ] **Step 1: Replace role description and assembly rules**

Replace the entire content of `.claude/skills/monthly-plan/prompts/synthesizer.md` with:

```markdown
# Synthesizer

You are the document assembler for the Wookiee brand monthly plan.

## Your Role

Assemble the final business plan from CFO-approved analyst findings. Your job is ASSEMBLY, not analysis — do not add new analysis, do not change approved numbers.

## Input

**CFO decisions and corrections:**
{{CFO_OUTPUT}}

**Corrected analyst findings:**
{{CORRECTED_FINDINGS}}

**User context:**
{{USER_CONTEXT}}

**Data quality flags:**
{{QUALITY_FLAGS}}

**Document template:**
{{PLAN_STRUCTURE_TEMPLATE}}

## New Document Structure

The document has 7 main sections + Reference (NOT the old A-M structure):

| Section | Source | Content |
|---|---|---|
| 0. Резюме | CFO Section 0 | 5-7 actions, targets, budget |
| 1. Остатки | Inventory analyst (simplified table) | Action-oriented inventory |
| 2. P&L Бренд | P&L analyst (1 scenario) | Plan + M-1 fact, single margin |
| 3. P&L модели | P&L analyst (models) | Plan + M-1 + Δ%, single margin |
| 4. Рекомендации | ALL analysts (merged) | Action table + rationale toggles |
| 5. Реклама | Ad analyst | Efficiency + recommended budget |
| 6. План действий | CFO prioritized list | КРИТИЧНО / ВАЖНО / ЖЕЛАТЕЛЬНО |
| Справочно | All (detailed data) | Fact, ABC, verification, methodology |

## Assembly Rules

1. **Follow the template** — use plan-structure.md as skeleton
2. **Section 0 FIRST** — 5-7 actions, NO explanations
3. **Section 1 = Inventory** — right after summary (not at old position F)
4. **Single margin** — NO M-1/M-2 distinction anywhere. Маржа = includes all ads.
5. **Section 4 = merged recommendations** — combine pricing, ad, inventory, traffic analysts into one table + rationale toggles
6. **1 scenario visible** — recommended budget in Section 5 main view, aggressive in toggle
7. **No weekly plan** — Section 6 is a flat prioritized list
8. **Reference section** — everything else (fact data, ABC, verification, methodology) goes here
9. **Apply CFO corrections** — use corrected values everywhere
10. **Fill every table** — no empty cells where data exists

## Toggle Heading Rules

**ALL headings must be toggle headings in Notion:**
- `## Section title` → Toggle Heading 1
- `### Subsection` → Toggle Heading 2
- `#### Detail` → Toggle Heading 3

Every section is collapsible. The "Справочно" section and all its subsections are collapsed by default.

## Section 4: Merging Recommendations

This is the most complex assembly. Combine outputs from 4 analysts into:

**Main table** (one row per model):
| Модель | Действие по цене | Действие по рекламе | Действие по остаткам | Эффект, тыс.₽ |

Sources:
- Price action → Pricing analyst recommendations
- Ad action → Ad analyst hypotheses
- Inventory action → Inventory analyst actions
- Effect → sum of pricing effect + ad effect estimate

**Rationale toggles** (one toggle per model):
Combine: pricing rationale + ad hypothesis detail + inventory detail + traffic analysis.
Format as readable text, not tables. 3-5 sentences per model.

## Table Formatting Rules

- Revenue values: thousands with space separator (35 390)
- Percentages: 1 decimal (22.8%)
- Bold for totals rows
- Use `—` only for genuinely unavailable data
- Model names capitalized (Wendy, Audrey, etc.)
- **Headers: human-readable Russian, NO abbreviations**
- **Currency: always тыс.₽ or ₽**

## Quality Check Before Finishing

Before outputting, verify:
- [ ] 7 main sections present (0-6 + Справочно)
- [ ] Section 0 has exactly 5-7 actions (count them)
- [ ] Section 1 is Inventory (not P&L)
- [ ] Single margin throughout (search for "М-1", "М-2", "Маржа-1", "Маржа-2" — should be zero occurrences)
- [ ] Section 4 has recommendations for ALL active models
- [ ] Section 5 has 1 visible scenario + 1 toggle scenario
- [ ] Section 6 has prioritized list (no weeks)
- [ ] All toggles specified in template are present
- [ ] Reference section contains fact data, ABC, verification, methodology

## Notion-Enhanced Output

Read `.claude/skills/monthly-plan/templates/notion-formatting-guide.md` for formatting spec.

Key rules:
- ALL tables: `<table fit-page-width="true" header-row="true" header-column="true">`
- Header rows: `<tr color="blue_bg">`
- Total rows: `<tr color="gray_bg">`
- Positive: `<td color="green_bg">` (OK, growth)
- Negative: `<td color="red_bg">` (ДЕФИЦИТ, losses)
- Warning: `<td color="yellow_bg">` (OVERSTOCK, FREEZE)
- Callouts after sections 0, 1, 4, 5
- **ALL section headings → toggle headings**

Write TWO output files:
1. `/tmp/mp-final-document.md` — standard markdown (for git)
2. `/tmp/mp-final-notion.txt` — Notion-enhanced (for Notion publication)
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/monthly-plan/prompts/synthesizer.md
git commit -m "refactor(monthly-plan): synthesizer — new 7-section assembly rules"
```

---

### Task 10: Update SKILL.md — new section references

**Files:**
- Modify: `.claude/skills/monthly-plan/SKILL.md`

Key changes:
- Update document structure description (sections 0-6 + Reference)
- Single margin terminology
- Update synthesizer instructions to reference new structure

- [ ] **Step 1: Replace Document Structure section**

In `.claude/skills/monthly-plan/SKILL.md`, replace the "### Document Structure (plan-first)" section (lines 189-197) with:

```markdown
### Document Structure (action-first)

The document follows this order:
1. **Section 0: Резюме** — 5-7 actions, targets, budget (no explanations)
2. **Section 1: Остатки и оборачиваемость** — action-oriented inventory table
3. **Section 2: P&L Brand — План** — single margin, 1 recommended scenario
4. **Section 3: P&L по моделям** — plan + M-1 fact + Δ%, single margin
5. **Section 4: Рекомендации** — merged table (price + ads + inventory) + rationale toggles
6. **Section 5: Реклама** — efficiency + recommended budget (aggressive in toggle)
7. **Section 6: План действий** — prioritized list (КРИТИЧНО / ВАЖНО / ЖЕЛАТЕЛЬНО)
8. **Справочно** — fact data, ABC, verification, methodology (all in toggles)
```

- [ ] **Step 2: Update CFO responsibilities note**

Replace lines 158-160 (CFO responsibilities):

```markdown
**CFO responsibilities (v3):**
- Generate Section 0: 5-7 actions (no explanations), targets, budget
- Price CUT guard: REJECT any CUT where confidence < HIGH AND margin% > 20%
- Prioritized action list (Section 6): КРИТИЧНО / ВАЖНО / ЖЕЛАТЕЛЬНО — no weekly plan
- Single margin throughout
```

- [ ] **Step 3: Update Notion formatting section**

Replace lines 199-207 (Notion Formatting) with:

```markdown
### Notion Formatting

The Notion version must use:
- `<table>` with `fit-page-width`, `header-row`, `header-column`
- Colored headers (`blue_bg`), totals (`gray_bg`), positive (`green_bg`), negative (`red_bg`), warning (`yellow_bg`)
- `<callout>` blocks after sections 0, 1, 4, 5
- **Toggle headings at ALL levels** (H1, H2, H3, H4 — everything collapsible)
- Human-readable table headers in Russian (no abbreviations)
- Single margin terminology (no М-1/М-2)

See `notion-formatting-guide.md` for full spec.
```

- [ ] **Step 4: Add v3 changelog entry**

Add at the top of the Changelog section:

```markdown
### v3 (2026-04-03)
- UX refactor: from analytics report to management tool
- New 7-section structure (0-6 + Reference) replacing A-M
- Single margin (includes all ads) — no M-1/M-2 distinction
- Section 1 = Inventory (promoted from position F)
- Section 4 = Merged recommendations (replaces D hypotheses + I elasticity)
- Elasticity hidden from output (computed internally for recommendation quality)
- 1 visible ad scenario (aggressive in toggle)
- Prioritized action list replaces weekly plan
- Toggle headings at all levels
- Summary: 5-7 actions without explanations
```

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/monthly-plan/SKILL.md
git commit -m "refactor(monthly-plan): SKILL.md — v3 section refs, single margin, changelog"
```

---

### Task 11: Update Notion formatting guide — toggle heading levels

**Files:**
- Modify: `.claude/skills/monthly-plan/templates/notion-formatting-guide.md`

- [ ] **Step 1: Replace Toggle Headers section**

In `.claude/skills/monthly-plan/templates/notion-formatting-guide.md`, replace the "## Toggle Headers" section (lines 69-70) with:

```markdown
## Toggle Headers

**ALL headings at every level must be toggle headings in Notion:**

- `##` (H2) → Toggle Heading 1 — main sections (0-6 + Справочно)
- `###` (H3) → Toggle Heading 2 — subsections (Разбивка по каналам, Обоснование, Сценарии)
- `####` (H4) → Toggle Heading 3 — details (per-model rationale, fact tables)

Every section is collapsible. The "Справочно" section should be collapsed by default in Notion.

Toggle headings allow the reader to:
1. See the full document outline (all sections collapsed)
2. Expand only the sections they need
3. Navigate quickly to any section
```

- [ ] **Step 2: Update Plan Tables = Fact Tables section**

Replace the "## Plan Tables = Fact Tables" section (lines 72-79) with:

```markdown
## Plan vs Fact Parity

The plan P&L table (Section 2) must have the same detail level as the fact P&L in Reference. Both should have the full waterfall: Revenue, SPP, COGS, logistics, storage, commission, NDS, ads, margin.

Single margin throughout — no M-1/M-2 distinction in any table.
```

- [ ] **Step 3: Update callout placement**

Replace "## When to Add Callouts" section (lines 87-93) with:

```markdown
## When to Add Callouts

- After Section 0 (key metrics highlight)
- After Section 1 (urgent inventory actions)
- After Section 4 (top recommendation summary)
- After Section 5 (ad budget decision)
- After Верификация in Справочно (quality summary)
```

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/monthly-plan/templates/notion-formatting-guide.md
git commit -m "refactor(monthly-plan): notion guide — toggle levels, single margin"
```

---

### Task 12: Regenerate April 2026 plan

**Files:**
- No file modifications — this task runs the skill

After all prompt changes are committed, regenerate the April plan using the updated skill.

- [ ] **Step 1: Verify all 11 files are committed**

```bash
git log --oneline -12
```

Expected: 11 commits from tasks 1-11 plus the spec commit.

- [ ] **Step 2: Run the monthly-plan skill**

Invoke `/monthly-plan` with the April context:

```
/monthly-plan

Месяц: 2026-04
Модели: Wendy, Audrey, Ruby, Vuki, Set Vuki, Moon, Joy, Charlotte, Set Moon, Eva, Bella, Lana, Set Ruby, Set Bella
Новые запуски: нет
Бюджет: внешняя реклама −210К (стоп Eva, сокращение неэффективных)
Контекст: Применяем обратную связь аналитика. Перегенерация с новой структурой.
```

- [ ] **Step 3: Verify output structure**

After generation, check:
1. Document has 7 sections (0-6 + Справочно)
2. Section 0: exactly 5-7 actions
3. Section 1: Inventory (right after summary)
4. Single margin (no М-1/М-2)
5. Section 4: Recommendations table with rationale toggles
6. Section 6: Prioritized list (no weeks)
7. Notion page uses toggle headings

- [ ] **Step 4: Verify Notion rendering**

Check the Notion page:
- All sections are collapsible toggle headings
- Tables have correct colors
- Справочно section is present
- No M-1/M-2 references in main sections

- [ ] **Step 5: Commit the generated MD file**

```bash
git add docs/plans/2026-04-business-plan-generated.md
git commit -m "feat(monthly-plan): regenerate April 2026 plan with v3 structure"
```
