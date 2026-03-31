"""
Marketer Agent — marketing funnel analysis and ad efficiency.

Analyzes the full marketing funnel (impressions -> clicks -> cart -> orders -> buyouts),
ad spend efficiency, and provides budget recommendations.
"""
import logging
from typing import List, Dict, Any, Optional

from agents.oleg.agents.base_agent import BaseAgent
from agents.oleg.agents.marketer.tools import (
    MARKETER_TOOL_DEFINITIONS,
    execute_marketer_tool,
)
from agents.oleg.agents.marketer.prompts import get_marketer_system_prompt
from agents.oleg.playbooks.loader import load as load_playbook

logger = logging.getLogger(__name__)


class MarketerAgent(BaseAgent):
    """Marketer sub-agent: marketing funnel and ad efficiency analysis."""

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
        return "marketer"

    def get_system_prompt(self) -> str:
        if self._task_type:
            assembled = load_playbook(self._task_type)
            return get_marketer_system_prompt(assembled_playbook=assembled)
        return get_marketer_system_prompt(self._playbook_path)

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        return MARKETER_TOOL_DEFINITIONS

    async def execute_tool(self, tool_name: str, tool_args: dict) -> str:
        return await execute_marketer_tool(tool_name, tool_args)
