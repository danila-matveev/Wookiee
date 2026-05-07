# Logistics Audit Tool — Implementation Plan (Plan 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate `services/logistics_audit/` from Wookiee into `audit/` in `~/Projects/wb-logistics-toolkit/`, replacing all Wookiee-specific imports with toolkit equivalents and adding the new `sheet_recommendations.py` sheet.

**Architecture:** Direct migration with import substitution. No logic changes — all business rules (tariff periods, warehouse coefficient resolution, IL calculation) are preserved exactly. The only structural changes are: (1) API clients use `WBClient(token=...)` instead of raw `httpx`; (2) Supabase access via `get_supabase_client()` instead of psycopg2; (3) `il_overrides.json` removed — IL from WB API only; (4) one new Excel sheet added.

**Tech Stack:** Python 3.11+, openpyxl, httpx, supabase-py, pytest

**Working directory:** `~/Projects/wb-logistics-toolkit/`

---

## File Map

```
audit/
  __init__.py                        ← new (empty)
  run_audit.py                       ← new (CLI entry point)
  models/
    __init__.py                      ← new (empty)
    report_row.py                    ← migrated (no import changes)
    tariff_snapshot.py               ← migrated (no import changes)
    audit_config.py                  ← migrated + add cabinet field
  calculators/
    __init__.py                      ← new (empty)
    tariff_periods.py                ← migrated (no import changes)
    dimensions_checker.py            ← migrated (no import changes)
    logistics_overpayment.py         ← migrated (inline import fixed)
    localization_resolver.py         ← migrated (import: localization.data.mappings)
    weekly_il_calculator.py          ← migrated (2 import changes)
    warehouse_coef_resolver.py       ← migrated (load_supabase_tariffs rewritten)
  output/
    __init__.py                      ← new (empty)
    excel_generator.py               ← migrated + add 12th sheet
    sheet_overpayment_values.py      ← migrated (import change)
    sheet_overpayment_formulas.py    ← migrated (import change)
    sheet_svod.py                    ← migrated (import change)
    sheet_detail.py                  ← migrated (import change)
    sheet_il.py                      ← migrated (no import change)
    sheet_pivot_by_article.py        ← migrated (2 import changes)
    sheet_logistics_types.py         ← migrated (import change)
    sheet_weekly.py                  ← migrated (import change)
    sheet_dimensions.py              ← migrated (no import change)
    sheet_tariffs_box.py             ← migrated (import change)
    sheet_tariffs_pallet.py          ← migrated (no import change)
    sheet_recommendations.py         ← NEW
  etl/
    __init__.py                      ← new (empty)
    tariff_collector.py              ← rewritten (WBClient + Supabase client)
    import_coeff_table.py            ← new (bootstrap wb_coeff_table)

shared/wb_api/
  client.py                          ← add ANALYTICS_URL constant
  tariffs.py                         ← add fetch_pallet_tariffs
  penalties.py                       ← new
```

---

## Task 1: shared/wb_api extensions

Add `ANALYTICS_URL` to `WBClient`, `fetch_pallet_tariffs` to tariffs, create `penalties.py`.

**Files:**
- Modify: `shared/wb_api/client.py`
- Modify: `shared/wb_api/tariffs.py`
- Create: `shared/wb_api/penalties.py`
- Create: `tests/shared/test_wb_api_penalties.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/shared/test_wb_api_penalties.py
from unittest.mock import MagicMock
from shared.wb_api.penalties import fetch_measurement_penalties, fetch_deductions
from shared.wb_api.client import WBClient


def test_fetch_measurement_penalties_returns_data():
    client = MagicMock(spec=WBClient)
    client.get.return_value = {"data": [{"nmId": 1, "penalty": 10.0}]}
    result = fetch_measurement_penalties(client, "2026-03-25T23:59:59Z")
    assert result == [{"nmId": 1, "penalty": 10.0}]
    client.get.assert_called_once_with(
        base="https://seller-analytics-api.wildberries.ru",
        path="/api/analytics/v1/measurement-penalties",
        params={"dateTo": "2026-03-25T23:59:59Z", "limit": 1000},
    )


def test_fetch_measurement_penalties_empty_response():
    client = MagicMock(spec=WBClient)
    client.get.return_value = {}
    assert fetch_measurement_penalties(client, "2026-03-25T23:59:59Z") == []


def test_fetch_deductions_returns_data():
    client = MagicMock(spec=WBClient)
    client.get.return_value = {"data": [{"id": 42}]}
    result = fetch_deductions(client, "2026-03-25T23:59:59Z")
    assert result == [{"id": 42}]


def test_analytics_url_on_client():
    assert WBClient.ANALYTICS_URL == "https://seller-analytics-api.wildberries.ru"
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd ~/Projects/wb-logistics-toolkit && python -m pytest tests/shared/test_wb_api_penalties.py -v
```
Expected: `ImportError: cannot import name 'fetch_measurement_penalties'` or `AttributeError: ANALYTICS_URL`

- [ ] **Step 3: Add `ANALYTICS_URL` to `shared/wb_api/client.py`**

In `shared/wb_api/client.py`, add one line after `SUPPLY_URL`:
```python
ANALYTICS_URL = "https://seller-analytics-api.wildberries.ru"
```

Full updated constants block (lines 17–21):
```python
    STATS_URL = "https://statistics-api.wildberries.ru"
    CONTENT_URL = "https://content-api.wildberries.ru"
    SUPPLY_URL = "https://supplies-api.wildberries.ru"
    ANALYTICS_URL = "https://seller-analytics-api.wildberries.ru"
```

- [ ] **Step 4: Add `fetch_pallet_tariffs` to `shared/wb_api/tariffs.py`**

Append to the end of `shared/wb_api/tariffs.py`:
```python

def fetch_pallet_tariffs(
    client: WBClient,
    date: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch pallet delivery tariffs per warehouse.

    Returns raw list of warehouse dicts from WB API.
    """
    params: dict[str, Any] = {"date": date or _date.today().isoformat()}
    data = client.get(
        base=WBClient.SUPPLY_URL,
        path="/api/v1/tariffs/pallet",
        params=params,
    )
    return data.get("response", {}).get("data", {}).get("warehouseList", [])
```

- [ ] **Step 5: Create `shared/wb_api/penalties.py`**

```python
from __future__ import annotations

from typing import Any

from .client import WBClient


def fetch_measurement_penalties(
    client: WBClient,
    date_to: str,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    """Fetch measurement penalties (short-delivery fines) from Analytics API.

    Args:
        client: WBClient instance.
        date_to: RFC3339 datetime string, e.g. "2026-03-25T23:59:59Z".
        limit: Max rows per request.

    Returns:
        List of penalty dicts.
    """
    data = client.get(
        base=WBClient.ANALYTICS_URL,
        path="/api/analytics/v1/measurement-penalties",
        params={"dateTo": date_to, "limit": limit},
    )
    return data.get("data", []) if isinstance(data, dict) else []


def fetch_deductions(
    client: WBClient,
    date_to: str,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    """Fetch deductions (substitutions, incorrect items) from Analytics API.

    Args:
        client: WBClient instance.
        date_to: RFC3339 datetime string.
        limit: Max rows per request.

    Returns:
        List of deduction dicts.
    """
    data = client.get(
        base=WBClient.ANALYTICS_URL,
        path="/api/analytics/v1/deductions",
        params={"dateTo": date_to, "limit": limit, "sort": "dtBonus", "order": "desc"},
    )
    return data.get("data", []) if isinstance(data, dict) else []
```

- [ ] **Step 6: Run tests — expect PASS**

```bash
python -m pytest tests/shared/test_wb_api_penalties.py -v
```
Expected: `4 passed`

- [ ] **Step 7: Commit**

```bash
git add shared/wb_api/client.py shared/wb_api/tariffs.py shared/wb_api/penalties.py tests/shared/test_wb_api_penalties.py
git commit -m "feat(shared): add ANALYTICS_URL, fetch_pallet_tariffs, penalties API"
```

---

## Task 2: audit/models — three dataclasses

**Files:**
- Create: `audit/__init__.py`
- Create: `audit/models/__init__.py`
- Create: `audit/models/report_row.py`
- Create: `audit/models/tariff_snapshot.py`
- Create: `audit/models/audit_config.py`
- Create: `tests/audit/__init__.py`
- Create: `tests/audit/test_models.py`

Source: `~/Projects/Wookiee/services/logistics_audit/models/`

- [ ] **Step 1: Write failing tests**

```python
# tests/audit/test_models.py
from datetime import date
from audit.models.report_row import ReportRow
from audit.models.tariff_snapshot import TariffSnapshot
from audit.models.audit_config import AuditConfig


def test_report_row_from_api_basic():
    d = {
        "nm_id": 123,
        "supplier_oper_name": "Логистика",
        "bonus_type_name": "К клиенту при продаже",
        "delivery_rub": 150.0,
        "dlv_prc": 95.0,
        "office_name": "Коледино",
        "order_dt": "2026-01-15T00:00:00",
    }
    row = ReportRow.from_api(d)
    assert row.nm_id == 123
    assert row.is_logistics is True
    assert row.is_forward_delivery is True
    assert row.is_fixed_rate is False
    assert row.order_dt == date(2026, 1, 15)


def test_report_row_from_api_fixed_rate():
    d = {"bonus_type_name": "От клиента при отмене", "supplier_oper_name": "Логистика"}
    row = ReportRow.from_api(d)
    assert row.is_fixed_rate is True
    assert row.is_forward_delivery is False


def test_report_row_is_logistics_false():
    d = {"supplier_oper_name": "Хранение"}
    row = ReportRow.from_api(d)
    assert row.is_logistics is False


def test_tariff_snapshot_from_api_parses_ru_decimal():
    d = {
        "warehouseName": "Коледино",
        "boxDeliveryBase": "46,0",
        "boxDeliveryLiter": "14,0",
        "boxDeliveryCoefExpr": "95",
        "boxStorageBase": "0",
        "boxStorageLiter": "0",
        "boxStorageCoefExpr": "0",
    }
    snap = TariffSnapshot.from_api(d)
    assert snap.warehouse_name == "Коледино"
    assert snap.box_delivery_base == 46.0
    assert snap.box_delivery_liter == 14.0
    assert snap.delivery_coef_pct == 95


def test_tariff_snapshot_dash_value():
    d = {"warehouseName": "X", "boxDeliveryBase": "-", "boxDeliveryLiter": "0"}
    snap = TariffSnapshot.from_api(d)
    assert snap.box_delivery_base == 0.0


def test_audit_config_defaults():
    cfg = AuditConfig(api_key="tok", date_from=date(2026, 1, 1), date_to=date(2026, 3, 31))
    assert cfg.ktr == 1.0
    assert cfg.cabinet == ""


def test_audit_config_with_cabinet():
    cfg = AuditConfig(
        api_key="tok", date_from=date(2026, 1, 1), date_to=date(2026, 3, 31),
        cabinet="OOO",
    )
    assert cfg.cabinet == "OOO"
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
python -m pytest tests/audit/test_models.py -v
```
Expected: `ModuleNotFoundError: No module named 'audit'`

- [ ] **Step 3: Create empty `__init__.py` files**

```bash
touch audit/__init__.py audit/models/__init__.py tests/audit/__init__.py
```

- [ ] **Step 4: Create `audit/models/report_row.py`**

Copy from Wookiee source — no import changes (pure stdlib):

```python
# Source: ~/Projects/Wookiee/services/logistics_audit/models/report_row.py
# Change: none — stdlib only
from __future__ import annotations
from dataclasses import dataclass
from datetime import date

FIXED_RATE_TYPES = frozenset({
    "От клиента при отмене",
    "От клиента при возврате",
})

FORWARD_DELIVERY_TYPES = frozenset({
    "К клиенту при продаже",
    "К клиенту при отмене",
})


@dataclass
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
    raw: dict | None = None

    @property
    def is_logistics(self) -> bool:
        return self.supplier_oper_name == "Логистика"

    @property
    def is_fixed_rate(self) -> bool:
        return self.bonus_type_name in FIXED_RATE_TYPES

    @property
    def is_forward_delivery(self) -> bool:
        """Only forward deliveries are auditable for overpayment."""
        return self.bonus_type_name in FORWARD_DELIVERY_TYPES

    @classmethod
    def from_api(cls, d: dict) -> "ReportRow":
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
    s = val[:10]
    try:
        return date.fromisoformat(s)
    except (ValueError, TypeError):
        return None
```

- [ ] **Step 5: Create `audit/models/tariff_snapshot.py`**

Copy from Wookiee source — no import changes:

```python
# Source: ~/Projects/Wookiee/services/logistics_audit/models/tariff_snapshot.py
# Change: none — stdlib only
from __future__ import annotations
from dataclasses import dataclass


@dataclass
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
    def from_api(cls, d: dict) -> "TariffSnapshot":
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
    """Parse Russian decimal: '89,7' → 89.7, '-' → 0.0, '1 046' → 1046.0"""
    if not val or val == "-":
        return 0.0
    return float(val.replace(",", ".").replace(" ", "").replace("\xa0", ""))
```

- [ ] **Step 6: Create `audit/models/audit_config.py`**

Source + add `cabinet: str = ""`:

```python
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date


@dataclass
class AuditConfig:
    """Input parameters for the audit."""
    api_key: str
    date_from: date
    date_to: date
    ktr: float = 1.0
    cabinet: str = ""
```

- [ ] **Step 7: Run tests — expect PASS**

```bash
python -m pytest tests/audit/test_models.py -v
```
Expected: `7 passed`

- [ ] **Step 8: Commit**

```bash
git add audit/__init__.py audit/models/ tests/audit/__init__.py tests/audit/test_models.py
git commit -m "feat(audit): add models — ReportRow, TariffSnapshot, AuditConfig"
```

---

## Task 3: audit/calculators — pure logic (no dependency changes)

**Files:**
- Create: `audit/calculators/__init__.py`
- Create: `audit/calculators/tariff_periods.py`
- Create: `audit/calculators/dimensions_checker.py`
- Create: `tests/audit/test_tariff_periods.py`
- Create: `tests/audit/test_dimensions_checker.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/audit/test_tariff_periods.py
from datetime import date
from audit.calculators.tariff_periods import get_base_tariffs


def test_latest_period_standard_volume():
    """2025-10-01 with vol=2L → standard 46+14 (after SUB_LITER_START, but vol≥1)."""
    base, extra = get_base_tariffs(date(2025, 10, 1), None, None, 2.0)
    assert base == 46.0
    assert extra == 14.0


def test_sub_liter_tier_03():
    """2025-10-01 with vol=0.3L → tier (max_vol=0.4): 26+0."""
    base, extra = get_base_tariffs(date(2025, 10, 1), None, None, 0.3)
    assert base == 26.0
    assert extra == 0.0


def test_sub_liter_tier_02():
    """vol=0.15L → tier (max_vol=0.2): 23+0."""
    base, extra = get_base_tariffs(date(2025, 10, 1), None, None, 0.15)
    assert base == 23.0
    assert extra == 0.0


def test_sub_liter_before_start_date_ignored():
    """Sub-liter tiers only apply from 22.09.2025. Earlier date → standard period."""
    base, extra = get_base_tariffs(date(2025, 9, 1), None, None, 0.3)
    assert base == 38.0  # standard period 28.02.2025
    assert extra == 9.5


def test_period_2025_02_28():
    base, extra = get_base_tariffs(date(2025, 3, 1), None, None, 2.0)
    assert base == 38.0
    assert extra == 9.5


def test_period_2024_12_11():
    base, extra = get_base_tariffs(date(2024, 12, 15), None, None, 2.0)
    assert base == 35.0
    assert extra == 8.5


def test_period_2024_08_14():
    base, extra = get_base_tariffs(date(2024, 8, 20), None, None, 2.0)
    assert base == 33.0
    assert extra == 8.0


def test_fixation_uses_fixation_start():
    """When fixation active, tariff period determined by fixation_start."""
    base, extra = get_base_tariffs(
        order_date=date(2025, 10, 1),
        fixation_start=date(2024, 8, 20),
        fixation_end=date(2025, 12, 31),
        volume=2.0,
    )
    # fixation_start=2024-08-20 → period 2024-08-14: 33+8
    assert base == 33.0
    assert extra == 8.0
```

```python
# tests/audit/test_dimensions_checker.py
from audit.calculators.dimensions_checker import check_dimensions


def test_check_dimensions_flags_large_diff():
    card_dims = {1: 10.0}
    wb_volumes = {1: 12.5}
    results = check_dimensions(card_dims, wb_volumes, threshold_pct=10.0)
    assert results[1].flagged is True
    assert abs(results[1].pct_diff - 25.0) < 0.01


def test_check_dimensions_no_flag_within_threshold():
    card_dims = {1: 10.0}
    wb_volumes = {1: 10.5}
    results = check_dimensions(card_dims, wb_volumes, threshold_pct=10.0)
    assert results[1].flagged is False


def test_check_dimensions_skips_missing_wb_volume():
    card_dims = {1: 10.0, 2: 5.0}
    wb_volumes = {1: 11.0}
    results = check_dimensions(card_dims, wb_volumes)
    assert 2 not in results


def test_check_dimensions_skips_zero_card_volume():
    card_dims = {1: 0.0}
    wb_volumes = {1: 5.0}
    results = check_dimensions(card_dims, wb_volumes)
    assert 1 not in results
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
python -m pytest tests/audit/test_tariff_periods.py tests/audit/test_dimensions_checker.py -v
```
Expected: `ModuleNotFoundError: No module named 'audit.calculators'`

- [ ] **Step 3: Create `audit/calculators/__init__.py`**

```bash
touch audit/calculators/__init__.py
```

- [ ] **Step 4: Create `audit/calculators/tariff_periods.py`**

Copy from Wookiee — no import changes (pure stdlib):

```python
# Source: ~/Projects/Wookiee/services/logistics_audit/calculators/tariff_periods.py
# Change: none — stdlib only
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
        return TARIFF_PERIODS[0][1], TARIFF_PERIODS[0][2]

    if (
        fixation_start
        and fixation_end
        and fixation_end > order_date
    ):
        ref_date = fixation_start
    else:
        ref_date = order_date

    if order_date >= SUB_LITER_START and 0 < volume < 1.0:
        for max_vol, first_l, extra_l in SUB_LITER_TIERS:
            if volume <= max_vol:
                return first_l, extra_l

    for period_start, first_l, extra_l in TARIFF_PERIODS:
        if ref_date >= period_start:
            return first_l, extra_l

    return TARIFF_PERIODS[-1][1], TARIFF_PERIODS[-1][2]
```

- [ ] **Step 5: Create `audit/calculators/dimensions_checker.py`**

Copy from Wookiee — no import changes:

```python
# Source: ~/Projects/Wookiee/services/logistics_audit/calculators/dimensions_checker.py
# Change: none — stdlib only
from __future__ import annotations
from dataclasses import dataclass


@dataclass
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

- [ ] **Step 6: Run tests — expect PASS**

```bash
python -m pytest tests/audit/test_tariff_periods.py tests/audit/test_dimensions_checker.py -v
```
Expected: `12 passed`

- [ ] **Step 7: Commit**

```bash
git add audit/calculators/__init__.py audit/calculators/tariff_periods.py audit/calculators/dimensions_checker.py tests/audit/test_tariff_periods.py tests/audit/test_dimensions_checker.py
git commit -m "feat(audit): add tariff_periods and dimensions_checker calculators"
```

---

## Task 4: audit/calculators — IL and localization

Migrate `logistics_overpayment.py`, `localization_resolver.py`, `weekly_il_calculator.py`.
Key import changes: `services.wb_localization.*` → `localization.data.mappings` + `shared.coeff_table`.

**Files:**
- Create: `audit/calculators/logistics_overpayment.py`
- Create: `audit/calculators/localization_resolver.py`
- Create: `audit/calculators/weekly_il_calculator.py`
- Create: `tests/audit/test_logistics_overpayment.py`
- Create: `tests/audit/test_localization_resolver.py`
- Create: `tests/audit/test_weekly_il_calculator.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/audit/test_logistics_overpayment.py
from datetime import date
from unittest.mock import patch
from audit.calculators.logistics_overpayment import (
    calculate_row_overpayment,
    OverpaymentResult,
    FORMULA_CHANGE_DATE,
)


def test_formula_change_date():
    assert FORMULA_CHANGE_DATE == date(2026, 3, 23)


def test_fixed_rate_returns_zero_overpayment():
    result = calculate_row_overpayment(
        delivery_rub=100.0, volume=2.0, coef=1.0,
        base_1l=46.0, extra_l=14.0,
        order_dt=date(2025, 1, 1), ktr_manual=1.0,
        is_fixed_rate=True, is_forward_delivery=False,
    )
    assert result.overpayment == 0.0
    assert result.calculated_cost == 100.0


def test_non_forward_returns_none():
    result = calculate_row_overpayment(
        delivery_rub=100.0, volume=2.0, coef=1.0,
        base_1l=46.0, extra_l=14.0,
        order_dt=date(2025, 1, 1), ktr_manual=1.0,
        is_fixed_rate=False, is_forward_delivery=False,
    )
    assert result is None


def test_zero_coef_returns_none():
    result = calculate_row_overpayment(
        delivery_rub=100.0, volume=2.0, coef=0.0,
        base_1l=46.0, extra_l=14.0,
        order_dt=date(2025, 1, 1), ktr_manual=1.0,
        is_fixed_rate=False, is_forward_delivery=True,
    )
    assert result is None


def test_old_formula_basic():
    """Old formula (before 23.03.2026): cost = (46 + 1×14) × 1.0 × 1.0 = 60."""
    result = calculate_row_overpayment(
        delivery_rub=100.0, volume=2.0, coef=1.0,
        base_1l=46.0, extra_l=14.0,
        order_dt=date(2025, 1, 1), ktr_manual=1.0,
        is_fixed_rate=False, is_forward_delivery=True,
    )
    assert result is not None
    assert result.calculated_cost == 60.0
    assert result.overpayment == 40.0


def test_new_formula_uses_get_ktr_krp():
    """New formula (>=23.03.2026): uses get_ktr_krp from shared.coeff_table."""
    with patch(
        "audit.calculators.logistics_overpayment.get_ktr_krp",
        return_value=(0.8, 0.0),
    ):
        result = calculate_row_overpayment(
            delivery_rub=100.0, volume=2.0, coef=1.0,
            base_1l=46.0, extra_l=14.0,
            order_dt=date(2026, 4, 1), ktr_manual=1.0,
            is_fixed_rate=False, is_forward_delivery=True,
            sku_localization_pct=85.0, retail_price=500.0,
        )
    # base_cost = (46 + 1×14) × 1.0 = 60; cost = 60 × 0.8 + 500 × 0.0 = 48
    assert result is not None
    assert result.calculated_cost == 48.0
```

```python
# tests/audit/test_localization_resolver.py
from audit.calculators.localization_resolver import calculate_sku_localization


def test_local_order():
    orders = [{
        "nmId": 1,
        "warehouseName": "Коледино",
        "oblastOkrugName": "Центральный федеральный округ",
    }]
    result = calculate_sku_localization(orders)
    assert result[1] == 100.0


def test_non_local_order():
    orders = [{
        "nmId": 1,
        "warehouseName": "Коледино",
        "oblastOkrugName": "Приволжский федеральный округ",
    }]
    result = calculate_sku_localization(orders)
    assert result[1] == 0.0


def test_mixed_orders_50pct():
    orders = [
        {"nmId": 1, "warehouseName": "Коледино", "oblastOkrugName": "Центральный федеральный округ"},
        {"nmId": 1, "warehouseName": "Коледино", "oblastOkrugName": "Приволжский федеральный округ"},
    ]
    result = calculate_sku_localization(orders)
    assert result[1] == 50.0


def test_skips_unknown_warehouse():
    orders = [{"nmId": 1, "warehouseName": "НеизвестныйСклад", "oblastOkrugName": "Центральный федеральный округ"}]
    result = calculate_sku_localization(orders)
    assert 1 not in result


def test_skips_empty_nm_id():
    orders = [{"nmId": 0, "warehouseName": "Коледино", "oblastOkrugName": "Центральный федеральный округ"}]
    result = calculate_sku_localization(orders)
    assert not result
```

```python
# tests/audit/test_weekly_il_calculator.py
from datetime import date
from unittest.mock import patch
from audit.calculators.weekly_il_calculator import (
    calculate_weekly_il,
    get_il_for_date,
)


def _monday(d: date) -> date:
    from datetime import timedelta
    return d - timedelta(days=d.weekday())


def test_all_keys_are_mondays():
    with patch(
        "audit.calculators.weekly_il_calculator.get_ktr_krp",
        return_value=(1.0, 0.0),
    ):
        week_to_il, _ = calculate_weekly_il([], date(2026, 1, 5), date(2026, 1, 18))
    assert all(d.weekday() == 0 for d in week_to_il)


def test_returns_il_for_period():
    """Two weeks in period → two keys in week_to_il."""
    with patch(
        "audit.calculators.weekly_il_calculator.get_ktr_krp",
        return_value=(1.0, 0.0),
    ):
        week_to_il, _ = calculate_weekly_il([], date(2026, 1, 5), date(2026, 1, 18))
    assert len(week_to_il) == 2


def test_get_il_for_date_returns_none_empty():
    assert get_il_for_date({}, date(2026, 1, 5)) is None


def test_get_il_for_date_returns_none_none_date():
    assert get_il_for_date({date(2026, 1, 5): 1.0}, None) is None


def test_get_il_for_date_looks_up_monday():
    mon = _monday(date(2026, 1, 7))  # wednesday → monday 2026-01-05
    week_to_il = {mon: 0.8}
    assert get_il_for_date(week_to_il, date(2026, 1, 7)) == 0.8
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
python -m pytest tests/audit/test_logistics_overpayment.py tests/audit/test_localization_resolver.py tests/audit/test_weekly_il_calculator.py -v
```
Expected: multiple `ImportError` failures

- [ ] **Step 3: Create `audit/calculators/logistics_overpayment.py`**

Source change: inline `from services.wb_localization.irp_coefficients import get_ktr_krp` → top-level `from shared.coeff_table import get_ktr_krp`:

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import date

from shared.coeff_table import get_ktr_krp

FORMULA_CHANGE_DATE = date(2026, 3, 23)


@dataclass
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
    is_forward_delivery: bool = True,
    sku_localization_pct: float | None = None,
    retail_price: float = 0.0,
) -> OverpaymentResult | None:
    """Calculate overpayment for a single logistics row.

    Uses old formula (KTR) before 23.03.2026,
    new formula (IL + IRP) from 23.03.2026.
    Returns None if row is not auditable (non-forward, zero coef).
    """
    if is_fixed_rate:
        return OverpaymentResult(calculated_cost=delivery_rub, overpayment=0.0)

    if not is_forward_delivery:
        return None

    if coef == 0:
        return None

    if volume > 1:
        base_cost = (base_1l + (volume - 1) * extra_l) * coef
    else:
        base_cost = base_1l * coef

    use_new_formula = order_dt and order_dt >= FORMULA_CHANGE_DATE

    if use_new_formula and sku_localization_pct is not None:
        il, irp_pct = get_ktr_krp(sku_localization_pct)
        cost = base_cost * il + retail_price * (irp_pct / 100)
    else:
        cost = base_cost * ktr_manual

    cost = round(cost, 2)
    return OverpaymentResult(
        calculated_cost=cost,
        overpayment=round(delivery_rub - cost, 2),
    )
```

- [ ] **Step 4: Create `audit/calculators/localization_resolver.py`**

Source change: `services.wb_localization.wb_localization_mappings` → `localization.data.mappings`:

```python
from __future__ import annotations
from collections import defaultdict

from localization.data.mappings import WAREHOUSE_TO_FD, OBLAST_TO_FD


def calculate_sku_localization(orders: list[dict]) -> dict[int, float]:
    """Calculate per-SKU localization % from WB orders.

    An order is "local" if the warehouse's federal district matches
    the delivery oblast's federal district.

    Returns:
        {nm_id: localization_pct}
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

    result: dict[int, float] = {}
    for nm_id, total in sku_total.items():
        if total > 0:
            result[nm_id] = round(sku_local[nm_id] / total * 100, 2)
    return result
```

- [ ] **Step 5: Create `audit/calculators/weekly_il_calculator.py`**

Source changes:
- `from services.wb_localization.wb_localization_mappings import get_warehouse_fd, get_delivery_fd` → `from localization.data.mappings import get_warehouse_fd, get_delivery_fd`
- `from services.wb_localization.irp_coefficients import get_ktr_krp` → `from shared.coeff_table import get_ktr_krp`

```python
"""Calculate weekly Localization Index (ИЛ) from WB orders."""
from __future__ import annotations
from collections import defaultdict
from datetime import date, timedelta

from localization.data.mappings import get_warehouse_fd, get_delivery_fd
from shared.coeff_table import get_ktr_krp


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def calculate_weekly_il(
    orders: list[dict],
    date_from: date,
    date_to: date,
    il_overrides: dict[str, float] | None = None,
) -> tuple[dict[date, float], list[dict]]:
    """Calculate per-week IL for the audit period.

    Args:
        orders: Raw WB orders (from supplier/orders API).
        date_from: Audit start date.
        date_to: Audit end date.
        il_overrides: Optional manual IL values by week start date (Monday ISO string).

    Returns:
        (week_to_il, il_data)
        - week_to_il: {monday_date: IL_value} for per-row lookup
        - il_data: list of dicts for the ИЛ Excel sheet
    """
    week_local: dict[date, int] = defaultdict(int)
    week_total: dict[date, int] = defaultdict(int)

    for o in orders:
        order_date_str = o.get("date", "")[:10]
        if not order_date_str:
            continue
        try:
            order_date = date.fromisoformat(order_date_str)
        except ValueError:
            continue

        wh_name = o.get("warehouseName", "")
        delivery_region = (
            o.get("oblastOkrugName", "")
            or o.get("oblast", "")
            or o.get("countryName", "")
        )

        wh_fd = get_warehouse_fd(wh_name)
        delivery_fd = get_delivery_fd(delivery_region)

        if not wh_fd or not delivery_fd:
            continue

        mon = _monday(order_date)
        week_total[mon] += 1
        if wh_fd == delivery_fd:
            week_local[mon] += 1

    week_to_il: dict[date, float] = {}

    mon = _monday(date_from)
    end_mon = _monday(date_to)
    all_mondays: list[date] = []
    while mon <= end_mon:
        all_mondays.append(mon)
        mon += timedelta(days=7)

    for mon in all_mondays:
        total = week_total.get(mon, 0)
        local = week_local.get(mon, 0)
        loc_pct = local / total * 100 if total > 0 else 0.0
        il, _ = get_ktr_krp(loc_pct)
        week_to_il[mon] = il

    if il_overrides:
        for date_str, override_il in il_overrides.items():
            try:
                override_date = date.fromisoformat(date_str)
                mon = _monday(override_date)
                if mon in week_to_il:
                    week_to_il[mon] = override_il
            except ValueError:
                pass

    override_mondays: set[date] = set()
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

    return week_to_il, il_data


def get_il_for_date(week_to_il: dict[date, float], order_dt: date | None) -> float | None:
    """Look up the IL value for a specific order date."""
    if order_dt is None or not week_to_il:
        return None
    mon = _monday(order_dt)
    return week_to_il.get(mon)
```

- [ ] **Step 6: Run tests — expect PASS**

```bash
python -m pytest tests/audit/test_logistics_overpayment.py tests/audit/test_localization_resolver.py tests/audit/test_weekly_il_calculator.py -v
```
Expected: `14 passed`

- [ ] **Step 7: Commit**

```bash
git add audit/calculators/logistics_overpayment.py audit/calculators/localization_resolver.py audit/calculators/weekly_il_calculator.py tests/audit/test_logistics_overpayment.py tests/audit/test_localization_resolver.py tests/audit/test_weekly_il_calculator.py
git commit -m "feat(audit): add IL/localization calculators with corrected imports"
```

---

## Task 5: audit/calculators/warehouse_coef_resolver.py

Key change: `load_supabase_tariffs` rewritten to use Supabase Python client instead of psycopg2. `load_tariff_file_coefs` removed (Wookiee-specific Excel file, not in toolkit).

**Files:**
- Create: `audit/calculators/warehouse_coef_resolver.py`
- Create: `tests/audit/test_warehouse_coef_resolver.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/audit/test_warehouse_coef_resolver.py
from datetime import date
from unittest.mock import patch, MagicMock
from audit.calculators.warehouse_coef_resolver import (
    resolve_warehouse_coef,
    CoefResult,
    load_supabase_tariffs,
)


def test_resolve_fixation_tier():
    result = resolve_warehouse_coef(
        dlv_prc=100.0, fixed_coef=95.0,
        fixation_end=date(2026, 6, 1),
        order_date=date(2026, 3, 1),
        warehouse_name="Коледино",
        supabase_tariffs={},
    )
    assert result.source == "fixation"
    assert result.value == 95.0
    assert result.verified is True


def test_resolve_fixation_expired():
    """fixation_end <= order_date → fixation NOT used."""
    supabase = {"Коледино": {date(2026, 3, 1): 1.0}}
    result = resolve_warehouse_coef(
        dlv_prc=100.0, fixed_coef=95.0,
        fixation_end=date(2026, 3, 1),
        order_date=date(2026, 3, 1),
        warehouse_name="Коледино",
        supabase_tariffs=supabase,
    )
    assert result.source == "supabase"


def test_resolve_supabase_tier_closest_date():
    supabase = {
        "Коледино": {
            date(2026, 3, 1): 0.95,
            date(2026, 3, 10): 1.05,
        }
    }
    result = resolve_warehouse_coef(
        dlv_prc=0.0, fixed_coef=0.0,
        fixation_end=None, order_date=date(2026, 3, 15),
        warehouse_name="Коледино", supabase_tariffs=supabase,
    )
    assert result.source == "supabase"
    assert result.value == 1.05
    assert result.verified is True


def test_resolve_dlv_prc_fallback():
    result = resolve_warehouse_coef(
        dlv_prc=1.2, fixed_coef=0.0,
        fixation_end=None, order_date=date(2026, 3, 15),
        warehouse_name="НеизвестныйСклад",
        supabase_tariffs={},
    )
    assert result.source == "dlv_prc"
    assert result.verified is False
    assert result.value == 1.2


def test_resolve_zero_coef_fallback():
    """All tiers fail → CoefResult(0.0, dlv_prc, False)."""
    result = resolve_warehouse_coef(
        dlv_prc=0.0, fixed_coef=0.0,
        fixation_end=None, order_date=None,
        warehouse_name="НеизвестныйСклад",
        supabase_tariffs={},
    )
    assert result.value == 0.0


def test_load_supabase_tariffs_calls_client():
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.gte.return_value.lte.return_value.execute.return_value.data = [
        {"warehouse_name": "Коледино", "dt": "2026-03-15", "delivery_coef": 95},
    ]
    with patch("audit.calculators.warehouse_coef_resolver.get_supabase_client", return_value=mock_client):
        result = load_supabase_tariffs(date(2026, 3, 1), date(2026, 3, 31))
    assert "Коледино" in result
    assert result["Коледино"][date(2026, 3, 15)] == 0.95
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
python -m pytest tests/audit/test_warehouse_coef_resolver.py -v
```
Expected: `ImportError: cannot import name 'resolve_warehouse_coef'`

- [ ] **Step 3: Create `audit/calculators/warehouse_coef_resolver.py`**

```python
"""3-tier warehouse coefficient resolution: fixation → Supabase → dlv_prc."""
from __future__ import annotations
import logging
from dataclasses import dataclass
from datetime import date

from shared.supabase import get_supabase_client

logger = logging.getLogger(__name__)


@dataclass
class CoefResult:
    value: float
    source: str   # "fixation" | "supabase" | "dlv_prc"
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
    3. dlv_prc from report (fallback, not verified)
    """
    # Tier 1: Fixed coefficient (fixation active)
    if fixed_coef > 0 and fixation_end and order_date and fixation_end > order_date:
        return CoefResult(value=fixed_coef, source="fixation", verified=True)

    # Tier 2: Supabase historical tariffs
    wh_tariffs = supabase_tariffs.get(warehouse_name)
    if wh_tariffs and order_date:
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

    Returns:
        {warehouse_name: {date: delivery_coef / 100}}
    """
    try:
        client = get_supabase_client()
        rows = (
            client.table("wb_tariffs")
            .select("dt, warehouse_name, delivery_coef")
            .gte("dt", date_from.isoformat())
            .lte("dt", date_to.isoformat())
            .execute()
        ).data or []

        result: dict[str, dict[date, float]] = {}
        for row in rows:
            wh = row["warehouse_name"]
            dt = date.fromisoformat(row["dt"])
            coef = float(row["delivery_coef"]) / 100.0
            if wh not in result:
                result[wh] = {}
            result[wh][dt] = coef
        logger.info("Loaded Supabase tariffs: %d warehouses", len(result))
        return result
    except Exception as e:
        logger.warning("Failed to load Supabase tariffs: %s", e)
        return {}
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
python -m pytest tests/audit/test_warehouse_coef_resolver.py -v
```
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add audit/calculators/warehouse_coef_resolver.py tests/audit/test_warehouse_coef_resolver.py
git commit -m "feat(audit): add warehouse_coef_resolver with Supabase client"
```

---

## Task 6: audit/output — migrate 11 existing sheets

All 11 sheets have only one change: replace `services.logistics_audit.*` import prefix with `audit.*`. Logic is identical.

**Files:**
- Create: `audit/output/__init__.py`
- Create: `audit/output/sheet_overpayment_values.py`
- Create: `audit/output/sheet_overpayment_formulas.py`
- Create: `audit/output/sheet_svod.py`
- Create: `audit/output/sheet_detail.py`
- Create: `audit/output/sheet_il.py`
- Create: `audit/output/sheet_pivot_by_article.py`
- Create: `audit/output/sheet_logistics_types.py`
- Create: `audit/output/sheet_weekly.py`
- Create: `audit/output/sheet_dimensions.py`
- Create: `audit/output/sheet_tariffs_box.py`
- Create: `audit/output/sheet_tariffs_pallet.py`

Source: `~/Projects/Wookiee/services/logistics_audit/output/`

- [ ] **Step 1: Create `audit/output/__init__.py` and copy all 11 sheets**

```bash
mkdir -p ~/Projects/wb-logistics-toolkit/audit/output
touch ~/Projects/wb-logistics-toolkit/audit/output/__init__.py

SRC=~/Projects/Wookiee/services/logistics_audit/output
DST=~/Projects/wb-logistics-toolkit/audit/output

for f in sheet_overpayment_values sheet_overpayment_formulas sheet_svod sheet_detail sheet_il sheet_pivot_by_article sheet_logistics_types sheet_weekly sheet_dimensions sheet_tariffs_box sheet_tariffs_pallet; do
  cp "$SRC/${f}.py" "$DST/${f}.py"
done
```

- [ ] **Step 2: Replace all Wookiee imports with toolkit imports**

```bash
cd ~/Projects/wb-logistics-toolkit/audit/output

# Replace model imports
sed -i '' 's|from services\.logistics_audit\.models\.report_row import|from audit.models.report_row import|g' *.py
sed -i '' 's|from services\.logistics_audit\.models\.tariff_snapshot import|from audit.models.tariff_snapshot import|g' *.py
sed -i '' 's|from services\.logistics_audit\.models|from audit.models|g' *.py

# Replace calculator imports
sed -i '' 's|from services\.logistics_audit\.calculators\.logistics_overpayment import|from audit.calculators.logistics_overpayment import|g' *.py
sed -i '' 's|from services\.logistics_audit\.calculators|from audit.calculators|g' *.py
```

- [ ] **Step 3: Verify imports resolve correctly**

```bash
cd ~/Projects/wb-logistics-toolkit
python -c "
from audit.output.sheet_svod import write_svod
from audit.output.sheet_overpayment_values import write_overpayment_values
from audit.output.sheet_overpayment_formulas import write_overpayment_formulas
from audit.output.sheet_detail import write_detail
from audit.output.sheet_il import write_il
from audit.output.sheet_pivot_by_article import write_pivot_by_article
from audit.output.sheet_logistics_types import write_logistics_types
from audit.output.sheet_weekly import write_weekly
from audit.output.sheet_dimensions import write_dimensions
from audit.output.sheet_tariffs_box import write_tariffs_box
from audit.output.sheet_tariffs_pallet import write_tariffs_pallet
print('All 11 sheets import OK')
"
```
Expected: `All 11 sheets import OK`

- [ ] **Step 4: Commit**

```bash
git add audit/output/__init__.py audit/output/sheet_overpayment_values.py audit/output/sheet_overpayment_formulas.py audit/output/sheet_svod.py audit/output/sheet_detail.py audit/output/sheet_il.py audit/output/sheet_pivot_by_article.py audit/output/sheet_logistics_types.py audit/output/sheet_weekly.py audit/output/sheet_dimensions.py audit/output/sheet_tariffs_box.py audit/output/sheet_tariffs_pallet.py
git commit -m "feat(audit): migrate 11 output sheets with corrected imports"
```

---

## Task 7: audit/output/sheet_recommendations.py

New sheet summarizing overpayments for claims preparation. No equivalent in Wookiee.

**Files:**
- Create: `audit/output/sheet_recommendations.py`
- Create: `tests/audit/test_sheet_recommendations.py`

- [ ] **Step 1: Write failing test**

```python
# tests/audit/test_sheet_recommendations.py
from datetime import date
import openpyxl
from audit.output.sheet_recommendations import write_recommendations
from audit.models.report_row import ReportRow
from audit.calculators.logistics_overpayment import OverpaymentResult


def _make_row(nm_id: int, office: str, delivery_rub: float, order_dt: date) -> ReportRow:
    return ReportRow.from_api({
        "nm_id": nm_id,
        "office_name": office,
        "supplier_oper_name": "Логистика",
        "bonus_type_name": "К клиенту при продаже",
        "delivery_rub": delivery_rub,
        "order_dt": order_dt.isoformat(),
        "realizationreport_id": 1,
    })


def test_write_recommendations_total_row():
    wb = openpyxl.Workbook()
    ws = wb.active
    rows = [
        _make_row(1, "Коледино", 100.0, date(2026, 1, 10)),
        _make_row(2, "Тула", 200.0, date(2026, 2, 5)),
    ]
    results = [
        OverpaymentResult(calculated_cost=60.0, overpayment=40.0),
        OverpaymentResult(calculated_cost=100.0, overpayment=100.0),
    ]
    write_recommendations(ws, rows, results, date(2026, 1, 1), date(2026, 3, 31))
    # Check total overpayment cell exists and is 140
    values = [[ws.cell(r, c).value for c in range(1, 4)] for r in range(1, 20)]
    flat = [v for row in values for v in row if v is not None]
    assert 140.0 in flat or "140.0" in [str(v) for v in flat]


def test_write_recommendations_header_row():
    wb = openpyxl.Workbook()
    ws = wb.active
    write_recommendations(ws, [], [], date(2026, 1, 1), date(2026, 3, 31))
    assert ws.cell(1, 1).value is not None  # has a header
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
python -m pytest tests/audit/test_sheet_recommendations.py -v
```
Expected: `ImportError: cannot import name 'write_recommendations'`

- [ ] **Step 3: Create `audit/output/sheet_recommendations.py`**

```python
"""Sheet 12: 'Рекомендации' — overpayment summary for claims preparation."""
from __future__ import annotations
from collections import defaultdict
from datetime import date

from openpyxl.worksheet.worksheet import Worksheet

from audit.models.report_row import ReportRow
from audit.calculators.logistics_overpayment import OverpaymentResult


def write_recommendations(
    ws: Worksheet,
    logistics_rows: list[ReportRow],
    overpayment_results: list[OverpaymentResult | None],
    date_from: date,
    date_to: date,
) -> None:
    """Write summary for claims/lawsuit preparation.

    Sections:
    1. Overall totals
    2. Top-10 articles by overpayment sum
    3. Top-5 warehouses by overpayment sum
    4. Monthly overpayment trend
    """
    # Aggregate
    total_charged = 0.0
    total_overpay = 0.0
    by_article: dict[int, float] = defaultdict(float)
    by_warehouse: dict[str, float] = defaultdict(float)
    by_month: dict[str, float] = defaultdict(float)

    for row, res in zip(logistics_rows, overpayment_results):
        if res is None or res.overpayment < 0:
            continue
        total_charged += row.delivery_rub
        total_overpay += res.overpayment
        by_article[row.nm_id] += res.overpayment
        by_warehouse[row.office_name] += res.overpayment
        if row.order_dt:
            month_key = row.order_dt.strftime("%Y-%m")
            by_month[month_key] += res.overpayment

    excel_row = 1

    # Section 1: Overall totals
    ws.cell(excel_row, 1, "ОБЩИЙ ИТОГ")
    excel_row += 1
    ws.cell(excel_row, 1, "Период")
    ws.cell(excel_row, 2, f"{date_from.isoformat()} — {date_to.isoformat()}")
    excel_row += 1
    ws.cell(excel_row, 1, "WB удержал за логистику (₽)")
    ws.cell(excel_row, 2, round(total_charged, 2))
    excel_row += 1
    ws.cell(excel_row, 1, "Переплата по нашему расчёту (₽)")
    ws.cell(excel_row, 2, round(total_overpay, 2))
    excel_row += 1
    pct = total_overpay / total_charged * 100 if total_charged else 0
    ws.cell(excel_row, 1, "Доля переплаты (%)")
    ws.cell(excel_row, 2, round(pct, 1))
    excel_row += 2

    # Section 2: Top-10 articles
    ws.cell(excel_row, 1, "ТОП-10 АРТИКУЛОВ ПО СУММЕ ПЕРЕПЛАТЫ")
    excel_row += 1
    ws.cell(excel_row, 1, "Код номенклатуры")
    ws.cell(excel_row, 2, "Переплата (₽)")
    excel_row += 1
    for nm_id, overpay in sorted(by_article.items(), key=lambda x: x[1], reverse=True)[:10]:
        ws.cell(excel_row, 1, nm_id)
        ws.cell(excel_row, 2, round(overpay, 2))
        excel_row += 1
    excel_row += 1

    # Section 3: Top-5 warehouses
    ws.cell(excel_row, 1, "ТОП-5 СКЛАДОВ ПО СУММЕ ПЕРЕПЛАТЫ")
    excel_row += 1
    ws.cell(excel_row, 1, "Склад")
    ws.cell(excel_row, 2, "Переплата (₽)")
    excel_row += 1
    for wh, overpay in sorted(by_warehouse.items(), key=lambda x: x[1], reverse=True)[:5]:
        ws.cell(excel_row, 1, wh)
        ws.cell(excel_row, 2, round(overpay, 2))
        excel_row += 1
    excel_row += 1

    # Section 4: Monthly trend
    ws.cell(excel_row, 1, "ДИНАМИКА ПЕРЕПЛАТ ПО МЕСЯЦАМ")
    excel_row += 1
    ws.cell(excel_row, 1, "Месяц")
    ws.cell(excel_row, 2, "Переплата (₽)")
    excel_row += 1
    for month_key in sorted(by_month):
        ws.cell(excel_row, 1, month_key)
        ws.cell(excel_row, 2, round(by_month[month_key], 2))
        excel_row += 1
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
python -m pytest tests/audit/test_sheet_recommendations.py -v
```
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add audit/output/sheet_recommendations.py tests/audit/test_sheet_recommendations.py
git commit -m "feat(audit): add sheet_recommendations for claims preparation"
```

---

## Task 8: audit/output/excel_generator.py

Wire up all 12 sheets. Add `sheet_recommendations` to workbook. Import change: `services.logistics_audit.*` → `audit.*`.

**Files:**
- Create: `audit/output/excel_generator.py`
- Create: `tests/audit/test_excel_generator.py`

- [ ] **Step 1: Write failing test**

```python
# tests/audit/test_excel_generator.py
import openpyxl
from unittest.mock import patch, MagicMock
from datetime import date
from audit.output.excel_generator import generate_workbook, SHEET_NAMES
from audit.models.audit_config import AuditConfig


def test_sheet_names_count():
    assert len(SHEET_NAMES) == 12


def test_recommendations_sheet_present():
    assert "Рекомендации" in SHEET_NAMES


def test_generate_workbook_creates_12_sheets():
    config = AuditConfig(
        api_key="tok", date_from=date(2026, 1, 1), date_to=date(2026, 3, 31),
        cabinet="OOO",
    )
    with patch("audit.output.excel_generator.write_overpayment_formulas"), \
         patch("audit.output.excel_generator.write_overpayment_values"), \
         patch("audit.output.excel_generator.write_svod"), \
         patch("audit.output.excel_generator.write_detail"), \
         patch("audit.output.excel_generator.write_il"), \
         patch("audit.output.excel_generator.write_pivot_by_article"), \
         patch("audit.output.excel_generator.write_logistics_types"), \
         patch("audit.output.excel_generator.write_weekly"), \
         patch("audit.output.excel_generator.write_dimensions"), \
         patch("audit.output.excel_generator.write_tariffs_box"), \
         patch("audit.output.excel_generator.write_tariffs_pallet"), \
         patch("audit.output.excel_generator.write_recommendations"):
        wb = generate_workbook(
            config=config, all_rows=[], logistics_rows=[],
            overpayment_results=[], coefs=[], card_dims={},
            tariffs_box={}, tariffs_pallet={}, wb_volumes={},
        )
    assert len(wb.sheetnames) == 12
    assert "Рекомендации" in wb.sheetnames
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
python -m pytest tests/audit/test_excel_generator.py -v
```
Expected: `ImportError: cannot import name 'generate_workbook'`

- [ ] **Step 3: Create `audit/output/excel_generator.py`**

```python
"""Main Excel generator — creates workbook with all 12 sheets."""
from __future__ import annotations
import openpyxl
from audit.models.audit_config import AuditConfig
from audit.models.report_row import ReportRow
from audit.models.tariff_snapshot import TariffSnapshot
from audit.calculators.logistics_overpayment import OverpaymentResult
from audit.output.sheet_overpayment_formulas import write_overpayment_formulas
from audit.output.sheet_overpayment_values import write_overpayment_values
from audit.output.sheet_svod import write_svod
from audit.output.sheet_detail import write_detail
from audit.output.sheet_il import write_il
from audit.output.sheet_pivot_by_article import write_pivot_by_article
from audit.output.sheet_logistics_types import write_logistics_types
from audit.output.sheet_weekly import write_weekly
from audit.output.sheet_dimensions import write_dimensions
from audit.output.sheet_tariffs_box import write_tariffs_box
from audit.output.sheet_tariffs_pallet import write_tariffs_pallet
from audit.output.sheet_recommendations import write_recommendations

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
    "Рекомендации",
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
    row_ils: list[float] | None = None,
) -> openpyxl.Workbook:
    """Generate the full 12-sheet Excel workbook."""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    sheets = {name: wb.create_sheet(name) for name in SHEET_NAMES}

    overpay_by_report: dict[int, float] = {}
    for row, res in zip(logistics_rows, overpayment_results):
        if res is not None and res.overpayment >= 0:
            rid = row.realizationreport_id
            overpay_by_report[rid] = overpay_by_report.get(rid, 0) + res.overpayment

    volumes = {nm: d["volume"] for nm, d in card_dims.items()}

    write_overpayment_formulas(
        sheets["Переплата по логистике (короб)"], logistics_rows,
        ktr=config.ktr, base_1l=46.0, extra_l=14.0,
        row_ils=row_ils,
    )
    write_overpayment_values(
        sheets["Переплата по логистике"], logistics_rows,
        overpayment_results, volumes, coefs, row_ils=row_ils,
    )
    write_svod(sheets["СВОД"], all_rows, overpay_by_report)
    write_detail(sheets["Детализация"], all_rows)
    write_il(sheets["ИЛ"], il_data)
    write_pivot_by_article(sheets["Переплата по артикулам"], logistics_rows, overpayment_results)
    write_logistics_types(sheets["Виды логистики"], logistics_rows)
    write_weekly(sheets["Еженед. отчет"], all_rows)
    write_dimensions(sheets["Габариты в карточке"], card_dims)
    write_tariffs_box(sheets["Тарифы короб"], tariffs_box)
    write_tariffs_pallet(sheets["Тариф монопалета"], tariffs_pallet)
    write_recommendations(
        sheets["Рекомендации"], logistics_rows, overpayment_results,
        config.date_from, config.date_to,
    )
    return wb
```

- [ ] **Step 4: Run test — expect PASS**

```bash
python -m pytest tests/audit/test_excel_generator.py -v
```
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add audit/output/excel_generator.py tests/audit/test_excel_generator.py
git commit -m "feat(audit): add excel_generator with 12 sheets incl. Рекомендации"
```

---

## Task 9: audit/etl — tariff_collector and import_coeff_table

**Files:**
- Create: `audit/etl/__init__.py`
- Create: `audit/etl/tariff_collector.py`
- Create: `audit/etl/import_coeff_table.py`
- Create: `tests/audit/test_etl.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/audit/test_etl.py
from datetime import date
from unittest.mock import patch, MagicMock
from audit.etl.tariff_collector import build_upsert_rows
from audit.etl.import_coeff_table import COEFF_TABLE


def test_build_upsert_rows_from_api_list():
    raw_tariffs = [
        {
            "warehouseName": "Коледино",
            "boxDeliveryBase": "46,0",
            "boxDeliveryLiter": "14,0",
            "boxDeliveryCoefExpr": "95",
            "boxStorageBase": "0",
            "boxStorageLiter": "0",
            "boxStorageCoefExpr": "0",
        }
    ]
    rows = build_upsert_rows(date(2026, 5, 1), raw_tariffs)
    assert len(rows) == 1
    assert rows[0]["warehouse_name"] == "Коледино"
    assert rows[0]["delivery_coef"] == 95
    assert rows[0]["logistics_1l"] == 46.0
    assert rows[0]["dt"] == "2026-05-01"


def test_build_upsert_rows_empty():
    assert build_upsert_rows(date(2026, 5, 1), []) == []


def test_coeff_table_has_20_rows():
    assert len(COEFF_TABLE) == 20


def test_coeff_table_covers_full_range():
    """COEFF_TABLE covers 0–100% with no gaps."""
    for row in COEFF_TABLE:
        assert "min_loc" in row and "max_loc" in row
        assert "ktr" in row and "krp_pct" in row
    # first row should cover top tier
    top = max(COEFF_TABLE, key=lambda r: r["min_loc"])
    assert top["min_loc"] == 95.0
    assert top["ktr"] == 0.50
    # last row should cover bottom tier
    bottom = min(COEFF_TABLE, key=lambda r: r["min_loc"])
    assert bottom["min_loc"] == 0.0
    assert bottom["ktr"] == 2.20
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
python -m pytest tests/audit/test_etl.py -v
```
Expected: `ImportError: cannot import name 'build_upsert_rows'`

- [ ] **Step 3: Create `audit/etl/__init__.py`**

```bash
touch audit/etl/__init__.py
```

- [ ] **Step 4: Create `audit/etl/tariff_collector.py`**

Rewritten with WBClient pattern (no data_layer, no ToolLogger):

```python
"""Daily ETL: fetch WB box tariffs → upsert into Supabase wb_tariffs.

Usage:
    python audit/etl/tariff_collector.py                    # today
    python audit/etl/tariff_collector.py --date 2026-03-20
    python audit/etl/tariff_collector.py --backfill 30
    python audit/etl/tariff_collector.py --cabinet ip
"""
from __future__ import annotations

import argparse
import logging
from datetime import date, timedelta

from shared.config import get_cabinet
from shared.supabase import get_supabase_client
from shared.wb_api.client import WBClient
from shared.wb_api.tariffs import fetch_box_tariffs
from audit.models.tariff_snapshot import TariffSnapshot

logger = logging.getLogger(__name__)


def build_upsert_rows(dt: date, raw_tariffs: list[dict]) -> list[dict]:
    """Convert raw API tariff list to Supabase upsert dicts."""
    rows = []
    for d in raw_tariffs:
        snap = TariffSnapshot.from_api(d)
        rows.append({
            "dt": dt.isoformat(),
            "warehouse_name": snap.warehouse_name,
            "delivery_coef": snap.delivery_coef_pct,
            "logistics_1l": snap.box_delivery_base,
            "logistics_extra_l": snap.box_delivery_liter,
            "box_storage_base": snap.box_storage_base,
            "storage_coef": snap.storage_coef_pct,
            "geo_name": snap.geo_name,
        })
    return rows


def collect_tariffs(dt: date, cabinet_name: str) -> int:
    """Fetch tariffs for a single date and upsert into Supabase. Returns row count."""
    cab = get_cabinet(cabinet_name)
    client = WBClient(token=cab.wb_token)
    raw = fetch_box_tariffs(client, dt.isoformat())
    if not raw:
        logger.warning("No tariffs returned for %s", dt)
        return 0

    rows = build_upsert_rows(dt, raw)
    supabase = get_supabase_client()
    result = (
        supabase.table("wb_tariffs")
        .upsert(rows, on_conflict="dt,warehouse_name")
        .execute()
    )
    count = len(result.data or [])
    logger.info("Upserted %d warehouse tariffs for %s", count, dt)
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="WB Tariff Collector → Supabase")
    parser.add_argument("--date", type=str, default=None)
    parser.add_argument("--backfill", type=int, default=None, help="Backfill last N days")
    parser.add_argument("--cabinet", type=str, default="ooo")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    if args.backfill:
        total = 0
        for i in range(args.backfill):
            dt = date.today() - timedelta(days=i)
            total += collect_tariffs(dt, args.cabinet)
        logger.info("Backfill complete: %d total rows across %d days", total, args.backfill)
    else:
        dt = date.fromisoformat(args.date) if args.date else date.today()
        collect_tariffs(dt, args.cabinet)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Create `audit/etl/import_coeff_table.py`**

Bootstraps `wb_coeff_table` in Supabase from the official WB КТР/КРП table (verified data from Wookiee):

```python
"""Bootstrap wb_coeff_table in Supabase with current WB КТР/КРП coefficients.

Usage:
    python audit/etl/import_coeff_table.py                    # use default valid_from
    python audit/etl/import_coeff_table.py --valid-from 2026-03-27
"""
from __future__ import annotations

import argparse
import logging

from shared.supabase import get_supabase_client

logger = logging.getLogger(__name__)

# KTR/KRP table effective from 27.03.2026 (source: WB Partners → Тарифы)
COEFF_TABLE: list[dict] = [
    {"min_loc": 95.00, "max_loc": 100.00, "ktr": 0.50, "krp_pct": 0.00},
    {"min_loc": 90.00, "max_loc":  94.99, "ktr": 0.60, "krp_pct": 0.00},
    {"min_loc": 85.00, "max_loc":  89.99, "ktr": 0.70, "krp_pct": 0.00},
    {"min_loc": 80.00, "max_loc":  84.99, "ktr": 0.80, "krp_pct": 0.00},
    {"min_loc": 75.00, "max_loc":  79.99, "ktr": 0.90, "krp_pct": 0.00},
    {"min_loc": 70.00, "max_loc":  74.99, "ktr": 1.00, "krp_pct": 0.00},
    {"min_loc": 65.00, "max_loc":  69.99, "ktr": 1.00, "krp_pct": 0.00},
    {"min_loc": 60.00, "max_loc":  64.99, "ktr": 1.00, "krp_pct": 0.00},
    {"min_loc": 55.00, "max_loc":  59.99, "ktr": 1.05, "krp_pct": 2.00},
    {"min_loc": 50.00, "max_loc":  54.99, "ktr": 1.10, "krp_pct": 2.05},
    {"min_loc": 45.00, "max_loc":  49.99, "ktr": 1.20, "krp_pct": 2.05},
    {"min_loc": 40.00, "max_loc":  44.99, "ktr": 1.30, "krp_pct": 2.10},
    {"min_loc": 35.00, "max_loc":  39.99, "ktr": 1.40, "krp_pct": 2.10},
    {"min_loc": 30.00, "max_loc":  34.99, "ktr": 1.60, "krp_pct": 2.15},
    {"min_loc": 25.00, "max_loc":  29.99, "ktr": 1.70, "krp_pct": 2.20},
    {"min_loc": 20.00, "max_loc":  24.99, "ktr": 1.80, "krp_pct": 2.25},
    {"min_loc": 15.00, "max_loc":  19.99, "ktr": 1.90, "krp_pct": 2.30},
    {"min_loc": 10.00, "max_loc":  14.99, "ktr": 2.00, "krp_pct": 2.35},
    {"min_loc":  5.00, "max_loc":   9.99, "ktr": 2.10, "krp_pct": 2.45},
    {"min_loc":  0.00, "max_loc":   4.99, "ktr": 2.20, "krp_pct": 2.50},
]

DEFAULT_VALID_FROM = "2026-03-27"


def import_coeff_table(valid_from: str = DEFAULT_VALID_FROM) -> int:
    """Upsert COEFF_TABLE into wb_coeff_table with the given valid_from date.

    Returns number of rows upserted.
    """
    client = get_supabase_client()
    rows = [{"valid_from": valid_from, **row} for row in COEFF_TABLE]
    result = (
        client.table("wb_coeff_table")
        .upsert(rows, on_conflict="valid_from,min_loc")
        .execute()
    )
    count = len(result.data or [])
    logger.info("Upserted %d KTR/KRP rows with valid_from=%s", count, valid_from)
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap wb_coeff_table in Supabase")
    parser.add_argument("--valid-from", type=str, default=DEFAULT_VALID_FROM)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    count = import_coeff_table(args.valid_from)
    print(f"Done: {count} rows upserted")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run tests — expect PASS**

```bash
python -m pytest tests/audit/test_etl.py -v
```
Expected: `4 passed`

- [ ] **Step 7: Commit**

```bash
git add audit/etl/__init__.py audit/etl/tariff_collector.py audit/etl/import_coeff_table.py tests/audit/test_etl.py
git commit -m "feat(audit): add ETL — tariff_collector and import_coeff_table"
```

---

## Task 10: audit/run_audit.py

CLI entry point. Uses toolkit API clients, shared config, no Wookiee dependencies.

**Files:**
- Create: `audit/run_audit.py`
- Create: `tests/audit/test_run_audit.py`

- [ ] **Step 1: Write failing test**

```python
# tests/audit/test_run_audit.py
import pytest
from unittest.mock import patch, MagicMock
from datetime import date
from audit.run_audit import _parse_args, run_audit
from audit.models.audit_config import AuditConfig


def test_parse_args_basic():
    args = _parse_args(["ooo", "2026-01-01", "2026-03-31"])
    assert args.cabinet == "ooo"
    assert args.date_from == "2026-01-01"
    assert args.date_to == "2026-03-31"
    assert args.ktr == 1.0


def test_parse_args_with_ktr():
    args = _parse_args(["ooo", "2026-01-01", "2026-03-31", "--ktr", "0.8"])
    assert args.ktr == 0.8


def test_run_audit_returns_path():
    config = AuditConfig(
        api_key="tok", date_from=date(2026, 1, 1), date_to=date(2026, 3, 31),
        cabinet="OOO",
    )
    mock_wb = MagicMock()
    with patch("audit.run_audit.WBClient"), \
         patch("audit.run_audit.fetch_report", return_value=[]), \
         patch("audit.run_audit.fetch_box_tariffs", return_value=[]), \
         patch("audit.run_audit.fetch_pallet_tariffs", return_value=[]), \
         patch("audit.run_audit.fetch_nm_volumes", return_value={}), \
         patch("audit.run_audit.fetch_orders", return_value=[]), \
         patch("audit.run_audit.fetch_warehouse_remains", return_value=[]), \
         patch("audit.run_audit.fetch_measurement_penalties", return_value=[]), \
         patch("audit.run_audit.fetch_deductions", return_value=[]), \
         patch("audit.run_audit.load_supabase_tariffs", return_value={}), \
         patch("audit.run_audit.calculate_weekly_il", return_value=({}, [])), \
         patch("audit.run_audit.generate_workbook", return_value=mock_wb):
        path = run_audit(config, output_dir="/tmp")
    assert "Аудит логистики" in path
    assert path.endswith(".xlsx")
    mock_wb.save.assert_called_once()
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
python -m pytest tests/audit/test_run_audit.py -v
```
Expected: `ImportError: cannot import name '_parse_args'`

- [ ] **Step 3: Create `audit/run_audit.py`**

```python
"""Logistics audit pipeline: fetch → calculate → Excel.

Usage:
    python audit/run_audit.py ooo 2026-01-01 2026-03-31
    python audit/run_audit.py ooo 2026-01-01 2026-03-31 --ktr 0.9
"""
from __future__ import annotations

import argparse
import logging
from datetime import date, timedelta
from pathlib import Path

from shared.config import get_cabinet
from shared.wb_api.client import WBClient
from shared.wb_api.reports import fetch_report
from shared.wb_api.tariffs import fetch_box_tariffs, fetch_pallet_tariffs
from shared.wb_api.content import fetch_nm_volumes
from shared.wb_api.orders import fetch_orders
from shared.wb_api.warehouse_remains import fetch_warehouse_remains
from shared.wb_api.penalties import fetch_measurement_penalties, fetch_deductions
from audit.models.audit_config import AuditConfig
from audit.models.report_row import ReportRow
from audit.models.tariff_snapshot import TariffSnapshot
from audit.calculators.tariff_periods import get_base_tariffs
from audit.calculators.warehouse_coef_resolver import resolve_warehouse_coef, load_supabase_tariffs
from audit.calculators.logistics_overpayment import (
    calculate_row_overpayment, OverpaymentResult, FORMULA_CHANGE_DATE,
)
from audit.calculators.weekly_il_calculator import calculate_weekly_il, get_il_for_date
from audit.calculators.localization_resolver import calculate_sku_localization
from audit.output.excel_generator import generate_workbook

logger = logging.getLogger(__name__)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WB Logistics Audit")
    parser.add_argument("cabinet", help="Cabinet name (matches cabinets.yaml)")
    parser.add_argument("date_from", help="Audit start date YYYY-MM-DD")
    parser.add_argument("date_to", help="Audit end date YYYY-MM-DD")
    parser.add_argument("--ktr", type=float, default=1.0, help="Manual KTR override (default 1.0)")
    parser.add_argument("--output-dir", type=str, default=".", help="Output directory for Excel")
    return parser.parse_args(argv)


def run_audit(config: AuditConfig, output_dir: str = ".") -> str:
    """Run full logistics audit pipeline. Returns path to generated Excel file."""
    df = config.date_from.isoformat()
    dt = config.date_to.isoformat()
    logger.info("Starting audit: %s → %s, cabinet=%s", df, dt, config.cabinet)

    client = WBClient(token=config.api_key)

    # Step 1: Fetch all data
    logger.info("Fetching reportDetailByPeriod...")
    raw_rows = fetch_report(client, df, dt)
    all_rows = [ReportRow.from_api(d) for d in raw_rows]
    logger.info("Total rows: %d", len(all_rows))

    logger.info("Fetching tariffs...")
    raw_box = fetch_box_tariffs(client, dt)
    tariffs_box: dict[str, TariffSnapshot] = {
        TariffSnapshot.from_api(d).warehouse_name: TariffSnapshot.from_api(d)
        for d in raw_box
    }
    tariffs_pallet = fetch_pallet_tariffs(client, dt)

    logger.info("Fetching card dimensions...")
    nm_ids = list({row.nm_id for row in all_rows if row.nm_id})
    volumes_raw = fetch_nm_volumes(client, nm_ids)
    card_dims: dict[int, dict] = {nm: {"volume": v} for nm, v in volumes_raw.items()}

    logger.info("Fetching warehouse remains...")
    wb_volumes_raw = fetch_warehouse_remains(client)
    wb_volumes: dict[int, float] = {}
    for item in wb_volumes_raw:
        nm_id = item.get("nmId", 0)
        if nm_id:
            wb_volumes[nm_id] = float(item.get("volume", 0))

    logger.info("Fetching penalties...")
    dt_rfc3339 = f"{dt}T23:59:59Z"
    penalties = fetch_measurement_penalties(client, dt_rfc3339)
    deductions = fetch_deductions(client, dt_rfc3339)
    logger.info("Penalties: %d, Deductions: %d", len(penalties), len(deductions))

    # Step 2: Filter logistics rows
    logistics_rows = [r for r in all_rows if r.is_logistics]
    logger.info("Logistics rows: %d", len(logistics_rows))

    # Step 3: Weekly IL from orders
    logger.info("Fetching orders for weekly IL...")
    orders_from = (config.date_from - timedelta(days=7)).isoformat()
    orders = fetch_orders(client, orders_from)
    logger.info("Orders fetched: %d", len(orders))
    week_to_il, il_data = calculate_weekly_il(orders, config.date_from, config.date_to)

    # Step 4: Per-SKU localization (for new formula rows >= 23.03.2026)
    has_new_formula = any(
        r.order_dt and r.order_dt >= FORMULA_CHANGE_DATE for r in logistics_rows
    )
    sku_localization: dict[int, float] = {}
    prices: dict[int, float] = {}
    if has_new_formula:
        logger.info("New formula rows detected, calculating per-SKU localization...")
        sku_localization = calculate_sku_localization(orders)
        logger.info("Localization data for %d SKUs", len(sku_localization))

    # Step 5: Load Supabase historical tariffs
    logger.info("Loading Supabase tariffs...")
    supabase_tariffs = load_supabase_tariffs(config.date_from, config.date_to)

    # Step 6: Calculate per-row overpayments
    results: list[OverpaymentResult | None] = []
    coefs: list[float] = []
    row_ils: list[float] = []

    for row in logistics_rows:
        vol = card_dims.get(row.nm_id, {}).get("volume", 0)

        coef_result = resolve_warehouse_coef(
            dlv_prc=row.dlv_prc,
            fixed_coef=row.dlv_prc,
            fixation_end=row.fix_tariff_date_to,
            order_date=row.order_dt,
            warehouse_name=row.office_name,
            supabase_tariffs=supabase_tariffs,
        )
        coefs.append(coef_result.value)

        base_1l, extra_l = get_base_tariffs(
            order_date=row.order_dt,
            fixation_start=row.fix_tariff_date_from,
            fixation_end=row.fix_tariff_date_to,
            volume=vol,
        )

        row_il = get_il_for_date(week_to_il, row.order_dt)
        if row_il is None:
            row_il = config.ktr if config.ktr > 0 else 1.0
        row_ils.append(row_il)

        result = calculate_row_overpayment(
            delivery_rub=row.delivery_rub,
            volume=vol,
            coef=coef_result.value,
            base_1l=base_1l,
            extra_l=extra_l,
            order_dt=row.order_dt,
            ktr_manual=row_il,
            is_fixed_rate=row.is_fixed_rate,
            is_forward_delivery=row.is_forward_delivery,
            sku_localization_pct=sku_localization.get(row.nm_id),
            retail_price=prices.get(row.nm_id, 0.0),
        )
        results.append(result)

    total_charged = sum(r.delivery_rub for r in logistics_rows)
    if total_charged > 0:
        total_overpay = sum(res.overpayment for res in results if res is not None)
        logger.info(
            "WB charged: %.2f₽ | Calculated overpayment: %.2f₽ (%.1f%%)",
            total_charged, total_overpay, total_overpay / total_charged * 100,
        )

    # Step 7: Generate Excel
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
        il_data=il_data,
        row_ils=row_ils,
    )

    filename = f"Аудит логистики {df} — {dt}.xlsx"
    filepath = str(Path(output_dir) / filename)
    wb.save(filepath)
    logger.info("Excel saved: %s", filepath)
    return filepath


def main() -> None:
    args = _parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    cab = get_cabinet(args.cabinet)
    config = AuditConfig(
        api_key=cab.wb_token,
        date_from=date.fromisoformat(args.date_from),
        date_to=date.fromisoformat(args.date_to),
        ktr=args.ktr,
        cabinet=args.cabinet,
    )
    output = run_audit(config, output_dir=args.output_dir)
    print(f"Done: {output}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test — expect PASS**

```bash
python -m pytest tests/audit/test_run_audit.py -v
```
Expected: `3 passed`

- [ ] **Step 5: Run full test suite**

```bash
python -m pytest tests/ -v
```
Expected: all existing tests still pass + new audit tests pass

- [ ] **Step 6: Verify imports end-to-end**

```bash
python -c "from audit.run_audit import run_audit, _parse_args; print('run_audit imports OK')"
```
Expected: `run_audit imports OK`

- [ ] **Step 7: Commit**

```bash
git add audit/run_audit.py tests/audit/test_run_audit.py
git commit -m "feat(audit): add run_audit.py — full audit pipeline CLI entry point"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| `shared/wb_api/tariffs.py` (tariffs + pallet) | Task 1 |
| `shared/wb_api/penalties.py` | Task 1 |
| `audit/models/` (3 dataclasses + cabinet field) | Task 2 |
| `audit/calculators/tariff_periods.py` | Task 3 |
| `audit/calculators/dimensions_checker.py` | Task 3 |
| `audit/calculators/logistics_overpayment.py` | Task 4 |
| `audit/calculators/localization_resolver.py` | Task 4 |
| `audit/calculators/weekly_il_calculator.py` | Task 4 |
| `audit/calculators/warehouse_coef_resolver.py` | Task 5 |
| 11 output sheets (import changes) | Task 6 |
| `audit/output/sheet_recommendations.py` (new) | Task 7 |
| `audit/output/excel_generator.py` (12 sheets) | Task 8 |
| `audit/etl/tariff_collector.py` | Task 9 |
| `audit/etl/import_coeff_table.py` | Task 9 |
| `audit/run_audit.py` CLI | Task 10 |
| `il_overrides.json` removed | `run_audit.py` never passes overrides |

**Placeholder check:** None found.

**Type consistency check:**
- `TariffSnapshot.from_api(d)` used in Task 2, Task 9 — same signature
- `OverpaymentResult` from Task 4 used in Task 7, Task 8 — same import path `audit.calculators.logistics_overpayment`
- `fetch_box_tariffs(client, date)` returns `list[dict]` in Task 1 → `TariffSnapshot.from_api()` applied in Task 10 — consistent
- `generate_workbook(config, ...)` signature in Task 8 matches call in Task 10
