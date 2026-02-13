#!/usr/bin/env python3
"""
Месячный аналитический отчёт с понедельной динамикой,
сравнением с бизнес-целями и confidence scoring.

Формулы маржи верифицированы против PowerBI (расхождение < 1%).

Использование:
  python scripts/monthly_analytics.py --month 2026-01
  python scripts/monthly_analytics.py --month 2026-01 --compare 2025-12
  python scripts/monthly_analytics.py --month 2026-01 --save --notion
"""

import sys
import os
import argparse
import math
from datetime import datetime, timedelta
from calendar import monthrange

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.data_layer import (
    to_float, format_num, format_pct, get_arrow, calc_change, calc_change_pp,
    get_wb_finance, get_wb_by_model, get_wb_traffic, get_wb_traffic_by_model,
    get_ozon_finance, get_ozon_by_model, get_ozon_traffic, get_artikuly_statuses,
    get_wb_weekly_breakdown, get_ozon_weekly_breakdown,
    get_wb_daily_series_range, get_ozon_daily_series_range,
)


# =============================================================================
# КОНСТАНТЫ
# =============================================================================

TARGETS = {
    'margin_monthly_min': 5_000_000,
    'margin_monthly_mid': 6_500_000,
    'margin_pct_min': 20.0,
    'margin_pct_mid': 23.0,
    'margin_pct_high': 25.0,
    'drr_warning': 10.0,
}

CONFIDENCE_THRESHOLD = 0.6

MONTH_NAMES_RU = {
    1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
    5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
    9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь',
}


# =============================================================================
# CONFIDENCE ENGINE (адаптировано из daily_analytics.py)
# =============================================================================

def _stdev(values):
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((x - mean) ** 2 for x in values) / len(values))


def _cv(values):
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    if abs(mean) < 1:
        return 1.0
    return _stdev(values) / abs(mean)


def compute_confidence(evidence_directions, change_pct, series_values):
    total = len([e for e in evidence_directions if e != 0])
    confirming = len([e for e in evidence_directions if e > 0])
    direction = confirming / max(total, 1)

    if len(series_values) >= 3:
        sd = _stdev(series_values)
        mean = sum(series_values) / len(series_values)
        relative_sd = (sd / abs(mean) * 100) if abs(mean) > 1 else 50
        magnitude = min(1.0, abs(change_pct) / max(2 * relative_sd, 1))
    else:
        magnitude = 0.5

    if len(series_values) >= 3:
        stability = max(0.0, min(1.0, 1.0 - _cv(series_values)))
    else:
        stability = 0.5

    score = 0.4 * direction + 0.35 * magnitude + 0.25 * stability
    return round(min(1.0, max(0.0, score)), 2)


def confidence_label(score):
    if score >= 0.8:
        return "высокий"
    elif score >= 0.6:
        return "средний"
    elif score >= 0.3:
        return "низкий"
    return "очень низкий"


# =============================================================================
# MONTHLY RED TEAM
# =============================================================================

def monthly_red_team_checks(hypothesis, data_ctx):
    triggered = []
    penalty = 0.0

    # 1. Низкая база (OZON)
    if 'ozon_share' in data_ctx and data_ctx['ozon_share'] < 0.10:
        if hypothesis.get('category') in ('ozon', 'channel_divergence'):
            triggered.append(f"Низкая база: OZON = {data_ctx['ozon_share']*100:.1f}% от total — % изменения завышены")
            penalty += 0.15

    # 2. СПП изменение маркетплейсом
    if abs(data_ctx.get('spp_change_pp', 0)) > 2.0:
        if hypothesis.get('category') in ('margin', 'price'):
            triggered.append(f"Изменение СПП маркетплейсом: {data_ctx['spp_change_pp']:+.1f} п.п. — внешний фактор")
            penalty += 0.15

    # 3. Сезонность (декабрь → январь)
    if data_ctx.get('is_post_holiday', False):
        if hypothesis.get('category') in ('margin', 'model'):
            triggered.append("Сезонность: январь — постпраздничный спад, декабрь — пик продаж")
            penalty += 0.10

    return penalty, triggered


# =============================================================================
# ГЕНЕРАЦИЯ ГИПОТЕЗ (месячная адаптация)
# =============================================================================

def generate_monthly_hypotheses(wb, ozon, total, wb_daily, ozon_daily,
                                wb_models_c, wb_models_p,
                                ozon_models_c, ozon_models_p,
                                wb_adv_data, ozon_traffic_data):
    hypotheses = []
    tc, tp = total['current'], total['previous']

    total_margin_series = []
    if wb_daily and ozon_daily:
        wb_map = {d['date']: d['margin'] for d in wb_daily}
        ozon_map = {d['date']: d['margin'] for d in ozon_daily}
        all_dates = sorted(set(list(wb_map.keys()) + list(ozon_map.keys())))
        total_margin_series = [wb_map.get(d, 0) + ozon_map.get(d, 0) for d in all_dates]
    elif wb_daily:
        total_margin_series = [d['margin'] for d in wb_daily]

    wb_margin_series = [d['margin'] for d in wb_daily]
    ozon_margin_series = [d['margin'] for d in ozon_daily]
    total_adv_series = []
    if wb_daily and ozon_daily:
        wb_adv_map = {d['date']: d.get('adv_total', 0) for d in wb_daily}
        ozon_adv_map = {d['date']: d.get('adv_total', 0) for d in ozon_daily}
        all_dates = sorted(set(list(wb_adv_map.keys()) + list(ozon_adv_map.keys())))
        total_adv_series = [wb_adv_map.get(d, 0) + ozon_adv_map.get(d, 0) for d in all_dates]

    # ---------- H1: Маржинальная прибыль ----------
    margin_change = calc_change(tc['margin'], tp['margin'])
    if abs(margin_change) > 3:
        levers = []

        price_cur = tc['revenue_before_spp'] / tc['sales_count'] if tc['sales_count'] > 0 else 0
        price_prev = tp['revenue_before_spp'] / tp['sales_count'] if tp['sales_count'] > 0 else 0
        price_change = calc_change(price_cur, price_prev)
        levers.append(('Цена до СПП', price_change, price_cur, price_prev))

        spp_cur = tc.get('spp_pct', 0)
        spp_prev = tp.get('spp_pct', 0)
        spp_pp = calc_change_pp(spp_cur, spp_prev)
        levers.append(('СПП %', spp_pp, spp_cur, spp_prev))

        drr_pp = calc_change_pp(tc['drr'], tp['drr'])
        levers.append(('ДРР', drr_pp, tc['drr'], tp['drr']))

        log_per_unit_cur = tc['logistics'] / tc['sales_count'] if tc['sales_count'] > 0 else 0
        log_per_unit_prev = tp['logistics'] / tp['sales_count'] if tp['sales_count'] > 0 else 0
        log_change = calc_change(log_per_unit_cur, log_per_unit_prev)
        levers.append(('Логистика ₽/ед', log_change, log_per_unit_cur, log_per_unit_prev))

        buyout_cur = (tc['sales_count'] / tc['orders_count'] * 100) if tc.get('orders_count', 0) > 0 else 0
        buyout_prev = (tp['sales_count'] / tp['orders_count'] * 100) if tp.get('orders_count', 0) > 0 else 0
        buyout_pp = calc_change_pp(buyout_cur, buyout_prev)
        levers.append(('Выкуп %', buyout_pp, buyout_cur, buyout_prev))

        sebes_cur = tc['cost_of_goods'] / tc['sales_count'] if tc['sales_count'] > 0 else 0
        sebes_prev = tp['cost_of_goods'] / tp['sales_count'] if tp['sales_count'] > 0 else 0
        sebes_change = calc_change(sebes_cur, sebes_prev)

        lever_impacts = [(name, abs(val)) for name, val, _, _ in levers]
        lever_impacts.sort(key=lambda x: x[1], reverse=True)
        primary_lever = lever_impacts[0][0]

        evidence = []
        if margin_change > 0:
            evidence.append(+1 if price_change > 0 else (-1 if price_change < -1 else 0))
            evidence.append(-1 if spp_pp > 1 else (+1 if spp_pp < -1 else 0))
            evidence.append(-1 if drr_pp > 1 else (+1 if drr_pp < -1 else 0))
        else:
            evidence.append(-1 if price_change > 0 else (+1 if price_change < -1 else 0))
            evidence.append(+1 if spp_pp > 1 else (-1 if spp_pp < -1 else 0))
            evidence.append(+1 if drr_pp > 1 else (-1 if drr_pp < -1 else 0))

        conf = compute_confidence(evidence, margin_change, total_margin_series)
        abs_change = tc['margin'] - tp['margin']

        if margin_change < 0:
            what_if = f"Если устранить влияние {primary_lever}: потенциальное восстановление ~{format_num(abs(abs_change))} руб/мес маржи"
        else:
            what_if = f"Если сохранить динамику на следующий месяц: дополнительно +{format_num(abs(abs_change))} руб/мес маржи"

        hypotheses.append({
            'id': 'H1',
            'statement': f"Маржинальная прибыль {'выросла' if margin_change > 0 else 'снизилась'} на {abs(margin_change):.1f}% ({abs_change:+,.0f} руб). Главный рычаг: {primary_lever}",
            'confidence': conf,
            'sources': [f"abc_date.margin ({margin_change:+.1f}%)", f"{primary_lever} ({lever_impacts[0][1]:.1f})"],
            'triangulation': len([e for e in evidence if e > 0]),
            'triangulation_total': len([e for e in evidence if e != 0]),
            'what_if': what_if,
            'levers': levers,
            'sebes_change': sebes_change,
            'sebes_cur': sebes_cur,
            'sebes_prev': sebes_prev,
            'category': 'margin',
            'counter_arguments': [],
        })

    # ---------- H2: СПП рост ----------
    wb_spp_pp = calc_change_pp(wb['current'].get('spp_pct', 0), wb['previous'].get('spp_pct', 0))
    ozon_spp_pp = calc_change_pp(ozon['current'].get('spp_pct', 0), ozon['previous'].get('spp_pct', 0))
    if abs(wb_spp_pp) > 1.0 or abs(ozon_spp_pp) > 1.0:
        channel = 'WB' if abs(wb_spp_pp) > abs(ozon_spp_pp) else 'OZON'
        spp_pp = wb_spp_pp if channel == 'WB' else ozon_spp_pp
        ch_data = wb['current'] if channel == 'WB' else ozon['current']
        lost_revenue = ch_data['revenue_before_spp'] * abs(spp_pp) / 100
        evidence = [+1 if spp_pp > 0 else -1, +1 if margin_change != 0 else 0]
        spp_series = [d.get('spp_amount', 0) / max(d.get('revenue_before_spp', 1), 1) * 100 for d in (wb_daily if channel == 'WB' else ozon_daily)]
        conf = compute_confidence(evidence, spp_pp, spp_series)

        hypotheses.append({
            'id': 'H2',
            'statement': f"СПП на {channel} {'выросла' if spp_pp > 0 else 'снизилась'} на {abs(spp_pp):.1f} п.п. → {'давит' if spp_pp > 0 else 'помогает'} маржу (~{format_num(lost_revenue)} руб/мес)",
            'confidence': conf,
            'sources': [f"{channel}.spp_pct ({spp_pp:+.1f} п.п.)", f"lost revenue ~{format_num(lost_revenue)} руб"],
            'triangulation': len([e for e in evidence if e > 0]),
            'triangulation_total': len([e for e in evidence if e != 0]),
            'what_if': f"Если поднять цену на {abs(spp_pp):.0f}% для компенсации → восстановление ~{format_num(lost_revenue)} руб выручки/мес. Риск: возможное снижение заказов",
            'category': 'price',
            'counter_arguments': [],
        })

    # ---------- H3: ДРР аномалия ----------
    drr_change = calc_change_pp(tc['drr'], tp['drr'])
    if abs(drr_change) > 1.0:
        adv_change_pct = calc_change(tc['adv_total'], tp['adv_total'])
        adv_abs = tc['adv_total'] - tp['adv_total']

        ctr_info = ""
        if wb_adv_data:
            wb_adv_c = [r for r in wb_adv_data if r[0] == 'current']
            wb_adv_p = [r for r in wb_adv_data if r[0] == 'previous']
            if wb_adv_c and wb_adv_p:
                ctr_c, cpc_c = to_float(wb_adv_c[0][6]), to_float(wb_adv_c[0][7])
                ctr_p, cpc_p = to_float(wb_adv_p[0][6]), to_float(wb_adv_p[0][7])
                ctr_info = f"CTR {ctr_c:.2f}% ({calc_change_pp(ctr_c, ctr_p):+.2f} п.п.), CPC {format_num(cpc_c, 1)} руб ({calc_change(cpc_c, cpc_p):+.1f}%)"

        evidence = [
            +1 if drr_change > 0 and adv_change_pct > 0 else -1,
            +1 if drr_change > 0 else -1,
        ]
        conf = compute_confidence(evidence, drr_change, total_adv_series)

        hypotheses.append({
            'id': 'H3',
            'statement': f"ДРР {'вырос' if drr_change > 0 else 'снизился'} на {abs(drr_change):.1f} п.п. (реклама {adv_change_pct:+.1f}%, {adv_abs:+,.0f} руб). {ctr_info}",
            'confidence': conf,
            'sources': [f"ДРР {drr_change:+.1f} п.п.", f"adv_total {adv_change_pct:+.1f}%", ctr_info or "нет данных CTR"],
            'triangulation': len([e for e in evidence if e > 0]),
            'triangulation_total': len([e for e in evidence if e != 0]),
            'what_if': f"Если {'оптимизировать РК (снизить ставки на 20%)' if drr_change > 0 else 'сохранить текущую эффективность'} → экономия ~{format_num(abs(adv_abs) * 0.2)} руб/мес",
            'category': 'advertising',
            'counter_arguments': [],
        })

    # ---------- H4: Расхождение каналов ----------
    wb_margin_change = calc_change(wb['current']['margin'], wb['previous']['margin'])
    ozon_margin_change = calc_change(ozon['current']['margin'], ozon['previous']['margin'])
    if (wb_margin_change > 0) != (ozon_margin_change > 0) and abs(wb_margin_change - ozon_margin_change) > 15:
        evidence = [+1, +1]
        conf = compute_confidence(evidence, abs(wb_margin_change - ozon_margin_change), total_margin_series)

        hypotheses.append({
            'id': 'H4',
            'statement': f"Каналы расходятся: WB маржа {wb_margin_change:+.1f}%, OZON маржа {ozon_margin_change:+.1f}%",
            'confidence': conf,
            'sources': [f"WB margin {wb_margin_change:+.1f}%", f"OZON margin {ozon_margin_change:+.1f}%"],
            'triangulation': 2,
            'triangulation_total': 2,
            'what_if': f"Стоит проверить: {'что тянет WB вниз' if wb_margin_change < 0 else 'что тянет OZON вниз'} — возможно проблема локализована в одном канале",
            'category': 'channel_divergence',
            'counter_arguments': [],
        })

    # ---------- H5: Аномалии моделей ----------
    total_margin_cur = tc['margin']
    all_models_c = {}
    all_models_p = {}
    for model, margin, revenue, adv in wb_models_c:
        key = model.lower() if model else model
        all_models_c[key] = all_models_c.get(key, 0) + margin
    for model, margin in wb_models_p.items():
        key = model.lower() if model else model
        all_models_p[key] = all_models_p.get(key, 0) + margin
    for model, margin, revenue, adv in ozon_models_c:
        key = model.lower() if model else model
        all_models_c[key] = all_models_c.get(key, 0) + margin
    for model, margin in ozon_models_p.items():
        # ozon_models_p уже с lowercase ключами
        all_models_p[model] = all_models_p.get(model, 0) + margin

    sorted_models = sorted(all_models_c.items(), key=lambda x: x[1], reverse=True)
    for model, margin in sorted_models[:5]:
        prev_margin = all_models_p.get(model, 0)
        model_change = calc_change(margin, prev_margin)
        if abs(model_change) > 10 and abs(margin - prev_margin) > 20000:
            evidence = [+1]
            conf = compute_confidence(evidence, model_change, total_margin_series)
            share = (margin / total_margin_cur * 100) if total_margin_cur > 0 else 0
            impact = margin - prev_margin

            hypotheses.append({
                'id': f'H5_{model}',
                'statement': f"Модель {model} ({share:.0f}% маржи): маржа {model_change:+.1f}% ({impact:+,.0f} руб/мес)",
                'confidence': conf,
                'sources': [f"abc_date model={model} margin {model_change:+.1f}%"],
                'triangulation': 1,
                'triangulation_total': 1,
                'what_if': f"{'Если падение продолжится' if model_change < 0 else 'Если масштабировать'}: влияние ~{format_num(abs(impact))} руб/мес",
                'category': 'model',
                'counter_arguments': [],
            })

    # ---------- H6: Логистика ----------
    log_total_change = calc_change(tc['logistics'], tp['logistics'])
    if abs(log_total_change) > 5:
        log_per_sale = tc['logistics'] / tc['sales_count'] if tc['sales_count'] > 0 else 0
        log_per_sale_prev = tp['logistics'] / tp['sales_count'] if tp['sales_count'] > 0 else 0
        log_savings_10pct = tc['logistics'] * 0.10
        evidence = [+1 if log_total_change > 0 else -1]
        log_series = [d.get('logistics', 0) for d in wb_daily]
        conf = compute_confidence(evidence, log_total_change, log_series)

        hypotheses.append({
            'id': 'H6',
            'statement': f"Логистика {log_total_change:+.1f}% ({tc['logistics'] - tp['logistics']:+,.0f} руб). На единицу: {format_num(log_per_sale, 0)} руб ({calc_change(log_per_sale, log_per_sale_prev):+.1f}%)",
            'confidence': conf,
            'sources': [f"logistics total {log_total_change:+.1f}%", f"logistics/unit {calc_change(log_per_sale, log_per_sale_prev):+.1f}%"],
            'triangulation': 1,
            'triangulation_total': 1,
            'what_if': f"Если снизить логистику на 10% через перераспределение остатков → экономия ~{format_num(log_savings_10pct)} руб/мес",
            'category': 'logistics',
            'counter_arguments': [],
        })

    return hypotheses


# =============================================================================
# РЕНДЕР ОТЧЁТА
# =============================================================================

def render_monthly_report(target_month, compare_month, wb, ozon, total,
                          wb_weekly, ozon_weekly,
                          wb_models_c, wb_models_p, ozon_models_c, ozon_models_p,
                          artikuly_statuses,
                          wb_content, wb_adv, ozon_traffic,
                          hypotheses, wb_daily, ozon_daily):
    lines = []
    L = lines.append

    tc, tp = total['current'], total['previous']
    t_year, t_month = map(int, target_month.split('-'))
    c_year, c_month = map(int, compare_month.split('-'))
    t_name = MONTH_NAMES_RU[t_month]
    c_name = MONTH_NAMES_RU[c_month]
    t_days = monthrange(t_year, t_month)[1]
    c_days = monthrange(c_year, c_month)[1]

    L(f"# Месячный отчёт: {t_name} {t_year}")
    L("")
    L(f"**Сравнение:** {t_name} {t_year} vs {c_name} {c_year}")
    L(f"**Формулы маржи верифицированы:** расхождение с PowerBI < 1%")
    L("")
    L("---")
    L("")

    # =========================================================================
    # EXECUTIVE SUMMARY
    # =========================================================================
    L("## Executive Summary")
    L("")

    # Флаги
    margin_flag = "RED" if tc['margin'] < TARGETS['margin_monthly_min'] else ("GREEN" if tc['margin'] >= TARGETS['margin_monthly_mid'] else "YELLOW")
    margin_pct_flag = "RED" if tc['margin_pct'] < TARGETS['margin_pct_min'] else ("GREEN" if tc['margin_pct'] >= TARGETS['margin_pct_high'] else "YELLOW")
    drr_flag = "RED" if tc['drr'] > TARGETS['drr_warning'] else "GREEN"

    flag_emoji = {"RED": "!!!", "YELLOW": "!", "GREEN": "OK"}

    L("### Статус")
    L("")
    L(f"| Показатель | Факт | Ориентир | Статус |")
    L(f"|------------|------|----------|--------|")
    L(f"| Маржа | {format_num(tc['margin'])} руб | {format_num(TARGETS['margin_monthly_min'])}–{format_num(TARGETS['margin_monthly_mid'])} руб | {flag_emoji[margin_flag]} |")
    L(f"| Маржинальность | {format_pct(tc['margin_pct'])} | {format_pct(TARGETS['margin_pct_min'])}–{format_pct(TARGETS['margin_pct_high'])} | {flag_emoji[margin_pct_flag]} |")
    L(f"| ДРР | {format_pct(tc['drr'])} | < {format_pct(TARGETS['drr_warning'])} | {flag_emoji[drr_flag]} |")
    L("")

    # Ключевые изменения
    margin_change = calc_change(tc['margin'], tp['margin'])
    revenue_change = calc_change(tc['revenue_before_spp'], tp['revenue_before_spp'])
    orders_change = calc_change(tc['orders_rub'], tp['orders_rub'])
    sales_change = calc_change(tc['sales_count'], tp['sales_count'])
    adv_change = calc_change(tc['adv_total'], tp['adv_total'])

    wins = []
    losses = []
    if margin_change > 2:
        wins.append(f"Маржа выросла на {format_pct(margin_change)} (+{format_num(tc['margin'] - tp['margin'])} руб)")
    elif margin_change < -2:
        losses.append(f"Маржа снизилась на {format_pct(abs(margin_change))} ({format_num(tc['margin'] - tp['margin'])} руб)")
    if revenue_change > 5:
        wins.append(f"Выручка выросла на {format_pct(revenue_change)}")
    elif revenue_change < -5:
        losses.append(f"Выручка снизилась на {format_pct(abs(revenue_change))}")
    if sales_change > 5:
        wins.append(f"Продажи выросли на {format_pct(sales_change)} шт")
    elif sales_change < -5:
        losses.append(f"Продажи снизились на {format_pct(abs(sales_change))}")
    if adv_change < -10:
        wins.append(f"Расходы на рекламу снизились на {format_pct(abs(adv_change))}")
    elif adv_change > 20:
        losses.append(f"Расходы на рекламу выросли на {format_pct(adv_change)}")

    wb_margin_change = calc_change(wb['current']['margin'], wb['previous']['margin'])
    ozon_margin_change = calc_change(ozon['current']['margin'], ozon['previous']['margin'])
    if wb_margin_change > 5:
        wins.append(f"WB маржа +{format_pct(wb_margin_change)}")
    if ozon_margin_change > 20:
        wins.append(f"OZON маржа +{format_pct(ozon_margin_change)}")
    if wb_margin_change < -5:
        losses.append(f"WB маржа {format_pct(wb_margin_change)}")
    if ozon_margin_change < -20:
        losses.append(f"OZON маржа {format_pct(ozon_margin_change)}")

    if wins:
        L("### Победы")
        L("")
        for w in wins:
            L(f"- {w}")
        L("")

    if losses:
        L("### Проблемы")
        L("")
        for l in losses:
            L(f"- {l}")
        L("")

    L("---")
    L("")

    # =========================================================================
    # УРОВЕНЬ 1: БРЕНД (ИТОГО)
    # =========================================================================
    L("## Уровень 1: Бренд (ИТОГО WB + OZON)")
    L("")

    daily_avg_cur = tc['margin'] / t_days
    daily_avg_prev = tp['margin'] / c_days

    L("### Ключевые показатели")
    L("")
    L(f"| Метрика | {t_name} {t_year} | {c_name} {c_year} | Изменение | Статус |")
    L(f"|---------|{'---'*5}|{'---'*5}|-----------|--------|")
    L(f"| **Маржа** | {format_num(tc['margin'])} руб | {format_num(tp['margin'])} руб | {get_arrow(margin_change)} {margin_change:+.1f}% ({format_num(tc['margin'] - tp['margin'])}) | {flag_emoji[margin_flag]} |")
    L(f"| **Маржа/день** | {format_num(daily_avg_cur)} руб | {format_num(daily_avg_prev)} руб | {get_arrow(calc_change(daily_avg_cur, daily_avg_prev))} {calc_change(daily_avg_cur, daily_avg_prev):+.1f}% | — |")
    L(f"| **Маржинальность** | {format_pct(tc['margin_pct'])} | {format_pct(tp['margin_pct'])} | {calc_change_pp(tc['margin_pct'], tp['margin_pct']):+.1f} п.п. | {flag_emoji[margin_pct_flag]} |")
    L(f"| **ДРР** | {format_pct(tc['drr'])} | {format_pct(tp['drr'])} | {calc_change_pp(tc['drr'], tp['drr']):+.1f} п.п. | {flag_emoji[drr_flag]} |")
    L(f"| **ROMI** | {format_pct(tc['romi'])} | {format_pct(tp['romi'])} | {calc_change(tc['romi'], tp['romi']):+.1f}% | — |")
    L(f"| **Выручка до СПП** | {format_num(tc['revenue_before_spp'])} руб | {format_num(tp['revenue_before_spp'])} руб | {get_arrow(revenue_change)} {revenue_change:+.1f}% | — |")
    L(f"| **Заказы** | {format_num(tc['orders_count'])} шт / {format_num(tc['orders_rub'])} руб | {format_num(tp['orders_count'])} шт / {format_num(tp['orders_rub'])} руб | {get_arrow(orders_change)} {orders_change:+.1f}% | — |")
    L(f"| **Продажи** | {format_num(tc['sales_count'])} шт | {format_num(tp['sales_count'])} шт | {get_arrow(sales_change)} {sales_change:+.1f}% | — |")
    L(f"| **Ср.чек заказов** | {format_num(tc['avg_check_orders'])} руб | {format_num(tp['avg_check_orders'])} руб | {calc_change(tc['avg_check_orders'], tp['avg_check_orders']):+.1f}% | — |")
    L(f"| **Ср.чек продаж** | {format_num(tc['avg_check_sales'])} руб | {format_num(tp['avg_check_sales'])} руб | {calc_change(tc['avg_check_sales'], tp['avg_check_sales']):+.1f}% | — |")
    L("")

    L("### Структура расходов")
    L("")
    L(f"| Статья | {t_name} | {c_name} | Изменение |")
    L(f"|--------|{'---'*5}|{'---'*5}|-----------|")
    L(f"| Реклама | {format_num(tc['adv_total'])} руб | {format_num(tp['adv_total'])} руб | {adv_change:+.1f}% |")
    L(f"| Себестоимость | {format_num(tc['cost_of_goods'])} руб | {format_num(tp['cost_of_goods'])} руб | {calc_change(tc['cost_of_goods'], tp['cost_of_goods']):+.1f}% |")
    L(f"| Логистика | {format_num(tc['logistics'])} руб | {format_num(tp['logistics'])} руб | {calc_change(tc['logistics'], tp['logistics']):+.1f}% |")
    L(f"| Хранение | {format_num(tc['storage'])} руб | {format_num(tp['storage'])} руб | {calc_change(tc['storage'], tp['storage']):+.1f}% |")
    L(f"| Комиссия | {format_num(tc['commission'])} руб | {format_num(tp['commission'])} руб | {calc_change(tc['commission'], tp['commission']):+.1f}% |")
    L("")
    L("---")
    L("")

    # =========================================================================
    # УРОВЕНЬ 2: КАНАЛЫ
    # =========================================================================
    L("## Уровень 2: Каналы продаж")
    L("")

    # Доля каналов
    wb_share = (wb['current']['margin'] / tc['margin'] * 100) if tc['margin'] > 0 else 0
    ozon_share = (ozon['current']['margin'] / tc['margin'] * 100) if tc['margin'] > 0 else 0
    L(f"**Доли маржи:** WB {format_pct(wb_share)} | OZON {format_pct(ozon_share)}")
    L("")

    for ch_name, ch_data in [("Wildberries", wb), ("OZON", ozon)]:
        c, p = ch_data.get('current', {}), ch_data.get('previous', {})
        if not c or not p:
            continue

        ch_margin_change = calc_change(c['margin'], p['margin'])
        ch_revenue_change = calc_change(c['revenue_before_spp'], p['revenue_before_spp'])
        ch_sales_change = calc_change(c['sales_count'], p['sales_count'])
        ch_adv_change = calc_change(c.get('adv_total', 0), p.get('adv_total', 0))

        L(f"### {ch_name}")
        L("")
        L(f"| Метрика | {t_name} | {c_name} | Изменение |")
        L(f"|---------|{'---'*5}|{'---'*5}|-----------|")
        L(f"| Маржа | {format_num(c['margin'])} руб ({format_pct(c.get('margin_pct', 0))}) | {format_num(p['margin'])} руб ({format_pct(p.get('margin_pct', 0))}) | {ch_margin_change:+.1f}% |")
        L(f"| ДРР | {format_pct(c.get('drr', 0))} | {format_pct(p.get('drr', 0))} | {calc_change_pp(c.get('drr', 0), p.get('drr', 0)):+.1f} п.п. |")
        L(f"| Выручка до СПП | {format_num(c['revenue_before_spp'])} руб | {format_num(p['revenue_before_spp'])} руб | {ch_revenue_change:+.1f}% |")
        L(f"| Заказы | {format_num(c.get('orders_rub', 0))} руб | {format_num(p.get('orders_rub', 0))} руб | {calc_change(c.get('orders_rub', 0), p.get('orders_rub', 0)):+.1f}% |")
        L(f"| Продажи | {format_num(c['sales_count'])} шт | {format_num(p['sales_count'])} шт | {ch_sales_change:+.1f}% |")
        L(f"| СПП | {format_pct(c.get('spp_pct', 0))} | {format_pct(p.get('spp_pct', 0))} | {calc_change_pp(c.get('spp_pct', 0), p.get('spp_pct', 0)):+.1f} п.п. |")
        L(f"| Реклама | {format_num(c.get('adv_total', 0))} руб | {format_num(p.get('adv_total', 0))} руб | {ch_adv_change:+.1f}% |")
        L("")

    L("---")
    L("")

    # =========================================================================
    # УРОВЕНЬ 3: МОДЕЛИ
    # =========================================================================
    L("## Уровень 3: Модели (ТОП-10 по марже)")
    L("")

    # Комбинированный рейтинг — нормализация имён к lowercase для корректного объединения WB + OZON
    combined_c = {}
    combined_rev = {}
    combined_adv = {}
    for model, margin, revenue, adv in wb_models_c:
        key = model.lower() if model else model
        combined_c[key] = combined_c.get(key, 0) + margin
        combined_rev[key] = combined_rev.get(key, 0) + revenue
        combined_adv[key] = combined_adv.get(key, 0) + adv
    for model, margin, revenue, adv in ozon_models_c:
        key = model.lower() if model else model
        combined_c[key] = combined_c.get(key, 0) + margin
        combined_rev[key] = combined_rev.get(key, 0) + revenue
        combined_adv[key] = combined_adv.get(key, 0) + adv

    combined_p = {}
    for model, margin in wb_models_p.items():
        key = model.lower() if model else model
        combined_p[key] = combined_p.get(key, 0) + margin
    for model, margin in ozon_models_p.items():
        # ozon_models_p уже с lowercase ключами
        combined_p[model] = combined_p.get(model, 0) + margin

    sorted_combined = sorted(combined_c.items(), key=lambda x: x[1], reverse=True)

    L("### Комбинированный рейтинг (WB + OZON)")
    L("")
    L(f"| # | Модель | Маржа | Маржин. | ДРР | Изм. маржи |")
    L(f"|---|--------|-------|---------|-----|------------|")
    for i, (model, margin) in enumerate(sorted_combined[:10], 1):
        prev_m = combined_p.get(model, 0)
        rev = combined_rev.get(model, 0)
        adv = combined_adv.get(model, 0)
        m_pct = (margin / rev * 100) if rev > 0 else 0
        drr = (adv / rev * 100) if rev > 0 else 0
        ch = calc_change(margin, prev_m)
        L(f"| {i} | {model} | {format_num(margin)} руб | {format_pct(m_pct)} | {format_pct(drr)} | {get_arrow(ch)} {ch:+.1f}% ({format_num(margin - prev_m)}) |")
    L("")

    # WB ТОП-10
    wb_models_sorted = sorted(wb_models_c, key=lambda x: x[1], reverse=True)
    L("### WB ТОП-10")
    L("")
    L(f"| # | Модель | Маржа | Маржин. | ДРР | Изм. маржи |")
    L(f"|---|--------|-------|---------|-----|------------|")
    for i, (model, margin, revenue, adv) in enumerate(wb_models_sorted[:10], 1):
        prev_m = wb_models_p.get(model, 0)
        m_pct = (margin / revenue * 100) if revenue > 0 else 0
        drr = (adv / revenue * 100) if revenue > 0 else 0
        ch = calc_change(margin, prev_m)
        L(f"| {i} | {model} | {format_num(margin)} руб | {format_pct(m_pct)} | {format_pct(drr)} | {get_arrow(ch)} {ch:+.1f}% |")
    L("")

    # OZON ТОП-10
    ozon_models_sorted = sorted(ozon_models_c, key=lambda x: x[1], reverse=True)
    L("### OZON ТОП-10")
    L("")
    L(f"| # | Модель | Маржа | Маржин. | ДРР | Изм. маржи |")
    L(f"|---|--------|-------|---------|-----|------------|")
    for i, (model, margin, revenue, adv) in enumerate(ozon_models_sorted[:10], 1):
        prev_m = ozon_models_p.get(model.lower() if model else model, 0)
        m_pct = (margin / revenue * 100) if revenue > 0 else 0
        drr = (adv / revenue * 100) if revenue > 0 else 0
        ch = calc_change(margin, prev_m)
        L(f"| {i} | {model} | {format_num(margin)} руб | {format_pct(m_pct)} | {format_pct(drr)} | {get_arrow(ch)} {ch:+.1f}% |")
    L("")

    L("---")
    L("")

    # =========================================================================
    # УРОВЕНЬ 4: СТАТУСЫ
    # =========================================================================
    L("## Уровень 4: Статусы товаров")
    L("")
    if artikuly_statuses:
        # Группируем маржу по статусам
        status_margin_c = {}
        status_margin_p = {}
        status_sales_c = {}

        # WB модели -> артикулы -> статусы (упрощённо: модель = первая часть артикула)
        # Данные по моделям уже агрегированы, привяжем через artikuly_statuses
        all_articles_c = {}
        for model, margin, revenue, adv in wb_models_c + ozon_models_c:
            model_lower = model.lower()
            for article, status in artikuly_statuses.items():
                if article.startswith(model_lower + '/') or article == model_lower:
                    status_margin_c[status] = status_margin_c.get(status, 0) + margin / max(1, sum(1 for a in artikuly_statuses if a.startswith(model_lower + '/') or a == model_lower))

        if status_margin_c:
            sorted_statuses = sorted(status_margin_c.items(), key=lambda x: x[1], reverse=True)
            L(f"| Статус | Маржа (прибл.) |")
            L(f"|--------|----------------|")
            for status, margin in sorted_statuses:
                L(f"| {status} | {format_num(margin)} руб |")
            L("")
        else:
            L("(Приблизительная привязка по моделям — для точного анализа требуется прямая связь артикулов)")
            L("")
    else:
        L("(Требуется связь артикулов из БД с Supabase для полного анализа)")
        L("")

    L("---")
    L("")

    # =========================================================================
    # ПОНЕДЕЛЬНАЯ ДИНАМИКА
    # =========================================================================
    L("## Понедельная динамика")
    L("")

    # Объединяем WB + OZON по неделям
    wb_week_map = {w['week_start']: w for w in wb_weekly}
    ozon_week_map = {w['week_start']: w for w in ozon_weekly}
    all_week_starts = sorted(set(list(wb_week_map.keys()) + list(ozon_week_map.keys())))

    combined_weeks = []
    for ws in all_week_starts:
        ww = wb_week_map.get(ws, {})
        ow = ozon_week_map.get(ws, {})
        cw = {
            'week_start': ws,
            'week_end': ww.get('week_end', ow.get('week_end', ws)),
            'days': max(ww.get('days', 0), ow.get('days', 0)),
            'margin': ww.get('margin', 0) + ow.get('margin', 0),
            'revenue': ww.get('revenue_before_spp', 0) + ow.get('revenue_before_spp', 0),
            'sales': ww.get('sales_count', 0) + ow.get('sales_count', 0),
            'adv': ww.get('adv_total', 0) + ow.get('adv_total', 0),
        }
        cw['margin_pct'] = (cw['margin'] / cw['revenue'] * 100) if cw['revenue'] > 0 else 0
        cw['drr'] = (cw['adv'] / cw['revenue'] * 100) if cw['revenue'] > 0 else 0
        cw['margin_daily'] = cw['margin'] / cw['days'] if cw['days'] > 0 else 0
        combined_weeks.append(cw)

    if combined_weeks:
        L(f"| Неделя | Период | Дни | Маржа | Маржа/день | Маржин. | ДРР | Тренд |")
        L(f"|--------|--------|-----|-------|------------|---------|-----|-------|")
        prev_margin = None
        for i, cw in enumerate(combined_weeks, 1):
            ws_str = cw['week_start'].strftime('%d.%m') if hasattr(cw['week_start'], 'strftime') else str(cw['week_start'])
            we_str = cw['week_end'].strftime('%d.%m') if hasattr(cw['week_end'], 'strftime') else str(cw['week_end'])
            trend = "—"
            if prev_margin is not None and prev_margin != 0:
                ch = calc_change(cw['margin_daily'], prev_margin)
                trend = f"{get_arrow(ch)} {ch:+.1f}%"
            L(f"| W{i} | {ws_str}–{we_str} | {cw['days']} | {format_num(cw['margin'])} руб | {format_num(cw['margin_daily'])} руб | {format_pct(cw['margin_pct'])} | {format_pct(cw['drr'])} | {trend} |")
            prev_margin = cw['margin_daily']
        L("")

        # Лучшая/худшая неделя
        best_week = max(combined_weeks, key=lambda w: w['margin_daily'])
        worst_week = min(combined_weeks, key=lambda w: w['margin_daily'])
        best_i = combined_weeks.index(best_week) + 1
        worst_i = combined_weeks.index(worst_week) + 1
        L(f"**Лучшая неделя:** W{best_i} ({format_num(best_week['margin_daily'])} руб/день, маржин. {format_pct(best_week['margin_pct'])})")
        L(f"**Худшая неделя:** W{worst_i} ({format_num(worst_week['margin_daily'])} руб/день, маржин. {format_pct(worst_week['margin_pct'])})")
        L("")

    L("---")
    L("")

    # =========================================================================
    # ДЕКОМПОЗИЦИЯ ПО 5 РЫЧАГАМ
    # =========================================================================
    h1 = next((h for h in hypotheses if h['id'] == 'H1'), None)
    if h1 and h1.get('levers'):
        L("## Декомпозиция маржи по 5 рычагам")
        L("")
        L(f"Маржинальная прибыль {'выросла' if margin_change > 0 else 'снизилась'} на {abs(margin_change):.1f}% → анализ по рычагам:")
        L("")
        L(f"| # | Рычаг | {t_name} | {c_name} | Изменение | Статус |")
        L(f"|---|-------|{'---'*5}|{'---'*5}|-----------|--------|")
        for i, (name, change_val, cur_val, prev_val) in enumerate(h1['levers'], 1):
            if name in ('СПП %', 'ДРР', 'Выкуп %'):
                cur_s = format_pct(cur_val)
                prev_s = format_pct(prev_val)
                change_s = f"{change_val:+.1f} п.п."
            else:
                cur_s = format_num(cur_val) + " руб"
                prev_s = format_num(prev_val) + " руб"
                change_s = f"{change_val:+.1f}%"
            status = "!!!" if abs(change_val) > 5 else ("!" if abs(change_val) > 2 else "OK")
            L(f"| {i} | **{name}** | {cur_s} | {prev_s} | {change_s} | {status} |")

        L(f"| + | Себестоимость/ед | {format_num(h1['sebes_cur'])} руб | {format_num(h1['sebes_prev'])} руб | {h1['sebes_change']:+.1f}% | {'!' if abs(h1['sebes_change']) > 3 else 'OK'} |")
        L("")
        L("---")
        L("")

    # =========================================================================
    # ТРАФИК И РЕКЛАМА
    # =========================================================================
    L("## Трафик и реклама")
    L("")

    # WB Воронка
    if wb_content:
        wb_c_c = [r for r in wb_content if r[0] == 'current']
        wb_c_p = [r for r in wb_content if r[0] == 'previous']
        if wb_c_c and wb_c_p:
            cc, cp = wb_c_c[0], wb_c_p[0]
            opens_c, cart_c, orders_c, buyouts_c = to_float(cc[1]), to_float(cc[2]), to_float(cc[3]), to_float(cc[4])
            opens_p, cart_p, orders_p, buyouts_p = to_float(cp[1]), to_float(cp[2]), to_float(cp[3]), to_float(cp[4])

            cr_cart_c = (cart_c / opens_c * 100) if opens_c > 0 else 0
            cr_cart_p = (cart_p / opens_p * 100) if opens_p > 0 else 0
            cr_order_c = (orders_c / opens_c * 100) if opens_c > 0 else 0
            cr_order_p = (orders_p / opens_p * 100) if opens_p > 0 else 0
            buyout_pct_c = (buyouts_c / orders_c * 100) if orders_c > 0 else 0
            buyout_pct_p = (buyouts_p / orders_p * 100) if orders_p > 0 else 0

            L("### WB Воронка")
            L("")
            L(f"| Этап | {t_name} | {c_name} | Изменение | CR |")
            L(f"|------|{'---'*5}|{'---'*5}|-----------|-----|")
            L(f"| Просмотры карточек | {format_num(opens_c)} | {format_num(opens_p)} | {calc_change(opens_c, opens_p):+.1f}% | — |")
            L(f"| Корзина | {format_num(cart_c)} | {format_num(cart_p)} | {calc_change(cart_c, cart_p):+.1f}% | {format_pct(cr_cart_c)} ({calc_change_pp(cr_cart_c, cr_cart_p):+.1f} п.п.) |")
            L(f"| Заказы | {format_num(orders_c)} | {format_num(orders_p)} | {calc_change(orders_c, orders_p):+.1f}% | {format_pct(cr_order_c)} ({calc_change_pp(cr_order_c, cr_order_p):+.1f} п.п.) |")
            L(f"| Выкупы | {format_num(buyouts_c)} | {format_num(buyouts_p)} | {calc_change(buyouts_c, buyouts_p):+.1f}% | Выкуп {format_pct(buyout_pct_c)} ({calc_change_pp(buyout_pct_c, buyout_pct_p):+.1f} п.п.) |")
            L("")

    # WB Реклама
    if wb_adv:
        wb_a_c = [r for r in wb_adv if r[0] == 'current']
        wb_a_p = [r for r in wb_adv if r[0] == 'previous']
        if wb_a_c and wb_a_p:
            ac, ap = wb_a_c[0], wb_a_p[0]
            views_c, clicks_c, spend_c = to_float(ac[1]), to_float(ac[2]), to_float(ac[5])
            views_p, clicks_p, spend_p = to_float(ap[1]), to_float(ap[2]), to_float(ap[5])
            ctr_c, cpc_c = to_float(ac[6]), to_float(ac[7])
            ctr_p, cpc_p = to_float(ap[6]), to_float(ap[7])
            ad_orders_c = to_float(ac[4]) if len(ac) > 4 else 0
            ad_orders_p = to_float(ap[4]) if len(ap) > 4 else 0
            cpo_c = spend_c / ad_orders_c if ad_orders_c > 0 else 0
            cpo_p = spend_p / ad_orders_p if ad_orders_p > 0 else 0

            L("### WB Реклама")
            L("")
            L(f"| Метрика | {t_name} | {c_name} | Изменение |")
            L(f"|---------|{'---'*5}|{'---'*5}|-----------|")
            L(f"| Показы | {format_num(views_c)} | {format_num(views_p)} | {calc_change(views_c, views_p):+.1f}% |")
            L(f"| Клики | {format_num(clicks_c)} | {format_num(clicks_p)} | {calc_change(clicks_c, clicks_p):+.1f}% |")
            L(f"| Расход | {format_num(spend_c)} руб | {format_num(spend_p)} руб | {calc_change(spend_c, spend_p):+.1f}% |")
            L(f"| CTR | {format_pct(ctr_c)} | {format_pct(ctr_p)} | {calc_change_pp(ctr_c, ctr_p):+.2f} п.п. |")
            L(f"| CPC | {format_num(cpc_c, 1)} руб | {format_num(cpc_p, 1)} руб | {calc_change(cpc_c, cpc_p):+.1f}% |")
            if cpo_c > 0:
                L(f"| CPO | {format_num(cpo_c, 0)} руб | {format_num(cpo_p, 0)} руб | {calc_change(cpo_c, cpo_p):+.1f}% |")
            L("")

    # OZON Реклама
    if ozon_traffic:
        oz_c = [r for r in ozon_traffic if r[0] == 'current']
        oz_p = [r for r in ozon_traffic if r[0] == 'previous']
        if oz_c and oz_p:
            oc, op = oz_c[0], oz_p[0]
            oz_views_c, oz_clicks_c = to_float(oc[1]), to_float(oc[2])
            oz_views_p, oz_clicks_p = to_float(op[1]), to_float(op[2])
            oz_spend_c = to_float(oc[4])
            oz_spend_p = to_float(op[4])
            oz_ctr_c, oz_cpc_c = to_float(oc[5]), to_float(oc[6])
            oz_ctr_p, oz_cpc_p = to_float(op[5]), to_float(op[6])

            L("### OZON Реклама")
            L("")
            L(f"| Метрика | {t_name} | {c_name} | Изменение |")
            L(f"|---------|{'---'*5}|{'---'*5}|-----------|")
            L(f"| Показы | {format_num(oz_views_c)} | {format_num(oz_views_p)} | {calc_change(oz_views_c, oz_views_p):+.1f}% |")
            L(f"| Клики | {format_num(oz_clicks_c)} | {format_num(oz_clicks_p)} | {calc_change(oz_clicks_c, oz_clicks_p):+.1f}% |")
            L(f"| Расход | {format_num(oz_spend_c)} руб | {format_num(oz_spend_p)} руб | {calc_change(oz_spend_c, oz_spend_p):+.1f}% |")
            L(f"| CTR | {format_pct(oz_ctr_c)} | {format_pct(oz_ctr_p)} | {calc_change_pp(oz_ctr_c, oz_ctr_p):+.2f} п.п. |")
            L(f"| CPC | {format_num(oz_cpc_c, 1)} руб | {format_num(oz_cpc_p, 1)} руб | {calc_change(oz_cpc_c, oz_cpc_p):+.1f}% |")
            L("")

    L("---")
    L("")

    # =========================================================================
    # ГИПОТЕЗЫ
    # =========================================================================
    if hypotheses:
        L("## Гипотезы и сценарии")
        L("")
        for h in sorted(hypotheses, key=lambda x: x['confidence'], reverse=True):
            L(f"### {h['id']}: {h['statement']}")
            L("")
            L(f"- **Confidence:** {h['confidence']:.2f} ({confidence_label(h['confidence'])})")
            L(f"- **Источники:** {', '.join(h['sources'])}")
            L(f"- **Триангуляция:** {h['triangulation']}/{h['triangulation_total']} источников подтверждают")
            if h.get('what_if'):
                L(f"- **Что если:** {h['what_if']}")
            if h.get('counter_arguments'):
                L(f"- **Red Team:**")
                for ca in h['counter_arguments']:
                    L(f"  - {ca}")
            L("")

        L("---")
        L("")

    # =========================================================================
    # VS БИЗНЕС-ЦЕЛЕЙ
    # =========================================================================
    L("## Сравнение с бизнес-ориентирами")
    L("")
    L(f"| Ориентир | Порог | Факт | Статус | Разрыв |")
    L(f"|----------|-------|------|--------|--------|")
    L(f"| Маржа (мин) | {format_num(TARGETS['margin_monthly_min'])} руб | {format_num(tc['margin'])} руб | {flag_emoji['GREEN' if tc['margin'] >= TARGETS['margin_monthly_min'] else 'RED']} | {format_num(tc['margin'] - TARGETS['margin_monthly_min'])} руб |")
    L(f"| Маржа (цель) | {format_num(TARGETS['margin_monthly_mid'])} руб | {format_num(tc['margin'])} руб | {flag_emoji['GREEN' if tc['margin'] >= TARGETS['margin_monthly_mid'] else 'RED']} | {format_num(tc['margin'] - TARGETS['margin_monthly_mid'])} руб |")
    L(f"| Маржинальность (мин) | {format_pct(TARGETS['margin_pct_min'])} | {format_pct(tc['margin_pct'])} | {flag_emoji['GREEN' if tc['margin_pct'] >= TARGETS['margin_pct_min'] else 'RED']} | {calc_change_pp(tc['margin_pct'], TARGETS['margin_pct_min']):+.1f} п.п. |")
    L(f"| Маржинальность (цель) | {format_pct(TARGETS['margin_pct_mid'])} | {format_pct(tc['margin_pct'])} | {flag_emoji['GREEN' if tc['margin_pct'] >= TARGETS['margin_pct_mid'] else 'RED']} | {calc_change_pp(tc['margin_pct'], TARGETS['margin_pct_mid']):+.1f} п.п. |")
    L(f"| ДРР (лимит) | < {format_pct(TARGETS['drr_warning'])} | {format_pct(tc['drr'])} | {flag_emoji['GREEN' if tc['drr'] < TARGETS['drr_warning'] else 'RED']} | {format_pct(TARGETS['drr_warning'] - tc['drr'])} запас |")
    L("")

    L("---")
    L("")

    # =========================================================================
    # РЕКОМЕНДАЦИИ
    # =========================================================================
    L("## Рекомендации")
    L("")

    recommendations = []

    if tc['margin'] < TARGETS['margin_monthly_min']:
        gap = TARGETS['margin_monthly_min'] - tc['margin']
        recommendations.append({
            'priority': 1,
            'title': 'Маржа ниже минимального ориентира',
            'problem': f"Маржа {format_num(tc['margin'])} руб — ниже ориентира {format_num(TARGETS['margin_monthly_min'])} руб на {format_num(gap)} руб",
            'action': "Комбинация: оптимизация рекламы + повышение цен на 3-5% + снижение логистики",
            'what_if': f"Если поднять маржинальность на 2 п.п. → +{format_num(tc['revenue_before_spp'] * 0.02)} руб/мес маржи",
        })

    if tc['drr'] > TARGETS['drr_warning']:
        recommendations.append({
            'priority': 1,
            'title': f"ДРР выше лимита ({format_pct(tc['drr'])})",
            'problem': f"Рекламные расходы {format_num(tc['adv_total'])} руб — ДРР {format_pct(tc['drr'])} > {format_pct(TARGETS['drr_warning'])}",
            'action': "Снизить ставки на неэффективных РК на 20-30%",
            'what_if': f"Экономия ~{format_num(tc['adv_total'] * 0.2)} руб/мес",
        })

    if tc['margin_pct'] < TARGETS['margin_pct_min']:
        recommendations.append({
            'priority': 1,
            'title': f"Маржинальность ниже минимума ({format_pct(tc['margin_pct'])})",
            'problem': f"Маржинальность {format_pct(tc['margin_pct'])} < {format_pct(TARGETS['margin_pct_min'])}",
            'action': "Поднять цены на 5-10% для моделей с высоким спросом",
            'what_if': f"Повышение цен на 5% → потенциально +{format_num(tc['revenue_before_spp'] * 0.05)} руб выручки/мес",
        })

    if adv_change > 30:
        recommendations.append({
            'priority': 2,
            'title': f"Реклама выросла на {format_pct(adv_change)}",
            'problem': f"Расходы на рекламу выросли с {format_num(tp['adv_total'])} до {format_num(tc['adv_total'])} руб",
            'action': "Аудит эффективности рекламных кампаний, отключить нерентабельные",
            'what_if': f"Сокращение на 15% → экономия {format_num(tc['adv_total'] * 0.15)} руб/мес",
        })

    if ozon_margin_change < -20:
        recommendations.append({
            'priority': 2,
            'title': f"OZON маржа упала на {format_pct(abs(ozon_margin_change))}",
            'problem': f"Маржа OZON снизилась с {format_num(ozon['previous']['margin'])} до {format_num(ozon['current']['margin'])} руб",
            'action': "Проверить ценообразование и комиссии OZON, оптимизировать ассортимент",
            'what_if': f"Восстановление до уровня {c_name} → +{format_num(abs(ozon['previous']['margin'] - ozon['current']['margin']))} руб/мес",
        })

    if wb_margin_change < -5:
        recommendations.append({
            'priority': 2,
            'title': f"WB маржа снизилась на {format_pct(abs(wb_margin_change))}",
            'problem': f"Маржа WB снизилась с {format_num(wb['previous']['margin'])} до {format_num(wb['current']['margin'])} руб",
            'action': "Проанализировать структуру продаж: какие модели просели",
            'what_if': f"Восстановление до уровня {c_name} → +{format_num(abs(wb['previous']['margin'] - wb['current']['margin']))} руб/мес",
        })

    # Модели-чемпионы без рекламы
    for model, margin, revenue, adv in wb_models_sorted[:10]:
        m_pct = (margin / revenue * 100) if revenue > 0 else 0
        drr = (adv / revenue * 100) if revenue > 0 else 0
        if m_pct > 25 and drr < 1 and margin > 30000:
            recommendations.append({
                'priority': 3,
                'title': f"Масштабировать модель {model}",
                'problem': f"Модель {model}: маржинальность {format_pct(m_pct)}, ДРР {format_pct(drr)} — нет рекламы",
                'action': f"Запустить рекламу для {model} с бюджетом 3-5% от выручки",
                'what_if': f"Потенциальный рост продаж на 20-30% → +{format_num(margin * 0.25)} руб/мес маржи",
            })

    if not recommendations:
        L("Критических отклонений не выявлено. Продолжать текущую стратегию.")
        L("")
    else:
        recommendations.sort(key=lambda x: x['priority'])
        for i, rec in enumerate(recommendations, 1):
            p_label = {1: 'P1 (критично)', 2: 'P2 (важно)', 3: 'P3 (возможность)'}
            L(f"### {i}. {rec['title']}")
            L(f"- **Приоритет:** {p_label.get(rec['priority'], 'P3')}")
            L(f"- **Проблема:** {rec['problem']}")
            L(f"- **Действие:** {rec['action']}")
            L(f"- **Что если:** {rec['what_if']}")
            L("")

    # Требует внимания
    low_conf = [h for h in hypotheses if h['confidence'] < CONFIDENCE_THRESHOLD]
    if low_conf:
        L("---")
        L("")
        L("## Требует внимания (confidence < 0.6)")
        L("")
        for h in low_conf:
            L(f"- **{h['id']}** ({h['confidence']:.2f}): {h['statement'][:120]}")
            if h.get('counter_arguments'):
                for ca in h['counter_arguments']:
                    L(f"  - Red Team: {ca}")
        L("")

    L("---")
    L("")

    # Формулы
    L("## Формулы маржи (верифицированные)")
    L("")
    L("### WB:")
    L("```")
    L("Маржа = revenue_spp - comis_spp - logist - sebes - reclama - reclama_vn - storage - nds - penalty - retention - deduction")
    L("```")
    L("")
    L("### OZON:")
    L("```")
    L("Маржа = marga - nds")
    L("```")
    L("")
    L("---")
    L(f"*Отчёт сгенерирован: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")

    return '\n'.join(lines)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Месячный аналитический отчёт')
    parser.add_argument('--month', required=True, help='Целевой месяц (YYYY-MM)')
    parser.add_argument('--compare', default=None, help='Месяц сравнения (YYYY-MM), по умолчанию — предыдущий')
    parser.add_argument('--save', action='store_true', help='Сохранить в reports/')
    parser.add_argument('--notion', action='store_true', help='Синхронизировать с Notion')
    parser.add_argument('--export-context', action='store_true',
                        help='Экспортировать data_context.json для LLM-анализа (Рома)')
    args = parser.parse_args()

    # Парсинг дат
    t_year, t_month = map(int, args.month.split('-'))
    current_start = f"{t_year}-{t_month:02d}-01"
    if t_month == 12:
        current_end = f"{t_year + 1}-01-01"
    else:
        current_end = f"{t_year}-{t_month + 1:02d}-01"

    if args.compare:
        c_year, c_month = map(int, args.compare.split('-'))
    else:
        c_month = t_month - 1
        c_year = t_year
        if c_month < 1:
            c_month = 12
            c_year -= 1

    prev_start = f"{c_year}-{c_month:02d}-01"
    compare_month = f"{c_year}-{c_month:02d}"

    t_name = MONTH_NAMES_RU[t_month]
    c_name = MONTH_NAMES_RU[c_month]
    print(f"[Monthly] {t_name} {t_year} vs {c_name} {c_year}")

    # Загрузка данных
    print("[Monthly] Загрузка финансов...")
    wb_data, wb_orders = get_wb_finance(current_start, prev_start, current_end)
    ozon_data, ozon_orders = get_ozon_finance(current_start, prev_start, current_end)

    print("[Monthly] Загрузка моделей...")
    wb_models_raw = get_wb_by_model(current_start, prev_start, current_end)
    ozon_models_raw = get_ozon_by_model(current_start, prev_start, current_end)

    print("[Monthly] Загрузка трафика...")
    wb_content, wb_adv = get_wb_traffic(current_start, prev_start, current_end)
    ozon_traffic = get_ozon_traffic(current_start, prev_start, current_end)

    print("[Monthly] Загрузка статусов...")
    artikuly_statuses = get_artikuly_statuses()

    print("[Monthly] Загрузка понедельной динамики...")
    wb_weekly = get_wb_weekly_breakdown(current_start, current_end)
    ozon_weekly = get_ozon_weekly_breakdown(current_start, current_end)

    print("[Monthly] Загрузка дневных серий для confidence...")
    wb_daily = get_wb_daily_series_range(current_start, current_end)
    ozon_daily = get_ozon_daily_series_range(current_start, current_end)

    # Парсинг WB
    wb = {'current': {}, 'previous': {}}
    for row in wb_data:
        period = row[0]
        wb[period] = {
            'orders_count': to_float(row[1]), 'sales_count': to_float(row[2]),
            'revenue_before_spp': to_float(row[3]), 'revenue_after_spp': to_float(row[4]),
            'adv_internal': to_float(row[5]), 'adv_external': to_float(row[6]),
            'cost_of_goods': to_float(row[7]), 'logistics': to_float(row[8]),
            'storage': to_float(row[9]), 'commission': to_float(row[10]),
            'spp_amount': to_float(row[11]), 'nds': to_float(row[12]),
            'penalty': to_float(row[13]), 'retention': to_float(row[14]),
            'deduction': to_float(row[15]), 'margin': to_float(row[16]),
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
            'revenue_before_spp': to_float(row[2]), 'revenue_after_spp': to_float(row[3]),
            'adv_internal': to_float(row[4]), 'adv_external': to_float(row[5]),
            'margin': to_float(row[6]), 'cost_of_goods': to_float(row[7]),
            'logistics': to_float(row[8]), 'storage': to_float(row[9]),
            'commission': to_float(row[10]), 'spp_amount': to_float(row[11]),
            'nds': to_float(row[12]),
        }
    for row in ozon_orders:
        period = row[0]
        if period in ozon:
            ozon[period]['orders_count'] = to_float(row[1])
            ozon[period]['orders_rub'] = to_float(row[2])

    # Производные метрики
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
        # СПП: средневзвешенный по каналам (сумма скидок / сумма выручки до СПП)
        total_spp_amount = w.get('spp_amount', 0) + o.get('spp_amount', 0)
        t['spp_pct'] = (total_spp_amount / t['revenue_before_spp'] * 100) if t['revenue_before_spp'] > 0 else 0

    # Модели
    # WB модели — имена уже lowercase в БД
    wb_models_c = [(row[1], to_float(row[5]), to_float(row[3]), to_float(row[4])) for row in wb_models_raw if row[0] == 'current']
    wb_models_p = {row[1]: to_float(row[5]) for row in wb_models_raw if row[0] == 'previous'}
    wb_models_c.sort(key=lambda x: x[1], reverse=True)

    # OZON модели — нормализуем имена к lowercase для корректного объединения с WB
    # OZON хранит модели в Capitalized ("Wendy"), WB — в lowercase ("wendy")
    # Для OZON ТОП-10 сохраняем оригинальные имена для отображения
    ozon_models_c_raw = [(row[1], to_float(row[5]), to_float(row[3]), to_float(row[4])) for row in ozon_models_raw if row[0] == 'current']
    ozon_models_p_raw = [(row[1], to_float(row[5])) for row in ozon_models_raw if row[0] == 'previous']

    # Агрегируем OZON модели по lowercase (на случай дублей типа "Ruby" / "ruby")
    _ozon_c_agg = {}
    for name, margin, revenue, adv in ozon_models_c_raw:
        key = name.lower() if name else name
        if key not in _ozon_c_agg:
            _ozon_c_agg[key] = {'margin': 0, 'revenue': 0, 'adv': 0, 'display_name': name}
        _ozon_c_agg[key]['margin'] += margin
        _ozon_c_agg[key]['revenue'] += revenue
        _ozon_c_agg[key]['adv'] += adv

    ozon_models_c = [(v['display_name'], v['margin'], v['revenue'], v['adv']) for v in _ozon_c_agg.values()]
    ozon_models_c.sort(key=lambda x: x[1], reverse=True)

    _ozon_p_agg = {}
    for name, margin in ozon_models_p_raw:
        key = name.lower() if name else name
        _ozon_p_agg[key] = _ozon_p_agg.get(key, 0) + margin
    ozon_models_p = _ozon_p_agg  # ключи в lowercase

    # Генерация гипотез
    print("[Monthly] Генерация гипотез...")
    hypotheses = generate_monthly_hypotheses(
        wb, ozon, total, wb_daily, ozon_daily,
        wb_models_c, wb_models_p, ozon_models_c, ozon_models_p,
        wb_adv, ozon_traffic,
    )

    # Red Team
    print("[Monthly] Red Team анализ...")
    tc = total['current']
    ozon_share = ozon['current'].get('revenue_before_spp', 0) / tc['revenue_before_spp'] if tc['revenue_before_spp'] > 0 else 0
    wb_spp_pp = calc_change_pp(wb['current'].get('spp_pct', 0), wb['previous'].get('spp_pct', 0))
    is_post_holiday = (t_month == 1 and c_month == 12) or (t_month == 2 and c_month == 1)

    for h in hypotheses:
        data_ctx = {
            'ozon_share': ozon_share,
            'spp_change_pp': wb_spp_pp,
            'is_post_holiday': is_post_holiday,
        }
        penalty, triggered = monthly_red_team_checks(h, data_ctx)
        if triggered:
            h['counter_arguments'] = triggered
            h['confidence'] = round(max(0.10, h['confidence'] - penalty), 2)

    # Рендер
    print("[Monthly] Генерация отчёта...")
    report_md = render_monthly_report(
        args.month, compare_month, wb, ozon, total,
        wb_weekly, ozon_weekly,
        wb_models_c, wb_models_p, ozon_models_c, ozon_models_p,
        artikuly_statuses,
        wb_content, wb_adv, ozon_traffic,
        hypotheses, wb_daily, ozon_daily,
    )

    print(report_md)

    # Сохранение
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    reports_dir = os.path.join(project_root, 'reports')

    if args.save:
        os.makedirs(reports_dir, exist_ok=True)
        report_path = os.path.join(reports_dir, f"{args.month}_monthly_analytics.md")
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_md)
        print(f"\n[Monthly] Отчёт сохранён: {report_path}")

    # --- Export data context for Рома (LLM analysis) ---
    if args.export_context and args.save:
        import json
        from scripts.analytics_agent_roma.context_builder import prepare_monthly_context

        ctx = prepare_monthly_context(
            target_month=args.month,
            compare_month=compare_month,
            wb=wb, ozon=ozon, total=total,
            wb_models_c=wb_models_c, wb_models_p=wb_models_p,
            ozon_models_c=ozon_models_c, ozon_models_p=ozon_models_p,
            wb_weekly=wb_weekly, ozon_weekly=ozon_weekly,
            wb_daily=wb_daily, ozon_daily=ozon_daily,
            wb_adv_data=wb_adv, ozon_traffic_data=ozon_traffic,
        )
        ctx_path = os.path.join(reports_dir, f"{args.month}_data_context.json")
        with open(ctx_path, 'w', encoding='utf-8') as f:
            json.dump(ctx, f, ensure_ascii=False, indent=2)
        print(f"[Monthly] Контекст для Ромы сохранён: {ctx_path}")

    # --- Notion sync (skip when export-context: Рома сделает после анализа) ---
    if args.notion and not args.export_context:
        try:
            from scripts.notion_sync import sync_report_to_notion
            last_day = monthrange(t_year, t_month)[1]
            month_end_str = f"{t_year}-{t_month:02d}-{last_day:02d}"
            url = sync_report_to_notion(current_start, month_end_str, report_md)
            print(f"[Monthly] Отчёт в Notion: {url}")
        except Exception as e:
            print(f"[Monthly] Ошибка Notion: {e}")
    elif args.notion and args.export_context:
        print(f"[Monthly] Notion sync пропущен: Рома допишет анализ, затем sync")

    print(f"\n[Monthly] Гипотез: {len(hypotheses)}, из них требуют внимания: {len([h for h in hypotheses if h['confidence'] < CONFIDENCE_THRESHOLD])}")


if __name__ == "__main__":
    main()
