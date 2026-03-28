# agents/reporter/pipeline.py
"""Main pipeline: Collect → Analyze → Format → Validate → Deliver."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

from agents.reporter.analyst.analyst import analyze
from agents.reporter.analyst.schemas import ReportInsights
from agents.reporter.collector.base import BaseCollector, CollectedData
from agents.reporter.collector.financial import FinancialCollector
from agents.reporter.collector.funnel import FunnelCollector
from agents.reporter.collector.marketing import MarketingCollector
from agents.reporter.config import MAX_ATTEMPTS
from agents.reporter.delivery.notion import upsert_notion
from agents.reporter.delivery.telegram import send_or_edit_telegram, send_error_notification
from agents.reporter.formatter.notion import render_notion
from agents.reporter.formatter.telegram import render_telegram
from agents.reporter.playbook.loader import load_rules_from_state
from agents.reporter.playbook.updater import save_discovered_patterns
from agents.reporter.state import ReporterState
from agents.reporter.types import ReportScope
from agents.reporter.validator import validate

logger = logging.getLogger(__name__)

_COLLECTORS: dict[str, type[BaseCollector]] = {
    "financial": FinancialCollector,
    "marketing": MarketingCollector,
    "funnel": FunnelCollector,
}


@dataclass
class PipelineResult:
    success: bool
    notion_url: Optional[str] = None
    telegram_message_id: Optional[int] = None
    confidence: float = 0.0
    issues: list[str] | None = None
    error: Optional[str] = None


async def run_pipeline(scope: ReportScope, state: ReporterState) -> PipelineResult:
    """Execute full pipeline for one report."""
    start = time.monotonic()

    # 1. Create run in Supabase
    state.create_run(scope)
    state.update_run(scope, status="collecting")

    try:
        # 2. Collect data
        collector_cls = _COLLECTORS.get(scope.report_type.collector_kind)
        if not collector_cls:
            raise ValueError(f"No collector for {scope.report_type.collector_kind}")

        collector = collector_cls()
        data = await collector.collect(scope)

        # 3. Load playbook rules
        state.update_run(scope, status="analyzing")
        rules = load_rules_from_state(state, scope.report_type.value)

        # 4. LLM Analysis
        insights, meta = await analyze(data, scope, rules)

        # 5. Format
        state.update_run(scope, status="formatting")
        notion_md = render_notion(insights, data, scope)
        telegram_html = render_telegram(insights, data, scope, meta=meta)

        # 6. Validate
        result = validate(notion_md, insights)

        if result.verdict == "RETRY":
            logger.warning("Validation RETRY: %s", result.issues)
            # Retry with hints
            insights, meta = await analyze(data, scope, rules, retry_hint=result.issues)
            notion_md = render_notion(insights, data, scope)
            telegram_html = render_telegram(insights, data, scope, meta=meta)
            result = validate(notion_md, insights)

        if result.verdict == "FAIL":
            duration = time.monotonic() - start
            state.update_run(scope, status="failed", issues=result.issues, duration_sec=duration)
            await send_error_notification(scope, result.issues, state)
            return PipelineResult(success=False, issues=result.issues)

        # 7. Deliver
        state.update_run(scope, status="delivering")
        notion_url = await upsert_notion(notion_md, scope)
        telegram_html_with_url = render_telegram(insights, data, scope, notion_url=notion_url, meta=meta)
        tg_msg_id = await send_or_edit_telegram(telegram_html_with_url, scope, state)

        # 8. Log success
        duration = time.monotonic() - start
        state.update_run(
            scope,
            status="success",
            notion_url=notion_url,
            telegram_message_id=tg_msg_id,
            confidence=insights.overall_confidence,
            duration_sec=duration,
            llm_model=meta.get("model"),
            llm_tokens_in=meta.get("input_tokens"),
            llm_tokens_out=meta.get("output_tokens"),
        )

        # 9. Save discovered patterns
        if insights.discovered_patterns:
            save_discovered_patterns(state, insights.discovered_patterns, scope)

        logger.info(
            "Pipeline complete: %s, confidence=%.2f, duration=%.1fs",
            scope.report_type.value, insights.overall_confidence, duration,
        )

        return PipelineResult(
            success=True,
            notion_url=notion_url,
            telegram_message_id=tg_msg_id,
            confidence=insights.overall_confidence,
        )

    except Exception as e:
        duration = time.monotonic() - start
        logger.error("Pipeline failed: %s", e, exc_info=True)
        state.update_run(scope, status="error", error=str(e), duration_sec=duration)
        await send_error_notification(scope, [str(e)], state)
        return PipelineResult(success=False, error=str(e))
