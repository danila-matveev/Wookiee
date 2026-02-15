"""VasilyService — ядро агента по перераспределению товаров между складами WB.

Использование:
    from agents.vasily.service import VasilyService

    svc = VasilyService()
    result = svc.run_report("ooo", days=30)
    print(result["summary"]["overall_index"])
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# Путь к корню проекта
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from services.sheets_sync.config import CABINET_IP, CABINET_OOO

from agents.vasily.run_localization import (
    fetch_wb_data,
    fetch_own_stock,
    transform_remains_to_df_stocks,
    transform_orders_to_df_regions,
)
from agents.vasily.generate_localization_report_v3 import (
    run_analysis,
    load_barcodes,
    load_statuses,
    RUSSIAN_REGIONS,
)
from agents.vasily.wb_localization_mappings import log_unknown_mappings

from agents.vasily.history import History

logger = logging.getLogger(__name__)

CABINETS = {
    "ip": CABINET_IP,
    "ип": CABINET_IP,
    "ooo": CABINET_OOO,
    "ооо": CABINET_OOO,
}


class VasilyService:
    """Расчёт перераспределения товаров между складами WB."""

    def __init__(self):
        self.history = History()

    def run_report(self, cabinet: str, days: int = 30, **kwargs) -> dict:
        """Полный расчёт перестановок.

        Args:
            cabinet: "ip" / "ooo" (или "ип" / "ооо")
            days: период заказов в днях (по умолчанию 30)
            **kwargs: safety_days, min_donor_localization, max_turnover_days

        Returns:
            dict с ключами:
                cabinet, timestamp, report_path,
                summary, regions, top_problems, comparison
        """
        safety_days = kwargs.get("safety_days", 14)
        min_donor_loc = kwargs.get("min_donor_localization", 70)
        max_turnover = kwargs.get("max_turnover_days", 100)

        cab_key = cabinet.lower()
        cab_obj = CABINETS.get(cab_key)
        if cab_obj is None:
            raise ValueError(f"Неизвестный кабинет: {cabinet}. Доступны: ip, ooo")

        timestamp = datetime.now().isoformat(timespec="seconds")
        logger.info("Василий: расчёт для %s, период %d дней", cab_obj.name, days)

        # 1. Общие данные
        sku_db = str(PROJECT_ROOT / "sku_database" / "Спецификации.xlsx")
        barcode_dict = load_barcodes(sku_db)
        statuses = load_statuses(skip=False)
        own_stock = fetch_own_stock()

        # 2. Данные WB API
        remains, orders = fetch_wb_data(cab_obj, days)
        if not remains:
            raise RuntimeError(f"Нет остатков для {cab_obj.name}")
        if not orders:
            raise RuntimeError(f"Нет заказов для {cab_obj.name}")

        log_unknown_mappings(orders)

        # 3. Трансформация
        df_stocks = transform_remains_to_df_stocks(remains)
        df_regions = transform_orders_to_df_regions(orders, df_stocks, days=days)
        if df_regions.empty:
            raise RuntimeError(f"Нет данных по регионам для {cab_obj.name}")

        # 4. Анализ → Excel + DataFrames
        date_str = datetime.now().strftime("%d-%m-%Y")
        output_dir = Path(__file__).parent / "data" / "reports"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"Отчет_локализация_v3_{cab_obj.name}_{date_str}.xlsx"

        analysis = run_analysis(
            df_stocks=df_stocks,
            df_regions=df_regions,
            barcode_dict=barcode_dict,
            period_days=days,
            safety_days=safety_days,
            min_donor_localization=min_donor_loc,
            statuses=statuses,
            output_file=output_file,
            own_stock=own_stock,
            max_turnover_days=max_turnover,
        )

        # 5. Структурированный результат
        result = self._build_result(
            cab_obj.name, timestamp, analysis, str(analysis["report_path"])
        )

        # 5.1. Сырые DataFrames для экспорта (не сохраняются в историю)
        result["_moves_df"] = analysis.get("moves_df", pd.DataFrame())
        result["_supply_df"] = analysis.get("supply_df", pd.DataFrame())

        # 6. Сравнение с предыдущим
        result["comparison"] = self._compare_with_previous(cab_obj.name, result)

        # 7. Сохранить в историю
        self.history.save_run(result)

        return result

    # ------------------------------------------------------------------
    # Преобразование DataFrames → dict
    # ------------------------------------------------------------------

    def _build_result(
        self, cabinet_name: str, timestamp: str, analysis: dict, report_path: str
    ) -> dict:
        sku_stats: pd.DataFrame = analysis["sku_stats"]
        moves_df: pd.DataFrame = analysis["moves_df"]
        supply_df: pd.DataFrame = analysis["supply_df"]
        region_summary: pd.DataFrame = analysis["region_summary"]

        # Общий индекс (средневзвешенный)
        total_local = sku_stats["Локальные"].sum() if "Локальные" in sku_stats.columns else 0
        total_orders = sku_stats["Всего заказов"].sum() if "Всего заказов" in sku_stats.columns else 0
        overall_index = (total_local / total_orders * 100) if total_orders > 0 else 0.0

        # Сводка
        summary = {
            "overall_index": round(overall_index, 1),
            "total_sku": len(sku_stats),
            "sku_with_orders": int((sku_stats["Всего заказов"] > 0).sum()) if "Всего заказов" in sku_stats.columns else 0,
            "movements_count": len(moves_df),
            "movements_qty": int(moves_df["Кол-во"].sum()) if "Кол-во" in moves_df.columns and len(moves_df) > 0 else 0,
            "supplies_count": len(supply_df),
            "supplies_qty": int(supply_df["Кол-во"].sum()) if "Кол-во" in supply_df.columns and len(supply_df) > 0 else 0,
        }

        # Регионы
        regions = []
        if not region_summary.empty:
            for _, row in region_summary.iterrows():
                regions.append({
                    "region": row.get("Регион", ""),
                    "index": round(float(row.get("% локальных", 0)), 1),
                    "stock_share": round(float(row.get("Доля остатков, %", 0)), 1),
                    "order_share": round(float(row.get("Доля заказов, %", 0)), 1),
                    "recommendation": row.get("Рекомендация", ""),
                })

        # Топ проблемных SKU (по impact = заказы × (75 - индекс))
        top_problems = []
        if "Индекс, %" in sku_stats.columns and "Всего заказов" in sku_stats.columns:
            problem = sku_stats[
                (sku_stats["Индекс, %"] < 75) & (sku_stats["Всего заказов"] > 0)
            ].copy()
            problem["impact"] = problem["Всего заказов"] * (75 - problem["Индекс, %"])
            top10 = problem.nlargest(10, "impact")
            for _, r in top10.iterrows():
                top_problems.append({
                    "article": r.get("Артикул продавца", ""),
                    "size": r.get("Размер", ""),
                    "index": round(float(r.get("Индекс, %", 0)), 1),
                    "orders": int(r.get("Всего заказов", 0)),
                    "impact": round(float(r.get("impact", 0)), 0),
                })

        return {
            "cabinet": cabinet_name,
            "timestamp": timestamp,
            "report_path": report_path,
            "summary": summary,
            "regions": regions,
            "top_problems": top_problems,
            "comparison": None,
        }

    # ------------------------------------------------------------------
    # Сравнение с предыдущим расчётом
    # ------------------------------------------------------------------

    def _compare_with_previous(self, cabinet_name: str, current: dict) -> dict | None:
        prev = self.history.get_latest(cabinet_name)
        if prev is None:
            return None

        prev_summary = prev.get("summary", {})
        curr_summary = current.get("summary", {})
        prev_index = prev_summary.get("overall_index", 0)
        curr_index = curr_summary.get("overall_index", 0)

        # Дельта по регионам
        prev_regions = {r["region"]: r["index"] for r in prev.get("regions", [])}
        curr_regions = {r["region"]: r["index"] for r in current.get("regions", [])}

        improved = []
        worsened = []
        for region in curr_regions:
            if region in prev_regions:
                delta = curr_regions[region] - prev_regions[region]
                if delta > 1:
                    improved.append(region)
                elif delta < -1:
                    worsened.append(region)

        return {
            "prev_timestamp": prev.get("timestamp"),
            "prev_index": prev_index,
            "index_change": round(curr_index - prev_index, 1),
            "regions_improved": improved,
            "regions_worsened": worsened,
        }
