# agents/reporter/collector/funnel.py
"""Funnel data collector — conversion stages, SEO, article-level funnel."""
from __future__ import annotations

import logging
from datetime import datetime

from shared.data_layer.funnel_seo import (
    get_wb_article_funnel,
    get_wb_article_funnel_wow,
    get_wb_seo_keyword_positions,
)
from shared.data_layer.traffic import get_wb_traffic, get_ozon_traffic
from shared.data_layer.finance import get_wb_finance, get_ozon_finance

from agents.reporter.collector.base import (
    BaseCollector,
    CollectedData,
    ContextData,
    TopLevelMetrics,
    TrendData,
)
from agents.reporter.collector.financial import _parse_abc_row
from agents.reporter.types import ReportScope

logger = logging.getLogger(__name__)


class FunnelCollector(BaseCollector):
    def _collect_sync(self, scope: ReportScope) -> CollectedData:
        cs = scope.period_from.isoformat()
        ce = scope.period_to.isoformat()
        ps = scope.comparison_from.isoformat()

        warnings: list[str] = []

        # Base financials for context
        wb_abc, _ = get_wb_finance(cs, ps, ce)
        current = TopLevelMetrics()
        previous = TopLevelMetrics()
        for row in wb_abc:
            parsed = _parse_abc_row(row)
            if row[0] == "current":
                current = parsed
            else:
                previous = parsed

        # Article-level funnel (TOP-10)
        article_funnel = get_wb_article_funnel(cs, ce, top_n=10)

        # Week-over-week funnel comparison
        try:
            funnel_wow = get_wb_article_funnel_wow(cs, ps, ce)
        except Exception as e:
            logger.warning("Funnel WoW failed: %s", e)
            funnel_wow = []

        # Traffic (organic + ad)
        try:
            wb_organic, wb_ad = get_wb_traffic(cs, ps, ce)
        except Exception as e:
            logger.warning("WB traffic failed: %s", e)
            wb_organic, wb_ad = [], []

        try:
            ozon_traffic = get_ozon_traffic(cs, ps, ce)
        except Exception as e:
            logger.warning("OZON traffic failed: %s", e)
            ozon_traffic = []

        # SEO keywords
        try:
            seo_keywords = get_wb_seo_keyword_positions(limit=50)
        except Exception as e:
            logger.warning("SEO keywords failed: %s", e)
            seo_keywords = []

        return CollectedData(
            scope=scope.to_dict(),
            collected_at=datetime.utcnow().isoformat(),
            current=current,
            previous=previous,
            trends=TrendData(daily_series=[]),
            context=ContextData(
                ad_campaigns=[],
                ad_breakdown={
                    "article_funnel": article_funnel,
                    "funnel_wow": funnel_wow,
                    "wb_organic": wb_organic,
                    "wb_ad": wb_ad,
                    "ozon_traffic": ozon_traffic,
                    "seo_keywords": seo_keywords,
                },
            ),
            warnings=warnings,
        )
