"""Christina v3 — Knowledge & Data Navigation Orchestrator.

Routes user queries to KB micro-agents based on detected intent:
  search   → kb-searcher   (find relevant knowledge)
  manage   → kb-curator    (add / update / delete / verify KB entries)
  audit    → kb-auditor    (coverage stats and gap analysis)
  navigate → data-navigator (where does data X live?)
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional, TypedDict

from agents.v3 import config
from agents.v3.runner import run_agent, get_llm
from services.observability.logger import log_orchestrator_run, new_run_id

logger = logging.getLogger(__name__)


# ── State ────────────────────────────────────────────────────────────────

class ChristinaState(TypedDict):
    """Shared state for Christina orchestrator."""
    intent: str   # "search" | "manage" | "audit" | "navigate"
    query: str
    run_id: str
    trigger: str
    artifacts: dict[str, Any]
    result: Optional[dict]


# ── Intent classifier ────────────────────────────────────────────────────

_INTENT_SYSTEM = (
    "You are an intent classifier for a knowledge base assistant.\n"
    "Given the user message, reply with EXACTLY one word (lowercase) from this list:\n"
    "  search   — user wants to find or look up knowledge\n"
    "  manage   — user wants to add, update, delete, or verify a KB entry\n"
    "  audit    — user wants coverage stats, gap analysis, or health check\n"
    "  navigate — user asks where a specific piece of data lives or which tool/server provides it\n"
    "Reply with only the single word. No punctuation. No explanation."
)

_VALID_INTENTS = frozenset({"search", "manage", "audit", "navigate"})


async def classify_intent(query: str) -> str:
    """Use a lightweight LLM call to classify user intent.

    Falls back to "search" if the model returns an unexpected value.
    """
    llm = get_llm(model=config.MODEL_LIGHT, temperature=0.0)
    response = await llm.ainvoke([
        {"role": "system", "content": _INTENT_SYSTEM},
        {"role": "user", "content": query},
    ])
    intent = response.content.strip().lower().split()[0] if response.content.strip() else ""
    if intent not in _VALID_INTENTS:
        logger.warning(
            "classify_intent: unexpected value %r for query %r — defaulting to 'search'",
            intent, query[:120],
        )
        intent = "search"
    return intent


# ── Agent routing map ────────────────────────────────────────────────────

_AGENT_MAP: dict[str, str] = {
    "search": "kb-searcher",
    "manage": "kb-curator",
    "audit": "kb-auditor",
    "navigate": "data-navigator",
}


# ── Main entry point ─────────────────────────────────────────────────────

async def run_christina(
    query: str,
    trigger: str = "manual",
    force_intent: Optional[str] = None,
) -> dict:
    """Route query to the appropriate KB micro-agent.

    Args:
        query:        User question or instruction.
        trigger:      How the run was initiated ("manual", "telegram", "cron", ...).
        force_intent: Skip classification and use this intent directly (for testing).

    Returns:
        {
            "run_id":       str,
            "intent":       str,
            "agent":        str,
            "status":       "success" | "failed" | "timeout",
            "result":       Any (parsed JSON artifact from the agent, or None),
            "raw_output":   str,
            "duration_ms":  int,
        }
    """
    run_id = new_run_id()
    started_at = datetime.now(timezone.utc)
    start_time = time.monotonic()

    # ── Classify intent ──
    if force_intent and force_intent in _VALID_INTENTS:
        intent = force_intent
        logger.info("run_christina [%s]: intent forced to %r", run_id, intent)
    else:
        intent = await classify_intent(query)
        logger.info("run_christina [%s]: classified intent=%r for query=%r", run_id, intent, query[:120])

    agent_name = _AGENT_MAP[intent]

    # ── Run micro-agent ──
    result = await run_agent(
        agent_name=agent_name,
        task=query,
        parent_run_id=run_id,
        trigger=trigger,
        task_type=f"christina_{intent}",
    )

    duration_ms = int((time.monotonic() - start_time) * 1000)
    status = result["status"]

    # ── Observability (fire-and-forget) ──
    asyncio.create_task(log_orchestrator_run(
        run_id=run_id,
        orchestrator="christina",
        orchestrator_version="3.0",
        task_type=f"christina_{intent}",
        trigger=trigger,
        status=status,
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
        duration_ms=duration_ms,
        agents_called=1,
        agents_succeeded=1 if status == "success" else 0,
        agents_failed=0 if status == "success" else 1,
        total_tokens=0,
        total_cost_usd=0.0,
    ))

    return {
        "run_id": run_id,
        "intent": intent,
        "agent": agent_name,
        "status": status,
        "result": result.get("artifact"),
        "raw_output": result.get("raw_output", ""),
        "duration_ms": duration_ms,
    }


# ── Convenience helpers ──────────────────────────────────────────────────

async def search_kb(query: str, trigger: str = "manual") -> dict:
    """Shortcut: run kb-searcher directly."""
    return await run_christina(query, trigger=trigger, force_intent="search")


async def audit_kb(trigger: str = "manual") -> dict:
    """Shortcut: run kb-auditor with a standard audit request."""
    return await run_christina(
        "Проведи полный аудит базы знаний: покрытие, свежесть, пробелы, рекомендации.",
        trigger=trigger,
        force_intent="audit",
    )


async def navigate_data(query: str, trigger: str = "manual") -> dict:
    """Shortcut: run data-navigator directly."""
    return await run_christina(query, trigger=trigger, force_intent="navigate")
