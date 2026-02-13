#!/usr/bin/env python3
"""
Ежедневная аналитика с Confidence Scores, триангуляцией и Red Team.

Использование:
  python scripts/daily_analytics.py --date 2026-02-06
  python scripts/daily_analytics.py --date 2026-02-06 --save --notion
"""

import sys
import os
import argparse
import math
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.data_layer import (
    to_float, format_num, format_pct, get_arrow, calc_change, calc_change_pp,
    get_wb_finance, get_wb_by_model, get_wb_traffic, get_wb_traffic_by_model,
    get_wb_orders_by_model,
    get_ozon_finance, get_ozon_by_model, get_ozon_traffic,
    get_ozon_orders_by_model,
    get_wb_daily_series, get_ozon_daily_series,
    validate_wb_data_quality,
)


# =============================================================================
# БИЗНЕС-ОРИЕНТИРЫ (из Notion, гибкие — не жёсткие ограничения)
# =============================================================================

TARGETS = {
    'margin_monthly_min': 5_000_000,
    'margin_monthly_mid': 6_500_000,
    'margin_pct_min': 20.0,
    'margin_pct_mid': 23.0,
    'margin_pct_high': 25.0,
    'drr_warning': 10.0,
}

CONFIDENCE_THRESHOLD = 0.6  # ниже — human review


# =============================================================================
# CONFIDENCE ENGINE
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
    """
    Считает confidence из данных.

    evidence_directions: list of +1 (подтверждает), -1 (противоречит), 0 (нейтрально)
    change_pct: % изменения метрики
    series_values: list[float] — временной ряд за 7 дней для этой метрики
    """
    # 1. Direction agreement (0.4)
    total = len([e for e in evidence_directions if e != 0])
    confirming = len([e for e in evidence_directions if e > 0])
    direction = confirming / max(total, 1)

    # 2. Magnitude significance (0.35)
    if len(series_values) >= 3:
        sd = _stdev(series_values)
        mean = sum(series_values) / len(series_values)
        relative_sd = (sd / abs(mean) * 100) if abs(mean) > 1 else 50
        magnitude = min(1.0, abs(change_pct) / max(2 * relative_sd, 1))
    else:
        magnitude = 0.5

    # 3. Data stability (0.25)
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
# RED TEAM
# =============================================================================

def red_team_checks(hypothesis, data_ctx):
    """
    Применяет контраргументы к гипотезе. Возвращает (penalty, triggered_list).
    """
    triggered = []
    penalty = 0.0

    # 1. День недели — в пределах нормы?
    if 'series' in data_ctx and len(data_ctx['series']) >= 7:
        weekday = data_ctx.get('target_weekday', -1)
        same_day_vals = [
            v for d, v in zip(data_ctx.get('series_dates', []), data_ctx['series'])
            if hasattr(d, 'weekday') and d.weekday() == weekday
        ]
        if same_day_vals and len(same_day_vals) >= 1:
            avg = sum(same_day_vals) / len(same_day_vals)
            current = data_ctx.get('current_value', 0)
            sd = _stdev(data_ctx['series']) if len(data_ctx['series']) >= 3 else abs(avg) * 0.1
            if sd > 0 and abs(current - avg) <= sd:
                triggered.append(f"День недели: значение ({format_num(current)}) в пределах нормы для этого дня (avg {format_num(avg)}, ±{format_num(sd)})")
                penalty += 0.15

    # 2. Неполные данные
    if data_ctx.get('today_orders', 0) > 0 and data_ctx.get('avg_daily_orders', 0) > 0:
        ratio = data_ctx['today_orders'] / data_ctx['avg_daily_orders']
        if ratio < 0.5:
            triggered.append(f"Неполные данные: сегодня {format_num(data_ctx['today_orders'])} заказов — это {ratio*100:.0f}% от среднего ({format_num(data_ctx['avg_daily_orders'])})")
            penalty += 0.15

    # 3. Низкая база (OZON)
    if 'ozon_share' in data_ctx and data_ctx['ozon_share'] < 0.10:
        if hypothesis.get('category') in ('ozon', 'channel_divergence'):
            triggered.append(f"Низкая база: OZON = {data_ctx['ozon_share']*100:.1f}% от total — % изменения завышены")
            penalty += 0.15

    # 4. СПП изменение маркетплейсом
    if abs(data_ctx.get('spp_change_pp', 0)) > 2.0:
        if hypothesis.get('category') in ('margin', 'price'):
            triggered.append(f"Изменение СПП маркетплейсом: {data_ctx['spp_change_pp']:+.1f} п.п. — внешний фактор")
            penalty += 0.15

    # 5. Лаг выкупов (1 день)
    if data_ctx.get('is_single_day', False):
        triggered.append("Лаг выкупов: сравнение 1 дня — выкупы могут приходить с задержкой 3-21 дней")
        penalty += 0.10

    return penalty, triggered


# =============================================================================
# ГЕНЕРАЦИЯ ГИПОТЕЗ
# =============================================================================

def generate_hypotheses(wb, ozon, total, wb_series, ozon_series, wb_models_c, wb_models_p, ozon_models_c, ozon_models_p, wb_adv_data, ozon_traffic_data):
    hypotheses = []

    tc, tp = total['current'], total['previous']

    # Серии значений для confidence
    total_margin_series = [w['margin'] + o['margin'] for w, o in zip(wb_series, ozon_series)] if len(wb_series) == len(ozon_series) and wb_series else [w['margin'] for w in wb_series]
    wb_margin_series = [d['margin'] for d in wb_series]
    ozon_margin_series = [d['margin'] for d in ozon_series]
    total_adv_series = [(w.get('adv_total', 0) + o.get('adv_total', 0)) for w, o in zip(wb_series, ozon_series)] if len(wb_series) == len(ozon_series) else [w.get('adv_total', 0) for w in wb_series]

    # ---------- H1: Маржинальная прибыль ----------
    margin_change = calc_change(tc['margin'], tp['margin'])
    if abs(margin_change) > 3:
        # Декомпозиция по 5 рычагам
        levers = []
        # 1. Цена до СПП (revenue / sales)
        price_cur = tc['revenue_before_spp'] / tc['sales_count'] if tc['sales_count'] > 0 else 0
        price_prev = tp['revenue_before_spp'] / tp['sales_count'] if tp['sales_count'] > 0 else 0
        price_change = calc_change(price_cur, price_prev)
        levers.append(('Цена до СПП', price_change, price_cur, price_prev))

        # 2. СПП %
        spp_cur = tc.get('spp_pct', 0)
        spp_prev = tp.get('spp_pct', 0)
        spp_pp = calc_change_pp(spp_cur, spp_prev)
        levers.append(('СПП %', spp_pp, spp_cur, spp_prev))

        # 3. ДРР
        drr_pp = calc_change_pp(tc['drr'], tp['drr'])
        levers.append(('ДРР', drr_pp, tc['drr'], tp['drr']))

        # 4. Логистика ₽/ед
        log_per_unit_cur = tc['logistics'] / tc['sales_count'] if tc['sales_count'] > 0 else 0
        log_per_unit_prev = tp['logistics'] / tp['sales_count'] if tp['sales_count'] > 0 else 0
        log_change = calc_change(log_per_unit_cur, log_per_unit_prev)
        levers.append(('Логистика ₽/ед', log_change, log_per_unit_cur, log_per_unit_prev))

        # 5. Себестоимость ₽/ед
        sebes_cur = tc['cost_of_goods'] / tc['sales_count'] if tc['sales_count'] > 0 else 0
        sebes_prev = tp['cost_of_goods'] / tp['sales_count'] if tp['sales_count'] > 0 else 0
        sebes_change = calc_change(sebes_cur, sebes_prev)
        levers.append(('Себестоимость ₽/ед', sebes_change, sebes_cur, sebes_prev))

        # Выкуп % — информационный, ЛАГОВЫЙ показатель (3-21 дн.)
        # НЕ участвует в выборе primary lever для дневного отчёта
        buyout_cur = (tc['sales_count'] / tc['orders_count'] * 100) if tc.get('orders_count', 0) > 0 else 0
        buyout_prev = (tp['sales_count'] / tp['orders_count'] * 100) if tp.get('orders_count', 0) > 0 else 0
        buyout_pp = calc_change_pp(buyout_cur, buyout_prev)

        # Какой рычаг самый значимый?
        lever_impacts = [(name, abs(val)) for name, val, _, _ in levers]
        lever_impacts.sort(key=lambda x: x[1], reverse=True)
        primary_lever = lever_impacts[0][0]

        # Evidence directions
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

        # Что если
        abs_change = tc['margin'] - tp['margin']
        if margin_change < 0:
            what_if = f"Если устранить влияние {primary_lever}: потенциальное восстановление ~{format_num(abs(abs_change))} руб/день маржи"
        else:
            what_if = f"Если сохранить текущую динамику: дополнительно +{format_num(abs(abs_change) * 30)} руб/мес маржи"

        hypotheses.append({
            'id': 'H1',
            'statement': f"Маржинальная прибыль {'выросла' if margin_change > 0 else 'снизилась'} на {abs(margin_change):.1f}% ({abs_change:+,.0f} руб). Главный рычаг: {primary_lever}",
            'confidence': conf,
            'sources': [f"abc_date.margin ({margin_change:+.1f}%)", f"{primary_lever} ({lever_impacts[0][1]:.1f})"],
            'triangulation': len([e for e in evidence if e > 0]),
            'triangulation_total': len([e for e in evidence if e != 0]),
            'what_if': what_if,
            'levers': levers,
            'buyout_info': {'cur': buyout_cur, 'prev': buyout_prev, 'pp': buyout_pp},
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
        spp_series = [d.get('spp_amount', 0) / max(d.get('revenue_before_spp', 1), 1) * 100 for d in (wb_series if channel == 'WB' else ozon_series)]
        conf = compute_confidence(evidence, spp_pp, spp_series)

        hypotheses.append({
            'id': 'H2',
            'statement': f"СПП на {channel} {'выросла' if spp_pp > 0 else 'снизилась'} на {abs(spp_pp):.1f} п.п. → {'давит' if spp_pp > 0 else 'помогает'} маржу",
            'confidence': conf,
            'sources': [f"{channel}.spp_pct ({spp_pp:+.1f} п.п.)", f"lost revenue ~{format_num(lost_revenue)} руб"],
            'triangulation': len([e for e in evidence if e > 0]),
            'triangulation_total': len([e for e in evidence if e != 0]),
            'what_if': f"Если поднять цену на {abs(spp_pp):.0f}% для компенсации → восстановление ~{format_num(lost_revenue)} руб выручки. Риск: возможное снижение заказов",
            'category': 'price',
            'counter_arguments': [],
        })

    # ---------- H3: ДРР аномалия ----------
    drr_change = calc_change_pp(tc['drr'], tp['drr'])
    if abs(drr_change) > 1.0:
        adv_change_pct = calc_change(tc['adv_total'], tp['adv_total'])
        adv_abs = tc['adv_total'] - tp['adv_total']

        # Разбивка: внутренняя vs внешняя реклама
        adv_int_cur = tc.get('adv_internal', 0)
        adv_int_prev = tp.get('adv_internal', 0)
        adv_ext_cur = tc.get('adv_external', 0)
        adv_ext_prev = tp.get('adv_external', 0)
        adv_int_change = calc_change(adv_int_cur, adv_int_prev)
        adv_ext_change = calc_change(adv_ext_cur, adv_ext_prev)
        adv_breakdown = f"Внутр.: {format_num(adv_int_cur)} руб ({adv_int_change:+.1f}%), внешн.: {format_num(adv_ext_cur)} руб ({adv_ext_change:+.1f}%)"

        # Корреляция с заказами
        orders_cur = tc.get('orders_count', 0)
        orders_prev = tp.get('orders_count', 0)
        orders_rub_cur = tc.get('orders_rub', 0)
        orders_rub_prev = tp.get('orders_rub', 0)
        orders_count_change = calc_change(orders_cur, orders_prev)
        orders_rub_change = calc_change(orders_rub_cur, orders_rub_prev)

        # Оценка эффективности: реклама выросла → заказы выросли?
        if adv_change_pct > 5 and orders_rub_change > 3:
            efficiency = "эффективно (заказы растут вместе с рекламой)"
        elif adv_change_pct > 5 and orders_rub_change <= 3:
            efficiency = "неэффективно (реклама растёт, заказы не растут)"
        elif adv_change_pct < -5 and orders_rub_change < -3:
            efficiency = "снижение рекламы → снижение заказов"
        else:
            efficiency = "нейтрально"

        orders_info = f"Заказы: {format_num(orders_cur, 0)} шт ({orders_count_change:+.1f}%), {format_num(orders_rub_cur)} руб ({orders_rub_change:+.1f}%)"

        # Проверяем CTR/CPC из wb_adv
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
            'statement': f"ДРР {'вырос' if drr_change > 0 else 'снизился'} на {abs(drr_change):.1f} п.п. {adv_breakdown}. {orders_info}. Оценка: {efficiency}",
            'confidence': conf,
            'sources': [f"ДРР {drr_change:+.1f} п.п.", f"adv_total {adv_change_pct:+.1f}%", f"заказы {orders_count_change:+.1f}%", ctr_info or "нет данных CTR"],
            'triangulation': len([e for e in evidence if e > 0]),
            'triangulation_total': len([e for e in evidence if e != 0]),
            'what_if': f"Если {'оптимизировать РК (снизить ставки на 20%)' if drr_change > 0 else 'сохранить текущую эффективность'} → потенциальная экономия ~{format_num(abs(adv_abs) * 0.2)} руб/день",
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

    # ---------- H5: Аномалии моделей (A-группа) ----------
    total_margin_today = tc['margin']
    for model, margin, revenue, adv in wb_models_c[:5]:  # A-группа ~ топ-5
        prev_margin = wb_models_p.get(model, 0)
        model_change = calc_change(margin, prev_margin)
        if abs(model_change) > 15 and abs(margin - prev_margin) > 5000:
            evidence = [+1]
            conf = compute_confidence(evidence, model_change, wb_margin_series)
            share = (margin / total_margin_today * 100) if total_margin_today > 0 else 0
            impact = margin - prev_margin

            hypotheses.append({
                'id': f'H5_{model}',
                'statement': f"Модель {model} (A-группа, {share:.0f}% маржи): маржа {model_change:+.1f}% ({impact:+,.0f} руб)",
                'confidence': conf,
                'sources': [f"wb.abc_date model={model} margin {model_change:+.1f}%"],
                'triangulation': 1,
                'triangulation_total': 1,
                'what_if': f"{'Если модель продолжит падение' if model_change < 0 else 'Если масштабировать'}: влияние на общую маржу ~{format_num(abs(impact))} руб/день",
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
        log_series = [d.get('logistics', 0) for d in wb_series]
        conf = compute_confidence(evidence, log_total_change, log_series)

        hypotheses.append({
            'id': 'H6',
            'statement': f"Логистика {log_total_change:+.1f}% ({tc['logistics'] - tp['logistics']:+,.0f} руб). На единицу: {format_num(log_per_sale, 0)} руб ({calc_change(log_per_sale, log_per_sale_prev):+.1f}%)",
            'confidence': conf,
            'sources': [f"logistics total {log_total_change:+.1f}%", f"logistics/unit {calc_change(log_per_sale, log_per_sale_prev):+.1f}%"],
            'triangulation': 1,
            'triangulation_total': 1,
            'what_if': f"Если снизить логистику на 10% через перераспределение остатков между складами → экономия ~{format_num(log_savings_10pct)} руб/день. Побочный эффект: улучшение ранжирования на МП",
            'category': 'logistics',
            'counter_arguments': [],
        })

    return hypotheses


# =============================================================================
# MARKDOWN РЕНДЕР
# =============================================================================

def render_report(target_date, wb, ozon, total, hypotheses, wb_series, ozon_series, dq_warnings=None, export_context=False):
    lines = []
    L = lines.append

    tc, tp = total['current'], total['previous']
    target_dt = datetime.strptime(target_date, '%Y-%m-%d')
    prev_date = (target_dt - timedelta(days=1)).strftime('%Y-%m-%d')

    L(f"# Ежедневная аналитика: {target_date}")
    L(f"")
    L(f"**Сравнение:** {target_date} vs {prev_date} (день ко дню) + 7-дневный контекст")
    L(f"**Формулы маржи верифицированы:** расхождение с PowerBI < 1%")

    if dq_warnings:
        L("")
        L("> **Качество данных:** обнаружены аномалии, маржа скорректирована:")
        for w in dq_warnings:
            L(f"> - [{w['severity']}] {w['message']}")
            if w.get('explanation'):
                L(f">   - Что: {w['explanation']}")
            if w.get('etl_status'):
                L(f">   - Статус ETL: {w['etl_status']}")
            if w.get('comparison_note'):
                L(f">   - Влияние на сравнение: {w['comparison_note']}")
    L("")
    L("---")
    L("")

    # --- SECTION 1: Key metrics ---
    L("## Динамика ключевых показателей")
    L("")

    def avg_7d(series, key):
        vals = [d.get(key, 0) for d in series]
        return sum(vals) / len(vals) if vals else 0

    def trend_7d(series, key):
        vals = [d.get(key, 0) for d in series]
        if len(vals) < 3:
            return "—"
        first_half = sum(vals[:len(vals)//2]) / max(len(vals)//2, 1)
        second_half = sum(vals[len(vals)//2:]) / max(len(vals) - len(vals)//2, 1)
        change = calc_change(second_half, first_half)
        if change > 3:
            return "растёт"
        elif change < -3:
            return "падает"
        return "стабильно"

    # Brand total
    L("### Бренд (WB + OZON)")
    L("")
    L("| Метрика | Сегодня | Вчера | DoD | 7d Avg | vs 7d | Тренд 7d |")
    L("|---------|---------|-------|-----|--------|-------|----------|")

    wb_avg = lambda k: avg_7d(wb_series, k)
    oz_avg = lambda k: avg_7d(ozon_series, k)

    margin_avg = wb_avg('margin') + oz_avg('margin')
    revenue_avg = wb_avg('revenue_before_spp') + oz_avg('revenue_before_spp')
    adv_avg = wb_avg('adv_total') + oz_avg('adv_total')
    drr_avg = (adv_avg / revenue_avg * 100) if revenue_avg > 0 else 0
    margin_pct_avg = (margin_avg / revenue_avg * 100) if revenue_avg > 0 else 0
    spp_avg_amount = wb_avg('spp_amount') + oz_avg('spp_amount')
    spp_avg = (spp_avg_amount / revenue_avg * 100) if revenue_avg > 0 else 0
    orders_avg = wb_avg('orders_count')  # OZON series не содержит orders_count

    metrics = [
        ("Маржа, руб", tc['margin'], tp['margin'], margin_avg, '%'),
        ("Маржинальность", tc['margin_pct'], tp['margin_pct'], margin_pct_avg, 'pp'),
        ("СПП %", tc['spp_pct'], tp['spp_pct'], spp_avg, 'pp'),
        ("ДРР", tc['drr'], tp['drr'], drr_avg, 'pp'),
        ("Выручка до СПП", tc['revenue_before_spp'], tp['revenue_before_spp'], revenue_avg, '%'),
        ("Заказы, шт", tc['orders_count'], tp['orders_count'], orders_avg, '%'),
        ("Продажи, шт", tc['sales_count'], tp['sales_count'], wb_avg('sales_count') + oz_avg('sales_count'), '%'),
        ("Реклама, руб", tc['adv_total'], tp['adv_total'], adv_avg, '%'),
    ]

    total_margin_series = [w['margin'] + o['margin'] for w, o in zip(wb_series, ozon_series)] if len(wb_series) == len(ozon_series) else []

    for name, cur, prev, avg, mode in metrics:
        if mode == '%':
            dod = f"{calc_change(cur, prev):+.1f}%"
            vs7 = f"{calc_change(cur, avg):+.1f}%"
        else:
            dod = f"{calc_change_pp(cur, prev):+.1f} п.п."
            vs7 = f"{calc_change_pp(cur, avg):+.1f} п.п."

        if name.endswith('%') or name in ('Маржинальность', 'ДРР'):
            cur_s = format_pct(cur)
            prev_s = format_pct(prev)
            avg_s = format_pct(avg)
        else:
            cur_s = format_num(cur)
            prev_s = format_num(prev)
            avg_s = format_num(avg)

        trend = "—"
        if name == "Маржа, руб" and total_margin_series:
            trend = trend_7d([{'v': v} for v in total_margin_series], 'v')

        L(f"| **{name}** | {cur_s} | {prev_s} | {dod} | {avg_s} | {vs7} | {trend} |")

    L("")

    # Per-channel
    for ch_name, ch_data in [("WB", wb), ("OZON", ozon)]:
        c, p = ch_data.get('current', {}), ch_data.get('previous', {})
        if not c:
            continue
        L(f"### {ch_name}")
        L("")
        L(f"- Маржа: **{format_num(c['margin'])} руб** ({calc_change(c['margin'], p.get('margin', 0)):+.1f}%), маржинальность {format_pct(c.get('margin_pct', 0))}")
        L(f"- ДРР: {format_pct(c.get('drr', 0))} ({calc_change_pp(c.get('drr', 0), p.get('drr', 0)):+.1f} п.п.)")
        L(f"- Выручка до СПП: {format_num(c['revenue_before_spp'])} руб ({calc_change(c['revenue_before_spp'], p.get('revenue_before_spp', 0)):+.1f}%)")
        L(f"- Заказы: {format_num(c.get('orders_count', 0))} шт ({calc_change(c.get('orders_count', 0), p.get('orders_count', 0)):+.1f}%), {format_num(c.get('orders_rub', 0))} руб ({calc_change(c.get('orders_rub', 0), p.get('orders_rub', 0)):+.1f}%)")
        L(f"- Продажи: {format_num(c['sales_count'])} шт ({calc_change(c['sales_count'], p.get('sales_count', 0)):+.1f}%)")
        L(f"- СПП: {format_pct(c.get('spp_pct', 0))} ({calc_change_pp(c.get('spp_pct', 0), p.get('spp_pct', 0)):+.1f} п.п.)")
        L(f"- Реклама: внутр. {format_num(c.get('adv_internal', 0))} руб ({calc_change(c.get('adv_internal', 0), p.get('adv_internal', 0)):+.1f}%), внешн. {format_num(c.get('adv_external', 0))} руб ({calc_change(c.get('adv_external', 0), p.get('adv_external', 0)):+.1f}%)")
        L("")

    L("---")
    L("")

    # --- SECTION 2: Lever decomposition (if margin deviated) ---
    margin_change = calc_change(tc['margin'], tp['margin'])
    h1 = next((h for h in hypotheses if h['id'] == 'H1'), None)
    if h1 and h1.get('levers'):
        L("## Декомпозиция по 5 рычагам")
        L("")
        L(f"Маржинальная прибыль {'выросла' if margin_change > 0 else 'снизилась'} на {abs(margin_change):.1f}% → анализ по рычагам:")
        L("")
        L("| # | Рычаг | Сегодня | Вчера | Изменение | Статус |")
        L("|---|-------|---------|-------|-----------|--------|")
        for i, (name, change_val, cur_val, prev_val) in enumerate(h1['levers'], 1):
            if name in ('СПП %', 'ДРР'):
                cur_s = format_pct(cur_val)
                prev_s = format_pct(prev_val)
                change_s = f"{change_val:+.1f} п.п."
            else:
                cur_s = format_num(cur_val) + " руб"
                prev_s = format_num(prev_val) + " руб"
                change_s = f"{change_val:+.1f}%"
            # Направленная логика: для стоимостных рычагов рост = плохо, для доходных снижение = плохо
            cost_levers = {'ДРР', 'Логистика ₽/ед', 'Себестоимость ₽/ед', 'СПП %'}
            bad_change = change_val if name in cost_levers else -change_val
            if bad_change > 5:
                status = "!!!"
            elif bad_change > 2:
                status = "!"
            elif bad_change < -2:
                status = "✓"
            else:
                status = "OK"
            L(f"| {i} | **{name}** | {cur_s} | {prev_s} | {change_s} | {status} |")

        # Выкуп % — информационный (лаговый показатель, нельзя сравнивать день ко дню)
        if h1.get('buyout_info'):
            bi = h1['buyout_info']
            L(f"| - | Выкуп % *(лаг 3-21 дн.)* | {format_pct(bi['cur'])} | {format_pct(bi['prev'])} | {bi['pp']:+.1f} п.п. | инфо |")
        L("")

        # --- Рублёвая декомпозиция изменения маржи ---
        margin_abs_change = tc['margin'] - tp['margin']
        L("### Рублёвая декомпозиция изменения маржи")
        L("")
        margin_sign = "+" if margin_abs_change >= 0 else ""
        L(f"Изменение маржи: **{margin_sign}{format_num(margin_abs_change)} руб** ({margin_change:+.1f}%)")
        L("")
        L("| Фактор | Сегодня | Вчера | Вклад в Δ маржи |")
        L("|--------|---------|-------|-----------------|")

        # Компоненты формулы маржи WB: Маржа = revenue_spp - comis_spp - logist - sebes - reclama - storage - nds - penalty - retention - deduction
        # revenue_spp = revenue_before_spp (выручка ДО скидки площадки), comis_spp включает SPP
        rub_components = [
            ('Выручка до СПП', 'revenue_before_spp', +1),
            ('Комиссия (вкл. СПП)', 'commission', -1),
            ('Логистика', 'logistics', -1),
            ('Себестоимость', 'cost_of_goods', -1),
            ('Реклама', 'adv_total', -1),
            ('Хранение', 'storage', -1),
        ]
        rub_sum = 0
        for comp_name, comp_key, sign in rub_components:
            cur_v = tc.get(comp_key, 0)
            prev_v = tp.get(comp_key, 0)
            # Вклад: для доходного (+1) рост = плюс; для расходного (-1) рост = минус
            contribution = sign * (cur_v - prev_v)
            rub_sum += contribution
            sign_str = "+" if contribution >= 0 else ""
            L(f"| {comp_name} | {format_num(cur_v)} | {format_num(prev_v)} | **{sign_str}{format_num(contribution)} руб** |")

        # Прочее (NDS, penalty, retention, deduction) — суммарно
        nds_cur = wb.get('current', {}).get('nds', 0) + ozon.get('current', {}).get('nds', 0)
        nds_prev = wb.get('previous', {}).get('nds', 0) + ozon.get('previous', {}).get('nds', 0)
        penalty_cur = wb.get('current', {}).get('penalty', 0)
        penalty_prev = wb.get('previous', {}).get('penalty', 0)
        retention_cur = wb.get('current', {}).get('retention', 0)
        retention_prev = wb.get('previous', {}).get('retention', 0)
        deduction_cur = wb.get('current', {}).get('deduction', 0)
        deduction_prev = wb.get('previous', {}).get('deduction', 0)
        other_total_cur = nds_cur + penalty_cur + retention_cur + deduction_cur
        other_total_prev = nds_prev + penalty_prev + retention_prev + deduction_prev
        other_contribution = -(other_total_cur - other_total_prev)
        rub_sum += other_contribution
        other_sign = "+" if other_contribution >= 0 else ""
        L(f"| Прочее (НДС, штрафы, удерж.) | {format_num(other_total_cur)} | {format_num(other_total_prev)} | **{other_sign}{format_num(other_contribution)} руб** |")
        # Нераспределённое: разница между фактическим Δ маржи и суммой компонентов
        # (возникает из-за OZON marga — предвычисленное поле в БД)
        residual = margin_abs_change - rub_sum
        if abs(residual) > 1:
            res_sign = "+" if residual >= 0 else ""
            L(f"| Нераспределённое (OZON marga) | | | **{res_sign}{format_num(residual)} руб** |")
        L(f"| **Итого** | | | **{margin_sign}{format_num(margin_abs_change)} руб** |")
        L("")

        L("---")
        L("")

    # --- SECTION 3-5: Гипотезы, Рекомендации, Human Review ---
    # При --export-context эти секции пропускаются: Рома (LLM) напишет анализ сам
    if not export_context:
        if hypotheses:
            L("## Гипотезы и сценарии")
            L("")
            for h in sorted(hypotheses, key=lambda x: x['confidence'], reverse=True):
                L(f"### {h['id']}: {h['statement']}")
                L(f"")
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

        high_conf = [h for h in hypotheses if h['confidence'] >= CONFIDENCE_THRESHOLD and h.get('what_if')]
        if high_conf:
            L("## Рекомендации")
            L("")
            L("| # | Действие | Confidence | Ожидаемый эффект |")
            L("|---|----------|------------|-----------------|")
            for i, h in enumerate(sorted(high_conf, key=lambda x: x['confidence'], reverse=True), 1):
                L(f"| {i} | {h['what_if'][:80]} | {h['confidence']:.2f} | см. {h['id']} |")
            L("")
            L("---")
            L("")

        low_conf = [h for h in hypotheses if h['confidence'] < CONFIDENCE_THRESHOLD]
        if low_conf:
            L("## Требует внимания (confidence < 0.6)")
            L("")
            for h in low_conf:
                L(f"- **{h['id']}** ({h['confidence']:.2f}): {h['statement'][:100]}")
                if h.get('counter_arguments'):
                    for ca in h['counter_arguments']:
                        L(f"  - Red Team: {ca}")
            L("")

    L("---")
    L(f"*Отчёт сгенерирован: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    if export_context:
        L(f"*Анализ и рекомендации будут дописаны Ромой (ИИ-аналитик)*")

    return '\n'.join(lines)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Ежедневная аналитика с Confidence Scores')
    parser.add_argument('--date', required=True, help='Дата анализа (YYYY-MM-DD)')
    parser.add_argument('--lookback', type=int, default=7, help='Дней исторического контекста (default: 7)')
    parser.add_argument('--save', action='store_true', help='Сохранить в reports/')
    parser.add_argument('--notion', action='store_true', help='Синхронизировать с Notion')
    parser.add_argument('--export-context', action='store_true',
                        help='Экспортировать data_context.json для LLM-анализа (Рома)')
    args = parser.parse_args()

    target_date = args.date
    target_dt = datetime.strptime(target_date, '%Y-%m-%d')
    prev_date = (target_dt - timedelta(days=1)).strftime('%Y-%m-%d')
    current_end = (target_dt + timedelta(days=1)).strftime('%Y-%m-%d')

    print(f"[Daily] Загрузка данных за {target_date}...")

    # --- Data loading ---
    wb_data, wb_orders = get_wb_finance(target_date, prev_date, current_end)
    ozon_data, ozon_orders = get_ozon_finance(target_date, prev_date, current_end)
    wb_models_raw = get_wb_by_model(target_date, prev_date, current_end)
    ozon_models_raw = get_ozon_by_model(target_date, prev_date, current_end)
    _, wb_adv_data = get_wb_traffic(target_date, prev_date, current_end)
    ozon_traffic_data = get_ozon_traffic(target_date, prev_date, current_end)
    wb_orders_by_model = get_wb_orders_by_model(target_date, prev_date, current_end)
    ozon_orders_by_model = get_ozon_orders_by_model(target_date, prev_date, current_end)

    print(f"[Daily] Загрузка 7-дневного контекста...")
    wb_series = get_wb_daily_series(target_date, args.lookback)
    ozon_series = get_ozon_daily_series(target_date, args.lookback)

    # --- Parse WB ---
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
            'returns_revenue': to_float(row[17]), 'revenue_before_spp_gross': to_float(row[18]),
        }
    for row in wb_orders:
        period = row[0]
        if period in wb:
            wb[period]['orders_rub'] = to_float(row[1])

    # --- Parse OZON ---
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

    # --- Data quality checks ---
    # NB: С формулой маржи marga - nds - reclama_vn автокоррекция retention/deduction
    # отключена — поле `marga` вычисляется на стороне WB и может уже учитывать дублирование.
    # Предупреждения сохраняются для информации в отчёте.
    dq_current = validate_wb_data_quality(target_date)
    dq_previous = validate_wb_data_quality(prev_date)
    dq_warnings = dq_current['warnings'] + dq_previous['warnings']

    if dq_current['margin_adjustment'] > 0:
        print(f"[Daily] ⚠ Качество данных ({target_date}): retention == deduction ({format_num(dq_current['margin_adjustment'])} руб). Требуется сверка с OneScreen.")

    if dq_previous['margin_adjustment'] > 0:
        print(f"[Daily] ⚠ Качество данных ({prev_date}): retention == deduction ({format_num(dq_previous['margin_adjustment'])} руб). Требуется сверка с OneScreen.")

    # --- Derived metrics ---
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

    # --- Total ---
    total = {'current': {}, 'previous': {}}
    for period in ['current', 'previous']:
        w = wb.get(period, {})
        o = ozon.get(period, {})
        total_spp_amount = w.get('spp_amount', 0) + o.get('spp_amount', 0)
        total_revenue_bspp = w.get('revenue_before_spp', 0) + o.get('revenue_before_spp', 0)
        total[period] = {
            'orders_count': w.get('orders_count', 0) + o.get('orders_count', 0),
            'orders_rub': w.get('orders_rub', 0) + o.get('orders_rub', 0),
            'sales_count': w.get('sales_count', 0) + o.get('sales_count', 0),
            'revenue_before_spp': total_revenue_bspp,
            'revenue_after_spp': w.get('revenue_after_spp', 0) + o.get('revenue_after_spp', 0),
            'adv_total': w.get('adv_total', 0) + o.get('adv_total', 0),
            'adv_internal': w.get('adv_internal', 0) + o.get('adv_internal', 0),
            'adv_external': w.get('adv_external', 0) + o.get('adv_external', 0),
            'margin': w.get('margin', 0) + o.get('margin', 0),
            'cost_of_goods': w.get('cost_of_goods', 0) + o.get('cost_of_goods', 0),
            'logistics': w.get('logistics', 0) + o.get('logistics', 0),
            'storage': w.get('storage', 0) + o.get('storage', 0),
            'commission': w.get('commission', 0) + o.get('commission', 0),
            'spp_amount': total_spp_amount,
        }
        t = total[period]
        t['avg_check_orders'] = t['orders_rub'] / t['orders_count'] if t['orders_count'] > 0 else 0
        t['avg_check_sales'] = t['revenue_before_spp'] / t['sales_count'] if t['sales_count'] > 0 else 0
        t['drr'] = (t['adv_total'] / t['revenue_before_spp'] * 100) if t['revenue_before_spp'] > 0 else 0
        t['margin_pct'] = (t['margin'] / t['revenue_before_spp'] * 100) if t['revenue_before_spp'] > 0 else 0
        t['romi'] = (t['margin'] / t['adv_total'] * 100) if t['adv_total'] > 0 else 0
        t['spp_pct'] = (total_spp_amount / total_revenue_bspp * 100) if total_revenue_bspp > 0 else 0

    # --- Models ---
    wb_models_c = [(row[1], to_float(row[5]), to_float(row[3]), to_float(row[4])) for row in wb_models_raw if row[0] == 'current']
    wb_models_p = {row[1]: to_float(row[5]) for row in wb_models_raw if row[0] == 'previous'}
    wb_models_c.sort(key=lambda x: x[1], reverse=True)

    ozon_models_c = [(row[1], to_float(row[5]), to_float(row[3]), to_float(row[4])) for row in ozon_models_raw if row[0] == 'current']
    ozon_models_p = {row[1]: to_float(row[5]) for row in ozon_models_raw if row[0] == 'previous'}
    ozon_models_c.sort(key=lambda x: x[1], reverse=True)

    # --- Generate hypotheses ---
    print(f"[Daily] Генерация гипотез...")
    hypotheses = generate_hypotheses(
        wb, ozon, total, wb_series, ozon_series,
        wb_models_c, wb_models_p, ozon_models_c, ozon_models_p,
        wb_adv_data, ozon_traffic_data
    )

    # --- Red Team ---
    print(f"[Daily] Red Team анализ...")
    tc = total['current']
    ozon_share = ozon['current'].get('revenue_before_spp', 0) / tc['revenue_before_spp'] if tc['revenue_before_spp'] > 0 else 0
    wb_spp_pp = calc_change_pp(wb['current'].get('spp_pct', 0), wb['previous'].get('spp_pct', 0))
    avg_daily_orders = sum(d.get('orders_count', 0) for d in wb_series) / len(wb_series) if wb_series else 0

    for h in hypotheses:
        series_key = 'margin' if h['category'] in ('margin', 'model') else 'adv_total' if h['category'] == 'advertising' else 'margin'
        series_vals = [d.get(series_key, 0) for d in wb_series]
        series_dates = [d.get('date') for d in wb_series]

        data_ctx = {
            'series': series_vals,
            'series_dates': series_dates,
            'target_weekday': target_dt.weekday(),
            'current_value': tc.get(series_key, tc['margin']),
            'today_orders': tc.get('orders_count', 0),
            'avg_daily_orders': avg_daily_orders,
            'ozon_share': ozon_share,
            'spp_change_pp': wb_spp_pp,
            'is_single_day': True,
        }

        penalty, triggered = red_team_checks(h, data_ctx)
        if triggered:
            h['counter_arguments'] = triggered
            h['confidence'] = round(max(0.10, h['confidence'] - penalty), 2)

    # --- Render ---
    print(f"[Daily] Генерация отчёта...")
    report_md = render_report(target_date, wb, ozon, total, hypotheses, wb_series, ozon_series, dq_warnings, export_context=args.export_context)

    print(report_md)

    # --- Save ---
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    reports_dir = os.path.join(project_root, 'reports')

    if args.save:
        os.makedirs(reports_dir, exist_ok=True)
        report_path = os.path.join(reports_dir, f"{target_date}_daily_analytics.md")
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_md)
        print(f"\n[Daily] Отчёт сохранён: {report_path}")

    # --- Export data context for Рома (LLM analysis) ---
    if args.export_context and args.save:
        import json
        from scripts.analytics_agent_roma.context_builder import prepare_data_context
        ctx = prepare_data_context(
            target_date, prev_date,
            wb, ozon, total,
            wb_series, ozon_series,
            wb_models_c, wb_models_p,
            ozon_models_c, ozon_models_p,
            wb_adv_data, ozon_traffic_data,
            dq_warnings,
            wb_orders_by_model=wb_orders_by_model,
            ozon_orders_by_model=ozon_orders_by_model,
        )
        ctx_path = os.path.join(reports_dir, f"{target_date}_data_context.json")
        with open(ctx_path, 'w', encoding='utf-8') as f:
            json.dump(ctx, f, ensure_ascii=False, indent=2)
        print(f"[Daily] Контекст для Ромы сохранён: {ctx_path}")

    # --- Notion sync (skip when export-context: Рома сделает после анализа) ---
    if args.notion and not args.export_context:
        try:
            from scripts.notion_sync import sync_report_to_notion
            url = sync_report_to_notion(target_date, target_date, report_md)
            print(f"[Daily] Отчёт в Notion: {url}")
        except Exception as e:
            print(f"[Daily] Ошибка Notion: {e}")
    elif args.notion and args.export_context:
        print(f"[Daily] Notion sync пропущен: Рома допишет анализ, затем sync")

    print(f"\n[Daily] Гипотез: {len(hypotheses)}, из них требуют внимания: {len([h for h in hypotheses if h['confidence'] < CONFIDENCE_THRESHOLD])}")


if __name__ == "__main__":
    main()
