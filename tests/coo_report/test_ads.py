from unittest.mock import patch
from datetime import date
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from modules.coo_report.collectors.ads import collect

WB_ADS_ROWS = [
    ('current',  200_000, 80_000, 40_000, 10_000, 330_000),
    ('previous', 180_000, 70_000, 35_000,  8_000, 293_000),
]
OZON_ADS_ROWS = [
    ('current',  50_000, 20_000, 5_000, 75_000),
    ('previous', 45_000, 15_000, 4_000, 64_000),
]


@patch('modules.coo_report.collectors.ads.get_wb_finance')
@patch('modules.coo_report.collectors.ads.get_ozon_external_ad_breakdown')
@patch('modules.coo_report.collectors.ads.get_wb_external_ad_breakdown')
def test_vk_channel_extracted(mock_wb_ads, mock_oz_ads, mock_wb_fin):
    mock_wb_ads.return_value = WB_ADS_ROWS
    mock_oz_ads.return_value = OZON_ADS_ROWS
    mock_wb_fin.return_value = ([], [('current', 150, 5_200_000)])

    result = collect(ref_date=date(2026, 5, 7))

    assert "vk" in result["current"]
    assert result["current"]["vk"]["spend_rub"] == 40_000 + 5_000  # WB + OZON


@patch('modules.coo_report.collectors.ads.get_wb_finance')
@patch('modules.coo_report.collectors.ads.get_ozon_external_ad_breakdown')
@patch('modules.coo_report.collectors.ads.get_wb_external_ad_breakdown')
def test_drr_calculated_for_channels(mock_wb_ads, mock_oz_ads, mock_wb_fin):
    mock_wb_ads.return_value = WB_ADS_ROWS
    mock_oz_ads.return_value = OZON_ADS_ROWS
    mock_wb_fin.return_value = ([], [('current', 150, 5_200_000)])

    result = collect(ref_date=date(2026, 5, 7))

    bloggers = result["current"]["bloggers"]
    # WB bloggers 80k + OZON bloggers 20k = 100k total
    assert bloggers["drr_pct"] == round((80_000 + 20_000) / 5_200_000 * 100, 2)


@patch('modules.coo_report.collectors.ads.get_wb_finance')
@patch('modules.coo_report.collectors.ads.get_ozon_external_ad_breakdown')
@patch('modules.coo_report.collectors.ads.get_wb_external_ad_breakdown')
def test_manual_channels_flagged(mock_wb_ads, mock_oz_ads, mock_wb_fin):
    mock_wb_ads.return_value = WB_ADS_ROWS
    mock_oz_ads.return_value = OZON_ADS_ROWS
    mock_wb_fin.return_value = ([], [('current', 150, 5_200_000)])

    result = collect(ref_date=date(2026, 5, 7))

    assert result["manual_fill_required"] == ["yandex", "vk_seeds_contractor"]
