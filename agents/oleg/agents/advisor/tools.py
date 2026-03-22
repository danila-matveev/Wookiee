"""Advisor Agent tool definitions and executor."""
import json
import logging

logger = logging.getLogger(__name__)

# Advisor has access to KB search for finding relevant patterns
_kb_available = False
try:
    from services.knowledge_base.tools import KB_SEARCH_TOOL_DEFINITIONS, execute_kb_tool
    _kb_available = True
except ImportError:
    KB_SEARCH_TOOL_DEFINITIONS = []
    logger.info("Knowledge Base tools not available for Advisor")

ADVISOR_TOOL_DEFINITIONS = list(KB_SEARCH_TOOL_DEFINITIONS)


async def execute_advisor_tool(tool_name: str, tool_args: dict) -> str:
    """Execute an advisor tool. Currently only KB search is supported."""
    if _kb_available and tool_name == "search_knowledge_base":
        return await execute_kb_tool(tool_name, tool_args)
    return json.dumps({"error": f"Unknown tool: {tool_name}"}, ensure_ascii=False)
