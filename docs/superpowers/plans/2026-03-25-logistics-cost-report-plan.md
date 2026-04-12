# Анализ логистических расходов WB — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Weekly Notion report "Анализ логистических расходов" showing IRP/IL overpay, dynamics, and optimization potential + Google Sheets "ИРП-анализ" tab.

**Architecture:** Deterministic report formatter (`report_md.py`) renders `run_service_report()` results into Markdown → delivery via existing `agents/v3/delivery/` router (Notion + Telegram). History extended with IRP fields for week-over-week dynamics.

**Tech Stack:** Python, SQLite (history), openpyxl/gspread (Sheets), httpx (Notion API), APScheduler (cron)

**Spec:** `docs/superpowers/specs/2026-03-25-logistics-cost-report-design.md`

---

## File Structure

| File | Responsibility | Action |
|------|---------------|--------|
| `services/wb_localization/irp_coefficients.py` | KTR/KRP coefficient table | Edit: update 5 KTR values |
| `scripts/calc_irp.py` | Standalone IRP calculator (duplicate table) | Edit: update 5 KTR values |
| `services/wb_localization/history.py` | SQLite history with IRP columns | Edit: migration + save/read |
| `services/wb_localization/run_localization.py` | Orchestrator | Edit: _sku_stats in payload, IRP comparison |
| `services/wb_localization/sheets_export.py` | Google Sheets export | Edit: +_write_irp_analysis |
| `services/wb_localization/report_md.py` | **NEW** MD formatter for Notion | Create |
| `agents/v3/config.py` | Scheduler config | Edit: +2 env vars |
| `agents/v3/scheduler.py` | Cron jobs | Edit: +job function, +registration |
| `agents/v3/delivery/notion.py` | Notion delivery | Edit: +report type |
| `tests/wb_localization/test_irp_coefficients.py` | Tests for KTR update | Create |
| `tests/wb_localization/test_history_irp.py` | Tests for history IRP fields | Create |
| `tests/wb_localization/test_report_md.py` | Tests for MD formatter | Create |

---

### Task 1: Update KTR Coefficients

**Files:**
- Modify: `services/wb_localization/irp_coefficients.py:1-40`
- Modify: `scripts/calc_irp.py:50-73`
- Create: `tests/wb_localization/test_irp_coefficients.py`

- [ ] **Step 1: Write test for updated KTR values**

```python
# tests/wb_localization/test_irp_coefficients.py
"""Tests for updated KTR coefficients (27.03.2026)."""
import pytest
from services.wb_localization.irp_coefficients import get_ktr_krp, get_zone, IRP_THRESHOLD

@pytest.mark.parametrize("loc_pct, expected_ktr, expected_krp", [
    (97.0, 0.50, 0.00),   # top tier — unchanged
    (72.0, 1.00, 0.00),   # neutral — unchanged
    (62.0, 1.00, 0.00),   # just above IRP threshold — unchanged
    (57.0, 1.05, 2.00),   # was 1.10 → now 1.05
    (52.0, 1.10, 2.05),   # was 1.20 → now 1.10
    (47.0, 1.20, 2.05),   # was 1.30 → now 1.20
    (42.0, 1.30, 2.10),   # was 1.40 → now 1.30
    (37.0, 1.40, 2.10),   # was 1.50 → now 1.40
    (32.0, 1.60, 2.15),   # unchanged (below updated range)
    (2.0,  2.20, 2.50),   # bottom tier — unchanged
])
def test_get_ktr_krp_updated_values(loc_pct, expected_ktr, expected_krp):
    ktr, krp = get_ktr_krp(loc_pct)
    assert ktr == expected_ktr
    assert krp == expected_krp

def test_irp_threshold():
    assert IRP_THRESHOLD == 60.0

def test_zone_boundaries():
    assert get_zone(58.0) == "ИРП-зона"
    assert get_zone(62.0) == "ИЛ-зона"
    assert get_zone(76.0) == "OK"
```

- [ ] **Step 2: Run test — verify it fails on old KTR values**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python3 -m pytest tests/wb_localization/test_irp_coefficients.py -v`
Expected: FAIL on loc_pct=57 (got 1.10, expected 1.05)

- [ ] **Step 3: Update irp_coefficients.py**

In `services/wb_localization/irp_coefficients.py`:
- Line 4: change `(с 23.03.2026)` → `(с 27.03.2026)`
- Line 12: change `# Таблица коэффициентов WB (с 23.03.2026)` → `(с 27.03.2026)`
- Line 28: `(55.00,  59.99, 1.10, 2.00)` → `(55.00,  59.99, 1.05, 2.00)`
- Line 29: `(50.00,  54.99, 1.20, 2.05)` → `(50.00,  54.99, 1.10, 2.05)`
- Line 30: `(45.00,  49.99, 1.30, 2.05)` → `(45.00,  49.99, 1.20, 2.05)`
- Line 31: `(40.00,  44.99, 1.40, 2.10)` → `(40.00,  44.99, 1.30, 2.10)`
- Line 32: `(35.00,  39.99, 1.50, 2.10)` → `(35.00,  39.99, 1.40, 2.10)`

- [ ] **Step 4: Update scripts/calc_irp.py**

Same 5 KTR changes at lines 61-65. Update docstring date.

- [ ] **Step 5: Run test — verify it passes**

Run: `python3 -m pytest tests/wb_localization/test_irp_coefficients.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add services/wb_localization/irp_coefficients.py scripts/calc_irp.py tests/wb_localization/test_irp_coefficients.py
git commit -m "fix: update KTR coefficients to WB Partners 27.03.2026 values"
```

---

### Task 2: Extend History Schema for IRP Fields

**Files:**
- Modify: `services/wb_localization/history.py:15-195`
- Create: `tests/wb_localization/test_history_irp.py`

- [ ] **Step 1: Write test for IRP fields in history**

```python
# tests/wb_localization/test_history_irp.py
"""Tests for IRP fields in History SQLite store."""
import tempfile
from pathlib import Path
from services.wb_localization.history import History

def _make_history(tmp_path: Path) -> History:
    return History(db_path=tmp_path / "test.db")

def test_save_and_read_irp_fields(tmp_path):
    h = _make_history(tmp_path)
    result = {
        "cabinet": "ooo",
        "timestamp": "2026-03-25T10:00:00",
        "report_path": "/tmp/test.xlsx",
        "summary": {
            "overall_index": 73.5,
            "total_sku": 200,
            "sku_with_orders": 150,
            "movements_count": 50,
            "movements_qty": 1200,
            "supplies_count": 10,
            "supplies_qty": 300,
            "il_current": 0.98,
            "irp_current": 0.42,
            "irp_zone_sku": 12,
            "il_zone_sku": 30,
            "irp_impact_rub_month": 45200.0,
        },
        "regions": [],
        "top_problems": [],
    }
    h.save_run(result)
    latest = h.get_latest("ooo")

    assert latest is not None
    s = latest["summary"]
    assert s["il_current"] == 0.98
    assert s["irp_current"] == 0.42
    assert s["irp_zone_sku"] == 12
    assert s["il_zone_sku"] == 30
    assert s["irp_impact_rub_month"] == 45200.0

def test_old_rows_get_defaults(tmp_path):
    """Rows saved before IRP migration should return safe defaults."""
    h = _make_history(tmp_path)
    # Save a result WITHOUT IRP fields (simulating old data)
    result = {
        "cabinet": "ip",
        "timestamp": "2026-03-20T10:00:00",
        "report_path": "",
        "summary": {
            "overall_index": 70.0,
            "total_sku": 100,
            "sku_with_orders": 80,
            "movements_count": 20,
            "movements_qty": 500,
            "supplies_count": 5,
            "supplies_qty": 100,
        },
        "regions": [],
        "top_problems": [],
    }
    h.save_run(result)
    latest = h.get_latest("ip")

    s = latest["summary"]
    assert s["il_current"] == 1.0  # default
    assert s["irp_current"] == 0.0  # default
    assert s["irp_zone_sku"] == 0
    assert s["il_zone_sku"] == 0
    assert s["irp_impact_rub_month"] == 0.0

def test_migration_adds_columns(tmp_path):
    """Creating History twice on same DB should not error (idempotent migration)."""
    h1 = _make_history(tmp_path)
    h1.save_run({
        "cabinet": "ooo", "timestamp": "2026-03-25T10:00:00",
        "report_path": "", "summary": {"il_current": 0.99},
        "regions": [], "top_problems": [],
    })
    # Re-open — migration should be idempotent
    h2 = _make_history(tmp_path)
    latest = h2.get_latest("ooo")
    assert latest["summary"]["il_current"] == 0.99
```

- [ ] **Step 2: Run test — verify it fails**

Run: `python3 -m pytest tests/wb_localization/test_history_irp.py -v`
Expected: FAIL (il_current not in summary)

- [ ] **Step 3: Add _ensure_irp_columns migration to history.py**

In `services/wb_localization/history.py`, add after `_auto_migrate()` call in `__init__` (line 50):

```python
# In __init__, line 50, after self._auto_migrate():
self._ensure_irp_columns()
```

New method (add after `_auto_migrate`):

```python
_IRP_COLUMNS = [
    ("il_current", "REAL", "1.0"),
    ("irp_current", "REAL", "0.0"),
    ("irp_zone_sku", "INTEGER", "0"),
    ("il_zone_sku", "INTEGER", "0"),
    ("irp_impact_rub_month", "REAL", "0.0"),
]

def _ensure_irp_columns(self) -> None:
    """Add IRP columns if they don't exist (safe ALTER TABLE migration)."""
    with self._get_conn() as conn:
        existing = {row[1] for row in conn.execute("PRAGMA table_info(reports)").fetchall()}
        for col_name, col_type, default in self._IRP_COLUMNS:
            if col_name not in existing:
                conn.execute(
                    f"ALTER TABLE reports ADD COLUMN {col_name} {col_type} DEFAULT {default}"
                )
                logger.info("Миграция: добавлена колонка reports.%s", col_name)
```

Note: `_IRP_COLUMNS` is a class attribute on `History`.

- [ ] **Step 4: Update save_run() to write IRP fields**

In `save_run()` (line 118), change INSERT to include 5 new fields:

```python
def save_run(self, result: dict) -> None:
    """Сохранить результат расчёта."""
    summary = result.get("summary", {})
    with self._get_conn() as conn:
        conn.execute(
            """INSERT INTO reports
               (cabinet, timestamp, report_path,
                overall_index, total_sku, sku_with_orders,
                movements_count, movements_qty,
                supplies_count, supplies_qty,
                regions_json, top_problems_json,
                il_current, irp_current, irp_zone_sku,
                il_zone_sku, irp_impact_rub_month)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                result.get("cabinet", ""),
                result.get("timestamp", ""),
                result.get("report_path", ""),
                summary.get("overall_index", 0),
                summary.get("total_sku", 0),
                summary.get("sku_with_orders", 0),
                summary.get("movements_count", 0),
                summary.get("movements_qty", 0),
                summary.get("supplies_count", 0),
                summary.get("supplies_qty", 0),
                json.dumps(result.get("regions", []), ensure_ascii=False),
                json.dumps(result.get("top_problems", [])[:10], ensure_ascii=False),
                summary.get("il_current", 1.0),
                summary.get("irp_current", 0.0),
                summary.get("irp_zone_sku", 0),
                summary.get("il_zone_sku", 0),
                summary.get("irp_impact_rub_month", 0.0),
            ),
        )
    logger.info("Сохранён расчёт %s от %s", result.get("cabinet"), result.get("timestamp"))
```

- [ ] **Step 5: Update _row_to_dict() to read IRP fields**

In `_row_to_dict()` (line 177), add IRP fields with safe defaults:

```python
@staticmethod
def _row_to_dict(row: sqlite3.Row) -> dict:
    keys = row.keys()
    return {
        "cabinet": row["cabinet"],
        "timestamp": row["timestamp"],
        "report_path": row["report_path"],
        "summary": {
            "overall_index": row["overall_index"],
            "total_sku": row["total_sku"],
            "sku_with_orders": row["sku_with_orders"],
            "movements_count": row["movements_count"],
            "movements_qty": row["movements_qty"],
            "supplies_count": row["supplies_count"],
            "supplies_qty": row["supplies_qty"],
            "il_current": row["il_current"] if "il_current" in keys else 1.0,
            "irp_current": row["irp_current"] if "irp_current" in keys else 0.0,
            "irp_zone_sku": row["irp_zone_sku"] if "irp_zone_sku" in keys else 0,
            "il_zone_sku": row["il_zone_sku"] if "il_zone_sku" in keys else 0,
            "irp_impact_rub_month": row["irp_impact_rub_month"] if "irp_impact_rub_month" in keys else 0.0,
        },
        "regions": json.loads(row["regions_json"] or "[]"),
        "top_problems": json.loads(row["top_problems_json"] or "[]"),
    }
```

- [ ] **Step 6: Run test — verify it passes**

Run: `python3 -m pytest tests/wb_localization/test_history_irp.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add services/wb_localization/history.py tests/wb_localization/test_history_irp.py
git commit -m "feat: extend history schema with IRP fields for dynamics tracking"
```

---

### Task 3: Extend Comparison with IRP Deltas + Add _sku_stats to Payload

**Files:**
- Modify: `services/wb_localization/run_localization.py:507-550`

- [ ] **Step 1: Add _sku_stats to _build_result_payload()**

In `run_localization.py` line 507, add `'_sku_stats'` to the return dict:

```python
    return {
        'cabinet': cabinet_name,
        'timestamp': datetime.now().isoformat(timespec='seconds'),
        'report_path': str(analysis.get('report_path', '')),
        'summary': summary,
        'regions': regions,
        'top_problems': top_problems,
        'comparison': None,
        '_moves_df': moves_df,
        '_supply_df': supply_df,
        '_sku_stats': sku_stats,
    }
```

- [ ] **Step 2: Extend _attach_comparison_and_save() with IRP deltas**

In `run_localization.py` after line 548 (after `'regions_worsened': worsened,`), add IRP comparison fields:

```python
        result['comparison'] = {
            'prev_timestamp': prev.get('timestamp'),
            'prev_index': prev_index,
            'index_change': round(curr_index - prev_index, 1),
            'regions_improved': improved,
            'regions_worsened': worsened,
            # IRP dynamics
            'prev_il_current': prev_summary.get('il_current', 1.0),
            'il_current_change': round(
                curr_summary.get('il_current', 1.0) - prev_summary.get('il_current', 1.0), 3
            ),
            'prev_irp_current': prev_summary.get('irp_current', 0.0),
            'irp_current_change': round(
                curr_summary.get('irp_current', 0.0) - prev_summary.get('irp_current', 0.0), 3
            ),
            'prev_irp_impact': prev_summary.get('irp_impact_rub_month', 0),
            'irp_impact_change': round(
                curr_summary.get('irp_impact_rub_month', 0) - prev_summary.get('irp_impact_rub_month', 0), 0
            ),
            'prev_irp_zone_sku': prev_summary.get('irp_zone_sku', 0),
            'irp_zone_sku_change': curr_summary.get('irp_zone_sku', 0) - prev_summary.get('irp_zone_sku', 0),
        }
```

- [ ] **Step 3: Verify syntax**

Run: `python3 -c "import ast; ast.parse(open('services/wb_localization/run_localization.py').read()); print('OK')"`
Expected: OK

- [ ] **Step 4: Commit**

```bash
git add services/wb_localization/run_localization.py
git commit -m "feat: add _sku_stats to payload and IRP deltas to comparison"
```

---

### Task 4: Google Sheets "ИРП-анализ" Tab

**Files:**
- Modify: `services/wb_localization/sheets_export.py:31-90`

- [ ] **Step 1: Add _write_irp_analysis function**

Add after `_write_top_problems` function in `sheets_export.py`:

```python
def _write_irp_analysis(spreadsheet, cabinet: str, result: dict, meta):
    """Лист «ИРП-анализ {cabinet}» — артикулы с переплатой за логистику."""
    sku_stats: pd.DataFrame = result.get("_sku_stats", pd.DataFrame())
    summary = result.get("summary", {})

    ws = get_or_create_worksheet(spreadsheet, f"ИРП-анализ {cabinet}")

    # Шапка: ключевые метрики
    summary_rows = [
        ["ИЛ текущий", summary.get("il_current", 1.0)],
        ["ИРП текущий", f"{summary.get('irp_current', 0.0):.2f}%"],
        ["ИРП-переплата ₽/мес", summary.get("irp_impact_rub_month", 0)],
        ["SKU в ИРП-зоне", summary.get("irp_zone_sku", 0)],
        ["SKU в ИЛ-зоне", summary.get("il_zone_sku", 0)],
    ]
    clear_and_write(ws, ["Метрика", "Значение"], summary_rows, meta)

    if sku_stats.empty or "Зона" not in sku_stats.columns:
        return

    # Фильтр: только проблемные артикулы
    problem = sku_stats[
        (sku_stats["Зона"] != "OK") | (sku_stats.get("КТР", pd.Series(dtype=float)) > 1.0)
    ].copy()
    if problem.empty:
        return

    # Группировка по модели (артикул без размера)
    problem["Модель"] = problem["Артикул продавца"].str.strip()
    grouped = problem.groupby("Модель").agg(
        Индекс_пц=("Индекс, %", lambda x: round((x * problem.loc[x.index, "Всего заказов"]).sum() / max(problem.loc[x.index, "Всего заказов"].sum(), 1), 1)),
        КТР=("КТР", lambda x: round((x * problem.loc[x.index, "Всего заказов"]).sum() / max(problem.loc[x.index, "Всего заказов"].sum(), 1), 2)),
        КРП=("КРП%", lambda x: round((x * problem.loc[x.index, "Всего заказов"]).sum() / max(problem.loc[x.index, "Всего заказов"].sum(), 1), 2)),
        Заказов=("Всего заказов", "sum"),
        ИРП_нагрузка=("ИРП-нагрузка ₽/мес", "sum"),
        Цена=("Цена", "mean"),
    ).reset_index()

    # Зона — по средневзвешенному индексу
    grouped["Зона"] = grouped["Индекс_пц"].apply(
        lambda x: "ИРП-зона" if x < 60 else ("ИЛ-зона" if x < 75 else "OK")
    )

    # Потенциальная экономия
    # Средний тариф логистики — загружается через WB API при запуске,
    # или используется константа ~80₽ как fallback (до подключения базы тарифов)
    AVG_BASE_LOGISTICS = result.get("_avg_base_logistics", 80.0)

    def _calc_savings(r):
        if r["Индекс_пц"] < 60:
            # ИРП-зона → 60%: убирается КРП полностью
            return r["ИРП_нагрузка"]
        elif r["Индекс_пц"] < 75:
            # ИЛ-зона → 75%: КТР снижается до 0.90
            monthly_orders = r["Заказов"] / period_days * 30 if period_days else r["Заказов"]
            return (r["КТР"] - 0.90) * AVG_BASE_LOGISTICS * monthly_orders
        return 0

    period_days = result.get("_period_days", 91)
    grouped["Потенц_экономия"] = grouped.apply(_calc_savings, axis=1)

    grouped = grouped.sort_values("Потенц_экономия", ascending=False)

    # Запись таблицы (начиная со строки 8, после шапки)
    headers = ["Модель", "Индекс%", "КТР", "КРП%", "Зона", "Ср.цена", "Заказов", "ИРП-нагрузка ₽/мес", "Потенц. экономия"]
    rows = []
    for _, r in grouped.iterrows():
        rows.append([
            r["Модель"],
            to_number(r["Индекс_пц"]),
            to_number(r["КТР"]),
            to_number(r["КРП"]),
            r["Зона"],
            to_number(round(r["Цена"], 0)),
            to_number(int(r["Заказов"])),
            to_number(round(r["ИРП_нагрузка"], 0)),
            to_number(round(r["Потенц_экономия"], 0)),
        ])

    write_range(ws, 8, 1, [headers] + rows)
```

- [ ] **Step 2: Call _write_irp_analysis from export_to_sheets()**

In `export_to_sheets()`, after line 82 (`_write_top_problems`), add:

```python
    # --- ИРП-анализ ---
    _write_irp_analysis(spreadsheet, cabinet, result, meta)
```

- [ ] **Step 3: Verify syntax**

Run: `python3 -c "import ast; ast.parse(open('services/wb_localization/sheets_export.py').read()); print('OK')"`
Expected: OK

- [ ] **Step 4: Commit**

```bash
git add services/wb_localization/sheets_export.py
git commit -m "feat: add IRP analysis sheet to Google Sheets export"
```

---

### Task 5: Create report_md.py — Notion Report Formatter

**Files:**
- Create: `services/wb_localization/report_md.py`
- Create: `tests/wb_localization/test_report_md.py`

- [ ] **Step 1: Write test for MD formatter**

```python
# tests/wb_localization/test_report_md.py
"""Tests for localization weekly Notion report formatter."""
from services.wb_localization.report_md import (
    format_localization_weekly_md,
    format_localization_tg_summary,
)

def _sample_result(cabinet="ooo"):
    return {
        "cabinet": cabinet,
        "summary": {
            "overall_index": 73.5,
            "total_sku": 200,
            "sku_with_orders": 150,
            "il_current": 0.98,
            "irp_current": 0.42,
            "irp_zone_sku": 12,
            "il_zone_sku": 30,
            "irp_impact_rub_month": 45200.0,
            "movements_count": 50,
            "movements_qty": 1200,
            "supplies_count": 10,
            "supplies_qty": 300,
        },
        "regions": [
            {"region": "Центральный", "index": 93.4, "stock_share": 45.0, "order_share": 42.0, "recommendation": ""},
            {"region": "Дальневосточный + Сибирский", "index": 17.7, "stock_share": 3.0, "order_share": 13.0, "recommendation": "Дефицит остатков"},
        ],
        "top_problems": [
            {"article": "Joy/shinny_pink", "size": "S", "index": 41.4, "orders": 519, "impact": 12800, "zone": "ИРП-зона", "krp_pct": 2.10, "irp_rub_month": 12800},
        ],
        "comparison": {
            "prev_timestamp": "2026-03-18T10:00:00",
            "prev_index": 72.9,
            "index_change": 0.6,
            "regions_improved": ["Центральный"],
            "regions_worsened": [],
            "prev_il_current": 0.99,
            "il_current_change": -0.01,
            "prev_irp_current": 0.45,
            "irp_current_change": -0.03,
            "prev_irp_impact": 48500,
            "irp_impact_change": -3300,
            "prev_irp_zone_sku": 14,
            "irp_zone_sku_change": -2,
        },
    }

def test_format_md_contains_key_sections():
    md = format_localization_weekly_md([_sample_result()], period_days=91)
    assert "Анализ логистических расходов" in md
    assert "Сводка" in md
    assert "Динамика" in md
    assert "ooo" in md.lower() or "ООО" in md
    assert "45" in md  # irp impact ~45K
    assert "Joy/shinny_pink" in md

def test_format_md_two_cabinets():
    md = format_localization_weekly_md(
        [_sample_result("ip"), _sample_result("ooo")],
        period_days=91,
    )
    assert "ИП" in md or "ip" in md.lower()
    assert "ООО" in md or "ooo" in md.lower()

def test_format_md_no_comparison():
    result = _sample_result()
    result["comparison"] = None
    md = format_localization_weekly_md([result], period_days=91)
    assert "Анализ логистических расходов" in md
    # Should not crash, dynamics section may say "нет данных"

def test_tg_summary_short():
    tg = format_localization_tg_summary([_sample_result()])
    assert len(tg) < 500
    assert "Логистические расходы" in tg or "логистическ" in tg.lower()
```

- [ ] **Step 2: Run test — verify it fails**

Run: `python3 -m pytest tests/wb_localization/test_report_md.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement report_md.py**

Create `services/wb_localization/report_md.py`:

```python
"""Детерминистический MD-форматировщик для Notion-отчёта по логистическим расходам."""
from __future__ import annotations

from datetime import datetime, timedelta

_CABINET_LABELS = {"ip": "ИП", "ooo": "ООО", "ип": "ИП", "ооо": "ООО"}


def _cab(name: str) -> str:
    return _CABINET_LABELS.get(name.lower(), name)


def _fmt_rub(value: float) -> str:
    """Format ruble amount: 45200 → '45 200'."""
    return f"{value:,.0f}".replace(",", " ")


def _sign(value: float) -> str:
    return f"+{value}" if value > 0 else str(value)


def format_localization_weekly_md(results: list[dict], period_days: int) -> str:
    """Render weekly localization report as Markdown for Notion.

    Args:
        results: list of result dicts from run_service_report() (one per cabinet)
        period_days: index calculation window (typically 91)
    """
    now = datetime.now()
    idx_from = (now - timedelta(days=period_days)).strftime("%d.%m")
    idx_to = now.strftime("%d.%m.%Y")
    week_from = (now - timedelta(days=7)).strftime("%d.%m")
    week_to = (now - timedelta(days=1)).strftime("%d.%m")

    lines: list[str] = []
    lines.append("# Анализ логистических расходов WB")
    lines.append("")
    lines.append(f"> Период индексов: {period_days} дн ({idx_from} — {idx_to}). Динамика: неделя {week_from} — {week_to}.")
    lines.append("")

    # --- Сводка ---
    lines.append("## Сводка по кабинетам")
    lines.append("")
    lines.append("| Кабинет | ИЛ | ИРП | Индекс лок. | SKU в ИРП-зоне | Переплата ₽/мес |")
    lines.append("|---------|-----|------|------------|----------------|-----------------|")
    for r in results:
        s = r.get("summary", {})
        cab = _cab(r.get("cabinet", ""))
        lines.append(
            f"| {cab} | {s.get('il_current', 1.0):.2f} | {s.get('irp_current', 0.0):.2f}% "
            f"| {s.get('overall_index', 0):.1f}% | {s.get('irp_zone_sku', 0)} "
            f"| {_fmt_rub(s.get('irp_impact_rub_month', 0))} |"
        )
    lines.append("")

    # --- Динамика ---
    lines.append("## Динамика за неделю")
    lines.append("")
    for r in results:
        cab = _cab(r.get("cabinet", ""))
        comp = r.get("comparison")
        lines.append(f"### {cab}")
        if not comp:
            lines.append("_Нет данных за предыдущую неделю._")
            lines.append("")
            continue
        s = r.get("summary", {})
        lines.append(f"- Индекс локализации: {comp.get('prev_index', 0):.1f}% → {s.get('overall_index', 0):.1f}% ({_sign(comp.get('index_change', 0))} п.п.)")
        lines.append(f"- ИЛ: {comp.get('prev_il_current', 1.0):.2f} → {s.get('il_current', 1.0):.2f} ({_sign(comp.get('il_current_change', 0))})")
        lines.append(f"- ИРП: {comp.get('prev_irp_current', 0):.2f}% → {s.get('irp_current', 0):.2f}% ({_sign(comp.get('irp_current_change', 0))} п.п.)")

        impact_change = comp.get("irp_impact_change", 0)
        label = "экономия" if impact_change < 0 else "рост"
        lines.append(
            f"- Переплата: {_fmt_rub(comp.get('prev_irp_impact', 0))} → "
            f"{_fmt_rub(s.get('irp_impact_rub_month', 0))} ₽/мес "
            f"({label} {_fmt_rub(abs(impact_change))} ₽/мес)"
        )

        zone_change = comp.get("irp_zone_sku_change", 0)
        lines.append(f"- SKU в ИРП-зоне: {comp.get('prev_irp_zone_sku', 0)} → {s.get('irp_zone_sku', 0)} ({_sign(zone_change)})")

        improved = comp.get("regions_improved", [])
        worsened = comp.get("regions_worsened", [])
        lines.append(f"- Улучшенные регионы: {', '.join(improved) if improved else '—'}")
        lines.append(f"- Ухудшенные регионы: {', '.join(worsened) if worsened else '—'}")
        lines.append("")

    # --- Зоны ---
    lines.append("## Зональная разбивка")
    lines.append("")
    header = "| Зона | Описание |"
    sep = "|------|----------|"
    for r in results:
        header += f" {_cab(r.get('cabinet', ''))} |"
        sep += "------|"
    lines.append(header)
    lines.append(sep)

    zones = [
        ("ИРП-зона", "<60%, КРП > 0", "irp_zone_sku"),
        ("ИЛ-зона", "60-74%, КТР > 1", "il_zone_sku"),
    ]
    for zone_name, desc, key in zones:
        row = f"| {zone_name} | {desc} |"
        for r in results:
            row += f" {r.get('summary', {}).get(key, 0)} |"
        lines.append(row)

    ok_row = "| OK | ≥75% |"
    for r in results:
        s = r.get("summary", {})
        ok_count = s.get("sku_with_orders", 0) - s.get("irp_zone_sku", 0) - s.get("il_zone_sku", 0)
        ok_row += f" {max(ok_count, 0)} |"
    lines.append(ok_row)
    lines.append("")

    # --- Топ моделей ---
    lines.append("## Топ моделей по переплате")
    lines.append("")
    lines.append("| # | Модель | Кабинет | Лок% | КРП% | Заказов | Переплата ₽/мес |")
    lines.append("|---|--------|---------|------|------|---------|-----------------|")
    rank = 1
    all_problems = []
    for r in results:
        cab = _cab(r.get("cabinet", ""))
        for p in r.get("top_problems", []):
            all_problems.append((p, cab))
    all_problems.sort(key=lambda x: x[0].get("irp_rub_month", x[0].get("impact", 0)), reverse=True)
    for p, cab in all_problems[:15]:
        lines.append(
            f"| {rank} | {p.get('article', '')} | {cab} | {p.get('index', 0):.0f}% "
            f"| {p.get('krp_pct', 0):.2f}% "
            f"| {p.get('orders', 0)} | {_fmt_rub(p.get('irp_rub_month', p.get('impact', 0)))} |"
        )
        rank += 1
    lines.append("")

    # --- Регионы ---
    lines.append("## Регионы")
    lines.append("")
    header = "| Регион |"
    sep = "|--------|"
    for r in results:
        cab = _cab(r.get("cabinet", ""))
        header += f" Лок% {cab} |"
        sep += "----------|"
    header += " Рекомендация |"
    sep += "-------------|"
    lines.append(header)
    lines.append(sep)

    all_regions: dict[str, dict] = {}
    for r in results:
        cab = _cab(r.get("cabinet", ""))
        for reg in r.get("regions", []):
            name = reg.get("region", "")
            if name not in all_regions:
                all_regions[name] = {"recommendation": reg.get("recommendation", "")}
            all_regions[name][cab] = reg.get("index", 0)

    for name, data in sorted(all_regions.items(), key=lambda x: min(v for k, v in x[1].items() if isinstance(v, (int, float))), reverse=False):
        row = f"| {name} |"
        for r in results:
            cab = _cab(r.get("cabinet", ""))
            val = data.get(cab, "—")
            row += f" {val:.1f}% |" if isinstance(val, (int, float)) else f" {val} |"
        row += f" {data.get('recommendation', '')} |"
        lines.append(row)
    lines.append("")

    # --- Рекомендации ---
    lines.append("## Рекомендации")
    lines.append("")
    for r in results:
        cab = _cab(r.get("cabinet", ""))
        s = r.get("summary", {})
        if s.get("irp_zone_sku", 0) > 0:
            lines.append(f"- **{cab}**: {s['irp_zone_sku']} артикулов в ИРП-зоне — переплата {_fmt_rub(s.get('irp_impact_rub_month', 0))} ₽/мес. Приоритет перестановок.")
        if s.get("il_zone_sku", 0) > 0:
            lines.append(f"- **{cab}**: {s['il_zone_sku']} артикулов в ИЛ-зоне (60-74%) — наценка на логистику через КТР.")

    total_impact = sum(r.get("summary", {}).get("irp_impact_rub_month", 0) for r in results)
    if total_impact > 0:
        lines.append(f"- Общая ИРП-переплата по всем кабинетам: **{_fmt_rub(total_impact)} ₽/мес**")

    return "\n".join(lines)


def format_localization_tg_summary(results: list[dict]) -> str:
    """Short BBCode summary for Telegram (3-5 lines)."""
    now = datetime.now()
    week_from = (now - timedelta(days=7)).strftime("%d.%m")
    week_to = (now - timedelta(days=1)).strftime("%d.%m")

    lines = [f"<b>Логистические расходы WB</b> (неделя {week_from}—{week_to})"]
    for r in results:
        cab = _cab(r.get("cabinet", ""))
        s = r.get("summary", {})
        impact_k = s.get("irp_impact_rub_month", 0) / 1000
        lines.append(
            f"{cab}: ИЛ {s.get('il_current', 1.0):.2f} / ИРП {s.get('irp_current', 0):.2f}% "
            f"/ переплата {impact_k:.1f}K₽"
        )
    # Dynamics line
    total_change = sum(
        (r.get("comparison") or {}).get("irp_impact_change", 0) for r in results
    )
    if total_change != 0:
        label = "экономия" if total_change < 0 else "рост"
        lines.append(f"Динамика: {label} {abs(total_change)/1000:.1f}K₽ vs прошлая неделя")

    return "\n".join(lines)
```

- [ ] **Step 4: Run test — verify it passes**

Run: `python3 -m pytest tests/wb_localization/test_report_md.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add services/wb_localization/report_md.py tests/wb_localization/test_report_md.py
git commit -m "feat: add deterministic MD formatter for localization weekly report"
```

---

### Task 6: Config, Notion Report Type, Scheduler Job

**Files:**
- Modify: `agents/v3/config.py:64-72`
- Modify: `agents/v3/delivery/notion.py:29-44`
- Modify: `agents/v3/scheduler.py:644-845`

- [ ] **Step 1: Add config vars**

In `agents/v3/config.py`, after `FINOLOG_WEEKLY_REPORT_TIME` (line 71):

```python
LOCALIZATION_WEEKLY_REPORT_TIME: str = os.getenv("LOCALIZATION_WEEKLY_REPORT_TIME", "13:00")
LOCALIZATION_WEEKLY_ENABLED: bool = os.getenv("LOCALIZATION_WEEKLY_ENABLED", "true").lower() in ("true", "1", "yes")
```

- [ ] **Step 2: Add report type to Notion delivery**

In `agents/v3/delivery/notion.py`, add to `_REPORT_TYPE_MAP` (after line 44):

```python
    "localization_weekly":        ("Анализ логистических расходов", "Анализ логистических расходов"),
    "localization_weekly_report": ("Анализ логистических расходов", "Анализ логистических расходов"),
```

- [ ] **Step 3: Add scheduler job function**

In `agents/v3/scheduler.py`, add the job function (before `_setup_legacy_scheduler`):

```python
async def _job_localization_weekly() -> None:
    """Cron callback: weekly localization / logistics cost report (Monday)."""
    import asyncio
    from services.wb_localization.run_localization import run_service_report
    from services.wb_localization.report_md import (
        format_localization_weekly_md,
        format_localization_tg_summary,
    )
    from services.wb_localization.history import History

    date_to = _yesterday_msk()
    date_from = (datetime.strptime(date_to, "%Y-%m-%d") - timedelta(days=6)).strftime("%Y-%m-%d")

    if state.is_delivered("localization_weekly", date_to):
        logger.info("localization_weekly already delivered for %s", date_to)
        return

    logger.info("Starting localization weekly report for %s — %s", date_from, date_to)
    history = History()

    # Load average base logistics tariff from WB API (fallback: 80₽)
    avg_base_logistics = 80.0
    try:
        from shared.clients.wb_client import WBClient
        from services.sheets_sync.config import CABINET_OOO
        client = WBClient(api_key=CABINET_OOO.wb_api_key, cabinet_name="ooo")
        try:
            tariffs = client.get_box_tariffs()
            if tariffs:
                # Average of base logistics rates across warehouses
                rates = [t.get("deliveryBase", 0) for t in tariffs if t.get("deliveryBase", 0) > 0]
                if rates:
                    avg_base_logistics = sum(rates) / len(rates)
                    logger.info("Avg base logistics tariff: %.1f₽", avg_base_logistics)
        finally:
            client.close()
    except Exception as e:
        logger.warning("Failed to load tariffs, using default %.0f₽: %s", avg_base_logistics, e)

    cabinets = _get_cabinets()
    results: list[dict] = []
    caveats: list[str] = []

    for i, (cab_key, cabinet) in enumerate(cabinets):
        try:
            result = await asyncio.to_thread(
                run_service_report,
                cabinet_key=cab_key,
                days=91,
                history_store=history,
            )
            # Attach tariff for Sheets export savings calculation
            result["_avg_base_logistics"] = avg_base_logistics
            result["_period_days"] = 91
            results.append(result)
        except Exception as e:
            logger.error("Localization report failed for %s: %s", cab_key, e)
            caveats.append(f"Кабинет {cab_key}: ошибка ({e})")
        if i < len(cabinets) - 1:
            await asyncio.sleep(60)

    if not results:
        logger.error("No localization results — skipping delivery")
        return

    md = format_localization_weekly_md(results, period_days=91)
    tg = format_localization_tg_summary(results)

    envelope = {
        "status": "success",
        "report": {"detailed_report": md, "telegram_summary": tg},
        "agents_called": 0,
    }

    await _deliver(envelope, "localization_weekly", date_from, date_to, caveats=caveats or None)
    state.mark_delivered("localization_weekly", date_to)
    logger.info("Localization weekly delivered for %s", date_to)
```

Note: `_get_cabinets()` and `_yesterday_msk()` are existing helper functions in scheduler.py. Verify they exist; if not, use the pattern from `_job_weekly_report`.

- [ ] **Step 4: Register cron job in _setup_legacy_scheduler()**

In `_setup_legacy_scheduler()`, add after the last job:

```python
    # ── 16. Localization weekly (Monday) ──────────────────────────
    if config.LOCALIZATION_WEEKLY_ENABLED:
        loc_h, loc_m = _parse_hm(config.LOCALIZATION_WEEKLY_REPORT_TIME)
        scheduler.add_job(
            _job_localization_weekly,
            trigger=CronTrigger(day_of_week="mon", hour=loc_h, minute=loc_m, timezone=config.TIMEZONE),
            id="localization_weekly",
            **job_defaults,
        )
```

- [ ] **Step 5: Register in _setup_conductor_scheduler()**

Add same job registration in `_setup_conductor_scheduler()` (localization is independent of financial data gates):

```python
    # Localization weekly (independent of financial gates)
    if config.LOCALIZATION_WEEKLY_ENABLED:
        loc_h, loc_m = _parse_hm(config.LOCALIZATION_WEEKLY_REPORT_TIME)
        scheduler.add_job(
            _job_localization_weekly,
            trigger=CronTrigger(day_of_week="mon", hour=loc_h, minute=loc_m, timezone=config.TIMEZONE),
            id="localization_weekly",
            **job_defaults,
        )
```

- [ ] **Step 6: Verify syntax of all modified files**

```bash
python3 -c "
import ast
for f in ['agents/v3/config.py', 'agents/v3/delivery/notion.py', 'agents/v3/scheduler.py']:
    ast.parse(open(f).read())
    print(f'{f}: OK')
"
```
Expected: all OK

- [ ] **Step 7: Commit**

```bash
git add agents/v3/config.py agents/v3/delivery/notion.py agents/v3/scheduler.py
git commit -m "feat: add localization weekly scheduler job and Notion delivery"
```

---

### Task 7: End-to-End Verification

- [ ] **Step 1: Run all tests**

```bash
python3 -m pytest tests/wb_localization/ -v
```

Expected: ALL PASS

- [ ] **Step 2: Syntax check all modified files**

```bash
python3 -c "
import ast
files = [
    'services/wb_localization/irp_coefficients.py',
    'scripts/calc_irp.py',
    'services/wb_localization/history.py',
    'services/wb_localization/run_localization.py',
    'services/wb_localization/sheets_export.py',
    'services/wb_localization/report_md.py',
    'agents/v3/config.py',
    'agents/v3/scheduler.py',
    'agents/v3/delivery/notion.py',
]
for f in files:
    ast.parse(open(f).read())
    print(f'{f}: OK')
"
```

- [ ] **Step 3: Verify KTR update**

```bash
python3 -c "from services.wb_localization.irp_coefficients import get_ktr_krp; print(get_ktr_krp(57))"
```
Expected: `(1.05, 2.0)`

- [ ] **Step 4: Verify history round-trip**

```bash
python3 -c "
from services.wb_localization.history import History
import tempfile, pathlib
h = History(db_path=pathlib.Path(tempfile.mkdtemp()) / 'test.db')
h.save_run({'cabinet': 'test', 'timestamp': '2026-03-25', 'report_path': '', 'summary': {'il_current': 0.98, 'irp_current': 0.42, 'irp_zone_sku': 12, 'il_zone_sku': 30, 'irp_impact_rub_month': 45200}, 'regions': [], 'top_problems': []})
r = h.get_latest('test')
print(r['summary']['il_current'], r['summary']['irp_current'], r['summary']['irp_impact_rub_month'])
"
```
Expected: `0.98 0.42 45200.0`

- [ ] **Step 5: Final commit (if any fixups needed)**

```bash
git add -u && git commit -m "fix: address e2e verification issues"
```
