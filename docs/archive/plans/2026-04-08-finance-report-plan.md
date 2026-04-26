# /finance-report Deep Module — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `/finance-report` — a deep financial analytics skill with Oleg v2 depth (14 sections), analytics engine (detect→diagnose→strategize), and Notion publication in Q4vsQ1 format.

**Architecture:** SKILL.md orchestrator → collect data (existing collector) → Wave A (financial detector) → Wave B (diagnostician) → Wave C (strategist) → 2 analysts (WB deep + OZON deep) in parallel → verifier → synthesizer → Notion. Each subagent reads unified analytics-kb.md.

**Tech Stack:** Claude Code skills (SKILL.md + prompts), Python 3.9+ (collector already exists), Notion MCP

**Spec:** `docs/superpowers/specs/2026-04-08-modular-analytics-v2-design.md` (sections 3 + 4.1)
**Etalon:** Oleg v2 daily report `32a58a2bd58781918abcf1d855f07b90`
**KB:** `.claude/skills/analytics-report/references/analytics-kb.md`

---

## File Map

### Skill Files (`.claude/skills/finance-report/`)

| File | Responsibility |
|---|---|
| `SKILL.md` | Orchestrator: 5 stages, placeholder injection, wave dispatch |
| `prompts/detector.md` | Wave A: Financial detector — find all significant Δ |
| `prompts/diagnostician.md` | Wave B: Diagnose causes for each finding |
| `prompts/strategist.md` | Wave C: Formulate P0-P3 actions |
| `prompts/wb-analyst.md` | Deep WB P&L + model decomposition + funnel + cost structure |
| `prompts/ozon-analyst.md` | Deep OZON P&L + model decomposition |
| `prompts/verifier.md` | CFO + data quality verification |
| `prompts/synthesizer.md` | Assemble 14-section Notion-formatted report |

### Shared Resources (already exist)

| File | Used for |
|---|---|
| `.claude/skills/analytics-report/references/analytics-kb.md` | Knowledge Base — all subagents read this |
| `.claude/skills/analytics-report/references/data-sources.md` | Data source documentation |
| `.claude/skills/analytics-report/templates/notion-formatting-guide.md` | Notion formatting rules |
| `scripts/analytics_report/collect_all.py` | Data collection (8 parallel collectors) |

---

## Task 1: SKILL.md Orchestrator

**Files:**
- Create: `.claude/skills/finance-report/SKILL.md`

- [ ] **Step 1: Create directory and write SKILL.md**

Create `.claude/skills/finance-report/SKILL.md` with this structure:

```yaml
---
name: finance-report
description: Deep financial analytics for Wookiee brand (WB+OZON) — P&L funnel, model decomposition, cost structure, unit economics, ΔMargin reconciliation
triggers:
  - /finance-report
  - финансовый отчёт
  - фин анализ
---
```

**Content structure (follow monthly-plan SKILL.md pattern):**

**Quick Start:**
```
/finance-report 2026-04-05                     → дневной
/finance-report 2026-03-30 2026-04-05           → недельный  
/finance-report 2026-03-01 2026-03-31           → месячный
```

**Stage 0: Parse Arguments** — same as analytics-report: 1 date=daily, 2 dates=auto depth. No questions asked.

**Stage 1: Data Collection** — run `python3 scripts/analytics_report/collect_all.py --start {START} --end {END} --output /tmp/finance-report-{START}_{END}.json`. Read JSON, check errors.

**Stage 2: Analytics Engine (3 waves)**

*Wave A:* Read `prompts/detector.md`. Launch detector subagent with full finance+inventory+pricing data from JSON + analytics-kb.md content. Save output as `findings_raw`.

*Wave B:* Read `prompts/diagnostician.md`. Launch diagnostician with `findings_raw` + relevant raw data slices. Save as `diagnostics`.

*Wave C:* Read `prompts/strategist.md`. Launch strategist with `findings_raw` + `diagnostics`. Save as `hypotheses`.

**Stage 3: Deep Analysis (2 analysts in parallel)**

Read `prompts/wb-analyst.md` and `prompts/ozon-analyst.md`. Launch BOTH in parallel (2 Agent calls in single message):
- WB analyst gets: finance.wb_total + finance.wb_models + inventory + pricing + traffic.wb + advertising.wb + sku_statuses + findings_raw + diagnostics + hypotheses + analytics-kb.md
- OZON analyst gets: finance.ozon_total + finance.ozon_models + advertising.ozon + sku_statuses + findings_raw + diagnostics + hypotheses + analytics-kb.md

Save: `wb_deep`, `ozon_deep`

**Stage 4: Verification**

Read `prompts/verifier.md`. Launch verifier with `wb_deep` + `ozon_deep` + `findings_raw` + `hypotheses`.
Verdict: APPROVE/CORRECT/REJECT. If REJECT → re-run failing analyst → re-verify (max 1 retry).

**Stage 5: Synthesis + Publication**

Read `prompts/synthesizer.md` + `notion-formatting-guide.md`.
Launch synthesizer with ALL outputs + analytics-kb.md.
Produces `final_document_notion` — full 14-section Notion-formatted report.

Save MD: `docs/reports/{START}_{END}_finance.md`
Publish Notion: database `30158a2b-d587-8091-bfc3-000b83c6b747`, Тип="Ежедневный/Еженедельный/Ежемесячный фин анализ", Источник="Claude Code"

**CRITICAL:** Publish FULL report to Notion — all 14 sections with HTML tables, callouts, colors per notion-formatting-guide.md. Never abbreviate.

Chat summary: 5-7 lines + Notion link.

- [ ] **Step 2: Commit**

```bash
mkdir -p .claude/skills/finance-report/prompts
git add .claude/skills/finance-report/SKILL.md
git commit -m "feat(finance-report): add SKILL.md orchestrator (5 stages, analytics engine)"
```

---

## Task 2: Wave A — Financial Detector Prompt

**Files:**
- Create: `.claude/skills/finance-report/prompts/detector.md`

- [ ] **Step 1: Write detector prompt**

This subagent scans ALL financial data and finds significant changes. It answers: "ЧТО изменилось?"

**Prompt content must include:**

Role: Financial change detector for Wookiee brand.

Input placeholders: `{{DATA}}` (full finance+inventory+pricing JSON), `{{DEPTH}}`, `{{PERIOD_LABEL}}`, `{{PREV_PERIOD_LABEL}}`

Instructions to read: `.claude/skills/analytics-report/references/analytics-kb.md`

**Scanning protocol (from spec section 3 Wave A):**
1. Brand level: scan all P&L metrics (revenue, margin, COGS, logistics, storage, commission, NDS, ads internal, ads external)
2. Channel level: WB and OZON separately — same metrics
3. Model level: ALL models from sku_statuses — margin, marginality%, orders, COGS, DRR
4. Article level: significant article-level changes (Δ>30% in orders or margin)
5. Cost structure: compute each expense as % of revenue, flag Δ >3 п.п.
6. Inventory: flag DEFICIT (<14d), OVERSTOCK (>90d), DEAD_STOCK (>250d)

**Significance thresholds:**
- Weekly: Δ доли >3 п.п. OR Δ >50К₽ in absolute value
- Daily: Δ доли >3 п.п. OR Δ >10К₽
- Monthly: Δ доли >2 п.п. OR Δ >100К₽

**Output format:**
```
FINDINGS:
1. {severity: HIGH/MEDIUM, level: brand/channel/model/article, object: "Audrey WB", metric: "margin", current: 175000, previous: 309000, delta: -134000, delta_pct: -43.3%, context: "adv_external +45K without order growth"}
2. ...

COST_STRUCTURE_CHANGES:
{metric: "COGS%", wb_current: 17.5%, wb_previous: 21.0%, delta_pp: -3.5, ozon_current: ..., ...}
...

INVENTORY_ALERTS:
{model: "Wendy", channel: "OZON", days: 11, status: "DEFICIT", daily_sales: 31.6}
...
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/finance-report/prompts/detector.md
git commit -m "feat(finance-report): add financial detector prompt (Wave A)"
```

---

## Task 3: Wave B — Diagnostician Prompt

**Files:**
- Create: `.claude/skills/finance-report/prompts/diagnostician.md`

- [ ] **Step 1: Write diagnostician prompt**

This subagent receives findings from Wave A and diagnoses causes. It answers: "ПОЧЕМУ это произошло?"

Input: `{{FINDINGS}}` (from Wave A), `{{RAW_DATA}}` (relevant data slices for drill-down), `{{DEPTH}}`

Instructions to read analytics-kb.md, especially sections on causal patterns and diagnostics.

**Diagnostic protocol (from spec section 3 Wave B):**
For each HIGH/MEDIUM finding, apply cause-finding logic:
- Margin fell → check: price changed? COGS grew? Ads grew? Logistics?
- Orders fell → check: traffic fell? CR fell? OOS (no sizes)? Competition?
- DRR grew → check: budget increased? CPO grew? Ad orders fell?
- CR cart→order fell → check: price rose? Sizes ended? Delivery slowed?

**₽ effect calculation:**
For each finding: "if metric restored to previous level → +X₽ margin"
Formula: `effect = abs(current_margin - hypothetical_margin_with_restored_metric)`

**Output format:**
```
DIAGNOSTICS:
1. {finding_id: 1, cause: "Audrey: adv_external +45K (bloger) without proportional order growth. Orders -32% across both channels.", confidence: HIGH, effect_rub: 134000, related_findings: [3, 7]}
2. ...
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/finance-report/prompts/diagnostician.md
git commit -m "feat(finance-report): add diagnostician prompt (Wave B)"
```

---

## Task 4: Wave C — Strategist Prompt

**Files:**
- Create: `.claude/skills/finance-report/prompts/strategist.md`

- [ ] **Step 1: Write strategist prompt**

This subagent formulates actions. It answers: "ЧТО ДЕЛАТЬ?"

Input: `{{FINDINGS}}`, `{{DIAGNOSTICS}}`, `{{DEPTH}}`

Instructions to read analytics-kb.md, especially price logic decision tree, ad efficiency matrix, inventory thresholds.

**Output format (from spec):**
```
HYPOTHESES:
1. {priority: P0, object: "Wendy OZON", fact: "DEFICIT 11 days, OOS in 3-4 days", cause: "Daily sales 31.6 units vs 361 units stock", action: "Urgent shipment 700-900 units to OZON FBO", metric: "stock_days", base: 11, target: 30, effect_rub: 400000, window: "3 days", risks: "Shipping delay, OZON acceptance time"}
2. ...
```

Sort by |effect_rub| descending. Tag each with financial vs marketing vs operational.

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/finance-report/prompts/strategist.md
git commit -m "feat(finance-report): add strategist prompt (Wave C)"
```

---

## Task 5: WB Deep Analyst Prompt

**Files:**
- Create: `.claude/skills/finance-report/prompts/wb-analyst.md`

- [ ] **Step 1: Write WB analyst prompt**

This is the most important prompt — it generates sections VII (WB deep) + IX (Drivers) + X (Anti-drivers) of the report. Must match Oleg v2 depth.

Input: `{{WB_DATA}}` (finance.wb_total + wb_models + wb_articles), `{{INVENTORY}}`, `{{PRICING}}`, `{{TRAFFIC_WB}}`, `{{ADVERTISING_WB}}`, `{{SKU_STATUSES}}`, `{{FINDINGS}}`, `{{DIAGNOSTICS}}`, `{{HYPOTHESES}}`, `{{DEPTH}}`, `{{PERIOD_LABEL}}`, `{{PREV_PERIOD_LABEL}}`

Instructions to read analytics-kb.md.

**Sections to produce (matching Oleg v2 etalon exactly):**

**Section VII.1: Объём и прибыльность WB**
P&L table: маржа, маржинальность%, продажи шт/₽, заказы шт/₽, реклама внутр/внешн, ДРР от заказов/продаж, СПП% — all with Δ abs and Δ%
+ Interpretation (3-5 lines)

**Section VII.2: Модельная декомпозиция WB**
Table with ALL models (from sku_statuses), columns:
Model | Маржа₽ | МаржаΔ% | Маржинальность% | Остаток FBO | Свой склад (МойСклад) | В пути | Итого остаток | Оборач.(FBO) | Оборач.(все) | ROI год% | ДРР продаж% | Комментарий

Group by status: Продается / Выводим / Архив / Запуск
+ Interpretation per group

**Section VII.3: Воронка WB**
Table A — Volume: показы, переходы, корзина, заказы — тек/пред/Δ%
Table B — Efficiency: CTR, CR переход→корзина, CR корзина→заказ — тек/пред/Δ п.п.
+ Interpretation

**Section VII.4: Факторное разложение заказов WB**
Table: Фактор | Вклад (шт) | Формула | Вывод
Factors: за счёт показов (охват), за счёт CTR (привлекательность), за счёт конверсии (карточка→заказ)

**Section VII.5: Структура затрат WB**
Table: Статья | Текущий% | Прошлый% | Δ п.п. | Комментарий
Rows: комиссия до СПП, логистика, хранение, ДРР(вся), себестоимость, прочие, маржинальность

**Section VII.6: Реклама WB**
Table A — итоги: расходы внутр/внешн, ДРР внутр/внешн — тек/пред/Δ
Table B — детали: показы, клики, CTR%, CPC₽, CPM₽, CPO₽, расход₽ — тек/пред/Δ%
+ Interpretation

**Section IX: Драйверы WB**
Table: Model | Доля продаж | ΔМаржа | Маржа(тек) | Маржинальность% | ΔМаржинальность | ΔПродажи₽ | ΔЗаказы₽ | ДРР продаж | ДРР заказов | Внутр.рекл | Внешн.рекл | Комментарий
Top 5 models by positive ΔМаржа

**Section X: Антидрайверы WB**
Same table, top 5 by negative ΔМаржа

**Hard rules (from KB):**
- WB margin = marga - nds - reclama_vn - reclama_vn_vk - reclama_vn_creators
- GROUP BY LOWER()
- DRR always split internal/external
- Numbers: `1 234 567 ₽`, `24.1%`, `+3.2 п.п.`
- Tone: dry CFO, facts + ₽ effect

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/finance-report/prompts/wb-analyst.md
git commit -m "feat(finance-report): add WB deep analyst prompt (P&L, models, funnel, cost structure)"
```

---

## Task 6: OZON Deep Analyst Prompt

**Files:**
- Create: `.claude/skills/finance-report/prompts/ozon-analyst.md`

- [ ] **Step 1: Write OZON analyst prompt**

Same structure as WB analyst but for OZON. Produces sections VIII + XI.

Key differences from WB:
- OZON margin = marga - nds (no separate external ad deduction)
- No factored order decomposition (organic funnel unavailable)
- OZON organic data = 0 — mark as unavailable
- OZON has 34 commission types (aggregated in abc_date)

Sections:
- VIII.1: Объём и прибыльность OZON
- VIII.2: Модельная декомпозиция OZON (same columns as WB)
- VIII.3: Воронка OZON (ad only, organic unavailable)
- VIII.4: Структура затрат OZON
- VIII.5: Реклама OZON
- XI: Драйверы/Антидрайверы OZON

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/finance-report/prompts/ozon-analyst.md
git commit -m "feat(finance-report): add OZON deep analyst prompt"
```

---

## Task 7: Verifier Prompt

**Files:**
- Create: `.claude/skills/finance-report/prompts/verifier.md`

- [ ] **Step 1: Write verifier prompt**

Combined CFO + data quality critic. Checks:

1. **Arithmetic:** sum models = brand total ±1%. WB + OZON = Brand ±1%.
2. **Margin formulas:** WB uses correct formula. OZON uses correct formula. Single margin (no M-1/M-2).
3. **DRR split:** internal + external always separate.
4. **SPP:** weighted average when combining channels.
5. **GROUP BY LOWER():** no model duplicates.
6. **Buyout %:** not used as daily cause (depth=day).
7. **Shares sum:** commission% + logistics% + storage% + COGS% + ads% + NDS% + margin% ≈ 100% (±2%)
8. **Coverage:** every HIGH finding has a recommendation.
9. **Direction:** action matches problem (DEFICIT→restock, not lower price).
10. **Number accuracy:** text numbers match data ±1%.

Verdict: APPROVE / CORRECT (with corrections) / REJECT (with re-run list, max 1)

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/finance-report/prompts/verifier.md
git commit -m "feat(finance-report): add CFO verifier prompt"
```

---

## Task 8: Synthesizer Prompt

**Files:**
- Create: `.claude/skills/finance-report/prompts/synthesizer.md`

- [ ] **Step 1: Write synthesizer prompt**

Assembles the final 14-section report in Notion format.

Input: `{{WB_DEEP}}`, `{{OZON_DEEP}}`, `{{FINDINGS}}`, `{{DIAGNOSTICS}}`, `{{HYPOTHESES}}`, `{{CFO_VERDICT}}`, `{{DEPTH}}`, `{{PERIOD_LABEL}}`, `{{PREV_PERIOD_LABEL}}`, `{{NOTION_GUIDE}}`

Instructions to read: analytics-kb.md, notion-formatting-guide.md

**14 sections to assemble:**
- I. Паспорт отчёта (generate from metadata)
- II. Топ-выводы (from hypotheses, sort by |effect_rub|)
- III. План-факт (from plan_fact data)
- IV. Ключевые изменения бренда (compute from WB+OZON combined)
- V. Цены, СПП, стратегия (from pricing data)
- VI. Сведение ΔМаржи (compute waterfall from findings)
- VII. Wildberries deep (from wb_deep — pass through)
- VIII. OZON deep (from ozon_deep — pass through)
- IX. Драйверы WB (from wb_deep)
- X. Антидрайверы WB (from wb_deep)
- XI. Драйверы/Антидрайверы OZON (from ozon_deep)
- XII. Гипотезы → Действия (from hypotheses, financial only)
- XIII. Advisor (from hypotheses, grouped by 🔴🟡🟢)
- XIV. Итог (synthesize: что/почему/что двигало/что делать)

**Notion formatting rules:**
- ALL tables: `<table fit-page-width="true" header-row="true" header-column="true">`
- Row colors: blue_bg headers, gray_bg totals, green_bg positive, red_bg negative
- Cell colors for Δ values
- Callout blocks after key sections
- Section headers with Roman numerals: `## I. Паспорт отчёта`
- Toggle headings where appropriate
- Numbers: `1 234 567 ₽`, `24,1%`

**TWO outputs:**
1. `final_document_md` — standard markdown (for git)
2. `final_document_notion` — Notion-enhanced (for publication)

**CRITICAL:** Apply ALL CFO corrections before output. No section can be empty.

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/finance-report/prompts/synthesizer.md
git commit -m "feat(finance-report): add synthesizer prompt (14-section Notion report)"
```

---

## Task 9: E2E Test Run

**Files:** No new files — testing full pipeline.

- [ ] **Step 1: Run collector**

```bash
python3 scripts/analytics_report/collect_all.py --start 2026-03-30 --end 2026-04-05 --output /tmp/finance-report-test.json
```

- [ ] **Step 2: Invoke the skill**

```
/finance-report 2026-03-30 2026-04-05
```

- [ ] **Step 3: Verify output**

Check:
1. MD file at `docs/reports/2026-03-30_2026-04-05_finance.md`
2. Notion page created with ALL 14 sections
3. HTML tables with colors (not markdown tables)
4. Callout blocks present
5. Model decomposition has ALL models from Supabase
6. Factored order decomposition present (section VII.4)
7. Cost structure as % with Δ п.п. (section VII.5)
8. Drivers/Anti-drivers with full table (sections IX-XI)
9. Hypotheses sorted by |₽ effect| (section XII)

---

## Summary

| Task | What | Files | Commits |
|---|---|---|---|
| 1 | SKILL.md orchestrator | 1 create | 1 |
| 2 | Detector prompt (Wave A) | 1 create | 1 |
| 3 | Diagnostician prompt (Wave B) | 1 create | 1 |
| 4 | Strategist prompt (Wave C) | 1 create | 1 |
| 5 | WB deep analyst prompt | 1 create | 1 |
| 6 | OZON deep analyst prompt | 1 create | 1 |
| 7 | Verifier prompt | 1 create | 1 |
| 8 | Synthesizer prompt | 1 create | 1 |
| 9 | E2E test | 0 create | 0 |
| **Total** | | **8 files** | **8 commits** |
