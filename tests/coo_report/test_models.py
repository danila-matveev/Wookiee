from unittest.mock import patch
from datetime import date
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from modules.coo_report.collectors.models import collect

WB_MODEL_ROWS = [
    ('current', 'wendy', 80, 2_000_000, 80_000, 30_000, 400_000, 600_000),
    ('current', 'vuki',  40, 900_000,   30_000, 10_000, 150_000, 270_000),
    ('previous', 'wendy', 70, 1_600_000, 60_000, 20_000, 300_000, 480_000),
]
WB_ORDERS_ROWS = [
    ('current', 'wendy', 85, 2_100_000),
    ('current', 'vuki',  42, 940_000),
    ('previous', 'wendy', 72, 1_650_000),
]
OZON_MODEL_ROWS = [
    ('current', 'wendy', 20, 500_000, 20_000, 5_000, 100_000, 150_000),
]
OZON_ORDERS_ROWS = [
    ('current', 'wendy', 22, 520_000),
]


@patch('modules.coo_report.collectors.models.get_ozon_orders_by_model', return_value=OZON_ORDERS_ROWS)
@patch('modules.coo_report.collectors.models.get_ozon_by_model', return_value=OZON_MODEL_ROWS)
@patch('modules.coo_report.collectors.models.get_wb_orders_by_model', return_value=WB_ORDERS_ROWS)
@patch('modules.coo_report.collectors.models.get_wb_by_model', return_value=WB_MODEL_ROWS)
def test_models_merged_across_channels(mock_wb, mock_wb_ord, mock_oz, mock_oz_ord):
    result = collect(ref_date=date(2026, 5, 7))

    wendy = result["current"]["wendy"]
    assert wendy["revenue"] == 2_000_000 + 500_000
    assert wendy["margin"] == 400_000 + 100_000


@patch('modules.coo_report.collectors.models.get_ozon_orders_by_model', return_value=OZON_ORDERS_ROWS)
@patch('modules.coo_report.collectors.models.get_ozon_by_model', return_value=OZON_MODEL_ROWS)
@patch('modules.coo_report.collectors.models.get_wb_orders_by_model', return_value=WB_ORDERS_ROWS)
@patch('modules.coo_report.collectors.models.get_wb_by_model', return_value=WB_MODEL_ROWS)
def test_trend_positive_when_revenue_grew(mock_wb, mock_wb_ord, mock_oz, mock_oz_ord):
    result = collect(ref_date=date(2026, 5, 7))

    wendy_curr = result["current"]["wendy"]["revenue"]
    wendy_prev = result["previous"]["wendy"]["revenue"]
    assert wendy_curr > wendy_prev
    assert result["current"]["wendy"]["trend_pct"] > 0


@patch('modules.coo_report.collectors.models.get_ozon_orders_by_model', return_value=[])
@patch('modules.coo_report.collectors.models.get_ozon_by_model', return_value=[])
@patch('modules.coo_report.collectors.models.get_wb_orders_by_model', return_value=WB_ORDERS_ROWS)
@patch('modules.coo_report.collectors.models.get_wb_by_model', return_value=WB_MODEL_ROWS)
def test_drr_calculated_from_orders_rub(mock_wb, mock_wb_ord, mock_oz, mock_oz_ord):
    result = collect(ref_date=date(2026, 5, 7))

    wendy = result["current"]["wendy"]
    expected_drr = (80_000 + 30_000) / 2_100_000 * 100
    assert abs(wendy["drr_pct"] - expected_drr) < 0.01
