from unittest.mock import patch
from datetime import date
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from modules.coo_report.collectors.finance import collect


WB_FINANCE_ROW_CURRENT = (
    'current', 150, 120,
    5_000_000, 4_200_000,
    200_000, 80_000,
    1_500_000, 300_000,
    150_000, 420_000,
    300_000, 50_000,
    10_000, 5_000, 3_000,
    820_000,
    100_000, 5_100_000,
)
WB_ORDERS_ROW_CURRENT = ('current', 155, 5_200_000)

OZON_FINANCE_ROW_CURRENT = (
    'current', 60, 1_800_000, 1_600_000,
    50_000, 20_000,
    280_000, 600_000,
    90_000, 30_000, 160_000,
    80_000, 15_000,
)
OZON_ORDERS_ROW_CURRENT = ('current', 65, 1_850_000)


@patch('modules.coo_report.collectors.finance.get_ozon_finance')
@patch('modules.coo_report.collectors.finance.get_wb_finance')
def test_collect_returns_required_keys(mock_wb, mock_ozon):
    mock_wb.return_value = ([WB_FINANCE_ROW_CURRENT], [WB_ORDERS_ROW_CURRENT])
    mock_ozon.return_value = ([OZON_FINANCE_ROW_CURRENT], [OZON_ORDERS_ROW_CURRENT])

    result = collect(ref_date=date(2026, 5, 7))

    assert "wb" in result
    assert "ozon" in result
    assert "combined" in result
    assert "period" in result
    assert result["period"]["current_start"] == "2026-05-04"


@patch('modules.coo_report.collectors.finance.get_ozon_finance')
@patch('modules.coo_report.collectors.finance.get_wb_finance')
def test_drr_internal_calculation(mock_wb, mock_ozon):
    mock_wb.return_value = ([WB_FINANCE_ROW_CURRENT], [WB_ORDERS_ROW_CURRENT])
    mock_ozon.return_value = ([OZON_FINANCE_ROW_CURRENT], [OZON_ORDERS_ROW_CURRENT])

    result = collect(ref_date=date(2026, 5, 7))

    wb = result["wb"]["current"]
    assert abs(wb["drr_internal_pct"] - 200_000 / 5_200_000 * 100) < 0.01


@patch('modules.coo_report.collectors.finance.get_ozon_finance')
@patch('modules.coo_report.collectors.finance.get_wb_finance')
def test_combined_revenue_is_sum_of_channels(mock_wb, mock_ozon):
    mock_wb.return_value = ([WB_FINANCE_ROW_CURRENT], [WB_ORDERS_ROW_CURRENT])
    mock_ozon.return_value = ([OZON_FINANCE_ROW_CURRENT], [OZON_ORDERS_ROW_CURRENT])

    result = collect(ref_date=date(2026, 5, 7))

    combined = result["combined"]["current"]
    expected_revenue = 4_200_000 + 1_600_000
    assert combined["revenue_after_spp"] == expected_revenue
