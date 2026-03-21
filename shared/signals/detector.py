"""Universal Signal Detector — finds patterns in any dataset."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Signal:
    id: str
    type: str
    category: str           # margin | turnover | funnel | adv | price | model
    severity: str           # info | warning | critical
    impact_on: str          # margin | turnover | both
    data: dict              # exact numbers for validator
    hint: str               # human-readable description (Russian)
    source: str             # which tool produced the data


def detect_signals(
    data: dict,
    kb_patterns: list[dict] | None = None,
) -> list[Signal]:
    """Detect patterns in data using base rules + KB patterns.

    Pure function: no network calls, no side effects.
    """
    if not data:
        return []

    kb_patterns = kb_patterns or []
    signals: list[Signal] = []

    # Dispatch to source-specific detectors
    source = data.get("_source", "")
    if source == "plan_vs_fact":
        signals.extend(_detect_plan_fact_signals(data))
    if source == "brand_finance":
        signals.extend(_detect_finance_signals(data))
    if source == "margin_levers":
        signals.extend(_detect_margin_lever_signals(data))

    # Apply KB patterns
    signals.extend(_detect_kb_pattern_signals(data, kb_patterns))

    return signals


def _detect_plan_fact_signals(data: dict) -> list[Signal]:
    signals = []
    brand = data.get("brand_total", {}).get("metrics", {})
    if not brand:
        return signals

    date_suffix = f"{data.get('days_elapsed', 0)}d"

    orders_pct = brand.get("orders_count", {}).get("completion_mtd_pct", 0) or 0
    margin_pct = brand.get("margin", {}).get("completion_mtd_pct", 0) or 0
    sales_pct = brand.get("sales_count", {}).get("completion_mtd_pct", 0) or 0
    adv_int_pct = brand.get("adv_internal", {}).get("completion_mtd_pct", 0) or 0
    adv_ext_pct = brand.get("adv_external", {}).get("completion_mtd_pct", 0) or 0

    # 1. margin_lags_orders: orders grow faster than margin (gap > 5 pp)
    gap = orders_pct - margin_pct
    if gap > 5:
        signals.append(Signal(
            id=f"margin_lags_orders_{date_suffix}",
            type="margin_lags_orders",
            category="margin",
            severity="warning" if gap < 15 else "critical",
            impact_on="margin",
            data={"orders_completion_pct": orders_pct, "margin_completion_pct": margin_pct, "gap_pct": round(gap, 1)},
            hint=f"Заказы опережают маржу на {round(gap, 1)} п.п. — возможен рост низкомаржинальных позиций",
            source="plan_vs_fact",
        ))

    # 2. sales_lag_expected: orders up but sales barely up (buyout lag)
    if orders_pct > 105 and sales_pct < orders_pct - 8:
        signals.append(Signal(
            id=f"sales_lag_expected_{date_suffix}",
            type="sales_lag_expected",
            category="funnel",
            severity="info",
            impact_on="turnover",
            data={"orders_pct": orders_pct, "sales_pct": sales_pct, "gap_pct": round(orders_pct - sales_pct, 1)},
            hint=f"Заказы +{round(orders_pct - 100, 1)}%, продажи +{round(sales_pct - 100, 1)}% — выкупы подтянутся через 5-10 дней",
            source="plan_vs_fact",
        ))

    # 3. sales_lag_problem: orders up but sales DOWN
    if orders_pct > 105 and sales_pct < 95:
        signals.append(Signal(
            id=f"sales_lag_problem_{date_suffix}",
            type="sales_lag_problem",
            category="funnel",
            severity="critical",
            impact_on="both",
            data={"orders_pct": orders_pct, "sales_pct": sales_pct},
            hint=f"Заказы растут (+{round(orders_pct - 100, 1)}%), но продажи падают ({round(sales_pct - 100, 1)}%) — возможны возвраты или отмены",
            source="plan_vs_fact",
        ))

    # 4. adv_overspend: internal or external ads significantly over plan
    if adv_int_pct > 115:
        signals.append(Signal(
            id=f"adv_overspend_int_{date_suffix}",
            type="adv_overspend",
            category="adv",
            severity="warning" if adv_int_pct < 130 else "critical",
            impact_on="margin",
            data={"adv_internal_pct": adv_int_pct, "type": "internal"},
            hint=f"Внутренняя реклама перерасход: {round(adv_int_pct, 1)}% от плана МТД",
            source="plan_vs_fact",
        ))
    if adv_ext_pct > 120:
        signals.append(Signal(
            id=f"adv_overspend_ext_{date_suffix}",
            type="adv_overspend",
            category="adv",
            severity="warning" if adv_ext_pct < 140 else "critical",
            impact_on="margin",
            data={"adv_external_pct": adv_ext_pct, "type": "external"},
            hint=f"Внешняя реклама перерасход: {round(adv_ext_pct, 1)}% от плана МТД",
            source="plan_vs_fact",
        ))

    # 5. margin_pct_drop: margin dropping while revenue grows
    revenue_pct = brand.get("revenue", {}).get("completion_mtd_pct", 0) or 0
    if revenue_pct > 110 and margin_pct < 100:
        signals.append(Signal(
            id=f"margin_pct_drop_{date_suffix}",
            type="margin_pct_drop",
            category="margin",
            severity="critical",
            impact_on="margin",
            data={"revenue_pct": revenue_pct, "margin_pct": margin_pct},
            hint=f"Выручка растёт (+{round(revenue_pct - 100, 1)}%), а маржа падает ({round(margin_pct - 100, 1)}%) — проверь структуру затрат",
            source="plan_vs_fact",
        ))

    return signals


def _detect_finance_signals(data: dict) -> list[Signal]:
    return []


def _detect_margin_lever_signals(data: dict) -> list[Signal]:
    return []


def _detect_kb_pattern_signals(data: dict, kb_patterns: list[dict]) -> list[Signal]:
    return []
