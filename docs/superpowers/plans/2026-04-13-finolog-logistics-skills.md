# Finolog DDS Report + Logistics Report Skills — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create two new Claude Code skills (`finolog-dds-report` and `logistics-report`) with LLM-powered analysis, plus delete the obsolete `finolog_categorizer` agent.

**Architecture:** Python collector gathers data → Analyst LLM agent analyzes → Verifier + Synthesizer run in parallel → Notion publish. Both skills share the same 4-stage pattern. 3 prompts per skill (analyst, verifier, synthesizer).

**Tech Stack:** Python (data collectors), Claude Code skills (SKILL.md + prompts), Finolog API, WB/OZON data layer, MoySklad API, Notion API.

**Spec:** `docs/superpowers/specs/2026-04-13-finolog-logistics-skills-design.md`

---

## File Map

### New files
| File | Responsibility |
|------|----------------|
| `.claude/skills/finolog-dds-report/SKILL.md` | Orchestration: params, data collection commands, stage flow, Notion publish |
| `.claude/skills/finolog-dds-report/prompts/analyst.md` | Cash flow analysis: trends, scenarios, anomalies, recommendations |
| `.claude/skills/finolog-dds-report/prompts/verifier.md` | Arithmetic + fact checking for DDS report |
| `.claude/skills/finolog-dds-report/prompts/synthesizer.md` | Notion-format report assembly (5-7 sections) |
| `.claude/skills/logistics-report/SKILL.md` | Orchestration: params, data collection commands, stage flow, Notion publish |
| `.claude/skills/logistics-report/prompts/analyst.md` | Logistics analysis: costs, indices, returns, inventory, resupply |
| `.claude/skills/logistics-report/prompts/verifier.md` | Arithmetic + fact checking for logistics report |
| `.claude/skills/logistics-report/prompts/synthesizer.md` | Notion-format report assembly (7 sections) |
| `scripts/finolog_dds_report/__init__.py` | Package marker |
| `scripts/finolog_dds_report/collect_data.py` | Finolog data collector (balances, cashflow, forecast) |
| `scripts/logistics_report/__init__.py` | Package marker |
| `scripts/logistics_report/collect_data.py` | Logistics data collector (5 blocks) |

### Modified files
| File | Change |
|------|--------|
| `shared/notion_client.py:30-52` | Add `finolog_monthly` and `logistics_monthly` to `_REPORT_TYPE_MAP` |

### Deleted files
| Path | Reason |
|------|--------|
| `agents/finolog_categorizer/` (entire dir) | Daily categorization no longer needed |
| `agents/oleg/services/finolog_categorizer.py` | Oleg's copy of categorizer |
| `agents/oleg/services/finolog_categorizer_store.py` | Oleg's copy of categorizer store |
| `docs/archive/retired_agents/vasily_agent_runtime/` (entire dir) | Old Vasily, active version in `services/wb_localization/` |

---

## Task 1: Cleanup — Delete obsolete code

**Files:**
- Delete: `agents/finolog_categorizer/` (entire directory)
- Delete: `agents/oleg/services/finolog_categorizer.py`
- Delete: `agents/oleg/services/finolog_categorizer_store.py`
- Delete: `docs/archive/retired_agents/vasily_agent_runtime/` (entire directory)

- [ ] **Step 1: Verify no imports of finolog_categorizer elsewhere**

Run:
```bash
PYTHONPATH=. grep -r "finolog_categorizer" --include="*.py" . | grep -v "agents/finolog_categorizer/" | grep -v "agents/oleg/services/finolog_categorizer"
```
Expected: No results (or only comments/docs). If any active imports found, stop and report.

- [ ] **Step 2: Verify no imports of vasily_agent_runtime**

Run:
```bash
grep -r "vasily_agent_runtime" --include="*.py" . | grep -v "docs/archive/"
```
Expected: No results.

- [ ] **Step 3: Delete finolog_categorizer agent**

```bash
rm -rf agents/finolog_categorizer/
rm -f agents/oleg/services/finolog_categorizer.py
rm -f agents/oleg/services/finolog_categorizer_store.py
```

- [ ] **Step 4: Delete retired Vasily**

```bash
rm -rf docs/archive/retired_agents/vasily_agent_runtime/
```

- [ ] **Step 5: Run existing tests to verify nothing broke**

Run:
```bash
PYTHONPATH=. python -m pytest tests/ -x -q --timeout=30 2>&1 | head -30
```
Expected: All existing tests pass (or same failures as before deletion).

- [ ] **Step 6: Commit**

```bash
git add -A agents/finolog_categorizer/ agents/oleg/services/finolog_categorizer.py agents/oleg/services/finolog_categorizer_store.py docs/archive/retired_agents/vasily_agent_runtime/
git commit -m "chore: remove obsolete finolog_categorizer agent and retired Vasily runtime"
```

---

## Task 2: Add Notion report type mappings

**Files:**
- Modify: `shared/notion_client.py:30-52`

- [ ] **Step 1: Add monthly mappings to `_REPORT_TYPE_MAP`**

In `shared/notion_client.py`, find the `_REPORT_TYPE_MAP` dict and add two new entries after the existing `finolog_weekly` and `localization_weekly` entries:

```python
"finolog_monthly": ("Ежемесячная сводка ДДС", "Сводка ДДС"),
"logistics_monthly": ("Ежемесячный анализ логистики", "Анализ логистики"),
```

- [ ] **Step 2: Verify the mapping works**

Run:
```bash
PYTHONPATH=. python3 -c "
from shared.notion_client import NotionClient
import os
c = NotionClient(token='test', database_id='test')
# Access the class-level map to verify
from shared.notion_client import _REPORT_TYPE_MAP
assert 'finolog_monthly' in _REPORT_TYPE_MAP, 'finolog_monthly missing'
assert 'logistics_monthly' in _REPORT_TYPE_MAP, 'logistics_monthly missing'
assert _REPORT_TYPE_MAP['finolog_monthly'] == ('Ежемесячная сводка ДДС', 'Сводка ДДС')
print('All mappings OK')
"
```
Expected: `All mappings OK`

- [ ] **Step 3: Commit**

```bash
git add shared/notion_client.py
git commit -m "feat: add finolog_monthly and logistics_monthly Notion report type mappings"
```

---

## Task 3: Finolog DDS data collector

**Files:**
- Create: `scripts/finolog_dds_report/__init__.py`
- Create: `scripts/finolog_dds_report/collect_data.py`

- [ ] **Step 1: Create package**

```bash
mkdir -p scripts/finolog_dds_report
touch scripts/finolog_dds_report/__init__.py
```

- [ ] **Step 2: Write the collector**

Create `scripts/finolog_dds_report/collect_data.py`:

```python
"""Finolog DDS report data collector.

Usage:
    python scripts/finolog_dds_report/collect_data.py --start 2026-04-07 --end 2026-04-13
    python scripts/finolog_dds_report/collect_data.py --start 2026-04-07 --end 2026-04-13 --output /tmp/finolog.json
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import argparse
import asyncio
import json
from datetime import date, datetime, timedelta

from shared.config import config


async def _collect(start_date: str, end_date: str) -> dict:
    """Collect all Finolog data blocks for DDS report."""
    from agents.oleg.services.finolog_service import FinologService

    api_key = config.FINOLOG_API_KEY
    if not api_key:
        return {"meta": {"errors": 1, "quality_flags": ["FINOLOG_API_KEY not set"]}}

    svc = FinologService(api_key=api_key)
    errors: list[str] = []
    quality_flags: list[str] = []

    # --- Balances ---
    try:
        accounts = await svc._get_accounts()
        balances = svc._classify_accounts(accounts)
    except Exception as e:
        errors.append(f"balances: {e}")
        balances = {}

    # --- Cashflow current period ---
    try:
        cashflow_current = await svc._get_transactions_by_group(start_date, end_date)
    except Exception as e:
        errors.append(f"cashflow_current: {e}")
        cashflow_current = {}

    # --- Cashflow previous period (same length, shifted back) ---
    try:
        d_start = datetime.strptime(start_date, "%Y-%m-%d").date()
        d_end = datetime.strptime(end_date, "%Y-%m-%d").date()
        period_days = (d_end - d_start).days + 1
        prev_end = d_start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=period_days - 1)
        cashflow_previous = await svc._get_transactions_by_group(
            prev_start.isoformat(), prev_end.isoformat()
        )
    except Exception as e:
        errors.append(f"cashflow_previous: {e}")
        cashflow_previous = {}

    # --- Forecast ---
    try:
        total_balance = sum(
            acc.get("balance", 0)
            for acc in accounts
            if acc.get("currency_code") == "RUB"
        ) if accounts else 0
        forecast = await svc._build_forecast(total_balance, months=12)
    except Exception as e:
        errors.append(f"forecast: {e}")
        forecast = []

    return {
        "balances": balances,
        "cashflow_current": cashflow_current,
        "cashflow_previous": cashflow_previous,
        "forecast": forecast,
        "period": {"start": start_date, "end": end_date},
        "meta": {
            "errors": len(errors),
            "error_details": errors,
            "quality_flags": quality_flags,
            "collected_at": datetime.now().isoformat(),
        },
    }


def collect_finolog_dds(start_date: str, end_date: str) -> dict:
    """Synchronous wrapper for the async collector."""
    return asyncio.run(_collect(start_date, end_date))


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect Finolog DDS data")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--output", default=None, help="Output JSON path")
    args = parser.parse_args()

    data = collect_finolog_dds(args.start, args.end)

    output_path = args.output or f"/tmp/finolog-dds-{args.start}_{args.end}.json"
    Path(output_path).write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    print(f"Collected: {output_path}")
    print(f"Errors: {data['meta']['errors']}")

    if data["meta"]["errors"] > 3:
        print("GATE FAILED: too many errors")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

**IMPORTANT:** The `_get_transactions_by_group` and `_classify_accounts` methods may not exist on FinologService yet. During implementation:
1. Read `agents/oleg/services/finolog_service.py` fully
2. If these methods don't exist, extract the logic from `build_weekly_summary()` into separate callable methods
3. The collector needs: balances by company/purpose, transactions grouped by category (Выручка, Закупки, etc.), forecast

- [ ] **Step 3: Test the collector runs**

Run:
```bash
PYTHONPATH=. python scripts/finolog_dds_report/collect_data.py --start 2026-04-07 --end 2026-04-13 --output /tmp/test-finolog.json
```
Expected: JSON file created with `balances`, `cashflow_current`, `cashflow_previous`, `forecast` blocks. Check `meta.errors` is 0 or low.

- [ ] **Step 4: Commit**

```bash
git add scripts/finolog_dds_report/
git commit -m "feat(finolog-dds): add data collector for Finolog DDS report"
```

---

## Task 4: Logistics data collector

**Files:**
- Create: `scripts/logistics_report/__init__.py`
- Create: `scripts/logistics_report/collect_data.py`

- [ ] **Step 1: Create package**

```bash
mkdir -p scripts/logistics_report
touch scripts/logistics_report/__init__.py
```

- [ ] **Step 2: Write the collector**

Create `scripts/logistics_report/collect_data.py`:

```python
"""Logistics report data collector.

Usage:
    python scripts/logistics_report/collect_data.py --start 2026-04-07 --end 2026-04-13
    python scripts/logistics_report/collect_data.py --start 2026-03-01 --end 2026-03-31 --output /tmp/logistics.json
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import argparse
import json
from datetime import date, datetime, timedelta

from shared.config import config
from shared.data_layer.inventory import (
    get_moysklad_stock_by_model,
    get_ozon_avg_stock,
    get_ozon_turnover_by_model,
    get_wb_avg_stock,
    get_wb_turnover_by_model,
)


def _collect_logistics_cost(start_date: str, end_date: str) -> dict:
    """Block 1: WB logistics costs (ИП + ООО) + revenue for ratio."""
    from shared.data_layer import get_connection

    errors = []
    result = {"wb_ip": {}, "wb_ooo": {}, "ozon": {}, "revenue": {}}

    # WB logistics from DB (summary, not full audit)
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    cabinet,
                    SUM(delivery_rub) as logistics_cost,
                    COUNT(*) as shipments
                FROM orders
                WHERE date >= %s AND date < %s
                    AND delivery_rub > 0
                    AND source = 'wb'
                GROUP BY cabinet
            """, (start_date, end_date))
            for row in cur.fetchall():
                key = "wb_ip" if row[0] in ("ip", "ИП") else "wb_ooo"
                result[key] = {"logistics_cost": float(row[1]), "shipments": int(row[2])}
        conn.close()
    except Exception as e:
        errors.append(f"wb_logistics: {e}")

    # OZON logistics from DB
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    SUM(delivery_rub) as logistics_cost,
                    COUNT(*) as shipments
                FROM orders
                WHERE date >= %s AND date < %s
                    AND delivery_rub > 0
                    AND source = 'ozon'
            """, (start_date, end_date))
            row = cur.fetchone()
            if row and row[0]:
                result["ozon"] = {"logistics_cost": float(row[0]), "shipments": int(row[1])}
        conn.close()
    except Exception as e:
        errors.append(f"ozon_logistics: {e}")

    # Revenue for ratio
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT source, SUM(finishedprice) as revenue
                FROM orders
                WHERE date >= %s AND date < %s
                    AND iscancel::text IN ('0', 'false')
                GROUP BY source
            """, (start_date, end_date))
            for row in cur.fetchall():
                result["revenue"][row[0]] = float(row[1])
        conn.close()
    except Exception as e:
        errors.append(f"revenue: {e}")

    return result, errors


def _collect_indices(start_date: str, end_date: str) -> dict:
    """Block 2: WB Localization Index from logistics audit service."""
    errors = []
    result = {"il_ip": {}, "il_ooo": {}, "zones": {}, "problem_skus": []}

    # Try importing from existing localization service
    try:
        from services.wb_localization.run_localization import load_localization_data
        # Load pre-computed IL data if available
        # During implementation: check what functions are available in services/wb_localization/
        # and use the appropriate one to get IL, IRP, zone breakdown
    except Exception as e:
        errors.append(f"localization_index: {e}")

    return result, errors


def _collect_returns(start_date: str, end_date: str, closed_end: str) -> dict:
    """Block 3: Returns and buyouts from closed period."""
    from shared.data_layer import get_connection

    errors = []
    result = {"wb": {}, "ozon": {}}

    # Closed period = closed_end back 30 days
    d_closed = datetime.strptime(closed_end, "%Y-%m-%d").date()
    closed_start = (d_closed - timedelta(days=30)).isoformat()

    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    source,
                    LOWER(SPLIT_PART(supplierarticle, '/', 1)) as model,
                    COUNT(*) as orders,
                    SUM(CASE WHEN iscancel::text IN ('0', 'false') THEN 1 ELSE 0 END) as buyouts
                FROM orders
                WHERE date >= %s AND date < %s
                GROUP BY source, LOWER(SPLIT_PART(supplierarticle, '/', 1))
            """, (closed_start, closed_end))
            for row in cur.fetchall():
                channel = row[0]  # wb or ozon
                model = row[1]
                orders = int(row[2])
                buyouts = int(row[3])
                buyout_pct = round(buyouts / orders * 100, 1) if orders > 0 else 0
                if channel not in result:
                    result[channel] = {}
                result[channel][model] = {
                    "orders": orders,
                    "buyouts": buyouts,
                    "buyout_pct": buyout_pct,
                }
        conn.close()
    except Exception as e:
        errors.append(f"returns: {e}")

    return result, errors


def _collect_inventory(start_date: str, end_date: str) -> dict:
    """Block 4: Stock levels and turnover."""
    errors = []
    result = {}

    try:
        wb_stock = get_wb_avg_stock(start_date, end_date)
        ozon_stock = get_ozon_avg_stock(start_date, end_date)
        moysklad_stock = get_moysklad_stock_by_model()
        wb_turnover = get_wb_turnover_by_model(start_date, end_date)
        ozon_turnover = get_ozon_turnover_by_model(start_date, end_date)

        result = {
            "wb_stock": wb_stock,
            "ozon_stock": ozon_stock,
            "moysklad_stock": moysklad_stock,
            "wb_turnover": wb_turnover,
            "ozon_turnover": ozon_turnover,
        }
    except Exception as e:
        errors.append(f"inventory: {e}")

    return result, errors


def _collect_resupply() -> dict:
    """Block 5: MoySklad office stock for resupply recommendations."""
    from shared.clients.moysklad_client import MoySkladClient

    errors = []
    result = {}

    try:
        client = MoySkladClient(
            login=config.MOYSKLAD_LOGIN,
            password=config.MOYSKLAD_PASSWORD,
        )
        # STORE_MAIN = office warehouse
        office_stock = client.fetch_stock_by_store("4c51ead2-2731-11ef-0a80-07b100450c6a")
        result = {"office_stock": office_stock}
    except Exception as e:
        errors.append(f"resupply: {e}")

    return result, errors


def collect_logistics(start_date: str, end_date: str) -> dict:
    """Main collector: gathers all 5 blocks."""
    all_errors = []

    # Closed period = end_date - 30 days
    d_end = datetime.strptime(end_date, "%Y-%m-%d").date()
    closed_end = (d_end - timedelta(days=30)).isoformat()

    logistics_cost, errs = _collect_logistics_cost(start_date, end_date)
    all_errors.extend(errs)

    indices, errs = _collect_indices(start_date, end_date)
    all_errors.extend(errs)

    returns, errs = _collect_returns(start_date, end_date, closed_end)
    all_errors.extend(errs)

    inventory, errs = _collect_inventory(start_date, end_date)
    all_errors.extend(errs)

    resupply, errs = _collect_resupply()
    all_errors.extend(errs)

    return {
        "logistics_cost": logistics_cost,
        "indices": indices,
        "returns": returns,
        "inventory": inventory,
        "resupply": resupply,
        "period": {"start": start_date, "end": end_date, "closed_end": closed_end},
        "meta": {
            "errors": len(all_errors),
            "error_details": all_errors,
            "quality_flags": [],
            "collected_at": datetime.now().isoformat(),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect logistics report data")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--output", default=None, help="Output JSON path")
    args = parser.parse_args()

    data = collect_logistics(args.start, args.end)

    output_path = args.output or f"/tmp/logistics-{args.start}_{args.end}.json"
    Path(output_path).write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    print(f"Collected: {output_path}")
    print(f"Errors: {data['meta']['errors']}")

    if data["meta"]["errors"] > 3:
        print("GATE FAILED: too many errors")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

**IMPORTANT during implementation:**
1. The SQL queries above are approximations. Read the actual DB schema (`docs/database/`) to verify column names (`delivery_rub`, `finishedprice`, `supplierarticle`, `iscancel`, `source`).
2. `_collect_indices()` is a stub — read `services/wb_localization/` to find the right function to get IL/IRP data per cabinet.
3. `get_connection()` — verify the import path from `shared/data_layer`.
4. MoySklad credentials — check `shared/config.py` for exact attribute names.

- [ ] **Step 3: Test the collector runs**

Run:
```bash
PYTHONPATH=. python scripts/logistics_report/collect_data.py --start 2026-04-07 --end 2026-04-13 --output /tmp/test-logistics.json
```
Expected: JSON file with 5 blocks. Some blocks may have errors if data is unavailable — that's OK for now. Check `meta.errors` count.

- [ ] **Step 4: Commit**

```bash
git add scripts/logistics_report/
git commit -m "feat(logistics): add data collector for logistics report"
```

---

## Task 5: Finolog DDS skill — SKILL.md

**Files:**
- Create: `.claude/skills/finolog-dds-report/SKILL.md`

- [ ] **Step 1: Create skill directory**

```bash
mkdir -p .claude/skills/finolog-dds-report/prompts
```

- [ ] **Step 2: Write SKILL.md**

Create `.claude/skills/finolog-dds-report/SKILL.md` — the full orchestration document. Follow the exact pattern from `.claude/skills/finance-report/SKILL.md`.

Key sections to include:
- YAML frontmatter: `name: finolog-dds-report`, triggers: `/finolog-dds-report`, `сводка ддс`, `отчёт финолог`, `кассовый разрыв`
- Quick start with CLI examples
- Stage 0: Parameter parsing (week/month/custom dates)
- Stage 1: Data collection command: `python3 scripts/finolog_dds_report/collect_data.py --start {START} --end {END} --output /tmp/finolog-dds-{START}_{END}.json`
- Stage 1 validation: check `meta.errors`, abort if > 3
- Stage 2: Analyst subagent — read `prompts/analyst.md`, replace `{{DATA_JSON}}` with collector output, replace `{{DEPTH}}` with weekly/monthly
- Stage 3: Verifier + Synthesizer in parallel
  - Verifier: read `prompts/verifier.md`, replace `{{ANALYST_OUTPUT}}` and `{{RAW_DATA}}`
  - Synthesizer: read `prompts/synthesizer.md`, replace `{{ANALYST_OUTPUT}}` and `{{RAW_DATA}}` and `{{DEPTH}}`
- Stage 3 gate: if Verifier returns REJECT, re-run Analyst with error details (max 1 retry)
- Stage 4: Save MD to `docs/reports/{START}_{END}_finolog_dds.md`
- Stage 4: Notion publish command (exact Python snippet from spec)
- Stage 4: Report type = `finolog_weekly` or `finolog_monthly` based on DEPTH
- Completion: print summary to user

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/finolog-dds-report/SKILL.md
git commit -m "feat(finolog-dds): add SKILL.md orchestration"
```

---

## Task 6: Finolog DDS skill — prompts

**Files:**
- Create: `.claude/skills/finolog-dds-report/prompts/analyst.md`
- Create: `.claude/skills/finolog-dds-report/prompts/verifier.md`
- Create: `.claude/skills/finolog-dds-report/prompts/synthesizer.md`

- [ ] **Step 1: Write analyst.md**

The analyst prompt should instruct the LLM to:
- Receive `{{DATA_JSON}}` (all 5 data blocks from collector)
- Receive `{{DEPTH}}` (weekly or monthly)
- Analyze expense trends per group vs previous period
- Identify top-3 changes with ₽ and %
- Build 3 cash gap scenarios (optimistic +10%, base, pessimistic -20%)
- For each scenario: project balance month-by-month, flag when < 1M₽
- Flag anomalies: atypical transactions, sudden spikes
- Generate recommendations: fund status, months of runway, cost concerns
- If DEPTH=monthly: also analyze cost structure shifts (group shares, Δ > 3 пп)
- Output: structured JSON with keys: `expense_trends`, `cost_structure` (monthly only), `cash_gap_scenarios`, `anomalies`, `recommendations`
- Rules: Russian terminology, amounts as numbers (not formatted), confidence levels

- [ ] **Step 2: Write verifier.md**

The verifier prompt should:
- Receive `{{ANALYST_OUTPUT}}` and `{{RAW_DATA}}`
- Check: group sums = total
- Check: balances in analyst output match raw data
- Check: forecast scenarios are internally consistent (pessimistic < base < optimistic)
- Check: all amounts are reasonable (no negative balances unless explained, no >100% shares)
- Verdict: `APPROVE` / `CORRECT` (with specific fixes in JSON) / `REJECT` (with reason)
- Output: JSON with `verdict`, `fixes` (if CORRECT), `reason` (if REJECT)

- [ ] **Step 3: Write synthesizer.md**

The synthesizer prompt should:
- Receive `{{ANALYST_OUTPUT}}`, `{{RAW_DATA}}`, `{{DEPTH}}`
- Assemble Notion-format report using enhanced Markdown:
  - Tables: `<table fit-page-width="true" header-row="true" header-column="true">`
  - Header rows: `<tr color="blue_bg">`
  - Positive: `color="green_bg"`, negative: `color="red_bg"`
  - Callouts: `<callout icon="⚠️" color="yellow_bg">`, etc.
- Sections I-V (weekly) or I-VII (monthly) per spec
- Numbers: `1 234 567 ₽`, `24,1%`, `+3,2 пп`, `8,8М`
- Bold on significant changes: `**+24%**`
- Russian only: Выручка, not Revenue
- Output: complete Markdown document ready for `md_to_notion_blocks()`

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/finolog-dds-report/prompts/
git commit -m "feat(finolog-dds): add analyst, verifier, synthesizer prompts"
```

---

## Task 7: Logistics skill — SKILL.md

**Files:**
- Create: `.claude/skills/logistics-report/SKILL.md`

- [ ] **Step 1: Create skill directory**

```bash
mkdir -p .claude/skills/logistics-report/prompts
```

- [ ] **Step 2: Write SKILL.md**

Same pattern as Task 5 but for logistics:
- YAML frontmatter: `name: logistics-report`, triggers: `/logistics-report`, `логистика`, `логистический отчёт`, `остатки и оборачиваемость`
- Stage 1: `python3 scripts/logistics_report/collect_data.py --start {START} --end {END} --output /tmp/logistics-{START}_{END}.json`
- Stage 2: Analyst with `prompts/analyst.md`
- Stage 3: Verifier + Synthesizer parallel
- Stage 4: Save + Notion publish with `report_type = "localization_weekly"` or `"logistics_monthly"`

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/logistics-report/SKILL.md
git commit -m "feat(logistics): add SKILL.md orchestration"
```

---

## Task 8: Logistics skill — prompts

**Files:**
- Create: `.claude/skills/logistics-report/prompts/analyst.md`
- Create: `.claude/skills/logistics-report/prompts/verifier.md`
- Create: `.claude/skills/logistics-report/prompts/synthesizer.md`

- [ ] **Step 1: Write analyst.md**

The analyst prompt should instruct the LLM to:
- Receive `{{DATA_JSON}}` (all 5 blocks from logistics collector)
- Analyze logistics cost: trend, % of revenue, per-unit, ИП vs ООО
- Analyze localization index: dynamics, problem regions, ₽ impact
- Analyze returns: growth/decline by model, ONLY from closed period (lag 30+ days)
- Assess inventory: deficit → lost sales ₽ (order_velocity × days × avg_price), overstock → frozen capital ₽
- Generate resupply recs: model → warehouse → qty (constrained by MoySklad availability)
- Flag anomalies: cost spikes, buyout drops, dead stock
- Output: JSON with keys: `logistics_cost_analysis`, `localization`, `returns`, `inventory_assessment`, `resupply_recs`, `anomalies`
- Rules: Russian, GROUP BY LOWER(), closed period for buyout, amounts as numbers

- [ ] **Step 2: Write verifier.md**

The verifier prompt should:
- Check: closed period used for buyout/returns (not current open period)
- Check: arithmetic on shares, sums, turnover
- Check: resupply qty ≤ MoySklad office stock
- Check: deficit/overstock thresholds reasonable
- Verdict: APPROVE / CORRECT / REJECT

- [ ] **Step 3: Write synthesizer.md**

Same Notion format as finolog synthesizer but with 7 sections:
I. Сводка, II. Стоимость логистики, III. Индекс локализации, IV. Возвраты и выкупы, V. Остатки и оборачиваемость, VI. Рекомендации по допоставкам, VII. Выводы и действия

All tables with colored rows, callouts, bold on significant Δ.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/logistics-report/prompts/
git commit -m "feat(logistics): add analyst, verifier, synthesizer prompts"
```

---

## Task 9: End-to-end test — Finolog DDS

- [ ] **Step 1: Run the full skill manually**

```bash
# Collect data
PYTHONPATH=. python scripts/finolog_dds_report/collect_data.py --start 2026-04-07 --end 2026-04-13 --output /tmp/finolog-test.json

# Verify JSON has all blocks
python3 -c "
import json
d = json.load(open('/tmp/finolog-test.json'))
for k in ['balances', 'cashflow_current', 'cashflow_previous', 'forecast', 'meta']:
    assert k in d, f'Missing block: {k}'
print(f'Blocks OK, errors: {d[\"meta\"][\"errors\"]}')
"
```

- [ ] **Step 2: Invoke the skill**

Run `/finolog-dds-report week` and verify:
- Notion page created in "Аналитические отчеты" DB
- 5 sections present (I-V)
- Tables have colored rows
- Callout blocks present
- Numbers formatted correctly

- [ ] **Step 3: Commit any fixes**

---

## Task 10: End-to-end test — Logistics

- [ ] **Step 1: Run the full skill manually**

```bash
PYTHONPATH=. python scripts/logistics_report/collect_data.py --start 2026-04-07 --end 2026-04-13 --output /tmp/logistics-test.json

python3 -c "
import json
d = json.load(open('/tmp/logistics-test.json'))
for k in ['logistics_cost', 'indices', 'returns', 'inventory', 'resupply', 'meta']:
    assert k in d, f'Missing block: {k}'
print(f'Blocks OK, errors: {d[\"meta\"][\"errors\"]}')
"
```

- [ ] **Step 2: Invoke the skill**

Run `/logistics-report week` and verify:
- Notion page created
- 7 sections present (I-VII)
- Returns section clearly labeled as closed period data
- Resupply table has realistic quantities
- Colored tables and callouts

- [ ] **Step 3: Commit any fixes**

---

## Implementation Notes

1. **SQL queries are approximations.** The actual column names in the DB may differ. During implementation, read `docs/database/` and `shared/data_layer/` to verify exact schemas.
2. **FinologService private methods.** The collector calls `_get_accounts()`, `_classify_accounts()`, `_get_transactions_by_group()`, `_build_forecast()`. Some of these may not be separate methods — extract from `build_weekly_summary()` if needed.
3. **Localization index data.** The `_collect_indices()` stub needs to be filled in by reading `services/wb_localization/` and finding the right function to get IL/IRP per cabinet.
4. **LLM tier.** Per `economics.md`, use MAIN tier (google/gemini-3-flash-preview) for all agents. No escalation needed.
5. **Notion format.** The synthesizer uses enhanced Markdown that `md_to_notion_blocks()` in `shared/notion_blocks.py` converts to Notion API blocks. Read that function to understand what syntax is supported.
