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
            {"article": "Joy/shinny_pink", "size": "S", "index": 41.4, "orders": 519, "impact": 12800, "ktr": 1.30, "zone": "ИРП-зона", "krp_pct": 2.10, "irp_rub_month": 12800},
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

def test_tg_summary_short():
    tg = format_localization_tg_summary([_sample_result()])
    assert len(tg) < 500
    assert "Логистические расходы" in tg or "логистическ" in tg.lower()
