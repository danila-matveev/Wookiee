"""Deterministic report schedule — no LLM needed."""
from datetime import date
from enum import Enum


class ReportType(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    MARKETING_WEEKLY = "marketing_weekly"
    MARKETING_MONTHLY = "marketing_monthly"
    FUNNEL_WEEKLY = "funnel_weekly"
    PRICE_WEEKLY = "price_weekly"
    PRICE_MONTHLY = "price_monthly"
    FINOLOG_WEEKLY = "finolog_weekly"

    @property
    def orchestrator_method(self) -> str:
        """Name of the orchestrator function to call."""
        return {
            self.DAILY: "run_daily_report",
            self.WEEKLY: "run_weekly_report",
            self.MONTHLY: "run_monthly_report",
            self.MARKETING_WEEKLY: "run_marketing_report",
            self.MARKETING_MONTHLY: "run_marketing_report",
            self.FUNNEL_WEEKLY: "run_funnel_report",
            self.PRICE_WEEKLY: "run_price_analysis",
            self.PRICE_MONTHLY: "run_price_analysis",
            self.FINOLOG_WEEKLY: "run_finolog_report",
        }[self]

    @property
    def notion_label(self) -> str:
        """Notion database category label."""
        return {
            self.DAILY: "Ежедневный фин анализ",
            self.WEEKLY: "Еженедельный фин анализ",
            self.MONTHLY: "Ежемесячный фин анализ",
            self.MARKETING_WEEKLY: "Еженедельный маркетинговый анализ",
            self.MARKETING_MONTHLY: "Ежемесячный маркетинговый анализ",
            self.FUNNEL_WEEKLY: "Воронка WB (сводный)",
            self.PRICE_WEEKLY: "Еженедельный ценовой анализ",
            self.PRICE_MONTHLY: "Ценовой анализ",
            self.FINOLOG_WEEKLY: "Сводка ДДС",
        }[self]

    @property
    def human_name(self) -> str:
        """Short name for Telegram messages."""
        return {
            self.DAILY: "Daily фин",
            self.WEEKLY: "Weekly фин",
            self.MONTHLY: "Monthly фин",
            self.MARKETING_WEEKLY: "Weekly маркетинг",
            self.MARKETING_MONTHLY: "Monthly маркетинг",
            self.FUNNEL_WEEKLY: "Weekly воронка",
            self.PRICE_WEEKLY: "Weekly ценовой",
            self.PRICE_MONTHLY: "Monthly ценовой",
            self.FINOLOG_WEEKLY: "Weekly ДДС",
        }[self]


def get_today_reports(d: date) -> list:
    """Return list of reports that should be generated for given date.

    Rules:
    - Every day: DAILY
    - Monday (weekday 0): WEEKLY, MARKETING_WEEKLY, FUNNEL_WEEKLY, PRICE_WEEKLY
    - Friday (weekday 4): FINOLOG_WEEKLY
    - First Monday of month (day 1-7, weekday 0): MONTHLY, MARKETING_MONTHLY, PRICE_MONTHLY
    """
    reports = [ReportType.DAILY]

    if d.weekday() == 0:  # Monday
        reports += [
            ReportType.WEEKLY,
            ReportType.MARKETING_WEEKLY,
            ReportType.FUNNEL_WEEKLY,
            ReportType.PRICE_WEEKLY,
        ]

    if d.weekday() == 4:  # Friday
        reports.append(ReportType.FINOLOG_WEEKLY)

    if d.day <= 7 and d.weekday() == 0:  # First Monday of month
        reports += [
            ReportType.MONTHLY,
            ReportType.MARKETING_MONTHLY,
            ReportType.PRICE_MONTHLY,
        ]

    return reports


# ── Weekly report types that only trigger on specific days ────────────────
_WEEKLY_TYPES = {
    ReportType.WEEKLY, ReportType.MARKETING_WEEKLY,
    ReportType.FUNNEL_WEEKLY, ReportType.PRICE_WEEKLY,
}
_FRIDAY_TYPES = {ReportType.FINOLOG_WEEKLY}
_MONTHLY_TYPES = {ReportType.MONTHLY, ReportType.MARKETING_MONTHLY, ReportType.PRICE_MONTHLY}


def get_missed_reports(today: date, failed_or_missing: set[str], lookback_days: int = 6) -> list:
    """Return report types that were scheduled in the past `lookback_days` but are
    in `failed_or_missing` (set of report_type value strings).

    This allows recovery of weekly reports that failed on Monday but are
    retried on Tuesday-Sunday.
    """
    from datetime import timedelta
    missed: list = []
    seen: set = set()

    for offset in range(1, lookback_days + 1):
        past = today - timedelta(days=offset)
        scheduled = get_today_reports(past)
        for rt in scheduled:
            if rt.value in failed_or_missing and rt not in seen:
                # Don't recover daily reports from past days — stale data
                if rt == ReportType.DAILY:
                    continue
                missed.append(rt)
                seen.add(rt)

    return missed
