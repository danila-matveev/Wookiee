"""Тесты scenario_sheet writer."""
from unittest.mock import MagicMock


def test_scenario_sheet_name_includes_cabinet():
    from services.wb_localization.sheets_export.scenario_sheet import scenario_sheet_name
    assert scenario_sheet_name("ooo") == "Экономика сценариев ooo"


def test_write_scenario_sheet_writes_data():
    from services.wb_localization.sheets_export.scenario_sheet import write_scenario_sheet

    mock_spreadsheet = MagicMock()
    mock_worksheet = MagicMock()
    mock_worksheet.id = 42
    mock_spreadsheet.worksheet.return_value = mock_worksheet

    payload = {
        "period_days": 30,
        "current_il": 1.05,
        "current_loc_pct": 55.0,
        "current_scenario": {
            "label": "Сейчас",
            "level_pct": 55.0,
            "logistics_monthly": 126000.0,
            "irp_monthly": 14500.0,
            "total_monthly": 140500.0,
        },
        "scenarios": [
            {
                "level_pct": 30, "ktr": 1.50, "krp_pct": 2.15,
                "logistics_monthly": 180000.0, "irp_monthly": 28500.0,
                "total_monthly": 208500.0, "delta_vs_current": 68000.0,
                "delta_vs_worst": 0.0, "color": "red",
            },
            {
                "level_pct": 80, "ktr": 0.80, "krp_pct": 0.00,
                "logistics_monthly": 96000.0, "irp_monthly": 0.0,
                "total_monthly": 96000.0, "delta_vs_current": -44500.0,
                "delta_vs_worst": -112500.0, "color": "green",
            },
        ],
        "top_articles": [
            {
                "article": "wendy/xl", "loc_pct": 38, "ktr": 1.40, "krp_pct": 2.10,
                "orders_monthly": 520, "logistics_fact_monthly": 32000,
                "irp_current_monthly": 10920, "contribution_to_il": -12.4,
                "savings_if_80_monthly": 21500, "status": "🔴 Критическая",
            },
        ],
        "relocation_economics": {
            "turnover_monthly": 5200000.0,
            "commission_monthly": 26000.0,
            "breakeven_monthly": 26000.0,
            "max_savings_monthly": 44500.0,
            "net_benefit_monthly": 18500.0,
            "lock_in_days": 90,
        },
    }

    write_scenario_sheet(mock_spreadsheet, "ooo", payload)

    mock_worksheet.clear.assert_called_once()
    assert mock_worksheet.update.call_count >= 1
    assert mock_spreadsheet.batch_update.call_count >= 1


def test_sheet_column_docs_has_all_categories():
    from services.wb_localization.sheets_export.formatters import SHEET_COLUMN_DOCS
    assert "scenarios" in SHEET_COLUMN_DOCS
    assert "top_articles" in SHEET_COLUMN_DOCS
    assert "roadmap" in SHEET_COLUMN_DOCS
    assert "plan" in SHEET_COLUMN_DOCS
