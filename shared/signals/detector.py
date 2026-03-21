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
    if source == "advertising":
        signals.extend(_detect_advertising_signals(data))
    if source == "model_breakdown":
        signals.extend(_detect_model_signals(data))

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
    signals = []
    levers = data.get("levers", {})
    waterfall = data.get("waterfall", {})
    if not levers:
        return signals

    channel = data.get("channel", "unknown")

    # 1. spp_shift_up: SPP grew > 2 pp
    spp = levers.get("spp_pct", {})
    spp_cur = spp.get("current", 0) or 0
    spp_prev = spp.get("previous", 0) or 0
    spp_delta = spp_cur - spp_prev
    if spp_delta > 2:
        signals.append(Signal(
            id=f"spp_shift_up_{channel}",
            type="spp_shift_up",
            category="price",
            severity="info",
            impact_on="margin",
            data={"spp_current": spp_cur, "spp_previous": spp_prev, "delta_pp": round(spp_delta, 1)},
            hint=f"СПП выросла на {round(spp_delta, 1)} п.п. ({spp_prev}% → {spp_cur}%) — можно поднять базовую цену",
            source="margin_levers",
        ))

    # 2. spp_shift_down: SPP dropped > 2 pp
    if spp_delta < -2:
        signals.append(Signal(
            id=f"spp_shift_down_{channel}",
            type="spp_shift_down",
            category="price",
            severity="warning",
            impact_on="margin",
            data={"spp_current": spp_cur, "spp_previous": spp_prev, "delta_pp": round(spp_delta, 1)},
            hint=f"СПП упала на {round(abs(spp_delta), 1)} п.п. ({spp_prev}% → {spp_cur}%) — клиентская цена выросла",
            source="margin_levers",
        ))

    # 3. adv_overspend: DRR above threshold (WB > 12%, Ozon > 18%)
    drr = levers.get("drr_pct", {})
    drr_cur = drr.get("current", 0) or 0
    threshold = 18 if channel.upper() in ("OZON", "ОЗОН") else 12
    if drr_cur > threshold:
        signals.append(Signal(
            id=f"adv_overspend_{channel}",
            type="adv_overspend",
            category="adv",
            severity="critical" if drr_cur > threshold * 1.5 else "warning",
            impact_on="margin",
            data={"drr_pct": drr_cur, "threshold": threshold, "channel": channel},
            hint=f"ДРР {channel} = {round(drr_cur, 1)}% при норме < {threshold}%",
            source="margin_levers",
        ))

    # 4. adv_underspend: DRR < 3% and revenue not growing
    revenue_change = waterfall.get("revenue_change", 0) or 0
    if drr_cur < 3 and revenue_change <= 0:
        signals.append(Signal(
            id=f"adv_underspend_{channel}",
            type="adv_underspend",
            category="adv",
            severity="info",
            impact_on="turnover",
            data={"drr_pct": drr_cur, "revenue_change": revenue_change},
            hint=f"ДРР {channel} всего {round(drr_cur, 1)}%, выручка не растёт — мало трафика",
            source="margin_levers",
        ))

    return signals


def _detect_advertising_signals(data: dict) -> list[Signal]:
    signals = []
    ad = data.get("advertising", {})
    ad_cur = ad.get("current", {})
    ad_prev = ad.get("previous", {})
    funnel = data.get("funnel", {})
    funnel_cur = funnel.get("current", {})
    funnel_prev = funnel.get("previous", {})
    channel = data.get("channel", "unknown")
    if not ad_cur:
        return signals

    # 1. ctr_drop: CTR below threshold
    ctr = ad_cur.get("ctr_pct", 0) or 0
    threshold = 1.5 if channel.upper() in ("OZON", "ОЗОН") else 2.0
    if ctr > 0 and ctr < threshold:
        signals.append(Signal(
            id=f"ctr_drop_{channel}",
            type="ctr_drop",
            category="funnel",
            severity="warning",
            impact_on="turnover",
            data={"ctr_pct": ctr, "threshold": threshold, "channel": channel},
            hint=f"CTR {channel} = {ctr}% ниже нормы ({threshold}%)",
            source="advertising",
        ))

    # 2. cart_to_order_drop: cart-to-order fell > 5 pp (needs funnel data)
    if funnel_cur and funnel_prev:
        c2o_cur = funnel_cur.get("cart_to_order_pct", 0) or 0
        c2o_prev = funnel_prev.get("cart_to_order_pct", 0) or 0
        c2o_drop = c2o_prev - c2o_cur
        if c2o_drop > 5:
            signals.append(Signal(
                id=f"cart_to_order_drop_{channel}",
                type="cart_to_order_drop",
                category="funnel",
                severity="warning",
                impact_on="turnover",
                data={"c2o_current": c2o_cur, "c2o_previous": c2o_prev, "drop_pp": round(c2o_drop, 1)},
                hint=f"Конверсия корзина→заказ упала на {round(c2o_drop, 1)} п.п. ({c2o_prev}% → {c2o_cur}%)",
                source="advertising",
            ))

    # 3. cro_improvement: full conversion grew > 1 pp
    cr_cur = ad_cur.get("cr_full_pct", 0) or 0
    cr_prev = ad_prev.get("cr_full_pct", 0) or 0
    cr_growth = cr_cur - cr_prev
    if cr_growth > 1:
        signals.append(Signal(
            id=f"cro_improvement_{channel}",
            type="cro_improvement",
            category="funnel",
            severity="info",
            impact_on="turnover",
            data={"cr_current": cr_cur, "cr_previous": cr_prev, "growth_pp": round(cr_growth, 1)},
            hint=f"Сквозная конверсия выросла на {round(cr_growth, 1)} п.п. ({cr_prev}% → {cr_cur}%)",
            source="advertising",
        ))

    # 4. buyout_drop: buyout rate < 45% (needs funnel data)
    if funnel_cur:
        buyout = funnel_cur.get("order_to_buyout_pct", 0) or 0
        if buyout > 0 and buyout < 45:
            signals.append(Signal(
                id=f"buyout_drop_{channel}",
                type="buyout_drop",
                category="funnel",
                severity="warning",
                impact_on="both",
                data={"buyout_pct": buyout, "channel": channel},
                hint=f"Выкуп {channel} = {buyout}% (норма > 45%)",
                source="advertising",
            ))

    return signals


def _detect_model_signals(data: dict) -> list[Signal]:
    return []  # Implemented in Task 5


def _detect_kb_pattern_signals(data: dict, kb_patterns: list[dict]) -> list[Signal]:
    return []
