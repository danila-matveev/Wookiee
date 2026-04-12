# WB Logistics Audit Service — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a service that pulls WB API data, calculates logistics overpayments per the WB offer formula, and generates an 11-sheet Excel document identical to the contractor's example.

**Architecture:** Standalone Python module `services/logistics_audit/` with 4 layers: API clients (data fetching), calculators (business logic), models (dataclasses), output (openpyxl Excel generator). Each sheet is a separate generator file. Runner orchestrates the pipeline: fetch → calculate → generate.

**Tech Stack:** Python 3.11+, httpx (HTTP client), openpyxl (Excel), statistics (median), dataclasses, pytest

**Spec:** `docs/superpowers/specs/2026-03-25-logistics-audit-service-design.md`

---

## File Structure

```
services/logistics_audit/
├── __init__.py
├── config.py                          # AuditConfig dataclass: api_key, period, ktr, base tariffs
├── api/
│   ├── __init__.py
│   ├── wb_reports.py                  # reportDetailByPeriod v5, rrd_id pagination
│   ├── wb_tariffs.py                  # tariffs/box + tariffs/pallet, parse "89,7" → 89.7
│   ├── wb_content.py                  # Content API cards with dimensions, cursor pagination
│   ├── wb_warehouse_remains.py        # warehouse_remains async pattern (create→poll→download)
│   └── wb_penalties.py                # measurement-penalties, deductions, antifraud, goods-labeling
├── calculators/
│   ├── __init__.py
│   ├── tariff_calibrator.py           # Reverse-calculate base tariff from ≤1L rows
│   ├── logistics_overpayment.py       # Main formula: old (KTR) + new (IL+IRP) per-row
│   ├── localization_resolver.py       # Calculate per-SKU localization % from WB orders
│   └── dimensions_checker.py          # Card vs WB volume comparison
├── models/
│   ├── __init__.py
│   ├── report_row.py                  # @dataclass ReportRow: all fields from reportDetailByPeriod
│   ├── tariff_snapshot.py             # @dataclass TariffSnapshot: warehouse tariffs on date
│   └── audit_config.py               # @dataclass AuditConfig: api_key, dates, ktr, base tariffs
├── output/
│   ├── __init__.py
│   ├── excel_generator.py             # Main orchestrator: creates workbook, calls sheet generators
│   ├── sheet_overpayment_formulas.py  # Sheet 1: live Excel formulas
│   ├── sheet_overpayment_values.py    # Sheet 2: calculated values
│   ├── sheet_svod.py                  # Sheet 3: summary by report
│   ├── sheet_detail.py                # Sheet 4: full 80-column dump
│   ├── sheet_il.py                    # Sheet 5: localization index
│   ├── sheet_pivot_by_article.py      # Sheet 6: overpayment by nm_id
│   ├── sheet_logistics_types.py       # Sheet 7: by bonus_type_name
│   ├── sheet_weekly.py                # Sheet 8: weekly aggregation
│   ├── sheet_dimensions.py            # Sheet 9: card dimensions
│   ├── sheet_tariffs_box.py           # Sheet 10: box tariffs
│   └── sheet_tariffs_pallet.py        # Sheet 11: pallet tariffs
├── runner.py                          # Entry point: fetch → calculate → generate Excel
tests/
└── services/
    └── logistics_audit/
        ├── __init__.py
        ├── test_models.py
        ├── test_tariff_calibrator.py
        ├── test_overpayment.py
        ├── test_dimensions_checker.py
        ├── test_api_parsing.py
        └── test_excel_sheets.py
```

---

## Task 1: Models — Data Structures

**Files:**
- Create: `services/logistics_audit/__init__.py`
- Create: `services/logistics_audit/models/__init__.py`
- Create: `services/logistics_audit/models/report_row.py`
- Create: `services/logistics_audit/models/tariff_snapshot.py`
- Create: `services/logistics_audit/models/audit_config.py`
- Test: `tests/services/logistics_audit/__init__.py`
- Test: `tests/services/logistics_audit/test_models.py`

- [ ] **Step 1: Write tests for ReportRow**

```python
# tests/services/logistics_audit/test_models.py
from datetime import date, datetime

def test_report_row_from_api_dict():
    """Parse a real API row into ReportRow dataclass."""
    raw = {
        "realizationreport_id": 658038623,
        "nm_id": 257131227,
        "office_name": "Коледино",
        "supplier_oper_name": "Логистика",
        "bonus_type_name": "К клиенту при продаже",
        "delivery_rub": 147.23,
        "dlv_prc": 1.95,
        "fix_tariff_date_from": "2025-12-11",
        "fix_tariff_date_to": "2026-02-09",
        "order_dt": "2026-02-28T00:00:00",
        "shk_id": 41793344171,
        "srid": "20966880121115600.0.0",
        "gi_id": 12345,
        "gi_box_type_name": "Микс",
        "storage_fee": 0,
        "penalty": 0,
        "deduction": 0,
        "rebill_logistic_cost": 0,
        "ppvz_for_pay": 1234.56,
        "ppvz_supplier_name": "ООО Вуки",
        "retail_amount": 2000.0,
        "date_from": "2026-03-09",
        "date_to": "2026-03-15",
        "doc_type_name": "Продажа",
        "acceptance": 0,
    }
    from services.logistics_audit.models.report_row import ReportRow
    row = ReportRow.from_api(raw)
    assert row.nm_id == 257131227
    assert row.delivery_rub == 147.23
    assert row.dlv_prc == 1.95
    assert row.order_dt == date(2026, 2, 28)
    assert row.fix_tariff_date_to == date(2026, 2, 9)
    assert row.is_logistics is True
    assert row.is_fixed_rate is False


def test_report_row_fixed_rate():
    """Rows with 'От клиента при отмене' are fixed-rate."""
    raw = {
        "supplier_oper_name": "Логистика",
        "bonus_type_name": "От клиента при отмене",
        "delivery_rub": 50.0,
        "dlv_prc": 0,
        "nm_id": 123,
        "office_name": "Тула",
        "order_dt": "2026-03-01T00:00:00",
        "fix_tariff_date_from": "",
        "fix_tariff_date_to": "",
    }
    from services.logistics_audit.models.report_row import ReportRow
    row = ReportRow.from_api(raw)
    assert row.is_fixed_rate is True


def test_tariff_snapshot_parse_russian_decimal():
    """Parse Russian-format decimals: '89,7' → 89.7"""
    from services.logistics_audit.models.tariff_snapshot import TariffSnapshot
    raw = {
        "warehouseName": "Коледино",
        "boxDeliveryBase": "89,7",
        "boxDeliveryLiter": "27,3",
        "boxDeliveryCoefExpr": "195",
        "boxStorageBase": "0,1",
        "boxStorageCoefExpr": "145",
        "boxStorageLiter": "0,1",
        "geoName": "ЦФО",
    }
    snap = TariffSnapshot.from_api(raw)
    assert snap.warehouse_name == "Коледино"
    assert snap.box_delivery_base == 89.7
    assert snap.box_delivery_liter == 27.3
    assert snap.delivery_coef_pct == 195
    assert snap.storage_coef_pct == 145


def test_tariff_snapshot_dash_value():
    """'-' values (marketplace unavailable) parse as 0."""
    from services.logistics_audit.models.tariff_snapshot import TariffSnapshot
    raw = {
        "warehouseName": "Электросталь",
        "boxDeliveryBase": "73,6",
        "boxDeliveryLiter": "22,4",
        "boxDeliveryCoefExpr": "160",
        "boxDeliveryMarketplaceBase": "-",
        "boxDeliveryMarketplaceCoefExpr": "-",
        "boxDeliveryMarketplaceLiter": "-",
        "boxStorageBase": "0,08",
        "boxStorageCoefExpr": "115",
        "boxStorageLiter": "0,08",
        "geoName": "ЦФО",
    }
    snap = TariffSnapshot.from_api(raw)
    assert snap.box_delivery_base == 73.6


def test_audit_config():
    from services.logistics_audit.models.audit_config import AuditConfig
    cfg = AuditConfig(
        api_key="test_key",
        date_from=date(2026, 3, 9),
        date_to=date(2026, 3, 15),
        ktr=1.04,
        base_tariff_1l=46.0,
        base_tariff_extra_l=14.0,
    )
    assert cfg.ktr == 1.04
    assert cfg.base_tariff_1l == 46.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/services/logistics_audit/test_models.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'services.logistics_audit'`

- [ ] **Step 3: Implement ReportRow**

```python
# services/logistics_audit/models/report_row.py
from __future__ import annotations
from dataclasses import dataclass
from datetime import date

FIXED_RATE_TYPES = frozenset({
    "От клиента при отмене",
    "От клиента при возврате",
})


@dataclass(slots=True)
class ReportRow:
    """One row from reportDetailByPeriod v5."""
    realizationreport_id: int
    nm_id: int
    office_name: str
    supplier_oper_name: str
    bonus_type_name: str
    delivery_rub: float
    dlv_prc: float
    fix_tariff_date_from: date | None
    fix_tariff_date_to: date | None
    order_dt: date | None
    shk_id: int
    srid: str
    gi_id: int
    gi_box_type_name: str
    storage_fee: float
    penalty: float
    deduction: float
    rebill_logistic_cost: float
    ppvz_for_pay: float
    ppvz_supplier_name: str
    retail_amount: float
    date_from: str
    date_to: str
    doc_type_name: str
    acceptance: float
    # Raw dict for sheet 4 (full 80-column dump)
    raw: dict | None = None

    @property
    def is_logistics(self) -> bool:
        return self.supplier_oper_name == "Логистика"

    @property
    def is_fixed_rate(self) -> bool:
        return self.bonus_type_name in FIXED_RATE_TYPES

    @classmethod
    def from_api(cls, d: dict) -> ReportRow:
        return cls(
            realizationreport_id=d.get("realizationreport_id", 0),
            nm_id=d.get("nm_id", 0),
            office_name=d.get("office_name", ""),
            supplier_oper_name=d.get("supplier_oper_name", ""),
            bonus_type_name=d.get("bonus_type_name", ""),
            delivery_rub=d.get("delivery_rub", 0.0),
            dlv_prc=d.get("dlv_prc", 0.0),
            fix_tariff_date_from=_parse_date(d.get("fix_tariff_date_from")),
            fix_tariff_date_to=_parse_date(d.get("fix_tariff_date_to")),
            order_dt=_parse_date(d.get("order_dt")),
            shk_id=d.get("shk_id", 0),
            srid=d.get("srid", ""),
            gi_id=d.get("gi_id", 0),
            gi_box_type_name=d.get("gi_box_type_name", ""),
            storage_fee=d.get("storage_fee", 0.0),
            penalty=d.get("penalty", 0.0),
            deduction=d.get("deduction", 0.0),
            rebill_logistic_cost=d.get("rebill_logistic_cost", 0.0),
            ppvz_for_pay=d.get("ppvz_for_pay", 0.0),
            ppvz_supplier_name=d.get("ppvz_supplier_name", ""),
            retail_amount=d.get("retail_amount", 0.0),
            date_from=d.get("date_from", ""),
            date_to=d.get("date_to", ""),
            doc_type_name=d.get("doc_type_name", ""),
            acceptance=d.get("acceptance", 0.0),
            raw=d,
        )


def _parse_date(val: str | None) -> date | None:
    if not val:
        return None
    # Handle "2026-02-28T00:00:00" and "2026-02-28" formats
    s = val[:10]
    try:
        return date.fromisoformat(s)
    except (ValueError, TypeError):
        return None
```

- [ ] **Step 4: Implement TariffSnapshot**

```python
# services/logistics_audit/models/tariff_snapshot.py
from __future__ import annotations
from dataclasses import dataclass


@dataclass(slots=True)
class TariffSnapshot:
    """Warehouse tariff snapshot from /api/v1/tariffs/box."""
    warehouse_name: str
    box_delivery_base: float
    box_delivery_liter: float
    delivery_coef_pct: int
    box_storage_base: float
    box_storage_liter: float
    storage_coef_pct: int
    geo_name: str = ""

    @classmethod
    def from_api(cls, d: dict) -> TariffSnapshot:
        return cls(
            warehouse_name=d.get("warehouseName", ""),
            box_delivery_base=_parse_ru_decimal(d.get("boxDeliveryBase", "0")),
            box_delivery_liter=_parse_ru_decimal(d.get("boxDeliveryLiter", "0")),
            delivery_coef_pct=int(_parse_ru_decimal(d.get("boxDeliveryCoefExpr", "0"))),
            box_storage_base=_parse_ru_decimal(d.get("boxStorageBase", "0")),
            box_storage_liter=_parse_ru_decimal(d.get("boxStorageLiter", "0")),
            storage_coef_pct=int(_parse_ru_decimal(d.get("boxStorageCoefExpr", "0"))),
            geo_name=d.get("geoName", ""),
        )


def _parse_ru_decimal(val: str) -> float:
    """Parse Russian decimal format: '89,7' → 89.7, '-' → 0.0, '1 046' → 1046.0"""
    if not val or val == "-":
        return 0.0
    return float(val.replace(",", ".").replace(" ", "").replace("\xa0", ""))
```

- [ ] **Step 5: Implement AuditConfig + __init__ files**

```python
# services/logistics_audit/models/audit_config.py
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
    base_tariff_1l: float = 46.0
    base_tariff_extra_l: float = 14.0
```

Create empty `__init__.py` files:
- `services/logistics_audit/__init__.py`
- `services/logistics_audit/models/__init__.py`
- `tests/services/__init__.py` (if not exists)
- `tests/services/logistics_audit/__init__.py`

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/services/logistics_audit/test_models.py -v
```

Expected: all 5 tests PASS

- [ ] **Step 7: Commit**

```bash
git add services/logistics_audit/__init__.py services/logistics_audit/models/ tests/services/logistics_audit/
git commit -m "feat(logistics-audit): add data models — ReportRow, TariffSnapshot, AuditConfig"
```

---

## Task 2: Tariff Calibrator — Reverse-Calculate Base Tariff

**Files:**
- Create: `services/logistics_audit/calculators/__init__.py`
- Create: `services/logistics_audit/calculators/tariff_calibrator.py`
- Test: `tests/services/logistics_audit/test_tariff_calibrator.py`

**Context:** The WB API returns current tariffs (46₽/14₽), but actual charges for ≤1L items use ~33₽. The calibrator reverse-calculates the effective base from real data: `base_ktr = median(delivery_rub / dlv_prc)` for ≤1L rows.

- [ ] **Step 1: Write failing tests**

```python
# tests/services/logistics_audit/test_tariff_calibrator.py
from services.logistics_audit.calculators.tariff_calibrator import calibrate_base_tariff


def test_calibrate_with_sub1l_rows():
    """Reverse-calc from ≤1L rows: base*KTR ≈ delivery_rub / dlv_prc."""
    rows = [
        {"delivery_rub": 52.65, "dlv_prc": 1.6, "volume": 0.9},   # 52.65/1.6 = 32.91
        {"delivery_rub": 64.35, "dlv_prc": 1.95, "volume": 0.9},  # 64.35/1.95 = 33.0
        {"delivery_rub": 39.6, "dlv_prc": 1.2, "volume": 0.672},  # 39.6/1.2 = 33.0
    ]
    result = calibrate_base_tariff(rows)
    assert result is not None
    assert 32.9 <= result <= 33.1  # median ≈ 33.0


def test_calibrate_skips_zero_dlv_prc():
    """Rows with dlv_prc=0 are not logistics and must be skipped."""
    rows = [
        {"delivery_rub": 50.0, "dlv_prc": 0, "volume": 0.9},
        {"delivery_rub": 52.65, "dlv_prc": 1.6, "volume": 0.9},
    ]
    result = calibrate_base_tariff(rows)
    assert result is not None
    assert abs(result - 32.91) < 0.1


def test_calibrate_skips_above_1l():
    """Only ≤1L rows are used for calibration (formula = base * coef * ktr)."""
    rows = [
        {"delivery_rub": 52.65, "dlv_prc": 1.6, "volume": 0.9},   # ≤1L, used
        {"delivery_rub": 147.23, "dlv_prc": 1.95, "volume": 2.904}, # >1L, skipped
    ]
    result = calibrate_base_tariff(rows)
    assert result is not None
    assert abs(result - 32.91) < 0.1


def test_calibrate_no_valid_rows():
    """If no ≤1L rows with dlv_prc>0, return None."""
    rows = [
        {"delivery_rub": 147.23, "dlv_prc": 1.95, "volume": 2.904},
    ]
    result = calibrate_base_tariff(rows)
    assert result is None


def test_calibrate_empty():
    assert calibrate_base_tariff([]) is None
```

- [ ] **Step 2: Run tests — verify FAIL**

```bash
pytest tests/services/logistics_audit/test_tariff_calibrator.py -v
```

- [ ] **Step 3: Implement tariff_calibrator.py**

```python
# services/logistics_audit/calculators/tariff_calibrator.py
from __future__ import annotations
import statistics


def calibrate_base_tariff(rows: list[dict]) -> float | None:
    """
    Reverse-calculate base tariff * KTR from logistics rows with volume ≤ 1L.

    For ≤1L items: delivery_rub = base * dlv_prc * KTR
    So: base * KTR = delivery_rub / dlv_prc

    Returns median(delivery_rub / dlv_prc) across all valid ≤1L rows,
    or None if no valid rows exist.
    """
    bases = []
    for r in rows:
        vol = r.get("volume", 0)
        dlv = r.get("dlv_prc", 0)
        delivery = r.get("delivery_rub", 0)
        if 0 < vol <= 1 and dlv > 0 and delivery > 0:
            bases.append(delivery / dlv)
    if not bases:
        return None
    return statistics.median(bases)
```

- [ ] **Step 4: Run tests — verify PASS**

```bash
pytest tests/services/logistics_audit/test_tariff_calibrator.py -v
```

- [ ] **Step 5: Commit**

```bash
git add services/logistics_audit/calculators/ tests/services/logistics_audit/test_tariff_calibrator.py
git commit -m "feat(logistics-audit): tariff calibrator — reverse-calc base from ≤1L rows"
```

---

## Task 3: Logistics Overpayment Calculator (Dual Formula)

**Files:**
- Create: `services/logistics_audit/calculators/logistics_overpayment.py`
- Test: `tests/services/logistics_audit/test_overpayment.py`

**Context:** Core business logic. TWO formulas depending on order date:
- **Before 23.03.2026 (old):** `base_cost * coef * ktr_manual`
- **From 23.03.2026 (new):** `base_cost * coef * IL + price * IRP%`
  - IL (= КТР) and IRP (= КРП%) come from `services/wb_localization/irp_coefficients.get_ktr_krp(localization_pct)`
- Fixed-rate rows (50₽): excluded, overpayment = 0
- `coef == 0`: skipped

- [ ] **Step 1: Write failing tests with real data from spec**

```python
# tests/services/logistics_audit/test_overpayment.py
import pytest
from datetime import date
from services.logistics_audit.calculators.logistics_overpayment import (
    calculate_row_overpayment,
    OverpaymentResult,
    FORMULA_CHANGE_DATE,
)


def test_old_formula_above_1l_wookiee():
    """Before 23.03: nm_id=257131227, Коледино, volume=2.904L, KTR=1.04."""
    result = calculate_row_overpayment(
        delivery_rub=147.23,
        volume=2.904,
        coef=1.95,
        base_1l=46.0,
        extra_l=14.0,
        order_dt=date(2026, 2, 28),  # Before 23.03
        ktr_manual=1.04,
        is_fixed_rate=False,
    )
    # (46 + (2.904-1)*14) * 1.95 * 1.04 = 72.656 * 1.95 * 1.04 = 147.35
    assert result.calculated_cost == pytest.approx(147.35, abs=0.1)


def test_old_formula_below_1l_fisanov():
    """Before 23.03: nm_id=169516610, volume=0.98L, base=32₽, KTR=1.37."""
    result = calculate_row_overpayment(
        delivery_rub=268.93,
        volume=0.98,
        coef=2.0,
        base_1l=32.0,
        extra_l=14.0,
        order_dt=date(2026, 1, 15),
        ktr_manual=1.37,
        is_fixed_rate=False,
    )
    # 32 * 2 * 1.37 = 87.68
    assert result.calculated_cost == pytest.approx(87.68, abs=0.01)
    assert result.overpayment == pytest.approx(268.93 - 87.68, abs=0.01)


def test_new_formula_high_localization():
    """From 23.03: SKU with 80% localization → IL=0.80, IRP=0%."""
    result = calculate_row_overpayment(
        delivery_rub=100.0,
        volume=2.0,
        coef=1.5,
        base_1l=46.0,
        extra_l=14.0,
        order_dt=date(2026, 3, 25),  # After 23.03
        ktr_manual=1.04,  # ignored for new formula
        is_fixed_rate=False,
        sku_localization_pct=80.0,
        retail_price=1000.0,
    )
    # IL=0.80, IRP=0.00
    # base_cost = (46 + (2.0-1)*14) * 1.5 = 60 * 1.5 = 90
    # cost = 90 * 0.80 + 1000 * 0.00 = 72.0
    assert result.calculated_cost == pytest.approx(72.0, abs=0.1)


def test_new_formula_low_localization_irp():
    """From 23.03: SKU with 30% localization → IL=1.60, IRP=2.15%."""
    result = calculate_row_overpayment(
        delivery_rub=200.0,
        volume=0.9,
        coef=1.5,
        base_1l=46.0,
        extra_l=14.0,
        order_dt=date(2026, 3, 25),
        ktr_manual=1.04,
        is_fixed_rate=False,
        sku_localization_pct=30.0,
        retail_price=2000.0,
    )
    # IL=1.60, IRP=2.15%
    # base_cost = 46 * 1.5 = 69
    # cost = 69 * 1.60 + 2000 * 0.0215 = 110.4 + 43.0 = 153.4
    assert result.calculated_cost == pytest.approx(153.4, abs=0.5)


def test_fixed_rate_excluded():
    """Fixed-rate rows (50₽ return) have 0 overpayment."""
    result = calculate_row_overpayment(
        delivery_rub=50.0, volume=0.9, coef=1.6,
        base_1l=33.0, extra_l=14.0,
        order_dt=date(2026, 3, 1),
        ktr_manual=1.04, is_fixed_rate=True,
    )
    assert result.calculated_cost == 50.0
    assert result.overpayment == 0.0


def test_zero_coef_skipped():
    """Rows with coef=0 are not logistics — skip."""
    result = calculate_row_overpayment(
        delivery_rub=100.0, volume=0.9, coef=0.0,
        base_1l=33.0, extra_l=14.0,
        order_dt=date(2026, 3, 1),
        ktr_manual=1.04, is_fixed_rate=False,
    )
    assert result is None
```

- [ ] **Step 2: Run tests — verify FAIL**

```bash
pytest tests/services/logistics_audit/test_overpayment.py -v
```

- [ ] **Step 3: Implement logistics_overpayment.py (dual formula)**

```python
# services/logistics_audit/calculators/logistics_overpayment.py
from __future__ import annotations
from dataclasses import dataclass
from datetime import date

FORMULA_CHANGE_DATE = date(2026, 3, 23)


@dataclass(slots=True)
class OverpaymentResult:
    calculated_cost: float
    overpayment: float


def calculate_row_overpayment(
    delivery_rub: float,
    volume: float,
    coef: float,
    base_1l: float,
    extra_l: float,
    order_dt: date | None,
    ktr_manual: float,
    is_fixed_rate: bool,
    sku_localization_pct: float | None = None,
    retail_price: float = 0.0,
) -> OverpaymentResult | None:
    """
    Calculate overpayment for a single logistics row.

    Uses old formula (KTR) before 23.03.2026,
    new formula (IL + IRP) from 23.03.2026.
    Returns None if coef == 0 and not fixed_rate.
    """
    if is_fixed_rate:
        return OverpaymentResult(calculated_cost=delivery_rub, overpayment=0.0)

    if coef == 0:
        return None

    # Base logistics cost (before multipliers)
    if volume > 1:
        base_cost = (base_1l + (volume - 1) * extra_l) * coef
    else:
        base_cost = base_1l * coef

    use_new_formula = order_dt and order_dt >= FORMULA_CHANGE_DATE

    if use_new_formula and sku_localization_pct is not None:
        from services.wb_localization.irp_coefficients import get_ktr_krp
        il, irp_pct = get_ktr_krp(sku_localization_pct)
        cost = base_cost * il + retail_price * (irp_pct / 100)
    else:
        # Old formula or no localization data → use manual KTR
        cost = base_cost * ktr_manual

    cost = round(cost, 2)
    return OverpaymentResult(
        calculated_cost=cost,
        overpayment=round(delivery_rub - cost, 2),
    )
```

- [ ] **Step 4: Run tests — verify PASS**

```bash
pytest tests/services/logistics_audit/test_overpayment.py -v
```

- [ ] **Step 5: Commit**

```bash
git add services/logistics_audit/calculators/logistics_overpayment.py tests/services/logistics_audit/test_overpayment.py
git commit -m "feat(logistics-audit): dual-formula overpayment calculator (KTR before 23.03, IL+IRP after)"
```

---

## Task 3b: Localization Resolver — Per-SKU Localization %

**Files:**
- Create: `services/logistics_audit/calculators/localization_resolver.py`
- Test: `tests/services/logistics_audit/test_localization_resolver.py`

**Context:** For the new formula (from 23.03.2026), we need per-SKU localization percentage. This is calculated from WB supplier/orders API: `local_orders / total_orders * 100`. An order is "local" if the warehouse federal district matches the delivery federal district. Reuses mappings from `services/wb_localization/wb_localization_mappings.py`.

- [ ] **Step 1: Write failing tests**

```python
# tests/services/logistics_audit/test_localization_resolver.py
from services.logistics_audit.calculators.localization_resolver import (
    calculate_sku_localization,
)


def test_high_localization():
    """Most orders delivered locally → high localization."""
    orders = [
        {"nmId": 123, "warehouseName": "Коледино", "oblastOkrugName": "Московская область"},
        {"nmId": 123, "warehouseName": "Коледино", "oblastOkrugName": "Московская область"},
        {"nmId": 123, "warehouseName": "Коледино", "oblastOkrugName": "Краснодарский край"},
    ]
    result = calculate_sku_localization(orders)
    # 2 local out of 3 = 66.7%
    assert 123 in result
    assert 60 < result[123] < 70


def test_low_localization():
    """Most orders cross-region → low localization."""
    orders = [
        {"nmId": 456, "warehouseName": "Коледино", "oblastOkrugName": "Новосибирская область"},
        {"nmId": 456, "warehouseName": "Коледино", "oblastOkrugName": "Свердловская область"},
        {"nmId": 456, "warehouseName": "Коледино", "oblastOkrugName": "Московская область"},
    ]
    result = calculate_sku_localization(orders)
    assert result[456] < 40  # Only 1 out of 3 local


def test_empty_orders():
    result = calculate_sku_localization([])
    assert result == {}
```

- [ ] **Step 2: Run tests — verify FAIL**

- [ ] **Step 3: Implement localization_resolver.py**

```python
# services/logistics_audit/calculators/localization_resolver.py
from __future__ import annotations
from collections import defaultdict
from services.wb_localization.wb_localization_mappings import (
    WAREHOUSE_TO_FD,
    OBLAST_TO_FD,
)


def calculate_sku_localization(orders: list[dict]) -> dict[int, float]:
    """
    Calculate per-SKU localization % from WB orders.

    An order is "local" if the warehouse's federal district matches
    the delivery oblast's federal district.

    Returns: {nm_id: localization_pct}
    """
    sku_local: dict[int, int] = defaultdict(int)
    sku_total: dict[int, int] = defaultdict(int)

    for order in orders:
        nm_id = order.get("nmId", 0)
        if not nm_id:
            continue

        wh_name = order.get("warehouseName", "")
        oblast = order.get("oblastOkrugName", "")

        wh_fd = WAREHOUSE_TO_FD.get(wh_name, "")
        delivery_fd = OBLAST_TO_FD.get(oblast, "")

        if not wh_fd or not delivery_fd:
            continue

        sku_total[nm_id] += 1
        if wh_fd == delivery_fd:
            sku_local[nm_id] += 1

    result = {}
    for nm_id, total in sku_total.items():
        if total > 0:
            result[nm_id] = round(sku_local[nm_id] / total * 100, 2)
    return result
```

- [ ] **Step 4: Run tests — verify PASS**

- [ ] **Step 5: Commit**

```bash
git add services/logistics_audit/calculators/localization_resolver.py tests/services/logistics_audit/test_localization_resolver.py
git commit -m "feat(logistics-audit): per-SKU localization resolver from WB orders"
```

---

## Task 4: Dimensions Checker

**Files:**
- Create: `services/logistics_audit/calculators/dimensions_checker.py`
- Test: `tests/services/logistics_audit/test_dimensions_checker.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/services/logistics_audit/test_dimensions_checker.py
from services.logistics_audit.calculators.dimensions_checker import (
    check_dimensions,
    DimensionResult,
)


def test_no_discrepancy():
    """Volumes within 10% — no flag."""
    card_dims = {257131227: 2.904}
    wb_volumes = {257131227: 2.90}
    results = check_dimensions(card_dims, wb_volumes)
    assert len(results) == 1
    assert results[257131227].flagged is False


def test_discrepancy_above_10pct():
    """WB measured 20% more — flag it."""
    card_dims = {123: 0.9}
    wb_volumes = {123: 1.1}
    results = check_dimensions(card_dims, wb_volumes)
    assert results[123].flagged is True
    assert results[123].pct_diff > 10


def test_missing_wb_volume():
    """If WB didn't measure, no result for that nm_id."""
    card_dims = {123: 0.9}
    wb_volumes = {}
    results = check_dimensions(card_dims, wb_volumes)
    assert 123 not in results
```

- [ ] **Step 2: Run tests — verify FAIL**

- [ ] **Step 3: Implement dimensions_checker.py**

```python
# services/logistics_audit/calculators/dimensions_checker.py
from __future__ import annotations
from dataclasses import dataclass


@dataclass(slots=True)
class DimensionResult:
    nm_id: int
    card_volume: float
    wb_volume: float
    pct_diff: float
    flagged: bool


def check_dimensions(
    card_dims: dict[int, float],
    wb_volumes: dict[int, float],
    threshold_pct: float = 10.0,
) -> dict[int, DimensionResult]:
    """Compare card dimensions vs WB measured volume. Flag if difference > threshold."""
    results = {}
    for nm_id, card_vol in card_dims.items():
        wb_vol = wb_volumes.get(nm_id)
        if wb_vol is None or card_vol == 0:
            continue
        pct = abs(wb_vol - card_vol) / card_vol * 100
        results[nm_id] = DimensionResult(
            nm_id=nm_id,
            card_volume=card_vol,
            wb_volume=wb_vol,
            pct_diff=round(pct, 2),
            flagged=pct > threshold_pct,
        )
    return results
```

- [ ] **Step 4: Run tests — verify PASS**

- [ ] **Step 5: Commit**

```bash
git add services/logistics_audit/calculators/dimensions_checker.py tests/services/logistics_audit/test_dimensions_checker.py
git commit -m "feat(logistics-audit): dimensions checker — card vs WB volume comparison"
```

---

## Task 5: API Client — reportDetailByPeriod v5

**Files:**
- Create: `services/logistics_audit/api/__init__.py`
- Create: `services/logistics_audit/api/wb_reports.py`
- Test: `tests/services/logistics_audit/test_api_parsing.py`

**Context:** Paginated by `rrd_id`. Rate limit: 1 req/min. Max 100K rows per request. Must handle empty responses (end of pagination). Existing pattern in `services/marketplace_etl/api_clients/wb_client.py` uses exponential backoff + 429 handling.

- [ ] **Step 1: Write tests for response parsing (no network)**

```python
# tests/services/logistics_audit/test_api_parsing.py
from services.logistics_audit.api.wb_reports import parse_report_rows
from services.logistics_audit.models.report_row import ReportRow


def test_parse_report_rows():
    """Parse raw API response into list of ReportRow."""
    raw_data = [
        {
            "realizationreport_id": 658038623,
            "nm_id": 257131227,
            "office_name": "Коледино",
            "supplier_oper_name": "Логистика",
            "bonus_type_name": "К клиенту при продаже",
            "delivery_rub": 147.23,
            "dlv_prc": 1.95,
            "fix_tariff_date_from": "2025-12-11",
            "fix_tariff_date_to": "2026-02-09",
            "order_dt": "2026-02-28T00:00:00",
            "shk_id": 41793344171,
            "srid": "20966880121115600.0.0",
            "rrd_id": 999,
        },
    ]
    rows, last_rrd_id = parse_report_rows(raw_data)
    assert len(rows) == 1
    assert isinstance(rows[0], ReportRow)
    assert rows[0].nm_id == 257131227
    assert last_rrd_id == 999


def test_parse_empty_response():
    """Empty response → no rows, last_rrd_id = 0."""
    rows, last_rrd_id = parse_report_rows([])
    assert len(rows) == 0
    assert last_rrd_id == 0
```

- [ ] **Step 2: Run tests — verify FAIL**

- [ ] **Step 3: Implement wb_reports.py**

```python
# services/logistics_audit/api/wb_reports.py
from __future__ import annotations
import logging
import time
import httpx
from services.logistics_audit.models.report_row import ReportRow

logger = logging.getLogger(__name__)

BASE_URL = "https://statistics-api.wildberries.ru/api/v5/supplier/reportDetailByPeriod"
RATE_LIMIT_SEC = 62  # 1 req/min with buffer


def parse_report_rows(raw_data: list[dict]) -> tuple[list[ReportRow], int]:
    """Parse raw API JSON into ReportRow list. Returns (rows, last_rrd_id)."""
    if not raw_data:
        return [], 0
    rows = [ReportRow.from_api(d) for d in raw_data]
    last_rrd_id = raw_data[-1].get("rrd_id", 0)
    return rows, last_rrd_id


def fetch_report(
    api_key: str,
    date_from: str,
    date_to: str,
    timeout: float = 120.0,
) -> list[ReportRow]:
    """
    Fetch all pages of reportDetailByPeriod v5.
    Paginates by rrd_id until empty response.
    """
    all_rows: list[ReportRow] = []
    rrd_id = 0
    page = 0

    with httpx.Client(timeout=timeout) as client:
        while True:
            page += 1
            logger.info(f"Fetching report page {page}, rrd_id={rrd_id}")
            resp = client.get(
                BASE_URL,
                params={
                    "dateFrom": date_from,
                    "dateTo": date_to,
                    "limit": 100000,
                    "rrdid": rrd_id,
                },
                headers={"Authorization": api_key},
            )

            if resp.status_code == 429:
                logger.warning("Rate limited, sleeping 60s")
                time.sleep(60)
                continue

            resp.raise_for_status()
            data = resp.json()

            if not data:
                logger.info(f"Report complete: {len(all_rows)} total rows")
                break

            rows, rrd_id = parse_report_rows(data)
            all_rows.extend(rows)
            logger.info(f"Page {page}: {len(rows)} rows, rrd_id={rrd_id}")

            if len(data) < 100000:
                break

            time.sleep(RATE_LIMIT_SEC)

    return all_rows
```

- [ ] **Step 4: Run tests — verify PASS**

```bash
pytest tests/services/logistics_audit/test_api_parsing.py -v
```

- [ ] **Step 5: Commit**

```bash
git add services/logistics_audit/api/ tests/services/logistics_audit/test_api_parsing.py
git commit -m "feat(logistics-audit): reportDetailByPeriod v5 client with rrd_id pagination"
```

---

## Task 6: API Client — Tariffs

**Files:**
- Create: `services/logistics_audit/api/wb_tariffs.py`

- [ ] **Step 1: Write test for tariff parsing**

Add to `tests/services/logistics_audit/test_api_parsing.py`:

```python
from services.logistics_audit.api.wb_tariffs import parse_tariff_response


def test_parse_tariff_response():
    raw = {
        "response": {
            "data": {
                "dtNextBox": "",
                "dtTillMax": "2026-03-26",
                "warehouseList": [
                    {
                        "warehouseName": "Коледино",
                        "boxDeliveryBase": "89,7",
                        "boxDeliveryLiter": "27,3",
                        "boxDeliveryCoefExpr": "195",
                        "boxStorageBase": "0,1",
                        "boxStorageCoefExpr": "145",
                        "boxStorageLiter": "0,1",
                        "geoName": "ЦФО",
                    },
                ],
            }
        }
    }
    tariffs = parse_tariff_response(raw)
    assert len(tariffs) == 1
    assert tariffs["Коледино"].box_delivery_base == 89.7
    assert tariffs["Коледино"].delivery_coef_pct == 195
```

- [ ] **Step 2: Run test — verify FAIL**

- [ ] **Step 3: Implement wb_tariffs.py**

```python
# services/logistics_audit/api/wb_tariffs.py
from __future__ import annotations
import logging
import httpx
from services.logistics_audit.models.tariff_snapshot import TariffSnapshot

logger = logging.getLogger(__name__)

BOX_URL = "https://common-api.wildberries.ru/api/v1/tariffs/box"
PALLET_URL = "https://common-api.wildberries.ru/api/v1/tariffs/pallet"


def parse_tariff_response(raw: dict) -> dict[str, TariffSnapshot]:
    """Parse tariffs/box API response into dict keyed by warehouse name."""
    warehouses = raw.get("response", {}).get("data", {}).get("warehouseList", [])
    result = {}
    for wh in warehouses:
        snap = TariffSnapshot.from_api(wh)
        result[snap.warehouse_name] = snap
    return result


def fetch_tariffs_box(api_key: str, date: str, timeout: float = 30.0) -> dict[str, TariffSnapshot]:
    """Fetch box tariffs for a specific date."""
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(
            BOX_URL,
            params={"date": date},
            headers={"Authorization": api_key},
        )
        resp.raise_for_status()
        return parse_tariff_response(resp.json())


def fetch_tariffs_pallet(api_key: str, date: str, timeout: float = 30.0) -> dict:
    """Fetch pallet tariffs for a specific date. Returns raw parsed JSON."""
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(
            PALLET_URL,
            params={"date": date},
            headers={"Authorization": api_key},
        )
        resp.raise_for_status()
        return resp.json()
```

- [ ] **Step 4: Run tests — verify PASS**

- [ ] **Step 5: Commit**

```bash
git add services/logistics_audit/api/wb_tariffs.py tests/services/logistics_audit/test_api_parsing.py
git commit -m "feat(logistics-audit): tariffs/box + tariffs/pallet API clients"
```

---

## Task 7: API Client — Content Cards (Dimensions)

**Files:**
- Create: `services/logistics_audit/api/wb_content.py`

- [ ] **Step 1: Write test for card dimension parsing**

Add to `tests/services/logistics_audit/test_api_parsing.py`:

```python
from services.logistics_audit.api.wb_content import parse_cards_dimensions


def test_parse_cards_dimensions():
    raw_cards = [
        {
            "nmID": 257131227,
            "dimensions": {"width": 33, "height": 22, "length": 4},
        },
        {
            "nmID": 545069116,
            "dimensions": {"width": 15, "height": 20, "length": 3},
        },
    ]
    dims = parse_cards_dimensions(raw_cards)
    assert dims[257131227] == {"width": 33, "height": 22, "length": 4, "volume": 2.904}
    assert abs(dims[545069116]["volume"] - 0.9) < 0.001
```

- [ ] **Step 2: Run test — verify FAIL**

- [ ] **Step 3: Implement wb_content.py**

```python
# services/logistics_audit/api/wb_content.py
from __future__ import annotations
import logging
import time
import httpx

logger = logging.getLogger(__name__)

CARDS_URL = "https://content-api.wildberries.ru/content/v2/get/cards/list"


def parse_cards_dimensions(cards: list[dict]) -> dict[int, dict]:
    """Extract nm_id → {width, height, length, volume} from card list."""
    result = {}
    for card in cards:
        nm_id = card.get("nmID", 0)
        dims = card.get("dimensions", {})
        w = dims.get("width", 0)
        h = dims.get("height", 0)
        l = dims.get("length", 0)
        volume = round(w * h * l / 1000, 3)  # cm³ → liters
        result[nm_id] = {"width": w, "height": h, "length": l, "volume": volume}
    return result


def fetch_all_cards(api_key: str, timeout: float = 30.0) -> dict[int, dict]:
    """Fetch all content cards with dimensions. Cursor-based pagination."""
    all_dims: dict[int, dict] = {}
    cursor = {"limit": 100, "updatedAt": None, "nmID": None}

    with httpx.Client(timeout=timeout) as client:
        while True:
            body: dict = {
                "settings": {
                    "cursor": {"limit": cursor["limit"]},
                    "filter": {"withPhoto": -1},
                },
            }
            if cursor["updatedAt"]:
                body["settings"]["cursor"]["updatedAt"] = cursor["updatedAt"]
                body["settings"]["cursor"]["nmID"] = cursor["nmID"]

            resp = client.post(
                CARDS_URL,
                json=body,
                headers={"Authorization": api_key},
            )

            if resp.status_code == 429:
                time.sleep(5)
                continue

            resp.raise_for_status()
            data = resp.json()
            cards = data.get("cards", [])
            if not cards:
                break

            dims = parse_cards_dimensions(cards)
            all_dims.update(dims)
            logger.info(f"Fetched {len(cards)} cards, total {len(all_dims)}")

            cur = data.get("cursor", {})
            cursor["updatedAt"] = cur.get("updatedAt")
            cursor["nmID"] = cur.get("nmID")

            if len(cards) < 100:
                break
            time.sleep(0.5)

    return all_dims
```

- [ ] **Step 4: Run tests — verify PASS**

- [ ] **Step 5: Commit**

```bash
git add services/logistics_audit/api/wb_content.py tests/services/logistics_audit/test_api_parsing.py
git commit -m "feat(logistics-audit): Content API client — card dimensions with cursor pagination"
```

---

## Task 8: API Client — Warehouse Remains + Penalties

**Files:**
- Create: `services/logistics_audit/api/wb_warehouse_remains.py`
- Create: `services/logistics_audit/api/wb_penalties.py`

**Context:** Both use async report pattern from `shared/clients/wb_client.py`: create task → poll status → download. Rate limit: 1 req/min on seller-analytics-api.

- [ ] **Step 1: Implement wb_warehouse_remains.py**

```python
# services/logistics_audit/api/wb_warehouse_remains.py
from __future__ import annotations
import logging
import time
import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://seller-analytics-api.wildberries.ru/api/v1/warehouse_remains"


def fetch_warehouse_remains(api_key: str, timeout: float = 120.0) -> dict[int, float]:
    """
    Fetch warehouse remains with WB-measured volumes.
    Async pattern: create task → poll → download.
    Returns dict nm_id → volume (liters).
    """
    with httpx.Client(timeout=timeout) as client:
        # Step 1: Create task
        resp = client.get(
            BASE_URL,
            params={"groupByNm": "true"},
            headers={"Authorization": api_key},
        )
        resp.raise_for_status()
        data = resp.json()
        task_id = data.get("data", {}).get("taskId")
        if not task_id:
            logger.error("No taskId in response")
            return {}

        logger.info(f"Warehouse remains task created: {task_id}")
        time.sleep(10)

        # Step 2: Poll status
        for attempt in range(100):
            resp = client.get(
                f"{BASE_URL}/tasks/{task_id}/status",
                headers={"Authorization": api_key},
            )
            resp.raise_for_status()
            status = resp.json().get("data", {}).get("status")
            if status == "done":
                break
            logger.info(f"Poll {attempt}: status={status}")
            time.sleep(15)
        else:
            logger.error("Timeout waiting for warehouse_remains")
            return {}

        time.sleep(10)

        # Step 3: Download
        resp = client.get(
            f"{BASE_URL}/tasks/{task_id}/download",
            headers={"Authorization": api_key},
        )
        resp.raise_for_status()
        items = resp.json()

        nm_volumes: dict[int, float] = {}
        for item in items:
            nm_id = item.get("nmId", 0)
            vol = item.get("volume", 0)
            if nm_id and vol:
                nm_volumes[nm_id] = vol

        logger.info(f"Got {len(nm_volumes)} items with volumes")
        return nm_volumes
```

- [ ] **Step 2: Implement wb_penalties.py**

```python
# services/logistics_audit/api/wb_penalties.py
from __future__ import annotations
import logging
import time
import httpx

logger = logging.getLogger(__name__)

ANALYTICS_BASE = "https://seller-analytics-api.wildberries.ru/api"


def fetch_measurement_penalties(
    api_key: str, date_to: str, timeout: float = 30.0,
) -> list[dict]:
    """Fetch measurement penalties. date_to in RFC3339: '2026-03-25T23:59:59Z'."""
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(
            f"{ANALYTICS_BASE}/analytics/v1/measurement-penalties",
            params={"dateTo": date_to, "limit": 1000},
            headers={"Authorization": api_key},
        )
        resp.raise_for_status()
        return resp.json().get("data", [])


def fetch_deductions(
    api_key: str, date_to: str, timeout: float = 30.0,
) -> list[dict]:
    """Fetch deductions (substitutions, incorrect items)."""
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(
            f"{ANALYTICS_BASE}/analytics/v1/deductions",
            params={"dateTo": date_to, "limit": 1000, "sort": "dtBonus", "order": "desc"},
            headers={"Authorization": api_key},
        )
        resp.raise_for_status()
        return resp.json().get("data", [])


def fetch_antifraud(api_key: str, timeout: float = 30.0) -> list[dict]:
    """Fetch antifraud details."""
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(
            f"{ANALYTICS_BASE}/v1/analytics/antifraud-details",
            headers={"Authorization": api_key},
        )
        resp.raise_for_status()
        return resp.json().get("data", [])
```

- [ ] **Step 3: Commit**

```bash
git add services/logistics_audit/api/wb_warehouse_remains.py services/logistics_audit/api/wb_penalties.py
git commit -m "feat(logistics-audit): warehouse remains + penalties API clients"
```

---

## Task 9: Excel Generator — Sheets 1-3 (Core Overpayment)

**Files:**
- Create: `services/logistics_audit/output/__init__.py`
- Create: `services/logistics_audit/output/excel_generator.py`
- Create: `services/logistics_audit/output/sheet_overpayment_formulas.py`
- Create: `services/logistics_audit/output/sheet_overpayment_values.py`
- Create: `services/logistics_audit/output/sheet_svod.py`
- Test: `tests/services/logistics_audit/test_excel_sheets.py`

**Context:** Uses openpyxl. Sheet 1 has live Excel formulas (VLOOKUP, IF). Sheet 2 has pre-calculated values. Sheet 3 aggregates by report ID. See spec section 7.

- [ ] **Step 1: Write test for sheet 1 (formula sheet)**

```python
# tests/services/logistics_audit/test_excel_sheets.py
import openpyxl
from io import BytesIO
from services.logistics_audit.output.sheet_overpayment_formulas import write_overpayment_formulas
from services.logistics_audit.models.report_row import ReportRow


def _make_row(**overrides) -> ReportRow:
    defaults = dict(
        realizationreport_id=658038623, nm_id=257131227,
        office_name="Коледино", supplier_oper_name="Логистика",
        bonus_type_name="К клиенту при продаже", delivery_rub=147.23,
        dlv_prc=1.95, fix_tariff_date_from=None, fix_tariff_date_to=None,
        order_dt=None, shk_id=41793344171, srid="20966880121115600.0.0",
        gi_id=12345, gi_box_type_name="Микс", storage_fee=0, penalty=0,
        deduction=0, rebill_logistic_cost=0, ppvz_for_pay=0,
        ppvz_supplier_name="", retail_amount=0, date_from="", date_to="",
        doc_type_name="", acceptance=0,
    )
    defaults.update(overrides)
    return ReportRow(**defaults)


def test_sheet_overpayment_formulas_header():
    """Sheet 1 has correct header columns."""
    wb = openpyxl.Workbook()
    ws = wb.active
    rows = [_make_row()]
    write_overpayment_formulas(ws, rows, ktr=1.04, base_1l=46.0, extra_l=14.0)
    headers = [ws.cell(1, c).value for c in range(1, 20)]
    assert "Код номенклатуры" in headers
    assert "Услуги по доставке" in headers
    assert "Разница" in headers


def test_sheet_overpayment_formulas_has_formula():
    """Column R (стоимость логистики) must contain an Excel formula."""
    wb = openpyxl.Workbook()
    ws = wb.active
    rows = [_make_row()]
    write_overpayment_formulas(ws, rows, ktr=1.04, base_1l=46.0, extra_l=14.0)
    # Row 2 is first data row
    formula_cell = ws.cell(2, 18).value  # R = column 18
    assert formula_cell is not None
    assert str(formula_cell).startswith("=")
```

- [ ] **Step 2: Run tests — verify FAIL**

- [ ] **Step 3: Implement sheet_overpayment_formulas.py**

```python
# services/logistics_audit/output/sheet_overpayment_formulas.py
"""Sheet 1: 'Переплата по логистике (короб)' — with live Excel formulas."""
from __future__ import annotations
import openpyxl
from openpyxl.worksheet.worksheet import Worksheet
from services.logistics_audit.models.report_row import ReportRow

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
]


def write_overpayment_formulas(
    ws: Worksheet,
    rows: list[ReportRow],
    ktr: float,
    base_1l: float,
    extra_l: float,
) -> None:
    """Write Sheet 1 with live Excel formulas."""
    # Header
    for col, h in enumerate(HEADERS, 1):
        ws.cell(1, col, h)

    for i, row in enumerate(rows, 2):
        ws.cell(i, 1, row.gi_id)
        ws.cell(i, 2, row.nm_id)
        ws.cell(i, 3, str(row.order_dt) if row.order_dt else "")
        # D is unused
        ws.cell(i, 5, row.delivery_rub)
        ws.cell(i, 6, str(row.fix_tariff_date_from) if row.fix_tariff_date_from else "")
        ws.cell(i, 7, str(row.fix_tariff_date_to) if row.fix_tariff_date_to else "")
        ws.cell(i, 8, row.office_name)
        ws.cell(i, 9, row.shk_id)
        ws.cell(i, 10, row.srid)
        ws.cell(i, 11, row.dlv_prc)
        # L: Coefficient for calculation
        ws.cell(i, 12, f'=IF(K{i}>0,K{i},VLOOKUP(H{i},\'Тарифы короб\'!A:C,3,FALSE)/100)')
        # M: Volume from card lookup
        ws.cell(i, 13, f'=IFERROR(VLOOKUP(B{i},\'Габариты в карточке\'!A:E,5,FALSE),"")')
        # N: volume from remains (filled later by excel_generator)
        ws.cell(i, 14, "")
        ws.cell(i, 15, ktr)
        ws.cell(i, 16, base_1l)
        ws.cell(i, 17, extra_l)
        # R: logistics cost formula
        ws.cell(i, 18, f'=IF(M{i}>1,(P{i}+(M{i}-1)*Q{i})*L{i}*O{i},P{i}*L{i}*O{i})')
        # S: difference
        ws.cell(i, 19, f'=E{i}-R{i}')
```

- [ ] **Step 4: Implement sheet_overpayment_values.py**

```python
# services/logistics_audit/output/sheet_overpayment_values.py
"""Sheet 2: 'Переплата по логистике' — pre-calculated values, no formulas."""
from __future__ import annotations
from openpyxl.worksheet.worksheet import Worksheet
from services.logistics_audit.models.report_row import ReportRow
from services.logistics_audit.calculators.logistics_overpayment import OverpaymentResult

HEADERS = [
    "№ отчёта", "Номер поставки", "Код номенклатуры", "Дата заказа",
    "Услуги по доставке", "Склад", "ШК", "Srid", "Фикс. коэф.",
    "Коэф. для расчёта", "Объём", "КТР", "Расчётная стоимость",
    "Разница (переплата)",
]


def write_overpayment_values(
    ws: Worksheet,
    rows: list[ReportRow],
    results: list[OverpaymentResult | None],
    volumes: dict[int, float],
    coefs: list[float],
) -> None:
    """Write Sheet 2 with pre-calculated overpayment values."""
    for col, h in enumerate(HEADERS, 1):
        ws.cell(1, col, h)

    total_overpayment = 0.0
    for i, (row, res, coef) in enumerate(zip(rows, results, coefs), 2):
        if res is None:
            continue
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
        ws.cell(i, 12, res.calculated_cost)
        ws.cell(i, 13, res.calculated_cost)
        ws.cell(i, 14, res.overpayment)
        total_overpayment += res.overpayment

    # Summary row at top (insert after header)
    ws.insert_rows(1)
    ws.cell(1, 1, "ИТОГО переплата:")
    ws.cell(1, 14, round(total_overpayment, 2))
```

- [ ] **Step 5: Implement sheet_svod.py**

```python
# services/logistics_audit/output/sheet_svod.py
"""Sheet 3: 'СВОД' — summary by realizationreport_id."""
from __future__ import annotations
from collections import defaultdict
from openpyxl.worksheet.worksheet import Worksheet
from services.logistics_audit.models.report_row import ReportRow

HEADERS = [
    "№ отчёта", "Юр. лицо", "Дата начала", "Дата конца",
    "Стоимость логистики", "Переплата", "Коррекция логистики",
    "Сторно логистики", "Расчётная стоимость",
]


def write_svod(
    ws: Worksheet,
    all_rows: list[ReportRow],
    overpayments_by_report: dict[int, float],
) -> None:
    """Write SVOD sheet: one row per realizationreport_id."""
    for col, h in enumerate(HEADERS, 1):
        ws.cell(1, col, h)

    # Aggregate by report
    reports: dict[int, dict] = {}
    for row in all_rows:
        rid = row.realizationreport_id
        if rid not in reports:
            reports[rid] = {
                "supplier_name": row.ppvz_supplier_name,
                "date_from": row.date_from,
                "date_to": row.date_to,
                "logistics": 0.0,
                "correction": 0.0,
            }
        if row.supplier_oper_name == "Логистика":
            reports[rid]["logistics"] += row.delivery_rub
        elif row.supplier_oper_name == "Коррекция логистики":
            reports[rid]["correction"] += row.delivery_rub

    for i, (rid, info) in enumerate(sorted(reports.items()), 2):
        overpay = overpayments_by_report.get(rid, 0)
        ws.cell(i, 1, rid)
        ws.cell(i, 2, info["supplier_name"])
        ws.cell(i, 3, info["date_from"])
        ws.cell(i, 4, info["date_to"])
        ws.cell(i, 5, round(info["logistics"], 2))
        ws.cell(i, 6, round(overpay, 2))
        ws.cell(i, 7, round(info["correction"], 2))
        ws.cell(i, 8, 0)  # Сторно — из данных
        ws.cell(i, 9, round(info["logistics"] - overpay + info["correction"], 2))
```

- [ ] **Step 6: Run tests — verify PASS**

```bash
pytest tests/services/logistics_audit/test_excel_sheets.py -v
```

- [ ] **Step 7: Commit**

```bash
git add services/logistics_audit/output/ tests/services/logistics_audit/test_excel_sheets.py
git commit -m "feat(logistics-audit): Excel sheets 1-3 — overpayment formulas, values, SVOD"
```

---

## Task 10: Excel Generator — Sheets 4-11 (Reference + Aggregation)

**Files:**
- Create: `services/logistics_audit/output/sheet_detail.py`
- Create: `services/logistics_audit/output/sheet_il.py`
- Create: `services/logistics_audit/output/sheet_pivot_by_article.py`
- Create: `services/logistics_audit/output/sheet_logistics_types.py`
- Create: `services/logistics_audit/output/sheet_weekly.py`
- Create: `services/logistics_audit/output/sheet_dimensions.py`
- Create: `services/logistics_audit/output/sheet_tariffs_box.py`
- Create: `services/logistics_audit/output/sheet_tariffs_pallet.py`

These sheets are simpler (mostly data dumps and GROUP BY aggregations). Implement all in one task.

- [ ] **Step 1: Implement sheet_detail.py (Sheet 4 — full 80-column dump)**

```python
# services/logistics_audit/output/sheet_detail.py
"""Sheet 4: 'Детализация' — full reportDetailByPeriod dump."""
from __future__ import annotations
from openpyxl.worksheet.worksheet import Worksheet
from services.logistics_audit.models.report_row import ReportRow


def write_detail(ws: Worksheet, rows: list[ReportRow]) -> None:
    """Write all raw fields from reportDetailByPeriod."""
    if not rows or not rows[0].raw:
        return
    columns = list(rows[0].raw.keys())
    for col, key in enumerate(columns, 1):
        ws.cell(1, col, key)
    for i, row in enumerate(rows, 2):
        if not row.raw:
            continue
        for col, key in enumerate(columns, 1):
            ws.cell(i, col, row.raw.get(key, ""))
```

- [ ] **Step 2: Implement remaining sheets (5-11)**

```python
# services/logistics_audit/output/sheet_il.py
"""Sheet 5: 'ИЛ' — localization index."""
from __future__ import annotations
from openpyxl.worksheet.worksheet import Worksheet

HEADERS = ["Дата обновления", "ИЛ", "Дата начала действия", "Дата конца действия"]

def write_il(ws: Worksheet, il_data: list[dict] | None = None) -> None:
    for col, h in enumerate(HEADERS, 1):
        ws.cell(1, col, h)
    if il_data:
        for i, entry in enumerate(il_data, 2):
            ws.cell(i, 1, entry.get("date", ""))
            ws.cell(i, 2, entry.get("il", ""))
            ws.cell(i, 3, entry.get("date_from", ""))
            ws.cell(i, 4, entry.get("date_to", ""))
```

```python
# services/logistics_audit/output/sheet_pivot_by_article.py
"""Sheet 6: 'Переплата по артикулам' — GROUP BY nm_id."""
from __future__ import annotations
from collections import defaultdict
from openpyxl.worksheet.worksheet import Worksheet
from services.logistics_audit.calculators.logistics_overpayment import OverpaymentResult
from services.logistics_audit.models.report_row import ReportRow

HEADERS = ["Код номенклатуры", "Кол-во строк", "Сумма переплаты", "Средняя переплата"]

def write_pivot_by_article(
    ws: Worksheet,
    rows: list[ReportRow],
    results: list[OverpaymentResult | None],
) -> None:
    for col, h in enumerate(HEADERS, 1):
        ws.cell(1, col, h)

    agg: dict[int, list[float]] = defaultdict(list)
    for row, res in zip(rows, results):
        if res is not None:
            agg[row.nm_id].append(res.overpayment)

    sorted_agg = sorted(agg.items(), key=lambda x: sum(x[1]), reverse=True)
    for i, (nm_id, overpays) in enumerate(sorted_agg, 2):
        total = sum(overpays)
        ws.cell(i, 1, nm_id)
        ws.cell(i, 2, len(overpays))
        ws.cell(i, 3, round(total, 2))
        ws.cell(i, 4, round(total / len(overpays), 2) if overpays else 0)
```

```python
# services/logistics_audit/output/sheet_logistics_types.py
"""Sheet 7: 'Виды логистики' — GROUP BY bonus_type_name."""
from __future__ import annotations
from collections import defaultdict
from openpyxl.worksheet.worksheet import Worksheet
from services.logistics_audit.models.report_row import ReportRow

HEADERS = ["Тип логистики", "Кол-во", "Сумма", "Средняя"]

def write_logistics_types(ws: Worksheet, rows: list[ReportRow]) -> None:
    for col, h in enumerate(HEADERS, 1):
        ws.cell(1, col, h)

    agg: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        if row.is_logistics:
            agg[row.bonus_type_name].append(row.delivery_rub)

    sorted_agg = sorted(agg.items(), key=lambda x: sum(x[1]), reverse=True)
    for i, (btype, amounts) in enumerate(sorted_agg, 2):
        total = sum(amounts)
        ws.cell(i, 1, btype)
        ws.cell(i, 2, len(amounts))
        ws.cell(i, 3, round(total, 2))
        ws.cell(i, 4, round(total / len(amounts), 2) if amounts else 0)
```

```python
# services/logistics_audit/output/sheet_weekly.py
"""Sheet 8: 'Еженед. отчет' — GROUP BY realizationreport_id."""
from __future__ import annotations
from collections import defaultdict
from openpyxl.worksheet.worksheet import Worksheet
from services.logistics_audit.models.report_row import ReportRow

HEADERS = [
    "№ отчёта", "Розничная сумма продаж", "К перечислению",
    "Логистика", "Повышенная логистика", "Штрафы",
    "Хранение", "Приёмка", "Удержания",
]

def write_weekly(ws: Worksheet, all_rows: list[ReportRow]) -> None:
    for col, h in enumerate(HEADERS, 1):
        ws.cell(1, col, h)

    agg: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in all_rows:
        rid = row.realizationreport_id
        if row.doc_type_name == "Продажа":
            agg[rid]["retail"] += row.retail_amount
        agg[rid]["ppvz"] += row.ppvz_for_pay
        agg[rid]["delivery"] += row.delivery_rub
        agg[rid]["rebill"] += row.rebill_logistic_cost
        agg[rid]["penalty"] += row.penalty
        agg[rid]["storage"] += row.storage_fee
        agg[rid]["acceptance"] += row.acceptance
        agg[rid]["deduction"] += row.deduction

    for i, (rid, vals) in enumerate(sorted(agg.items()), 2):
        ws.cell(i, 1, rid)
        ws.cell(i, 2, round(vals["retail"], 2))
        ws.cell(i, 3, round(vals["ppvz"], 2))
        ws.cell(i, 4, round(vals["delivery"], 2))
        ws.cell(i, 5, round(vals["rebill"], 2))
        ws.cell(i, 6, round(vals["penalty"], 2))
        ws.cell(i, 7, round(vals["storage"], 2))
        ws.cell(i, 8, round(vals["acceptance"], 2))
        ws.cell(i, 9, round(vals["deduction"], 2))
```

```python
# services/logistics_audit/output/sheet_dimensions.py
"""Sheet 9: 'Габариты в карточке' — card dimensions."""
from __future__ import annotations
from openpyxl.worksheet.worksheet import Worksheet

HEADERS = ["Код номенклатуры", "Ширина (см)", "Высота (см)", "Длина (см)", "Объём (л)"]

def write_dimensions(ws: Worksheet, card_dims: dict[int, dict]) -> None:
    for col, h in enumerate(HEADERS, 1):
        ws.cell(1, col, h)
    for i, (nm_id, dims) in enumerate(sorted(card_dims.items()), 2):
        ws.cell(i, 1, nm_id)
        ws.cell(i, 2, dims.get("width", 0))
        ws.cell(i, 3, dims.get("height", 0))
        ws.cell(i, 4, dims.get("length", 0))
        ws.cell(i, 5, dims.get("volume", 0))
```

```python
# services/logistics_audit/output/sheet_tariffs_box.py
"""Sheet 10: 'Тарифы короб' — box tariff snapshot."""
from __future__ import annotations
from openpyxl.worksheet.worksheet import Worksheet
from services.logistics_audit.models.tariff_snapshot import TariffSnapshot

HEADERS = ["Склад", "Регион", "Коэф. логистики (%)", "Коэф. хранения (%)",
           "Логистика: база (₽)", "Логистика: доп.л (₽)", "Хранение: база (₽)"]

def write_tariffs_box(ws: Worksheet, tariffs: dict[str, TariffSnapshot]) -> None:
    for col, h in enumerate(HEADERS, 1):
        ws.cell(1, col, h)
    for i, (name, t) in enumerate(sorted(tariffs.items()), 2):
        ws.cell(i, 1, name)
        ws.cell(i, 2, t.geo_name)
        ws.cell(i, 3, t.delivery_coef_pct)
        ws.cell(i, 4, t.storage_coef_pct)
        ws.cell(i, 5, t.box_delivery_base)
        ws.cell(i, 6, t.box_delivery_liter)
        ws.cell(i, 7, t.box_storage_base)
```

```python
# services/logistics_audit/output/sheet_tariffs_pallet.py
"""Sheet 11: 'Тариф монопалета' — pallet tariff data."""
from __future__ import annotations
from openpyxl.worksheet.worksheet import Worksheet

def write_tariffs_pallet(ws: Worksheet, pallet_data: dict) -> None:
    """Write raw pallet tariff data. Structure TBD based on API response."""
    warehouses = pallet_data.get("response", {}).get("data", {}).get("warehouseList", [])
    if not warehouses:
        ws.cell(1, 1, "Нет данных по тарифам монопалета")
        return
    headers = list(warehouses[0].keys())
    for col, h in enumerate(headers, 1):
        ws.cell(1, col, h)
    for i, wh in enumerate(warehouses, 2):
        for col, h in enumerate(headers, 1):
            ws.cell(i, col, wh.get(h, ""))
```

- [ ] **Step 3: Commit**

```bash
git add services/logistics_audit/output/
git commit -m "feat(logistics-audit): Excel sheets 4-11 — detail, IL, pivot, types, weekly, dims, tariffs"
```

---

## Task 11: Excel Generator Orchestrator

**Files:**
- Create: `services/logistics_audit/output/excel_generator.py`

- [ ] **Step 1: Write test for full workbook generation**

Add to `tests/services/logistics_audit/test_excel_sheets.py`:

```python
def test_generate_full_workbook():
    """Excel generator creates workbook with all 11 sheet names."""
    from services.logistics_audit.output.excel_generator import generate_workbook
    from services.logistics_audit.models.audit_config import AuditConfig
    from datetime import date

    row = _make_row(raw={"realizationreport_id": 658038623, "nm_id": 257131227})
    config = AuditConfig(
        api_key="test", date_from=date(2026, 3, 9), date_to=date(2026, 3, 15),
        ktr=1.04, base_tariff_1l=46.0, base_tariff_extra_l=14.0,
    )
    wb = generate_workbook(
        config=config,
        all_rows=[row],
        logistics_rows=[row],
        overpayment_results=[None],
        coefs=[1.95],
        card_dims={257131227: {"width": 33, "height": 22, "length": 4, "volume": 2.904}},
        tariffs_box={},
        tariffs_pallet={},
        wb_volumes={},
    )
    sheet_names = wb.sheetnames
    assert len(sheet_names) == 11
    assert "Переплата по логистике (короб)" in sheet_names
    assert "СВОД" in sheet_names
    assert "Детализация" in sheet_names
```

- [ ] **Step 2: Implement excel_generator.py**

```python
# services/logistics_audit/output/excel_generator.py
"""Main Excel generator — creates workbook with all 11 sheets."""
from __future__ import annotations
import openpyxl
from services.logistics_audit.models.audit_config import AuditConfig
from services.logistics_audit.models.report_row import ReportRow
from services.logistics_audit.models.tariff_snapshot import TariffSnapshot
from services.logistics_audit.calculators.logistics_overpayment import OverpaymentResult
from services.logistics_audit.output.sheet_overpayment_formulas import write_overpayment_formulas
from services.logistics_audit.output.sheet_overpayment_values import write_overpayment_values
from services.logistics_audit.output.sheet_svod import write_svod
from services.logistics_audit.output.sheet_detail import write_detail
from services.logistics_audit.output.sheet_il import write_il
from services.logistics_audit.output.sheet_pivot_by_article import write_pivot_by_article
from services.logistics_audit.output.sheet_logistics_types import write_logistics_types
from services.logistics_audit.output.sheet_weekly import write_weekly
from services.logistics_audit.output.sheet_dimensions import write_dimensions
from services.logistics_audit.output.sheet_tariffs_box import write_tariffs_box
from services.logistics_audit.output.sheet_tariffs_pallet import write_tariffs_pallet

SHEET_NAMES = [
    "Переплата по логистике (короб)",
    "Переплата по логистике",
    "СВОД",
    "Детализация",
    "ИЛ",
    "Переплата по артикулам",
    "Виды логистики",
    "Еженед. отчет",
    "Габариты в карточке",
    "Тарифы короб",
    "Тариф монопалета",
]


def generate_workbook(
    config: AuditConfig,
    all_rows: list[ReportRow],
    logistics_rows: list[ReportRow],
    overpayment_results: list[OverpaymentResult | None],
    coefs: list[float],
    card_dims: dict[int, dict],
    tariffs_box: dict[str, TariffSnapshot],
    tariffs_pallet: dict,
    wb_volumes: dict[int, float],
    il_data: list[dict] | None = None,
) -> openpyxl.Workbook:
    """Generate the full 11-sheet Excel workbook."""
    wb = openpyxl.Workbook()

    # Remove default sheet
    wb.remove(wb.active)

    # Create all sheets
    sheets = {}
    for name in SHEET_NAMES:
        sheets[name] = wb.create_sheet(name)

    # Aggregate overpayment by report
    overpay_by_report: dict[int, float] = {}
    for row, res in zip(logistics_rows, overpayment_results):
        if res is not None:
            rid = row.realizationreport_id
            overpay_by_report[rid] = overpay_by_report.get(rid, 0) + res.overpayment

    volumes = {nm: d["volume"] for nm, d in card_dims.items()}

    # Sheet 1: Formulas
    write_overpayment_formulas(
        sheets["Переплата по логистике (короб)"], logistics_rows,
        ktr=config.ktr, base_1l=config.base_tariff_1l, extra_l=config.base_tariff_extra_l,
    )

    # Sheet 2: Values
    write_overpayment_values(
        sheets["Переплата по логистике"], logistics_rows,
        overpayment_results, volumes, coefs,
    )

    # Sheet 3: SVOD
    write_svod(sheets["СВОД"], all_rows, overpay_by_report)

    # Sheet 4: Detail
    write_detail(sheets["Детализация"], all_rows)

    # Sheet 5: IL
    write_il(sheets["ИЛ"], il_data)

    # Sheet 6: Pivot by article
    write_pivot_by_article(sheets["Переплата по артикулам"], logistics_rows, overpayment_results)

    # Sheet 7: Logistics types
    write_logistics_types(sheets["Виды логистики"], logistics_rows)

    # Sheet 8: Weekly
    write_weekly(sheets["Еженед. отчет"], all_rows)

    # Sheet 9: Dimensions
    write_dimensions(sheets["Габариты в карточке"], card_dims)

    # Sheet 10: Tariffs box
    write_tariffs_box(sheets["Тарифы короб"], tariffs_box)

    # Sheet 11: Tariffs pallet
    write_tariffs_pallet(sheets["Тариф монопалета"], tariffs_pallet)

    return wb
```

- [ ] **Step 3: Run tests — verify PASS**

```bash
pytest tests/services/logistics_audit/test_excel_sheets.py -v
```

- [ ] **Step 4: Commit**

```bash
git add services/logistics_audit/output/excel_generator.py tests/services/logistics_audit/test_excel_sheets.py
git commit -m "feat(logistics-audit): Excel generator orchestrator — all 11 sheets"
```

---

## Task 12: Runner — End-to-End Pipeline

**Files:**
- Create: `services/logistics_audit/runner.py`
- Create: `services/logistics_audit/config.py`

**Context:** Entry point that orchestrates: fetch all data → fetch localization data (for new formula) → calibrate tariffs → calculate overpayments (dual formula) → generate Excel → save file. For orders from 23.03.2026+, fetches WB supplier/orders to compute per-SKU localization %, then uses `irp_coefficients.get_ktr_krp()` for IL/IRP.

- [ ] **Step 1: Implement config.py**

```python
# services/logistics_audit/config.py
"""Load config from environment / .env for logistics audit."""
from __future__ import annotations
import os
from datetime import date
from pathlib import Path
from dotenv import load_dotenv
from services.logistics_audit.models.audit_config import AuditConfig

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


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

- [ ] **Step 2: Implement runner.py**

```python
# services/logistics_audit/runner.py
"""Entry point: fetch → calculate → generate Excel."""
from __future__ import annotations
import logging
from datetime import date
from pathlib import Path
from services.logistics_audit.models.audit_config import AuditConfig
from services.logistics_audit.api.wb_reports import fetch_report
from services.logistics_audit.api.wb_tariffs import fetch_tariffs_box, fetch_tariffs_pallet
from services.logistics_audit.api.wb_content import fetch_all_cards
from services.logistics_audit.api.wb_warehouse_remains import fetch_warehouse_remains
from services.logistics_audit.api.wb_penalties import (
    fetch_measurement_penalties, fetch_deductions,
)
from services.logistics_audit.calculators.tariff_calibrator import calibrate_base_tariff
from services.logistics_audit.calculators.logistics_overpayment import (
    calculate_row_overpayment,
    OverpaymentResult,
)
from services.logistics_audit.output.excel_generator import generate_workbook

logger = logging.getLogger(__name__)


def run_audit(config: AuditConfig, output_dir: str = ".") -> str:
    """
    Run full logistics audit pipeline.
    Returns path to generated Excel file.
    """
    df = config.date_from.isoformat()
    dt = config.date_to.isoformat()
    logger.info(f"Starting audit: {df} → {dt}, KTR={config.ktr}")

    # === Step 1: Fetch data ===
    logger.info("Fetching reportDetailByPeriod...")
    all_rows = fetch_report(config.api_key, df, dt)
    logger.info(f"Total rows: {len(all_rows)}")

    logger.info("Fetching tariffs...")
    tariffs_box = fetch_tariffs_box(config.api_key, dt)
    tariffs_pallet = fetch_tariffs_pallet(config.api_key, dt)

    logger.info("Fetching card dimensions...")
    card_dims = fetch_all_cards(config.api_key)

    logger.info("Fetching warehouse remains...")
    wb_volumes = fetch_warehouse_remains(config.api_key)

    logger.info("Fetching penalties...")
    dt_rfc3339 = f"{dt}T23:59:59Z"
    penalties = fetch_measurement_penalties(config.api_key, dt_rfc3339)
    deductions = fetch_deductions(config.api_key, dt_rfc3339)
    logger.info(f"Penalties: {len(penalties)}, Deductions: {len(deductions)}")

    # === Step 2: Filter logistics rows ===
    logistics_rows = [r for r in all_rows if r.is_logistics]
    logger.info(f"Logistics rows: {len(logistics_rows)}")

    # === Step 2b: Fetch localization data (for new formula, orders from 23.03.2026+) ===
    from services.logistics_audit.calculators.logistics_overpayment import FORMULA_CHANGE_DATE
    has_new_formula_rows = any(
        r.order_dt and r.order_dt >= FORMULA_CHANGE_DATE for r in logistics_rows
    )
    sku_localization: dict[int, float] = {}
    prices: dict[int, float] = {}
    if has_new_formula_rows:
        logger.info("New formula rows detected (>=23.03.2026), fetching localization data...")
        from services.logistics_audit.calculators.localization_resolver import (
            calculate_sku_localization,
        )
        # Fetch orders for localization calculation (last 30 days)
        from shared.clients.wb_client import WBClient
        wb_client = WBClient(config.api_key)
        orders = wb_client.get_supplier_orders(date_from=config.date_from.isoformat())
        sku_localization = calculate_sku_localization(orders)
        logger.info(f"Localization data for {len(sku_localization)} SKUs")

        # Fetch prices for IRP calculation
        prices_raw = wb_client.get_prices()
        for p in prices_raw:
            nm_id = p.get("nmId", 0)
            price = p.get("price", 0) * (1 - p.get("discount", 0) / 100)
            if nm_id:
                prices[nm_id] = price
        logger.info(f"Prices for {len(prices)} SKUs")

    # === Step 3: Calibrate base tariff ===
    calib_rows = []
    for row in logistics_rows:
        vol = card_dims.get(row.nm_id, {}).get("volume", 0)
        if vol > 0:
            calib_rows.append({
                "delivery_rub": row.delivery_rub,
                "dlv_prc": row.dlv_prc,
                "volume": vol,
            })

    calibrated = calibrate_base_tariff(calib_rows)
    if calibrated and config.ktr > 0:
        estimated_base = calibrated / config.ktr
        logger.info(f"Calibrated base (≤1L): {estimated_base:.2f}₽ "
                     f"(median base*ktr={calibrated:.2f})")
    else:
        estimated_base = config.base_tariff_1l
        logger.info(f"Using default base: {estimated_base}₽")

    # === Step 4: Calculate overpayments ===
    results: list[OverpaymentResult | None] = []
    coefs: list[float] = []
    for row in logistics_rows:
        vol = card_dims.get(row.nm_id, {}).get("volume", 0)

        # Determine coefficient
        if row.dlv_prc > 0:
            coef = row.dlv_prc
        else:
            coef = 0.0

        coefs.append(coef)

        # Determine base tariff for this row
        if vol <= 1:
            base = estimated_base
        else:
            base = config.base_tariff_1l

        result = calculate_row_overpayment(
            delivery_rub=row.delivery_rub,
            volume=vol,
            coef=coef,
            base_1l=base,
            extra_l=config.base_tariff_extra_l,
            order_dt=row.order_dt,
            ktr_manual=config.ktr,
            is_fixed_rate=row.is_fixed_rate,
            sku_localization_pct=sku_localization.get(row.nm_id),
            retail_price=prices.get(row.nm_id, 0),
        )
        results.append(result)

    # Summary
    total_charged = sum(r.delivery_rub for r in logistics_rows)
    if total_charged == 0:
        logger.warning("No logistics charges found")
        total_calculated = 0
        total_overpay = 0
    else:
        total_calculated = sum(
            res.calculated_cost for res in results if res is not None
        )
        total_overpay = sum(
            res.overpayment for res in results if res is not None
    )
    logger.info(f"WB charged: {total_charged:,.2f}₽")
    logger.info(f"Calculated: {total_calculated:,.2f}₽")
    logger.info(f"Overpayment: {total_overpay:,.2f}₽ ({total_overpay/total_charged*100:.1f}%)")

    # === Step 5: Generate Excel ===
    wb = generate_workbook(
        config=config,
        all_rows=all_rows,
        logistics_rows=logistics_rows,
        overpayment_results=results,
        coefs=coefs,
        card_dims=card_dims,
        tariffs_box=tariffs_box,
        tariffs_pallet=tariffs_pallet,
        wb_volumes=wb_volumes,
    )

    filename = f"Аудит логистики {df} — {dt}.xlsx"
    filepath = str(Path(output_dir) / filename)
    wb.save(filepath)
    logger.info(f"Excel saved: {filepath}")
    return filepath


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    from services.logistics_audit.config import load_config

    cabinet = sys.argv[1] if len(sys.argv) > 1 else "OOO"
    date_from = sys.argv[2] if len(sys.argv) > 2 else None
    date_to = sys.argv[3] if len(sys.argv) > 3 else None
    ktr = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0

    cfg = load_config(cabinet, date_from, date_to, ktr)
    output = run_audit(cfg)
    print(f"Done: {output}")
```

**Usage:**
```bash
python -m services.logistics_audit.runner OOO 2026-03-09 2026-03-15 1.04
```

- [ ] **Step 3: Commit**

```bash
git add services/logistics_audit/config.py services/logistics_audit/runner.py
git commit -m "feat(logistics-audit): runner pipeline — fetch, calculate, generate Excel"
```

---

## Task 14: Integration Test — Verify on Real Data (short period)

**Files:**
- No new files — use existing runner

- [ ] **Step 1: Run on ООО Wookiee data — 1 week (requires API key)**

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee
python -m services.logistics_audit.runner OOO 2026-03-09 2026-03-15 1.04
```

- [ ] **Step 2: Verify output against spec section 10 checkpoints**

| Check | Expected |
|---|---|
| Total rows | 32,776 |
| Logistics rows | 8,494 |
| delivery_rub total | 661,472₽ |
| Fixed-rate (50₽) count | 2,440 |
| Unique nm_ids | 204 |
| Excel has 11 sheets | Yes |

- [ ] **Step 3: Open Excel and spot-check**

Open the generated `.xlsx` file and verify:
- Sheet 1 has live formulas in columns L, M, R, S
- Sheet 3 (СВОД) has one row per report ID
- Sheet 9 (Габариты) has dimensions for all nm_ids
- Sheet 10 (Тарифы) has warehouse coefficients

- [ ] **Step 4: Commit any fixes**

```bash
git add -A
git commit -m "fix(logistics-audit): integration test fixes from real data run"
```

---

## Task 15: Full Test Run — January to Today (3 months)

**Files:**
- No new files — use existing runner

**Context:** This is the full test run the user requested. Covers both formula periods:
- 01.01 — 22.03: old formula (КТР=1.04 manual)
- 23.03 — 25.03: new formula (ИЛ + ИРП, auto-calculated from localization)

~100-150K rows expected. API rate limit: 1 req/min → ~15 min for report fetching.

- [ ] **Step 1: Run full 3-month audit**

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee
python -m services.logistics_audit.runner OOO 2026-01-01 2026-03-25 1.04
```

Expected output:
```
Starting audit: 2026-01-01 → 2026-03-25, KTR=1.04
Fetching reportDetailByPeriod... (may take ~15 min due to pagination)
Total rows: ~100,000-150,000
Logistics rows: ~30,000-50,000
New formula rows detected (>=23.03.2026), fetching localization data...
Localization data for ~200 SKUs
WB charged: ~X₽
Calculated: ~Y₽
Overpayment: ~Z₽
Excel saved: Аудит логистики 2026-01-01 — 2026-03-25.xlsx
```

- [ ] **Step 2: Verify the generated Excel**

Check:
- 11 sheets present
- СВОД shows ~12-13 weekly reports
- Rows from before 23.03 use KTR=1.04
- Rows from after 23.03 use IL/IRP from localization
- Sheet 6 (по артикулам) shows top overpayers
- Sheet 7 (виды логистики) breakdown matches expected types

- [ ] **Step 3: Commit the final state**

```bash
git add -A
git commit -m "feat(logistics-audit): verified full 3-month audit (Jan-Mar 2026)"
```
