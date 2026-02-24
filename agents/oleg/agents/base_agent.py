"""
BaseAgent — abstract base class for all sub-agents.

Each sub-agent (Reporter, Researcher, Quality) inherits from this class
and provides:
- system_prompt: agent-specific instructions
- tool_definitions: OpenAI function calling format
- execute_tool(): tool dispatcher
"""
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

from agents.oleg.executor.react_loop import ReactLoop, AgentResult
from agents.oleg.executor.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Abstract base for Oleg v2 sub-agents."""

    def __init__(
        self,
        llm_client,
        model: str,
        pricing: Optional[dict] = None,
        max_iterations: int = 10,
        tool_timeout_sec: float = 30.0,
        total_timeout_sec: float = 120.0,
    ):
        self.llm_client = llm_client
        self.model = model
        self.pricing = pricing or {}
        self.max_iterations = max_iterations
        self.tool_timeout_sec = tool_timeout_sec
        self.total_timeout_sec = total_timeout_sec
        self.cb = CircuitBreaker(name=self.agent_name)

        self._loop: Optional[ReactLoop] = None

    @property
    @abstractmethod
    def agent_name(self) -> str:
        """Unique agent identifier: 'reporter', 'researcher', 'quality'."""
        ...

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the agent's system prompt."""
        ...

    @abstractmethod
    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Return tool definitions in OpenAI function calling format."""
        ...

    @abstractmethod
    async def execute_tool(self, tool_name: str, tool_args: dict) -> str:
        """Execute a tool by name with given arguments. Returns JSON string."""
        ...

    def _get_loop(self) -> ReactLoop:
        """Lazily create the ReactLoop instance."""
        if self._loop is None:
            self._loop = ReactLoop(
                llm_client=self.llm_client,
                model=self.model,
                tool_definitions=self.get_tool_definitions(),
                tool_executor=self.execute_tool,
                pricing=self.pricing,
                max_iterations=self.max_iterations,
                tool_timeout_sec=self.tool_timeout_sec,
                total_timeout_sec=self.total_timeout_sec,
                circuit_breaker=self.cb,
            )
        return self._loop

    async def analyze(
        self,
        instruction: str,
        context: Optional[str] = None,
        temperature: float = 0.4,
        max_tokens: int = 4000,
    ) -> AgentResult:
        """
        Run the agent on a task.

        Args:
            instruction: What the orchestrator wants this agent to do.
            context: Optional context from previous chain steps.
            temperature: LLM temperature.
            max_tokens: Max tokens per LLM call.

        Returns:
            AgentResult with content, steps, usage, cost.
        """
        system_prompt = self.get_system_prompt()

        user_message = instruction
        if context:
            user_message = f"Контекст от предыдущих шагов:\n{context}\n\n{instruction}"

        logger.info(
            f"[{self.agent_name}] Starting analysis: "
            f"{instruction[:100]}..."
        )

        loop = self._get_loop()
        result = await loop.run(
            system_prompt=system_prompt,
            user_message=user_message,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        logger.info(
            f"[{self.agent_name}] Done: {result.iterations} iterations, "
            f"{len(result.steps)} tool calls, "
            f"${result.total_cost:.4f}, "
            f"{result.finish_reason}"
        )

        return result

    async def continue_analysis(
        self,
        prior_result: AgentResult,
        continuation_message: str,
        temperature: float = 0.4,
        max_tokens: int = 4000,
    ) -> AgentResult:
        """Continue from a prior analysis result."""
        loop = self._get_loop()
        return await loop.continue_run(
            prior_result=prior_result,
            continuation_message=continuation_message,
            temperature=temperature,
            max_tokens=max_tokens,
        )
