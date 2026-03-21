"""Shared SQL fragments and constants used across data layer modules."""

__all__ = ["WB_MARGIN_SQL", "MAX_TURNOVER_DAYS", "MIN_DAILY_SALES"]

WB_MARGIN_SQL = """
    SUM(marga) - SUM(nds) - SUM(reclama_vn)
    - COALESCE(SUM(reclama_vn_vk), 0)
    - COALESCE(SUM(reclama_vn_creators), 0)
"""
# reclama = внутренняя реклама МП (Поиск/Автореклама), reclama_vn = внешняя (блогеры/ВК), reclama_vn_vk = ВК,
# reclama_vn_creators = блогеры — отдельные поля.
# Верифицировано 18.02.2026: расхождение с OneScreen 0.03 руб на 14.9 млн (< 0.001%).
# Поле `marga` уже включает все возвраты (revenue_return_spp, sebes_return и т.д.).

MAX_TURNOVER_DAYS = 365  # Cap: свыше 1 года = мёртвый сток
MIN_DAILY_SALES = 0.05  # < 1 продажи за 20 дней = недостаточно данных
