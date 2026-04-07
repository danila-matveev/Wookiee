# scripts/familia_eval/agents/advisor.py
"""Advisor agent: synthesizes analysis into final decisions."""

import logging
import os

from shared.clients.openrouter_client import OpenRouterClient
from shared.config import OPENROUTER_API_KEY
from scripts.familia_eval.config import CONFIG

log = logging.getLogger(__name__)

PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "advisor.md")


async def run_advisor(
    scenarios_summary: str,
    mp_comparator_report: str,
    familia_expert_report: str,
) -> str:
    """Synthesize expert reports into final decisions.

    Args:
        scenarios_summary: JSON string with scenario data
        mp_comparator_report: MP Comparator output
        familia_expert_report: Familia Expert output

    Returns:
        Markdown report with decisions per article
    """
    with open(PROMPT_PATH) as f:
        system_prompt = f.read()

    system_prompt = system_prompt.replace("{mp_comparator_report}", mp_comparator_report)
    system_prompt = system_prompt.replace("{familia_expert_report}", familia_expert_report)
    system_prompt = system_prompt.replace("{scenarios_summary}", scenarios_summary)

    llm = OpenRouterClient(
        api_key=OPENROUTER_API_KEY,
        model=CONFIG["model_heavy"],
    )

    result = await llm.complete(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": (
                "Прими финальное решение по каждому артикулу. "
                "Сформируй отчёт с рекомендациями для байера Familia."
            )},
        ],
        temperature=0.3,
        max_tokens=12000,
    )

    log.info(
        "Advisor: %d input, %d output tokens, model: %s",
        result.get("usage", {}).get("input_tokens", 0),
        result.get("usage", {}).get("output_tokens", 0),
        result.get("model", "unknown"),
    )
    return result["content"]
