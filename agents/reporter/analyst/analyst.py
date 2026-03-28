# agents/reporter/analyst/analyst.py
"""Single-LLM analyst — the only point where LLM is called in the pipeline."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from agents.reporter.analyst.circuit_breaker import CircuitBreaker
from agents.reporter.analyst.schemas import ReportInsights
from agents.reporter.collector.base import CollectedData
from agents.reporter.config import (
    LLM_MAX_TOKENS,
    LLM_TIMEOUT,
    MODEL_FREE,
    MODEL_FALLBACK,
    MODEL_PRIMARY,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    PROMPTS_DIR,
    CB_FAILURE_THRESHOLD,
    CB_COOLDOWN_SEC,
)
from agents.reporter.types import ReportScope

logger = logging.getLogger(__name__)

_circuit_breaker = CircuitBreaker(
    failure_threshold=CB_FAILURE_THRESHOLD,
    cooldown_sec=CB_COOLDOWN_SEC,
)


async def _call_llm(
    messages: list[dict],
    model: str,
    max_tokens: int = LLM_MAX_TOKENS,
) -> dict[str, Any]:
    """Call OpenRouter via openai SDK. Returns {content, usage, model}."""
    import openai

    client = openai.AsyncOpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL,
    )
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=0.3,
        response_format={"type": "json_object"},
        timeout=LLM_TIMEOUT,
    )
    choice = response.choices[0]
    return {
        "content": choice.message.content or "",
        "usage": {
            "input_tokens": response.usage.prompt_tokens if response.usage else 0,
            "output_tokens": response.usage.completion_tokens if response.usage else 0,
        },
        "model": model,
    }


def _build_prompt(
    data: CollectedData,
    scope: ReportScope,
    playbook_rules: list[dict],
    retry_hint: list[str] | None = None,
) -> str:
    """Build the full prompt from template + data + rules."""
    # Load report-type-specific prompt
    prompt_file = PROMPTS_DIR / f"{scope.report_type.value}.md"
    if prompt_file.exists():
        template = prompt_file.read_text(encoding="utf-8")
    else:
        template = "Проанализируй данные и верни ReportInsights JSON."

    # Construct playbook section
    rules_text = ""
    if playbook_rules:
        rules_lines = [f"- {r.get('rule_text', '')}" for r in playbook_rules]
        rules_text = "\n## Правила анализа (Playbook)\n" + "\n".join(rules_lines)

    # Retry hint
    retry_text = ""
    if retry_hint:
        retry_text = (
            "\n## Замечания к предыдущей попытке\n"
            + "\n".join(f"- {h}" for h in retry_hint)
            + "\nИсправь указанные проблемы."
        )

    # JSON schema for structured output
    schema = json.dumps(ReportInsights.model_json_schema(), ensure_ascii=False, indent=2)

    prompt = f"""{template}

## Период
{scope.period_str}
Сравнение: {scope.comparison_from.isoformat()} — {scope.comparison_to.isoformat()}
Маркетплейс: {scope.marketplace}
{f'Модель: {scope.model}' if scope.model else ''}
{f'Артикул: {scope.article}' if scope.article else ''}

{rules_text}
{retry_text}

## Данные
```json
{data.model_dump_json(indent=2)}
```

## Формат ответа
Верни JSON, соответствующий этой схеме:
```json
{schema}
```

ВАЖНО:
- Все тексты на русском языке
- executive_summary: 3-5 предложений, ключевые выводы
- Заполни ВСЕ секции от 0 до 12 (для финансовых отчётов)
- Каждый root_cause должен содержать конкретные цифры в evidence
- discovered_patterns: только если нашёл неочевидную закономерность
"""
    return prompt


async def analyze(
    data: CollectedData,
    scope: ReportScope,
    playbook_rules: list[dict],
    retry_hint: list[str] | None = None,
) -> tuple[ReportInsights, dict]:
    """Run single LLM analysis. Returns (insights, meta).

    Meta: {model, input_tokens, output_tokens, cost_usd}
    Fallback chain: PRIMARY → retry → FALLBACK → FREE
    """
    prompt = _build_prompt(data, scope, playbook_rules, retry_hint)
    messages = [{"role": "user", "content": prompt}]

    models_to_try = [MODEL_PRIMARY, MODEL_PRIMARY, MODEL_FALLBACK, MODEL_FREE]
    last_error = None

    for model in models_to_try:
        if not _circuit_breaker.can_execute:
            logger.warning("Circuit breaker OPEN — skipping LLM call")
            raise RuntimeError("Circuit breaker is open — LLM calls suspended")

        try:
            result = await _call_llm(messages, model=model)
            content = result["content"]

            # Strip code fences if present
            if content.strip().startswith("```"):
                lines = content.strip().split("\n")
                content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

            insights = ReportInsights.model_validate_json(content)
            _circuit_breaker.record_success()

            meta = {
                "model": model,
                "input_tokens": result["usage"]["input_tokens"],
                "output_tokens": result["usage"]["output_tokens"],
            }
            logger.info(
                "Analysis complete: model=%s, confidence=%.2f, tokens_in=%d, tokens_out=%d",
                model, insights.overall_confidence,
                meta["input_tokens"], meta["output_tokens"],
            )
            return insights, meta

        except Exception as e:
            _circuit_breaker.record_failure()
            last_error = e
            logger.warning("LLM call failed (model=%s): %s", model, e)
            continue

    raise RuntimeError(f"All LLM models failed. Last error: {last_error}")
