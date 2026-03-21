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
    signals = []
    brand = data.get("brand", {})
    current = brand.get("current", {})
    previous = brand.get("previous", {})
    changes = brand.get("changes", {})
    if not current:
        return signals

    channel = data.get("channel", "brand")

    # 1. margin_pct_drop: margin % drops > 2 pp while revenue grows
    margin_cur = current.get("margin_pct", 0) or 0
    margin_prev = previous.get("margin_pct", 0) or 0
    rev_change = changes.get("revenue_before_spp_change_pct", 0) or 0
    margin_drop = margin_prev - margin_cur
    if margin_drop > 2 and rev_change > 0:
        signals.append(Signal(
            id=f"margin_pct_drop_{channel}",
            type="margin_pct_drop",
            category="margin",
            severity="critical" if margin_drop > 5 else "warning",
            impact_on="margin",
            data={"margin_pct_current": margin_cur, "margin_pct_previous": margin_prev, "drop_pp": round(margin_drop, 1)},
            hint=f"Маржинальность упала на {round(margin_drop, 1)} п.п. ({margin_prev}% → {margin_cur}%) при росте выручки",
            source="brand_finance",
        ))

    # 2. cogs_anomaly: cogs_per_unit change > 5%
    cogs_change = abs(changes.get("cogs_per_unit_change_pct", 0) or 0)
    if cogs_change > 5:
        signals.append(Signal(
            id=f"cogs_anomaly_{channel}",
            type="cogs_anomaly",
            category="margin",
            severity="critical",
            impact_on="margin",
            data={"cogs_change_pct": round(cogs_change, 1), "cogs_current": current.get("cogs_per_unit", 0)},
            hint=f"Себестоимость на единицу изменилась на {round(cogs_change, 1)}% — проверь поставщика",
            source="brand_finance",
        ))

    # 3. logistics_overweight: logistics / revenue > 8%
    logistics = current.get("logistics", 0) or 0
    revenue = current.get("revenue_after_spp", 0) or current.get("revenue_before_spp", 0) or 0
    if revenue > 0:
        logistics_pct = logistics / revenue * 100
        if logistics_pct > 8:
            signals.append(Signal(
                id=f"logistics_overweight_{channel}",
                type="logistics_overweight",
                category="margin",
                severity="warning",
                impact_on="margin",
                data={"logistics_pct": round(logistics_pct, 1), "logistics": logistics, "revenue": revenue},
                hint=f"Логистика {round(logistics_pct, 1)}% от выручки (норма < 8%)",
                source="brand_finance",
            ))

    # 4. price_signal: avg check orders vs avg check sales differ > 5%
    orders_rub = current.get("orders_rub", 0) or 0
    orders_count = current.get("orders_count", 0) or 0
    sales_count = current.get("sales_count", 0) or 0
    if orders_count > 0 and sales_count > 0 and revenue > 0:
        avg_order = orders_rub / orders_count
        avg_sale = revenue / sales_count
        if avg_sale > 0:
            diff_pct = abs(avg_order - avg_sale) / avg_sale * 100
            if diff_pct > 5:
                direction = "выше" if avg_order > avg_sale else "ниже"
                signals.append(Signal(
                    id=f"price_signal_{channel}",
                    type="price_signal",
                    category="price",
                    severity="info",
                    impact_on="margin",
                    data={"avg_order": round(avg_order), "avg_sale": round(avg_sale), "diff_pct": round(diff_pct, 1)},
                    hint=f"Ср. чек заказов ({round(avg_order)}₽) {direction} ср. чека продаж ({round(avg_sale)}₽) на {round(diff_pct, 1)}%",
                    source="brand_finance",
                ))

    return signals


def _detect_margin_lever_signals(data: dict) -> list[Signal]:
    return []


def _detect_kb_pattern_signals(data: dict, kb_patterns: list[dict]) -> list[Signal]:
    return []
