"""wookiee-marketing MCP server — marketing funnel and ad analytics.

Wraps agents/oleg/services/marketing_tools.py and funnel_tools.py.

Run: python -m mcp_servers.wookiee_marketing.server
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcp.server import Server
from mcp.server.stdio import stdio_server

from mcp_servers.common.server_utils import setup_logging, to_json
from agents.oleg.services.marketing_tools import (
    MARKETING_TOOL_DEFINITIONS,
    execute_marketing_tool,
)
from agents.oleg.services.funnel_tools import (
    FUNNEL_TOOL_DEFINITIONS,
    execute_funnel_tool,
)

setup_logging("wookiee-marketing")

server = Server("wookiee-marketing")

_MARKETING_NAMES = {t["function"]["name"] for t in MARKETING_TOOL_DEFINITIONS}
_FUNNEL_NAMES = {t["function"]["name"] for t in FUNNEL_TOOL_DEFINITIONS}
_ALL_DEFS = MARKETING_TOOL_DEFINITIONS + FUNNEL_TOOL_DEFINITIONS


@server.list_tools()
async def list_tools():
    return [
        {
            "name": t["function"]["name"],
            "description": t["function"]["description"],
            "inputSchema": t["function"]["parameters"],
        }
        for t in _ALL_DEFS
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    try:
        if name in _MARKETING_NAMES:
            result = await execute_marketing_tool(name, arguments)
        elif name in _FUNNEL_NAMES:
            result = await execute_funnel_tool(name, arguments)
        else:
            return [{"type": "text", "text": to_json({"error": f"Unknown tool: {name}"})}]

        return [{"type": "text", "text": result if isinstance(result, str) else to_json(result)}]
    except Exception as e:
        return [{"type": "text", "text": to_json({"error": str(e), "tool": name})}]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
