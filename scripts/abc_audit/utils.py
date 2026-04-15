"""Утилиты для ABC-аудита: даты, quality flags, helpers."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional


def compute_abc_date_params(cut_date_str: str) -> dict:
    """Вычисляет все даты для ABC-аудита (30/90/180 дней назад от даты отсечки).

    Args:
        cut_date_str: Дата отсечки в формате YYYY-MM-DD.

    Returns:
        Словарь с датами всех периодов.
    """
    cut = date.fromisoformat(cut_date_str)

    p30_start = cut - timedelta(days=30)
    p90_start = cut - timedelta(days=90)
    p180_start = cut - timedelta(days=180)
    end_exclusive = cut + timedelta(days=1)

    year_ago_end = cut - timedelta(days=365)
    year_ago_start = year_ago_end - timedelta(days=30)

    # Monthly breakdown (3 consecutive 30-day windows within 90d)
    m1_start = p90_start  # oldest month
    m1_end = p90_start + timedelta(days=30)
    m2_start = m1_end
    m2_end = m2_start + timedelta(days=30)
    m3_start = m2_end  # = p30_start (latest month = last 30 days)
    m3_end = end_exclusive

    return {
        "cut_date": cut.isoformat(),
        "p30_start": p30_start.isoformat(),
        "p90_start": p90_start.isoformat(),
        "p180_start": p180_start.isoformat(),
        "p30_end_exclusive": end_exclusive.isoformat(),
        "p90_end_exclusive": end_exclusive.isoformat(),
        "p180_end_exclusive": end_exclusive.isoformat(),
        "year_ago_start": year_ago_start.isoformat(),
        "year_ago_end": year_ago_end.isoformat(),
        "m1_start": m1_start.isoformat(),
        "m1_end": m1_end.isoformat(),
        "m2_start": m2_start.isoformat(),
        "m2_end": m2_end.isoformat(),
        "m3_start": m3_start.isoformat(),
        "m3_end": m3_end.isoformat(),
        "days_30": 30,
        "days_90": 90,
        "days_180": 180,
    }


def build_abc_quality_flags(
    errors: dict,
    article_count: int,
    supabase_count: int,
    moysklad_stale: bool = False,
    ozon_buyout_available: bool = False,
) -> dict:
    """Строит quality flags для ABC-аудита.

    Args:
        errors: Словарь ошибок коллекторов {name: error_msg}.
        article_count: Количество артикулов с данными по продажам.
        supabase_count: Количество артикулов в Supabase (активные статусы).
        moysklad_stale: True если данные МойСклад устарели (>3 дней).
        ozon_buyout_available: True если OZON buyout аппроксимирован из finance.

    Returns:
        Словарь с флагами качества.
    """
    coverage = (article_count / supabase_count * 100) if supabase_count > 0 else 0.0

    return {
        "collector_errors": dict(errors),
        "coverage_pct": round(coverage, 1),
        "ozon_buyout_available": ozon_buyout_available,
        "moysklad_stale": moysklad_stale,
        "buyout_lag_3_21_days": True,
    }


def safe_float(val) -> Optional[float]:
    """Безопасное приведение к float."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Безопасное деление с дефолтом при нуле."""
    if not denominator:
        return default
    return numerator / denominator
