"""AdvisorAgent — generates actionable recommendations from detected signals."""
import json
import logging
from typing import List, Dict, Any, Optional

from agents.oleg.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class AdvisorAgent(BaseAgent):
    """Generates actionable recommendations based on detected signals."""

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
        return "advisor"

    def get_system_prompt(self) -> str:
        return (
            "Ты — Advisor, аналитик-советник бренда Wookiee.\n\n"
            "Тебе передаются сигналы (signals) и структурированные данные (structured_data).\n"
            "Твоя задача — сформировать actionable рекомендации в формате JSON.\n\n"
            "Формат ответа (строго JSON):\n"
            '{\n'
            '  "recommendations": [\n'
            '    {\n'
            '      "signal_id": "id сигнала",\n'
            '      "action": "что конкретно сделать",\n'
            '      "priority": "high | medium | low",\n'
            '      "expected_impact": "ожидаемый эффект",\n'
            '      "category": "margin | adv | funnel | price"\n'
            '    }\n'
            '  ]\n'
            '}\n\n'
            "ПРАВИЛА:\n"
            "- Каждая рекомендация ДОЛЖНА ссылаться на конкретный signal_id\n"
            "- Рекомендации должны быть конкретными и измеримыми\n"
            "- Не придумывай данные — используй только то, что есть в signals и structured_data\n"
            "- Ответ — ТОЛЬКО JSON, без markdown"
        )

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        return []

    async def execute_tool(self, tool_name: str, tool_args: dict) -> str:
        return json.dumps({"error": f"Advisor has no tool '{tool_name}'"})
