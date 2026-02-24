"""
Reporter Agent tools — financial and price analysis tools.

Tool definitions and handlers from agents/oleg/services/agent_tools.py
and agents/oleg/services/price_tools.py.
All SQL queries delegate to shared/data_layer.py.
"""
from agents.oleg.services.agent_tools import (
    TOOL_DEFINITIONS as FINANCIAL_TOOL_DEFINITIONS,
    TOOL_HANDLERS as FINANCIAL_TOOL_HANDLERS,
    execute_tool as _v1_execute_tool,
)
from agents.oleg.services.price_tools import (
    PRICE_TOOL_DEFINITIONS,
    PRICE_TOOL_HANDLERS,
)

# Combined tool definitions (12 financial + 18 price = 30 tools)
REPORTER_TOOL_DEFINITIONS = list(FINANCIAL_TOOL_DEFINITIONS)
# Price tools are already appended to FINANCIAL_TOOL_DEFINITIONS in v1's agent_tools.py
# but we need standalone lists for clarity
_ALL_DEFINITIONS = REPORTER_TOOL_DEFINITIONS  # Already includes price tools

# Combined handlers
REPORTER_TOOL_HANDLERS = {**FINANCIAL_TOOL_HANDLERS}
# Price handlers already merged in v1's agent_tools.py


async def execute_reporter_tool(tool_name: str, tool_args: dict) -> str:
    """Execute a reporter tool. Delegates to v1 tool executor."""
    return await _v1_execute_tool(tool_name, tool_args)
