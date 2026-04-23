"""Тесты roadmap_sheet writer."""
from unittest.mock import MagicMock


def test_sheet_name_includes_cabinet():
    from services.wb_localization.sheets_export.roadmap_sheet import roadmap_sheet_name
    assert roadmap_sheet_name("ooo") == "Перестановки Roadmap ooo"


def test_write_roadmap_sheet_writes_14_weeks():
    from services.wb_localization.sheets_export.roadmap_sheet import write_roadmap_sheet

    mock_spreadsheet = MagicMock()
    mock_worksheet = MagicMock()
    mock_worksheet.id = 77
    mock_spreadsheet.worksheet.return_value = mock_worksheet

    payload = {
        "params": {
            "realistic_limit_pct": 0.3,
            "target_localization": 85.0,
            "period_days": 30,
            "total_plan_qty": 4200,
            "articles_with_movements": 23,
        },
        "roadmap": [
            {
                "week": i,
                "date": f"2026-04-{16+i:02d}",
                "moved_units_cumulative": i * 300,
                "plan_pct": i * 7.5,
                "il_forecast": 55 + i * 2,
                "ktr_weighted": 1.05 - i * 0.02,
                "logistics_monthly": 140000 - i * 4000,
                "irp_monthly": 14000 - i * 1000,
                "total_monthly": 140500 - i * 3500,
                "savings_vs_current": -i * 3500,
            }
            for i in range(14)
        ],
        "schedule": {str(i): [{"article": f"A{i}", "qty": 300}] for i in range(14)},
        "milestones": {"week_60pct": 4, "week_80pct": 9},
        "movements_plan": [
            {
                "rank": 1, "priority": "P1", "article": "wendy/xl", "size": "XL",
                "loc_pct_current": 38, "from_fd": "Центральный", "to_fd": "Уральский",
                "from_stock_surplus": 420, "to_stock_deficit": 320,
                "qty": 320, "impact_il_pp": 1.6, "savings_monthly": 21500,
                "warehouse_limit_status": "✅", "start_week": 1,
            },
        ],
    }

    write_roadmap_sheet(mock_spreadsheet, "ooo", payload)

    mock_worksheet.clear.assert_called_once()
    assert mock_worksheet.update.call_count >= 1
    assert mock_spreadsheet.batch_update.call_count >= 1


def test_write_roadmap_handles_no_milestones():
    """Если milestones None — не должно падать."""
    from services.wb_localization.sheets_export.roadmap_sheet import write_roadmap_sheet

    mock_spreadsheet = MagicMock()
    mock_worksheet = MagicMock()
    mock_worksheet.id = 77
    mock_spreadsheet.worksheet.return_value = mock_worksheet

    payload = {
        "params": {
            "realistic_limit_pct": 0.3, "target_localization": 85.0,
            "period_days": 30, "total_plan_qty": 0, "articles_with_movements": 0,
        },
        "roadmap": [
            {
                "week": 0, "date": "2026-04-16",
                "moved_units_cumulative": 0, "plan_pct": 0,
                "il_forecast": 55, "ktr_weighted": 1.05,
                "logistics_monthly": 140000, "irp_monthly": 14000,
                "total_monthly": 154000, "savings_vs_current": 0,
            }
        ],
        "schedule": {},
        "milestones": {"week_60pct": None, "week_80pct": None},
        "movements_plan": [],
    }

    write_roadmap_sheet(mock_spreadsheet, "ooo", payload)
    mock_worksheet.clear.assert_called_once()
