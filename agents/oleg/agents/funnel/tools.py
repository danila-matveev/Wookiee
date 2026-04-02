"""
Funnel Agent tools — build_funnel_report generates the complete report
in Python (no LLM formatting needed for 14 models).

Primary workflow: call build_funnel_report → get formatted MD report.
Individual tools available for deeper drill-down if needed.
"""
import json
import logging

from agents.oleg.services.funnel_tools import (
    FUNNEL_TOOL_DEFINITIONS as _INDIVIDUAL_TOOLS,
    execute_funnel_tool as _execute_individual,
    get_all_models_funnel_bundle,
)
from agents.oleg.agents.funnel.report_builder import build_funnel_report

logger = logging.getLogger(__name__)

# Knowledge Base tool (optional)
_kb_available = False
try:
    from services.knowledge_base.tools import KB_TOOL_DEFINITIONS, execute_kb_tool
    _kb_available = True
except ImportError:
    KB_TOOL_DEFINITIONS = []
    logger.info("Knowledge Base tools not available for Funnel")

# ---------------------------------------------------------------------------
# Main tool — fetches data + formats complete report
# ---------------------------------------------------------------------------

_BUILD_REPORT_TOOL = {
    "type": "function",
    "function": {
        "name": "build_funnel_report",
        "description": (
            "Формирует ПОЛНЫЙ отчёт воронки по ВСЕМ моделям бренда. "
            "Загружает данные из базы, форматирует таблицы, генерирует гипотезы. "
            "Возвращает готовый отчёт в формате telegram_summary + brief_summary + detailed_report. "
            "Вызови ПЕРВЫМ И ЕДИНСТВЕННЫМ — возвращает финальный результат."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "Начало периода YYYY-MM-DD",
                },
                "end_date": {
                    "type": "string",
                    "description": "Конец периода YYYY-MM-DD (включительно)",
                },
            },
            "required": ["start_date", "end_date"],
        },
    },
}

# Export: build_report first, then individual tools for drill-down, then KB
FUNNEL_AGENT_TOOL_DEFINITIONS = (
    [_BUILD_REPORT_TOOL]
    + list(_INDIVIDUAL_TOOLS)
    + list(KB_TOOL_DEFINITIONS)
)


async def execute_funnel_agent_tool(tool_name: str, tool_args: dict) -> str:
    """Execute a funnel agent tool."""
    if tool_name == "build_funnel_report":
        try:
            start_date = tool_args["start_date"]
            end_date = tool_args["end_date"]
            bundle = await get_all_models_funnel_bundle(
                start_date=start_date,
                end_date=end_date,
            )
            result = build_funnel_report(bundle, start_date, end_date)
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"build_funnel_report error: {e}", exc_info=True)
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    if _kb_available and tool_name == "search_knowledge_base":
        return await execute_kb_tool(tool_name, tool_args)

    return await _execute_individual(tool_name, tool_args)
