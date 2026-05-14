"""Runtime mode tests for sheets_sync."""

from __future__ import annotations

import builtins
from types import SimpleNamespace
from unittest.mock import MagicMock

from services.sheets_sync import config, control_panel, runner


def test_test_mode_override_controls_sheet_name():
    original_mode = config.is_test_mode()

    with config.test_mode_override(False):
        assert config.get_sheet_name("Фин данные NEW") == "Фин данные NEW"

    with config.test_mode_override(True):
        assert config.get_sheet_name("Фин данные NEW") == "Фин данные NEW_TEST"

    assert config.is_test_mode() is original_mode


def test_run_sync_applies_mode_override(monkeypatch):
    observed = {}

    def sync():
        observed["sheet"] = config.get_sheet_name("Фин данные NEW")
        return 7

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "fake.sync":
            return SimpleNamespace(sync=sync)
        return real_import(name, globals=globals, locals=locals, fromlist=fromlist, level=level)

    real_import = builtins.__import__
    monkeypatch.setitem(
        runner.SYNC_REGISTRY,
        "fake",
        {"module": "fake.sync", "sheet": "Фин данные NEW", "description": "fake"},
    )
    monkeypatch.setattr(builtins, "__import__", fake_import)

    result = runner.run_sync("fake", test_mode=False)

    assert result.status == "ok"
    assert result.rows == 7
    assert result.test_mode is False
    assert observed["sheet"] == "Фин данные NEW"


def test_sheet_candidates_prioritize_configured_mode(monkeypatch):
    monkeypatch.setattr(config, "TEST_MODE", True)
    assert control_panel._sheet_candidates("Фин данные NEW") == [
        ("Фин данные NEW_TEST", True),
        ("Фин данные NEW", False),
    ]

    monkeypatch.setattr(config, "TEST_MODE", False)
    assert control_panel._sheet_candidates("Фин данные NEW") == [
        ("Фин данные NEW", False),
        ("Фин данные NEW_TEST", True),
    ]


def test_empty_fin_data_new_test_trigger_redirects_to_prod():
    spreadsheet = MagicMock()
    test_ws = MagicMock()
    prod_ws = MagicMock()
    test_ws.col_values.return_value = ["", "", ""]
    prod_ws.col_values.return_value = ["", "", "2000989949060"]
    spreadsheet.worksheet.return_value = prod_ws

    sheet_name, ws, test_mode = control_panel._resolve_trigger_sheet(
        spreadsheet=spreadsheet,
        base_name="Фин данные NEW",
        sheet_name="Фин данные NEW_TEST",
        ws=test_ws,
        test_mode=True,
        sync_name="fin_data_new",
    )

    assert sheet_name == "Фин данные NEW"
    assert ws is prod_ws
    assert test_mode is False
