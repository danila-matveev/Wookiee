"""wookiee-data MCP server — financial analytics tools.

Wraps shared/data_layer.py and agents/oleg/services/agent_tools.py
to expose financial data via MCP protocol.

Run: python -m mcp_servers.wookiee_data.server
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcp.server import Server
from mcp.server.stdio import stdio_server

from mcp_servers.common.server_utils import setup_logging, to_json
from agents.oleg.services.agent_tools import TOOL_DEFINITIONS, execute_tool
from agents.oleg.services.price_tools import PRICE_TOOL_DEFINITIONS

setup_logging("wookiee-data")

server = Server("wookiee-data")

# Filter out price tools — those belong to wookiee-price server
_PRICE_TOOL_NAMES = {t["function"]["name"] for t in PRICE_TOOL_DEFINITIONS}
_DATA_TOOL_DEFS = [t for t in TOOL_DEFINITIONS if t["function"]["name"] not in _PRICE_TOOL_NAMES]
_DATA_TOOL_NAMES = {t["function"]["name"] for t in _DATA_TOOL_DEFS}


@server.list_tools()
async def list_tools():
    """Return tool definitions in MCP format (data tools only, no price tools)."""
    return [
        {
            "name": t["function"]["name"],
            "description": t["function"]["description"],
            "inputSchema": t["function"]["parameters"],
        }
        for t in _DATA_TOOL_DEFS
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Dispatch tool call via execute_tool() dispatcher."""
    if name not in _DATA_TOOL_NAMES:
        return [{"type": "text", "text": to_json({"error": f"Unknown tool: {name}"})}]

    try:
        result = await execute_tool(name, arguments)
        return [{"type": "text", "text": result if isinstance(result, str) else to_json(result)}]
    except Exception as e:
        return [{"type": "text", "text": to_json({"error": str(e), "tool": name})}]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
