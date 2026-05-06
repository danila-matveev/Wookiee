import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from shared.data_layer.advertising import get_wb_external_ad_breakdown, get_ozon_external_ad_breakdown
from shared.data_layer.finance import get_wb_finance
from modules.coo_report.config import get_week_bounds

OUTPUT_PATH = Path("/tmp/coo_ads.json")


def collect(ref_date: date = None) -> dict:
    """
    Ограничение БД: ВК и блогеры агрегированы в группы, гранулярная разбивка
    (посевы ВК отдельно от таргета, посевы подрядчик отдельно от блогеров)
    недоступна. Яндекс реклама в БД отсутствует.
    """
    current_start, current_end, prev_start, _ = get_week_bounds(ref_date)

    wb_rows = get_wb_external_ad_breakdown(current_start, prev_start, current_end)
    ozon_rows = get_ozon_external_ad_breakdown(current_start, prev_start, current_end)
    _, wb_orders_rows = get_wb_finance(current_start, prev_start, current_end)

    orders_by_period = {row[0]: float(row[2] or 0) for row in wb_orders_rows}

    wb_by_period: dict = {}
    for row in wb_rows:
        period = row[0]
        wb_by_period[period] = {
            "internal": float(row[1] or 0),
            "bloggers": float(row[2] or 0),
            "vk": float(row[3] or 0),
            "creators": float(row[4] or 0),
        }

    ozon_by_period: dict = {}
    for row in ozon_rows:
        period = row[0]
        ozon_by_period[period] = {
            "internal": float(row[1] or 0),
            "bloggers": float(row[2] or 0),
            "vk": float(row[3] or 0),
        }

    result_by_period: dict = {}
    for period in set(list(wb_by_period.keys()) + list(ozon_by_period.keys())):
        wb = wb_by_period.get(period, {})
        oz = ozon_by_period.get(period, {})
        orders_rub = orders_by_period.get(period, 0)

        def _drr(spend: float) -> float:
            return round(spend / orders_rub * 100, 2) if orders_rub > 0 else 0.0

        bloggers_spend = wb.get("bloggers", 0) + oz.get("bloggers", 0)
        vk_spend = wb.get("vk", 0) + oz.get("vk", 0)
        creators_spend = wb.get("creators", 0)
        internal_wb_spend = wb.get("internal", 0)

        result_by_period[period] = {
            "bloggers": {"spend_rub": bloggers_spend, "drr_pct": _drr(bloggers_spend)},
            "vk": {"spend_rub": vk_spend, "drr_pct": _drr(vk_spend)},
            "creators": {"spend_rub": creators_spend, "drr_pct": _drr(creators_spend)},
            "internal_wb": {"spend_rub": internal_wb_spend, "drr_pct": _drr(internal_wb_spend)},
            "orders_rub": orders_rub,
        }

    return {
        **result_by_period,
        "manual_fill_required": ["yandex", "vk_seeds_contractor"],
        "note": (
            "ВК и блогеры агрегированы в группы. "
            "Разбивка на посевы ВК / посевы подрядчик / таргет — недоступна из БД. "
            "Яндекс — заполнить вручную из рекламного кабинета."
        ),
        "period": {
            "current_start": str(current_start),
            "current_end": str(current_end),
        },
    }


if __name__ == "__main__":
    ref = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else None
    data = collect(ref)
    OUTPUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Реклама сохранена → {OUTPUT_PATH}")
    for channel, stats in data.get("current", {}).items():
        if isinstance(stats, dict) and "spend_rub" in stats:
            print(f"  {channel:20s}  {stats['spend_rub']:>10,.0f} ₽  ДРР {stats['drr_pct']:.1f}%")
