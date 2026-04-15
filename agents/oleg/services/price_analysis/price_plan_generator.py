"""
Price Plan Generator — оркестратор ценовой аналитики.

Объединяет все модули price_analysis в единый план управления ценами:
1. Данные из data_layer (метрики, остатки, оборачиваемость)
2. Эластичность из regression_engine
3. ROI из roi_optimizer
4. Stock constraints из stock_price_optimizer
5. Рекомендации из recommendation_engine
6. Гипотезы из hypothesis_tester

Главная функция: generate_price_management_plan(channel, period_start, period_end)
"""
import logging
from datetime import timedelta

from agents.oleg.services.time_utils import get_now_msk

from shared.data_layer import (
    get_wb_price_margin_daily,
    get_ozon_price_margin_daily,
    get_wb_price_margin_by_model_period,
    get_ozon_price_margin_by_model_period,
    get_wb_turnover_by_model,
    get_ozon_turnover_by_model,
)
from agents.oleg.services.price_analysis.regression_engine import (
    estimate_price_elasticity,
)
from agents.oleg.services.price_analysis.recommendation_engine import (
    generate_recommendations,
)
from agents.oleg.services.price_analysis.roi_optimizer import (
    compute_annual_roi,
    compute_model_roi_dashboard,
    find_optimal_price_for_roi,
)
from agents.oleg.services.price_analysis.stock_price_optimizer import (
    assess_stock_health,
    generate_stock_aware_recommendation,
    generate_stock_price_matrix,
)

logger = logging.getLogger(__name__)

# Минимум дней данных для анализа
MIN_DAYS_FOR_ANALYSIS = 14
# Период для эластичности (чем больше, тем точнее)
ELASTICITY_LOOKBACK_DAYS = 180


def generate_price_management_plan(
    channel: str,
    period_start: str = None,
    period_end: str = None,
    learning_store=None,
) -> dict:
    """
    Генерация полного плана управления ценами для канала.

    Шаги:
    1. Получить метрики всех моделей
    2. Получить остатки и оборачиваемость
    3. Рассчитать эластичность для каждой модели (с кэшем)
    4. Рассчитать annual ROI
    5. Сгенерировать stock-aware рекомендации
    6. Составить приоритизированный план действий

    Args:
        channel: 'wb' или 'ozon'
        period_start: начало периода анализа (YYYY-MM-DD), default = -30 дней
        period_end: конец периода (YYYY-MM-DD), default = вчера
        learning_store: LearningStore для кэширования (опционально)

    Returns:
        dict с полным планом: models, roi_dashboard, stock_matrix,
        priority_actions, summary
    """
    # Даты по умолчанию
    now_msk = get_now_msk()
    if period_end is None:
        period_end = (now_msk - timedelta(days=1)).strftime('%Y-%m-%d')
    if period_start is None:
        period_start = (now_msk - timedelta(days=30)).strftime('%Y-%m-%d')

    # Широкий период для эластичности
    elasticity_start = (
        now_msk - timedelta(days=ELASTICITY_LOOKBACK_DAYS)
    ).strftime('%Y-%m-%d')

    logger.info(
        "Генерация ценового плана: channel=%s, period=%s — %s",
        channel, period_start, period_end,
    )

    # ─── Шаг 1: Метрики всех моделей ──────────────────────────────
    if channel == 'wb':
        models_period = get_wb_price_margin_by_model_period(period_start, period_end)
    else:
        models_period = get_ozon_price_margin_by_model_period(period_start, period_end)

    if not models_period:
        return {
            'channel': channel,
            'error': 'no_model_data',
            'period': f'{period_start} — {period_end}',
        }

    model_names = [m['model'] for m in models_period if m.get('model')]

    logger.info("Найдено %d моделей для канала %s", len(model_names), channel)

    # ─── Шаг 2: Остатки и оборачиваемость ─────────────────────────
    try:
        if channel == 'wb':
            turnover_data = get_wb_turnover_by_model(period_start, period_end)
        else:
            turnover_data = get_ozon_turnover_by_model(period_start, period_end)
    except Exception as e:
        logger.warning("Не удалось получить оборачиваемость: %s", e)
        turnover_data = {}

    # ─── Шаг 3: Эластичность для каждой модели ────────────────────
    elasticities = {}
    models_daily_data = {}

    for model_name in model_names:
        # Данные за широкий период
        try:
            if channel == 'wb':
                daily_data = get_wb_price_margin_daily(
                    elasticity_start, period_end, model_name
                )
            else:
                daily_data = get_ozon_price_margin_daily(
                    elasticity_start, period_end, model_name
                )
        except Exception as e:
            logger.warning("Ошибка данных для %s: %s", model_name, e)
            continue

        if not daily_data or len(daily_data) < MIN_DAYS_FOR_ANALYSIS:
            continue

        models_daily_data[model_name] = daily_data

        # Проверить кэш
        cached = None
        if learning_store:
            cached = learning_store.get_elasticity_cached(model_name, channel)

        if cached and 'error' not in cached:
            elasticities[model_name] = cached
        else:
            result = estimate_price_elasticity(daily_data)
            if 'error' not in result:
                elasticities[model_name] = result
                # Сохранить в кэш
                if learning_store:
                    try:
                        learning_store.cache_elasticity(
                            model_name, channel, result,
                            elasticity_start, period_end,
                        )
                    except Exception as e:
                        logger.warning("Не удалось закэшировать эластичность %s: %s", model_name, e)

    logger.info(
        "Эластичность рассчитана для %d из %d моделей",
        len(elasticities), len(model_names),
    )

    # ─── Шаг 4: ROI дашборд ───────────────────────────────────────
    roi_dashboard = compute_model_roi_dashboard(models_period, turnover_data)

    # Сохранить ROI снапшоты
    if learning_store:
        for row in roi_dashboard:
            try:
                learning_store.save_roi_snapshot(
                    model=row['model'],
                    channel=channel,
                    snapshot={
                        'margin_pct': row['margin_pct'],
                        'turnover_days': row['turnover_days'],
                        'annual_roi': row['annual_roi'],
                        'avg_stock': row['avg_stock'],
                        'daily_sales': row['daily_sales'],
                    },
                )
            except Exception as e:
                logger.warning("Не удалось сохранить ROI snapshot %s: %s", row['model'], e)

    # ─── Шаг 5: Stock health ──────────────────────────────────────
    stock_health_map = {}
    for model_name in model_names:
        t_info = turnover_data.get(model_name, {})
        t_days = t_info.get('turnover_days', 0)
        avg_stock = t_info.get('avg_stock', 0)
        daily_sales = t_info.get('daily_sales', 0)

        if avg_stock > 0 or daily_sales > 0:
            stock_health_map[model_name] = assess_stock_health(
                t_days, avg_stock, daily_sales
            )

    # Stock-price матрица
    stock_matrix = generate_stock_price_matrix(
        models_period,
        {m: turnover_data.get(m, {}).get('avg_stock', 0) for m in model_names},
        turnover_data,
        elasticities,
    )

    # ─── Шаг 6: Рекомендации с наложением stock constraints ──────
    plan_models = []

    for model_row in models_period:
        model_name = model_row.get('model', '')
        if not model_name:
            continue

        daily_data = models_daily_data.get(model_name)
        if not daily_data or len(daily_data) < MIN_DAYS_FOR_ANALYSIS:
            plan_models.append({
                'model': model_name,
                'status': 'insufficient_data',
                'n_days': len(daily_data) if daily_data else 0,
            })
            continue

        # Базовая рекомендация
        elasticity = elasticities.get(model_name)
        t_info = turnover_data.get(model_name, {})
        t_days = t_info.get('turnover_days')

        rec = generate_recommendations(
            data=daily_data,
            model=model_name,
            channel=channel,
            elasticity_result=elasticity,
            stock_health=stock_health_map.get(model_name),
            turnover_days=t_days,
        )

        # Stock-aware overlay
        stock_health = stock_health_map.get(model_name)
        if stock_health and 'error' not in rec:
            rec = generate_stock_aware_recommendation(
                rec, stock_health, t_days or 0
            )

        # ROI оптимизация
        roi_optimization = None
        if (
            elasticity
            and 'error' not in elasticity
            and t_days
            and t_days > 0
        ):
            avg_stock = t_info.get('avg_stock', 0)
            current_metrics = rec.get('current_metrics', {})
            if current_metrics.get('price_per_unit') and current_metrics.get('sales_per_day'):
                roi_optimization = find_optimal_price_for_roi(
                    current_data=current_metrics,
                    elasticity=elasticity['elasticity'],
                    turnover_days=t_days,
                    avg_stock=avg_stock,
                )
                # Не включаем all_scenarios в план (слишком объёмно)
                if roi_optimization:
                    roi_optimization.pop('all_scenarios', None)

        # Текущее состояние
        current_state = {
            'price': model_row.get('avg_price_per_unit'),
            'margin_pct': model_row.get('margin_pct'),
            'turnover_days': t_days,
            'daily_sales': t_info.get('daily_sales'),
            'avg_stock': t_info.get('avg_stock'),
        }

        # Annual ROI
        if current_state['margin_pct'] and t_days and t_days > 0:
            current_state['annual_roi'] = round(
                compute_annual_roi(current_state['margin_pct'], t_days), 2
            )

        # Stock status
        if stock_health:
            current_state['stock_status'] = stock_health.get('status')
            current_state['weeks_supply'] = stock_health.get('weeks_supply')

        # Приоритет = |margin_impact| × revenue_weight
        margin_impact = 0
        if 'error' not in rec:
            margin_impact = abs(
                rec.get('recommended', {}).get(
                    'predicted_impact', {}
                ).get('margin_rub_change_per_day', 0) or 0
            )

        revenue = float(model_row.get('revenue', 0))

        plan_models.append({
            'model': model_name,
            'status': 'analyzed',
            'current_state': current_state,
            'recommendation': {
                'action': rec.get('action', 'hold'),
                'change_pct': rec.get('recommended', {}).get('price_change_pct'),
                'new_price': rec.get('recommended', {}).get('new_price'),
                'reasoning': rec.get('recommended', {}).get('reasoning', ''),
                'confidence': rec.get('confidence', 'low'),
                'stock_override': rec.get('stock_override', False),
                'stock_reasoning': rec.get('stock_reasoning', ''),
            },
            'roi_optimization': roi_optimization,
            'risk_factors': rec.get('risk_factors', []),
            'priority': round(margin_impact, 0),
            'expected_margin_impact_daily': round(
                rec.get('recommended', {}).get(
                    'predicted_impact', {}
                ).get('margin_rub_change_per_day', 0) or 0, 0
            ),
            'revenue': round(revenue, 0),
        })

    # Сортировка по приоритету
    plan_models.sort(key=lambda x: x.get('priority', 0), reverse=True)

    # ─── Summary ──────────────────────────────────────────────────
    analyzed = [m for m in plan_models if m.get('status') == 'analyzed']
    actions = {
        'increase': sum(1 for m in analyzed if m['recommendation']['action'] == 'increase_price'),
        'decrease': sum(1 for m in analyzed if m['recommendation']['action'] == 'decrease_price'),
        'hold': sum(1 for m in analyzed if m['recommendation']['action'] == 'hold'),
    }
    stock_overrides = sum(
        1 for m in analyzed if m['recommendation'].get('stock_override')
    )
    total_daily_impact = sum(
        m.get('expected_margin_impact_daily', 0) for m in analyzed
    )

    summary = (
        f"Проанализировано {len(analyzed)} моделей на канале {channel.upper()}. "
        f"Повысить цену: {actions['increase']}, снизить: {actions['decrease']}, "
        f"удерживать: {actions['hold']}. "
        f"Складских переопределений: {stock_overrides}. "
        f"Ожидаемый эффект: {total_daily_impact:+,.0f} руб./день "
        f"({total_daily_impact * 30:+,.0f} руб./мес.)."
    )

    return {
        'channel': channel,
        'period': f'{period_start} — {period_end}',
        'generated_at': get_now_msk().isoformat(),
        'models': plan_models,
        'roi_dashboard': roi_dashboard,
        'stock_matrix': stock_matrix,
        'summary': summary,
        'stats': {
            'total_models': len(model_names),
            'analyzed': len(analyzed),
            'with_elasticity': len(elasticities),
            'with_turnover': len(turnover_data),
            'with_stock_health': len(stock_health_map),
            'actions': actions,
            'stock_overrides': stock_overrides,
            'total_daily_impact': round(total_daily_impact, 0),
        },
    }


def generate_article_level_plan(
    channel: str,
    model: str,
    period_start: str = None,
    period_end: str = None,
) -> dict:
    """
    Артикульный план внутри модели (цветовые варианты).

    Анализирует каждый артикул отдельно: эластичность, рекомендации.

    Args:
        channel: 'wb' или 'ozon'
        model: имя модели
        period_start: начало периода
        period_end: конец периода

    Returns:
        dict с articles: список рекомендаций по артикулам
    """
    from shared.data_layer import (
        get_wb_price_margin_daily_by_article,
        get_ozon_price_margin_daily_by_article,
    )

    now_msk = get_now_msk()
    if period_end is None:
        period_end = (now_msk - timedelta(days=1)).strftime('%Y-%m-%d')
    if period_start is None:
        period_start = (now_msk - timedelta(days=90)).strftime('%Y-%m-%d')

    # Артикульные данные
    if channel == 'wb':
        data = get_wb_price_margin_daily_by_article(
            period_start, period_end, model=model
        )
    else:
        data = get_ozon_price_margin_daily_by_article(
            period_start, period_end, model=model
        )

    if not data:
        return {
            'channel': channel,
            'model': model,
            'error': 'no_article_data',
        }

    # Группировка по артикулу
    import pandas as pd
    df = pd.DataFrame(data)
    articles = df['article'].unique().tolist()

    article_results = []

    for article in articles:
        art_data = df[df['article'] == article].to_dict('records')

        if len(art_data) < MIN_DAYS_FOR_ANALYSIS:
            article_results.append({
                'article': article,
                'status': 'insufficient_data',
                'n_days': len(art_data),
            })
            continue

        # Эластичность
        elasticity = estimate_price_elasticity(art_data)

        # Метрики
        art_df = pd.DataFrame(art_data)
        recent = art_df.tail(7)

        current = {
            'price_per_unit': round(float(recent['price_per_unit'].mean()), 2),
            'sales_per_day': round(float(recent['sales_count'].mean()), 1),
            'margin_pct': round(float(recent['margin_pct'].mean()), 2),
        }

        article_results.append({
            'article': article,
            'status': 'analyzed',
            'n_days': len(art_data),
            'current': current,
            'elasticity': {
                'value': elasticity.get('elasticity'),
                'r_squared': elasticity.get('r_squared'),
                'p_value': elasticity.get('p_value'),
                'is_significant': elasticity.get('is_significant'),
                'interpretation': elasticity.get('interpretation'),
            } if 'error' not in elasticity else {'error': elasticity.get('error')},
        })

    # Сортировка: по price_per_unit (убывание)
    article_results.sort(
        key=lambda a: a.get('current', {}).get('price_per_unit', 0),
        reverse=True,
    )

    return {
        'channel': channel,
        'model': model,
        'period': f'{period_start} — {period_end}',
        'total_articles': len(articles),
        'analyzed': sum(1 for a in article_results if a['status'] == 'analyzed'),
        'articles': article_results,
    }
