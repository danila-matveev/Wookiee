"""
Quality Agent — feedback processing, playbook management, verification.
"""
import logging
from typing import List, Dict, Any, Optional

from agents.oleg.agents.base_agent import BaseAgent
from agents.oleg.agents.quality.tools import (
    QUALITY_TOOL_DEFINITIONS,
    execute_quality_tool,
    set_playbook_path,
    set_state_store,
)
from agents.oleg.agents.quality.prompts import QUALITY_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class QualityAgent(BaseAgent):
    """Quality sub-agent: feedback processing and playbook updates."""

    def __init__(
        self,
        llm_client,
        model: str,
        playbook_path: str = None,
        state_store=None,
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
        if playbook_path:
            set_playbook_path(playbook_path)
        if state_store:
            set_state_store(state_store)

    @property
    def agent_name(self) -> str:
        return "quality"

    def get_system_prompt(self) -> str:
        return QUALITY_SYSTEM_PROMPT

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        return QUALITY_TOOL_DEFINITIONS

    async def execute_tool(self, tool_name: str, tool_args: dict) -> str:
        return await execute_quality_tool(tool_name, tool_args)
