"""ABC-аудит: главный коллектор данных.

Запуск:
    python3 scripts/abc_audit/collect_data.py --date 2026-04-11
    python3 scripts/abc_audit/collect_data.py  # по умолчанию: сегодня
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from scripts.abc_audit.utils import compute_abc_date_params, build_abc_quality_flags
from scripts.abc_audit.collectors.finance import collect_finance
from shared.tool_logger import ToolLogger
from scripts.abc_audit.collectors.inventory import collect_inventory
from scripts.abc_audit.collectors.hierarchy import collect_hierarchy
from scripts.abc_audit.collectors.buyouts import collect_buyouts, collect_size_data


def run_collection(cut_date_str: str | None = None) -> dict:
    """Запускает все коллекторы параллельно и объединяет результаты.

    Args:
        cut_date_str: Дата отсечки YYYY-MM-DD (по умолчанию — сегодня).

    Returns:
        Единый JSON с блоками finance, inventory, hierarchy, buyouts, sizes, meta.
    """
    if cut_date_str is None:
        cut_date_str = datetime.now().strftime("%Y-%m-%d")

    t0 = time.time()
    params = compute_abc_date_params(cut_date_str)

    p30s = params["p30_start"]
    p90s = params["p90_start"]
    p180s = params["p180_start"]
    end_ex = params["p30_end_exclusive"]

    tasks = {
        "finance": lambda: collect_finance(
            p30s, end_ex, p90s, end_ex, p180s, end_ex,
            params["m1_start"], params["m1_end"],
            params["m2_start"], params["m2_end"],
            params["m3_start"], params["m3_end"],
        ),
        "inventory": lambda: collect_inventory(p30s, end_ex),
        "hierarchy": lambda: collect_hierarchy(),
        "buyouts": lambda: collect_buyouts(p30s, end_ex),
        "sizes": lambda: collect_size_data(p30s, end_ex),
    }

    results: dict = {}
    errors: dict = {}
    inventory_meta: dict = {}

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fn): name for name, fn in tasks.items()}
        for future in as_completed(futures):
            name = futures[future]
            try:
                block = future.result()
                # Inventory возвращает доп. meta
                if name == "inventory" and "meta" in block:
                    inventory_meta = block.pop("meta")
                results.update(block)
            except Exception as e:
                errors[name] = str(e)
                results[name] = {}

    # Подсчёт покрытия
    hierarchy = results.get("hierarchy", {})
    status_counts = hierarchy.get("status_counts", {})
    active_statuses = {"Продается", "Выводим", "Новый", "Запуск"}
    supabase_active = sum(
        v for k, v in status_counts.items() if k in active_statuses
    )
    finance_articles = len(results.get("finance", {}))

    results["meta"] = {
        "cut_date": params["cut_date"],
        "p30_start": p30s,
        "p90_start": p90s,
        "p180_start": p180s,
        "end_exclusive": end_ex,
        "year_ago_start": params["year_ago_start"],
        "year_ago_end": params["year_ago_end"],
        "m1_start": params["m1_start"],
        "m1_end": params["m1_end"],
        "m2_start": params["m2_start"],
        "m2_end": params["m2_end"],
        "m3_start": params["m3_start"],
        "m3_end": params["m3_end"],
        "collected_at": datetime.now().isoformat(timespec="seconds"),
        "duration_sec": round(time.time() - t0, 1),
        "errors": errors,
        "quality_flags": build_abc_quality_flags(
            errors=errors,
            article_count=finance_articles,
            supabase_count=supabase_active,
            moysklad_stale=inventory_meta.get("moysklad_stale", False),
        ),
    }

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Сбор данных для ABC-аудита")
    parser.add_argument(
        "--date",
        default=None,
        help="Дата отсечки YYYY-MM-DD (по умолчанию: сегодня)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Путь для сохранения JSON (по умолчанию: /tmp/abc-audit-{DATE}.json)",
    )
    args = parser.parse_args()

    tl = ToolLogger("/abc-audit")
    with tl.run(period_start=args.date or datetime.now().strftime("%Y-%m-%d"),
                period_end=args.date or datetime.now().strftime("%Y-%m-%d")) as run_meta:
        data = run_collection(args.date)

        cut_date = data["meta"]["cut_date"]
        output_path = args.output or f"/tmp/abc-audit-{cut_date}.json"

        output = json.dumps(data, ensure_ascii=False, default=str)
        with open(output_path, "w") as f:
            f.write(output)

        duration = data["meta"]["duration_sec"]
        err_count = len(data["meta"]["errors"])
        print(
            f"ABC-audit data collected: {output_path} "
            f"({len(output)} bytes, {duration}s, {err_count} errors)",
            file=sys.stderr,
        )

        run_meta["items"] = data["meta"].get("sku_count", 0)
        if err_count:
            run_meta["notes"] = f"{err_count} errors"


if __name__ == "__main__":
    main()
