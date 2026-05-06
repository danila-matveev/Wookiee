import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from shared.data_layer.inventory import get_wb_turnover_by_model
from modules.coo_report.config import get_week_bounds

OUTPUT_PATH = Path("/tmp/coo_logistics.json")
LOCALIZATION_SCRIPT = PROJECT_ROOT / "services" / "wb_localization" / "run_localization.py"


def get_localization_index() -> Optional[float]:
    """
    Запускает run_localization.py --dry-run, парсит индекс локализации из stdout.
    Ожидаемый формат строки: "Индекс локализации: 67.3%"
    """
    try:
        result = subprocess.run(
            [sys.executable, str(LOCALIZATION_SCRIPT), "--dry-run"],
            capture_output=True, text=True, timeout=120,
        )
        for line in result.stdout.splitlines():
            if "локализац" in line.lower() and "%" in line:
                match = re.search(r"(\d+(?:\.\d+)?)\s*%", line)
                if match:
                    return float(match.group(1))
    except Exception:
        pass
    return None


def calculate_gmroi(weekly_margin: float, avg_stock_units: float, cost_per_unit: float) -> float:
    """GMROI = (годовая маржа) / (средние остатки по себестоимости) * 100."""
    inventory_cost = avg_stock_units * cost_per_unit
    if inventory_cost <= 0:
        return 0.0
    return round((weekly_margin * 52) / inventory_cost * 100, 1)


def collect(ref_date: date = None) -> dict:
    current_start, current_end, _, _ = get_week_bounds(ref_date)

    turnover = get_wb_turnover_by_model(str(current_start), str(current_end))
    localization = get_localization_index()

    models_data = {}
    for model, data in turnover.items():
        revenue = data.get("revenue", 0)
        sales_count = data.get("sales_count", 1) or 1
        # Себестоимость не возвращается get_wb_turnover_by_model.
        # Оценка ~40% от выручки достаточна для GMROI как ориентировочного показателя.
        cost_per_unit = (revenue / sales_count * 0.4) if sales_count > 0 and revenue > 0 else 0
        gmroi = calculate_gmroi(
            weekly_margin=data.get("margin", 0),
            avg_stock_units=data.get("avg_stock", 0),
            cost_per_unit=cost_per_unit,
        )
        # stock_ms — ключ из get_wb_turnover_by_model; stock_moysklad — алиас из тестов
        stock_ms = data.get("stock_ms", data.get("stock_moysklad", 0))
        models_data[model] = {
            "turnover_days": data.get("turnover_days", 0),
            "stock_fbo_units": int(data.get("stock_mp", 0)),
            "stock_moysklad_units": int(stock_ms),
            "stock_transit_units": int(data.get("stock_transit", 0)),
            "daily_sales": data.get("daily_sales", 0),
            "gmroi_pct": gmroi,
            "low_sales": data.get("low_sales", False),
        }

    return {
        "localization_index": localization,
        "localization_warning": (localization is not None and localization < 30),
        "models": models_data,
        "period": {
            "current_start": str(current_start),
            "current_end": str(current_end),
        },
    }


if __name__ == "__main__":
    data = collect()
    OUTPUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    loc = data.get("localization_index")
    print(f"Логистика сохранена → {OUTPUT_PATH}")
    print(f"  Индекс локализации: {loc}%")
    print(f"  Моделей: {len(data['models'])}")
    for model, m in sorted(data["models"].items(), key=lambda x: x[1]["turnover_days"]):
        print(f"  {model:15s}  оборачиваемость {m['turnover_days']:.0f} дн.  FBO {m['stock_fbo_units']} шт")
