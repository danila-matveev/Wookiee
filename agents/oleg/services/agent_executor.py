"""
Agent Executor — ReAct loop для агента Олег.

Цикл: Think → Act → Observe → Think → ... → Final Answer

Использует z.ai API с OpenAI-compatible tool-use format.
"""
import json
import logging
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable, Awaitable

from agents.oleg.services.agent_tools import execute_tool

logger = logging.getLogger(__name__)


@dataclass
class AgentStep:
    """One step in the agent's reasoning chain."""
    tool_name: str
    tool_args: dict
    tool_result: str
    iteration: int
    duration_ms: int = 0


@dataclass
class AgentResult:
    """Final result of the agent execution."""
    content: str
    steps: List[AgentStep] = field(default_factory=list)
    total_usage: Dict[str, int] = field(default_factory=lambda: {"input_tokens": 0, "output_tokens": 0})
    total_cost: float = 0.0
    iterations: int = 0
    duration_ms: int = 0
    finish_reason: str = "stop"
    _messages: List[Dict] = field(default_factory=list, repr=False)


class AgentExecutor:
    """
    ReAct loop executor.

    1. Send messages + tools → LLM
    2. If finish_reason == "tool_calls" → execute tools
    3. Add results to messages
    4. Repeat (max MAX_ITERATIONS)
    5. If finish_reason == "stop" → return final answer
    """

    MAX_ITERATIONS = 10
    MAX_TOOL_RESULT_LENGTH = 8500  # Truncate large tool results

    def __init__(
        self,
        zai_client,
        model: str = "claude-opus-4-6",
        tool_definitions: Optional[List[Dict]] = None,
    ):
        self.zai = zai_client
        self.model = model
        self.tool_definitions = tool_definitions or []

    async def run(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.4,
        max_tokens: int = 4000,
    ) -> AgentResult:
        """
        Run the agent ReAct loop.

        Args:
            system_prompt: System instructions (playbook + format)
            user_message: User query
            temperature: LLM temperature
            max_tokens: Max tokens per LLM call

        Returns:
            AgentResult with final content, steps, usage, and cost
        """
        start_time = time.time()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        steps = []
        total_usage = {"input_tokens": 0, "output_tokens": 0}

        for iteration in range(self.MAX_ITERATIONS):
            logger.info(f"Agent iteration {iteration + 1}/{self.MAX_ITERATIONS}")

            # Call LLM with tools
            response = await self.zai.complete_with_tools(
                messages=messages,
                tools=self.tool_definitions,
                model=self.model,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            # Accumulate usage
            usage = response.get("usage", {})
            total_usage["input_tokens"] += (
                usage.get("input_tokens") or usage.get("prompt_tokens", 0)
            )
            total_usage["output_tokens"] += (
                usage.get("output_tokens") or usage.get("completion_tokens", 0)
            )

            finish_reason = response.get("finish_reason", "stop")
            content = response.get("content")
            tool_calls = response.get("tool_calls", [])

            # Case 1: Final answer (no tool calls)
            if finish_reason == "stop" or (content and not tool_calls):
                total_cost = self._calc_cost(total_usage)
                duration = int((time.time() - start_time) * 1000)

                return AgentResult(
                    content=content or "",
                    steps=steps,
                    total_usage=total_usage,
                    total_cost=total_cost,
                    iterations=iteration + 1,
                    duration_ms=duration,
                    finish_reason="stop",
                    _messages=messages,
                )

            # Case 2: Tool calls
            if not tool_calls:
                # No tools and no content — API returned empty response
                logger.warning(
                    f"No tool_calls and no content at iteration {iteration + 1}. "
                    f"finish_reason={finish_reason}, "
                    f"response keys={list(response.keys())}, "
                    f"content repr={repr(content)[:200]}"
                )
                total_cost = self._calc_cost(total_usage)
                duration = int((time.time() - start_time) * 1000)

                return AgentResult(
                    content="Не удалось сформировать ответ.",
                    steps=steps,
                    total_usage=total_usage,
                    total_cost=total_cost,
                    iterations=iteration + 1,
                    duration_ms=duration,
                    finish_reason="error",
                    _messages=messages,
                )

            # Add assistant message with tool_calls
            assistant_msg = {
                "role": "assistant",
                "content": content,  # May be None or contain reasoning
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": (
                                json.dumps(tc["arguments"], ensure_ascii=False)
                                if isinstance(tc["arguments"], dict)
                                else tc["arguments"]
                            ),
                        },
                    }
                    for tc in tool_calls
                ],
            }
            messages.append(assistant_msg)

            # Execute each tool call
            for tc in tool_calls:
                tool_start = time.time()
                tool_name = tc["name"]
                tool_args = tc["arguments"]

                logger.info(f"  Executing tool: {tool_name}({json.dumps(tool_args, ensure_ascii=False)[:150]})")

                result_str = await execute_tool(tool_name, tool_args)

                # Truncate large results to avoid context overflow
                if len(result_str) > self.MAX_TOOL_RESULT_LENGTH:
                    truncated = result_str[:self.MAX_TOOL_RESULT_LENGTH]
                    result_str = truncated + f'\n... (truncated, {len(result_str)} total chars)'

                tool_duration = int((time.time() - tool_start) * 1000)

                steps.append(AgentStep(
                    tool_name=tool_name,
                    tool_args=tool_args,
                    tool_result=result_str[:2000],  # Short version for logging
                    iteration=iteration,
                    duration_ms=tool_duration,
                ))

                # Add tool result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result_str,
                })

                logger.info(f"  Tool {tool_name} completed in {tool_duration}ms ({len(result_str)} chars)")

        # Max iterations reached
        logger.warning(f"Agent reached max iterations ({self.MAX_ITERATIONS})")
        total_cost = self._calc_cost(total_usage)
        duration = int((time.time() - start_time) * 1000)

        # Try to get partial answer from last response
        last_content = "Превышено максимальное количество шагов анализа. Частичный результат на основе собранных данных."

        return AgentResult(
            content=last_content,
            steps=steps,
            total_usage=total_usage,
            total_cost=total_cost,
            iterations=self.MAX_ITERATIONS,
            duration_ms=duration,
            finish_reason="max_iterations",
            _messages=messages,
        )

    async def continue_run(
        self,
        prior_result: AgentResult,
        continuation_message: str,
        temperature: float = 0.4,
        max_tokens: int = 4000,
    ) -> AgentResult:
        """
        Continue analysis from a prior result.

        Appends a user message to the prior conversation and resumes
        the ReAct loop, preserving full tool call context.
        """
        start_time = time.time()

        # Reconstruct messages from prior result
        messages = list(prior_result._messages)
        messages.append({"role": "user", "content": continuation_message})

        steps = []
        total_usage = {"input_tokens": 0, "output_tokens": 0}

        for iteration in range(self.MAX_ITERATIONS):
            logger.info(f"Agent continuation iteration {iteration + 1}/{self.MAX_ITERATIONS}")

            response = await self.zai.complete_with_tools(
                messages=messages,
                tools=self.tool_definitions,
                model=self.model,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            usage = response.get("usage", {})
            total_usage["input_tokens"] += (
                usage.get("input_tokens") or usage.get("prompt_tokens", 0)
            )
            total_usage["output_tokens"] += (
                usage.get("output_tokens") or usage.get("completion_tokens", 0)
            )

            finish_reason = response.get("finish_reason", "stop")
            content = response.get("content")
            tool_calls = response.get("tool_calls", [])

            if finish_reason == "stop" or (content and not tool_calls):
                total_cost = self._calc_cost(total_usage)
                duration = int((time.time() - start_time) * 1000)
                return AgentResult(
                    content=content or "",
                    steps=steps,
                    total_usage=total_usage,
                    total_cost=total_cost,
                    iterations=iteration + 1,
                    duration_ms=duration,
                    finish_reason="stop",
                    _messages=messages,
                )

            if not tool_calls:
                total_cost = self._calc_cost(total_usage)
                duration = int((time.time() - start_time) * 1000)
                return AgentResult(
                    content=content or "",
                    steps=steps,
                    total_usage=total_usage,
                    total_cost=total_cost,
                    iterations=iteration + 1,
                    duration_ms=duration,
                    finish_reason="error",
                    _messages=messages,
                )

            assistant_msg = {
                "role": "assistant",
                "content": content,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": (
                                json.dumps(tc["arguments"], ensure_ascii=False)
                                if isinstance(tc["arguments"], dict)
                                else tc["arguments"]
                            ),
                        },
                    }
                    for tc in tool_calls
                ],
            }
            messages.append(assistant_msg)

            for tc in tool_calls:
                tool_start = time.time()
                tool_name = tc["name"]
                tool_args = tc["arguments"]

                logger.info(f"  Executing tool: {tool_name}({json.dumps(tool_args, ensure_ascii=False)[:150]})")
                result_str = await execute_tool(tool_name, tool_args)

                if len(result_str) > self.MAX_TOOL_RESULT_LENGTH:
                    truncated = result_str[:self.MAX_TOOL_RESULT_LENGTH]
                    result_str = truncated + f'\n... (truncated, {len(result_str)} total chars)'

                tool_duration = int((time.time() - tool_start) * 1000)
                steps.append(AgentStep(
                    tool_name=tool_name,
                    tool_args=tool_args,
                    tool_result=result_str[:2000],
                    iteration=iteration,
                    duration_ms=tool_duration,
                ))
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result_str,
                })
                logger.info(f"  Tool {tool_name} completed in {tool_duration}ms ({len(result_str)} chars)")

        # Max iterations
        total_cost = self._calc_cost(total_usage)
        duration = int((time.time() - start_time) * 1000)
        return AgentResult(
            content="Продолжение анализа: превышено максимальное количество шагов.",
            steps=steps,
            total_usage=total_usage,
            total_cost=total_cost,
            iterations=self.MAX_ITERATIONS,
            duration_ms=duration,
            finish_reason="max_iterations",
            _messages=messages,
        )

    def _calc_cost(self, usage: dict) -> float:
        """Calculate cost based on model pricing from config."""
        from agents.oleg import config
        default_rate = {"input": 0.001, "output": 0.001}
        rates = config.PRICING.get(self.model, default_rate)
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)

        return round(
            (input_tokens / 1000) * rates["input"] +
            (output_tokens / 1000) * rates["output"],
            4,
        )
