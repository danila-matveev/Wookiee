---
name: financial-overview
description: Generate a comprehensive financial + marketing comparison report between two periods. Collects data from WB/OZON DB, Google Sheets (performance, SMM, bloggers), verifies, and publishes to MD + Notion.
triggers:
  - /financial-overview
  - финансовый обзор
  - financial overview
  - сравнение периодов
---

# Financial Overview Skill

Generates a comparative financial + marketing report for two periods using parallel data collection agents.

## Stage 0: Interactive Setup

Ask the user 3 questions using AskUserQuestion:

**Q1 — Current Period (Period A):**
```
question: "Какой текущий период анализировать?"
header: "Период A"
options:
  - label: "Q1 2026 (янв-мар)" / description: "2026-01-01 : 2026-03-31"
  - label: "Q2 2026 (апр-июн)" / description: "2026-04-01 : 2026-06-30"
  - label: "Последний месяц" / description: "Автоматически определяется"
  (+ Other для ввода custom дат в формате "YYYY-MM-DD : YYYY-MM-DD")
```

**Q2 — Comparison Period (Period B):**
```
question: "С чем сравнить?"
header: "Период B"
options:
  - label: "Предыдущий аналогичный (auto)" / description: "Q1→Q4, месяц→предыдущий месяц"
  - label: "Q4 2025 (окт-дек)" / description: "2025-10-01 : 2025-12-31"
  (+ Other для custom дат)
```

Auto-logic: если Period A — квартал, берём предыдущий квартал. Если месяц — предыдущий месяц. Если custom range — такой же по длительности, сразу перед ним.

**Q3 — Sections (multiSelect):**
```
question: "Какие разделы включить?"
header: "Разделы"
options:
  - "Финансы (ОПИУ)" — finance
  - "Органика WB (воронка)" — organic
  - "Внутренний маркетинг WB/OZON" — ads
  - "Внешний performance" — performance
  - "SMM" — smm
  - "Блогеры" — bloggers
All selected by default.
```

**Q4 — Additional context (open text, optional):**
Ask only if user has notes: "Есть дополнительный контекст? (например, 'март неполный, косвенные ≈ фев + 150K'). Пропусти если нет."

Store answers as:
- `period_a` = "YYYY-MM-DD:YYYY-MM-DD"
- `period_b` = "YYYY-MM-DD:YYYY-MM-DD"
- `period_a_label` = "Q1 2026"
- `period_b_label` = "Q4 2025"
- `sections` = "finance,organic,ads,performance,smm,bloggers"
- `user_context` = free text or empty

## Stage 1: Data Collection

Run the collector orchestrator:

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee
python3 scripts/financial_overview/collect_all.py \
  --period-a "{{period_a}}" \
  --period-b "{{period_b}}" \
  --sections "{{sections}}" \
  --output /tmp/financial_overview_data.json
```

Check exit code:
- Exit 0: all collectors succeeded
- Exit 1: some collectors failed — check `meta.errors` in output, warn user, continue with available data

## Stage 2: Verify + Synthesize

### 2a. Verification Agent

Launch a background Agent with the verifier prompt:

```
Read the prompt template from: .claude/skills/financial-overview/prompts/verifier.md
Replace {{DATA_FILE}} with: /tmp/financial_overview_data.json
Execute the verification checklist.
Report: STATUS, ISSUES, WARNINGS.
```

If STATUS == FAIL: report issues to user and stop.
If STATUS == WARN or PASS: proceed.

### 2b. Synthesizer Agent

Launch an Agent with the synthesizer prompt:

```
Read the prompt template from: .claude/skills/financial-overview/prompts/synthesizer.md
Replace placeholders:
  {{DATA_FILE}} = /tmp/financial_overview_data.json
  {{USER_CONTEXT}} = user_context from Stage 0
  {{PERIOD_A_LABEL}} = period_a_label
  {{PERIOD_B_LABEL}} = period_b_label
  {{SECTIONS}} = sections
  {{VERIFIER_WARNINGS}} = warnings from 2a (if any)

Tasks:
1. Read JSON data
2. Compute all comparisons (deltas, percentages, weighted averages)
3. Write MD report to: docs/reports/{{period_a_label}}-vs-{{period_b_label}}-overview.md
4. Publish to Notion with proper Notion-flavored markdown tables and callouts
```

## Stage 3: Delivery

After synthesizer completes:
1. Confirm MD file path to user
2. Confirm Notion page URL
3. Show a brief summary table with key metrics
