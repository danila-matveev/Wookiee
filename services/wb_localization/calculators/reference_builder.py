"""Строит структуру данных для листа «Справочник» (пояснительная документация)."""
from __future__ import annotations

import math
from typing import Any

from services.wb_localization.irp_coefficients import (
    COEFF_TABLE,
    REDISTRIBUTION_LIMITS,
)


def _ktr_color(ktr: float) -> str:
    """Цвет строки в таблице КТР по значению множителя."""
    if ktr <= 0.90:
        return "green"
    if ktr <= 1.00:
        return "yellow"
    return "red"


def _weeks_until_threshold(current_loc: float, target: float = 60.0) -> str:
    """Оценка: сколько недель до достижения порога при идеальной локализации в новых неделях.

    Формула: blended(t) = ((13-t)*current + t*100) / 13 >= target
    => t >= (target*13 - 13*current) / (100 - current)
    """
    if current_loc >= target:
        return "порог достигнут"
    t_exact = (target * 13 - 13 * current_loc) / (100 - current_loc)
    t_ceil = math.ceil(t_exact)
    return f"{t_ceil} недель"


def build_reference_content() -> dict[str, Any]:
    """Собирает структуру данных справочника.

    Returns:
        Словарь с 8 секциями: cover, formula_block, il_section, irp_section,
        exceptions, relocation_section, sliding_window, disclaimer.
    """
    # KTR table
    ktr_table = []
    for min_loc, max_loc, ktr, krp in COEFF_TABLE:
        ktr_table.append({
            "min_loc": min_loc,
            "max_loc": max_loc,
            "ktr": ktr,
            "description": (
                "Скидка" if ktr < 1.0
                else "Базовый" if ktr == 1.0
                else "Штраф"
            ),
            "color": _ktr_color(ktr),
        })

    # KRP table
    krp_table = []
    for min_loc, max_loc, ktr, krp in COEFF_TABLE:
        krp_table.append({
            "min_loc": min_loc,
            "max_loc": max_loc,
            "krp_pct": krp,
            "description": "Нет надбавки" if krp == 0 else f"+{krp:.2f}% к цене",
            "color": "green" if krp == 0 else "red",
        })

    # Warehouses with limits
    warehouses = [
        {"name": name, "limit_per_day": limit}
        for name, limit in sorted(
            REDISTRIBUTION_LIMITS.items(),
            key=lambda x: -x[1],
        )
    ]

    # Weeks to threshold table
    weeks_table = [
        {"from_loc": loc, "to_loc": 60.0, "weeks": _weeks_until_threshold(loc)}
        for loc in [30, 40, 45, 50, 55, 58]
    ]

    return {
        "cover": {
            "title": "📘 СПРАВОЧНИК: ИЛ, ИРП и перестановки",
            "subtitle": "Полная документация по логистике Wildberries",
        },
        "formula_block": {
            "formula": "Логистика = (База × Коэф.склада × ИЛ) + (Цена × ИРП%)",
            "components": [
                {"name": "База", "desc": "Стоимость 1 литра + доп. литры"},
                {"name": "Коэф.склада", "desc": "Индивидуален для каждого склада WB"},
                {"name": "ИЛ", "desc": "Индекс локализации (КТР-множитель, 0.50–2.00)"},
                {"name": "ИРП%", "desc": "Надбавка к цене (0.00–2.50%)"},
            ],
            "example": {
                "price": 1000,
                "volume_liters": 3,
                "base": 74.0,  # 46 + 2*14
                "warehouse_coeff": 1.0,
                "article_loc_pct": 45.0,
                "article_ktr": 1.20,
                "article_krp_pct": 2.05,
                "cabinet_il": 1.05,
                "cabinet_irp_pct": 1.15,
                "volume_part": 77.70,
                "price_part": 11.50,
                "total": 89.20,
            },
        },
        "il_section": {
            "title": "Индекс локализации (ИЛ)",
            "definition": (
                "Локальный заказ = склад отгрузки и адрес доставки "
                "в одном федеральном округе (или объединённой зоне)."
            ),
            "formula": "ИЛ = Σ(заказы_артикула × КТР_артикула) / Всего_заказов",
            "period_note": "Скользящие 13 недель. Обновление — воскресенье→понедельник.",
            "table": ktr_table,
            "example": {
                "loc_pct": 40,
                "ktr": 1.30,
                "meaning": "платите 1.30× базовой логистики = +30%",
            },
        },
        "irp_section": {
            "title": "Индекс распределения продаж (ИРП)",
            "definition": "ИРП оценивает распределение локализации по артикулам.",
            "formula": "ИРП = Σ(заказы_артикула × КРП%_артикула) / Всего_заказов",
            "critical_threshold": {
                "value": 60.0,
                "note": "При локализации 60%+ КРП резко падает с 2.00% до 0.00%",
            },
            "table": krp_table,
            "example": {
                "article_loc": 55,
                "price": 1000,
                "orders_monthly": 500,
                "krp_pct": 2.00,
                "irp_monthly_rub": 10000,
            },
        },
        "exceptions": {
            "categories": ["КГТ", "СГТ", "КБТ", "FBS"],
            "rule_35": (
                "Если исключений > 35% от всех заказов артикула, "
                "ВЕСЬ артикул становится исключением (КРП=0%, не считается в ИЛ/ИРП)."
            ),
            "krp_for_exceptions": 0.0,
        },
        "relocation_section": {
            "title": "Перераспределение товаров (перестановки)",
            "commission_pct": 0.5,
            "lock_in_days": 90,
            "description": (
                "Опт-ин сервис в Конструкторе тарифов. Позволяет вручную перемещать "
                "сток между складами WB. Комиссия +0.5% на ВСЕ продажи, не только "
                "перемещённые. Отключить нельзя раньше 90 дней."
            ),
            "warehouses": warehouses,
            "economics_example": {
                "turnover_monthly": 5_000_000,
                "commission_monthly": 25_000,
                "breakeven": "экономия на логистике > 25 000 ₽/мес",
            },
        },
        "sliding_window": {
            "title": "Скользящее окно 13 недель",
            "explanation": (
                "Индекс считается за 13 последних календарных недель. "
                "Одна неделя идеальной локализации даёт +1/13 к индексу."
            ),
            "formula": "loc_week_t = ((13 - t) × loc_before + t × loc_after) / 13",
            "weeks_to_threshold": weeks_table,
            "call_to_action": (
                "Начинать перестановки надо СЕЙЧАС — эффект отложенный на 2–9 недель."
            ),
        },
        "disclaimer": {
            "title": "Наш расчёт vs WB",
            "note": (
                "Наш расчёт — на календарных днях. WB — на ISO-неделях. "
                "Расхождение ≤ 3 п.п. Точные значения — в ЛК WB."
            ),
        },
    }
