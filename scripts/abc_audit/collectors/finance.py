"""Коллектор финансовых данных: выручка, маржа по артикулам."""
from __future__ import annotations

from collections import defaultdict

from shared.data_layer.article import get_wb_by_article, get_ozon_by_article
from scripts.abc_audit.utils import safe_float


# Числовые ключи из data_layer, которые суммируются при merge WB + OZON
_SUM_KEYS = (
    "orders_count",
    "sales_count",
    "revenue",
    "margin",
    "adv_internal",
    "adv_external",
    "adv_total",
)


def _empty_article() -> dict:
    return {k: 0.0 for k in _SUM_KEYS}


def _merge_channel(target: dict, source: dict) -> None:
    """Суммирует числовые поля из source в target."""
    for key in _SUM_KEYS:
        val = safe_float(source.get(key))
        if val is not None:
            target[key] = target.get(key, 0.0) + val


def _collect_period(start: str, end: str) -> dict[str, dict]:
    """Собирает WB+OZON данные за один период и мержит по артикулу."""
    merged: dict[str, dict] = defaultdict(_empty_article)

    for row in get_wb_by_article(start, end):
        article = (row.get("article") or "").lower()
        if not article:
            continue
        _merge_channel(merged[article], row)
        merged[article]["model"] = row.get("model", "")

    for row in get_ozon_by_article(start, end):
        article = (row.get("article") or "").lower()
        if not article:
            continue
        _merge_channel(merged[article], row)
        if not merged[article].get("model"):
            merged[article]["model"] = row.get("model", "")

    return dict(merged)


def collect_finance(
    p30_start: str,
    p30_end: str,
    p90_start: str,
    p90_end: str,
    p180_start: str,
    p180_end: str,
    m1_start: str = "",
    m1_end: str = "",
    m2_start: str = "",
    m2_end: str = "",
    m3_start: str = "",
    m3_end: str = "",
) -> dict:
    """Собирает финансовые данные по артикулам за 3 периода + помесячную разбивку.

    Returns:
        {"finance": {article: {revenue_30d, margin_30d, ..., revenue_m1, ...}}}
    """
    data_30 = _collect_period(p30_start, p30_end)
    data_90 = _collect_period(p90_start, p90_end)
    data_180 = _collect_period(p180_start, p180_end)

    # Monthly breakdown (optional)
    monthly: dict[str, dict[str, dict]] = {}
    monthly_suffixes = ("m1", "m2", "m3")
    monthly_ranges = (
        (m1_start, m1_end),
        (m2_start, m2_end),
        (m3_start, m3_end),
    )
    for suffix, (ms, me) in zip(monthly_suffixes, monthly_ranges):
        if ms and me:
            monthly[suffix] = _collect_period(ms, me)

    all_articles = set(data_30) | set(data_90) | set(data_180)
    for suffix, period_data in monthly.items():
        all_articles |= set(period_data)

    result: dict[str, dict] = {}

    for article in all_articles:
        entry: dict = {"article": article}
        d30 = data_30.get(article, _empty_article())
        d90 = data_90.get(article, _empty_article())
        d180 = data_180.get(article, _empty_article())

        entry["model"] = (
            d30.get("model") or d90.get("model") or d180.get("model", "")
        )

        for key in _SUM_KEYS:
            entry[f"{key}_30d"] = d30.get(key, 0.0)
            entry[f"{key}_90d"] = d90.get(key, 0.0)
            entry[f"{key}_180d"] = d180.get(key, 0.0)

        # Вычисляемые метрики
        rev30 = entry["revenue_30d"]
        mar30 = entry["margin_30d"]
        entry["margin_pct_30d"] = round(mar30 / rev30 * 100, 1) if rev30 else 0.0

        rev90 = entry["revenue_90d"]
        mar90 = entry["margin_90d"]
        entry["margin_pct_90d"] = round(mar90 / rev90 * 100, 1) if rev90 else 0.0

        adv30 = entry.get("adv_total_30d", 0.0)
        entry["drr_30d"] = round(adv30 / rev30 * 100, 1) if rev30 else 0.0

        # Monthly breakdown metrics
        for suffix in monthly_suffixes:
            if suffix not in monthly:
                continue
            dm = monthly[suffix].get(article, _empty_article())
            for key in _SUM_KEYS:
                entry[f"{key}_{suffix}"] = dm.get(key, 0.0)
            rev_m = entry[f"revenue_{suffix}"]
            mar_m = entry[f"margin_{suffix}"]
            entry[f"margin_pct_{suffix}"] = (
                round(mar_m / rev_m * 100, 1) if rev_m else 0.0
            )
            adv_m = entry.get(f"adv_total_{suffix}", 0.0)
            entry[f"drr_{suffix}"] = (
                round(adv_m / rev_m * 100, 1) if rev_m else 0.0
            )

        result[article] = entry

    return {"finance": result}
