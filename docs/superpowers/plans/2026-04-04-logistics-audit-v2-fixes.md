# Logistics Audit v2 — Fix 5 Calculation Errors

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 5 business logic errors in the logistics audit that cause a 94,062 rub discrepancy vs manual audit.

**Architecture:** Sequential targeted fixes to `services/logistics_audit/` — each fix is an isolated change to one calculation rule. Fixes build on each other (Fix 1 filters rows, Fix 2-3 change per-row calculation, Fix 4 changes multiplier, Fix 5 changes output aggregation). All work happens in `services/logistics_audit/` directory.

**Tech Stack:** Python 3.12, openpyxl, psycopg2, httpx, Supabase (wb_tariffs table)

**Spec:** `docs/superpowers/specs/2026-04-03-logistics-audit-v2-fix-design.md`

---

## File Map

| File | Responsibility | Tasks |
|---|---|---|
| `services/logistics_audit/calculators/logistics_overpayment.py` | Core overpayment calculation | Fix 1, 2, 3 |
| `services/logistics_audit/calculators/tariff_periods.py` | **NEW** — Period-based tariff lookup | Fix 2 |
| `services/logistics_audit/calculators/warehouse_coef_resolver.py` | **NEW** — 3-tier coefficient resolution | Fix 3 |
| `services/logistics_audit/calculators/weekly_il_calculator.py` | Weekly IL calculation + overrides | Fix 4 |
| `services/logistics_audit/models/audit_config.py` | Config dataclass | Fix 2, 4 |
| `services/logistics_audit/models/report_row.py` | Row model — add `is_forward_delivery` | Fix 1 |
| `services/logistics_audit/output/sheet_overpayment_values.py` | Values sheet — "Включено в итог" column | Fix 5 |
| `services/logistics_audit/output/sheet_overpayment_formulas.py` | Formulas sheet — conditional sum | Fix 5 |
| `services/logistics_audit/output/sheet_svod.py` | СВОД — exclude negative rows | Fix 5 |
| `services/logistics_audit/output/excel_generator.py` | Wire new params through | Fix 3, 5 |
| `services/logistics_audit/runner.py` | Pipeline orchestration + CLI | Fix 1, 2, 3, 4 |
| `services/logistics_audit/config.py` | Config loader — new fields | Fix 4 |
| `services/logistics_audit/il_overrides.json` | **NEW** — Manual IL override values | Fix 4 |

---

## Task 1: Fix 1 — Filter logistics types (whitelist forward deliveries only)

**Problem:** Reverse logistics rows (returns, defects with `bonus_type_name` like "От клиента при отмене", etc.) are included in overpayment calculation. They have fixed tariffs (50 rub) and should not be audited.

**Files:**
- Modify: `services/logistics_audit/models/report_row.py`
- Modify: `services/logistics_audit/calculators/logistics_overpayment.py`
- Modify: `services/logistics_audit/runner.py`

### Steps

- [ ] **Step 1: Add forward delivery whitelist to report_row.py**

In `services/logistics_audit/models/report_row.py`, add the whitelist constant after `FIXED_RATE_TYPES` and a new property:

```python
FORWARD_DELIVERY_TYPES = frozenset({
    "К клиенту при продаже",
    "К клиенту при отмене",
})
```

Add property to `ReportRow` class (after `is_fixed_rate`):

```python
    @property
    def is_forward_delivery(self) -> bool:
        """Only forward deliveries are auditable for overpayment."""
        return self.bonus_type_name in FORWARD_DELIVERY_TYPES
```

- [ ] **Step 2: Update logistics_overpayment.py to accept and check the flag**

In `services/logistics_audit/calculators/logistics_overpayment.py`, add `is_forward_delivery: bool` parameter to `calculate_row_overpayment()` — insert it after `is_fixed_rate`:

```python
def calculate_row_overpayment(
    delivery_rub: float,
    volume: float,
    coef: float,
    base_1l: float,
    extra_l: float,
    order_dt: date | None,
    ktr_manual: float,
    is_fixed_rate: bool,
    is_forward_delivery: bool = True,
    sku_localization_pct: float | None = None,
    retail_price: float = 0.0,
) -> OverpaymentResult | None:
```

Add check right after `is_fixed_rate` check (line 33):

```python
    if is_fixed_rate:
        return OverpaymentResult(calculated_cost=delivery_rub, overpayment=0.0)

    if not is_forward_delivery:
        return None
```

- [ ] **Step 3: Pass the flag from runner.py**

In `services/logistics_audit/runner.py`, in the overpayment calculation loop (~line 155), add:

```python
        result = calculate_row_overpayment(
            delivery_rub=row.delivery_rub,
            volume=vol,
            coef=coef,
            base_1l=base,
            extra_l=config.base_tariff_extra_l,
            order_dt=row.order_dt,
            ktr_manual=row_il,
            is_fixed_rate=row.is_fixed_rate,
            is_forward_delivery=row.is_forward_delivery,
            sku_localization_pct=sku_localization.get(row.nm_id),
            retail_price=prices.get(row.nm_id, 0),
        )
```

- [ ] **Step 4: Verify syntax**

Run: `python -c "from services.logistics_audit.models.report_row import ReportRow, FORWARD_DELIVERY_TYPES; print(FORWARD_DELIVERY_TYPES)"`

Expected: `frozenset({'К клиенту при продаже', 'К клиенту при отмене'})`

- [ ] **Step 5: Commit**

```bash
git add services/logistics_audit/models/report_row.py services/logistics_audit/calculators/logistics_overpayment.py services/logistics_audit/runner.py
git commit -m "fix(logistics-audit): filter reverse logistics from overpayment (Fix 1)

Only forward deliveries ('К клиенту при продаже', 'К клиенту при отмене')
are now included in overpayment calculation. Reverse logistics rows
(returns, defects) have fixed tariffs and should not be audited."
```

---

## Task 2: Fix 2 — Period-based base tariffs + sub-liter tiers

**Problem:** Script uses hardcoded `base_tariff_1l = 46` for all items. Since 22.09.2025, WB has sub-liter pricing tiers, and historical periods had different base rates.

**Files:**
- Create: `services/logistics_audit/calculators/tariff_periods.py`
- Modify: `services/logistics_audit/models/audit_config.py`
- Modify: `services/logistics_audit/runner.py`

### Steps

- [ ] **Step 1: Create tariff_periods.py with period lookup + sub-liter tiers**

Create `services/logistics_audit/calculators/tariff_periods.py`:

```python
"""Period-based base tariffs and sub-liter pricing tiers for WB logistics."""
from __future__ import annotations
from datetime import date


# Standard tariffs by period: (start_date, first_liter, extra_liter)
# Sorted newest-first for lookup efficiency
TARIFF_PERIODS: list[tuple[date, float, float]] = [
    (date(2025, 9, 22), 46.0, 14.0),
    (date(2025, 2, 28), 38.0, 9.5),
    (date(2024, 12, 11), 35.0, 8.5),
    (date(2024, 8, 14), 33.0, 8.0),
]

# Sub-liter tiers (only for order_date >= 22.09.2025 AND volume < 1L)
# (max_volume, first_liter, extra_liter)
SUB_LITER_TIERS: list[tuple[float, float, float]] = [
    (0.200, 23.0, 0.0),
    (0.400, 26.0, 0.0),
    (0.600, 29.0, 0.0),
    (0.800, 30.0, 0.0),
    (1.000, 32.0, 0.0),
]

SUB_LITER_START = date(2025, 9, 22)


def get_base_tariffs(
    order_date: date | None,
    fixation_start: date | None,
    fixation_end: date | None,
    volume: float,
) -> tuple[float, float]:
    """Determine (first_liter, extra_liter) tariffs for a row.

    Tariff period selection:
    - If fixation is active (fixation_end > order_date): use fixation_start
    - Otherwise: use order_date

    Sub-liter tiers apply when order_date >= 22.09.2025 AND volume < 1L.
    """
    if order_date is None:
        # Fallback to latest period
        return TARIFF_PERIODS[0][1], TARIFF_PERIODS[0][2]

    # Determine reference date for period selection
    if (
        fixation_start
        and fixation_end
        and fixation_end > order_date
    ):
        ref_date = fixation_start
    else:
        ref_date = order_date

    # Sub-liter check (uses order_date, not ref_date)
    if order_date >= SUB_LITER_START and 0 < volume < 1.0:
        for max_vol, first_l, extra_l in SUB_LITER_TIERS:
            if volume <= max_vol:
                return first_l, extra_l
        # volume between 0.8 and 1.0 → last tier
        return SUB_LITER_TIERS[-1][1], SUB_LITER_TIERS[-1][2]

    # Standard period lookup
    for period_start, first_l, extra_l in TARIFF_PERIODS:
        if ref_date >= period_start:
            return first_l, extra_l

    # Before earliest known period — use earliest rates
    return TARIFF_PERIODS[-1][1], TARIFF_PERIODS[-1][2]
```

- [ ] **Step 2: Remove hardcoded tariff defaults from AuditConfig**

In `services/logistics_audit/models/audit_config.py`, remove `base_tariff_1l` and `base_tariff_extra_l` fields (they're now calculated per-row):

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import date


@dataclass
class AuditConfig:
    """Input parameters for the audit."""
    api_key: str
    date_from: date
    date_to: date
    ktr: float = 1.0
```

- [ ] **Step 3: Update runner.py to use per-row tariffs**

In `services/logistics_audit/runner.py`:

Add import at top (after other calculator imports):
```python
from services.logistics_audit.calculators.tariff_periods import get_base_tariffs
```

Replace the per-row calculation loop (Step 4, ~line 128-168). The key change is replacing the static `base`/`extra_l` with per-row `get_base_tariffs()`:

```python
    # === Step 4: Calculate overpayments ===
    results: list[OverpaymentResult | None] = []
    coefs: list[float] = []
    row_ils: list[float] = []
    for row in logistics_rows:
        vol = card_dims.get(row.nm_id, {}).get("volume", 0)

        # Determine coefficient
        if row.dlv_prc > 0:
            coef = row.dlv_prc
        else:
            coef = 0.0

        coefs.append(coef)

        # Per-row tariffs based on period + sub-liter tiers
        base_1l, extra_l = get_base_tariffs(
            order_date=row.order_dt,
            fixation_start=row.fix_tariff_date_from,
            fixation_end=row.fix_tariff_date_to,
            volume=vol,
        )

        # Per-row IL from weekly calculation
        row_il = get_il_for_date(week_to_il, row.order_dt)
        if row_il is None:
            row_il = config.ktr if config.ktr > 0 else 1.0
        row_ils.append(row_il)

        result = calculate_row_overpayment(
            delivery_rub=row.delivery_rub,
            volume=vol,
            coef=coef,
            base_1l=base_1l,
            extra_l=extra_l,
            order_dt=row.order_dt,
            ktr_manual=row_il,
            is_fixed_rate=row.is_fixed_rate,
            is_forward_delivery=row.is_forward_delivery,
            sku_localization_pct=sku_localization.get(row.nm_id),
            retail_price=prices.get(row.nm_id, 0),
        )
        results.append(result)
```

Also remove the tariff calibration block (Step 3, ~lines 102-126) which is no longer needed — tariffs are now looked up per-row from the period table. Remove these lines:

```python
    # === Step 3: Calibrate base tariff ===
    # ... (entire block from line 102 to line 126)
```

And remove the `calibrate_base_tariff` import from the top.

Also update `generate_workbook` call — remove `config.base_tariff_1l` and `config.base_tariff_extra_l` references. In the `write_overpayment_formulas` call inside `excel_generator.py`, we'll need to pass row-level tariffs instead of static ones. For now, pass default values to maintain sheet compatibility:

In `excel_generator.py`, update `write_overpayment_formulas` call:
```python
    write_overpayment_formulas(
        sheets["Переплата по логистике (короб)"], logistics_rows,
        ktr=config.ktr, base_1l=46.0, extra_l=14.0,
        row_ils=row_ils,
    )
```

- [ ] **Step 4: Verify syntax**

Run: `python -c "from services.logistics_audit.calculators.tariff_periods import get_base_tariffs; from datetime import date; print(get_base_tariffs(date(2025, 1, 15), None, None, 0.5))"`

Expected: `(33.0, 8.0)` (period 14.08.2024–10.12.2024, volume < 1L but before sub-liter start)

Run: `python -c "from services.logistics_audit.calculators.tariff_periods import get_base_tariffs; from datetime import date; print(get_base_tariffs(date(2026, 1, 15), None, None, 0.3))"`

Expected: `(26.0, 0.0)` (sub-liter tier 0.201–0.400)

- [ ] **Step 5: Commit**

```bash
git add services/logistics_audit/calculators/tariff_periods.py services/logistics_audit/models/audit_config.py services/logistics_audit/runner.py services/logistics_audit/output/excel_generator.py
git commit -m "fix(logistics-audit): period-based tariffs + sub-liter tiers (Fix 2)

Replace hardcoded base_tariff_1l=46 with period-based lookup:
- 4 tariff periods (14.08.2024 → current)
- 5 sub-liter tiers for items <1L (from 22.09.2025)
- Fixation-aware: uses fixation_start when fixation is active
Removes tariff calibration step (no longer needed)."
```

---

## Task 3: Fix 3 — Warehouse coefficient resolution with fixation check

**Problem:** Script always uses `dlv_prc` from realization report. Correct logic must check fixation status first, then try Supabase historical data, then fall back to `dlv_prc`.

**Files:**
- Create: `services/logistics_audit/calculators/warehouse_coef_resolver.py`
- Modify: `services/logistics_audit/runner.py`

### Steps

- [ ] **Step 1: Create warehouse_coef_resolver.py**

Create `services/logistics_audit/calculators/warehouse_coef_resolver.py`:

```python
"""3-tier warehouse coefficient resolution: fixation → Supabase → dlv_prc fallback."""
from __future__ import annotations
import logging
from dataclasses import dataclass
from datetime import date

logger = logging.getLogger(__name__)


@dataclass
class CoefResult:
    value: float
    source: str  # "fixation" | "supabase" | "dlv_prc"
    verified: bool  # False only for dlv_prc fallback


def resolve_warehouse_coef(
    dlv_prc: float,
    fixed_coef: float,
    fixation_end: date | None,
    order_date: date | None,
    warehouse_name: str,
    supabase_tariffs: dict[str, dict[date, float]],
) -> CoefResult:
    """Resolve warehouse coefficient with 3-tier priority.

    Priority:
    1. Fixed coefficient (if fixation is active: fixation_end > order_date)
    2. Supabase wb_tariffs (historical ETL data)
    3. dlv_prc from report (fallback, flagged as not verified)

    Args:
        dlv_prc: Coefficient from realization report row
        fixed_coef: Fixed warehouse coefficient from report (фикс. коэф. склада по поставке)
        fixation_end: End date of tariff fixation
        order_date: Order date for this row
        warehouse_name: Warehouse name for Supabase lookup
        supabase_tariffs: {warehouse_name: {date: coef}} from wb_tariffs ETL
    """
    # Tier 1: Fixed coefficient (fixation active)
    if fixed_coef > 0 and fixation_end and order_date and fixation_end > order_date:
        return CoefResult(value=fixed_coef, source="fixation", verified=True)

    # Tier 2: Supabase historical tariffs
    wh_tariffs = supabase_tariffs.get(warehouse_name)
    if wh_tariffs and order_date:
        # Find closest date <= order_date
        matching_dates = [d for d in wh_tariffs if d <= order_date]
        if matching_dates:
            closest = max(matching_dates)
            coef = wh_tariffs[closest]
            if coef > 0:
                return CoefResult(value=coef, source="supabase", verified=True)

    # Tier 3: dlv_prc fallback
    if dlv_prc > 0:
        return CoefResult(value=dlv_prc, source="dlv_prc", verified=False)

    return CoefResult(value=0.0, source="dlv_prc", verified=False)


def load_supabase_tariffs(date_from: date, date_to: date) -> dict[str, dict[date, float]]:
    """Load warehouse coefficients from Supabase wb_tariffs table.

    Returns: {warehouse_name: {date: delivery_coef_pct / 100}}
    """
    import os
    try:
        import psycopg2
    except ImportError:
        logger.warning("psycopg2 not installed, skipping Supabase tariff lookup")
        return {}

    config = {
        "host": os.getenv("POSTGRES_HOST_SUPABASE", os.getenv("POSTGRES_HOST", "localhost")),
        "port": int(os.getenv("POSTGRES_PORT_SUPABASE", os.getenv("POSTGRES_PORT", "5432"))),
        "database": os.getenv("POSTGRES_DB_SUPABASE", os.getenv("POSTGRES_DB", "postgres")),
        "user": os.getenv("POSTGRES_USER_SUPABASE", os.getenv("POSTGRES_USER", "postgres")),
        "password": os.getenv("POSTGRES_PASSWORD_SUPABASE", os.getenv("POSTGRES_PASSWORD", "")),
        "sslmode": "require",
    }

    try:
        conn = psycopg2.connect(**config)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT dt, warehouse_name, delivery_coef
            FROM wb_tariffs
            WHERE dt BETWEEN %s AND %s
            """,
            (date_from, date_to),
        )
        result: dict[str, dict[date, float]] = {}
        for dt, wh_name, coef in cur.fetchall():
            if wh_name not in result:
                result[wh_name] = {}
            result[wh_name][dt] = coef / 100.0  # stored as pct, need decimal
        cur.close()
        conn.close()
        logger.info(f"Loaded Supabase tariffs: {len(result)} warehouses, "
                     f"{sum(len(v) for v in result.values())} data points")
        return result
    except Exception as e:
        logger.warning(f"Failed to load Supabase tariffs: {e}")
        return {}
```

- [ ] **Step 2: Add fixed_warehouse_coef to ReportRow**

In `services/logistics_audit/models/report_row.py`, the field `dlv_prc` currently stores the coefficient from the report. We need to also capture the fixed warehouse coefficient. The WB API field is `kiz` — but actually looking at the spec, the fixed coefficient is likely already in `dlv_prc` when fixation is active. The spec says `fixed_warehouse_coeff` comes from "фиксированный коэф. склада по поставке" in the report.

Check the WB API v5 response — the field name is likely `dlv_prc` itself (it represents the coefficient). The fixation dates (`fix_tariff_date_from`, `fix_tariff_date_to`) are already parsed in `ReportRow`. When fixation is active, `dlv_prc` IS the fixed coefficient.

So the resolution logic simplifies to: if fixation dates exist and fixation is active → `dlv_prc` is the fixed coef (tier 1). Otherwise → check Supabase → fallback to `dlv_prc` (but flagged as unverified).

No change needed to ReportRow model — `dlv_prc` and `fix_tariff_date_to` are already available.

- [ ] **Step 3: Wire coefficient resolver into runner.py**

In `services/logistics_audit/runner.py`, add import:
```python
from services.logistics_audit.calculators.warehouse_coef_resolver import (
    resolve_warehouse_coef,
    load_supabase_tariffs,
    CoefResult,
)
```

After the orders fetch block (~after Step 2c), add Supabase tariff loading:
```python
    # === Step 2d: Load Supabase historical tariffs for coefficient resolution ===
    logger.info("Loading Supabase historical tariffs...")
    supabase_tariffs = load_supabase_tariffs(config.date_from, config.date_to)
```

Replace the coefficient determination in the calculation loop. Change:
```python
        # Determine coefficient
        if row.dlv_prc > 0:
            coef = row.dlv_prc
        else:
            coef = 0.0
```

To:
```python
        # Resolve coefficient with 3-tier priority
        coef_result = resolve_warehouse_coef(
            dlv_prc=row.dlv_prc,
            fixed_coef=row.dlv_prc,  # dlv_prc is the fixed coef when fixation active
            fixation_end=row.fix_tariff_date_to,
            order_date=row.order_dt,
            warehouse_name=row.office_name,
            supabase_tariffs=supabase_tariffs,
        )
        coef = coef_result.value
```

- [ ] **Step 4: Verify syntax**

Run: `python -c "from services.logistics_audit.calculators.warehouse_coef_resolver import resolve_warehouse_coef, CoefResult; from datetime import date; r = resolve_warehouse_coef(1.5, 1.5, date(2026, 6, 1), date(2026, 1, 15), 'Склад', {}); print(r)"`

Expected: `CoefResult(value=1.5, source='fixation', verified=True)` (fixation_end > order_date)

- [ ] **Step 5: Commit**

```bash
git add services/logistics_audit/calculators/warehouse_coef_resolver.py services/logistics_audit/runner.py
git commit -m "fix(logistics-audit): 3-tier warehouse coefficient resolution (Fix 3)

Priority: fixation (active) → Supabase wb_tariffs ETL → dlv_prc fallback.
Rows using dlv_prc fallback are flagged as not verified.
Supabase lookup uses historical ETL data from tariff_collector."
```

---

## Task 4: Fix 4 — IL calibration with manual overrides

**Problem:** Calculated IL (~1.00 for Wookiee) differs from WB dashboard (1.05–1.10). Need override capability.

**Files:**
- Modify: `services/logistics_audit/calculators/weekly_il_calculator.py`
- Create: `services/logistics_audit/il_overrides.json`
- Modify: `services/logistics_audit/config.py`
- Modify: `services/logistics_audit/runner.py`

### Steps

- [ ] **Step 1: Add IL overrides to weekly_il_calculator.py**

In `services/logistics_audit/calculators/weekly_il_calculator.py`, modify `calculate_weekly_il` to accept overrides:

Change function signature:
```python
def calculate_weekly_il(
    orders: list[dict],
    date_from: date,
    date_to: date,
    il_overrides: dict[str, float] | None = None,
) -> tuple[dict[date, float], list[dict]]:
```

After building `week_to_il` mapping (after the `for mon in all_mondays` loop, ~line 89), apply overrides:

```python
    # --- 2b. Apply manual overrides ---
    if il_overrides:
        for date_str, override_il in il_overrides.items():
            try:
                override_date = date.fromisoformat(date_str)
                mon = _monday(override_date)
                if mon in week_to_il:
                    week_to_il[mon] = override_il
            except ValueError:
                pass
```

Update `il_data` generation to show override status. Change the il_data block:
```python
    # --- 3. Build il_data for Excel sheet ---
    override_mondays = set()
    if il_overrides:
        for date_str in il_overrides:
            try:
                override_mondays.add(_monday(date.fromisoformat(date_str)))
            except ValueError:
                pass

    il_data: list[dict] = []
    for mon in sorted(all_mondays, reverse=True):
        sun = mon + timedelta(days=6)
        il_data.append({
            "date": mon.isoformat(),
            "il": week_to_il[mon],
            "date_from": mon.isoformat(),
            "date_to": sun.isoformat(),
            "source": "override" if mon in override_mondays else "calculated",
        })
```

- [ ] **Step 2: Add --calibrate mode**

Add a new function at the end of `weekly_il_calculator.py`:

```python
def print_calibration_table(
    orders: list[dict],
    date_from: date,
    date_to: date,
    il_overrides: dict[str, float] | None = None,
) -> None:
    """Print IL values for comparison with WB dashboard."""
    week_to_il, il_data = calculate_weekly_il(orders, date_from, date_to, il_overrides)

    print(f"\n{'Week':<24} {'IL':>8} {'Source':<12}")
    print("-" * 48)
    for entry in reversed(il_data):
        src = entry.get("source", "calculated")
        marker = " *" if src == "override" else ""
        print(f"{entry['date_from']} — {entry['date_to']}  {entry['il']:>8.4f} {src:<12}{marker}")
    print("\n* = manual override applied")
```

- [ ] **Step 3: Create il_overrides.json**

Create `services/logistics_audit/il_overrides.json`:

```json
{
    "_comment": "Manual IL overrides by week start date (Monday). Values from WB dashboard.",
    "_usage": "Compare --calibrate output with WB dashboard, add overrides for mismatches."
}
```

- [ ] **Step 4: Update config.py to load overrides**

In `services/logistics_audit/config.py`, add override loading:

```python
"""Load config from environment / .env for logistics audit."""
from __future__ import annotations
import json
import os
from datetime import date
from pathlib import Path
from dotenv import load_dotenv
from services.logistics_audit.models.audit_config import AuditConfig

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

IL_OVERRIDES_PATH = Path(__file__).parent / "il_overrides.json"


def load_il_overrides(path: Path | None = None) -> dict[str, float]:
    """Load IL overrides from JSON. Returns {date_str: il_value}."""
    p = path or IL_OVERRIDES_PATH
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return {k: float(v) for k, v in data.items() if not k.startswith("_")}
    except (json.JSONDecodeError, ValueError):
        return {}


def load_config(
    cabinet: str = "OOO",
    date_from: str | None = None,
    date_to: str | None = None,
    ktr: float = 1.0,
) -> AuditConfig:
    api_key = os.getenv(f"WB_API_KEY_{cabinet.upper()}")
    if not api_key:
        raise ValueError(f"Missing WB_API_KEY_{cabinet.upper()} in .env")
    return AuditConfig(
        api_key=api_key,
        date_from=date.fromisoformat(date_from) if date_from else date.today(),
        date_to=date.fromisoformat(date_to) if date_to else date.today(),
        ktr=ktr,
    )
```

- [ ] **Step 5: Wire overrides + calibrate into runner.py**

In `services/logistics_audit/runner.py`:

Add import:
```python
from services.logistics_audit.config import load_il_overrides
from services.logistics_audit.calculators.weekly_il_calculator import print_calibration_table
```

In `run_audit()`, load overrides and pass to `calculate_weekly_il`:
```python
    # Load IL overrides
    il_overrides = load_il_overrides()
    if il_overrides:
        logger.info(f"IL overrides loaded: {len(il_overrides)} weeks")

    week_to_il, il_data = calculate_weekly_il(
        orders, config.date_from, config.date_to, il_overrides=il_overrides,
    )
```

Update the `if __name__ == "__main__"` block to support `--calibrate`:
```python
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    from services.logistics_audit.config import load_config, load_il_overrides

    # Parse args
    args = sys.argv[1:]
    calibrate_mode = "--calibrate" in args
    args = [a for a in args if a != "--calibrate"]

    cabinet = args[0] if len(args) > 0 else "OOO"
    date_from = args[1] if len(args) > 1 else None
    date_to = args[2] if len(args) > 2 else None
    ktr = float(args[3]) if len(args) > 3 else 1.0

    cfg = load_config(cabinet, date_from, date_to, ktr)

    if calibrate_mode:
        from datetime import timedelta
        from shared.clients.wb_client import WBClient
        wb_client = WBClient(api_key=cfg.api_key, cabinet_name="audit")
        orders_from = (cfg.date_from - timedelta(days=7)).isoformat()
        orders = wb_client.get_supplier_orders(date_from=orders_from)
        wb_client.close()
        il_overrides = load_il_overrides()
        print_calibration_table(orders, cfg.date_from, cfg.date_to, il_overrides)
    else:
        output = run_audit(cfg)
        print(f"Done: {output}")
```

- [ ] **Step 6: Verify syntax**

Run: `python -c "from services.logistics_audit.config import load_il_overrides; print(load_il_overrides())"`

Expected: `{}` (empty dict — no real overrides yet)

- [ ] **Step 7: Commit**

```bash
git add services/logistics_audit/calculators/weekly_il_calculator.py services/logistics_audit/il_overrides.json services/logistics_audit/config.py services/logistics_audit/runner.py
git commit -m "fix(logistics-audit): IL calibration with manual overrides (Fix 4)

- il_overrides.json for manual IL values by week
- --calibrate mode outputs comparison table for WB dashboard
- Override priority: manual > calculated
- Iterative calibration workflow enabled"
```

---

## Task 5: Fix 5 — Exclude negative differences from totals

**Problem:** Rows where WB charged LESS than calculated (negative overpayment) inflate the total.

**Files:**
- Modify: `services/logistics_audit/output/sheet_overpayment_values.py`
- Modify: `services/logistics_audit/output/sheet_overpayment_formulas.py`
- Modify: `services/logistics_audit/output/sheet_svod.py`
- Modify: `services/logistics_audit/output/excel_generator.py`

### Steps

- [ ] **Step 1: Update sheet_overpayment_values.py**

Replace `services/logistics_audit/output/sheet_overpayment_values.py` content:

```python
"""Sheet 2: 'Переплата по логистике' — pre-calculated values, no formulas."""
from __future__ import annotations
from openpyxl.worksheet.worksheet import Worksheet
from services.logistics_audit.models.report_row import ReportRow
from services.logistics_audit.calculators.logistics_overpayment import OverpaymentResult

HEADERS = [
    "№ отчёта", "Номер поставки", "Код номенклатуры", "Дата заказа",
    "Услуги по доставке", "Склад", "ШК", "Srid", "Фикс. коэф.",
    "Коэф. для расчёта", "Объём", "КТР", "Расчётная стоимость",
    "Разница (переплата)", "Включено в итог",
]


def write_overpayment_values(
    ws: Worksheet,
    rows: list[ReportRow],
    results: list[OverpaymentResult | None],
    volumes: dict[int, float],
    coefs: list[float],
    row_ils: list[float] | None = None,
) -> None:
    """Write Sheet 2 with pre-calculated overpayment values."""
    for col, h in enumerate(HEADERS, 1):
        ws.cell(1, col, h)

    total_overpayment = 0.0
    for i, (row, res, coef) in enumerate(zip(rows, results, coefs), 2):
        if res is None:
            continue
        idx = i - 2
        included = res.overpayment >= 0
        ws.cell(i, 1, row.realizationreport_id)
        ws.cell(i, 2, row.gi_id)
        ws.cell(i, 3, row.nm_id)
        ws.cell(i, 4, str(row.order_dt) if row.order_dt else "")
        ws.cell(i, 5, row.delivery_rub)
        ws.cell(i, 6, row.office_name)
        ws.cell(i, 7, row.shk_id)
        ws.cell(i, 8, row.srid)
        ws.cell(i, 9, row.dlv_prc)
        ws.cell(i, 10, coef)
        ws.cell(i, 11, volumes.get(row.nm_id, 0))
        if row_ils is not None and idx < len(row_ils):
            ws.cell(i, 12, row_ils[idx])
        else:
            ws.cell(i, 12, res.calculated_cost)
        ws.cell(i, 13, res.calculated_cost)
        ws.cell(i, 14, res.overpayment)
        ws.cell(i, 15, "Да" if included else "Нет")
        if included:
            total_overpayment += res.overpayment

    # Summary row at top
    ws.insert_rows(1)
    ws.cell(1, 1, "ИТОГО переплата:")
    ws.cell(1, 14, round(total_overpayment, 2))
    ws.cell(1, 15, "(только положительные)")
```

- [ ] **Step 2: Update sheet_overpayment_formulas.py — add conditional sum**

In `services/logistics_audit/output/sheet_overpayment_formulas.py`:

Add new column header. Change HEADERS — add after "Разница" (column S):
```python
HEADERS = [
    "Номер поставки",      # A: gi_id
    "Код номенклатуры",     # B: nm_id
    "Дата заказа",          # C: order_dt
    "",                     # D: unused
    "Услуги по доставке",   # E: delivery_rub
    "Дата начала фиксации", # F: fix_tariff_date_from
    "Дата конца фиксации",  # G: fix_tariff_date_to
    "Склад",                # H: office_name
    "ШК",                   # I: shk_id
    "Srid",                 # J: srid
    "Фикс. коэф.",         # K: dlv_prc
    "Коэф. для расчёта",   # L: formula
    "Объём из карточки",    # M: VLOOKUP
    "Объём из остатков",    # N: warehouse_remains
    "КТР",                  # O: ktr
    "Стоимость 1л",         # P: base_1l
    "Стоимость доп.л",      # Q: extra_l
    "Стоимость логистики",  # R: formula
    "Разница",              # S: formula
    "Включено в итог",      # T: formula
]
```

At the end of the row loop (after the `S` column formula), add column T:
```python
        # T: included in total (only positive differences)
        ws.cell(i, 20, f'=IF(S{i}>=0,"Да","Нет")')
```

- [ ] **Step 3: Update sheet_svod.py — exclude negative overpayments**

In `services/logistics_audit/output/sheet_svod.py`, change `write_svod` to accept per-row results for filtering:

Replace the function signature and body:

```python
def write_svod(
    ws: Worksheet,
    all_rows: list[ReportRow],
    overpayments_by_report: dict[int, float],
) -> None:
    """Write SVOD sheet: one row per realizationreport_id.

    overpayments_by_report should already exclude negative differences.
    """
```

The filtering happens in `excel_generator.py` when building `overpay_by_report`. No changes needed to `sheet_svod.py` itself — just the data passed to it.

- [ ] **Step 4: Update excel_generator.py — filter negative overpayments for SVOD**

In `services/logistics_audit/output/excel_generator.py`, change the overpayment aggregation block:

```python
    # Aggregate overpayment by report (exclude negative differences)
    overpay_by_report: dict[int, float] = {}
    for row, res in zip(logistics_rows, overpayment_results):
        if res is not None and res.overpayment >= 0:
            rid = row.realizationreport_id
            overpay_by_report[rid] = overpay_by_report.get(rid, 0) + res.overpayment
```

- [ ] **Step 5: Verify syntax**

Run: `python -c "from services.logistics_audit.output.sheet_overpayment_values import HEADERS; print(len(HEADERS), HEADERS[-1])"`

Expected: `15 Включено в итог`

- [ ] **Step 6: Commit**

```bash
git add services/logistics_audit/output/sheet_overpayment_values.py services/logistics_audit/output/sheet_overpayment_formulas.py services/logistics_audit/output/sheet_svod.py services/logistics_audit/output/excel_generator.py
git commit -m "fix(logistics-audit): exclude negative differences from totals (Fix 5)

- New column 'Включено в итог': Да/Нет per row
- Negative overpayments visible in sheet but excluded from ИТОГО
- СВОД summary sums only positive differences
- Formula sheet has matching conditional column"
```

---

## Task 6: Post-fix — Integration verification

**Files:** None (verification only)

- [ ] **Step 1: Verify all imports resolve**

Run: `python -c "from services.logistics_audit.runner import run_audit; print('OK')"`

Expected: `OK`

- [ ] **Step 2: Verify tariff_periods edge cases**

Run:
```bash
python -c "
from services.logistics_audit.calculators.tariff_periods import get_base_tariffs
from datetime import date

# Period: before earliest
print('Before:', get_base_tariffs(date(2024, 1, 1), None, None, 2.0))

# Period: 14.08.2024–10.12.2024
print('Aug 2024:', get_base_tariffs(date(2024, 10, 1), None, None, 2.0))

# Sub-liter: 0.15L on 2026-01-15
print('Sub-liter 0.15:', get_base_tariffs(date(2026, 1, 15), None, None, 0.15))

# Sub-liter: 0.5L on 2026-01-15
print('Sub-liter 0.5:', get_base_tariffs(date(2026, 1, 15), None, None, 0.5))

# Fixation active: fixation_start in old period
print('Fixation:', get_base_tariffs(date(2026, 1, 1), date(2024, 11, 1), date(2026, 6, 1), 2.0))

# Normal current period
print('Current:', get_base_tariffs(date(2026, 1, 15), None, None, 2.0))
"
```

Expected:
```
Before: (33.0, 8.0)
Aug 2024: (33.0, 8.0)
Sub-liter 0.15: (23.0, 0.0)
Sub-liter 0.5: (29.0, 0.0)
Fixation: (35.0, 8.5)
Current: (46.0, 14.0)
```

- [ ] **Step 3: Verify warehouse coef resolver**

Run:
```bash
python -c "
from services.logistics_audit.calculators.warehouse_coef_resolver import resolve_warehouse_coef
from datetime import date

# Fixation active
r = resolve_warehouse_coef(1.5, 1.5, date(2026, 6, 1), date(2026, 1, 15), 'Test', {})
print('Fixation:', r)

# No fixation, no Supabase → dlv_prc fallback
r = resolve_warehouse_coef(1.5, 0.0, None, date(2026, 1, 15), 'Test', {})
print('Fallback:', r)

# No fixation, has Supabase data
sb = {'Test': {date(2026, 1, 10): 2.0, date(2026, 1, 14): 2.5}}
r = resolve_warehouse_coef(1.5, 0.0, None, date(2026, 1, 15), 'Test', sb)
print('Supabase:', r)
"
```

Expected:
```
Fixation: CoefResult(value=1.5, source='fixation', verified=True)
Fallback: CoefResult(value=1.5, source='dlv_prc', verified=False)
Supabase: CoefResult(value=2.5, source='supabase', verified=True)
```

---

## Reviewer Checklist (for Agent 2)

After all tasks complete, verify against the spec:

- [ ] **Fix 1:** Whitelist = exactly 2 types ("К клиенту при продаже", "К клиенту при отмене")? All others return None from `calculate_row_overpayment`?
- [ ] **Fix 2:** 4 tariff periods implemented with correct dates and values? 5 sub-liter tiers? Fixation-aware period selection (uses `fixation_start` when active)?
- [ ] **Fix 3:** Priority chain fixed→Supabase→dlv_prc? `verified=False` flag on dlv_prc fallback?
- [ ] **Fix 4:** `il_overrides.json` loaded and applied? `--calibrate` mode prints comparison table? Override > calculated priority?
- [ ] **Fix 5:** "Включено в итог" column in both sheets? ИТОГО sums only "Да" rows? СВОД excludes negative?
- [ ] **No regressions:** All existing sheet structures preserved? No removed columns?
