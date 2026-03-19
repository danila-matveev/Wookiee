"""
Funnel Agent (Макар) — оцифровка маркетинговой воронки WB.

Полная воронка: Показы → Переходы → Корзина → Заказы → Выкупы → Маржинальная прибыль.
Уровни: Бренд → Модель → Артикул/SKU.
"""
import logging
from typing import List, Dict, Any, Optional

from agents.oleg.agents.base_agent import BaseAgent
from agents.oleg.agents.seo.tools import (
    FUNNEL_TOOL_DEFINITIONS,
    execute_funnel_tool,
)
from agents.oleg.agents.seo.prompts import get_funnel_system_prompt

logger = logging.getLogger(__name__)


class FunnelAgent(BaseAgent):
    """Funnel sub-agent (Макар): маркетинговая воронка и экономика артикулов."""

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
        return "funnel"

    def get_system_prompt(self) -> str:
        return get_funnel_system_prompt(self._playbook_path)

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        return FUNNEL_TOOL_DEFINITIONS

    async def execute_tool(self, tool_name: str, tool_args: dict) -> str:
        return await execute_funnel_tool(tool_name, tool_args)
