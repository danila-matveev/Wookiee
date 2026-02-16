"""
Stock Price Optimizer — наложение складских ограничений на ценовые рекомендации.

Ключевая идея: уровень остатков на складе должен ограничивать ценовые решения.

Логика:
- Если товар заканчивается (< 1 недели) → нельзя снижать цену, иначе спрос вырастет,
  а товара не будет — потеря выручки и рейтинга.
- Если товар залежался (> 16 недель) → нужно снижать цену, чтобы ускорить оборот
  и освободить склад.
- Здоровый запас (2–8 недель) → ценовые решения принимаются свободно.

Пороги запаса (в неделях):
    CRITICAL_LOW_WEEKS  = 1    критический дефицит
    LOW_STOCK_WEEKS     = 2    низкий запас
    HEALTHY_MAX_WEEKS   = 8    верхняя граница здорового запаса
    OVERSTOCKED_WEEKS   = 16   затоваривание
"""
import logging
from copy import deepcopy

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Пороги запаса (в неделях обеспеченности)
# ---------------------------------------------------------------------------
CRITICAL_LOW_WEEKS = 1
LOW_STOCK_WEEKS = 2
HEALTHY_MAX_WEEKS = 8
OVERSTOCKED_WEEKS = 16

# Умеренное снижение цены при принудительном действии (%)
_FORCED_DECREASE_PCT = -5.0

# Маппинг статус → ценовое ограничение
_STATUS_TO_CONSTRAINT = {
    'critical_low': 'no_decrease',
    'low': 'no_decrease',
    'healthy': 'no_constraint',
    'overstocked': 'prefer_decrease',
    'severely_overstocked': 'force_decrease',
}


# ===================================================================
#  1. assess_stock_health
# ===================================================================

def assess_stock_health(
    turnover_days: float,
    avg_stock: float,
    daily_sales: float,
) -> dict:
    """
    Оценка здоровья остатков для одной модели.

    Args:
        turnover_days: оборачиваемость в днях (из turnover-отчёта).
        avg_stock: средний остаток на складе (штуки).
        daily_sales: средние дневные продажи (штуки).

    Returns:
        dict:
            weeks_supply   — обеспеченность в неделях
            status         — строковый статус
            price_constraint — ценовое ограничение
            turnover_days  — входной параметр (для удобства)
            avg_stock      — входной параметр
            daily_sales    — входной параметр
            reasoning      — человекочитаемое обоснование (RU)
    """
    # --- weeks_supply -------------------------------------------------------
    if daily_sales > 0:
        weeks_supply = avg_stock / (daily_sales * 7)
    else:
        # Нет продаж — если есть остаток, это перезатоваривание;
        # если остатка тоже нет — данные отсутствуют.
        weeks_supply = 0.0 if avg_stock == 0 else float('inf')

    # --- status -------------------------------------------------------------
    if weeks_supply == float('inf'):
        status = 'severely_overstocked'
    elif weeks_supply < CRITICAL_LOW_WEEKS:
        status = 'critical_low'
    elif weeks_supply < LOW_STOCK_WEEKS:
        status = 'low'
    elif weeks_supply <= HEALTHY_MAX_WEEKS:
        status = 'healthy'
    elif weeks_supply <= OVERSTOCKED_WEEKS:
        status = 'overstocked'
    else:
        status = 'severely_overstocked'

    # --- price_constraint ---------------------------------------------------
    price_constraint = _STATUS_TO_CONSTRAINT[status]

    # --- reasoning ----------------------------------------------------------
    reasoning = _build_stock_reasoning(
        weeks_supply, status, price_constraint, avg_stock, daily_sales,
    )

    logger.debug(
        "assess_stock_health: avg_stock=%.1f daily_sales=%.2f → "
        "weeks_supply=%.1f status=%s constraint=%s",
        avg_stock, daily_sales, weeks_supply, status, price_constraint,
    )

    return {
        'weeks_supply': round(weeks_supply, 2) if weeks_supply != float('inf') else None,
        'status': status,
        'price_constraint': price_constraint,
        'turnover_days': turnover_days,
        'avg_stock': avg_stock,
        'daily_sales': daily_sales,
        'reasoning': reasoning,
    }


def _build_stock_reasoning(
    weeks_supply: float,
    status: str,
    price_constraint: str,
    avg_stock: float,
    daily_sales: float,
) -> str:
    """Формирование человекочитаемого обоснования на русском языке."""

    if weeks_supply == float('inf'):
        return (
            f"Остаток {avg_stock:.0f} шт., продаж нет. "
            "Товар не продаётся — рекомендуется значительное снижение цены "
            "или вывод из ассортимента."
        )

    ws_display = f"{weeks_supply:.1f}"

    if status == 'critical_low':
        return (
            f"Критически низкий запас: {ws_display} нед. "
            f"(остаток {avg_stock:.0f} шт., продажи {daily_sales:.1f} шт./день). "
            "Снижение цены запрещено — при росте спроса товар закончится, "
            "что приведёт к потере рейтинга карточки."
        )

    if status == 'low':
        return (
            f"Низкий запас: {ws_display} нед. "
            f"(остаток {avg_stock:.0f} шт., продажи {daily_sales:.1f} шт./день). "
            "Не рекомендуется снижать цену до пополнения склада."
        )

    if status == 'healthy':
        return (
            f"Здоровый запас: {ws_display} нед. "
            f"(остаток {avg_stock:.0f} шт., продажи {daily_sales:.1f} шт./день). "
            "Ограничений по цене нет — решение принимается на основе "
            "эластичности и маржинальности."
        )

    if status == 'overstocked':
        return (
            f"Затоваривание: {ws_display} нед. "
            f"(остаток {avg_stock:.0f} шт., продажи {daily_sales:.1f} шт./день). "
            "Желательно снизить цену для ускорения оборота и "
            "освобождения складских мощностей."
        )

    # severely_overstocked
    return (
        f"Сильное затоваривание: {ws_display} нед. "
        f"(остаток {avg_stock:.0f} шт., продажи {daily_sales:.1f} шт./день). "
        "Необходимо снижение цены — товар занимает склад и замораживает "
        "оборотные средства."
    )


# ===================================================================
#  2. generate_stock_aware_recommendation
# ===================================================================

def generate_stock_aware_recommendation(
    price_recommendation: dict,
    stock_health: dict,
    turnover_days: float,
) -> dict:
    """
    Наложение складских ограничений на ценовую рекомендацию.

    Берёт существующую рекомендацию из recommendation_engine и модифицирует
    действие, если складская ситуация этого требует.

    Args:
        price_recommendation: dict из generate_recommendations()
            (обязательное поле 'action': 'increase_price' | 'decrease_price' | 'hold')
        stock_health: dict из assess_stock_health()
        turnover_days: оборачиваемость в днях

    Returns:
        dict — копия рекомендации с добавленными полями:
            stock_override   — True, если действие было изменено
            stock_reasoning  — обоснование изменения (RU)
            original_action  — исходное действие до наложения
            stock_health     — результат assess_stock_health
    """
    result = deepcopy(price_recommendation)
    original_action = result.get('action', 'hold')
    constraint = stock_health.get('price_constraint', 'no_constraint')
    status = stock_health.get('status', 'healthy')

    stock_override = False
    stock_reasoning = ""

    # --- Правило 1: запрет на снижение при дефиците -------------------------
    if original_action == 'decrease_price' and constraint == 'no_decrease':
        result['action'] = 'hold'
        stock_override = True
        stock_reasoning = (
            f"Снижение цены отменено: статус остатков «{_status_label(status)}» "
            f"({stock_health.get('weeks_supply', '?')} нед. обеспеченности). "
            "При текущем уровне запаса снижение цены приведёт к "
            "ускоренному вымыванию остатков без возможности допоставки."
        )
        logger.info(
            "Stock override: decrease_price → hold (status=%s, weeks=%.1f)",
            status, stock_health.get('weeks_supply', 0),
        )

    # --- Правило 2: нельзя повышать цену при затоваривании ------------------
    elif original_action == 'increase_price' and status == 'severely_overstocked':
        result['action'] = 'decrease_price'
        stock_override = True
        # Устанавливаем параметры умеренного снижения
        if 'recommended' not in result:
            result['recommended'] = {}
        result['recommended']['price_change_pct'] = _FORCED_DECREASE_PCT
        stock_reasoning = (
            f"Повышение цены заменено на снижение: статус остатков "
            f"«{_status_label(status)}» ({stock_health.get('weeks_supply', '?')} нед.). "
            "Склад критически перегружен — необходимо ускорить оборот."
        )
        logger.info(
            "Stock override: increase_price → decrease_price "
            "(status=%s, weeks=%.1f)",
            status, stock_health.get('weeks_supply', 0),
        )

    elif original_action == 'increase_price' and status == 'overstocked':
        result['action'] = 'hold'
        stock_override = True
        stock_reasoning = (
            f"Повышение цены отменено: статус остатков "
            f"«{_status_label(status)}» ({stock_health.get('weeks_supply', '?')} нед.). "
            "При текущем уровне затоваривания повышение цены "
            "замедлит оборот и усугубит проблему."
        )
        logger.info(
            "Stock override: increase_price → hold (status=%s, weeks=%.1f)",
            status, stock_health.get('weeks_supply', 0),
        )

    # --- Правило 3: hold при сильном затоваривании → принудительное снижение -
    elif original_action == 'hold' and status == 'severely_overstocked':
        result['action'] = 'decrease_price'
        stock_override = True
        if 'recommended' not in result:
            result['recommended'] = {}
        result['recommended']['price_change_pct'] = _FORCED_DECREASE_PCT
        stock_reasoning = (
            f"Удержание цены заменено на снижение ({_FORCED_DECREASE_PCT}%): "
            f"статус остатков «{_status_label(status)}» "
            f"({stock_health.get('weeks_supply', '?')} нед.). "
            "Товар замораживает оборотные средства — необходимы активные "
            "меры по ускорению продаж."
        )
        logger.info(
            "Stock override: hold → decrease_price "
            "(status=%s, weeks=%.1f, forced=%s%%)",
            status, stock_health.get('weeks_supply', 0), _FORCED_DECREASE_PCT,
        )

    else:
        stock_reasoning = (
            f"Складское ограничение не применено: статус «{_status_label(status)}», "
            f"действие «{original_action}» — совместимы."
        )

    # --- Добавляем складские поля к результату ------------------------------
    result['stock_override'] = stock_override
    result['stock_reasoning'] = stock_reasoning
    result['original_action'] = original_action
    result['stock_health'] = stock_health

    return result


def _status_label(status: str) -> str:
    """Человекочитаемая метка статуса для логов и reasoning."""
    labels = {
        'critical_low': 'критический дефицит',
        'low': 'низкий запас',
        'healthy': 'здоровый запас',
        'overstocked': 'затоваривание',
        'severely_overstocked': 'сильное затоваривание',
    }
    return labels.get(status, status)


# ===================================================================
#  3. generate_stock_price_matrix
# ===================================================================

def generate_stock_price_matrix(
    models_metrics: list[dict],
    stock_data: dict,
    turnover_data: dict,
    elasticities: dict | None = None,
) -> dict:
    """
    Построение матрицы «остатки × цена» по всем моделям.

    Для каждой модели совмещает данные о марже, остатках и оборачиваемости,
    формируя единую таблицу для принятия решений.

    Args:
        models_metrics: list[dict] — метрики моделей из
            get_*_price_margin_by_model_period (поля: model, margin_pct, ...).
        stock_data: dict {model_lower: avg_stock} — средний остаток по моделям.
        turnover_data: dict {model_lower: {turnover_days, daily_sales, ...}} —
            данные об оборачиваемости.
        elasticities: dict {model_lower: {elasticity: float, ...}} —
            предвычисленные эластичности (опционально).

    Returns:
        dict:
            matrix         — list[dict] строка на каждую модель
            urgent_actions — list[dict] модели, требующие срочных действий
            summary        — текстовая сводка
    """
    if elasticities is None:
        elasticities = {}

    matrix: list[dict] = []
    urgent_actions: list[dict] = []

    # Счётчики для summary
    status_counts: dict[str, int] = {
        'critical_low': 0,
        'low': 0,
        'healthy': 0,
        'overstocked': 0,
        'severely_overstocked': 0,
        'no_data': 0,
    }

    for metrics_row in models_metrics:
        model = metrics_row.get('model', '').lower()
        margin_pct = metrics_row.get('margin_pct', 0.0)

        # --- Данные об остатках и оборачиваемости --------------------------
        avg_stock = stock_data.get(model, 0.0)
        turnover_info = turnover_data.get(model, {})
        turnover_days = turnover_info.get('turnover_days', 0.0)
        daily_sales = turnover_info.get('daily_sales', 0.0)

        # Если нет данных о продажах и остатках — пропускаем расчёт здоровья
        if avg_stock == 0 and daily_sales == 0:
            status_counts['no_data'] += 1
            matrix.append({
                'model': model,
                'stock_status': 'no_data',
                'weeks_supply': None,
                'turnover_days': turnover_days,
                'margin_pct': margin_pct,
                'recommended_action': 'need_data',
                'urgency': 'normal',
                'elasticity': elasticities.get(model, {}).get('elasticity'),
            })
            continue

        # --- Оценка здоровья остатков --------------------------------------
        stock_health = assess_stock_health(turnover_days, avg_stock, daily_sales)
        status = stock_health['status']
        weeks_supply = stock_health['weeks_supply']

        status_counts[status] = status_counts.get(status, 0) + 1

        # --- Рекомендуемое действие на основе остатков ---------------------
        recommended_action = _action_from_stock_status(status)

        # --- Срочность -----------------------------------------------------
        urgency = _urgency_from_status(status)

        # --- Эластичность (если есть) --------------------------------------
        model_elasticity = elasticities.get(model, {}).get('elasticity')

        row = {
            'model': model,
            'stock_status': status,
            'weeks_supply': weeks_supply,
            'turnover_days': turnover_days,
            'margin_pct': round(margin_pct, 2) if margin_pct else 0.0,
            'recommended_action': recommended_action,
            'urgency': urgency,
            'elasticity': model_elasticity,
        }
        matrix.append(row)

        if urgency != 'normal':
            urgent_actions.append(row)

    # --- Summary -----------------------------------------------------------
    summary = _build_matrix_summary(status_counts, len(models_metrics))

    logger.info(
        "generate_stock_price_matrix: %d моделей, %d срочных действий",
        len(matrix), len(urgent_actions),
    )

    return {
        'matrix': matrix,
        'urgent_actions': urgent_actions,
        'summary': summary,
    }


def _action_from_stock_status(status: str) -> str:
    """Определение рекомендуемого ценового действия по статусу остатков."""
    action_map = {
        'critical_low': 'hold_or_increase',
        'low': 'hold',
        'healthy': 'optimize',
        'overstocked': 'consider_decrease',
        'severely_overstocked': 'decrease_price',
    }
    return action_map.get(status, 'hold')


def _urgency_from_status(status: str) -> str:
    """Определение срочности действия по статусу остатков."""
    if status in ('critical_low', 'severely_overstocked'):
        return 'critical'
    if status in ('low', 'overstocked'):
        return 'high'
    return 'normal'


def _build_matrix_summary(status_counts: dict, total: int) -> str:
    """Формирование текстовой сводки по матрице."""
    parts = [f"Всего моделей: {total}."]

    labels = {
        'critical_low': 'критический дефицит',
        'low': 'низкий запас',
        'healthy': 'здоровый запас',
        'overstocked': 'затоваривание',
        'severely_overstocked': 'сильное затоваривание',
        'no_data': 'нет данных',
    }

    for key, label in labels.items():
        count = status_counts.get(key, 0)
        if count > 0:
            parts.append(f"  {label}: {count}")

    critical = status_counts.get('critical_low', 0)
    severely = status_counts.get('severely_overstocked', 0)
    if critical + severely > 0:
        parts.append(
            f"Требуют немедленного внимания: {critical + severely} "
            f"(дефицит: {critical}, затоваривание: {severely})."
        )

    return "\n".join(parts)
