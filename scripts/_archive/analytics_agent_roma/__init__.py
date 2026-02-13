"""
analytics-agent-roma — Рома, ИИ финансовый и бизнес-аналитик Wookiee.

Экспорт:
    prepare_data_context() — сборка data_context.json для LLM-анализа
"""

from scripts.analytics_agent_roma.context_builder import prepare_data_context

__all__ = ['prepare_data_context']
