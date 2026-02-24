"""
ReactLoop — hardened ReAct engine for all sub-agents.

Improvements over v1 (agent_executor.py):
1. Try-catch on EVERY tool call → {"error": "..."} instead of crash
2. Per-tool timeout (30s) and total timeout (120s)
3. Circuit breaker integration for LLM and tool calls
4. Context compression after iteration 5
5. Partial result on max_iterations (ask LLM to summarize)
"""
import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable, Awaitable

from agents.oleg_v2.executor.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


@dataclass
class AgentStep:
    """One step in the agent's reasoning chain."""
    tool_name: str
    tool_args: dict
    tool_result: str
    iteration: int
    duration_ms: int = 0
    error: bool = False


@dataclass
class AgentResult:
    """Final result of agent execution."""
    content: str
    steps: List[AgentStep] = field(default_factory=list)
    total_usage: Dict[str, int] = field(
        default_factory=lambda: {"input_tokens": 0, "output_tokens": 0}
    )
    total_cost: float = 0.0
    iterations: int = 0
    duration_ms: int = 0
    finish_reason: str = "stop"
    _messages: List[Dict] = field(default_factory=list, repr=False)


class ReactLoop:
    """
    Hardened ReAct loop executor.

    1. Send messages + tools → LLM
    2. If tool_calls → execute each with try-catch + timeout
    3. Add results to messages
    4. After iteration 5 → compress context
    5. Repeat (max MAX_ITERATIONS)
    6. If finish_reason == "stop" → return final answer
    7. On max_iterations → request partial summary from LLM
    """

    def __init__(
        self,
        llm_client,
        model: str,
        tool_definitions: List[Dict],
        tool_executor: Callable[[str, dict], Awaitable[str]],
        pricing: Optional[dict] = None,
        max_iterations: int = 10,
        max_tool_result_length: int = 8500,
        tool_timeout_sec: float = 30.0,
        total_timeout_sec: float = 120.0,
        compress_after: int = 5,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ):
        self.llm = llm_client
        self.model = model
        self.tool_definitions = tool_definitions
        self.tool_executor = tool_executor
        self.pricing = pricing or {}
        self.max_iterations = max_iterations
        self.max_tool_result_length = max_tool_result_length
        self.tool_timeout_sec = tool_timeout_sec
        self.total_timeout_sec = total_timeout_sec
        self.compress_after = compress_after
        self.cb = circuit_breaker or CircuitBreaker(name="react_loop")

    async def run(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.4,
        max_tokens: int = 4000,
    ) -> AgentResult:
        """Run the ReAct loop."""
        start_time = time.time()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        steps: List[AgentStep] = []
        total_usage = {"input_tokens": 0, "output_tokens": 0}

        for iteration in range(self.max_iterations):
            # Check total timeout
            elapsed = time.time() - start_time
            if elapsed >= self.total_timeout_sec:
                logger.warning(
                    f"Total timeout ({self.total_timeout_sec}s) reached "
                    f"at iteration {iteration + 1}"
                )
                return self._make_partial_result(
                    steps, total_usage, start_time, messages,
                    "total_timeout",
                )

            # Check circuit breaker
            if self.cb.is_open:
                logger.warning(f"Circuit breaker OPEN, aborting at iteration {iteration + 1}")
                return AgentResult(
                    content="Сервис временно недоступен (circuit breaker). Повторите позже.",
                    steps=steps,
                    total_usage=total_usage,
                    total_cost=self._calc_cost(total_usage),
                    iterations=iteration,
                    duration_ms=int((time.time() - start_time) * 1000),
                    finish_reason="circuit_breaker",
                    _messages=messages,
                )

            logger.info(f"ReactLoop iteration {iteration + 1}/{self.max_iterations}")

            # Context compression after N iterations
            if iteration == self.compress_after:
                messages = self._compress_context(messages)

            # Call LLM with tools
            try:
                response = await self.llm.complete_with_tools(
                    messages=messages,
                    tools=self.tool_definitions,
                    model=self.model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                self.cb.record_success()
            except Exception as e:
                logger.error(f"LLM call failed: {type(e).__name__}: {e}")
                self.cb.record_failure()
                return AgentResult(
                    content=f"Ошибка LLM: {type(e).__name__}",
                    steps=steps,
                    total_usage=total_usage,
                    total_cost=self._calc_cost(total_usage),
                    iterations=iteration + 1,
                    duration_ms=int((time.time() - start_time) * 1000),
                    finish_reason="llm_error",
                    _messages=messages,
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
            tool_calls = response.get("tool_calls") or []

            # Case 1: Final answer
            if finish_reason == "stop" or (content and not tool_calls):
                return AgentResult(
                    content=content or "",
                    steps=steps,
                    total_usage=total_usage,
                    total_cost=self._calc_cost(total_usage),
                    iterations=iteration + 1,
                    duration_ms=int((time.time() - start_time) * 1000),
                    finish_reason="stop",
                    _messages=messages,
                )

            # Case 2: No tool calls and no content — API error
            if not tool_calls:
                logger.warning(
                    f"Empty response at iteration {iteration + 1}: "
                    f"finish_reason={finish_reason}"
                )
                return AgentResult(
                    content="Не удалось сформировать ответ.",
                    steps=steps,
                    total_usage=total_usage,
                    total_cost=self._calc_cost(total_usage),
                    iterations=iteration + 1,
                    duration_ms=int((time.time() - start_time) * 1000),
                    finish_reason="error",
                    _messages=messages,
                )

            # Case 3: Execute tool calls
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
                tool_name = tc["name"]
                tool_args = tc["arguments"]

                logger.info(
                    f"  Tool: {tool_name}"
                    f"({json.dumps(tool_args, ensure_ascii=False)[:150]})"
                )

                # Execute with try-catch + timeout
                tool_start = time.time()
                result_str, is_error = await self._execute_tool_safe(
                    tool_name, tool_args
                )

                # Truncate large results
                if len(result_str) > self.max_tool_result_length:
                    result_str = (
                        result_str[:self.max_tool_result_length]
                        + f"\n... (truncated, {len(result_str)} total chars)"
                    )

                tool_duration = int((time.time() - tool_start) * 1000)

                steps.append(AgentStep(
                    tool_name=tool_name,
                    tool_args=tool_args,
                    tool_result=result_str[:2000],
                    iteration=iteration,
                    duration_ms=tool_duration,
                    error=is_error,
                ))

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result_str,
                })

                logger.info(
                    f"  Tool {tool_name} {'ERROR' if is_error else 'OK'} "
                    f"in {tool_duration}ms ({len(result_str)} chars)"
                )

        # Max iterations reached — request partial summary
        logger.warning(f"Max iterations ({self.max_iterations}) reached")
        return await self._request_partial_summary(
            messages, steps, total_usage, start_time
        )

    async def continue_run(
        self,
        prior_result: AgentResult,
        continuation_message: str,
        temperature: float = 0.4,
        max_tokens: int = 4000,
    ) -> AgentResult:
        """Continue analysis from a prior result."""
        messages = list(prior_result._messages)
        messages.append({"role": "user", "content": continuation_message})

        # Create a temporary ReactLoop instance reusing all config
        # but run() with existing messages
        start_time = time.time()
        steps: List[AgentStep] = []
        total_usage = {"input_tokens": 0, "output_tokens": 0}

        for iteration in range(self.max_iterations):
            elapsed = time.time() - start_time
            if elapsed >= self.total_timeout_sec:
                return self._make_partial_result(
                    steps, total_usage, start_time, messages, "total_timeout"
                )

            if self.cb.is_open:
                return AgentResult(
                    content="Circuit breaker OPEN.",
                    steps=steps,
                    total_usage=total_usage,
                    total_cost=self._calc_cost(total_usage),
                    iterations=iteration,
                    duration_ms=int((time.time() - start_time) * 1000),
                    finish_reason="circuit_breaker",
                    _messages=messages,
                )

            try:
                response = await self.llm.complete_with_tools(
                    messages=messages,
                    tools=self.tool_definitions,
                    model=self.model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                self.cb.record_success()
            except Exception as e:
                self.cb.record_failure()
                return AgentResult(
                    content=f"Ошибка LLM: {type(e).__name__}",
                    steps=steps,
                    total_usage=total_usage,
                    total_cost=self._calc_cost(total_usage),
                    iterations=iteration + 1,
                    duration_ms=int((time.time() - start_time) * 1000),
                    finish_reason="llm_error",
                    _messages=messages,
                )

            usage = response.get("usage", {})
            total_usage["input_tokens"] += (
                usage.get("input_tokens") or usage.get("prompt_tokens", 0)
            )
            total_usage["output_tokens"] += (
                usage.get("output_tokens") or usage.get("completion_tokens", 0)
            )

            content = response.get("content")
            tool_calls = response.get("tool_calls") or []
            finish_reason = response.get("finish_reason", "stop")

            if finish_reason == "stop" or (content and not tool_calls):
                return AgentResult(
                    content=content or "",
                    steps=steps,
                    total_usage=total_usage,
                    total_cost=self._calc_cost(total_usage),
                    iterations=iteration + 1,
                    duration_ms=int((time.time() - start_time) * 1000),
                    finish_reason="stop",
                    _messages=messages,
                )

            if not tool_calls:
                return AgentResult(
                    content=content or "",
                    steps=steps,
                    total_usage=total_usage,
                    total_cost=self._calc_cost(total_usage),
                    iterations=iteration + 1,
                    duration_ms=int((time.time() - start_time) * 1000),
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
                result_str, is_error = await self._execute_tool_safe(
                    tc["name"], tc["arguments"]
                )
                if len(result_str) > self.max_tool_result_length:
                    result_str = (
                        result_str[:self.max_tool_result_length]
                        + f"\n... (truncated)"
                    )
                tool_duration = int((time.time() - tool_start) * 1000)
                steps.append(AgentStep(
                    tool_name=tc["name"],
                    tool_args=tc["arguments"],
                    tool_result=result_str[:2000],
                    iteration=iteration,
                    duration_ms=tool_duration,
                    error=is_error,
                ))
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result_str,
                })

        return self._make_partial_result(
            steps, total_usage, start_time, messages, "max_iterations"
        )

    async def _execute_tool_safe(
        self, tool_name: str, tool_args: dict
    ) -> tuple[str, bool]:
        """Execute a tool with try-catch and timeout. Returns (result, is_error)."""
        try:
            result = await asyncio.wait_for(
                self.tool_executor(tool_name, tool_args),
                timeout=self.tool_timeout_sec,
            )
            return result, False
        except asyncio.TimeoutError:
            error_msg = json.dumps(
                {"error": f"Tool '{tool_name}' timed out after {self.tool_timeout_sec}s"},
                ensure_ascii=False,
            )
            logger.warning(f"Tool timeout: {tool_name}")
            return error_msg, True
        except Exception as e:
            error_msg = json.dumps(
                {"error": f"Tool '{tool_name}' failed: {type(e).__name__}: {e}"},
                ensure_ascii=False,
            )
            logger.error(f"Tool error: {tool_name}: {e}")
            return error_msg, True

    async def _request_partial_summary(
        self,
        messages: List[Dict],
        steps: List[AgentStep],
        total_usage: Dict[str, int],
        start_time: float,
    ) -> AgentResult:
        """When max iterations hit, ask LLM to produce partial answer."""
        messages.append({
            "role": "user",
            "content": (
                "Достигнут лимит шагов анализа. "
                "Сформируй финальный ответ на основе уже собранных данных. "
                "Укажи, что анализ может быть неполным."
            ),
        })

        try:
            response = await self.llm.complete(
                messages=messages,
                model=self.model,
                max_tokens=4000,
            )
            content = response.get("content") or (
                "Превышено максимальное количество шагов анализа. "
                "Частичный результат на основе собранных данных."
            )
            usage = response.get("usage", {})
            total_usage["input_tokens"] += usage.get("input_tokens", 0)
            total_usage["output_tokens"] += usage.get("output_tokens", 0)
        except Exception:
            content = (
                "Превышено максимальное количество шагов анализа. "
                "Частичный результат на основе собранных данных."
            )

        return AgentResult(
            content=content,
            steps=steps,
            total_usage=total_usage,
            total_cost=self._calc_cost(total_usage),
            iterations=self.max_iterations,
            duration_ms=int((time.time() - start_time) * 1000),
            finish_reason="max_iterations",
            _messages=messages,
        )

    def _make_partial_result(
        self,
        steps: List[AgentStep],
        total_usage: Dict[str, int],
        start_time: float,
        messages: List[Dict],
        reason: str,
    ) -> AgentResult:
        """Create a partial result for timeout/error cases."""
        return AgentResult(
            content="Анализ прерван по таймауту. Данные могут быть неполными.",
            steps=steps,
            total_usage=total_usage,
            total_cost=self._calc_cost(total_usage),
            iterations=len([s for s in steps if s.iteration == 0]) or 1,
            duration_ms=int((time.time() - start_time) * 1000),
            finish_reason=reason,
            _messages=messages,
        )

    def _compress_context(self, messages: List[Dict]) -> List[Dict]:
        """Compress tool results in older messages to save context window."""
        compressed = []
        for i, msg in enumerate(messages):
            if msg["role"] == "tool" and i < len(messages) - 6:
                # Keep only first 500 chars of old tool results
                content = msg["content"]
                if len(content) > 500:
                    msg = {**msg, "content": content[:500] + "\n... (compressed)"}
            compressed.append(msg)

        original_len = sum(len(m.get("content", "") or "") for m in messages)
        compressed_len = sum(len(m.get("content", "") or "") for m in compressed)
        if original_len > compressed_len:
            logger.info(
                f"Context compressed: {original_len} → {compressed_len} chars "
                f"({100 - compressed_len * 100 // original_len}% reduction)"
            )
        return compressed

    def _calc_cost(self, usage: dict) -> float:
        """Calculate cost based on model pricing."""
        default_rate = {"input": 0.001, "output": 0.001}
        rates = self.pricing.get(self.model, default_rate)
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        return round(
            (input_tokens / 1000) * rates["input"]
            + (output_tokens / 1000) * rates["output"],
            4,
        )
