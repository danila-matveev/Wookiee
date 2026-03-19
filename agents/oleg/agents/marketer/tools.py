"""
Marketer Agent tools — marketing funnel and ad efficiency tools + knowledge base.

Tool definitions and handlers from agents/oleg/services/marketing_tools.py.
All SQL queries delegate to shared/data_layer.py.
"""
import logging

from agents.oleg.services.marketing_tools import (
    MARKETING_TOOL_DEFINITIONS,
    execute_marketing_tool,
)

logger = logging.getLogger(__name__)

# Knowledge Base tool (optional)
_kb_available = False
try:
    from services.knowledge_base.tools import KB_TOOL_DEFINITIONS, execute_kb_tool
    _kb_available = True
except ImportError:
    KB_TOOL_DEFINITIONS = []
    logger.info("Knowledge Base tools not available for Marketer")

# Export for MarketerAgent (marketing tools + KB)
MARKETER_TOOL_DEFINITIONS = list(MARKETING_TOOL_DEFINITIONS) + list(KB_TOOL_DEFINITIONS)


async def execute_marketer_tool(tool_name: str, tool_args: dict) -> str:
    """Execute a marketer tool. Delegates to marketing_tools executor or KB."""
    if _kb_available and tool_name == "search_knowledge_base":
        return await execute_kb_tool(tool_name, tool_args)
    return await execute_marketing_tool(tool_name, tool_args)
