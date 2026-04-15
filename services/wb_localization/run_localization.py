#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

"""
Автоматизированная оптимизация индекса локализации WB.

Обёртка над generate_localization_report_v3.py:
- Скачивает остатки WB через API (warehouse_remains)
- Скачивает заказы через API (supplier/orders) → рассчитывает local/non-local
- Получает остатки своего склада через МойСклад API
- Вызывает проверенную логику v3 для генерации отчёта

Запуск:
    python "MP scripts/Index_localization WB/run_localization.py"
    python "MP scripts/Index_localization WB/run_localization.py" --cabinet ip
    python "MP scripts/Index_localization WB/run_localization.py" --cabinet ooo --days 14
    python "MP scripts/Index_localization WB/run_localization.py" --dry-run
"""

import argparse
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

# Путь к корню проекта
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shared.clients.wb_client import WBClient
from shared.clients.moysklad_client import MoySkladClient
from services.sheets_sync.config import CABINET_IP, CABINET_OOO, MOYSKLAD_TOKEN

from services.wb_localization.generate_localization_report_v3 import (
    run_analysis,
    load_barcodes,
    load_statuses,
    BASE_PATH,
    RUSSIAN_REGIONS,
    DEFAULT_SAFETY_DAYS,
    DEFAULT_MIN_DONOR_LOC,
    TARGET_LOCALIZATION_INDEX,
)
from services.wb_localization.wb_localization_mappings import (
    SKIP_WAREHOUSES,
    get_warehouse_fd,
    get_delivery_fd,
    log_unknown_mappings,
)
from services.wb_localization.history import History
from services.wb_localization.calculators.il_irp_analyzer import analyze_il_irp

logger = logging.getLogger(__name__)


# ============================================
# CLI
# ============================================

def parse_args():
    parser = argparse.ArgumentParser(
        description='Автоматическая оптимизация локализации WB (через API)'
    )
    parser.add_argument(
        '--cabinet', choices=['ip', 'ooo', 'both'], default='both',
        help='Кабинет: ip, ooo, both (по умолчанию: both)'
    )
    parser.add_argument(
        '--days', type=int, default=30,
        help='Период заказов, дней назад (по умолчанию: 30)'
    )
    parser.add_argument(
        '--safety-days', type=int, default=DEFAULT_SAFETY_DAYS,
        help=f'Буфер безопасности донора, дней (по умолчанию: {DEFAULT_SAFETY_DAYS})'
    )
    parser.add_argument(
        '--min-donor-localization', type=float, default=DEFAULT_MIN_DONOR_LOC,
        help=f'Мин. локализация донора %% (по умолчанию: {DEFAULT_MIN_DONOR_LOC})'
    )
    parser.add_argument(
        '--max-turnover-days', type=int, default=100,
        help='Макс. оборот при допоставке, дней (по умолчанию: 100)'
    )
    parser.add_argument(
        '--no-statuses', action='store_true', default=False,
        help='Не загружать статусы из Supabase'
    )
    parser.add_argument(
        '--sku-db', default=str(PROJECT_ROOT / 'sku_database' / 'Спецификации.xlsx'),
        help='Путь к файлу баркодов (Спецификации.xlsx)'
    )
    parser.add_argument(
        '--output-dir', default=None,
        help='Папка для выходного Excel (по умолчанию: Отчеты готовые/)'
    )
    parser.add_argument(
        '--dry-run', action='store_true', default=False,
        help='Только загрузить данные и показать сводку'
    )
    parser.add_argument(
        '--skip-il-analysis', action='store_true', default=False,
        help='Пропустить ИЛ/ИРП анализ (только перестановки)'
    )
    return parser.parse_args()


# ============================================
# ЗАГРУЗКА ДАННЫХ ЧЕРЕЗ API
# ============================================

def fetch_wb_data(cabinet, days: int) -> tuple[list[dict], list[dict], dict[str, float]]:
    """Загрузка остатков, заказов и цен из WB API для одного кабинета.

    Returns:
        (remains_data, orders_data, prices_dict)
    """
    client = WBClient(api_key=cabinet.wb_api_key, cabinet_name=cabinet.name)
    try:
        # 1. Остатки по складам (асинхронный отчёт, 5-15 мин)
        print(f"   [{cabinet.name}] Запрос остатков по складам (warehouse_remains)...")
        remains = client.get_warehouse_remains()
        print(f"   [{cabinet.name}] Получено: {len(remains)} позиций")

        if not remains:
            print(f"   [{cabinet.name}] ОШИБКА: нет данных по остаткам")
            return [], [], {}

        # 2. Заказы за период
        date_from = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%dT00:00:00')
        print(f"   [{cabinet.name}] Запрос заказов с {date_from[:10]} (supplier/orders)...")
        orders = client.get_supplier_orders(date_from=date_from)
        print(f"   [{cabinet.name}] Получено: {len(orders)} заказов")

        # 3. Цены (для расчёта ИРП-нагрузки)
        print(f"   [{cabinet.name}] Запрос цен (prices API)...")
        prices_dict: dict[str, float] = {}
        try:
            prices_raw = client.get_prices()
            for item in prices_raw:
                vendor_code = item.get('vendorCode', '')
                sizes = item.get('sizes', [])
                if vendor_code and sizes:
                    # Берём максимальную цену среди размеров (retail price до скидки)
                    max_price = 0
                    for sz in sizes:
                        price = sz.get('price', 0) or 0
                        if price > max_price:
                            max_price = price
                    if max_price > 0:
                        prices_dict[vendor_code.lower()] = max_price
            print(f"   [{cabinet.name}] Цены: {len(prices_dict)} артикулов")
        except Exception as e:
            logger.warning("Не удалось загрузить цены: %s", e)
            print(f"   [{cabinet.name}] Цены: ошибка ({e}), продолжаем без ИРП-расчёта")

        return remains, orders, prices_dict
    finally:
        client.close()


def fetch_own_stock() -> dict[str, int]:
    """Загрузка остатков своего склада из МойСклад.

    Returns:
        {article_lower: quantity}
    """
    if not MOYSKLAD_TOKEN:
        print("   МойСклад: токен не задан, пропускаем")
        return {}

    print("   Загрузка остатков своего склада (МойСклад)...")
    ms = MoySkladClient(token=MOYSKLAD_TOKEN)
    try:
        moment = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        store_url = f"{ms.BASE_URL}/entity/store/{ms.STORE_MAIN}"
        data = ms.fetch_assortment(moment=moment, store_url=store_url)

        own_stock: dict[str, int] = {}
        for item in data:
            article = item.get('article', '')
            quantity = item.get('quantity', 0)
            if article and quantity > 0:
                key = article.strip().lower()
                own_stock[key] = own_stock.get(key, 0) + int(quantity)

        print(f"   МойСклад: {len(own_stock)} артикулов с остатками")
        return own_stock
    except Exception as e:
        logger.error("МойСклад ошибка: %s", e)
        print(f"   МойСклад: ошибка загрузки ({e}), продолжаем без данных")
        return {}


# ============================================
# ТРАНСФОРМАЦИЯ API → DataFrame
# ============================================

def transform_remains_to_df_stocks(remains: list[dict]) -> pd.DataFrame:
    """Остатки warehouse_remains → df_stocks в формате v3.

    Маппим warehouseName → федеральный округ, оставляем только 6 российских ФО.
    """
    rows = []
    for item in remains:
        vendor_code = item.get('vendorCode', '')
        tech_size = item.get('techSize', '')

        for wh in item.get('warehouses', []):
            wh_name = wh.get('warehouseName', '')
            qty = wh.get('quantity', 0)

            if qty <= 0 or wh_name in SKIP_WAREHOUSES:
                continue

            fd = get_warehouse_fd(wh_name)
            if fd is None or fd not in RUSSIAN_REGIONS:
                continue

            rows.append({
                'Артикул продавца': vendor_code,
                'Размер': tech_size,
                'Регион': fd,
                'Склад': wh_name,
                'Остатки на текущий день, шт': int(qty),
            })

    df = pd.DataFrame(rows)
    if not df.empty:
        print(f"   df_stocks: {len(df)} строк, {df['Артикул продавца'].nunique()} артикулов")
    return df


def transform_orders_to_df_regions(
    orders: list[dict],
    df_stocks: pd.DataFrame,
    days: int = 30,
) -> pd.DataFrame:
    """Заказы supplier/orders → df_regions в формате v3.

    Для каждого заказа определяем local/non-local через маппинг
    склада и области доставки в федеральные округа.

    Важно: НЕ фильтруем по isCancel — ручной отчёт WB учитывает все заказы
    (включая отменённые) при расчёте индекса локализации.
    Фильтруем по полю date — API возвращает по lastChangeDate, не по date.
    """
    # Фильтрация по дате заказа (не по lastChangeDate)
    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    period_orders = [o for o in orders if o.get('date', '')[:10] >= cutoff]
    print(f"   Заказов в периоде (date >= {cutoff}): {len(period_orders)} из {len(orders)}")

    records = []
    skipped = 0
    for o in period_orders:
        wh_name = o.get('warehouseName', '')
        wh_fd = get_warehouse_fd(wh_name)

        # oblast пустое в API — ФО доставки в oblastOkrugName
        # Для СНГ-заказов оба поля пустые → fallback на countryName
        delivery_region = o.get('oblastOkrugName', '') or o.get('oblast', '') or o.get('countryName', '')
        delivery_fd = get_delivery_fd(delivery_region)

        # Пропускаем если не можем определить ФО или не российский
        if wh_fd is None or delivery_fd is None:
            skipped += 1
            continue
        if wh_fd not in RUSSIAN_REGIONS or delivery_fd not in RUSSIAN_REGIONS:
            skipped += 1
            continue

        records.append({
            'Артикул продавца': o.get('supplierArticle', ''),
            'Размер': o.get('techSize', ''),
            'Артикул WB': o.get('nmId', 0),
            'Регион': delivery_fd,
            'is_local': (wh_fd == delivery_fd),
        })

    if skipped > 0:
        print(f"   Пропущено заказов (не-РФ или unknown): {skipped}")

    if not records:
        print("   ОШИБКА: нет данных для df_regions после фильтрации")
        return pd.DataFrame()

    df = pd.DataFrame(records)

    # Агрегируем: по (article, size, nmId, region) считаем local/non-local
    grouped = df.groupby(
        ['Артикул продавца', 'Размер', 'Артикул WB', 'Регион']
    ).agg(
        local_count=('is_local', 'sum'),
        nonlocal_count=('is_local', lambda x: (~x).sum()),
    ).reset_index()

    # Join с остатками для "Остатки склад ВБ, шт"
    if not df_stocks.empty:
        stocks_by_region = df_stocks.groupby(
            ['Артикул продавца', 'Размер', 'Регион']
        )['Остатки на текущий день, шт'].sum().reset_index()
        stocks_by_region.rename(
            columns={'Остатки на текущий день, шт': 'Остатки склад ВБ, шт'},
            inplace=True,
        )
        result = grouped.merge(
            stocks_by_region,
            on=['Артикул продавца', 'Размер', 'Регион'],
            how='left',
        )
    else:
        result = grouped.copy()
        result['Остатки склад ВБ, шт'] = 0

    result['Остатки склад ВБ, шт'] = result['Остатки склад ВБ, шт'].fillna(0).astype(int)

    # Переименовываем в формат v3
    result.rename(columns={
        'local_count': 'Заказы со склада ВБ локально, шт',
        'nonlocal_count': 'Заказы со склада ВБ не локально, шт',
    }, inplace=True)

    # Добавляем Название (нет в API, но v3 ожидает)
    result['Название'] = ''

    print(f"   df_regions: {len(result)} строк, {result['Артикул продавца'].nunique()} артикулов")

    # Быстрая сводка по локализации
    total_local = result['Заказы со склада ВБ локально, шт'].sum()
    total_orders = total_local + result['Заказы со склада ВБ не локально, шт'].sum()
    if total_orders > 0:
        avg_loc = total_local / total_orders * 100
        print(f"   Общий индекс локализации: {avg_loc:.1f}%")

    return result


# ============================================
# КОНСОЛЬНАЯ СВОДКА
# ============================================

def _print_summary(report_path: Path) -> None:
    """Выводит краткую сводку после генерации отчёта."""
    try:
        xls = pd.ExcelFile(report_path)

        # Регионы
        if 'Регионы' in xls.sheet_names:
            df_reg = pd.read_excel(xls, sheet_name='Регионы')
            print("\n   --- Сводка по регионам ---")
            for _, row in df_reg.iterrows():
                region = row.get('Регион', '?')
                loc_pct = row.get('% локальных', 0)
                rec = row.get('Рекомендация', '')
                mark = '  ' if loc_pct >= TARGET_LOCALIZATION_INDEX else ' !'
                print(f"  {mark} {region}: {loc_pct:.0f}%  {rec}")

        # Перемещения
        moves_count = 0
        supply_count = 0
        if 'Все перемещения' in xls.sheet_names:
            df_moves = pd.read_excel(xls, sheet_name='Все перемещения')
            moves_count = len(df_moves)
            moves_qty = int(df_moves['Кол-во'].sum()) if 'Кол-во' in df_moves.columns else 0
        if 'Допоставки' in xls.sheet_names:
            df_supply = pd.read_excel(xls, sheet_name='Допоставки')
            supply_count = len(df_supply)
            supply_qty = int(df_supply['Кол-во'].sum()) if 'Кол-во' in df_supply.columns else 0

        print(f"\n   Перемещений: {moves_count} ({moves_qty} шт)")
        print(f"   Допоставок:  {supply_count} ({supply_qty} шт)")

        # ИРП-анализ
        if 'ИРП-анализ' in xls.sheet_names:
            df_irp = pd.read_excel(xls, sheet_name='ИРП-анализ')
            if not df_irp.empty:
                irp_count = len(df_irp)
                irp_total = df_irp['ИРП-нагрузка ₽/мес'].sum() if 'ИРП-нагрузка ₽/мес' in df_irp.columns else 0
                print("\n   --- ИРП-зона ---")
                print(f"   Артикулов в ИРП-зоне (< 60%): {irp_count}")
                print(f"   Общая ИРП-нагрузка: {irp_total:,.0f} ₽/мес")
                # Топ-5 по ИРП-нагрузке
                if 'ИРП-нагрузка ₽/мес' in df_irp.columns:
                    top5_irp = df_irp.nlargest(5, 'ИРП-нагрузка ₽/мес')
                    print("   Топ-5 по ИРП-нагрузке:")
                    for _, r in top5_irp.iterrows():
                        art = r.get('Артикул продавца', '?')
                        loc = r.get('Индекс, %', 0)
                        impact = r.get('ИРП-нагрузка ₽/мес', 0)
                        zone = r.get('Зона', '')
                        print(f"     {art}: лок {loc:.0f}%, {impact:,.0f} ₽/мес [{zone}]")

        # Топ-5 критичных SKU (ИЛ-зона)
        if 'Анализ_SKU' in xls.sheet_names:
            df_sku = pd.read_excel(xls, sheet_name='Анализ_SKU')
            if 'Индекс, %' in df_sku.columns and 'Всего заказов' in df_sku.columns:
                problem = df_sku[
                    (df_sku['Индекс, %'] < TARGET_LOCALIZATION_INDEX) & (df_sku['Всего заказов'] > 0)
                ].copy()
                problem['impact'] = problem['Всего заказов'] * (TARGET_LOCALIZATION_INDEX - problem['Индекс, %'])
                top5 = problem.nlargest(5, 'impact')
                if not top5.empty:
                    print("\n   --- Топ-5 критичных SKU (ИЛ-зона) ---")
                    for _, r in top5.iterrows():
                        art = r.get('Артикул продавца', '?')
                        sz = r.get('Размер', '')
                        idx = r.get('Индекс, %', 0)
                        orders = int(r.get('Всего заказов', 0))
                        print(f"   {art} [{sz}]: индекс {idx:.0f}%, заказов {orders}")

        xls.close()
    except Exception as e:
        logger.warning("Не удалось вывести сводку: %s", e)


# ============================================
# ОСНОВНАЯ ЛОГИКА
# ============================================

def _build_result_payload(cabinet_name: str, analysis: dict[str, Any]) -> dict[str, Any]:
    """Преобразует результат анализа в структурированный payload для API/экспорта."""
    sku_stats: pd.DataFrame = analysis.get('sku_stats', pd.DataFrame())
    moves_df: pd.DataFrame = analysis.get('moves_df', pd.DataFrame())
    supply_df: pd.DataFrame = analysis.get('supply_df', pd.DataFrame())
    region_summary: pd.DataFrame = analysis.get('region_summary', pd.DataFrame())

    total_local = float(sku_stats['Локальные'].sum()) if 'Локальные' in sku_stats.columns else 0.0
    total_orders = float(sku_stats['Всего заказов'].sum()) if 'Всего заказов' in sku_stats.columns else 0.0
    overall_index = (total_local / total_orders * 100) if total_orders > 0 else 0.0

    # ИРП-статистика
    irp_zone_count = 0
    irp_impact_rub = 0.0
    il_zone_count = 0
    if 'Зона' in sku_stats.columns:
        irp_zone_count = int((sku_stats['Зона'] == 'ИРП-зона').sum())
        il_zone_count = int((sku_stats['Зона'] == 'ИЛ-зона').sum())
    if 'ИРП-нагрузка ₽/мес' in sku_stats.columns:
        irp_impact_rub = float(sku_stats['ИРП-нагрузка ₽/мес'].sum())

    # Средневзвешенные ИЛ/ИРП (текущие)
    il_current = 1.0
    irp_current = 0.0
    if 'КТР' in sku_stats.columns and 'Всего заказов' in sku_stats.columns:
        w = sku_stats['Всего заказов']
        if w.sum() > 0:
            il_current = float((sku_stats['КТР'] * w).sum() / w.sum())
            if 'КРП%' in sku_stats.columns:
                irp_current = float((sku_stats['КРП%'] * w).sum() / w.sum())

    summary = {
        'overall_index': round(overall_index, 1),
        'total_sku': int(len(sku_stats)),
        'sku_with_orders': int((sku_stats['Всего заказов'] > 0).sum()) if 'Всего заказов' in sku_stats.columns else 0,
        'movements_count': int(len(moves_df)),
        'movements_qty': int(moves_df['Кол-во'].sum()) if 'Кол-во' in moves_df.columns and len(moves_df) > 0 else 0,
        'supplies_count': int(len(supply_df)),
        'supplies_qty': int(supply_df['Кол-во'].sum()) if 'Кол-во' in supply_df.columns and len(supply_df) > 0 else 0,
        'il_current': round(il_current, 2),
        'irp_current': round(irp_current, 2),
        'irp_zone_sku': irp_zone_count,
        'il_zone_sku': il_zone_count,
        'irp_impact_rub_month': round(irp_impact_rub, 0),
    }

    regions: list[dict[str, Any]] = []
    if not region_summary.empty:
        for _, row in region_summary.iterrows():
            regions.append({
                'region': row.get('Регион', ''),
                'index': round(float(row.get('% локальных', 0)), 1),
                'stock_share': round(float(row.get('Доля остатков, %', 0)), 1),
                'order_share': round(float(row.get('Доля заказов, %', 0)), 1),
                'recommendation': row.get('Рекомендация', ''),
            })

    top_problems: list[dict[str, Any]] = []
    if 'Индекс, %' in sku_stats.columns and 'Всего заказов' in sku_stats.columns:
        problem = sku_stats[
            (sku_stats['Индекс, %'] < TARGET_LOCALIZATION_INDEX) & (sku_stats['Всего заказов'] > 0)
        ].copy()
        if not problem.empty:
            # Сортировка: ИРП-нагрузка (₽/мес) если есть, иначе старый impact
            has_irp = 'ИРП-нагрузка ₽/мес' in problem.columns
            if has_irp:
                problem['impact'] = problem['ИРП-нагрузка ₽/мес'].fillna(0)
                # Для артикулов без ИРП-нагрузки — старая формула
                no_irp = problem['impact'] <= 0
                problem.loc[no_irp, 'impact'] = problem.loc[no_irp, 'Всего заказов'] * (TARGET_LOCALIZATION_INDEX - problem.loc[no_irp, 'Индекс, %'])
            else:
                problem['impact'] = problem['Всего заказов'] * (TARGET_LOCALIZATION_INDEX - problem['Индекс, %'])
            top10 = problem.nlargest(10, 'impact')
            for _, row in top10.iterrows():
                entry: dict[str, Any] = {
                    'article': row.get('Артикул продавца', ''),
                    'size': row.get('Размер', ''),
                    'index': round(float(row.get('Индекс, %', 0)), 1),
                    'orders': int(row.get('Всего заказов', 0)),
                    'impact': round(float(row.get('impact', 0)), 0),
                }
                if has_irp:
                    entry['zone'] = row.get('Зона', '')
                    entry['krp_pct'] = round(float(row.get('КРП%', 0)), 2)
                    entry['irp_rub_month'] = round(float(row.get('ИРП-нагрузка ₽/мес', 0)), 0)
                top_problems.append(entry)

    return {
        'cabinet': cabinet_name,
        'timestamp': datetime.now().isoformat(timespec='seconds'),
        'report_path': str(analysis.get('report_path', '')),
        'summary': summary,
        'regions': regions,
        'top_problems': top_problems,
        'comparison': None,
        '_moves_df': moves_df,
        '_supply_df': supply_df,
        '_sku_stats': sku_stats,
    }


def _attach_comparison_and_save(result: dict[str, Any], history_store: History) -> None:
    """Добавляет сравнение с предыдущим расчётом и сохраняет в историю."""
    prev = history_store.get_latest(result['cabinet'])
    if prev:
        prev_summary = prev.get('summary', {})
        curr_summary = result.get('summary', {})
        prev_index = prev_summary.get('overall_index', 0)
        curr_index = curr_summary.get('overall_index', 0)

        prev_regions = {r.get('region'): r.get('index') for r in prev.get('regions', [])}
        curr_regions = {r.get('region'): r.get('index') for r in result.get('regions', [])}

        improved: list[str] = []
        worsened: list[str] = []
        for region, curr_index_region in curr_regions.items():
            if region in prev_regions:
                delta = float(curr_index_region) - float(prev_regions[region])
                if delta > 1:
                    improved.append(region)
                elif delta < -1:
                    worsened.append(region)

        result['comparison'] = {
            'prev_timestamp': prev.get('timestamp'),
            'prev_index': prev_index,
            'index_change': round(curr_index - prev_index, 1),
            'regions_improved': improved,
            'regions_worsened': worsened,
            # IRP dynamics
            'prev_il_current': prev_summary.get('il_current', 1.0),
            'il_current_change': round(
                curr_summary.get('il_current', 1.0) - prev_summary.get('il_current', 1.0), 3
            ),
            'prev_irp_current': prev_summary.get('irp_current', 0.0),
            'irp_current_change': round(
                curr_summary.get('irp_current', 0.0) - prev_summary.get('irp_current', 0.0), 3
            ),
            'prev_irp_impact': prev_summary.get('irp_impact_rub_month', 0),
            'irp_impact_change': round(
                curr_summary.get('irp_impact_rub_month', 0) - prev_summary.get('irp_impact_rub_month', 0), 0
            ),
            'prev_irp_zone_sku': prev_summary.get('irp_zone_sku', 0),
            'irp_zone_sku_change': curr_summary.get('irp_zone_sku', 0) - prev_summary.get('irp_zone_sku', 0),
        }

    history_store.save_run(result)


def run_for_cabinet(
    cabinet,
    args,
    own_stock: dict[str, int],
    barcode_dict: dict,
    statuses: dict,
    return_result: bool = False,
    history_store: History | None = None,
) -> Path | dict[str, Any] | None:
    """Полный цикл для одного кабинета."""
    print(f"\n{'=' * 60}")
    print(f"Кабинет: {cabinet.name}")
    print(f"{'=' * 60}")

    # 1. Загрузка данных из WB API
    print("\n1. Загрузка данных из WB API...")
    remains, orders, prices_dict = fetch_wb_data(cabinet, args.days)

    if not remains:
        print(f"   ОШИБКА: нет остатков для {cabinet.name}")
        return None
    if not orders:
        print(f"   ОШИБКА: нет заказов для {cabinet.name}")
        return None

    # Проверяем маппинги
    log_unknown_mappings(orders)

    # 2. Трансформация в формат v3
    print("\n2. Трансформация данных...")
    df_stocks = transform_remains_to_df_stocks(remains)
    df_regions = transform_orders_to_df_regions(orders, df_stocks, days=args.days)

    if df_regions.empty:
        print(f"   ОШИБКА: нет данных по регионам для {cabinet.name}")
        return None

    # 3. Dry-run: только показать сводку
    if args.dry_run:
        print(f"\n--- DRY RUN ({cabinet.name}) ---")
        print(f"   Уникальных SKU: {df_regions['Артикул продавца'].nunique()}")
        total = df_regions[['Заказы со склада ВБ локально, шт', 'Заказы со склада ВБ не локально, шт']].sum().sum()
        print(f"   Всего заказов: {int(total)}")
        print(f"   Регионы: {sorted(df_regions['Регион'].unique())}")
        print(f"   Остатки на своём складе: {sum(own_stock.values())} шт ({len(own_stock)} артикулов)")
        return None

    # 4. Запуск v3 анализа
    print("\n3. Запуск анализа v3...")
    date_str = datetime.now().strftime('%d-%m-%Y')
    output_dir = Path(args.output_dir) if args.output_dir else BASE_PATH / 'Отчеты готовые'
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f'Отчет_локализация_v3_{cabinet.name}_{date_str}.xlsx'

    analysis = run_analysis(
        df_stocks=df_stocks,
        df_regions=df_regions,
        barcode_dict=barcode_dict,
        period_days=args.days,
        safety_days=args.safety_days,
        min_donor_localization=args.min_donor_localization,
        statuses=statuses,
        output_file=output_file,
        own_stock=own_stock,
        max_turnover_days=args.max_turnover_days,
    )

    report_path = analysis['report_path']
    print(f"\n   Отчёт сохранён: {report_path}")

    # Module 2: ИЛ/ИРП анализ (в обоих режимах: CLI и service)
    il_irp = None
    if not getattr(args, 'skip_il_analysis', False):
        print("\n4. ИЛ/ИРП анализ...")
        il_irp = analyze_il_irp(
            orders=orders,
            prices_dict=prices_dict,
            period_days=args.days,
        )
        s = il_irp['summary']
        print(f"   ИЛ: {s['overall_il']:.2f}, ИРП: {s['overall_irp_pct']:.2f}%")
        print(f"   Артикулов: {s['total_articles']}, в ИРП-зоне: {s['irp_zone_articles']}")
        print(f"   ИРП-нагрузка: {s['irp_monthly_cost_rub']:,.0f} ₽/мес")

    if return_result:
        result = _build_result_payload(cabinet.name, analysis)
        if history_store is not None:
            _attach_comparison_and_save(result, history_store)
        if il_irp:
            result['il_irp'] = il_irp
        return result

    # 5. Консольная сводка
    _print_summary(report_path)
    return report_path


def run_service_report(
    cabinet_key: str,
    days: int = 30,
    safety_days: int = DEFAULT_SAFETY_DAYS,
    min_donor_localization: float = DEFAULT_MIN_DONOR_LOC,
    max_turnover_days: int = 100,
    no_statuses: bool = False,
    sku_db_path: str | None = None,
    output_dir: str | None = None,
    history_store: History | None = None,
) -> dict[str, Any]:
    """Сервисный entrypoint: полный расчёт и структурированный результат для одного кабинета."""
    cab_key = cabinet_key.lower()
    if cab_key in ('ip', 'ип'):
        cabinet = CABINET_IP
    elif cab_key in ('ooo', 'ооо'):
        cabinet = CABINET_OOO
    else:
        raise ValueError(f"Unknown cabinet '{cabinet_key}', expected ip or ooo")

    sku_db = sku_db_path or str(PROJECT_ROOT / 'sku_database' / 'Спецификации.xlsx')
    barcode_dict = load_barcodes(sku_db)
    statuses = load_statuses(skip=no_statuses, cabinet_name=cabinet.name)
    own_stock = fetch_own_stock()

    args = argparse.Namespace(
        days=days,
        safety_days=safety_days,
        min_donor_localization=min_donor_localization,
        max_turnover_days=max_turnover_days,
        output_dir=output_dir,
        dry_run=False,
    )

    result = run_for_cabinet(
        cabinet=cabinet,
        args=args,
        own_stock=own_stock,
        barcode_dict=barcode_dict,
        statuses=statuses,
        return_result=True,
        history_store=history_store,
    )
    if result is None or isinstance(result, Path):
        raise RuntimeError(f'Calculation failed for cabinet {cabinet.name}')
    return result


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    args = parse_args()

    print("=" * 60)
    print("Автоматическая оптимизация локализации WB")
    print(f"Период заказов: {args.days} дней")
    print(f"Буфер безопасности: {args.safety_days} дней")
    print(f"Мин. локализация донора: {args.min_donor_localization}%")
    print(f"Макс. оборот при допоставке: {args.max_turnover_days} дней")
    print("=" * 60)

    # Определяем кабинеты
    cabinets = []
    if args.cabinet in ('ip', 'both'):
        cabinets.append(CABINET_IP)
    if args.cabinet in ('ooo', 'both'):
        cabinets.append(CABINET_OOO)

    # Загрузка общих данных (один раз для всех кабинетов)
    print("\n0. Загрузка общих данных...")
    own_stock = fetch_own_stock()

    # Запуск для каждого кабинета
    results = []
    for i, cabinet in enumerate(cabinets):
        barcode_dict = load_barcodes(args.sku_db)
        statuses = load_statuses(
            skip=args.no_statuses,
            cabinet_name=cabinet.name,
        )
        result = run_for_cabinet(cabinet, args, own_stock, barcode_dict, statuses)
        if result:
            results.append(result)

        # Пауза между кабинетами для rate limit
        if i < len(cabinets) - 1:
            print("\n   Ожидание 60с между кабинетами (rate limit)...")
            time.sleep(60)

    # Итоги
    print(f"\n{'=' * 60}")
    if results:
        print(f"Готово! Создано отчётов: {len(results)}")
        for r in results:
            print(f"   {r}")
    else:
        print("Отчёты не сгенерированы (dry-run или ошибки)")
    print("=" * 60)


if __name__ == "__main__":
    main()
