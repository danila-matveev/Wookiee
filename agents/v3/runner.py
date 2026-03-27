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

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
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

def _json_type_to_python(json_type: str) -> type:
    """Map JSON Schema type to Python type for Pydantic."""
    return {"string": str, "integer": int, "number": float, "boolean": bool}.get(json_type, str)


def _build_args_schema(name: str, func_def: dict):
    """Build a Pydantic model from OpenAI function calling parameters."""
    from pydantic import BaseModel, Field

    params = func_def.get("parameters", {})
    properties = params.get("properties", {})
    required_fields = set(params.get("required", []))

    if not properties:
        return None

    field_definitions: dict[str, Any] = {}
    for field_name, field_spec in properties.items():
        field_type = _json_type_to_python(field_spec.get("type", "string"))
        description = field_spec.get("description", "")
        default = field_spec.get("default")

        if field_name in required_fields:
            field_definitions[field_name] = (field_type, Field(description=description))
        elif default is not None:
            field_definitions[field_name] = (field_type, Field(default=default, description=description))
        else:
            field_definitions[field_name] = (Optional[field_type], Field(default=None, description=description))

    # Dynamically create a Pydantic model
    schema_name = "".join(part.capitalize() for part in name.split("_")) + "Input"
    model = type(schema_name, (BaseModel,), {"__annotations__": {k: v[0] for k, v in field_definitions.items()}, **{k: v[1] for k, v in field_definitions.items()}})
    return model


def _make_langchain_tool(name: str, entry: dict) -> StructuredTool:
    """Convert a tool registry entry to a LangChain StructuredTool."""
    func_def = entry["definition"]["function"]
    handler = entry["handler"]

    args_schema = _build_args_schema(name, func_def)

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
        args_schema=args_schema,
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


# ── Token usage helpers ──────────────────────────────────────────────────

def extract_token_usage(messages: list) -> dict[str, int]:
    """Sum token usage from all AIMessages in a LangGraph result."""
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for msg in messages:
        if isinstance(msg, AIMessage) and hasattr(msg, "response_metadata"):
            token_usage = msg.response_metadata.get("token_usage", {})
            usage["prompt_tokens"] += token_usage.get("prompt_tokens", 0)
            usage["completion_tokens"] += token_usage.get("completion_tokens", 0)
            usage["total_tokens"] += token_usage.get("total_tokens", 0)
    return usage


def sanitize_meta(meta: dict) -> None:
    """Enforce sanity rules on _meta block (mutates in place)."""
    coverage = meta.get("data_coverage", 1.0)
    confidence = meta.get("confidence", 0.0)
    if coverage < 0.5 and confidence > 0.6:
        meta["confidence"] = min(confidence, 0.5)
        meta.setdefault("limitations", []).append(
            "confidence снижен автоматически: data_coverage < 50%"
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
    # Use dedicated compiler model for report-compiler (better format compliance)
    effective_model = model
    if not effective_model and agent_name == "report-compiler":
        effective_model = config.MODEL_COMPILER
    llm = get_llm(model=effective_model)

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
    usage: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    cost_usd: float = 0.0

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
            # Strategy 1: Try parsing the entire output as JSON
            stripped = raw_output.strip()
            if stripped.startswith("{"):
                try:
                    artifact = json.loads(stripped)
                except json.JSONDecodeError:
                    pass

            # Strategy 2: Strip code fence wrapper and parse
            if artifact is None:
                fence_match = re.match(
                    r"^\s*```(?:json)?\s*\n?([\s\S]*?)\n?\s*```\s*$",
                    stripped,
                )
                if fence_match:
                    inner = fence_match.group(1).strip()
                    try:
                        artifact = json.loads(inner)
                    except json.JSONDecodeError:
                        pass

            # Strategy 3: Find first { and match to last }
            if artifact is None:
                first_brace = raw_output.find("{")
                last_brace = raw_output.rfind("}")
                if first_brace >= 0 and last_brace > first_brace:
                    candidate = raw_output[first_brace:last_brace + 1]
                    try:
                        artifact = json.loads(candidate)
                    except json.JSONDecodeError:
                        pass
        except (json.JSONDecodeError, AttributeError):
            pass

        if artifact is None and raw_output:
            logger.warning(
                "run_agent[%s]: could not extract JSON artifact from output (%d chars)",
                agent_name, len(raw_output),
            )

        # Sanitize _meta if present
        if artifact and isinstance(artifact, dict) and "_meta" in artifact:
            sanitize_meta(artifact["_meta"])

        # Token usage & cost
        usage = extract_token_usage(result.get("messages", []))
        model_used = effective_model or config.MODEL_MAIN
        cost_usd = config.calc_cost(model_used, usage["prompt_tokens"], usage["completion_tokens"])

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
        prompt_tokens=usage["prompt_tokens"],
        completion_tokens=usage["completion_tokens"],
        total_tokens=usage["total_tokens"],
        cost_usd=cost_usd,
    ))

    return {
        "agent_name": agent_name,
        "status": status,
        "artifact": artifact,
        "raw_output": raw_output,
        "duration_ms": duration_ms,
        "run_id": run_id,
        "prompt_tokens": usage["prompt_tokens"],
        "completion_tokens": usage["completion_tokens"],
        "total_tokens": usage["total_tokens"],
        "cost_usd": cost_usd,
    }
