"""
ROI Optimizer — оптимизация цен на основе годового ROI.

Ключевая идея: высокая маржа при низкой оборачиваемости = замороженные деньги
в стоке. Настоящая эффективность — это баланс маржинальности и скорости
оборота, выраженный формулой:

    annual_roi = margin_pct * (365 / turnover_days)

Модуль реализует:
- compute_annual_roi: расчёт годового ROI
- find_optimal_price_for_roi: grid search оптимальной цены по ROI
- compute_model_roi_dashboard: дашборд ROI по моделям
- generate_roi_optimization_plan: план оптимизации с приоритизацией
"""
import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# --- Пороги ROI-категорий ---
ROI_LEADER_THRESHOLD = 500.0
ROI_HEALTHY_THRESHOLD = 200.0
ROI_UNDERPERFORMER_THRESHOLD = 50.0

# --- Минимальная маржинальность (hard floor) ---
MIN_MARGIN_PCT = 15.0


def compute_annual_roi(margin_pct: float, turnover_days: float) -> float:
    """
    Расчёт годового ROI на основе маржинальности и оборачиваемости.

    Формула: annual_roi = margin_pct * (365 / turnover_days)

    Args:
        margin_pct: маржинальность в процентах (например, 30.0 = 30%)
        turnover_days: среднее количество дней до продажи единицы стока

    Returns:
        Годовой ROI в процентах. 0 если turnover_days <= 0.
    """
    if turnover_days <= 0:
        return 0.0
    return margin_pct * (365.0 / turnover_days)


def find_optimal_price_for_roi(
    current_data: dict,
    elasticity: float,
    turnover_days: float,
    avg_stock: float,
    price_range_pct: tuple[float, float] = (-20, 20),
    step_pct: float = 1.0,
) -> dict:
    """
    Grid search оптимальной цены, максимизирующей годовой ROI.

    Перебирает варианты изменения цены в заданном диапазоне и для каждого
    рассчитывает новый объём продаж (через эластичность), маржу, оборачиваемость
    и итоговый ROI. Сценарии с маржинальностью < 15% отбрасываются.

    Args:
        current_data: dict с ключами:
            - price_per_unit: текущая цена за единицу
            - sales_per_day: текущие продажи в день (шт.)
            - margin_per_day: текущая маржа в день (руб.)
            - margin_pct: текущая маржинальность (%)
        elasticity: коэффициент ценовой эластичности (β из log-log регрессии)
        turnover_days: текущая оборачиваемость (дни)
        avg_stock: средний остаток на складе (шт.)
        price_range_pct: диапазон изменения цены (мин%, макс%)
        step_pct: шаг перебора (%)

    Returns:
        dict с ключами: optimal_price_change_pct, optimal_price,
        current_annual_roi, optimal_annual_roi, improvement_pct, all_scenarios
    """
    current_price = current_data['price_per_unit']
    current_sales = current_data['sales_per_day']
    current_margin_per_day = current_data['margin_per_day']
    current_margin_pct = current_data['margin_pct']

    # Маржа на единицу = маржа в день / продажи в день
    current_margin_per_unit = (
        current_margin_per_day / current_sales if current_sales > 0 else 0.0
    )

    # Текущий ROI
    current_annual_roi = compute_annual_roi(current_margin_pct, turnover_days)

    # Grid search
    all_scenarios = []
    best_scenario = None
    best_roi = -np.inf

    pct_values = np.arange(
        price_range_pct[0],
        price_range_pct[1] + step_pct * 0.5,  # включить правую границу
        step_pct,
    )

    for pct in pct_values:
        pct = float(round(pct, 2))

        # 1. Новая цена
        new_price = current_price * (1 + pct / 100.0)

        # 2. Изменение объёма через эластичность
        volume_change_pct = elasticity * pct

        # 3. Новые продажи
        new_sales = max(0.0, current_sales * (1 + volume_change_pct / 100.0))

        # 4. Маржа на единицу (COGS фиксирован)
        margin_per_unit = current_margin_per_unit + (new_price - current_price)

        # 5. Маржа в день
        new_margin_per_day = margin_per_unit * new_sales

        # 6. Маржинальность (%)
        if new_sales > 0 and new_price * new_sales > 0:
            new_margin_pct = new_margin_per_day / (new_price * new_sales) * 100.0
        else:
            new_margin_pct = 0.0

        # 7. Новая оборачиваемость
        if new_sales > 0:
            new_turnover_days = avg_stock / new_sales
        else:
            new_turnover_days = 9999.0

        # 8. Новый ROI
        if new_turnover_days > 0:
            new_roi = new_margin_pct * (365.0 / new_turnover_days)
        else:
            new_roi = 0.0

        scenario = {
            'price_change_pct': pct,
            'new_price': round(new_price, 2),
            'new_sales_per_day': round(new_sales, 3),
            'margin_per_unit': round(margin_per_unit, 2),
            'new_margin_per_day': round(new_margin_per_day, 2),
            'new_margin_pct': round(new_margin_pct, 2),
            'new_turnover_days': round(new_turnover_days, 1),
            'new_annual_roi': round(new_roi, 2),
        }
        all_scenarios.append(scenario)

        # Пропускаем сценарии с маржой ниже порога
        if new_margin_pct < MIN_MARGIN_PCT:
            continue

        if new_roi > best_roi:
            best_roi = new_roi
            best_scenario = scenario

    # Если ни один сценарий не прошёл фильтр — текущее состояние
    if best_scenario is None:
        logger.warning(
            'Ни один сценарий не прошёл фильтр маржинальности (>%.0f%%). '
            'Возвращаем текущее состояние.',
            MIN_MARGIN_PCT,
        )
        optimal_pct = 0.0
        optimal_price = current_price
        optimal_roi = current_annual_roi
    else:
        optimal_pct = best_scenario['price_change_pct']
        optimal_price = best_scenario['new_price']
        optimal_roi = best_scenario['new_annual_roi']

    improvement_pct = (
        (optimal_roi - current_annual_roi) / current_annual_roi * 100.0
        if current_annual_roi > 0
        else 0.0
    )

    return {
        'optimal_price_change_pct': optimal_pct,
        'optimal_price': round(optimal_price, 2),
        'current_annual_roi': round(current_annual_roi, 2),
        'optimal_annual_roi': round(optimal_roi, 2),
        'improvement_pct': round(improvement_pct, 2),
        'all_scenarios': all_scenarios,
    }


def _assign_roi_category(annual_roi: float, sales_trend: str = 'stable') -> str:
    """Присвоение категории модели по уровню ROI.

    Если модель попадает в deadstock_risk но продажи растут —
    переклассифицируем в underperformer (Charlotte fix).
    """
    if annual_roi > ROI_LEADER_THRESHOLD:
        return 'roi_leader'
    elif annual_roi >= ROI_HEALTHY_THRESHOLD:
        return 'healthy'
    elif annual_roi >= ROI_UNDERPERFORMER_THRESHOLD:
        return 'underperformer'
    else:
        if sales_trend == 'growth':
            return 'underperformer'
        return 'deadstock_risk'


def _generate_recommendation(category: str, margin_pct: float, turnover_days: float) -> str:
    """Генерация краткой текстовой рекомендации на основе категории ROI."""
    if category == 'roi_leader':
        return 'Лидер ROI. Поддерживать текущую стратегию, контролировать наличие стока.'
    elif category == 'healthy':
        if turnover_days > 30:
            return (
                'Здоровый ROI, но оборачиваемость можно улучшить. '
                'Рассмотреть стимулирование продаж.'
            )
        return 'Здоровый ROI. Мониторить стабильность маржи и оборачиваемости.'
    elif category == 'underperformer':
        if margin_pct < 20:
            return (
                'Низкая маржа тянет ROI вниз. '
                'Рассмотреть повышение цены или снижение себестоимости.'
            )
        if turnover_days > 60:
            return (
                'Высокая оборачиваемость убивает ROI. '
                'Снизить цену для ускорения продаж.'
            )
        return 'ROI ниже нормы. Провести анализ эластичности и скорректировать цену.'
    else:
        if turnover_days > 90:
            return (
                'Риск мёртвого стока. '
                'Рассмотреть агрессивную скидку или вывод из ассортимента.'
            )
        return 'Крайне низкий ROI. Требуется срочный пересмотр ценовой стратегии.'


def compute_model_roi_dashboard(
    models_data: list[dict],
    turnover_data: dict,
    sales_trends: dict = None,  # NEW: {model: {trend: str, growth_pct: float}}
) -> list[dict]:
    """
    Дашборд ROI по моделям: расчёт годового ROI, категоризация, рекомендации.

    Args:
        models_data: список dict из get_*_price_margin_by_model_period.
            Ключи: model, avg_price_per_unit, sales_count, margin, margin_pct, revenue
        turnover_data: dict {model: {turnover_days, avg_stock, daily_sales, ...}}
            из get_*_turnover_by_model

    Returns:
        Список dict отсортированный по annual_roi (убывание) с ключами:
        model, margin_pct, turnover_days, annual_roi, category,
        avg_stock, daily_sales, recommendation
    """
    dashboard = []

    for model_row in models_data:
        model = model_row.get('model', '')
        margin_pct = float(model_row.get('margin_pct', 0))

        # Данные оборачиваемости
        turnover_info = turnover_data.get(model, {})
        turnover_days = float(turnover_info.get('turnover_days', 9999))
        avg_stock = float(turnover_info.get('avg_stock', 0))
        daily_sales = float(turnover_info.get('daily_sales', 0))

        # Годовой ROI
        annual_roi = compute_annual_roi(margin_pct, turnover_days)

        # Категория
        model_trend = 'stable'
        if sales_trends:
            trend_info = sales_trends.get(model, {})
            model_trend = trend_info.get('trend', 'stable')
        category = _assign_roi_category(annual_roi, sales_trend=model_trend)

        # Рекомендация
        recommendation = _generate_recommendation(category, margin_pct, turnover_days)

        dashboard.append({
            'model': model,
            'margin_pct': round(margin_pct, 2),
            'turnover_days': round(turnover_days, 1),
            'annual_roi': round(annual_roi, 2),
            'category': category,
            'avg_stock': round(avg_stock, 1),
            'daily_sales': round(daily_sales, 2),
            'recommendation': recommendation,
        })

    # Сортировка: лучший ROI первым
    dashboard.sort(key=lambda x: x['annual_roi'], reverse=True)

    logger.info(
        'ROI дашборд: %d моделей, лидеров=%d, здоровых=%d, отстающих=%d, deadstock=%d',
        len(dashboard),
        sum(1 for d in dashboard if d['category'] == 'roi_leader'),
        sum(1 for d in dashboard if d['category'] == 'healthy'),
        sum(1 for d in dashboard if d['category'] == 'underperformer'),
        sum(1 for d in dashboard if d['category'] == 'deadstock_risk'),
    )

    return dashboard


def generate_roi_optimization_plan(
    models_data: list[dict],
    elasticities: dict,
    turnover_data: dict,
    stock_data: dict,
) -> dict:
    """
    Генерация плана оптимизации цен для максимизации ROI по всем моделям.

    Для каждой модели с валидной эластичностью:
    1. Определяет текущее состояние (маржа, оборачиваемость, ROI)
    2. Ищет оптимальную цену через grid search
    3. Рассчитывает приоритет = |roi_improvement_pct| * revenue_weight

    Args:
        models_data: список dict из get_*_price_margin_by_model_period
        elasticities: dict {model: {elasticity: float, ...}}
        turnover_data: dict {model: {turnover_days, avg_stock, daily_sales, ...}}
        stock_data: dict {model: {avg_stock, ...}} — данные по остаткам

    Returns:
        dict с ключами:
        - models: список моделей с текущим состоянием, оптимумом, приоритетом
        - total_roi_improvement: средневзвешенное улучшение ROI (%)
        - summary: текстовое резюме плана
    """
    # Общая выручка для расчёта весов
    total_revenue = sum(float(m.get('revenue', 0)) for m in models_data)
    if total_revenue <= 0:
        total_revenue = 1.0  # защита от деления на ноль

    plan_models = []

    for model_row in models_data:
        model = model_row.get('model', '')
        revenue = float(model_row.get('revenue', 0))
        revenue_weight = revenue / total_revenue

        # Проверяем наличие эластичности
        elasticity_info = elasticities.get(model, {})
        elasticity_value = elasticity_info.get('elasticity')

        if elasticity_value is None:
            logger.debug('Модель %s: нет данных по эластичности, пропускаем.', model)
            continue

        elasticity_value = float(elasticity_value)

        # Текущие данные
        margin_pct = float(model_row.get('margin_pct', 0))
        price_per_unit = float(model_row.get('avg_price_per_unit', 0))
        sales_count = float(model_row.get('sales_count', 0))
        margin_total = float(model_row.get('margin', 0))

        turnover_info = turnover_data.get(model, {})
        turnover_days = float(turnover_info.get('turnover_days', 9999))
        daily_sales = float(turnover_info.get('daily_sales', 0))

        # avg_stock: приоритет — stock_data, fallback — turnover_data
        stock_info = stock_data.get(model, {})
        avg_stock = float(
            stock_info.get('avg_stock', turnover_info.get('avg_stock', 0))
        )

        if price_per_unit <= 0 or daily_sales <= 0:
            logger.debug('Модель %s: нет цены или продаж, пропускаем.', model)
            continue

        # Маржа в день
        # sales_count — суммарные продажи за период; нужна маржа в день
        margin_per_day = margin_total / max(sales_count, 1) * daily_sales

        current_data = {
            'price_per_unit': price_per_unit,
            'sales_per_day': daily_sales,
            'margin_per_day': margin_per_day,
            'margin_pct': margin_pct,
        }

        # Оптимизация
        optimal = find_optimal_price_for_roi(
            current_data=current_data,
            elasticity=elasticity_value,
            turnover_days=turnover_days,
            avg_stock=avg_stock,
        )

        roi_improvement_pct = optimal.get('improvement_pct', 0.0)
        priority = abs(roi_improvement_pct) * revenue_weight

        # Ожидаемое изменение маржи в месяц
        expected_margin_impact_monthly = 0.0
        if optimal['all_scenarios']:
            # Находим сценарий с оптимальным изменением
            opt_pct = optimal['optimal_price_change_pct']
            opt_scenario = next(
                (
                    s for s in optimal['all_scenarios']
                    if abs(s['price_change_pct'] - opt_pct) < 0.01
                ),
                None,
            )
            if opt_scenario:
                expected_margin_impact_monthly = round(
                    (opt_scenario['new_margin_per_day'] - margin_per_day) * 30, 2
                )

        plan_models.append({
            'model': model,
            'current_state': {
                'price_per_unit': round(price_per_unit, 2),
                'daily_sales': round(daily_sales, 2),
                'margin_pct': round(margin_pct, 2),
                'turnover_days': round(turnover_days, 1),
                'annual_roi': optimal['current_annual_roi'],
                'revenue_weight': round(revenue_weight, 4),
            },
            'optimal': {
                'price_change_pct': optimal['optimal_price_change_pct'],
                'optimal_price': optimal['optimal_price'],
                'optimal_annual_roi': optimal['optimal_annual_roi'],
                'improvement_pct': optimal['improvement_pct'],
            },
            'priority': round(priority, 4),
            'expected_margin_impact_monthly': expected_margin_impact_monthly,
        })

    # Сортировка по приоритету (убывание)
    plan_models.sort(key=lambda x: x['priority'], reverse=True)

    # Средневзвешенное улучшение ROI
    total_weighted_improvement = sum(
        m['optimal']['improvement_pct'] * m['current_state']['revenue_weight']
        for m in plan_models
    )

    # Резюме
    n_total = len(plan_models)
    n_improve = sum(1 for m in plan_models if m['optimal']['improvement_pct'] > 1)
    n_reduce = sum(1 for m in plan_models if m['optimal']['price_change_pct'] < -0.5)
    n_increase = sum(1 for m in plan_models if m['optimal']['price_change_pct'] > 0.5)
    total_monthly_impact = sum(m['expected_margin_impact_monthly'] for m in plan_models)

    summary = (
        f'Проанализировано {n_total} моделей с валидной эластичностью. '
        f'Для {n_improve} моделей найден потенциал улучшения ROI. '
        f'Рекомендуется снизить цену у {n_reduce} моделей, повысить у {n_increase}. '
        f'Средневзвешенное улучшение ROI: {total_weighted_improvement:+.1f}%. '
        f'Ожидаемое изменение маржи: {total_monthly_impact:+,.0f} руб./мес.'
    )

    logger.info('ROI план: %s', summary)

    return {
        'models': plan_models,
        'total_roi_improvement': round(total_weighted_improvement, 2),
        'summary': summary,
    }
