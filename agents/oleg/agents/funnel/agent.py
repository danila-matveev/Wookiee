"""
Funnel Agent — per-model WB conversion funnel analysis.

Bypasses LLM for report formatting — data is fetched and formatted
entirely in Python via report_builder.py. This guarantees all 14 models
are included with correct structure regardless of LLM token limits.
"""
import json
import logging
import time
from typing import List, Dict, Any, Optional

from agents.oleg.agents.base_agent import BaseAgent
from agents.oleg.agents.funnel.tools import (
    FUNNEL_AGENT_TOOL_DEFINITIONS,
    execute_funnel_agent_tool,
)
from agents.oleg.agents.funnel.prompts import get_funnel_system_prompt
from agents.oleg.agents.funnel.report_builder import build_funnel_report
from agents.oleg.services.funnel_tools import get_all_models_funnel_bundle
from agents.oleg.executor.react_loop import AgentResult, AgentStep

logger = logging.getLogger(__name__)


class FunnelAgent(BaseAgent):
    """Funnel sub-agent: per-model conversion funnel analysis.

    Unlike other agents, FunnelAgent bypasses the LLM ReactLoop.
    The report is built entirely in Python from data_layer queries.
    """

    def __init__(
        self,
        llm_client,
        model: str,
        pricing: Optional[dict] = None,
        max_iterations: int = 10,
        tool_timeout_sec: float = 30.0,
        total_timeout_sec: float = 300.0,
    ):
        super().__init__(
            llm_client=llm_client,
            model=model,
            pricing=pricing,
            max_iterations=max_iterations,
            tool_timeout_sec=tool_timeout_sec,
            total_timeout_sec=total_timeout_sec,
        )

    @property
    def agent_name(self) -> str:
        return "funnel"

    def get_system_prompt(self) -> str:
        return get_funnel_system_prompt()

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        return FUNNEL_AGENT_TOOL_DEFINITIONS

    async def execute_tool(self, tool_name: str, tool_args: dict) -> str:
        return await execute_funnel_agent_tool(tool_name, tool_args)

    async def analyze(
        self,
        instruction: str,
        context: Optional[str] = None,
        temperature: float = 0.4,
        max_tokens: int = 16000,
    ) -> AgentResult:
        """Build funnel report directly in Python — no LLM needed.

        Extracts date_from/date_to from context or instruction,
        fetches data, and formats the complete report.
        """
        t0 = time.time()
        logger.info(f"[{self.agent_name}] Starting direct report build")

        # Extract dates from context
        date_from = None
        date_to = None
        if context:
            import re
            # Try to find dates in context string (JSON or plain text)
            dates = re.findall(r'\d{4}-\d{2}-\d{2}', context)
            if len(dates) >= 2:
                date_from, date_to = dates[0], dates[1]
            else:
                # Try JSON parsing
                try:
                    ctx = json.loads(context)
                    date_from = ctx.get("date_from")
                    date_to = ctx.get("date_to")
                except (json.JSONDecodeError, TypeError):
                    pass

        # Fallback: extract from instruction
        if not date_from or not date_to:
            import re
            dates = re.findall(r'\d{4}-\d{2}-\d{2}', instruction)
            if len(dates) >= 2:
                date_from, date_to = dates[0], dates[1]

        if not date_from or not date_to:
            return AgentResult(
                content="telegram_summary:\nОшибка: не удалось определить даты периода\n\n"
                        "brief_summary:\nОшибка: не удалось определить даты периода\n\n"
                        "detailed_report:\n# Ошибка\nНе удалось определить date_from и date_to из контекста.",
                steps=[],
                iterations=0,
                duration_ms=int((time.time() - t0) * 1000),
                finish_reason="error",
            )

        # Fetch data
        try:
            bundle = await get_all_models_funnel_bundle(
                start_date=date_from,
                end_date=date_to,
            )
        except Exception as e:
            logger.error(f"[{self.agent_name}] Data fetch error: {e}", exc_info=True)
            return AgentResult(
                content=f"telegram_summary:\nОшибка загрузки данных: {e}\n\n"
                        f"brief_summary:\nОшибка загрузки данных: {e}\n\n"
                        f"detailed_report:\n# Ошибка\n{e}",
                steps=[],
                iterations=0,
                duration_ms=int((time.time() - t0) * 1000),
                finish_reason="error",
            )

        fetch_ms = int((time.time() - t0) * 1000)
        n_models = len(bundle.get("models", []))

        # Build report
        report = build_funnel_report(bundle, date_from, date_to)

        # Assemble content in the format orchestrator expects
        content = (
            f"telegram_summary:\n{report['telegram_summary']}\n\n"
            f"brief_summary:\n{report['brief_summary']}\n\n"
            f"detailed_report:\n{report['detailed_report']}"
        )

        duration_ms = int((time.time() - t0) * 1000)
        logger.info(
            f"[{self.agent_name}] Done: {n_models} models, "
            f"data fetch {fetch_ms}ms, total {duration_ms}ms"
        )

        return AgentResult(
            content=content,
            steps=[AgentStep(
                tool_name="build_funnel_report",
                tool_args={"start_date": date_from, "end_date": date_to},
                tool_result=f"{n_models} models fetched",
                iteration=1,
                duration_ms=fetch_ms,
            )],
            iterations=1,
            duration_ms=duration_ms,
            finish_reason="stop",
        )
