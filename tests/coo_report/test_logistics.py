from unittest.mock import patch
from datetime import date
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from modules.coo_report.collectors.logistics import collect, calculate_gmroi

TURNOVER_DATA = {
    "wendy": {
        "avg_stock": 500.0, "stock_mp": 500.0, "stock_moysklad": 200.0,
        "stock_transit": 50.0, "daily_sales": 5.5, "turnover_days": 90.9,
        "sales_count": 110, "revenue": 2_200_000.0, "margin": 440_000.0,
        "low_sales": False,
    },
    "vuki": {
        "avg_stock": 200.0, "stock_mp": 200.0, "stock_moysklad": 80.0,
        "stock_transit": 20.0, "daily_sales": 2.0, "turnover_days": 100.0,
        "sales_count": 40, "revenue": 800_000.0, "margin": 160_000.0,
        "low_sales": False,
    },
}


def test_gmroi_calculation():
    result = calculate_gmroi(weekly_margin=440_000, avg_stock_units=500, cost_per_unit=18_000)
    assert result > 0
    assert isinstance(result, float)


@patch('modules.coo_report.collectors.logistics.get_localization_index', return_value=67.3)
@patch('modules.coo_report.collectors.logistics.get_wb_turnover_by_model', return_value=TURNOVER_DATA)
def test_collect_structure(mock_turnover, mock_loc):
    result = collect(ref_date=date(2026, 5, 7))

    assert "localization_index" in result
    assert result["localization_index"] == 67.3
    assert "models" in result
    assert "wendy" in result["models"]


@patch('modules.coo_report.collectors.logistics.get_localization_index', return_value=67.3)
@patch('modules.coo_report.collectors.logistics.get_wb_turnover_by_model', return_value=TURNOVER_DATA)
def test_turnover_days_preserved(mock_turnover, mock_loc):
    result = collect(ref_date=date(2026, 5, 7))
    assert result["models"]["wendy"]["turnover_days"] == 90.9


@patch('modules.coo_report.collectors.logistics.get_localization_index', return_value=25.0)
@patch('modules.coo_report.collectors.logistics.get_wb_turnover_by_model', return_value=TURNOVER_DATA)
def test_low_localization_flagged(mock_turnover, mock_loc):
    result = collect(ref_date=date(2026, 5, 7))
    assert result["localization_warning"] is True
