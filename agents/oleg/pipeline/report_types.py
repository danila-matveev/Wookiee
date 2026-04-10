"""
Report types registry for the reliability pipeline.

Defines the 8 v2.0 report types with metadata: display names, period,
marketplaces, required hard gates, and template paths (for Phase 3 validation).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class ReportType(str, Enum):
    """All 8 v2.0 report types."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    MARKETING_WEEKLY = "marketing_weekly"
    MARKETING_MONTHLY = "marketing_monthly"
    FUNNEL_WEEKLY = "funnel_weekly"
    FINOLOG_WEEKLY = "finolog_weekly"
    LOCALIZATION_WEEKLY = "localization_weekly"


@dataclass
class ReportConfig:
    """Configuration metadata for a report type."""
    report_type: ReportType
    display_name_ru: str
    period: str  # "daily" | "weekly" | "monthly"
    marketplaces: List[str]  # e.g. ["wb"], ["ozon"], ["wb", "ozon"]
    hard_gates: List[str]  # which hard gate names are required
    # template_path points to future agents/oleg/playbooks/templates/{type}.md
    # required_sections are parsed dynamically from template by report_pipeline (Plan 02)
    template_path: Optional[str] = None


REPORT_CONFIGS: dict[ReportType, ReportConfig] = {
    ReportType.DAILY: ReportConfig(
        report_type=ReportType.DAILY,
        display_name_ru="Ежедневный фин анализ",
        period="daily",
        marketplaces=["wb", "ozon"],
        hard_gates=["wb_orders_freshness", "ozon_orders_freshness", "fin_data_freshness"],
        template_path="agents/oleg/playbooks/templates/daily.md",
    ),
    ReportType.WEEKLY: ReportConfig(
        report_type=ReportType.WEEKLY,
        display_name_ru="Еженедельный фин анализ",
        period="weekly",
        marketplaces=["wb", "ozon"],
        hard_gates=["wb_orders_freshness", "ozon_orders_freshness", "fin_data_freshness"],
        template_path="agents/oleg/playbooks/templates/weekly.md",
    ),
    ReportType.MONTHLY: ReportConfig(
        report_type=ReportType.MONTHLY,
        display_name_ru="Ежемесячный фин анализ",
        period="monthly",
        marketplaces=["wb", "ozon"],
        hard_gates=["wb_orders_freshness", "ozon_orders_freshness", "fin_data_freshness"],
        template_path="agents/oleg/playbooks/templates/monthly.md",
    ),
    ReportType.MARKETING_WEEKLY: ReportConfig(
        report_type=ReportType.MARKETING_WEEKLY,
        display_name_ru="Еженедельный маркетинговый анализ",
        period="weekly",
        marketplaces=["wb", "ozon"],
        hard_gates=["wb_orders_freshness", "ozon_orders_freshness"],
        template_path="agents/oleg/playbooks/templates/marketing_weekly.md",
    ),
    ReportType.MARKETING_MONTHLY: ReportConfig(
        report_type=ReportType.MARKETING_MONTHLY,
        display_name_ru="Ежемесячный маркетинговый анализ",
        period="monthly",
        marketplaces=["wb", "ozon"],
        hard_gates=["wb_orders_freshness", "ozon_orders_freshness"],
        template_path="agents/oleg/playbooks/templates/marketing_monthly.md",
    ),
    ReportType.FUNNEL_WEEKLY: ReportConfig(
        report_type=ReportType.FUNNEL_WEEKLY,
        display_name_ru="Воронка продаж (еженедельная)",
        period="weekly",
        marketplaces=["wb"],
        hard_gates=["wb_orders_freshness", "fin_data_freshness"],
        template_path="agents/oleg/playbooks/templates/funnel_weekly.md",
    ),
    ReportType.FINOLOG_WEEKLY: ReportConfig(
        report_type=ReportType.FINOLOG_WEEKLY,
        display_name_ru="Еженедельная сводка ДДС",
        period="weekly",
        marketplaces=["wb", "ozon"],
        hard_gates=["fin_data_freshness"],
        template_path="agents/oleg/playbooks/templates/dds.md",
    ),
    ReportType.LOCALIZATION_WEEKLY: ReportConfig(
        report_type=ReportType.LOCALIZATION_WEEKLY,
        display_name_ru="Анализ логистических расходов (еженедельный)",
        period="weekly",
        marketplaces=["wb"],
        hard_gates=["wb_orders_freshness"],
        template_path="agents/oleg/playbooks/templates/localization.md",
    ),
}
