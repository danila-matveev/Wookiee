# /funnel-report Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the `/funnel-report` skill — deep weekly funnel analysis for WB (переходы→корзина→заказы→выкупы) with per-model toggle sections, CRO as main metric, and actionable recommendations with ₽ effect calculations.

**Architecture:** 3-wave analytics engine (detector → diagnostician → strategist) + per-model analyst → verifier → synthesizer → Notion. Same pipeline as marketing-report but focused on WB sales funnel. Data from `collect_all.py` (blocks: traffic, advertising, finance, sku_statuses).

**Tech Stack:** Claude Code skills (SKILL.md + 6 prompt files), Notion API (sync_report), collect_all.py (Python data collector)

**Reference materials:**
- Spec: `docs/superpowers/specs/2026-04-08-modular-analytics-v2-design.md` (section 4.3)
- Notion etalon: page `32758a2bd58781b394b4e4c4d16dfeba` — "Воронка WB за 10-16 марта 2026"
- Oleg playbook: `agents/oleg/funnel_playbook.md` (194 lines — metrics, benchmarks, CRO formulas)
- Oleg template: `agents/oleg/playbooks/templates/funnel_weekly.md`
- Marketing-report skill: `.claude/skills/marketing-report/` (architecture template)
- Analytics KB: `.claude/skills/analytics-report/references/analytics-kb.md`
- Notion guide: `.claude/skills/analytics-report/templates/notion-formatting-guide.md`

---

## File Structure

```
.claude/skills/funnel-report/
├── SKILL.md                    ← Main orchestrator (Stage 0-5)
└── prompts/
    ├── detector.md             ← Wave A: funnel anomaly detection per model
    ├── diagnostician.md        ← Wave B: root causes + ₽ effect
    ├── strategist.md           ← Wave C: prioritized actions
    ├── model-analyst.md        ← Per-model deep analysis (parallel)
    ├── verifier.md             ← 10 quality checks
    └── synthesizer.md          ← Final report assembly (13 sections)
```

---

### Task 1: Create directory structure

**Files:**
- Create: `.claude/skills/funnel-report/prompts/` (directory)

- [ ] **Step 1: Create the prompts directory**

```bash
mkdir -p .claude/skills/funnel-report/prompts
```

- [ ] **Step 2: Verify**

```bash
ls -la .claude/skills/funnel-report/prompts/
```

Expected: empty directory exists.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/funnel-report/
git commit -m "chore: create funnel-report skill directory structure"
```

---

### Task 2: Write SKILL.md — main orchestrator

**Files:**
- Create: `.claude/skills/funnel-report/SKILL.md`
- Reference: `.claude/skills/marketing-report/SKILL.md` (structural template)

**This is the master orchestrator. It defines:**
- Frontmatter (name, description, triggers)
- Stage 0: Parse Arguments (dates → DEPTH → period labels)
- Stage 1: Data Collection (collect_all.py → JSON, blocks: traffic + advertising + finance + sku_statuses)
- Stage 2: Analytics Engine (3 sequential waves: detector → diagnostician → strategist)
- Stage 3: Deep Analysis (model-analyst subagent — per-model parallel analysis)
- Stage 4: Verification (verifier subagent — 10 checks)
- Stage 5: Synthesis + Publication (synthesizer → MD file → Notion)

- [ ] **Step 1: Write SKILL.md**

Write the file with this exact content:

```markdown
---
name: funnel-report
description: Deep funnel analytics for Wookiee brand WB — per-model funnel (переходы→корзина→заказы→выкупы), CRO as main metric, CR each step with Δ п.п., economics, significant articles, actionable recommendations with ₽ effect
triggers:
  - /funnel-report
  - воронка продаж
  - воронка WB
  - funnel анализ
---

# Funnel Report Skill

Deep WB funnel analytics for the Wookiee brand. Uses a 3-wave analytics engine (detect → diagnose → strategize) + per-model deep analysis before generating a 13-section report with brand overview, per-model toggle sections (funnel + economics + significant articles + analysis), and TOP-3 actions with ₽ effect.

## Quick Start

\`\`\`
/funnel-report 2026-04-05                     → дневной (vs вчера)
/funnel-report 2026-03-30 2026-04-05           → недельный
/funnel-report 2026-03-01 2026-03-31           → месячный
\`\`\`

**Время выполнения:** ~15-25 минут (коллектор ~30с, 3 волны ~6м, модельный аналитик ~8м, верификация ~3м, синтез+публикация ~5м)

**Результаты:**
- MD: `docs/reports/{START}_{END}_funnel.md`
- Notion: страница в "Аналитические отчеты" (database `30158a2b-d587-8091-bfc3-000b83c6b747`)

---

## Stage 0: Parse Arguments

Parse the user's input. No questions asked — infer everything from dates.

**Input patterns:**
- 1 date → daily report (vs previous day)
- 2 dates → auto-detect depth by span

**Depth detection (2 dates):**
- Span <= 14 days → `DEPTH = "week"`
- Span > 14 days → `DEPTH = "month"`

**Compute variables:**

\`\`\`
START = first date (or the single date)
END = second date (or same as START for daily)

If DEPTH == "day":
  PREV_START = START - 1 day
  PREV_END = START - 1 day
  PERIOD_LABEL = "DD.MM.YYYY"
  PREV_PERIOD_LABEL = "DD.MM.YYYY (вчера)"

If DEPTH == "week":
  PREV_START = START - (END - START + 1) days
  PREV_END = START - 1 day
  PERIOD_LABEL = "DD.MM — DD.MM.YYYY"
  PREV_PERIOD_LABEL = "DD.MM — DD.MM.YYYY (пред. неделя)"

If DEPTH == "month":
  PREV_START = same days in previous month
  PREV_END = last day of previous month
  PERIOD_LABEL = "Месяц YYYY"
  PREV_PERIOD_LABEL = "Месяц YYYY (пред. месяц)"
\`\`\`

Save: `START`, `END`, `DEPTH`, `PREV_START`, `PREV_END`, `PERIOD_LABEL`, `PREV_PERIOD_LABEL`.

---

## Stage 1: Data Collection

Run the Python collector:

\`\`\`bash
python3 scripts/analytics_report/collect_all.py --start {START} --end {END} --output /tmp/funnel-report-{START}_{END}.json
\`\`\`

Read the output JSON. Save the full JSON as `data_bundle`.

**Error handling:**
- Check `data_bundle["meta"]["errors"]`
- If 0-3 errors → proceed, note missing blocks as `quality_flags`
- If >3 errors → report to user and STOP
- If collector fails entirely → report error and STOP

**Data blocks used in this skill:**
- `traffic` — WB funnel (card_opens, cart, orders, buyouts) total + by model, organic vs paid
- `advertising` — ad spend, organic vs paid split, WB ad funnel (impressions, clicks, cart, orders)
- `finance` — revenue, margin, DRR by model (WB only)
- `sku_statuses` — model lifecycle statuses (Продается / Выводим / Архив / Запуск)

**Data NOT used (other skills handle these):**
- `external_marketing` → marketing-report
- `plan_fact` → finance-report
- `inventory` → finance-report
- `pricing` → finance-report

---

## Stage 2: Analytics Engine (3 sequential waves)

Three waves run SEQUENTIALLY. Each wave builds on the previous one's output.

### Wave A: Detector

Read prompt: `.claude/skills/funnel-report/prompts/detector.md`
Read knowledge base: `.claude/skills/analytics-report/references/analytics-kb.md`

Launch Detector as a subagent (Agent tool):
- **Input data:** `traffic` + `advertising` + `finance` + `sku_statuses` blocks from `data_bundle`
- **Replace placeholders:**
  - `{{DATA}}` — the 4 data blocks above (JSON)
  - `{{DEPTH}}` — "day" | "week" | "month"
  - `{{PERIOD_LABEL}}` — human-readable current period
  - `{{PREV_PERIOD_LABEL}}` — human-readable previous period
- **Inject:** full analytics-kb.md content as reference context

Save output as `findings_raw`.

### Wave B: Diagnostician

Read prompt: `.claude/skills/funnel-report/prompts/diagnostician.md`

Launch Diagnostician as a subagent (Agent tool):
- **Input data:** `findings_raw` + relevant raw data slices (traffic by model, advertising organic vs paid, finance by model)
- **Replace placeholders:**
  - `{{FINDINGS}}` — full `findings_raw` output
  - `{{RAW_DATA}}` — traffic + advertising + finance from `data_bundle`
  - `{{DEPTH}}` — "day" | "week" | "month"

Save output as `diagnostics`.

### Wave C: Strategist

Read prompt: `.claude/skills/funnel-report/prompts/strategist.md`

Launch Strategist as a subagent (Agent tool):
- **Input data:** `findings_raw` + `diagnostics`
- **Replace placeholders:**
  - `{{FINDINGS}}` — full `findings_raw` output
  - `{{DIAGNOSTICS}}` — full `diagnostics` output
  - `{{DEPTH}}` — "day" | "week" | "month"

Save output as `hypotheses`.

---

## Stage 3: Deep Analysis — Model Analyst

Read prompt: `.claude/skills/funnel-report/prompts/model-analyst.md`

Launch Model Analyst as a subagent (Agent tool):
- **Input data:** ALL data blocks (traffic by model, advertising organic vs paid, finance by model, sku_statuses) + `findings_raw` + `diagnostics` + `hypotheses` + analytics-kb.md
- **Task:** Generate per-model toggle sections for ALL models with status "Продается" or "Запуск" from sku_statuses.

For EACH model, produce:
1. **Воронка** — table: переходы, корзина, заказы, выкупы* + CR each step + Δ п.п. + CRO + CRP
2. **Экономика** — table: выручка, маржа, ДРР, ROMI, доля органики (переходы), доля органики (заказы)
3. **Значимые артикулы** — table: артикул, переходы, заказы, флаги (Δ >30%)
4. **Анализ** — КРИТИЧЕСКАЯ ПРОБЛЕМА or ПОЗИТИВ + ГИПОТЕЗА + расчёт эффекта ₽

Save output as `model_deep`.

---

## Stage 4: Verification

Read prompt: `.claude/skills/funnel-report/prompts/verifier.md`

Launch Verifier as a subagent (Agent tool) with: `model_deep` + `findings_raw` + `hypotheses` + raw data blocks.

**10 checks:**
1. Funnel math: each step <= previous step (no inversions)
2. CRO formula: CRO = orders / card_opens × 100 (must match table values)
3. CRP formula: CRP = buyouts / card_opens × 100 (check buyout lag caveat present)
4. Real models only: all from sku_statuses, no invented names
5. All "Продается" + "Запуск" models present in model sections
6. Effect calculations: correct formula (Δ CRO × переходы × avg_check × margin%)
7. Economics data matches finance block (revenue, margin, DRR)
8. Organic share formula: organic_orders / total_orders × 100
9. Buyout caveat: every buyout mention has "лаг 3-21 дн" note
10. Recommendations are specific: model + metric + base → target + ₽ effect

**Verdict:** APPROVE / CORRECT / REJECT (max 1 retry).

---

## Stage 5: Synthesis + Publication

### 5.1 Synthesis

Read prompt: `.claude/skills/funnel-report/prompts/synthesizer.md`
Read formatting guide: `.claude/skills/analytics-report/templates/notion-formatting-guide.md`

Launch Synthesizer as a subagent (Agent tool) with ALL outputs: `findings_raw` + `diagnostics` + `hypotheses` + `model_deep`.

**Output:** ONE `final_document_md` — clean Markdown for Notion.

### Report Structure (Notion etalon: page 32758a2bd58781b394b4e4c4d16dfeba)

| # | Секция | Содержание |
|---|--------|------------|
| Title | Воронка WB за {PERIOD_LABEL} | Main heading |
| I | Общий обзор бренда | Table: переходы, заказы, выкупы*, выручка, маржа, ДРР — тек vs пред + Δ |
| II-XII | Модель: {Name} — {headline} | Per-model toggle section (воронка + экономика + артикулы + анализ) |
| XIII | Выводы и рекомендации | ТОП-3 действия + общий потенциал роста маржи |

### Formatting Rules

- **ONLY clean Markdown.** NO HTML (`<table>`, `<tr>`, `<callout>` — not supported)
- **Tables:** pipe format `| Col | Col |`. Bold in cells: `**+187К**`
- **Toggle headings:** `## Модель: Name — headline {toggle="true"}` for per-model sections
- **Subsections inside toggle:** tab-indented `### Воронка`, `### Экономика`, `### Значимые артикулы`, `### Анализ`
- **Callouts:** `> ⚠️ text`, `> 💡 text`, `> 📊 text`, `> ✅ text`
- **Numbers:** `1 234 567 ₽`, `24,1%`, `+3,2 п.п.`, `8,8М`
- **Terminology:** Russian ONLY
- **Models:** Title Case (Wendy, not wendy). Only REAL models from sku_statuses
- **Buyout caveat:** `\*Данные по выкупам неполные (лаг 3-21 день)` after every buyout table row
- **CRO = MAIN metric.** Always highlight CRO changes in toggle headlines

### 5.2 Save MD file

Save to `docs/reports/{START}_{END}_funnel.md`.

### 5.3 Publish to Notion

Use `shared.notion_client.NotionClient.sync_report()`:

\`\`\`python
PYTHONPATH=. python3 -c "
import asyncio, os
from dotenv import load_dotenv; load_dotenv()
from shared.notion_client import NotionClient
from pathlib import Path

async def main():
    md = Path('docs/reports/{START}_{END}_funnel.md').read_text()
    client = NotionClient(token=os.getenv('NOTION_TOKEN'), database_id=os.getenv('NOTION_DATABASE_ID'))
    url = await client.sync_report(start_date='{START}', end_date='{END}', report_md=md, report_type='funnel_weekly', source='Claude Code')
    print(f'Published: {url}')

asyncio.run(main())
"
\`\`\`

**report_type mapping:** `day` → "funnel_daily", `week` → "funnel_weekly", `month` → "funnel_monthly"

### 5.4 Verify Notion Rendering

After publishing — fetch page via `mcp__claude_ai_Notion__notion-fetch` and verify:
- Tables render as native table blocks
- Toggle headings work (`{toggle="true"}`)
- Callouts render with icons
- Bold text preserved in table cells
- Buyout caveats visible

---

## Completion

Report to user (5-7 lines):
- Period analyzed and depth
- Verifier verdict
- Number of models analyzed (N "Продается" + M "Запуск")
- Top CRO finding (which model, Δ CRO, effect ₽)
- Top recommendation (model + action + ₽ effect)
- Total growth potential (sum of all TOP-3 effects)
- Files: MD path + Notion link

---

## Prompt Files Reference

| File | Role | Stage |
|------|------|-------|
| `prompts/detector.md` | Funnel anomaly detection — CR each step per model, significant articles | 2A |
| `prompts/diagnostician.md` | Root causes — CRO drop analysis, traffic quality, OOS | 2B |
| `prompts/strategist.md` | CRO restoration actions with ₽ effect | 2C |
| `prompts/model-analyst.md` | Per-model deep toggle sections (funnel + economics + articles + analysis) | 3 |
| `prompts/verifier.md` | 10 funnel-specific checks — math, formulas, models, effects | 4 |
| `prompts/synthesizer.md` | 13-section report assembly: brand overview + per-model toggles + TOP-3 conclusions | 5 |

**External references (read-only):**
- `.claude/skills/analytics-report/references/analytics-kb.md` — unified knowledge base
- `.claude/skills/analytics-report/templates/notion-formatting-guide.md` — Notion formatting spec

---

## Changelog

### v1 (2026-04-12)
- Initial release: 3-wave engine + model analyst + verifier + synthesizer
- Per-model toggle sections with funnel, economics, significant articles, analysis
- CRO as main metric, effect calculations in ₽
- Notion publication with toggle support
```

- [ ] **Step 2: Verify file written**

```bash
wc -l .claude/skills/funnel-report/SKILL.md
```

Expected: ~280 lines.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/funnel-report/SKILL.md
git commit -m "feat(funnel-report): add SKILL.md orchestrator"
```

---

### Task 3: Write detector.md — Wave A funnel anomaly detection

**Files:**
- Create: `.claude/skills/funnel-report/prompts/detector.md`
- Reference: `.claude/skills/marketing-report/prompts/detector.md` (structural template)
- Reference: `agents/oleg/funnel_playbook.md` (metrics, benchmarks)

**This prompt defines the funnel detector subagent that:**
- Scans CR at every funnel step (переходы→корзина→заказы→выкупы) for EVERY model
- Identifies significant articles with >30% change in transitions or orders
- Uses benchmarks from Oleg's playbook
- Outputs per-model findings + per-article flags

- [ ] **Step 1: Write detector.md**

Write `.claude/skills/funnel-report/prompts/detector.md` with this content:

```markdown
# Wave A: Воронковый детектор

> Роль: детектор значимых изменений воронки продаж WB бренда Wookiee (~35-40М₽/мес).
> Задача: найти ВСЕ значимые изменения CR на каждом шаге воронки по КАЖДОЙ модели.
> Вопрос: **ЧТО изменилось в воронке?**
> CRO (переход→заказ) — ГЛАВНАЯ метрика.

---

## Инструкции

**Перед анализом** прочитай Knowledge Base: `.claude/skills/analytics-report/references/analytics-kb.md`.
Особо изучи разделы: Воронка продаж (раздел 11-12), Диагностика аномалий (раздел 18), Лаговые показатели (раздел 6), Бенчмарки.
Соблюдай все жёсткие правила (GROUP BY LOWER(), средневзвешенные %, формат чисел).

---

## Входные данные

- `{{DATA}}` — полный JSON:
  - `traffic.wb_total` — бренд WB итого: переходы, корзина, заказы, выкупы (тек + пред)
  - `traffic.wb_by_model` — per-model: переходы, корзина, заказы, выкупы (тек + пред), по КАЖДОМУ артикулу
  - `traffic.wb_organic_vs_paid` — органика vs реклама: переходы, корзина, заказы (тек + пред)
  - `advertising` — рекламные расходы, ROMI, ДРР по моделям
  - `finance` — выручка, маржа по моделям
  - `sku_statuses` — статусы моделей (Продается / Выводим / Архив / Запуск)
- `{{DEPTH}}` — глубина: `day` / `week` / `month`
- `{{PERIOD_LABEL}}` — текущий период
- `{{PREV_PERIOD_LABEL}}` — предыдущий период

---

## Словарь метрик (ТОЛЬКО русские названия)

| Системное имя | Русское название | Формула |
|---|---|---|
| openCardCount | Переходы | Открытия карточки |
| addToCartCount | Корзина | Добавления в корзину |
| ordersCount | Заказы | Оформленные заказы |
| buyoutsCount | Выкупы | Фактически выкупленные |
| CR open→cart | Конверсия переход→корзина | корзина / переходы × 100 |
| CR cart→order | Конверсия корзина→заказ | заказы / корзина × 100 |
| CRO | Конверсия переход→заказ (СКВОЗНАЯ) | заказы / переходы × 100 |
| CRP | Конверсия переход→выкуп (ИТОГОВАЯ) | выкупы / переходы × 100 |

**CRO — ГЛАВНАЯ метрика.** Все остальные CR — диагностические.

---

## Бенчмарки (категория: нижнее бельё WB)

| Метрика | Проблема | Норма | Отлично |
|---|---|---|---|
| Переход→корзина | < 5% | 5–15% | > 15% |
| Корзина→заказ | < 20% | 20–40% | > 40% |
| CRO (переход→заказ) | < 1% | 1–3% | > 3% |
| CRP (переход→выкуп) | < 0.5% | 0.5–2% | > 2% |

---

## Пороги значимости

| Глубина | Δ CR (п.п.) | Δ переходов (%) | Δ заказов (%) | Δ артикулов |
|---|---|---|---|---|
| day | > 1 п.п. | > 10% | > 10% | > 20% |
| week | > 1 п.п. | > 15% | > 15% | > 30% |
| month | > 2 п.п. | > 20% | > 20% | > 30% |

---

## Протокол сканирования

### 1. Бренд WB (суммарно)

Сводная воронка бренда:
- Переходы: тек | пред | Δ%
- Корзина: тек | пред | Δ%
- Заказы: тек | пред | Δ%
- Выкупы*: тек | пред | Δ% (*лаг 3-21 дн)
- CR переход→корзина: тек% | пред% | Δ п.п.
- CR корзина→заказ: тек% | пред% | Δ п.п.
- CRO (переход→заказ): тек% | пред% | Δ п.п.
- CRP (переход→выкуп): тек% | пред% | Δ п.п. (*лаг)
- Выручка: тек | пред | Δ%
- Маржа: тек | пред | Δ%
- ДРР: тек% | пред% | Δ п.п.

### 2. По моделям (ВСЕ модели из sku_statuses)

Список моделей: из `sku_statuses` — **ВСЕ** со статусом "Продается" и "Запуск".
ЗАПРЕЩЕНО придумывать модели.

Для КАЖДОЙ модели из данных traffic.wb_by_model:
- Переходы: тек | пред | Δ%
- Корзина: тек | пред | Δ%
- Заказы: тек | пред | Δ%
- Выкупы*: тек | пред | Δ%
- CR переход→корзина: тек% | пред% | Δ п.п.
- CR корзина→заказ: тек% | пред% | Δ п.п.
- **CRO**: тек% | пред% | Δ п.п. — **ВСЕГДА считать и выделять**
- CRP: тек% | пред% | Δ п.п. (*лаг)

Флаг если: Δ CRO > 0.5 п.п. ИЛИ Δ заказов > 15%.

**Headline для каждой модели:**
- CRO упал > 0.5 п.п. → "КРИТИЧЕСКАЯ ПРОБЛЕМА: CRO -{X}pp"
- CRO вырос > 0.5 п.п. → "ПОЗИТИВ: CRO +{X}pp"
- Заказы упали > 15% → "падение заказов -{X}%"
- Заказы выросли > 30% → "рост заказов +{X}%"

### 3. Значимые артикулы (per model)

Для каждой модели — найти артикулы с Δ переходов > 30% ИЛИ Δ заказов > 30%:
- Артикул: имя
- Переходы: тек | пред | Δ%
- Заказы: тек | пред | Δ%
- Флаги: текстовое описание значимого изменения

Сортировать: рост → падение (сначала top по росту, затем top по падению).

### 4. Органика vs Платное (по бренду)

Структура трафика:
- Доля органических переходов: тек% | пред% | Δ п.п.
- Доля органических заказов: тек% | пред% | Δ п.п.
- CR органика (переходы→заказы): тек% | пред% | Δ п.п.
- CR платное (переходы→заказы): тек% | пред% | Δ п.п.

### 5. Экономика по моделям

Для КАЖДОЙ модели (из finance block):
- Выручка: тек | Δ%
- Маржа: тек | маржинальность%
- ДРР: тек% | Δ п.п.
- ROMI: тек%
- Средний чек: тек ₽

---

## Severity

- **HIGH**: CRO упал > 1 п.п. у модели A-группы (>5% выручки), заказы упали > 20% у модели A-группы, CR корзина→заказ упал > 5 п.п.
- **MEDIUM**: CRO упал 0.5-1.0 п.п., заказы упали 15-20%, CR любого шага изменился > 3 п.п.
- **LOW**: CRO изменился < 0.5 п.п., изменения в пределах нормы

---

## Формат вывода

\`\`\`
BRAND_OVERVIEW:
{
  card_opens: {current: <n>, previous: <n>, delta_pct: <n>},
  cart: {current: <n>, previous: <n>, delta_pct: <n>},
  orders: {current: <n>, previous: <n>, delta_pct: <n>},
  buyouts: {current: <n>, previous: <n>, delta_pct: <n>, note: "лаг 3-21 дн"},
  cr_open_cart: {current_pct: <n>, previous_pct: <n>, delta_pp: <n>},
  cr_cart_order: {current_pct: <n>, previous_pct: <n>, delta_pp: <n>},
  cro: {current_pct: <n>, previous_pct: <n>, delta_pp: <n>},
  crp: {current_pct: <n>, previous_pct: <n>, delta_pp: <n>, note: "лаг 3-21 дн"},
  revenue: {current: <n>, delta_pct: <n>},
  margin: {current: <n>, delta_pct: <n>},
  drr: {current_pct: <n>, delta_pp: <n>}
}

MODEL_FINDINGS:
[
  {
    model: "Wendy",
    status: "Продается",
    severity: HIGH,
    headline: "падение заказов -21.5%, CRO -0.50pp",
    funnel: {
      card_opens: {current: <n>, previous: <n>, delta_pct: <n>},
      cart: {current: <n>, previous: <n>, delta_pct: <n>},
      orders: {current: <n>, previous: <n>, delta_pct: <n>},
      buyouts: {current: <n>, previous: <n>, delta_pct: <n>},
      cr_open_cart: {current_pct: <n>, previous_pct: <n>, delta_pp: <n>},
      cr_cart_order: {current_pct: <n>, previous_pct: <n>, delta_pp: <n>},
      cro: {current_pct: <n>, previous_pct: <n>, delta_pp: <n>},
      crp: {current_pct: <n>, previous_pct: <n>, delta_pp: <n>}
    },
    economics: {
      revenue: <n>, margin: <n>, margin_pct: <n>, drr: <n>, romi: <n>, avg_check: <n>,
      organic_share_opens: <n>, organic_share_orders: <n>
    },
    significant_articles: [
      {article: "wendy/fig", opens: <n>, orders: <n>, flags: "переходы -48.5%, заказы -43.8%"},
      ...
    ]
  },
  ...
]

ORGANIC_VS_PAID:
{
  organic_opens_share: {current_pct: <n>, previous_pct: <n>, delta_pp: <n>},
  organic_orders_share: {current_pct: <n>, previous_pct: <n>, delta_pp: <n>},
  cr_organic: {current_pct: <n>, previous_pct: <n>, delta_pp: <n>},
  cr_paid: {current_pct: <n>, previous_pct: <n>, delta_pp: <n>}
}
\`\`\`

---

## Правила

1. **CRO — ГЛАВНАЯ метрика.** ВСЕГДА считать, ВСЕГДА выделять в headline модели.
2. **Выкуп % — лаговый показатель** (3-21 дн). При DEPTH=day — НЕ использовать выкупы как причину. Всегда с пометкой.
3. **ТОЛЬКО реальные модели** из sku_statuses. Не придумывать.
4. **ТОЛЬКО реальные данные** из `{{DATA}}`. Никогда не генерировать числа.
5. **GROUP BY модели:** `LOWER(SPLIT_PART(article, '/', 1))` — данные уже агрегированы в wb_by_model.
6. **Значимые артикулы:** Δ переходов > 30% ИЛИ Δ заказов > 30%. Макс 5 артикулов на модель (top рост + top падение).
7. **Все CR в п.п.** (процентных пунктах), не в %.
8. **Формат чисел:** `1 234 567 ₽`, `24.1%`, `+3.2 п.п.`.
9. Не рекомендовать действия — это задача Wave C (стратег).
10. Если данных по модели нет — писать `"н/д"`, не пропускать модель.
```

- [ ] **Step 2: Verify**

```bash
wc -l .claude/skills/funnel-report/prompts/detector.md
```

Expected: ~200 lines.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/funnel-report/prompts/detector.md
git commit -m "feat(funnel-report): add Wave A detector prompt"
```

---

### Task 4: Write diagnostician.md — Wave B root cause analysis

**Files:**
- Create: `.claude/skills/funnel-report/prompts/diagnostician.md`
- Reference: `.claude/skills/marketing-report/prompts/diagnostician.md` (structural template)
- Reference: `agents/oleg/funnel_playbook.md` (diagnostic trees)

**This prompt defines the diagnostician that:**
- For each HIGH/MEDIUM finding from Wave A, determines WHY it happened
- Builds causal chains specific to funnel (CRO drop → which step? → what factor?)
- Calculates ₽-effect: "if restore CRO to X% → +Y orders × avg_check × margin%"
- Links cross-model patterns

- [ ] **Step 1: Write diagnostician.md**

Write `.claude/skills/funnel-report/prompts/diagnostician.md` with this content:

```markdown
# Wave B: Воронковый диагност

> Роль: диагност корневых причин изменений воронки продаж WB бренда Wookiee.
> Задача: для каждого значимого finding определить ПОЧЕМУ это произошло, рассчитать ₽-эффект восстановления CRO.
> Вопрос: **ПОЧЕМУ CRO/CR изменился?**

---

## Инструкции

**Перед анализом** прочитай Knowledge Base: `.claude/skills/analytics-report/references/analytics-kb.md`.
Особое внимание: Воронка продаж (разделы 11-12), Причинно-следственные паттерны (раздел 9), Лаговые показатели (раздел 6), Диагностика аномалий (раздел 18).

---

## Входные данные

- `{{FINDINGS}}` — результат Wave A (BRAND_OVERVIEW + MODEL_FINDINGS + ORGANIC_VS_PAID)
- `{{RAW_DATA}}` — JSON: traffic (by model, by article), advertising (organic vs paid), finance (by model)
- `{{DEPTH}}` — глубина: `day` / `week` / `month`

---

## Диагностический протокол

Для КАЖДОГО finding с severity HIGH и MEDIUM — полная диагностика.
LOW findings — только если связаны с HIGH/MEDIUM.

### Шаг 1. Определи шаг воронки с проблемой

CRO = CR_open_cart × CR_cart_order. Декомпозируй:

| Симптом | Диагностическое дерево |
|---|---|
| CRO упал, CR переход→корзина упал | Проблема ПРИВЛЕЧЕНИЯ: трафик нецелевой? фото/описание не убеждает? цена выше конкурентов? |
| CRO упал, CR корзина→заказ упал | Проблема КОНВЕРСИИ: размеры OOS? цена выросла? доставка замедлилась? акция конкурента? |
| CRO упал, ОБА CR упали | Комплексная проблема: проверить оба дерева, определить первопричину |
| CRO стабильный, переходы упали | Проблема ТРАФИКА: позиции в поиске, рекламный бюджет, сезонность |
| CRO вырос, переходы упали | ПОЗИТИВ конверсии при потере трафика — трафик стал более целевым |
| Переходы выросли, CRO упал | Нецелевой трафик: реклама привела невалидную аудиторию |

### Шаг 2. Проверь каждую гипотезу по данным

**CR переход→корзина упал:**
1. Переходы выросли сильно (>30%)? → Нецелевой трафик — рост показов привёл менее заинтересованных
2. Доля платных переходов выросла? → Рекламный трафик менее конвертируемый
3. Конкретные артикулы потеряли переходы? → Проблема контента/позиций конкретных SKU

**CR корзина→заказ упал:**
1. Цена модели изменилась? → Ценовая конкурентоспособность
2. Конкретные артикулы потеряли заказы при стабильной корзине? → OOS по размерам (S/M/L)
3. Доставка замедлилась? → Барьер оформления (данные недоступны — пометить как гипотезу)
4. Множество артикулов модели одновременно → Системная проблема модели (не артикульная)

**Переходы упали:**
1. Реклама сокращена? → Проверить advertising.organic_vs_paid
2. Органика упала? → Позиции в поиске (проверить по данным)
3. Сезонность? → Проверить тренд (если DEPTH=week или month)

### Шаг 3. Рассчитай ₽-эффект восстановления CRO

**ОБЯЗАТЕЛЬНАЯ формула для каждой модели с CRO↓:**

\`\`\`
Δ_CRO = prev_cro - current_cro (в п.п.)
additional_orders = current_card_opens × Δ_CRO / 100
additional_revenue = additional_orders × avg_check
additional_margin = additional_revenue × margin_pct / 100

Пример:
Wendy: CRO упала с 2.10% до 1.60% (-0.50pp)
Переходы = 79 784
Дополнительные заказы = 79 784 × 0.50% = 399
Дополнительная выручка = 399 × 1 608₽ = +641 592₽
Дополнительная маржа = 641 592 × 21.4% = +137 300₽
\`\`\`

avg_check = economics.revenue / economics.orders (из findings)
margin_pct = economics.margin / economics.revenue × 100

### Шаг 4. Cross-model patterns

Найди модели с ОДИНАКОВЫМ симптомом:
- Если 3+ модели потеряли CR корзина→заказ одновременно → системная причина (доставка, акция конкурента, сезон)
- Если 1 модель потеряла CR → артикульная/модельная причина (OOS, цена, контент)
- Если органика↓ + переходы↓ по нескольким моделям → проблема позиций в поиске (системная)

---

## Уровень уверенности

| Уровень | Критерий |
|---|---|
| HIGH | Данные за 7+ дней, причина подтверждена данными (конкретные артикулы с OOS, ценовое изменение) |
| MEDIUM | Данные за 3-7 дней, причина вероятна (корреляция переходов и CRO, рост нецелевого трафика) |
| LOW | < 3 дней, гипотеза не подтверждена данными, несколько альтернативных объяснений |

При DEPTH=day — максимальный confidence = MEDIUM.
Выкупы и CRP — НЕ использовать как причину при DEPTH=day (лаг 3-21 дн).

---

## Формат вывода

\`\`\`
FUNNEL_DIAGNOSTICS:

1. {
     model: "Wendy",
     finding_id: 1,
     symptom: "CRO упала с 2.10% до 1.60% (-0.50pp) при росте переходов +2.8%",
     funnel_step: "CR переход→корзина (-1.02pp) + CR корзина→заказ (-3.27pp)",
     cause: "Падение CR переход→корзина на 1.02pp + CR корзина→заказ на 3.27pp. Артикулы fig, ivory, light_pink потеряли -48%, -29%, -35% переходов и -44%, -41%, -44% заказов соответственно. Гипотеза: отсутствие ходовых размеров в этих цветах.",
     confidence: MEDIUM,
     effect_formula: "79 784 × (2.10% - 1.60%) = 399 доп.заказов × 1 608₽ = +641 592₽ выручки × 21.4% = +137 300₽ маржи",
     effect_margin_rub: 137300,
     causal_chain: "Размеры OOS (fig/ivory/light_pink) → CR переход→корзина↓ (-1.02pp) → CR корзина→заказ↓ (-3.27pp) → CRO↓ (2.10%→1.60%) → заказы↓ (-21.5%)",
     related_models: []
   }

2. ...

CROSS_MODEL_PATTERNS:
1. {
     pattern: "CR корзина→заказ упал у 5 из 11 моделей одновременно (Wendy -3.27pp, Ruby -6.18pp, Moon -8.04pp, Joy -7.96pp, Charlotte -26.98pp). Вероятная системная причина: сезонное изменение или обновление алгоритмов WB.",
     models: ["Wendy", "Ruby", "Moon", "Joy", "Charlotte"],
     confidence: MEDIUM,
     combined_effect_margin_rub: 280900
   }
\`\`\`

---

## Правила

1. **₽-эффект восстановления CRO обязателен** для каждой модели с CRO↓. Формулу указывать полностью.
2. **Декомпозиция CRO** на два шага (CR переход→корзина и CR корзина→заказ) — обязательна. Определить какой шаг "сломался".
3. **Causal chain** — обязательна для каждого диагноза.
4. **Значимые артикулы** — привязывать к диагнозу (какие артикулы потеряли больше всего).
5. **Выкупы — лаговый показатель.** Не диагностировать падение выкупов как проблему при DEPTH=day/week.
6. **Числа — ТОЛЬКО из `{{RAW_DATA}}` и `{{FINDINGS}}`**. Никогда не генерировать.
7. **Тон:** сухой аналитик. Факт → причина → формула → эффект.
8. Не рекомендовать действия — это задача Wave C.
```

- [ ] **Step 2: Verify**

```bash
wc -l .claude/skills/funnel-report/prompts/diagnostician.md
```

Expected: ~150 lines.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/funnel-report/prompts/diagnostician.md
git commit -m "feat(funnel-report): add Wave B diagnostician prompt"
```

---

### Task 5: Write strategist.md — Wave C prioritized actions

**Files:**
- Create: `.claude/skills/funnel-report/prompts/strategist.md`
- Reference: `.claude/skills/marketing-report/prompts/strategist.md` (structural template)

**This prompt defines the strategist that:**
- Ranks diagnostics by ₽ effect
- Formulates CRO restoration actions
- Produces TOP-3 recommendations with "если восстановить CRO" scenarios

- [ ] **Step 1: Write strategist.md**

Write `.claude/skills/funnel-report/prompts/strategist.md` with this content:

```markdown
# Wave C: Воронковый стратег

> Роль: стратег восстановления конверсии бренда Wookiee WB.
> Задача: на основе findings (Wave A) и diagnostics (Wave B) сформулировать ТОП-3 действия по восстановлению CRO с расчётом ₽-эффекта.
> Вопрос: **ЧТО ДЕЛАТЬ для восстановления CRO?**

---

## Инструкции

**Перед анализом** прочитай Knowledge Base: `.claude/skills/analytics-report/references/analytics-kb.md`.
Особое внимание: Воронка продаж (разделы 11-12), Ценовая логика (раздел 7), Диагностика аномалий (раздел 18).

---

## Входные данные

- `{{FINDINGS}}` — результат Wave A (MODEL_FINDINGS)
- `{{DIAGNOSTICS}}` — результат Wave B (FUNNEL_DIAGNOSTICS + CROSS_MODEL_PATTERNS)
- `{{DEPTH}}` — глубина: `day` / `week` / `month`

---

## Протокол формирования действий

### Шаг 1. Ранжируй модели по |₽-эффект маржи|

Отсортируй все модели с CRO↓ по убыванию `effect_margin_rub` из diagnostics. Работай сверху вниз.

### Шаг 2. Для каждой модели — определи действие

| Симптом (из диагностики) | Действие |
|---|---|
| CR переход→корзина↓ + нецелевой трафик | Проверить ключевые слова и рекламные кампании. Возможно: добавить минус-слова, снизить бюджет нецелевых РК |
| CR переход→корзина↓ + конкретные артикулы | Проверить контент карточек (фото, описание) проблемных артикулов |
| CR корзина→заказ↓ + конкретные артикулы | Проверить наличие размеров S/M/L/XL в проблемных артикулах. Пополнить если OOS |
| CR корзина→заказ↓ + системное падение | Проверить цены vs конкуренты, сроки доставки, наличие размеров по всей модели |
| Переходы↓ + CRO стабильный | Восстановить рекламный бюджет или проверить позиции в поиске |
| Переходы↑ + CRO↓ | Снизить нецелевой трафик (минус-слова), улучшить карточку для конверсии |

### Шаг 3. Формат рекомендации

Для КАЖДОЙ модели с CRO↓ и effect_margin_rub > 10К₽:

\`\`\`
ФАКТ: CRO {model} упала с {prev}% до {current}% ({delta}pp). Заказы {delta_orders}%.
ГИПОТЕЗА: {cause из diagnostics}
ДЕЙСТВИЕ: {конкретное действие — что проверить/сделать}
ЭФФЕКТ: Если восстановить CRO до {prev}%:
  - Дополнительные заказы: {card_opens} × ({prev}% - {current}%) = {n} заказов
  - Дополнительная выручка: {n} × {avg_check}₽ = +{revenue}₽
  - Дополнительная маржа: {revenue} × {margin_pct}% = +{margin}₽
\`\`\`

### Шаг 4. ТОП-3 действия

Выбери 3 модели с максимальным ₽-эффектом маржи. Это ТОП-3 для раздела "Выводы и рекомендации".

### Шаг 5. Общий потенциал роста

Суммируй ₽-эффект маржи ВСЕХ моделей с CRO↓:
`Общий потенциал = Σ effect_margin_rub всех моделей`

---

## Формат вывода

\`\`\`
FUNNEL_HYPOTHESES:

TOP_3:
1. {
     rank: 1,
     model: "Wendy",
     fact: "CRO упала с 2.10% до 1.60% (-0.50pp). Заказы -21.5%.",
     cause: "Отсутствие ходовых размеров в цветах fig, ivory, light_pink.",
     action: "Проверить наличие размеров S/M/L/XL в артикулах wendy/fig, wendy/ivory, wendy/light_pink. Пополнить при OOS.",
     effect_orders: 399,
     effect_revenue: 641592,
     effect_margin: 137300,
     effect_formula: "79 784 × (2.10% - 1.60%) = 399 заказов × 1 608₽ = +641 592₽ × 21.4% = +137 300₽",
     confidence: MEDIUM
   }

2. { ... }
3. { ... }

ALL_MODELS:
[
  {model: "Wendy", cro_delta_pp: -0.50, effect_margin: 137300, action: "..."},
  {model: "Audrey", cro_delta_pp: -0.55, effect_margin: 65700, action: "..."},
  ...
]

TOTAL_GROWTH_POTENTIAL: {
  margin_per_week: <sum>,
  note: "Сумма ₽-эффектов восстановления CRO всех моделей с падением"
}
\`\`\`

---

## Правила

1. **Расчёт эффекта — ОБЯЗАТЕЛЕН** для каждой модели с CRO↓. Формула полностью.
2. **Действие — КОНКРЕТНОЕ**: "проверить наличие размеров S/M/L/XL в wendy/fig", НЕ "улучшить конверсию".
3. **ТОП-3** — по ₽-эффекту маржи (не по Δ CRO).
4. **Общий потенциал** — сумма всех ₽-эффектов.
5. **Числа — ТОЛЬКО из `{{FINDINGS}}` и `{{DIAGNOSTICS}}`**. Никогда не генерировать.
6. **Тон:** сухой CMO. Факт → гипотеза → действие → эффект.
7. **Выкупы — лаговый.** Не рекомендовать действия по выкупам при DEPTH=day/week.
8. **Не рекомендовать:** "обновить фото", "добавить инфографику", "запросить отзывы" — это из плейбука запрещённых формулировок (Oleg playbook §8).
9. **РАЗРЕШЕНО:** указать конкретные проблемы + предложить проверить конкретные факторы (цена, размеры, отзывы) + рассчитать потенциальный эффект.
```

- [ ] **Step 2: Verify**

```bash
wc -l .claude/skills/funnel-report/prompts/strategist.md
```

Expected: ~120 lines.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/funnel-report/prompts/strategist.md
git commit -m "feat(funnel-report): add Wave C strategist prompt"
```

---

### Task 6: Write model-analyst.md — per-model deep analysis

**Files:**
- Create: `.claude/skills/funnel-report/prompts/model-analyst.md`
- Reference: Notion etalon page `32758a2bd58781b394b4e4c4d16dfeba`

**This prompt defines the model analyst that generates per-model toggle sections (the core of the report).**

- [ ] **Step 1: Write model-analyst.md**

Write `.claude/skills/funnel-report/prompts/model-analyst.md` with this content:

```markdown
# Model Analyst — Per-Model Funnel Sections

> Роль: аналитик воронки по моделям бренда Wookiee WB.
> Задача: сгенерировать toggle-секцию для КАЖДОЙ модели ("Продается" + "Запуск") с 4 подсекциями: Воронка, Экономика, Значимые артикулы, Анализ.
> Формат: ЧИСТЫЙ MARKDOWN (pipe-таблицы, toggle-заголовки).

---

## Инструкции

**Перед анализом** прочитай Knowledge Base: `.claude/skills/analytics-report/references/analytics-kb.md`.
Прочитай Notion formatting guide: `.claude/skills/analytics-report/templates/notion-formatting-guide.md`.

---

## Входные данные

- `{{FINDINGS}}` — результат Wave A (MODEL_FINDINGS с funnel + economics + significant_articles)
- `{{DIAGNOSTICS}}` — результат Wave B (FUNNEL_DIAGNOSTICS с cause, confidence, effect)
- `{{HYPOTHESES}}` — результат Wave C (FUNNEL_HYPOTHESES с actions и TOP-3)
- `{{RAW_DATA}}` — JSON: traffic.wb_by_model, advertising, finance by model, sku_statuses
- `{{DEPTH}}` / `{{PERIOD_LABEL}}` / `{{PREV_PERIOD_LABEL}}`

---

## Список моделей

Из `sku_statuses`: ВСЕ модели со статусом "Продается" или "Запуск".
ЗАПРЕЩЕНО придумывать модели. Если модели нет в sku_statuses — НЕ включать.

Сортировка: по убыванию выручки (крупные модели первыми).

---

## Шаблон секции модели

Для КАЖДОЙ модели генерируй:

\`\`\`markdown
## Модель: {Name} — {headline} {toggle="true"}
\tВоронка модели (CRO как ГЛАВНАЯ метрика):
\t### Воронка
\t| Метрика | Текущая | Прошлая | Δ |
\t|---|---|---|---|
\t| Переходы | {n} | {n} | {+/-n}% |
\t| Корзина | {n} | {n} | {+/-n}% |
\t| Заказы | {n} | {n} | {+/-n}% |
\t| Выкупы | {n} | {n} | {+/-n}%\* |
\t| Конверсия переход→корзина | {n}% | {n}% | {+/-n}pp |
\t| Конверсия корзина→заказ | {n}% | {n}% | {+/-n}pp |
\t| CRO (переход→заказ) | {n}% | {n}% | {+/-n}pp |
\t| CRP (переход→выкуп) | {n}% | {n}% | {+/-n}pp |
\t\*Данные по выкупам неполные (лаг 3-21 день)
\t### Экономика
\t| Метрика | Значение |
\t|---|---|
\t| Выручка | {n} ₽ |
\t| Маржа | {n} ₽ |
\t| ДРР | {n}% |
\t| ROMI | {n}% |
\t| Доля органики (переходы) | {n}% |
\t| Доля органики (заказы) | {n}% |
\t### Значимые артикулы
\t| Артикул | Переходы | Заказы | Флаги |
\t|---|---|---|---|
\t| {article} | {n} | {n} | {flags} |
\t| ... | ... | ... | ... |
\t### Анализ
\t{Текст анализа — см. правила ниже}
\t---
\`\`\`

---

## Headline модели

Headline для toggle-заголовка (после "Модель: Name —"):

| Условие | Headline |
|---|---|
| CRO упал > 0.5 п.п. И заказы упали | "падение заказов {-X}%" |
| CRO упал > 0.5 п.п. НО переходы выросли | "CRO снижение {-X.XX}pp при росте трафика" |
| CRO вырос > 0.5 п.п. | "рост CRO {+X.XX}pp" |
| Заказы выросли > 30% | "взрывной рост +{X}% заказов" |
| Заказы упали > 30% | "падение заказов {-X}%" |
| Иначе | "заказы {+/-X}%" |

---

## Текст анализа (подсекция "Анализ")

### Если CRO упал > 0.5 п.п.:

\`\`\`
**КРИТИЧЕСКАЯ ПРОБЛЕМА:** CRO упала с {prev}% до {current}% ({delta}pp) {контекст переходов}.

**ГИПОТЕЗА:** {cause из diagnostics — 2-3 предложения с конкретными данными}

**Расчёт эффекта:** Если восстановить CRO до {prev}%:
- Дополнительные заказы: {card_opens} × ({prev}% - {current}%) = {n} заказов
- Дополнительная выручка: {n} × {avg_check}₽ (ср.чек) = +{revenue} ₽
- Дополнительная маржа: {revenue} × {margin_pct}% (маржинальность) = +{margin} ₽
\`\`\`

### Если CRO вырос > 0.5 п.п. или модель стабильна:

\`\`\`
{Name} показывает {стабильную CRO / отличный рост} — CRO {current}% (vs {prev}%). {1-2 предложения о ключевых факторах: доля органики, ROMI, тренд артикулов}.
\`\`\`

### Если данных мало (< 50 заказов за период):

\`\`\`
{Name}: объём данных недостаточен для выводов ({orders} заказов за период). Мониторинг.
\`\`\`

---

## КРИТИЧЕСКИЕ ПРАВИЛА

1. **ТОЛЬКО чистый Markdown.** Никакого HTML: никаких `<table>`, `<tr>`, `<td>`.
2. **Pipe-таблицы** — единственный формат таблиц.
3. **Toggle-заголовок:** `## Модель: {Name} — {headline} {toggle="true"}`
4. **Tab-indentation** (`\t`) для контента внутри toggle (Notion требует).
5. **Выкуп*:** ВСЕГДА с `*` и сноской `*Данные по выкупам неполные (лаг 3-21 день)`.
6. **Числа:** `1 234 567 ₽`, `24,1%`, `+3,2 п.п.` — пробелы в тысячах.
7. **Title Case** для моделей: Wendy, Vuki, Ruby (не wendy, vuki, ruby).
8. **ТОЛЬКО реальные данные** из входных данных. Никогда не придумывать.
9. **ТОЛЬКО реальные модели** из sku_statuses (Продается + Запуск).
10. **Значимые артикулы:** макс 5 на модель. Δ переходов > 30% ИЛИ Δ заказов > 30%.
11. **Расчёт эффекта:** ОБЯЗАТЕЛЕН для каждой модели с CRO↓ > 0.5 п.п. Формулу писать полностью.
12. **Разделитель `---`** после каждой модельной секции.
13. **CRO — ГЛАВНАЯ метрика.** Всегда выделять в headline и анализе.
14. **Сортировка моделей:** по убыванию выручки.

---

## Формат вывода

Один Markdown-документ, содержащий ВСЕ модельные секции подряд. Каждая секция — по шаблону выше.

Этот документ будет вставлен в финальный отчёт как секции II-XII синтезатором.
```

- [ ] **Step 2: Verify**

```bash
wc -l .claude/skills/funnel-report/prompts/model-analyst.md
```

Expected: ~160 lines.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/funnel-report/prompts/model-analyst.md
git commit -m "feat(funnel-report): add model-analyst prompt"
```

---

### Task 7: Write verifier.md — quality controller

**Files:**
- Create: `.claude/skills/funnel-report/prompts/verifier.md`
- Reference: `.claude/skills/marketing-report/prompts/verifier.md` (structural template)

- [ ] **Step 1: Write verifier.md**

Write `.claude/skills/funnel-report/prompts/verifier.md` with this content:

```markdown
# Verifier — Funnel Quality Controller

> Роль: контролёр качества воронковый отчёта.
> Проверяет корректность данных, формул и логики перед публикацией.
> Выносит вердикт: APPROVE / CORRECT / REJECT

---

## Вход

| Переменная | Описание |
|---|---|
| `{{MODEL_DEEP}}` | Все модельные секции от Model Analyst |
| `{{FINDINGS}}` | Находки детектора (BRAND_OVERVIEW + MODEL_FINDINGS) |
| `{{HYPOTHESES}}` | Гипотезы стратега (TOP_3 + ALL_MODELS + TOTAL_GROWTH_POTENTIAL) |
| `{{RAW_DATA}}` | Исходные данные для кросс-проверки |

---

## Инструкция

Ты — контролёр качества воронковой аналитики Wookiee.
Проведи все 10 проверок. Каждую завершай: PASS / FAIL (причина).

---

## 10 проверок

### 1. Воронка — математическая целостность

Для КАЖДОЙ модели: `переходы > корзина > заказы > выкупы`.
Все CR в диапазоне 0–100%.

CRO = заказы / переходы × 100.
CRP = выкупы / переходы × 100.
CR переход→корзина = корзина / переходы × 100.
CR корзина→заказ = заказы / корзина × 100.

FAIL если: любой шаг > предыдущего, CR < 0% или > 100%, CRO ≠ заказы/переходы×100 (±0.01pp).

### 2. CRO формула

Проверить что CRO в каждой таблице = заказы / переходы × 100.
Допуск: ±0.01 п.п. (округление).

FAIL если: CRO отличается от расчётного более чем на 0.01 п.п. у любой модели.

### 3. CRP формула + buyout caveat

CRP = выкупы / переходы × 100.
Каждое упоминание выкупов ДОЛЖНО содержать пометку `*Данные по выкупам неполные (лаг 3-21 день)`.

FAIL если: CRP отличается от расчётного ИЛИ пометка о лаге отсутствует.

### 4. Реальные модели

Все модели в отчёте — из sku_statuses. Проверить:
- Нет выдуманных моделей (Devi, Luna, Elsa, Ariel, Jasmine НЕ СУЩЕСТВУЮТ)
- Нет дубликатов (wendy и Wendy = одна модель)
- Все модели в Title Case

FAIL если: найдена выдуманная модель ИЛИ дубликат.

### 5. Полнота моделей

Все модели из sku_statuses со статусом "Продается" или "Запуск" должны присутствовать в секциях II-XII.

FAIL если: модель отсутствует.

### 6. Расчёт эффекта

Для КАЖДОЙ модели с CRO↓ > 0.5 п.п. проверить формулу:
`доп.заказы = переходы × Δ_CRO / 100`
`доп.выручка = доп.заказы × ср.чек`
`доп.маржа = доп.выручка × маржинальность%`

Допуск: ±5% от расчётного значения.

FAIL если: формула неверна ИЛИ отсутствует расчёт эффекта ИЛИ отклонение > 5%.

### 7. Экономика — сверка с finance block

Выручка и маржа в секции "Экономика" каждой модели должны совпадать с данными finance block из RAW_DATA. Допуск: ±5%.

FAIL если: отклонение > 5%.

### 8. Доля органики

Формула: organic_orders / total_orders × 100.
Проверить для каждой модели: organic_share_orders ≤ 100%.
Если доля органики переходов или заказов показана — формулы должны быть корректны.

FAIL если: organic_share > 100% ИЛИ формула неверна.

### 9. Buyout caveat

КАЖДАЯ строка таблицы с выкупами должна иметь звёздочку (*).
Сноска `*Данные по выкупам неполные (лаг 3-21 день)` — обязательна после таблицы.

FAIL если: пометка отсутствует у любой модели.

### 10. Рекомендации — конкретность

Секция XIII (Выводы и рекомендации) должна содержать ТОП-3 действия.
Каждое:
- Содержит конкретную модель
- Содержит ФАКТ (что произошло с CRO)
- Содержит ГИПОТЕЗУ (почему)
- Содержит ДЕЙСТВИЕ (что сделать)
- Содержит ЭФФЕКТ (₽ маржи)
- Содержит "Общий потенциал роста" (сумма ₽)

FAIL если: рекомендация абстрактная ("улучшить конверсию") без конкретных моделей и ₽.

---

## Формат выхода

\`\`\`
VERDICT: APPROVE | CORRECT | REJECT

CHECKS:
1. Воронка математика: ✅ PASS | ❌ FAIL — {детали}
2. CRO формула: ✅ PASS | ❌ FAIL — {детали}
3. CRP + buyout caveat: ✅ PASS | ❌ FAIL — {детали}
4. Реальные модели: ✅ PASS | ❌ FAIL — {детали}
5. Полнота моделей: ✅ PASS | ❌ FAIL — {детали}
6. Расчёт эффекта: ✅ PASS | ❌ FAIL — {детали}
7. Экономика finance: ✅ PASS | ❌ FAIL — {детали}
8. Доля органики: ✅ PASS | ❌ FAIL — {детали}
9. Buyout caveat: ✅ PASS | ❌ FAIL — {детали}
10. Рекомендации конкретность: ✅ PASS | ❌ FAIL — {детали}

CORRECTIONS (if CORRECT):
- ...

RE_RUN (if REJECT):
- ...
\`\`\`

---

## Вердикт

### APPROVE
Все 10 проверок = PASS.

### CORRECT
1-3 проверки = FAIL, ошибки исправимы (опечатки, округление, пропущенная сноска).

### REJECT
Критические ошибки:
- Более 3 FAIL
- Нарушение монотонности воронки
- Выдуманная модель
- Отсутствующая секция

**Максимум 1 повторная попытка.**

---

## Приоритет проверок

1. **Критические (REJECT):** 1 (воронка математика), 2 (CRO формула), 4 (реальные модели)
2. **Важные (влияют на вердикт):** 3 (CRP + caveat), 5 (полнота), 6 (расчёт эффекта), 7 (экономика)
3. **Форматирование (CORRECT):** 8 (органика), 9 (buyout caveat), 10 (рекомендации)
```

- [ ] **Step 2: Verify**

```bash
wc -l .claude/skills/funnel-report/prompts/verifier.md
```

Expected: ~170 lines.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/funnel-report/prompts/verifier.md
git commit -m "feat(funnel-report): add verifier prompt"
```

---

### Task 8: Write synthesizer.md — final report assembly

**Files:**
- Create: `.claude/skills/funnel-report/prompts/synthesizer.md`
- Reference: `.claude/skills/marketing-report/prompts/synthesizer.md` (structural template)
- Reference: Notion etalon page `32758a2bd58781b394b4e4c4d16dfeba`

**This prompt defines the synthesizer that assembles the final 13-section report matching the Notion etalon.**

- [ ] **Step 1: Write synthesizer.md**

Write `.claude/skills/funnel-report/prompts/synthesizer.md` with this content:

```markdown
# Synthesizer — Воронка WB v1 (чистый Markdown)

> Роль: собрать финальный отчёт воронки WB из данных всех субагентов.
> Формат: ЧИСТЫЙ MARKDOWN — никакого HTML. Таблицы через `|`, заголовки через `##`.
> Эталон: Notion page 32758a2bd58781b394b4e4c4d16dfeba

---

## Вход

| Переменная | Описание |
|---|---|
| `{{MODEL_DEEP}}` | Все модельные секции от Model Analyst (toggle-блоки для каждой модели) |
| `{{FINDINGS}}` | Находки детектора (BRAND_OVERVIEW) |
| `{{DIAGNOSTICS}}` | Диагностика причин |
| `{{HYPOTHESES}}` | Гипотезы стратега (TOP_3 + TOTAL_GROWTH_POTENTIAL) |
| `{{DEPTH}}` | day / week / month |
| `{{PERIOD_LABEL}}` | Текущий период |
| `{{PREV_PERIOD_LABEL}}` | Предыдущий период |
| `{{QUALITY_FLAGS}}` | Флаги качества данных |

---

## КРИТИЧЕСКИЕ ПРАВИЛА

### Формат

1. **ТОЛЬКО чистый Markdown.** Никакого HTML: никаких `<table>`, `<tr>`, `<td>`, `<callout>`, `<br>`.
2. **Таблицы** — ТОЛЬКО pipe-формат: `| Колонка1 | Колонка2 |`
3. **Toggle-заголовки** — `## Модель: Name — headline {toggle="true"}` для модельных секций
4. **Tab-indentation** (`\t`) для контента внутри toggle
5. **Разделители** — `---` между секциями

### Данные

6. **ТОЛЬКО реальные данные.** Если данных нет — писать "н/д". НИКОГДА не придумывать.
7. **ТОЛЬКО реальные модели** из sku_statuses. ЗАПРЕЩЕНО придумывать.
8. **Выкуп\*:** ВСЕГДА со сноской `*Данные по выкупам неполные (лаг 3-21 день)`.

### Числа

9. Формат: `1 234 567 ₽`, `24,1%`, `+3,2 п.п.`
10. Крупные суммы: `8,8М` — не `8 800 000 ₽`
11. Значимые изменения: **bold** (`**-21.5%**`, `**+0.50pp**`)

### Терминология

12. **Русская ТОЛЬКО:** Переходы (не card_opens), Корзина (не cart), Выкупы (не buyouts), ДРР (не DRR), Маржа (не Margin).

---

## Структура отчёта

\`\`\`
# Воронка WB за {PERIOD_LABEL}

## ОБЩИЙ ОБЗОР БРЕНДА
{Секция I}
---

## Модель: Wendy — падение заказов -21.5% {toggle="true"}
{Секция II — из MODEL_DEEP}
---

## Модель: Vuki — заказы -9.2% {toggle="true"}
{Секция III — из MODEL_DEEP}
---

... (секции IV-XII — остальные модели из MODEL_DEEP)

## Выводы и рекомендации
{Секция XIII}
\`\`\`

---

## Секция I: ОБЩИЙ ОБЗОР БРЕНДА

**ТЫ ГЕНЕРИРУЕШЬ** из `{{FINDINGS}}.BRAND_OVERVIEW`.

| Метрика | Текущая неделя | Прошлая неделя | Изменение |
|---|---|---|---|
| Переходы | {n} | {n} | {+/-n}% |
| Заказы | {n} | {n} | {+/-n}% |
| Выкупы | {n} | {n} | {+/-n}%\* |
| Выручка | {n} ₽ | — | — |
| Маржа | {n} ₽ | — | — |
| ДРР | {n}% | — | — |

\*Данные по выкупам неполные (лаг 3-21 день)

**Правила:**
- Если прошлая выручка/маржа/ДРР есть в данных — показать. Если нет — "—".
- Формат чисел с пробелами: `282 953`, `5 985 587 ₽`.

---

## Секции II-XII: Модельные секции

Вставить **БЕЗ ИЗМЕНЕНИЙ** из `{{MODEL_DEEP}}`.

Каждая секция — toggle с 4 подсекциями (Воронка, Экономика, Значимые артикулы, Анализ).
Модели идут по убыванию выручки.
Разделитель `---` после каждой модели.

---

## Секция XIII: Выводы и рекомендации

**СИНТЕЗИРУЙ** из `{{HYPOTHESES}}`.

### ТОП-3 ДЕЙСТВИЯ С РАСЧЁТОМ ЭФФЕКТА

Для каждого из 3 действий:

\`\`\`markdown
### {N}. {Заголовок действия}

**ФАКТ:** {что произошло — CRO, заказы, конкретные цифры}

**ГИПОТЕЗА:** {почему — из diagnostics, 2-3 предложения с данными}

**ДЕЙСТВИЕ:** {конкретное действие — что проверить/сделать}

**ЭФФЕКТ:** Если восстановить CRO до {target}%:
- Дополнительные заказы: {card_opens} × ({target}% - {current}%) = {n} заказов
- Дополнительная выручка: {n} × {avg_check}₽ (ср.чек) = +{revenue} ₽
- Дополнительная маржа: {revenue} × {margin_pct}% (маржинальность) = +{margin} ₽
\`\`\`

---

### ОБЩИЙ ПОТЕНЦИАЛ РОСТА МАРЖИ

\`\`\`markdown
Если выполнить все 3 рекомендации:
- **Дополнительная маржа: {sum_1} + {sum_2} + {sum_3} = +{total}₽/нед**
\`\`\`

### ДОПОЛНИТЕЛЬНЫЕ НАБЛЮДЕНИЯ

3-5 пунктов:
1. **Выкупы:** пометка о лаге + общий Δ%
2. **{Модель-звезда}:** ключевой позитив
3. **Органика:** обзор доли органики
4. **{Модель-рост}:** если есть модель с сильным ростом

---

## Проверка перед выводом

Перед генерацией проверь:

- [ ] Нет HTML тегов (поиск `<table`, `<tr`, `<td`, `<callout`)
- [ ] Все таблицы в pipe-формате
- [ ] Секция I (обзор бренда) присутствует
- [ ] ВСЕ модели из sku_statuses (Продается + Запуск) присутствуют как toggle-секции
- [ ] Секция XIII (выводы) содержит ТОП-3 + общий потенциал
- [ ] Toggle-заголовки: `## Модель: Name — headline {toggle="true"}`
- [ ] Tab-indentation (`\t`) внутри toggles
- [ ] Каждый выкуп со звёздочкой и сноской
- [ ] Расчёт эффекта: полная формула (переходы × Δ CRO × ср.чек × маржинальность)
- [ ] Числа с пробелами в тысячах
- [ ] Терминология русская
- [ ] Модели в Title Case
- [ ] Разделители `---` между секциями
- [ ] Нет выдуманных моделей
- [ ] Значимые Δ выделены **bold**
```

- [ ] **Step 2: Verify**

```bash
wc -l .claude/skills/funnel-report/prompts/synthesizer.md
```

Expected: ~180 lines.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/funnel-report/prompts/synthesizer.md
git commit -m "feat(funnel-report): add synthesizer prompt"
```

---

### Task 9: E2E test — run /funnel-report 2026-03-30 2026-04-05

**Files:**
- Read: `.claude/skills/funnel-report/SKILL.md` (orchestrator)
- Read: All 6 prompts in `prompts/`
- Output: `docs/reports/2026-03-30_2026-04-05_funnel.md`
- Output: Notion page

- [ ] **Step 1: Run the skill**

Execute `/funnel-report 2026-03-30 2026-04-05` following SKILL.md stages 0-5.

- [ ] **Step 2: Verify MD output**

```bash
wc -l docs/reports/2026-03-30_2026-04-05_funnel.md
grep -c "## Модель:" docs/reports/2026-03-30_2026-04-05_funnel.md
grep -c "toggle=" docs/reports/2026-03-30_2026-04-05_funnel.md
grep -c "<table" docs/reports/2026-03-30_2026-04-05_funnel.md  # should be 0
```

Expected:
- File exists, >200 lines
- Multiple model sections found
- Toggle attributes present
- Zero HTML table tags

- [ ] **Step 3: Verify Notion rendering**

Fetch the published Notion page via `mcp__claude_ai_Notion__notion-fetch` and check:
- Tables render correctly
- Toggle sections work
- Buyout caveats present
- TOP-3 conclusions with ₽ effect

- [ ] **Step 4: Commit test output**

```bash
git add docs/reports/2026-03-30_2026-04-05_funnel.md
git commit -m "test(funnel-report): E2E test output for 2026-03-30 — 2026-04-05"
```

---

## Self-Review Checklist

1. **Spec coverage:** All sections from spec 4.3 (I. Brand overview, II-XII per-model, XIII conclusions) are covered by synthesizer.md.
2. **Notion etalon match:** Toggle format, table structure, headline format, analysis text, effect calculations all match page 32758a2bd58781b394b4e4c4d16dfeba.
3. **No placeholders:** Every prompt has complete content with specific metrics, formulas, format examples.
4. **Type consistency:** CRO formula, effect calculation, model names consistent across all 6 prompts + SKILL.md.
5. **Oleg playbook coverage:** Benchmarks (§3), metrics dictionary (§1), diagnostic trees (§6, §9), forbidden recommendations (§8) — all incorporated.
6. **Architecture match:** Same collect_all.py → Wave A → B → C → Analyst → Verifier → Synthesizer pattern as marketing-report.
