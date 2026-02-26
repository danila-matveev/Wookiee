"""
Marketer Agent tools — marketing funnel and ad efficiency tools.

Tool definitions and handlers from agents/oleg/services/marketing_tools.py.
All SQL queries delegate to shared/data_layer.py.
"""
from agents.oleg.services.marketing_tools import (
    MARKETING_TOOL_DEFINITIONS,
    execute_marketing_tool,
)

# Export for MarketerAgent
MARKETER_TOOL_DEFINITIONS = list(MARKETING_TOOL_DEFINITIONS)


async def execute_marketer_tool(tool_name: str, tool_args: dict) -> str:
    """Execute a marketer tool. Delegates to marketing_tools executor."""
    return await execute_marketing_tool(tool_name, tool_args)
