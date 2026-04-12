# Financial Overview Skill — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable `/financial-overview` skill that interactively collects period parameters, runs parallel data collectors (DB + Google Sheets), verifies data, and publishes a formatted comparison report to MD + Notion.

**Architecture:** Interactive Stage 0 (AskUserQuestion) → Python collector orchestrator with 5 parallel collectors (Stage 1) → Verifier agent + Synthesizer agent (Stage 2) → MD file + Notion publication (Stage 3). Follows the monthly-plan skill pattern but without critics/CFO — simpler pipeline.

**Tech Stack:** Python 3 (collectors), shared/data_layer (DB queries), gws CLI (Google Sheets), Notion MCP (publication), Claude Code skills (SKILL.md)

**Spec:** `docs/superpowers/specs/2026-04-02-financial-overview-skill-design.md`

---

## File Structure

```
.claude/skills/financial-overview/
├── SKILL.md                         # Skill definition + state machine
└── prompts/
    ├── synthesizer.md               # Report template + Notion formatting
    └── verifier.md                  # Data verification checklist

scripts/financial_overview/
├── collect_all.py                   # Orchestrator (ThreadPoolExecutor)
└── collectors/
    ├── __init__.py                  # Empty init
    ├── wb_funnel.py                 # WB organic traffic + funnel
    ├── wb_ozon_finance.py           # WB/OZON finance + ad breakdown
    ├── sheets_performance.py        # External performance (gws CLI)
    ├── sheets_smm.py               # SMM data (gws CLI)
    └── sheets_bloggers.py          # Blogger campaigns (gws CLI)
```

---

### Task 1: Collector Infrastructure — `collect_all.py` + `__init__.py`

**Files:**
- Create: `scripts/financial_overview/__init__.py` (empty)
- Create: `scripts/financial_overview/collectors/__init__.py` (empty)
- Create: `scripts/financial_overview/collect_all.py`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p scripts/financial_overview/collectors
touch scripts/financial_overview/__init__.py
touch scripts/financial_overview/collectors/__init__.py
```

- [ ] **Step 2: Write collect_all.py orchestrator**

```python
#!/usr/bin/env python3
"""Financial Overview — parallel data collection orchestrator.

Usage:
    python scripts/financial_overview/collect_all.py \
        --period-a "2026-01-01:2026-03-31" \
        --period-b "2025-10-01:2025-12-31" \
        --sections "finance,organic,ads,performance,smm,bloggers" \
        --output /tmp/financial_overview_data.json
"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def parse_period(period_str: str) -> tuple[str, str]:
    """Parse 'YYYY-MM-DD:YYYY-MM-DD' into (start, end) strings."""
    start, end = period_str.split(":")
    return start.strip(), end.strip()


def run_collector(name: str, func, kwargs: dict) -> tuple[str, dict | None, str | None]:
    """Run a single collector, return (name, result, error)."""
    try:
        result = func(**kwargs)
        return name, result, None
    except Exception as e:
        return name, None, f"{type(e).__name__}: {e}"


def main():
    parser = argparse.ArgumentParser(description="Financial Overview data collector")
    parser.add_argument("--period-a", required=True, help="Current period: YYYY-MM-DD:YYYY-MM-DD")
    parser.add_argument("--period-b", required=True, help="Comparison period: YYYY-MM-DD:YYYY-MM-DD")
    parser.add_argument("--sections", default="finance,organic,ads,performance,smm,bloggers",
                        help="Comma-separated sections to collect")
    parser.add_argument("--output", default="/tmp/financial_overview_data.json",
                        help="Output JSON file path")
    args = parser.parse_args()

    a_start, a_end = parse_period(args.period_a)
    b_start, b_end = parse_period(args.period_b)
    sections = [s.strip() for s in args.sections.split(",")]

    # Import collectors based on requested sections
    collectors = {}
    if "finance" in sections or "ads" in sections:
        from scripts.financial_overview.collectors.wb_ozon_finance import collect_finance
        collectors["wb_ozon_finance"] = (collect_finance, {
            "a_start": a_start, "a_end": a_end,
            "b_start": b_start, "b_end": b_end,
        })
    if "organic" in sections:
        from scripts.financial_overview.collectors.wb_funnel import collect_funnel
        collectors["wb_funnel"] = (collect_funnel, {
            "a_start": a_start, "a_end": a_end,
            "b_start": b_start, "b_end": b_end,
        })
    if "performance" in sections:
        from scripts.financial_overview.collectors.sheets_performance import collect_performance
        collectors["sheets_performance"] = (collect_performance, {
            "a_start": a_start, "a_end": a_end,
            "b_start": b_start, "b_end": b_end,
        })
    if "smm" in sections:
        from scripts.financial_overview.collectors.sheets_smm import collect_smm
        collectors["sheets_smm"] = (collect_smm, {
            "a_start": a_start, "a_end": a_end,
            "b_start": b_start, "b_end": b_end,
        })
    if "bloggers" in sections:
        from scripts.financial_overview.collectors.sheets_bloggers import collect_bloggers
        collectors["sheets_bloggers"] = (collect_bloggers, {
            "a_start": a_start, "a_end": a_end,
            "b_start": b_start, "b_end": b_end,
        })

    # Run collectors in parallel
    t0 = time.time()
    results = {}
    errors = {}

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {
            pool.submit(run_collector, name, func, kwargs): name
            for name, (func, kwargs) in collectors.items()
        }
        for future in as_completed(futures):
            name, result, error = future.result()
            if error:
                errors[name] = error
                print(f"[WARN] Collector {name} failed: {error}", file=sys.stderr)
            else:
                results[name] = result
                print(f"[OK] Collector {name} done")

    duration = round(time.time() - t0, 1)

    # Build output
    output = {
        **results,
        "meta": {
            "period_a": {"start": a_start, "end": a_end},
            "period_b": {"start": b_start, "end": b_end},
            "sections": sections,
            "errors": errors,
            "quality_flags": {},
            "collection_duration_sec": duration,
        },
    }

    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2, default=str))
    print(f"\nData saved to {args.output} ({duration}s, {len(errors)} errors)")

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Verify script parses args**

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee
python scripts/financial_overview/collect_all.py --help
```

Expected: help text with --period-a, --period-b, --sections, --output args.

- [ ] **Step 4: Commit**

```bash
git add scripts/financial_overview/
git commit -m "feat(financial-overview): add collector orchestrator with parallel execution"
```

---

### Task 2: WB Funnel Collector

**Files:**
- Create: `scripts/financial_overview/collectors/wb_funnel.py`
- Reference: `shared/data_layer/traffic.py`, `shared/data_layer/funnel_seo.py`, `shared/data_layer/advertising.py`

- [ ] **Step 1: Write wb_funnel.py**

```python
"""WB organic funnel collector — traffic, conversions, organic vs paid split."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from shared.data_layer import (
    get_wb_traffic,
    get_wb_article_funnel,
    get_wb_organic_vs_paid_funnel,
)


def collect_funnel(a_start: str, a_end: str, b_start: str, b_end: str) -> dict:
    """Collect WB organic funnel data for two periods."""

    # Traffic funnel for period A (current)
    traffic_a = get_wb_traffic(a_start, b_start, a_end)
    # Traffic funnel for period B (comparison)
    # For period B, we need a "previous" reference — use the period before B
    # Calculate prev_start for period B (same length before b_start)
    from datetime import datetime, timedelta
    b_s = datetime.strptime(b_start, "%Y-%m-%d")
    b_e = datetime.strptime(b_end, "%Y-%m-%d")
    b_length = (b_e - b_s).days
    prev_b_start = (b_s - timedelta(days=b_length)).strftime("%Y-%m-%d")
    traffic_b = get_wb_traffic(b_start, prev_b_start, b_end)

    # Article funnel (top 10 models)
    funnel_a = get_wb_article_funnel(a_start, a_end, top_n=10)
    funnel_b = get_wb_article_funnel(b_start, b_end, top_n=10)

    # Organic vs paid split
    organic_a = get_wb_organic_vs_paid_funnel(a_start, b_start, a_end)
    organic_b = get_wb_organic_vs_paid_funnel(b_start, prev_b_start, b_end)

    # Parse traffic results into dicts
    def parse_traffic(rows):
        """Convert traffic tuples to structured dict."""
        result = {"card_opens": 0, "add_to_cart": 0, "orders": 0, "buyouts": 0}
        if not rows:
            return result
        for row in rows:
            # Columns depend on get_wb_traffic return format
            # Accumulate totals across all rows
            if len(row) >= 5:
                result["card_opens"] += int(row[1] or 0)
                result["add_to_cart"] += int(row[2] or 0)
                result["orders"] += int(row[3] or 0)
                result["buyouts"] += int(row[4] or 0)
        return result

    def calc_conversions(data):
        """Calculate conversion rates from funnel data."""
        opens = data.get("card_opens", 0)
        cart = data.get("add_to_cart", 0)
        orders = data.get("orders", 0)
        buyouts = data.get("buyouts", 0)
        return {
            "cr_open_to_cart": round(cart / opens * 100, 2) if opens else 0,
            "cr_cart_to_order": round(orders / cart * 100, 2) if cart else 0,
            "cr_open_to_order": round(orders / opens * 100, 2) if opens else 0,
            "cr_order_to_buyout": round(buyouts / orders * 100, 2) if orders else 0,
        }

    traffic_data_a = parse_traffic(traffic_a)
    traffic_data_b = parse_traffic(traffic_b)

    return {
        "funnel": {
            "period_a": traffic_data_a,
            "period_b": traffic_data_b,
        },
        "conversions": {
            "period_a": calc_conversions(traffic_data_a),
            "period_b": calc_conversions(traffic_data_b),
        },
        "organic_vs_paid": {
            "period_a": organic_a,
            "period_b": organic_b,
        },
        "top_models": {
            "period_a": funnel_a,
            "period_b": funnel_b,
        },
    }
```

- [ ] **Step 2: Verify import works**

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee
python -c "from scripts.financial_overview.collectors.wb_funnel import collect_funnel; print('OK')"
```

Expected: "OK" (no import errors).

- [ ] **Step 3: Test with real data (dry run)**

```bash
python -c "
from scripts.financial_overview.collectors.wb_funnel import collect_funnel
import json
result = collect_funnel('2026-01-01', '2026-03-31', '2025-10-01', '2025-12-31')
print(json.dumps({k: type(v).__name__ for k, v in result.items()}, indent=2))
"
```

Expected: dict with keys funnel, conversions, organic_vs_paid, top_models — all dicts.

- [ ] **Step 4: Commit**

```bash
git add scripts/financial_overview/collectors/wb_funnel.py
git commit -m "feat(financial-overview): add WB organic funnel collector"
```

---

### Task 3: WB/OZON Finance Collector

**Files:**
- Create: `scripts/financial_overview/collectors/wb_ozon_finance.py`
- Reference: `shared/data_layer/finance.py`, `shared/data_layer/advertising.py`

- [ ] **Step 1: Write wb_ozon_finance.py**

```python
"""WB/OZON finance + internal ad breakdown collector."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from shared.data_layer import (
    get_wb_finance,
    get_ozon_finance,
    get_wb_external_ad_breakdown,
    get_wb_model_ad_roi,
)


def collect_finance(a_start: str, a_end: str, b_start: str, b_end: str) -> dict:
    """Collect WB and OZON financial data for two periods."""
    from datetime import datetime, timedelta

    b_s = datetime.strptime(b_start, "%Y-%m-%d")
    b_e = datetime.strptime(b_end, "%Y-%m-%d")
    b_length = (b_e - b_s).days
    prev_b_start = (b_s - timedelta(days=b_length)).strftime("%Y-%m-%d")

    # WB Finance
    wb_fin_a = get_wb_finance(a_start, b_start, a_end)
    wb_fin_b = get_wb_finance(b_start, prev_b_start, b_end)

    # OZON Finance
    try:
        ozon_fin_a = get_ozon_finance(a_start, b_start, a_end)
        ozon_fin_b = get_ozon_finance(b_start, prev_b_start, b_end)
    except Exception:
        ozon_fin_a, ozon_fin_b = [], []

    # WB Ad Breakdown (internal/bloggers/VK/creators)
    wb_ads_a = get_wb_external_ad_breakdown(a_start, b_start, a_end)
    wb_ads_b = get_wb_external_ad_breakdown(b_start, prev_b_start, b_end)

    # WB Ad ROI by model
    wb_roi_a = get_wb_model_ad_roi(a_start, b_start, a_end)
    wb_roi_b = get_wb_model_ad_roi(b_start, prev_b_start, b_end)

    return {
        "wb_finance": {"period_a": wb_fin_a, "period_b": wb_fin_b},
        "ozon_finance": {"period_a": ozon_fin_a, "period_b": ozon_fin_b},
        "wb_ads": {"period_a": wb_ads_a, "period_b": wb_ads_b},
        "ad_roi": {"period_a": wb_roi_a, "period_b": wb_roi_b},
    }
```

- [ ] **Step 2: Verify import**

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee
python -c "from scripts.financial_overview.collectors.wb_ozon_finance import collect_finance; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add scripts/financial_overview/collectors/wb_ozon_finance.py
git commit -m "feat(financial-overview): add WB/OZON finance + ads collector"
```

---

### Task 4: Google Sheets Collectors (Performance, SMM, Bloggers)

**Files:**
- Create: `scripts/financial_overview/collectors/sheets_performance.py`
- Create: `scripts/financial_overview/collectors/sheets_smm.py`
- Create: `scripts/financial_overview/collectors/sheets_bloggers.py`
- Reference: `shared/config.py` for env vars

- [ ] **Step 1: Write sheets_performance.py**

```python
"""External performance marketing collector — reads from Google Sheets via gws CLI."""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from shared.config import get_config

SHEET_ID = get_config("PERFORMANCE_SHEET_ID", "1PvsgAkb2K84ss4iTD25yoD0pxSZYiVgcqetVUtCBvGg")


def _gws_read(sheet_id: str, range_str: str) -> list[list[str]]:
    """Read a range from Google Sheets via gws CLI."""
    cmd = ["gws", "sheets", "+read", "--spreadsheet", sheet_id, "--range", range_str]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"gws read failed: {result.stderr}")
    # Parse TSV output
    rows = []
    for line in result.stdout.strip().split("\n"):
        if line.strip():
            rows.append(line.split("\t"))
    return rows


def collect_performance(a_start: str, a_end: str, b_start: str, b_end: str) -> dict:
    """Collect external performance marketing data from Google Sheets.

    Reads the 'Итог Март' style sheets and aggregates by month.
    Returns monthly data with: spend, clicks, cpc, utm_clicks, utm_cpc.
    """
    # Read summary data — try different sheet names
    monthly = {}
    for sheet_name in ["Итог Март", "Итог Февраль", "Итог Январь",
                       "Итог Декабрь", "Итог Ноябрь", "Итог Октябрь"]:
        try:
            rows = _gws_read(SHEET_ID, f"'{sheet_name}'!A1:Q50")
            if rows:
                # Find "Итого" row and extract aggregates
                for row in rows:
                    if row and row[0].strip().lower() == "итого":
                        monthly[sheet_name] = {
                            "spend_nds": _safe_float(row[1]) if len(row) > 1 else 0,
                            "clicks": _safe_float(row[2]) if len(row) > 2 else 0,
                            "cpc": _safe_float(row[3]) if len(row) > 3 else 0,
                            "views": _safe_float(row[4]) if len(row) > 4 else 0,
                            "cpm": _safe_float(row[5]) if len(row) > 5 else 0,
                        }
                        break
        except Exception:
            continue

    return {"monthly": monthly}


def _safe_float(val) -> float:
    """Safely convert a value to float, handling commas and spaces."""
    if not val:
        return 0.0
    try:
        return float(str(val).replace(",", ".").replace(" ", "").replace("\xa0", ""))
    except (ValueError, TypeError):
        return 0.0
```

- [ ] **Step 2: Write sheets_smm.py**

```python
"""SMM data collector — reads from Google Sheets via gws CLI."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from shared.config import get_config

SHEET_ID = get_config("SMM_SHEET_ID", "19NXHQGWSFjeWiPE12R3YAy5u2IsLpTISrECpysPSdPU")


def _gws_read(sheet_id: str, range_str: str) -> list[list[str]]:
    """Read a range from Google Sheets via gws CLI."""
    cmd = ["gws", "sheets", "+read", "--spreadsheet", sheet_id, "--range", range_str]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"gws read failed: {result.stderr}")
    rows = []
    for line in result.stdout.strip().split("\n"):
        if line.strip():
            rows.append(line.split("\t"))
    return rows


def _safe_float(val) -> float:
    if not val:
        return 0.0
    try:
        return float(str(val).replace(",", ".").replace(" ", "").replace("\xa0", ""))
    except (ValueError, TypeError):
        return 0.0


def collect_smm(a_start: str, a_end: str, b_start: str, b_end: str) -> dict:
    """Collect SMM data from Google Sheets.

    Reads 'Отчёт месяц' sheet for monthly aggregates.
    """
    rows = _gws_read(SHEET_ID, "'Отчёт месяц'!A1:N20")

    # Parse header row to find months, then extract metrics
    monthly = {}
    if len(rows) >= 3:
        # Row 0: month names, Row 1: dates, Row 2+: metrics
        # Structure varies — parse what we find
        for row in rows:
            if row and row[0].strip().lower() in ("затраты", "показы", "cpv", "переходы", "cr", "cpc"):
                metric = row[0].strip().lower()
                for i, val in enumerate(row[1:], 1):
                    month_key = f"col_{i}"
                    if month_key not in monthly:
                        monthly[month_key] = {}
                    monthly[month_key][metric] = _safe_float(val) if metric != "cr" else val

    return {"monthly": monthly, "raw_rows": len(rows)}
```

- [ ] **Step 3: Write sheets_bloggers.py**

```python
"""Blogger campaigns collector — reads from Google Sheets via gws CLI."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from shared.config import get_config

SHEET_ID = get_config("BLOGGERS_SHEET_ID", "1Y7uxZnrjHLBntoDLkKJBOt5-lmODRJ5QEkE19QBA8xk")


def _gws_read(sheet_id: str, range_str: str) -> list[list[str]]:
    """Read a range from Google Sheets via gws CLI."""
    cmd = ["gws", "sheets", "+read", "--spreadsheet", sheet_id, "--range", range_str]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"gws read failed: {result.stderr}")
    rows = []
    for line in result.stdout.strip().split("\n"):
        if line.strip():
            rows.append(line.split("\t"))
    return rows


def _safe_float(val) -> float:
    if not val:
        return 0.0
    try:
        return float(str(val).replace(",", ".").replace(" ", "").replace("\xa0", ""))
    except (ValueError, TypeError):
        return 0.0


def collect_bloggers(a_start: str, a_end: str, b_start: str, b_end: str) -> dict:
    """Collect blogger campaign data from Google Sheets.

    Reads 'Блогеры' sheet and aggregates by month.
    Monthly aggregates: budget, placements, CPM, CPC, clicks, carts, orders, CR.
    """
    rows = _gws_read(SHEET_ID, "'Блогеры'!A1:AF800")

    monthly = {}
    current_month = None

    for row in rows[2:]:  # Skip header rows
        if not row or not row[0]:
            continue

        # Detect month headers like "Октябрь 2025", "Январь 2026"
        first_cell = row[0].strip()
        if any(m in first_cell.lower() for m in [
            "январь", "февраль", "март", "апрель", "май", "июнь",
            "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"
        ]) and any(y in first_cell for y in ["2025", "2026"]):
            current_month = first_cell
            monthly[current_month] = {
                "placements": 0, "budget": 0, "views": 0,
                "clicks": 0, "carts": 0, "orders": 0,
            }
            continue

        if current_month and len(row) >= 6:
            # Skip cancelled or empty rows
            spend = _safe_float(row[13]) if len(row) > 13 else 0  # Column N = итоговая цена
            if spend <= 0:
                spend = _safe_float(row[10]) if len(row) > 10 else 0  # Column K = стоимость

            if spend > 0:
                monthly[current_month]["placements"] += 1
                monthly[current_month]["budget"] += spend
                monthly[current_month]["views"] += _safe_float(row[23]) if len(row) > 23 else 0  # X
                monthly[current_month]["clicks"] += _safe_float(row[25]) if len(row) > 25 else 0  # Z
                monthly[current_month]["carts"] += _safe_float(row[28]) if len(row) > 28 else 0  # AC
                monthly[current_month]["orders"] += _safe_float(row[30]) if len(row) > 30 else 0  # AE

    # Calculate derived metrics
    for month, data in monthly.items():
        views = data["views"]
        clicks = data["clicks"]
        budget = data["budget"]
        data["cpm"] = round(budget / views * 1000, 0) if views else 0
        data["cpc"] = round(budget / clicks, 1) if clicks else 0
        data["cr_cart"] = round(data["carts"] / clicks * 100, 2) if clicks else 0
        data["cr_order"] = round(data["orders"] / clicks * 100, 2) if clicks else 0

    return {"monthly": monthly}
```

- [ ] **Step 4: Verify all three collectors import**

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee
python -c "
from scripts.financial_overview.collectors.sheets_performance import collect_performance
from scripts.financial_overview.collectors.sheets_smm import collect_smm
from scripts.financial_overview.collectors.sheets_bloggers import collect_bloggers
print('All 3 sheets collectors import OK')
"
```

- [ ] **Step 5: Commit**

```bash
git add scripts/financial_overview/collectors/sheets_*.py
git commit -m "feat(financial-overview): add Google Sheets collectors (performance, SMM, bloggers)"
```

---

### Task 5: Verifier Prompt

**Files:**
- Create: `.claude/skills/financial-overview/prompts/verifier.md`

- [ ] **Step 1: Create prompts directory**

```bash
mkdir -p .claude/skills/financial-overview/prompts
```

- [ ] **Step 2: Write verifier.md**

```markdown
# Data Verifier — Financial Overview

You are a data verification agent. Your job is to cross-check the collected data for consistency and correctness.

## Input

Read the data file at: `{{DATA_FILE}}`

## Verification Checklist

### 1. Cross-Source Consistency
- WB finance from DB (revenue, orders) should be within 5% of any user-provided ОПИУ totals
- If both WB and OZON data present, their sum should approximate total revenue

### 2. Arithmetic Checks
- Period A + Period B growth percentages: `(A - B) / B * 100`
- Weighted averages for percentage metrics: `sum(numerator) / sum(denominator)`
- NOT simple averages of percentages

### 3. Data Completeness
- All requested sections have data for BOTH periods
- No section returns all zeros (likely a collection error)
- Monthly data covers all months in each period

### 4. Quality Flags
- content_analysis (WB organic) has ~20% gap vs PowerBI — note as caveat
- Google Sheets amounts: check if labeled "с НДС" or "без НДС"
- Выкуп % is lagging (3-21 days) — flag if used as causal

### 5. Sensitive Data
- No юрлица (ООО, ИП) names
- No ИНН (10-12 digit tax IDs)
- No server IPs or credentials

## Output Format

Report your findings as:
```
STATUS: PASS | WARN | FAIL
ISSUES: [list of critical issues requiring abort]
WARNINGS: [list of non-critical issues to note in report footer]
```

If STATUS is FAIL, explain what went wrong and suggest fixes.
If STATUS is WARN, list warnings to include in the report.
If STATUS is PASS, confirm all checks passed.
```

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/financial-overview/prompts/verifier.md
git commit -m "feat(financial-overview): add verifier prompt template"
```

---

### Task 6: Synthesizer Prompt

**Files:**
- Create: `.claude/skills/financial-overview/prompts/synthesizer.md`

- [ ] **Step 1: Write synthesizer.md**

```markdown
# Report Synthesizer — Financial Overview

You are a report synthesizer. Your job is to compile collected data into a formatted financial overview report.

## Input

- Data file: `{{DATA_FILE}}` (JSON with all collected data)
- User context: `{{USER_CONTEXT}}` (additional notes, e.g. "март неполный")
- Period A label: `{{PERIOD_A_LABEL}}` (e.g. "Q1 2026")
- Period B label: `{{PERIOD_B_LABEL}}` (e.g. "Q4 2025")
- Sections: `{{SECTIONS}}` (comma-separated list of sections to include)
- Verifier warnings: `{{VERIFIER_WARNINGS}}` (if any)

## Task

1. Read the data JSON
2. For each requested section, compute period A vs period B comparison
3. Write the report as markdown to: `docs/reports/{{PERIOD_A_LABEL}}-vs-{{PERIOD_B_LABEL}}-overview.md`
4. Publish to Notion database (Аналитические отчеты):
   - Parent: `data_source_id: 30158a2b-d587-8091-bfc3-000b83c6b747`
   - Properties: Name=title, Статус="Актуальный", Источник="Claude Code", Тип анализа="Ежемесячный фин анализ", Корректность="Да"
   - Use Notion table format `<table>` with colors, callouts for insights

## Report Structure

### I. Финансы (if "finance" in sections)
- Q-to-Q comparison table: продажи, выручка, себестоимость, маржа, маржинальность, средний чек, выкуп, EBITDA, ЧП
- Monthly trend table: выручка, маржа, EBITDA, ЧП
- Apply any user_context adjustments (e.g. estimated March costs)

### II. Органика WB (if "organic" in sections)
- Funnel: показы → корзина → заказы → выкупы
- CRs at each step
- Organic vs paid orders split
- Top models by order growth

### III. Внутренний маркетинг WB/OZON (if "ads" in sections)
- WB ad spend by channel (internal, bloggers, VK)
- DRR, ROMI
- OZON ad spend + margin

### IV. Внешний performance (if "performance" in sections)
- Monthly aggregate: spend, clicks, CPC (no channel breakdown)
- Note if this is a new channel with limited history

### V. SMM (if "smm" in sections)
- Q-to-Q: spend, views, clicks, CPC, CR
- Monthly trend

### VI. Блогеры (if "bloggers" in sections)
- Q-to-Q: placements, budget, CPM, CPC, CR cart, CR order
- Monthly CR trend

### Итоги
- One callout per section with key takeaway

### Footer
- Data sources listed
- Quality caveats (content_analysis gap, partial months, etc.)
- Verifier warnings if any

## Formatting Rules

- Numbers: space-separated thousands (1 234 567)
- Percentages: weighted averages ONLY — `sum(numerator) / sum(denominator) * 100`
- Deltas: show both absolute and percentage
- Estimates: marked with asterisk (*) and explained in footnote
- GROUP BY LOWER() — model names normalized
- Notion tables: use `<table>` with `header-row="true"`, color rows for emphasis
- Callouts: `<callout icon="emoji" color="color_bg">text</callout>`
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/financial-overview/prompts/synthesizer.md
git commit -m "feat(financial-overview): add synthesizer prompt template"
```

---

### Task 7: SKILL.md — Main Skill Definition

**Files:**
- Create: `.claude/skills/financial-overview/SKILL.md`

- [ ] **Step 1: Write SKILL.md**

````markdown
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
python scripts/financial_overview/collect_all.py \
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
````

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/financial-overview/SKILL.md
git commit -m "feat(financial-overview): add main SKILL.md with 4-stage state machine"
```

---

### Task 8: Environment Config + Integration Test

**Files:**
- Modify: `.env` (add sheet IDs if not present)
- Test: full pipeline dry run

- [ ] **Step 1: Check .env for sheet IDs**

Read `.env` and check if `PERFORMANCE_SHEET_ID`, `SMM_SHEET_ID`, `BLOGGERS_SHEET_ID` exist. If not, add them:

```
PERFORMANCE_SHEET_ID=1PvsgAkb2K84ss4iTD25yoD0pxSZYiVgcqetVUtCBvGg
SMM_SHEET_ID=19NXHQGWSFjeWiPE12R3YAy5u2IsLpTISrECpysPSdPU
BLOGGERS_SHEET_ID=1Y7uxZnrjHLBntoDLkKJBOt5-lmODRJ5QEkE19QBA8xk
```

- [ ] **Step 2: Run full collector pipeline**

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee
python scripts/financial_overview/collect_all.py \
  --period-a "2026-01-01:2026-03-31" \
  --period-b "2025-10-01:2025-12-31" \
  --sections "finance,organic,ads" \
  --output /tmp/financial_overview_test.json
```

Expected: JSON file with wb_funnel, wb_ozon_finance data + meta block. May have errors for sheets collectors if gws not available.

- [ ] **Step 3: Verify JSON structure**

```bash
python -c "
import json
data = json.load(open('/tmp/financial_overview_test.json'))
print('Keys:', list(data.keys()))
print('Meta:', json.dumps(data.get('meta', {}), indent=2))
print('Errors:', data.get('meta', {}).get('errors', {}))
"
```

- [ ] **Step 4: Commit**

```bash
git add .env
git commit -m "feat(financial-overview): add Google Sheets IDs to .env"
```

---

### Task 9: Final Integration — Test Full Skill

- [ ] **Step 1: Test skill invocation**

In Claude Code, run `/financial-overview` and verify:
1. AskUserQuestion appears with Q1 (period selection)
2. After answering Q1-Q3, collector script runs
3. Verifier checks data
4. Synthesizer produces MD + Notion page

- [ ] **Step 2: Fix any issues discovered during integration test**

Common issues:
- Column indices in sheets collectors may need adjustment based on actual sheet structure
- `get_wb_traffic()` return format may differ from expected — adapt `parse_traffic()`
- gws CLI authentication issues — ensure `gws` is configured

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat(financial-overview): complete skill with all collectors, prompts, and integration"
```
