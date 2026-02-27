"""
Централизованный словарь переводов для ценовых отчётов.

Все технические термины → читаемый русский текст.
"""

# ── Названия факторов регрессии ──

FACTOR_NAMES_RU: dict[str, str] = {
    'price_per_unit': 'Цена за единицу, руб.',
    'spp_pct': 'СПП (скидка пост. покупателя), %',
    'drr_pct': 'ДРР (доля рекл. расходов), %',
    'logistics_per_unit': 'Логистика за единицу, руб.',
    'cogs_per_unit': 'Себестоимость за единицу, руб.',
    'price_x_drr': 'Взаимодействие: Цена × Реклама',
    'price_x_spp': 'Взаимодействие: Цена × СПП',
    'drr_lag1': 'ДРР с задержкой 1 день',
}

# ── Месяцы (для сезонных дамми month_N) ──

_MONTHS_RU = {
    1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
    5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
    9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь',
}

# ── Дни недели (для dow_N) ──

_DOW_RU = {
    0: 'Понедельник', 1: 'Вторник', 2: 'Среда', 3: 'Четверг',
    4: 'Пятница', 5: 'Суббота', 6: 'Воскресенье',
}

# ── Ценовые политики ──

POLICY_NAMES_RU: dict[str, str] = {
    'premium_hold': 'Премиальное удержание',
    'volume_play': 'Стимулирование объёма',
    'margin_squeeze': 'Повышение маржи',
    'clearance': 'Распродажа / вывод',
    'neutral': 'Текущая цена',
    'controlled_exit': 'Контролируемый вывод',
}

POLICY_EMOJI: dict[str, str] = {
    'premium_hold': '⚡',
    'volume_play': '📦',
    'margin_squeeze': '💰',
    'clearance': '🏷️',
    'neutral': '➖',
    'controlled_exit': '🔄',
}

POLICY_DESCRIPTIONS_RU: dict[str, str] = {
    'premium_hold': 'Товар продаётся стабильно по текущей цене — менять незачем.',
    'volume_play': 'Есть смысл снизить цену для ускорения продаж.',
    'margin_squeeze': 'Спрос неэластичен — можно повысить цену.',
    'clearance': 'Оборачиваемость критично низкая — нужна распродажа.',
    'neutral': 'Нет оснований для изменения цены.',
    'controlled_exit': 'Модель выводится. Остатки распродаются планово.',
}

# ── Действия ──

ACTION_NAMES_RU: dict[str, str] = {
    'hold': 'Удерживать',
    'increase': 'Повысить',
    'decrease': 'Снизить',
}

# ── ROI-категории ──

ROI_CATEGORY_RU: dict[str, str] = {
    'roi_leader': 'Лидер ROI',
    'healthy': 'Здоровый',
    'underperformer': 'Отстающий',
    'deadstock_risk': 'Риск залёживания',
}

# ── Направление бета-коэффициента ──

DIRECTION_RU: dict[str, str] = {
    'positive': 'положительное',
    'negative': 'отрицательное',
}

# ── Интерпретация эластичности ──

ELASTICITY_INTERP_RU: dict[str, str] = {
    'highly_inelastic': 'очень слабая (спрос почти не реагирует)',
    'inelastic': 'слабая (спрос слабо реагирует)',
    'unit_elastic': 'единичная (пропорциональная)',
    'elastic': 'сильная (спрос чувствителен)',
    'highly_elastic': 'очень сильная (спрос крайне чувствителен)',
}

# ── Приоритеты ──

PRIORITY_RU: dict[str, str] = {
    'high': 'высокий',
    'medium': 'средний',
    'low': 'низкий',
}


# ============================================================================
# Хелперы
# ============================================================================

def translate_factor(name: str) -> str:
    """Перевести техническое название фактора в русский."""
    if name in FACTOR_NAMES_RU:
        return FACTOR_NAMES_RU[name]

    # Сезонные: month_N
    if name.startswith('month_'):
        try:
            n = int(name.split('_')[1])
            return f'Сезонность: {_MONTHS_RU.get(n, name)}'
        except (ValueError, IndexError):
            pass

    # Дни недели: dow_N
    if name.startswith('dow_'):
        try:
            n = int(name.split('_')[1])
            return f'День недели: {_DOW_RU.get(n, name)}'
        except (ValueError, IndexError):
            pass

    return name


def translate_policy(policy: str) -> str:
    """Перевести код политики в русское название."""
    return POLICY_NAMES_RU.get(policy, policy)


def translate_roi_category(category: str) -> str:
    """Перевести ROI-категорию."""
    return ROI_CATEGORY_RU.get(category, category)


def translate_month(n: int) -> str:
    """Номер месяца → русское название."""
    return _MONTHS_RU.get(n, str(n))


def translate_dow(n: int) -> str:
    """Номер дня недели (0=пн) → русское название."""
    return _DOW_RU.get(n, str(n))


def interpret_elasticity(e: float) -> str:
    """Числовая эластичность → текстовая интерпретация на русском."""
    abs_e = abs(e)
    if abs_e < 0.5:
        return 'очень слабая (спрос почти не реагирует на цену)'
    elif abs_e < 1.0:
        return 'слабая (спрос слабо реагирует на цену)'
    elif abs_e < 1.2:
        return 'умеренная (спрос пропорционален цене)'
    elif abs_e < 2.0:
        return 'сильная (спрос чувствителен к цене)'
    else:
        return 'очень сильная (спрос крайне чувствителен к цене)'


def interpret_r2(r2: float) -> str:
    """R² → текстовая оценка качества модели."""
    if r2 >= 0.7:
        return 'хорошее'
    elif r2 >= 0.4:
        return 'умеренное'
    elif r2 >= 0.2:
        return 'слабое'
    else:
        return 'очень слабое'


def interpret_significance(p_value: float) -> str:
    """p-value → человекочитаемая значимость."""
    if p_value < 0.01:
        return 'высокозначимо'
    elif p_value < 0.05:
        return 'значимо'
    elif p_value < 0.1:
        return 'слабозначимо'
    else:
        return 'незначимо'


def factor_impact_text(name: str, beta: float, p_value: float) -> str:
    """Факторный коэффициент → текстовое описание влияния."""
    ru_name = translate_factor(name)
    is_sig = p_value < 0.05

    if beta > 0:
        direction_word = 'увеличивает'
        emoji = '📈'
    else:
        direction_word = 'снижает'
        emoji = '📉'

    if not is_sig:
        emoji = '⚪'
        return f'{emoji} **{ru_name}** — влияние незначимо (можно игнорировать).'

    abs_beta = abs(beta)
    if abs_beta > 0.3:
        strength = 'сильно'
    elif abs_beta > 0.15:
        strength = 'умеренно'
    else:
        strength = 'слабо'

    return f'{emoji} **{ru_name}** — {strength} {direction_word} маржу.'
