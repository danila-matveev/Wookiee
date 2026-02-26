"""
Price Pattern Analyzer — анализ исторических ценовых решений.

Отвечает на вопрос: «Какие ценовые решения в прошлом привели к улучшению метрик?»

Функции:
- detect_price_change_events: находит значимые изменения цены
- measure_post_change_impact: измеряет эффект до/после изменения
- classify_price_decisions: оценивает решения как improved/worsened/neutral
- summarize_pricing_patterns: агрегированные паттерны
"""
import logging
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)

# Минимальное число точек в окне для статистики
_MIN_WINDOW_POINTS = 5


def detect_price_change_events(
    data: list[dict],
    min_change_pct: float = 3.0,
) -> list[dict]:
    """
    Обнаружение значимых изменений цены в таймсерии.

    Args:
        data: ежедневные данные из data_layer (date, price_per_unit, margin_pct, orders_count, ...)
        min_change_pct: минимальный порог изменения цены в %

    Returns:
        Список событий: [{date, price_before, price_after, change_pct, direction}]
    """
    if len(data) < 2:
        return []

    df = pd.DataFrame(data)

    if 'date' not in df.columns or 'price_per_unit' not in df.columns:
        logger.warning("detect_price_change_events: missing 'date' or 'price_per_unit' column")
        return []

    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)

    # Дневное изменение цены в %
    prices = df['price_per_unit'].values
    pct_changes = np.zeros(len(prices))
    for i in range(1, len(prices)):
        if prices[i - 1] > 0:
            pct_changes[i] = (prices[i] - prices[i - 1]) / prices[i - 1] * 100

    # Индексы значимых изменений
    significant_idx = [i for i in range(1, len(pct_changes)) if abs(pct_changes[i]) >= min_change_pct]

    if not significant_idx:
        return []

    # Объединение последовательных дней в одно событие
    events = []
    group_start = significant_idx[0]
    group_end = significant_idx[0]

    for k in range(1, len(significant_idx)):
        if significant_idx[k] == significant_idx[k - 1] + 1:
            # Продолжение последовательности
            group_end = significant_idx[k]
        else:
            # Завершить текущую группу и начать новую
            events.append(_build_event(df, group_start, group_end))
            group_start = significant_idx[k]
            group_end = significant_idx[k]

    # Последняя группа
    events.append(_build_event(df, group_start, group_end))

    return events


def _build_event(df: pd.DataFrame, start_idx: int, end_idx: int) -> dict:
    """Построить событие из группы последовательных дней изменения."""
    price_before = float(df.loc[start_idx - 1, 'price_per_unit'])
    price_after = float(df.loc[end_idx, 'price_per_unit'])
    change_pct = (price_after - price_before) / price_before * 100 if price_before > 0 else 0.0
    direction = 'increase' if change_pct > 0 else 'decrease'

    return {
        'date': str(df.loc[start_idx, 'date'].date()),
        'price_before': round(price_before, 2),
        'price_after': round(price_after, 2),
        'change_pct': round(change_pct, 2),
        'direction': direction,
    }


def measure_post_change_impact(
    data: list[dict],
    change_date: str,
    window_days: int = 14,
) -> dict:
    """
    Измеряет влияние изменения цены на метрики (до vs после).

    Args:
        data: полный таймсерия
        change_date: дата изменения (YYYY-MM-DD)
        window_days: окно сравнения (по умолчанию 14 дней)

    Returns:
        dict с before/after средними для margin_pct, orders_count, revenue
        и статистической значимостью (t-test)
    """
    df = pd.DataFrame(data)

    if 'date' not in df.columns:
        return {'error': 'missing_date_column'}

    df['date'] = pd.to_datetime(df['date'])
    change_dt = pd.to_datetime(change_date)

    before_mask = (df['date'] >= change_dt - pd.Timedelta(days=window_days)) & (df['date'] < change_dt)
    after_mask = (df['date'] > change_dt) & (df['date'] <= change_dt + pd.Timedelta(days=window_days))

    df_before = df[before_mask]
    df_after = df[after_mask]

    if len(df_before) < _MIN_WINDOW_POINTS or len(df_after) < _MIN_WINDOW_POINTS:
        return {
            'error': 'insufficient_window_data',
            'before_points': len(df_before),
            'after_points': len(df_after),
            'min_required': _MIN_WINDOW_POINTS,
        }

    metrics_to_compare = ['margin_pct', 'orders_count', 'revenue']
    available_metrics = [m for m in metrics_to_compare if m in df.columns]

    if not available_metrics:
        return {'error': 'no_metrics_available', 'expected': metrics_to_compare}

    result = {
        'change_date': change_date,
        'window_days': window_days,
        'before_points': len(df_before),
        'after_points': len(df_after),
        'metrics': {},
    }

    for metric in available_metrics:
        before_vals = df_before[metric].dropna().values
        after_vals = df_after[metric].dropna().values

        if len(before_vals) < _MIN_WINDOW_POINTS or len(after_vals) < _MIN_WINDOW_POINTS:
            result['metrics'][metric] = {
                'error': 'insufficient_nonnan_data',
                'before_nonnan': len(before_vals),
                'after_nonnan': len(after_vals),
            }
            continue

        mean_before = float(np.mean(before_vals))
        mean_after = float(np.mean(after_vals))
        metric_change_pct = (
            (mean_after - mean_before) / abs(mean_before) * 100
            if abs(mean_before) > 1e-10
            else 0.0
        )

        # t-тест: проверяем значимость различия
        t_stat, p_value = stats.ttest_ind(before_vals, after_vals, equal_var=False)

        result['metrics'][metric] = {
            'mean_before': round(mean_before, 3),
            'mean_after': round(mean_after, 3),
            'change_pct': round(metric_change_pct, 2),
            't_statistic': round(float(t_stat), 3),
            'p_value': round(float(p_value), 4),
            'is_significant': float(p_value) < 0.05,
        }

    return result


def classify_price_decisions(
    events_with_impacts: list[dict],
) -> list[dict]:
    """
    Классифицирует каждое ценовое решение как improved/worsened/neutral.

    Logic:
    - improved: margin_pct increased OR (orders_count increased AND margin_pct stable)
    - worsened: margin_pct decreased AND orders_count decreased
    - neutral: no significant change or mixed results

    Args:
        events_with_impacts: список dict, каждый содержит ключи event и impact
            (результаты detect_price_change_events и measure_post_change_impact)

    Returns:
        Список dict с добавленным ключом classification
    """
    classified = []

    for item in events_with_impacts:
        event = item.get('event', {})
        impact = item.get('impact', {})

        if impact.get('error'):
            classified.append({
                **item,
                'classification': 'insufficient_data',
                'reason': impact.get('error'),
            })
            continue

        metrics = impact.get('metrics', {})
        margin_info = metrics.get('margin_pct', {})
        orders_info = metrics.get('orders_count', {})

        margin_change = margin_info.get('change_pct', 0.0)
        margin_sig = margin_info.get('is_significant', False)
        orders_change = orders_info.get('change_pct', 0.0)
        orders_sig = orders_info.get('is_significant', False)

        # Классификация
        if margin_sig and margin_change > 0:
            classification = 'improved'
            reason = f'margin_pct +{margin_change:.1f}% (significant)'
        elif orders_sig and orders_change > 0 and (not margin_sig or margin_change >= -1.0):
            classification = 'improved'
            reason = f'orders_count +{orders_change:.1f}%, margin stable'
        elif margin_change < 0 and orders_change < 0:
            classification = 'worsened'
            reason = f'margin_pct {margin_change:.1f}%, orders {orders_change:.1f}%'
        else:
            classification = 'neutral'
            reason = f'mixed/insignificant: margin {margin_change:+.1f}%, orders {orders_change:+.1f}%'

        classified.append({
            **item,
            'classification': classification,
            'reason': reason,
        })

    return classified


def summarize_pricing_patterns(
    data: list[dict],
    min_change_pct: float = 3.0,
    window_days: int = 14,
) -> dict:
    """
    Полный анализ ценовых паттернов: обнаружение -> измерение -> классификация -> агрегация.

    Это основная entry-point функция.

    Args:
        data: ежедневные данные из data_layer (date, price_per_unit, margin_pct, orders_count, ...)
        min_change_pct: минимальный порог изменения цены в %
        window_days: окно для before/after сравнения

    Returns:
        dict:
        - total_events: int
        - increases: {count, avg_change_pct, improved_pct, avg_margin_impact}
        - decreases: {count, avg_change_pct, improved_pct, avg_margin_impact}
        - events: list of individual classified events
        - insights: list of str (текстовые инсайты)
    """
    if len(data) < 2 * window_days + 2:
        return {
            'error': 'insufficient_data',
            'n_observations': len(data),
            'min_required': 2 * window_days + 2,
        }

    # 1. Обнаружение событий
    events = detect_price_change_events(data, min_change_pct=min_change_pct)

    if not events:
        return {
            'total_events': 0,
            'increases': _empty_direction_summary(),
            'decreases': _empty_direction_summary(),
            'events': [],
            'insights': ['Значимых изменений цены не обнаружено в указанном периоде.'],
        }

    # 2. Измерение эффекта каждого события
    events_with_impacts = []
    for event in events:
        try:
            impact = measure_post_change_impact(
                data=data,
                change_date=event['date'],
                window_days=window_days,
            )
            events_with_impacts.append({'event': event, 'impact': impact})
        except Exception as e:
            logger.warning(f"Failed to measure impact for event {event['date']}: {e}")
            events_with_impacts.append({
                'event': event,
                'impact': {'error': f'measurement_failed: {e}'},
            })

    # 3. Классификация
    classified = classify_price_decisions(events_with_impacts)

    # 4. Агрегация по направлениям
    increases = [e for e in classified if e['event']['direction'] == 'increase']
    decreases = [e for e in classified if e['event']['direction'] == 'decrease']

    increase_summary = _aggregate_direction(increases)
    decrease_summary = _aggregate_direction(decreases)

    # 5. Генерация текстовых инсайтов
    insights = _generate_insights(increases, decreases, increase_summary, decrease_summary)

    return {
        'total_events': len(classified),
        'increases': increase_summary,
        'decreases': decrease_summary,
        'events': classified,
        'insights': insights,
    }


def _empty_direction_summary() -> dict:
    """Пустой summary для направления без событий."""
    return {
        'count': 0,
        'avg_change_pct': 0.0,
        'improved_pct': 0.0,
        'avg_margin_impact': 0.0,
    }


def _aggregate_direction(classified_events: list[dict]) -> dict:
    """Агрегация статистики по направлению (increase или decrease)."""
    if not classified_events:
        return _empty_direction_summary()

    count = len(classified_events)

    # Средний % изменения цены
    change_pcts = [e['event']['change_pct'] for e in classified_events]
    avg_change_pct = float(np.mean(change_pcts))

    # Доля improved
    improved_count = sum(1 for e in classified_events if e.get('classification') == 'improved')
    improved_pct = improved_count / count * 100 if count > 0 else 0.0

    # Средний эффект на margin_pct
    margin_impacts = []
    for e in classified_events:
        margin_info = e.get('impact', {}).get('metrics', {}).get('margin_pct', {})
        if 'change_pct' in margin_info:
            margin_impacts.append(margin_info['change_pct'])
    avg_margin_impact = float(np.mean(margin_impacts)) if margin_impacts else 0.0

    return {
        'count': count,
        'avg_change_pct': round(avg_change_pct, 2),
        'improved_pct': round(improved_pct, 1),
        'avg_margin_impact': round(avg_margin_impact, 2),
    }


def _generate_insights(
    increases: list[dict],
    decreases: list[dict],
    increase_summary: dict,
    decrease_summary: dict,
) -> list[str]:
    """Генерация текстовых инсайтов на основе агрегированных данных."""
    insights = []

    # Инсайт по повышениям цены
    if increase_summary['count'] > 0:
        pct = increase_summary['improved_pct']
        margin_impact = increase_summary['avg_margin_impact']
        if margin_impact > 0:
            insights.append(
                f"{pct:.0f}% повышений цены привели к росту маржи "
                f"в среднем на +{margin_impact:.1f} п.п."
            )
        elif margin_impact < 0:
            insights.append(
                f"Повышения цены в среднем снижали маржу на {margin_impact:.1f} п.п. "
                f"(улучшение только в {pct:.0f}% случаев)"
            )

    # Инсайт по снижениям цены
    if decrease_summary['count'] > 0:
        # Оценка эффекта на объём
        orders_impacts = []
        for e in decreases:
            orders_info = e.get('impact', {}).get('metrics', {}).get('orders_count', {})
            if 'change_pct' in orders_info:
                orders_impacts.append(orders_info['change_pct'])
        if orders_impacts:
            avg_orders_impact = float(np.mean(orders_impacts))
            avg_price_drop = abs(decrease_summary['avg_change_pct'])
            if avg_orders_impact > 0:
                insights.append(
                    f"Снижения цены на >{avg_price_drop:.0f}% обычно увеличивают "
                    f"объём на {avg_orders_impact:.0f}% в первые 2 недели"
                )
            else:
                insights.append(
                    f"Снижения цены на >{avg_price_drop:.0f}% не дали ожидаемого "
                    f"роста объёма (средний эффект: {avg_orders_impact:+.0f}%)"
                )

    # Инсайт по оптимальному диапазону изменений
    improved_events = [
        e for e in (increases + decreases)
        if e.get('classification') == 'improved'
    ]
    if len(improved_events) >= 2:
        improved_changes = [abs(e['event']['change_pct']) for e in improved_events]
        min_good = min(improved_changes)
        max_good = max(improved_changes)
        insights.append(
            f"Наиболее результативные изменения: "
            f"{'повышение' if len(increases) > len(decreases) else 'изменение'} "
            f"на {min_good:.0f}-{max_good:.0f}%"
        )

    if not insights:
        insights.append('Недостаточно данных для формирования инсайтов.')

    return insights
