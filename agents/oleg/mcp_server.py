"""
Oleg MCP Server — exposes Oleg's analytics tools via MCP HTTP transport.

Thin wrapper around existing tool executors + orchestrator.
Designed for eggent integration — runs as a separate Docker container.
"""
import asyncio
import json
import logging
import os
import sys
from typing import Any

from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import Tool, TextContent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool registry: collects all tool definitions and executors from Oleg agents
# ---------------------------------------------------------------------------

# Each entry: (TOOL_DEFINITIONS list, executor_fn)
# executor_fn signature: async (tool_name: str, args: dict) -> str (JSON)
_TOOL_REGISTRIES: list[tuple[list[dict], Any]] = []


def _load_registries():
    """Import and collect all tool registries. Called once at startup."""
    global _TOOL_REGISTRIES

    # 1. Reporter tools (financial + price = 30 tools)
    from agents.oleg.services.agent_tools import (
        TOOL_DEFINITIONS as REPORTER_DEFS,
        execute_tool as execute_reporter,
    )
    _TOOL_REGISTRIES.append((REPORTER_DEFS, execute_reporter))

    # 2. Marketing tools (12 tools)
    from agents.oleg.services.marketing_tools import (
        MARKETING_TOOL_DEFINITIONS,
        execute_marketing_tool,
    )
    _TOOL_REGISTRIES.append((MARKETING_TOOL_DEFINITIONS, execute_marketing_tool))

    # 3. Researcher tools (10 tools)
    from agents.oleg.agents.researcher.tools import (
        RESEARCHER_TOOL_DEFINITIONS,
        execute_researcher_tool,
    )
    _TOOL_REGISTRIES.append((RESEARCHER_TOOL_DEFINITIONS, execute_researcher_tool))

    # 4. Quality tools (5 tools)
    from agents.oleg.agents.quality.tools import (
        QUALITY_TOOL_DEFINITIONS,
        execute_quality_tool,
        set_playbook_path,
        set_state_store,
    )
    _TOOL_REGISTRIES.append((QUALITY_TOOL_DEFINITIONS, execute_quality_tool))

    # Initialize quality tool dependencies
    from agents.oleg import config
    set_playbook_path(config.PLAYBOOK_PATH)

    from agents.oleg.storage.state_store import StateStore
    state_store = StateStore(config.SQLITE_DB_PATH)
    state_store.init_db()
    set_state_store(state_store)

    # Initialize LearningStore for price tools
    from agents.oleg.services.price_analysis.learning_store import LearningStore
    from agents.oleg.services.price_tools import set_learning_store
    learning_store = LearningStore()
    set_learning_store(learning_store)

    # 5. Knowledge Base tools (search + management)
    try:
        from services.knowledge_base.tools import (
            KB_SEARCH_TOOL_DEFINITIONS,
            KB_MANAGE_TOOL_DEFINITIONS,
            execute_kb_tool,
        )
        all_kb_tools = list(KB_SEARCH_TOOL_DEFINITIONS) + list(KB_MANAGE_TOOL_DEFINITIONS)
        _TOOL_REGISTRIES.append((all_kb_tools, execute_kb_tool))
        logger.info("Knowledge Base tools loaded (%d search + %d manage)",
                     len(KB_SEARCH_TOOL_DEFINITIONS), len(KB_MANAGE_TOOL_DEFINITIONS))
    except ImportError:
        logger.warning("Knowledge Base tools not available (services.knowledge_base not installed)")


def _build_tool_index() -> dict[str, tuple[dict, Any]]:
    """Build name -> (tool_def, executor) index. Deduplicates by name."""
    index = {}
    for defs, executor in _TOOL_REGISTRIES:
        for tool_def in defs:
            name = tool_def["function"]["name"]
            if name not in index:
                index[name] = (tool_def, executor)
    return index


# ---------------------------------------------------------------------------
# Orchestrator (for ask_oleg high-level tool)
# ---------------------------------------------------------------------------

_orchestrator = None


async def _init_orchestrator():
    """Initialize orchestrator (same as OlegApp.setup minus Telegram/scheduler)."""
    global _orchestrator
    from agents.oleg import config
    from shared.clients.openrouter_client import OpenRouterClient

    llm_client = OpenRouterClient(
        api_key=config.OPENROUTER_API_KEY,
        model=config.ANALYTICS_MODEL,
        fallback_model=config.FALLBACK_MODEL,
        site_name="Wookiee Oleg MCP",
    )

    from agents.oleg.agents.reporter.agent import ReporterAgent
    reporter = ReporterAgent(
        llm_client=llm_client,
        model=config.ANALYTICS_MODEL,
        pricing=config.PRICING,
        max_iterations=config.MAX_ITERATIONS,
        tool_timeout_sec=config.TOOL_TIMEOUT_SEC,
        total_timeout_sec=config.TOTAL_TIMEOUT_SEC,
    )

    from agents.oleg.agents.researcher.agent import ResearcherAgent
    researcher = ResearcherAgent(
        llm_client=llm_client,
        model=config.ANALYTICS_MODEL,
        pricing=config.PRICING,
        max_iterations=config.MAX_ITERATIONS,
        tool_timeout_sec=config.TOOL_TIMEOUT_SEC,
        total_timeout_sec=config.TOTAL_TIMEOUT_SEC,
    )

    from agents.oleg.agents.quality.agent import QualityAgent
    quality = QualityAgent(
        llm_client=llm_client,
        model=config.ANALYTICS_MODEL,
        pricing=config.PRICING,
        playbook_path=config.PLAYBOOK_PATH,
        state_store=None,  # MCP server: read-only mode for state
        max_iterations=config.MAX_ITERATIONS,
        tool_timeout_sec=config.TOOL_TIMEOUT_SEC,
        total_timeout_sec=config.TOTAL_TIMEOUT_SEC,
    )

    from agents.oleg.agents.marketer.agent import MarketerAgent
    marketer = MarketerAgent(
        llm_client=llm_client,
        model=config.ANALYTICS_MODEL,
        pricing=config.PRICING,
        playbook_path=config.MARKETING_PLAYBOOK_PATH,
        max_iterations=config.MAX_ITERATIONS,
        tool_timeout_sec=config.TOOL_TIMEOUT_SEC,
        total_timeout_sec=config.TOTAL_TIMEOUT_SEC,
    )

    from agents.oleg.agents.seo.agent import FunnelAgent
    funnel = FunnelAgent(
        llm_client=llm_client,
        model=config.ANALYTICS_MODEL,
        pricing=config.PRICING,
        playbook_path=config.FUNNEL_PLAYBOOK_PATH,
        max_iterations=config.MAX_ITERATIONS,
        tool_timeout_sec=config.TOOL_TIMEOUT_SEC,
        total_timeout_sec=config.TOTAL_TIMEOUT_SEC,
    )

    from agents.oleg.agents.christina.agent import ChristinaAgent
    christina = ChristinaAgent(
        llm_client=llm_client,
        model=config.ANALYTICS_MODEL,
        pricing=config.PRICING,
        playbook_path=config.CHRISTINA_PLAYBOOK_PATH,
        max_iterations=config.MAX_ITERATIONS,
        tool_timeout_sec=config.TOOL_TIMEOUT_SEC,
        total_timeout_sec=config.TOTAL_TIMEOUT_SEC,
    )

    from agents.oleg.orchestrator.orchestrator import OlegOrchestrator
    _orchestrator = OlegOrchestrator(
        llm_client=llm_client,
        model=config.ANALYTICS_MODEL,
        agents={
            "reporter": reporter,
            "researcher": researcher,
            "quality": quality,
            "marketer": marketer,
            "funnel": funnel,
            "christina": christina,
        },
        pricing=config.PRICING,
    )
    logger.info("Orchestrator initialized with 6 sub-agents")


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

def _openai_to_mcp_schema(func_def: dict) -> dict:
    """Convert OpenAI function calling params to MCP JSON Schema."""
    params = func_def.get("parameters", {})
    # OpenAI format is already JSON Schema compatible
    return params


def create_server() -> Server:
    """Create and configure the MCP server."""
    server = Server("oleg")

    _load_registries()
    tool_index = _build_tool_index()
    logger.info("Loaded %d tools from %d registries", len(tool_index), len(_TOOL_REGISTRIES))

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        tools = []

        # High-level orchestrator tool
        tools.append(Tool(
            name="ask_oleg",
            description=(
                "Задать вопрос Олегу — AI финансовому аналитику бренда Wookiee. "
                "Использует мульти-агентную оркестрацию (Reporter → Researcher → Quality → Marketer). "
                "Для сложных аналитических вопросов: 'Почему упала маржа?', 'Сравни WB и OZON за неделю'. "
                "Может занять 30-180 секунд."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Вопрос для Олега (на русском)",
                    },
                    "task_type": {
                        "type": "string",
                        "enum": ["query", "daily", "weekly", "monthly",
                                 "marketing_daily", "marketing_weekly",
                                 "marketing_monthly", "marketing_custom",
                                 "funnel_weekly", "custom", "feedback"],
                        "description": "Тип задачи (по умолчанию query — свободный вопрос)",
                        "default": "query",
                    },
                },
                "required": ["question"],
            },
        ))

        # Individual tools from all registries
        for name, (tool_def, _) in tool_index.items():
            func = tool_def["function"]
            tools.append(Tool(
                name=name,
                description=func.get("description", ""),
                inputSchema=_openai_to_mcp_schema(func),
            ))

        return tools

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        # Handle ask_oleg separately
        if name == "ask_oleg":
            if _orchestrator is None:
                await _init_orchestrator()

            question = arguments.get("question", "")
            task_type = arguments.get("task_type", "query")

            try:
                result = await _orchestrator.run_chain(
                    task=question,
                    task_type=task_type,
                )
                response = {
                    "summary": result.summary,
                    "detailed": result.detailed,
                    "telegram_summary": result.telegram_summary,
                    "steps": result.total_steps,
                    "cost_usd": result.total_cost,
                    "duration_ms": result.total_duration_ms,
                }
                return [TextContent(
                    type="text",
                    text=json.dumps(response, ensure_ascii=False, default=str),
                )]
            except Exception as e:
                logger.error("ask_oleg failed: %s", e, exc_info=True)
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": str(e)}, ensure_ascii=False),
                )]

        # Individual tools — lookup in registry
        if name not in tool_index:
            return [TextContent(
                type="text",
                text=json.dumps({"error": f"Unknown tool: {name}"}, ensure_ascii=False),
            )]

        _, executor = tool_index[name]
        try:
            result_json = await executor(name, arguments)
            return [TextContent(type="text", text=result_json)]
        except Exception as e:
            logger.error("Tool %s failed: %s", name, e, exc_info=True)
            return [TextContent(
                type="text",
                text=json.dumps({"error": str(e)}, ensure_ascii=False),
            )]

    return server


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main():
    """Run MCP server with Streamable HTTP transport."""
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8080"))

    server = create_server()
    session_manager = StreamableHTTPSessionManager(
        app=server,
        stateless=True,
    )

    from starlette.applications import Starlette
    from starlette.routing import Route
    from starlette.responses import JSONResponse
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def lifespan(app):
        async with session_manager.run():
            yield

    async def health(request):
        return JSONResponse({"status": "ok", "service": "oleg-mcp"})

    async def handle_mcp(scope, receive, send):
        await session_manager.handle_request(scope, receive, send)

    from starlette.routing import Mount

    app = Starlette(
        routes=[
            Route("/health", health),
            Mount("/mcp", app=handle_mcp),
            Mount("/sse", app=handle_mcp),
        ],
        lifespan=lifespan,
    )

    import uvicorn
    logger.info("Starting Oleg MCP Server on %s:%d", host, port)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
