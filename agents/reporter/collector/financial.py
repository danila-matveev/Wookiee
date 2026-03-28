# agents/reporter/collector/financial.py
"""Financial data collector — uses shared/data_layer for all SQL queries."""
from __future__ import annotations

import logging
from datetime import datetime

from shared.data_layer.finance import (
    get_wb_finance,
    get_wb_by_model,
    get_ozon_finance,
    get_ozon_by_model,
)
from shared.data_layer.advertising import get_wb_external_ad_breakdown
from shared.data_layer.inventory import (
    get_wb_avg_stock,
    get_ozon_avg_stock,
    get_wb_turnover_by_model,
)
from shared.data_layer.time_series import get_wb_daily_series, get_ozon_daily_series
from shared.data_layer.pricing import get_wb_price_changes
from shared.data_layer.quality import validate_wb_data_quality

from agents.reporter.collector.base import (
    BaseCollector,
    CollectedData,
    ContextData,
    MarketplaceMetrics,
    ModelMetrics,
    TopLevelMetrics,
    TrendData,
)
from agents.reporter.types import ReportScope

logger = logging.getLogger(__name__)


def _safe_div(a: float, b: float) -> float:
    return round(a / b * 100, 2) if b else 0.0


def _parse_abc_row_wb(row: tuple) -> TopLevelMetrics:
    """Parse WB abc_date row (19 columns).

    0: period, 1: orders_count, 2: sales_count, 3: revenue_before_spp,
    4: revenue_after_spp, 5: adv_internal, 6: adv_external,
    7: cost_of_goods, 8: logistics, 9: storage, 10: commission,
    11: spp_amount, 12: nds, 13: penalty, 14: retention, 15: deduction,
    16: margin, 17: returns_revenue, 18: revenue_before_spp_gross
    """
    sales = int(row[2] or 0)
    rev_before = float(row[3] or 0)
    rev_after = float(row[4] or 0)
    adv_int = float(row[5] or 0)
    adv_ext = float(row[6] or 0)
    cogs = float(row[7] or 0)
    logistics = float(row[8] or 0)
    storage = float(row[9] or 0)
    commission = float(row[10] or 0)
    spp_amount = float(row[11] or 0)
    margin = float(row[16] or 0)

    adv_total = adv_int + adv_ext
    return TopLevelMetrics(
        revenue_before_spp=rev_before,
        revenue_after_spp=rev_after,
        orders_count=int(row[1] or 0),
        sales_count=sales,
        margin=margin,
        margin_pct=_safe_div(margin, rev_before),
        adv_internal=adv_int,
        adv_external=adv_ext,
        adv_total=adv_total,
        drr_pct=_safe_div(adv_total, rev_before),
        spp_pct=_safe_div(spp_amount, rev_before),
        logistics=logistics,
        storage=storage,
        cost_of_goods=cogs,
        commission=commission,
    )


def _parse_abc_row_ozon(row: tuple) -> TopLevelMetrics:
    """Parse OZON abc_date row (13 columns).

    0: period, 1: sales_count, 2: revenue_before_spp,
    3: revenue_after_spp, 4: adv_internal, 5: adv_external,
    6: margin, 7: cost_of_goods, 8: logistics, 9: storage,
    10: commission, 11: spp_amount, 12: nds
    """
    sales = int(row[1] or 0)
    rev_before = float(row[2] or 0)
    rev_after = float(row[3] or 0)
    adv_int = float(row[4] or 0)
    adv_ext = float(row[5] or 0)
    margin = float(row[6] or 0)
    cogs = float(row[7] or 0)
    logistics = float(row[8] or 0)
    storage = float(row[9] or 0)
    commission = float(row[10] or 0)
    spp_amount = float(row[11] or 0)

    adv_total = adv_int + adv_ext
    return TopLevelMetrics(
        revenue_before_spp=rev_before,
        revenue_after_spp=rev_after,
        sales_count=sales,
        margin=margin,
        margin_pct=_safe_div(margin, rev_before),
        adv_internal=adv_int,
        adv_external=adv_ext,
        adv_total=adv_total,
        drr_pct=_safe_div(adv_total, rev_before),
        spp_pct=_safe_div(spp_amount, rev_before),
        logistics=logistics,
        storage=storage,
        cost_of_goods=cogs,
        commission=commission,
    )


def _parse_model_rows(rows: list[tuple]) -> list[ModelMetrics]:
    """Parse by-model rows into ModelMetrics list, sorted by current revenue."""
    models: dict[str, dict] = {}  # {model: {current: ..., previous: ...}}

    for row in rows:
        # period, model, sales_count, revenue_before_spp, adv_internal,
        # adv_external, margin, cost_of_goods
        period, model, sales, rev, adv_int, adv_ext, margin, cogs = row
        bucket = "current" if period == "current" else "previous"

        if model not in models:
            models[model] = {"current": TopLevelMetrics(), "previous": TopLevelMetrics()}

        adv_total = float(adv_int or 0) + float(adv_ext or 0)
        rev_f = float(rev or 0)
        models[model][bucket] = TopLevelMetrics(
            revenue_before_spp=rev_f,
            sales_count=int(sales or 0),
            margin=float(margin or 0),
            margin_pct=_safe_div(float(margin or 0), rev_f),
            adv_internal=float(adv_int or 0),
            adv_external=float(adv_ext or 0),
            adv_total=adv_total,
            drr_pct=_safe_div(adv_total, rev_f),
            cost_of_goods=float(cogs or 0),
        )

    # Sort by current revenue descending
    sorted_models = sorted(
        models.items(), key=lambda x: x[1]["current"].revenue_before_spp, reverse=True
    )
    return [
        ModelMetrics(
            model=name,
            rank=i + 1,
            metrics=data["current"],
            prev_metrics=data["previous"],
        )
        for i, (name, data) in enumerate(sorted_models)
    ]


class FinancialCollector(BaseCollector):
    def _collect_sync(self, scope: ReportScope) -> CollectedData:
        cs = scope.period_from.isoformat()
        ce = scope.period_to.isoformat()
        ps = scope.comparison_from.isoformat()

        warnings: list[str] = []

        # ── Layer 1: Top-level metrics ─────────────────────────────────
        wb_abc, wb_orders = get_wb_finance(cs, ps, ce)
        ozon_abc, ozon_orders = get_ozon_finance(cs, ps, ce)

        current = TopLevelMetrics()
        previous = TopLevelMetrics()
        wb_current = TopLevelMetrics()
        wb_previous = TopLevelMetrics()
        ozon_current = TopLevelMetrics()
        ozon_previous = TopLevelMetrics()

        for row in wb_abc:
            parsed = _parse_abc_row_wb(row)
            if row[0] == "current":
                wb_current = parsed
            else:
                wb_previous = parsed

        # Fill orders_rub from separate orders query
        for row in wb_orders:
            # period, orders_count, orders_rub
            if row[0] == "current":
                wb_current.orders_rub = float(row[2] or 0)
                if wb_current.orders_count == 0:
                    wb_current.orders_count = int(row[1] or 0)
            else:
                wb_previous.orders_rub = float(row[2] or 0)
                if wb_previous.orders_count == 0:
                    wb_previous.orders_count = int(row[1] or 0)

        for row in ozon_abc:
            parsed = _parse_abc_row_ozon(row)
            if row[0] == "current":
                ozon_current = parsed
            else:
                ozon_previous = parsed

        for row in ozon_orders:
            if row[0] == "current":
                ozon_current.orders_count = int(row[1] or 0)
                ozon_current.orders_rub = float(row[2] or 0)
            else:
                ozon_previous.orders_count = int(row[1] or 0)
                ozon_previous.orders_rub = float(row[2] or 0)

        # Merge WB + OZON (weighted averages for percentages)
        for period_label, wb, oz, target in [
            ("current", wb_current, ozon_current, None),
            ("previous", wb_previous, ozon_previous, None),
        ]:
            merged = TopLevelMetrics(
                revenue_before_spp=wb.revenue_before_spp + oz.revenue_before_spp,
                revenue_after_spp=wb.revenue_after_spp + oz.revenue_after_spp,
                orders_count=wb.orders_count + oz.orders_count,
                orders_rub=wb.orders_rub + oz.orders_rub,
                sales_count=wb.sales_count + oz.sales_count,
                margin=wb.margin + oz.margin,
                adv_internal=wb.adv_internal + oz.adv_internal,
                adv_external=wb.adv_external + oz.adv_external,
                adv_total=wb.adv_total + oz.adv_total,
                logistics=wb.logistics + oz.logistics,
                storage=wb.storage + oz.storage,
                cost_of_goods=wb.cost_of_goods + oz.cost_of_goods,
                commission=wb.commission + oz.commission,
            )
            # Weighted averages
            total_rev = merged.revenue_before_spp
            merged.margin_pct = _safe_div(merged.margin, total_rev)
            merged.drr_pct = _safe_div(merged.adv_total, total_rev)
            merged.spp_pct = _safe_div(
                wb.spp_pct * wb.revenue_before_spp + oz.spp_pct * oz.revenue_before_spp,
                total_rev,
            ) if total_rev else 0.0

            if period_label == "current":
                current = merged
            else:
                previous = merged

        # ── Layer 2: Marketplace breakdown ─────────────────────────────
        mp_breakdown = []
        if wb_current.revenue_before_spp > 0 or wb_previous.revenue_before_spp > 0:
            mp_breakdown.append(MarketplaceMetrics(
                marketplace="wb", metrics=wb_current, prev_metrics=wb_previous
            ))
        if ozon_current.revenue_before_spp > 0 or ozon_previous.revenue_before_spp > 0:
            mp_breakdown.append(MarketplaceMetrics(
                marketplace="ozon", metrics=ozon_current, prev_metrics=ozon_previous
            ))

        # ── Layer 3: By model ──────────────────────────────────────────
        wb_models = get_wb_by_model(cs, ps, ce)
        ozon_models = get_ozon_by_model(cs, ps, ce)
        all_model_rows = wb_models + ozon_models
        model_breakdown = _parse_model_rows(all_model_rows)

        # ── Layer 4: Trends ────────────────────────────────────────────
        wb_series = get_wb_daily_series(ce, lookback_days=14)
        ozon_series = get_ozon_daily_series(ce, lookback_days=14)

        # ── Layer 5: Context ───────────────────────────────────────────
        wb_stock = get_wb_avg_stock(cs, ce)
        ozon_stock = get_ozon_avg_stock(cs, ce)
        all_stock = {**wb_stock, **ozon_stock}

        turnover = get_wb_turnover_by_model(cs, ce)
        price_changes = get_wb_price_changes(cs, ce)

        try:
            ad_breakdown = get_wb_external_ad_breakdown(cs, ps, ce)
        except Exception as e:
            logger.warning("Ad breakdown failed: %s", e)
            ad_breakdown = []

        # ── Data quality ───────────────────────────────────────────────
        try:
            quality = validate_wb_data_quality(ce)
            if quality.get("warnings"):
                warnings.extend(quality["warnings"])
        except Exception as e:
            logger.warning("Quality check failed: %s", e)

        return CollectedData(
            scope=scope.to_dict(),
            collected_at=datetime.utcnow().isoformat(),
            current=current,
            previous=previous,
            marketplace_breakdown=mp_breakdown,
            model_breakdown=model_breakdown,
            trends=TrendData(
                daily_series=wb_series + ozon_series,
            ),
            context=ContextData(
                stock_by_model=all_stock,
                turnover_by_model=turnover,
                price_changes=price_changes,
                ad_breakdown={"rows": ad_breakdown},
            ),
            warnings=warnings,
        )
