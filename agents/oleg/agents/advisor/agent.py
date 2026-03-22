"""Advisor Agent — universal recommendation engine.

Takes signals from the Signal Detector and generates structured,
actionable recommendations prioritized by margin impact.
"""
import logging
from typing import List, Dict, Any, Optional

from agents.oleg.agents.base_agent import BaseAgent
from agents.oleg.agents.advisor.tools import (
    ADVISOR_TOOL_DEFINITIONS,
    execute_advisor_tool,
)
from agents.oleg.agents.advisor.prompts import get_advisor_system_prompt

logger = logging.getLogger(__name__)


class AdvisorAgent(BaseAgent):
    """Advisor sub-agent: actionable recommendations from detected signals."""

    def __init__(
        self,
        llm_client,
        model: str,
        pricing: Optional[dict] = None,
        max_iterations: int = 5,
        tool_timeout_sec: float = 30.0,
        total_timeout_sec: float = 90.0,
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
        return "advisor"

    def get_system_prompt(self) -> str:
        return get_advisor_system_prompt()

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        return ADVISOR_TOOL_DEFINITIONS

    async def execute_tool(self, tool_name: str, tool_args: dict) -> str:
        return await execute_advisor_tool(tool_name, tool_args)
