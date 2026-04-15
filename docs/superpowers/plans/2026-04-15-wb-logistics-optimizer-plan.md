# WB Logistics Optimizer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix cabinet mixing bug, add per-article ИЛ/ИРП analysis with price impact to the WB logistics optimizer, rename Vasily → WB Logistics.

**Architecture:** Three independent blocks executed sequentially: (1) cabinet-filter SQL fix, (2) new `il_irp_analyzer.py` calculator + Sheets export, (3) rename. All share the same data pipeline in `run_localization.py`. Module 2 reuses existing `irp_coefficients.py` and `wb_localization_mappings.py`.

**Tech Stack:** Python 3.11, psycopg2 (Supabase), pandas, gspread (Google Sheets), WB supplier/orders API.

---

## File Structure

| File | Responsibility |
|------|---------------|
| `shared/data_layer/sku_mapping.py` | **Modify**: add `cabinet_name` param to 3 functions |
| `services/wb_localization/generate_localization_report_v3.py` | **Modify**: `load_statuses()` accepts `cabinet_name` |
| `services/wb_localization/run_localization.py` | **Modify**: per-cabinet loading, Module 2 integration |
| `services/wb_localization/calculators/il_irp_analyzer.py` | **Create**: Module 2 — per-article ИЛ/ИРП analysis |
| `services/wb_localization/sheets_export.py` | **Modify**: add `_write_il_analysis()` and `_write_reference()` |
| `services/wb_localization/config.py` | **Modify**: new env vars with fallback |
| `services/vasily_api/` → `services/wb_logistics_api/` | **Rename**: folder + update imports |
| `tests/wb_localization/test_il_irp_analyzer.py` | **Create**: unit tests for Module 2 |
| `tests/wb_localization/test_cabinet_filter.py` | **Create**: cabinet separation tests |

---

### Task 1: Cabinet Filter — sku_mapping.py

**Files:**
- Modify: `shared/data_layer/sku_mapping.py:24-67` (`get_artikuly_statuses`)
- Modify: `shared/data_layer/sku_mapping.py:70-104` (`get_artikul_to_submodel_mapping`)
- Modify: `shared/data_layer/sku_mapping.py:107-141` (`get_nm_to_article_mapping`)
- Create: `tests/wb_localization/test_cabinet_filter.py`

- [ ] **Step 1: Write test for cabinet-filtered statuses**

```python
# tests/wb_localization/test_cabinet_filter.py
"""Tests for cabinet-filtered SKU queries."""
import pytest
from unittest.mock import patch, MagicMock


def _make_mock_cursor(rows):
    """Helper: return a mock cursor that yields given rows."""
    cur = MagicMock()
    cur.fetchall.return_value = rows
    return cur


class TestGetArtikulyStatuses:
    """get_artikuly_statuses with optional cabinet_name."""

    @patch("shared.data_layer.sku_mapping.psycopg2.connect")
    def test_no_filter_returns_all(self, mock_connect):
        """Without cabinet_name, returns all articles."""
        rows = [
            ("vuki/black", "Продается", "Vuki"),
            ("ruby/red", "Выводим", "Ruby"),
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = _make_mock_cursor(rows)
        mock_connect.return_value = mock_conn

        from shared.data_layer.sku_mapping import get_artikuly_statuses
        result = get_artikuly_statuses()

        assert len(result) == 2
        assert result["vuki/black"] == "Продается"
        assert result["ruby/red"] == "Выводим"

        # Verify no WHERE clause in query
        executed_query = mock_conn.cursor().execute.call_args[0][0]
        assert "WHERE" not in executed_query

    @patch("shared.data_layer.sku_mapping.psycopg2.connect")
    def test_filter_by_cabinet_adds_where(self, mock_connect):
        """With cabinet_name='ИП', query includes importer filter."""
        rows = [("vuki/black", "Продается", "Vuki")]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = _make_mock_cursor(rows)
        mock_connect.return_value = mock_conn

        from shared.data_layer.sku_mapping import get_artikuly_statuses
        result = get_artikuly_statuses(cabinet_name="ИП")

        assert len(result) == 1

        # Verify WHERE clause with importer join
        call_args = mock_conn.cursor().execute.call_args
        executed_query = call_args[0][0]
        assert "importery" in executed_query.lower() or "importer" in executed_query.lower()
        assert "WHERE" in executed_query


class TestGetNmToArticleMapping:
    """get_nm_to_article_mapping with optional cabinet_name."""

    @patch("shared.data_layer.sku_mapping.psycopg2.connect")
    def test_filter_by_cabinet(self, mock_connect):
        """With cabinet_name, query includes importer join."""
        rows = [(12345, "vuki/black")]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = _make_mock_cursor(rows)
        mock_connect.return_value = mock_conn

        from shared.data_layer.sku_mapping import get_nm_to_article_mapping
        result = get_nm_to_article_mapping(cabinet_name="ООО")

        call_args = mock_conn.cursor().execute.call_args
        executed_query = call_args[0][0]
        assert "importery" in executed_query.lower() or "importer" in executed_query.lower()


class TestGetArtikulToSubmodelMapping:
    """get_artikul_to_submodel_mapping with optional cabinet_name."""

    @patch("shared.data_layer.sku_mapping.psycopg2.connect")
    def test_filter_by_cabinet(self, mock_connect):
        """With cabinet_name, query includes importer join."""
        rows = [("vuki/black", "VukiW", "Vuki")]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = _make_mock_cursor(rows)
        mock_connect.return_value = mock_conn

        from shared.data_layer.sku_mapping import get_artikul_to_submodel_mapping
        result = get_artikul_to_submodel_mapping(cabinet_name="ИП")

        call_args = mock_conn.cursor().execute.call_args
        executed_query = call_args[0][0]
        assert "importery" in executed_query.lower() or "importer" in executed_query.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/wb_localization/test_cabinet_filter.py -v`
Expected: FAIL — `get_artikuly_statuses()` doesn't accept `cabinet_name` parameter.

- [ ] **Step 3: Implement cabinet filter in `get_artikuly_statuses()`**

In `shared/data_layer/sku_mapping.py`, replace the function signature and query building (lines 24-67):

```python
def get_artikuly_statuses(cabinet_name: str | None = None) -> dict[str, str]:
    """Получение статусов артикулов из Supabase.

    Args:
        cabinet_name: "ИП" или "ООО" для фильтрации по кабинету.
                      None = все артикулы (backward compat).
    """
    if os.path.exists(SUPABASE_ENV_PATH):
        load_dotenv(SUPABASE_ENV_PATH)

    supabase_config = {
        'host': os.getenv('POSTGRES_HOST', 'aws-0-eu-central-1.pooler.supabase.com'),
        'port': int(os.getenv('POSTGRES_PORT', 6543)),
        'database': os.getenv('POSTGRES_DB', 'postgres'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', '')
    }

    try:
        conn = psycopg2.connect(**supabase_config)
        cur = conn.cursor()

        query = """
        SELECT
            a.artikul,
            s.nazvanie as status,
            mo.kod as model_osnova
        FROM artikuly a
        LEFT JOIN statusy s ON a.status_id = s.id
        LEFT JOIN modeli m ON a.model_id = m.id
        LEFT JOIN modeli_osnova mo ON m.model_osnova_id = mo.id
        """
        params: tuple = ()
        if cabinet_name:
            query += """
            JOIN importery i ON m.importer_id = i.id
            WHERE i.nazvanie LIKE %s
            """
            params = (f"%{cabinet_name}%",)

        cur.execute(query, params)
        results = cur.fetchall()

        cur.close()
        conn.close()

        statuses = {}
        for row in results:
            article = row[0]
            status = row[1]
            statuses[article.lower()] = status

        return statuses
    except Exception as e:
        print(f"Предупреждение: не удалось подключиться к Supabase: {e}")
        return {}
```

- [ ] **Step 4: Implement cabinet filter in `get_artikul_to_submodel_mapping()`**

In `shared/data_layer/sku_mapping.py`, replace lines 70-104:

```python
def get_artikul_to_submodel_mapping(cabinet_name: str | None = None) -> dict:
    """Маппинг артикул → kod модели из Supabase (VukiN, VukiW, RubyP, ...).

    Args:
        cabinet_name: "ИП" или "ООО" для фильтрации. None = все.

    Returns: {"компбел-ж-бесшов/leo_brown": "VukiN", ...}
    """
    if os.path.exists(SUPABASE_ENV_PATH):
        load_dotenv(SUPABASE_ENV_PATH)

    supabase_config = {
        'host': os.getenv('POSTGRES_HOST', 'aws-0-eu-central-1.pooler.supabase.com'),
        'port': int(os.getenv('POSTGRES_PORT', 6543)),
        'database': os.getenv('POSTGRES_DB', 'postgres'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', '')
    }

    try:
        conn = psycopg2.connect(**supabase_config)
        cur = conn.cursor()

        query = """
            SELECT a.artikul, m.kod as model_kod, mo.kod as osnova_kod
            FROM artikuly a
            JOIN modeli m ON a.model_id = m.id
            JOIN modeli_osnova mo ON m.model_osnova_id = mo.id
        """
        params: tuple = ()
        if cabinet_name:
            query += """
            JOIN importery i ON m.importer_id = i.id
            WHERE i.nazvanie LIKE %s
            """
            params = (f"%{cabinet_name}%",)

        cur.execute(query, params)
        result = {}
        for row in cur.fetchall():
            result[row[0].lower()] = {'model_kod': row[1], 'osnova_kod': row[2]}
        cur.close()
        conn.close()
        return result
    except Exception as e:
        print(f"Предупреждение: не удалось получить маппинг подмоделей: {e}")
        return {}
```

- [ ] **Step 5: Implement cabinet filter in `get_nm_to_article_mapping()`**

In `shared/data_layer/sku_mapping.py`, replace lines 107-141:

```python
def get_nm_to_article_mapping(cabinet_name: str | None = None) -> dict:
    """Маппинг WB nm_id → artikul из Supabase.

    Args:
        cabinet_name: "ИП" или "ООО" для фильтрации. None = все.

    Returns: {123456: 'vuki/black', ...}
    """
    if os.path.exists(SUPABASE_ENV_PATH):
        load_dotenv(SUPABASE_ENV_PATH)

    supabase_config = {
        'host': os.getenv('POSTGRES_HOST', 'aws-0-eu-central-1.pooler.supabase.com'),
        'port': int(os.getenv('POSTGRES_PORT', 6543)),
        'database': os.getenv('POSTGRES_DB', 'postgres'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', '')
    }

    try:
        conn = psycopg2.connect(**supabase_config)
        cur = conn.cursor()

        query = """
            SELECT a.nomenklatura_wb, LOWER(a.artikul)
            FROM artikuly a
            WHERE a.nomenklatura_wb IS NOT NULL
        """
        params: tuple = ()
        if cabinet_name:
            query += """
            AND EXISTS (
                SELECT 1 FROM modeli m
                JOIN importery i ON m.importer_id = i.id
                WHERE m.id = a.model_id AND i.nazvanie LIKE %s
            )
            """
            params = (f"%{cabinet_name}%",)

        cur.execute(query, params)
        result = {}
        for row in cur.fetchall():
            if row[0]:
                result[int(row[0])] = row[1]
        cur.close()
        conn.close()
        return result
    except Exception as e:
        print(f"Предупреждение: не удалось получить маппинг nm_id → artikul: {e}")
        return {}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/wb_localization/test_cabinet_filter.py -v`
Expected: All 4 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add shared/data_layer/sku_mapping.py tests/wb_localization/test_cabinet_filter.py
git commit -m "fix: add cabinet_name filter to sku_mapping.py queries

Adds optional cabinet_name parameter to get_artikuly_statuses(),
get_artikul_to_submodel_mapping(), get_nm_to_article_mapping().
Filters via JOIN importery WHERE nazvanie LIKE '%ИП%' or '%ООО%'.
None = backward compatible (no filter)."
```

---

### Task 2: Wire cabinet filter into Vasily pipeline

**Files:**
- Modify: `services/wb_localization/generate_localization_report_v3.py:231-261` (`load_statuses`)
- Modify: `services/wb_localization/run_localization.py:720-729` (main loop)

- [ ] **Step 1: Update `load_statuses()` to accept `cabinet_name`**

In `services/wb_localization/generate_localization_report_v3.py`, find the `load_statuses` function (around line 231) and add `cabinet_name` parameter:

```python
def load_statuses(skip=False, cabinet_name: str | None = None):
    """
    Загрузка статусов артикулов из Supabase (graceful degradation).

    Args:
        skip: пропустить загрузку
        cabinet_name: "ИП" или "ООО" для фильтрации по кабинету

    Возвращает dict: {article_lowercase: status}
    """
    if skip:
        print("2.5. Статусы: пропущено (--no-statuses)")
        return {}

    if not HAS_DATA_LAYER:
        print("2.5. Статусы: data_layer не найден, продолжаем без статусов")
        return {}

    print(f"2.5. Загрузка статусов из Supabase{f' ({cabinet_name})' if cabinet_name else ''}...")
    try:
        statuses = get_artikuly_statuses(cabinet_name=cabinet_name)
        print(f"   Загружено: {len(statuses)} артикулов")
        return statuses
    except Exception as e:
        print(f"   Ошибка загрузки статусов: {e}")
        return {}
```

- [ ] **Step 2: Update `run_localization.py` main loop — per-cabinet loading**

In `services/wb_localization/run_localization.py`, replace lines 720-731:

```python
    # Загрузка общих данных (один раз для всех кабинетов)
    print("\n0. Загрузка общих данных...")
    own_stock = fetch_own_stock()

    # Запуск для каждого кабинета
    results = []
    for i, cabinet in enumerate(cabinets):
        # Per-cabinet data: barcode_dict и statuses фильтруются по кабинету
        barcode_dict = load_barcodes(args.sku_db)
        statuses = load_statuses(
            skip=args.no_statuses,
            cabinet_name=cabinet.name,
        )
        result = run_for_cabinet(cabinet, args, own_stock, barcode_dict, statuses)
        if result:
            results.append(result)

        # Пауза между кабинетами для rate limit
        if i < len(cabinets) - 1:
            print("\n   Ожидание 60с между кабинетами (rate limit)...")
            time.sleep(60)
```

Note: `load_barcodes()` reads from Excel and doesn't have cabinet filtering yet. This is OK because barcodes are just a display lookup — the actual data comes from WB API which is cabinet-specific. The critical filter is `load_statuses()` which determines business logic (e.g. "Выводим" exclusion).

- [ ] **Step 3: Run existing tests to verify no regression**

Run: `python -m pytest tests/wb_localization/ -v --timeout=30`
Expected: All existing tests PASS.

- [ ] **Step 4: Commit**

```bash
git add services/wb_localization/generate_localization_report_v3.py services/wb_localization/run_localization.py
git commit -m "fix: wire cabinet filter into localization pipeline

load_statuses() now accepts cabinet_name param.
Main loop loads statuses per-cabinet instead of once globally.
Fixes ИП/ООО article mixing in reports."
```

---

### Task 3: Module 2 — il_irp_analyzer.py (core calculator)

**Files:**
- Create: `services/wb_localization/calculators/il_irp_analyzer.py`
- Create: `tests/wb_localization/test_il_irp_analyzer.py`

- [ ] **Step 1: Write tests for the core calculator**

```python
# tests/wb_localization/test_il_irp_analyzer.py
"""Tests for IL/IRP per-article analyzer."""
import pytest


class TestLookupKtrKrp:
    """Verify lookup tables match WB reference (23.03.2026)."""

    def test_high_localization_discount(self):
        from services.wb_localization.irp_coefficients import get_ktr_krp
        ktr, krp = get_ktr_krp(97.0)
        assert ktr == 0.50
        assert krp == 0.00

    def test_neutral_zone(self):
        from services.wb_localization.irp_coefficients import get_ktr_krp
        ktr, krp = get_ktr_krp(65.0)
        assert ktr == 1.00
        assert krp == 0.00

    def test_irp_zone_threshold(self):
        """КРП jumps from 0 to 2.00 at 60% boundary."""
        from services.wb_localization.irp_coefficients import get_ktr_krp
        ktr_above, krp_above = get_ktr_krp(60.0)
        ktr_below, krp_below = get_ktr_krp(59.99)
        assert krp_above == 0.00
        assert krp_below == 2.00

    def test_worst_case(self):
        from services.wb_localization.irp_coefficients import get_ktr_krp
        ktr, krp = get_ktr_krp(2.0)
        assert ktr == 2.20
        assert krp == 2.50


class TestClassifyStatus:
    """Status label assignment."""

    def test_excellent(self):
        from services.wb_localization.calculators.il_irp_analyzer import classify_status
        assert classify_status(0.50) == "Отличная"
        assert classify_status(0.90) == "Отличная"

    def test_neutral(self):
        from services.wb_localization.calculators.il_irp_analyzer import classify_status
        assert classify_status(1.00) == "Нейтральная"
        assert classify_status(1.05) == "Нейтральная"

    def test_weak(self):
        from services.wb_localization.calculators.il_irp_analyzer import classify_status
        assert classify_status(1.10) == "Слабая"
        assert classify_status(1.30) == "Слабая"

    def test_critical(self):
        from services.wb_localization.calculators.il_irp_analyzer import classify_status
        assert classify_status(1.40) == "Критическая"
        assert classify_status(2.20) == "Критическая"


class TestAnalyzeIlIrp:
    """End-to-end test of analyze_il_irp()."""

    def _make_orders(self):
        """Create test orders: 2 articles, 3 regions."""
        return [
            # Article A: 80% local (Центральный warehouse → Центральный delivery)
            {"supplierArticle": "vuki/black", "warehouseName": "Коледино",
             "oblast": "Москва", "orderType": "Клиентский", "isCancel": False},
            {"supplierArticle": "vuki/black", "warehouseName": "Коледино",
             "oblast": "Москва", "orderType": "Клиентский", "isCancel": False},
            {"supplierArticle": "vuki/black", "warehouseName": "Коледино",
             "oblast": "Москва", "orderType": "Клиентский", "isCancel": False},
            {"supplierArticle": "vuki/black", "warehouseName": "Коледино",
             "oblast": "Москва", "orderType": "Клиентский", "isCancel": False},
            # 1 non-local for vuki/black: Центральный warehouse → Приволжский delivery
            {"supplierArticle": "vuki/black", "warehouseName": "Коледино",
             "oblast": "Казань", "orderType": "Клиентский", "isCancel": False},
            # Article B: 0% local (Центральный warehouse → Дальневосточный delivery)
            {"supplierArticle": "ruby/red", "warehouseName": "Коледино",
             "oblast": "Новосибирская область", "orderType": "Клиентский", "isCancel": False},
            {"supplierArticle": "ruby/red", "warehouseName": "Коледино",
             "oblast": "Новосибирская область", "orderType": "Клиентский", "isCancel": False},
        ]

    def test_overall_metrics(self):
        from services.wb_localization.calculators.il_irp_analyzer import analyze_il_irp

        result = analyze_il_irp(
            orders=self._make_orders(),
            prices_dict={"vuki/black": 3000.0, "ruby/red": 2000.0},
            period_days=30,
        )

        summary = result["summary"]
        # vuki/black: 4 local, 1 nonlocal → 80% → КТР=0.80, КРП=0
        # ruby/red: 0 local, 2 nonlocal → 0% → КТР=2.20, КРП=2.50
        # ИЛ = (5*0.80 + 2*2.20) / (5+2) = (4.0+4.4)/7 = 1.2
        assert abs(summary["overall_il"] - 1.20) < 0.01

        # ИРП = (5*0 + 2*2.50) / 7 = 5.0/7 = 0.714%
        assert abs(summary["overall_irp_pct"] - 0.71) < 0.05

        assert summary["total_articles"] == 2
        assert summary["irp_zone_articles"] == 1  # only ruby/red

    def test_article_details(self):
        from services.wb_localization.calculators.il_irp_analyzer import analyze_il_irp

        result = analyze_il_irp(
            orders=self._make_orders(),
            prices_dict={"vuki/black": 3000.0, "ruby/red": 2000.0},
            period_days=30,
        )

        articles = {a["article"]: a for a in result["articles"]}

        vuki = articles["vuki/black"]
        assert vuki["wb_local"] == 4
        assert vuki["wb_nonlocal"] == 1
        assert vuki["ktr"] == 0.80
        assert vuki["krp_pct"] == 0.00
        assert vuki["status"] == "Отличная"

        ruby = articles["ruby/red"]
        assert ruby["wb_local"] == 0
        assert ruby["wb_nonlocal"] == 2
        assert ruby["ktr"] == 2.20
        assert ruby["krp_pct"] == 2.50
        assert ruby["status"] == "Критическая"
        assert ruby["irp_per_order"] == 50.0  # 2000 * 2.5% = 50

    def test_sorted_by_contribution_desc(self):
        from services.wb_localization.calculators.il_irp_analyzer import analyze_il_irp

        result = analyze_il_irp(
            orders=self._make_orders(),
            prices_dict={},
            period_days=30,
        )

        articles = result["articles"]
        # ruby/red contribution = (2.20-1)*2 = 2.4
        # vuki/black contribution = (0.80-1)*5 = -1.0
        assert articles[0]["article"] == "ruby/red"

    def test_top_problems(self):
        from services.wb_localization.calculators.il_irp_analyzer import analyze_il_irp

        result = analyze_il_irp(
            orders=self._make_orders(),
            prices_dict={},
            period_days=30,
        )

        # Only articles with contribution > 0 appear in top_problems
        assert len(result["top_problems"]) == 1
        assert result["top_problems"][0]["article"] == "ruby/red"

    def test_cis_orders_excluded_from_il_included_in_irp_denominator(self):
        """CIS orders go into ИРП denominator but not into per-article localization."""
        from services.wb_localization.calculators.il_irp_analyzer import analyze_il_irp

        orders = [
            # 1 local RF order
            {"supplierArticle": "vuki/black", "warehouseName": "Коледино",
             "oblast": "Москва", "orderType": "Клиентский", "isCancel": False},
            # 1 CIS order (Минск warehouse = Беларусь)
            {"supplierArticle": "vuki/black", "warehouseName": "Минск",
             "oblast": "Минская область", "orderType": "Клиентский", "isCancel": False},
        ]
        result = analyze_il_irp(orders=orders, prices_dict={}, period_days=30)

        # Article should show 100% localization (only RF order counted)
        art = result["articles"][0]
        assert art["wb_local"] == 1
        assert art["wb_nonlocal"] == 0
        assert art["loc_pct"] == 100.0

        # But CIS order is in denominator for ИРП
        assert result["summary"]["total_cis_orders"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/wb_localization/test_il_irp_analyzer.py -v`
Expected: FAIL — module `il_irp_analyzer` does not exist.

- [ ] **Step 3: Create the calculators directory**

Run: `mkdir -p services/wb_localization/calculators && touch services/wb_localization/calculators/__init__.py`

- [ ] **Step 4: Implement `il_irp_analyzer.py`**

```python
# services/wb_localization/calculators/il_irp_analyzer.py
"""Per-article ИЛ/ИРП analysis with regional breakdown and price impact.

Replicates the logic of the WB ИЛ/ИРП spreadsheet (Telegram community),
but uses WB supplier/orders API data instead of manual export.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from services.wb_localization.irp_coefficients import get_ktr_krp, calc_financial_impact
from services.wb_localization.wb_localization_mappings import (
    get_warehouse_fd,
    get_delivery_fd,
    SKIP_WAREHOUSES,
)

logger = logging.getLogger(__name__)

# 6 macro-regions matching WB's federal districts
# Keys must match the values returned by get_warehouse_fd() / get_delivery_fd()
REGION_GROUPS: dict[str, list[str]] = {
    'Центральный': ['Центральный'],
    'Южный + Северо-Кавказский': ['Южный + Северо-Кавказский'],
    'Приволжский': ['Приволжский'],
    'Уральский': ['Уральский'],
    'Дальневосточный + Сибирский': ['Дальневосточный + Сибирский'],
    'Северо-Западный': ['Северо-Западный'],
}

# Reverse: FD name → macro-region name
_FD_TO_GROUP: dict[str, str] = {}
for group_name, fd_list in REGION_GROUPS.items():
    for fd in fd_list:
        _FD_TO_GROUP[fd] = group_name

# CIS countries — excluded from ИЛ, included in ИРП denominator
CIS_REGIONS = {'Беларусь', 'Казахстан', 'Армения', 'Кыргызстан', 'Узбекистан'}


def classify_status(ktr: float) -> str:
    """Status label based on КТР value."""
    if ktr <= 0.90:
        return "Отличная"
    if ktr <= 1.05:
        return "Нейтральная"
    if ktr <= 1.30:
        return "Слабая"
    return "Критическая"


def analyze_il_irp(
    orders: list[dict],
    prices_dict: dict[str, float],
    period_days: int = 30,
) -> dict[str, Any]:
    """Full per-article ИЛ/ИРП analysis.

    Args:
        orders: WB supplier/orders API response (list of order dicts).
        prices_dict: {article_lower: retail_price} from WB prices API.
        period_days: period length for monthly extrapolation.

    Returns:
        Dict with 'summary', 'articles', 'top_problems' keys.
    """
    # --- 1. Classify each order ---
    # Per-article: {article: {region_group: {local: int, nonlocal: int}}}
    article_regions: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"local": 0, "nonlocal": 0})
    )
    # Per-article totals (RF only)
    article_rf: dict[str, dict[str, int]] = defaultdict(lambda: {"local": 0, "nonlocal": 0})
    total_cis_orders = 0

    for order in orders:
        # Skip cancelled orders
        if order.get("isCancel"):
            continue

        article = (order.get("supplierArticle") or "").strip()
        if not article:
            continue

        warehouse = order.get("warehouseName", "")
        if warehouse in SKIP_WAREHOUSES:
            continue

        warehouse_fd = get_warehouse_fd(warehouse)
        if not warehouse_fd:
            continue

        # Check if CIS
        if warehouse_fd in CIS_REGIONS:
            total_cis_orders += 1
            continue

        oblast = order.get("oblast", "") or order.get("regionName", "") or ""
        delivery_fd = get_delivery_fd(oblast)
        if not delivery_fd:
            continue

        # Check if delivery is CIS
        if delivery_fd in CIS_REGIONS:
            total_cis_orders += 1
            continue

        art_lower = article.lower()
        is_local = warehouse_fd == delivery_fd

        # RF totals
        if is_local:
            article_rf[art_lower]["local"] += 1
        else:
            article_rf[art_lower]["nonlocal"] += 1

        # Regional breakdown
        region_group = _FD_TO_GROUP.get(delivery_fd)
        if region_group:
            if is_local:
                article_regions[art_lower][region_group]["local"] += 1
            else:
                article_regions[art_lower][region_group]["nonlocal"] += 1

    # --- 2. Calculate per-article metrics ---
    articles_list: list[dict[str, Any]] = []
    total_weighted_ktr = 0.0
    total_weighted_krp = 0.0
    total_rf_orders = 0
    total_local = 0
    total_nonlocal = 0
    irp_zone_count = 0
    irp_monthly_total = 0.0

    for art, counts in article_rf.items():
        local = counts["local"]
        nonlocal_ = counts["nonlocal"]
        total = local + nonlocal_
        if total == 0:
            continue

        loc_pct = local / total * 100
        ktr, krp_pct = get_ktr_krp(loc_pct)
        contribution = (ktr - 1) * total
        weighted = total * ktr
        status = classify_status(ktr)

        price = prices_dict.get(art, 0.0)
        irp_per_order = price * krp_pct / 100 if krp_pct > 0 and price > 0 else 0.0
        irp_per_month = calc_financial_impact(krp_pct, price, total, period_days)

        # Regional breakdown
        regions_data: dict[str, dict[str, Any]] = {}
        for rg_name in REGION_GROUPS:
            rg = article_regions[art].get(rg_name, {"local": 0, "nonlocal": 0})
            rg_local = rg["local"]
            rg_nonlocal = rg["nonlocal"]
            rg_total = rg_local + rg_nonlocal
            rg_pct = rg_local / rg_total * 100 if rg_total > 0 else 0.0
            regions_data[rg_name] = {
                "local": rg_local,
                "nonlocal": rg_nonlocal,
                "total": rg_total,
                "pct": round(rg_pct, 1),
            }

        # Find weakest region (lowest pct among regions with orders)
        weakest_region = ""
        weakest_pct = 101.0
        for rg_name, rg_data in regions_data.items():
            if rg_data["total"] > 0 and rg_data["pct"] < weakest_pct:
                weakest_pct = rg_data["pct"]
                weakest_region = rg_name

        articles_list.append({
            "article": art,
            "wb_local": local,
            "wb_nonlocal": nonlocal_,
            "wb_total": total,
            "loc_pct": round(loc_pct, 1),
            "ktr": ktr,
            "krp_pct": krp_pct,
            "contribution": round(contribution, 1),
            "weighted": round(weighted, 1),
            "status": status,
            "price": price,
            "irp_per_order": round(irp_per_order, 2),
            "irp_per_month": round(irp_per_month, 0),
            "regions": regions_data,
            "weakest_region": weakest_region,
        })

        # Aggregates
        total_weighted_ktr += weighted
        total_weighted_krp += total * krp_pct
        total_rf_orders += total
        total_local += local
        total_nonlocal += nonlocal_
        if krp_pct > 0:
            irp_zone_count += 1
            irp_monthly_total += irp_per_month

    # --- 3. Sort by contribution desc (worst offenders first) ---
    articles_list.sort(key=lambda a: a["contribution"], reverse=True)

    # --- 4. Overall metrics ---
    overall_il = total_weighted_ktr / total_rf_orders if total_rf_orders > 0 else 1.0
    irp_denominator = total_rf_orders + total_cis_orders
    overall_irp = total_weighted_krp / irp_denominator if irp_denominator > 0 else 0.0

    # --- 5. Top-10 problems (only positive contribution = penalty) ---
    top_problems = []
    for i, art in enumerate(articles_list):
        if art["contribution"] <= 0:
            break
        if i >= 10:
            break
        top_problems.append({
            "rank": i + 1,
            "article": art["article"],
            "orders": art["wb_total"],
            "loc_pct": art["loc_pct"],
            "ktr": art["ktr"],
            "krp_pct": art["krp_pct"],
            "contribution": art["contribution"],
            "weakest_region": art["weakest_region"],
            "recommendation": f"Добавить остатки на склады {art['weakest_region']}" if art["weakest_region"] else "",
        })

    return {
        "summary": {
            "overall_il": round(overall_il, 2),
            "overall_irp_pct": round(overall_irp, 2),
            "total_rf_orders": total_rf_orders,
            "total_cis_orders": total_cis_orders,
            "local_orders": total_local,
            "nonlocal_orders": total_nonlocal,
            "loc_pct": round(total_local / total_rf_orders * 100, 1) if total_rf_orders > 0 else 0.0,
            "total_articles": len(articles_list),
            "irp_zone_articles": irp_zone_count,
            "irp_monthly_cost_rub": round(irp_monthly_total, 0),
        },
        "articles": articles_list,
        "top_problems": top_problems,
    }
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/wb_localization/test_il_irp_analyzer.py -v`
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add services/wb_localization/calculators/ tests/wb_localization/test_il_irp_analyzer.py
git commit -m "feat: add il_irp_analyzer.py — per-article ИЛ/ИРП calculator

Implements the logic from the WB ИЛ/ИРП spreadsheet:
- Per-article localization % with 6-FD regional breakdown
- КТР/КРП lookup from irp_coefficients.py
- ИРП price impact in ₽/month per article
- Top-10 problems ranked by (КТР-1)×orders
- CIS orders excluded from ИЛ, included in ИРП denominator"
```

---

### Task 4: Integrate Module 2 into run_localization.py

**Files:**
- Modify: `services/wb_localization/run_localization.py:568-646` (`run_for_cabinet`)

- [ ] **Step 1: Add import at top of run_localization.py**

After line 55 (`from services.wb_localization.history import History`), add:

```python
from services.wb_localization.calculators.il_irp_analyzer import analyze_il_irp
```

- [ ] **Step 2: Add `--skip-il-analysis` CLI flag**

In the `parse_args()` function, add after the `--dry-run` argument:

```python
    parser.add_argument(
        '--skip-il-analysis', action='store_true', default=False,
        help='Пропустить ИЛ/ИРП анализ (только перестановки)'
    )
```

- [ ] **Step 3: Pass orders and prices to Module 2 in `run_for_cabinet()`**

In `run_for_cabinet()`, after line 641 (`_attach_comparison_and_save(result, history_store)`), add the Module 2 call:

```python
        # Module 2: ИЛ/ИРП анализ (если не отключён)
        if not getattr(args, 'skip_il_analysis', False):
            print("\n4. ИЛ/ИРП анализ...")
            il_irp = analyze_il_irp(
                orders=orders,
                prices_dict=prices_dict,
                period_days=args.days,
            )
            result['il_irp'] = il_irp
            s = il_irp['summary']
            print(f"   ИЛ: {s['overall_il']:.2f}, ИРП: {s['overall_irp_pct']:.2f}%")
            print(f"   Артикулов: {s['total_articles']}, в ИРП-зоне: {s['irp_zone_articles']}")
            print(f"   ИРП-нагрузка: {s['irp_monthly_cost_rub']:,.0f} ₽/мес")
```

Note: `orders` is available in scope from `fetch_wb_data()` call at line 584. `prices_dict` is also in scope. We need to make sure `orders` and `prices_dict` are passed through to where the result is built. Check the existing flow — `orders` is used at line 599 for `transform_orders_to_df_regions()`, and `prices_dict` is not currently used in `run_for_cabinet` (it's returned from `fetch_wb_data` but only used in `run_service_report`). We need to store both variables and pass them to Module 2.

In `run_for_cabinet()`, the variables `remains`, `orders`, `prices_dict` are already assigned at line 584. After the `return result` block at line 642, add the il_irp analysis. The full integration:

Find the block starting at line 638:
```python
    if return_result:
        result = _build_result_payload(cabinet.name, analysis)
        if history_store is not None:
            _attach_comparison_and_save(result, history_store)
        return result
```

Replace with:
```python
    if return_result:
        result = _build_result_payload(cabinet.name, analysis)
        if history_store is not None:
            _attach_comparison_and_save(result, history_store)

        # Module 2: ИЛ/ИРП анализ
        if not getattr(args, 'skip_il_analysis', False):
            print("\n4. ИЛ/ИРП анализ...")
            il_irp = analyze_il_irp(
                orders=orders,
                prices_dict=prices_dict,
                period_days=args.days,
            )
            result['il_irp'] = il_irp
            s = il_irp['summary']
            print(f"   ИЛ: {s['overall_il']:.2f}, ИРП: {s['overall_irp_pct']:.2f}%")
            print(f"   Артикулов: {s['total_articles']}, в ИРП-зоне: {s['irp_zone_articles']}")
            print(f"   ИРП-нагрузка: {s['irp_monthly_cost_rub']:,.0f} ₽/мес")

        return result
```

- [ ] **Step 4: Run existing tests**

Run: `python -m pytest tests/wb_localization/ -v --timeout=30`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/wb_localization/run_localization.py
git commit -m "feat: integrate il_irp_analyzer into localization pipeline

Module 2 runs after relocations, using same orders/prices data.
Adds --skip-il-analysis flag for backward compat.
Prints ИЛ, ИРП, zone count, monthly cost to console."
```

---

### Task 5: Sheets export — ИЛ Анализ + Справочник

**Files:**
- Modify: `services/wb_localization/sheets_export.py`

- [ ] **Step 1: Add `_write_il_analysis()` function to `sheets_export.py`**

Add at the end of the file, before any `if __name__` block:

```python
def _write_il_analysis(il_irp: dict, cabinet: str, spreadsheet) -> None:
    """Write per-article ИЛ analysis sheet."""
    sheet_name = f"ИЛ Анализ {cabinet}"
    ws = get_or_create_worksheet(spreadsheet, sheet_name, rows=2000, cols=37)

    summary = il_irp["summary"]
    articles = il_irp["articles"]

    # --- Header (rows 1-10): summary KPIs ---
    header_data = [
        ["", "Метрика", "Значение"],
        ["", "ИЛ (Индекс Локализации)", summary["overall_il"]],
        ["", "ИРП", f"{summary['overall_irp_pct']:.2f}%"],
        ["", "Локальных заказов WB (РФ)", summary["local_orders"]],
        ["", "Нелокальных заказов WB (РФ)", summary["nonlocal_orders"]],
        ["", "% локализации (всего)", f"{summary['loc_pct']:.1f}%"],
        ["", "Всего FBW заказов (РФ)", summary["total_rf_orders"]],
        ["", "Артикулов в расчёте", summary["total_articles"]],
        ["", "Артикулов в ИРП-зоне", summary["irp_zone_articles"]],
        ["", "ИРП-нагрузка ₽/мес", f"{summary['irp_monthly_cost_rub']:,.0f}"],
    ]

    # --- Column headers (row 12) ---
    region_names = [
        "Центральный", "Южный+СК", "Приволжский",
        "Уральский", "Дальн.+Сиб.", "С-Западный",
    ]
    region_keys = [
        "Центральный", "Южный + Северо-Кавказский", "Приволжский",
        "Уральский", "Дальневосточный + Сибирский", "Северо-Западный",
    ]

    col_headers = [
        "Артикул", "Название", "Предмет",
        "ВБ Лок. (РФ)", "ВБ Нелок. (РФ)", "Всего WB (РФ)",
        "% лок.", "КТР", "КРП,%", "Вклад шт×КТР", "Статус",
    ]
    for rn in region_names:
        col_headers.extend([f"Лок. {rn}", f"Нелок. {rn}", f"Всего {rn}", f"% лок. {rn}"])
    col_headers.extend(["Вклад в ИЛ", "ИРП ₽/мес"])

    # --- Data rows (row 13+) ---
    data_rows = []
    for art in articles:
        row = [
            art["article"], "", "",  # name/category not in API data
            art["wb_local"], art["wb_nonlocal"], art["wb_total"],
            art["loc_pct"], art["ktr"], art["krp_pct"],
            art["weighted"], art["status"],
        ]
        for rk in region_keys:
            rg = art["regions"].get(rk, {"local": 0, "nonlocal": 0, "total": 0, "pct": 0})
            row.extend([rg["local"], rg["nonlocal"], rg["total"], rg["pct"]])
        row.extend([art["contribution"], art["irp_per_month"]])
        data_rows.append(row)

    # --- Write everything ---
    all_data = header_data + [[""]] + [col_headers] + data_rows
    clear_and_write(ws, all_data)

    logger.info("Записан лист '%s': %d артикулов", sheet_name, len(articles))


def _write_reference_sheet(spreadsheet) -> None:
    """Write static reference sheet with КТР/КРП tables."""
    from services.wb_localization.irp_coefficients import COEFF_TABLE

    ws = get_or_create_worksheet(spreadsheet, "Справочник", rows=40, cols=10)

    data = [
        ["Таблица КТР (с 23.03.2026)", "", "", "", "Таблица КРП (с 23.03.2026)"],
        ["Доля лок., %", "КТР", "Описание", "", "Доля лок., %", "КРП, %", "Описание"],
    ]

    for min_loc, max_loc, ktr, krp in COEFF_TABLE:
        ktr_desc = "Скидка" if ktr < 1.0 else ("Базовый" if ktr == 1.0 else "Штраф")
        krp_desc = "Нет надбавки" if krp == 0 else f"{krp}% от цены"
        data.append([
            f"{min_loc:.0f}–{max_loc:.0f}%", ktr, ktr_desc,
            "", f"{min_loc:.0f}–{max_loc:.0f}%", f"{krp:.2f}%", krp_desc,
        ])

    data.append([])
    data.append(["Формулы:"])
    data.append(["ИЛ = Σ(заказы × КТР) / Σ(заказы)  — средневзвешенный КТР"])
    data.append(["ИРП = Σ(заказы × КРП%) / (РФ + СНГ заказы)  — СНГ в знаменателе с КРП=0"])
    data.append([])
    data.append(["Статусы:"])
    data.append(["КТР ≤ 0.90 → Отличная | 0.91–1.05 → Нейтральная | 1.06–1.30 → Слабая | ≥ 1.31 → Критическая"])

    clear_and_write(ws, data)
    logger.info("Записан лист 'Справочник'")
```

- [ ] **Step 2: Call new functions from `export_to_sheets()`**

In `export_to_sheets()`, at the end (before the `return` statement), add:

```python
    # Module 2: ИЛ/ИРП sheets
    il_irp = result.get("il_irp")
    if il_irp:
        _write_il_analysis(il_irp, cabinet, spreadsheet)
        _write_reference_sheet(spreadsheet)
```

You need to make `spreadsheet` object available. Check the existing code — `export_to_sheets()` likely opens the spreadsheet via `gc.open_by_key(VASILY_SPREADSHEET_ID)`. Store that reference and pass it to the new functions. If `spreadsheet` is already a local variable in `export_to_sheets()`, just use it directly.

- [ ] **Step 3: Run existing tests**

Run: `python -m pytest tests/wb_localization/ -v --timeout=30`
Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
git add services/wb_localization/sheets_export.py
git commit -m "feat: add ИЛ Анализ and Справочник sheets export

_write_il_analysis() — 37-column per-article breakdown with
  summary KPIs, regional localization %, КТР/КРП, price impact.
_write_reference_sheet() — static КТР/КРП tables + formulas."
```

---

### Task 6: Rename Vasily → WB Logistics

**Files:**
- Modify: `services/wb_localization/config.py`
- Rename: `services/vasily_api/` → `services/wb_logistics_api/`
- Modify: `services/wb_logistics_api/app.py`
- Modify: `services/wb_localization/history.py`

- [ ] **Step 1: Update config.py env vars with fallback**

In `services/wb_localization/config.py`, replace the env var lines:

```python
# Google Sheets
VASILY_SPREADSHEET_ID: str = (
    os.getenv("WB_LOGISTICS_SPREADSHEET_ID")
    or os.getenv("VASILY_SPREADSHEET_ID", "")
)

# Period and cabinets
REPORT_PERIOD_DAYS: int = int(
    os.getenv("WB_LOGISTICS_PERIOD_DAYS")
    or os.getenv("VASILY_REPORT_PERIOD_DAYS", "7")
)
CABINETS: list = (
    os.getenv("WB_LOGISTICS_CABINETS")
    or os.getenv("VASILY_CABINETS", "ip,ooo")
).split(",")
```

- [ ] **Step 2: Rename vasily_api folder**

Run: `git mv services/vasily_api services/wb_logistics_api`

- [ ] **Step 3: Update imports in `services/wb_logistics_api/app.py`**

Replace any `vasily` references in the app.py file with `wb_logistics`. Update log messages from "Vasily" to "WB Logistics".

- [ ] **Step 4: Update SQLite path in `history.py`**

In `services/wb_localization/history.py`, find the DB path definition and add migration logic:

```python
import shutil

_OLD_DB = Path(__file__).parent / "data" / "vasily.db"
_NEW_DB = Path(__file__).parent / "data" / "wb_logistics.db"

def _get_db_path() -> Path:
    """Get DB path, migrating from old name if needed."""
    if _NEW_DB.exists():
        return _NEW_DB
    if _OLD_DB.exists():
        _NEW_DB.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_OLD_DB, _NEW_DB)
        return _NEW_DB
    _NEW_DB.parent.mkdir(parents=True, exist_ok=True)
    return _NEW_DB
```

- [ ] **Step 5: Update any imports referencing `vasily_api`**

Run: `grep -r "vasily_api" --include="*.py" .` and update all references to `wb_logistics_api`.

- [ ] **Step 6: Run all tests**

Run: `python -m pytest tests/wb_localization/ tests/services/logistics_audit/ -v --timeout=30`
Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor: rename Vasily → WB Logistics

- vasily_api/ → wb_logistics_api/
- Env vars: WB_LOGISTICS_SPREADSHEET_ID (fallback to VASILY_*)
- SQLite: wb_logistics.db (auto-migrate from vasily.db)
- Log messages updated"
```

---

### Task 7: End-to-end verification

**Files:** None (testing only)

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/ -v --timeout=60 -x`
Expected: All tests PASS.

- [ ] **Step 2: Dry-run for ООО cabinet**

Run: `python services/wb_localization/run_localization.py --cabinet ooo --days 7 --dry-run`
Expected: Should show separate ООО data without ИП articles.

- [ ] **Step 3: Verify KTR/KRP tables match reference**

Run a quick Python check:
```bash
python -c "
from services.wb_localization.irp_coefficients import get_ktr_krp
# Check key thresholds
assert get_ktr_krp(60.0) == (1.00, 0.00), 'Threshold at 60%'
assert get_ktr_krp(59.99) == (1.05, 2.00), 'Just below 60%'
assert get_ktr_krp(95.0) == (0.50, 0.00), 'Best case'
assert get_ktr_krp(0.0) == (2.20, 2.50), 'Worst case'
print('All KTR/KRP checks passed')
"
```

- [ ] **Step 4: Commit any fixes**

If any issues found, fix and commit. Otherwise, no action needed.
