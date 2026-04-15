# scripts/familia_eval/agents/familia_expert.py
"""Familia Expert agent: analyzes hidden costs and contract risks."""

import logging
import os

from shared.clients.openrouter_client import OpenRouterClient
from shared.config import OPENROUTER_API_KEY
from scripts.familia_eval.config import CONFIG

log = logging.getLogger(__name__)

PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "familia_expert.md")
CONTRACT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "contract_summary.md")
CONDITIONS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "supply_conditions.md")


async def run_familia_expert(scenarios: list) -> str:
    """Analyze hidden costs and risks of working with Familia.

    Args:
        scenarios: list of article dicts with 'scenarios' key from Calculator

    Returns:
        LLM response text (JSON with risk assessment)
    """
    with open(PROMPT_PATH) as f:
        system_prompt = f.read()
    with open(CONTRACT_PATH) as f:
        contract = f.read()
    with open(CONDITIONS_PATH) as f:
        conditions = f.read()

    system_prompt = system_prompt.replace("{contract_summary}", contract)
    system_prompt = system_prompt.replace("{supply_conditions}", conditions)

    summary = _build_scenarios_summary(scenarios)
    system_prompt = system_prompt.replace("{scenarios_summary}", summary)

    llm = OpenRouterClient(
        api_key=OPENROUTER_API_KEY,
        model=CONFIG["model_main"],
    )

    result = await llm.complete(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Проанализируй скрытые расходы и риски для этой поставки."},
        ],
        temperature=0.3,
        max_tokens=6000,
    )

    log.info(
        "Familia Expert: %d input, %d output tokens",
        result.get("usage", {}).get("input_tokens", 0),
        result.get("usage", {}).get("output_tokens", 0),
    )
    return result["content"]


def _build_scenarios_summary(scenarios: list) -> str:
    """Compact summary of articles for expert context."""
    total_stock = sum(a["stock_moysklad"] for a in scenarios)
    total_value = sum(a["stock_moysklad"] * a["rrc"] for a in scenarios)
    models = set(a["model"] for a in scenarios)

    lines = [
        f"Всего артикулов: {len(scenarios)}",
        f"Моделей: {len(models)} ({', '.join(sorted(models))})",
        f"Общий сток: {total_stock} шт",
        f"Общая стоимость по РРЦ: {total_value:,.0f} руб",
        "",
        "Артикулы:",
    ]
    for a in scenarios:
        lines.append(
            f"- {a['article']}: {a['stock_moysklad']} шт, "
            f"РРЦ {a['rrc']}₽, COGS {a['cogs_per_unit']}₽, "
            f"оборачиваемость {a['turnover_days']}д"
        )
    return "\n".join(lines)
