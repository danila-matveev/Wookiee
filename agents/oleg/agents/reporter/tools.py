"""
Reporter Agent tools — financial and price analysis tools + knowledge base.

Tool definitions and handlers from agents/oleg/services/agent_tools.py
and agents/oleg/services/price_tools.py.
All SQL queries delegate to shared/data_layer.py.
"""
import logging

from agents.oleg.services.agent_tools import (
    TOOL_DEFINITIONS as FINANCIAL_TOOL_DEFINITIONS,
    TOOL_HANDLERS as FINANCIAL_TOOL_HANDLERS,
    execute_tool as _v1_execute_tool,
)
from agents.oleg.services.price_tools import (
    PRICE_TOOL_DEFINITIONS,
    PRICE_TOOL_HANDLERS,
)

logger = logging.getLogger(__name__)

# Knowledge Base tool (optional — graceful fallback if not installed)
_kb_available = False
try:
    from services.knowledge_base.tools import KB_TOOL_DEFINITIONS, execute_kb_tool
    _kb_available = True
except ImportError:
    KB_TOOL_DEFINITIONS = []
    logger.info("Knowledge Base tools not available for Reporter")

# Combined tool definitions (12 financial + 18 price + 1 KB = 31 tools)
REPORTER_TOOL_DEFINITIONS = list(FINANCIAL_TOOL_DEFINITIONS) + list(KB_TOOL_DEFINITIONS)
_ALL_DEFINITIONS = REPORTER_TOOL_DEFINITIONS

# Combined handlers
REPORTER_TOOL_HANDLERS = {**FINANCIAL_TOOL_HANDLERS}


async def execute_reporter_tool(tool_name: str, tool_args: dict) -> str:
    """Execute a reporter tool. Delegates to v1 tool executor or KB."""
    if _kb_available and tool_name == "search_knowledge_base":
        return await execute_kb_tool(tool_name, tool_args)
    return await _v1_execute_tool(tool_name, tool_args)
