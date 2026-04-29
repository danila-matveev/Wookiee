---
name: logistics-report
description: Анализ логистики WB+OZON — расходы, индекс локализации, возвраты, остатки, оборачиваемость, рекомендации по допоставкам. Еженедельный + ежемесячный.
triggers:
  - /logistics-report
  - логистика
  - логистический отчёт
  - остатки и оборачиваемость
  - анализ логистики
---

# Logistics Report Skill

Еженедельный и ежемесячный анализ логистических расходов, остатков, оборачиваемости и рекомендации по допоставкам для бренда Wookiee (WB + OZON).

Архитектура: Python collector → Analyst → Verifier ‖ Synthesizer (parallel) → Notion.

## Quick Start

```
/logistics-report              → прошлая неделя (Пн–Вс)
/logistics-report week         → прошлая неделя
/logistics-report month        → прошлый месяц
/logistics-report 2026-04-01 2026-04-30   → произвольный период
```

**Результаты:**
- MD: `docs/reports/{START}_{END}_logistics.md`
- Notion: страница в "Аналитические отчеты"

---

## Stage 0: Parse Arguments

**Compute variables:**

```
If no args or "week":
  END = last Sunday
  START = END - 6 days
  DEPTH = "weekly"

If "month":
  END = last day of previous month
  START = 1st day of previous month
  DEPTH = "monthly"

If 2 dates:
  START = first date, END = second date
  DEPTH = "weekly" if (END-START).days <= 14 else "monthly"

CLOSED_PERIOD_END = END - 30 days  (for buyout/returns — lag)
```

Save: `START`, `END`, `DEPTH`, `CLOSED_PERIOD_END`.

---

## Stage 1: Data Collection

Run the Python collector:

```bash
python3 scripts/logistics_report/collect_data.py --start {START} --end {END} --output /tmp/logistics-{START}_{END}.json
```

Read the output JSON. Save as `data_bundle`.

**Validation gate:**
- Check `data_bundle["meta"]["errors"]`
- If 0–3 errors → proceed, note in `quality_flags`
- If >3 errors → report to user and STOP

**Blocks in JSON:**
- `logistics_cost` — WB + OZON logistics cost, % of revenue, per-unit cost (from `abc_date`)
- `indices` — WB Localization Index per cabinet (ИП + ООО) from vasily.db
- `returns` — buyout % by model from **closed period** (CLOSED_PERIOD_END, lag 30+ days)
- `inventory` — WB/OZON stock, MoySklad stock, turnover by model
- `resupply` — office warehouse stock from MoySklad
- `period.closed_end` — actual closed period date used for returns

---

## Stage 2: Analyst

Read prompt: `.claude/skills/logistics-report/prompts/analyst.md`

Launch as **subagent** (Agent tool):
- Replace `{{DATA_JSON}}` with full `data_bundle` JSON
- Replace `{{DEPTH}}` with `DEPTH`

Save output as `analyst_output`.

---

## Stage 3: Verifier + Synthesizer (PARALLEL)

Launch BOTH in a **single message** (2 Agent calls in parallel).

### Verifier

Read prompt: `.claude/skills/logistics-report/prompts/verifier.md`

Replace:
- `{{ANALYST_OUTPUT}}` with `analyst_output`
- `{{RAW_DATA}}` with `data_bundle`

Save as `verifier_result`.

### Synthesizer

Read prompt: `.claude/skills/logistics-report/prompts/synthesizer.md`

Replace:
- `{{ANALYST_OUTPUT}}` with `analyst_output`
- `{{RAW_DATA}}` with `data_bundle`
- `{{DEPTH}}` with `DEPTH`

Save as `synthesizer_output`.

---

## Stage 3 Gate: Verifier Decision

- `APPROVE` → proceed to Stage 4
- `CORRECT` → apply fixes, proceed
- `REJECT` → re-run Analyst once with error details. If REJECT again → publish with `> ⚠️ Отчёт не прошёл верификацию: {reason}`

---

## Stage 4: Save + Publish

### 4.1 Save MD

Save `synthesizer_output` to `docs/reports/{START}_{END}_logistics.md`.

### 4.2 Publish to Notion

```python
PYTHONPATH=. python3 -c "
import asyncio, os
from dotenv import load_dotenv; load_dotenv()
from shared.notion_client import NotionClient
from pathlib import Path

async def main():
    md = Path('docs/reports/{START}_{END}_logistics.md').read_text()
    client = NotionClient(token=os.getenv('NOTION_TOKEN'), database_id=os.getenv('NOTION_DATABASE_ID'))
    report_type = 'logistics_monthly' if '{DEPTH}' == 'monthly' else 'localization_weekly'
    url = await client.sync_report(start_date='{START}', end_date='{END}', report_md=md, report_type=report_type, source='Claude Code')
    print(f'Published: {url}')

asyncio.run(main())
"
```

---

## Completion

Report to user (5–7 lines):
- Period and depth
- Verifier verdict
- WB logistics cost (₽ and % revenue)
- Top deficit model (lost sales ₽)
- Top resupply recommendation
- Files: MD path + Notion link

---

## Report Sections (7 total)

| # | Section |
|---|---------|
| I | Сводка |
| II | Стоимость логистики |
| III | Индекс локализации WB |
| IV | Возвраты и выкупы (закрытый период — лаг 30+ дней) |
| V | Остатки и оборачиваемость |
| VI | Рекомендации по допоставкам |
| VII | Выводы и действия |

---

## Formatting Rules

- **ONLY clean Markdown.** No HTML.
- Callouts: `> ⚠️ text`, `> 💡 text`, `> 📊 text`, `> ✅ text`
- Tables: `| Модель | WB | OZON | МойСклад | Оборачиваемость | Статус |`
- Numbers: `1 234 567 ₽`, `24,1%`, `+3,2 пп`, `8,8М`
- **Bold** on significant Δ
- Returns section MUST label data as closed period (e.g. "данные за 15.03–14.04, лаг 30+ дней")
- Resupply quantities must not exceed MoySklad office stock
