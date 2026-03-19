"""
Bulk Price Analysis — comprehensive price report for a long historical period.

Generates a single comprehensive report per channel with:
- Elasticity analysis per model
- Factor regression (what drives margin)
- ROI dashboard
- Price management recommendations
- Price patterns
- Hypothesis testing
- Model status awareness (phasing-out models treated differently)

All output in Russian. Saves to JSON + Notion + Telegram notification.

Usage:
    python scripts/run_price_analysis.py --start 2024-03-01 --end 2026-02-25 --channels wb,ozon
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================================
# Data helpers
# ============================================================================

def get_all_models(channel: str, start_date: str, end_date: str) -> list[str]:
    """Get all unique model names for a channel."""
    from shared.data_layer import (
        get_wb_price_margin_by_model_period,
        get_ozon_price_margin_by_model_period,
    )
    if channel == 'wb':
        models_data = get_wb_price_margin_by_model_period(start_date, end_date)
    else:
        models_data = get_ozon_price_margin_by_model_period(start_date, end_date)

    if not models_data:
        return []

    return list({m.get('model', '') for m in models_data if m.get('model')})


def get_model_data(channel: str, start_date: str, end_date: str, model: str) -> list[dict]:
    """Get daily price/margin data for a model."""
    from shared.data_layer import (
        get_wb_price_margin_daily,
        get_ozon_price_margin_daily,
    )
    if channel == 'wb':
        return get_wb_price_margin_daily(start_date, end_date, model) or []
    else:
        return get_ozon_price_margin_daily(start_date, end_date, model) or []


# ============================================================================
# Adaptive period logic
# ============================================================================

MIN_SALES_FOR_TREND = 10  # Минимум продаж модели для оценки тренда


def _pick_adaptive_period(
    channel: str,
    base_end: str,
    model_names: list[str],
) -> tuple[str, str, str]:
    """Выбрать оптимальный период анализа: 7d → 30d → 90d.

    Начинает с недели. Если для >50% моделей данных недостаточно
    (< MIN_SALES_FOR_TREND продаж), расширяет до месяца, затем квартала.

    Returns: (start_date, end_date, period_label)
    """
    from shared.data_layer import (
        get_wb_by_article, get_ozon_by_article,
    )
    from shared.model_mapping import map_to_osnova

    periods = [
        (7, '7d'),
        (30, '30d'),
        (90, '90d'),
    ]

    end_dt = datetime.strptime(base_end, '%Y-%m-%d')

    for days, label in periods:
        start_dt = end_dt - timedelta(days=days)
        start_str = start_dt.strftime('%Y-%m-%d')
        end_str = base_end

        try:
            if channel == 'wb':
                articles = get_wb_by_article(start_str, end_str)
            else:
                articles = get_ozon_by_article(start_str, end_str)
        except Exception:
            articles = []

        # Подсчёт продаж по моделям
        sales_by_model: dict[str, int] = {}
        for art in articles:
            model = map_to_osnova(art.get('model', ''))
            if model in model_names:
                sales_by_model[model] = sales_by_model.get(model, 0) + (art.get('sales_count', 0) or 0)

        # Проверяем достаточность
        sufficient = sum(1 for m in model_names if sales_by_model.get(m, 0) >= MIN_SALES_FOR_TREND)
        ratio = sufficient / len(model_names) if model_names else 0

        logger.info(
            f"[{channel}] Adaptive period {label}: {sufficient}/{len(model_names)} "
            f"models have >= {MIN_SALES_FOR_TREND} sales ({ratio:.0%})"
        )

        if ratio >= 0.5 or label == '90d':
            return start_str, end_str, label

    # Fallback (не должен дойти сюда)
    return (end_dt - timedelta(days=30)).strftime('%Y-%m-%d'), base_end, '30d'


# ============================================================================
# Pricing hypotheses generator
# ============================================================================

def _calc_scenario(
    avg_price: float,
    margin_pct: float,
    daily_sales: float,
    stock_total: float,
    change_pct: float,
    elasticity: float,
) -> dict:
    """Рассчитать один сценарий изменения цены.

    Returns dict с конкретными числами: новая цена, объём, маржа, прибыль, оборачиваемость.
    stock_total — общие остатки (МП + МойСклад).
    """
    price_delta = avg_price * change_pct / 100
    new_price = avg_price + price_delta

    # Маржа за единицу до и после
    margin_per_unit = avg_price * margin_pct / 100
    # При изменении цены маржа на единицу меняется примерно на price_delta
    # (комиссия МП ~15-20% съедает часть, берём ~80% от дельты идёт в маржу)
    COMMISSION_PASSTHROUGH = 0.80
    new_margin_per_unit = margin_per_unit + price_delta * COMMISSION_PASSTHROUGH
    new_margin_pct = (new_margin_per_unit / new_price * 100) if new_price > 0 else 0

    # Изменение объёма через эластичность
    volume_change_pct = elasticity * change_pct  # elasticity отрицательная
    new_daily_sales = daily_sales * (1 + volume_change_pct / 100)
    new_daily_sales = max(new_daily_sales, 0)

    # Прибыль в день
    daily_profit_before = daily_sales * margin_per_unit
    daily_profit_after = new_daily_sales * new_margin_per_unit
    profit_delta = daily_profit_after - daily_profit_before
    profit_delta_pct = (profit_delta / daily_profit_before * 100) if daily_profit_before > 0 else 0

    # Месячная прибыль
    monthly_profit_before = daily_profit_before * 30
    monthly_profit_after = daily_profit_after * 30
    monthly_delta = monthly_profit_after - monthly_profit_before

    # Оборачиваемость (по общим остаткам)
    turnover_before = (stock_total / daily_sales) if daily_sales > 0 else 999
    turnover_after = (stock_total / new_daily_sales) if new_daily_sales > 0 else 999
    turnover_before = min(turnover_before, 365)
    turnover_after = min(turnover_after, 365)

    return {
        'change_pct': change_pct,
        'new_price': round(new_price, 0),
        'new_margin_pct': round(new_margin_pct, 1),
        'volume_change_pct': round(volume_change_pct, 1),
        'new_daily_sales': round(new_daily_sales, 2),
        'daily_profit_before': round(daily_profit_before, 0),
        'daily_profit_after': round(daily_profit_after, 0),
        'profit_delta': round(profit_delta, 0),
        'profit_delta_pct': round(profit_delta_pct, 1),
        'monthly_delta': round(monthly_delta, 0),
        'turnover_before': round(turnover_before, 0),
        'turnover_after': round(turnover_after, 0),
    }


def _pick_assumed_elasticity(
    status: str,
    roi_category: str,
    turnover_days: float,
    spp_delta_pp: float = 0,
    has_external_ads: bool = False,
) -> float:
    """Допущение по эластичности для fashion/underwear категории.

    Базовые значения:
    - Выводим: -1.8 | Deadstock: -2.0 | Underperformer: -1.5
    - Быстрый оборот (<30 дн.): -0.7 | Средний (<60): -1.0 | Baseline: -1.2

    Модификаторы:
    - СПП растёт (>+2 п.п.): -0.2 (спрос более чувствителен при росте комиссии)
    - Внешняя реклама: +0.3 (снижает ценовую чувствительность)
    """
    if status == 'Выводим':
        base = -1.8
    elif roi_category == 'deadstock_risk':
        base = -2.0
    elif roi_category == 'underperformer':
        base = -1.5
    elif turnover_days > 0 and turnover_days < 30:
        base = -0.7
    elif turnover_days > 0 and turnover_days < 60:
        base = -1.0
    else:
        base = -1.2

    # Модификаторы
    if spp_delta_pp > 2:
        base -= 0.2  # Более эластичный при росте комиссии
    if has_external_ads:
        base += 0.3  # Менее эластичный при внешнем трафике

    return round(base, 1)


def _pick_recommended_scenario(
    scenarios: list[dict],
    status: str,
    roi_category: str,
    turnover_days: float,
    margin_pct: float,
    elasticity_source: str = 'assumed',
    has_external_ads: bool = False,
    drr_pct: float = 0,
    spp_delta_pp: float = 0,
) -> dict | None:
    """Выбрать лучший сценарий для рекомендации.

    Правила:
    - При допущенной эластичности: максимум ±5% (осторожность)
    - Выводим → снижение для ускорения распродажи (даже при низкой марже)
    - Deadstock → снижение для ускорения оборачиваемости
    - Лидеры с быстрым оборотом → повышение (до +5% если есть внешняя реклама)
    - СПП растёт → приоритет повышения цены для компенсации
    - Underperformer с низкой маржой → повышение
    """
    MIN_MARGIN_PCT = 15.0
    MAX_CHANGE = 5.0 if elasticity_source == 'assumed' else 10.0

    safe_scenarios = [s for s in scenarios if abs(s['change_pct']) <= MAX_CHANGE]

    if status == 'Выводим':
        decreases = [s for s in safe_scenarios if s['change_pct'] < 0 and s['new_margin_pct'] >= 5.0]
        if not decreases:
            decreases = [s for s in safe_scenarios if s['change_pct'] < 0 and s['new_margin_pct'] > 0]
        if decreases:
            return min(decreases, key=lambda s: s['turnover_after'])
        return None

    if roi_category == 'deadstock_risk':
        decreases = [s for s in safe_scenarios if s['change_pct'] < 0 and s['new_margin_pct'] >= 5.0]
        if decreases:
            return min(decreases, key=lambda s: s['turnover_after'])
        return None

    # СПП растёт → приоритет повышения для компенсации
    if spp_delta_pp > 2 and roi_category != 'underperformer':
        increases = [s for s in safe_scenarios if s['change_pct'] > 0 and s['profit_delta'] > 0]
        if increases:
            return min(increases, key=lambda s: s['change_pct'])

    if roi_category == 'underperformer':
        if margin_pct < 20:
            increases = [s for s in safe_scenarios if s['change_pct'] > 0 and s['profit_delta'] > 0]
            if increases:
                return min(increases, key=lambda s: s['change_pct'])
        decreases = [s for s in safe_scenarios if s['change_pct'] < 0 and s['new_margin_pct'] >= MIN_MARGIN_PCT and s['monthly_delta'] > 0]
        if decreases:
            return min(decreases, key=lambda s: abs(s['change_pct']))
        return None

    if roi_category == 'roi_leader' and turnover_days > 0 and turnover_days < 45:
        # Лидер с внешней рекламой → можно +5%
        max_step = 5 if has_external_ads else 3
        increases = [s for s in safe_scenarios if 0 < s['change_pct'] <= max_step and s['profit_delta'] > 0]
        if increases:
            # С внешней рекламой выбираем максимальный прибыльный шаг
            if has_external_ads:
                return max(increases, key=lambda s: s['change_pct'])
            return min(increases, key=lambda s: s['change_pct'])
        return None

    # Healthy или прочие → минимальное повышение с ростом прибыли
    profitable = [s for s in safe_scenarios if s['change_pct'] > 0 and s['profit_delta'] > 0 and s['new_margin_pct'] >= MIN_MARGIN_PCT]
    if profitable:
        return min(profitable, key=lambda s: s['change_pct'])
    return None


def _build_marketing_note(change_pct: float, has_external_ads: bool, drr_pct: float) -> str:
    """Рекомендация по маркетингу в зависимости от изменения цены."""
    if change_pct < 0:
        cut = abs(change_pct) * 0.6
        return f"Сократить рекламу на ~{cut:.0f}% — цена работает как стимул"
    if change_pct > 0 and has_external_ads:
        boost = change_pct * 0.5
        return f"Увеличить внешний трафик на ~{boost:.0f}% для компенсации оттока"
    if change_pct > 0:
        return "Сохранить текущий маркетинг"
    return ""


def generate_pricing_hypotheses(
    report: dict,
    turnover_map: dict,
) -> list[dict]:
    """Генерация сценарных гипотез по ценообразованию.

    Для каждой модели рассчитывает конкретные сценарии «что если» (+3%, +5%, -5%, -10%)
    с числами в рублях: как изменится маржа, объём, дневная прибыль, оборачиваемость.

    Учитывает:
    - Эластичность из регрессии или допущение (с модификаторами СПП / внешнего трафика)
    - Тренд СПП (комиссия МП), рекламные расходы, логистику
    - Раздельные гипотезы для продающихся и выводимых артикулов внутри одной модели
    - Маркетинговые рекомендации

    Returns: list of hypothesis dicts с полем 'scenarios'.
    """
    SKIP_MODELS = {'Other', 'Неопознанный товар'}

    elasticities = report.get('elasticities', {})
    roi_dashboard = report.get('roi_dashboard', [])
    model_statuses = report.get('model_statuses', {})
    models_data = report.get('models_data', [])
    spp_trends = report.get('spp_trends', {})
    enriched_ctx = report.get('enriched_context', {})
    article_group_metrics = report.get('article_group_metrics', {})

    roi_map = {item.get('model', ''): item for item in roi_dashboard if item.get('model')}

    md_map = {}
    if isinstance(models_data, list):
        for md in models_data:
            if md.get('model'):
                md_map[md['model']] = md

    hypotheses = []
    SCENARIO_STEPS = [-10, -5, -3, 3, 5, 10]

    all_models = set(roi_map.keys()) | set(turnover_map.keys()) | set(md_map.keys())

    for model in sorted(all_models):
        if model in SKIP_MODELS:
            continue

        elast = elasticities.get(model, {})
        roi = roi_map.get(model, {})
        turnover = turnover_map.get(model, {})
        md = md_map.get(model, {})
        status = model_statuses.get(model, 'Неизвестен')
        spp = spp_trends.get(model, {})
        ctx = enriched_ctx.get(model, {})
        agm = article_group_metrics.get(model, {})

        # Enriched context
        spp_delta = spp.get('delta_pp', 0)
        spp_current = spp.get('current_pct', 0)
        spp_trend = spp.get('trend', 'flat')
        has_external_ads = ctx.get('has_external_ads', False)
        drr_pct = ctx.get('drr_pct', 0)
        logistics_pct = ctx.get('logistics_pct', 0)

        # Общие метрики модели
        avg_price = float(elast.get('avg_price', 0) or md.get('avg_price_per_unit', 0) or 0)
        margin_pct = float(roi.get('margin_pct', 0) or md.get('margin_pct', 0) or 0)
        t_days = float(turnover.get('turnover_days', 0) or 0)
        daily_sales = float(turnover.get('daily_sales', 0) or roi.get('daily_sales', 0) or 0)
        stock_total = float(turnover.get('total_stock', 0) or turnover.get('avg_stock', 0) or 0)
        roi_category = roi.get('category', '')

        has_mixed = agm.get('has_mixed_statuses', False)

        # Пропускаем если совсем нет данных
        if avg_price <= 0 or daily_sales <= 0:
            hypotheses.append({
                'model': model,
                'channel': report.get('channel', ''),
                'hypothesis_type': 'hold',
                'article_group': 'all',
                'current_avg_price': round(avg_price, 0) if avg_price > 0 else None,
                'margin_pct': round(margin_pct, 1),
                'daily_sales': round(daily_sales, 2),
                'turnover_days': round(t_days, 0),
                'status': status,
                'roi_category': roi_category,
                'suggested_change_pct': 0,
                'scenarios': [],
                'recommended': None,
                'confidence': 'low',
                'marketing_note': '',
                'reasoning': 'Недостаточно данных (нет цены или продаж)',
            })
            continue

        # Если модель имеет смешанные статусы — генерируем 2 гипотезы
        if has_mixed:
            for group_name in ('selling', 'clearance'):
                gm = agm.get(group_name, {})
                if not gm:
                    continue
                g_margin_pct = gm.get('margin_pct', margin_pct)
                g_sales = gm.get('sales_count', 0)
                # Пропорция продаж группы от общих
                total_model_sales = float(turnover.get('sales_count', 1) or 1)
                sales_ratio = g_sales / total_model_sales if total_model_sales > 0 else 0.5
                g_daily_sales = daily_sales * sales_ratio
                g_stock = stock_total * sales_ratio
                g_articles_count = gm.get('articles_count', 0)

                if group_name == 'clearance':
                    g_status = 'Выводим'
                    g_e_val = -1.8
                    g_elasticity_source = 'assumed'
                    g_confidence = 'medium'
                else:
                    g_status = status if status != 'Выводим' else 'Продается'
                    e_val = elast.get('elasticity')
                    if e_val is not None and e_val < 0:
                        g_e_val = e_val
                        g_elasticity_source = 'regression'
                        g_confidence = 'high' if elast.get('r_squared', 0) > 0.3 else 'medium'
                    else:
                        g_e_val = _pick_assumed_elasticity(
                            g_status, roi_category, t_days,
                            spp_delta_pp=spp_delta, has_external_ads=has_external_ads,
                        )
                        g_elasticity_source = 'assumed'
                        g_confidence = 'medium' if roi_category in ('roi_leader', 'deadstock_risk') else 'low'

                scenarios = []
                for step in SCENARIO_STEPS:
                    sc = _calc_scenario(avg_price, g_margin_pct, g_daily_sales, g_stock, step, g_e_val)
                    scenarios.append(sc)

                recommended = _pick_recommended_scenario(
                    scenarios, g_status, roi_category, t_days, g_margin_pct,
                    elasticity_source=g_elasticity_source,
                    has_external_ads=has_external_ads, drr_pct=drr_pct, spp_delta_pp=spp_delta,
                )

                if recommended:
                    hypothesis_type = 'price_increase' if recommended['change_pct'] > 0 else 'price_decrease'
                    suggested_pct = abs(recommended['change_pct'])
                    marketing_note = _build_marketing_note(recommended['change_pct'], has_external_ads, drr_pct)
                else:
                    hypothesis_type = 'hold'
                    suggested_pct = 0
                    marketing_note = ''

                reasoning_parts = _build_reasoning(
                    g_e_val, g_elasticity_source, g_margin_pct, t_days, g_daily_sales,
                    g_status, spp_trend, spp_delta, spp_current, has_external_ads, drr_pct, logistics_pct,
                )

                hypotheses.append({
                    'model': model,
                    'channel': report.get('channel', ''),
                    'hypothesis_type': hypothesis_type,
                    'article_group': group_name,
                    'articles_count': g_articles_count,
                    'current_avg_price': round(avg_price, 0),
                    'margin_pct': round(g_margin_pct, 1),
                    'daily_sales': round(g_daily_sales, 2),
                    'turnover_days': round(t_days, 0),
                    'total_stock': round(g_stock, 0),
                    'status': g_status,
                    'roi_category': roi_category,
                    'suggested_change_pct': suggested_pct,
                    'scenarios': scenarios,
                    'recommended': recommended,
                    'elasticity': g_e_val,
                    'elasticity_source': g_elasticity_source,
                    'confidence': g_confidence,
                    'marketing_note': marketing_note,
                    'reasoning': '; '.join(reasoning_parts),
                })
            continue

        # Единая гипотеза для модели (нет mixed statuses)
        e_val = elast.get('elasticity')
        elasticity_source = 'regression'
        if e_val is not None and e_val < 0:
            confidence = 'high' if elast.get('r_squared', 0) > 0.3 else 'medium'
        else:
            e_val = _pick_assumed_elasticity(
                status, roi_category, t_days,
                spp_delta_pp=spp_delta, has_external_ads=has_external_ads,
            )
            elasticity_source = 'assumed'
            confidence = 'medium' if roi_category in ('roi_leader', 'deadstock_risk') else 'low'

        scenarios = []
        for step in SCENARIO_STEPS:
            sc = _calc_scenario(avg_price, margin_pct, daily_sales, stock_total, step, e_val)
            scenarios.append(sc)

        recommended = _pick_recommended_scenario(
            scenarios, status, roi_category, t_days, margin_pct,
            elasticity_source=elasticity_source,
            has_external_ads=has_external_ads, drr_pct=drr_pct, spp_delta_pp=spp_delta,
        )

        if recommended:
            hypothesis_type = 'price_increase' if recommended['change_pct'] > 0 else 'price_decrease'
            suggested_pct = abs(recommended['change_pct'])
            marketing_note = _build_marketing_note(recommended['change_pct'], has_external_ads, drr_pct)
        else:
            hypothesis_type = 'hold'
            suggested_pct = 0
            marketing_note = ''

        reasoning_parts = _build_reasoning(
            e_val, elasticity_source, margin_pct, t_days, daily_sales,
            status, spp_trend, spp_delta, spp_current, has_external_ads, drr_pct, logistics_pct,
        )

        hypotheses.append({
            'model': model,
            'channel': report.get('channel', ''),
            'hypothesis_type': hypothesis_type,
            'article_group': 'all',
            'current_avg_price': round(avg_price, 0),
            'margin_pct': round(margin_pct, 1),
            'daily_sales': round(daily_sales, 2),
            'turnover_days': round(t_days, 0),
            'stock_total': round(stock_total, 0),
            'status': status,
            'roi_category': roi_category,
            'suggested_change_pct': suggested_pct,
            'scenarios': scenarios,
            'recommended': recommended,
            'elasticity': e_val,
            'elasticity_source': elasticity_source,
            'confidence': confidence,
            'marketing_note': marketing_note,
            'reasoning': '; '.join(reasoning_parts),
        })

    return hypotheses


def _build_reasoning(
    e_val, elasticity_source, margin_pct, t_days, daily_sales,
    status, spp_trend, spp_delta, spp_current,
    has_external_ads, drr_pct, logistics_pct,
) -> list[str]:
    """Собрать reasoning для гипотезы."""
    parts = []
    if elasticity_source == 'regression':
        parts.append(f'Эластичность {e_val:.2f} (регрессия)')
    else:
        parts.append(f'Эластичность {e_val:.1f} (допущение)')
    parts.append(f'Маржа {margin_pct:.1f}%')
    if t_days > 0:
        parts.append(f'Оборачиваемость {t_days:.0f} дн.')
    parts.append(f'Продажи {daily_sales:.1f} шт/день')
    if status == 'Выводим':
        parts.append('Модель выводится')
    # SPP trend
    if spp_trend == 'up':
        parts.append(f'СПП ↑ {spp_current:.1f}% (+{spp_delta:.1f} п.п.)')
    elif spp_trend == 'down':
        parts.append(f'СПП ↓ {spp_current:.1f}% ({spp_delta:.1f} п.п.)')
    # Ads
    if has_external_ads:
        parts.append(f'Внешняя реклама (DRR {drr_pct:.1f}%)')
    elif drr_pct > 0:
        parts.append(f'DRR {drr_pct:.1f}%')
    # Logistics
    if logistics_pct > 10:
        parts.append(f'Логистика {logistics_pct:.1f}% от выручки (высокая)')
    elif logistics_pct > 0:
        parts.append(f'Логистика {logistics_pct:.1f}%')
    return parts


# ============================================================================
# Analysis pipeline
# ============================================================================

def analyze_channel(channel: str, start_date: str, end_date: str, learning_store) -> dict:
    """Run full price analysis for one channel. Returns report dict."""
    from agents.oleg.services.price_analysis.regression_engine import (
        estimate_price_elasticity,
        margin_factor_regression,
        run_full_analysis,
        classify_elastic_policy,
        multi_factor_margin_drivers,
    )
    from agents.oleg.services.price_analysis.price_plan_generator import (
        generate_price_management_plan,
        generate_article_level_plan,
    )
    from agents.oleg.services.price_analysis.roi_optimizer import (
        compute_model_roi_dashboard,
    )
    from agents.oleg.services.price_analysis.hypothesis_tester import (
        run_all_hypotheses,
    )
    from agents.oleg.services.price_analysis.price_pattern_analyzer import (
        summarize_pricing_patterns,
    )
    from shared.data_layer import (
        get_wb_turnover_by_model,
        get_ozon_turnover_by_model,
        get_wb_stock_daily_by_model,
        get_ozon_stock_daily_by_model,
        get_wb_price_margin_by_model_period,
        get_ozon_price_margin_by_model_period,
        get_wb_price_margin_by_submodel_period,
        get_wb_turnover_by_submodel,
        get_model_statuses_mapped,
        get_artikuly_statuses,
        get_wb_by_article,
        get_ozon_by_article,
    )

    report = {
        'channel': channel,
        'period': f"{start_date} — {end_date}",
        'generated_at': datetime.now().isoformat(),
    }

    # 1. Discover all models + statuses
    model_names = get_all_models(channel, start_date, end_date)
    report['models_total'] = len(model_names)
    logger.info(f"[{channel}] Found {len(model_names)} models: {model_names}")

    model_statuses = get_model_statuses_mapped()
    report['model_statuses'] = model_statuses
    phasing_out = [m for m in model_names if model_statuses.get(m) == 'Выводим']
    if phasing_out:
        logger.info(f"[{channel}] Models phasing out: {phasing_out}")

    # 1b. Article-level status breakdown per model
    article_statuses = get_artikuly_statuses()
    try:
        if channel == 'wb':
            raw_articles = get_wb_by_article(start_date, end_date)
        else:
            raw_articles = get_ozon_by_article(start_date, end_date)
    except Exception as e:
        logger.warning(f"[{channel}] Article data load failed: {e}")
        raw_articles = []

    # Build breakdown: {model: {'selling': [...], 'clearance': [...]}}
    article_breakdown = {}
    SELLING_STATUSES = {'Продается', 'Новый', 'Запуск'}
    for art_row in raw_articles:
        article = art_row.get('article', '').lower()
        model = art_row.get('model', '')
        if not model or not article:
            continue
        status = article_statuses.get(article, 'Продается')
        group = 'clearance' if status == 'Выводим' else 'selling'
        if model not in article_breakdown:
            article_breakdown[model] = {'selling': [], 'clearance': []}
        article_breakdown[model][group].append(art_row)

    # Compute aggregated metrics per group
    article_group_metrics = {}
    for model, groups in article_breakdown.items():
        article_group_metrics[model] = {}
        has_both = bool(groups['selling']) and bool(groups['clearance'])
        for group_name, articles in groups.items():
            if not articles:
                continue
            total_sales = sum(a.get('sales_count', 0) or 0 for a in articles)
            total_revenue = sum(a.get('revenue', 0) or 0 for a in articles)
            total_margin = sum(a.get('margin', 0) or 0 for a in articles)
            margin_pct = (total_margin / total_revenue * 100) if total_revenue > 0 else 0
            article_group_metrics[model][group_name] = {
                'articles_count': len(articles),
                'sales_count': total_sales,
                'revenue': total_revenue,
                'margin': total_margin,
                'margin_pct': round(margin_pct, 1),
                'top_articles': sorted(articles, key=lambda x: x.get('sales_count', 0) or 0, reverse=True)[:5],
            }
        article_group_metrics[model]['has_mixed_statuses'] = has_both

    report['article_group_metrics'] = article_group_metrics
    mixed_models = [m for m, g in article_group_metrics.items() if g.get('has_mixed_statuses')]
    if mixed_models:
        logger.info(f"[{channel}] Models with mixed statuses (selling+clearance): {mixed_models}")

    # 2. Per-model elasticity matrix
    elasticities = {}
    elasticity_errors = {}
    for model in model_names:
        try:
            data = get_model_data(channel, start_date, end_date, model)
            if len(data) < 14:
                elasticity_errors[model] = f"insufficient_data ({len(data)} days)"
                continue

            result = estimate_price_elasticity(data)
            if 'error' in result:
                elasticity_errors[model] = result['error']
            else:
                elasticities[model] = result
                # Cache in LearningStore
                if learning_store:
                    try:
                        learning_store.cache_elasticity(model, channel, result, start_date, end_date)
                    except Exception:
                        pass

            logger.info(f"[{channel}] Elasticity for {model}: {'OK' if 'error' not in result else result['error']}")
        except Exception as e:
            elasticity_errors[model] = str(e)
            logger.warning(f"[{channel}] Elasticity failed for {model}: {e}")

    report['elasticities'] = elasticities
    report['elasticity_errors'] = elasticity_errors
    report['models_with_elasticity'] = len(elasticities)

    # 3. Turnover data
    if channel == 'wb':
        turnover_map = get_wb_turnover_by_model(start_date, end_date) or {}
    else:
        turnover_map = get_ozon_turnover_by_model(start_date, end_date) or {}

    # 4. ROI dashboard
    roi_dashboard = []
    models_agg_data = []
    try:
        if channel == 'wb':
            models_agg_data = get_wb_price_margin_by_model_period(start_date, end_date)
        else:
            models_agg_data = get_ozon_price_margin_by_model_period(start_date, end_date)
        if models_agg_data and turnover_map:
            roi_dashboard = compute_model_roi_dashboard(models_agg_data, turnover_map)
    except Exception as e:
        logger.warning(f"[{channel}] ROI dashboard failed: {e}")
    report['roi_dashboard'] = roi_dashboard
    report['models_data'] = models_agg_data or []

    # 4b. Submodel breakdown (knitwear collection: Vuki-N, Vuki-W, Moon-W, etc.)
    submodel_data = []
    submodel_turnover = {}
    try:
        if channel == 'wb':
            submodel_data = get_wb_price_margin_by_submodel_period(start_date, end_date)
            submodel_turnover = get_wb_turnover_by_submodel(start_date, end_date) or {}
        # TODO: add ozon submodel queries when needed
    except Exception as e:
        logger.warning(f"[{channel}] Submodel data failed: {e}")
    report['submodel_data'] = submodel_data
    report['submodel_turnover'] = submodel_turnover

    # 5. Classify pricing policies (uses elasticity + turnover + model status)
    policies = {}
    for model, elast in elasticities.items():
        e_val = elast.get('elasticity', -1.0)
        margin_pct = elast.get('avg_margin_pct', 25.0)
        t_info = turnover_map.get(model, {})
        t_days = float(t_info.get('turnover_days', 30.0)) if isinstance(t_info, dict) else 30.0
        try:
            status = model_statuses.get(model, 'Неизвестен')
            is_phasing_out = (status == 'Выводим')
            policy = classify_elastic_policy(e_val, margin_pct, t_days, is_phasing_out=is_phasing_out)
            policies[model] = policy
        except Exception:
            pass
    report['policies'] = policies

    # 6. Margin factor regression per model
    margin_factors = {}
    for model in model_names:
        try:
            data = get_model_data(channel, start_date, end_date, model)
            if len(data) < 20:
                continue
            result = margin_factor_regression(data)
            if 'error' not in result:
                margin_factors[model] = result
        except Exception as e:
            logger.warning(f"[{channel}] Margin regression failed for {model}: {e}")
    report['margin_factors'] = margin_factors

    # 7. Price management plan
    try:
        plan = generate_price_management_plan(
            channel=channel,
            period_start=start_date,
            period_end=end_date,
            learning_store=learning_store,
        )
        report['price_plan'] = plan
    except Exception as e:
        logger.error(f"[{channel}] Price management plan failed: {e}")
        report['price_plan'] = {'error': str(e)}

    # 8. Price pattern analysis per model
    price_patterns = {}
    for model in model_names:
        try:
            data = get_model_data(channel, start_date, end_date, model)
            if len(data) < 30:
                continue
            patterns = summarize_pricing_patterns(data)
            if 'error' not in patterns:
                price_patterns[model] = patterns
        except Exception as e:
            logger.warning(f"[{channel}] Price patterns failed for {model}: {e}")
    report['price_patterns'] = price_patterns

    # 9. Hypothesis testing
    try:
        all_models_data = {}
        for model in model_names:
            data = get_model_data(channel, start_date, end_date, model)
            if data:
                all_models_data[model] = data

        if all_models_data:
            stock_daily_data = {}
            for model in model_names:
                try:
                    if channel == 'wb':
                        stock = get_wb_stock_daily_by_model(start_date, end_date, model)
                    else:
                        stock = get_ozon_stock_daily_by_model(start_date, end_date, model)
                    if stock:
                        stock_daily_data[model] = stock
                except Exception:
                    pass

            hypotheses = run_all_hypotheses(
                models_daily_data=all_models_data,
                article_data=None,
                stock_daily_data=stock_daily_data or None,
                turnover_data=turnover_map or None,
                product_lines=None,
            )
            report['hypotheses'] = hypotheses
    except Exception as e:
        logger.error(f"[{channel}] Hypothesis testing failed: {e}")
        report['hypotheses'] = {'error': str(e)}

    # 10. Article-level plan per model
    article_plans = {}
    for model in model_names:
        try:
            plan = generate_article_level_plan(
                channel=channel,
                model=model,
                period_start=start_date,
                period_end=end_date,
            )
            if plan and 'error' not in plan:
                article_plans[model] = plan
        except Exception as e:
            logger.warning(f"[{channel}] Article-level plan failed for {model}: {e}")
    report['article_plans'] = article_plans

    # 11. Full statistical analysis per model
    full_analyses = {}
    for model in model_names:
        try:
            data = get_model_data(channel, start_date, end_date, model)
            if len(data) < 30:
                continue
            analysis = run_full_analysis(data, model_name=model, channel=channel)
            if 'error' not in analysis:
                full_analyses[model] = analysis
        except Exception as e:
            logger.warning(f"[{channel}] Full analysis failed for {model}: {e}")
    report['full_analyses'] = full_analyses

    # 12. Deep margin drivers (multi-factor with seasonality)
    deep_margin_drivers = {}
    for model in model_names:
        try:
            data = get_model_data(channel, start_date, end_date, model)
            if len(data) < 30:
                continue
            result = multi_factor_margin_drivers(data)
            if 'error' not in result:
                deep_margin_drivers[model] = result
        except Exception as e:
            logger.warning(f"[{channel}] Deep margin drivers failed for {model}: {e}")
    report['deep_margin_drivers'] = deep_margin_drivers

    # 12b. SPP trends per model (WB only)
    spp_trends = {}
    if channel == 'wb':
        try:
            from shared.data_layer import get_wb_spp_history_by_model
            spp_history = get_wb_spp_history_by_model(start_date, end_date)
            if spp_history:
                # Group by model
                from collections import defaultdict
                model_spp = defaultdict(list)
                for row in spp_history:
                    model_spp[row['model']].append(row)
                for raw_model, rows in model_spp.items():
                    from shared.model_mapping import map_to_osnova
                    model = map_to_osnova(raw_model)
                    sorted_rows = sorted(rows, key=lambda r: r['date'])
                    all_spp = [r['spp_pct'] for r in sorted_rows if r['spp_pct']]
                    last_7 = [r['spp_pct'] for r in sorted_rows[-7:] if r['spp_pct']]
                    if all_spp and last_7:
                        avg_all = sum(all_spp) / len(all_spp)
                        avg_7 = sum(last_7) / len(last_7)
                        delta = avg_7 - avg_all
                        trend = 'up' if delta > 1 else ('down' if delta < -1 else 'flat')
                        spp_trends[model] = {
                            'current_pct': round(avg_7, 1),
                            'period_avg_pct': round(avg_all, 1),
                            'delta_pp': round(delta, 1),
                            'trend': trend,
                        }
        except Exception as e:
            logger.warning(f"[{channel}] SPP trends failed: {e}")
    report['spp_trends'] = spp_trends

    # 12c. Build enriched context from models_data (logistics, ads)
    enriched_context = {}
    for md in models_agg_data:
        model = md.get('model', '')
        if not model:
            continue
        revenue = float(md.get('revenue', 0) or 0)
        logistics = float(md.get('logistics', 0) or 0)
        if channel == 'wb':
            adv_internal = float(md.get('adv_internal', 0) or 0)
            adv_bloggers = float(md.get('adv_bloggers', 0) or 0)
            adv_vk = float(md.get('adv_vk', 0) or 0)
            adv_creators = float(md.get('adv_creators', 0) or 0)
            adv_external = adv_bloggers + adv_vk + adv_creators
            adv_total = adv_internal + adv_external
        else:
            adv_internal = float(md.get('adv_internal', 0) or 0)
            adv_external = float(md.get('adv_external', 0) or 0)
            adv_total = adv_internal + adv_external
        drr_pct = (adv_total / revenue * 100) if revenue > 0 else 0
        logistics_pct = (logistics / revenue * 100) if revenue > 0 else 0
        has_external_ads = adv_external > 0
        enriched_context[model] = {
            'adv_internal': round(adv_internal, 0),
            'adv_external': round(adv_external, 0),
            'adv_total': round(adv_total, 0),
            'drr_pct': round(drr_pct, 1),
            'logistics': round(logistics, 0),
            'logistics_pct': round(logistics_pct, 1),
            'has_external_ads': has_external_ads,
        }
    report['enriched_context'] = enriched_context

    # 13. Pricing hypotheses (гипотезы по ценообразованию)
    try:
        pricing_hypotheses = generate_pricing_hypotheses(report, turnover_map)
        report['pricing_hypotheses'] = pricing_hypotheses
        increase_count = sum(1 for h in pricing_hypotheses if h['hypothesis_type'] == 'price_increase')
        decrease_count = sum(1 for h in pricing_hypotheses if h['hypothesis_type'] == 'price_decrease')
        logger.info(
            f"[{channel}] Pricing hypotheses: {len(pricing_hypotheses)} total, "
            f"{increase_count} increase, {decrease_count} decrease"
        )
    except Exception as e:
        logger.error(f"[{channel}] Pricing hypotheses failed: {e}")
        report['pricing_hypotheses'] = []

    return report


def analyze_channel_adaptive(
    channel: str,
    end_date: str,
    learning_store,
) -> dict:
    """Адаптивный анализ: автоматически подбирает период (7d → 30d → 90d).

    Args:
        channel: 'wb' или 'ozon'
        end_date: конечная дата анализа (YYYY-MM-DD)
        learning_store: LearningStore instance
    """
    # Определяем модели для оценки достаточности данных
    model_names_30d = get_all_models(
        channel,
        (datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=30)).strftime('%Y-%m-%d'),
        end_date,
    )

    start_date, end_date_final, period_label = _pick_adaptive_period(
        channel, end_date, model_names_30d,
    )

    logger.info(f"[{channel}] Adaptive analysis: selected period {period_label} ({start_date} — {end_date_final})")

    report = analyze_channel(channel, start_date, end_date_final, learning_store)
    report['adaptive_period'] = period_label
    return report


# ============================================================================
# Report formatting — readable Russian text
# ============================================================================

def format_comprehensive_report(report: dict) -> str:
    """Форматирование единого читаемого отчёта на русском языке.

    Принципы:
    - Текстовые выводы вместо сырых таблиц
    - Все термины на русском
    - Статус модели учитывается в интерпретации
    - Один отчёт объединяет ценовой + регрессионный анализ
    """
    channel = report.get('channel', '?').upper()
    period = report.get('period', '?')
    model_statuses = report.get('model_statuses', {})

    channel_name = 'Wildberries' if channel == 'WB' else 'Ozon' if channel == 'OZON' else channel

    md = f"# {channel_name}: {period}\n\n"

    # -- Краткие итоги (toggle) --
    md += _format_summary(report, model_statuses, channel_name)

    # -- Ценовые гипотезы (основной блок с рекомендациями) --
    md += _format_pricing_hypotheses(report)

    return md


def _format_summary(report: dict, model_statuses: dict, channel_name: str) -> str:
    """Краткие итоги анализа."""
    total = report.get('models_total', 0)
    with_elast = report.get('models_with_elasticity', 0)
    policies = report.get('policies', {})
    margin_factors = report.get('margin_factors', {})
    deep_drivers = report.get('deep_margin_drivers', {})
    roi_dashboard = report.get('roi_dashboard', [])

    action_counts = {'hold': 0, 'increase': 0, 'decrease': 0}
    for p in policies.values():
        action = p.get('action', 'hold')
        action_counts[action] = action_counts.get(action, 0) + 1

    # Модели на выводе — из всех известных моделей, не только из elasticities
    all_model_names = set()
    for item in roi_dashboard:
        m = item.get('model', '')
        if m:
            all_model_names.add(m)
    all_model_names.update(margin_factors.keys())
    all_model_names.update(deep_drivers.keys())

    phasing_out = sorted(m for m in all_model_names if model_statuses.get(m) == 'Выводим')

    # ROI-категории
    roi_categories = {}
    for item in roi_dashboard:
        cat = item.get('category', '')
        if cat:
            roi_categories[cat] = roi_categories.get(cat, 0) + 1

    md = "## ▶ Краткие итоги\n\n"
    md += f"Проанализировано **{total} моделей** на {channel_name} "
    md += f"за период {report.get('period', '?')}.\n\n"

    with_factors = len(set(margin_factors.keys()) | set(deep_drivers.keys()))
    md += f"- Факторный анализ маржи: {with_factors} моделей\n"
    md += f"- Рассчитана эластичность: {with_elast} моделей"
    if total > with_elast:
        md += f" ({total - with_elast} — недостаточно данных)"
    md += "\n"

    if phasing_out:
        md += f"- Модели на выводе: {len(phasing_out)} ({', '.join(phasing_out)})\n"

    if roi_categories.get('roi_leader', 0):
        md += f"- Лидеры ROI: {roi_categories['roi_leader']} моделей\n"
    if roi_categories.get('deadstock_risk', 0):
        md += f"- Риск залёживания: {roi_categories['deadstock_risk']} моделей\n"

    if action_counts.get('increase', 0):
        md += f"- Рекомендовано повысить цену: {action_counts['increase']} моделей\n"
    if action_counts.get('decrease', 0):
        md += f"- Рекомендовано снизить цену: {action_counts['decrease']} моделей\n"
    if action_counts.get('hold', 0):
        md += f"- Удерживать текущую цену: {action_counts['hold']} моделей\n"

    md += "\n---\n\n"
    return md


def _format_model_blocks(
    report: dict,
    model_statuses: dict,
    elasticities: dict,
    policies: dict,
    margin_factors: dict,
    deep_drivers: dict,
    roi_dashboard: list,
    article_group_metrics: dict = None,
) -> str:
    """Генерация текстовых блоков по каждой модели.

    Использует ВСЕ источники данных: ROI dashboard, margin factors,
    deep drivers, elasticities, policies. Модели без эластичности
    всё равно показываются с метриками ROI и факторами маржи.

    Для моделей с артикулами разных статусов (selling + clearance)
    показывает разбивку: «продающиеся» и «выводимые» артикулы отдельно.
    """
    if article_group_metrics is None:
        article_group_metrics = {}
    from agents.oleg.services.price_analysis.translations import (
        translate_policy,
        translate_roi_category,
        interpret_elasticity,
        interpret_r2,
        factor_impact_text,
        POLICY_EMOJI,
        POLICY_DESCRIPTIONS_RU,
    )

    # ROI-словарь для быстрого доступа
    roi_map = {}
    for item in roi_dashboard:
        model_name = item.get('model', '')
        if model_name:
            roi_map[model_name] = item

    # Собираем ВСЕ модели из всех источников
    all_model_names = set()
    all_model_names.update(elasticities.keys())
    all_model_names.update(policies.keys())
    all_model_names.update(margin_factors.keys())
    all_model_names.update(deep_drivers.keys())
    all_model_names.update(roi_map.keys())

    # Фильтруем модели без значимых данных (нет факторов, нет ROI с продажами)
    def has_meaningful_data(model):
        if model in margin_factors or model in deep_drivers:
            return True
        if model in elasticities or model in policies:
            return True
        roi = roi_map.get(model, {})
        if roi.get('daily_sales', 0) > 0 or (roi.get('margin_pct') is not None and roi.get('turnover_days', 9999) < 9999):
            return True
        return False

    meaningful_models = {m for m in all_model_names if has_meaningful_data(m)}

    if not meaningful_models:
        return ""

    md = "## Обзор моделей\n\n"

    # Сортировка: по ROI категории (лидеры первые), затем по annual_roi убывание
    category_order = {'roi_leader': 0, 'healthy': 1, 'underperformer': 2, 'deadstock_risk': 3}

    def sort_key(model):
        # Модели с ценовой рекомендацией (increase/decrease) — в топ
        p = policies.get(model, {})
        action = p.get('action', 'hold')
        has_action = 0 if action in ('increase', 'decrease') else 1

        roi = roi_map.get(model, {})
        cat = roi.get('category', 'underperformer')
        annual_roi = roi.get('annual_roi', 0)

        return (has_action, category_order.get(cat, 2), -annual_roi, model)

    sorted_models = sorted(meaningful_models, key=sort_key)

    for model in sorted_models:
        elast = elasticities.get(model, {})
        policy = policies.get(model, {})
        roi_info = roi_map.get(model, {})
        status = model_statuses.get(model, 'Неизвестен')
        is_phasing_out = (status == 'Выводим')

        # Заголовок: модель + политика или ROI категория
        policy_code = policy.get('policy', '')
        roi_category = roi_info.get('category', '')

        if policy_code:
            policy_name = translate_policy(policy_code)
            emoji = POLICY_EMOJI.get(policy_code, '')
            md += f"### {model} {emoji} {policy_name}\n\n"
        elif is_phasing_out:
            md += f"### {model} 🔄 Контролируемый вывод\n\n"
        elif roi_category:
            cat_name = translate_roi_category(roi_category)
            cat_emoji = {'roi_leader': '🟢', 'healthy': '🟡', 'underperformer': '🟠', 'deadstock_risk': '🔴'}.get(roi_category, '')
            md += f"### {model} {cat_emoji} {cat_name}\n\n"
        else:
            md += f"### {model}\n\n"

        # Метрики модели
        meta_parts = [f"**Статус:** {status}"]

        e_val = elast.get('elasticity')
        if e_val is not None:
            e_interp = interpret_elasticity(e_val)
            short_interp = e_interp.split('(')[0].strip()
            meta_parts.append(f"**Эластичность:** {e_val:.2f} ({short_interp})")

        margin_pct = roi_info.get('margin_pct', elast.get('avg_margin_pct'))
        if margin_pct is not None:
            meta_parts.append(f"**Маржа:** {margin_pct:.1f}%")

        turnover = roi_info.get('turnover_days')
        if turnover is not None and turnover < 9999:
            meta_parts.append(f"**Оборачиваемость:** {turnover:.0f} дн.")

        annual_roi = roi_info.get('annual_roi')
        if annual_roi is not None:
            meta_parts.append(f"**ROI:** {annual_roi:.0f}%")

        daily_sales = roi_info.get('daily_sales')
        if daily_sales is not None:
            meta_parts.append(f"**Продажи:** {daily_sales:.1f} шт/день")

        md += " | ".join(meta_parts) + "\n\n"

        # Текстовое описание для моделей на выводе
        if is_phasing_out and not policy_code:
            if margin_pct is not None:
                if margin_pct > 20:
                    md += (
                        f"Модель выводится из ассортимента. Маржа достаточная ({margin_pct:.1f}%), "
                        f"агрессивное снижение цены не требуется. Остатки распродаются планово.\n\n"
                    )
                else:
                    md += (
                        f"Модель выводится из ассортимента. Маржа низкая ({margin_pct:.1f}%). "
                        f"Рассмотреть ускорение распродажи остатков.\n\n"
                    )
            else:
                md += "Модель выводится из ассортимента. Остатки распродаются планово.\n\n"

        # Текстовое описание эластичности
        if e_val is not None:
            r2 = elast.get('r_squared', 0)
            r2_quality = interpret_r2(r2) if isinstance(r2, (int, float)) else 'неизвестное'

            abs_e = abs(e_val)
            if abs_e < 0.5:
                md += (
                    f"Спрос на модель **практически не реагирует** на изменение цены "
                    f"(эластичность {e_val:.2f}). Повышение цены на 10% приведёт к снижению "
                    f"продаж всего на ~{abs_e * 10:.0f}%."
                )
            elif abs_e < 1.0:
                md += (
                    f"Спрос на модель **слабо реагирует** на изменение цены "
                    f"(эластичность {e_val:.2f}). Повышение цены на 10% приведёт к снижению "
                    f"продаж на ~{abs_e * 10:.0f}%."
                )
            elif abs_e < 1.5:
                md += (
                    f"Спрос на модель **умеренно чувствителен** к цене "
                    f"(эластичность {e_val:.2f}). Изменение цены заметно влияет на продажи."
                )
            else:
                md += (
                    f"Спрос на модель **сильно чувствителен** к цене "
                    f"(эластичность {e_val:.2f}). Любое изменение цены значительно влияет на объём продаж."
                )

            if isinstance(r2, (int, float)):
                md += f" Качество модели: {r2_quality} (R² = {r2:.2f}).\n\n"
            else:
                md += "\n\n"

        # Текст рекомендации (из policy.reasoning или ROI recommendation)
        reasoning = policy.get('reasoning', '')
        if reasoning:
            md += f"**Вывод:** {reasoning}\n\n"
        elif policy_code and policy_code in POLICY_DESCRIPTIONS_RU:
            md += f"**Вывод:** {POLICY_DESCRIPTIONS_RU[policy_code]}\n\n"
        elif not is_phasing_out:
            roi_rec = roi_info.get('recommendation', '')
            if roi_rec:
                md += f"**Вывод:** {roi_rec}\n\n"

        # Факторы маржи — текстовый формат
        factors_data = margin_factors.get(model, {})
        factors_dict = factors_data.get('factors', {})
        deep = deep_drivers.get(model, {})
        deep_factors = deep.get('factors', [])

        # Предпочитаем deep_drivers (более полные), fallback на margin_factors
        if deep_factors:
            sig_factors = [f for f in deep_factors if f.get('p_value', 1) < 0.1]
            sig_factors.sort(key=lambda x: abs(x.get('beta_std', 0)), reverse=True)

            if sig_factors:
                r2 = deep.get('r_squared', factors_data.get('r_squared'))
                header = "**Что влияет на маржу"
                if r2 is not None and isinstance(r2, (int, float)):
                    header += f" (R² = {r2:.2f})"
                header += ":**\n"
                md += header
                for i, f in enumerate(sig_factors[:5], 1):
                    name = f.get('name', '?')
                    beta = f.get('beta_std', 0)
                    pval = f.get('p_value', 1)
                    md += f"{i}. {factor_impact_text(name, beta, pval)}\n"
                md += "\n"
        elif factors_dict:
            sig_items = [(n, v) for n, v in factors_dict.items() if v.get('p_value', 1) < 0.1]
            sig_items.sort(key=lambda x: abs(x[1].get('standardized_beta', 0)), reverse=True)

            if sig_items:
                r2 = factors_data.get('r_squared')
                header = "**Что влияет на маржу"
                if r2 is not None and isinstance(r2, (int, float)):
                    header += f" (R² = {r2:.2f})"
                header += ":**\n"
                md += header
                for i, (name, vals) in enumerate(sig_items[:5], 1):
                    beta = vals.get('standardized_beta', 0)
                    pval = vals.get('p_value', 1)
                    md += f"{i}. {factor_impact_text(name, beta, pval)}\n"
                md += "\n"

        # Артикульная разбивка по статусам (продающиеся / выводимые)
        agm = article_group_metrics.get(model, {})
        if agm.get('has_mixed_statuses'):
            md += "**Разбивка по статусу артикулов:**\n\n"
            for group_key, group_label in [('selling', 'Продающиеся'), ('clearance', 'Выводимые')]:
                g = agm.get(group_key, {})
                if not g:
                    continue
                g_margin_pct = g.get('margin_pct', 0)
                g_sales = g.get('sales_count', 0)
                g_revenue = g.get('revenue', 0)
                g_count = g.get('articles_count', 0)
                md += (
                    f"*{group_label}* ({g_count} арт.): "
                    f"продажи {g_sales:,.0f} шт, "
                    f"выручка {g_revenue:,.0f}₽, "
                    f"маржа {g_margin_pct:.1f}%\n"
                )
                top = g.get('top_articles', [])
                if top:
                    md += "| Артикул | Продажи | Выручка | Маржа |\n"
                    md += "|---------|---------|---------|-------|\n"
                    for a in top:
                        a_sales = a.get('sales_count', 0) or 0
                        a_rev = a.get('revenue', 0) or 0
                        a_margin = a.get('margin', 0) or 0
                        a_mpct = (a_margin / a_rev * 100) if a_rev > 0 else 0
                        md += f"| {a.get('article', '?')} | {a_sales:,.0f} | {a_rev:,.0f}₽ | {a_mpct:.1f}% |\n"
                    md += "\n"

            md += "\n"

        md += "---\n\n"

    return md


def _format_submodel_breakdown(report: dict) -> str:
    """Разбивка трикотажной коллекции по подмоделям (Vuki-N, Vuki-W, Moon-W и т.д.)."""
    from shared.model_mapping import KNITWEAR_MODELS
    from agents.oleg.services.price_analysis.roi_optimizer import compute_annual_roi

    submodel_data = report.get('submodel_data', [])
    submodel_turnover = report.get('submodel_turnover', {})

    if not submodel_data:
        return ""

    # Фильтруем только трикотажную коллекцию
    knitwear_rows = [r for r in submodel_data if r.get('model') in KNITWEAR_MODELS]
    if not knitwear_rows:
        return ""

    # Группируем по osnova-модели
    by_osnova = {}
    for row in knitwear_rows:
        osnova = row['model']
        if osnova not in by_osnova:
            by_osnova[osnova] = []
        by_osnova[osnova].append(row)

    # Показываем только модели, где есть > 1 подмодель
    models_with_subs = {k: v for k, v in by_osnova.items() if len(v) > 1}
    if not models_with_subs:
        return ""

    md = "---\n\n## Разбивка по подмоделям (трикотажная коллекция)\n\n"

    for osnova in sorted(models_with_subs.keys()):
        subs = models_with_subs[osnova]
        # Сортировка по выручке (убывание)
        subs.sort(key=lambda x: x.get('revenue', 0) or 0, reverse=True)

        md += f"### {osnova}\n\n"
        md += "| Подмодель | Продажи, шт | Выручка, руб | Маржа, % | Оборач., дн. | ROI, % |\n"
        md += "|-----------|------------|-------------|---------|-------------|--------|\n"

        for sub in subs:
            submodel = sub.get('submodel', '?')
            sales = sub.get('sales_count', 0) or 0
            revenue = sub.get('revenue', 0) or 0
            margin_pct = sub.get('margin_pct')
            t_info = submodel_turnover.get(submodel, {})
            turnover_days = t_info.get('turnover_days', None) if isinstance(t_info, dict) else None

            # ROI расчёт
            roi = None
            if margin_pct is not None and turnover_days and turnover_days > 0:
                roi = compute_annual_roi(margin_pct, turnover_days)

            margin_str = f"{margin_pct:.1f}" if margin_pct is not None else "—"
            turnover_str = f"{turnover_days:.0f}" if turnover_days else "—"
            roi_str = f"{roi:.0f}" if roi is not None else "—"

            md += f"| {submodel} | {sales:,.0f} | {revenue:,.0f} | {margin_str} | {turnover_str} | {roi_str} |\n"

        md += "\n"

    return md


def _format_hypotheses(report: dict) -> str:
    """Форматирование гипотез в читаемом виде."""
    hyp = report.get('hypotheses', {})
    if not hyp or 'error' in hyp:
        return ""

    hyp_results = hyp.get('results', {})
    if not hyp_results:
        return ""

    md = "## Тестирование гипотез\n\n"
    md += "| Гипотеза | Результат | Вывод |\n"
    md += "|----------|-----------|-------|\n"

    for key, h in sorted(hyp_results.items()):
        name = h.get('hypothesis', key)
        result = h.get('result', '?')
        pval = h.get('p_value', None)
        conclusion = h.get('conclusion', h.get('interpretation', ''))

        if result in ('confirmed', 'significant', True, 'true', 'Подтверждена'):
            icon = 'Подтверждена'
        elif result in ('rejected', 'not_significant', False, 'false', 'Не подтверждена'):
            icon = 'Не подтверждена'
        else:
            icon = str(result)

        if not conclusion and pval is not None and isinstance(pval, (int, float)):
            if pval < 0.05:
                conclusion = f'Статистически значимо (p = {pval:.3f})'
            else:
                conclusion = f'Статистически незначимо (p = {pval:.3f})'

        md += f"| {name} | {icon} | {conclusion} |\n"

    summary = hyp.get('summary', '')
    if summary:
        md += f"\n**Общий итог:** {summary}\n"

    md += "\n"
    return md


def _format_pricing_hypotheses(report: dict) -> str:
    """Форматирование блока ценовых гипотез со сценариями «что если».

    Использует ▶ (U+25B6) для toggle-заголовков в Notion.
    Модели с mixed statuses получают вложенные toggles для selling/clearance.
    """
    hypotheses = report.get('pricing_hypotheses', [])
    if not hypotheses:
        return ""

    TYPE_EMOJI = {
        'price_increase': '📈',
        'price_decrease': '📉',
        'hold': '➡️',
    }
    TYPE_NAME = {
        'price_increase': 'Повысить цену',
        'price_decrease': 'Снизить цену',
        'hold': 'Удержать',
    }
    CONFIDENCE_NAME = {
        'high': '🟢 Высокая',
        'medium': '🟡 Средняя',
        'low': '🔴 Низкая',
    }
    CATEGORY_NAME = {
        'roi_leader': 'Лидер',
        'healthy': 'Здоровый',
        'underperformer': 'Отстающий',
        'deadstock_risk': 'Deadstock',
    }
    GROUP_NAME = {
        'selling': 'Продающиеся артикулы',
        'clearance': 'Выводимые артикулы',
        'all': '',
    }

    # Группируем гипотезы по модели (для mixed — несколько записей на модель)
    from collections import defaultdict
    model_hyps = defaultdict(list)
    for h in hypotheses:
        model_hyps[h['model']].append(h)

    # Сортировка: сначала actionable, потом hold
    def model_sort_key(model_name):
        hyps = model_hyps[model_name]
        has_action = any(h['hypothesis_type'] != 'hold' for h in hyps)
        return (0 if has_action else 1, model_name)

    sorted_models = sorted(model_hyps.keys(), key=model_sort_key)

    md_text = "---\n\n## Ценовые гипотезы: управление маржой и оборачиваемостью\n\n"

    # Сводка
    increase = [h for h in hypotheses if h['hypothesis_type'] == 'price_increase']
    decrease = [h for h in hypotheses if h['hypothesis_type'] == 'price_decrease']
    hold = [h for h in hypotheses if h['hypothesis_type'] == 'hold']

    adaptive = report.get('adaptive_period', '')
    if adaptive:
        md_text += f"Период анализа: **{adaptive}**\n\n"

    # Считаем уникальные модели
    increase_models = len(set(h['model'] for h in increase))
    decrease_models = len(set(h['model'] for h in decrease))
    hold_models = len(set(h['model'] for h in hold if h['model'] not in
                         set(h2['model'] for h2 in increase + decrease)))

    md_text += f"- 📈 Повысить цену: **{increase_models}** моделей\n"
    md_text += f"- 📉 Снизить цену: **{decrease_models}** моделей\n"
    md_text += f"- ➡️ Удержать: **{hold_models}** моделей\n\n"

    # Суммарный эффект рекомендаций
    total_monthly_delta = sum(
        h['recommended']['monthly_delta']
        for h in hypotheses
        if h.get('recommended')
    )
    if total_monthly_delta != 0:
        md_text += f"Суммарный потенциал рекомендаций: **{total_monthly_delta:+,.0f} ₽/мес**\n\n"

    md_text += "---\n\n"

    # Детали по моделям
    for model in sorted_models:
        hyps = model_hyps[model]
        is_mixed = len(hyps) > 1  # selling + clearance

        if is_mixed:
            # Сводный заголовок для mixed модели
            types = set(h['hypothesis_type'] for h in hyps)
            emojis = ' / '.join(TYPE_EMOJI.get(t, '') for t in sorted(types))
            md_text += f"### ▶ {model} {emojis} (mixed: продающиеся + выводимые)\n\n"

            for h in hyps:
                group = h.get('article_group', 'all')
                group_label = GROUP_NAME.get(group, group)
                arts_count = h.get('articles_count', 0)
                emoji = TYPE_EMOJI.get(h['hypothesis_type'], '')
                type_name = TYPE_NAME.get(h['hypothesis_type'], '')

                # Используем bold-разделитель вместо вложенного toggle
                # (Notion не поддерживает таблицы в heading_3 > heading_3)
                if h['hypothesis_type'] != 'hold':
                    sign = '+' if h['hypothesis_type'] == 'price_increase' else '-'
                    md_text += f"**{group_label} ({arts_count} арт.) — {type_name} {sign}{h['suggested_change_pct']:.0f}% {emoji}**\n\n"
                else:
                    md_text += f"**{group_label} ({arts_count} арт.) — Удержать ➡️**\n\n"

                md_text += _format_single_hypothesis(h, CONFIDENCE_NAME, CATEGORY_NAME)
        else:
            # Единая гипотеза
            h = hyps[0]
            if h['hypothesis_type'] == 'hold':
                continue  # hold модели — в конце общим блоком

            emoji = TYPE_EMOJI.get(h['hypothesis_type'], '')
            type_name = TYPE_NAME.get(h['hypothesis_type'], '')
            sign = '+' if h['hypothesis_type'] == 'price_increase' else '-'
            md_text += f"### ▶ {h['model']} {emoji} {type_name} ({sign}{h['suggested_change_pct']:.0f}%)\n\n"
            md_text += _format_single_hypothesis(h, CONFIDENCE_NAME, CATEGORY_NAME)

    # Hold — в toggle
    hold_only = [model for model in sorted_models
                 if all(h['hypothesis_type'] == 'hold' for h in model_hyps[model])]
    if hold_only:
        md_text += "---\n\n### ▶ Модели без рекомендации (удержать текущую цену)\n\n"
        md_text += "| Модель | Цена | Маржа | Продажи/день | Оборач. | Причина |\n"
        md_text += "|:------:|:----:|:-----:|:------------:|:-------:|:-------:|\n"
        for model in hold_only:
            h = model_hyps[model][0]
            price_str = f"{h['current_avg_price']:.0f} ₽" if h.get('current_avg_price') else '—'
            reason = h.get('reasoning', '')
            short_reason = reason[:60] + '…' if len(reason) > 60 else reason
            md_text += (
                f"| {h['model']} "
                f"| {price_str} "
                f"| {h.get('margin_pct', 0):.1f}% "
                f"| {h.get('daily_sales', 0):.1f} "
                f"| {h.get('turnover_days', 0):.0f} дн. "
                f"| {short_reason} |\n"
            )
        md_text += "\n"

    return md_text


def _format_single_hypothesis(h: dict, CONFIDENCE_NAME: dict, CATEGORY_NAME: dict) -> str:
    """Форматировать одну гипотезу (тело toggle-секции)."""
    md = ""
    confidence = CONFIDENCE_NAME.get(h.get('confidence', ''), h.get('confidence', ''))
    category = CATEGORY_NAME.get(h.get('roi_category', ''), '')
    rec = h.get('recommended', {})

    # Текущее состояние
    md += f"**Сейчас:** цена {h['current_avg_price']:.0f} ₽ · маржа {h.get('margin_pct', 0):.1f}% · "
    md += f"продажи {h.get('daily_sales', 0):.1f} шт/день · "
    md += f"оборачиваемость {h.get('turnover_days', 0):.0f} дн."
    if category:
        md += f" · {category}"
    if h.get('status') == 'Выводим':
        md += " · ⚠️ Выводим"
    md += "\n\n"

    # Рекомендация
    if rec:
        md += f"**Рекомендация:** изменить цену на **{rec['change_pct']:+.0f}%** → "
        md += f"**{rec['new_price']:.0f} ₽**\n"
        md += f"- Маржинальность: {h.get('margin_pct', 0):.1f}% → **{rec['new_margin_pct']:.1f}%**\n"
        md += f"- Объём продаж: {rec['volume_change_pct']:+.1f}%\n"
        md += f"- Дневная прибыль: {rec['daily_profit_before']:.0f} → **{rec['daily_profit_after']:.0f} ₽** ({rec['profit_delta']:+,.0f} ₽)\n"
        md += f"- Месячный эффект: **{rec['monthly_delta']:+,.0f} ₽**\n"
        if rec.get('turnover_before', 0) > 0:
            md += f"- Оборачиваемость: {rec['turnover_before']:.0f} → **{rec['turnover_after']:.0f} дн.**\n"
        md += "\n"

    # Маркетинговая рекомендация
    marketing_note = h.get('marketing_note', '')
    if marketing_note:
        md += f"**Маркетинг:** {marketing_note}\n\n"

    # Таблица сценариев
    scenarios = h.get('scenarios', [])
    if scenarios:
        md += "**Сценарии «что если»:**\n\n"
        md += "| Изменение | Новая цена | Маржа | Объём | Прибыль/день | Δ прибыль/мес | Оборач. |\n"
        md += "|:---------:|:----------:|:-----:|:-----:|:------------:|:-------------:|:-------:|\n"
        for sc in scenarios:
            delta_str = f"{sc['monthly_delta']:+,.0f} ₽"
            md += (
                f"| {sc['change_pct']:+.0f}% "
                f"| {sc['new_price']:.0f} ₽ "
                f"| {sc['new_margin_pct']:.1f}% "
                f"| {sc['volume_change_pct']:+.1f}% "
                f"| {sc['daily_profit_after']:.0f} ₽ "
                f"| {delta_str} "
                f"| {sc['turnover_after']:.0f} дн. |\n"
            )
        md += "\n"

    # Обоснование
    md += f"**Обоснование:** {h.get('reasoning', '')}\n\n"
    e_source = h.get('elasticity_source', '')
    e_val = h.get('elasticity', 0)
    if e_source == 'regression':
        md += f"Эластичность: **{e_val:.2f}** (рассчитана регрессией) · "
    else:
        md += f"Эластичность: **{e_val:.1f}** (допущение) · "
    md += f"Уверенность: {confidence}\n\n"

    return md


# ============================================================================
# Delivery: Notion + Telegram
# ============================================================================

async def deliver_to_notion(report_md: str, channel: str, start_date: str, end_date: str) -> str | None:
    """Save report to Notion, return page URL."""
    try:
        from agents.oleg import config
        from agents.oleg.services.notion_service import NotionService
        notion = NotionService(
            token=config.NOTION_TOKEN,
            database_id=config.NOTION_DATABASE_ID,
        )
        if not notion.enabled:
            logger.warning("Notion not configured")
            return None

        page_url = await notion.sync_report(
            start_date=start_date,
            end_date=end_date,
            report_md=report_md,
            report_type="Ценовой анализ",
            source="CLI (bulk analysis)",
        )
        return page_url
    except Exception as e:
        logger.error(f"Notion delivery failed: {e}")
        return None


async def notify_telegram(message: str):
    """Send notification to Telegram."""
    try:
        from agents.oleg import config
        if not config.TELEGRAM_BOT_TOKEN or not config.ADMIN_CHAT_ID:
            return

        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties
        bot = Bot(token=config.TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
        try:
            await bot.send_message(config.ADMIN_CHAT_ID, message)
        finally:
            await bot.session.close()
    except Exception as e:
        logger.warning(f"Telegram notification failed: {e}")


# ============================================================================
# Main
# ============================================================================

async def main():
    parser = argparse.ArgumentParser(description="Bulk Price Analysis")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--channels", default="wb,ozon", help="Channels (comma-separated)")
    parser.add_argument("--no-notion", action="store_true", help="Skip Notion delivery")
    parser.add_argument("--telegram", action="store_true", help="Send Telegram notification (off by default for CLI runs)")
    args = parser.parse_args()

    channels = [c.strip() for c in args.channels.split(",")]

    # Initialize LearningStore
    from agents.oleg.services.price_analysis.learning_store import LearningStore
    from agents.oleg.services.price_tools import set_learning_store
    learning_store = LearningStore()
    set_learning_store(learning_store)

    data_dir = Path(__file__).parent.parent / "agents" / "oleg" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime('%Y-%m-%d')
    all_reports_md = []  # Собираем MD всех каналов для одной Notion-страницы

    for channel in channels:
        print(f"\n{'='*60}")
        print(f"Analyzing {channel.upper()}: {args.start} — {args.end}")
        print(f"{'='*60}\n")

        # Run analysis
        report = analyze_channel(channel, args.start, args.end, learning_store)

        # Save JSON
        json_path = data_dir / f"price_report_{channel}_{today}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)
        print(f"JSON saved: {json_path}")

        # Format single comprehensive Markdown report
        report_md = format_comprehensive_report(report)

        # Save Markdown
        md_path = data_dir / f"price_report_{channel}_{today}.md"
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(report_md)
        print(f"Markdown saved: {md_path}")

        # Добавляем в общий отчёт (заголовок канала уже в report_md)
        all_reports_md.append(report_md)

        # Print summary
        print(f"\nSummary for {channel.upper()}:")
        print(f"  Models: {report.get('models_total', 0)}")
        print(f"  With elasticity: {report.get('models_with_elasticity', 0)}")
        print(f"  Margin factors: {len(report.get('margin_factors', {}))}")
        print(f"  Price patterns: {len(report.get('price_patterns', {}))}")

    # Deliver combined report to Notion (one page for all channels)
    page_url = None
    if not args.no_notion and all_reports_md:
        combined_md = "\n\n---\n\n".join(all_reports_md)
        page_url = await deliver_to_notion(combined_md, channels[0], args.start, args.end)
        if page_url:
            print(f"\nNotion: {page_url}")

    # Telegram notification (opt-in for CLI runs)
    if args.telegram:
        msg_parts = [
            f"Ценовой анализ за {args.start} — {args.end} завершён.",
            f"Каналы: {', '.join(c.upper() for c in channels)}",
        ]
        if page_url:
            msg_parts.insert(0, f'<a href="{page_url}">Отчёт в Notion</a>')
        await notify_telegram("\n".join(msg_parts))


if __name__ == "__main__":
    asyncio.run(main())
