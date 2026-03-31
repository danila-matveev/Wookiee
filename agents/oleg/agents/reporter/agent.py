"""
Reporter Agent — structured financial reports.

Uses 30 tools (12 financial + 18 price) from v1, all delegating
to shared/data_layer.py for SQL queries.
"""
import logging
from typing import List, Dict, Any, Optional

from agents.oleg.agents.base_agent import BaseAgent
from agents.oleg.agents.reporter.tools import (
    REPORTER_TOOL_DEFINITIONS,
    execute_reporter_tool,
)
from agents.oleg.agents.reporter.prompts import get_reporter_system_prompt
from agents.oleg.playbooks.loader import load as load_playbook

logger = logging.getLogger(__name__)


class ReporterAgent(BaseAgent):
    """Reporter sub-agent: data collection and structured reports."""

    def __init__(
        self,
        llm_client,
        model: str,
        playbook_path: str = None,
        task_type: str = None,
        pricing: Optional[dict] = None,
        max_iterations: int = 10,
        tool_timeout_sec: float = 30.0,
        total_timeout_sec: float = 120.0,
    ):
        super().__init__(
            llm_client=llm_client,
            model=model,
            pricing=pricing,
            max_iterations=max_iterations,
            tool_timeout_sec=tool_timeout_sec,
            total_timeout_sec=total_timeout_sec,
        )
        self._playbook_path = playbook_path
        self._task_type = task_type

    @property
    def agent_name(self) -> str:
        return "reporter"

    def get_system_prompt(self) -> str:
        if self._task_type:
            assembled = load_playbook(self._task_type)
            return get_reporter_system_prompt(assembled_playbook=assembled)
        return get_reporter_system_prompt(self._playbook_path)

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        return REPORTER_TOOL_DEFINITIONS

    async def execute_tool(self, tool_name: str, tool_args: dict) -> str:
        return await execute_reporter_tool(tool_name, tool_args)
