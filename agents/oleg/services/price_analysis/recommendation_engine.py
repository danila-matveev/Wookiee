"""
Recommendation Engine — генерация ценовых рекомендаций.

Алгоритм:
1. Получить эластичность модели
2. Рассчитать оптимальную цену (MR = MC)
3. Применить бизнес-ограничения (маржа >= 20%, объём не падает > 10%)
4. Сгенерировать сценарии (+5%, +10%, -5%, -10%)
5. Ранжировать по прогнозу маржинальной прибыли (₽)
"""
import logging
from datetime import datetime
from agents.oleg.services.time_utils import get_now_msk

import numpy as np
import pandas as pd

from agents.oleg.services.price_analysis.regression_engine import (
    estimate_price_elasticity,
    run_full_analysis,
)
from agents.oleg.services.price_analysis.roi_optimizer import compute_annual_roi

logger = logging.getLogger(__name__)

# Бизнес-ограничения (из playbook)
MIN_MARGIN_PCT = 20.0       # Минимальная маржинальность %
MAX_VOLUME_LOSS_PCT = 10.0  # Максимально допустимая потеря объёма %
SCENARIO_STEPS = [-10, -5, -3, 3, 5, 10]  # Сценарии изменения цены %


def generate_recommendations(
    data: list[dict],
    model: str,
    channel: str,
    elasticity_result: dict = None,
    stock_health: dict = None,
    turnover_days: float = None,
) -> dict:
    """
    Генерация ценовых рекомендаций для модели.

    Args:
        data: ежедневные данные из get_*_price_margin_daily()
        model: имя модели (lowercase)
        channel: 'wb' или 'ozon'
        elasticity_result: предвычисленная эластичность (опционально)

    Returns:
        dict с рекомендациями, сценариями, обоснованием.
    """
    if len(data) < 14:
        return {
            'model': model,
            'channel': channel,
            'error': 'insufficient_data',
            'n_days': len(data),
        }

    df = pd.DataFrame(data)

    # Текущие метрики (последние 7 дней)
    recent = df.tail(7)
    current = {
        'price_per_unit': round(float(recent['price_per_unit'].mean()), 2),
        'sales_per_day': round(float(recent['sales_count'].mean()), 1),
        'margin_per_day': round(float(recent['margin'].mean()), 0),
        'margin_pct': round(float(recent['margin_pct'].mean()), 2),
        'revenue_per_day': round(float(recent['revenue_before_spp'].mean()), 0),
    }

    # Эластичность
    if elasticity_result is None:
        elasticity_result = estimate_price_elasticity(data)

    if 'error' in elasticity_result:
        return {
            'model': model,
            'channel': channel,
            'current_metrics': current,
            'error': f'elasticity_error: {elasticity_result["error"]}',
        }

    elasticity = elasticity_result.get('elasticity', 0)

    # ====== Quality Gates: делегируем к selection_status из оркестратора ======
    selection_status = elasticity_result.get('selection_status')
    reason_code = elasticity_result.get('reason_code', '')

    allowed_statuses = {'PASS', 'DEPRECATED_FALLBACK'}

    # Если оркестратор вернул блокировку — формируем human-readable reason
    if selection_status and selection_status not in allowed_statuses:
        gate_status = selection_status
        reason_map = {
            'insufficient_data': f"INSUFFICIENT_DATA. Слишком мало наблюдений или низкое покрытие дат.",
            'low_price_variation': f"FAIL. Недостаточная вариация цены (мало уникальных цен / изменений / диапазон).",
            'low_predictive_power': f"FAIL. Модель не превосходит Naive Baseline на ≥10% WAPE или переобучена.",
            'positive_elasticity': f"CONFOUNDED. Положительная эластичность ({elasticity}). Модель не идентифицирована.",
        }
        gate_reason = reason_map.get(reason_code, f"{gate_status}: {reason_code}")
        return {
            'model': model,
            'channel': channel,
            'timestamp': get_now_msk().isoformat(),
            'action': 'hold',
            'current_metrics': current,
            'elasticity': elasticity_result,
            'quality_status': gate_status,
            'reason_code': reason_code,
            'selected_model': elasticity_result.get('selected_model', 'none'),
            'backtest_results': elasticity_result.get('backtest_results', {}),
            'scenarios': [],
            'recommended': {
                'action': 'hold',
                'reasoning': gate_reason,
            },
        }

    # Fallback: если selection_status отсутствует (старый API) — применяем legacy-проверки
    if not selection_status:
        quality_metrics = elasticity_result.get('quality_metrics', {})
        n_obs = elasticity_result.get('n_observations', 0)
        if n_obs < 30 or quality_metrics.get('low_date_coverage', False):
            gate_reason = f"INSUFFICIENT_DATA. Мало наблюдений ({n_obs}) или низкое покрытие дат."
            return {
                'model': model, 'channel': channel,
                'timestamp': get_now_msk().isoformat(), 'action': 'hold',
                'current_metrics': current, 'elasticity': elasticity_result,
                'quality_status': 'INSUFFICIENT_DATA', 'scenarios': [],
                'recommended': {'action': 'hold', 'reasoning': gate_reason},
            }
        if quality_metrics.get('insufficient_unique_prices') or quality_metrics.get('low_price_range') or quality_metrics.get('insufficient_price_changes'):
            gate_reason = "FAIL. Недостаточная вариация цены."
            return {
                'model': model, 'channel': channel,
                'timestamp': get_now_msk().isoformat(), 'action': 'hold',
                'current_metrics': current, 'elasticity': elasticity_result,
                'quality_status': 'FAIL', 'scenarios': [],
                'recommended': {'action': 'hold', 'reasoning': gate_reason},
            }
        if quality_metrics.get('is_confounded', False) or elasticity > 0:
            gate_reason = f"CONFOUNDED. Положительная эластичность ({elasticity})."
            return {
                'model': model, 'channel': channel,
                'timestamp': get_now_msk().isoformat(), 'action': 'hold',
                'current_metrics': current, 'elasticity': elasticity_result,
                'quality_status': 'CONFOUNDED', 'scenarios': [],
                'recommended': {'action': 'hold', 'reasoning': gate_reason},
            }
    # ====== Конец Quality Gates ======


    # Генерация сценариев
    scenarios = []
    for pct in SCENARIO_STEPS:
        scenario = _simulate_scenario(
            current=current,
            price_change_pct=pct,
            elasticity=elasticity,
        )
        scenarios.append(scenario)

    # Найти лучший сценарий по маржинальной прибыли
    valid_scenarios = [s for s in scenarios if s['passes_constraints']]

    if valid_scenarios:
        best = max(valid_scenarios, key=lambda s: s['predicted_margin_per_day'])
        action = 'increase_price' if best['price_change_pct'] > 0 else 'decrease_price'
    else:
        best = None
        action = 'hold'

    # Определение confidence
    confidence = _assess_confidence(elasticity_result, len(data))

    # Формирование рекомендации
    recommendation = {
        'model': model,
        'channel': channel,
        'timestamp': get_now_msk().isoformat(),
        'action': action,
        'quality_status': 'PASS',
        'current_metrics': current,
        'elasticity': elasticity_result,
        'confidence': confidence,
        'scenarios': scenarios,
    }

    if best:
        recommendation['recommended'] = {
            'price_change_pct': best['price_change_pct'],
            'new_price': best['new_price'],
            'predicted_impact': {
                'margin_rub_change_per_day': round(
                    best['predicted_margin_per_day'] - current['margin_per_day'], 0
                ),
                'margin_pct_change': round(
                    best['predicted_margin_pct'] - current['margin_pct'], 2
                ),
                'volume_change_pct': best['predicted_volume_change_pct'],
                'revenue_change_pct': best['predicted_revenue_change_pct'],
            },
            'reasoning': _build_reasoning(
                elasticity_result, best, current, confidence
            ),
        }
    else:
        recommendation['recommended'] = {
            'action': 'hold',
            'reasoning': _build_hold_reasoning(elasticity_result, current, scenarios),
        }

    # Предупреждения
    recommendation['risk_factors'] = _identify_risks(
        elasticity_result, current, df
    )

    # Risk Check: Wide CI (только для PASS)
    ci = elasticity_result.get('confidence_interval_95', [0, 0])
    if len(ci) == 2:
        ci_width = ci[1] - ci[0]
        ci_ratio = ci_width / max(abs(elasticity), 0.1)
        if ci_ratio > 3.0:
            recommendation['risk_factors'].append(
                f"Wide CI: коэффициент нестабилен (CI width {ci_width:.2f}, ratio {ci_ratio:.1f})"
            )

    # ROI если есть данные оборачиваемости
    if turnover_days and turnover_days > 0:
        current_roi = compute_annual_roi(current['margin_pct'], turnover_days)
        recommendation['current_annual_roi'] = round(current_roi, 2)
        recommendation['turnover_days'] = round(turnover_days, 1)

    # Stock-aware overlay
    if stock_health:
        recommendation['stock_health'] = stock_health

    return recommendation



def _simulate_scenario(
    current: dict,
    price_change_pct: float,
    elasticity: float,
) -> dict:
    """Симуляция одного сценария изменения цены."""
    new_price = current['price_per_unit'] * (1 + price_change_pct / 100)

    # Предсказание объёма через эластичность: %ΔQ = ε × %ΔP
    volume_change_pct = elasticity * price_change_pct
    new_sales = current['sales_per_day'] * (1 + volume_change_pct / 100)
    new_sales = max(new_sales, 0)  # объём не может быть < 0

    # Предсказание выручки
    new_revenue = new_price * new_sales
    revenue_change_pct = (new_revenue - current['revenue_per_day']) / (
        current['revenue_per_day'] + 1e-10
    ) * 100

    # Предсказание маржи (упрощение: маржа% сохраняется, меняется абсолют через объём)
    # Более точно: маржа/шт растёт при росте цены (фикс. затраты на шт не меняются)
    margin_per_unit_current = (
        current['margin_per_day'] / (current['sales_per_day'] + 1e-10)
    )
    # При росте цены маржа/шт растёт на ΔP (при фикс. COGS, логистике)
    price_delta = new_price - current['price_per_unit']
    new_margin_per_unit = margin_per_unit_current + price_delta
    new_margin_per_day = new_margin_per_unit * new_sales

    new_margin_pct = (
        new_margin_per_day / (new_revenue + 1e-10) * 100 if new_revenue > 0 else 0
    )

    # Проверка ограничений
    passes_constraints = (
        new_margin_pct >= MIN_MARGIN_PCT
        and volume_change_pct >= -MAX_VOLUME_LOSS_PCT
    )

    return {
        'price_change_pct': price_change_pct,
        'new_price': round(new_price, 2),
        'predicted_volume_change_pct': round(volume_change_pct, 2),
        'predicted_sales_per_day': round(new_sales, 1),
        'predicted_revenue_per_day': round(new_revenue, 0),
        'predicted_revenue_change_pct': round(revenue_change_pct, 2),
        'predicted_margin_per_day': round(new_margin_per_day, 0),
        'predicted_margin_pct': round(new_margin_pct, 2),
        'passes_constraints': passes_constraints,
        'turnover_impact': None,  # will be filled if turnover_days is available
        'roi_impact': None,
        'constraint_violations': _check_violations(
            new_margin_pct, volume_change_pct
        ),
    }


def _check_violations(margin_pct: float, volume_change_pct: float) -> list[str]:
    """Проверить какие ограничения нарушены."""
    violations = []
    if margin_pct < MIN_MARGIN_PCT:
        violations.append(f'margin_below_{MIN_MARGIN_PCT}pct')
    if volume_change_pct < -MAX_VOLUME_LOSS_PCT:
        violations.append(f'volume_loss_above_{MAX_VOLUME_LOSS_PCT}pct')
    return violations


def _assess_confidence(elasticity_result: dict, n_days: int) -> str:
    """Оценка уверенности в рекомендации."""
    r2 = elasticity_result.get('r_squared', 0)
    p = elasticity_result.get('p_value', 1)
    is_sig = elasticity_result.get('is_significant', False)

    if is_sig and r2 >= 0.5 and n_days >= 60:
        return 'high'
    elif is_sig and r2 >= 0.3 and n_days >= 30:
        return 'medium'
    return 'low'


def _build_reasoning(
    elasticity_result: dict, best_scenario: dict, current: dict, confidence: str
) -> str:
    """Построить текстовое обоснование рекомендации."""
    e = elasticity_result['elasticity']
    interp = elasticity_result['interpretation']
    r2 = elasticity_result['r_squared']
    pct = best_scenario['price_change_pct']
    direction = 'повысить' if pct > 0 else 'снизить'

    parts = [
        f"Эластичность спроса: {e} ({interp}), R²={r2}.",
    ]

    if abs(e) < 1:
        parts.append(
            f"Спрос неэластичен — {direction} цену на {abs(pct)}% "
            f"приведёт к изменению объёма всего на {abs(best_scenario['predicted_volume_change_pct'])}%."
        )
    else:
        parts.append(
            f"Спрос эластичен — {direction} цену осторожно, "
            f"объём изменится на {best_scenario['predicted_volume_change_pct']}%."
        )

    margin_delta = best_scenario['predicted_margin_per_day'] - current['margin_per_day']
    parts.append(
        f"Прогноз: маржинальная прибыль {'+' if margin_delta > 0 else ''}"
        f"{margin_delta:.0f}₽/день."
    )

    if confidence == 'low':
        parts.append("⚠️ Низкая уверенность — рекомендуется осторожный подход.")

    return ' '.join(parts)


def _build_hold_reasoning(
    elasticity_result: dict, current: dict, scenarios: list
) -> str:
    """Обоснование для рекомендации 'hold'."""
    parts = ["Рекомендация: сохранить текущую цену."]

    if scenarios:
        violations = set()
        for s in scenarios:
            violations.update(s.get('constraint_violations', []))
        if violations:
            parts.append(f"Все сценарии нарушают ограничения: {', '.join(violations)}.")

    parts.append(
        f"Текущая маржинальность {current['margin_pct']}% "
        f"при объёме {current['sales_per_day']} шт/день."
    )

    return ' '.join(parts)


def _identify_risks(
    elasticity_result: dict, current: dict, df: pd.DataFrame
) -> list[str]:
    """Идентификация рисков для рекомендации."""
    risks = []

    if elasticity_result.get('r_squared', 0) < 0.3:
        risks.append('Низкий R² — модель плохо объясняет связь цена-объём')

    if not elasticity_result.get('is_significant', False):
        risks.append('Эластичность статистически не значима (p > 0.05)')

    if 'spp_pct' in df.columns:
        spp_std = df['spp_pct'].std()
        if spp_std > 3:
            risks.append(
                f'Высокая волатильность СПП (σ={spp_std:.1f}пп) — '
                'МП может переопределить скидку'
            )

    if current['margin_pct'] < MIN_MARGIN_PCT + 3:
        risks.append(
            f'Маржинальность близка к минимуму ({current["margin_pct"]}% при пороге {MIN_MARGIN_PCT}%)'
        )

    return risks


def generate_recommendations_batch(
    models_data: dict,
    channel: str,
    elasticities: dict = None,
    stock_data: dict = None,
    turnover_data: dict = None,
) -> dict:
    """
    Генерация рекомендаций для ВСЕХ моделей за один вызов.

    Args:
        models_data: dict {model_name: list[dict]} — дневные данные по моделям
        channel: 'wb' или 'ozon'
        elasticities: dict {model: elasticity_result} (опционально)
        stock_data: dict {model: stock_health_dict} (опционально)
        turnover_data: dict {model: {turnover_days, ...}} (опционально)

    Returns:
        dict с recommendations, priority_order, total_margin_impact
    """
    recommendations = []
    total_margin_impact = 0

    for model_name, daily_data in models_data.items():
        elasticity = (elasticities or {}).get(model_name)
        stock = (stock_data or {}).get(model_name)
        turnover_info = (turnover_data or {}).get(model_name, {})
        t_days = turnover_info.get('turnover_days')

        rec = generate_recommendations(
            data=daily_data,
            model=model_name,
            channel=channel,
            elasticity_result=elasticity,
            stock_health=stock,
            turnover_days=t_days,
        )

        if 'error' not in rec:
            predicted_impact = rec.get('recommended', {}).get(
                'predicted_impact', {}
            ).get('margin_rub_change_per_day', 0) or 0
            rec['priority_score'] = abs(predicted_impact)
            total_margin_impact += predicted_impact

        recommendations.append(rec)

    # Сортировка по приоритету
    recommendations.sort(
        key=lambda r: r.get('priority_score', 0), reverse=True
    )

    priority_order = [
        r['model'] for r in recommendations if 'error' not in r
    ]

    return {
        'channel': channel,
        'recommendations': recommendations,
        'priority_order': priority_order,
        'total_margin_impact_per_day': round(total_margin_impact, 0),
        'models_analyzed': len(recommendations),
        'models_with_recommendations': sum(
            1 for r in recommendations
            if r.get('action') != 'hold' and 'error' not in r
        ),
    }
