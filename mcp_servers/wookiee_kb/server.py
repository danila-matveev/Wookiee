"""wookiee-kb MCP server — knowledge base search and management.

Wraps services/knowledge_base/ tools.

Run: python -m mcp_servers.wookiee_kb.server
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcp.server import Server
from mcp.server.stdio import stdio_server

from mcp_servers.common.server_utils import setup_logging, to_json
from services.knowledge_base.tools import (
    KB_SEARCH_TOOL_DEFINITIONS,
    KB_MANAGE_TOOL_DEFINITIONS,
    execute_kb_tool,
)

setup_logging("wookiee-kb")

server = Server("wookiee-kb")

_ALL_DEFS = KB_SEARCH_TOOL_DEFINITIONS + KB_MANAGE_TOOL_DEFINITIONS
_ALL_NAMES = {t["function"]["name"] for t in _ALL_DEFS}


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
    if name not in _ALL_NAMES:
        return [{"type": "text", "text": to_json({"error": f"Unknown tool: {name}"})}]

    try:
        result = await execute_kb_tool(name, arguments)
        return [{"type": "text", "text": result if isinstance(result, str) else to_json(result)}]
    except Exception as e:
        return [{"type": "text", "text": to_json({"error": str(e), "tool": name})}]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
