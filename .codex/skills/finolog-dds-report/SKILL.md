---
name: finolog-dds-report
description: Анализ ДДС из Финолога — остатки, cashflow, прогноз кассового разрыва, 3 сценария. Еженедельный + ежемесячный.
triggers:
  - /finolog-dds-report
  - сводка ддс
  - отчёт финолог
  - кассовый разрыв
  - ддс отчёт
---

# Finolog DDS Report Skill

Еженедельный и ежемесячный отчёт по движению денежных средств из Финолога.
Архитектура: Python collector → Analyst → Verifier ‖ Synthesizer (parallel) → Notion.

## Quick Start

```
/finolog-dds-report           → прошлая неделя (Пн–Вс)
/finolog-dds-report week      → прошлая неделя
/finolog-dds-report month     → прошлый месяц
/finolog-dds-report 2026-04-01 2026-04-30   → произвольный период
```

**Результаты:**
- MD: `docs/reports/{START}_{END}_finolog_dds.md`
- Notion: страница в "Аналитические отчеты"

---

## Stage 0: Parse Arguments

**Input patterns:**
- No args / `week` → last full week (Mon–Sun)
- `month` → last full month
- 2 dates → custom period

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
```

Save: `START`, `END`, `DEPTH`.

---

## Stage 1: Data Collection

Run the Python collector:

```bash
python3 scripts/finolog_dds_report/collect_data.py --start {START} --end {END} --output /tmp/finolog-dds-{START}_{END}.json
```

Read the output JSON. Save as `data_bundle`.

**Validation gate:**
- Check `data_bundle["meta"]["errors"]`
- If 0–3 errors → proceed, note in `quality_flags`
- If >3 errors → report to user and STOP

**Blocks in JSON:**
- `balances` — остатки по компаниям: ИП Медведева + ООО ВУКИ, по назначениям
- `cashflow_current` — cashflow за период: группы + суммы прихода/расхода/сальдо
- `cashflow_previous` — то же для предыдущего периода (для сравнения)
- `forecast` — 12-месячный прогноз: доход, расход, сальдо, баланс по месяцам
- `period` — даты

---

## Stage 2: Analyst

Read prompt: `.claude/skills/finolog-dds-report/prompts/analyst.md`

Launch as **subagent** (Agent tool):
- Replace `{{DATA_JSON}}` with full `data_bundle` JSON
- Replace `{{DEPTH}}` with `DEPTH`

Save output as `analyst_output`.

---

## Stage 3: Verifier + Synthesizer (PARALLEL)

Launch BOTH in a **single message** (2 Agent calls in parallel).

### Verifier

Read prompt: `.claude/skills/finolog-dds-report/prompts/verifier.md`

Replace:
- `{{ANALYST_OUTPUT}}` with `analyst_output`
- `{{RAW_DATA}}` with `data_bundle`

Save as `verifier_result`.

### Synthesizer

Read prompt: `.claude/skills/finolog-dds-report/prompts/synthesizer.md`

Replace:
- `{{ANALYST_OUTPUT}}` with `analyst_output`
- `{{RAW_DATA}}` with `data_bundle`
- `{{DEPTH}}` with `DEPTH`

Save as `synthesizer_output`.

---

## Stage 3 Gate: Verifier Decision

After both complete:

- If `verifier_result.verdict == "APPROVE"` → proceed to Stage 4
- If `verifier_result.verdict == "CORRECT"` → apply `verifier_result.fixes` to `synthesizer_output`, proceed
- If `verifier_result.verdict == "REJECT"` → **re-run Analyst** (Stage 2 once) with `verifier_result.reason` appended to prompt, then re-run Stage 3. If REJECT again → publish with `> ⚠️ Отчёт не прошёл верификацию: {reason}` at the top.

---

## Stage 4: Save + Publish

### 4.1 Save MD

Save `synthesizer_output` to `docs/reports/{START}_{END}_finolog_dds.md`.

### 4.2 Publish to Notion

```python
PYTHONPATH=. python3 -c "
import asyncio, os
from dotenv import load_dotenv; load_dotenv()
from shared.notion_client import NotionClient
from pathlib import Path

async def main():
    md = Path('docs/reports/{START}_{END}_finolog_dds.md').read_text()
    client = NotionClient(token=os.getenv('NOTION_TOKEN'), database_id=os.getenv('NOTION_DATABASE_ID'))
    report_type = 'finolog_monthly' if '{DEPTH}' == 'monthly' else 'finolog_weekly'
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
- Total balance (free + funds)
- Cash gap status (3 scenarios)
- Top-1 expense trend finding
- Files: MD path + Notion link

---

## Report Sections

| DEPTH | Sections |
|-------|---------|
| weekly | I Остатки, II Cashflow, III Тренды расходов, IV Прогноз кассового разрыва, V Выводы |
| monthly | + VI Доли затрат, VII Структурные изменения |

---

## Formatting Rules

- **ONLY clean Markdown.** No HTML.
- Callouts: `> ⚠️ text`, `> 💡 text`, `> 📊 text`, `> ✅ text`
- Tables: pipe format `| Группа | Приход | Расход | Сальдо | Δ |`
- Numbers: `1 234 567 ₽`, `24,1%`, `+3,2 пп`, `8,8М`
- **Bold** on significant Δ: `**+24%**`, `**-4,6 пп**`
- Russian terminology only: Выручка, Закупки, Фонды, Кассовый разрыв
- All group names from `CATEGORY_GROUPS`: Выручка, Закупки, Логистика, Маркетинг, Налоги, ФОТ, Склад, Услуги, Кредиты
