# agents/reporter/types.py
"""Core types: ReportType enum and ReportScope dataclass."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Optional


class ReportType(str, Enum):
    FINANCIAL_DAILY = "financial_daily"
    FINANCIAL_WEEKLY = "financial_weekly"
    FINANCIAL_MONTHLY = "financial_monthly"
    MARKETING_WEEKLY = "marketing_weekly"
    MARKETING_MONTHLY = "marketing_monthly"
    FUNNEL_WEEKLY = "funnel_weekly"
    FUNNEL_MONTHLY = "funnel_monthly"

    @property
    def collector_kind(self) -> str:
        """Return collector category: 'financial', 'marketing', or 'funnel'."""
        return self.value.rsplit("_", 1)[0].split("_")[0]

    @property
    def period_kind(self) -> str:
        """Return period: 'daily', 'weekly', or 'monthly'."""
        return self.value.rsplit("_", 1)[-1]

    @property
    def human_name(self) -> str:
        names = {
            "financial_daily": "Дневной фин. отчёт",
            "financial_weekly": "Недельный фин. отчёт",
            "financial_monthly": "Месячный фин. отчёт",
            "marketing_weekly": "Маркетинг (неделя)",
            "marketing_monthly": "Маркетинг (месяц)",
            "funnel_weekly": "Воронка (неделя)",
            "funnel_monthly": "Воронка (месяц)",
        }
        return names[self.value]

    @property
    def notion_label(self) -> str:
        labels = {
            "financial_daily": "Ежедневный фин анализ",
            "financial_weekly": "Еженедельный фин анализ",
            "financial_monthly": "Ежемесячный фин анализ",
            "marketing_weekly": "Маркетинговый анализ (неделя)",
            "marketing_monthly": "Маркетинговый анализ (месяц)",
            "funnel_weekly": "Воронка продаж (неделя)",
            "funnel_monthly": "Воронка продаж (месяц)",
        }
        return labels[self.value]


@dataclass(frozen=True)
class ReportScope:
    report_type: ReportType
    period_from: date
    period_to: date
    comparison_from: date
    comparison_to: date
    marketplace: str = "all"      # "wb", "ozon", "all"
    legal_entity: str = "all"     # "IP", "OOO", "all"
    model: Optional[str] = None
    article: Optional[str] = None

    @property
    def scope_hash(self) -> str:
        parts = [
            self.period_from.isoformat(),
            self.period_to.isoformat(),
            self.report_type.value,
            self.marketplace,
            self.legal_entity,
            self.model or "",
            self.article or "",
        ]
        return hashlib.md5("|".join(parts).encode()).hexdigest()[:12]

    @property
    def period_str(self) -> str:
        if self.period_from == self.period_to:
            return self.period_from.isoformat()
        return f"{self.period_from.isoformat()} — {self.period_to.isoformat()}"

    def to_dict(self) -> dict:
        return {
            "report_type": self.report_type.value,
            "period_from": self.period_from.isoformat(),
            "period_to": self.period_to.isoformat(),
            "comparison_from": self.comparison_from.isoformat(),
            "comparison_to": self.comparison_to.isoformat(),
            "marketplace": self.marketplace,
            "legal_entity": self.legal_entity,
            "model": self.model,
            "article": self.article,
        }


def compute_scope(report_type: ReportType, today: date) -> ReportScope:
    """Compute default scope for a report type based on today's date."""
    from datetime import timedelta

    if report_type.period_kind == "daily":
        yesterday = today - timedelta(days=1)
        day_before = yesterday - timedelta(days=1)
        return ReportScope(
            report_type=report_type,
            period_from=yesterday,
            period_to=yesterday,
            comparison_from=day_before,
            comparison_to=day_before,
        )
    elif report_type.period_kind == "weekly":
        # Last full week (Mon-Sun)
        days_since_monday = today.weekday()
        last_sunday = today - timedelta(days=days_since_monday + 1)
        last_monday = last_sunday - timedelta(days=6)
        prev_sunday = last_monday - timedelta(days=1)
        prev_monday = prev_sunday - timedelta(days=6)
        return ReportScope(
            report_type=report_type,
            period_from=last_monday,
            period_to=last_sunday,
            comparison_from=prev_monday,
            comparison_to=prev_sunday,
        )
    else:  # monthly
        first_of_this_month = today.replace(day=1)
        last_month_end = first_of_this_month - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        prev_month_end = last_month_start - timedelta(days=1)
        prev_month_start = prev_month_end.replace(day=1)
        return ReportScope(
            report_type=report_type,
            period_from=last_month_start,
            period_to=last_month_end,
            comparison_from=prev_month_start,
            comparison_to=prev_month_end,
        )


def get_today_reports(today: date) -> list[ReportType]:
    """Which reports should run today."""
    reports = [ReportType.FINANCIAL_DAILY]

    if today.weekday() == 0:  # Monday
        reports.extend([
            ReportType.FINANCIAL_WEEKLY,
            ReportType.MARKETING_WEEKLY,
            ReportType.FUNNEL_WEEKLY,
        ])
        # First Monday of month (day 1-7)
        if today.day <= 7:
            reports.extend([
                ReportType.FINANCIAL_MONTHLY,
                ReportType.MARKETING_MONTHLY,
                ReportType.FUNNEL_MONTHLY,
            ])

    return reports
