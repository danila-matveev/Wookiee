"""Shared utilities for all Wookiee MCP servers."""
import json
import logging
import sys
from datetime import date, datetime
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)


class WookieeJSONEncoder(json.JSONEncoder):
    """JSON encoder handling date, datetime, Decimal types from DB results."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def to_json(data: Any) -> str:
    """Serialize data to JSON string, handling DB types."""
    return json.dumps(data, cls=WookieeJSONEncoder, ensure_ascii=False)


def safe_tool_call(func):
    """Decorator for MCP tool handlers. Catches exceptions, returns JSON error."""
    async def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            # Handle both sync and async functions
            if hasattr(result, "__await__"):
                result = await result
            return to_json(result)
        except Exception as e:
            logger.exception(f"Tool call failed: {func.__name__}")
            return to_json({"error": str(e), "tool": func.__name__})
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


def setup_logging(server_name: str) -> None:
    """Configure logging for an MCP server."""
    logging.basicConfig(
        level=logging.INFO,
        format=f"%(asctime)s [{server_name}] %(levelname)s: %(message)s",
        stream=sys.stderr,  # MCP uses stdout for protocol, stderr for logs
    )
