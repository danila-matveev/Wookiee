"""
Scenario Modeler — прогнозирование и контрфактуальный анализ.

Методы:
- simulate_price_change: прогноз при заданном % изменения цены
- counterfactual_analysis: "что было бы если мы изменили цену N дней назад"
- compare_periods: сравнение периодов до/после ценового изменения
"""
import logging

import pandas as pd

from agents.oleg.services.price_analysis.regression_engine import (
    estimate_price_elasticity,
)

logger = logging.getLogger(__name__)


def simulate_price_change(
    data: list[dict],
    price_change_pct: float,
    model: str = '',
    channel: str = '',
    forecast_days: int = 7,
) -> dict:
    """
    Прогноз: что произойдёт если изменить цену на X%.

    Использует эластичность + последние 7 дней как baseline.
    """
    if len(data) < 14:
        return {'error': 'insufficient_data', 'n_days': len(data)}

    df = pd.DataFrame(data)

    # Baseline — последние 7 дней
    baseline = df.tail(7)
    baseline_metrics = {
        'price_per_unit': float(baseline['price_per_unit'].mean()),
        'sales_per_day': float(baseline['sales_count'].mean()),
        'margin_per_day': float(baseline['margin'].mean()),
        'margin_pct': float(baseline['margin_pct'].mean()),
        'revenue_per_day': float(baseline['revenue_before_spp'].mean()),
    }

    # Эластичность
    elasticity_result = estimate_price_elasticity(data)
    if 'error' in elasticity_result:
        return {
            'model': model,
            'channel': channel,
            'error': f'elasticity_error: {elasticity_result["error"]}',
        }

    e = elasticity_result['elasticity']

    # Новая цена
    new_price = baseline_metrics['price_per_unit'] * (1 + price_change_pct / 100)

    # Предсказание объёма: %ΔQ = ε × %ΔP
    volume_change_pct = e * price_change_pct
    new_sales = baseline_metrics['sales_per_day'] * (1 + volume_change_pct / 100)
    new_sales = max(new_sales, 0)

    # Маржа: маржа/шт изменяется на ΔP
    margin_per_unit = baseline_metrics['margin_per_day'] / (
        baseline_metrics['sales_per_day'] + 1e-10
    )
    price_delta = new_price - baseline_metrics['price_per_unit']
    new_margin_per_unit = margin_per_unit + price_delta
    new_margin_per_day = new_margin_per_unit * new_sales

    new_revenue = new_price * new_sales
    new_margin_pct = new_margin_per_day / (new_revenue + 1e-10) * 100 if new_revenue > 0 else 0

    # Прогноз на N дней
    forecast = {
        'period_days': forecast_days,
        'baseline_total_margin': round(baseline_metrics['margin_per_day'] * forecast_days, 0),
        'forecast_total_margin': round(new_margin_per_day * forecast_days, 0),
        'margin_delta': round(
            (new_margin_per_day - baseline_metrics['margin_per_day']) * forecast_days, 0
        ),
        'baseline_total_revenue': round(baseline_metrics['revenue_per_day'] * forecast_days, 0),
        'forecast_total_revenue': round(new_revenue * forecast_days, 0),
        'baseline_total_sales': round(baseline_metrics['sales_per_day'] * forecast_days, 0),
        'forecast_total_sales': round(new_sales * forecast_days, 0),
    }

    return {
        'model': model,
        'channel': channel,
        'price_change_pct': price_change_pct,
        'elasticity': elasticity_result,
        'baseline': {k: round(v, 2) for k, v in baseline_metrics.items()},
        'predicted': {
            'price_per_unit': round(new_price, 2),
            'sales_per_day': round(new_sales, 1),
            'margin_per_day': round(new_margin_per_day, 0),
            'margin_pct': round(new_margin_pct, 2),
            'revenue_per_day': round(new_revenue, 0),
            'volume_change_pct': round(volume_change_pct, 2),
        },
        'forecast': forecast,
    }


def counterfactual_analysis(
    data: list[dict],
    price_change_pct: float,
    period_start: str,
    period_end: str,
    model: str = '',
    channel: str = '',
) -> dict:
    """
    Контрфактуальный анализ: "что было бы если мы изменили цену N дней назад".

    Сравнивает фактические результаты с гипотетическими при другой цене.
    """
    if len(data) < 14:
        return {'error': 'insufficient_data'}

    df = pd.DataFrame(data)
    df['date'] = pd.to_datetime(df['date'])

    # Фильтр по периоду
    mask = (df['date'] >= period_start) & (df['date'] <= period_end)
    period_data = df[mask]

    if len(period_data) == 0:
        return {'error': 'no_data_in_period'}

    # Фактические результаты
    actual = {
        'total_margin': round(float(period_data['margin'].sum()), 0),
        'total_revenue': round(float(period_data['revenue_before_spp'].sum()), 0),
        'total_sales': round(float(period_data['sales_count'].sum()), 0),
        'avg_price': round(float(period_data['price_per_unit'].mean()), 2),
        'avg_margin_pct': round(float(period_data['margin_pct'].mean()), 2),
        'days': len(period_data),
    }

    # Эластичность (на данных ДО периода для чистоты)
    pre_period = df[df['date'] < period_start]
    if len(pre_period) < 14:
        pre_period = df  # fallback: используем все данные

    elasticity_result = estimate_price_elasticity(pre_period.to_dict('records'))
    if 'error' in elasticity_result:
        return {
            'model': model,
            'channel': channel,
            'actual': actual,
            'error': f'elasticity_error: {elasticity_result["error"]}',
        }

    e = elasticity_result['elasticity']

    # Гипотетические результаты при другой цене
    volume_change_pct = e * price_change_pct
    hypothetical_sales = actual['total_sales'] * (1 + volume_change_pct / 100)
    hypothetical_sales = max(hypothetical_sales, 0)

    avg_margin_per_unit = actual['total_margin'] / (actual['total_sales'] + 1e-10)
    price_delta = actual['avg_price'] * price_change_pct / 100
    hypothetical_margin_per_unit = avg_margin_per_unit + price_delta
    hypothetical_margin = hypothetical_margin_per_unit * hypothetical_sales

    hypothetical_price = actual['avg_price'] * (1 + price_change_pct / 100)
    hypothetical_revenue = hypothetical_price * hypothetical_sales
    hypothetical_margin_pct = (
        hypothetical_margin / (hypothetical_revenue + 1e-10) * 100
        if hypothetical_revenue > 0 else 0
    )

    hypothetical = {
        'total_margin': round(hypothetical_margin, 0),
        'total_revenue': round(hypothetical_revenue, 0),
        'total_sales': round(hypothetical_sales, 0),
        'avg_price': round(hypothetical_price, 2),
        'avg_margin_pct': round(hypothetical_margin_pct, 2),
    }

    # Дельта
    delta = {
        'margin_difference': round(hypothetical_margin - actual['total_margin'], 0),
        'revenue_difference': round(hypothetical_revenue - actual['total_revenue'], 0),
        'sales_difference': round(hypothetical_sales - actual['total_sales'], 0),
        'would_have_been_better': hypothetical_margin > actual['total_margin'],
    }

    return {
        'model': model,
        'channel': channel,
        'price_change_pct': price_change_pct,
        'period': {'start': period_start, 'end': period_end},
        'elasticity': elasticity_result,
        'actual': actual,
        'hypothetical': hypothetical,
        'delta': delta,
    }


def compare_price_change_periods(
    data: list[dict],
    change_date: str,
    days_before: int = 14,
    days_after: int = 14,
) -> dict:
    """
    Сравнение периодов до и после ценового изменения.

    Полезно для оценки эффекта ценовых изменений, которые уже произошли.
    """
    df = pd.DataFrame(data)
    df['date'] = pd.to_datetime(df['date'])
    change_dt = pd.to_datetime(change_date)

    before = df[(df['date'] < change_dt) & (df['date'] >= change_dt - pd.Timedelta(days=days_before))]
    after = df[(df['date'] >= change_dt) & (df['date'] < change_dt + pd.Timedelta(days=days_after))]

    if len(before) < 3 or len(after) < 3:
        return {'error': 'insufficient_data_around_change_date'}

    metrics = ['price_per_unit', 'sales_count', 'margin', 'margin_pct',
               'revenue_before_spp', 'spp_pct', 'drr_pct']

    comparison = {}
    for m in metrics:
        if m not in df.columns:
            continue
        before_val = float(before[m].mean())
        after_val = float(after[m].mean())
        change = (after_val - before_val) / (abs(before_val) + 1e-10) * 100
        comparison[m] = {
            'before': round(before_val, 2),
            'after': round(after_val, 2),
            'change_pct': round(change, 2),
        }

    return {
        'change_date': change_date,
        'days_before': len(before),
        'days_after': len(after),
        'comparison': comparison,
    }
