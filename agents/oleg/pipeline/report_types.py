"""Report type definitions."""
from enum import Enum
from dataclasses import dataclass
from typing import Optional


class ReportType(Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"
    QUERY = "query"       # free-form user question
    FEEDBACK = "feedback"
    MARKETING_DAILY = "marketing_daily"
    MARKETING_WEEKLY = "marketing_weekly"
    MARKETING_MONTHLY = "marketing_monthly"
    MARKETING_CUSTOM = "marketing_custom"


@dataclass
class ReportRequest:
    """A request to generate a report."""
    report_type: ReportType
    start_date: str               # YYYY-MM-DD
    end_date: str                 # YYYY-MM-DD
    user_query: Optional[str] = None   # for QUERY type
    user_id: Optional[int] = None
    channel: Optional[str] = None      # 'wb', 'ozon', or None (both)
    context: Optional[dict] = None     # additional context


@dataclass
class ReportResult:
    """Result of report generation."""
    brief_summary: str        # BBCode for Telegram
    detailed_report: str      # Markdown for Notion
    report_type: ReportType
    telegram_summary: str = ""  # Short TG summary (5-8 lines, KPI only)
    chain_steps: int = 1      # number of orchestrator chain steps
    cost_usd: float = 0.0
    duration_ms: int = 0
    caveats: list = None      # soft gate warnings

    def __post_init__(self):
        if self.caveats is None:
            self.caveats = []
