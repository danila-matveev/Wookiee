"""Validator Agent tool definitions and executor."""
import json
from agents.oleg.agents.validator.scripts.check_numbers import check_numbers
from agents.oleg.agents.validator.scripts.check_coverage import check_coverage
from agents.oleg.agents.validator.scripts.check_direction import check_direction
from agents.oleg.agents.validator.scripts.check_kb_rules import check_kb_rules

VALIDATOR_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "validate_numbers",
            "description": "Проверить, что числа в рекомендации совпадают с данными сигнала",
            "parameters": {
                "type": "object",
                "properties": {
                    "signal_data": {"type": "object", "description": "signal.data dict"},
                    "recommendation": {"type": "object", "description": "recommendation dict"},
                },
                "required": ["signal_data", "recommendation"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_coverage",
            "description": "Проверить, что все warning/critical сигналы покрыты рекомендациями",
            "parameters": {
                "type": "object",
                "properties": {
                    "signals": {"type": "array", "description": "Массив сигналов"},
                    "recommendations": {"type": "array", "description": "Массив рекомендаций"},
                },
                "required": ["signals", "recommendations"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_direction",
            "description": "Проверить, что направление действия допустимо для данного типа сигнала",
            "parameters": {
                "type": "object",
                "properties": {
                    "signal_type": {"type": "string"},
                    "action_category": {"type": "string"},
                },
                "required": ["signal_type", "action_category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_kb_rules",
            "description": "Проверить, что рекомендация не конфликтует с правилами из KB",
            "parameters": {
                "type": "object",
                "properties": {
                    "recommendation": {"type": "object"},
                    "kb_patterns": {"type": "array"},
                },
                "required": ["recommendation", "kb_patterns"],
            },
        },
    },
]


async def execute_validator_tool(tool_name: str, tool_args: dict) -> str:
    if tool_name == "validate_numbers":
        result = check_numbers(tool_args["signal_data"], tool_args["recommendation"])
    elif tool_name == "validate_coverage":
        result = check_coverage(tool_args["signals"], tool_args["recommendations"])
    elif tool_name == "validate_direction":
        result = check_direction(tool_args["signal_type"], tool_args["action_category"])
    elif tool_name == "validate_kb_rules":
        result = check_kb_rules(tool_args["recommendation"], tool_args["kb_patterns"])
    else:
        result = {"error": f"Unknown tool: {tool_name}"}

    return json.dumps(result, ensure_ascii=False)
