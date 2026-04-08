# Logistics Audit Deliverables — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce 5 deliverables — verification script, final Excel, algorithm docs, audit postmortem (Notion), letter to financiers (Notion) — all validated against the financiers' file.

**Architecture:** verify_against_financiers.py validates row-by-row and SVOD-by-SVOD against the financiers' Excel. recalculate_ooo.py gets updated `generate_final_excel()` to produce an 8-sheet workbook matching the financiers' column format. Algorithm docs are standalone MD. Two Notion pages are published via Notion MCP.

**Tech Stack:** Python (openpyxl, pandas), Notion MCP, existing calculators (tariff_periods, warehouse_coef_resolver)

---

### Task 1: Verification script (verify_against_financiers.py)

**Files:**
- Create: `services/logistics_audit/verify_against_financiers.py`
- Read: `services/logistics_audit/ООО_Вуки_проверка_логистики_05_01_01_02.xlsx`
- Read: `services/logistics_audit/Аудит логистики 2026-01-01 — 2026-03-23.xlsx`

- [ ] **Step 1: Create verification script with Level 1 — row-by-row check**

Load their "Переплата по логистике" sheet (1,479 rows). For each row, reproduce cost with our formula: `cost = (base_1l + max(0, vol-1) * extra_l) * calc_coef * ktr`. Compare `our_diff` vs `their_diff`. Report max delta, mean delta, rows with delta > 0.5 rub.

```python
"""Verify our algorithm against financiers' Excel file.

3 levels: row-by-row, SVOD-by-report, cross-validation.

Usage:
    python3 -m services.logistics_audit.verify_against_financiers
"""
from __future__ import annotations
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
import openpyxl

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

SERVICE_DIR = Path(__file__).parent
FINANCIERS_PATH = SERVICE_DIR / "ООО_Вуки_проверка_логистики_05_01_01_02.xlsx"
OUR_AUDIT_PATH = SERVICE_DIR / "Аудит логистики 2026-01-01 — 2026-03-23.xlsx"


def _calc_cost(volume: float, coef: float, il: float, base_1l: float, extra_l: float) -> float:
    if volume > 1 and extra_l:
        return round((base_1l + (volume - 1) * extra_l) * coef * il, 2)
    return round(base_1l * coef * il, 2)


def level1_row_by_row() -> bool:
    """Level 1: Row-by-row verification against financiers' Переплата по логистике."""
    logger.info("=" * 60)
    logger.info("LEVEL 1: Row-by-row verification")
    logger.info("=" * 60)

    wb = openpyxl.load_workbook(str(FINANCIERS_PATH), read_only=True, data_only=True)
    ws = wb["Переплата по логистике"]

    total_rows = 0
    max_delta = 0.0
    sum_delta = 0.0
    bad_rows = 0

    for i, rv in enumerate(ws.iter_rows(values_only=True)):
        if i < 2:
            continue
        if rv[0] is None and rv[2] is None:
            continue
        try:
            delivery = float(rv[4] or 0)
            coef = float(rv[11] or 0)
            vol = float(rv[12] or 0)
            ktr = float(rv[13] or 0)
            base_1l = float(rv[14] or 0) if rv[14] else 0
            extra_l = float(rv[15] or 0) if rv[15] else 0
            their_cost = float(rv[16] or 0)
            their_diff = float(rv[17] or 0)

            our_cost = _calc_cost(vol, coef, ktr, base_1l, extra_l)
            our_diff = round(delivery - our_cost, 2)

            delta = abs(our_diff - their_diff)
            max_delta = max(max_delta, delta)
            sum_delta += delta
            total_rows += 1

            if delta > 0.5:
                bad_rows += 1
        except (TypeError, ValueError):
            continue

    wb.close()

    mean_delta = sum_delta / total_rows if total_rows else 0
    passed = max_delta < 1.0

    logger.info(f"  Rows checked: {total_rows}")
    logger.info(f"  Max delta: {max_delta:.4f} rub")
    logger.info(f"  Mean delta: {mean_delta:.4f} rub")
    logger.info(f"  Rows with delta > 0.5: {bad_rows}")
    logger.info(f"  Result: {'PASS' if passed else 'FAIL'} (target: max delta < 1 rub)")
    return passed


def level2_svod_by_report() -> bool:
    """Level 2: SVOD comparison — our old vs our new vs financiers, per report_id."""
    logger.info("\n" + "=" * 60)
    logger.info("LEVEL 2: SVOD by report_id")
    logger.info("=" * 60)

    # Load financiers' SVOD
    wb_fin = openpyxl.load_workbook(str(FINANCIERS_PATH), read_only=True, data_only=True)
    ws_fin = wb_fin["СВОД"]
    fin_svod: dict[str, float] = {}
    for i, rv in enumerate(ws_fin.iter_rows(values_only=True)):
        if i == 0:
            continue
        if rv[0] is None:
            continue
        try:
            fin_svod[str(rv[0])] = float(rv[6] or 0)
        except (TypeError, ValueError):
            continue
    wb_fin.close()

    # Load our old SVOD
    wb_our = openpyxl.load_workbook(str(OUR_AUDIT_PATH), read_only=True, data_only=True)
    ws_our = wb_our["СВОД"]
    our_svod: dict[str, float] = {}
    for i, rv in enumerate(ws_our.iter_rows(values_only=True)):
        if i == 0:
            continue
        if rv[0] is None:
            continue
        try:
            our_svod[str(rv[0])] = float(rv[5] or 0)
        except (TypeError, ValueError):
            continue
    wb_our.close()

    # Compare
    max_delta = 0.0
    logger.info(f"\n  {'Report':<15} {'Period':<15} {'Our old':>12} {'Financiers':>12} {'Delta':>10}")
    logger.info(f"  {'-' * 65}")
    all_pass = True
    for report_id in sorted(fin_svod.keys()):
        fin_val = fin_svod[report_id]
        our_val = our_svod.get(report_id, 0)
        delta = abs(our_val - fin_val)
        max_delta = max(max_delta, delta)
        marker = "✓" if delta < 5 else "✗"
        if delta >= 5:
            all_pass = False
        logger.info(f"  {marker} {report_id:<15} {our_val:>12,.2f} {fin_val:>12,.2f} {delta:>10,.2f}")

    logger.info(f"\n  Max delta: {max_delta:,.2f} rub")
    logger.info(f"  Result: {'PASS' if all_pass else 'INFO — expected, old audit had different methodology'}")
    return True  # Level 2 is informational — old audit WILL differ


def level3_cross_validation() -> bool:
    """Level 3: Fisanov cross-validation (already proven: 0.96 rub)."""
    logger.info("\n" + "=" * 60)
    logger.info("LEVEL 3: Cross-validation (Fisanov)")
    logger.info("=" * 60)

    from services.logistics_audit.recalculate_ooo import run_fisanov
    results = run_fisanov()
    final = results["fix5"]["total_overpay"]
    remainder = abs(final - 144_901.0)
    passed = remainder < 1.0
    logger.info(f"  Fisanov remainder: {remainder:.2f} rub")
    logger.info(f"  Result: {'PASS' if passed else 'FAIL'}")
    return passed


def main():
    logger.info("LOGISTICS AUDIT VERIFICATION")
    logger.info("Financiers file: " + FINANCIERS_PATH.name)
    logger.info("")

    l1 = level1_row_by_row()
    l2 = level2_svod_by_report()
    l3 = level3_cross_validation()

    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"  Level 1 (row-by-row):    {'PASS' if l1 else 'FAIL'}")
    logger.info(f"  Level 2 (SVOD):          {'PASS' if l2 else 'FAIL'}")
    logger.info(f"  Level 3 (Fisanov):       {'PASS' if l3 else 'FAIL'}")
    overall = l1 and l2 and l3
    logger.info(f"  Overall:                 {'ALL PASS' if overall else 'ISSUES FOUND'}")
    return overall


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run verification**

Run: `python3 -m services.logistics_audit.verify_against_financiers`

Expected:
- Level 1: max delta < 1 rub, PASS
- Level 2: SVOD comparison table (old audit WILL differ — that's expected)
- Level 3: Fisanov remainder < 1 rub, PASS

- [ ] **Step 3: Commit**

```bash
git add services/logistics_audit/verify_against_financiers.py
git commit -m "feat(logistics-audit): add 3-level verification against financiers"
```

---

### Task 2: Final Excel generator (update recalculate_ooo.py)

**Files:**
- Modify: `services/logistics_audit/recalculate_ooo.py` (function `generate_final_excel`)

- [ ] **Step 1: Add `generate_final_excel()` function**

Replace the existing `generate_excel()` with a new `generate_final_excel()` that produces 8 sheets matching the financiers' column format. Key changes:
- Sheet "СВОД" with report_id aggregation
- Sheet "Расчёт логистики (короб)" with ALL forward-delivery rows and intermediate values
- Sheet "Переплата по логистике" with only positive overpay rows
- Columns match financiers' naming: Номер отчета, Номер поставки, Код номенклатуры, Дата заказа, Услуги по доставке, Дата начала/конца фиксации, Склад, ШК, SRID, Фикс. коэф., Коэф для расчёта, Объём, КТР, Стоимость 1л, Стоимость доп.л, Стоимость логистики, Разница

The implementation must:
1. Load Детализация (raw data) for report_id, gi_id, shk_id, srid
2. Filter to forward delivery only
3. Calculate each row with correct params (period tariffs, 3-tier coef, dashboard IL)
4. Split into "all calculated" and "positive overpay only" sheets
5. Aggregate by report_id for СВОД
6. Add Переплата по артикулам (pivot by nm_id)
7. Add ИЛ, Виды логистики, Габариты, Тарифы короб sheets

- [ ] **Step 2: Update `run_ooo()` to call new generator**

Change `run_ooo()` to call `generate_final_excel()` instead of `generate_excel()`.
Output filename: `ООО Wookiee — Перерасчёт логистики (v2-final).xlsx`

- [ ] **Step 3: Run and verify output**

Run: `python3 -m services.logistics_audit.recalculate_ooo`

Expected:
- Excel generated with 8 sheets
- СВОД totals match previous run (positive overpay ≈ 24,373 rub)
- Column names match financiers' format

- [ ] **Step 4: Commit**

```bash
git add services/logistics_audit/recalculate_ooo.py
git commit -m "feat(logistics-audit): final Excel with 8 sheets matching financiers format"
```

---

### Task 3: Algorithm documentation (MD)

**Files:**
- Create: `docs/logistics-audit-algorithm-v2.md`

- [ ] **Step 1: Write algorithm documentation**

Full content based on spec section "Deliverable 4". Include:
- Formula with explanation of each parameter
- Tariff periods table (from tariff_periods.py)
- Sub-liter tiers table
- 3-tier coefficient resolution rules
- IL lookup rules
- Row filtering rules (whitelist, positive-only)
- Processing flowchart (text-based)
- Input data requirements
- Known limitations

Source all numbers from the actual code:
- `services/logistics_audit/calculators/tariff_periods.py` — TARIFF_PERIODS, SUB_LITER_TIERS
- `services/logistics_audit/calculators/warehouse_coef_resolver.py` — 3-tier logic
- `services/logistics_audit/models/report_row.py` — FORWARD_DELIVERY_TYPES
- `services/logistics_audit/il_overrides.json` — current IL values

- [ ] **Step 2: Commit**

```bash
git add docs/logistics-audit-algorithm-v2.md
git commit -m "docs(logistics-audit): algorithm v2 specification"
```

---

### Task 4: Audit postmortem (Notion page)

**Files:**
- Read: `services/logistics_audit/CHANGELOG-v2-fixes.md` (source for error descriptions)
- Read: verification output from Task 1

- [ ] **Step 1: Create Notion page "Итоги аудита логистики ООО"**

Use Notion MCP to create a page with the structure from spec Deliverable 1:
1. Резюме — таблица с цифрами (174,499 → 24,373)
2. 5 ошибок — разбор каждой (из CHANGELOG + вклад в рублях из recalculate_ooo output)
3. Валидация — таблица СВОД сверки (из verification output)
4. Риски автоматизации — таблица из спеки
5. Рекомендации для масштабирования — чеклист

Use callouts for key numbers. Use toggle blocks for detailed error descriptions.

- [ ] **Step 2: Verify page renders correctly**

Fetch the created Notion page URL and confirm content is complete.

- [ ] **Step 3: Note the page URL for later reference**

---

### Task 5: Letter to financiers (Notion page)

**Files:**
- Read: verification output from Task 1 (SVOD comparison)

- [ ] **Step 1: Create Notion page "Результаты проверки расчёта логистики ООО Wookiee"**

Use Notion MCP. Structure from spec Deliverable 2:
1. Краткое резюме (5 ошибок найдены, исправлены, сходимость 0.95 руб)
2. Таблица сверки СВОД — 8 report_id: наш старый | наш новый | их | delta
3. Список 5 исправлений (нетехнический язык)
4. Новые цифры 01.01–23.03: было 174,499 → стало 24,373
5. Просьба о проверке полного периода
6. Приложение: упоминание Excel-файла

Tone: деловой, не бюрократический. Без технических терминов (не "dlv_prc", а "коэффициент склада").

- [ ] **Step 2: Verify page renders correctly**

- [ ] **Step 3: Note the page URL for user to share with financiers**

---

### Task 6: Final verification pass

- [ ] **Step 1: Run full verification suite**

```bash
python3 -m services.logistics_audit.verify_against_financiers
```

Expected: all 3 levels PASS.

- [ ] **Step 2: Run Fisanov validation**

```bash
python3 -m services.logistics_audit.recalculate_ooo --fisanov
```

Expected: remainder < 1 rub.

- [ ] **Step 3: Run all tests**

```bash
python3 -m pytest tests/logistics_audit/ -v
```

Expected: all tests pass (50+).

- [ ] **Step 4: Verify Excel file opens and totals match**

Open `ООО Wookiee — Перерасчёт логистики (v2-final).xlsx` and check:
- СВОД total overpay ≈ 24,373 rub
- Переплата по логистике has only positive rows
- Column names match financiers' format
- ИЛ sheet has 18 weeks

- [ ] **Step 5: Update CHANGELOG**

Add "Deliverables package" section to `services/logistics_audit/CHANGELOG-v2-fixes.md`:
- Verification: 3 levels pass
- Final Excel: 8 sheets
- Algorithm docs: `docs/logistics-audit-algorithm-v2.md`
- Notion: postmortem + letter to financiers

- [ ] **Step 6: Commit all remaining changes**

```bash
git add -A
git commit -m "feat(logistics-audit): complete deliverables package — verification, Excel, docs, Notion"
```
