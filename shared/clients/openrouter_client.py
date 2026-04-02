"""
OpenRouter API Client — единый LLM-клиент для всех агентов Wookiee.

Использует OpenAI Python SDK с base_url = https://openrouter.ai/api/v1.
Модельные тиры:
- LIGHT: google/gemini-3-flash-preview — классификация, intent detection
- MAIN: google/gemini-3-flash-preview — аналитика, tool-use, отчёты
- HEAVY: anthropic/claude-sonnet-4-6 — сложный reasoning, fallback
- FREE: openrouter/free — last-resort fallback
"""
import json
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# Default models
DEFAULT_MODEL = "google/gemini-3-flash-preview"
DEFAULT_FALLBACK = "openrouter/free"


class OpenRouterClient:
    """OpenAI-compatible client for OpenRouter API."""

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        fallback_model: str = DEFAULT_FALLBACK,
        site_name: str = "Wookiee Analytics",
    ):
        """
        Args:
            api_key: OpenRouter API key
            model: Default model (OpenRouter model ID)
            fallback_model: Model to use when primary fails
            site_name: App name for OpenRouter analytics
        """
        self.api_key = api_key
        self.model = model
        self.fallback_model = fallback_model
        self.site_name = site_name

        try:
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1",
                default_headers={
                    "HTTP-Referer": "https://wookiee.ru",
                    "X-Title": site_name,
                },
            )
            logger.info(f"OpenRouterClient initialized, default model: {model}")
        except ImportError:
            logger.error("openai package not installed. Run: pip install openai>=1.30.0")
            self.client = None

    async def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.4,
        max_tokens: int = 4000,
        model: Optional[str] = None,
        response_format: Optional[Dict[str, str]] = None,
        timeout: float = 120.0,
    ) -> Dict[str, Any]:
        """
        Send completion request via OpenRouter.

        Compatible with ZAIClient.complete() interface.
        """
        if not self.client:
            return {"content": None, "error": "OpenRouter client not initialized"}

        use_model = model or self.model

        try:
            kwargs = {
                "model": use_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if response_format:
                kwargs["response_format"] = response_format

            response = await self.client.chat.completions.create(**kwargs)

            content = response.choices[0].message.content
            finish_reason = response.choices[0].finish_reason if response.choices else "unknown"
            usage = {
                "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                "output_tokens": response.usage.completion_tokens if response.usage else 0,
            }

            if finish_reason == "length":
                logger.warning(
                    f"Response truncated (finish_reason=length), "
                    f"max_tokens={max_tokens}, model={use_model}"
                )

            return {
                "content": content,
                "confidence": 0.8 if finish_reason == "stop" else 0.6,
                "finish_reason": finish_reason,
                "usage": usage,
                "model": use_model,
            }

        except Exception as e:
            logger.error(f"OpenRouter API error: {type(e).__name__}: {e}")
            # Try fallback model
            if use_model != self.fallback_model:
                logger.info(f"Trying fallback model: {self.fallback_model}")
                return await self.complete(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    model=self.fallback_model,
                    response_format=response_format,
                )
            return {
                "content": None,
                "confidence": 0.0,
                "error": f"{type(e).__name__}: {e}",
            }

    async def complete_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        tool_choice: str = "auto",
        temperature: float = 0.4,
        max_tokens: int = 4000,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Completion with tool-use support.

        Compatible with ZAIClient.complete_with_tools() interface.
        """
        if not self.client:
            return {
                "content": None,
                "tool_calls": None,
                "finish_reason": "error",
                "usage": {},
                "error": "OpenRouter client not initialized",
            }

        use_model = model or self.model

        try:
            response = await self.client.chat.completions.create(
                model=use_model,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            choice = response.choices[0]
            message = choice.message
            finish_reason = choice.finish_reason or "stop"
            usage = {
                "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                "output_tokens": response.usage.completion_tokens if response.usage else 0,
            }

            content = message.content
            tool_calls = None

            if message.tool_calls:
                tool_calls = []
                for tc in message.tool_calls:
                    try:
                        args = json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments
                    except json.JSONDecodeError:
                        args = {"_raw": tc.function.arguments}

                    tool_calls.append({
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": args,
                    })

            return {
                "content": content,
                "tool_calls": tool_calls,
                "finish_reason": finish_reason,
                "usage": usage,
                "model": use_model,
            }

        except Exception as e:
            logger.error(f"OpenRouter tool-use error: {type(e).__name__}: {e}")
            # Try fallback model
            if use_model != self.fallback_model:
                logger.info(f"Tool-use fallback: {self.fallback_model}")
                return await self.complete_with_tools(
                    messages=messages,
                    tools=tools,
                    tool_choice=tool_choice,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    model=self.fallback_model,
                )
            return {
                "content": None,
                "tool_calls": None,
                "finish_reason": "error",
                "usage": {},
                "error": f"{type(e).__name__}: {e}",
            }

    async def health_check(self) -> bool:
        """Check if OpenRouter API is accessible."""
        try:
            result = await self.complete(
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=5,
            )
            return result.get("content") is not None
        except Exception as e:
            logger.error(f"OpenRouter health check failed: {e}")
            return False
