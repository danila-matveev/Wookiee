"""
PromptTuner tools — tool handlers for the prompt-tuner micro-agent.

The agent (prompt-tuner.md) uses these tools to:
- Fetch Notion feedback comments
- Save/deactivate persistent instructions in StateStore
- Reply to Notion comments with confirmations

Instructions are stored as JSON arrays at keys `pi:{agent_name}` in StateStore.
The orchestrator pipeline reads them via load_persistent_instructions().
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from agents.v3 import config
from agents.v3.state import StateStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared state (lazy singletons, same pattern as scheduler.py)
# ---------------------------------------------------------------------------

_state: Optional[StateStore] = None
_notion = None


def _get_state() -> StateStore:
    global _state
    if _state is None:
        _state = StateStore(config.STATE_DB_PATH)
    return _state


def _get_notion():
    global _notion
    if _notion is None:
        from agents.v3.delivery.notion import NotionDelivery
        _notion = NotionDelivery(config.NOTION_TOKEN, config.NOTION_DATABASE_ID)
    return _notion


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

async def _handle_get_notion_feedback(days: int = 7) -> dict:
    """Fetch recent feedback comments from Notion report pages."""
    notion = _get_notion()
    if not notion.enabled:
        return {"error": "Notion not configured", "feedback": []}
    feedback = await notion.get_recent_feedback(days=days)
    return {"feedback": feedback, "total_pages": len(feedback)}


async def _handle_get_processed_comment_ids() -> dict:
    """Get list of already-processed comment IDs."""
    state = _get_state()
    raw = state.get("pt:processed_ids")
    if raw:
        try:
            ids = json.loads(raw)
            return {"processed_ids": ids, "count": len(ids)}
        except (json.JSONDecodeError, TypeError):
            pass
    return {"processed_ids": [], "count": 0}


async def _handle_save_instruction(
    agent_name: str,
    instruction: str,
    source_comment_id: str,
    source_page: str = "",
) -> dict:
    """Save a persistent instruction for a micro-agent.

    FIFO: if max instructions reached, oldest is deactivated.
    """
    state = _get_state()
    max_instructions = config.PROMPT_TUNER_MAX_INSTRUCTIONS
    key = f"pi:{agent_name}"

    raw = state.get(key)
    instructions: list[dict] = []
    if raw:
        try:
            instructions = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            instructions = []

    new_entry = {
        "instruction": instruction,
        "source_comment_id": source_comment_id,
        "source_page": source_page,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "active": True,
    }
    instructions.append(new_entry)

    # FIFO: deactivate oldest if over limit
    active = [i for i in instructions if i.get("active", True)]
    while len(active) > max_instructions:
        for i in instructions:
            if i.get("active", True):
                i["active"] = False
                break
        active = [i for i in instructions if i.get("active", True)]

    state.set(key, json.dumps(instructions, ensure_ascii=False))

    active_count = len([i for i in instructions if i.get("active")])
    return {
        "status": "saved",
        "agent_name": agent_name,
        "instruction": instruction,
        "active_instructions": active_count,
        "max_instructions": max_instructions,
    }


async def _handle_deactivate_instruction(
    agent_name: str,
    query: str,
) -> dict:
    """Deactivate a persistent instruction matching the query substring.

    Query must be at least 10 characters to prevent accidental deactivation.
    """
    state = _get_state()

    if len(query) < 10:
        return {"status": "error", "error": f"Query too short ({len(query)} chars), need at least 10"}

    key = f"pi:{agent_name}"
    raw = state.get(key)
    if not raw:
        return {"status": "not_found", "agent_name": agent_name}

    try:
        instructions = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {"status": "error", "error": "Corrupted instruction data"}

    query_lower = query.lower()
    for instr in instructions:
        if instr.get("active") and query_lower in instr.get("instruction", "").lower():
            instr["active"] = False
            state.set(key, json.dumps(instructions, ensure_ascii=False))
            return {
                "status": "deactivated",
                "agent_name": agent_name,
                "deactivated_instruction": instr["instruction"],
            }

    return {"status": "not_found", "agent_name": agent_name, "query": query}


async def _handle_reply_notion_comment(
    page_id: str,
    text: str,
) -> dict:
    """Post a reply comment on a Notion page."""
    notion = _get_notion()
    if not notion.enabled:
        return {"status": "skipped", "reason": "Notion not configured"}
    await notion.add_comment(page_id, text)
    return {"status": "posted", "page_id": page_id}


async def _handle_mark_comment_processed(comment_id: str) -> dict:
    """Mark a comment ID as processed so it won't be handled again."""
    state = _get_state()
    raw = state.get("pt:processed_ids")
    ids_list: list[str] = []
    if raw:
        try:
            ids_list = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            pass
    if comment_id not in ids_list:
        ids_list.append(comment_id)
    # Keep last 500 to prevent unbounded growth
    if len(ids_list) > 500:
        ids_list = ids_list[-500:]
    state.set("pt:processed_ids", json.dumps(ids_list))
    return {"status": "marked", "comment_id": comment_id}


async def _handle_get_active_instructions(agent_name: str = "") -> dict:
    """Get active instructions, optionally filtered by agent name.

    If agent_name is empty, returns all active instructions across all agents.
    """
    state = _get_state()

    if agent_name:
        raw = state.get(f"pi:{agent_name}")
        if not raw:
            return {"agent_name": agent_name, "instructions": [], "count": 0}
        try:
            instructions = json.loads(raw)
            active = [i for i in instructions if i.get("active", True)]
            return {"agent_name": agent_name, "instructions": active, "count": len(active)}
        except (json.JSONDecodeError, TypeError):
            return {"agent_name": agent_name, "instructions": [], "count": 0}

    # All agents
    all_instructions: dict[str, list] = {}
    # Scan known agent prefixes — StateStore doesn't support key listing,
    # so we check known agent names
    known_agents = [
        "margin-analyst", "revenue-decomposer", "ad-efficiency", "report-compiler",
        "campaign-optimizer", "organic-vs-paid", "funnel-digitizer", "keyword-analyst",
        "finolog-analyst",
    ]
    total = 0
    for name in known_agents:
        raw = state.get(f"pi:{name}")
        if not raw:
            continue
        try:
            instructions = json.loads(raw)
            active = [i for i in instructions if i.get("active", True)]
            if active:
                all_instructions[name] = active
                total += len(active)
        except (json.JSONDecodeError, TypeError):
            continue

    return {"instructions_by_agent": all_instructions, "total_active": total}


# ---------------------------------------------------------------------------
# Tool definitions (OpenAI function calling format)
# ---------------------------------------------------------------------------

PROMPT_TUNER_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_notion_feedback",
            "description": (
                "Fetch recent feedback comments from Notion report pages. "
                "Returns list of pages with their comments. Each comment has: id, text, created_time. "
                "Each page has: page_title, page_url, page_id, report_type, comments."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "How many days back to look for feedback (default: 7)",
                        "default": 7,
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_processed_comment_ids",
            "description": "Get list of comment IDs that have already been processed. Use this to skip comments you've already handled.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_instruction",
            "description": (
                "Save a persistent instruction for a micro-agent. The instruction will be injected "
                "into the agent's task context in every future report pipeline run. "
                "FIFO: if max instructions (10) reached, the oldest is automatically deactivated."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_name": {
                        "type": "string",
                        "description": (
                            "Target micro-agent name. One of: margin-analyst, revenue-decomposer, "
                            "ad-efficiency, report-compiler, campaign-optimizer, organic-vs-paid, "
                            "funnel-digitizer, keyword-analyst, finolog-analyst"
                        ),
                    },
                    "instruction": {
                        "type": "string",
                        "description": "The instruction text (1-2 sentences, actionable rule for the agent)",
                    },
                    "source_comment_id": {
                        "type": "string",
                        "description": "Notion comment ID that this instruction was extracted from",
                    },
                    "source_page": {
                        "type": "string",
                        "description": "Title of the Notion page where the comment was found",
                    },
                },
                "required": ["agent_name", "instruction", "source_comment_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "deactivate_instruction",
            "description": (
                "Deactivate (cancel) a persistent instruction matching the query substring. "
                "Use this when a comment contains a cancellation command like 'отмена: ...' "
                "Query must be at least 10 characters."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_name": {
                        "type": "string",
                        "description": "Target micro-agent name to search instructions in",
                    },
                    "query": {
                        "type": "string",
                        "description": "Substring to match against active instructions (min 10 chars)",
                    },
                },
                "required": ["agent_name", "query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reply_notion_comment",
            "description": (
                "Post a reply comment on a Notion page. Use to confirm that an instruction was saved "
                "or cancelled. Include: which agents, the instruction text, and cancellation syntax."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "page_id": {
                        "type": "string",
                        "description": "Notion page ID to post the comment on",
                    },
                    "text": {
                        "type": "string",
                        "description": "Comment text (max 2000 chars)",
                    },
                },
                "required": ["page_id", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mark_comment_processed",
            "description": "Mark a comment ID as processed. Call this for EVERY comment you handle (saved, skipped, or cancelled).",
            "parameters": {
                "type": "object",
                "properties": {
                    "comment_id": {
                        "type": "string",
                        "description": "Notion comment ID to mark as processed",
                    },
                },
                "required": ["comment_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_active_instructions",
            "description": "Get currently active persistent instructions. Optionally filter by agent name. Useful for reviewing what's already saved before adding new instructions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_name": {
                        "type": "string",
                        "description": "Filter by agent name. Leave empty to get all agents.",
                        "default": "",
                    },
                },
                "required": [],
            },
        },
    },
]


PROMPT_TUNER_TOOL_HANDLERS = {
    "get_notion_feedback": _handle_get_notion_feedback,
    "get_processed_comment_ids": _handle_get_processed_comment_ids,
    "save_instruction": _handle_save_instruction,
    "deactivate_instruction": _handle_deactivate_instruction,
    "reply_notion_comment": _handle_reply_notion_comment,
    "mark_comment_processed": _handle_mark_comment_processed,
    "get_active_instructions": _handle_get_active_instructions,
}
