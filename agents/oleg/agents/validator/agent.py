"""Validator Agent — recommendation verification with deterministic scripts."""
from typing import List, Dict, Any, Optional
from agents.oleg.agents.base_agent import BaseAgent
from agents.oleg.agents.validator.tools import VALIDATOR_TOOL_DEFINITIONS, execute_validator_tool
from agents.oleg.agents.validator.prompts import get_validator_system_prompt


class ValidatorAgent(BaseAgent):
    def __init__(self, llm_client, model: str, pricing: Optional[dict] = None):
        super().__init__(
            llm_client, model, pricing=pricing,
            max_iterations=5,
            total_timeout_sec=120.0,
        )

    @property
    def agent_name(self) -> str:
        return "validator"

    def get_system_prompt(self) -> str:
        return get_validator_system_prompt()

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        return VALIDATOR_TOOL_DEFINITIONS

    async def execute_tool(self, tool_name: str, tool_args: dict) -> str:
        return await execute_validator_tool(tool_name, tool_args)
