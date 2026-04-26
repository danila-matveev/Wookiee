# Logistics Audit v2 — Fix 5 Calculation Errors

**Date:** 2026-04-03
**Status:** Design approved
**Problem:** Logistics audit script produces 94,062 rub discrepancy vs manual audit by financial team
**Approach:** Targeted fixes to 5 specific business rules in existing code

## Context

The logistics audit service (`services/logistics_audit/`, 32 files) was built 2026-03-25.
It calculates overpayments WB charges for logistics vs the formula from WB Offer.

**Published results (Notion):** 174,499 rub overpayment for ООО Wookiee (01.01–23.03.2026).
**Financial team feedback:** Calculation is incorrect, 94,062 rub discrepancy.
**Reference:** Manual audit "ИП Фисанов" (05.01–01.02.2026) = 144,901 rub overpayment on 1,157 rows.

Source materials:
- `services/logistics_audit/Расчет переплаты по логистике.pdf` — original methodology
- `services/logistics_audit/Рекомендации к изменениям в расчете логистики.pdf` — 5 errors identified
- `services/logistics_audit/ИП Фисанов. Проверка логистики 05.01.2026 г. - 01.02.2026 г._Итоговый.xlsx` — reference audit
- `services/logistics_audit/Запись экрана (01.04.2026 15-30-09) (2).wmv` — video walkthrough of errors

## 5 Fixes

### Fix 1: Filter logistics types (whitelist only forward deliveries)

**Problem:** Reverse logistics rows (returns, defects) are included in overpayment calculation.
They have fixed tariffs (50 rub) and should not be audited.

**File:** `calculators/logistics_overpayment.py`

**Rule:** Only these `supplier_oper_name` + delivery type combinations pass:
- "К клиенту при продаже"
- "К клиенту при отмене"

Everything else (all "От клиента", "Возврат брака", "Возврат неопознанного товара",
"Возврат по инициативе продавца", "Возврат товара продавцу по отзыву") is excluded.

**Implementation:** Add a whitelist constant at module level. Check before calculation.
Rows not in whitelist get `overpayment = None`.

### Fix 2: Sub-liter tariff tiers + period-based base tariffs

**Problem:** Script uses hardcoded `base_tariff_1l = 46` for all items.
Since 22.09.2025, WB introduced sub-liter pricing tiers, and historical periods had different rates.

**File:** `calculators/logistics_overpayment.py`

**New function:** `get_base_tariffs(order_date, fixation_start, fixation_end, volume) -> (first_liter, extra_liter)`

**Tariff period selection logic:**
- If `fixation_end > order_date` (fixation active): use `fixation_start` to determine period
- Else: use `order_date` to determine period

**Standard tariffs by period:**

| Date range | 1st liter (rub) | Extra liter (rub) |
|---|---|---|
| 14.08.2024 — 10.12.2024 | 33 | 8 |
| 11.12.2024 — 27.02.2025 | 35 | 8.5 |
| 28.02.2025 — 21.09.2025 | 38 | 9.5 |
| >= 22.09.2025 | 46 | 14 |

**Sub-liter tiers (only when order_date >= 22.09.2025 AND volume < 1L):**

| Volume range (L) | 1st liter (rub) | Extra liter (rub) |
|---|---|---|
| 0.001 — 0.200 | 23 | 0 |
| 0.201 — 0.400 | 26 | 0 |
| 0.401 — 0.600 | 29 | 0 |
| 0.601 — 0.800 | 30 | 0 |
| 0.801 — 1.000 | 32 | 0 |

Extra liter = 0 for sub-liter items (no additional liters exist).

### Fix 3: Warehouse coefficient selection with fixation check

**Problem:** Script uses `dlv_prc` from realization report for all rows.
Correct logic must check whether fixation is still active.

**File:** `calculators/logistics_overpayment.py`

**Rule:**
```python
if fixed_warehouse_coeff > 0 AND fixation_end_date > order_date:
    coef = fixed_warehouse_coeff
elif has_tariff_in_supabase(warehouse, order_date):
    coef = tariff_from_supabase  # from wb_tariffs_box ETL
else:
    coef = dlv_prc  # fallback from report row
    flag = "coefficient_not_verified"
```

**Data sources:**
- `fixed_warehouse_coeff`: from realization report field (фиксированный коэф. склада по поставке)
- `fixation_end_date`: from realization report field (дата конца действия фиксации)
- Supabase `wb_tariffs_box`: historical ETL (currently ~1 week of data)
- `dlv_prc`: from realization report (last resort fallback)

**Note:** Historical ETL data is limited (~1 week). As more data accumulates,
Supabase coverage will improve automatically. Rows using `dlv_prc` fallback
are flagged as "coefficient_not_verified" in output.

### Fix 4: Localization Index (ИЛ) calibration

**Problem:** Script calculates ИЛ from orders (~1.00 for Wookiee), but WB dashboard
shows different values (1.05–1.10). Reference Fisanov has ИЛ = 1.29–1.48.

**File:** `calculators/weekly_il_calculator.py`

**Approach:** Keep calculated ИЛ as base, add manual override capability for calibration.

**Changes:**
1. Add `il_overrides: dict[str, float]` parameter — manual ИЛ values by week start date
   (e.g., `{"2026-01-05": 1.09, "2026-01-12": 1.09, ...}`)
2. Priority: override > calculated
3. New CLI flag `--calibrate`: outputs table of calculated ИЛ values for comparison with WB dashboard
4. Config file `il_overrides.json` for persistent overrides

**Calibration workflow (iterative, post-fix):**
1. Run script with `--calibrate` for target period
2. User compares output with WB dashboard screenshots
3. If mismatch: either fix algorithm (warehouse→FD mapping) or add override
4. Repeat until match

### Fix 5: Exclude negative differences from totals

**Problem:** Rows where WB charged LESS than calculated (negative overpayment)
are included in total, inflating the reported overpayment.

**Files:** `output/sheet_overpayment_values.py`, `output/sheet_svod.py`

**Rule:** Negative differences stay in the sheet for transparency but are excluded from totals.

**Implementation:**
- New column "Включено в итог" (Included in total): "Да" / "Нет"
- Rows with negative difference → "Нет"
- СВОД summary sums only "Да" rows
- Формулы sheet: conditional sum excluding negative rows

## Multi-Agent Execution Pipeline

### Agent 1 — Executor
- Receives this spec with exact files and rules
- Works in isolated git worktree
- Implements Fix 1→2→3→4→5 sequentially
- Commits after each fix with descriptive message

### Agent 2 — Reviewer
- Runs after Executor completes
- Reads diff of each commit against this spec
- Checklist verification:
  - Fix 1: whitelist = exactly 2 types? Others filtered?
  - Fix 2: 4 tariff periods + 5 sub-liter tiers implemented? fixation_start vs order_date logic?
  - Fix 3: priority chain fixed→Supabase→dlv_prc? "not verified" flag?
  - Fix 4: overrides apply? calibrate mode works?
  - Fix 5: "Included in total" column? Totals exclude "Нет" rows?
- Output: PASS / FAIL with specific issues

### Agent 3 — Validator (Numerical Verification)
- Runs after Reviewer passes
- Loads Fisanov reference data (ИП, 05.01–01.02.2026)
- Runs updated script against same data
- Produces **discrepancy decomposition report:**

| Error source | Delta (rub) | Rows affected |
|---|---|---|
| Fix 1: Reverse logistics included | +XX XXX | N |
| Fix 2: Wrong base tariffs | +XX XXX | N |
| Fix 3: Wrong warehouse coefficient | +XX XXX | N |
| Fix 4: Wrong ИЛ values | +XX XXX | N |
| Fix 5: Negative differences included | +XX XXX | N |
| **Total explained** | **≈94,062** | |
| **Unexplained remainder** | **→ 0** | |

**Method:** Calculates overpayment 5 times — first without fixes (baseline), then
cumulatively adding Fix 1, 1+2, 1+2+3, etc. Delta between steps = contribution of each fix.

**Target: unexplained remainder = 0.** Every ruble of the 94K must be attributed to a specific fix.

**Failure handling:**
- If Reviewer finds issues → back to Executor (max 3 iterations)
- If Validator finds unexplained remainder > 0 → escalation to user with detailed report
- No auto-merge until remainder = 0

## Post-Fix: ИЛ Calibration for ООО Wookiee

After fixes are verified against Fisanov reference:

1. Run `--calibrate` for period 01.01–23.03.2026
2. User compares with WB dashboard and provides screenshots
3. Adjust algorithm or add overrides until match
4. Re-run full audit for ООО Wookiee with calibrated ИЛ values
5. Update Notion page with corrected results

## Files to Modify

| File | Changes |
|---|---|
| `calculators/logistics_overpayment.py` | Fixes 1, 2, 3 (whitelist, tariffs, warehouse coef) |
| `calculators/weekly_il_calculator.py` | Fix 4 (ИЛ overrides + calibrate mode) |
| `output/sheet_overpayment_values.py` | Fix 5 (included column, conditional totals) |
| `output/sheet_overpayment_formulas.py` | Fix 5 (formula sheet parity) |
| `output/sheet_svod.py` | Fix 5 (summary excludes negative rows) |
| `models/audit_config.py` | New fields: il_overrides path, calibrate flag |
| `runner.py` | CLI args for --calibrate, il_overrides.json |

## Success Criteria

1. Fisanov reference audit reproduced with 0 unexplained discrepancy
2. Each of the 5 error sources quantified in rub
3. ИЛ calibration mode functional for iterative tuning
4. All existing Excel sheets preserved and working
5. Negative differences visible but excluded from totals
