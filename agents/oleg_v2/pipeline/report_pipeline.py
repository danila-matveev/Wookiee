"""
Report Pipeline — gate check → orchestrator → format → deliver.
"""
import logging
import time
from typing import Optional

from agents.oleg_v2.pipeline.gate_checker import GateChecker, GateCheckResult
from agents.oleg_v2.pipeline.report_types import ReportRequest, ReportResult, ReportType

logger = logging.getLogger(__name__)


class ReportPipeline:
    """
    Pipeline: gate → orchestrator → format → deliver.

    Behavior:
    - Hard passed + soft passed → full report
    - Hard passed + soft failed → report with caveats
    - Hard failed → skip + log for watchdog
    """

    def __init__(self, orchestrator, gate_checker: Optional[GateChecker] = None):
        self.orchestrator = orchestrator
        self.gate_checker = gate_checker or GateChecker()

    async def generate_report(self, request: ReportRequest) -> Optional[ReportResult]:
        """
        Generate a report through the full pipeline.

        Returns ReportResult or None if hard gates failed.
        """
        start_time = time.time()

        # Step 1: Gate check (skip for user queries — they bypass gates)
        caveats = []
        if request.report_type in (ReportType.DAILY, ReportType.WEEKLY, ReportType.MONTHLY):
            marketplace = request.channel or "wb"
            gate_result = self.gate_checker.check_all(marketplace)

            if not gate_result.can_generate:
                logger.warning(
                    f"Hard gates FAILED for {request.report_type.value}: "
                    f"{[g.detail for g in gate_result.gates if g.is_hard and not g.passed]}"
                )
                return None  # Watchdog will handle alerting

            if gate_result.has_caveats:
                caveats = gate_result.caveats
                logger.info(
                    f"Soft gate warnings: {caveats}"
                )

        # Step 2: Build task description for orchestrator
        task = self._build_task(request)
        task_type = request.report_type.value

        # Step 3: Run orchestrator chain
        chain_result = await self.orchestrator.run_chain(
            task=task,
            task_type=task_type,
            context=request.context or {},
        )

        # Step 4: Build result
        duration_ms = int((time.time() - start_time) * 1000)

        return ReportResult(
            brief_summary=chain_result.summary,
            detailed_report=chain_result.detailed or chain_result.summary,
            report_type=request.report_type,
            chain_steps=chain_result.total_steps,
            cost_usd=chain_result.total_cost,
            duration_ms=duration_ms,
            caveats=caveats,
        )

    def _build_task(self, request: ReportRequest) -> str:
        """Build a task description from a report request."""
        if request.report_type == ReportType.QUERY:
            return request.user_query or "Произвольный запрос без деталей."

        if request.report_type == ReportType.FEEDBACK:
            return f"Обработка feedback: {request.user_query}"

        period = f"за период {request.start_date} — {request.end_date}"

        if request.report_type == ReportType.DAILY:
            return (
                f"Сформируй дневной финансовый отчёт {period}. "
                f"Используй get_brand_finance, get_channel_finance (wb + ozon), "
                f"get_margin_levers, get_model_breakdown. "
                f"Обязательно проверь данные через validate_data_quality."
            )

        if request.report_type == ReportType.WEEKLY:
            return (
                f"Сформируй еженедельный финансовый отчёт {period}. "
                f"Используй все доступные tools: brand_finance, channel_finance, "
                f"model_breakdown, margin_levers, advertising_stats, daily_trend. "
                f"Анализируй тренды и аномалии."
            )

        if request.report_type == ReportType.MONTHLY:
            return (
                f"Сформируй месячный финансовый отчёт {period}. "
                f"Используй все tools включая weekly_breakdown. "
                f"Определи лучшую и худшую недели."
            )

        # CUSTOM
        channel_note = f" Канал: {request.channel}." if request.channel else ""
        return (
            f"Сформируй отчёт {period}.{channel_note} "
            f"{request.user_query or ''}"
        )
