---
name: market-review
description: Monthly market & competitor review — MPStats data collection, LLM analysis, Notion publication. Covers market dynamics, competitor tracking, top model comparison.
triggers:
  - /market-review
  - обзор рынка
  - market review
  - анализ конкурентов
---

# Market Review Skill

Generates a monthly market & competitor analysis report using MPStats API + internal DB + browser research, with HEAVY LLM generating actionable hypotheses.

## Stage 0: Interactive Setup

Ask the user using AskUserQuestion:

**Q1 — Month:**
```
question: "Какой месяц анализировать?"
header: "Месяц"
options:
  - label: "Прошлый месяц (авто)" / description: "Автоматически определяется"
  - label: "Март 2026" / description: "2026-03"
  - label: "Февраль 2026" / description: "2026-02"
  (+ Other для ввода YYYY-MM)
```

**Q2 — Sections (multiSelect):**
```
question: "Какие разделы включить?"
header: "Разделы"
options:
  - "Динамика категорий" — categories
  - "Наши метрики" — our
  - "Конкуренты" — competitors
  - "Наши топ-модели" — models_ours
  - "Аналоги конкурентов" — models_rivals
  - "Новинки" — new_items
All selected by default.
```

Store answers as:
- `month` = "YYYY-MM"
- `sections` = "categories,our,competitors,models_ours,models_rivals,new_items"

## Stage 1: Data Collection

Run the collector orchestrator:

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee
python3 scripts/market_review/collect_all.py \
  --month "{{month}}" \
  --sections "{{sections}}" \
  --output /tmp/market_review_data.json
```

Check exit code:
- Exit 0: all collectors succeeded
- Exit 1: some collectors failed — check `meta.errors`, warn user, continue

## Stage 1.5: Browser Research (Optional)

If browser tools are available (agent-browser or chrome-devtools MCP):

**Instagram Research:**
For each competitor with an Instagram account (from config):
1. Navigate to their Instagram profile
2. Collect last 10-15 posts from the analysis month
3. Note: type (reels/photo/carousel), likes, comments, topic, hook
4. Identify top-engagement posts (above average)

**WB Card Research:**
For competitors in WB_CARD_DEEP_ANALYSIS config:
1. Open their top WB product cards
2. Note: cover image, video, infographics, description structure, UTP

Save browser research results to `/tmp/market_review_browser.json` and merge into main data.

## Stage 2: Verify + Analyze

### 2a. Verification Agent

Launch a background Agent with the verifier prompt:

```
Read prompt from: .claude/skills/market-review/prompts/verifier.md
Replace {{DATA_FILE}} with: /tmp/market_review_data.json
Execute verification checklist.
Report: STATUS, ISSUES, WARNINGS.
```

If STATUS == FAIL: report issues to user and stop.
If STATUS == WARN or PASS: proceed.

### 2b. Analyst Agent

Launch an Agent with the analyst prompt:

```
Read prompt from: .claude/skills/market-review/prompts/analyst.md
Replace placeholders:
  {{DATA_FILE}} = /tmp/market_review_data.json
  {{MONTH_LABEL}} = "Март 2026"
  {{VERIFIER_WARNINGS}} = warnings from 2a (if any)

Tasks:
1. Read JSON data
2. Analyze market dynamics, competitor movements, model comparisons
3. Generate hypotheses with estimated impact
4. Write MD report to: docs/reports/YYYY-MM-market-review.md
5. Publish to Notion page (ID: 2f458a2bd58780648974f98347b2d4d5)
```

## Stage 3: Delivery

After analyst completes:
1. Confirm MD file path
2. Confirm Notion page URL
3. Show summary: key findings + top 3 hypotheses
