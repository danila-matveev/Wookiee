"""
Quality Agent tools — playbook R/W, feedback verification, history.
"""
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# =============================================================================
# TOOL DEFINITIONS
# =============================================================================

QUALITY_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "read_playbook",
            "description": "Прочитать текущий playbook.md — бизнес-правила анализа.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_playbook",
            "description": (
                "Добавить или обновить правило в playbook.md. "
                "Указать секцию и новый текст правила."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "section": {"type": "string", "description": "Секция playbook (напр. 'Аналитические правила')"},
                    "rule_text": {"type": "string", "description": "Текст нового/обновлённого правила"},
                },
                "required": ["section", "rule_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_feedback_history",
            "description": "История всех feedback с решениями Quality Agent.",
            "parameters": {
                "type": "object",
                "properties": {
                    "last_n": {"type": "integer", "description": "Количество последних записей", "default": 10},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_feedback_decision",
            "description": (
                "Записать решение по feedback: принято/отклонено/частично + обоснование."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "feedback_text": {"type": "string", "description": "Текст ОС"},
                    "decision": {"type": "string", "enum": ["accepted", "rejected", "partial"], "description": "Решение"},
                    "reasoning": {"type": "string", "description": "Обоснование решения"},
                    "playbook_update": {"type": "string", "description": "Что обновлено в playbook (если что-то)"},
                },
                "required": ["feedback_text", "decision", "reasoning"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "verify_claim",
            "description": (
                "Перепроверить утверждение из ОС через финансовые данные. "
                "Вызывает Reporter tools для верификации."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string", "description": "Утверждение для проверки"},
                    "start_date": {"type": "string", "description": "Период проверки YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "Конец периода YYYY-MM-DD"},
                    "channel": {"type": "string", "enum": ["wb", "ozon"], "description": "Канал"},
                },
                "required": ["claim", "start_date", "end_date"],
            },
        },
    },
]


# Playbook path (set by agent init)
_playbook_path: Optional[str] = None
_state_store = None


def set_playbook_path(path: str) -> None:
    global _playbook_path
    _playbook_path = path


def set_state_store(store) -> None:
    global _state_store
    _state_store = store


# =============================================================================
# TOOL HANDLERS
# =============================================================================

async def _handle_read_playbook() -> dict:
    """Read current playbook."""
    if not _playbook_path:
        return {"error": "Playbook path not configured"}
    path = Path(_playbook_path)
    if not path.exists():
        # Try v1 playbook
        v1_path = Path(_playbook_path).parent.parent / "oleg" / "playbook.md"
        if v1_path.exists():
            path = v1_path
        else:
            return {"error": "Playbook not found"}

    content = path.read_text(encoding="utf-8")
    return {
        "content": content[:8000],  # Truncate for LLM context
        "total_chars": len(content),
        "path": str(path),
    }


async def _handle_update_playbook(section: str, rule_text: str) -> dict:
    """Add or update a rule in playbook."""
    if not _playbook_path:
        return {"error": "Playbook path not configured"}
    path = Path(_playbook_path)
    if not path.exists():
        return {"error": "Playbook not found"}

    content = path.read_text(encoding="utf-8")

    # Find section and append rule
    section_marker = f"## {section}"
    if section_marker in content:
        # Append after section header
        idx = content.index(section_marker) + len(section_marker)
        # Find end of section header line
        next_newline = content.index("\n", idx)
        content = (
            content[:next_newline + 1]
            + f"\n{rule_text}\n"
            + content[next_newline + 1:]
        )
    else:
        # Create new section at end
        content += f"\n\n{section_marker}\n\n{rule_text}\n"

    path.write_text(content, encoding="utf-8")
    logger.info(f"Playbook updated: section='{section}', rule='{rule_text[:100]}'")

    return {
        "status": "updated",
        "section": section,
        "rule_added": rule_text,
    }


async def _handle_read_feedback_history(last_n: int = 10) -> dict:
    """Read feedback history from state store."""
    if not _state_store:
        return {"history": [], "note": "State store not initialized"}

    history = _state_store.get_feedback_history(last_n=last_n)
    return {
        "total": len(history),
        "history": history,
    }


async def _handle_log_feedback_decision(
    feedback_text: str, decision: str, reasoning: str,
    playbook_update: str = "",
) -> dict:
    """Log a feedback decision."""
    if _state_store:
        _state_store.log_feedback(
            user_id=0,
            feedback_text=feedback_text,
            decision=decision,
            reasoning=reasoning,
            playbook_update=playbook_update,
        )

    return {
        "status": "logged",
        "decision": decision,
        "reasoning": reasoning,
    }


async def _handle_verify_claim(
    claim: str, start_date: str, end_date: str, channel: str = "wb",
) -> dict:
    """Verify a claim using financial data."""
    from agents.oleg.services.agent_tools import (
        _handle_brand_finance,
        _handle_channel_finance,
        _handle_margin_levers,
    )

    # Get relevant data to verify the claim
    brand_data = await _handle_brand_finance(start_date, end_date)
    channel_data = await _handle_channel_finance(channel, start_date, end_date)
    levers = await _handle_margin_levers(channel, start_date, end_date)

    return {
        "claim": claim,
        "verification_data": {
            "brand": brand_data,
            "channel": channel_data,
            "levers": levers,
        },
        "note": "Данные для верификации утверждения. Сопоставь с ОС.",
    }


# =============================================================================
# REGISTRY
# =============================================================================

QUALITY_TOOL_HANDLERS = {
    "read_playbook": _handle_read_playbook,
    "update_playbook": _handle_update_playbook,
    "read_feedback_history": _handle_read_feedback_history,
    "log_feedback_decision": _handle_log_feedback_decision,
    "verify_claim": _handle_verify_claim,
}


async def execute_quality_tool(tool_name: str, tool_args: dict) -> str:
    """Execute a quality tool."""
    handler = QUALITY_TOOL_HANDLERS.get(tool_name)
    if not handler:
        return json.dumps({"error": f"Unknown tool: {tool_name}"}, ensure_ascii=False)
    try:
        result = await handler(**tool_args)
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"error": f"Tool {tool_name} failed: {e}"}, ensure_ascii=False)
