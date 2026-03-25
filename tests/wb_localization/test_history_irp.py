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
    assert s["il_current"] == 1.0
    assert s["irp_current"] == 0.0
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
    h2 = _make_history(tmp_path)
    latest = h2.get_latest("ooo")
    assert latest["summary"]["il_current"] == 0.99
