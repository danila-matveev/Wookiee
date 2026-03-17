"""
Единый ABC-анализ бренда Wookiee (WB + OZON).

Объединяет финансы обоих каналов, делает ABC по комбинированной марже,
анализирует цвета кросс-модельно в рамках продуктовых линеек.
Выводит структурированные данные (JSON) для анализа в Claude Code.

Использование:
  python scripts/abc_analysis_unified.py --save
  python scripts/abc_analysis_unified.py --save --start 2025-11-01 --end 2026-02-12
  python scripts/abc_analysis_unified.py --save --notion
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from collections import defaultdict

# Корень проекта
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from shared.data_layer import (
    to_float, format_num, format_pct,
    get_wb_by_article, get_ozon_by_article,
    get_wb_orders_by_article,
    get_wb_avg_stock, get_ozon_avg_stock,
    get_artikuly_full_info,
)
from scripts.abc_helpers import (
    calc_abc_classes, calc_high_turnover, classify_article,
)


# =============================================================================
# ПРОДУКТОВЫЕ ЛИНЕЙКИ (фолбэк если tip_kollekcii NULL)
# =============================================================================

PRODUCT_LINE_FALLBACK = {
    'tricot': [
        'vuki', 'moon', 'ruby', 'joy', 'space', 'alice', 'valery',
        'set vuki', 'set moon', 'set ruby',
        'vukip', 'rubyp', 'moonp', 'joyp',
        'vuki pattern', 'ruby pattern',
    ],
    'seamless_wendy': [
        'wendy', 'bella', 'charlotte', 'eva', 'lana', 'mia', 'miafull',
        'jess', 'angelina', 'set wendy',
    ],
    'seamless_audrey': [
        'audrey',
    ],
}


# =============================================================================
# ОБЪЕДИНЕНИЕ КАНАЛОВ
# =============================================================================

def merge_channel_data(wb_data, ozon_data):
    """
    Объединяет WB + OZON данные по артикулу (суммы маржей, выручки, продаж).
    Сохраняет wb_margin и ozon_margin для раздельного анализа.
    """
    wb_by_art = {a['article']: a for a in wb_data}
    ozon_by_art = {a['article']: a for a in ozon_data}
    all_articles = set(wb_by_art.keys()) | set(ozon_by_art.keys())

    merged = []
    for art in all_articles:
        wb = wb_by_art.get(art)
        oz = ozon_by_art.get(art)

        if wb and oz:
            channels = 'WB+OZ'
            model = wb['model']
        elif wb:
            channels = 'WB'
            model = wb['model']
        else:
            channels = 'OZ'
            model = oz['model']

        def s(field):
            return to_float((wb or {}).get(field, 0)) + to_float((oz or {}).get(field, 0))

        merged.append({
            'article': art,
            'model': model,
            'channels': channels,
            'orders_count': s('orders_count'),
            'sales_count': s('sales_count'),
            'revenue': s('revenue'),
            'margin': s('margin'),
            'adv_internal': s('adv_internal'),
            'adv_external': s('adv_external'),
            'adv_total': s('adv_total'),
            'wb_margin': to_float((wb or {}).get('margin', 0)),
            'ozon_margin': to_float((oz or {}).get('margin', 0)),
            'wb_revenue': to_float((wb or {}).get('revenue', 0)),
            'ozon_revenue': to_float((oz or {}).get('revenue', 0)),
        })

    return merged


# =============================================================================
# ОПРЕДЕЛЕНИЕ ЛИНЕЙКИ
# =============================================================================

def get_product_line(model_osnova_lower, tip_kollekcii=None):
    """Определяет линейку по model_osnova или tip_kollekcii."""
    if tip_kollekcii:
        return tip_kollekcii
    if not model_osnova_lower:
        return None
    for line, models in PRODUCT_LINE_FALLBACK.items():
        if model_osnova_lower.lower() in models:
            return line
    return None


# =============================================================================
# АНАЛИЗ ЦВЕТОВ ПО ЛИНЕЙКАМ
# =============================================================================

def analyze_color_across_line(all_rows, meta, abc_classes):
    """
    Кросс-модельный анализ цветов в рамках продуктовых линеек.

    Возвращает: {(line, color_code): {
        models: [list], abc_by_model: {}, margin_by_model: {},
        total_margin: float, recommendation: str, conflicts: []
    }}
    """
    color_data = defaultdict(lambda: defaultdict(list))

    for row in all_rows:
        art = row['article']
        m = meta.get(art, {})
        color_code = m.get('color_code')
        model_osnova = (m.get('model_osnova') or '').lower()
        tip_kol = m.get('tip_kollekcii')
        line = get_product_line(model_osnova, tip_kol)

        if not line or not color_code:
            continue

        abc = abc_classes.get(art, 'C')
        color_data[(line, color_code)][model_osnova].append({
            'article': art,
            'abc': abc,
            'margin': row['margin'],
            'wb_margin': row.get('wb_margin', 0),
            'ozon_margin': row.get('ozon_margin', 0),
        })

    results = {}
    for (line, color_code), models_dict in color_data.items():
        abc_by_model = {}
        margin_by_model = {}
        total_margin = 0

        for model, articles in models_dict.items():
            abcs = [a['abc'] for a in articles]
            if 'A' in abcs:
                best_abc = 'A'
            elif 'B' in abcs:
                best_abc = 'B'
            else:
                best_abc = 'C'
            abc_by_model[model] = best_abc
            model_margin = sum(a['margin'] for a in articles)
            margin_by_model[model] = model_margin
            total_margin += model_margin

        c_count = sum(1 for v in abc_by_model.values() if v == 'C')
        total_models = len(abc_by_model)

        if total_models == 0:
            continue

        if c_count == total_models:
            recommendation = 'Убрать'
        elif c_count > total_models / 2 and total_margin <= 0:
            recommendation = 'Убрать'
        elif c_count == 0:
            recommendation = 'Оставить'
        else:
            recommendation = 'Смешанный'

        majority = 'C' if c_count > total_models / 2 else 'A/B'
        conflicts = []
        if recommendation == 'Смешанный':
            for model, abc in abc_by_model.items():
                if abc == 'C' and majority != 'C':
                    conflicts.append(f'{model}=C')
                elif abc != 'C' and majority == 'C':
                    conflicts.append(f'{model}={abc}')

        results[(line, color_code)] = {
            'models': list(abc_by_model.keys()),
            'abc_by_model': abc_by_model,
            'margin_by_model': {k: round(v) for k, v in margin_by_model.items()},
            'total_margin': total_margin,
            'recommendation': recommendation,
            'conflicts': conflicts,
        }

    return results


# =============================================================================
# ПОДГОТОВКА КОНТЕКСТА (JSON для Claude Code)
# =============================================================================

def prepare_analysis_context(all_rows, meta, abc_last, abc_prev,
                             color_analysis, turnover_last, totals,
                             start_date, end_date, prev_start, prev_end):
    """Строит полный JSON-контекст для анализа в Claude Code."""

    # Модельные итоги
    model_data = defaultdict(lambda: {
        'margin': 0, 'wb_margin': 0, 'ozon_margin': 0,
        'revenue': 0, 'wb_revenue': 0, 'ozon_revenue': 0,
        'adv_total': 0, 'sales': 0,
        'articles': 0, 'a_count': 0, 'b_count': 0, 'c_count': 0,
        'model_osnova': None, 'tip_kollekcii': None,
    })
    for row in all_rows:
        m = model_data[row['model']]
        m['margin'] += row['margin']
        m['wb_margin'] += row.get('wb_margin', 0)
        m['ozon_margin'] += row.get('ozon_margin', 0)
        m['revenue'] += row['revenue']
        m['wb_revenue'] += row.get('wb_revenue', 0)
        m['ozon_revenue'] += row.get('ozon_revenue', 0)
        m['adv_total'] += row['adv_total']
        m['sales'] += row['sales_count']
        m['articles'] += 1
        abc_cls = abc_last.get(row['article'], 'C')
        if abc_cls == 'A':
            m['a_count'] += 1
        elif abc_cls == 'B':
            m['b_count'] += 1
        else:
            m['c_count'] += 1
        # model_osnova и tip_kollekcii — берём из первого встречного артикула
        art_meta = meta.get(row['article'], {})
        if not m['model_osnova'] and art_meta.get('model_osnova'):
            m['model_osnova'] = art_meta['model_osnova']
        if not m['tip_kollekcii'] and art_meta.get('tip_kollekcii'):
            m['tip_kollekcii'] = art_meta['tip_kollekcii']

    models_summary = []
    for model, d in sorted(model_data.items(), key=lambda x: x[1]['margin'], reverse=True):
        drr = (d['adv_total'] / d['revenue'] * 100) if d['revenue'] > 0 else 0
        margin_pct = (d['margin'] / d['revenue'] * 100) if d['revenue'] > 0 else 0
        models_summary.append({
            'model': model,
            'model_osnova': d['model_osnova'],
            'tip_kollekcii': d['tip_kollekcii'],
            'margin': round(d['margin']),
            'wb_margin': round(d['wb_margin']),
            'ozon_margin': round(d['ozon_margin']),
            'revenue': round(d['revenue']),
            'wb_revenue': round(d['wb_revenue']),
            'ozon_revenue': round(d['ozon_revenue']),
            'margin_pct': round(margin_pct, 1),
            'drr_pct': round(drr, 1),
            'sales': round(d['sales']),
            'abc': f"A:{d['a_count']} B:{d['b_count']} C:{d['c_count']}",
        })

    # Расхождения статусов
    prodaetsya_to_nelikvid = []
    vyvodim_to_good = []
    for row in all_rows:
        art = row['article']
        m = meta.get(art, {})
        status = m.get('status', 'Нет данных')
        abc = abc_last.get(art, 'C')
        turnover = turnover_last.get(art, 0)

        revenue = row.get('revenue', 0)
        margin_pct = round((row['margin'] / revenue * 100), 1) if revenue > 0 else 0.0
        color_code = m.get('color_code')
        model_osnova = m.get('model_osnova')
        tip_kollekcii = m.get('tip_kollekcii')

        if status == 'Продается' and abc == 'C':
            prodaetsya_to_nelikvid.append({
                'article': art,
                'model': row['model'],
                'model_osnova': model_osnova,
                'margin': round(row['margin']),
                'revenue': round(revenue),
                'margin_pct': margin_pct,
                'wb_margin': round(row.get('wb_margin', 0)),
                'ozon_margin': round(row.get('ozon_margin', 0)),
                'turnover_days': round(turnover) if turnover > 0 else None,
                'color_code': color_code,
                'tip_kollekcii': tip_kollekcii,
            })
        elif status == 'Выводим' and abc in ('A', 'B'):
            vyvodim_to_good.append({
                'article': art,
                'model': row['model'],
                'model_osnova': model_osnova,
                'abc': abc,
                'margin': round(row['margin']),
                'revenue': round(revenue),
                'margin_pct': margin_pct,
                'wb_margin': round(row.get('wb_margin', 0)),
                'ozon_margin': round(row.get('ozon_margin', 0)),
                'turnover_days': round(turnover) if turnover > 0 else None,
                'color_code': color_code,
                'tip_kollekcii': tip_kollekcii,
            })

    # Убыточные артикулы
    loss_articles = sorted(
        [r for r in all_rows if r['margin'] < 0],
        key=lambda x: x['margin']
    )
    worst = []
    for r in loss_articles:
        art = r['article']
        m_info = meta.get(art, {})
        rev = r.get('revenue', 0)
        mpct = round((r['margin'] / rev * 100), 1) if rev > 0 else 0.0
        worst.append({
            'article': art, 'model': r['model'],
            'model_osnova': m_info.get('model_osnova'),
            'margin': round(r['margin']),
            'revenue': round(rev),
            'margin_pct': mpct,
            'wb_margin': round(r.get('wb_margin', 0)),
            'ozon_margin': round(r.get('ozon_margin', 0)),
            'channels': r.get('channels', ''),
            'turnover_days': round(turnover_last.get(art, 0)) or None,
            'color_code': m_info.get('color_code'),
            'tip_kollekcii': m_info.get('tip_kollekcii'),
        })

    # Анализ цветов по линейкам
    color_ctx = []
    for (line, cc), info in sorted(color_analysis.items()):
        color_ctx.append({
            'line': line,
            'color_code': cc,
            'models': info['models'],
            'abc_by_model': info['abc_by_model'],
            'margin_by_model': info['margin_by_model'],
            'total_margin': round(info['total_margin']),
            'recommendation': info['recommendation'],
            'conflicts': info['conflicts'],
        })

    # Динамика (A→C, C→A)
    dynamics = []
    for row in all_rows:
        art = row['article']
        last = abc_last.get(art)
        prev = abc_prev.get(art)
        if last and prev and last != prev:
            rev = row.get('revenue', 0)
            mpct = round((row['margin'] / rev * 100), 1) if rev > 0 else 0.0
            m_info = meta.get(art, {})
            dynamics.append({
                'article': art, 'model': row['model'],
                'model_osnova': m_info.get('model_osnova'),
                'was': prev, 'now': last,
                'margin': round(row['margin']),
                'revenue': round(rev),
                'margin_pct': mpct,
                'color_code': m_info.get('color_code'),
            })

    # Оборачиваемость — топ по замороженным деньгам
    high_turnover = []
    for row in all_rows:
        art = row['article']
        turn = turnover_last.get(art, 0)
        if turn > 60 and row['margin'] > 0:
            rev = row.get('revenue', 0)
            mpct = round((row['margin'] / rev * 100), 1) if rev > 0 else 0.0
            m_info = meta.get(art, {})
            high_turnover.append({
                'article': art, 'model': row['model'],
                'model_osnova': m_info.get('model_osnova'),
                'turnover_days': round(turn),
                'margin': round(row['margin']),
                'revenue': round(rev),
                'margin_pct': mpct,
                'abc': abc_last.get(art, 'C'),
                'color_code': m_info.get('color_code'),
                'tip_kollekcii': m_info.get('tip_kollekcii'),
            })
    high_turnover.sort(key=lambda x: x['turnover_days'], reverse=True)

    return {
        'period': f"{start_date} — {end_date}",
        'comparison': f"{prev_start} — {prev_end}",
        'totals': totals,
        'models_summary': models_summary,
        'status_mismatches': {
            'prodaetsya_to_nelikvid': prodaetsya_to_nelikvid,
            'vyvodim_to_good': vyvodim_to_good,
        },
        'loss_articles': worst,
        'color_analysis': color_ctx,
        'dynamics': dynamics,
        'high_turnover_articles': high_turnover[:50],
    }


# =============================================================================
# ГЕНЕРАЦИЯ ОТЧЁТА (сводка + таблица, без аналитики)
# =============================================================================

def build_unified_report(all_rows_last, all_rows_prev, meta,
                         abc_last, abc_prev, turnover_last,
                         high_turn_last, high_turn_prev,
                         color_analysis,
                         start_date, end_date, prev_start, prev_end):
    """Генерирует Markdown-отчёт (сводка + таблица). Аналитику пишет Claude Code."""

    lines = []

    # Шапка
    lines.append('# Единый ABC-анализ бренда Wookiee')
    lines.append('')
    lines.append(f'**Период**: {start_date} — {end_date}')
    lines.append(f'**Сравнение**: {prev_start} — {prev_end}')
    lines.append('**Каналы**: Wildberries + OZON')

    # Подсчёт stats
    total_articles = len(all_rows_last)
    wb_only = sum(1 for r in all_rows_last if r['channels'] == 'WB')
    oz_only = sum(1 for r in all_rows_last if r['channels'] == 'OZ')
    both_ch = sum(1 for r in all_rows_last if r['channels'] == 'WB+OZ')
    models_set = set(r['model'] for r in all_rows_last)
    total_margin = sum(r['margin'] for r in all_rows_last)
    total_revenue = sum(r['revenue'] for r in all_rows_last)
    total_adv = sum(r['adv_total'] for r in all_rows_last)
    margin_pct = (total_margin / total_revenue * 100) if total_revenue > 0 else 0
    drr_pct = (total_adv / total_revenue * 100) if total_revenue > 0 else 0

    period_days = (datetime.strptime(end_date, '%Y-%m-%d') - datetime.strptime(start_date, '%Y-%m-%d')).days

    # Модельный подсчёт
    model_articles = defaultdict(int)
    for r in all_rows_last:
        model_articles[r['model']] += 1

    # Классификация
    best = good = bad = new = 0
    best_margin = good_margin = bad_margin = new_margin = 0
    status_to_nelikvid = 0
    status_from_vyvodim = 0

    classified_rows = []
    for row in all_rows_last:
        art = row['article']
        m = meta.get(art, {})
        status = m.get('status', 'Нет данных')
        color_code = m.get('color_code', '')
        model_osnova = (m.get('model_osnova') or '').lower()
        tip_kol = m.get('tip_kollekcii')
        line = get_product_line(model_osnova, tip_kol)

        abc_l = abc_last.get(art, 'C')
        abc_p = abc_prev.get(art)
        ht_l = high_turn_last.get(art, False)
        ht_p = high_turn_prev.get(art, False)
        turn = turnover_last.get(art, 0)

        category, rec, reasons, dynamics = classify_article(
            abc_l, abc_p, ht_l, ht_p,
            status, row['margin'], model_articles[row['model']]
        )

        # Цвет в линейке
        color_rec = '—'
        if line and color_code:
            ca = color_analysis.get((line, color_code))
            if ca:
                color_rec = ca['recommendation']

        if category == 'Лучшие':
            best += 1
            best_margin += row['margin']
        elif category == 'Хорошие':
            good += 1
            good_margin += row['margin']
        elif category == 'Неликвид':
            bad += 1
            bad_margin += row['margin']
        else:
            new += 1
            new_margin += row['margin']

        if status == 'Продается' and category == 'Неликвид':
            status_to_nelikvid += 1
        if status == 'Выводим' and category in ('Лучшие', 'Хорошие'):
            status_from_vyvodim += 1

        classified_rows.append({
            'article': art,
            'model': row['model'],
            'line': line or '—',
            'color_code': color_code or '—',
            'channels': row['channels'],
            'status': status,
            'category': category,
            'abc_last': abc_l,
            'abc_prev': abc_p or '—',
            'margin': row['margin'],
            'wb_margin': row.get('wb_margin', 0),
            'ozon_margin': row.get('ozon_margin', 0),
            'margin_pct': (row['margin'] / row['revenue'] * 100) if row['revenue'] > 0 else 0,
            'turnover': turn,
            'color_rec': color_rec,
            'rec': rec,
            'reasons': '; '.join(reasons[:3]),
        })

    lines.append(f'**Артикулов**: {total_articles} (WB: {wb_only + both_ch}, OZON: {oz_only + both_ch}, на обоих: {both_ch})')
    lines.append(f'**Моделей**: {len(models_set)}')
    lines.append(f'**Период дней**: {period_days}')
    lines.append(f'**Маржа бренда**: {format_num(total_margin)} руб ({format_pct(margin_pct)})')
    lines.append(f'**ДРР бренда**: {format_pct(drr_pct)}')
    lines.append('')

    # Распределение
    lines.append('**Распределение:**')
    m_share = lambda m: f' ({format_pct(m / total_margin * 100)} маржи)' if total_margin > 0 else ''
    lines.append(f'- Лучшие: {best}{m_share(best_margin)}')
    lines.append(f'- Хорошие: {good}{m_share(good_margin)}')
    lines.append(f'- Неликвид: {bad}{m_share(bad_margin)}')
    lines.append(f'- Новый: {new}')
    lines.append('')

    if status_to_nelikvid > 0:
        lines.append(f'**Продается -> Неликвид: {status_to_nelikvid} артикулов** (рекомендуем вывод)')
    if status_from_vyvodim > 0:
        lines.append(f'**Выводим -> Хорошие/Лучшие: {status_from_vyvodim} артикулов** (рекомендуем вернуть)')
    lines.append('')
    lines.append('---')
    lines.append('')

    # Таблица
    lines.append('## Таблица ABC-анализа')
    lines.append('')

    header = '| Артикул | Модель | Линейка | Цвет | Каналы | Статус | Категория | ABC | ABC пред. | Маржа всего | Маржа WB | Маржа OZ | Маржин-ть% | Оборот дн. | Цвет в линейке | Рек. статус | Причины |'
    sep = '|---|---|---|---|---|---|---|---|---|---:|---:|---:|---:|---:|---|---|---|'
    lines.append(header)
    lines.append(sep)

    # Сортировка: по модели, потом по марже убывающей
    classified_rows.sort(key=lambda x: (x['model'], -x['margin']))

    for r in classified_rows:
        turn_str = str(round(r['turnover'])) if r['turnover'] > 0 else '—'
        lines.append(
            f"| {r['article']} | {r['model']} | {r['line']} | {r['color_code']} "
            f"| {r['channels']} | {r['status']} | {r['category']} "
            f"| {r['abc_last']} | {r['abc_prev']} "
            f"| {format_num(r['margin'])} | {format_num(r['wb_margin'])} | {format_num(r['ozon_margin'])} "
            f"| {format_pct(r['margin_pct'])} | {turn_str} "
            f"| {r['color_rec']} | {r['rec']} | {r['reasons']} |"
        )

    return '\n'.join(lines)


# =============================================================================
# ОРКЕСТРАТОР
# =============================================================================

def run_unified(save=False, notion=False, start_date=None, end_date=None):
    """Основная функция: загрузка, мерж, классификация, отчёт + JSON."""

    # Даты по умолчанию: ~3 месяца назад от вчера
    if not end_date:
        end_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    if not start_date:
        # ~3 месяца назад, округляем до 1-го числа
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        start_dt = (end_dt - timedelta(days=90)).replace(day=1)
        start_date = start_dt.strftime('%Y-%m-%d')

    # Период сравнения: такой же длины, непосредственно до основного
    period_days = (datetime.strptime(end_date, '%Y-%m-%d') - datetime.strptime(start_date, '%Y-%m-%d')).days
    prev_end = start_date
    prev_start_dt = datetime.strptime(prev_end, '%Y-%m-%d') - timedelta(days=period_days)
    prev_start = prev_start_dt.strftime('%Y-%m-%d')

    print('=' * 60)
    print(' Единый ABC-анализ бренда Wookiee')
    print(f' Основной период: {start_date} — {end_date} ({period_days} дн.)')
    print(f' Сравнение:       {prev_start} — {prev_end} ({period_days} дн.)')
    print('=' * 60)

    # 1. Метаданные
    print('\n  Загрузка метаданных из Supabase...')
    meta = get_artikuly_full_info()
    print(f'  -> {len(meta)} артикулов')

    # 2. Финансы основной период
    print('  Загрузка финансов WB (основной период)...')
    wb_last = get_wb_by_article(start_date, end_date)
    print(f'  -> {len(wb_last)} WB артикулов')

    print('  Загрузка финансов OZON (основной период)...')
    ozon_last = get_ozon_by_article(start_date, end_date)
    print(f'  -> {len(ozon_last)} OZON артикулов')

    # 3. Финансы период сравнения
    print('  Загрузка финансов WB (период сравнения)...')
    wb_prev = get_wb_by_article(prev_start, prev_end)
    print(f'  -> {len(wb_prev)} WB артикулов')

    print('  Загрузка финансов OZON (период сравнения)...')
    ozon_prev = get_ozon_by_article(prev_start, prev_end)
    print(f'  -> {len(ozon_prev)} OZON артикулов')

    # 4. Мерж каналов
    print('\n  Объединение каналов...')
    data_last = merge_channel_data(wb_last, ozon_last)
    data_prev = merge_channel_data(wb_prev, ozon_prev)
    print(f'  -> {len(data_last)} объединённых артикулов (основной)')
    print(f'  -> {len(data_prev)} объединённых артикулов (сравнение)')

    # 5. Заказы WB
    print('  Загрузка заказов WB...')
    wb_orders = get_wb_orders_by_article(start_date, end_date)
    print(f'  -> {len(wb_orders)} артикулов')

    # 6. Остатки
    print('  Загрузка остатков WB...')
    wb_stock_last = get_wb_avg_stock(start_date, end_date)
    wb_stock_prev = get_wb_avg_stock(prev_start, prev_end)
    print(f'  -> {len(wb_stock_last)} WB артикулов')

    print('  Загрузка остатков OZON...')
    ozon_stock_last = get_ozon_avg_stock(start_date, end_date)
    ozon_stock_prev = get_ozon_avg_stock(prev_start, prev_end)
    print(f'  -> {len(ozon_stock_last)} OZON артикулов')

    # 7. Комбинированная оборачиваемость
    turnover_last = {}
    turnover_prev = {}
    for row in data_last:
        art = row['article']
        stock = to_float(wb_stock_last.get(art, 0)) + to_float(ozon_stock_last.get(art, 0))
        daily = row['sales_count'] / period_days if row['sales_count'] > 0 else 0
        turnover_last[art] = stock / daily if daily > 0 else 0

    prev_days = (datetime.strptime(prev_end, '%Y-%m-%d') - datetime.strptime(prev_start, '%Y-%m-%d')).days
    for row in data_prev:
        art = row['article']
        stock = to_float(wb_stock_prev.get(art, 0)) + to_float(ozon_stock_prev.get(art, 0))
        daily = row['sales_count'] / prev_days if row['sales_count'] > 0 else 0
        turnover_prev[art] = stock / daily if daily > 0 else 0

    # 8. ABC-классификация
    print('\n  ABC-классификация...')
    abc_last = calc_abc_classes(data_last)
    abc_prev = calc_abc_classes(data_prev) if data_prev else {}

    # 9. Высокий оборот
    high_turn_last = calc_high_turnover(data_last, turnover_last)
    high_turn_prev = calc_high_turnover(data_prev, turnover_prev) if data_prev else {}

    # 10. Анализ цветов по линейкам
    print('  Анализ цветов по линейкам...')
    color_analysis = analyze_color_across_line(data_last, meta, abc_last)
    colors_to_remove = sum(1 for v in color_analysis.values() if v['recommendation'] == 'Убрать')
    colors_mixed = sum(1 for v in color_analysis.values() if v['recommendation'] == 'Смешанный')
    print(f'  -> {len(color_analysis)} цветов в линейках, {colors_to_remove} к выводу, {colors_mixed} смешанных')

    # 11. Totals
    total_margin = sum(r['margin'] for r in data_last)
    total_revenue = sum(r['revenue'] for r in data_last)
    total_adv = sum(r['adv_total'] for r in data_last)
    a_count = sum(1 for v in abc_last.values() if v == 'A')
    b_count = sum(1 for v in abc_last.values() if v == 'B')
    c_count = sum(1 for v in abc_last.values() if v == 'C')

    totals = {
        'articles': len(data_last),
        'models': len(set(r['model'] for r in data_last)),
        'total_margin': round(total_margin),
        'total_revenue': round(total_revenue),
        'total_adv': round(total_adv),
        'margin_pct': round(total_margin / total_revenue * 100, 1) if total_revenue > 0 else 0,
        'drr_pct': round(total_adv / total_revenue * 100, 1) if total_revenue > 0 else 0,
        'distribution': {'A': a_count, 'B': b_count, 'C': c_count},
        'period_days': period_days,
    }

    # 12. Подготовка JSON-контекста для анализа Claude Code
    print('\n  Подготовка данных для анализа...')
    analysis_ctx = prepare_analysis_context(
        data_last, meta, abc_last, abc_prev,
        color_analysis, turnover_last, totals,
        start_date, end_date, prev_start, prev_end
    )
    ctx_size = len(json.dumps(analysis_ctx, ensure_ascii=False))
    print(f'  -> Контекст: {ctx_size:,} символов')

    # 13. Генерация отчёта (сводка + таблица)
    print('\n  Генерация отчёта...')
    report_md = build_unified_report(
        data_last, data_prev, meta,
        abc_last, abc_prev, turnover_last,
        high_turn_last, high_turn_prev,
        color_analysis,
        start_date, end_date, prev_start, prev_end
    )

    # 14. Сохранение
    reports_dir = os.path.join(PROJECT_ROOT, 'reports')
    os.makedirs(reports_dir, exist_ok=True)

    if save:
        # Markdown отчёт
        md_filename = f'abc_analysis_unified_{start_date}_{end_date}.md'
        md_path = os.path.join(reports_dir, md_filename)
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(report_md)
        print(f'\n  Отчёт: {md_path}')

    # JSON всегда сохраняем (нужен для Claude Code)
    json_filename = f'abc_unified_data_{start_date}_{end_date}.json'
    json_path = os.path.join(reports_dir, json_filename)
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(analysis_ctx, f, ensure_ascii=False, indent=2)
    print(f'  Данные для анализа: {json_path}')

    # 15. Notion (только таблица+сводка, аналитику Claude Code добавит отдельно)
    if notion:
        try:
            from scripts.notion_sync import sync_report_to_notion
            print('\n  Синхронизация с Notion...')
            notion_title = f"ABC-анализ бренда {start_date} — {end_date}"
            url = sync_report_to_notion(
                start_date, end_date, report_md,
                source="ABC-анализ Unified", title=notion_title
            )
            if url:
                print(f'  Notion: {url}')
        except Exception as e:
            print(f'  Ошибка Notion: {e}')

    # Вывод в консоль (краткая сводка)
    print('\n' + '=' * 60)
    print(f'  Маржа бренда: {format_num(total_margin)} руб ({totals["margin_pct"]}%)')
    print(f'  ДРР: {totals["drr_pct"]}%')
    print(f'  Артикулов: {totals["articles"]}, Моделей: {totals["models"]}')
    print(f'  ABC: A={a_count}, B={b_count}, C={c_count}')
    print(f'  Цветов к выводу: {colors_to_remove}, смешанных: {colors_mixed}')
    print('=' * 60)

    return report_md, json_path


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Единый ABC-анализ бренда Wookiee (WB + OZON)')
    parser.add_argument('--save', action='store_true',
                        help='Сохранить Markdown-отчёт в reports/')
    parser.add_argument('--notion', action='store_true',
                        help='Синхронизировать в Notion')
    parser.add_argument('--start', type=str, default=None,
                        help='Начало периода (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, default=None,
                        help='Конец периода (YYYY-MM-DD)')
    args = parser.parse_args()

    run_unified(save=args.save, notion=args.notion,
                start_date=args.start, end_date=args.end)


if __name__ == '__main__':
    main()
