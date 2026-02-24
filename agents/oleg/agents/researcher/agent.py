"""
Researcher Agent — deep analysis, hypothesis testing, API tools.
"""
import logging
from typing import List, Dict, Any, Optional

from agents.oleg.agents.base_agent import BaseAgent
from agents.oleg.agents.researcher.tools import (
    RESEARCHER_TOOL_DEFINITIONS,
    execute_researcher_tool,
)
from agents.oleg.agents.researcher.prompts import RESEARCHER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class ResearcherAgent(BaseAgent):
    """Researcher sub-agent: hypothesis-driven deep analysis."""

    @property
    def agent_name(self) -> str:
        return "researcher"

    def get_system_prompt(self) -> str:
        return RESEARCHER_SYSTEM_PROMPT

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        return RESEARCHER_TOOL_DEFINITIONS

    async def execute_tool(self, tool_name: str, tool_args: dict) -> str:
        return await execute_researcher_tool(tool_name, tool_args)
