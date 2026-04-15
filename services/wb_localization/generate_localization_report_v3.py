#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Генератор отчёта по оптимизации индекса локализации Wildberries v3

Максимизирует общий индекс локализации, при этом не допуская
ухудшения индекса ни в одном регионе-доноре.

Запуск:
    python3 generate_localization_report_v3.py "Data 08.02"
    python3 generate_localization_report_v3.py "Data 08.02" --compare-with "Data 04.02"
    python3 generate_localization_report_v3.py "Data 08.02" --safety-days 7
"""

import argparse
import math
import re
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Путь к корню проекта для импорта data_layer
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from scripts.data_layer import get_artikuly_statuses
    HAS_DATA_LAYER = True
except ImportError:
    HAS_DATA_LAYER = False


# ============================================
# КОНФИГУРАЦИЯ
# ============================================

BASE_PATH = Path(__file__).parent

# Пороги
TARGET_LOCALIZATION_INDEX = 80  # Целевой индекс %
CRITICAL_INDEX = 50             # Критичный порог %
HIGH_ORDERS = 10                # Порог высоких заказов

# Защита доноров (по умолчанию, можно переопределить через CLI)
DEFAULT_SAFETY_DAYS = 14        # Дней запаса для донора
DEFAULT_MIN_DONOR_LOC = 70      # Мин. допустимая локализация донора %

# Рекомендуемые склады по регионам
WAREHOUSES = {
    'Центральный': 'Коледино',
    'Южный + Северо-Кавказский': 'Краснодар',
    'Приволжский': 'Казань',
    'Северо-Западный': 'Склад СПБ Шушары Московское',
    'Уральский': 'Екатеринбург - Перспективный 12',
    'Дальневосточный + Сибирский': 'Новосибирск',
    'Беларусь': 'Минск',
    'Казахстан': 'Астана Карагандинское шоссе',
    'Армения': 'СЦ Ереван Арташисян 106',
    'Узбекистан': 'Ташкент 2  WB',
}

# Российские регионы — только между ними возможны перемещения
RUSSIAN_REGIONS = {
    'Центральный',
    'Южный + Северо-Кавказский',
    'Приволжский',
    'Северо-Западный',
    'Уральский',
    'Дальневосточный + Сибирский',
}


# ============================================
# CLI
# ============================================

def parse_args():
    """Парсинг аргументов командной строки"""
    parser = argparse.ArgumentParser(
        description='Отчёт по оптимизации индекса локализации v3 (с защитой доноров)'
    )
    parser.add_argument(
        'data_folder',
        help='Папка с данными, например "Data 08.02"'
    )
    parser.add_argument(
        '--sku-db',
        default=str(BASE_PATH.parent / 'sku_database' / 'Спецификации.xlsx'),
        help='Путь к файлу баркодов (Спецификации.xlsx)'
    )
    parser.add_argument(
        '--compare-with',
        default=None,
        help='Папка предыдущего периода для сравнения, например "Data 04.02"'
    )
    parser.add_argument(
        '--safety-days',
        type=int,
        default=DEFAULT_SAFETY_DAYS,
        help=f'Дней запаса для донора (по умолчанию {DEFAULT_SAFETY_DAYS})'
    )
    parser.add_argument(
        '--min-donor-localization',
        type=float,
        default=DEFAULT_MIN_DONOR_LOC,
        help=f'Мин. локализация донора %% (по умолчанию {DEFAULT_MIN_DONOR_LOC})'
    )
    parser.add_argument(
        '--no-statuses',
        action='store_true',
        default=False,
        help='Не загружать статусы из Supabase (работать без фильтрации Выводим)'
    )
    return parser.parse_args()


# ============================================
# АВТООБНАРУЖЕНИЕ ФАЙЛОВ
# ============================================

def detect_files_and_period(data_path):
    """
    Находит файлы данных в папке и определяет длину периода.
    Возвращает (stocks_file, regions_file, period_days)
    """
    stocks_file = None
    regions_file = None

    for f in data_path.iterdir():
        name = f.name.lower()
        if f.suffix == '.xlsx':
            if 'истори' in name and 'остатк' in name:
                stocks_file = f.name
            elif 'поставки' in name and 'регион' in name:
                regions_file = f.name

    if not stocks_file:
        raise FileNotFoundError(f"Не найден файл 'История остатков' в {data_path}")
    if not regions_file:
        raise FileNotFoundError(f"Не найден файл 'Поставки по регионам' в {data_path}")

    # Извлекаем даты из имени файла поставок
    period_days = 7  # fallback
    pattern = r'с\s+(\d{2})-(\d{2})-(\d{4})\s+по\s+(\d{2})-(\d{2})-(\d{4})'
    match = re.search(pattern, regions_file)
    if match:
        d1, m1, y1, d2, m2, y2 = match.groups()
        try:
            start = datetime(int(y1), int(m1), int(d1))
            end = datetime(int(y2), int(m2), int(d2))
            days = (end - start).days
            if days > 0:
                period_days = days
        except ValueError:
            pass

    print(f"   Остатки: {stocks_file}")
    print(f"   Регионы: {regions_file}")
    print(f"   Период: {period_days} дней")

    if period_days < 7:
        print(f"   ⚠ Короткий период ({period_days} дн.) — расчёты могут быть консервативными")

    return stocks_file, regions_file, period_days


# ============================================
# ЗАГРУЗКА ДАННЫХ
# ============================================

def load_source_data(data_path, stocks_file, regions_file):
    """Загрузка исходных данных из указанной папки"""
    print("1. Загрузка данных...")

    df_stocks = pd.read_excel(
        data_path / stocks_file,
        sheet_name='Детальная информация',
        skiprows=1
    )
    df_regions = pd.read_excel(
        data_path / regions_file,
        sheet_name='Детальные данные',
        skiprows=1
    )
    df_regions_summary = pd.read_excel(
        data_path / regions_file,
        sheet_name='Общее',
        skiprows=1
    )

    print(f"   Остатки: {len(df_stocks)} строк | Регионы: {len(df_regions)} строк")
    return df_stocks, df_regions, df_regions_summary


def load_barcodes(sku_db_path):
    """Загрузка справочника баркодов (graceful degradation)"""
    print("2. Загрузка баркодов...")

    path = Path(sku_db_path)
    if not path.exists():
        print(f"   ⚠ Файл не найден: {path}")
        print("   Продолжаем без баркодов")
        return {}

    df = pd.read_excel(path, sheet_name='Все товары')

    def clean(val):
        if pd.isna(val) or str(val) in ('', 'nan'):
            return None
        return f"{int(val)}" if isinstance(val, float) else str(val).strip()

    # Поддержка обоих вариантов названия колонки
    barcode_col = 'БАРКОД ' if 'БАРКОД ' in df.columns else 'БАРКОД'
    if barcode_col not in df.columns:
        print("   ⚠ Колонка БАРКОД не найдена")
        return {}

    barcode_dict = {}
    for _, row in df.iterrows():
        key = (str(row['Артикул']).strip(), str(row['Размер']).strip())
        barcode_dict[key] = clean(row[barcode_col])

    print(f"   Загружено: {len(barcode_dict)} баркодов")
    return barcode_dict


def load_statuses(skip=False, cabinet_name: str | None = None):
    """
    Загрузка статусов артикулов из Supabase (graceful degradation).

    Возвращает dict: {article_lowercase: status}
    Пустой dict если загрузка не удалась или отключена.
    """
    if skip:
        print("2.5. Статусы: пропущено (--no-statuses)")
        return {}

    if not HAS_DATA_LAYER:
        print("2.5. Статусы: data_layer не найден, продолжаем без статусов")
        return {}

    print(f"2.5. Загрузка статусов из Supabase{f' ({cabinet_name})' if cabinet_name else ''}...")
    statuses = get_artikuly_statuses(cabinet_name=cabinet_name)

    if not statuses:
        print("   Статусы не загружены (нет подключения?)")
        return {}

    status_counts = {}
    for status in statuses.values():
        status_counts[status] = status_counts.get(status, 0) + 1

    vyvodim_count = status_counts.get('Выводим', 0)
    print(f"   Загружено: {len(statuses)} артикулов")
    print(f"   Статус 'Выводим': {vyvodim_count} артикулов")

    return statuses


# ============================================
# РАСЧЁТ МЕТРИК
# ============================================

def calculate_sku_stats(df_regions):
    """Расчёт статистики по SKU"""
    print("3. Расчёт индекса локализации...")

    stats = df_regions.groupby(
        ['Артикул продавца', 'Размер', 'Артикул WB', 'Название']
    ).agg({
        'Заказы со склада ВБ локально, шт': 'sum',
        'Заказы со склада ВБ не локально, шт': 'sum',
        'Остатки склад ВБ, шт': 'sum'
    }).reset_index()

    stats.columns = [
        'Артикул продавца', 'Размер', 'Артикул WB', 'Название',
        'Локальные', 'Нелокальные', 'Остатки'
    ]

    stats['Всего заказов'] = stats['Локальные'] + stats['Нелокальные']
    stats['Индекс, %'] = np.where(
        stats['Всего заказов'] > 0,
        (stats['Локальные'] / stats['Всего заказов'] * 100).round(1),
        np.nan
    )

    with_orders = stats[stats['Всего заказов'] > 0]
    avg_idx = with_orders['Индекс, %'].mean() if len(with_orders) > 0 else 0
    median_idx = with_orders['Индекс, %'].median() if len(with_orders) > 0 else 0
    print(f"   SKU: {len(stats)} | С заказами: {len(with_orders)}")
    print(f"   Средний индекс: {avg_idx:.1f}% | Медиана: {median_idx:.1f}%")
    return stats


# ============================================
# ЗАЩИТА ДОНОРОВ
# ============================================

def calculate_donor_limits(region_orders_total, region_local_orders,
                           region_stock, period_days, safety_days, min_loc):
    """
    Рассчитывает безопасный минимум остатков и доступное для трансфера.

    Ограничение: оставить запас на safety_days дней по ОБЩЕМУ спросу
    (локальный + нелокальный), чтобы донор не остался без товара.

    Возвращает (safe_minimum, available_for_transfer, limiting_factor)
    """
    if region_stock == 0:
        return 0, 0, 'нет остатков'

    if region_orders_total == 0:
        return 0, region_stock, 'нет спроса'

    daily_orders = region_orders_total / period_days

    # Оставляем запас на safety_days дней полного спроса
    safe_min_demand = math.ceil(daily_orders * safety_days)

    available = max(0, region_stock - safe_min_demand)

    if available == 0:
        factor = 'буфер спроса'
    else:
        factor = 'доступен'

    safe_minimum = region_stock - available
    return safe_minimum, available, factor


# ============================================
# АНАЛИЗ РАСПРЕДЕЛЕНИЯ
# ============================================

def analyze_distribution_v3(sku, size, df_regions, df_stocks,
                            period_days, safety_days, min_loc):
    """Анализ распределения SKU по регионам с защитой доноров"""
    sku_orders = df_regions[
        (df_regions['Артикул продавца'] == sku) &
        (df_regions['Размер'] == size)
    ].copy()

    if len(sku_orders) == 0:
        return None, None, None, None

    sku_stocks = df_stocks[
        (df_stocks['Артикул продавца'] == sku) &
        (df_stocks['Размер'] == size)
    ].copy()

    sku_orders['Всего'] = (
        sku_orders['Заказы со склада ВБ локально, шт'] +
        sku_orders['Заказы со склада ВБ не локально, шт']
    )

    total_orders = sku_orders['Всего'].sum()
    total_stocks = sku_orders['Остатки склад ВБ, шт'].sum()

    if total_orders == 0:
        return None, None, None, None

    analysis = []
    donor_records = []

    for _, row in sku_orders.iterrows():
        share = row['Всего'] / total_orders
        target = share * total_stocks
        deficit = round(target - row['Остатки склад ВБ, шт'])
        local = row['Заказы со склада ВБ локально, шт']
        nonlocal_ = row['Заказы со склада ВБ не локально, шт']
        region_total = local + nonlocal_
        stock = row['Остатки склад ВБ, шт']

        # Защита донора
        safe_min, available, factor = calculate_donor_limits(
            region_total, local, stock, period_days, safety_days, min_loc
        )

        # Если дефицит < 0 (т.е. surplus), ограничиваем доступное
        if deficit < 0:
            actual_available = min(abs(deficit), available)
        else:
            actual_available = 0

        analysis.append({
            'Регион': row['Регион'],
            'Заказов': row['Всего'],
            'Локальных': local,
            'Доля, %': round(share * 100, 1),
            'Остатки': stock,
            'Целевые': round(target),
            'Дефицит': deficit,
            'Безопасный минимум': safe_min,
            'Доступно для трансфера': actual_available,
        })

        # Запись для листа "Защита доноров"
        if deficit < 0:
            current_loc_pct = round(local / region_total * 100, 1) if region_total > 0 else 0
            donor_records.append({
                'Артикул продавца': sku,
                'Размер': size,
                'Регион-донор': row['Регион'],
                'Текущие остатки': int(stock),
                'Среднедневные заказы': round(region_total / period_days, 2) if period_days > 0 else 0,
                'Текущая локализация, %': current_loc_pct,
                'Безопасный минимум': safe_min,
                'Доступно для трансфера': actual_available,
                'Ограничено на': abs(deficit) - actual_available,
                'Фактор ограничения': factor,
            })

    stocks_by_wh = pd.DataFrame()
    if len(sku_stocks) > 0 and 'Остатки на текущий день, шт' in sku_stocks.columns:
        stocks_by_wh = sku_stocks.groupby(['Регион', 'Склад'])[
            'Остатки на текущий день, шт'
        ].sum().reset_index()
        stocks_by_wh.columns = ['Регион', 'Склад', 'Остатки']

    summary = {
        'total_orders': total_orders,
        'total_stocks': total_stocks,
        'local_orders': sku_orders['Заказы со склада ВБ локально, шт'].sum(),
        'current_index': sku_orders['Заказы со склада ВБ локально, шт'].sum() / total_orders * 100
    }

    return pd.DataFrame(analysis), stocks_by_wh, summary, pd.DataFrame(donor_records)


# ============================================
# ГЕНЕРАЦИЯ РЕКОМЕНДАЦИЙ
# ============================================

def generate_movements_v3(sku_stats, df_regions, df_stocks, barcode_dict,
                          period_days, safety_days, min_loc, statuses=None,
                          own_stock=None, max_turnover_days=100):
    """Генерация перемещений с защитой доноров и фильтрацией статуса 'Выводим'.

    Args:
        own_stock: dict {article_lower: quantity} — остатки своего склада (МойСклад).
            Если передан, допоставки обогащаются колонками доступности.
        max_turnover_days: макс. допустимый оборот при допоставке (дней запаса).
    """
    print("4. Генерация перемещений (с защитой доноров)...")

    movements = []
    supplies = []
    all_donor_records = []

    problem_skus = sku_stats[
        (sku_stats['Индекс, %'] < TARGET_LOCALIZATION_INDEX) &
        (sku_stats['Всего заказов'] > 0)
    ].copy()

    # Сортируем по влиянию: больше заказов × ниже индекс = выше приоритет
    problem_skus['impact'] = problem_skus['Всего заказов'] * (
        TARGET_LOCALIZATION_INDEX - problem_skus['Индекс, %'].fillna(0)
    )
    problem_skus = problem_skus.sort_values('impact', ascending=False)

    vyvodim_excluded = 0

    def _make_supply(sku, size, name, wb_art, barcode, sku_status,
                     region, needed, region_orders_total):
        """Создаёт запись допоставки с учётом own_stock и max_turnover."""
        rec = {
            'Баркод': barcode,
            'Артикул': sku,
            'Размер': size,
            'Название': name,
            'Артикул WB': wb_art,
            'Статус': sku_status or '',
            'Регион': region,
            'Склад': WAREHOUSES.get(region, ''),
            'Кол-во': int(needed),
        }
        if own_stock is not None:
            available_own = own_stock.get(sku.lower(), 0)
            # Ограничение по обороту: не создавать запас больше max_turnover_days
            daily_orders = region_orders_total / period_days if period_days > 0 else 0
            # Текущие остатки в этом регионе (из df_regions)
            region_data = df_regions[
                (df_regions['Артикул продавца'] == sku) &
                (df_regions['Размер'] == size) &
                (df_regions['Регион'] == region)
            ]
            current_wb_stock = int(region_data['Остатки склад ВБ, шт'].sum()) if len(region_data) > 0 else 0
            max_by_turnover = max(0, int(daily_orders * max_turnover_days) - current_wb_stock)
            capped = min(int(needed), max_by_turnover)
            actual = min(capped, available_own)

            rec['Макс. по обороту'] = max_by_turnover
            rec['На своём складе'] = available_own
            rec['К допоставке (факт)'] = actual
        return rec

    for _, row in problem_skus.iterrows():
        sku, size = row['Артикул продавца'], row['Размер']
        name, wb_art = row['Название'], row['Артикул WB']
        barcode = barcode_dict.get((sku, size))

        # Определяем статус артикула
        sku_status = statuses.get(sku.lower()) if statuses else None
        is_vyvodim = (sku_status == 'Выводим')

        region_df, stocks_df, summary, donor_df = analyze_distribution_v3(
            sku, size, df_regions, df_stocks, period_days, safety_days, min_loc
        )

        if region_df is None:
            continue

        # Собираем записи защиты доноров
        if donor_df is not None and len(donor_df) > 0:
            donor_df['Баркод'] = barcode
            all_donor_records.append(donor_df)

        # Только российские регионы участвуют в перемещениях
        ru_mask = region_df['Регион'].isin(RUSSIAN_REGIONS)
        donors = region_df[ru_mask & (region_df['Доступно для трансфера'] > 0)]
        recipients = region_df[ru_mask & (region_df['Дефицит'] > 0)].sort_values(
            'Дефицит', ascending=False
        )

        if len(donors) == 0 or len(recipients) == 0:
            if not is_vyvodim:
                for _, rec in recipients.iterrows():
                    if rec['Дефицит'] > 0 and rec['Регион'] in RUSSIAN_REGIONS:
                        supplies.append(_make_supply(
                            sku, size, name, wb_art, barcode, sku_status,
                            rec['Регион'], rec['Дефицит'], rec['Заказов'],
                        ))
            else:
                vyvodim_excluded += 1
            continue

        # Собираем доступные излишки с УЧЁТОМ защиты
        surplus = {}
        for _, d in donors.iterrows():
            region = d['Регион']
            avail = int(d['Доступно для трансфера'])
            if avail <= 0:
                continue

            region_stocks = stocks_df[stocks_df['Регион'] == region] if len(stocks_df) > 0 else pd.DataFrame()
            if len(region_stocks) == 0:
                surplus[(region, WAREHOUSES.get(region, region))] = avail
            else:
                total_region_stock = region_stocks['Остатки'].sum()
                for _, ws in region_stocks.iterrows():
                    if ws['Остатки'] > 0 and total_region_stock > 0:
                        wh_share = ws['Остатки'] / total_region_stock
                        wh_avail = min(int(ws['Остатки']), max(1, int(avail * wh_share)))
                        if wh_avail > 0:
                            surplus[(region, ws['Склад'])] = wh_avail

        # Распределяем по получателям
        for _, rec in recipients.iterrows():
            needed = int(rec['Дефицит'])
            target_region = rec['Регион']

            while needed > 0 and surplus:
                for (dr, dw), avail in list(surplus.items()):
                    if avail <= 0:
                        del surplus[(dr, dw)]
                        continue

                    transfer = min(needed, avail)
                    movements.append({
                        'Баркод': barcode,
                        'Артикул': sku,
                        'Размер': size,
                        'Название': name,
                        'Артикул WB': wb_art,
                        'Статус': sku_status or '',
                        'Откуда регион': dr,
                        'Откуда склад': dw,
                        'Куда регион': target_region,
                        'Куда склад': WAREHOUSES.get(target_region, ''),
                        'Кол-во': transfer,
                        'Индекс SKU, %': round(summary['current_index'], 1),
                        'Заказов': row['Всего заказов'],
                    })

                    surplus[(dr, dw)] -= transfer
                    needed -= transfer
                    if surplus[(dr, dw)] <= 0:
                        del surplus[(dr, dw)]
                    break
                else:
                    break

            if needed > 0 and not is_vyvodim:
                # Получаем заказы в целевом регионе для расчёта оборота
                target_orders = 0
                for _, tr in recipients.iterrows():
                    if tr['Регион'] == target_region:
                        target_orders = tr['Заказов']
                        break
                supplies.append(_make_supply(
                    sku, size, name, wb_art, barcode, sku_status,
                    target_region, needed, target_orders,
                ))

    moves_df = pd.DataFrame(movements) if movements else pd.DataFrame()
    supply_df = pd.DataFrame(supplies) if supplies else pd.DataFrame()
    donor_protection_df = pd.concat(all_donor_records, ignore_index=True) if all_donor_records else pd.DataFrame()

    print(f"   Перемещений: {len(moves_df)} | Допоставок: {len(supply_df)}")
    if len(donor_protection_df) > 0:
        limited = donor_protection_df[donor_protection_df['Ограничено на'] > 0]
        print(f"   Доноров с ограничением: {len(limited)} из {len(donor_protection_df)}")
    if statuses and vyvodim_excluded > 0:
        print(f"   Исключено из допоставок ('Выводим'): {vyvodim_excluded} SKU")

    return moves_df, supply_df, donor_protection_df


# ============================================
# ПРИОРИТИЗАЦИЯ
# ============================================

def add_priority(df, index_col='Индекс SKU, %', orders_col='Заказов'):
    """Добавление приоритета"""
    if df.empty or index_col not in df.columns:
        return df

    def get_priority(row):
        idx = row.get(index_col, 100)
        orders = row.get(orders_col, 0)

        if pd.isna(idx):
            return 'Нет данных', 0

        if idx < CRITICAL_INDEX and orders >= HIGH_ORDERS:
            return 'Критично+', 35
        elif idx < CRITICAL_INDEX:
            return 'Критично', 30
        elif idx < TARGET_LOCALIZATION_INDEX and orders >= HIGH_ORDERS:
            return 'Важно+', 25
        elif idx < TARGET_LOCALIZATION_INDEX:
            return 'Важно', 20
        else:
            return 'OK', 10

    df['Приоритет'], df['Балл'] = zip(*df.apply(get_priority, axis=1))
    df = df.sort_values('Балл', ascending=False)
    return df


def split_by_priority(df):
    """Разделение по приоритетам"""
    if df.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    critical = df[df['Приоритет'].str.contains('Критично', na=False)]
    important = df[df['Приоритет'].str.contains('Важно', na=False)]
    other = df[~df.index.isin(critical.index) & ~df.index.isin(important.index)]

    return critical, important, other


# ============================================
# СВОДКА ПО РЕГИОНАМ
# ============================================

def calc_region_summary(df_regions, df_stocks):
    """Сводка по регионам"""
    stocks = df_stocks.groupby('Регион')['Остатки на текущий день, шт'].sum()
    total_stocks = stocks.sum()

    orders = df_regions.groupby('Регион').agg({
        'Заказы со склада ВБ локально, шт': 'sum',
        'Заказы со склада ВБ не локально, шт': 'sum',
    })
    orders['Всего'] = orders.sum(axis=1)
    total_orders = orders['Всего'].sum()

    summary = []
    for region in stocks.index:
        s = stocks.get(region, 0)
        o = orders.loc[region, 'Всего'] if region in orders.index else 0
        local = orders.loc[region, 'Заказы со склада ВБ локально, шт'] if region in orders.index else 0

        s_pct = s / total_stocks * 100 if total_stocks else 0
        o_pct = o / total_orders * 100 if total_orders else 0
        target = (o_pct / 100) * total_stocks

        summary.append({
            'Регион': region,
            'Остатки': int(s),
            'Доля остатков, %': round(s_pct, 1),
            'Доля заказов, %': round(o_pct, 1),
            '% локальных': round(local / o * 100, 1) if o else 0,
            'Целевые': int(target),
            'Разница': int(s - target),
            'Рекомендация': 'Убрать излишки' if s > target * 1.1 else ('Добавить остатки' if s < target * 0.9 else 'OK'),
        })

    return pd.DataFrame(summary).sort_values('Доля заказов, %', ascending=False)


# ============================================
# СРАВНЕНИЕ ПЕРИОДОВ
# ============================================

def compare_periods(current_path, current_regions_file, previous_path):
    """Сравнение текущего и предыдущего периодов"""
    print("6. Сравнение периодов...")

    # Находим файлы в предыдущей папке
    prev_regions_file = None
    for f in previous_path.iterdir():
        if f.suffix == '.xlsx' and 'поставки' in f.name.lower() and 'регион' in f.name.lower():
            prev_regions_file = f.name
            break

    if not prev_regions_file:
        print("   ⚠ Не найден файл поставок в предыдущем периоде")
        return None

    # Загружаем сводки по регионам
    try:
        curr_summary = pd.read_excel(
            current_path / current_regions_file,
            sheet_name='Общее', skiprows=1
        )
        prev_summary = pd.read_excel(
            previous_path / prev_regions_file,
            sheet_name='Общее', skiprows=1
        )
    except Exception as e:
        print(f"   ⚠ Ошибка загрузки: {e}")
        return None

    # Определяем колонки
    loc_col = None
    share_col = None
    for col in curr_summary.columns:
        col_lower = col.lower()
        # Ищем именно "Локальные заказы, %", исключая "Не локальные"
        if 'локальн' in col_lower and '%' in col and 'не ' not in col_lower and 'не_' not in col_lower:
            loc_col = col
        if 'доля' in col_lower and 'регион' in col_lower:
            share_col = col

    if not loc_col:
        for col in curr_summary.columns:
            col_lower = col.lower()
            if 'локальн' in col_lower and 'не ' not in col_lower and 'не_' not in col_lower:
                loc_col = col
                break

    region_col = 'Регион' if 'Регион' in curr_summary.columns else curr_summary.columns[0]

    comparison = []
    for _, curr_row in curr_summary.iterrows():
        region = curr_row[region_col]
        curr_loc = curr_row[loc_col] if loc_col and loc_col in curr_row.index else None
        curr_share = curr_row[share_col] if share_col and share_col in curr_row.index else None

        # Ищем этот регион в предыдущем периоде
        prev_row = prev_summary[prev_summary[region_col] == region]
        if len(prev_row) == 0:
            prev_loc = None
            prev_share = None
        else:
            prev_row = prev_row.iloc[0]
            prev_loc = prev_row[loc_col] if loc_col and loc_col in prev_row.index else None
            prev_share = prev_row[share_col] if share_col and share_col in prev_row.index else None

        delta_loc = None
        if curr_loc is not None and prev_loc is not None:
            try:
                delta_loc = round(float(curr_loc) - float(prev_loc), 1)
            except (ValueError, TypeError):
                pass

        comparison.append({
            'Регион': region,
            'Локализация пред., %': prev_loc,
            'Локализация тек., %': curr_loc,
            'Изменение, п.п.': delta_loc,
            'Доля заказов пред., %': prev_share,
            'Доля заказов тек., %': curr_share,
        })

    result = pd.DataFrame(comparison)
    if len(result) > 0 and 'Изменение, п.п.' in result.columns:
        result = result.sort_values('Изменение, п.п.', ascending=False, na_position='last')
    print(f"   Регионов: {len(result)}")
    return result


# ============================================
# СОХРАНЕНИЕ
# ============================================

def save_report_v3(sku_stats, moves_df, supply_df, donor_protection_df,
                   region_summary, barcode_dict, comparison_df,
                   output_file, period_days, safety_days, min_loc, statuses=None):
    """Сохранение отчёта v3"""
    print("7. Сохранение отчёта...")

    # Добавляем баркоды к SKU статистике
    sku_stats = sku_stats.copy()
    sku_stats['Баркод'] = sku_stats.apply(
        lambda r: barcode_dict.get((r['Артикул продавца'], r['Размер'])), axis=1
    )

    # Добавляем статус артикула
    if statuses:
        sku_stats['Статус'] = sku_stats['Артикул продавца'].apply(
            lambda art: statuses.get(art.lower(), '')
        )

    # Приоритеты
    sku_stats = add_priority(sku_stats, 'Индекс, %', 'Всего заказов')
    moves_df = add_priority(moves_df) if not moves_df.empty else moves_df

    critical, important, other = split_by_priority(moves_df)

    # Статистика
    total_sku = len(sku_stats)
    with_orders = len(sku_stats[sku_stats['Всего заказов'] > 0])
    idx_series = sku_stats['Индекс, %'].dropna()
    avg_idx = idx_series.mean() if len(idx_series) > 0 else 0
    median_idx = idx_series.median() if len(idx_series) > 0 else 0

    critical_sku = len(sku_stats[sku_stats['Индекс, %'] < CRITICAL_INDEX])
    attention_sku = len(sku_stats[
        (sku_stats['Индекс, %'] >= CRITICAL_INDEX) &
        (sku_stats['Индекс, %'] < TARGET_LOCALIZATION_INDEX)
    ])
    ok_sku = len(sku_stats[sku_stats['Индекс, %'] >= TARGET_LOCALIZATION_INDEX])

    # Статистика защиты доноров
    donors_limited = 0
    total_protected = 0
    if len(donor_protection_df) > 0 and 'Ограничено на' in donor_protection_df.columns:
        limited = donor_protection_df[donor_protection_df['Ограничено на'] > 0]
        donors_limited = len(limited)
        total_protected = int(limited['Ограничено на'].sum())

    # Сводка
    summary_rows = [
        ['=== ОБЩАЯ СТАТИСТИКА ===', '', ''],
        ['Всего SKU', total_sku, ''],
        ['SKU с заказами', with_orders, ''],
        ['Средний индекс', f'{avg_idx:.1f}%', ''],
        ['Медианный индекс', f'{median_idx:.1f}%', ''],
        ['Период данных, дней', period_days, ''],
        ['', '', ''],
        ['=== РАСПРЕДЕЛЕНИЕ SKU ===', '', ''],
        ['Критичных (индекс <50%)', f'{critical_sku} ({critical_sku/total_sku*100:.0f}%)' if total_sku else '0', ''],
        ['Требует внимания (50-75%)', f'{attention_sku} ({attention_sku/total_sku*100:.0f}%)' if total_sku else '0', ''],
        ['OK (>=75%)', f'{ok_sku} ({ok_sku/total_sku*100:.0f}%)' if total_sku else '0', ''],
        ['', '', ''],
        ['=== ПЕРЕМЕЩЕНИЯ ===', '', ''],
        ['Критичных перемещений', len(critical), 'Делать в первую очередь'],
        ['Важных перемещений', len(important), 'Делать во вторую очередь'],
        ['Остальных', len(other), 'Можно отложить'],
        ['Всего перемещений', len(moves_df), ''],
        ['Допоставок', len(supply_df), ''],
        ['', '', ''],
        ['=== ЗАЩИТА ДОНОРОВ ===', '', ''],
        ['Буфер безопасности, дней', safety_days, ''],
        ['Мин. локализация донора, %', f'{min_loc}%', ''],
        ['Доноров с ограничением', donors_limited, 'Трансфер ограничен для защиты'],
        ['Защищённый объём, шт', total_protected, 'Оставлено у доноров'],
    ]

    # Статусы
    if statuses:
        vyvodim_total = sum(1 for s in statuses.values() if s == 'Выводим')
        vyvodim_in_report = len(sku_stats[sku_stats.get('Статус', pd.Series()) == 'Выводим']) if 'Статус' in sku_stats.columns else 0
        summary_rows.extend([
            ['', '', ''],
            ['=== СТАТУСЫ (Wookiee SKU Database) ===', '', ''],
            ['Всего артикулов в базе', len(statuses), ''],
            ['Статус "Выводим" (в базе)', vyvodim_total, ''],
            ['Статус "Выводим" (в отчёте)', vyvodim_in_report, 'Исключены из допоставок'],
        ])

    summary = pd.DataFrame(summary_rows, columns=['Показатель', 'Значение', 'Примечание'])

    # Сохранение
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(output_file, engine='openpyxl') as w:
        summary.to_excel(w, sheet_name='Сводка', index=False)

        if len(critical) > 0:
            critical.to_excel(w, sheet_name='1_Критичные', index=False)
        if len(important) > 0:
            important.to_excel(w, sheet_name='2_Важные', index=False)
        if len(other) > 0:
            other.to_excel(w, sheet_name='3_Остальные', index=False)

        if not moves_df.empty:
            moves_df.to_excel(w, sheet_name='Все перемещения', index=False)

        cols = ['Приоритет', 'Баркод', 'Артикул продавца', 'Размер', 'Название',
                'Артикул WB', 'Статус', 'Всего заказов', 'Локальные', 'Нелокальные',
                'Индекс, %', 'Остатки', 'Балл']
        sku_out = sku_stats[[c for c in cols if c in sku_stats.columns]]
        sku_out.to_excel(w, sheet_name='Анализ_SKU', index=False)

        if len(donor_protection_df) > 0:
            donor_protection_df.to_excel(w, sheet_name='Защита доноров', index=False)

        if len(supply_df) > 0:
            supply_df.to_excel(w, sheet_name='Допоставки', index=False)

        region_summary.to_excel(w, sheet_name='Регионы', index=False)

        if comparison_df is not None and len(comparison_df) > 0:
            comparison_df.to_excel(w, sheet_name='Динамика', index=False)

    print(f"   Файл: {output_file}")
    return output_file


# ============================================
# MAIN
# ============================================

def run_analysis(df_stocks, df_regions, barcode_dict, period_days,
                 safety_days=DEFAULT_SAFETY_DAYS, min_donor_localization=DEFAULT_MIN_DONOR_LOC,
                 statuses=None, output_file=None, comparison_df=None,
                 own_stock=None, max_turnover_days=100):
    """Запуск анализа локализации на готовых DataFrame.

    Программный entry point: вызывается и из CLI (main()), и из API-обёртки.

    Args:
        df_stocks: остатки WB по складам
        df_regions: заказы по регионам с колонками local/non-local
        barcode_dict: {(article, size): barcode}
        period_days: длина периода в днях
        safety_days: буфер безопасности донора
        min_donor_localization: мин. локализация донора %
        statuses: {article_lower: status} или None
        output_file: путь для Excel. Если None — автогенерация.
        comparison_df: DataFrame сравнения с предыдущим периодом
        own_stock: {article_lower: quantity} — остатки своего склада
        max_turnover_days: макс. допустимый оборот при допоставке

    Returns:
        dict с ключами:
            report_path: Path к Excel-отчёту
            sku_stats: DataFrame с метриками SKU
            moves_df: DataFrame перемещений
            supply_df: DataFrame допоставок
            donor_protection_df: DataFrame защиты доноров
            region_summary: DataFrame сводки по регионам
    """
    # 3. Расчёт метрик
    sku_stats = calculate_sku_stats(df_regions)

    # 4. Генерация перемещений с защитой доноров
    moves_df, supply_df, donor_protection_df = generate_movements_v3(
        sku_stats, df_regions, df_stocks, barcode_dict,
        period_days, safety_days, min_donor_localization, statuses,
        own_stock=own_stock, max_turnover_days=max_turnover_days,
    )

    # 5. Сводка по регионам
    print("5. Сводка по регионам...")
    region_summary = calc_region_summary(df_regions, df_stocks)

    # 7. Сохранение
    if output_file is None:
        date_str = datetime.now().strftime('%d-%m-%Y')
        output_dir = BASE_PATH / 'Отчеты готовые'
        output_file = output_dir / f'Отчет_локализация_v3_{date_str}.xlsx'

    report_path = save_report_v3(
        sku_stats, moves_df, supply_df, donor_protection_df,
        region_summary, barcode_dict, comparison_df,
        output_file, period_days, safety_days, min_donor_localization, statuses
    )

    return {
        "report_path": report_path,
        "sku_stats": sku_stats,
        "moves_df": moves_df,
        "supply_df": supply_df,
        "donor_protection_df": donor_protection_df,
        "region_summary": region_summary,
    }


def main():
    args = parse_args()

    print("=" * 60)
    print("Отчёт по оптимизации локализации v3")
    print(f"Данные: {args.data_folder}")
    print(f"Буфер безопасности: {args.safety_days} дней")
    print(f"Мин. локализация донора: {args.min_donor_localization}%")
    print("=" * 60)

    # Пути
    data_path = BASE_PATH / args.data_folder
    if not data_path.exists():
        print(f"ОШИБКА: Папка не найдена: {data_path}")
        return None

    # 1. Обнаружение файлов и периода
    stocks_file, regions_file, period_days = detect_files_and_period(data_path)

    # 2. Загрузка данных
    df_stocks, df_regions, df_regions_summary = load_source_data(
        data_path, stocks_file, regions_file
    )
    barcode_dict = load_barcodes(args.sku_db)

    # 2.5. Загрузка статусов
    statuses = load_statuses(skip=args.no_statuses)

    # 6. Сравнение периодов (опционально)
    comparison_df = None
    if args.compare_with:
        prev_path = BASE_PATH / args.compare_with
        if prev_path.exists():
            comparison_df = compare_periods(data_path, regions_file, prev_path)
        else:
            print(f"   ⚠ Папка сравнения не найдена: {prev_path}")

    # Запуск анализа
    analysis = run_analysis(
        df_stocks=df_stocks,
        df_regions=df_regions,
        barcode_dict=barcode_dict,
        period_days=period_days,
        safety_days=args.safety_days,
        min_donor_localization=args.min_donor_localization,
        statuses=statuses,
        comparison_df=comparison_df,
    )

    print("=" * 60)
    print("Готово!")
    return analysis["report_path"]


if __name__ == "__main__":
    main()
