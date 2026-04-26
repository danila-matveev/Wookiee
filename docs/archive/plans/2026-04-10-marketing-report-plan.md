# /marketing-report Deep Module — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `/marketing-report` — a deep marketing analytics skill with 11-section report (channels, funnels, organic vs paid, external ads, model efficiency matrix, advisor), analytics engine (detect→diagnose→strategize), and Notion publication.

**Architecture:** SKILL.md orchestrator → collect data (existing `collect_all.py`) → Wave A (marketing detector) → Wave B (diagnostician) → Wave C (strategist) → 2 analysts (Performance + Funnel) in parallel → verifier → synthesizer → Notion. Each subagent reads unified analytics-kb.md.

**Tech Stack:** Claude Code skills (SKILL.md + prompts), Python 3.9+ (collector already exists), Notion MCP, Google Sheets via `gws` CLI (external marketing data)

**Spec:** `docs/superpowers/specs/2026-04-08-modular-analytics-v2-design.md` (sections 2 + 4.2)
**Etalon:** Маркетинговый анализ за 16-22 марта 2026 `32c58a2bd58781a3823bd03f03676fb8`
**KB:** `.claude/skills/analytics-report/references/analytics-kb.md`
**Finance-report (template):** `.claude/skills/finance-report/SKILL.md`

---

## File Map

### Skill Files (`.claude/skills/marketing-report/`)

| File | Responsibility |
|---|---|
| `SKILL.md` | Orchestrator: 5 stages, placeholder injection, wave dispatch |
| `prompts/detector.md` | Wave A: Marketing detector — find significant Δ in DRR, funnel, traffic, ROMI |
| `prompts/diagnostician.md` | Wave B: Diagnose causes for marketing findings |
| `prompts/strategist.md` | Wave C: Formulate marketing actions with ₽ impact |
| `prompts/performance-analyst.md` | Deep channel P&L + model efficiency matrix + daily dynamics + external ads + avg check |
| `prompts/funnel-analyst.md` | Funnel analysis: ASCII funnels (WB organic + WB ad + OZON ad), organic vs paid tables |
| `prompts/verifier.md` | Marketing-specific verification (DRR split, dual KPI, funnel math, ROMI) |
| `prompts/synthesizer.md` | Assemble 11-section report with callouts and Notion formatting |

### Shared Resources (already exist, read-only)

| File | Used for |
|---|---|
| `.claude/skills/analytics-report/references/analytics-kb.md` | Knowledge Base — all subagents read this |
| `.claude/skills/analytics-report/templates/notion-formatting-guide.md` | Notion formatting rules |
| `scripts/analytics_report/collect_all.py` | Data collection (8 parallel collectors) |
| `scripts/analytics_report/collectors/advertising.py` | WB/OZON ad data, ROMI, DRR, organic vs paid funnel |
| `scripts/analytics_report/collectors/external_marketing.py` | Google Sheets: bloggers, VK, SMM |
| `scripts/analytics_report/collectors/traffic.py` | WB/OZON traffic funnel |
| `shared/notion_client.py` | `sync_report()` with report_type `marketing_weekly` etc. |
| `shared/notion_blocks.py` | `md_to_notion_blocks()` — Markdown → Notion blocks |

### Oleg Templates (reference, read-only)

| File | Used for |
|---|---|
| `agents/oleg/playbooks/templates/marketing_weekly.md` | Section structure reference |
| `agents/oleg/playbooks/templates/marketing_monthly.md` | Monthly depth reference |

---

## Task 1: SKILL.md Orchestrator

**Files:**
- Create: `.claude/skills/marketing-report/SKILL.md`

- [ ] **Step 1: Create directory and write SKILL.md**

Create `.claude/skills/marketing-report/SKILL.md` with the following content:

```markdown
---
name: marketing-report
description: Deep marketing analytics for Wookiee brand (WB+OZON) — funnel analysis, DRR decomposition, model efficiency matrix, organic vs paid, external ads (bloggers/VK/SMM)
triggers:
  - /marketing-report
  - маркетинговый отчёт
  - маркетинг анализ
---

# Marketing Report Skill

Deep marketing analytics for the Wookiee brand (WB+OZON). Uses a 3-wave analytics engine (detect → diagnose → strategize) before generating an 11-section report with ASCII funnels, model efficiency matrix, and external ad evaluation.

## Quick Start

` ` `
/marketing-report 2026-04-05                     → дневной (vs вчера)
/marketing-report 2026-03-30 2026-04-05           → недельный
/marketing-report 2026-03-01 2026-03-31           → месячный
` ` `

**Время выполнения:** ~20-30 минут (коллектор ~30с, 3 волны аналитики ~8м, 2 аналитика ~10м, верификация ~3м, синтез+публикация ~6м)

**Результаты:**
- MD: `docs/reports/{START}_{END}_marketing.md`
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

` ` `
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
` ` `

Save: `START`, `END`, `DEPTH`, `PREV_START`, `PREV_END`, `PERIOD_LABEL`, `PREV_PERIOD_LABEL`.

---

## Stage 1: Data Collection

Run the Python collector:

` ` `bash
python3 scripts/analytics_report/collect_all.py --start {START} --end {END} --output /tmp/marketing-report-{START}_{END}.json
` ` `

Read the output JSON. Save as `data_bundle`.

**Error handling:**
- Check `data_bundle["meta"]["errors"]`
- If 0-3 errors → proceed, note missing blocks as `quality_flags`
- If >3 errors → report to user and STOP
- If collector fails entirely → report error and STOP

**Data blocks used by marketing-report:**
- `finance` — revenue, margin, orders (for DRR calculation)
- `advertising` — ad spend, ROAS, DRR, organic vs paid funnel, model ROI, daily series, campaign stats
- `external_marketing` — bloggers, VK, Yandex, SMM from Google Sheets
- `traffic` — visits, conversion, organic vs paid, by model
- `sku_statuses` — model lifecycle statuses (for efficiency matrix grouping)

---

## Stage 2: Analytics Engine (3 sequential waves)

Three waves run SEQUENTIALLY. Each wave builds on the previous one's output.

### Wave A: Marketing Detector

Read prompt: `.claude/skills/marketing-report/prompts/detector.md`
Read knowledge base: `.claude/skills/analytics-report/references/analytics-kb.md`

Launch Detector as a subagent (Agent tool):
- **Input data:** `advertising` + `traffic` + `finance` (totals + by-model) + `external_marketing` + `sku_statuses` from `data_bundle`
- **Replace placeholders:**
  - `{{DATA}}` — the data blocks above (JSON)
  - `{{DEPTH}}` — "day" | "week" | "month"
  - `{{PERIOD_LABEL}}` — human-readable current period
  - `{{PREV_PERIOD_LABEL}}` — human-readable previous period
- **Inject:** full analytics-kb.md content as reference context

Save output as `findings_raw`.

### Wave B: Marketing Diagnostician

Read prompt: `.claude/skills/marketing-report/prompts/diagnostician.md`

Launch Diagnostician as a subagent (Agent tool):
- **Input data:** `findings_raw` + relevant raw data slices (advertising, traffic, finance by model)
- **Replace placeholders:**
  - `{{FINDINGS}}` — full `findings_raw` output
  - `{{RAW_DATA}}` — advertising + traffic + finance totals/models from `data_bundle`
  - `{{DEPTH}}` — "day" | "week" | "month"

Save output as `diagnostics`.

### Wave C: Marketing Strategist

Read prompt: `.claude/skills/marketing-report/prompts/strategist.md`

Launch Strategist as a subagent (Agent tool):
- **Input data:** `findings_raw` + `diagnostics`
- **Replace placeholders:**
  - `{{FINDINGS}}` — full `findings_raw` output
  - `{{DIAGNOSTICS}}` — full `diagnostics` output
  - `{{DEPTH}}` — "day" | "week" | "month"

Save output as `hypotheses`.

---

## Stage 3: Deep Analysis (2 analysts in parallel)

Launch BOTH analysts in a SINGLE message (2 Agent calls in parallel). Wait for both.

### Performance Analyst

Read prompt: `.claude/skills/marketing-report/prompts/performance-analyst.md`

Input: `finance` (wb_total + ozon_total + wb_models + ozon_models) + `advertising` (all blocks) + `external_marketing` + `sku_statuses` + `findings_raw` + `diagnostics` + `hypotheses` + analytics-kb.md + `DEPTH` + `PERIOD_LABEL` + `PREV_PERIOD_LABEL`

Produces sections: II (channels), V (external ads), VI (model matrix), VII (daily dynamics), VIII (avg check + DRR)

### Funnel Analyst

Read prompt: `.claude/skills/marketing-report/prompts/funnel-analyst.md`

Input: `traffic` + `advertising` (wb_organic_vs_paid, wb_ad_daily_series, ozon_ad_daily_series) + `finance` (totals for DRR context) + `findings_raw` + `diagnostics` + analytics-kb.md + `DEPTH` + `PERIOD_LABEL` + `PREV_PERIOD_LABEL`

Produces sections: III (funnels ASCII), IV (organic vs paid)

Save outputs as `performance_deep` and `funnel_deep`.

---

## Stage 4: Verification

Read prompt: `.claude/skills/marketing-report/prompts/verifier.md`

Launch verifier with `performance_deep` + `funnel_deep` + `findings_raw` + `hypotheses` + raw data slices for cross-check.

**10 checks:** DRR split, dual KPI external, funnel math (each step < previous), ROMI formula, organic+paid=total, model matrix coverage, no invented models, ASCII funnel numbers match data, Sheets data present, action direction matches problem.

**Verdict:** APPROVE / CORRECT / REJECT (max 1 retry).

---

## Stage 5: Synthesis + Publication

### 5.1 Synthesis

Read prompt: `.claude/skills/marketing-report/prompts/synthesizer.md`
Read formatting guide: `.claude/skills/analytics-report/templates/notion-formatting-guide.md`

Launch synthesizer with ALL outputs + analytics-kb.md.

**Output:** ONE `final_document_md` — clean Markdown that `md_to_notion_blocks()` converts to native Notion blocks.

### 11-Section Report Structure

| # | Section | Content |
|---|---------|---------|
| I | Исполнительная сводка | Таблица: метрика/значение/Δ/статус + резюме (3-5 строк) |
| II | Анализ по каналам | WB P&L маркетинга + OZON P&L + выводы |
| III | Анализ воронки | WB organic ASCII + WB ad ASCII + OZON ad ASCII + бенчмарки |
| IV | Органик vs Платное | 3 таблицы: доли, динамика, конверсии + инсайт |
| V | Внешняя реклама | Разбивка каналов + V.1 Блогеры + V.2 VK/Яндекс + V.3 SMM |
| VI | Матрица эффективности | Growth/Harvest/Optimize/Cut + WB детали + OZON детали |
| VII | Дневная динамика | WB: дата/показы/клики/CTR/расход/заказы/CPO + OZON аналогично |
| VIII | Средний чек и ДРР | Таблица по каналам + рекомендации по ассортименту |
| IX | Рекомендации | Срочные (3 дня) + Оптимизация (неделя) + Стратегические (месяц) |
| X | Прогноз | Таблица прогноз/обоснование + Риски + Возможности |
| XI | Advisor | 🔴 Критичные + 🟡 Внимание + 🟢 Позитивные с confidence% |

### Formatting Rules

- **ONLY clean Markdown.** NO HTML (`<table>`, `<tr>`, `<callout>` — not supported by md_to_notion_blocks)
- **Tables:** pipe format `| Col | Col |`. Bold in cells supported: `**+187К**`
- **Toggle headings:** `## ▶` for sections, `### ▶` for subsections
- **Callouts:** `> ⚠️ text`, `> 💡 text`, `> 📊 text`, `> ✅ text` → native Notion callout blocks
- **ASCII funnels:** inside ` ` `` ` ` ` code blocks (render as code in Notion)
- **Numbers:** `1 234 567 ₽`, `24,1%`, `+3,2 п.п.`, `8,8М`
- **Terminology:** Russian only (ДРР, СПП, not DRR, SPP in text)
- **Models:** Title Case (Wendy, Audrey). Only REAL models from sku_statuses
- **Quality flags:** Russian, not snake_case
- **Anomalies:** Δ доли > 3 п.п. → ⚠️ mark
- **Risks:** always with ₽ estimate + time horizon

### 5.2 Save MD file

Save to `docs/reports/{START}_{END}_marketing.md`.

### 5.3 Publish to Notion

Use `shared.notion_client.NotionClient.sync_report()`:

` ` `python
PYTHONPATH=. python3 -c "
import asyncio, os
from dotenv import load_dotenv; load_dotenv()
from shared.notion_client import NotionClient
from pathlib import Path

async def main():
    md = Path('docs/reports/{START}_{END}_marketing.md').read_text()
    client = NotionClient(token=os.getenv('NOTION_TOKEN'), database_id=os.getenv('NOTION_DATABASE_ID'))
    url = await client.sync_report(start_date='{START}', end_date='{END}', report_md=md, report_type='marketing_weekly', source='Claude Code')
    print(f'Published: {url}')

asyncio.run(main())
"
` ` `

**report_type mapping:** `day` → "marketing_daily", `week` → "marketing_weekly", `month` → "marketing_monthly"

### 5.4 Verify Notion Rendering

After publishing — fetch page via `mcp__claude_ai_Notion__notion-fetch` and verify:
- Tables render as native table blocks (not raw text)
- Toggle headings work
- Callouts render with icons and colors
- ASCII funnels render inside code blocks
- Bold text preserved in table cells

---

## Completion

Report to user (5-7 lines):
- Period analyzed and depth
- Verifier verdict
- Key finding #1 (biggest DRR/funnel change)
- Key finding #2 (most actionable model recommendation)
- Key finding #3 (external ad efficiency verdict)
- Files: MD path + Notion link

---

## Prompt Files Reference

| File | Role | Wave |
|------|------|------|
| `prompts/detector.md` | Marketing anomaly detection: DRR, funnel CR, traffic shifts, ROMI | 2A |
| `prompts/diagnostician.md` | Root causes: ads↔organic linkage, CPO drivers, CR drops | 2B |
| `prompts/strategist.md` | Budget reallocation, model actions, external ad decisions | 2C |
| `prompts/performance-analyst.md` | Channel P&L + model matrix + daily dynamics + external ads + avg check | 3 |
| `prompts/funnel-analyst.md` | ASCII funnels + organic vs paid analysis | 3 |
| `prompts/verifier.md` | Marketing-specific checks: DRR split, dual KPI, funnel math | 4 |
| `prompts/synthesizer.md` | Merge all into 11-section report with callouts | 5 |

**External references (read-only):**
- `.claude/skills/analytics-report/references/analytics-kb.md` — unified knowledge base
- `.claude/skills/analytics-report/templates/notion-formatting-guide.md` — Notion formatting spec
```

- [ ] **Step 2: Commit**

```bash
mkdir -p .claude/skills/marketing-report/prompts
git add .claude/skills/marketing-report/SKILL.md
git commit -m "feat(marketing-report): add SKILL.md orchestrator (5 stages, analytics engine)"
```

---

## Task 2: Wave A — Marketing Detector Prompt

**Files:**
- Create: `.claude/skills/marketing-report/prompts/detector.md`

- [ ] **Step 1: Write marketing detector prompt**

This subagent scans ALL marketing data and finds significant changes. It answers: "ЧТО изменилось в маркетинге?"

```markdown
# Detector — Маркетинговый анализ

> Роль: Найти ВСЕ значимые изменения в маркетинговых метриках Wookiee.
> Ты отвечаешь на вопрос: "ЧТО изменилось?"

---

## Вход

| Переменная | Описание |
|---|---|
| `{{DATA}}` | JSON: advertising + traffic + finance (totals + by-model) + external_marketing + sku_statuses |
| `{{DEPTH}}` | day / week / month |
| `{{PERIOD_LABEL}}` | Текущий период (человекочитаемый) |
| `{{PREV_PERIOD_LABEL}}` | Предыдущий период |

---

## Контекст

Прочитай Knowledge Base перед анализом:
`.claude/skills/analytics-report/references/analytics-kb.md`

Особенно секции:
- ДРР и реклама (целевые уровни, двойной KPI)
- Причинно-следственные паттерны (5 паттернов)
- Маркетинговые бенчмарки (CTR, CPC, CPM, CPO, CR)
- Матрица эффективности рекламы (Growth/Harvest/Optimize/Cut)
- Внешняя реклама (окна атрибуции, минимальный бюджет)

---

## Протокол сканирования

### 1. Бренд (WB+OZON суммарно)
- Общий ДРР (внутр + внешн)
- CPO средневзвешенный
- Общие заказы (органика + платное)
- Средний чек заказа

### 2. По каналам (WB и OZON отдельно)
- ДРР внутренний, ДРР внешний, ДРР общий
- CPO, ROMI
- Рекламные расходы (абс + % от выручки)
- Заказы с рекламы vs органические

### 3. Воронка (WB)
- Органическая: переходы → корзина → заказы → выкупы (CR на каждом шаге)
- Рекламная: показы → клики → корзина → заказы (CTR, CR на каждом шаге)
- OZON рекламная: показы → клики → заказы (CTR, CR)

### 4. Органик vs Платное (WB)
- Доля органических переходов / корзины / заказов
- Δ долей в п.п.
- CR органик vs CR платное на каждом шаге

### 5. По моделям
- ДРР, ROMI, CPO — для каждой модели
- Δ заказов с рекламы (%)
- Δ рекламного расхода (%)
- Классификация: Growth (ROMI>200%) / Harvest (100-200%) / Optimize (50-100%) / Cut (<50%)

### 6. Внешняя реклама
- Блогеры: бюджет, Δ%, охват, переходы, заказы
- VK/Яндекс: расход, переходы, CPO
- SMM: показы, переходы, CPC
- ДРР продаж + ДРР заказов (двойной KPI)

### 7. Дневная динамика
- Аномальные дни: CPO > 2× среднего, CTR < 50% среднего
- Тренды: растущий/падающий CPO, нестабильный CTR

---

## Пороги значимости

| Глубина | Δ доли | Δ абсолют (рекл. расход) | Δ% (CR) |
|---|---|---|---|
| day | > 2 п.п. | > 5К₽ | > 2 п.п. |
| week | > 3 п.п. | > 20К₽ | > 3 п.п. |
| month | > 2 п.п. | > 50К₽ | > 2 п.п. |

---

## Формат выхода

```
MARKETING_FINDINGS:
1. {severity: HIGH/MEDIUM, level: brand/channel/model/funnel/external, object: "WB funnel", metric: "CR_cart_to_order", current: 37.67, previous: 35.13, delta: +2.54, delta_unit: "п.п.", context: "Конверсия корзина→заказ выросла при падении CTR"}
2. {severity: HIGH, level: model, object: "Charlotte WB", metric: "ROMI", current: -2367.4, previous: -800.0, delta: -1567.4, delta_unit: "%", context: "Критически убыточная модель, расход растёт"}
3. ...

FUNNEL_CHANGES:
{
  wb_organic: {opens: {current: 457282, previous: 460310, delta_pct: -0.7}, cart: {...}, orders: {...}, buyouts: {...}},
  wb_ad: {impressions: {...}, clicks: {...}, cart: {...}, orders: {...}},
  ozon_ad: {impressions: {...}, clicks: {...}, orders: {...}},
  cr_changes: [{step: "WB organic open→cart", current: 6.59, previous: 6.66, delta_pp: -0.07}, ...]
}

EXTERNAL_FINDINGS:
{bloggers: {spend: ..., delta_pct: ..., drr_sales: ..., drr_orders: ...}, vk: {...}, smm: {...}}

MODEL_CLASSIFICATIONS:
{growth: ["Vuki"], harvest: ["Moon", "Joy", "Audrey", "Ruby", "Eva", "Alice"], optimize: ["Wendy"], cut: ["Charlotte"]}
```

---

## Правила

1. **ДРР ВСЕГДА с разбивкой** — внутренний (МП) и внешний (блогеры, VK) отдельно
2. **Двойной KPI внешней рекламы** — ДРР продаж И ДРР заказов
3. **Выкуп % — лаговый** (3-21 дн). НЕ использовать как причину в дневном отчёте (depth=day)
4. **ТОЛЬКО реальные модели** из sku_statuses. Никогда не придумывать
5. **Органика + Платное = Общее** — проверять сходимость
6. **CTR** — показы→клики (не складывать card_opens с impressions)
7. **CR** — ВСЕГДА показывать текущий и прошлый (Δ в п.п.)
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/marketing-report/prompts/detector.md
git commit -m "feat(marketing-report): add marketing detector prompt (Wave A)"
```

---

## Task 3: Wave B — Marketing Diagnostician Prompt

**Files:**
- Create: `.claude/skills/marketing-report/prompts/diagnostician.md`

- [ ] **Step 1: Write marketing diagnostician prompt**

```markdown
# Diagnostician — Маркетинговый анализ

> Роль: Определить ПРИЧИНЫ каждого значимого маркетингового изменения.
> Ты отвечаешь на вопрос: "ПОЧЕМУ это произошло?"

---

## Вход

| Переменная | Описание |
|---|---|
| `{{FINDINGS}}` | Выход Wave A (MARKETING_FINDINGS + FUNNEL_CHANGES + EXTERNAL_FINDINGS + MODEL_CLASSIFICATIONS) |
| `{{RAW_DATA}}` | advertising + traffic + finance (totals + by-model) из data_bundle |
| `{{DEPTH}}` | day / week / month |

---

## Контекст

Прочитай Knowledge Base: `.claude/skills/analytics-report/references/analytics-kb.md`

Особенно секции:
- Причинно-следственные паттерны (все 5 паттернов)
- Связка Реклама — Трафик — Заказы

---

## Диагностический протокол

Для каждого HIGH/MEDIUM finding примени причинно-следственную логику:

### Маркетинговые причинные цепочки

| Симптом | Проверь |
|---|---|
| ДРР вырос | Бюджет увеличился? CPO вырос? Заказы с рекл. упали при том же бюджете? |
| ДРР упал | Бюджет сократили? CPO снизился? Заказы выросли? |
| CPO вырос | CTR упал? CPC вырос? CR cart→order упал? Конкуренция за аукцион? |
| CTR упал | Креативы устарели? Позиции в выдаче ниже? Новые конкуренты? |
| CR cart→order упал | Цена выросла? Размеры закончились (OOS)? Доставка замедлилась? |
| Органика упала | Внешнюю рекламу сократили? → WB пессимизирует в выдаче → меньше органики |
| ROMI упал | Маржа модели упала? Или расход вырос без роста заказов? |
| Внешняя рекл. не конвертирует | Проверь окно атрибуции! Блогеры: 7-14 дней. VK: 3-7 дней |

### КРИТИЧЕСКАЯ СВЯЗКА: внешняя реклама ↔ органика

Если внешняя реклама сокращена И органический трафик упал → ОБЯЗАТЕЛЬНО связать:
"Сокращение внешней рекламы → меньше продаж → WB пессимизирует в выдаче → падение органических показов"

### Расчёт ₽-эффекта

Для каждого finding: "если метрику вернуть к прошлому уровню → +X₽ маржи"

Формулы:
- ДРР эффект: `(current_drr - prev_drr) / 100 * current_revenue`
- CPO эффект: `(current_cpo - prev_cpo) * current_ad_orders`
- CR эффект: `current_traffic * (prev_cr - current_cr) / 100 * avg_order_value * margin_pct`
- ROMI эффект: `current_ad_spend * (target_romi - current_romi) / 100`

---

## Формат выхода

```
MARKETING_DIAGNOSTICS:
1. {finding_id: 1, cause: "CTR WB снизился с 2,39% до 2,32% → клики -14,5% при стабильных показах. Причина: рост аукционных ставок + устаревшие креативы (CTR < 3% нормы)", confidence: HIGH, effect_rub: 25000, causal_chain: "CTR↓ → клики↓ → заказы с рекл.↓ → ДРР не снижается при снижении расхода", related_findings: [3, 5]}
2. {finding_id: 4, cause: "Charlotte: ROMI -2367% из-за отрицательной маржи модели (-убыток) при продолжающихся рекл. расходах 11К/нед. Реклама генерирует заказы (+121%), но каждый заказ убыточен", confidence: HIGH, effect_rub: 11061, causal_chain: "Отрицательная маржа + реклама = усиление убытков", related_findings: []}
3. ...

CROSS_DOMAIN_LINKS:
1. {link: "Сокращение VK рекламы (-67,5%) → органический трафик WB стабилен (-0,7%). Связь слабая — VK не был основным драйвером органики", confidence: MEDIUM}
2. ...
```

---

## Правила

1. **Каждый диагноз — с causal_chain** (цепочка причин, не просто "метрика упала")
2. **₽-эффект обязателен** для каждого HIGH finding
3. **Внешняя реклама: учитывай окна атрибуции** — не делать вывод "не конвертирует" сразу
4. **ЗАПРЕЩЕНО:** "возможно", "может быть", "вероятно" без confidence уровня
5. **Двойной KPI:** если ДРР продаж высокий, но ДРР заказов в норме → НЕ рекомендовать сокращение
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/marketing-report/prompts/diagnostician.md
git commit -m "feat(marketing-report): add marketing diagnostician prompt (Wave B)"
```

---

## Task 4: Wave C — Marketing Strategist Prompt

**Files:**
- Create: `.claude/skills/marketing-report/prompts/strategist.md`

- [ ] **Step 1: Write marketing strategist prompt**

```markdown
# Strategist — Маркетинговый анализ

> Роль: Сформулировать конкретные ДЕЙСТВИЯ с оценкой ₽-эффекта.
> Ты отвечаешь на вопрос: "ЧТО ДЕЛАТЬ?"

---

## Вход

| Переменная | Описание |
|---|---|
| `{{FINDINGS}}` | Выход Wave A (все findings) |
| `{{DIAGNOSTICS}}` | Выход Wave B (все диагнозы + cross-domain links) |
| `{{DEPTH}}` | day / week / month |

---

## Контекст

Прочитай Knowledge Base: `.claude/skills/analytics-report/references/analytics-kb.md`

Особенно:
- Матрица эффективности рекламы (ROMI → действие)
- Матрица решений по двойному KPI
- Внешняя реклама: окна атрибуции, минимальный бюджет блогера

---

## Протокол формирования гипотез

### Матрица действий по ROMI

| ROMI | Действие | Тип |
|---|---|---|
| < 50% (или отрицательный) | СТОП рекламы | P0 — срочное |
| 50-100% | Сокращение бюджета на 30-50% | P1 — важное |
| 100-200% | Оптимизация ключей, снижение ДРР | P2 — оптимизация |
| > 200% | Масштабирование бюджета +20-30% | P2 — рост |

**Исключения:**
- Новые модели < 4 недель → инвестиционный период, не Cut
- Growth-модели с ростом > 20% WoW → не Optimize, даже если ROMI 100-200%

### Типы действий

1. **Бюджет:** увеличить / сократить / перераспределить / остановить
2. **Ключевые слова:** добавить минус-слова / увеличить ставку на генераторы
3. **Внешняя реклама:** масштабировать канал / оптимизировать / отказаться
4. **Воронка:** улучшить CTR (креативы) / CR (карточки) / конверсию (цены/размеры)
5. **Ассортимент:** продвигать высокомаржинальные / снизить цену на залежи

### "Что если" сценарии

Для каждого P0-P1 действия — расчёт:
- "Если остановить рекламу Charlotte → экономия X₽/нед, 0 потерянных заказов (маржа отрицательная)"
- "Если увеличить бюджет Vuki на 20% → +Y заказов/нед при ROMI >1000%"

---

## Формат выхода

```
MARKETING_HYPOTHESES:
1. {priority: P0, type: "budget", object: "Charlotte WB", fact: "ROMI -2367%, расход 11К/нед, каждый заказ убыточен", cause: "Отрицательная маржа модели", action: "Немедленно остановить всю рекламу Charlotte", metric: "ad_spend", base: 11061, target: 0, effect_rub: 11061, effect_unit: "₽/нед экономия", window: "сегодня", risks: "Потеря 12 заказов/нед (убыточных)"}
2. {priority: P0, type: "funnel", object: "WB buyout", fact: "Выкуп упал на 9,36 п.п. (49,66% → 40,30%)", cause: "Требуется анализ причин возвратов", action: "Проанализировать причины возвратов: качество, размеры, упаковка", metric: "buyout_rate", base: 40.3, target: 45.0, effect_rub: 150000, effect_unit: "₽/мес маржи", window: "3 дня", risks: "Лаг данных 3-21 дн"}
3. {priority: P1, type: "budget", object: "Vuki WB", fact: "ROMI 1229,6%, ДРР 1,9%, CPO 59,6₽", cause: "Суперэффективная модель, бюджет недоиспользован", action: "Увеличить рекламный бюджет на 20-30% с контролем ДРР <3%", metric: "ad_spend", base: 5000, target: 6500, effect_rub: 15000, effect_unit: "₽/нед доп. маржи", window: "неделя", risks: "Рост CPO при масштабировании"}
4. ...
```

Сортировать по |effect_rub| убывание. Тегировать: budget / funnel / external / keywords / assortment.

---

## Правила

1. **Каждое действие — с конкретной цифрой** (₽, %, шт). Не "увеличить бюджет", а "увеличить на 20К₽/нед"
2. **"Что если" обязательны** для P0 и P1
3. **Внешняя реклама:** учитывать окна атрибуции. Если блогер < 14 дней назад → "ожидать конверсию"
4. **Двойной KPI:** если ДРР продаж > нормы, но ДРР заказов в норме → "инвестиция, мониторить"
5. **Минимальный бюджет блогера:** 30 000₽ для оценки. Меньше → "недостаточно данных"
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/marketing-report/prompts/strategist.md
git commit -m "feat(marketing-report): add marketing strategist prompt (Wave C)"
```

---

## Task 5: Performance Analyst Prompt

**Files:**
- Create: `.claude/skills/marketing-report/prompts/performance-analyst.md`

- [ ] **Step 1: Write performance analyst prompt**

This is the core prompt — generates 5 of 11 sections: II (channels), V (external ads), VI (model matrix), VII (daily dynamics), VIII (avg check + DRR). Must match Oleg v2 etalon depth.

```markdown
# Performance Analyst — Маркетинговый анализ

> Роль: Глубокий анализ эффективности маркетинга по каналам, моделям, внешней рекламе.
> Генерирует секции II, V, VI, VII, VIII отчёта.

---

## Вход

| Переменная | Описание |
|---|---|
| `{{FINANCE}}` | finance: wb_total, ozon_total, wb_models, ozon_models (revenue, margin, orders для расчёта ДРР) |
| `{{ADVERTISING}}` | advertising: все блоки (breakdowns, model ROI, daily series, campaign stats, budget utilization) |
| `{{EXTERNAL_MARKETING}}` | external_marketing: bloggers, seedings, external_traffic (VK/Яндекс), smm_monthly, smm_weekly |
| `{{SKU_STATUSES}}` | sku_statuses: статусы моделей (Продается/Выводим/Архив/Запуск) |
| `{{FINDINGS}}` | Находки детектора (HIGH / MEDIUM) |
| `{{DIAGNOSTICS}}` | Диагностика причин |
| `{{HYPOTHESES}}` | Гипотезы и рекомендации |
| `{{DEPTH}}` | day / week / month |
| `{{PERIOD_LABEL}}` | Текущий период |
| `{{PREV_PERIOD_LABEL}}` | Предыдущий период |

---

## Контекст

Прочитай Knowledge Base: `.claude/skills/analytics-report/references/analytics-kb.md`

---

## Секции к генерации

### Секция II: Анализ по каналам

#### Wildberries

Таблица:

| Метрика | Текущая | Прошлая | Изменение |
|---|---|---|---|
| Выручка (до СПП) | ... | ... | ... |
| Маржа | ... | ... | ... |
| Маржинальность | ... | ... | ... п.п. |
| Заказы | ... | ... | ...% |
| Ср. чек | ... | ... | ...% |
| ДРР общий | ... | ... | ... п.п. |
| ДРР внутренний | ... | ... | ... п.п. |
| ДРР внешний | ... | ... | ... п.п. |
| CPO | ... | ... | ...% |

Вывод по WB (2-3 строки): ключевое изменение + причина + связь маржа↔реклама.

#### OZON

Аналогичная таблица. Добавить: OZON organic estimate = total orders - ad orders.

Вывод по OZON (2-3 строки).

**Данные:**
- Выручка, маржа, заказы → из `{{FINANCE}}` (wb_total, ozon_total)
- ДРР, CPO → из `{{ADVERTISING}}` (wb_external_breakdown, ozon_external_breakdown)
- ДРР внутренний = `adv_internal / revenue_before_spp * 100`
- ДРР внешний = `adv_external / revenue_before_spp * 100`
- ДРР общий = внутренний + внешний
- CPO = `total_ad_spend / ad_orders`

---

### Секция V: Внешняя реклама

#### Разбивка по каналам

| Канал | Расход ₽ | Изменение | Доля |
|---|---|---|---|
| Блогеры | ... | ...% | ...% |
| VK Реклама | ... | ...% | ...% |
| Внутренняя МП (WB) | ... | ...% | ...% |
| Внутренняя МП (OZON) | ... | ...% | ...% |
| Итого внешняя | ... | ...% | ...% |

**Оценка эффективности:**
- ДРР продаж (по выручке): `внешн_расход / wb_revenue * 100`
- ДРР заказов (по заказам): `внешн_расход / (wb_orders_count * avg_check) * 100`

Интерпретация по матрице двойного KPI из KB.

#### V.1 Блогеры (из Google Sheets)

Данные из `{{EXTERNAL_MARKETING}}.bloggers` (Sheet `1Y7uxZnrjHLBntoDLkKJBOt5-lmODRJ5QEkE19QBA8xk`).

Таблица (фильтр по датам периода):

| Артикул | Дата | Бюджет ₽ | Охват | Переходы | CR | Заказы | CPO |
|---|---|---|---|---|---|---|---|

Если данных за период нет → "Данные за период отсутствуют в Google Sheets"

#### V.2 VK + Яндекс (из Google Sheets)

Данные из `{{EXTERNAL_MARKETING}}.external_traffic` (Sheet `1h0NeYw_5Cn7mkI03QxUk_zkvJ7NGV1zFmAtXNW9euSU`).

| Канал | Расход ₽ | Охват | Переходы | CPO | Заказы |
|---|---|---|---|---|---|

#### V.3 SMM (из Google Sheets)

Данные из `{{EXTERNAL_MARKETING}}.smm_weekly` или `smm_monthly` (Sheet `19NXHQGWSFjeWiPE12R3YAy5u2IsLpTISrECpysPSdPU`).

| Метрика | Текущая | Прошлая | Изменение |
|---|---|---|---|
| Показы | ... | ... | ...% |
| Переходы | ... | ... | ...% |
| CPC | ... | ... | ...% |
| CR | ... | ... | ... п.п. |

---

### Секция VI: Матрица эффективности по моделям

#### Матрица классификации

| Категория | Модели | Критерий | Действие |
|---|---|---|---|
| Growth | ... | ROMI >200%, рост заказов | Увеличивать бюджет |
| Harvest | ... | ROMI 100-200%, стабильные | Поддерживать |
| Optimize | ... | ROMI 50-100%, или расход растёт без заказов | Снижать ДРР |
| Cut | ... | ROMI <50% или отрицательный | Отключить рекламу |

**Данные:** из `{{ADVERTISING}}.wb_model_ad_roi` и `ozon_model_ad_roi`. Классификация по ROMI.

#### Детальный анализ WB

| Модель | ДРР | ROMI | CPO ₽ | Заказы с рекл. (Δ%) | Расход (Δ%) | Рекомендация |
|---|---|---|---|---|---|---|

Все модели из `wb_model_ad_roi` с ненулевым расходом. Сортировка по |ΔМаржа|.

Выделить **bold** аномалии: ROMI < 0, расход > +50%, заказы < -30%.

#### Детальный анализ OZON

Аналогичная таблица из `ozon_model_ad_roi`.

---

### Секция VII: Дневная динамика рекламы

#### Wildberries

| Дата | Показы | Клики | CTR | Расход ₽ | Заказы | CPO ₽ |
|---|---|---|---|---|---|---|

Данные из `{{ADVERTISING}}.wb_ad_daily_series`. Все дни периода.

Анализ (2-3 строки): лучший/худший CPO, стабильность CTR, аномальные дни.

#### OZON

Аналогичная таблица из `ozon_ad_daily_series`.

Анализ аномальных дней.

---

### Секция VIII: Средний чек и связь с ДРР

| Канал | Ср.чек тек | Ср.чек прош | Δ | ДРР тек | ДРР прош |
|---|---|---|---|---|---|
| WB | ... | ... | ...% | ...% | ...% |
| OZON | ... | ... | ...% | ...% | ...% |

**Ср.чек** = `revenue_before_spp / orders_count` из `{{FINANCE}}`.

Анализ связи (3-5 строк):
- Рост чека компенсирует ДРР?
- Рекомендации по ассортименту в рекламе (какие модели продвигать для роста чека)
- Связь чек↔конверсия (высокий чек = ниже конверсия?)

---

## КРИТИЧЕСКИЕ ПРАВИЛА

1. **ТОЛЬКО чистый Markdown** — pipe-таблицы, `## ▶`, `### ▶`. Никакого HTML
2. **ТОЛЬКО реальные данные** из входных JSON. Никогда не придумывать числа
3. **ТОЛЬКО реальные модели** из sku_statuses. Запрещено: Devi, Luna, Elsa, Ariel, Jasmine
4. **ДРР ВСЕГДА с разбивкой** — внутренний + внешний
5. **Двойной KPI** для внешней рекламы — ДРР продаж И ДРР заказов
6. **Числа:** `1 234 567 ₽`, `24,1%`, `+3,2 п.п.`
7. **Значимые Δ выделять bold:** `**+137,7%**`, `**-2367%**`
8. **Терминология русская:** ДРР (не DRR), СПП (не SPP), Выручка (не Revenue)
9. **Пустые ячейки:** если данных нет → "н/д" с причиной. Не оставлять пустые `—`
10. **Callouts:** `> ⚠️ text` после аномалий, `> 💡 text` после инсайтов
11. **Внешняя реклама из Sheets:** если данных нет → "Данные за период отсутствуют в Google Sheets". НЕ придумывать
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/marketing-report/prompts/performance-analyst.md
git commit -m "feat(marketing-report): add performance analyst prompt (channels, models, daily dynamics, external ads)"
```

---

## Task 6: Funnel Analyst Prompt

**Files:**
- Create: `.claude/skills/marketing-report/prompts/funnel-analyst.md`

- [ ] **Step 1: Write funnel analyst prompt**

```markdown
# Funnel Analyst — Маркетинговый анализ

> Роль: Глубокий анализ воронки продаж и соотношения органика/платное.
> Генерирует секции III и IV отчёта.

---

## Вход

| Переменная | Описание |
|---|---|
| `{{TRAFFIC}}` | traffic: wb_total, wb_by_model, ozon_total, wb_organic_vs_paid, wb_organic_by_status, ozon_organic_estimated |
| `{{ADVERTISING}}` | advertising: wb_ad_daily_series, ozon_ad_daily_series (для рекламной воронки) |
| `{{FINANCE}}` | finance: wb_total, ozon_total (для контекста DRR) |
| `{{FINDINGS}}` | Находки детектора |
| `{{DIAGNOSTICS}}` | Диагностика причин |
| `{{DEPTH}}` | day / week / month |
| `{{PERIOD_LABEL}}` | Текущий период |
| `{{PREV_PERIOD_LABEL}}` | Предыдущий период |

---

## Контекст

Прочитай Knowledge Base: `.claude/skills/analytics-report/references/analytics-kb.md`

Особенно секции:
- Нормы конверсии воронки
- Маркетинговые бенчмарки

---

## Секции к генерации

### Секция III: Анализ воронки

#### WB — Органическая воронка

ASCII-диаграмма (ОБЯЗАТЕЛЬНА):

```
┌──────────────────────────────────────────────────┐
│                 ОРГАНИЧЕСКАЯ ВОРОНКА WB           │
│  {opens}  Переходы в карточку                     │
│     ▼ ({cr_open_cart}%)                           │
│  {cart}   Добавления в корзину  [{prev_cr}% → {delta}pp]│
│     ▼ ({cr_cart_order}%)                          │
│  {orders} Заказы                [{prev_cr}% → {delta}pp]│
│     ▼ ({cr_order_buyout}%)                        │
│  {buyouts} Выкупы               [{prev_cr}% → {delta}pp]│
└──────────────────────────────────────────────────┘
```

**Данные:** из `{{TRAFFIC}}.wb_total` — current period:
- `card_opens` → Переходы
- `add_to_cart` → Корзина
- `orders` → Заказы
- `buyouts` → Выкупы

CR расчёт:
- Переход→корзина: `add_to_cart / card_opens * 100`
- Корзина→заказ: `orders / add_to_cart * 100`
- Заказ→выкуп: `buyouts / orders * 100`

В скобках после каждого CR показать `[prev_cr% → Δpp]`.

**Бенчмарки (нижнее бельё):**
- Переход→корзина: норма 5-15%
- Корзина→заказ: норма 20-40%
- Заказ→выкуп: норма 40-65%

Оценка каждого шага: ✅ в норме / ⚠️ ниже нормы / 🔴 критично (CR < 50% от нижней границы нормы)

Особое внимание: если выкуп упал >5 п.п. → "🔴 Критическое падение конверсии выкупа — требует срочного анализа причин возвратов"

**ВАЖНО:** Выкуп % — лаговый показатель (3-21 дн). При depth=day отмечать: "⚠️ Лаговый показатель, интерпретировать с осторожностью"

#### WB — Рекламная воронка

ASCII-диаграмма:

```
┌──────────────────────────────────────────────────┐
│                 РЕКЛАМНАЯ ВОРОНКА WB              │
│  {impressions}  Показы                           │
│     ▼ ({ctr}%)                                    │
│  {clicks}   Клики               [{prev_ctr}% → {delta}pp]│
│     ▼ ({cr_click_cart}%)                          │
│  {cart}     Добавления в корзину [{prev_cr}% → {delta}pp]│
│     ▼ ({cr_cart_order}%)                          │
│  {orders}   Заказы              [{prev_cr}% → {delta}pp]│
└──────────────────────────────────────────────────┘
Полная конверсия: {full_cr}% ({prev_full_cr}% → {delta}pp)
```

**Данные:** из `{{ADVERTISING}}` — суммарные данные за период:
- WB ad: `views` → Показы, `clicks` → Клики, `to_cart` → Корзина, `orders` → Заказы

**Бенчмарки:**
- CTR: норма 3-7%
- Клик→корзина: норма 15-25%
- Корзина→заказ: норма 25-40%
- Полная конверсия: норма 2-5%

#### OZON — Рекламная воронка

ASCII-диаграмма:

```
┌──────────────────────────────────────────────────┐
│                 РЕКЛАМНАЯ ВОРОНКА OZON            │
│  {impressions}  Показы                           │
│     ▼ ({ctr}%)                                    │
│  {clicks}   Клики               [{prev_ctr}% → {delta}pp]│
│     ▼ ({cr_click_order}%)                         │
│  {orders}   Заказы              [{prev_cr}% → {delta}pp]│
└──────────────────────────────────────────────────┘
```

**Данные:** из `{{TRAFFIC}}.ozon_total` или `{{ADVERTISING}}.ozon_ad_daily_series` (суммировать).

Примечание: OZON organic показы/переходы недоступны. Показывать только рекламную воронку.

---

### Секция IV: Органика vs Платное (WB)

**Данные:** из `{{TRAFFIC}}.wb_organic_vs_paid`.

#### Таблица 4а — Доли трафика

| Метрика | Органика % | Платное % | Δ органики (п.п.) |
|---|---|---|---|
| Переходы | ... | ... | ... |
| Корзина | ... | ... | ... |
| Заказы | ... | ... | ... |

Расчёт:
- Органика % переходов = `organic_opens / (organic_opens + ad_clicks) * 100`
- Органика % корзины = `organic_cart / (organic_cart + ad_cart) * 100`
- Органика % заказов = `organic_orders / (organic_orders + ad_orders) * 100`
- Δ = текущий% - прошлый%

#### Таблица 4б — Динамика

| Метрика | Текущая | Прошлая | Изменение |
|---|---|---|---|
| Органические переходы | ... | ... | ...% |
| Платные клики | ... | ... | ...% |
| Органические заказы | ... | ... | ...% |
| Платные заказы | ... | ... | ...% |

#### Таблица 4в — Конверсии

| Шаг | Органика CR | Платное CR | Разница |
|---|---|---|---|
| Переход→корзина | ... | ... | ... п.п. |
| Корзина→заказ | ... | ... | ... п.п. |
| Полная CR | ... | ... | ... п.п. |

Расчёт:
- Органика CR переход→корзина = `organic_cart / organic_opens * 100`
- Платное CR клик→корзина = `ad_cart / ad_clicks * 100`
- Полная CR органика = `organic_orders / organic_opens * 100`
- Полная CR платное = `ad_orders / ad_clicks * 100`

**Ключевой инсайт (3-5 строк):**
- Органика растёт/падает? (направление + причина)
- Что это значит для ДРР? (если органика растёт → зависимость от рекламы снижается)
- Связь с внешней рекламой (если внешнюю сократили → как это повлияло на органику)

---

## КРИТИЧЕСКИЕ ПРАВИЛА

1. **ASCII-диаграммы ОБЯЗАТЕЛЬНЫ** — это ключевая особенность маркетингового отчёта
2. **ASCII внутри ` ` `` ` ` `` ` ` ` блоков** — для корректного рендера в Notion как code block
3. **Каждый CR — текущий + прошлый + Δ в п.п.** Не показывать CR без сравнения
4. **Бенчмарки после каждой воронки** с оценкой (✅/⚠️/🔴)
5. **Выкуп — лаговый** (3-21 дн). Помечать при depth=day
6. **ТОЛЬКО чистый Markdown** — pipe-таблицы. Никакого HTML
7. **ТОЛЬКО реальные числа** из входных данных. Не придумывать
8. **Числа:** `1 234 567 ₽`, `24,1%`, `+3,2 п.п.`
9. **Callouts:** `> ⚠️ text` при аномалиях CR, `> 💡 text` при инсайтах
10. **Если данных нет** (organic unavailable на OZON) → явно указать "Органические данные OZON недоступны"
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/marketing-report/prompts/funnel-analyst.md
git commit -m "feat(marketing-report): add funnel analyst prompt (ASCII funnels, organic vs paid)"
```

---

## Task 7: Marketing Verifier Prompt

**Files:**
- Create: `.claude/skills/marketing-report/prompts/verifier.md`

- [ ] **Step 1: Write verifier prompt**

```markdown
# Verifier — Маркетинговый отчёт

> Роль: Проверить корректность маркетингового анализа перед публикацией.
> Вердикт: APPROVE / CORRECT / REJECT

---

## Вход

| Переменная | Описание |
|---|---|
| `{{PERFORMANCE_DEEP}}` | Выход Performance Analyst (секции II, V, VI, VII, VIII) |
| `{{FUNNEL_DEEP}}` | Выход Funnel Analyst (секции III, IV) |
| `{{FINDINGS}}` | Находки детектора |
| `{{HYPOTHESES}}` | Гипотезы стратега |
| `{{RAW_DATA}}` | Исходные данные для cross-check |

---

## 10 проверок

### 1. ДРР разбивка
ДРР ВСЕГДА показан с разбивкой на внутренний и внешний.
- ДРР общий ≈ ДРР внутр + ДРР внешн (±0,1 п.п.)
- Формула: `ad_spend / revenue * 100`

### 2. Двойной KPI внешней рекламы
Секция V содержит ОБА:
- ДРР продаж = `external_spend / revenue * 100`
- ДРР заказов = `external_spend / (orders * avg_check) * 100`

### 3. Воронка: математическая корректность
Каждый следующий шаг < предыдущего:
- WB organic: opens > cart > orders > buyouts
- WB ad: impressions > clicks > cart > orders
- OZON ad: impressions > clicks > orders
- CR на каждом шаге: 0% < CR < 100%

### 4. ROMI формула
`ROMI = (margin - ad_spend) / ad_spend * 100`
- Проверить для каждой модели в секции VI
- ROMI < 0 возможен (когда маржа < расхода)
- ROMI > 5000% → подозрительно, проверить данные

### 5. Органика + Платное = Общее
- Органические заказы + Платные заказы ≈ Общие заказы (±5%)
- Органические переходы + Платные клики ≈ Общие переходы (±5%)

### 6. Матрица эффективности — полнота
- ВСЕ модели с ненулевым рекламным расходом присутствуют
- Каждая модель в одной категории (Growth/Harvest/Optimize/Cut)
- Нет дублей моделей

### 7. Модели — только реальные
Сверить все упомянутые модели с sku_statuses.
- Запрещённые: Devi, Luna, Elsa, Ariel, Jasmine (НЕ СУЩЕСТВУЮТ)
- Допустимые: только из sku_statuses

### 8. ASCII воронки — числа совпадают
Числа внутри ASCII-диаграмм = числа в таблицах ±1%.

### 9. Sheets-данные — отмечены
Если данные из Google Sheets пустые → в отчёте написано "Данные отсутствуют", а не пустые ячейки.

### 10. Направление действий
- ROMI < 0 → действие: СТОП (не "оптимизировать")
- ROMI > 200% → действие: масштабировать (не "сократить")
- Выкуп упал → действие: анализ причин (не "снизить цену")
- CTR < нормы → действие: обновить креативы (не "увеличить бюджет")

---

## Формат вердикта

```
VERDICT: APPROVE | CORRECT | REJECT

CHECKS:
1. ДРР разбивка: ✅ / ❌ {details}
2. Двойной KPI: ✅ / ❌ {details}
3. Воронка математика: ✅ / ❌ {details}
4. ROMI формула: ✅ / ❌ {details}
5. Органика+Платное=Общее: ✅ / ❌ {details}
6. Матрица полнота: ✅ / ❌ {details}
7. Реальные модели: ✅ / ❌ {details}
8. ASCII числа: ✅ / ❌ {details}
9. Sheets данные: ✅ / ❌ {details}
10. Направление действий: ✅ / ❌ {details}

CORRECTIONS (if CORRECT):
- Section VI, model "Wendy": ROMI should be 141.0%, not 143.2%
- ...

RE_RUN (if REJECT):
- Re-run funnel-analyst: reason
```

**Правила вердикта:**
- APPROVE: 0 ошибок
- CORRECT: 1-3 minor ошибки (числа ±5%, форматирование)
- REJECT: >3 ошибок ИЛИ любая критическая (неверная формула, выдуманная модель, пропущена секция). Max 1 retry.
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/marketing-report/prompts/verifier.md
git commit -m "feat(marketing-report): add marketing verifier prompt (10 checks)"
```

---

## Task 8: Synthesizer Prompt

**Files:**
- Create: `.claude/skills/marketing-report/prompts/synthesizer.md`

- [ ] **Step 1: Write synthesizer prompt**

```markdown
# Synthesizer — Маркетинговый отчёт (чистый Markdown)

> Роль: Собрать финальный 11-секционный маркетинговый отчёт из данных всех субагентов.
> Формат: ЧИСТЫЙ MARKDOWN — никакого HTML. Таблицы через `|`, заголовки через `## ▶`.

---

## Вход

| Переменная | Описание |
|---|---|
| `{{PERFORMANCE_DEEP}}` | Секции II, V, VI, VII, VIII от Performance Analyst |
| `{{FUNNEL_DEEP}}` | Секции III, IV от Funnel Analyst |
| `{{FINDINGS}}` | Находки детектора (HIGH / MEDIUM) |
| `{{DIAGNOSTICS}}` | Диагностика причин |
| `{{HYPOTHESES}}` | Гипотезы и рекомендации (P0-P3) |
| `{{DEPTH}}` | day / week / month |
| `{{PERIOD_LABEL}}` | Текущий период |
| `{{PREV_PERIOD_LABEL}}` | Предыдущий период |

---

## КРИТИЧЕСКИЕ ПРАВИЛА

### Формат
1. **ТОЛЬКО чистый Markdown.** Никакого HTML: никаких `<table>`, `<tr>`, `<td>`, `<callout>`, `<br>`. Notion API не рендерит HTML.
2. **Таблицы** — ТОЛЬКО pipe-формат: `| Колонка1 | Колонка2 |`
3. **Toggle-заголовки** — `## ▶ Название секции` (символ ▶ обязателен для свёртки в Notion)
4. **Форматирование** — `**жирный**`, `*курсив*`, `` `код` ``
5. **Разделители** — `---` между секциями
6. **ASCII-воронки** — внутри ``` блоков

### Данные
7. **ТОЛЬКО реальные данные.** Если данных нет — "Данные за период отсутствуют". НИКОГДА не придумывать числа.
8. **ТОЛЬКО реальные модели** из входных данных. ЗАПРЕЩЕНО придумывать модели.
9. **ВСЕ ячейки заполнены.** Если данных нет — "н/д" с причиной.

### Терминология (РУССКАЯ)
10. ДРР (не DRR), СПП (не SPP), Выручка (не Revenue), Маржа (не Margin), Заказы (не Orders)

### Числа
11. Формат: `1 234 567 ₽`, `24,1%`, `+3,2 п.п.`
12. Крупные суммы: `8,8М` или `42,8 млн`
13. Значимые изменения выделять bold: `**+137,7%**`, `**-2367%**`

### Стилистика (эталон: Маркетинговый анализ за 16-22 марта 2026)
14. **Читаемость** — короткие предложения, причинно-следственные цепочки, конкретные цифры
15. **Callout-блоки** — после ключевых секций (I, III, VI, IX, XI):
    - Позитивный: `> ✅ Текст`
    - Негативный: `> ❌ Текст`
    - Предупреждение: `> ⚠️ Текст`
    - Инсайт: `> 💡 Текст`
    - Нейтральный: `> 📊 Текст`
16. **Подсветка в таблицах** — значимые Δ выделять **bold**
17. **Краткость** — после каждой таблицы 1-3 строки интерпретации

---

## Структура отчёта (11 секций)

### Один выход: `final_document_md`

```
# Еженедельный маркетинговый анализ Wookiee
**Период:** {PERIOD_LABEL}

## ▶ I. Исполнительная сводка
## ▶ II. Анализ по каналам
## ▶ III. Анализ воронки
## ▶ IV. Органик vs Платное
## ▶ V. Внешняя реклама
## ▶ VI. Матрица эффективности по моделям
## ▶ VII. Дневная динамика рекламы
## ▶ VIII. Средний чек и связь с ДРР
## ▶ IX. Рекомендации и план действий
## ▶ X. Прогноз на следующую неделю
## ▶ XI. Рекомендации Advisor
```

---

## Секции

### I. Исполнительная сводка

**СИНТЕЗИРОВАТЬ из всех входов.** Не копировать из analyst — собрать бренд-уровень.

| Метрика | Значение | Изменение | Статус |
|---|---|---|---|
| Выручка (до СПП) | ... | ...% (... тыс.₽) | 🟢/⚠️/🔴 |
| Маржа | ... | ...% (... тыс.₽) | 🟢/⚠️/🔴 |
| Маржинальность | ... | ... п.п. | 🟢/⚠️/🔴 |
| Заказы | ... | ...% (... шт) | 🟢/⚠️/🔴 |
| Средний чек | ... | ...% (... ₽) | 🟢/⚠️/🔴 |
| Общий ДРР | ... | ... п.п. | 🟢/⚠️/🔴 |

Статусы:
- 🟢 Рост / Улучшение (позитивная динамика)
- ⚠️ Снижение / Внимание (умеренная проблема)
- 🔴 Критично (сильное отклонение или ниже порога)

**Краткое резюме (3-5 строк):** Главное изменение + причина + эффект на маржу. Связка реклама↔органика↔заказы.

> 📊 {Ключевой вывод одним предложением}

### II-VIII: Вставить из аналитиков

Секции II-VIII — вставить из `{{PERFORMANCE_DEEP}}` и `{{FUNNEL_DEEP}}` БЕЗ ИЗМЕНЕНИЙ.

Порядок вставки:
- II из `{{PERFORMANCE_DEEP}}`
- III из `{{FUNNEL_DEEP}}`
- IV из `{{FUNNEL_DEEP}}`
- V из `{{PERFORMANCE_DEEP}}`
- VI из `{{PERFORMANCE_DEEP}}`
- VII из `{{PERFORMANCE_DEEP}}`
- VIII из `{{PERFORMANCE_DEEP}}`

### IX. Рекомендации и план действий

**СИНТЕЗИРОВАТЬ из `{{HYPOTHESES}}`**, отсортировать по |effect_rub|.

#### Срочные (до 3 дней)

| Действие | Модель/Канал | Эффект | Приоритет |
|---|---|---|---|
| {P0 actions from hypotheses} | ... | ... | 🔴 Высокий |
| {P1 actions} | ... | ... | 🟡 Средний |

#### Оптимизация бюджета (неделя)

| Действие | Модель | Изменение бюджета | Ожидаемый эффект |
|---|---|---|---|
| {Budget reallocation from hypotheses} | ... | ... | ... |

**Итоговый эффект:** +X заказов/нед при экономии/доп.расходах Y ₽/нед.

#### Стратегические (месяц)

Нумерованный список из P2-P3 hypotheses:
1. Масштабирование эффективных моделей: {details}
2. Внешняя реклама: {details}
3. Воронка: {details}
4. Ассортимент: {details}

### X. Прогноз на следующую неделю

**СИНТЕЗИРОВАТЬ из `{{HYPOTHESES}}` и `{{DIAGNOSTICS}}`.**

| Метрика | Прогноз | Обоснование |
|---|---|---|
| Заказы WB | ... | ... |
| Заказы OZON | ... | ... |
| Общий ДРР | ... | ... |
| Маржинальность | ... | ... |

**Риски:**
1-4 пункта из diagnostics (негативные тренды)

**Возможности:**
1-4 пункта из hypotheses (позитивные действия)

### XI. Рекомендации Advisor

**СИНТЕЗИРОВАТЬ из `{{HYPOTHESES}}`**, группировка по severity.

#### 🔴 Критичные (делай сегодня)

**Сигнал:** {fact} → **Действие:** {action}. Эффект: {effect_rub}. Confidence: {confidence}%.

#### 🟡 Внимание (на этой неделе)

**Сигнал:** {fact} → **Действие:** {action}. Эффект: {effect_rub}. Confidence: {confidence}%.

#### 🟢 Позитивные сигналы

**Сигнал:** {fact} → **Действие:** {action}. Эффект: {effect_rub}. Confidence: {confidence}%.

---

## Проверка перед выводом

- [ ] Нет HTML тегов (поиск `<table`, `<tr`, `<td`, `<callout`)
- [ ] Все таблицы в pipe-формате (`| Col | Col |`)
- [ ] Все секции I-XI присутствуют
- [ ] ASCII-воронки внутри ``` блоков
- [ ] Нет выдуманных моделей
- [ ] Нет пустых ячеек где есть данные
- [ ] Терминология русская
- [ ] Toggle-заголовки: `## ▶` для секций
- [ ] Числа: пробелы в тысячах, ₽, %, п.п.
- [ ] ДРР с разбивкой: внутренний + внешний
- [ ] Двойной KPI внешней рекламы (ДРР продаж + ДРР заказов)
- [ ] Callout блоки после ключевых секций
- [ ] Значимые Δ выделены **bold**
- [ ] Advisor: 🔴🟡🟢 с confidence%
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/marketing-report/prompts/synthesizer.md
git commit -m "feat(marketing-report): add synthesizer prompt (11-section Notion report)"
```

---

## Task 9: E2E Test Run

**Files:** No new files — testing full pipeline.

- [ ] **Step 1: Run collector**

```bash
python3 scripts/analytics_report/collect_all.py --start 2026-03-16 --end 2026-03-22 --output /tmp/marketing-report-test.json
```

Use the same period as the etalon (16-22 March 2026) for comparison.

- [ ] **Step 2: Invoke the skill**

```
/marketing-report 2026-03-16 2026-03-22
```

- [ ] **Step 3: Verify output against etalon**

Compare with Notion etalon `32c58a2bd58781a3823bd03f03676fb8`:

1. MD file at `docs/reports/2026-03-16_2026-03-22_marketing.md`
2. Notion page created with ALL 11 sections
3. ASCII funnels present (3 funnels: WB organic, WB ad, OZON ad)
4. Organic vs Paid has 3 tables (доли, динамика, конверсии)
5. Model efficiency matrix has all models from sku_statuses
6. External ad section has dual KPI (ДРР продаж + ДРР заказов)
7. Daily dynamics table for both WB and OZON
8. Advisor section has 🔴🟡🟢 groups with confidence%
9. All numbers in correct format: `1 234 567 ₽`, `24,1%`
10. No HTML tags in output
11. All models are real (cross-check with sku_statuses)
12. Callout blocks render correctly in Notion

- [ ] **Step 4: Fix issues found during verification**

If any issues found, fix the relevant prompt and re-run.

---

## Summary

| Task | What | Files | Commits |
|---|---|---|---|
| 1 | SKILL.md orchestrator | 1 create | 1 |
| 2 | Marketing detector (Wave A) | 1 create | 1 |
| 3 | Marketing diagnostician (Wave B) | 1 create | 1 |
| 4 | Marketing strategist (Wave C) | 1 create | 1 |
| 5 | Performance analyst (channels, models, external, daily) | 1 create | 1 |
| 6 | Funnel analyst (ASCII funnels, organic vs paid) | 1 create | 1 |
| 7 | Marketing verifier (10 checks) | 1 create | 1 |
| 8 | Synthesizer (11-section report) | 1 create | 1 |
| 9 | E2E test | 0 create | 0 |
| **Total** | | **8 files** | **8 commits** |
