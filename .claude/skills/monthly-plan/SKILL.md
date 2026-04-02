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

Launch Synthesizer subagent:
- Input: `cfo_output` + `corrected_findings` + `user_context` + `quality_flags`
- Also inject the plan-structure.md template as the output skeleton
- Inject: `{{CFO_OUTPUT}}`, `{{CORRECTED_FINDINGS}}`, `{{USER_CONTEXT}}`, `{{QUALITY_FLAGS}}`, `{{PLAN_STRUCTURE_TEMPLATE}}`
- Save output as `final_document`

## Stage 4: Publication

### 4.1 Save MD file
```bash
# Save to docs/plans/
cat > docs/plans/{PLAN_MONTH}-business-plan-final.md << 'EOF'
{final_document}
EOF
```

### 4.2 Publish to Notion

Use the Notion MCP tool to create a new page in the analytics reports database:
- Database ID: `30158a2b-d587-8091-bfc3-000b83c6b747`
- Title: `Бизнес-план {PLAN_MONTH_NAME} {PLAN_YEAR}`
- Content: `final_document`

Use `mcp__claude_ai_Notion__notion-create-pages` tool.

### 4.3 Publish to Google Sheets

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
