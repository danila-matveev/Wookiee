#!/usr/bin/env python3
"""
Аналитика за произвольный период с 4-уровневой иерархией.
Формулы маржи верифицированы против PowerBI (расхождение < 1%).

Иерархия:
1. Бренд (ИТОГО)
2. Канал продаж (WB, OZON)
3. Модель основа
4. Статус товара

Использование:
  python scripts/period_analytics.py --start 2026-02-01 --end 2026-02-05 --compare-days 5
  python scripts/period_analytics.py --start 2026-02-01 --end 2026-02-05  # compare-days = кол-во дней в периоде
"""

import sys
import os
import argparse
from datetime import datetime, timedelta
from decimal import Decimal

import psycopg2
from dotenv import load_dotenv

# Добавляем корень проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.config import DB_CONFIG, DB_WB, DB_OZON, SUPABASE_ENV_PATH
from scripts.data_layer import (
    to_float, format_num, format_pct, get_arrow, calc_change, calc_change_pp,
    get_wb_finance, get_wb_by_model, get_wb_traffic, get_wb_traffic_by_model,
    get_ozon_finance, get_ozon_by_model, get_ozon_traffic, get_artikuly_statuses,
)


# =============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Аналитика за произвольный период')
    parser.add_argument('--start', required=True, help='Начало текущего периода (YYYY-MM-DD)')
    parser.add_argument('--end', required=True, help='Конец текущего периода (YYYY-MM-DD)')
    parser.add_argument('--compare-days', type=int, default=None,
                        help='Кол-во дней для предыдущего периода (по умолчанию = длина текущего)')
    parser.add_argument('--save', action='store_true', help='Сохранить отчёт в reports/')
    parser.add_argument('--notion', action='store_true', help='Синхронизировать отчёт с Notion')
    parser.add_argument('--export-context', action='store_true',
                        help='Экспортировать data_context.json для LLM-анализа (Рома)')
    args = parser.parse_args()

    current_start = args.start
    current_end_date = datetime.strptime(args.end, '%Y-%m-%d')
    current_start_date = datetime.strptime(args.start, '%Y-%m-%d')

    days = (current_end_date - current_start_date).days
    compare_days = args.compare_days if args.compare_days else days

    # current_end — день ПОСЛЕ конца (exclusive)
    current_end = (current_end_date + timedelta(days=1)).strftime('%Y-%m-%d')
    prev_start = (current_start_date - timedelta(days=compare_days)).strftime('%Y-%m-%d')

    period_label = f"{args.start} — {args.end}"
    prev_end_date = current_start_date - timedelta(days=1)
    prev_start_date = current_start_date - timedelta(days=compare_days)
    prev_label = f"{prev_start_date.strftime('%Y-%m-%d')} — {prev_end_date.strftime('%Y-%m-%d')}"

    output_lines = []

    def out(text=""):
        output_lines.append(text)
        print(text)

    out("=" * 80)
    out(f"АНАЛИТИКА {period_label} vs {prev_label}")
    out("Формулы маржи верифицированы (расхождение с PowerBI < 1%)")
    out("=" * 80)

    # Загрузка данных
    out("\nЗагрузка данных...")
    out("  WB финансы...")
    wb_data, wb_orders = get_wb_finance(current_start, prev_start, current_end)
    wb_models = get_wb_by_model(current_start, prev_start, current_end)
    wb_content, wb_adv = get_wb_traffic(current_start, prev_start, current_end)

    out("  OZON финансы...")
    ozon_data, ozon_orders = get_ozon_finance(current_start, prev_start, current_end)
    ozon_models = get_ozon_by_model(current_start, prev_start, current_end)
    ozon_traffic = get_ozon_traffic(current_start, prev_start, current_end)

    out("  Статусы товаров из Supabase...")
    artikuly_statuses = get_artikuly_statuses()

    # Парсинг WB
    wb = {'current': {}, 'previous': {}}
    for row in wb_data:
        period = row[0]
        wb[period] = {
            'orders_count': to_float(row[1]),
            'sales_count': to_float(row[2]),
            'revenue_before_spp': to_float(row[3]),
            'revenue_after_spp': to_float(row[4]),
            'adv_internal': to_float(row[5]),
            'adv_external': to_float(row[6]),
            'cost_of_goods': to_float(row[7]),
            'logistics': to_float(row[8]),
            'storage': to_float(row[9]),
            'commission': to_float(row[10]),
            'spp_amount': to_float(row[11]),
            'nds': to_float(row[12]),
            'penalty': to_float(row[13]),
            'retention': to_float(row[14]),
            'deduction': to_float(row[15]),
            'margin': to_float(row[16]),
        }

    for row in wb_orders:
        period = row[0]
        if period in wb:
            wb[period]['orders_rub'] = to_float(row[1])

    # Парсинг OZON
    ozon = {'current': {}, 'previous': {}}
    for row in ozon_data:
        period = row[0]
        ozon[period] = {
            'sales_count': to_float(row[1]),
            'revenue_before_spp': to_float(row[2]),
            'revenue_after_spp': to_float(row[3]),
            'adv_internal': to_float(row[4]),
            'adv_external': to_float(row[5]),
            'margin': to_float(row[6]),
            'cost_of_goods': to_float(row[7]),
            'logistics': to_float(row[8]),
            'storage': to_float(row[9]),
            'commission': to_float(row[10]),
            'spp_amount': to_float(row[11]),
            'nds': to_float(row[12]),
        }

    for row in ozon_orders:
        period = row[0]
        if period in ozon:
            ozon[period]['orders_count'] = to_float(row[1])
            ozon[period]['orders_rub'] = to_float(row[2])

    # Расчёт производных метрик
    for channel in [wb, ozon]:
        for period in ['current', 'previous']:
            d = channel.get(period, {})
            if d:
                d['adv_total'] = d.get('adv_internal', 0) + d.get('adv_external', 0)
                d['avg_check_orders'] = d.get('orders_rub', 0) / d.get('orders_count', 1) if d.get('orders_count', 0) > 0 else 0
                d['avg_check_sales'] = d['revenue_before_spp'] / d['sales_count'] if d.get('sales_count', 0) > 0 else 0
                d['spp_pct'] = (d['spp_amount'] / d['revenue_before_spp'] * 100) if d.get('revenue_before_spp', 0) > 0 else 0
                d['drr'] = (d['adv_total'] / d['revenue_before_spp'] * 100) if d.get('revenue_before_spp', 0) > 0 else 0
                d['margin_pct'] = (d['margin'] / d['revenue_before_spp'] * 100) if d.get('revenue_before_spp', 0) > 0 else 0
                d['romi'] = (d['margin'] / d['adv_total'] * 100) if d.get('adv_total', 0) > 0 else 0

    # ИТОГО
    total = {'current': {}, 'previous': {}}
    for period in ['current', 'previous']:
        w = wb.get(period, {})
        o = ozon.get(period, {})
        total[period] = {
            'orders_count': w.get('orders_count', 0) + o.get('orders_count', 0),
            'orders_rub': w.get('orders_rub', 0) + o.get('orders_rub', 0),
            'sales_count': w.get('sales_count', 0) + o.get('sales_count', 0),
            'revenue_before_spp': w.get('revenue_before_spp', 0) + o.get('revenue_before_spp', 0),
            'revenue_after_spp': w.get('revenue_after_spp', 0) + o.get('revenue_after_spp', 0),
            'adv_total': w.get('adv_total', 0) + o.get('adv_total', 0),
            'margin': w.get('margin', 0) + o.get('margin', 0),
            'cost_of_goods': w.get('cost_of_goods', 0) + o.get('cost_of_goods', 0),
            'logistics': w.get('logistics', 0) + o.get('logistics', 0),
            'storage': w.get('storage', 0) + o.get('storage', 0),
            'commission': w.get('commission', 0) + o.get('commission', 0),
        }
        t = total[period]
        t['avg_check_orders'] = t['orders_rub'] / t['orders_count'] if t['orders_count'] > 0 else 0
        t['avg_check_sales'] = t['revenue_before_spp'] / t['sales_count'] if t['sales_count'] > 0 else 0
        t['drr'] = (t['adv_total'] / t['revenue_before_spp'] * 100) if t['revenue_before_spp'] > 0 else 0
        t['margin_pct'] = (t['margin'] / t['revenue_before_spp'] * 100) if t['revenue_before_spp'] > 0 else 0
        t['romi'] = (t['margin'] / t['adv_total'] * 100) if t['adv_total'] > 0 else 0

    # ======================================================================
    # РЕНДЕРИНГ В MARKDOWN
    # ======================================================================
    tc, tp = total['current'], total['previous']
    lines = []
    L = lines.append

    L(f"# Аналитика: {period_label}")
    L("")
    L(f"**Сравнение:** {period_label} vs {prev_label}")
    L(f"**Формулы маржи верифицированы** (расхождение с PowerBI < 1%)")
    L("")
    L("---")
    L("")

    # --- УРОВЕНЬ 1 ---
    L("## Уровень 1: Бренд (ИТОГО WB + OZON)")
    L("")
    L("| Метрика | Текущий | Пред. | Изменение |")
    L("|---------|---------|-------|-----------|")
    L(f"| **Заказы** | {format_num(tc['orders_count'])} шт / {format_num(tc['orders_rub'])} руб | {format_num(tp['orders_count'])} шт / {format_num(tp['orders_rub'])} руб | {get_arrow(calc_change(tc['orders_rub'], tp['orders_rub']))} {calc_change(tc['orders_rub'], tp['orders_rub']):+.1f}% |")
    buyout_total_c = (tc['sales_count'] / tc['orders_count'] * 100) if tc['orders_count'] > 0 else 0
    L(f"| **Продажи** | {format_num(tc['sales_count'])} шт (выкуп {format_pct(buyout_total_c)}) | {format_num(tp['sales_count'])} шт | {get_arrow(calc_change(tc['sales_count'], tp['sales_count']))} {calc_change(tc['sales_count'], tp['sales_count']):+.1f}% |")
    L(f"| **Выручка до СПП** | {format_num(tc['revenue_before_spp'])} руб | {format_num(tp['revenue_before_spp'])} руб | {get_arrow(calc_change(tc['revenue_before_spp'], tp['revenue_before_spp']))} {calc_change(tc['revenue_before_spp'], tp['revenue_before_spp']):+.1f}% |")
    L(f"| **Ср.чек заказов** | {format_num(tc['avg_check_orders'])} руб | {format_num(tp['avg_check_orders'])} руб | {get_arrow(calc_change(tc['avg_check_orders'], tp['avg_check_orders']))} {calc_change(tc['avg_check_orders'], tp['avg_check_orders']):+.1f}% |")
    L(f"| **Ср.чек продаж** | {format_num(tc['avg_check_sales'])} руб | {format_num(tp['avg_check_sales'])} руб | {get_arrow(calc_change(tc['avg_check_sales'], tp['avg_check_sales']))} {calc_change(tc['avg_check_sales'], tp['avg_check_sales']):+.1f}% |")
    L(f"| **Маржа** | {format_num(tc['margin'])} руб ({format_pct(tc['margin_pct'])}) | {format_num(tp['margin'])} руб ({format_pct(tp['margin_pct'])}) | {get_arrow(calc_change(tc['margin'], tp['margin']))} {calc_change(tc['margin'], tp['margin']):+.1f}% |")
    L(f"| **ДРР** | {format_pct(tc['drr'])} | {format_pct(tp['drr'])} | {calc_change_pp(tc['drr'], tp['drr']):+.1f} п.п. |")
    L(f"| **ROMI** | {format_pct(tc['romi'])} | {format_pct(tp['romi'])} | {get_arrow(calc_change(tc['romi'], tp['romi']))} {calc_change(tc['romi'], tp['romi']):+.1f}% |")
    L("")

    # Структура расходов
    L("### Структура расходов")
    L("")
    rev_c = tc['revenue_before_spp'] if tc['revenue_before_spp'] > 0 else 1
    rev_p = tp['revenue_before_spp'] if tp['revenue_before_spp'] > 0 else 1
    adv_pct_orders_c = (tc['adv_total'] / tc['orders_rub'] * 100) if tc['orders_rub'] > 0 else 0
    adv_pct_orders_p = (tp['adv_total'] / tp['orders_rub'] * 100) if tp['orders_rub'] > 0 else 0
    sebes_pct_c = tc['cost_of_goods'] / rev_c * 100
    sebes_pct_p = tp['cost_of_goods'] / rev_p * 100
    log_pct_c = tc['logistics'] / rev_c * 100
    log_pct_p = tp['logistics'] / rev_p * 100
    stor_pct_c = tc['storage'] / rev_c * 100
    stor_pct_p = tp['storage'] / rev_p * 100
    com_pct_c = tc['commission'] / rev_c * 100
    com_pct_p = tp['commission'] / rev_p * 100

    L("| Статья | Сумма | % от выручки | Изменение доли |")
    L("|--------|-------|-------------|----------------|")
    L(f"| Реклама | {format_num(tc['adv_total'])} руб | {format_pct(adv_pct_orders_c)} от заказов | {calc_change_pp(adv_pct_orders_c, adv_pct_orders_p):+.1f} п.п. |")
    L(f"| Себестоимость | {format_num(tc['cost_of_goods'])} руб | {format_pct(sebes_pct_c)} | {calc_change_pp(sebes_pct_c, sebes_pct_p):+.1f} п.п. |")
    L(f"| Логистика | {format_num(tc['logistics'])} руб | {format_pct(log_pct_c)} | {calc_change_pp(log_pct_c, log_pct_p):+.1f} п.п. |")
    L(f"| Хранение | {format_num(tc['storage'])} руб | {format_pct(stor_pct_c)} | {calc_change_pp(stor_pct_c, stor_pct_p):+.1f} п.п. |")
    L(f"| Комиссия | {format_num(tc['commission'])} руб | {format_pct(com_pct_c)} | {calc_change_pp(com_pct_c, com_pct_p):+.1f} п.п. |")
    L("")
    L("---")
    L("")

    # --- УРОВЕНЬ 2: КАНАЛЫ ---
    L("## Уровень 2: Каналы продаж")
    L("")

    # Парсим рекламные данные
    wb_adv_c, wb_adv_p = {}, {}
    for row in wb_adv:
        period = row[0]
        d = {'views': to_float(row[1]), 'clicks': to_float(row[2]), 'atbs': to_float(row[3]),
             'orders': to_float(row[4]), 'spend': to_float(row[5]), 'ctr': to_float(row[6]), 'cpc': to_float(row[7])}
        if period == 'current':
            wb_adv_c = d
        else:
            wb_adv_p = d

    ozon_adv_c, ozon_adv_p = {}, {}
    for row in ozon_traffic:
        period = row[0]
        d = {'views': to_float(row[1]), 'clicks': to_float(row[2]),
             'orders': to_float(row[3]), 'spend': to_float(row[4]), 'ctr': to_float(row[5]), 'cpc': to_float(row[6])}
        if period == 'current':
            ozon_adv_c = d
        else:
            ozon_adv_p = d

    channel_adv = {'Wildberries': (wb_adv_c, wb_adv_p), 'OZON': (ozon_adv_c, ozon_adv_p)}

    for channel_name, channel_data in [("Wildberries", wb), ("OZON", ozon)]:
        c, p = channel_data.get('current', {}), channel_data.get('previous', {})
        if not c or not p:
            continue

        L(f"### {channel_name}")
        L("")

        # Воронка + маржа
        buyout_pct_c = (c['sales_count'] / c.get('orders_count', 1) * 100) if c.get('orders_count', 0) > 0 else 0
        ch_rev_c = c['revenue_before_spp'] if c['revenue_before_spp'] > 0 else 1
        ch_sebes_pct = c.get('cost_of_goods', 0) / ch_rev_c * 100
        ch_log_pct = c.get('logistics', 0) / ch_rev_c * 100
        ch_com_pct = c.get('commission', 0) / ch_rev_c * 100

        L("| Метрика | Текущий | Пред. | Изменение |")
        L("|---------|---------|-------|-----------|")
        L(f"| Заказы | {format_num(c.get('orders_count', 0))} шт / {format_num(c.get('orders_rub', 0))} руб | {format_num(p.get('orders_count', 0))} шт / {format_num(p.get('orders_rub', 0))} руб | {get_arrow(calc_change(c.get('orders_rub', 0), p.get('orders_rub', 0)))} {calc_change(c.get('orders_rub', 0), p.get('orders_rub', 0)):+.1f}% |")
        L(f"| Продажи | {format_num(c['sales_count'])} шт (выкуп {format_pct(buyout_pct_c)}) | {format_num(p['sales_count'])} шт | {get_arrow(calc_change(c['sales_count'], p['sales_count']))} {calc_change(c['sales_count'], p['sales_count']):+.1f}% |")
        L(f"| Выручка до СПП | {format_num(c['revenue_before_spp'])} руб | {format_num(p['revenue_before_spp'])} руб | {get_arrow(calc_change(c['revenue_before_spp'], p['revenue_before_spp']))} {calc_change(c['revenue_before_spp'], p['revenue_before_spp']):+.1f}% |")
        L(f"| СПП | {format_pct(c['spp_pct'])} | {format_pct(p['spp_pct'])} | {calc_change_pp(c['spp_pct'], p['spp_pct']):+.1f} п.п. |")
        L(f"| **Маржа** | **{format_num(c['margin'])} руб ({format_pct(c['margin_pct'])})** | {format_num(p['margin'])} руб ({format_pct(p['margin_pct'])}) | {get_arrow(calc_change(c['margin'], p['margin']))} {calc_change(c['margin'], p['margin']):+.1f}% |")
        L(f"| Расходы от выр. | себест. {format_pct(ch_sebes_pct)} / логист. {format_pct(ch_log_pct)} / комис. {format_pct(ch_com_pct)} | | |")
        L("")

        # Реклама
        adv_c_data, adv_p_data = channel_adv[channel_name]
        if adv_c_data:
            ch_drr_orders = (c['adv_total'] / c.get('orders_rub', 1) * 100) if c.get('orders_rub', 0) > 0 else 0
            ctr_c = adv_c_data.get('ctr', 0)
            ctr_p = adv_p_data.get('ctr', 0) if adv_p_data else 0
            cpc_c = adv_c_data.get('cpc', 0)
            cpc_p = adv_p_data.get('cpc', 0) if adv_p_data else 0
            ad_orders_c = adv_c_data.get('orders', 0)
            cpo_c = adv_c_data.get('spend', 0) / ad_orders_c if ad_orders_c > 0 else 0
            ad_orders_p = adv_p_data.get('orders', 0) if adv_p_data else 0
            cpo_p = adv_p_data.get('spend', 0) / ad_orders_p if ad_orders_p > 0 and adv_p_data else 0

            L("**Реклама:**")
            L("")
            L("| Метрика | Текущий | Изменение |")
            L("|---------|---------|-----------|")
            L(f"| ДРР от заказов | {format_pct(ch_drr_orders)} | ДРР от выр.: {format_pct(c['drr'])} |")
            L(f"| Расход | {format_num(adv_c_data.get('spend', 0))} руб | {get_arrow(calc_change(adv_c_data.get('spend', 0), adv_p_data.get('spend', 0) if adv_p_data else 0))} {calc_change(adv_c_data.get('spend', 0), adv_p_data.get('spend', 0) if adv_p_data else 0):+.1f}% |")
            L(f"| Показы | {format_num(adv_c_data.get('views', 0))} | {get_arrow(calc_change(adv_c_data.get('views', 0), adv_p_data.get('views', 0) if adv_p_data else 0))} {calc_change(adv_c_data.get('views', 0), adv_p_data.get('views', 0) if adv_p_data else 0):+.1f}% |")
            L(f"| Клики | {format_num(adv_c_data.get('clicks', 0))} | {get_arrow(calc_change(adv_c_data.get('clicks', 0), adv_p_data.get('clicks', 0) if adv_p_data else 0))} {calc_change(adv_c_data.get('clicks', 0), adv_p_data.get('clicks', 0) if adv_p_data else 0):+.1f}% |")
            L(f"| CTR | {format_pct(ctr_c)} | {calc_change_pp(ctr_c, ctr_p):+.2f} п.п. |")
            L(f"| CPC | {cpc_c:.1f} руб | {get_arrow(calc_change(cpc_c, cpc_p))} {calc_change(cpc_c, cpc_p):+.1f}% |")
            if cpo_c > 0:
                L(f"| CPO | {cpo_c:.0f} руб | {get_arrow(calc_change(cpo_c, cpo_p))} {calc_change(cpo_c, cpo_p):+.1f}% |")
            L("")

        # Инсайты
        insights = []
        margin_ch = calc_change(c['margin'], p['margin'])
        orders_ch = calc_change(c.get('orders_rub', 0), p.get('orders_rub', 0))
        adv_ch = calc_change(c['adv_total'], p.get('adv_total', 0))
        spp_pp = calc_change_pp(c['spp_pct'], p['spp_pct'])

        if margin_ch > 15:
            insights.append(f"Маржа растёт (+{margin_ch:.0f}%)")
        elif margin_ch < -15:
            insights.append(f"Маржа падает ({margin_ch:.0f}%)")
        if adv_ch > 30 and margin_ch > 0:
            insights.append(f"Рост рекламы (+{adv_ch:.0f}%) окупается ростом маржи")
        elif adv_ch > 30 and margin_ch < 0:
            insights.append(f"Рост рекламы (+{adv_ch:.0f}%) не окупается — маржа падает")
        if abs(spp_pp) > 3:
            direction = "выросла" if spp_pp > 0 else "снизилась"
            insights.append(f"СПП {direction} на {abs(spp_pp):.1f} п.п. — внешний фактор")
        if orders_ch > 20 and calc_change(c['sales_count'], p['sales_count']) < 5:
            insights.append("Заказы растут, но продажи нет — возможно растут возвраты")

        if insights:
            for ins in insights:
                L(f"> {ins}")
            L("")

    L("---")
    L("")

    # --- УРОВЕНЬ 3: МОДЕЛИ ---
    L("## Уровень 3: Модели (ТОП-10 по марже)")
    L("")

    wb_models_current = [(row[1], to_float(row[5]), to_float(row[3]), to_float(row[4])) for row in wb_models if row[0] == 'current']
    wb_models_prev = {row[1]: to_float(row[5]) for row in wb_models if row[0] == 'previous'}
    wb_models_current.sort(key=lambda x: x[1], reverse=True)

    L("### WB ТОП-10")
    L("")
    L("| # | Модель | Маржа | Маржин. | ДРР | Изм. маржи |")
    L("|---|--------|-------|---------|-----|------------|")
    for i, (model, margin, revenue, adv) in enumerate(wb_models_current[:10], 1):
        prev_margin = wb_models_prev.get(model, 0)
        m_pct = (margin / revenue * 100) if revenue > 0 else 0
        drr = (adv / revenue * 100) if revenue > 0 else 0
        ch = calc_change(margin, prev_margin)
        L(f"| {i} | {model} | {format_num(margin)} руб | {format_pct(m_pct)} | {format_pct(drr)} | {get_arrow(ch)} {ch:+.1f}% |")
    L("")

    ozon_models_current = [(row[1], to_float(row[5]), to_float(row[3]), to_float(row[4])) for row in ozon_models if row[0] == 'current']
    ozon_models_prev = {row[1]: to_float(row[5]) for row in ozon_models if row[0] == 'previous'}
    ozon_models_current.sort(key=lambda x: x[1], reverse=True)

    L("### OZON ТОП-10")
    L("")
    L("| # | Модель | Маржа | Маржин. | ДРР | Изм. маржи |")
    L("|---|--------|-------|---------|-----|------------|")
    for i, (model, margin, revenue, adv) in enumerate(ozon_models_current[:10], 1):
        prev_margin = ozon_models_prev.get(model, 0)
        m_pct = (margin / revenue * 100) if revenue > 0 else 0
        drr = (adv / revenue * 100) if revenue > 0 else 0
        ch = calc_change(margin, prev_margin)
        L(f"| {i} | {model} | {format_num(margin)} руб | {format_pct(m_pct)} | {format_pct(drr)} | {get_arrow(ch)} {ch:+.1f}% |")
    L("")
    L("---")
    L("")

    # --- ТОПОВАЯ МОДЕЛЬ ---
    if wb_models_current:
        top_model = wb_models_current[0][0]
        top_margin = wb_models_current[0][1]
        top_revenue = wb_models_current[0][2]
        top_adv = wb_models_current[0][3]
        prev_margin = wb_models_prev.get(top_model, 0)

        L(f"## Топовая модель WB: {top_model}")
        L("")
        L("| Метрика | Значение | Изменение |")
        L("|---------|----------|-----------|")
        L(f"| Маржа | {format_num(top_margin)} руб | {get_arrow(calc_change(top_margin, prev_margin))} {calc_change(top_margin, prev_margin):+.1f}% |")
        L(f"| Маржинальность | {format_pct(top_margin / top_revenue * 100 if top_revenue > 0 else 0)} | |")
        L(f"| Выручка | {format_num(top_revenue)} руб | |")
        L(f"| Реклама | {format_num(top_adv)} руб | ДРР {format_pct(top_adv / top_revenue * 100 if top_revenue > 0 else 0)} |")

        wb_traffic_data = get_wb_traffic_by_model(current_start, prev_start, current_end)
        model_traffic_current = [row for row in wb_traffic_data if row[0] == 'current' and row[1] == top_model]
        model_traffic_prev = [row for row in wb_traffic_data if row[0] == 'previous' and row[1] == top_model]

        if model_traffic_current:
            mt_c = model_traffic_current[0]
            mt_p = model_traffic_prev[0] if model_traffic_prev else (None, None, 0, 0, 0, 0, 0)
            L(f"| Показы (рекл.) | {format_num(to_float(mt_c[2]))} | {get_arrow(calc_change(to_float(mt_c[2]), to_float(mt_p[2])))} {calc_change(to_float(mt_c[2]), to_float(mt_p[2])):+.1f}% |")
            L(f"| Клики | {format_num(to_float(mt_c[3]))} | {get_arrow(calc_change(to_float(mt_c[3]), to_float(mt_p[3])))} {calc_change(to_float(mt_c[3]), to_float(mt_p[3])):+.1f}% |")
            L(f"| CTR | {format_pct(to_float(mt_c[5]))} | {calc_change_pp(to_float(mt_c[5]), to_float(mt_p[5])):+.2f} п.п. |")
            L(f"| CPC | {to_float(mt_c[6]):.1f} руб | {get_arrow(calc_change(to_float(mt_c[6]), to_float(mt_p[6])))} {calc_change(to_float(mt_c[6]), to_float(mt_p[6])):+.1f}% |")
        L("")
        L("---")
        L("")

    # При --export-context эти секции пропускаются: Рома (LLM) напишет анализ сам
    if not args.export_context:
        # --- ГИПОТЕЗЫ ---
        L("## Гипотезы")
        L("")

        margin_change = calc_change(tc['margin'], tp['margin'])
        if abs(margin_change) > 5:
            direction = "выросла" if margin_change > 0 else "упала"
            L(f"**Маржа {direction} на {format_pct(abs(margin_change))}** ({format_num(tc['margin'] - tp['margin'])} руб)")
            L("")
            hyp_items = []
            ozon_ch = calc_change(ozon['current']['margin'], ozon['previous']['margin'])
            wb_ch = calc_change(wb['current']['margin'], wb['previous']['margin'])
            adv_ch = calc_change(tc['adv_total'], tp['adv_total'])
            if abs(ozon_ch) > 20:
                hyp_items.append(f"OZON маржа {'+' if ozon_ch > 0 else ''}{ozon_ch:.0f}%")
            if abs(wb_ch) > 20:
                hyp_items.append(f"WB маржа {'+' if wb_ch > 0 else ''}{wb_ch:.0f}%")
            if adv_ch > 10:
                hyp_items.append(f"Рост рекламы +{adv_ch:.0f}% мог привести к росту продаж")
            elif adv_ch < -10:
                hyp_items.append(f"Снижение рекламы {adv_ch:.0f}%")
            for item in hyp_items:
                L(f"- {item}")
            L("")
        else:
            L("Маржа в пределах нормы.")
            L("")

        L("---")
        L("")

        # --- РЕКОМЕНДАЦИИ ---
        L("## Рекомендации")
        L("")

        recommendations = []
        if tc['drr'] > 10:
            recommendations.append(f"**ДРР высокий ({format_pct(tc['drr'])})** — снизить ставки на 15-20% для товаров с низкой конверсией. Экономия ~{format_num(tc['adv_total'] * 0.15)} руб")
        if tc['margin_pct'] < 15:
            recommendations.append(f"**Маржинальность низкая ({format_pct(tc['margin_pct'])})** — поднять цены на 5-10% на товары с высоким спросом. Потенциал +{format_num(tc['revenue_before_spp'] * 0.05)} руб выручки")

        wb_orders_change = calc_change(wb['current'].get('orders_rub', 0), wb['previous'].get('orders_rub', 0))
        if wb_orders_change < -10:
            recommendations.append(f"**Заказы WB упали на {abs(wb_orders_change):.0f}%** — проверить ставки и бюджеты рекламных кампаний")

        ozon_margin_change = calc_change(ozon['current']['margin'], ozon['previous']['margin'])
        if ozon_margin_change > 20:
            recommendations.append(f"**OZON маржа +{ozon_margin_change:.0f}%** — масштабировать, увеличить бюджет рекламы на 20-30%")

        if recommendations:
            for i, rec in enumerate(recommendations, 1):
                L(f"{i}. {rec}")
        else:
            L("Критических отклонений не выявлено. Продолжать текущую стратегию.")
        L("")

    if args.export_context:
        L("")
        L("---")
        L("*Данные подготовлены для LLM-анализа (Рома). Гипотезы и рекомендации будут сгенерированы LLM.*")
    else:
        L("---")
        L(f"*Отчёт сгенерирован: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")

    report_md = '\n'.join(lines)
    print(report_md)

    # Сохранение отчёта
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    reports_dir = os.path.join(project_root, 'reports')

    if args.save:
        os.makedirs(reports_dir, exist_ok=True)
        report_path = os.path.join(reports_dir, f"{args.start}_{args.end}_analytics.md")
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_md)
        print(f"\nОтчёт сохранён: {report_path}")

    # --- Export data context for Рома (LLM analysis) ---
    if args.export_context and args.save:
        import json
        from scripts.analytics_agent_roma.context_builder import prepare_period_context

        # Подготовка данных моделей
        wb_models_c = [(row[1], to_float(row[5]), to_float(row[3]), to_float(row[4])) for row in wb_models if row[0] == 'current']
        wb_models_p_dict = {row[1]: to_float(row[5]) for row in wb_models if row[0] == 'previous'}
        wb_models_c.sort(key=lambda x: x[1], reverse=True)

        ozon_models_c = [(row[1], to_float(row[5]), to_float(row[3]), to_float(row[4])) for row in ozon_models if row[0] == 'current']
        ozon_models_p_dict = {row[1]: to_float(row[5]) for row in ozon_models if row[0] == 'previous'}
        ozon_models_c.sort(key=lambda x: x[1], reverse=True)

        ctx = prepare_period_context(
            start_date=args.start,
            end_date=args.end,
            prev_start=prev_start_date.strftime('%Y-%m-%d'),
            prev_end=prev_end_date.strftime('%Y-%m-%d'),
            wb=wb, ozon=ozon, total=total,
            wb_models_c=wb_models_c, wb_models_p=wb_models_p_dict,
            ozon_models_c=ozon_models_c, ozon_models_p=ozon_models_p_dict,
            wb_adv_data=wb_adv,
            ozon_traffic_data=ozon_traffic,
        )
        ctx_path = os.path.join(reports_dir, f"{args.start}_{args.end}_data_context.json")
        with open(ctx_path, 'w', encoding='utf-8') as f:
            json.dump(ctx, f, ensure_ascii=False, indent=2)
        print(f"[Period] Контекст для Ромы сохранён: {ctx_path}")

    # --- Notion sync (skip when export-context: Рома сделает после анализа) ---
    if args.notion and not args.export_context:
        try:
            from scripts.notion_sync import sync_report_to_notion
            url = sync_report_to_notion(args.start, args.end, report_md)
            print(f"\n[Notion] Отчёт синхронизирован: {url}")
        except Exception as e:
            print(f"\n[Notion] Ошибка синхронизации: {e}")
    elif args.notion and args.export_context:
        print(f"[Period] Notion sync пропущен: Рома допишет анализ, затем sync")


if __name__ == "__main__":
    main()
