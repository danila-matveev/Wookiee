"""ValidatorAgent — verifies advisor recommendations against data."""
import json
import logging
from typing import List, Dict, Any, Optional

from agents.oleg.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ValidatorAgent(BaseAgent):
    """Verifies advisor recommendations using deterministic checks."""

    def __init__(
        self,
        llm_client,
        model: str,
        pricing: Optional[dict] = None,
        max_iterations: int = 3,
        tool_timeout_sec: float = 30.0,
        total_timeout_sec: float = 60.0,
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
        return "validator"

    def get_system_prompt(self) -> str:
        return (
            "Ты — Validator, верификатор рекомендаций бренда Wookiee.\n\n"
            "Тебе передаются рекомендации от Advisor, сигналы и structured_data.\n"
            "Твоя задача — проверить каждую рекомендацию и вынести вердикт.\n\n"
            "Формат ответа (строго JSON):\n"
            '{\n'
            '  "verdict": "pass | fail",\n'
            '  "checks": [\n'
            '    {\n'
            '      "signal_id": "id сигнала",\n'
            '      "check": "что проверено",\n'
            '      "result": "ok | fail",\n'
            '      "note": "комментарий"\n'
            '    }\n'
            '  ],\n'
            '  "issues": ["описание проблемы, если есть"]\n'
            '}\n\n'
            "ПРАВИЛА:\n"
            "- verdict=pass только если ВСЕ рекомендации корректны\n"
            "- Проверяй: signal_id существует в signals, данные не противоречат structured_data\n"
            "- Проверяй: рекомендация конкретна и измерима\n"
            "- Ответ — ТОЛЬКО JSON, без markdown"
        )

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        return []

    async def execute_tool(self, tool_name: str, tool_args: dict) -> str:
        return json.dumps({"error": f"Validator has no tool '{tool_name}'"})
