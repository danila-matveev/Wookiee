---
name: monthly-plan
description: Generate monthly business plan for Wookiee brand using multi-wave agent architecture
triggers:
  - /monthly-plan
  - monthly plan
  - месячный план
  - бизнес-план месяц
---

# Monthly Plan Skill

Generates a verified monthly business plan for the Wookiee brand using a multi-wave agent architecture: 5 analysts, 2 critics, corrector, CFO, synthesizer.

## Quick Start (перезапуск)

```
/monthly-plan
```

Скилл задаст 5 вопросов (Stage 0) и запустит пайплайн автоматически.

**Для ускорения** — передай ответы сразу в сообщении:

```
/monthly-plan

Месяц: 2026-05
Модели: Wendy, Audrey, Ruby, Vuki, Set Vuki, Moon, Joy, Charlotte, Set Moon, Eva, Bella, Lana, Set Ruby, Set Bella
Новые запуски: нет
Бюджет: внешняя реклама +100К на Charlotte
Контекст: Майские праздники, сезонный рост спроса на базовое бельё
```

**Время выполнения:** ~30-40 минут (коллектор ~30с, 5 аналитиков ~8м, критики ~6м, корректор+CFO ~6м, синтезайзер ~14м, публикация ~3м)

**Результаты:**
- MD: `docs/plans/{YYYY-MM}-business-plan-generated.md`
- Notion: страница в "Аналитические отчеты" (database `30158a2b-d587-8091-bfc3-000b83c6b747`)

---

## Stage 0: Context Collection

Ask the user these 5 questions using AskUserQuestion (one at a time or combined):

1. **Plan month**: "На какой месяц строим план? (формат YYYY-MM, например 2026-05)"
2. **Model lineup**: "Какие модели активны? Есть изменения статусов с прошлого месяца?"
3. **New launches**: "Планируются новинки или новые SKU? На каком этапе производства?"
4. **Budget limits**: "Есть ограничения по рекламному бюджету, производству или закупкам?"
5. **Strategic context**: "Что ещё учесть? Сезонность, акции WB/OZON, изменения в команде?"

Save all answers as `user_context` (will be passed to all subagents):
```
user_context = """
Месяц планирования: {answer_1}
Активные модели: {answer_2}
Новые запуски: {answer_3}
Бюджетные ограничения: {answer_4}
Стратегический контекст: {answer_5}
"""
```

## Stage 1: Data Collection

Run the Python collector:
```bash
python scripts/monthly_plan/collect_all.py --month {PLAN_MONTH} --output /tmp/monthly-plan-{PLAN_MONTH}-data.json
```

Read the output:
```bash
cat /tmp/monthly-plan-{PLAN_MONTH}-data.json
```

Save the full JSON as `data_bundle`. Note any errors from `data_bundle["meta"]["errors"]`.

If collector fails entirely: report error to user and stop.

## Stage 1.5: Triage

Read the triage prompt template:
- Read `.claude/skills/monthly-plan/prompts/triage.md`

Run triage as a subagent (Agent tool):
- Pass the triage prompt with `{{DATA_BUNDLE}}` replaced by the full JSON
- The subagent will return either "NO_ANOMALIES" or a list of 1-5 questions

If the triage subagent returns questions, ask them to the user via AskUserQuestion.
Add answers to `user_context`.

## Stage 2: Multi-Wave Analysis

### Wave 1: 5 Analysts (launch in parallel using 5 separate Agent calls in a single message)

For each analyst, read their prompt file and launch as a subagent:

**P&L Analyst** — Read `.claude/skills/monthly-plan/prompts/analysts/pnl-analyst.md`
- Data slice: `data_bundle["pnl_total"]` + `data_bundle["pnl_models"]`
- Summary of other blocks: meta, advertising totals, inventory risks summary
- Inject: `{{DATA_SLICE}}`, `{{USER_CONTEXT}}`, `{{QUALITY_FLAGS}}`, `{{BASE_MONTH}}`, `{{PREV_MONTH}}`
- Save output as `pnl_findings`

**Pricing Analyst** — Read `.claude/skills/monthly-plan/prompts/analysts/pricing-analyst.md`
- Data slice: `data_bundle["pricing"]` + pnl_models summary (margin per model only)
- Inject: `{{DATA_SLICE}}`, `{{USER_CONTEXT}}`, `{{QUALITY_FLAGS}}`
- Save output as `pricing_findings`

**Ad Analyst** — Read `.claude/skills/monthly-plan/prompts/analysts/ad-analyst.md`
- Data slice: `data_bundle["advertising"]` + pnl_models summary (revenue + margin per model) + `data_bundle["sheets"]["external_ads_detailed"]`
- Inject: `{{DATA_SLICE}}`, `{{USER_CONTEXT}}`, `{{QUALITY_FLAGS}}`
- Save output as `ad_findings`

**Inventory Analyst** — Read `.claude/skills/monthly-plan/prompts/analysts/inventory-analyst.md`
- Data slice: `data_bundle["inventory"]` + `data_bundle["abc"]` + `data_bundle["sheets"]["financier_plan"]`
- Inject: `{{DATA_SLICE}}`, `{{USER_CONTEXT}}`, `{{QUALITY_FLAGS}}`
- Save output as `inventory_findings`

**Traffic Analyst** — Read `.claude/skills/monthly-plan/prompts/analysts/traffic-analyst.md`
- Data slice: `data_bundle["traffic"]` + pnl_models summary (model names + revenue only)
- Inject: `{{DATA_SLICE}}`, `{{USER_CONTEXT}}`, `{{QUALITY_FLAGS}}`
- Save output as `traffic_findings`

Wait for all 5 analysts to complete.

### Wave 2: 2 Critics (launch in parallel)

**Data Quality Critic** — Read `.claude/skills/monthly-plan/prompts/critics/data-quality-critic.md`
- Input: all 5 analyst findings concatenated
- Inject: `{{ALL_ANALYST_FINDINGS}}`, `{{QUALITY_FLAGS}}`
- Save output as `dq_critic_findings`

**Strategy Critic** — Read `.claude/skills/monthly-plan/prompts/critics/strategy-critic.md`
- Input: all 5 analyst findings concatenated
- Inject: `{{ALL_ANALYST_FINDINGS}}`, `{{USER_CONTEXT}}`
- Save output as `strategy_critic_findings`

Wait for both critics.

### Wave 3: Corrector

Read `.claude/skills/monthly-plan/prompts/corrector.md`

Launch Corrector subagent:
- Input: all 5 analyst findings + both critic findings
- Inject: `{{ALL_ANALYST_FINDINGS}}`, `{{DQ_CRITIC}}`, `{{STRATEGY_CRITIC}}`
- Save output as `corrected_findings` (includes CFO question list)

### Wave 4: CFO (Pass 1)

Read `.claude/skills/monthly-plan/prompts/cfo.md`

Launch CFO subagent:
- Input: corrected_findings + both critic findings + user_context
- Inject: `{{CORRECTED_FINDINGS}}`, `{{CRITIC_NOTES}}`, `{{USER_CONTEXT}}`
- Save output as `cfo_output`

**CFO responsibilities (v3):**
- Generate Section 0: 5-7 actions (no explanations), targets, budget
- Price CUT guard: REJECT any CUT where confidence < HIGH AND margin% > 20%
- Prioritized action list (Section 6): КРИТИЧНО / ВАЖНО / ЖЕЛАТЕЛЬНО — no weekly plan
- Single margin throughout

**CFO Verdict handling:**

If `cfo_output` contains `"verdict": "APPROVE"` or `"verdict": "CORRECT"`:
- Proceed to Stage 3

If `cfo_output` contains `"verdict": "REJECT"`:
- This is Pass 2 (last chance)
- Re-run only the analysts listed in `rerun_analysts`
- Re-run Data Quality Critic on the new outputs
- Re-run Corrector
- Re-run CFO — **CFO must APPROVE or CORRECT on Pass 2, no further REJECT**
- Proceed to Stage 3

## Stage 3: Synthesis

Read `.claude/skills/monthly-plan/prompts/synthesizer.md`
Also read `.claude/skills/monthly-plan/templates/plan-structure.md`
Also read `.claude/skills/monthly-plan/templates/notion-formatting-guide.md`

Launch Synthesizer subagent:
- Input: `cfo_output` + `corrected_findings` + `user_context` + `quality_flags`
- Also inject the plan-structure.md template as the output skeleton
- Inject: `{{CFO_OUTPUT}}`, `{{CORRECTED_FINDINGS}}`, `{{USER_CONTEXT}}`, `{{QUALITY_FLAGS}}`, `{{PLAN_STRUCTURE_TEMPLATE}}`
- **Produce TWO outputs:**
  1. `final_document_md` — standard markdown (for git/docs)
  2. `final_document_notion` — Notion-enhanced format (for Notion publication)

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

### Notion Formatting

The Notion version must use:
- `<table>` with `fit-page-width`, `header-row`, `header-column`
- Colored headers (`blue_bg`), totals (`gray_bg`), positive (`green_bg`), negative (`red_bg`), warning (`yellow_bg`)
- `<callout>` blocks after sections 0, 1, 4, 5
- **Toggle headings at ALL levels** (H1, H2, H3, H4 — everything collapsible)
- Human-readable table headers in Russian (no abbreviations)
- Single margin terminology (no М-1/М-2)

See `notion-formatting-guide.md` for full spec.

## Stage 4: Publication

### 4.1 Save MD file
```bash
# Save to docs/plans/
cat > docs/plans/{PLAN_MONTH}-business-plan-generated.md << 'EOF'
{final_document_md}
EOF
```

### 4.2 Publish to Notion

Use the Notion MCP tool to create a new page in the analytics reports database:
- Database ID (data_source_id): `30158a2b-d587-8091-bfc3-000b83c6b747`
- Title: `Бизнес-план {PLAN_MONTH_NAME} {PLAN_YEAR}`
- **CRITICAL: Publish the FULL `final_document_notion` content** — all sections with all tables and data. Do NOT publish a summary or abbreviated version.
- Properties: Тип анализа = "Бизнес-план", Источник = "Claude Code", Статус = "Актуальный", Период начала = first day of plan month, Период конца = last day of plan month, Корректность = "Да"

Use `mcp__claude_ai_Notion__notion-create-pages` tool with `parent.type = "data_source_id"`.

### 4.3 Publish to Google Sheets (optional)

Add a new sheet tab to KPI_PlanFact:
```bash
gws sheets create-tab "1GRCGSAJESSDvAhoVMmXljXy-qErMKt-n45PV96YBiVY" "📋 План {PLAN_MONTH_NAME} {PLAN_YEAR}"
```

Write key metrics from the plan (Revenue, Маржа-1, Маржа-2, DRR by scenario).

## Completion

Report to user:
- Total time taken
- CFO verdict (Pass 1 or Pass 2)
- Files created (MD path, Notion URL, Sheets tab)
- Any data quality flags that affected the analysis
- Key CFO decisions summary (3-5 bullets)

---

## Changelog

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

### v2 (2026-04-02)
- Added Section 0 (plan summary) — document opens with targets, not retrospective
- Plan-first structure: A = Plan P&L, B = Plan models, L = Fact (reference)
- Pricing CUT guard: only HIGH confidence (|r|>0.5), never CUT at M-1%>20% without overstock
- CFO generates Section 0 before reviewing analyst findings
- Dual output: MD (git) + Notion-enhanced (native tables, colors, callouts)
- Notion formatting: toggle headers, full-width tables, colored cells, callout blocks
- Human-readable table headers (no abbreviations)

### v1 (2026-04-02)
- Initial release: 5 analysts, 2 critics, corrector, CFO, synthesizer
- Data collector: DB + Google Sheets integration
- Triage stage for anomaly detection
