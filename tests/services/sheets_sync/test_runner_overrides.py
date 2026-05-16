"""CLI override tests for hub_to_sheets.runner."""
from __future__ import annotations

from unittest.mock import patch

from services.sheets_sync.hub_to_sheets import runner
from services.sheets_sync.hub_to_sheets.config import SheetSpec


def test_retarget_view_swaps_schema():
    spec = SheetSpec(
        sheet_name="Все модели",
        view_name="public.vw_export_modeli",
        anchor_cols=("Модель",),
        status_col="Статус",
    )
    out = runner._retarget_view(spec, "test_catalog_sync")
    assert out.view_name == "test_catalog_sync.vw_export_modeli"
    assert out.sheet_name == spec.sheet_name
    assert out.anchor_cols == spec.anchor_cols
    assert out.status_col == spec.status_col


def test_retarget_view_passthrough_for_public_or_empty():
    spec = SheetSpec(
        sheet_name="X",
        view_name="public.vw_export_x",
        anchor_cols=("X",),
        status_col=None,
    )
    assert runner._retarget_view(spec, "public") is spec
    assert runner._retarget_view(spec, "") is spec


def test_sync_one_respects_spreadsheet_id_override():
    captured = {}

    class FakeWriter:
        def __init__(self, spreadsheet_id="", *, dry_run=False):
            captured["spreadsheet_id"] = spreadsheet_id
            captured["dry_run"] = dry_run

    fake_metrics = {"sheet": "Все модели", "cells_updated": 0, "rows_appended": 0, "rows_deleted": 0}
    with patch.object(runner, "SheetsBatchWriter", FakeWriter), \
         patch.object(runner, "_sync_one", return_value=fake_metrics):
        runner.sync_one("Все модели", spreadsheet_id="TEST_ID_123", views_schema="public")

    assert captured["spreadsheet_id"] == "TEST_ID_123"


def test_sync_one_respects_views_schema_override():
    received_specs = []

    class FakeWriter:
        def __init__(self, *args, **kwargs):
            pass

    def fake_sync_one(spec, writer):
        received_specs.append(spec)
        return {"sheet": spec.sheet_name, "cells_updated": 0, "rows_appended": 0, "rows_deleted": 0}

    with patch.object(runner, "SheetsBatchWriter", FakeWriter), \
         patch.object(runner, "_sync_one", side_effect=fake_sync_one):
        runner.sync_one("Все модели", views_schema="test_catalog_sync")

    assert len(received_specs) == 1
    assert received_specs[0].view_name == "test_catalog_sync.vw_export_modeli"


def test_cli_passes_overrides_through():
    captured = {}

    def fake_sync_one(sheet_name, *, dry_run, spreadsheet_id, views_schema):
        captured["sheet_name"] = sheet_name
        captured["dry_run"] = dry_run
        captured["spreadsheet_id"] = spreadsheet_id
        captured["views_schema"] = views_schema
        return {"status": "ok", "sheet": sheet_name}

    with patch.object(runner, "sync_one", side_effect=fake_sync_one):
        rc = runner.main([
            "--sheet", "Все модели",
            "--spreadsheet-id", "TEST_ID_XYZ",
            "--views-schema", "test_catalog_sync",
        ])

    assert rc == 0
    assert captured == {
        "sheet_name": "Все модели",
        "dry_run": False,
        "spreadsheet_id": "TEST_ID_XYZ",
        "views_schema": "test_catalog_sync",
    }
