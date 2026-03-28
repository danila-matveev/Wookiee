# agents/reporter/collector/marketing.py
"""Marketing data collector — ad campaigns, organic vs paid, DRR breakdown."""
from __future__ import annotations

import logging
from datetime import datetime

from shared.data_layer.advertising import (
    get_wb_external_ad_breakdown,
    get_ozon_external_ad_breakdown,
    get_wb_campaign_stats,
    get_wb_model_ad_roi,
    get_ozon_model_ad_roi,
    get_wb_organic_vs_paid_funnel,
    get_wb_ad_daily_series,
    get_ozon_ad_daily_series,
)
from shared.data_layer.traffic import (
    get_wb_traffic,
    get_wb_traffic_by_model,
    get_ozon_traffic,
)
from shared.data_layer.finance import get_wb_finance, get_ozon_finance

from agents.reporter.collector.base import (
    BaseCollector,
    CollectedData,
    ContextData,
    MarketplaceMetrics,
    ModelMetrics,
    TopLevelMetrics,
    TrendData,
)
from agents.reporter.collector.financial import _parse_abc_row_wb, _safe_div
from agents.reporter.types import ReportScope

logger = logging.getLogger(__name__)

def _rows_to_dicts(rows: list, cols: list[str] | None = None) -> list[dict]:
    """Convert raw psycopg2 tuples to list of dicts. Auto-generates col_N keys if cols not given."""
    if not rows:
        return []
    if isinstance(rows[0], dict):
        return rows
    if cols is None:
        cols = [f"col_{i}" for i in range(len(rows[0]))]
    result = []
    for row in rows:
        d = {}
        for i, v in enumerate(row):
            key = cols[i] if i < len(cols) else f"col_{i}"
            d[key] = str(v) if hasattr(v, 'isoformat') else (float(v) if isinstance(v, __import__('decimal').Decimal) else v)
        result.append(d)
    return result


_WB_AD_SERIES_COLS = ["date", "views", "clicks", "spend", "to_cart", "orders", "ctr", "cpc"]
_OZON_AD_SERIES_COLS = ["date", "views", "clicks", "orders", "spend", "avg_bid", "ctr", "cpc"]
_WB_AD_BREAKDOWN_COLS = ["period", "adv_internal", "adv_bloggers", "adv_vk", "adv_creators", "adv_total"]
_OZON_AD_BREAKDOWN_COLS = ["period", "adv_internal", "adv_external", "adv_total"]
_WB_CAMPAIGN_COLS = ["period", "campaign", "views", "clicks", "spend", "to_cart", "orders", "ctr", "cpc"]
_WB_AD_ROI_COLS = ["period", "model", "revenue", "adv_spend", "margin", "romi", "drr"]
_OZON_AD_ROI_COLS = ["period", "model", "revenue", "adv_spend", "margin", "romi", "drr"]


class MarketingCollector(BaseCollector):
    def _collect_sync(self, scope: ReportScope) -> CollectedData:
        cs = scope.period_from.isoformat()
        ce = scope.period_to.isoformat()
        ps = scope.comparison_from.isoformat()

        warnings: list[str] = []

        # ── Base financials (for DRR context) ──────────────────────────
        wb_abc, _ = get_wb_finance(cs, ps, ce)
        ozon_abc, _ = get_ozon_finance(cs, ps, ce)

        current = TopLevelMetrics()
        previous = TopLevelMetrics()
        for row in wb_abc:
            parsed = _parse_abc_row_wb(row)
            if row[0] == "current":
                current = parsed
            else:
                previous = parsed

        # ── Ad breakdown (internal/external/VK/bloggers) ──────────────
        wb_ad_breakdown = _rows_to_dicts(get_wb_external_ad_breakdown(cs, ps, ce), _WB_AD_BREAKDOWN_COLS)
        ozon_ad_breakdown = _rows_to_dicts(get_ozon_external_ad_breakdown(cs, ps, ce), _OZON_AD_BREAKDOWN_COLS)

        # ── Campaign stats ─────────────────────────────────────────────
        campaign_stats = _rows_to_dicts(get_wb_campaign_stats(cs, ps, ce), _WB_CAMPAIGN_COLS)

        # ── Model-level ad ROI ─────────────────────────────────────────
        wb_roi_raw = get_wb_model_ad_roi(cs, ps, ce)
        ozon_roi_raw = get_ozon_model_ad_roi(cs, ps, ce)
        wb_roi = _rows_to_dicts(wb_roi_raw)
        ozon_roi = _rows_to_dicts(ozon_roi_raw)

        model_breakdown = []
        for i, row in enumerate(wb_roi_raw[:10]):
            model_breakdown.append(ModelMetrics(
                model=str(row[1]) if len(row) > 1 else f"model_{i}",
                rank=i + 1,
                metrics=TopLevelMetrics(),
                prev_metrics=TopLevelMetrics(),
            ))

        # ── Organic vs paid ────────────────────────────────────────────
        try:
            organic_funnel, paid_funnel = get_wb_organic_vs_paid_funnel(cs, ps, ce)
        except Exception as e:
            logger.warning("Organic vs paid failed: %s", e)
            organic_funnel, paid_funnel = [], []

        # ── Traffic by model ───────────────────────────────────────────
        traffic_by_model = _rows_to_dicts(get_wb_traffic_by_model(cs, ps, ce))

        # ── Ad time series ─────────────────────────────────────────────
        wb_ad_series = _rows_to_dicts(get_wb_ad_daily_series(ps, ce), _WB_AD_SERIES_COLS)
        ozon_ad_series = _rows_to_dicts(get_ozon_ad_daily_series(ps, ce), _OZON_AD_SERIES_COLS)

        return CollectedData(
            scope=scope.to_dict(),
            collected_at=datetime.utcnow().isoformat(),
            current=current,
            previous=previous,
            model_breakdown=model_breakdown,
            trends=TrendData(daily_series=wb_ad_series + ozon_ad_series),
            context=ContextData(
                ad_breakdown={
                    "wb": wb_ad_breakdown,
                    "ozon": ozon_ad_breakdown,
                },
                ad_campaigns=campaign_stats,
            ),
            warnings=warnings,
        )
