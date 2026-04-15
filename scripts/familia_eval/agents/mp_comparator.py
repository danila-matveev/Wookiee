# scripts/familia_eval/agents/mp_comparator.py
"""MP Comparator agent: compares Familia vs WB/OZON for each article."""

import json
import logging
import os

from shared.clients.openrouter_client import OpenRouterClient
from shared.config import OPENROUTER_API_KEY
from scripts.familia_eval.config import CONFIG

log = logging.getLogger(__name__)

PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "mp_comparator.md")


async def run_mp_comparator(scenarios: list) -> str:
    """Analyze each article: Familia vs MP profitability.

    Args:
        scenarios: list of article dicts with 'scenarios' key from Calculator

    Returns:
        LLM response text (JSON with verdicts)
    """
    with open(PROMPT_PATH) as f:
        system_prompt = f.read()

    data_summary = _build_summary(scenarios)

    llm = OpenRouterClient(
        api_key=OPENROUTER_API_KEY,
        model=CONFIG["model_main"],
    )

    result = await llm.complete(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Вот данные для анализа:\n\n```json\n{data_summary}\n```"},
        ],
        temperature=0.3,
        max_tokens=8000,
    )

    log.info(
        "MP Comparator: %d input, %d output tokens",
        result.get("usage", {}).get("input_tokens", 0),
        result.get("usage", {}).get("output_tokens", 0),
    )
    return result["content"]


def _build_summary(scenarios: list) -> str:
    """Build compact JSON summary for LLM (drop unnecessary fields)."""
    compact = []
    for art in scenarios:
        compact.append({
            "article": art["article"],
            "model": art["model"],
            "status": art["status"],
            "stock": art["stock_moysklad"],
            "cogs": art["cogs_per_unit"],
            "rrc": art["rrc"],
            "daily_sales_mp": art["daily_sales_mp"],
            "turnover_days": art["turnover_days"],
            "margin_pct_mp": art["margin_pct_mp"],
            "drr_pct": art["drr_pct"],
            "breakeven_discount": art["breakeven_discount"],
            "scenarios": [
                {
                    "discount": s["discount"],
                    "price": s["price"],
                    "margin": s["margin"],
                    "margin_pct": s["margin_pct"],
                    "delta": s["delta"],
                }
                for s in art["scenarios"]
            ],
        })
    return json.dumps(compact, ensure_ascii=False, indent=2)
