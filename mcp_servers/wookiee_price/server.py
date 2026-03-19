"""wookiee-price MCP server — price analysis and strategy tools.

Wraps agents/oleg/services/price_tools.py and services/price_analysis/*.

Run: python -m mcp_servers.wookiee_price.server
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcp.server import Server
from mcp.server.stdio import stdio_server

from mcp_servers.common.server_utils import setup_logging, to_json
from agents.oleg.services.price_tools import PRICE_TOOL_DEFINITIONS, execute_price_tool

setup_logging("wookiee-price")

server = Server("wookiee-price")

_PRICE_TOOL_NAMES = {t["function"]["name"] for t in PRICE_TOOL_DEFINITIONS}


@server.list_tools()
async def list_tools():
    return [
        {
            "name": t["function"]["name"],
            "description": t["function"]["description"],
            "inputSchema": t["function"]["parameters"],
        }
        for t in PRICE_TOOL_DEFINITIONS
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name not in _PRICE_TOOL_NAMES:
        return [{"type": "text", "text": to_json({"error": f"Unknown tool: {name}"})}]

    try:
        result = await execute_price_tool(name, arguments)
        return [{"type": "text", "text": result if isinstance(result, str) else to_json(result)}]
    except Exception as e:
        return [{"type": "text", "text": to_json({"error": str(e), "tool": name})}]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
