"""
ABC-анализ по финансовым данным.

Классифицирует каждый артикул внутри своей модели:
  «Лучшие» / «Хорошие» / «Неликвид» / «Новый»

Использование:
  python scripts/abc_analysis.py --channel wb --save --notion
  python scripts/abc_analysis.py --channel ozon --save --notion
  python scripts/abc_analysis.py --channel both --save --notion
"""

import os
import sys
import argparse
from datetime import datetime, timedelta
from statistics import median

# Корень проекта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.data_layer import (
    to_float, format_num, format_pct,
    get_wb_by_article, get_ozon_by_article,
    get_wb_orders_by_article,
    get_wb_avg_stock, get_ozon_avg_stock,
    get_artikuly_full_info,
)
from scripts.abc_helpers import calc_abc_classes, calc_high_turnover, classify_article

from calendar import monthrange


# =============================================================================
# ПЕРИОДЫ (dynamic — last full month vs month before)
# =============================================================================

def _default_periods():
    """Calculate default periods: last full month and the month before."""
    today = datetime.today()
    # Last month: 1st of current month - 1 day → that month
    last_month_end_dt = today.replace(day=1)  # 1st of current month = exclusive end
    last_month_start_dt = (last_month_end_dt - timedelta(days=1)).replace(day=1)
    # Previous month
    prev_month_end_dt = last_month_start_dt
    prev_month_start_dt = (prev_month_end_dt - timedelta(days=1)).replace(day=1)

    last_days = monthrange(last_month_start_dt.year, last_month_start_dt.month)[1]
    prev_days = monthrange(prev_month_start_dt.year, prev_month_start_dt.month)[1]

    return (
        last_month_start_dt.strftime('%Y-%m-%d'),
        last_month_end_dt.strftime('%Y-%m-%d'),
        prev_month_start_dt.strftime('%Y-%m-%d'),
        prev_month_end_dt.strftime('%Y-%m-%d'),
        last_days,
        prev_days,
    )


(LAST_MONTH_START, LAST_MONTH_END,
 PREV_MONTH_START, PREV_MONTH_END,
 LAST_MONTH_DAYS, PREV_MONTH_DAYS) = _default_periods()


# =============================================================================
# ГЕНЕРАЦИЯ ОТЧЁТА
# =============================================================================

def build_report(channel, data_last, data_prev, orders_last_map,
                 stocks_last, stocks_prev, meta,
                 last_days, prev_days):
    """
    Строит итоговую таблицу ABC-анализа.

    Возвращает Markdown-строку с таблицей.
    """
    channel_label = 'Wildberries' if channel == 'wb' else 'OZON'

    # Индексы по article (уже lowercase из SQL-запросов)
    last_by_art = {a['article']: a for a in data_last}
    prev_by_art = {a['article']: a for a in data_prev}

    # ABC-классификация
    abc_last = calc_abc_classes(data_last)
    abc_prev = calc_abc_classes(data_prev) if data_prev else {}

    # Оборачиваемость (дни)
    turnover_last = {}
    turnover_prev = {}
    for key, a in last_by_art.items():
        avg_stock = stocks_last.get(a['article'], stocks_last.get(key, 0))
        daily_sales = a['sales_count'] / last_days if a['sales_count'] > 0 else 0
        turnover_last[key] = avg_stock / daily_sales if daily_sales > 0 else 0

    for key, a in prev_by_art.items():
        avg_stock = stocks_prev.get(a['article'], stocks_prev.get(key, 0))
        daily_sales = a['sales_count'] / prev_days if a['sales_count'] > 0 else 0
        turnover_prev[key] = avg_stock / daily_sales if daily_sales > 0 else 0

    # Высокий оборот
    ht_last = calc_high_turnover(data_last, turnover_last)
    ht_prev = calc_high_turnover(data_prev, turnover_prev) if data_prev else {}

    # Количество артикулов в модели (для предупреждения о малых моделях)
    model_counts = {}
    for a in data_last:
        model_counts[a['model']] = model_counts.get(a['model'], 0) + 1

    # Собираем все артикулы (из последнего месяца, плюс из предыдущего если есть новые)
    all_articles = set(last_by_art.keys())
    # Не включаем артикулы, которые были только в предыдущем месяце —
    # если артикул не продавался в последнем месяце, он не должен быть в итоге
    # (пользователь хочет классификацию по последнему месяцу)

    # Формируем строки таблицы
    rows = []
    for key in sorted(all_articles):
        a_last = last_by_art.get(key, {})
        a_prev = prev_by_art.get(key, {})

        article = a_last.get('article', key)
        model = a_last.get('model', '')
        margin = a_last.get('margin', 0)
        revenue = a_last.get('revenue', 0)
        sales = a_last.get('sales_count', 0)
        orders = a_last.get('orders_count', 0)
        adv_int = a_last.get('adv_internal', 0)
        adv_ext = a_last.get('adv_external', 0)
        adv_total = a_last.get('adv_total', 0)

        # Метаданные из Supabase
        m = meta.get(key, {})
        status = m.get('status', 'Нет данных')
        color_code = m.get('color_code', '')
        cvet = m.get('cvet', '')
        color = m.get('color', '')
        skleyka = m.get('skleyka_wb', '')

        # Производные метрики
        margin_pct = (margin / revenue * 100) if revenue > 0 else 0
        drr = (adv_total / revenue * 100) if revenue > 0 else 0
        avg_check = (revenue / sales) if sales > 0 else 0

        # Для WB-заказов: подменяем данные из orders таблицы, если есть
        if orders_last_map and article in orders_last_map:
            ord_data = orders_last_map[article]
            orders = ord_data['orders_count']
            avg_check_orders = ord_data['orders_rub'] / orders if orders > 0 else 0
        else:
            avg_check_orders = avg_check

        turn = turnover_last.get(key, 0)

        abc_l = abc_last.get(key, '?')
        abc_p = abc_prev.get(key, '—')

        ht_l = ht_last.get(key, False)
        ht_p = ht_prev.get(key, False)

        mc = model_counts.get(model, 1)

        category, rec, reasons, dynamics = classify_article(
            abc_l, abc_p if abc_p != '—' else None,
            ht_l, ht_p,
            status, margin, mc
        )

        rows.append({
            'article': article,
            'model': model,
            'status': status,
            'color_code': color_code or '',
            'cvet': cvet or '',
            'color': color or '',
            'skleyka': skleyka or '',
            'orders': orders,
            'avg_check': avg_check_orders,
            'sales': sales,
            'margin': margin,
            'margin_pct': margin_pct,
            'adv_total': adv_total,
            'adv_internal': adv_int,
            'adv_external': adv_ext,
            'drr': drr,
            'turnover': turn,
            'category': category,
            'abc_last': abc_l,
            'abc_prev': abc_p,
            'ht': ht_l,
            'rec': rec,
            'reasons': reasons,
            'dynamics': dynamics,
        })

    # Сортировка: по модели, затем по марже убыванию
    rows.sort(key=lambda x: (x['model'], -x['margin']))

    # Генерация Markdown
    md_lines = []
    md_lines.append(f'# ABC-анализ: {channel_label}')
    md_lines.append('')
    md_lines.append(f'**Последний месяц**: {LAST_MONTH_START} — {LAST_MONTH_END}')
    md_lines.append(f'**Предыдущий месяц**: {PREV_MONTH_START} — {PREV_MONTH_END}')
    md_lines.append(f'**Всего артикулов**: {len(rows)}')
    md_lines.append(f'**Всего моделей**: {len(model_counts)}')
    md_lines.append('')

    # Сводка по категориям
    cat_counts = {}
    for r in rows:
        cat_counts[r['category']] = cat_counts.get(r['category'], 0) + 1
    md_lines.append('**Распределение:**')
    for cat in ['Лучшие', 'Хорошие', 'Неликвид', 'Новый']:
        cnt = cat_counts.get(cat, 0)
        md_lines.append(f'- {cat}: {cnt}')
    md_lines.append('')

    # Сводка расхождений статусов
    mismatches = [r for r in rows if r['status'] == 'Продается' and r['category'] == 'Неликвид']
    if mismatches:
        md_lines.append(f'**Расхождения статусов (Продается → Неликвид): {len(mismatches)} артикулов**')
        md_lines.append('')

    md_lines.append('---')
    md_lines.append('')

    # Таблица
    header = '| Артикул | Модель | Факт. статус | Итог. категория | Маржа, руб | Маржинальность, % | Оборот, дни | ABC посл. | ABC пред. | Оборот высокий? | Рекоменд. статус | Причины | Динамика |'
    sep = '|---|---|---|---|---:|---:|---:|---|---|---|---|---|---|'
    md_lines.append(header)
    md_lines.append(sep)

    for r in rows:
        reasons_str = '; '.join(r['reasons'][:3])
        ht_str = 'да' if r['ht'] else 'нет'
        turn_str = f"{r['turnover']:.0f}" if r['turnover'] > 0 else '—'

        line = (
            f"| {r['article']} "
            f"| {r['model']} "
            f"| {r['status']} "
            f"| {r['category']} "
            f"| {format_num(r['margin'])} "
            f"| {r['margin_pct']:.1f}% "
            f"| {turn_str} "
            f"| {r['abc_last']} "
            f"| {r['abc_prev']} "
            f"| {ht_str} "
            f"| {r['rec']} "
            f"| {reasons_str} "
            f"| {r['dynamics']} |"
        )
        md_lines.append(line)

    return '\n'.join(md_lines)


# =============================================================================
# ОСНОВНАЯ ЛОГИКА
# =============================================================================

def run_abc(channel, save=False, notion=False):
    """Запускает ABC-анализ для указанного канала."""
    print(f'\n{"="*60}')
    print(f' ABC-анализ: {channel.upper()}')
    print(f' Последний месяц: {LAST_MONTH_START} — {LAST_MONTH_END}')
    print(f' Предыдущий месяц: {PREV_MONTH_START} — {PREV_MONTH_END}')
    print(f'{"="*60}\n')

    # 1. Метаданные из Supabase
    print('  Загрузка метаданных из Supabase...')
    meta = get_artikuly_full_info()
    print(f'  → {len(meta)} артикулов')

    if channel == 'wb':
        # 2. Финансы WB
        print('  Загрузка финансов WB (последний месяц)...')
        data_last = get_wb_by_article(LAST_MONTH_START, LAST_MONTH_END)
        print(f'  → {len(data_last)} артикулов')

        print('  Загрузка финансов WB (предыдущий месяц)...')
        data_prev = get_wb_by_article(PREV_MONTH_START, PREV_MONTH_END)
        print(f'  → {len(data_prev)} артикулов')

        # 3. Заказы WB
        print('  Загрузка заказов WB...')
        orders_last = get_wb_orders_by_article(LAST_MONTH_START, LAST_MONTH_END)
        print(f'  → {len(orders_last)} артикулов')

        # 4. Остатки WB
        print('  Загрузка остатков WB (последний месяц)...')
        stocks_last = get_wb_avg_stock(LAST_MONTH_START, LAST_MONTH_END)
        print(f'  → {len(stocks_last)} артикулов')

        print('  Загрузка остатков WB (предыдущий месяц)...')
        stocks_prev = get_wb_avg_stock(PREV_MONTH_START, PREV_MONTH_END)
        print(f'  → {len(stocks_prev)} артикулов')

        orders_map = orders_last

    elif channel == 'ozon':
        # 2. Финансы OZON
        print('  Загрузка финансов OZON (последний месяц)...')
        data_last = get_ozon_by_article(LAST_MONTH_START, LAST_MONTH_END)
        print(f'  → {len(data_last)} артикулов')

        print('  Загрузка финансов OZON (предыдущий месяц)...')
        data_prev = get_ozon_by_article(PREV_MONTH_START, PREV_MONTH_END)
        print(f'  → {len(data_prev)} артикулов')

        # 3. Остатки OZON
        print('  Загрузка остатков OZON (последний месяц)...')
        stocks_last = get_ozon_avg_stock(LAST_MONTH_START, LAST_MONTH_END)
        print(f'  → {len(stocks_last)} артикулов')

        print('  Загрузка остатков OZON (предыдущий месяц)...')
        stocks_prev = get_ozon_avg_stock(PREV_MONTH_START, PREV_MONTH_END)
        print(f'  → {len(stocks_prev)} артикулов')

        orders_map = None  # OZON заказы уже в get_ozon_by_article

    # 5. Генерация отчёта
    print('\n  Генерация ABC-анализа...')
    report_md = build_report(
        channel, data_last, data_prev, orders_map,
        stocks_last, stocks_prev, meta,
        LAST_MONTH_DAYS, PREV_MONTH_DAYS
    )

    # Выводим в консоль
    print('\n' + report_md)

    # 6. Сохранение
    if save:
        reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'reports')
        os.makedirs(reports_dir, exist_ok=True)
        filename = f'abc_analysis_{channel}_{PREV_MONTH_START[:7]}_{LAST_MONTH_START[:7]}.md'
        filepath = os.path.join(reports_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report_md)
        print(f'\n  Сохранено: {filepath}')

    # 7. Notion
    if notion:
        try:
            from scripts.notion_sync import sync_report_to_notion
            print('\n  Синхронизация с Notion...')
            source_name = f"ABC-анализ {channel.upper()}"
            notion_title = f"ABC-анализ {channel.upper()} {PREV_MONTH_START.replace('-', '.')} — {LAST_MONTH_END.replace('-', '.')}"
            url = sync_report_to_notion(
                PREV_MONTH_START, LAST_MONTH_END, report_md,
                source=source_name, title=notion_title
            )
            if url:
                print(f'  Notion: {url}')
        except Exception as e:
            print(f'  Ошибка Notion: {e}')

    return report_md


def main():
    parser = argparse.ArgumentParser(description='ABC-анализ по финансовым данным')
    parser.add_argument('--channel', choices=['wb', 'ozon', 'both'], default='wb',
                        help='Канал: wb, ozon, both (по умолчанию: wb)')
    parser.add_argument('--save', action='store_true',
                        help='Сохранить в reports/')
    parser.add_argument('--notion', action='store_true',
                        help='Синхронизировать в Notion')
    args = parser.parse_args()

    if args.channel == 'both':
        run_abc('wb', save=args.save, notion=args.notion)
        run_abc('ozon', save=args.save, notion=args.notion)
    else:
        run_abc(args.channel, save=args.save, notion=args.notion)


if __name__ == '__main__':
    main()
