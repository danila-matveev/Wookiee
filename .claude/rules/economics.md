<important if="adding LLM calls, choosing models, or configuring AI agents">
Единый провайдер: OpenRouter. Все LLM-вызовы через OpenRouter API. Нет прямых подключений к провайдерам.

3 тира моделей:
- LIGHT (google/gemini-3-flash-preview, $0.50/$3.00) — классификация, intent, роутинг
- MAIN (google/gemini-3-flash-preview, $0.50/$3.00) — аналитика, tool-use, отчёты
- HEAVY (anthropic/claude-sonnet-4-6, $3/$15) — сложный reasoning, fallback
- FREE (openrouter/free, $0) — last-resort

Стратегия: MAIN → retry 1x → HEAVY → FREE.
Confidence > 0.8 на MAIN — не эскалировать.
</important>

- При добавлении нового агента — оценить стоимость на 1000 запросов и зафиксировать в AGENT_SPEC.md.
