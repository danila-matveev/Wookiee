#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Калькулятор ИЛ (Индекс Локализации) и ИРП (Индекс Распределения Продаж)
для Wildberries.

Рассчитывает оба индекса по правилам WB (с 27.03.2026):
  1. Загружает заказы за последние 13 недель через WB Statistics API
  2. Определяет долю локализации каждого артикула
  3. По таблице КТР/КРП находит коэффициенты
  4. ИЛ = средневзвешенный КТР по артикулам (вес = кол-во заказов)
  5. ИРП = средневзвешенный КРП по артикулам (вес = кол-во заказов)

Формула логистики WB:
  Логистика = (литр₁ + доп_литры) × Коэфф_склада × ИЛ + Цена_товара × ИРП

Использование:
  python scripts/calc_irp.py                    # ООО, последние 13 недель
  python scripts/calc_irp.py --cabinet ip       # ИП
  python scripts/calc_irp.py --date-from 2025-12-22 --date-to 2026-03-22
  python scripts/calc_irp.py --top 20           # показать топ-20 артикулов
"""

import argparse
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shared.clients.wb_client import WBClient
from services.sheets_sync.config import CABINET_IP, CABINET_OOO
from services.wb_localization.wb_localization_mappings import (
    get_warehouse_fd,
    get_delivery_fd,
    SKIP_WAREHOUSES,
)

# ============================================================================
# Таблица коэффициентов WB (с 27.03.2026)
# Источник: wb partners → Тарифы → Тарифы складов → "Индексы локализации
# и распределения продаж"
# ============================================================================
# (min_loc, max_loc, КТР, КРП%)
# КТР — для расчёта ИЛ (множитель к стоимости логистики)
# КРП — для расчёта ИРП (% от цены товара)

COEFF_TABLE = [
    # Высокая локализация — скидка на логистику, КРП = 0
    (95.00, 100.00, 0.50, 0.00),
    (90.00,  94.99, 0.60, 0.00),
    (85.00,  89.99, 0.70, 0.00),
    (80.00,  84.99, 0.80, 0.00),
    (75.00,  79.99, 0.90, 0.00),
    (70.00,  74.99, 1.00, 0.00),
    (65.00,  69.99, 1.00, 0.00),
    (60.00,  64.99, 1.00, 0.00),
    # Низкая локализация — наценка + КРП > 0
    (55.00,  59.99, 1.05, 2.00),
    (50.00,  54.99, 1.10, 2.05),
    (45.00,  49.99, 1.20, 2.05),
    (40.00,  44.99, 1.30, 2.10),
    (35.00,  39.99, 1.40, 2.10),
    (30.00,  34.99, 1.60, 2.15),
    (25.00,  29.99, 1.70, 2.20),
    (20.00,  24.99, 1.80, 2.25),
    (15.00,  19.99, 1.90, 2.30),
    (10.00,  14.99, 2.00, 2.35),
    ( 5.00,   9.99, 2.10, 2.45),
    ( 0.00,   4.99, 2.20, 2.50),
]


def get_ktr_krp(localization_pct: float) -> tuple[float, float]:
    """Находит КТР и КРП по доле локализации артикула.

    Args:
        localization_pct: доля локальных заказов (0-100%)

    Returns:
        (КТР, КРП%) — коэффициенты из таблицы WB
    """
    loc = max(0.0, min(100.0, localization_pct))
    for min_loc, max_loc, ktr, krp in COEFF_TABLE:
        if min_loc <= loc <= max_loc:
            return ktr, krp
    # Fallback (не должен сработать)
    return 2.20, 2.50


def load_orders(cabinet, date_from: str, date_to: str) -> list[dict]:
    """Загружает заказы из WB Statistics API."""
    client = WBClient(api_key=cabinet.wb_api_key, cabinet_name=cabinet.name)
    try:
        print(f"Загрузка заказов из WB Statistics API ({cabinet.name})...")
        print(f"  date_from: {date_from}")
        orders = client.get_supplier_orders(date_from=date_from)
        print(f"  Получено заказов (всего): {len(orders)}")

        # Фильтрация по дате заказа
        filtered = [
            o for o in orders
            if date_from[:10] <= o.get("date", "")[:10] <= date_to[:10]
        ]
        print(f"  Заказов в периоде ({date_from[:10]} — {date_to[:10]}): {len(filtered)}")
        return filtered
    finally:
        client.close()


def calc_article_localization(orders: list[dict]) -> dict:
    """Считает долю локализации по каждому артикулу.

    Заказ считается ЛОКАЛЬНЫМ, если склад отгрузки и адрес доставки
    находятся в одном федеральном округе.

    Returns:
        dict: {sa_name: {"local": N, "total": N, "loc_pct": float}}
    """
    # Группируем по артикулу поставщика
    article_stats = defaultdict(lambda: {"local": 0, "total": 0})
    skipped = 0
    unknown_wh = set()
    unknown_obl = set()

    for o in orders:
        sa_name = o.get("supplierArticle", "UNKNOWN")
        wh_name = o.get("warehouseName", "")
        delivery_region = o.get("oblastOkrugName", "") or o.get("oblast", "")

        wh_fd = get_warehouse_fd(wh_name)
        delivery_fd = get_delivery_fd(delivery_region)

        if wh_fd is None:
            if wh_name and wh_name not in SKIP_WAREHOUSES:
                unknown_wh.add(wh_name)
            skipped += 1
            continue
        if delivery_fd is None:
            if delivery_region:
                unknown_obl.add(delivery_region)
            skipped += 1
            continue

        is_local = (wh_fd == delivery_fd)
        article_stats[sa_name]["total"] += 1
        if is_local:
            article_stats[sa_name]["local"] += 1

    # Вычисляем % локализации
    for sa, stats in article_stats.items():
        stats["loc_pct"] = (
            stats["local"] / stats["total"] * 100
            if stats["total"] > 0 else 0.0
        )

    if unknown_wh:
        print(f"\n  WARNING: Неизвестные склады ({len(unknown_wh)}): {sorted(unknown_wh)}")
    if unknown_obl:
        print(f"  WARNING: Неизвестные области ({len(unknown_obl)}): {sorted(unknown_obl)}")
    if skipped:
        print(f"  Пропущено заказов (неизвестный склад/область): {skipped}")

    return dict(article_stats)


def calc_indices(article_stats: dict) -> dict:
    """Рассчитывает ИЛ и ИРП по правилам WB.

    ИЛ = Σ(КТР_i × заказы_i) / Σ(заказы_i)
    ИРП = Σ(КРП_i × заказы_i) / Σ(заказы_i)

    Returns:
        dict с полями il, irp, articles (детализация)
    """
    total_orders = 0
    weighted_ktr = 0.0
    weighted_krp = 0.0
    articles_detail = []

    for sa_name, stats in article_stats.items():
        loc_pct = stats["loc_pct"]
        orders_count = stats["total"]
        ktr, krp = get_ktr_krp(loc_pct)

        weighted_ktr += ktr * orders_count
        weighted_krp += krp * orders_count
        total_orders += orders_count

        articles_detail.append({
            "article": sa_name,
            "orders": orders_count,
            "local": stats["local"],
            "loc_pct": loc_pct,
            "ktr": ktr,
            "krp": krp,
        })

    il = weighted_ktr / total_orders if total_orders > 0 else 1.0
    irp = weighted_krp / total_orders if total_orders > 0 else 0.0

    # Сортировка: сначала артикулы с высоким КРП (проблемные), потом по заказам
    articles_detail.sort(key=lambda x: (-x["krp"], -x["orders"]))

    return {
        "il": il,
        "irp": irp,
        "total_orders": total_orders,
        "total_articles": len(articles_detail),
        "articles": articles_detail,
    }


def calc_region_indices(orders: list[dict]) -> dict:
    """Рассчитывает локализацию по регионам (как на скриншоте WB Partners)."""
    region_stats = defaultdict(lambda: {"local": 0, "total": 0})
    skipped = 0

    for o in orders:
        wh_name = o.get("warehouseName", "")
        delivery_region = o.get("oblastOkrugName", "") or o.get("oblast", "")

        wh_fd = get_warehouse_fd(wh_name)
        delivery_fd = get_delivery_fd(delivery_region)

        if wh_fd is None or delivery_fd is None:
            skipped += 1
            continue

        is_local = (wh_fd == delivery_fd)
        region_stats[delivery_fd]["total"] += 1
        if is_local:
            region_stats[delivery_fd]["local"] += 1

    return dict(region_stats)


def print_results(result: dict, top_n: int = 15):
    """Красиво выводит результаты расчёта."""
    print("\n" + "=" * 90)
    print("  РЕЗУЛЬТАТЫ РАСЧЁТА ИЛ и ИРП")
    print("=" * 90)

    print(f"\n  Индекс Локализации (ИЛ):          {result['il']:.2f}")
    print(f"  Индекс Распределения Продаж (ИРП): {result['irp']:.2f}%")
    print(f"  Всего артикулов:                   {result['total_articles']}")
    print(f"  Всего заказов:                     {result['total_orders']}")

    # Статистика по зонам
    articles = result["articles"]
    with_krp = [a for a in articles if a["krp"] > 0]
    without_krp = [a for a in articles if a["krp"] == 0]

    print(f"\n  Артикулов с КРП > 0 (ИРП-нагрузка): {len(with_krp)}")
    print(f"  Артикулов с КРП = 0 (чисто):         {len(without_krp)}")

    if with_krp:
        total_krp_orders = sum(a["orders"] for a in with_krp)
        print(f"  Заказов с КРП > 0:                   {total_krp_orders} "
              f"({total_krp_orders / result['total_orders'] * 100:.1f}%)")

    # Топ проблемных артикулов
    if with_krp:
        print(f"\n  {'─' * 86}")
        print(f"  АРТИКУЛЫ С КРП > 0 (влияют на ИРП) — топ {min(top_n, len(with_krp))}")
        print(f"  {'─' * 86}")
        print(f"  {'Артикул':<30} {'Заказов':>8} {'Лок-ых':>7} {'Лок,%':>7} {'КТР':>6} {'КРП,%':>7}")
        print(f"  {'─' * 86}")
        for a in with_krp[:top_n]:
            print(f"  {a['article']:<30} {a['orders']:>8} {a['local']:>7} "
                  f"{a['loc_pct']:>6.1f}% {a['ktr']:>5.2f} {a['krp']:>6.2f}%")

    # Топ чистых артикулов
    clean_sorted = sorted(without_krp, key=lambda x: -x["orders"])
    if clean_sorted:
        print(f"\n  {'─' * 86}")
        print(f"  АРТИКУЛЫ С КРП = 0 (не влияют на ИРП) — топ {min(top_n, len(clean_sorted))}")
        print(f"  {'─' * 86}")
        print(f"  {'Артикул':<30} {'Заказов':>8} {'Лок-ых':>7} {'Лок,%':>7} {'КТР':>6} {'КРП,%':>7}")
        print(f"  {'─' * 86}")
        for a in clean_sorted[:top_n]:
            print(f"  {a['article']:<30} {a['orders']:>8} {a['local']:>7} "
                  f"{a['loc_pct']:>6.1f}% {a['ktr']:>5.2f} {a['krp']:>6.2f}%")


def print_region_results(region_stats: dict, total_orders: int):
    """Выводит разбивку локализации по регионам."""
    print(f"\n  {'─' * 86}")
    print(f"  ЛОКАЛИЗАЦИЯ ПО РЕГИОНАМ (как на WB Partners)")
    print(f"  {'─' * 86}")
    print(f"  {'Регион':<35} {'Лок,%':>8} {'Доля,%':>8} {'Заказов':>8} {'Лок-ых':>8} {'КТР':>6} {'КРП,%':>7}")
    print(f"  {'─' * 86}")

    sorted_regions = sorted(region_stats.items(), key=lambda x: -x[1]["total"])
    for region, stats in sorted_regions:
        loc_pct = stats["local"] / stats["total"] * 100 if stats["total"] > 0 else 0
        share = stats["total"] / total_orders * 100 if total_orders > 0 else 0
        ktr, krp = get_ktr_krp(loc_pct)
        print(f"  {region:<35} {loc_pct:>7.1f}% {share:>7.1f}% {stats['total']:>8} "
              f"{stats['local']:>8} {ktr:>5.2f} {krp:>6.2f}%")

    # Общий
    total_all = sum(s["total"] for s in region_stats.values())
    total_local = sum(s["local"] for s in region_stats.values())
    overall_loc = total_local / total_all * 100 if total_all > 0 else 0
    print(f"  {'─' * 86}")
    print(f"  {'ИТОГО':<35} {overall_loc:>7.1f}% {'100.0%':>8} {total_all:>8} {total_local:>8}")


def print_comparison(result: dict, wb_il: float = 0.98, wb_irp: float = 0.42):
    """Сравнение расчётных значений с данными WB Partners."""
    print(f"\n  {'=' * 60}")
    print(f"  СРАВНЕНИЕ С WB PARTNERS")
    print(f"  {'=' * 60}")
    print(f"  {'Показатель':<25} {'Наш расчёт':>12} {'WB Partners':>12} {'Δ':>10}")
    print(f"  {'─' * 60}")

    our_il = result["il"]
    our_irp = result["irp"]

    il_delta = our_il - wb_il
    irp_delta = our_irp - wb_irp

    il_match = "✓" if abs(il_delta) < 0.03 else "✗"
    irp_match = "✓" if abs(irp_delta) < 0.10 else "✗"

    print(f"  {'ИЛ':<25} {our_il:>11.2f} {wb_il:>11.2f} {il_delta:>+9.2f}  {il_match}")
    print(f"  {'ИРП, %':<25} {our_irp:>10.2f}% {wb_irp:>10.2f}% {irp_delta:>+8.2f}%  {irp_match}")
    print(f"  {'─' * 60}")

    if abs(il_delta) < 0.03 and abs(irp_delta) < 0.10:
        print("  Расчёт СХОДИТСЯ с WB Partners!")
    else:
        print("  Расхождение. Возможные причины:")
        if abs(il_delta) >= 0.03:
            print("   - ИЛ: WB может группировать регионы иначе")
            print("   - ИЛ: разный период или неполные данные orders API")
        if abs(irp_delta) >= 0.10:
            print("   - ИРП: WB считает по артикулу, мы — по supplierArticle")
            print("   - ИРП: некоторые товары-исключения (КРП всегда = 0)")
            print("   - ИРП: пропущенные заказы (неизвестный склад/область)")

    print()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Калькулятор ИЛ и ИРП Wildberries"
    )
    parser.add_argument(
        "--cabinet", choices=["ip", "ooo"], default="ooo",
        help="Кабинет: ip или ooo (default: ooo)"
    )
    parser.add_argument(
        "--date-from", default=None,
        help="Начало периода YYYY-MM-DD (default: 13 недель назад)"
    )
    parser.add_argument(
        "--date-to", default=None,
        help="Конец периода YYYY-MM-DD (default: вчера)"
    )
    parser.add_argument(
        "--top", type=int, default=15,
        help="Показать топ-N артикулов (default: 15)"
    )
    parser.add_argument(
        "--wb-il", type=float, default=0.98,
        help="ИЛ из WB Partners для сравнения (default: 0.98)"
    )
    parser.add_argument(
        "--wb-irp", type=float, default=0.42,
        help="ИРП из WB Partners для сравнения (default: 0.42)"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Кабинет
    cabinet = CABINET_IP if args.cabinet == "ip" else CABINET_OOO
    if not cabinet.wb_api_key:
        print(f"ERROR: WB API key не найден для кабинета {cabinet.name}")
        print(f"  Проверь .env: WB_API_KEY_{args.cabinet.upper()}")
        sys.exit(1)

    # Период: 13 недель (91 день) — как в правилах WB
    today = datetime.now()
    if args.date_from:
        date_from = args.date_from + "T00:00:00"
    else:
        date_from = (today - timedelta(days=91)).strftime("%Y-%m-%dT00:00:00")

    if args.date_to:
        date_to = args.date_to
    else:
        date_to = (today - timedelta(days=1)).strftime("%Y-%m-%d")

    print(f"╔{'═' * 68}╗")
    print(f"║  Калькулятор ИЛ и ИРП Wildberries                                  ║")
    print(f"╠{'═' * 68}╣")
    print(f"║  Кабинет: {cabinet.name:<57}║")
    print(f"║  Период:  {date_from[:10]} — {date_to:<44}║")
    print(f"║  WB ref:  ИЛ = {args.wb_il}, ИРП = {args.wb_irp}%{' ' * 40}║")
    print(f"╚{'═' * 68}╝")

    # 1. Загрузка заказов
    orders = load_orders(cabinet, date_from, date_to)
    if not orders:
        print("ERROR: Нет заказов за указанный период")
        sys.exit(1)

    # 2. Локализация по артикулам
    print("\nРасчёт локализации по артикулам...")
    article_stats = calc_article_localization(orders)
    print(f"  Артикулов с заказами: {len(article_stats)}")

    # 3. Расчёт ИЛ и ИРП
    print("Расчёт ИЛ и ИРП...")
    result = calc_indices(article_stats)

    # 4. Локализация по регионам
    region_stats = calc_region_indices(orders)

    # 5. Вывод
    print_results(result, top_n=args.top)
    print_region_results(region_stats, result["total_orders"])
    print_comparison(result, wb_il=args.wb_il, wb_irp=args.wb_irp)


if __name__ == "__main__":
    main()
