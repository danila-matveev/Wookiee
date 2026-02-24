"""
Price Tools — инструменты ценовой аналитики для агента Олег.

Обёртки над price_analysis/ модулями в формате OpenAI function calling.
Все SQL-запросы в shared/data_layer.py — здесь только оркестрация.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from agents.oleg.services.time_utils import get_now_msk, get_today_msk

from shared.data_layer import (
    get_wb_price_margin_daily,
    get_ozon_price_margin_daily,
    get_wb_price_changes,
    get_ozon_price_changes,
    get_wb_spp_history_by_model,
    get_wb_price_margin_by_model_period,
    get_ozon_price_margin_by_model_period,
    get_wb_price_margin_daily_by_article,
    get_ozon_price_margin_daily_by_article,
    get_wb_turnover_by_model,
    get_ozon_turnover_by_model,
    get_wb_stock_daily_by_model,
    get_ozon_stock_daily_by_model,
)
from agents.oleg.services.price_analysis.regression_engine import (
    estimate_price_elasticity,
    estimate_price_elasticity_quadratic,
    compute_correlation_matrix,
    detect_price_trend,
    run_full_analysis,
)
from agents.oleg.services.price_analysis.recommendation_engine import (
    generate_recommendations,
    generate_recommendations_batch,
)
from agents.oleg.services.price_analysis.scenario_modeler import (
    simulate_price_change,
    counterfactual_analysis,
)
from agents.oleg.services.price_analysis.roi_optimizer import (
    compute_model_roi_dashboard,
    find_optimal_price_for_roi,
)
from agents.oleg.services.price_analysis.stock_price_optimizer import (
    assess_stock_health,
    generate_stock_price_matrix,
)
from agents.oleg.services.price_analysis.hypothesis_tester import (
    run_all_hypotheses,
)
from agents.oleg.services.price_analysis.price_plan_generator import (
    generate_price_management_plan,
    generate_article_level_plan,
)

logger = logging.getLogger(__name__)

# Глобальный learning_store (инициализируется в main.py при запуске)
_learning_store = None


def set_learning_store(store):
    """Установить LearningStore для кэширования и сохранения рекомендаций."""
    global _learning_store
    _learning_store = store


# =============================================================================
# TOOL DEFINITIONS (OpenAI function calling format)
# =============================================================================

PRICE_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_price_elasticity",
            "description": (
                "Оценка ценовой эластичности спроса для модели. "
                "Показывает как изменение цены влияет на объём продаж. "
                "Эластичность < -1 = спрос эластичен (повышение цены → потеря объёма). "
                "Эластичность > -1 = неэластичен (можно повышать цену). "
                "Используй для обоснования ценовых решений."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "model": {"type": "string", "description": "Имя модели (напр. wendy, ruby)"},
                    "channel": {"type": "string", "enum": ["wb", "ozon"], "description": "Канал"},
                    "lookback_days": {
                        "type": "integer",
                        "description": "Период анализа в днях (по умолчанию 90)",
                        "default": 90,
                    },
                },
                "required": ["model", "channel"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_price_margin_correlation",
            "description": (
                "Корреляционная матрица: связь цены с маржой, объёмом, СПП, ДРР, "
                "логистикой и другими метриками. Pearson + Spearman с p-value. "
                "Используй для поиска скрытых зависимостей."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "enum": ["wb", "ozon"], "description": "Канал"},
                    "start_date": {"type": "string", "description": "Начало периода YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "Конец периода YYYY-MM-DD"},
                    "model": {"type": "string", "description": "Модель (опционально, без = все модели)"},
                },
                "required": ["channel", "start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_price_recommendation",
            "description": (
                "Сгенерировать рекомендацию по изменению цены для модели. "
                "Анализирует эластичность, генерирует сценарии (+5%, +10%, -5%, -10%), "
                "ранжирует по прогнозу маржинальной прибыли с учётом ограничений "
                "(маржа >= 20%, потеря объёма <= 10%). "
                "Используй для конкретных ценовых рекомендаций."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "model": {"type": "string", "description": "Модель"},
                    "channel": {"type": "string", "enum": ["wb", "ozon"], "description": "Канал"},
                },
                "required": ["model", "channel"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "simulate_price_change",
            "description": (
                "Прогноз: что произойдёт если изменить цену на X%. "
                "Показывает ожидаемое изменение объёма, маржи, выручки "
                "на основе эластичности. 'Что если поднять цену Wendy на 10%?'"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "model": {"type": "string", "description": "Модель"},
                    "channel": {"type": "string", "enum": ["wb", "ozon"], "description": "Канал"},
                    "price_change_pct": {
                        "type": "number",
                        "description": "Изменение цены в % (напр. 10 = повышение на 10%, -5 = снижение)",
                    },
                },
                "required": ["model", "channel", "price_change_pct"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_price_counterfactual",
            "description": (
                "Контрфактуальный анализ: 'что было бы если мы изменили цену "
                "на X% в прошлом периоде'. Сравнивает фактические результаты "
                "с гипотетическими. 'Что было бы если бы мы подняли цену на 5% на прошлой неделе?'"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "model": {"type": "string", "description": "Модель"},
                    "channel": {"type": "string", "enum": ["wb", "ozon"], "description": "Канал"},
                    "price_change_pct": {"type": "number", "description": "Гипотетическое изменение цены %"},
                    "start_date": {"type": "string", "description": "Начало периода YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "Конец периода YYYY-MM-DD"},
                },
                "required": ["model", "channel", "price_change_pct", "start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_promotion",
            "description": (
                "Анализ акции маркетплейса: рассчитать финансовый эффект участия, "
                "рекомендовать участвовать или нет. Сканирует доступные акции "
                "через API WB/OZON и анализирует каждую."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "enum": ["wb", "ozon"], "description": "Канал"},
                },
                "required": ["channel"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_price_trend",
            "description": (
                "Ценовой тренд модели: растёт/падает/стабильна? "
                "Включает тест Манна-Кендалла, волатильность, мин/макс, "
                "скользящее среднее. Также СПП-тренд."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "model": {"type": "string", "description": "Модель"},
                    "channel": {"type": "string", "enum": ["wb", "ozon"], "description": "Канал"},
                    "lookback_days": {"type": "integer", "description": "Период в днях (по умолчанию 30)", "default": 30},
                },
                "required": ["model", "channel"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recommendation_history",
            "description": (
                "История прошлых ценовых рекомендаций и их результатов. "
                "Показывает: что рекомендовали, что произошло, точность прогнозов."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "model": {"type": "string", "description": "Модель (опционально)"},
                    "last_n": {"type": "integer", "description": "Количество последних записей (по умолчанию 10)", "default": 10},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_price_changes_detected",
            "description": (
                "Обнаруженные значимые изменения цены (>3%) за период. "
                "Показывает когда и на сколько менялась цена каждой модели."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "enum": ["wb", "ozon"], "description": "Канал"},
                    "start_date": {"type": "string", "description": "Начало периода YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "Конец периода YYYY-MM-DD"},
                    "model": {"type": "string", "description": "Модель (опционально)"},
                },
                "required": ["channel", "start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_price_management_plan",
            "description": (
                "Полный ценовой план для канала: метрики, эластичность, ROI, "
                "остатки, рекомендации по каждой модели с приоритизацией. "
                "Используй для комплексного ценового обзора."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "enum": ["wb", "ozon"], "description": "Канал"},
                    "period_start": {"type": "string", "description": "Начало периода YYYY-MM-DD (по умолчанию -30 дней)"},
                    "period_end": {"type": "string", "description": "Конец периода YYYY-MM-DD (по умолчанию вчера)"},
                },
                "required": ["channel"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_model_roi_dashboard",
            "description": (
                "ROI дашборд: маржа% × 365/оборачиваемость по всем моделям. "
                "Ранжирование моделей по годовому ROI с категоризацией: "
                "roi_leader, healthy, underperformer, deadstock_risk."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "enum": ["wb", "ozon"], "description": "Канал"},
                },
                "required": ["channel"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "test_price_hypothesis",
            "description": (
                "Статистическая проверка гипотез H1-H7 о ценовой эластичности, "
                "прибыли, рекламе, остатках, кросс-модельных эффектах, "
                "временных паттернах и ROI. Используй для глубокого анализа."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "enum": ["wb", "ozon"], "description": "Канал"},
                    "lookback_days": {
                        "type": "integer",
                        "description": "Период анализа в днях (по умолчанию 180)",
                        "default": 180,
                    },
                },
                "required": ["channel"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_price_matrix",
            "description": (
                "Матрица остатки × цена по всем моделям: статус запаса, "
                "рекомендуемое действие, срочность. Модели с критическим "
                "дефицитом или затовариванием выделяются в urgent_actions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "enum": ["wb", "ozon"], "description": "Канал"},
                },
                "required": ["channel"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_article_elasticity",
            "description": (
                "Поартикульная эластичность внутри модели. "
                "Показывает как разные цветовые варианты реагируют на цену. "
                "Используй для детального анализа внутри модели."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "model": {"type": "string", "description": "Модель"},
                    "channel": {"type": "string", "enum": ["wb", "ozon"], "description": "Канал"},
                },
                "required": ["model", "channel"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "optimize_price_for_roi",
            "description": (
                "Оптимальная цена для максимизации ROI (маржа% × 365/оборачиваемость). "
                "Grid search по диапазону цен с учётом эластичности и стока."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "model": {"type": "string", "description": "Модель"},
                    "channel": {"type": "string", "enum": ["wb", "ozon"], "description": "Канал"},
                },
                "required": ["model", "channel"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_cross_model_effects",
            "description": (
                "Каннибализация между моделями: как изменение цены одной "
                "модели влияет на продажи другой в той же продуктовой линейке."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "enum": ["wb", "ozon"], "description": "Канал"},
                    "lookback_days": {
                        "type": "integer",
                        "description": "Период анализа в днях (по умолчанию 90)",
                        "default": 90,
                    },
                },
                "required": ["channel"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_promotion_plan",
            "description": (
                "Полный план участия в акциях с учётом остатков, маржи и "
                "эластичности. Какие модели включить, какие исключить."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "enum": ["wb", "ozon"], "description": "Канал"},
                },
                "required": ["channel"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_deep_price_analysis",
            "description": (
                "Глубокий анализ ценовой эластичности по группам SKU: 'Развитие' (Продается, Новый, Запуск) "
                "и 'Ликвидация' (Выводим). Использует поартикульные данные заказов и реальные цены после СПП. "
                "Позволяет понять, как изменение цены влияет на спрос отдельно для ядра ассортимента и для стока на вывод."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "model": {"type": "string", "description": "Имя модели (напр. wendy, ruby)"},
                    "channel": {"type": "string", "enum": ["wb", "ozon"], "description": "Канал"},
                    "lookback_days": {
                        "type": "integer",
                        "description": "Период анализа в днях (по умолчанию 180)",
                        "default": 180,
                    },
                },
                "required": ["model", "channel"],
            },
        },
    },
]


# =============================================================================
# TOOL HANDLERS
# =============================================================================

def _get_data(channel: str, start_date: str, end_date: str, model: str = None) -> list[dict]:
    """Получить данные из data_layer по каналу."""
    if channel == 'wb':
        return get_wb_price_margin_daily(start_date, end_date, model)
    return get_ozon_price_margin_daily(start_date, end_date, model)


async def _handle_price_elasticity(model: str, channel: str, lookback_days: int = 90) -> dict:
    """Обработчик get_price_elasticity."""
    model = model.lower()

    now_msk = get_now_msk()
    end_date = now_msk.strftime('%Y-%m-%d')
    start_date = (now_msk - timedelta(days=lookback_days)).strftime('%Y-%m-%d')

    # Проверить кэш
    if _learning_store:
        cached = _learning_store.get_elasticity_cached(model, channel)
        if cached:
            cached['source'] = 'cache'
            return cached

    data = _get_data(channel, start_date, end_date, model)
    if not data:
        return {'error': f'No data for {model} on {channel}'}

    result = estimate_price_elasticity(data)

    # Сохранить в кэш
    if _learning_store and 'error' not in result:
        _learning_store.cache_elasticity(model, channel, result, start_date, end_date)

    result['model'] = model
    result['channel'] = channel
    result['period'] = f"{start_date} — {end_date}"
    return result


async def _handle_price_margin_correlation(channel: str, start_date: str, end_date: str, model: str = None) -> dict:
    """Обработчик get_price_margin_correlation."""
    data = _get_data(channel, start_date, end_date, model)
    if not data:
        return {'error': 'No data for specified period'}

    result = compute_correlation_matrix(data)
    result['channel'] = channel
    result['period'] = f"{start_date} — {end_date}"
    if model:
        result['model'] = model
    return result


async def _handle_price_recommendation(model: str, channel: str) -> dict:
    """Обработчик get_price_recommendation."""
    model = model.lower()

    now_msk = get_now_msk()
    end_date = now_msk.strftime('%Y-%m-%d')
    start_date = (now_msk - timedelta(days=90)).strftime('%Y-%m-%d')

    data = _get_data(channel, start_date, end_date, model)
    if not data:
        return {'error': f'No data for {model} on {channel}'}

    result = generate_recommendations(data, model, channel)

    # Сохранить рекомендацию
    if _learning_store and 'error' not in result:
        rec_id = _learning_store.save_recommendation(result)
        result['recommendation_id'] = rec_id

    return result


async def _handle_simulate_price_change(model: str, channel: str, price_change_pct: float) -> dict:
    """Обработчик simulate_price_change."""
    model = model.lower()

    now_msk = get_now_msk()
    end_date = now_msk.strftime('%Y-%m-%d')
    start_date = (now_msk - timedelta(days=90)).strftime('%Y-%m-%d')

    data = _get_data(channel, start_date, end_date, model)
    if not data:
        return {'error': f'No data for {model} on {channel}'}

    return simulate_price_change(data, price_change_pct, model, channel)


async def _handle_price_counterfactual(model: str, channel: str, price_change_pct: float, start_date: str, end_date: str) -> dict:
    """Обработчик get_price_counterfactual."""
    model = model.lower()

    # Данные за более широкий период (для эластичности)
    wider_start = (datetime.strptime(start_date, '%Y-%m-%d') - timedelta(days=60)).strftime('%Y-%m-%d')
    data = _get_data(channel, wider_start, end_date, model)
    if not data:
        return {'error': f'No data for {model} on {channel}'}

    return counterfactual_analysis(data, price_change_pct, start_date, end_date, model, channel)


async def _handle_analyze_promotion(channel: str) -> dict:
    """Обработчик analyze_promotion."""
    now_msk = get_now_msk()
    end_date = now_msk.strftime('%Y-%m-%d')
    start_date = (now_msk - timedelta(days=30)).strftime('%Y-%m-%d')

    # Текущие метрики по моделям
    if channel == 'wb':
        models = get_wb_price_margin_by_model_period(start_date, end_date)
    else:
        models = get_ozon_price_margin_by_model_period(start_date, end_date)

    if not models:
        return {'error': f'No model data for {channel}'}

    # Примечание: PromotionAnalyzer требует инициализированные WB/OZON клиенты.
    # В текущей интеграции клиенты инициализируются в main.py.
    # Пока возвращаем метрики с пометкой что API-сканирование нужно настроить.
    return {
        'channel': channel,
        'models_overview': models[:10],  # Топ-10 по марже
        'note': 'Для сканирования акций через API необходима настройка WB/OZON клиентов в main.py',
        'models_count': len(models),
    }


async def _handle_price_trend(model: str, channel: str, lookback_days: int = 30) -> dict:
    """Обработчик get_price_trend."""
    model = model.lower()

    now_msk = get_now_msk()
    end_date = now_msk.strftime('%Y-%m-%d')
    start_date = (now_msk - timedelta(days=lookback_days)).strftime('%Y-%m-%d')

    data = _get_data(channel, start_date, end_date, model)
    if not data:
        return {'error': f'No data for {model} on {channel}'}

    price_trend = detect_price_trend(data, 'price_per_unit')
    margin_trend = detect_price_trend(data, 'margin_pct')

    # СПП тренд
    spp_trend = detect_price_trend(data, 'spp_pct') if any('spp_pct' in d for d in data) else None

    result = {
        'model': model,
        'channel': channel,
        'period': f"{start_date} — {end_date}",
        'price_trend': price_trend,
        'margin_trend': margin_trend,
    }
    if spp_trend:
        result['spp_trend'] = spp_trend

    return result


async def _handle_recommendation_history(model: str = '', last_n: int = 10) -> dict:
    """Обработчик get_recommendation_history."""
    model = model.lower() if model else None

    if not _learning_store:
        return {'error': 'Learning store not initialized'}

    recs = _learning_store.get_recommendations(model=model, last_n=last_n)
    accuracy = _learning_store.get_prediction_accuracy(model=model)

    return {
        'recommendations': recs,
        'prediction_accuracy': accuracy,
        'total_count': len(recs),
    }


async def _handle_price_changes_detected(channel: str, start_date: str, end_date: str, model: str = None) -> dict:
    """Обработчик get_price_changes_detected."""
    if channel == 'wb':
        changes = get_wb_price_changes(start_date, end_date, model)
    else:
        changes = get_ozon_price_changes(start_date, end_date, model)

    return {
        'channel': channel,
        'period': f"{start_date} — {end_date}",
        'changes_count': len(changes),
        'changes': changes[:50],  # Лимит на вывод
    }


async def _handle_price_management_plan(channel: str, period_start: str = None, period_end: str = None) -> dict:
    """Обработчик get_price_management_plan."""
    return generate_price_management_plan(
        channel=channel,
        period_start=period_start,
        period_end=period_end,
        learning_store=_learning_store,
    )


async def _handle_model_roi_dashboard(channel: str) -> dict:
    """Обработчик get_model_roi_dashboard."""
    now_msk = get_now_msk()
    end_date = now_msk.strftime('%Y-%m-%d')
    start_date = (now_msk - timedelta(days=30)).strftime('%Y-%m-%d')

    if channel == 'wb':
        models = get_wb_price_margin_by_model_period(start_date, end_date)
        turnover = get_wb_turnover_by_model(start_date, end_date)
    else:
        models = get_ozon_price_margin_by_model_period(start_date, end_date)
        turnover = get_ozon_turnover_by_model(start_date, end_date)

    if not models:
        return {'error': f'No model data for {channel}'}

    dashboard = compute_model_roi_dashboard(models, turnover)
    return {
        'channel': channel,
        'period': f"{start_date} — {end_date}",
        'dashboard': dashboard,
        'total_models': len(dashboard),
    }


async def _handle_test_hypothesis(channel: str, lookback_days: int = 180) -> dict:
    """Обработчик test_price_hypothesis."""
    now_msk = get_now_msk()
    end_date = now_msk.strftime('%Y-%m-%d')
    start_date = (now_msk - timedelta(days=lookback_days)).strftime('%Y-%m-%d')

    # Получить данные по всем моделям
    if channel == 'wb':
        models_period = get_wb_price_margin_by_model_period(start_date, end_date)
    else:
        models_period = get_ozon_price_margin_by_model_period(start_date, end_date)

    if not models_period:
        return {'error': f'No model data for {channel}'}

    model_names = [m['model'] for m in models_period if m.get('model')]

    # Собрать дневные данные по моделям
    models_daily_data = {}
    for model_name in model_names[:15]:  # лимит на 15 моделей
        data = _get_data(channel, start_date, end_date, model_name)
        if data and len(data) >= 14:
            models_daily_data[model_name] = data

    if not models_daily_data:
        return {'error': 'Insufficient daily data for hypothesis testing'}

    # Оборачиваемость
    try:
        if channel == 'wb':
            turnover = get_wb_turnover_by_model(start_date, end_date)
        else:
            turnover = get_ozon_turnover_by_model(start_date, end_date)
    except Exception:
        turnover = None

    # Дневные остатки
    try:
        if channel == 'wb':
            stock_raw = get_wb_stock_daily_by_model(start_date, end_date)
        else:
            stock_raw = get_ozon_stock_daily_by_model(start_date, end_date)
        # Группировка по модели
        stock_daily = {}
        for row in stock_raw:
            model = row.get('model', '')
            if model not in stock_daily:
                stock_daily[model] = []
            stock_daily[model].append(row)
    except Exception:
        stock_daily = None

    result = run_all_hypotheses(
        models_daily_data=models_daily_data,
        stock_daily_data=stock_daily,
        turnover_data=turnover,
    )

    # Сохранить результаты
    if _learning_store and 'results' in result:
        for h_id, h_result in result['results'].items():
            try:
                _learning_store.save_hypothesis_result(h_id, channel, h_result)
            except Exception:
                pass

    return result


async def _handle_stock_price_matrix(channel: str) -> dict:
    """Обработчик get_stock_price_matrix."""
    now_msk = get_now_msk()
    end_date = now_msk.strftime('%Y-%m-%d')
    start_date = (now_msk - timedelta(days=30)).strftime('%Y-%m-%d')

    if channel == 'wb':
        models = get_wb_price_margin_by_model_period(start_date, end_date)
        turnover = get_wb_turnover_by_model(start_date, end_date)
    else:
        models = get_ozon_price_margin_by_model_period(start_date, end_date)
        turnover = get_ozon_turnover_by_model(start_date, end_date)

    if not models:
        return {'error': f'No model data for {channel}'}

    stock_data = {
        m.get('model', ''): turnover.get(m.get('model', ''), {}).get('avg_stock', 0)
        for m in models
    }

    result = generate_stock_price_matrix(models, stock_data, turnover)
    result['channel'] = channel
    result['period'] = f"{start_date} — {end_date}"
    return result


async def _handle_article_elasticity(model: str, channel: str) -> dict:
    """Обработчик get_article_elasticity."""
    result = generate_article_level_plan(channel, model.lower())
    return result


async def _handle_optimize_price_for_roi(model: str, channel: str) -> dict:
    """Обработчик optimize_price_for_roi."""
    model = model.lower()

    now_msk = get_now_msk()
    end_date = now_msk.strftime('%Y-%m-%d')
    start_date = (now_msk - timedelta(days=90)).strftime('%Y-%m-%d')

    data = _get_data(channel, start_date, end_date, model)
    if not data:
        return {'error': f'No data for {model} on {channel}'}

    # Эластичность
    elasticity = estimate_price_elasticity(data)
    if 'error' in elasticity:
        return {'error': f'Elasticity error: {elasticity["error"]}', 'model': model}

    # Оборачиваемость
    try:
        if channel == 'wb':
            turnover = get_wb_turnover_by_model(start_date, end_date)
        else:
            turnover = get_ozon_turnover_by_model(start_date, end_date)
    except Exception:
        return {'error': 'Could not get turnover data', 'model': model}

    t_info = turnover.get(model, {})
    t_days = t_info.get('turnover_days', 0)
    avg_stock = t_info.get('avg_stock', 0)

    if t_days <= 0:
        return {'error': 'No turnover data for model', 'model': model}

    # Текущие метрики
    import pandas as pd
    df = pd.DataFrame(data)
    recent = df.tail(7)
    current = {
        'price_per_unit': round(float(recent['price_per_unit'].mean()), 2),
        'sales_per_day': round(float(recent['sales_count'].mean()), 1),
        'margin_per_day': round(float(recent['margin'].mean()), 0),
        'margin_pct': round(float(recent['margin_pct'].mean()), 2),
    }

    result = find_optimal_price_for_roi(
        current_data=current,
        elasticity=elasticity['elasticity'],
        turnover_days=t_days,
        avg_stock=avg_stock,
    )

    # Убрать all_scenarios (слишком объёмно для LLM)
    result.pop('all_scenarios', None)
    result['model'] = model
    result['channel'] = channel
    result['elasticity'] = elasticity
    result['turnover_days'] = t_days
    return result


async def _handle_cross_model_effects(channel: str, lookback_days: int = 90) -> dict:
    """Обработчик analyze_cross_model_effects."""
    from agents.oleg.services.price_analysis.hypothesis_tester import test_cross_model_hypotheses

    now_msk = get_now_msk()
    end_date = now_msk.strftime('%Y-%m-%d')
    start_date = (now_msk - timedelta(days=lookback_days)).strftime('%Y-%m-%d')

    if channel == 'wb':
        models_period = get_wb_price_margin_by_model_period(start_date, end_date)
    else:
        models_period = get_ozon_price_margin_by_model_period(start_date, end_date)

    if not models_period:
        return {'error': f'No model data for {channel}'}

    model_names = [m['model'] for m in models_period if m.get('model')]

    models_daily_data = {}
    for model_name in model_names[:15]:
        data = _get_data(channel, start_date, end_date, model_name)
        if data and len(data) >= 14:
            models_daily_data[model_name] = data

    result = test_cross_model_hypotheses(models_daily_data)
    result['channel'] = channel
    result['period'] = f"{start_date} — {end_date}"
    return result


async def _handle_promotion_plan(channel: str) -> dict:
    """Обработчик get_promotion_plan."""
    from agents.oleg.services.price_analysis.promotion_analyzer import PromotionAnalyzer

    now_msk = get_now_msk()
    end_date = now_msk.strftime('%Y-%m-%d')
    start_date = (now_msk - timedelta(days=30)).strftime('%Y-%m-%d')

    if channel == 'wb':
        models = get_wb_price_margin_by_model_period(start_date, end_date)
        turnover = get_wb_turnover_by_model(start_date, end_date)
    else:
        models = get_ozon_price_margin_by_model_period(start_date, end_date)
        turnover = get_ozon_turnover_by_model(start_date, end_date)

    if not models:
        return {'error': f'No model data for {channel}'}

    # Stock health
    stock_data = {}
    for m in models:
        model_name = m.get('model', '')
        t_info = turnover.get(model_name, {})
        t_days = t_info.get('turnover_days', 0)
        avg_stock = t_info.get('avg_stock', 0)
        daily_sales = t_info.get('daily_sales', 0)
        if avg_stock > 0 or daily_sales > 0:
            stock_data[model_name] = assess_stock_health(t_days, avg_stock, daily_sales)

    # Эластичности
    elasticities = {}
    for m in models[:10]:
        model_name = m.get('model', '')
        if _learning_store:
            cached = _learning_store.get_elasticity_cached(model_name, channel)
            if cached and 'error' not in cached:
                elasticities[model_name] = cached

    analyzer = PromotionAnalyzer()
    result = analyzer.generate_promotion_participation_plan(
        channel=channel,
        models_metrics=models,
        stock_data=stock_data,
        turnover_data=turnover,
        elasticities=elasticities,
    )
    return result


async def _handle_deep_price_analysis(model: str, channel: str, lookback_days: int = 180) -> dict:
    """Обработчик get_deep_price_analysis."""
    from agents.oleg.services.price_analysis.deep_elasticity_service import analyze_model_deep_elasticity
    return analyze_model_deep_elasticity(channel, model, lookback_days)


# =============================================================================
# HANDLERS MAP
# =============================================================================

PRICE_TOOL_HANDLERS = {
    "get_price_elasticity": _handle_price_elasticity,
    "get_price_margin_correlation": _handle_price_margin_correlation,
    "get_price_recommendation": _handle_price_recommendation,
    "simulate_price_change": _handle_simulate_price_change,
    "get_price_counterfactual": _handle_price_counterfactual,
    "analyze_promotion": _handle_analyze_promotion,
    "get_price_trend": _handle_price_trend,
    "get_recommendation_history": _handle_recommendation_history,
    "get_price_changes_detected": _handle_price_changes_detected,
    "get_price_management_plan": _handle_price_management_plan,
    "get_model_roi_dashboard": _handle_model_roi_dashboard,
    "test_price_hypothesis": _handle_test_hypothesis,
    "get_stock_price_matrix": _handle_stock_price_matrix,
    "get_article_elasticity": _handle_article_elasticity,
    "optimize_price_for_roi": _handle_optimize_price_for_roi,
    "analyze_cross_model_effects": _handle_cross_model_effects,
    "get_promotion_plan": _handle_promotion_plan,
    "get_deep_price_analysis": _handle_deep_price_analysis,
}
