"""
Сборка data_context.json для LLM-анализа (Рома).

Собирает данные из daily/period/monthly скриптов в единый JSON,
который Рома (Claude Code или Claude API) использует для анализа.
"""

from scripts.data_layer import calc_change, calc_change_pp


def _channel_snapshot(data, period):
    """Извлекает ключевые метрики канала за период."""
    d = data.get(period, {})
    if not d:
        return {}
    return {
        'margin': d.get('margin', 0),
        'margin_pct': d.get('margin_pct', 0),
        'revenue_before_spp': d.get('revenue_before_spp', 0),
        'revenue_after_spp': d.get('revenue_after_spp', 0),
        'orders_count': d.get('orders_count', 0),
        'orders_rub': d.get('orders_rub', 0),
        'sales_count': d.get('sales_count', 0),
        'adv_total': d.get('adv_total', 0),
        'adv_internal': d.get('adv_internal', 0),
        'adv_external': d.get('adv_external', 0),
        'drr': d.get('drr', 0),
        'spp_pct': d.get('spp_pct', 0),
        'spp_amount': d.get('spp_amount', 0),
        'cost_of_goods': d.get('cost_of_goods', 0),
        'logistics': d.get('logistics', 0),
        'storage': d.get('storage', 0),
        'commission': d.get('commission', 0),
        'avg_check_orders': d.get('avg_check_orders', 0),
        'avg_check_sales': d.get('avg_check_sales', 0),
        'romi': d.get('romi', 0),
    }


def _compute_changes(current, previous):
    """Вычисляет изменения между периодами."""
    if not current or not previous:
        return {}
    return {
        'margin_pct': calc_change(current.get('margin', 0), previous.get('margin', 0)),
        'margin_abs': current.get('margin', 0) - previous.get('margin', 0),
        'margin_pct_pp': calc_change_pp(current.get('margin_pct', 0), previous.get('margin_pct', 0)),
        'revenue_pct': calc_change(current.get('revenue_before_spp', 0), previous.get('revenue_before_spp', 0)),
        'orders_count_pct': calc_change(current.get('orders_count', 0), previous.get('orders_count', 0)),
        'orders_rub_pct': calc_change(current.get('orders_rub', 0), previous.get('orders_rub', 0)),
        'sales_count_pct': calc_change(current.get('sales_count', 0), previous.get('sales_count', 0)),
        'adv_total_pct': calc_change(current.get('adv_total', 0), previous.get('adv_total', 0)),
        'adv_internal_pct': calc_change(current.get('adv_internal', 0), previous.get('adv_internal', 0)),
        'adv_external_pct': calc_change(current.get('adv_external', 0), previous.get('adv_external', 0)),
        'drr_pp': calc_change_pp(current.get('drr', 0), previous.get('drr', 0)),
        'spp_pp': calc_change_pp(current.get('spp_pct', 0), previous.get('spp_pct', 0)),
        'logistics_pct': calc_change(current.get('logistics', 0), previous.get('logistics', 0)),
    }


def _compute_levers(tc, tp):
    """Вычисляет 5 рычагов маржи + выкуп (информационный)."""
    levers = []

    # 1. Цена до СПП
    price_cur = tc['revenue_before_spp'] / tc['sales_count'] if tc.get('sales_count', 0) > 0 else 0
    price_prev = tp['revenue_before_spp'] / tp['sales_count'] if tp.get('sales_count', 0) > 0 else 0
    levers.append({
        'name': 'Цена до СПП',
        'current': round(price_cur, 0),
        'previous': round(price_prev, 0),
        'change_pct': round(calc_change(price_cur, price_prev), 1),
    })

    # 2. СПП %
    levers.append({
        'name': 'СПП %',
        'current': round(tc.get('spp_pct', 0), 1),
        'previous': round(tp.get('spp_pct', 0), 1),
        'change_pp': round(calc_change_pp(tc.get('spp_pct', 0), tp.get('spp_pct', 0)), 1),
    })

    # 3. ДРР
    levers.append({
        'name': 'ДРР',
        'current': round(tc.get('drr', 0), 1),
        'previous': round(tp.get('drr', 0), 1),
        'change_pp': round(calc_change_pp(tc.get('drr', 0), tp.get('drr', 0)), 1),
    })

    # 4. Логистика ₽/ед
    log_cur = tc['logistics'] / tc['sales_count'] if tc.get('sales_count', 0) > 0 else 0
    log_prev = tp['logistics'] / tp['sales_count'] if tp.get('sales_count', 0) > 0 else 0
    levers.append({
        'name': 'Логистика ₽/ед',
        'current': round(log_cur, 0),
        'previous': round(log_prev, 0),
        'change_pct': round(calc_change(log_cur, log_prev), 1),
    })

    # 5. Себестоимость ₽/ед
    sebes_cur = tc['cost_of_goods'] / tc['sales_count'] if tc.get('sales_count', 0) > 0 else 0
    sebes_prev = tp['cost_of_goods'] / tp['sales_count'] if tp.get('sales_count', 0) > 0 else 0
    levers.append({
        'name': 'Себестоимость ₽/ед',
        'current': round(sebes_cur, 0),
        'previous': round(sebes_prev, 0),
        'change_pct': round(calc_change(sebes_cur, sebes_prev), 1),
    })

    # Выкуп % (информационный, лаговый 3-21 дн.)
    buyout_cur = (tc['sales_count'] / tc['orders_count'] * 100) if tc.get('orders_count', 0) > 0 else 0
    buyout_prev = (tp['sales_count'] / tp['orders_count'] * 100) if tp.get('orders_count', 0) > 0 else 0
    buyout = {
        'current': round(buyout_cur, 1),
        'previous': round(buyout_prev, 1),
        'change_pp': round(calc_change_pp(buyout_cur, buyout_prev), 1),
        'note': 'лаговый 3-21 дн.',
    }

    return levers, buyout


def _models_snapshot(models_current, models_previous, orders_by_model=None):
    """Формирует список моделей с изменениями и ДРР заказов."""
    # Парсим заказы по моделям: {model: orders_rub}
    orders_map = {}
    if orders_by_model:
        for row in orders_by_model:
            if row[0] == 'current':
                orders_map[row[1]] = float(row[3]) if row[3] else 0

    result = []
    for model, margin, revenue, adv in models_current[:10]:
        prev_margin = models_previous.get(model, 0)
        total_margin = sum(m for _, m, _, _ in models_current)
        share = (margin / total_margin * 100) if total_margin > 0 else 0
        orders_rub = orders_map.get(model, 0)
        drr_sales = round((adv / revenue * 100) if revenue > 0 else 0, 1)
        drr_orders = round((adv / orders_rub * 100) if orders_rub > 0 else 0, 1)
        result.append({
            'name': model,
            'margin': round(margin, 0),
            'prev_margin': round(prev_margin, 0),
            'change_pct': round(calc_change(margin, prev_margin), 1),
            'share_pct': round(share, 1),
            'revenue': round(revenue, 0),
            'adv': round(adv, 0),
            'orders_rub': round(orders_rub, 0),
            'drr_sales': drr_sales,
            'drr_orders': drr_orders,
        })
    return result


def _series_snapshot(wb_series, ozon_series):
    """Формирует 7-дневный ряд данных."""
    result = []
    for i, ws in enumerate(wb_series):
        os_data = ozon_series[i] if i < len(ozon_series) else {}
        result.append({
            'date': str(ws.get('date', '')),
            'wb_margin': round(ws.get('margin', 0), 0),
            'ozon_margin': round(os_data.get('margin', 0), 0),
            'total_margin': round(ws.get('margin', 0) + os_data.get('margin', 0), 0),
            'wb_adv': round(ws.get('adv_total', 0), 0),
            'ozon_adv': round(os_data.get('adv_total', 0), 0),
            'wb_orders': round(ws.get('orders_count', 0), 0),
            'wb_sales': round(ws.get('sales_count', 0), 0),
        })
    return result


def prepare_data_context(
    target_date, prev_date,
    wb, ozon, total,
    wb_series, ozon_series,
    wb_models_c, wb_models_p,
    ozon_models_c, ozon_models_p,
    wb_adv_data=None, ozon_traffic_data=None,
    dq_warnings=None,
    wb_orders_by_model=None, ozon_orders_by_model=None,
):
    """
    Собирает все данные в единый JSON-контекст для LLM-анализа.

    Returns:
        dict: data_context для записи в JSON
    """
    tc = _channel_snapshot(total, 'current')
    tp = _channel_snapshot(total, 'previous')
    levers, buyout = _compute_levers(
        total.get('current', {}),
        total.get('previous', {}),
    )

    # Рекламная статистика WB (CTR, CPC)
    wb_adv_stats = {}
    if wb_adv_data:
        from scripts.data_layer import to_float
        wb_adv_c = [r for r in wb_adv_data if r[0] == 'current']
        wb_adv_p = [r for r in wb_adv_data if r[0] == 'previous']
        if wb_adv_c and wb_adv_p:
            wb_adv_stats = {
                'views_cur': to_float(wb_adv_c[0][3]),
                'clicks_cur': to_float(wb_adv_c[0][4]),
                'ctr_cur': to_float(wb_adv_c[0][6]),
                'cpc_cur': to_float(wb_adv_c[0][7]),
                'views_prev': to_float(wb_adv_p[0][3]),
                'clicks_prev': to_float(wb_adv_p[0][4]),
                'ctr_prev': to_float(wb_adv_p[0][6]),
                'cpc_prev': to_float(wb_adv_p[0][7]),
            }

    ctx = {
        'date': target_date,
        'prev_date': prev_date,
        'total': {
            'current': tc,
            'previous': tp,
            'changes': _compute_changes(tc, tp),
        },
        'wb': {
            'current': _channel_snapshot(wb, 'current'),
            'previous': _channel_snapshot(wb, 'previous'),
            'changes': _compute_changes(
                _channel_snapshot(wb, 'current'),
                _channel_snapshot(wb, 'previous'),
            ),
        },
        'ozon': {
            'current': _channel_snapshot(ozon, 'current'),
            'previous': _channel_snapshot(ozon, 'previous'),
            'changes': _compute_changes(
                _channel_snapshot(ozon, 'current'),
                _channel_snapshot(ozon, 'previous'),
            ),
        },
        'levers': levers,
        'buyout': buyout,
        'wb_top_models': _models_snapshot(wb_models_c, wb_models_p, wb_orders_by_model),
        'ozon_top_models': _models_snapshot(ozon_models_c, ozon_models_p, ozon_orders_by_model),
        'advertising': {
            'wb': wb_adv_stats,
        },
        'series_7d': _series_snapshot(wb_series, ozon_series),
        'data_quality': [w['message'] for w in (dq_warnings or [])],
    }

    return ctx


def _adv_stats_from_raw(wb_adv_data, ozon_traffic_data=None):
    """Извлекает рекламную статистику из сырых данных."""
    from scripts.data_layer import to_float
    stats = {'wb': {}, 'ozon': {}}

    if wb_adv_data:
        wb_adv_c = [r for r in wb_adv_data if r[0] == 'current']
        wb_adv_p = [r for r in wb_adv_data if r[0] == 'previous']
        if wb_adv_c and wb_adv_p:
            stats['wb'] = {
                'views_cur': to_float(wb_adv_c[0][3]),
                'clicks_cur': to_float(wb_adv_c[0][4]),
                'ctr_cur': to_float(wb_adv_c[0][6]),
                'cpc_cur': to_float(wb_adv_c[0][7]),
                'views_prev': to_float(wb_adv_p[0][3]),
                'clicks_prev': to_float(wb_adv_p[0][4]),
                'ctr_prev': to_float(wb_adv_p[0][6]),
                'cpc_prev': to_float(wb_adv_p[0][7]),
            }

    if ozon_traffic_data:
        oz_c = [r for r in ozon_traffic_data if r[0] == 'current']
        oz_p = [r for r in ozon_traffic_data if r[0] == 'previous']
        if oz_c and oz_p:
            stats['ozon'] = {
                'views_cur': to_float(oz_c[0][1]),
                'clicks_cur': to_float(oz_c[0][2]),
                'ctr_cur': to_float(oz_c[0][5]),
                'cpc_cur': to_float(oz_c[0][6]),
                'views_prev': to_float(oz_p[0][1]),
                'clicks_prev': to_float(oz_p[0][2]),
                'ctr_prev': to_float(oz_p[0][5]),
                'cpc_prev': to_float(oz_p[0][6]),
            }

    return stats


def prepare_period_context(
    start_date, end_date,
    prev_start, prev_end,
    wb, ozon, total,
    wb_models_c, wb_models_p,
    ozon_models_c, ozon_models_p,
    wb_adv_data=None, ozon_traffic_data=None,
):
    """
    Собирает данные периодного отчёта в JSON-контекст для LLM-анализа.

    Args:
        start_date: Начало текущего периода (YYYY-MM-DD)
        end_date: Конец текущего периода (YYYY-MM-DD)
        prev_start: Начало предыдущего периода
        prev_end: Конец предыдущего периода
        wb, ozon, total: Данные каналов {'current': {...}, 'previous': {...}}
        wb_models_c/p, ozon_models_c/p: Модели
        wb_adv_data, ozon_traffic_data: Сырые рекламные данные

    Returns:
        dict: data_context для записи в JSON
    """
    tc = _channel_snapshot(total, 'current')
    tp = _channel_snapshot(total, 'previous')
    levers, buyout = _compute_levers(
        total.get('current', {}),
        total.get('previous', {}),
    )
    adv_stats = _adv_stats_from_raw(wb_adv_data, ozon_traffic_data)

    ctx = {
        'report_type': 'period',
        'period': {
            'start': start_date,
            'end': end_date,
        },
        'comparison_period': {
            'start': prev_start,
            'end': prev_end,
        },
        'total': {
            'current': tc,
            'previous': tp,
            'changes': _compute_changes(tc, tp),
        },
        'wb': {
            'current': _channel_snapshot(wb, 'current'),
            'previous': _channel_snapshot(wb, 'previous'),
            'changes': _compute_changes(
                _channel_snapshot(wb, 'current'),
                _channel_snapshot(wb, 'previous'),
            ),
        },
        'ozon': {
            'current': _channel_snapshot(ozon, 'current'),
            'previous': _channel_snapshot(ozon, 'previous'),
            'changes': _compute_changes(
                _channel_snapshot(ozon, 'current'),
                _channel_snapshot(ozon, 'previous'),
            ),
        },
        'levers': levers,
        'buyout': buyout,
        'wb_top_models': _models_snapshot(wb_models_c, wb_models_p),
        'ozon_top_models': _models_snapshot(ozon_models_c, ozon_models_p),
        'advertising': adv_stats,
    }

    return ctx


def _weekly_breakdown_snapshot(wb_weekly, ozon_weekly):
    """Формирует понедельную разбивку для месячного контекста."""
    wb_map = {str(w.get('week_start', '')): w for w in wb_weekly}
    ozon_map = {str(w.get('week_start', '')): w for w in ozon_weekly}
    all_weeks = sorted(set(list(wb_map.keys()) + list(ozon_map.keys())))

    result = []
    for ws in all_weeks:
        ww = wb_map.get(ws, {})
        ow = ozon_map.get(ws, {})
        margin = ww.get('margin', 0) + ow.get('margin', 0)
        revenue = ww.get('revenue_before_spp', 0) + ow.get('revenue_before_spp', 0)
        adv = ww.get('adv_total', 0) + ow.get('adv_total', 0)
        days = max(ww.get('days', 0), ow.get('days', 0))
        result.append({
            'week_start': ws,
            'week_end': str(ww.get('week_end', ow.get('week_end', ws))),
            'days': days,
            'margin': round(margin, 0),
            'margin_daily': round(margin / days, 0) if days > 0 else 0,
            'margin_pct': round((margin / revenue * 100) if revenue > 0 else 0, 1),
            'revenue': round(revenue, 0),
            'adv': round(adv, 0),
            'drr': round((adv / revenue * 100) if revenue > 0 else 0, 1),
        })
    return result


def _daily_series_from_raw(wb_daily, ozon_daily):
    """Формирует дневной ряд из данных daily_series_range."""
    wb_map = {str(d.get('date', '')): d for d in wb_daily}
    ozon_map = {str(d.get('date', '')): d for d in ozon_daily}
    all_dates = sorted(set(list(wb_map.keys()) + list(ozon_map.keys())))

    result = []
    for date in all_dates:
        ws = wb_map.get(date, {})
        os_data = ozon_map.get(date, {})
        result.append({
            'date': date,
            'wb_margin': round(ws.get('margin', 0), 0),
            'ozon_margin': round(os_data.get('margin', 0), 0),
            'total_margin': round(ws.get('margin', 0) + os_data.get('margin', 0), 0),
            'wb_adv': round(ws.get('adv_total', 0), 0),
            'ozon_adv': round(os_data.get('adv_total', 0), 0),
            'wb_orders': round(ws.get('orders_count', 0), 0),
            'wb_sales': round(ws.get('sales_count', 0), 0),
        })
    return result


TARGETS = {
    'margin_monthly_min': 5_000_000,
    'margin_monthly_mid': 6_500_000,
    'margin_pct_min': 20.0,
    'margin_pct_mid': 23.0,
    'margin_pct_high': 25.0,
}


def prepare_monthly_context(
    target_month, compare_month,
    wb, ozon, total,
    wb_models_c, wb_models_p,
    ozon_models_c, ozon_models_p,
    wb_weekly=None, ozon_weekly=None,
    wb_daily=None, ozon_daily=None,
    wb_adv_data=None, ozon_traffic_data=None,
):
    """
    Собирает данные месячного отчёта в JSON-контекст для LLM-анализа.

    Args:
        target_month: Целевой месяц (YYYY-MM)
        compare_month: Месяц сравнения (YYYY-MM)
        wb, ozon, total: Данные каналов
        wb/ozon_models_c/p: Модели
        wb/ozon_weekly: Понедельная разбивка
        wb/ozon_daily: Дневные серии за месяц
        wb_adv_data, ozon_traffic_data: Рекламные данные

    Returns:
        dict: data_context для записи в JSON
    """
    tc = _channel_snapshot(total, 'current')
    tp = _channel_snapshot(total, 'previous')
    levers, buyout = _compute_levers(
        total.get('current', {}),
        total.get('previous', {}),
    )
    adv_stats = _adv_stats_from_raw(wb_adv_data, ozon_traffic_data)

    # Targets gap
    targets_gap = {
        'margin_vs_min': round(tc.get('margin', 0) - TARGETS['margin_monthly_min'], 0),
        'margin_vs_mid': round(tc.get('margin', 0) - TARGETS['margin_monthly_mid'], 0),
        'margin_pct_vs_min': round(tc.get('margin_pct', 0) - TARGETS['margin_pct_min'], 1),
        'margin_pct_vs_mid': round(tc.get('margin_pct', 0) - TARGETS['margin_pct_mid'], 1),
        'margin_pct_vs_high': round(tc.get('margin_pct', 0) - TARGETS['margin_pct_high'], 1),
    }

    ctx = {
        'report_type': 'monthly',
        'target_month': target_month,
        'compare_month': compare_month,
        'total': {
            'current': tc,
            'previous': tp,
            'changes': _compute_changes(tc, tp),
        },
        'wb': {
            'current': _channel_snapshot(wb, 'current'),
            'previous': _channel_snapshot(wb, 'previous'),
            'changes': _compute_changes(
                _channel_snapshot(wb, 'current'),
                _channel_snapshot(wb, 'previous'),
            ),
        },
        'ozon': {
            'current': _channel_snapshot(ozon, 'current'),
            'previous': _channel_snapshot(ozon, 'previous'),
            'changes': _compute_changes(
                _channel_snapshot(ozon, 'current'),
                _channel_snapshot(ozon, 'previous'),
            ),
        },
        'levers': levers,
        'buyout': buyout,
        'wb_top_models': _models_snapshot(wb_models_c, wb_models_p),
        'ozon_top_models': _models_snapshot(ozon_models_c, ozon_models_p),
        'advertising': adv_stats,
        'targets_gap': targets_gap,
        'weekly_breakdown': _weekly_breakdown_snapshot(wb_weekly or [], ozon_weekly or []),
        'daily_series': _daily_series_from_raw(wb_daily or [], ozon_daily or []),
    }

    return ctx
