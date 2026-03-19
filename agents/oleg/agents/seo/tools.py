"""
Funnel Agent tools — delegates to services/funnel_tools.py + KB search.

Tool definitions and handlers for funnel analysis (Макар).
All SQL queries delegate to shared/data_layer.py.
KB search is available for expert knowledge consultation.
"""
import logging

from agents.oleg.services.funnel_tools import (
    FUNNEL_TOOL_DEFINITIONS,
    execute_funnel_tool,
)

logger = logging.getLogger(__name__)

# KB search tools (optional — graceful if KB service unavailable)
_kb_available = False
try:
    from services.knowledge_base.tools import KB_SEARCH_TOOL_DEFINITIONS, execute_kb_tool
    _kb_available = True
except ImportError:
    KB_SEARCH_TOOL_DEFINITIONS = []
    logger.warning("KB tools not available for Funnel agent")

# Combined tool definitions: funnel analysis + KB search
FUNNEL_COMBINED_TOOL_DEFINITIONS = list(FUNNEL_TOOL_DEFINITIONS) + list(KB_SEARCH_TOOL_DEFINITIONS)


async def execute_funnel_combined_tool(tool_name: str, tool_args: dict) -> str:
    """Execute a funnel or KB tool."""
    if _kb_available and tool_name == "search_knowledge_base":
        return await execute_kb_tool(tool_name, tool_args)
    return await execute_funnel_tool(tool_name, tool_args)


__all__ = [
    "FUNNEL_TOOL_DEFINITIONS",
    "FUNNEL_COMBINED_TOOL_DEFINITIONS",
    "execute_funnel_tool",
    "execute_funnel_combined_tool",
]
