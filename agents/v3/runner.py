"""Agent runner — loads MD-defined agents and executes them via LangGraph.

Internal agents call Python tool handlers directly (not via MCP protocol).
MCP servers are for external clients like Claude Code.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from agents.v3 import config
from services.observability.logger import log_agent_run, new_run_id
from services.observability.version_tracker import compute_prompt_hash

logger = logging.getLogger(__name__)


# ── Tool registries (import existing handlers) ──────────────────────────
# These map tool_name -> async callable(**kwargs) -> result

def _build_tool_registry() -> dict[str, dict]:
    """Build unified tool registry from all existing tool modules.

    Returns {tool_name: {"handler": callable, "definition": dict, "server": str}}

    Design notes:
    - agent_tools.TOOL_HANDLERS already includes PRICE_TOOL_HANDLERS via .update()
      at module level, so we import once and split by which sub-dict owns the name.
    - KB tools have no HANDLERS dict; they use execute_kb_tool(tool_name, arguments).
      We build per-tool lambdas that wrap the dispatcher.
    """
    registry: dict[str, dict] = {}

    # ── wookiee-data + wookiee-price ─────────────────────────────────────
    from agents.oleg.services.price_tools import PRICE_TOOL_DEFINITIONS, PRICE_TOOL_HANDLERS
    from agents.oleg.services.agent_tools import TOOL_DEFINITIONS as DATA_DEFS, TOOL_HANDLERS as DATA_HANDLERS

    # TOOL_HANDLERS already has price entries merged in at import time.
    # Assign server label based on which sub-dict originally owned the name.
    price_names = set(PRICE_TOOL_HANDLERS.keys())

    for tdef in DATA_DEFS:
        name = tdef["function"]["name"]
        if name in DATA_HANDLERS:
            server = "wookiee-price" if name in price_names else "wookiee-data"
            registry[name] = {"handler": DATA_HANDLERS[name], "definition": tdef, "server": server}

    # ── wookiee-marketing ────────────────────────────────────────────────
    from agents.oleg.services.marketing_tools import MARKETING_TOOL_DEFINITIONS, MARKETING_TOOL_HANDLERS
    for tdef in MARKETING_TOOL_DEFINITIONS:
        name = tdef["function"]["name"]
        if name in MARKETING_TOOL_HANDLERS:
            registry[name] = {"handler": MARKETING_TOOL_HANDLERS[name], "definition": tdef, "server": "wookiee-marketing"}

    # ── wookiee-marketing funnel ─────────────────────────────────────────
    from agents.oleg.services.funnel_tools import FUNNEL_TOOL_DEFINITIONS, FUNNEL_TOOL_HANDLERS
    for tdef in FUNNEL_TOOL_DEFINITIONS:
        name = tdef["function"]["name"]
        if name in FUNNEL_TOOL_HANDLERS:
            registry[name] = {"handler": FUNNEL_TOOL_HANDLERS[name], "definition": tdef, "server": "wookiee-marketing"}

    # ── wookiee-kb ───────────────────────────────────────────────────────
    # KB tools use execute_kb_tool(tool_name, arguments) dispatcher — no HANDLERS dict.
    # Build per-tool async lambdas that forward to the dispatcher.
    from services.knowledge_base.tools import (
        KB_SEARCH_TOOL_DEFINITIONS,
        KB_MANAGE_TOOL_DEFINITIONS,
        execute_kb_tool,
    )
    for tdef in KB_SEARCH_TOOL_DEFINITIONS + KB_MANAGE_TOOL_DEFINITIONS:
        name = tdef["function"]["name"]
        # Capture name in default arg to avoid closure-over-loop-variable bug
        async def _kb_handler(_tool_name=name, **kwargs) -> str:
            return await execute_kb_tool(_tool_name, kwargs)
        registry[name] = {"handler": _kb_handler, "definition": tdef, "server": "wookiee-kb"}

    # ── wookiee-prompt-tuner ──────────────────────────────────────────────
    from agents.v3.prompt_tuner import PROMPT_TUNER_TOOL_DEFINITIONS, PROMPT_TUNER_TOOL_HANDLERS
    for tdef in PROMPT_TUNER_TOOL_DEFINITIONS:
        name = tdef["function"]["name"]
        if name in PROMPT_TUNER_TOOL_HANDLERS:
            registry[name] = {"handler": PROMPT_TUNER_TOOL_HANDLERS[name], "definition": tdef, "server": "wookiee-prompt-tuner"}

    return registry


# Lazy singleton
_TOOL_REGISTRY: Optional[dict] = None


def _get_registry() -> dict:
    global _TOOL_REGISTRY
    if _TOOL_REGISTRY is None:
        _TOOL_REGISTRY = _build_tool_registry()
    return _TOOL_REGISTRY


# ── MD file parser ──────────────────────────────────────────────────────

def parse_agent_md(md_path: Path) -> dict:
    """Parse agent MD file into structured config.

    Returns:
        {
            "name": str,
            "role": str,
            "rules": str,
            "mcp_tools": {server: [tool_names]},
            "output_format": str,
            "system_prompt": str (full MD content),
        }
    """
    content = md_path.read_text(encoding="utf-8")

    # Extract agent name from header
    name_match = re.search(r"^#\s+Agent:\s+(.+)$", content, re.MULTILINE)
    name = name_match.group(1).strip() if name_match else md_path.stem

    # Extract sections
    sections: dict[str, str] = {}
    current_section: Optional[str] = None
    current_lines: list[str] = []

    for line in content.split("\n"):
        header_match = re.match(r"^##\s+(.+)$", line)
        if header_match:
            if current_section:
                sections[current_section] = "\n".join(current_lines).strip()
            current_section = header_match.group(1).strip().lower()
            current_lines = []
        elif current_section is not None:
            current_lines.append(line)

    if current_section:
        sections[current_section] = "\n".join(current_lines).strip()

    # Parse MCP tools section: "- server_name: tool1, tool2, ..."
    mcp_tools: dict[str, list[str]] = {}
    tools_text = sections.get("mcp tools", "")
    for line in tools_text.split("\n"):
        match = re.match(r"^-\s+([\w-]+):\s+(.+)$", line.strip())
        if match:
            server = match.group(1)
            tools = [t.strip() for t in match.group(2).split(",")]
            mcp_tools[server] = tools

    return {
        "name": name,
        "role": sections.get("role", ""),
        "rules": sections.get("rules", ""),
        "mcp_tools": mcp_tools,
        "output_format": sections.get("output format", ""),
        "system_prompt": content,
    }


# ── Tool builder ────────────────────────────────────────────────────────

def _make_langchain_tool(name: str, entry: dict) -> StructuredTool:
    """Convert a tool registry entry to a LangChain StructuredTool."""
    func_def = entry["definition"]["function"]
    handler = entry["handler"]

    async def _invoke(**kwargs: Any) -> str:
        try:
            result = handler(**kwargs)
            if asyncio.iscoroutine(result):
                result = await result
            if isinstance(result, str):
                return result
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception as exc:
            return json.dumps({"error": str(exc), "tool": name})

    return StructuredTool.from_function(
        coroutine=_invoke,
        name=name,
        description=func_def.get("description", ""),
        args_schema=None,  # Accept **kwargs; LangChain will pass args by name
    )


def build_tools_for_agent(agent_config: dict) -> list:
    """Build LangChain tools for an agent based on its MD file MCP Tools section."""
    registry = _get_registry()
    tools = []

    for server, tool_names in agent_config["mcp_tools"].items():
        for tname in tool_names:
            if tname in registry:
                tools.append(_make_langchain_tool(tname, registry[tname]))
            else:
                logger.warning("Tool %s from server %s not found in registry", tname, server)

    return tools


# ── LLM factory ─────────────────────────────────────────────────────────

def get_llm(model: Optional[str] = None, temperature: float = 0.0) -> ChatOpenAI:
    """Create a ChatOpenAI instance via OpenRouter."""
    return ChatOpenAI(
        model=model or config.MODEL_MAIN,
        openai_api_key=config.OPENROUTER_API_KEY,
        openai_api_base=config.OPENROUTER_BASE_URL,
        temperature=temperature,
        default_headers={
            "HTTP-Referer": "https://wookiee.ru",
            "X-Title": "Wookiee Analytics v3",
        },
    )


# ── Agent execution ─────────────────────────────────────────────────────

async def run_agent(
    agent_name: str,
    task: str,
    model: Optional[str] = None,
    parent_run_id: Optional[str] = None,
    trigger: str = "orchestrator",
    task_type: Optional[str] = None,
    timeout: int = config.AGENT_TIMEOUT,
) -> dict:
    """Run a micro-agent by name.

    Loads the MD file, builds tools, creates LangGraph ReAct agent, executes.

    Returns:
        {
            "agent_name": str,
            "status": "success" | "failed" | "timeout",
            "artifact": Any (parsed JSON if possible),
            "raw_output": str,
            "duration_ms": int,
            "run_id": str,
        }
    """
    md_path = config.AGENTS_DIR / f"{agent_name}.md"
    if not md_path.exists():
        return {
            "agent_name": agent_name,
            "status": "failed",
            "artifact": None,
            "raw_output": f"Agent MD file not found: {md_path}",
            "duration_ms": 0,
            "run_id": "",
        }

    agent_config = parse_agent_md(md_path)
    tools = build_tools_for_agent(agent_config)
    llm = get_llm(model=model)

    # Build system prompt from parsed MD sections
    system_prompt = (
        f"You are {agent_config['name']}.\n\n"
        f"{agent_config['role']}\n\n"
        f"## Rules\n{agent_config['rules']}\n\n"
        f"## Output Format\n{agent_config['output_format']}\n\n"
        "IMPORTANT: Return your final answer as a valid JSON object matching the "
        "Output Format. Do not wrap it in markdown code blocks. Just return raw JSON."
    )

    # create_react_agent accepts prompt as str | SystemMessage | callable | Runnable
    agent = create_react_agent(llm, tools, prompt=system_prompt)

    run_id = new_run_id()
    started_at = datetime.now(timezone.utc)
    start_time = time.monotonic()

    raw_output: str = ""
    artifact: Any = None
    status: str = "success"
    error_message: Optional[str] = None

    try:
        result = await asyncio.wait_for(
            agent.ainvoke({"messages": [HumanMessage(content=task)]}),
            timeout=timeout,
        )

        duration_ms = int((time.monotonic() - start_time) * 1000)

        messages = result.get("messages", [])
        raw_output = messages[-1].content if messages else ""

        # Try to extract a JSON artifact from the output
        try:
            json_match = re.search(r"\{[\s\S]*\}", raw_output)
            if json_match:
                artifact = json.loads(json_match.group())
        except (json.JSONDecodeError, AttributeError):
            pass

    except asyncio.TimeoutError:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        raw_output = f"Agent timed out after {timeout}s"
        status = "timeout"
        error_message = raw_output

    except Exception as exc:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        raw_output = str(exc)
        status = "failed"
        error_message = str(exc)

    # Observability — fire-and-forget
    prompt_hash = compute_prompt_hash(agent_config["system_prompt"])
    asyncio.create_task(log_agent_run(
        run_id=run_id,
        agent_name=agent_name,
        agent_type="micro-agent",
        agent_version="1.0",
        status=status,
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
        duration_ms=duration_ms,
        error_message=error_message,
        model=model or config.MODEL_MAIN,
        system_prompt_hash=prompt_hash,
        user_input=task[:2000],
        output_summary=raw_output[:2000] if raw_output else None,
        artifact=artifact,
        task_type=task_type,
        trigger=trigger,
        parent_run_id=parent_run_id,
    ))

    return {
        "agent_name": agent_name,
        "status": status,
        "artifact": artifact,
        "raw_output": raw_output,
        "duration_ms": duration_ms,
        "run_id": run_id,
    }
