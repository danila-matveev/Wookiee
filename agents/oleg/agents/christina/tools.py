"""
Christina Agent tools — knowledge base search + management.

Christina has access to both search and management tools,
unlike other agents who only get search_knowledge_base.
"""
import logging

from services.knowledge_base.tools import (
    KB_SEARCH_TOOL_DEFINITIONS,
    KB_MANAGE_TOOL_DEFINITIONS,
    execute_kb_tool,
)

logger = logging.getLogger(__name__)

# Christina gets all KB tools: search + management
CHRISTINA_TOOL_DEFINITIONS = list(KB_SEARCH_TOOL_DEFINITIONS) + list(KB_MANAGE_TOOL_DEFINITIONS)


async def execute_christina_tool(tool_name: str, tool_args: dict) -> str:
    """Execute a Christina tool. All tools delegate to KB executor."""
    return await execute_kb_tool(tool_name, tool_args)
