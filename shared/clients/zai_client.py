"""
z.ai API Client
Primary AI provider for cost-effective query processing
"""
import httpx
import json
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class ZAIClient:
    """Client for z.ai API"""

    def __init__(self, api_key: str, model: str = "jlm", base_url: str = "https://api.z.ai/api/paas/v4"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

    async def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        model: Optional[str] = None,
        response_format: Optional[Dict[str, str]] = None,
        timeout: float = 90.0,
    ) -> Dict[str, Any]:
        """
        Send completion request to z.ai

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            model: Optional model override (default: self.model)
            timeout: Request timeout in seconds (default: 90)

        Returns:
            Response dict with 'content', 'confidence', and 'usage'
        """
        use_model = model or self.model
        last_error = None

        for attempt in range(2):  # 1 retry on transient errors
            try:
                async with httpx.AsyncClient() as client:
                    payload = {
                        "model": use_model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    }
                    if response_format:
                        payload["response_format"] = response_format

                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json"
                        },
                        json=payload,
                        timeout=timeout,
                    )

                    response.raise_for_status()
                    data = response.json()

                    # Extract response
                    content = data["choices"][0]["message"]["content"]
                    usage = data.get("usage", {})

                    # Calculate confidence (z.ai specific)
                    confidence = self._calculate_confidence(data)

                    return {
                        "content": content,
                        "confidence": confidence,
                        "usage": usage,
                        "model": use_model,
                    }

            except httpx.HTTPStatusError as e:
                error_body = e.response.text if e.response else "no response body"
                logger.error(f"z.ai API HTTP error: {type(e).__name__}: {e} | Body: {error_body[:500]}")
                return {
                    "content": None,
                    "confidence": 0.0,
                    "error": f"{type(e).__name__}: {e}"
                }
            except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as e:
                last_error = e
                logger.warning(f"z.ai API transient error (attempt {attempt+1}/2): {type(e).__name__}: {e}")
                if attempt == 0:
                    continue  # retry once
            except Exception as e:
                logger.error(f"z.ai API error: {type(e).__name__}: {e}")
                return {
                    "content": None,
                    "confidence": 0.0,
                    "error": f"{type(e).__name__}: {e}" or "unknown error"
                }

        # All retries exhausted
        logger.error(f"z.ai API failed after 2 attempts: {type(last_error).__name__}: {last_error}")
        return {
            "content": None,
            "confidence": 0.0,
            "error": f"{type(last_error).__name__}: {last_error}" if last_error else "unknown error"
        }

    async def complete_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        tool_choice: str = "auto",
        temperature: float = 0.4,
        max_tokens: int = 2000,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Completion with tool-use support (OpenAI-compatible format).

        Returns:
            {
                "content": str | None,
                "tool_calls": [{"id": ..., "name": ..., "arguments": {...}}] | None,
                "finish_reason": "stop" | "tool_calls",
                "usage": {...},
                "model": str,
            }
        """
        use_model = model or self.model
        last_error = None

        for attempt in range(2):  # 1 retry on transient errors
            try:
                async with httpx.AsyncClient() as client:
                    payload = {
                        "model": use_model,
                        "messages": messages,
                        "tools": tools,
                        "tool_choice": tool_choice,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    }

                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json"
                        },
                        json=payload,
                        timeout=120.0  # Longer timeout for tool-use
                    )

                    response.raise_for_status()
                    data = response.json()

                    choice = data["choices"][0]
                    message = choice["message"]
                    finish_reason = choice.get("finish_reason", "stop")
                    usage = data.get("usage", {})

                    # Extract content
                    content = message.get("content")

                    # Extract tool calls
                    raw_tool_calls = message.get("tool_calls")
                    tool_calls = None
                    if raw_tool_calls:
                        tool_calls = []
                        for tc in raw_tool_calls:
                            func = tc.get("function", {})
                            args_str = func.get("arguments", "{}")
                            try:
                                args = json.loads(args_str) if isinstance(args_str, str) else args_str
                            except json.JSONDecodeError:
                                args = {"_raw": args_str}

                            tool_calls.append({
                                "id": tc.get("id", f"call_{id(tc)}"),
                                "name": func.get("name", ""),
                                "arguments": args,
                            })

                    return {
                        "content": content,
                        "tool_calls": tool_calls,
                        "finish_reason": finish_reason,
                        "usage": usage,
                        "model": use_model,
                    }

            except httpx.HTTPStatusError as e:
                error_body = e.response.text if e.response else "no response body"
                logger.error(f"z.ai tool-use API error: {e} | Body: {error_body[:500]}")
                return {
                    "content": None,
                    "tool_calls": None,
                    "finish_reason": "error",
                    "usage": {},
                    "error": str(e),
                }
            except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as e:
                last_error = e
                logger.warning(f"z.ai tool-use transient error (attempt {attempt+1}/2): {type(e).__name__}: {e}")
                if attempt == 0:
                    continue  # retry once
            except Exception as e:
                logger.error(f"z.ai tool-use error: {e}")
                return {
                    "content": None,
                    "tool_calls": None,
                    "finish_reason": "error",
                    "usage": {},
                    "error": str(e),
                }

        # All retries exhausted
        logger.error(f"z.ai tool-use failed after 2 attempts: {type(last_error).__name__}: {last_error}")
        return {
            "content": None,
            "tool_calls": None,
            "finish_reason": "error",
            "usage": {},
            "error": f"{type(last_error).__name__}: {last_error}" if last_error else "unknown error",
        }

    async def extract_parameters(
        self,
        user_query: str,
        schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract structured parameters from user query

        Args:
            user_query: Natural language query
            schema: JSON schema for expected parameters

        Returns:
            Extracted parameters dict with confidence score
        """
        system_prompt = f"""You are a parameter extraction assistant.
Extract structured parameters from user queries according to this schema:

{json.dumps(schema, indent=2)}

Return ONLY valid JSON matching the schema. Include a 'confidence' field (0.0-1.0)."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ]

        response = await self.complete(messages, temperature=0.3)

        if not response.get("content"):
            return {"confidence": 0.0, "error": response.get("error")}

        try:
            # Parse JSON response
            params = json.loads(response["content"])
            params["z_ai_confidence"] = response.get("confidence", 0.0)
            return params
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse z.ai JSON response: {e}")
            return {"confidence": 0.0, "error": "Invalid JSON response"}

    def _calculate_confidence(self, response_data: Dict[str, Any]) -> float:
        """
        Calculate confidence score from z.ai response

        Args:
            response_data: Raw API response

        Returns:
            Confidence score (0.0-1.0)
        """
        # Check if z.ai provides confidence in response
        if "confidence" in response_data:
            return float(response_data["confidence"])

        # Otherwise calculate based on finish_reason and other signals
        finish_reason = response_data.get("choices", [{}])[0].get("finish_reason")

        if finish_reason == "stop":
            return 0.8  # Normal completion
        elif finish_reason == "length":
            return 0.6  # Truncated response
        else:
            return 0.5  # Unknown finish reason

    async def health_check(self) -> bool:
        """
        Check if z.ai API is accessible

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Use a minimal completion request as health check
            result = await self.complete(
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=5
            )
            return result.get("content") is not None
        except Exception as e:
            logger.error(f"z.ai health check failed: {e}")
            return False
