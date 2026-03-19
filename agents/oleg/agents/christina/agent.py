"""
Christina Agent — knowledge base management and enrichment.

Manages the Wookiee knowledge base: adding, updating, deleting,
verifying content. The "knowledge librarian" of the Oleg system.
"""
import logging
from typing import List, Dict, Any, Optional

from agents.oleg.agents.base_agent import BaseAgent
from agents.oleg.agents.christina.tools import (
    CHRISTINA_TOOL_DEFINITIONS,
    execute_christina_tool,
)
from agents.oleg.agents.christina.prompts import get_christina_system_prompt

logger = logging.getLogger(__name__)


class ChristinaAgent(BaseAgent):
    """Christina sub-agent: knowledge base management."""

    def __init__(
        self,
        llm_client,
        model: str,
        playbook_path: str = None,
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

    @property
    def agent_name(self) -> str:
        return "christina"

    def get_system_prompt(self) -> str:
        return get_christina_system_prompt(self._playbook_path)

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        return CHRISTINA_TOOL_DEFINITIONS

    async def execute_tool(self, tool_name: str, tool_args: dict) -> str:
        return await execute_christina_tool(tool_name, tool_args)
